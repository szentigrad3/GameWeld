# Snapshot provenance

- Input: `gameweld-0.7.0-source.zip` (historical stable sources) and curated `GameWeld-GitHub-Repository-0.8.0-dev1.zip` (common project files).
- The stable versions of `gameweld-native-040.c`, `gameweld-stability-preflight.py`, `gameweld-trainer-updates.py` and the stable release notes come from the original stable archive.
- Six common files differed between the historical stable and development tree; two differences were documentation/build entrypoints and have been rewritten as stable-specific documentation and a wrapper targeting the original stable packager.
- Development-only build scripts, tests and workflow definitions are omitted.
- Reference game artwork is omitted from this source snapshot, but remains in the existing **binary** and must be separately addressed.
- This snapshot is source for review. Do not claim it yields the same AppImage bytes without running the old runtime-based packager and comparing hashes.
