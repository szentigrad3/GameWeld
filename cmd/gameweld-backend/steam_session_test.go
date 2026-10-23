package main

import (
	"os"
	"path/filepath"
	"strconv"
	"testing"
)

func TestSteamEnvironmentMatchExact(t *testing.T) {
	env:=[]byte("PATH=/usr/bin\x00SteamAppId=346900\x00SteamGameId=123\x00STEAM_COMPAT_APP_ID=456\x00")
	for _,tc:=range []struct{id,key string}{
		{"346900","SteamAppId"},{"123","SteamGameId"},{"456","STEAM_COMPAT_APP_ID"},
	}{
		if got:=steamEnvironmentMatch(env,tc.id);got!=tc.key{
			t.Fatalf("id %s: got %q, want %q",tc.id,got,tc.key)
		}
	}
	for _,wrong:=range []string{"3469","3469000","900","457","1","0"} {
		if got:=steamEnvironmentMatch(env,wrong);got!="" {
			t.Fatalf("inexact app ID %s matched as %q",wrong,got)
		}
	}
}
func addTestSessionProc(t *testing.T,root string,pid int,comm string,env []byte) {
	t.Helper()
	dir:=filepath.Join(root,strconv.Itoa(pid))
	if err:=os.MkdirAll(dir,0700);err!=nil{t.Fatal(err)}
	if err:=os.WriteFile(filepath.Join(dir,"environ"),env,0600);err!=nil{t.Fatal(err)}
	if err:=os.WriteFile(filepath.Join(dir,"comm"),[]byte(comm+"\n"),0600);err!=nil{t.Fatal(err)}
}
func TestSessionObservationFromFixture(t *testing.T) {
	root:=t.TempDir()
	addTestSessionProc(t,root,1234,"AdventureCapitalist",[]byte("SteamAppId=346900\x00X=y\x00"))
	addTestSessionProc(t,root,1235,"steamwebhelper",[]byte("SteamGameId=346900\x00"))
	addTestSessionProc(t,root,1236,"unrelated",[]byte("SteamAppId=3469000\x00"))
	result:=inspectSteamSession(root,"346900")
	if result.Mode!="read_only"||result.State!="associated_processes_observed"||
		result.AssociatedProcessCount!=2||len(result.Processes)!=2||
		result.GameRunningConfirmed||result.ScanTruncated {
		t.Fatalf("unexpected session evidence: %+v",result)
	}
	for _,process:=range result.Processes{
		if process.Comm==""||len(process.Comm)>15||process.Association=="" {
			t.Fatalf("malformed evidence %+v",process)
		}
	}
	result=inspectSteamSession(root,"346901")
	if result.State!="no_process_evidence"||result.GameRunningConfirmed||result.AssociatedProcessCount!=0{
		t.Fatalf("unknown app ID state: %+v",result)
	}
}
func TestSessionObservationReadOnly(t *testing.T) {
	root:=t.TempDir()
	addTestSessionProc(t,root,120,"steamwebhelper",[]byte("SteamAppId=346900\x00"))
	path:=filepath.Join(root,"120","environ")
	before,err:=os.ReadFile(path)
	if err!=nil {t.Fatal(err)}
	got:=inspectSteamSession(root,"346900")
	after,err:=os.ReadFile(path)
	if err!=nil {t.Fatal(err)}
	if string(before)!=string(after)||got.GameRunningConfirmed{
		t.Fatalf("inspection changed evidence or claimed live game: %+v",got)
	}
}
func TestSessionUnavailableAndMalformed(t *testing.T) {
	root:=filepath.Join(t.TempDir(),"not-here")
	got:=inspectSteamSession(root,"346900")
	if got.State!="unavailable"||got.GameRunningConfirmed {t.Fatal(got)}
	got=inspectSteamSession(root,"bad")
	if got.State!="invalid_appid"||got.GameRunningConfirmed {t.Fatal(got)}
}
func TestSessionEvidenceBounded(t *testing.T) {
	root:=t.TempDir()
	for i:=0;i<maxSessionEvidence+2;i++{
		addTestSessionProc(t,root,i+100,"fixture",[]byte("SteamAppId=346900\x00"))
	}
	got:=inspectSteamSession(root,"346900")
	if !got.ScanTruncated||len(got.Processes)!=maxSessionEvidence||got.AssociatedProcessCount!=maxSessionEvidence+2{
		t.Fatalf("unbounded or missing process data %+v",got)
	}
}
func TestSteamSessionHTTPFailClosed(t *testing.T) {
	t.Setenv("HOME",t.TempDir())
	t.Setenv("STEAM_ROOT","")
	for _,path:=range []string{"/api/steam-session","/api/steam-session?appid=1","/api/steam-session?appid=1%3Bwhoami"}{
		status,result:=req(t,"GET",path)
		if status!=404||result.OK {
			t.Fatalf("%s accepted: %d %+v",path,status,result)
		}
	}
	status,result:=req(t,"POST","/api/steam-session?appid=346900")
	if status!=405||result.OK {
		t.Fatalf("session endpoint accepted mutation: %d %+v",status,result)
	}
}
