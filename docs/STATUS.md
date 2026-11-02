# GameWeld Desktop 0.2.0-alpha status

## Verified in development container

- 36 offline tests and Python source compilation passed.
- Original Batch77 fixture's byte count, PE format and pinned hash agree.
- Four-stage original protocol verified with an owned fake Wine launcher; malformed response fails closed.
- Generated source ZIP integrity check passes.

## Host-only gates still open

- GTK4 UI layout, selection, notes editing and live status on CachyOS.
- IPC Lab run with **real system Wine** on CachyOS. This new desktop integration has not been exercised on the host yet.
- Complete cleanup of unobserved detached Wine helpers is not provable.
- No live Steam game / Proton process identity or trainer functionality has been validated.

## Historical evidence

Earlier Batch77 ran the original Win64 v2 fixture under isolated system Wine in two verified CachyOS sessions. That is a separate, known good baseline and does **not** substitute for testing the new UI supervisor.
