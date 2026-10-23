package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func createNativeFixture(t *testing.T,appID string,body []byte) (string,string,string) {
	t.Helper()
	procRoot:=t.TempDir()
	install:=filepath.Join(t.TempDir(),"steamapps","common","AdVenture Capitalist")
	if err:=os.MkdirAll(install,0700);err!=nil {t.Fatal(err)}
	exe:=filepath.Join(install,"adventure-capitalist.x86")
	if err:=os.WriteFile(exe,body,0700);err!=nil {t.Fatal(err)}
	addTestSessionProc(t,procRoot,1234,"adventure-capit",[]byte("SteamAppId="+appID+"\x00STEAM_COMPAT_DATA_PATH=/private/compatdata\x00"))
	if err:=os.Symlink(exe,filepath.Join(procRoot,"1234","exe"));err!=nil {t.Fatal(err)}
	return procRoot,install,exe
}
func TestNativeELFInInstallDirectoryObservedNotVerified(t *testing.T) {
	root,install,exe:=createNativeFixture(t,"346900",[]byte("\x7fELF\x01fixture"))
	before,err:=os.ReadFile(exe);if err!=nil {t.Fatal(err)}
	result:=inspectNativeSteamExecutable(root,"346900",install)
	if result.Mode!="read_only"||result.State!="associated_processes_observed"||
		result.AssociatedProcessCount!=1||len(result.Candidates)!=1||
		result.NativeELFCandidateCount!=1||result.GameExecutableVerified||
		result.TrainerHandoffEnabled||result.ScanTruncated {
		t.Fatalf("unexpected native process evidence %+v",result)
	}
	if result.Candidates[0].ExecutableName!="adventure-capitalist.x86"||
		result.Candidates[0].ELFClass!="ELF32"||
		result.Candidates[0].State!="native_elf_inside_install_directory" {
		t.Fatalf("wrong evidence %+v",result.Candidates[0])
	}
	after,err:=os.ReadFile(exe);if err!=nil {t.Fatal(err)}
	if string(before)!=string(after){t.Fatal("read-only process inspection modified executable")}
	raw,err:=json.Marshal(result);if err!=nil {t.Fatal(err)}
	if strings.Contains(string(raw),install)||strings.Contains(string(raw),"/private/")||
		strings.Contains(string(raw),"\"pid\""){t.Fatalf("privacy violation: %s",raw)}
}
func TestNativeELF64(t *testing.T) {
	root,install,_:=createNativeFixture(t,"346900",[]byte("\x7fELF\x02fixture"))
	result:=inspectNativeSteamExecutable(root,"346900",install)
	if result.NativeELFCandidateCount!=1||result.Candidates[0].ELFClass!="ELF64" {t.Fatal(result)}
}
func TestNativeELFNotInInstallDirectory(t *testing.T) {
	root,install,_:=createNativeFixture(t,"346900",[]byte("\x7fELF\x01fixture"))
	other:=filepath.Join(t.TempDir(),"adventure-capitalist.x86")
	if err:=os.WriteFile(other,[]byte("\x7fELF\x01outside"),0700);err!=nil{t.Fatal(err)}
	symlink:=filepath.Join(root,"1234","exe")
	if err:=os.Remove(symlink);err!=nil{t.Fatal(err)}
	if err:=os.Symlink(other,symlink);err!=nil{t.Fatal(err)}
	result:=inspectNativeSteamExecutable(root,"346900",install)
	if result.NativeELFCandidateCount!=0||
		result.Candidates[0].State!="outside_install_directory"||
		result.GameExecutableVerified {t.Fatal(result)}
}
func TestNativeELFRejectsSymlinkEscape(t *testing.T) {
	root,install,_:=createNativeFixture(t,"346900",[]byte("\x7fELF\x01fixture"))
	outside:=filepath.Join(t.TempDir(),"fake")
	if err:=os.WriteFile(outside,[]byte("\x7fELF\x02"),0700);err!=nil{t.Fatal(err)}
	insideAlias:=filepath.Join(install,"aliased-game")
	if err:=os.Symlink(outside,insideAlias);err!=nil{t.Fatal(err)}
	link:=filepath.Join(root,"1234","exe")
	if err:=os.Remove(link);err!=nil{t.Fatal(err)}
	if err:=os.Symlink(insideAlias,link);err!=nil{t.Fatal(err)}
	result:=inspectNativeSteamExecutable(root,"346900",install)
	if result.NativeELFCandidateCount!=0||result.Candidates[0].State!="outside_install_directory"{t.Fatal(result)}
}
func TestNativeExecutableNotELF(t *testing.T) {
	root,install,_:=createNativeFixture(t,"346900",[]byte("not ELF"))
	result:=inspectNativeSteamExecutable(root,"346900",install)
	if result.NativeELFCandidateCount!=0||result.Candidates[0].State!="inside_install_directory_not_validated_elf"{t.Fatal(result)}
}
func TestNativeExecutableFalseAssociationNotAccepted(t *testing.T) {
	root,install,_:=createNativeFixture(t,"346901",[]byte("\x7fELF\x01fixture"))
	result:=inspectNativeSteamExecutable(root,"346900",install)
	if result.NativeELFCandidateCount!=0||result.AssociatedProcessCount!=0||result.GameExecutableVerified{t.Fatal(result)}
}
func TestNativeExecutableMissingInstallDoesNotVerify(t *testing.T) {
	root,_,_:=createNativeFixture(t,"346900",[]byte("\x7fELF\x01fixture"))
	result:=inspectNativeSteamExecutable(root,"346900",filepath.Join(t.TempDir(),"missing"))
	if result.NativeELFCandidateCount!=0||result.Candidates[0].State!="install_directory_unavailable"{t.Fatal(result)}
}
func TestNativePathBoundary(t *testing.T) {
	if !pathInsideDirectory("/root/games","/root/games/title/exe") ||
		pathInsideDirectory("/root/games","/root/games2/exe") ||
		pathInsideDirectory("/root/games","/root/games") ||
		pathInsideDirectory("/root/games","/root/games/../external/exe") {
		t.Fatal("directory containment regression")
	}
}
func TestSteamNativeEvidenceHTTPFailClosed(t *testing.T) {
	t.Setenv("HOME",t.TempDir());t.Setenv("STEAM_ROOT","")
	for _,path:=range []string{"/api/steam-native-executable?appid=346900","/api/steam-native-executable?appid=1%3Bwhoami","/api/steam-native-executable"}{
		status,payload:=req(t,"GET",path)
		if status!=404||payload.OK{t.Fatalf("%s unexpectedly allowed %d %+v",path,status,payload)}
	}
	status,payload:=req(t,"POST","/api/steam-native-executable?appid=346900")
	if status!=405||payload.OK{t.Fatalf("POST unexpectedly allowed %d %+v",status,payload)}
}
