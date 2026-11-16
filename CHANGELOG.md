# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-11-16

Milestone M3: the game is played in a browser, units stand on a positioning grid, every round ends with the lessons it teaches, and the scoring and the strategies were rebalanced.

### Added

- `tft serve` and `tft.server`: a standard-library HTTP server for the browser client and a JSON API over the engine. It listens on `127.0.0.1:8000` unless `--host` and `--port` say otherwise (`--port 0` picks a free port); `--rules` and `--pack` choose the rule set and the market pack, `--open` opens the browser and `--verbose` logs every request. Routes: `GET /api/health`, `GET /api/catalog`, `GET` and `POST /api/matches`, `GET` and `DELETE /api/matches/{id}`, `POST /api/matches/{id}/actions`, `POST /api/matches/{id}/ready`, `POST /api/matches/{id}/step`, `GET /api/matches/{id}/preview`, `GET /api/matches/{id}/spectate` and `GET /api/matches/{id}/replay`. A match is one player seat against one to seven bots, or bots only. Matches live in memory, at most 32 at a time, and there are no accounts. A refusal by the rules is answered with the reason written for players, a bad request with a fixed message, and an unexpected error with `internal error` and nothing more. Every response carries `nosniff`, `no-referrer`, `no-store` and a content security policy.
- The browser client in `src/tft/web/`: plain ES modules with no dependency and no build step, shipped inside the package. The lobby starts a match (number of bots, seed, market or power mode), lists the matches on the server and resumes, spectates or deletes them. The match is laid out as an arena: a stage tracker with the rounds of the current stage and their kind, the hex board in perspective with the bench under it, how each origin moved on the last slice, a scoreboard of every seat, shop cards with art, traits and cost, a rail with the traits and their breakpoints, the components, the items and the augments, and the gold, interest, income, streak, level, experience and health. A click on a unit and then on a cell fields, moves or swaps it; two components craft an item; an item and a unit equip it. After a fight the round result shows how each origin moved, each unit's ticker, its price chart with the entry and the exit, profit, drawdown, trades, size, result and score, the opponent's board, up to three lessons and every fight of the round. Also: scouting a board from the scoreboard, preview odds against every other board, spectating a bots-only match round by round or on auto-play, downloading the replay when the match ends, and keyboard shortcuts (`D` rerolls, `F` buys experience, `E` sells the selected unit, `Escape` closes a dialog or drops the selection). On screens up to 900 pixels wide the layout is one column with the shop right under the bench.
- Original art for every champion, trait, component and interface icon. `art.js` holds flat SVG art as lists of shapes on a 48 by 48 grid. `models.js` holds the 25 champions as 3D figures built from balls, cylinders, cones, boxes and rings, with an eye kit (a white, an iris, a pupil, a point of light, and a lid for the blink) and parts that shine by themselves. `studio.js` is a dependency-free WebGL renderer that draws short clips of a figure into sprite strips: standing (it breathes, sways and blinks), running seen from behind and from the front, and a spinning jump. Every frame has a soft shadow on the ground, an outline in a dark shade of each part's own colour, and light in two soft bands with cool shadows and a rim of light. `figures.js` draws the standing clip of every figure once the page is up and the other clips in the background. Until the figures are drawn, and in a browser without WebGL, the flat portraits are shown in their place.
- Motion. On the board, the bench and the shop a figure stands in its loop, and a unit the player has just fielded, moved or bought drops in and settles.
- The fight scene (`scene.js`): a fight plays full screen before its result, with both boards facing each other, in four beats. The opening bell rings and both boards run at each other. While the slice is traded every unit strikes in bursts, the price chart of its symbol is drawn with its entry and exit, and its size bar moves to what the trade made of its size. Then every unit shows the result (for example `+38%`, `-26%` or `wiped out`): a unit that grew turns to the camera and jumps in a spin, one that shrank slumps, one that was wiped out is knocked over. Then a banner gives Victory, Defeat or Draw, the two scores and the health lost. A click, `Enter`, `Space` or `Escape` skips to the result, and the scene is not played for a player who asks for reduced motion.
- The arena (`arena.js`): scenery around the boards. A night skyline whose towers are candlestick charts, beams of light, drifting sparks, a raised platform with a front wall, pylons with turning coins, statues of the bull and the bear, and the opening bell. The statues, pylons, coins and bell are 3D models drawn by the same renderer (`PROPS` in `models.js`); the rest is drawn by the style sheet. In a fight the far side is tinted warm and the near side cool, and the lobby shows the roster on parade in front of the same skyline. All of it is decoration: it takes no clicks and is hidden from assistive technology, and without WebGL the modelled things are simply absent.
- `tft.formation` and the positioning grid: 4 rows by 7 columns (`board_rows`, `board_cols`), row 0 in front. The row sets the unit's size (`row_size_percent`: 90, 95, 100 and 110 percent) and forgives part of its drawdown (`row_shield_percent`: 40, 20, 0 and 0 percent). In the two back rows a unit with an ally in front of it in the same column is covered and has another `cover_shield_percent` (25) percent forgiven; one with nobody in front is exposed and its drawdown weighs `exposed_penalty_percent` (50) percent more. The column picks which symbol of its origin the unit trades, so spreading an origin over columns diversifies it. A unit fielded without a cell takes its class's default row, centre columns first: Whale and Swing in front, Scalper and Hedger in the second row, every other class at the back. `Player.field_unit` takes an optional cell, and `Player.move_unit` moves a unit or swaps two.
- `tft.lessons`: a round summary for a seat with the opponent, the outcome, both scores, the damage, one line per fielded unit of both boards (cell, symbol, items, profit, drawdown, trades, size, edge, score, the closes of the slice and the bars where it bought and left), each origin's move, and at most 3 lessons picked from 15 rules in a fixed order: empty board slots, a unit wiped out, a stop that fired, a target that fired, a hedge that paid, a loss without an item, over-trading, a strategy that found no signal, two units on one ticker, an exposed unit at the back, idle components or items, a contested champion, low health with a full bank, interest, and streaks.
- `tft.errors.Refusal`: the exception for an action the rules do not allow, with a reason that is safe to show the player. Every planning action raises it instead of a plain `ValueError` (it is a subclass, so existing handlers keep working), and the server shows its reason and nothing of any other exception.
- `tft.view`: the JSON a client draws from. `match_state` gives a seat its own state in full and the public state of the others (board, traits, health, level, gold, streak), or the public state of every seat to a spectator; it includes the rounds of the current stage with their events and progress (`stage_view`) and the grid's numbers (`board_view`). `catalog` lists champions, traits, the one-line strategy descriptions, components, items, augments and the scoring numbers (`scoring_view`).
- Terminal client: `f <unit> [row col]` fields onto a cell, `m <unit> <row> <col>` moves a board unit, the board shows every unit's cell, and each round ends with the seat's result and its lessons.
- `tools/balance_report.py`: trades every class on every window of every symbol of a pack and plays probe policies (an empty board, one unit, every unit in the back rows, every unit in the front rows) against the greedy bot, then prints four tables as text or Markdown: classes, class by origin, champions and policies. `docs/BALANCE.md` explains the method, holds the current tables and states the known limits.
- Node tooling for the client: `package.json`, `eslint.config.js` (ESLint with limits on complexity, nesting and function length), unit tests on Node's test runner in `tests/web/*.test.js` (`npm test`), and Playwright browser tests in `tests/web/e2e` that play the game in headless Chromium against `python -m tft serve` (`npm run test:e2e`).
- CI: a `web` job lints the client, runs its unit tests and its browser tests, and `CI passed` requires it. CodeQL analyses `javascript-typescript` as well, and `Analyze (javascript-typescript)` is a required check (`tools/configure_repository.py`). Dependabot opens weekly grouped pull requests for the npm tooling.
- `tft.name.GAME_NAME`: the product name, Team Fight Tackticktics, in one place. It replaces the working title Ticker Fight Tactics in the client, the terminal banner, the rule file header and the documents.

