# GameWeld PC2 RC1 — release-facing build gate

The development-only interface lives on `feature/pc2-source-backend`. A
separate `release/pc2-ui-cleanup` branch compiles a cleaner RC1-facing UI with
`GAMEWELD_PC2_PUBLIC_UI=1`. This changes presentation, **not** the permissions
or semantics of any game launch, trainer patch, or Steam operation.

## Keep in public builds

- Overview and Library, with a working **Play with WeMod** button.
- Per-game validation, an explicit **Play with WeMod** action, and visible
  disclosure that DeckCheatz may modify the selected game's Proton prefix.
  First-time managed DeckCheatz installation still requires separate consent.
- Settings: window-size reset, managed DeckCheatz update with rollback, and
  WeMod Enhancer detect/install/patch/restore controls.
- Genuine errors and useful support-export actions. Do not invent verified
  compatibility for untested titles.

## Exclude from customer-facing RC1 presentation

- "SOURCE TEST", "DISCOVERY TEST", "Experimental direct", personal field-test
  claims, and development-only branding.
- Smoke-test, live-render, manual Steam launch-gate, and debug-only buttons.
- Internal test numbers and the developer-only "Advanced Providers" tab.
- `PC2-DEVELOPMENT-ONLY.txt` from candidate AppImages.

Internal C/Python tests and diagnostic code stay in the source repository.
Never remove safety gates, rollback code, or automated tests merely to make a
release look finished.

## Build the candidate

```bash
GAMEWELD_PC2_PUBLIC_UI=1 bash scripts/pc2-build-local-appimage.sh
```

This produces `GameWeld-PC2-RC1-CANDIDATE-*.AppImage`, includes its SHA256
checksum and license notices, and runs the read-only extracted package audit.
This is a **release candidate for local validation**, not a published release.

## Evidence / blockers

- [x] Development source GTK window sizing and reset field-tested on KDE Wayland.
- [x] Original local AppImage: resize, restore, reset, reopening and WeMod UI.
- [x] Original local AppImage: Astrometica + WeMod launched; user closed game
      early (the upstream fast-exit message was not proof of launch failure).
- [ ] Clean RC1 UI builds and passes CI in both development and public mode.
- [x] Release-facing **Play Game** requests the owning Steam, Heroic or
      Lutris platform, without initiating a trainer or requiring dev mode.
- [ ] Platform-native launch ownership and **verified same-session trainer**
      attachment; see [platform-native launch design](PC2-PLATFORM-NATIVE-LAUNCH.md).
      The previous Astrometica + WeMod success used direct Proton, not Steam
      supervision. Do not advertise Steam-native trainer integration as complete.
- [ ] Clean RC1 AppImage tested in person for one-click Play with WeMod,
      automatic Windows game EXE detection, no raw preview/picker/extra launch
      confirmation, and correct first-time installer consent.
- [ ] Compatibility checks across at least one additional Linux distribution,
      plus portability inspection for GLIBC, GTK and bundled runtime dependencies.
- [ ] Verify all shipped third-party licenses, notices and redistribution rights.
- [ ] Audit visible disabled/non-working controls; hide them or complete them.
- [ ] Set stable version, release notes and reproducible/checksummed assets.
- [ ] Explicit approval before publishing to GitHub Releases / AppImageHub.

**Do not promote this candidate to a stable GitHub release until the unchecked
items are complete.**
