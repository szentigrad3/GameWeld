package main

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// PC2 inspects only existing compatibility-tool metadata.
// A Proton executable does not prove that patched DLL hashes match.
const pc2CompatToolID = "GE-Proton-Wand-SHA256"
const pc2CompatMaxMeta = 64 << 10

type compatibilityCandidate struct {
	Path        string `json:"path"`
	State       string `json:"state"`
	HasProton   bool   `json:"has_proton"`
	HasManifest bool   `json:"has_manifest"`
	HasMetadata bool   `json:"has_metadata"`
	MetadataState string `json:"metadata_state"`
}

type compatibilityReport struct {
	Mode       string                   `json:"mode"`
	ToolID     string                   `json:"tool_id"`
	State      string                   `json:"state"`
	Verified   bool                     `json:"verified"`
	Candidates []compatibilityCandidate `json:"candidates"`
	Message    string                   `json:"message"`
}

func regularSmall(path string) []byte {
	st, err := os.Lstat(path)
	if err != nil || !st.Mode().IsRegular() || st.Size() <= 0 || st.Size() > pc2CompatMaxMeta {
		return nil
	}
	b, err := os.ReadFile(path)
	if err != nil || len(b) > pc2CompatMaxMeta {
		return nil
	}
	return b
}

// metadataCondition inspects only local metadata and never writes, follows a
// download URL, or executes an installed Proton runner. Never expose file bytes.
func metadataCondition(path string) (string, bool) {
	st, err := os.Lstat(path)
	if errors.Is(err, os.ErrNotExist) { return "missing", false }
	if err != nil { return "unreadable", false }
	if !st.Mode().IsRegular() { return "not_regular", false }
	if st.Size() == 0 { return "empty", false }
	if st.Size() > pc2CompatMaxMeta { return "too_large", false }
	raw, err := os.ReadFile(path)
	if err != nil { return "unreadable", false }
	var metadata struct {
		Schema int `json:"schema"`
		ToolID string `json:"tool_id"`
		BaseProton string `json:"base_proton"`
	}
	if json.Unmarshal(raw, &metadata) != nil { return "invalid_json", false }
	if metadata.Schema != 1 { return "invalid_schema", false }
	if metadata.ToolID != pc2CompatToolID { return "unexpected_tool_id", false }
	if strings.TrimSpace(metadata.BaseProton) == "" { return "missing_base_proton", false }
	return "valid_metadata_only", true
}

func inspectCompatibility(libraries []string) compatibilityReport {
	result := compatibilityReport{
		Mode: "read_only", ToolID: pc2CompatToolID,
		State: "not_found", Verified: false,
		Candidates: []compatibilityCandidate{},
		Message: "Wand Proton compatibility tool not detected (nothing was modified)",
	}
	seen := map[string]bool{}
	for _, root := range libraries {
		if root == "" { continue }
		path := filepath.Join(root, "compatibilitytools.d", pc2CompatToolID)
		st, err := os.Lstat(path)
		if err != nil || !st.IsDir() { continue }
		realRoot, err := filepath.Abs(path)
		if err != nil || seen[realRoot] { continue }
		seen[realRoot] = true
		candidate := compatibilityCandidate{Path: realRoot, State: "incomplete"}
		p, err := os.Stat(filepath.Join(path, "proton"))
		candidate.HasProton = err == nil && p.Mode().IsRegular() && p.Mode()&0111 != 0
		manifest := regularSmall(filepath.Join(path, "compatibilitytool.vdf"))
		candidate.HasManifest = strings.Contains(string(manifest), `"`+pc2CompatToolID+`"`)
		candidate.MetadataState, candidate.HasMetadata = metadataCondition(filepath.Join(path, "WAND-HYBRID.json"))
		if candidate.HasProton && candidate.HasManifest {
			switch {
			case candidate.HasMetadata:
				candidate.State = "detected_unverified"
			case candidate.MetadataState == "missing":
				// Older installations can work without a GameWeld-created sidecar.
				// Do not mark them healthy or trigger a reinstall.
				candidate.State = "legacy_metadata_missing"
			}
		}
		result.Candidates = append(result.Candidates, candidate)
	}
	sort.Slice(result.Candidates, func(i, j int) bool { return result.Candidates[i].Path < result.Candidates[j].Path })
	if len(result.Candidates) > 0 {
		result.State = "incomplete"
		result.Message = "Wand Proton directory found but metadata is incomplete; no verification or changes performed"
		for _, candidate := range result.Candidates {
			if candidate.State == "detected_unverified" {
				result.State = "detected_unverified"
				result.Message = "Wand Proton metadata detected; DLL hashes, provider health and live compatibility NOT verified"
				break
			}
			if candidate.State == "legacy_metadata_missing" {
				result.State = "legacy_metadata_missing"
				result.Message = "Wand Proton launcher and Steam registration exist, but the optional GameWeld sidecar is absent; keep the existing installation; runtime health NOT verified"
			}
		}
	}
	return result
}
