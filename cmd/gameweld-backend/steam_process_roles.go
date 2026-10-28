package main

import (
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// Observations of process names and environment keys, NOT verified game
// executable identity or a trainer attach target.
type processRoleEvidence struct {
	Comm string `json:"comm"`
	ExecutableName string `json:"executable_name"`
	Role string `json:"role"`
	HasCompatdataEnv bool `json:"has_compatdata_env"`
	HasWineprefixEnv bool `json:"has_wineprefix_env"`
}
type steamProcessRoleReport struct {
	Mode string `json:"mode"`
	AppID string `json:"appid"`
	State string `json:"state"`
	AssociatedProcessCount int `json:"associated_process_count"`
	Roles []processRoleEvidence `json:"roles"`
	ScanTruncated bool `json:"scan_truncated"`
	GameExecutableVerified bool `json:"game_executable_verified"`
	PrefixOwnershipVerified bool `json:"prefix_ownership_verified"`
	TrainerHandoffEnabled bool `json:"trainer_handoff_enabled"`
	Message string `json:"message"`
}
func safeProcessLabel(input string) string {
	if input=="" {return "unavailable"}
	base:=filepath.Base(input)
	if len(base)>64 {return "redacted"}
	for _,r:=range base {
		if !((r>='a'&&r<='z')||(r>='A'&&r<='Z')||(r>='0'&&r<='9')||r=='.'||r=='-'||r=='_'||r=='+') {
			return "redacted"
		}
	}
	if base=="."||base==".." {return "redacted"}
	return base
}
func environmentKeyPresent(contents []byte,key string) bool {
	if len(contents)==0{return false}
	prefix:=key+"="
	for _,entry:=range strings.Split(string(contents),"\x00") {
		if strings.HasPrefix(entry,prefix)&&len(entry)>len(prefix) {return true}
	}
	return false
}
func classifyAssociatedProcess(comm,executable string) string {
	s:=strings.ToLower(comm+" "+executable)
	if strings.Contains(s,"steamwebhelper")||strings.Contains(s,"steam-runtime")||
		strings.Contains(s,"steamservice")||strings.Contains(s,"reaper")||
		strings.Contains(s,"pressure-vessel") {return "steam_helper"}
	if strings.Contains(s,"wineserver")||strings.Contains(s,"services.exe")||
		strings.Contains(s,"explorer.exe")||strings.Contains(s,"conhost.exe")||
		strings.Contains(s,"winedevice.exe")||strings.Contains(s,"rpcss.exe")||
		strings.Contains(s,"plugplay.exe") {return "wine_runtime"}
	// A Windows .exe name is only a heuristic, never game proof.
	if strings.HasSuffix(strings.ToLower(comm),".exe") {return "windows_executable_candidate"}
	// wine64-preloader also hosts game code, so its binary name alone
	// is NOT enough to label this process as a harmless runtime helper.
	if strings.Contains(s,"wine64")||strings.Contains(s,"wine-preloader") {
		return "wine_loader_ambiguous"
	}
	return "other_associated"
}
func roleForObservedProcess(procRoot string,process sessionProcessEvidence,appid string) (processRoleEvidence,bool) {
	dir:=filepath.Join(procRoot,strconv.Itoa(process.PID))
	if !sameUserProc(dir){return processRoleEvidence{},false}
	env:=limitedProcEnv(filepath.Join(dir,"environ"))
	if steamEnvironmentMatch(env,appid)=="" {return processRoleEvidence{},false}
	exeName:="unavailable"
	// /proc/PID/exe is a symlink: Readlink gets metadata, does not run/follow exe.
	if target,err:=os.Readlink(filepath.Join(dir,"exe"));err==nil{
		exeName=safeProcessLabel(target)
	}
	name:=safeProcessLabel(process.Comm)
	return processRoleEvidence{
		Comm:name,ExecutableName:exeName,
		Role:classifyAssociatedProcess(name,exeName),
		HasCompatdataEnv:environmentKeyPresent(env,"STEAM_COMPAT_DATA_PATH"),
		HasWineprefixEnv:environmentKeyPresent(env,"WINEPREFIX"),
	},true
}
func inspectSteamProcessRoles(procRoot,appid string) steamProcessRoleReport {
	result:=steamProcessRoleReport{
		Mode:"read_only",AppID:appid,State:"no_process_evidence",
		Roles:[]processRoleEvidence{},GameExecutableVerified:false,
		PrefixOwnershipVerified:false,TrainerHandoffEnabled:false,
		Message:"Names, executable basenames and compatibility environment-key presence are heuristics only; no ownership verified",
	}
	if !validSteamID(appid){result.State="invalid_appid";return result}
	session:=inspectSteamSession(procRoot,appid)
	result.State=session.State
	result.AssociatedProcessCount=session.AssociatedProcessCount
	result.ScanTruncated=session.ScanTruncated
	for _,process:=range session.Processes {
		if role,ok:=roleForObservedProcess(procRoot,process,appid);ok{
			result.Roles=append(result.Roles,role)
		}
	}
	if len(result.Roles)<session.AssociatedProcessCount {result.ScanTruncated=true}
	return result
}
