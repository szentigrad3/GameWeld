package main

import (
    "crypto/sha256"
    "encoding/hex"
    "os"
    "path/filepath"
    "testing"
)

func fixtureDLL(t *testing.T,dir,arch string, payload []byte) string {
    t.Helper()
    d:=filepath.Join(dir,"files","lib64","wine",arch+"-windows")
    if err:=os.MkdirAll(d,0700);err!=nil{t.Fatal(err)}
    p:=filepath.Join(d,"crypt32.dll")
    if err:=os.WriteFile(p,payload,0600);err!=nil{t.Fatal(err)}
    return p
}
func TestRuntimeFingerprintsPresentUnverified(t *testing.T) {
    lib,dir:=fixtureCompatibility(t)
    blob:=[]byte("test-only fake DLL not a working patch")
    fixtureDLL(t,dir,"x86_64",blob)
    fixtureDLL(t,dir,"i386",blob)
    got:=inspectRuntime([]string{lib})
    if got.Mode!="read_only" || got.IntegrityVerified || len(got.Candidates)!=1 {t.Fatalf("unexpected runtime status: %+v",got)}
    c:=got.Candidates[0]
    expected:=sha256.Sum256(blob)
    if c.X64.State!="fingerprinted_unverified" || c.X64.SHA256!=hex.EncodeToString(expected[:]) ||
       c.X86.State!="fingerprinted_unverified" || c.X86.SHA256!=hex.EncodeToString(expected[:]) ||
       c.IntegrityVerified {
        t.Fatalf("unexpected fingerprint: %+v",c)
    }
}
func TestRuntimeMissingDLLDoesNotVerify(t *testing.T) {
    lib,_:=fixtureCompatibility(t)
    c:=inspectRuntime([]string{lib}).Candidates[0]
    if c.X64.State!="not_found_in_known_layouts"||c.X86.State!="not_found_in_known_layouts"||c.IntegrityVerified {t.Fatalf("bad missing status: %+v",c)}
}
func TestRuntimeSymlinkedDLLNotRead(t *testing.T) {
    lib,dir:=fixtureCompatibility(t)
    target:=filepath.Join(t.TempDir(),"target")
    if err:=os.WriteFile(target,[]byte("do not read"),0600);err!=nil{t.Fatal(err)}
    dst:=fixtureDLL(t,dir,"x86_64",[]byte("temporary"))
    if err:=os.Remove(dst);err!=nil{t.Fatal(err)}
    if err:=os.Symlink(target,dst);err!=nil{t.Fatal(err)}
    c:=inspectRuntime([]string{lib}).Candidates[0]
    if c.X64.State!="symlink_not_followed"||c.X64.SHA256!=""{t.Fatalf("symlink followed %+v",c)}
}
func TestRuntimeSymlinkParentNotFollowed(t *testing.T) {
    lib,dir:=fixtureCompatibility(t)
    outside:=t.TempDir()
    d:=filepath.Join(outside,"wine","x86_64-windows")
    if err:=os.MkdirAll(d,0700);err!=nil{t.Fatal(err)}
    if err:=os.WriteFile(filepath.Join(d,"crypt32.dll"),[]byte("external"),0600);err!=nil{t.Fatal(err)}
    if err:=os.MkdirAll(filepath.Join(dir,"files"),0700);err!=nil{t.Fatal(err)}
    if err:=os.Symlink(outside,filepath.Join(dir,"files","lib64"));err!=nil{t.Fatal(err)}
    c:=inspectRuntime([]string{lib}).Candidates[0]
    if c.X64.State!="not_found_in_known_layouts"||c.X64.SHA256!=""{t.Fatalf("followed symlink parent %+v",c)}
}
func TestFingerprintAbsentEmptyAndOversized(t *testing.T) {
    p:=filepath.Join(t.TempDir(),"crypt32.dll")
    if got:=fingerprintDLL(p);got.State!="missing"{t.Fatal(got)}
    if err:=os.WriteFile(p,nil,0600);err!=nil{t.Fatal(err)}
    if got:=fingerprintDLL(p);got.State!="empty"{t.Fatal(got)}
    if err:=os.Truncate(p,maxDLLBytes+1);err!=nil{t.Fatal(err)}
    if got:=fingerprintDLL(p);got.State!="oversized"{t.Fatal(got)}
}
