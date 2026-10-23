# GameWeld 0.7.0 source tagging

This snapshot is **not yet tagged** on GitHub. Its purpose is to prevent a `v0.7.0` tag pointing to 0.8.0 Dev 1 source on `main`.

Before creating the release branch or tag, complete the license and provenance review in the live repository (issues #4 and #5). The current 0.7.0 binary contains reference artwork and a Paul44-derived native trainer whose redistribution status is not established. The stable packager inherits binaries from RC11 and is not source-complete.

After approval, commit this reviewed source snapshot to a **dedicated stable-source branch**, tag that exact commit `v0.7.0`, then publish the SHA256-pinned tested binary and release notes. Do not attach an unreviewed AppImage just to unblock CI.
