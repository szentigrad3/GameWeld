# Maintenance workflow

The repository owner controls publication and release approvals. Work on code changes in branches and review them in pull requests before merging to `main`.

## Routine triage

- Review incoming bug and feature issues. Reproduce bugs with a minimal fixture when possible.
- Run offline regression checks for every change. Changes to session handoffs also require live Steam/Heroic/Lutris verification.
- For trainer download integrations, separate page evidence, unsigned-catalog checksums and independently authenticated releases.
- Run publication and third-party licensing checks before packaging binaries.
- Ship AppImage artifacts separately as GitHub Release assets; do not commit executable trainers or built runtimes.

## Working with the connected GitHub account

The repository owner can request reviews, issue triage, source edits, feature branches, pull requests and release notes through the GitHub connection. Proposed changes should be traceable to actual commits and tests. Merging, approving downloads and publishing releases remain explicit owner decisions.

Useful requests: "Review open GameWeld issues and identify critical bugs", "Prepare a PR for the FLiNG release inspector", "Compare CI results for the latest PR", and "Draft the next GameWeld release notes".

GitHub may display the account or automation identity used to perform repository actions. Do not forge commit authorship or hide a service identity in repository metadata.
