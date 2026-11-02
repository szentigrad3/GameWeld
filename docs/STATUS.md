# GameWeld Desktop 0.4.0-alpha — source and verification status

## Host evidence carried into 0.4.0

The user ran the 0.2.0 desktop IPC fixture on CachyOS. READY, PING/PONG, STATUS and STOP/STOPPED all passed, the launcher exited zero, and the temporary prefix was removed. Time to READY was approximately 20.7 seconds. This is a confirmed real-host **desktop supervisor** success for the exact pinned Win64 test fixture, not trainer compatibility.

## Batch 0.3.0 lifecycle work — now exercised on CachyOS

- Optional one-, two- or three-session Wine benchmark with explicit consent and owned-process cancellation.
- Separate cold-start timing (time until READY) and sub-millisecond IPC round-trip measurement.
- Bounded read-only /proc census matching only an exact owned WINEPREFIX within the new owned process group, with two post-exit checks against previously observed PID/starttime identities.
- Neither this census nor zero post-exit matches prove all detached Wine helpers were reaped.
- GTK4 IPC tab run-count selector and mean startup display. The 0.3 benchmark CLI was host-verified; visual tab layout still needs review.

## Remaining restrictions

No third-party trainers, game-memory access, live game attachment, Steam launch-option changes, arbitrary executable selection, or Steam Proton prefix reuse. The Wine benchmark executes only the pinned original 4096-byte GameWeld Win64 v2 probe. All private process information is kept out of shareable JSON.

Development-environment tests use original fake Wine children for the protocol, not the actual Linux GTK4 desktop runtime. Real GTK4 visual and 0.4.0 Wine integration testing must take place on CachyOS.

## Verified Batch 0.3.0 host result and 0.4.0 follow-up

2026-11-02 CachyOS: two real Win64 v2 fixture sessions succeeded. Time to READY:
9025 ms and 6824 ms; session totals 13263 ms and 11061 ms. Roundtrip latency
(PING/STATUS/STOP) was 0.014–0.031 ms, confirming startup dominates this
fixture. The benchmark observed one exact-prefix identity per session in the
owned Linux process group; those identities were absent in two post-exit
checks. This does not verify that all detached Wine helper processes ended.

Desktop 0.4.0 adds opt-in local numeric-only benchmark history, a History tab,
strict report import, CLI comparisons and deduplication. Full GTK4 user
interaction, including importing your existing 0.3 report, still requires a CachyOS test.

## Batch 0.5.0-alpha

Two-session prior test mean READY 7,924.5 ms; later one-session user test 35,247 ms.
Both passed IPC protocol and owned prefix cleanup, but the slower result is one
observation, not evidence of the cause. Startup performance comparison, weighted
history statistics, and separate spawn-vs-READY timing fields added. The legacy
history schema is unchanged. Graphical GTK4 testing and real new timing evidence
are still pending on CachyOS. No game attachment or trainer execution.

## Batch 0.6.0-alpha

The user supplied an explanation for the 35,247 ms READY observation: Wine
Mono installer activity. This remains user-observed context, not a verified
mechanism proven by the stored timing report. Benchmarks now support an
allowlisted startup context in the local history envelope, with a CLI and GTK4
button to mark the newest record. Explicitly tagged setup sessions are not
used in routine/unclassified baselines; the full population statistics remain
visible. Historical schema-1 timing summaries and SHA-256 IDs are unchanged.

A new user-level Linux desktop installer copies only allowlisted project
Python modules and writes a KDE/GNOME application shortcut without sudo. It
refuses unmanaged conflicting launchers and symlinks, and preserves user
settings, notes and benchmark history on uninstall. A real CachyOS GUI/menu
launch still needs verification. The Batch77 pinned fixture, consent gating and
no-game-access boundaries remain unchanged.

## 0.7.0-alpha local trainer experiment

GameWeld now supports an opt-in, hash-reviewed local Win32/Win64 EXE launch, with isolated system Wine or a separately authorised pre-existing Steam game Proton prefix. An actual third-party trainer has **not** been run on the developer host. Existing Batch77 fixture IPC evidence does not verify trainers. GUI behaviour and Proton compatibility require the user's real CachyOS evidence. Only the user-supplied original EXE is executed; no trainer provider files are distributed. No game-memory access, trainer-to-game attachment, anticheat compatibility or detached child cleanup is verified by the app.
