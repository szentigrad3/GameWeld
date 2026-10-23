# GameWeld 0.7.0 PC1 — Release review

The source of **Publication Candidate 1** is on branch `release/0.7.0-pc1`. It is intentionally separate from the 0.8.0 Dev 1 code on `main`.

This branch must **not** be tagged `v0.7.0` and described as the original tested stable source: PC1 modifies that build to reduce redistribution risk. If an eventual PC1-derived release is approved, prepare a tag and release assets that accurately identify its final contents.

## Required gates before publication

1. Complete the license and provenance review for GameWeld branding and remaining inherited compiled runtimes. See [issue #5](https://github.com/szentigrad3/GameWeld/issues/5).
2. Run the branch's offline checks and make sure the packaged helper scripts match the source snapshot.
3. Build only from the pinned stable input; check the candidate AppImage SHA256 and inspect extracted assets.
4. Confirm **actual PC1** Steam, Heroic and Lutris game/trainer handoffs. A general 'works' report is helpful but not a per-launcher result.
5. Decide and document the final source tag/version independently of 0.8.0 `main`.
6. Obtain maintainer approval, then publish verified binaries, checksums, source notices and release notes.

The baseline input is SHA256-pinned but the current packaging pipeline **is not source-complete**, and offline checks cannot establish permission to redistribute third-party material. Publishing remains blocked until review is completed.

Follow [GitHub issue #4](https://github.com/szentigrad3/GameWeld/issues/4) for the release decision.
