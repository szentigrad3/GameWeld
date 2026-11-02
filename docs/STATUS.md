# GameWeld Desktop 0.3.0-alpha — source and verification status

## Host evidence carried into 0.3.0

The user ran the 0.2.0 desktop IPC fixture on CachyOS. READY, PING/PONG, STATUS and STOP/STOPPED all passed, the launcher exited zero, and the temporary prefix was removed. Time to READY was approximately 20.7 seconds. This is a confirmed real-host **desktop supervisor** success for the exact pinned Win64 test fixture, not trainer compatibility.

## 0.3.0 changes requiring new host validation

- Optional one-, two- or three-session Wine benchmark with explicit consent and owned-process cancellation.
- Separate cold-start timing (time until READY) and sub-millisecond IPC round-trip measurement.
- Bounded read-only /proc census matching only an exact owned WINEPREFIX within the new owned process group, with two post-exit checks against previously observed PID/starttime identities.
- Neither this census nor zero post-exit matches prove all detached Wine helpers were reaped.
- GTK4 IPC tab run-count selector and mean startup display.

## Remaining restrictions

No third-party trainers, game-memory access, live game attachment, Steam launch-option changes, arbitrary executable selection, or Steam Proton prefix reuse. The Wine benchmark executes only the pinned original 4096-byte GameWeld Win64 v2 probe. All private process information is kept out of shareable JSON.

Development-environment tests use original fake Wine children for the protocol, not the actual Linux GTK4 desktop runtime. Real GTK4 visual and 0.3.0 Wine integration testing must take place on CachyOS.
