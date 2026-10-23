package main

import (
	"errors"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
)

// Session observation is intentionally conservative. A Steam environment
// association is not proof that a particular game executable is running.
// This only reads same-user Linux /proc metadata and never signals processes.
const (
	maxSessionProcEntries = 8192
	maxSessionEvidence = 32
	maxSessionEnvBytes = 128 << 10
)
type sessionProcessEvidence struct {
	PID int `json:"pid"`
	Comm string `json:"comm"`
	Association string `json:"association"`
}
type steamSessionReport struct {
	Mode string `json:"mode"`
	AppID string `json:"appid"`
	State string `json:"state"`
	AssociatedProcessCount int `json:"associated_process_count"`
	Processes []sessionProcessEvidence `json:"processes"`
	GameRunningConfirmed bool `json:"game_running_confirmed"`
	ScanTruncated bool `json:"scan_truncated"`
	Message string `json:"message"`
}
func steamEnvironmentMatch(contents []byte, appid string) string {
	for _, candidate := range []string{"SteamAppId=", "SteamGameId=", "STEAM_COMPAT_APP_ID="} {
		want := candidate + appid
		for _, entry := range strings.Split(string(contents), "\x00") {
			if entry == want { return strings.TrimSuffix(candidate,"=") }
		}
	}
	return ""
}
func limitedProcEnv(path string) []byte {
	f,err:=os.Open(path)
	if err!=nil{return nil}
	defer f.Close()
	// Proc files often report Size()==0 despite having readable contents.
	b,err:=io.ReadAll(io.LimitReader(f,maxSessionEnvBytes+1))
	if err!=nil||len(b)>maxSessionEnvBytes {return nil}
	return b
}
func sameUserProc(dir string) bool {
	info,err:=os.Stat(dir)
	if err!=nil{return false}
	st,ok:=info.Sys().(*syscall.Stat_t)
	return ok&&st.Uid==uint32(os.Getuid())&&info.IsDir()
}
func readSessionProcess(procRoot string,pid int,appid string) (sessionProcessEvidence,bool) {
	dir:=filepath.Join(procRoot,strconv.Itoa(pid))
	if !sameUserProc(dir) {return sessionProcessEvidence{},false}
	match:=steamEnvironmentMatch(limitedProcEnv(filepath.Join(dir,"environ")),appid)
	if match=="" {return sessionProcessEvidence{},false}
	commRaw,err:=os.ReadFile(filepath.Join(dir,"comm"))
	if err!=nil{return sessionProcessEvidence{},false}
	name:=strings.TrimSpace(string(commRaw))
	// A process name can be user-controlled. Limit it to a display-safe
	// 15-byte Linux comm value; no command lines or environment are returned.
	if len(name)>15 {name=name[:15]}
	if name=="" {name="unknown"}
	for _,c:=range name {if c<' '||c==127{name="unknown";break}}
	return sessionProcessEvidence{PID:pid,Comm:name,Association:match},true
}
func inspectSteamSession(procRoot,appid string) steamSessionReport {
	result:=steamSessionReport{
		Mode:"read_only",AppID:appid,State:"no_process_evidence",
		Processes:[]sessionProcessEvidence{},GameRunningConfirmed:false,
		Message:"No exact same-user Steam app-ID process association observed; game state is unknown",
	}
	if !validSteamID(appid) {result.State="invalid_appid";return result}
	entries,err:=os.ReadDir(procRoot)
	if err!=nil {
		result.State="unavailable"
		result.Message="Process observation is unavailable; game state unknown"
		return result
	}
	seen:=0
	for _,e:=range entries {
		id,err:=strconv.Atoi(e.Name())
		if err!=nil||id<=0 {continue}
		seen++
		if seen>maxSessionProcEntries {result.ScanTruncated=true;break}
		if process,ok:=readSessionProcess(procRoot,id,appid);ok{
			result.AssociatedProcessCount++
			if len(result.Processes)<maxSessionEvidence{
				result.Processes=append(result.Processes,process)
			} else {result.ScanTruncated=true}
		}
	}
	if result.AssociatedProcessCount>0 {
		result.State="associated_processes_observed"
		result.Message="Exact Steam app-ID environment association observed; actual game executable and trainer/session ownership NOT verified"
	}
	return result
}
func procScanAvailable() bool {
	_,err:=os.Stat("/proc")
	return !errors.Is(err,os.ErrNotExist)&&err==nil
}
