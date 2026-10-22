# Security policy

## Supported versions

Security fixes are currently targeted at the latest stable release (0.7.0) and the active 0.8.0 development branch.

## Reporting vulnerabilities

Please **do not** post exploitable security details, secret material or malicious trainer samples in a public issue. Use GitHub's **Report a vulnerability** / private vulnerability reporting feature when enabled, or contact the repository owner privately through GitHub.

Useful details: affected version, affected provider/launcher, reproduction steps, scope, logs with secrets and local paths redacted, and whether an executable was actually run. Never include real authentication tokens or paid software binaries.

## Trust model

- GameWeld treats publisher web pages and filename labels as unverified evidence.
- A checksum supplied by an untrusted catalog proves consistency with that catalog, **not** publisher identity.
- Provider-authenticated signing keys must be independently verified before pinning.
- Third-party trainers and manager applications are not bundled with the source repository.
