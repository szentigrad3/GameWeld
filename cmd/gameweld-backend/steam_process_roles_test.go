package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestProcessRoleLabelsOnlyHeuristics(t *testing.T) {
	for _,tc:=range []struct { comm,exe,want string }{
		{"steamwebhelper","/usr/bin/steamwebhelper","steam_helper"},
		{"pressure-vessel","/usr/lib/pressure-vessel","steam_helper"},
		{"wineserver","/usr/bin/wineserver","wine_runtime"},
		{"services.exe","/usr/bin/wine64-preloader","wine_runtime"},
		{"Adventure.exe","/usr/bin/wine64-preloader","windows_executable_candidate"},
		{"AdCapMain","/usr/bin/wine64-preloader","wine_runtime"},
		{"unknown","/usr/bin/something","other_associated"},
	} {
		if got:=classifyAssociatedProcess(tc.comm,tc.exe);got!=tc.want {
			t.Errorf("role (%s,%s): %s, want %s",tc.comm,tc.exe,got,tc.want)
		}
	}
}
func TestSafeProcessLabels(t *testing.T) {
	for _,tc:=range []struct{input,want string}{
		{"/home/private/steamapps/common/AdCap.exe","AdCap.exe"},
		{"/secret/name with spaces","redacted"},
		{"../evil","evil"},
		{"/bin/normal.exe","normal.exe"},
		{"/with/path/a\ntest","redacted"},
		{"","unavailable"},
	}{
		if got:=safeProcessLabel(tc.input);got!=tc.want {t.Errorf("input %q got %q expected %q",tc.input,got,tc.want)}
	}
}
func TestRoleInspectionFixtureNoPathsAndNoTrust(t *testing.T) {
	root:=t.TempDir()
	environment:=[]byte("SteamAppId=346900\x00STEAM_COMPAT_DATA_PATH=/private/user/gameprefix\x00WINEPREFIX=/private/wineprefix\x00")
	addTestSessionProc(t,root,1234,"Adventure.exe",environment)
	if err:=os.Symlink("/some/private/path/wine64-preloader",filepath.Join(root,"1234","exe"));err!=nil{t.Fatal(err)}
	addTestSessionProc(t,root,1235,"steamwebhelper",[]byte("SteamGameId=346900\x00"))
	addTestSessionProc(t,root,1236,"unrelated",[]byte("SteamAppId=346901\x00"))
	report:=inspectSteamProcessRoles(root,"346900")
	if report.Mode!="read_only"||report.State!="associated_processes_observed"||
		report.AssociatedProcessCount!=2||len(report.Roles)!=2||
		report.GameExecutableVerified||report.PrefixOwnershipVerified||report.TrainerHandoffEnabled||
		report.ScanTruncated {
		t.Fatalf("unexpected role report %+v",report)
	}
	found:=false
	for _,role:=range report.Roles {
		if role.Comm=="Adventure.exe" {
			found=true
			if role.Role!="windows_executable_candidate"||role.ExecutableName!="wine64-preloader"||
				!role.HasCompatdataEnv||!role.HasWineprefixEnv {t.Fatalf("incorrect role %+v",role)}
		}
	}
	if !found {t.Fatal("test process missing")}
	data,err:=json.Marshal(report)
	if err!=nil{t.Fatal(err)}
	if strings.Contains(string(data),"/private/")||strings.Contains(string(data),"gameprefix")||
		strings.Contains(string(data),"\"pid\"") {
		t.Fatalf("report leaks path or PID: %s",data)
	}
}
func TestRoleInspectionCannotElevateTrustOnAbsentProcesses(t *testing.T) {
	root:=t.TempDir()
	report:=inspectSteamProcessRoles(root,"346900")
	if report.State!="no_process_evidence"||len(report.Roles)!=0||
		report.GameExecutableVerified||report.PrefixOwnershipVerified||report.TrainerHandoffEnabled{
		t.Fatalf("false trust %+v",report)
	}
	report=inspectSteamProcessRoles(root,"bad-appid")
	if report.State!="invalid_appid"||report.GameExecutableVerified {t.Fatal(report)}
}
func TestRoleInspectionNoWrites(t *testing.T) {
	root:=t.TempDir()
	env:=[]byte("SteamAppId=346900\x00STEAM_COMPAT_DATA_PATH=/tmp/pfx\x00")
	addTestSessionProc(t,root,1234,"wine64",env)
	path:=filepath.Join(root,"1234","environ")
	before,err:=os.ReadFile(path);if err!=nil{t.Fatal(err)}
	_ =inspectSteamProcessRoles(root,"346900")
	after,err:=os.ReadFile(path);if err!=nil{t.Fatal(err)}
	if string(before)!=string(after) {t.Fatal("observation wrote source")}
}
