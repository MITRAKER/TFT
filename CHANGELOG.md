# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-11-02

Milestone M2: combat is decided by real market history, items are stops and targets, and the Time Machine previews the odds.

### Added

- `tft.market`: market packs of aligned daily bars per symbol grouped by origin, slices dealt per round, JSON and gzip files, builders from Yahoo Finance *chart* and *spark* responses, and the built-in `starter` pack (29 US stocks, 60 trading days, from the Day Trader skill's MIT fixtures).
- `tft.strategies`: one strategy per class (hold, breakout with a bracket, mean reversion, scalping, hedging, range capture, quant, leveraged whale) returning profit, drawdown and trades.
- `tft.items`: eight components, 36 completed items with additive effects on stop, target, size and drawdown shield, Prospectus emblems that grant traits, and the Index Fund that adds a board slot. Components drop on PvE rounds and carousels; bots craft and equip them.
- `tft.combat`: `MarketResolver` scores every board on the round's slice (unit size from power and items, trait and augment bonuses, drawdown penalty); `preview` bootstraps slices to estimate the odds; `PowerResolver` keeps the first mock behind the same `CombatContext` interface.
- The scripted Market: PvE rounds now fight a board that grows with the stage, through the active resolver.
- Client: `c <i> <j>` crafts, `i <unit> <item>` equips, `p` previews the odds; `--pack` and `--no-market` on `play`, `sim` and `replay`; the round report names the market slice.
- `tools/build_market_pack.py`: builds packs from a directory of saved responses or by fetching symbols.
- Replay format 2: actions carry a list of numbers; replays record the pack they were played on.

### Changed

- `Rules` gained the market, item and strategy knobs (`slice_bars`, `risk_penalty_tenths`, `preview_samples`, `components_per_pve_round`, `max_items_per_unit`, stop, target, cost and leverage settings); `market_survivors` was removed.
- The combat resolver interface takes a `CombatContext` (the round and its slice).

## [0.2.0] - 2026-11-02

Milestone M1: the game is playable from a terminal, and a match can be replayed and verified.

### Added

- `tft.rules`: every tunable number in one `Rules` object; `tft rules` prints it as TOML, `--rules FILE` loads overrides, and a digest ties replays to the rule set they were recorded under.
- `tft.environment`: rounds in two phases (`start_round`, `finish_round`) with an outside-controlled seat, augment offers to choose from, benching, and `scout` views of the other boards.
- `tft.replay`: the replay format (seed, rules digest, the seat's actions per round, result), `run_replay` and `verify_replay`.
- `tft.cli` and the `tft` command: `play` against bots with a plain-text board, shop, bench, scouting and augment picks; `sim` for bots-only matches; `replay --verify`; `rules`.
- Release workflow: *Run workflow* with a version creates the tag and releases without a local git push.
- `tools/bootstrap_windows.cmd`: installs Python and the GitHub CLI if missing, signs in, and applies the repository settings in one run.

## [0.1.0] - 2026-11-02

First tagged release: the repository pipeline and the M0 mock of the game.

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

[Unreleased]: https://github.com/MITRAKER/TFT/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/MITRAKER/TFT/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/MITRAKER/TFT/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/MITRAKER/TFT/releases/tag/v0.1.0
