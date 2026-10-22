# Contributing

Thanks for helping improve GameWeld.

## Before opening a pull request

1. Search for an existing issue and describe the behaviour you're fixing.
2. Keep changes scoped. In particular, don't casually change Steam/Proton, Heroic or Lutris session ownership.
3. Run `./scripts/ci-check.sh` and include relevant test results.
4. Don't commit downloaded trainers, commercial manager binaries, game artwork, Wine prefixes, private logs, credentials or user configuration.
5. Describe what was tested offline and what still requires a real-game test.

Use branches such as `fix/selection-context` or `feature/provider-metadata`, with focused commits. Pull requests should include the reason for the change, a summary of changed behaviour, tests, risks and migration notes if state files change.

Do not automatically enable unverified downloads or disable source verification in order to make a test pass.

## Code and release policy

GameWeld's application source is MIT licensed. Third-party components retain their own licenses. New third-party code or assets need explicit permission/license information. For vulnerabilities, follow [SECURITY.md](SECURITY.md), not public issues.
