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
