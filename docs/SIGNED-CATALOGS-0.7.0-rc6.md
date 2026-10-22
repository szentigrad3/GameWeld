# Signed catalog v2 format and trust setup (RC6)

RC6 supports optional Ed25519 **key-pinned** manifests for a single trainer provider. No signing keys are bundled. Do not generate and pin your own key then describe that catalog as authenticated by FLiNG or another real publisher. A source is publisher-authenticated only if you independently verified that the key belongs to that publisher.

## Signing envelope

JSON object with exactly these keys:

```json
{
  "schema": 2,
  "provider": "fling",
  "issued_at": "2026-10-20T00:00:00Z",
  "expires_at": "2026-10-25T00:00:00Z",
  "key_fingerprint": "<lowercase SHA256 of the 44-byte Ed25519 SPKI DER>",
  "entries": [
    {
      "id": "example-only",
      "game": "Example Game",
      "provider": "fling",
      "version": "1.0",
      "url": "https://flingtrainer.com/example-only.exe",
      "sha256": "<64 lowercase hex SHA256 of the actual downloadable ZIP or EXE>"
    }
  ],
  "signature": "<base64 Ed25519 signature over the canonical payload>"
}
```

**This example is not an actual publisher release or usable manifest.** RC6 requires a real publisher-hosted URL ending `.exe` or `.zip`, a valid SHA256, an approved provider, an expiry no more than 90 days after issue, and a valid signature. All entries must have the exact envelope provider.

Payload signed or verified: all top-level properties *except `signature`*, represented by Python `json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')`. No extra envelope keys accepted. Duplicate JSON keys rejected.

The `key_fingerprint` is `SHA256` of the DER SubjectPublicKeyInfo encoding of the Ed25519 public key (44 bytes; standard prefix `302a300506032b6570032100`, then 32 raw public-key bytes).

## CLI (local files only)

The script is included as `usr/libexec/gameweld-trainer-updates.py` inside the AppImage and under `scripts/` in the source ZIP. Use `python3 <path-to-script> ...`. `openssl` 3 must be installed on your Linux system.

```bash
python3 scripts/gameweld-trainer-updates.py fingerprint-key --key publisher-public.pem

# Only proceed after checking this SHA256 against an independent trusted channel:
python3 scripts/gameweld-trainer-updates.py pin-key \
  --provider fling --key publisher-public.pem \
  --expected-fingerprint <64_hex_sha256_spki_fingerprint> --confirm

python3 scripts/gameweld-trainer-updates.py import-signed \
  --file publisher-signed-catalog.json --confirm

python3 scripts/gameweld-trainer-updates.py trust-report
python3 scripts/gameweld-trainer-updates.py check --game 'Example Game' --plain
```

To explicitly remove an existing pin (which removes its downgrade protection):

```bash
python3 scripts/gameweld-trainer-updates.py unpin-key --provider fling --confirm
```

Pins are stored in `~/.config/gameweld/trusted-publisher-keys.json` with restrictive file permissions; active catalogs are in `~/.config/gameweld/trainer-catalog.json`. A previous catalog is retained as `trainer-catalog.json.previous` after replacement. No network access is required for key pinning, import or audit. Provider-authenticated keys and signed manifests are not currently supplied by GameWeld.
