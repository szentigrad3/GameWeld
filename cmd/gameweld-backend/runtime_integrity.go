package main

import (
    "crypto/sha256"
    "encoding/hex"
    "errors"
    "io"
    "os"
    "strconv"
    "path/filepath"
)

// Read-only evidence collection: a calculated SHA256 is a fingerprint,
// NOT verification against a trusted source. Never execute Proton here.
const maxDLLBytes int64 = 64 << 20

type dllEvidence struct {
    State string `json:"state"`
    SHA256 string `json:"sha256,omitempty"`
}
type runtimeCandidate struct {
    Label string `json:"label"`
    MetadataState string `json:"metadata_state"`
    X64 dllEvidence `json:"x86_64"`
    X86 dllEvidence `json:"i386"`
    IntegrityVerified bool `json:"integrity_verified"`
}
type runtimeReport struct {
    Mode string `json:"mode"`
    IntegrityVerified bool `json:"integrity_verified"`
    Summary string `json:"summary"`
    Candidates []runtimeCandidate `json:"candidates"`
}
func fingerprintDLL(path string) dllEvidence {
    st, err := os.Lstat(path)
    if errors.Is(err, os.ErrNotExist) { return dllEvidence{State:"missing"} }
    if err != nil { return dllEvidence{State:"unreadable"} }
    if st.Mode()&os.ModeSymlink != 0 { return dllEvidence{State:"symlink_not_followed"} }
    if !st.Mode().IsRegular() { return dllEvidence{State:"not_regular"} }
    if st.Size() == 0 { return dllEvidence{State:"empty"} }
    if st.Size() > maxDLLBytes { return dllEvidence{State:"oversized"} }
    f,err:=os.Open(path)
    if err!=nil { return dllEvidence{State:"unreadable"} }
    defer f.Close()
    hash:=sha256.New()
    n,err:=io.CopyN(hash,f,maxDLLBytes+1)
    if err!=nil && !errors.Is(err,io.EOF) {return dllEvidence{State:"unreadable"}}
    if n>maxDLLBytes {return dllEvidence{State:"oversized"}}
    if n!=st.Size(){return dllEvidence{State:"changed_while_reading"}}
    return dllEvidence{State:"fingerprinted_unverified", SHA256:hex.EncodeToString(hash.Sum(nil))}
}
func locateDLL(tool,arch string) string {
    // These are the GE-Proton layout variants used by local installs.
    // Avoid walking arbitrary trees or following directory symlinks.
    libnames:=[]string{"lib64","lib","lib32"}
    for _,lib:=range libnames {
        p:=filepath.Join(tool,"files",lib,"wine",arch+"-windows","crypt32.dll")
        if st,err:=os.Lstat(p);err==nil && st!=nil {
            return p
        }
    }
    // No known-layout file: do not guess, download, patch or scan other paths.
    return ""
}
func inspectDLL(tool,arch string) dllEvidence {
    p:=locateDLL(tool,arch)
    if p=="" { return dllEvidence{State:"not_found_in_known_layouts"} }
    return fingerprintDLL(p)
}
func inspectRuntime(libraries []string) runtimeReport {
    result:=runtimeReport{
        Mode:"read_only",IntegrityVerified:false,
        Summary:"File presence and SHA256 fingerprints are evidence only; no trusted reference or trainer health check",
        Candidates:[]runtimeCandidate{},
    }
    compat:=inspectCompatibility(libraries)
    for i,candidate:=range compat.Candidates {
        result.Candidates=append(result.Candidates,runtimeCandidate{
            Label: "candidate_"+strconv.Itoa(i+1),
            MetadataState:candidate.MetadataState,
            X64: inspectDLL(candidate.Path,"x86_64"),
            X86: inspectDLL(candidate.Path,"i386"),
            IntegrityVerified:false,
        })
    }
    return result
}
