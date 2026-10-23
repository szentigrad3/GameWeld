package main

import (
	"encoding/json"
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
		raw := regularSmall(filepath.Join(path, "WAND-HYBRID.json"))
		var metadata struct {
			Schema     int    `json:"schema"`
			ToolID     string `json:"tool_id"`
			BaseProton string `json:"base_proton"`
		}
		candidate.HasMetadata = json.Unmarshal(raw, &metadata) == nil &&
			metadata.Schema == 1 && metadata.ToolID == pc2CompatToolID && metadata.BaseProton != ""
		if candidate.HasProton && candidate.HasManifest && candidate.HasMetadata {
			candidate.State = "detected_unverified"
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
		}
	}
	return result
}
