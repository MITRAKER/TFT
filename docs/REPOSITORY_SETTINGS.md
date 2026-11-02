# Repository settings

Most of the pipeline lives in files in this repository. These settings live in
GitHub itself and need an administrator. Apply them all with one command, from
any machine where the [GitHub CLI](https://cli.github.com) is logged in as an
admin of the repository:

```bash
gh auth login
python tools/configure_repository.py --repo MITRAKER/TFT --dry-run   # shows the steps
python tools/configure_repository.py --repo MITRAKER/TFT             # applies them
```

The command is safe to repeat: it updates the rulesets in place instead of
duplicating them. The tables below describe what it sets, so the state can also
be checked by hand under **Settings** after cloning or transferring the
repository, and whenever GitHub adds a new protection.

## Code security (Settings, Code security)

| Setting | Wanted | Why |
| --- | --- | --- |
| Dependency graph | On | Required by Dependabot and by dependency review |
| Dependabot alerts | On | Alerts for vulnerable dependencies |
| Dependabot security updates | On | Automatic pull requests that fix alerts |
| Grouped security updates | On | One pull request per group instead of one per package |
| Dependabot version updates | On (configured by `.github/dependabot.yml`) | Weekly tooling and Actions updates |
| Code scanning, CodeQL | **Advanced** setup through `.github/workflows/codeql.yml`; leave *Default setup* off | Default and advanced setups conflict; the workflow version is reviewable and pinned |
| Secret scanning | On | Detect committed credentials |
| Push protection | On | Block pushes that contain credentials |
| Non-provider patterns and validity checks | On | Broader secret detection |
| Private vulnerability reporting | On | The reporting channel in `SECURITY.md` |

## Rules (Settings, Rules, Rulesets)

**Protect main** (branch ruleset, target: default branch)

- Restrict deletions, block force pushes.
- Require a pull request before merging; require conversation resolution.
- Require status checks to pass, strict (branch must be up to date): `CI passed`, `Standards passed`, `Analyze (python)`, `Analyze (actions)`.
- Bypass: repository administrators, so the owner can still push an urgent fix directly. Remove the bypass once more than one person maintains the project.

**Protect release tags** (tag ruleset, target: `refs/tags/v*`)

- Restrict updates and deletions; creation stays open so releases can be tagged.
- `stable` is deliberately not covered: the Release workflow moves it.

## Actions (Settings, Actions, General)

- Actions permissions: allow actions created by GitHub and verified creators, or the pinned list used here.
- Workflow permissions: **Read repository contents and packages permissions**. Every workflow declares the extra permissions it needs.
- "Allow GitHub Actions to create and approve pull requests": off.
- Fork pull request workflows from outside collaborators: require approval for first-time contributors.

## General

- Default branch `main`.
- Automatically delete head branches after merge: on.
- Description and topics filled in, so the community profile is complete.
