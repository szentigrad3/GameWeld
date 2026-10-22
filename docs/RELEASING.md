# Release process

The maintainer approves every public release. CI produces test evidence; it never silently uploads executable updates or ships unverified trainer packages.

## First tagged GitHub release

The project source has been pushed to [`main`](https://github.com/szentigrad3/GameWeld). The public `v0.7.0` release assets have **not** yet been published; follow [issue #4](https://github.com/szentigrad3/GameWeld/issues/4).

1. Complete the maintainer license and third-party distribution review in `docs/PUBLICATION-REVIEW.md` and [issue #5](https://github.com/szentigrad3/GameWeld/issues/5).
2. Verify the stable AppImage matches the SHA256 in `docs/BASELINE-SHA256.txt`.
3. Create tag `v0.7.0` at the approved source commit and attach the verified AppImage and SHA256 manifest. Keep binaries outside source Git history.
4. Download the published AppImage and verify its checksum and startup on Linux x86_64.
5. Only then enable the development AppImage workflow, which fetches the runtime by release tag.

Example local release command, after completing the reviews:

```bash
gh auth login
gh release create v0.7.0 \\
  GameWeld-0.7.0-x86_64.AppImage GameWeld-0.7.0-SHA256SUMS.txt \\
  --title 'GameWeld 0.7.0' --notes-file docs/RELEASE-NOTES-0.7.0.md
```

The example assumes the files exist locally and the maintainer has release permissions. **Do not publish a GitHub release until the checksum and distribution review gates pass.**

## Subsequent development release

A maintainer triggers **Build development AppImage** (workflow dispatch); it downloads only the pinned `v0.7.0` bootstrap runtime, rebuilds the development UI/helpers and produces an unsigned Actions artifact for review. Validate it, then create the corresponding prerelease manually.

This project does not publish trainer executables, proprietary manager installers, paid downloads or scraped archives in GitHub Releases.
