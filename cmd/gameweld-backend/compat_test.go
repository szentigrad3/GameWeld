package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestCompatibilityMissing(t *testing.T) {
	r := inspectCompatibility([]string{t.TempDir()})
	if r.State != "not_found" || r.Verified || len(r.Candidates) != 0 {
		t.Fatalf("unexpected: %+v", r)
	}
}
func fixtureCompatibility(t *testing.T) (string, string) {
	t.Helper()
	lib := t.TempDir()
	dir := filepath.Join(lib, "compatibilitytools.d", pc2CompatToolID)
	if err := os.MkdirAll(dir, 0700); err != nil { t.Fatal(err) }
	for name, file := range map[string]string{
		"proton": "#!/bin/sh\nexit 0\n",
		"compatibilitytool.vdf": `"compat_tools" { "GE-Proton-Wand-SHA256" { "install_path" "." } }`,
		"WAND-HYBRID.json": `{"schema":1,"tool_id":"GE-Proton-Wand-SHA256","base_proton":"/fixture/GE-Proton"}`,
	} {
		mode := os.FileMode(0600)
		if name == "proton" { mode = 0700 }
		if err := os.WriteFile(filepath.Join(dir, name), []byte(file), mode); err != nil { t.Fatal(err) }
	}
	return lib, dir
}
func TestCompatibilityDetectedButNeverVerified(t *testing.T) {
	lib, dir := fixtureCompatibility(t)
	r := inspectCompatibility([]string{lib, lib})
	if r.State != "detected_unverified" || r.Verified || len(r.Candidates) != 1 {
		t.Fatalf("unexpected: %+v", r)
	}
	if r.Candidates[0].Path != dir || !r.Candidates[0].HasProton || !r.Candidates[0].HasManifest || !r.Candidates[0].HasMetadata { t.Fatal(r.Candidates) }
}
func TestCompatibilityIncompleteAndDoesNotWrite(t *testing.T) {
	lib, dir := fixtureCompatibility(t)
	meta := filepath.Join(dir, "WAND-HYBRID.json")
	if err := os.WriteFile(meta, []byte(`{"schema":1,"tool_id":"OTHER","base_proton":"/fake"}`), 0600); err != nil { t.Fatal(err) }
	before, err := os.ReadFile(meta)
	if err != nil { t.Fatal(err) }
	r := inspectCompatibility([]string{lib})
	after, err := os.ReadFile(meta)
	if err != nil { t.Fatal(err) }
	if r.State != "incomplete" || r.Verified || string(before) != string(after) { t.Fatalf("unexpected result %+v", r) }
}
func TestCompatibilitySymlinkToolNotFollowed(t *testing.T) {
	lib, dir := fixtureCompatibility(t)
	other := t.TempDir()
	dest := filepath.Join(other, "compatibilitytools.d")
	if err := os.MkdirAll(dest, 0700); err != nil { t.Fatal(err) }
	if err := os.Symlink(dir, filepath.Join(dest, pc2CompatToolID)); err != nil { t.Fatal(err) }
	r := inspectCompatibility([]string{other, lib})
	if len(r.Candidates) != 1 || r.Candidates[0].Path != dir { t.Fatalf("symlink followed: %+v", r) }
}

func TestCompatibilityEndpointIsReadOnlyAndUnverified(t *testing.T) {
    lib, _ := fixtureCompatibility(t)
    t.Setenv("STEAM_ROOT", lib)
    t.Setenv("HOME", t.TempDir())
    code, response := req(t, "GET", "/api/compatibility")
    if code != 200 || !response.OK { t.Fatalf("request failed: %d %#v", code, response) }
    data, ok := response.Data.(map[string]any)
    if !ok { t.Fatalf("unexpected payload: %#v", response.Data) }
    if data["mode"] != "read_only" || data["verified"] != false || data["state"] != "detected_unverified" {
        t.Fatalf("incorrect verification claim: %#v", data)
    }
}

func TestMetadataConditionDiagnostics(t *testing.T) {
    _, dir := fixtureCompatibility(t)
    path := filepath.Join(dir, "WAND-HYBRID.json")
    cases := []struct {
        name string
        raw string
        state string
        valid bool
        remove bool
    }{
        {"valid", `{"schema":1,"tool_id":"GE-Proton-Wand-SHA256","base_proton":"/example"}`, "valid_metadata_only", true, false},
        {"missing", "", "missing", false, true},
        {"empty", "", "empty", false, false},
        {"invalid_json", "garbled", "invalid_json", false, false},
        {"invalid_schema", `{"schema":2,"tool_id":"GE-Proton-Wand-SHA256","base_proton":"/example"}`, "invalid_schema", false, false},
        {"unexpected_tool", `{"schema":1,"tool_id":"other","base_proton":"/example"}`, "unexpected_tool_id", false, false},
        {"missing_base", `{"schema":1,"tool_id":"GE-Proton-Wand-SHA256","base_proton":" "}`, "missing_base_proton", false, false},
    }
    for _, tc := range cases {
        t.Run(tc.name,func(t *testing.T){
            if tc.remove {
                if err := os.Remove(path); err != nil { t.Fatal(err) }
            } else {
                if err := os.WriteFile(path, []byte(tc.raw), 0600); err != nil { t.Fatal(err) }
            }
            state, ok := metadataCondition(path)
            if state != tc.state || ok != tc.valid { t.Fatalf("state %q valid %v; want %q %v",state,ok,tc.state,tc.valid) }
            if !tc.remove {
                after, err := os.ReadFile(path)
                if err != nil || string(after) != tc.raw { t.Fatal("inspector altered source") }
            }
        })
    }
}
func TestMetadataConditionRejectsSymlink(t *testing.T) {
    _, dir := fixtureCompatibility(t)
    path := filepath.Join(dir,"WAND-HYBRID.json")
    if err := os.Remove(path); err != nil { t.Fatal(err) }
    outside := filepath.Join(t.TempDir(),"metadata.json")
    if err := os.WriteFile(outside, []byte("{}"),0600); err != nil { t.Fatal(err) }
    if err := os.Symlink(outside,path); err != nil { t.Fatal(err) }
    state, ok := metadataCondition(path)
    if ok || state != "not_regular" { t.Fatalf("symlink followed: %v %v",state,ok) }
}

func TestLegacyMetadataMissingIsNotBrokenOrHealthy(t *testing.T) {
    lib, dir := fixtureCompatibility(t)
    if err := os.Remove(filepath.Join(dir,"WAND-HYBRID.json")); err != nil { t.Fatal(err) }
    r := inspectCompatibility([]string{lib})
    if r.State != "legacy_metadata_missing" || r.Verified || len(r.Candidates) != 1 {
        t.Fatalf("expected legacy unverified state: %+v",r)
    }
    c := r.Candidates[0]
    if c.MetadataState != "missing" || c.HasMetadata || !c.HasProton || !c.HasManifest {
        t.Fatalf("invalid legacy evidence %+v", c)
    }
    t.Setenv("HOME",t.TempDir())
    t.Setenv("STEAM_ROOT",lib)
    code, payload := req(t,"GET","/api/status")
    if code != 200 { t.Fatal(code) }
    status, ok := payload.Data.(map[string]any)
    if !ok || status["wand_installed"] != false || status["wand_healthy"] != false || status["base_compatible"] != false {
        t.Fatalf("status prematurely enabled provider: %#v", status)
    }
    if status["wand_tool"] != dir {
        t.Fatalf("legacy tool not discovered: %#v", status["wand_tool"])
    }
}
