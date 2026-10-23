package main

import (
 "testing"
 "os"
 "path/filepath"
)

func TestSteamLaunchPlanOnlyInstalled(t *testing.T){
 fixtures:=[]game{
    {AppID:"12345",Name:"Fixture Game",InstallDir:"/tmp/fixturegame"},
    {AppID:"45678",Name:"Not Installed"},
 }
 p,ok:=steamLaunchPlan(fixtures,"12345")
 if !ok||p.URI!="steam://rungameid/12345"||p.Mode!="preview_only"||p.Provider!="steam"||p.LaunchEnabled {
    t.Fatalf("unsafe or incorrect plan: %+v %v",p,ok)
 }
 if _,ok:=steamLaunchPlan(fixtures,"45678");ok{t.Fatal("Missing install dir unexpectedly previewable")}
 if _,ok:=steamLaunchPlan(fixtures,"999");ok{t.Fatal("Unknown appid unexpectedly previewable")}
}
func TestSteamLaunchPlanRejectsInjectionAndMalformed(t *testing.T){
 installed:=[]game{{AppID:"1",Name:"Safe",InstallDir:"/tmp/safe"}}
 for _,id:=range []string{"", "0","01","-1","+1","1?param=x","1;rm","%31","4294967296","1\n"," 1","1/2"}{
    if _,ok:=steamLaunchPlan(installed,id);ok {t.Fatalf("accepted %q",id)}
 }
 if !validSteamID("1") || !validSteamID("4294967295"){t.Fatal("legitimate 32-bit id rejected")}
}
func TestSteamLaunchPreviewHTTP(t *testing.T) {
 home:=t.TempDir()
 t.Setenv("HOME",home)
 t.Setenv("STEAM_ROOT","")
 // Reuse in-memory provider contract separately; an empty HOME must not
 // return an executable launch plan or any user-changing response.
 for _,path:=range []string{"/api/launch-preview", "/api/launch-preview?appid=12345", "/api/launch-preview?appid=1%3Bwhoami"} {
   status,v:=req(t,"GET",path)
   if status!=404 || v.OK {t.Fatalf("%s unexpectedly launchable: %d %+v",path,status,v)}
 }
 code,v:=req(t,"POST","/api/launch-preview?appid=1")
 if code!=405 || v.OK {t.Fatalf("POST accepted: %d %+v",code,v)}
}

func TestSteamLaunchPreviewReadsFixtureManifest(t *testing.T) {
    home:=t.TempDir()
    t.Setenv("HOME",home)
    root:=filepath.Join(home,"Steam")
    t.Setenv("STEAM_ROOT",root)
    apps:=filepath.Join(root,"steamapps")
    if err:=os.MkdirAll(apps,0700);err!=nil{t.Fatal(err)}
    manifest:=filepath.Join(apps,"appmanifest_12345.acf")
    original:=[]byte("\"AppState\" { \"appid\" \"12345\" \"name\" \"Test Game\" \"installdir\" \"testgame\" }")
    if err:=os.WriteFile(manifest,original,0600);err!=nil{t.Fatal(err)}
    status,data:=req(t,"GET","/api/launch-preview?appid=12345")
    if status!=200||!data.OK {t.Fatalf("fixture preview unavailable: %d %+v",status,data)}
    plan,ok:=data.Data.(map[string]any)
    if !ok||plan["uri"]!="steam://rungameid/12345"||plan["mode"]!="preview_only"||plan["launch_enabled"]!=false{
        t.Fatalf("unsafe preview payload %#v",data.Data)
    }
    after,err:=os.ReadFile(manifest)
    if err!=nil||string(after)!=string(original){t.Fatal("Steam manifest modified by preview")}
}
