# Release process

The maintainer approves every public release. CI produces test evidence; it never silently uploads executable updates or ships unverified trainer packages.

## First GitHub publication

1. Verify the source rights and review the third-party checklist in `docs/PUBLICATION-REVIEW.md`.
2. Create an empty repository `szentigrad3/GameWeld` on GitHub (don't initialize it with a separate README/LICENSE).
3. Push this source tree as `main`, then enable Actions and (recommended) private vulnerability reporting.
4. Publish the verified **0.7.0** stable AppImage and its SHA256 manifest as GitHub Release `v0.7.0`.
5. Check that the uploaded stable AppImage hash equals `docs/BASELINE-SHA256.txt` before building 0.8.0 Dev 1.

Example local commands from the repository root after creating the repository:

```bash
git init -b main
git add .
git commit -m "chore: prepare GameWeld source for GitHub"
git remote add origin https://github.com/szentigrad3/GameWeld.git
git push -u origin main
```

Upload release assets separately from Git history:

```bash
gh auth login
gh release create v0.7.0 \
  GameWeld-0.7.0-x86_64.AppImage GameWeld-0.7.0-SHA256SUMS.txt \
  --title 'GameWeld 0.7.0' --notes-file docs/RELEASE-NOTES-0.7.0.md
```

The `gh` example requires the referenced files to exist locally and a repository account with release permissions. **Don't publish a GitHub release until the SHA256 and licensing checks pass.**

## Subsequent development release

A maintainer triggers **Build development AppImage** (workflow dispatch); it downloads only the pinned `v0.7.0` bootstrap runtime, rebuilds the development UI/helpers and produces an unsigned Actions artifact for review. Validate it, then create the corresponding prerelease manually.

This project does not publish trainer executables, proprietary manager installers, paid downloads or scraped archives in GitHub Releases.
