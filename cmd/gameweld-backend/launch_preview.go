package main

import (
    "fmt"
    "net/http"
    "strconv"
)

// previewSteamLaunch intentionally does not execute Steam, edit LaunchOptions,
// run a trainer, or create Wine/Proton processes. The caller chooses what to do
// with the URI in a later, separately authorized stage.
type steamLaunchPreview struct {
    Mode string `json:"mode"`
    Provider string `json:"provider"`
    AppID string `json:"appid"`
    Name string `json:"name"`
    URI string `json:"uri"`
    LaunchEnabled bool `json:"launch_enabled"`
    Message string `json:"message"`
}

func validSteamID(id string) bool {
    if len(id)<1 || len(id)>10 { return false }
    if id[0]=='0' { return false }
    for _,c:=range id { if c<'0'||c>'9'{return false} }
    n,err:=strconv.ParseUint(id,10,32)
    return err==nil && n>0
}
func steamLaunchPlan(installed []game,appid string) (steamLaunchPreview,bool) {
    if !validSteamID(appid) {return steamLaunchPreview{},false}
    for _,g:=range installed {
        if g.AppID!=appid || g.InstallDir=="" {continue}
        return steamLaunchPreview{
            Mode:"preview_only",Provider:"steam",AppID:appid,Name:g.Name,
            URI:fmt.Sprintf("steam://rungameid/%s",appid),
            LaunchEnabled:false,
            Message:"Preview only. No Steam, game, trainer or compatibility tool was launched.",
        },true
    }
    return steamLaunchPreview{},false
}
func steamLaunchPreviewHandler(w http.ResponseWriter,r *http.Request){
    if !method(w,r,"GET") {return}
    id:=r.URL.Query().Get("appid")
    inv:=steamInventory()
    plan,ok:=steamLaunchPlan(inv.Games,id)
    if !ok {
        response(w,404,nil,"No installed Steam manifest matches that app ID; preview not available")
        return
    }
    response(w,200,plan,"")
}
