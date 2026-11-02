# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| The latest stable release (the `stable` tag) | Yes |
| Pre-releases (`vX.Y.Z-rc.N`) | Until the matching stable release ships |
| Older releases | No. Please upgrade. |

## Reporting a vulnerability

Please do **not** open a public issue for a security problem.

Report it privately through GitHub's vulnerability reporting form:
<https://github.com/MITRAKER/TFT/security/advisories/new>. Include the affected
version, steps to reproduce, and what an attacker could achieve.

What to expect:

- an acknowledgement within 3 business days;
- an assessment and a plan within 7 days;
- a fix in a patch release, a published advisory, and credit to the reporter unless they prefer to stay anonymous.

## What protects this repository

- CodeQL analysis of the code and of the workflow files on every change and weekly.
- `pip-audit` against known vulnerabilities on every change and weekly; dependency review on every pull request.
- Dependabot alerts, security updates and weekly version updates.
- Secret scanning with push protection.
- Every GitHub Action pinned to a full commit SHA; every workflow token limited to the permissions it needs.
- Protected `main` branch and immutable `vX.Y.Z` release tags.
- Signed build provenance attestations and SHA-256 checksums for every release artifact.
