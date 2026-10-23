# PC1 Windows elevation helper — source correspondence check

The packaged `usr/libexec/gameweld-elevate.exe` was compared with a local cross-compile from `cmd/gameweld-elevate/main.go` in the PC1 source snapshot.

The test used Go 1.23.2 (`GO111MODULE=off`, `GOOS=windows`, `GOARCH=amd64`, `CGO_ENABLED=0`, `go build -trimpath -ldflags='-s -w'`). The rebuild was performed from the legacy source-path layout reported by `go version -m` in the packaged PE.

| Property | Packaged | Rebuilt |
| --- | --- | --- |
| Size | 1,286,656 bytes | 1,286,656 bytes |
| SHA256 | `36d93b5597aec71dc54ea2d15647a0b6b0a84747ce7c3d2d1a373d59652513ef` | `8447b219cb965edcbc10b58ab01eec6aa1437393a635f58fef1db2c868dacb5c` |
| Target | Windows amd64 | Windows amd64 |
| Go compiler | 1.23.2 | 1.23.2 |

Byte comparison: 41 byte values differ in a total of 1,286,656 bytes, at file offsets 220, 1552–1571 and 1615–1634 (zero-based). Offsets 1552–1571 and 1615–1634 are the two 20-byte variable portions of the embedded Go build ID; offset 220 is a PE header byte. Every other byte matches exactly. The original and rebuilt `go version -m` records agree on compiler, target, toolchain flags and source import path.

**Meaning:** this provides strong evidence that the helper's actual compiled implementation corresponds to the available Go source. The files do not have identical SHA256 hashes, so it is not accurate to call the helper bit-for-bit reproducible. This check does not grant copyright or third-party redistribution rights and does not establish behavior of the other runtime components.

To reproduce the comparison, build `cmd/gameweld-elevate/main.go` with the flags above, and use `go version -m`, `go tool buildid`, `cmp -l` and SHA256 hashes to compare it with the packaged PE. Some Go build ID bytes can vary with the source-path context.

Related: GitHub issues #4, #5, #6 and draft PR #10.
