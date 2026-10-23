package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestPayloadParityMatchesLocalNotTrusted(t *testing.T) {
	lib, tool := fixtureCompatibility(t)
	tmp := t.TempDir()
	payload := filepath.Join(tmp,"payload")
	t.Setenv("WAND_PAYLOAD_ROOT",payload)
	for _, arch := range []string{"x86_64","i386"} {
		d := filepath.Join(payload,arch+"-windows")
		if err := os.MkdirAll(d,0700);err != nil { t.Fatal(err) }
		bytes := []byte("fixture-"+arch)
		if err := os.WriteFile(filepath.Join(d,"crypt32.dll"),bytes,0600);err!=nil{t.Fatal(err)}
		fixtureDLL(t,tool,arch,bytes)
	}
	result := inspectLocalPayloadParity([]string{lib})
	if result.Mode!="read_only" || result.TrustedIntegrityVerified || len(result.Candidates)!=1 {
		t.Fatalf("unexpected result: %+v",result)
	}
	c := result.Candidates[0]
	for _, item := range []parityResult{c.X64,c.X86} {
		if item.Result!="matches_local_payload"||!item.MatchesLocalPayload {
			t.Fatalf("did not match local payload: %+v",item)
		}
	}
}
func TestPayloadParityMismatchNotHealthy(t *testing.T) {
	lib, tool := fixtureCompatibility(t)
	payload := t.TempDir()
	t.Setenv("WAND_PAYLOAD_ROOT",payload)
	d:=filepath.Join(payload,"x86_64-windows")
	if err:=os.MkdirAll(d,0700);err!=nil{t.Fatal(err)}
	if err:=os.WriteFile(filepath.Join(d,"crypt32.dll"),[]byte("local"),0600);err!=nil{t.Fatal(err)}
	fixtureDLL(t,tool,"x86_64",[]byte("installed-not-matching"))
	c := inspectLocalPayloadParity([]string{lib}).Candidates[0]
	if c.X64.Result!="differs_from_local_payload" || c.X64.MatchesLocalPayload || c.X86.Result!="comparison_unavailable" {
		t.Fatalf("incorrect parity result: %+v",c)
	}
}
func TestPayloadParityAbsentDoesNotConcludeMismatch(t *testing.T) {
	lib, tool := fixtureCompatibility(t)
	fixtureDLL(t,tool,"x86_64",[]byte("installed"))
	t.Setenv("WAND_PAYLOAD_ROOT",filepath.Join(t.TempDir(),"missing"))
	c := inspectLocalPayloadParity([]string{lib}).Candidates[0]
	if c.X64.PayloadState!="local_payload_missing" || c.X64.Result!="comparison_unavailable" || c.X64.MatchesLocalPayload {
		t.Fatalf("missing payload treated as mismatch: %+v",c)
	}
}
func TestPayloadParitySymlinkDirectoryRejected(t *testing.T) {
	lib, tool := fixtureCompatibility(t)
	fixtureDLL(t,tool,"x86_64",[]byte("installed"))
	dir:=t.TempDir()
	payload:=filepath.Join(dir,"payload")
	if err:=os.Symlink(t.TempDir(),payload);err!=nil{t.Fatal(err)}
	t.Setenv("WAND_PAYLOAD_ROOT",payload)
	c:=inspectLocalPayloadParity([]string{lib}).Candidates[0]
	if c.X64.PayloadState!="local_payload_directory_unsafe" || c.X64.Result!="comparison_unavailable" {
		t.Fatalf("symlink unexpectedly traversed: %+v",c)
	}
}
func TestPayloadParityRejectsRelativeOverride(t *testing.T) {
	lib, _ := fixtureCompatibility(t)
	t.Setenv("WAND_PAYLOAD_ROOT","relative-path")
	c:=inspectLocalPayloadParity([]string{lib}).Candidates[0]
	if c.X64.PayloadState!="no_absolute_payload_root" || c.X86.PayloadState!="no_absolute_payload_root" {
		t.Fatalf("relative path override accepted: %+v",c)
	}
}
func TestPayloadParityReportDoesNotIncludePaths(t *testing.T) {
	lib,tool:=fixtureCompatibility(t)
	t.Setenv("WAND_PAYLOAD_ROOT",filepath.Join(t.TempDir(),"no-payload"))
	fixtureDLL(t,tool,"x86_64",[]byte("installed"))
	report:=inspectLocalPayloadParity([]string{lib})
	if report.TrustedIntegrityVerified || len(report.Candidates)!=1 || report.Candidates[0].Label!="candidate_1" {
		t.Fatalf("privacy or trust regression: %+v",report)
	}
}
