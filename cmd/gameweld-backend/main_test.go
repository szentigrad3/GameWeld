package main

import (
    "encoding/json"
    "fmt"
    "net"
    "net/http/httptest"
    "os"
    "path/filepath"
    "testing"
)
func req(t *testing.T, method, path string) (int,envelope) {
    t.Helper()
    r:=httptest.NewRequest(method,path,nil)
    w:=httptest.NewRecorder()
    router().ServeHTTP(w,r)
    var resp envelope
    if err:=json.Unmarshal(w.Body.Bytes(),&resp);err!=nil{t.Fatal(err)}
    return w.Code,resp
}
func TestHTTPContract(t *testing.T) {
    t.Setenv("HOME",t.TempDir())
    for _,test:=range []struct{method,path string;code int;ok bool}{
        {"GET","/api/status",200,true},
        {"GET","/api/compatibility",200,true},
        {"GET","/api/runtime-integrity",200,true},
        {"POST","/api/runtime-integrity",405,false},
        {"POST","/api/compatibility",405,false},
        {"GET","/api/job",200,true},
        {"GET","/api/verify",409,false},
        {"GET","/api/health?appid=10",200,true},
        {"POST","/api/install",501,false},
        {"POST","/api/set-game",501,false},
        {"GET","/not-here",404,false},
        {"POST","/api/status",405,false},
        {"GET","/api/install",405,false},
    }{
        code,x:=req(t,test.method,test.path)
        if code!=test.code||x.OK!=test.ok {t.Errorf("%s %s: status %d ok %v",test.method,test.path,code,x.OK)}
    }
}
func TestSteamDiscovery(t *testing.T) {
    home:=t.TempDir()
    t.Setenv("HOME",home)
    t.Setenv("STEAM_ROOT","")
    root:=filepath.Join(home,".local","share","Steam")
    extra:=filepath.Join(home,"games","library")
    for _,p:=range []string{root,extra}{
        if err:=os.MkdirAll(filepath.Join(p,"steamapps"),0700);err!=nil{t.Fatal(err)}
    }
    vdf:=fmt.Sprintf("\"libraryfolders\" { \"0\" { \"path\" %q } \"1\" { \"path\" %q } }",root,extra)
    if err:=os.WriteFile(filepath.Join(root,"steamapps","libraryfolders.vdf"),[]byte(vdf),0600);err!=nil{t.Fatal(err)}
    acf:= "\"AppState\" { \"appid\" \"12345\" \"name\" \"Fixture Game\" \"installdir\" \"fixture-game\" }"
    if err:=os.WriteFile(filepath.Join(extra,"steamapps","appmanifest_12345.acf"),[]byte(acf),0600);err!=nil{t.Fatal(err)}
    inv:=steamInventory()
    if len(inv.Games)!=1||inv.Games[0].Name!="Fixture Game"||inv.Games[0].AppID!="12345" {t.Fatalf("unexpected games %#v",inv.Games)}
    if inv.Games[0].InstallDir!=filepath.Join(extra,"steamapps","common","fixture-game"){t.Fatal("wrong installation path")}
}
func TestManifestMismatchRejected(t *testing.T) {
    home:=t.TempDir()
    t.Setenv("HOME",home)
    t.Setenv("STEAM_ROOT","")
    p:=filepath.Join(home,".local","share","Steam","steamapps")
    if err:=os.MkdirAll(p,0700);err!=nil{t.Fatal(err)}
    if err:=os.WriteFile(filepath.Join(p,"appmanifest_12345.acf"),[]byte("\"appid\" \"98765\" \"name\" \"Bad\""),0600);err!=nil{t.Fatal(err)}
    if got:=steamInventory().Games;len(got)!=0 {t.Fatalf("mismatched ID accepted: %#v",got)}
}
func TestLoopbackOnly(t *testing.T) {
    l,err:=loopbackListener()
    if err!=nil{t.Fatal(err)}
    defer l.Close()
    addr,ok:=l.Addr().(*net.TCPAddr)
    if !ok||!addr.IP.IsLoopback()||addr.Port<=0{t.Fatalf("listener not loopback: %v",l.Addr())}
}
