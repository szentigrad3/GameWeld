// GameWeld PC2 source backend: experimental read-only compatibility surface.
// All install, game mapping and provider mutation endpoints fail closed.
// This does not replace the validated PC1 runtime.
package main

import (
    "encoding/json"
    "fmt"
    "log"
    "net"
    "net/http"
    "os"
    "path/filepath"
    "sort"
    "strings"
    "time"
)

const version = "0.7.0-pc2-backend-dev1"
const maxManifestBytes = 2 << 20

type game struct {
    AppID string `json:"appid"`
    Name string `json:"name"`
    InstallDir string `json:"install_dir"`
    SelectedTool string `json:"selected_tool"`
    WandFound bool `json:"wand_found"`
}
type inventory struct {
    Roots []string
    Libraries []string
    Games []game
}
type envelope struct {
    OK bool `json:"ok"`
    Data any `json:"data,omitempty"`
    Error string `json:"error,omitempty"`
}

func tokens(b []byte) []string {
    // Extract VDF quoted atoms; tolerate braces, tabs and unrelated entries.
    s := string(b)
    out := make([]string, 0, 128)
    for i := 0; i < len(s); i++ {
        if s[i] != '"' { continue }
        i++
        var v strings.Builder
        for i < len(s) {
            if s[i] == '"' { break }
            if s[i] == '\\' && i+1 < len(s) {
                next := s[i+1]
                if next == '\\' || next == '"' {
                    v.WriteByte(next); i += 2; continue
                }
            }
            v.WriteByte(s[i]); i++
        }
        out = append(out, v.String())
    }
    return out
}
func val(t []string, key string) string {
    for i := 0; i+1 < len(t); i++ {
        if strings.EqualFold(t[i], key) { return t[i+1] }
    }
    return ""
}
func readSmall(path string) []byte {
    fi, err := os.Stat(path)
    if err != nil || !fi.Mode().IsRegular() || fi.Size() > maxManifestBytes { return nil }
    data, err := os.ReadFile(path)
    if err != nil { return nil }
    return data
}
func addDir(dest *[]string, seen map[string]bool, path string) {
    if path == "" { return }
    path, err := filepath.Abs(path)
    if err != nil { return }
    if real, err := filepath.EvalSymlinks(path); err == nil { path = real }
    info, err := os.Stat(path)
    if err != nil || !info.IsDir() || seen[path] { return }
    seen[path] = true
    *dest = append(*dest, path)
}
func steamInventory() inventory {
    out := inventory{Roots: []string{}, Libraries: []string{}, Games: []game{}}
    home, err := os.UserHomeDir()
    if err != nil || home == "" { return out }
    seen := make(map[string]bool)
    roots := []string{
        os.Getenv("STEAM_ROOT"),
        filepath.Join(home, ".steam", "steam"),
        filepath.Join(home, ".steam", "root"),
        filepath.Join(home, ".local", "share", "Steam"),
        filepath.Join(home, ".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam"),
    }
    for _, root := range roots { addDir(&out.Roots, seen, root) }
    seen = make(map[string]bool)
    for _, root := range out.Roots {
        addDir(&out.Libraries, seen, root)
        for _, location := range []string{
            filepath.Join(root, "steamapps", "libraryfolders.vdf"),
            filepath.Join(root, "config", "libraryfolders.vdf"),
        } {
            atoms := tokens(readSmall(location))
            for i := 0; i+1 < len(atoms); i++ {
                if strings.EqualFold(atoms[i], "path") {
                    addDir(&out.Libraries, seen, atoms[i+1])
                }
            }
        }
    }
    found := make(map[string]bool)
    for _, lib := range out.Libraries {
        paths, _ := filepath.Glob(filepath.Join(lib, "steamapps", "appmanifest_*.acf"))
        sort.Strings(paths)
        for _, p := range paths {
            if len(out.Games) >= 1024 { break }
            data := readSmall(p)
            if data == nil { continue }
            atoms := tokens(data)
            id, name := val(atoms, "appid"), val(atoms, "name")
            if id == "" || name == "" || found[id] || filepath.Base(p) != "appmanifest_"+id+".acf" { continue }
            valid := true
            for _, ch := range id { if ch < '0' || ch > '9' { valid = false; break } }
            if !valid { continue }
            dir := val(atoms, "installdir")
            install := ""
            if dir != "" && dir != "." && dir != ".." && filepath.Base(dir) == dir {
                install = filepath.Join(lib, "steamapps", "common", dir)
            }
            found[id] = true
            out.Games = append(out.Games, game{AppID: id, Name: name, InstallDir: install})
        }
    }
    sort.Slice(out.Games, func(i,j int) bool { return strings.ToLower(out.Games[i].Name) < strings.ToLower(out.Games[j].Name) })
    return out
}
func response(w http.ResponseWriter, code int, data any, errorMessage string) {
    w.Header().Set("Content-Type", "application/json")
    w.Header().Set("Cache-Control", "no-store")
    w.Header().Set("X-Content-Type-Options", "nosniff")
    w.WriteHeader(code)
    _ = json.NewEncoder(w).Encode(envelope{OK: code >= 200 && code < 300, Data: data, Error: errorMessage})
}
func method(w http.ResponseWriter, r *http.Request, allowed string) bool {
    if r.Method == allowed { return true }
    w.Header().Set("Allow", allowed)
    response(w, 405, nil, "Method not allowed")
    return false
}
func router() http.Handler {
    mux := http.NewServeMux()
    mux.HandleFunc("/api/status", func(w http.ResponseWriter,r *http.Request) {
        if !method(w,r,"GET") { return }
        inv := steamInventory()
        response(w,200,map[string]any{
            "version":version, "steam_roots":inv.Roots, "libraries":inv.Libraries,"games":inv.Games,
            "wand_installed":false,"wand_healthy":false,"base_compatible":false,
            "base_proton":"","wand_tool":"",
            "verify_message":"Compatibility setup unavailable in PC2 development backend",
        },"")
    })
    mux.HandleFunc("/api/job",func(w http.ResponseWriter,r *http.Request){
        if !method(w,r,"GET") { return }
        response(w,200,map[string]any{"running":false,"action":"","message":"","progress":0,
            "error":"","done":false,"started":"0001-01-01T00:00:00Z"},"")
    })
    mux.HandleFunc("/api/verify",func(w http.ResponseWriter,r *http.Request){
        if !method(w,r,"GET") { return }
        response(w,409,nil,"Verification unavailable; no changes made")
    })
    mux.HandleFunc("/api/health",func(w http.ResponseWriter,r *http.Request){
        if !method(w,r,"GET") { return }
        response(w,200,map[string]any{"healthy":false,"commands":false,"input":false,
            "plugin":false,"signature_ok":false,"trace":"",
            "message":"Read-only backend: trainer health unavailable"},"")
    })
    for _, endpoint := range []string{"/api/install","/api/set-game"} {
        ep:=endpoint
        mux.HandleFunc(ep,func(w http.ResponseWriter,r *http.Request){
            if !method(w,r,"POST") { return }
            response(w,501,nil,"PC2 source backend: "+ep+" disabled until compatibility testing")
        })
    }
    mux.HandleFunc("/",func(w http.ResponseWriter,r *http.Request){
        response(w,404,nil,"Unknown endpoint")
    })
    return mux
}
func loopbackListener() (net.Listener,error) {return net.Listen("tcp4","127.0.0.1:0")}
func serve() error {
    listener,err := loopbackListener()
    if err != nil { return err }
    defer listener.Close()
    port:=listener.Addr().(*net.TCPAddr).Port
    // First line is the GTK frontend's startup handshake.
    fmt.Printf("Wand Native UI: http://127.0.0.1:%d/\n",port)
    server:=&http.Server{
        Handler:router(),
        ReadHeaderTimeout:5*time.Second,ReadTimeout:10*time.Second,
        WriteTimeout:10*time.Second,IdleTimeout:30*time.Second,
        ErrorLog:log.New(os.Stderr,"gameweld-backend: ",log.LstdFlags),
    }
    return server.Serve(listener)
}
func main() {
    if err:=serve(); err!=nil {log.Fatal(err)}
}
