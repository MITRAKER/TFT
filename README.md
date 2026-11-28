# TFT

[![CI](https://github.com/MITRAKER/TFT/actions/workflows/ci.yml/badge.svg)](https://github.com/MITRAKER/TFT/actions/workflows/ci.yml)
[![Standards](https://github.com/MITRAKER/TFT/actions/workflows/standards.yml/badge.svg)](https://github.com/MITRAKER/TFT/actions/workflows/standards.yml)
[![CodeQL](https://github.com/MITRAKER/TFT/actions/workflows/codeql.yml/badge.svg)](https://github.com/MITRAKER/TFT/actions/workflows/codeql.yml)
[![Security](https://github.com/MITRAKER/TFT/actions/workflows/security.yml/badge.svg)](https://github.com/MITRAKER/TFT/actions/workflows/security.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/MITRAKER/TFT/badge)](https://scorecard.dev/viewer/?uri=github.com/MITRAKER/TFT)
[![Release](https://img.shields.io/github/v/release/MITRAKER/TFT?include_prereleases&sort=semver)](https://github.com/MITRAKER/TFT/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.11 | 3.12 | 3.13 | 3.14](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)

**Team Fight Tackticktics** is a strategy game in the auto-battler
genre in which the pieces are trading strategies, the gold is capital, and the
battles are real market sessions replayed from history. It is played in a
browser (`tft serve`) or in a terminal (`tft play`). The product requirements
are in [docs/PRD.md](docs/PRD.md) and the state of the balance in
[docs/BALANCE.md](docs/BALANCE.md).

The engine lives in [`src/tft`](src/tft):

| Module | What it holds |
| --- | --- |
| `tft.rules` | Every tunable number, loadable from TOML |
| `tft.economy` | Income, interest and streak rules |
| `tft.roster` | The mock roster: six origins, eight classes, twenty-five original trader-champions |
| `tft.environment` | The headless, deterministic game environment: rounds and stages, shop odds, the shared pool, star-ups, levels, augments, carousel, component drops, PvE rounds against the scripted Market, damage and eliminations, with a greedy bot |
| `tft.formation` | The positioning grid: cells, the default row of each class, and what a row, cover and exposure do to a unit's size and drawdown |
| `tft.market` | Market packs: aligned bar series per symbol grouped by origin, slices, the built-in starter pack, and builders from Yahoo Finance responses |
| `tft.strategies` | One trading strategy per class, scored on a slice: profit, drawdown, trades, and the bars where it entered and left |
| `tft.items` | Eight components, 36 completed items, emblems; effects on stops, targets, size and drawdown |
| `tft.combat` | The resolvers (`PowerResolver`, `MarketResolver`), the scoring (edge, result factor, survivors), and the preview odds on bootstrapped slices |
| `tft.lessons` | Round summaries: what every unit of both boards did on its symbol, how the origins moved, and up to three lessons |
| `tft.replay` | Replay files: seed, rules digest, pack and the seat's actions reproduce a match |
| `tft.view` | The JSON a client draws from: a seat's view, a spectator's view, the catalogue |
| `tft.server` | The web server (`tft serve`): a JSON API over the engine, and the browser client's files |
| `tft.cli` | The command-line client (`tft serve`, `play`, `sim`, `replay`, `rules`) |
| `tft.errors` | `Refusal`, the exception for an action the rules do not allow, with a reason for the player |
| `tft.name` | The product name, in one place |

The browser client lives in [`src/tft/web`](src/tft/web). It is plain ES
modules with no dependency and no build step, and it ships inside the package:

| File | What it holds |
| --- | --- |
| `index.html`, `style.css` | The page and its styles, including the motion of the fight scene |
| `app.js` | The screens and the wiring: lobby, match, round result, spectating, keyboard |
| `logic.js` | Pure helpers with no DOM, tested under Node: what a click means, labels, cell effects, standings |
| `dom.js` | Element helpers and pictures |
| `pieces.js` | Unit tokens, hex grids, price charts, item tiles |
| `battle.js` | The script of a fight, worked out from the round's result: who moves where, who hits whom, who falls when |
| `scene.js` | The fight scene: plays that script on the floor |
| `arena.js` | The scenery around the boards: skyline, platform, statues, pylons, bell, sparks |
| `art.js` | Flat SVG art as lists of shapes: portraits, trait and component glyphs, icons |
| `models.js` | The 25 champions and the arena's props as 3D figures built from solid shapes |
| `studio.js` | A small WebGL renderer that draws clips of a figure into sprite strips |
| `figures.js` | Draws every figure and prop once and hands out the elements |

The repository ships with the quality and security pipeline described below,
so every change is tested, linted, type-checked, scanned and held to the
NASA/JPL Power of Ten rules before it reaches `main`, and every release is a
tagged, checksummed build with signed provenance.

## Play

### In the browser

```bash
pip install "git+https://github.com/MITRAKER/TFT.git@stable"
tft serve --open
```

`tft serve` starts a web server on your machine at `http://127.0.0.1:8000/`
and `--open` opens it in your browser. Press *Play* in the lobby and you sit
against seven bots.

| Flag | Default | What it does |
| --- | --- | --- |
| `--host HOST` | `127.0.0.1` | The IPv4 or IPv6 address to listen on; `0.0.0.0` listens on every address |
| `--allow-host NAME` | none | A DNS name the server may be reached by, besides `localhost` and plain addresses; repeat it for more |
| `--port PORT` | `8000` | The port to listen on; `0` picks a free one |
| `--rules FILE` | the built-in rules | The TOML rule file every match on the server is played under |
| `--pack FILE` | the starter pack | The market pack fights are decided on |
| `--open` | off | Open the client in the default browser |
| `--verbose` | off | Log every request |

The server has no accounts and keeps its matches in memory, at most 32 of
them: everybody who can reach it can see, spectate and delete every match, and
a restart loses them all. Keep it on `127.0.0.1` unless you mean to share it.

To play from another device on your network, start it with `--host 0.0.0.0`
and open `http://<this machine's IP address>:8000/` there. The server answers
to `localhost` and to plain IP addresses; to reach it by a name, such as the
machine's name on the network or the public name of a proxy in front of it,
name it with `--allow-host`:

```bash
tft serve --host 0.0.0.0 --allow-host supercom
```

What the client shows:

- **Lobby.** A new match with one to seven bots, a seed and market or power
  mode; *Watch bots play* for a bots-only match; the matches on the server,
  to resume, spectate or delete.
- **Stage tracker.** The rounds of the current stage: fights against other
  seats, rounds against the Market, carousels and augment rounds, with the
  current round marked.
- **Board and bench.** The grid of 4 rows by 7 columns in perspective, front
  row at the top, and the bench of nine slots under it. Click a unit, then a
  cell, to field it, move it or swap two units. A unit at the back with
  nobody in front of it gets a red rim.
- **Scoreboard.** Every seat by health. Click a seat to scout its board and
  its traits.
- **Shop.** Five cards with the unit's picture, name, origin, class and cost,
  next to the gold, the interest pips, the next income, the streak, the
  level, the experience, the shop odds and the health.
- **Rails.** The traits on the board with their breakpoints and bonuses; the
  components and items (click two components to craft, an item and then a
  unit to equip); the augments.
- **Fight scene.** *Fight* plays the round full screen in an arena, as a
  fight: the bell rings, the units leave their cells and close with the
  enemy, strike by hand or shoot from a distance, call out their signature
  moves, lose health and fall until one side has nobody left. The result was
  decided before by the trades; the fight is scripted to end the same way,
  with the weakest trades falling first. Then every unit shows what its own
  trade did, and a banner gives the result. A click, `Enter`, `Space` or
  `Escape` skips it.
- **Round result.** How each origin moved; for every unit its ticker, its
  price chart with the entry and the exit, profit, drawdown, trades, size,
  result and score; the opponent's board; up to three lessons; every fight
  of the round.
- **Preview odds.** Your share of wins against each other board on
  bootstrapped slices: a simulation of the past, never a promise.
- **Spectating.** Every seat's board, health, level, gold, streak and traits,
  round by round or on auto-play.
- **Replay.** When the match ends, *Download replay* saves it in the format
  `tft replay` reads.

Keyboard: `D` rerolls, `F` buys experience, `E` sells the selected unit and
`Escape` closes a dialog or drops the selection.

Every unit is drawn as a 3D figure that breathes, sways and blinks, and swings
its arms and legs when it runs. The board stands in an arena: a night skyline of candlestick towers, a raised
platform, statues of the bull and the bear, pylons with turning coins and the
opening bell. The client builds the figures and the arena's props itself with
WebGL when the page loads; until they are drawn, and in a browser without
WebGL, it shows the flat portrait of each unit instead and leaves the props
out, and everything else works the same. With the system setting for reduced
motion nothing moves, the fight scene is not played and the round result comes
up at once. On a screen up to 900 pixels wide the layout is one column with
the shop right under the bench.

### In the terminal

```bash
tft play --seed 7
```

You sit against seven bots and each round shows your health, gold, level,
board with every unit's cell, bench, traits, components, items, shop and any
augment offer. Type `h` for the commands: `b 0` buys shop slot 0, `f 0` fields
unit 0 on its class's default cell and `f 0 3 2` on row 3, column 2, `m 0 0 4`
moves a board unit to another cell, `c 0 1` crafts an item from two
components, `i 0 0` equips it, `o` scouts the other boards, `p` previews your
odds on replayed slices, and Enter fights. After the fight the client prints
your result and the round's lessons. When the match ends the replay is saved
under `replays/` and can be checked:

```bash
tft replay replays/match-7-20261116T120000Z.json --verify
```

`tft sim --seed 7` runs a bots-only match, `--no-market` falls back to the
power comparison of the first mock, and `tft rules > my-rules.toml` writes
every number the engine uses so you can change them and play with
`--rules my-rules.toml`. Python users get the same engine as a library:

```python
from tft import Game

game = Game(["ana", "bo", "cy", "di", "ed", "fay", "gus", "hal"], seed=42)
print(game.run())  # placements, first to last; the same seed always gives the same match
```

### How a fight is decided

Every fight is decided on a slice of real market history, ten daily bars by
default, the same for the whole lobby. Each unit trades its class's strategy
(a breakout, a mean reversion, a hedge) on a symbol of its origin.

**Positioning.** The board is a grid of 4 rows by 7 columns; row 0 is the
front. A unit's row sets its size (90, 95, 100 and 110 percent from front to
back) and forgives part of its drawdown (40, 20, 0 and 0 percent). In the two
back rows a unit with an ally in front of it in the same column is covered
and has another 25 percent forgiven; one with nobody in front is exposed and
its drawdown weighs 50 percent more. The front is the place for what swings,
the back for what is steady. The column picks which symbol of its origin the
unit trades: spread an origin over columns to diversify it, stack it in one
column to concentrate it. A unit fielded without a cell takes the default row
of its class (Whale and Swing in front, Scalper and Hedger in the second row,
every other class at the back), and that is where the bots stand.

**Scoring.** A unit's *edge* is its strategy's profit on the slice minus 0.3
times its worst drawdown (after what its row and its items forgive or add),
in percent. Its score is its size times a result factor of 100 percent plus
10 percent per percent of edge, kept between 0 and 200 percent, so a flat
trade keeps the size, an edge of -10 percent wipes the unit out, a fielded
unit can never lower its board's score, and the board with the higher total
after trait and augment bonuses wins.

**Lessons.** After every round the client names up to three things the round
just showed, picked from 15 rules in a fixed order: empty board slots, a unit
wiped out, a stop that fired, a target that fired, a hedge that paid, a loss
with no item to limit it, over-trading, a strategy that found no signal, two
units on one ticker, an exposed unit at the back, idle components or items, a
contested champion, low health with a full bank, interest, and streaks.

Every number above is a rule (`tft rules` prints them all), and
[docs/BALANCE.md](docs/BALANCE.md) has the measurements behind them.

## The web API

`tft serve` answers these routes with JSON. A good answer has `"ok": true`
and its data; a refused one has `"ok": false` and an `error` sentence, with
status 400 (a bad request, or an action the rules do not allow), 403 (see
below), 404, 405, 409 (the match is not waiting for that), 411 (a body
without a `Content-Length`), 413 (a body over 64 KiB), 415 (a `POST` that is
not sent as `application/json`, also one without a body), 500 (`internal
error`, nothing more; the traceback goes to the server's log) or 501 (a
method the server does not have).

The server protects the player's browser from other sites. Every `POST` must
be JSON, which a page on another site cannot send without asking first; a
request that changes something is refused with 403 when its `Origin` is not
the server's own; and on every address it listens on the server answers only
to `localhost`, to plain IP addresses and to the names given with
`--allow-host`, so a page that points its own domain at your machine gets 403
as well.

It also keeps one client from holding it up: a connection that stays silent
for 15 seconds is dropped, a whole request has 30 seconds to arrive, and a
seat may take at most 500 planning actions in one round (409 after that,
until the round is fought).

| Method and path | What it does |
| --- | --- |
| `GET /api/health` | The status, the game's name and the package version |
| `GET /api/catalog` | Static content for tooltips: champions, traits, strategies, components, items, augments, the grid, the scoring numbers and how many bots the rules seat |
| `GET /api/matches` | The matches on the server, most recently used first |
| `POST /api/matches` | Create a match and return its state with status 201. The body is optional: `seed` (0 to 2147483647, random when left out), `bots` (1 to 7 under the default rules, by default as many as the rules seat), `market` (default `true`; `false` decides fights by power) and `spectate` (default `false`; `true` creates a bots-only match) |
| `GET /api/matches/{id}` | The match as its player sees it |
| `DELETE /api/matches/{id}` | Forget the match |
| `POST /api/matches/{id}/actions` | One planning action, for example `{"kind": "buy", "args": [0]}`. The kinds are `buy`, `sell`, `reroll`, `xp`, `field`, `move`, `bench`, `augment`, `craft` and `equip`; the arguments are up to four whole numbers |
| `POST /api/matches/{id}/ready` | End planning: fight the round, summarise it and open the next one |
| `POST /api/matches/{id}/step` | Play one whole round of a bots-only match |
| `GET /api/matches/{id}/preview` | The seat's odds against every other board on bootstrapped slices |
| `GET /api/matches/{id}/spectate` | The match as a spectator sees it: the public state of every seat |
| `GET /api/matches/{id}/replay` | The match's replay, as `tft replay` reads it |

Every other path serves one of the client's files or answers 404.

## Install

```bash
pip install "git+https://github.com/MITRAKER/TFT.git@stable"
python -c "import tft; print(tft.__version__)"
```

`stable` always points at the latest stable release. Pin an exact version with
its tag instead, for example `@v0.1.0`. Release archives, checksums and
provenance attestations are on the [Releases](https://github.com/MITRAKER/TFT/releases) page.

## Development

```bash
git clone https://github.com/MITRAKER/TFT.git
cd TFT
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
python -m pip install -e . -r requirements-dev.txt
pre-commit install
```

Run the same gate CI runs:

```bash
ruff format --check .
ruff check .
mypy
python tools/jpl_check.py --root .
python -m pytest
```

`pre-commit` runs the formatter, the linter, mypy and the Power of Ten checker
on every commit.

The browser client has its own checks, which need Node 22 or newer:

```bash
npm ci                            # ESLint and Playwright, pinned in package-lock.json
npm run lint                      # ESLint on the client, its tests and the configs
npm test                          # unit tests on Node's test runner (tests/web/*.test.js)
npx playwright install chromium   # once
npm run test:e2e                  # browser tests: the game played in headless Chromium
```

The browser tests start `python -m tft serve` on port 8765 themselves, with
the short rule set in `tests/web/e2e/short-rules.toml`, so run them with the
virtual environment active. `pre-commit` does not run the client's checks;
the `web` job of CI does.

## Quality gates

| Workflow | Runs on | What it checks |
| --- | --- | --- |
| [CI](.github/workflows/ci.yml) | pushes to `main`, pull requests | Test suite on Python 3.11 to 3.14 (Linux) and 3.13 (Windows) with 95 % branch coverage required; sdist and wheel build, metadata check and install smoke test; the `web` job: ESLint on the client, its unit tests, and the browser tests in headless Chromium |
| [Standards](.github/workflows/standards.yml) | pushes to `main`, pull requests | Formatting, lint (pycodestyle, pyflakes, bugbear, bandit, pylint design limits, Google-style docstrings), `mypy --strict`, and the [NASA/JPL Power of Ten](docs/STANDARDS.md) checker |
| [CodeQL](.github/workflows/codeql.yml) | pushes, pull requests, weekly | GitHub's semantic security analysis of the Python code, of the client's JavaScript and of the workflow files themselves |
| [Security](.github/workflows/security.yml) | pushes, pull requests, weekly | `pip-audit` against known vulnerabilities; dependency review of every pull request |
| [Scorecard](.github/workflows/scorecard.yml) | pushes to `main`, weekly | OpenSSF Scorecard supply-chain posture, published to code scanning |
| [Release](.github/workflows/release.yml) | tags `vX.Y.Z` and `vX.Y.Z-label` | The Python gate again, build, `SHA256SUMS.txt`, SLSA build provenance attestation, GitHub Release with generated notes, and the moving `stable` tag |

[Dependabot](.github/dependabot.yml) opens grouped weekly pull requests for the
GitHub Actions, the Python tooling and the client's npm tooling, and security
updates for anything with a published advisory. Every action is pinned to a
full commit SHA and every workflow token carries the least privilege it needs.

## Market packs

The starter pack ships inside the package: 29 US stocks over 60 trading days
of 2026, built from the MIT-licensed fixtures of the Day Trader skill. Its
origins are stand-ins (for example the volatile names play "Crypto") until a
pack with real asset classes replaces it. Build your own from saved Yahoo
Finance responses or by fetching:

```bash
python tools/build_market_pack.py --from-dir tests/fixtures/market --name starter --out packs/starter.json
python tools/build_market_pack.py --fetch AAPL,KO,XOM,TLT,GLD --range 6mo --name live --out packs/live.json
tft play --pack packs/live.json
```

A replay records the pack it was played on and refuses to run on another.

## Balance

`tools/balance_report.py` measures the balance on a market pack. It trades
every class on every window of every symbol and plays whole matches in which
one seat follows a probe policy (an empty board, a single unit, every unit in
the back rows, every unit in the front rows) against the greedy bot, then
prints four tables: classes, class by origin, champions and policies.

```bash
python tools/balance_report.py                    # text; 60 matches per probe, about 15 seconds
python tools/balance_report.py --matches 0        # the class tables only, under a second
python tools/balance_report.py --pack packs/live.json --rules my-rules.toml --format markdown
```

[docs/BALANCE.md](docs/BALANCE.md) explains the tables, holds the current
ones, and says what they cannot tell yet: the starter pack is one period of
60 trading days, its origins are stand-ins, the bots are one greedy policy,
and no playtest with people has happened.

## Standards

The code standards and the mapping of each of the ten NASA/JPL rules to the tool
that enforces it are in [docs/STANDARDS.md](docs/STANDARDS.md).

## Releases and tags

Versions follow [Semantic Versioning](https://semver.org). `vX.Y.Z` tags are
immutable and protected; `stable` moves to the newest stable release. The
step-by-step release process is in [docs/RELEASING.md](docs/RELEASING.md).

## Security

See [SECURITY.md](SECURITY.md) for the supported versions and the private
reporting channel. The repository settings that back the pipeline (Dependabot
alerts and security updates, secret scanning, private vulnerability reporting,
branch and tag rulesets) are listed in
[docs/REPOSITORY_SETTINGS.md](docs/REPOSITORY_SETTINGS.md) and applied in one
command with `tools/configure_repository.py`.

## Repository layout

```text
.github/            workflows, Dependabot, CODEOWNERS, issue and PR templates
docs/               PRD, balance, standards, release process, repository settings
src/tft/            the engine: rules, economy, roster, formation, market, strategies, items, combat,
                    environment, lessons, replay, view, server, cli
src/tft/packs/      the built-in starter market pack
src/tft/web/        the browser client that `tft serve` serves
tests/              pytest suite, 95 % branch coverage required
tests/web/          the client's unit tests (node:test) and browser tests (Playwright, in e2e/)
tools/jpl_check.py  NASA/JPL Power of Ten checker
tools/release_version.py  tag-to-version check used by the Release workflow
tools/configure_repository.py  applies the GitHub-side settings (security, Dependabot, rulesets)
tools/build_market_pack.py  builds a market pack from Yahoo Finance responses
tools/balance_report.py  measures the classes, the champions, the grid and the bots on a pack
tools/bootstrap_windows.cmd  Windows one-click: installs Python and the GitHub CLI, signs in, runs the tool
pyproject.toml      package metadata and every tool's configuration
requirements-dev.txt pinned development and CI tools (Dependabot keeps them current)
package.json        the client's lint and test tools (ESLint, Playwright), pinned in package-lock.json
eslint.config.js    ESLint rules for the client and its tests
playwright.config.js  browser test settings: starts `tft serve` with a short rule set
```

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

[MIT](LICENSE)