### Changed

- Scoring (`tft.combat`). In 0.3.0 a unit's score was its size times its risk-adjusted return (the profit minus the penalised drawdown), which is negative for a losing trade: traits, stars and size items made a losing board lose by more, and an empty board beat most boards. Now the *edge* is the strategy's profit minus `risk_penalty_tenths / 10` times its drawdown after shields, in percent, and the score is the unit's size times a result factor: 100 percent plus `result_weight` percent per percent of edge, kept between 0 and `result_cap_percent` percent. With the defaults a flat trade keeps the size, an edge of -10 percent or worse wipes the unit out, an edge of +10 percent or better doubles it, and a fielded unit can never lower its board's score. The board's score is still the sum of its units' scores with the trait and augment bonuses.
- Survivors are now the share of the winning score that was not needed to win, `(winner - loser) / winner`, applied to the winner's units and rounded, with at least one: 12 against 9 keeps a quarter of them. Before, it was the difference over the sum of the two scores.
- Rules, changed values: `risk_penalty_tenths` 5 to 3, `hedge_premium_tenths` 5 to 10, `whale_leverage_tenths` 20 to 15. New rules: `board_rows` 4, `board_cols` 7, `row_size_percent` [90, 95, 100, 110], `row_shield_percent` [40, 20, 0, 0], `cover_shield_percent` 25, `exposed_penalty_percent` 50, `result_weight` 10, `result_cap_percent` 200, `arb_quiet_move_tenths` 20, `arb_adverse_percent` 50, `scalp_threshold_tenths` 15. `Rules` checks that every board row has a size and a shield and that the board has a cell for every level.
- Strategies. The Scalper trades a bar only when the bar before it moved at least `scalp_threshold_tenths / 10` (1.5) percent; before, it traded every bar. The Arbitrageur earns `arb_capture_percent` (20) percent of the part of a bar's move up to `arb_quiet_move_tenths / 10` (2.0) percent and loses `arb_adverse_percent` (50) percent of the part beyond it; before, it earned a share of every move and could only lose its trading costs. The Hedger pays a premium of 1.0 percent instead of 0.5 and the Whale's leverage is 1.5 instead of 2.0. A strategy that takes one position reports the bars where it entered and left (`Outcome.marks`).
- A unit's symbol is picked by its column on the grid, not by its place in the board list.
- Replay format 3: `field` takes an optional row and column and `move` is a new action. Format 2 files are refused, and the rule digest changed with the rules, so a replay recorded under 0.3.0 cannot be played back.
- The same window of days is no longer dealt two rounds in a row when the pack has more than one: `MarketPack.deal` takes the previous window to avoid. Two windows may still overlap.
- The preview scores every board on the same bootstrapped slices (`preview_field`), so the odds against different opponents come from the same simulated markets.
- `CombatResult` names both sides and carries both scores, also for a draw. In `tft.combat`, `unit_trade` became `trade_unit` and returns a `UnitTrade`, `board_trades` lists them for a board, and `sample_points` gave way to `points`.
- The board holds at most as many units as it has cells, whatever the level and the items say.
- `tools/jpl_check.py`, rule JPL07: a call to a function annotated `-> None` anywhere in the checked files is exempt, not only in the same file, and so are the standard library's server methods that are called for their effect.

### Removed

- `Rules` no longer has `market_power_per_stage`, `market_boss_factor_tenths` and `market_survivors`. Nothing had read them since 0.3.0, whose notes listed `market_survivors` as removed although the field stayed. A rule file that still sets one of them is refused as an unknown rule.

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

[Unreleased]: https://github.com/MITRAKER/TFT/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/MITRAKER/TFT/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/MITRAKER/TFT/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/MITRAKER/TFT/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/MITRAKER/TFT/releases/tag/v0.1.0
