package main

import (
	"os"
	"path/filepath"
	"strconv"
)

// A local payload comparison establishes only whether the installed DLLs
// have the same bytes as the user's local GameWeld payload files. It does NOT
// establish upstream authenticity, safety, subscription status or game health.
type parityResult struct {
	InstalledState string `json:"installed_state"`
	PayloadState string `json:"payload_state"`
	Result string `json:"result"`
	MatchesLocalPayload bool `json:"matches_local_payload"`
}
type parityCandidate struct {
	Label string `json:"label"`
	X64 parityResult `json:"x86_64"`
	X86 parityResult `json:"i386"`
}
type parityReport struct {
	Mode string `json:"mode"`
	TrustedIntegrityVerified bool `json:"trusted_integrity_verified"`
	Summary string `json:"summary"`
	Candidates []parityCandidate `json:"candidates"`
}

func localPayloadRoot() string {
	override := os.Getenv("WAND_PAYLOAD_ROOT")
	if override != "" {
		if !filepath.IsAbs(override) { return "" }
		return filepath.Clean(override)
	}
	xdg := os.Getenv("XDG_DATA_HOME")
	if !filepath.IsAbs(xdg) {
		home, err := os.UserHomeDir()
		if err != nil || home == "" { return "" }
		xdg = filepath.Join(home, ".local", "share")
	}
	return filepath.Join(xdg, "wand-native", "payload", "crypt32")
}

func localPayloadEvidence(root, arch string) dllEvidence {
	if root == "" { return dllEvidence{State: "no_absolute_payload_root"} }
	dir := filepath.Join(root, arch+"-windows")
	// Reject a symlink at either boundary. A missing payload is normal.
	for _, part := range []string{root, dir} {
		st, err := os.Lstat(part)
		if os.IsNotExist(err) { return dllEvidence{State: "local_payload_missing"} }
		if err != nil { return dllEvidence{State: "local_payload_unreadable"} }
		if !st.IsDir() || st.Mode()&os.ModeSymlink != 0 {
			return dllEvidence{State: "local_payload_directory_unsafe"}
		}
	}
	return fingerprintDLL(filepath.Join(dir, "crypt32.dll"))
}

func compareEvidence(installed, payload dllEvidence) parityResult {
	item := parityResult{
		InstalledState: installed.State, PayloadState: payload.State,
		Result: "comparison_unavailable", MatchesLocalPayload: false,
	}
	if installed.State != "fingerprinted_unverified" ||
		payload.State != "fingerprinted_unverified" ||
		installed.SHA256 == "" || payload.SHA256 == "" {
		return item
	}
	if installed.SHA256 == payload.SHA256 {
		item.Result = "matches_local_payload"
		item.MatchesLocalPayload = true
	} else {
		item.Result = "differs_from_local_payload"
	}
	return item
}

func inspectLocalPayloadParity(libraries []string) parityReport {
	report := parityReport{
		Mode: "read_only", TrustedIntegrityVerified: false,
		Summary: "Local payload byte comparison only; no trusted reference, modification, download or live runtime test",
		Candidates: []parityCandidate{},
	}
	root := localPayloadRoot()
	compat := inspectCompatibility(libraries)
	local64 := localPayloadEvidence(root,"x86_64")
	local32 := localPayloadEvidence(root,"i386")
	for i, candidate := range compat.Candidates {
		report.Candidates = append(report.Candidates,parityCandidate{
			Label: "candidate_"+strconv.Itoa(i+1),
			X64: compareEvidence(inspectDLL(candidate.Path,"x86_64"),local64),
			X86: compareEvidence(inspectDLL(candidate.Path,"i386"),local32),
		})
	}
	return report
}
