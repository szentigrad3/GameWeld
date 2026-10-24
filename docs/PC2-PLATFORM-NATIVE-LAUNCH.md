# GameWeld PC2 — platform-owned launch contract (RC1)

**Decision:** game launch is owned by the platform where the game is installed.
GameWeld discovers the game, starts it through that platform, then manages an
optional trainer in the *verified same game/runtime session*.

This is the direction for the normal **Play** and **Play with WeMod** controls.
Do not replace the currently field-tested DeckCheatz 1.x direct-Proton path
until an alternative has passed a real game + trainer + restart test. The existing
direct path is a development compatibility fallback, not proof that all games
work without Steam/Heroic/Lutris supervising them.

## Platform ownership

| Installation source | Owner | Launch request | Session proof |
| --- | --- | --- | --- |
| Steam Windows games | Steam | `steam -applaunch <appid>` or validated `steam://rungameid/<appid>` | Steam AppID game process/reaper, exact compatdata and selected Proton |
| Steam non-Steam shortcuts | Steam | resolved `steam://rungameid/<shortcut-id>` | exact shortcut identity + live compatibility runtime |
| Epic / GOG / Amazon via Heroic | Heroic | existing `gameweld-heroic-launch` helper using Heroic's installed-game identity | Heroic-managed game PID, prefix and Wine/Proton owner |
| Lutris | Lutris | existing validated `gameweld-lutris-session` helper | Lutris game ID, launch URI, prefix, configured runner and live game PID |
| Standalone | User-selected install | selected executable via configured Wine/Proton | exact executable, compatible prefix and live PID |

Never choose an arbitrary similar executable from another installation. Never
launch a second copy of a game after the platform has successfully started it.

## One-click sequence

1. User clicks **Play with WeMod** once.
2. Resolve **provider and installed game identity**. Do not open an EXE picker,
   display raw JSON, or require an extra confirmation for an already-established
   provider. First-time provider installation or risky changes still require
   consent. Do not silently modify a Wine prefix if that user consent has not
   yet been established.
3. Send a single launch request to the owning platform. Returning zero from
   `steam -applaunch` / a URI handler confirms only the request, **not** that
   the game started.
4. Observe and verify the *actual* game session: identity, live process,
   selected runtime and exact game-specific prefix. Allow for launchers and
   child-process handoff; do not mistake Steam/Proton wrappers for the game.
5. Only if the WeMod provider supports it, start/attach the trainer in the
   verified session. A trainer window alone is not a successful attachment.
6. Present honest states: `starting_game` → `game_verified` →
   `trainer_attaching` → `trainer_verified`; or a precise actionable failure.

**Release requirement:** the status must not say "Play with WeMod succeeded"
when only Steam, DeckCheatz or WeMod started. Check an actual trainer-in-game
session with the packaged AppImage.

## DeckCheatz 1.x limitation

The upstream DeckCheatz 1.x documented Steam integration is a wrapper of
Steam's `%command%`. Its current direct-Proton mode in GameWeld invokes
a manually constructed `proton waitforexitandrun game.exe` command, which
**does not use Steam as launch supervisor**. This worked for Astrometica in a
specific user test, but it cannot be assumed reliable for DRM/authentication,
Steam APIs, or every title.

Do **not** simply replace that command with `steam -applaunch` and then claim
the trainer attaches; Steam owns a separate process tree. A separately verified
same-session injection/attach route is needed. If no supported attach route
exists for an installation, show an honest unsupported status rather than
launching a trainer into another prefix or pretending a game launch was enough.

No user should need to manually edit Steam Launch Options in the default flow;
neither should GameWeld silently change Launch Options to get DeckCheatz working.

## Existing code paths (as of the release cleanup branch)

- `on_play_normal`: Steam `-applaunch`, Steam shortcut `rungameid`,
  `spawn_heroic_normal`, `spawn_lutris_normal`.
- `on_pc2_steam_game_only`: separately gated/validated game-only request.
- `pc2_deckcheatz_flow`: currently validates and executes the direct-Proton
  DeckCheatz route. **Not platform-owned**.
- `scripts/gameweld-deckcheatz-direct.py`: constructs direct Proton command
  with `will_invoke_steam_client: false`.

Reuse the existing provider/session helpers; do not create a second universal
launch implementation without verified compatibility checks.

## Implementation progress

The release-facing **Play with WeMod** now uses the experimental
`scripts/gameweld-steam-wemod-platform.py` route instead of launching the game
EXE directly: resolve installed game/Proton, request `steam -applaunch`, wait
for an exact game AppID/executable/prefix observation, then join the
game's active Proton Wine server with its own Wine binary to request an
installed WeMod.exe/Wand.exe. The earlier second `proton runinprefix` invocation
did not display WeMod in the Astrometica live test and was replaced. This
requires no Steam Launch Options edits. **Trainer attachment and Electron
rendering remain unverified**.
When runtime or matching game-process evidence is missing, it does not launch a
second standalone game EXE or claim success. The existing direct DeckCheatz 1.x
launch remains available in developer-only builds as a regression fallback.

The release-facing Overview and Library now expose **Play Game**, which uses the
owning platform without starting a trainer: Steam via the validated PC2 Steam
handoff, Steam shortcuts via their exact numeric `rungameid`, and existing
Heroic/Lutris launch helpers. Internal test-only launch controls remain hidden
from the public-facing UI. The original working direct-Proton **Play with WeMod**
path is deliberately unchanged.

`scripts/gameweld-platform-session.py` provides read-only, fail-closed
*game-process identity* evidence for Steam: exact AppID, expected executable
process name and exact compatdata path. It never asserts that WeMod attached, a
window appeared, or Steam supervision was independently proven.

## RC1 test matrix (not yet complete)

- [x] Previous packaged local PC2 build: Astrometica game + WeMod launched;
      user exited early. This was **direct Proton**, not platform-native.
- [x] PC2 release-facing native **Play Game** wired for Steam, Steam
      shortcuts, Heroic and Lutris with game-only request status.
- [x] Read-only exact game-process identity observer and synthetic fixture tests.
- [x] Release **Play with WeMod** code requests Steam-owned game launch before
      an existing WeMod runtime, rather than invoking the game .exe.
- [x] Steam-owned Astrometica launch with correct Steam AppID and real
      game PID observed in the user's session log (PID 162175, AppID 2353250).
- [ ] WeMod trainer starts/attaches in that *same* Steam game/prefix session.
- [ ] Already-running game: no duplicate launch or prefix collision.
- [ ] Game-only launch remains usable when WeMod attach is unavailable.
- [ ] Heroic Epic/GOG/Amazon installed-game launch through Heroic.
- [ ] Lutris game launch through Lutris with correct runner and prefix.
- [ ] Steam shortcut uses its exact `rungameid` identifier.
- [ ] No Steam Launch Options changes, no unnecessary EXE picker and no raw JSON.
- [ ] Package integrity, cross-distribution compatibility and license audit.

Keep this gate open for GitHub RC1 promotion until platform ownership and
trainer-session attachment have real-game evidence.
