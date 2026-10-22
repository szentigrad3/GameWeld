# Patched Wine crypt32 payload

A public Wand Native release should bundle the x86_64 and i386 Wine `crypt32.dll`
files built from the same GE-Proton/Wine baseline as the tested release, with the
included `CERT_SHA256_HASH_PROP_ID` compatibility patch applied.

Maintainers: after building `GE-Proton-Wand-SHA256.tar.gz`, run:

```bash
./scripts/extract-wand-proton-payload.sh ~/src/wand-ge-proton/build/GE-Proton-Wand-SHA256.tar.gz
```

The public installer never disables signature verification. These DLLs implement
the documented Windows certificate SHA-256 property behavior used by Tophat.
The corresponding source patch is in `patches/wine-crypt32-cert-sha256-prop.patch`.
