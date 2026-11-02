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
