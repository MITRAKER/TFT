# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `docs/PRD.md`: the product requirements document for Ticker Fight Tactics, a trading auto-battler.
- `tft.roster`: six origins, eight classes and twenty-five original trader-champions with trait tiers and synergy bonuses.
- `tft.environment`: the headless, deterministic game environment (rounds, shop odds, shared pool, star-ups, levels, augments, carousel, PvE rounds, damage, eliminations), the `CombatResolver` seam with a mock `PowerResolver`, and a greedy baseline bot.
- Repository scaffold: CI (tests on Python 3.11 to 3.14 and Windows, build and smoke test), Standards (ruff, `mypy --strict`, NASA/JPL Power of Ten checker), CodeQL for Python and workflows, Security (`pip-audit`, dependency review), OpenSSF Scorecard, and a Release workflow that verifies the tag, builds, attests provenance, publishes a GitHub Release and moves the `stable` tag.
- Dependabot for GitHub Actions and Python tooling, CODEOWNERS, issue and pull request templates, security policy, contributing guide and code of conduct.
- `tft.economy`: example module with `interest`, `streak_bonus`, `round_income` and `rounds_to_reach`.
- `tools/jpl_check.py`: Power of Ten checker with `# noqa: JPLxx` suppressions and GitHub annotations.
- `tools/release_version.py`: tag-to-version check used by the Release workflow.
- `tools/configure_repository.py`: applies the GitHub-side settings (Dependabot alerts and security updates, secret scanning, private vulnerability reporting, the `main` and release-tag rulesets) through the GitHub CLI.

[Unreleased]: https://github.com/MITRAKER/TFT/commits/main
