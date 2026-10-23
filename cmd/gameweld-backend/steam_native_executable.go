package main

import (
	"io"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// Native executable evidence is a read-only corroboration, never permission
// to attach trainers or control processes. Paths are never returned.
type nativeExecutableCandidate struct {
	ExecutableName string `json:"executable_name"`
	State string `json:"state"`
	ELFClass string `json:"elf_class"`
}
type nativeExecutableReport struct {
	Mode string `json:"mode"`
	AppID string `json:"appid"`
	State string `json:"state"`
	AssociatedProcessCount int `json:"associated_process_count"`
	Candidates []nativeExecutableCandidate `json:"candidates"`
	NativeELFCandidateCount int `json:"native_elf_candidate_count"`
	ScanTruncated bool `json:"scan_truncated"`
	GameExecutableVerified bool `json:"game_executable_verified"`
	TrainerHandoffEnabled bool `json:"trainer_handoff_enabled"`
	Message string `json:"message"`
}
func pathInsideDirectory(root, target string) bool {
	if root=="" || target=="" || !filepath.IsAbs(root) || !filepath.IsAbs(target) {
		return false
	}
	relative,err:=filepath.Rel(root,target)
	if err!=nil {return false}
	return relative!="." && relative!=".." && !strings.HasPrefix(relative,".."+string(filepath.Separator)) && !filepath.IsAbs(relative)
}
func elfClass(path string) string {
	f,err:=os.Open(path)
	if err!=nil {return "unreadable"}
	defer f.Close()
	var header [5]byte
	if _,err:=io.ReadFull(f,header[:]);err!=nil {return "not_elf"}
	if string(header[:4])!="\x7fELF" {return "not_elf"}
	switch header[4] {
	case 1:return "ELF32"
	case 2:return "ELF64"
	default:return "unknown_elf_class"
	}
}
func inspectNativeCandidate(procRoot string,process sessionProcessEvidence,appid,installDir string) nativeExecutableCandidate {
	result:=nativeExecutableCandidate{ExecutableName:"unavailable",State:"executable_unavailable",ELFClass:"unavailable"}
	procDir:=filepath.Join(procRoot,strconv.Itoa(process.PID))
	if !sameUserProc(procDir) || steamEnvironmentMatch(limitedProcEnv(filepath.Join(procDir,"environ")),appid)=="" {
		result.State="association_disappeared"
		return result
	}
	linked,err:=os.Readlink(filepath.Join(procDir,"exe"))
	if err!=nil {return result}
	result.ExecutableName=safeProcessLabel(linked)
	if !filepath.IsAbs(linked)||strings.HasSuffix(linked," (deleted)") {
		result.State="executable_path_unavailable"
		return result
	}
	rootReal,err:=filepath.EvalSymlinks(installDir)
	if err!=nil {
		result.State="install_directory_unavailable"
		return result
	}
	rootStat,err:=os.Stat(rootReal)
	if err!=nil||!rootStat.IsDir(){
		result.State="install_directory_unavailable"
		return result
	}
	exeReal,err:=filepath.EvalSymlinks(linked)
	if err!=nil {
		result.State="executable_path_unavailable"
		return result
	}
	if !pathInsideDirectory(rootReal,exeReal) {
		result.State="outside_install_directory"
		return result
	}
	info,err:=os.Stat(exeReal)
	if err!=nil||!info.Mode().IsRegular() {
		result.State="executable_not_regular"
		return result
	}
	result.ELFClass=elfClass(exeReal)
	if result.ELFClass=="ELF32"||result.ELFClass=="ELF64" {
		result.State="native_elf_inside_install_directory"
	} else {
		result.State="inside_install_directory_not_validated_elf"
	}
	return result
}
func inspectNativeSteamExecutable(procRoot,appid,installDir string) nativeExecutableReport {
	report:=nativeExecutableReport{
		Mode:"read_only",AppID:appid,State:"no_process_evidence",
		Candidates:[]nativeExecutableCandidate{},
		GameExecutableVerified:false,TrainerHandoffEnabled:false,
		Message:"ELF header and install-directory containment are corroborating evidence, not authenticated game identity",
	}
	if !validSteamID(appid) {report.State="invalid_appid";return report}
	session:=inspectSteamSession(procRoot,appid)
	report.State=session.State
	report.AssociatedProcessCount=session.AssociatedProcessCount
	report.ScanTruncated=session.ScanTruncated
	for _,process:=range session.Processes {
		item:=inspectNativeCandidate(procRoot,process,appid,installDir)
		report.Candidates=append(report.Candidates,item)
		if item.State=="native_elf_inside_install_directory" {
			report.NativeELFCandidateCount++
		}
	}
	if len(report.Candidates)<report.AssociatedProcessCount {
		report.ScanTruncated=true
	}
	return report
}
