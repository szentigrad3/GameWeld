# GameWeld — Linux Desktop Application

**Development transition (Batch78). Not a stable release.**

GameWeld is moving toward a source-built Linux desktop application for organising installed games, viewing read-only compatibility diagnostics, and managing **explicitly authorised** standalone sidecar sessions. The near-term UI target is GTK4 on Linux, with CachyOS/Arch among the development hosts.

> The historical repository on `main` contains a different, older GameWeld GTK3/AppImage trainer-manager implementation (0.7.0 / 0.8.0 Dev 1). This branch documents the transition; the Batch78 GTK4 app source is **not yet merged into this GitHub branch**. Do not treat the old packaging instructions as the new desktop app's build instructions.

## New direction

- **Desktop library:** Steam game discovery, local search and favourites.
- **Diagnostics:** read-only installed-game, Wine and Proton status, with uncertainty shown accurately.
- **IPC Lab:** a GameWeld-owned, SHA-256-pinned Win64 probe with READY → PING/PONG → STATUS/OK → STOP/STOPPED protocol.
- **Session management:** explicit consent, bounded runtime, per-session temporary Wine prefixes and lifecycle observation.
- **Reproducible releases:** complete source, automated tests and source-built Linux deliverables before publishing as stable.

The Batch77 prototype demonstrated the four-stage Win64 IPC handshake in two real isolated system-Wine runs. That evidence is **not proof** of compatibility with third-party trainers, live games, Steam-managed Proton or anti-cheat systems.

## Safety and compatibility boundaries

No game-memory reads/writes, automatic trainer attachment, anti-cheat bypass, arbitrary executable launching, Steam launch-option mutation or third-party trainer redistribution is enabled by this transition. Experimental native-lab fixtures and game diagnostics must remain explicitly marked as such.

## Project status and navigation

- [Desktop-first roadmap](ROADMAP.md)
- [Architecture and release gates](docs/DESKTOP-ARCHITECTURE.md)
- [Legacy work and migration register](docs/LEGACY-TRANSITION.md)
- [Current historical build instructions](docs/BUILDING.md) — **legacy GTK3/AppImage path only**
- [Security](SECURITY.md)
- [Third-party licensing](THIRD-PARTY.md)

**Release policy:** no public AppImage or native Linux binary should be labelled ready until its source, packaging, checksums, clean-install test and relevant host validations are available. Do not infer that a GitHub Release asset exists from old roadmap references.

GameWeld is an independent project and is not affiliated with Valve, WeMod, FLiNG, Epic or game publishers.
