//go:build windows

package main

import (
    "os"
    "path/filepath"
    "syscall"
    "unsafe"
)

var (
    shell32       = syscall.NewLazyDLL("shell32.dll")
    shellExecuteW = shell32.NewProc("ShellExecuteW")
)

func utf16Ptr(s string) *uint16 {
    p, err := syscall.UTF16PtrFromString(s)
    if err != nil {
        return nil
    }
    return p
}

func main() {
    if len(os.Args) < 2 {
        os.Exit(2)
    }

    exe := os.Args[1]
    dir := ""
    if len(os.Args) >= 3 {
        dir = os.Args[2]
    } else {
        dir = filepath.Dir(exe)
    }

    verb := utf16Ptr("runas")
    file := utf16Ptr(exe)
    cwd := utf16Ptr(dir)
    if verb == nil || file == nil || cwd == nil {
        os.Exit(3)
    }

    // ShellExecute returns a value > 32 on success. Wine implements the
    // standard "runas" verb by starting the target with the linked full token.
    r, _, _ := shellExecuteW.Call(
        0,
        uintptr(unsafe.Pointer(verb)),
        uintptr(unsafe.Pointer(file)),
        0,
        uintptr(unsafe.Pointer(cwd)),
        1,
    )
    if r <= 32 {
        os.Exit(int(r))
    }
}
