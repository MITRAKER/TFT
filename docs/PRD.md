# Product Requirements Document: Team Fight Tackticktics (TFT)

| | |
| --- | --- |
| Status | Draft v0.1 for review |
| Owner | Mitra Kermanian (MITRAKER) |
| Repository | <https://github.com/MITRAKER/TFT> |
| Last updated | 2026-11-16 |

## 1. Summary

Team Fight Tackticktics is a strategy game in the auto-battler genre in which the
pieces are **trading strategies**, the gold is **capital**, and the battles are
**real market sessions replayed from historical data**. A player drafts a
board of trader-champions from a shared shop, combines copies to star them up,
unlocks synergies between markets and trading styles, manages an economy of
income, interest and streaks, and survives rounds until one of eight players
is left. Everything a Teamfight Tactics player already knows how to do
(scout, roll, slam items, play the streak, protect health) maps onto something
a trader actually has to learn (scan, size, hedge, respect the drawdown).

The game is **not a brokerage and moves no real money**. Its ambition is to
make the discipline of day trading, as taught in the reference video, as
learnable and as fun as an evening of auto-battler.

## 2. Background and inputs

- **Reference video.** BunnyMuffins, *Beginner Guide to Teamfight Tactics*
  (<https://youtu.be/nXmNrPgCH1k>). Its three parts (rules and interface, a
  full match walkthrough, strategic tips) define the mechanics, pacing and
  vocabulary this document borrows: eight players, 100 health, star levels,
  the shared unit pool, traits, item components, the carousel and PvE rounds,
  interest to 50 gold, streak gold, augments at 2-1, 3-2 and 4-2, leveling
  versus rerolling, frontline and backline positioning, slamming items,
  health as a resource, scouting, and mastering one or two compositions.
  The video page itself cannot be fetched from this build environment
  (youtube.com is not on its network allow-list); the summary captured at the
  start of the project is the working source.
- **Trading engine.** The *Day Trader skill* pack
  (<https://github.com/Jakeschincariol/day-trader-skill>, MIT): eleven
  standard-library Python tools that scan the US stock universe for setups,
  read news and filings, time entries, plan exits, replay a trade ten
  thousand times from the stock's own recent bars (the "Time Machine"), size
  positions and gate risk. Its data sources are free and public (Yahoo
  Finance charts, Nasdaq Trader symbol lists, SEC EDGAR, Stooq). These tools
  become the game's market layer.
- **Reference engines** (section 13): an unlicensed but instructive headless
  deterministic autobattler built as a reinforcement-learning environment,
  and an MIT-licensed TFT research engine whose published rule tables
  (shop odds, pool sizes, stage damage) calibrate the mock in this repository.
- **This repository.** `src/tft/roster.py` holds the mock roster,
  `src/tft/environment.py` the mock game environment, `src/tft/economy.py`
  the income rules. All three run under the repository's quality gates.

## 3. Goals and non-goals

### Goals

1. **Teach by play.** A player who reaches the late game understands position
   sizing, stops, streak and drawdown management, diversification and why
   contested trades are worse trades, without reading a textbook.
2. **Real market, fair fight.** Every round's combat is resolved against the
   same slice of real historical market data for every player in the lobby,
   so skill, not luck of the draw, decides.
3. **Auto-battler feel.** Round rhythm, shop and bench, star-ups, synergies,
   augments, carousel and PvE rounds, eight-player lobbies, the health bar
   drama of the final rounds.
4. **Deterministic, headless core.** A seed reproduces a whole game byte for
   byte. The engine never renders, sleeps or prints; clients and bots sit on
   top of it. Replays are first-class.
5. **Original intellectual property.** Mechanics are genre conventions; every
   name, character, ability, icon and piece of art is ours.

### Non-goals (v1)

- Real-money trading, brokerage connectivity, or any instruction to buy or
  sell a security. The game is simulation and education.
- Live market data during a match. Matches replay history; live data is a
  later mode once fairness and rate limits are solved.
- Options, margin, leverage mechanics beyond flavour text.
- Mobile clients and controller support (web first).
- Copying any Riot Games content. See section 12.

### Design principles

- *Every number is data.* Rules live in one configuration; the engine reads
  them. Balancing is a data change, not a rewrite.
- *Mock first, replace later.* Every system ships first as a deterministic
  mock behind an interface (this commit), then gets its real implementation.
- *The lobby shares one market.* Fairness comes from identical inputs.
- *Health is a resource; so is attention.* Rounds are short; decisions are few
  and meaningful.

## 4. Players

| Persona | Who | What they want | What success looks like |
| --- | --- | --- | --- |
| The auto-battler regular | Plays TFT or similar weekly, curious about markets | A new flavour of the genre that respects their skill | Reads a board at a glance, climbs a ladder, discovers "econ" is literally economics |
| The aspiring trader | Watches trading content, has or wants a paper account | Learn the discipline without losing money | Explains interest, streaks and risk-per-trade in game terms, then in trading terms |
| The quant hobbyist | Likes simulations and bots | A deterministic environment to script against | Writes a policy against the engine API and benchmarks it on seeds |
| The streamer or coach | Teaches either hobby | A spectator-friendly, explainable game | Replays and round summaries that make a lesson out of a match |

## 5. The core loop

A match is a sequence of rounds grouped into stages. Each round:

1. **Income.** Base income plus interest on banked gold (one per ten, capped
   at five) plus the streak bonus. Passive experience is granted.
2. **Events.** On augment rounds (2-1, 3-2, 4-2) the player picks one of
   three augments. On carousel rounds (every stage's fourth round) the player
   picks a free champion carrying an item component.
3. **Shop.** Five slots roll from the shared pool with odds set by the
   player's level. Buy, sell, reroll (two gold), buy experience (four gold).
4. **Board.** Field up to *level* units; combine three copies into a higher
   star; place items; position.
5. **Combat.** Player-versus-player rounds pair the lobby; PvE rounds
   ("the Market") face every player with the same scripted opponent.
   Combat is resolved by the **market replay** (section 7.8).
6. **Damage.** The loser takes stage damage plus damage per surviving enemy
   unit. Draws break both streaks. Players at zero health are eliminated.

The match ends when one player remains, or at the hard round cap.

## 6. Mechanic mapping: auto-battler to trading

| Auto-battler mechanic | In Team Fight Tackticktics | What it teaches |
| --- | --- | --- |
| Little Legend with 100 health | The trader's **drawdown budget** | Health is a resource; blowing up is the only unrecoverable loss |
| Gold | **Capital** | Compounding beats spending |
| Interest, capped at 50 gold | **Interest on idle capital** | Patience pays; the 50-gold benchmark |
| Win and loss streaks | **Streak discipline**: consistent behaviour pays, flip-flopping does not | Mixed results are the worst state |
| Champions (1- to 5-cost) | **Trader-champions**: trading archetypes with a market (origin) and a style (class) | Expensive is not better until it is upgraded and supported |
| Star-ups (3 copies, 9 copies) | **Conviction**: three signals of the same setup become a bigger, better-sized position | Scale into what works |
| Shared unit pool | **Crowded trades**: the more players buy a champion, the scarcer it is for everyone | Contested setups have worse fills; pivot when crowded |
| Traits (origins and classes) | **Diversification and factor synergies** across markets and styles | Correlated boards win big and lose big |
| Items and components | **Risk tools**: stop-loss, take-profit, hedge, trailing stop, position sizing; components combine | Slam a stop early; perfect is the enemy of protected |
| Augments | **Account rules**: commission rebates, extra rerolls (more scans), lower interest step, leverage with margin-call risk | Rules you set for yourself shape outcomes more than any single trade |
| Leveling vs rerolling | **Time horizon**: level toward big setups, or roll for many small ones | Scalping and swing trading are different economies |
| Positioning (frontline, backline, corners) | **Position sizing**: the front rows trade smaller and forgive part of a drawdown; the back rows trade bigger and pay extra for a drawdown unless a unit stands in front of them; the column picks the ticker | Size down what swings; cover the big position; do not put every unit on one ticker |
| Carousel | **Free pick** of a champion with a component, worst players first | Catch-up mechanics, and the value of a stop you did not pay for |
| PvE rounds | **The Market** itself as the opponent: a scripted board that scales by stage | Some sessions are against the tape, not against people |
| Scouting | **Watch the lobby**: see what others hold and what is contested | Pivot out of crowded trades |
| Combat | **Market replay**: every board is scored against the same historical session | Outcomes are distributions, not promises |

## 7. Game systems

### 7.1 Match structure

- Lobby of 8 (2 to 8 in custom games). Stage 1 is three PvE rounds; every
  later stage has seven rounds; the hard cap is 45 rounds (7-7).
- Round *X-4* is the carousel, *X-7* is the stage boss ("the Market"
  at full strength). Augments at 2-1, 3-2 and 4-2.
- Stage base damage: 0, 2, 5, 8, 10, 12, 17 for stages 1 to 7, plus one per
  surviving enemy unit (star and cost scale it in later iterations).

### 7.2 Economy

- Base income 5. Interest: 1 per 10 banked, capped at 5. Streak bonus:
  +1 at 2 to 3, +2 at 4, +3 at 5 or more (win or loss streaks alike).
- Reroll 2 gold. Experience: 4 gold for 4 XP; 2 XP free per round.
  Levels 1 to 10; experience to the next level: 2, 2, 6, 10, 20, 36, 48, 80, 84.
- Sell value: cost for a one-star; cost × 3 − 1 for a two-star; cost × 9 − 1
  for a three-star (one-cost champions sell for 3 and 9).
- Implemented in `src/tft/economy.py` and `src/tft/environment.py`.

### 7.3 Shop and pool

- Five slots. Shop odds by level (percent chance per slot of a 1/2/3/4/5-cost):

  | Level | 1 | 2 | 3 | 4 | 5 |
  | --- | --- | --- | --- | --- | --- |
  | 1 to 2 | 100 | 0 | 0 | 0 | 0 |
  | 3 | 75 | 25 | 0 | 0 | 0 |
  | 4 | 55 | 30 | 15 | 0 | 0 |
  | 5 | 45 | 33 | 20 | 2 | 0 |
  | 6 | 30 | 40 | 25 | 5 | 0 |
  | 7 | 19 | 30 | 40 | 10 | 1 |
  | 8 | 17 | 24 | 32 | 24 | 3 |
  | 9 | 15 | 18 | 25 | 30 | 12 |
  | 10 | 5 | 10 | 20 | 40 | 25 |

- Shared pool copies per champion: 30 / 25 / 18 / 10 / 9 by cost. Buying
  removes a copy; selling returns it; rerolling does not consume the pool.
  Within a cost tier, a slot picks a champion weighted by copies remaining,
  so contested champions get rarer.

### 7.4 Champions, origins and classes

Every champion has one **origin** (the market it trades) and one **class**
(how it trades). Traits count *distinct* champions on the board.

Origins (v0): Equities, Tech, Crypto, Commodities, Bonds, Forex.
Classes (v0): Scalper, Swing, Momentum, Contrarian, Hedger, Arbitrageur,
Quant, Whale.

The v0 roster of 25 champions is in section 8 and in `src/tft/roster.py`.
Base power by cost is 10 / 14 / 20 / 28 / 40; a two-star is 1.8× and a
three-star 3.2× (placeholder curve).

### 7.5 Items

Components (v0 set of eight): Stop Order, Limit Order, Volume Filter,
Volatility Gauge, Hedge Ticket, Cash Buffer, Margin Note, and the wildcard
Prospectus (grants an origin, like a spatula). Two components combine into a
completed item; three archetypes: **offence** (bigger size on winning
setups), **defence** (stops, hedges, cash buffers that reduce damage taken)
and **utility** (extra reroll, interest step, scouting). Items are data;
the first implementation is a flat stat multiplier per item, as the
reference engines do.

### 7.6 Augments

Three fixed augment rounds; three choices each, tiered silver, gold,
prismatic. Families: **economy** (gold now, cheaper rerolls, more interest),
**combat** (board power), **trait** (an emblem for an origin or class),
**rules** (change a rule for the rest of the game, for example "Tight Stops:
stage damage you take is halved, your boards hit 10 % softer"). The mock
ships six augments with gold and power effects only.

### 7.7 Positioning

A 7×4 hex board as in the genre: 4 rows by 7 columns, row 0 in front.
Implemented in M3 as `tft.formation`, where the row is a position-sizing
dial:

| Row | Size | Drawdown forgiven |
| --- | --- | --- |
| 0 (front) | 90 % | 40 % |
| 1 | 95 % | 20 % |
| 2 | 100 % | 0 % |
| 3 (back) | 110 % | 0 % |

In the two back rows a unit with an ally in front of it in the same column
is **covered** and has another 25 % of its drawdown forgiven; one with
nobody in front is **exposed** and its drawdown weighs 50 % more. In trading
terms the front rows are the hedge book, small positions for what swings,
and the back rows are the alpha book, the largest positions, for what is
steady. The **column** picks which symbol of its origin a unit trades, so
spreading an origin over columns diversifies it and stacking it in one
column concentrates it. A unit fielded without a cell takes the default row
of its class, centre columns first: Whale and Swing in front, Scalper and
Hedger in the second row, every other class at the back. Every number here
is a rule (`row_size_percent`, `row_shield_percent`, `cover_shield_percent`,
`exposed_penalty_percent`); how they were tuned is in `docs/BALANCE.md`.

### 7.8 Combat: the market replay

The defining system. For each round the lobby is dealt **one market slice**:
a real historical session (or a block of 5-minute bars) for a basket of
symbols, chosen by seed and hidden from players until combat. Each champion
is a scripted strategy over that slice (an opening-range breakout, a mean
reversion, a carry trade); its star level sets size, its items set stops and
targets, and its traits add bonuses. Each unit's trade turns its size into a
score: a good trade grows it, a bad one shrinks it, a disaster wipes it out.
A board's **combat score** is the sum of its units' scores with the trait
and augment bonuses; the higher score wins and the margin sets survivors.

Properties:

- *Same inputs for everyone.* No player can have a lucky market.
- *Distribution, not prediction.* The Time Machine approach of the Day Trader
  skill (bootstrap replays from the instrument's own recent bars) powers a
  "preview" that shows the odds of a board before combat, never a promise.
- *Deterministic.* Seed → slice → scores. Replays verify byte for byte.
- *Offline fixtures.* Tests run on committed historical bars, exactly as the
  Day Trader skill's own tests do.

Implemented in M2 as `tft.combat.MarketResolver` and rescored in M3. A
unit's **edge** is its strategy's profit on its symbol's bars minus 0.3
times its drawdown, in percent; its items and its row shield part of the
drawdown from the penalty, and exposure adds to it. The unit's **score** is
its size (power, scaled by its items and its row) times a **result factor**:
100 % plus 10 % per percent of edge, kept between 0 and 200 %. A flat trade
keeps the size, an edge of −10 % or worse wipes the unit out, an edge of
+10 % or better doubles it, and the factor is never negative, so fielding a
unit can never lower a board's score. The board's score adds the trait and
augment bonuses. The winner keeps the share of its units that matches the
share of its score that was not needed to win, and at least one: 12 against
9 keeps a quarter.

M2 scored a unit as its size times its edge with a penalty of 0.5, which is
negative for every losing trade; an empty board then beat most boards.
`docs/BALANCE.md` has the measurements and the reasons for the change.

The first mock, `PowerResolver`, remains available with `--no-market`.
Slices are ``slice_bars`` consecutive daily bars (10 by default) dealt from
the pack by the game's seed; when the pack has more than one window, the
same one is not dealt two rounds in a row.

### 7.9 Lobby, multiplayer and bots

Eight seats; empty seats are filled by bots (greedy, positional, learned).
Pairings are random among the living; an odd player out fights the Market.
Scouting exposes every other board (not shops) at planning time.

## 8. Content: the v0 roster

Costs 1 to 5. *Origin / Class*. Ability names are flavour hooks for the
market resolver.

| Cost | Champion | Origin / Class | Ability |
| --- | --- | --- | --- |
| 1 | Pip Squeak | Forex / Scalper | Tick Hunt |
| 1 | Index Drone | Equities / Quant | Rebalance |
| 1 | Hodl Hamster | Crypto / Contrarian | Diamond Paws |
| 1 | Barrel Bo | Commodities / Swing | Roll Over |
| 1 | Coupon Clerk | Bonds / Hedger | Yield Shield |
| 1 | Candle Reader | Tech / Momentum | Engulfing |
| 2 | Gap Gazelle | Equities / Momentum | Gap and Go |
| 2 | Mean Reverend | Equities / Contrarian | Back to the Mean |
| 2 | Spread Spider | Forex / Arbitrageur | Pip Web |
| 2 | Gold Bug | Commodities / Hedger | Safe Haven |
| 2 | Stable Coin | Crypto / Hedger | The Peg |
| 2 | Yield Yeti | Bonds / Swing | Coupon Crush |
| 3 | Breakout Bull | Equities / Momentum | Opening Range Breakout |
| 3 | Bear Baron | Equities / Contrarian | Bear Raid |
| 3 | Vol Vampire | Tech / Quant | Implied Volatility |
| 3 | Carry Caravan | Forex / Swing | Carry Trade |
| 3 | Miner Mole | Crypto / Scalper | Hash Rate |
| 3 | Crude Colossus | Commodities / Momentum | Supply Shock |
| 4 | Market Maker | Equities / Arbitrageur | Bid-Ask Bite |
| 4 | Fed Whisperer | Bonds / Quant | Rate Decision |
| 4 | Flash Crash | Tech / Scalper | Liquidity Vacuum |
| 4 | Whale Watcher | Crypto / Whale | Order Wall |
| 5 | Black Swan | Equities / Contrarian | Tail Event |
| 5 | Central Banker | Bonds / Whale | Quantitative Easing |
| 5 | Algo Overlord | Tech / Quant | Backtest Everything |

Trait breakpoints and bonuses are in `src/tft/roster.py`. Art direction:
stylised, readable at board scale, each origin with its own palette (Equities
blue, Tech violet, Crypto orange, Commodities bronze, Bonds green, Forex
teal) and each class with a silhouette rule (Scalpers small and quick,
Whales large and slow).

## 9. Market data and simulation

| Need | Source | Notes |
| --- | --- | --- |
| Symbol universe | Nasdaq Trader symbol directories | About 5,900 US common stocks; filter as the Day Trader scanner does |
| Intraday bars | Yahoo Finance chart endpoint (5-minute, 60 days) | Unofficial; cache aggressively; commit fixtures for tests |
| Daily bars | Yahoo spark, Stooq CSV | Fallbacks and long history |
| News and filings | Yahoo RSS, SEC EDGAR | Flavour for "event" rounds; later |
| Replay engine | Day Trader skill `trader-timemachine` approach | Bootstrap from the instrument's own bars; seeded |

Market slices are prepared offline into versioned packs ("Sets" in genre
terms: *Set 1: Earnings Season*, *Set 2: Rate Hikes*). A match is pinned to
one pack so that replays stay valid when sources change.

## 10. Architecture

```text
clients (web UI, CLI, bots)  ->  Game API (match, actions, observations, replays)
                                   |        server, view: `tft serve`, JSON over HTTP (M3)
                              tft engine (pure Python, deterministic, headless)
                                   |-- roster        traits, champions, items, augments (data)
                                   |-- environment   rounds, shop, pool, levels, damage, lobby
                                   |-- formation     the positioning grid: rows, cover, exposure (M3)
                                   |-- economy       income, interest, streaks
                                   |-- resolvers     PowerResolver (mock) -> MarketResolver (replay)
                                   |-- lessons       round summaries and what a round teaches (M3)
                                   |-- replay        seed + config hash + actions -> byte-identical log
                                   |
                              market packs (versioned historical slices, offline fixtures)
```

- **Engine.** Pure Python 3.11+, standard library only, no printing, sleeping
  or rendering in the engine; a single seeded `random.Random`; every loop
  bounded (the repository enforces the NASA/JPL Power of Ten rules).
- **Interfaces.** `CombatResolver` (protocol) and `Policy` (callable) are the
  two seams; bots, tests and the future market replay plug in there.
- **RL readiness.** The environment is shaped so a gym or PettingZoo wrapper
  is a thin layer (observation = own state live, opponents frozen at round
  start, shops hidden), following the reference engines.
- **Clients.** Web client first. Since M3 `tft serve` runs a standard-library
  HTTP server with a JSON API (`tft.server`, `tft.view`) and serves a browser
  client of plain ES modules with no dependency and no build step: board,
  shop, bench, lobby, spectating and round summaries. It can download a
  replay but has no replay viewer yet. The engine ships as a package so the
  CLI and bots need nothing else.
- **Quality gates.** Every change passes the repository's CI, Standards
  (ruff, mypy strict, Power of Ten), CodeQL and Security workflows; CI also
  lints the browser client and tests it in a real browser; releases are
  tagged, attested builds (see `docs/RELEASING.md`).

## 11. Milestones

| Milestone | Scope | Exit criteria |
| --- | --- | --- |
| **M0 Mock** (released as v0.1.0) | Roster v0, environment mock (rounds, shop, pool, economy, star-ups, levels, augments, carousel, PvE, eliminations), `PowerResolver`, greedy bot, PRD | Deterministic eight-bot game runs to a result under the quality gates; 95 % branch coverage |
| **M1 Playable CLI** (released as v0.2.0) | Human actions through the API, scouting observation, replay file, rules in a config file | A person plays a full match against seven bots in a terminal; replay verifies |
| **M2 Market replay** (released as v0.3.0) | Market packs, `MarketResolver`, items as stops and targets, preview odds, the scripted Market board | Combat decided by real historical slices; fixture-based tests; the positioning grid moved to M3, where a spatial client gives it meaning |
| **M3 Web client** (delivered in v0.4.0) | Board UI with the positioning grid, lobby, spectating, round summaries that explain the trading lesson, balance pass (made on the scoring, the strategies and the grid; the champions' costs and power and the trait bonuses are unchanged; see `docs/BALANCE.md`) | Playtest with ten external players; median round under 60 seconds. **Not met yet:** the playtest is the owner's task and has not been run, so neither number has been measured |
| **M4 Multiplayer and ladder** | Authoritative server, matchmaking, ranked seasons tied to market packs | Public beta |

## 12. Risks and compliance

| Risk | Mitigation |
| --- | --- |
| Intellectual property: Teamfight Tactics is Riot Games' property | Mechanics of a genre are not protected; names, art, characters, UI assets and text are. Nothing is copied; the roster, items and augments are original; no Riot assets or data files ship. The reference engines were read for rule tables, not copied (one has no license at all and is used only as a design reference). |
| Perception of gambling or financial advice | No real money, no brokerage, no live recommendations. Disclaimers in product and store copy. Education framing throughout. |
| Market data licensing | Free, unofficial endpoints for development; versioned offline packs for tests; a licensed feed before commercial launch. |
| Fairness and determinism bugs | Seeded RNG, byte-identical replays asserted by tests, shared market slice per round. |
| Balance | Everything is data; ablation workflow on seeds (as the reference engines do) before every roster change. `tools/balance_report.py` measures the classes, the champions, the grid and probe policies on a pack; `docs/BALANCE.md` holds the method, the current tables and their limits (one pack, one bot policy, no playtest yet). |
| Scope creep | Milestones gated by exit criteria; mock first. |

## 13. Reference projects

| Project | What it is | License | What we take |
| --- | --- | --- | --- |
| [danielkkim1005/AutoBattler](https://github.com/danielkkim1005/AutoBattler) | Headless, deterministic autobattler engine and RL environment; `rules.yaml` holds every number, `SPEC.md` the semantics; byte-identical replays | **No license file** (all rights reserved by default) | Design lessons only: data-driven rules, split random streams, event log, replay format, observation model. No code. |
| [MielPopsssssss/TFT_GOAT](https://github.com/MielPopsssssss/TFT_GOAT) | Research RL agent for the real TFT; PettingZoo 8-player environment; three swappable combat resolvers | MIT | Rule tables (shop odds, pool sizes, stage damage, XP curve) and the `CombatResolver` seam pattern. |
| [kono94/theme-fusion-tactics](https://github.com/kono94/theme-fusion-tactics) | Browser auto-battler with a theme-swappable engine | Check before use | Evidence that a themed re-skin of the genre works; UI ideas. |
| [Laksh-Goyal/tft-agent](https://github.com/Laksh-Goyal/tft-agent) | RL for a simplified TFT-style autobattler | Check before use | Simplification choices for an RL-friendly rule set. |
| [enzo-going/tactical-autobattler-python](https://github.com/enzo-going/tactical-autobattler-python) | Small OOP autobattler simulator with tournament mode | Check before use | Tournament and reporting ideas. |
| [Jakeschincariol/day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill) | Eleven Claude skills and tools for day trading on free data | MIT | Scanner, Time Machine and risk tools as the market layer; its offline-fixture testing style. |

## 14. Open questions

1. **Name.** Decided by the product owner on 2026-11-14: **Team Fight
   Tackticktics**. It replaces the working title "Ticker Fight Tactics" and
   keeps the TFT initials. It is kept in one place, `src/tft/name.py`. The
   name, logo and store copy must stay distinct from Riot Games' trademark
   "Teamfight Tactics".
2. **Combat scoring.** Risk-adjusted P&L (for example return divided by
   maximum drawdown over the slice) or plain P&L? The first is more
   educational, the second more legible. Since M3 the engine scores
   risk-adjusted (profit minus the penalised drawdown, turned into a bounded
   result factor, section 7.8) and the client shows the plain profit and the
   drawdown of every unit next to it. The penalty, the weight and the cap
   are rules and stay open to tuning on more market packs.
3. **How much real trading vocabulary in the UI** versus game vocabulary with
   trading in the tooltips?
4. **Single-player campaign** (climb through market regimes) before
   multiplayer, or straight to lobbies with bots?
5. **Monetisation**, if any: cosmetics only, consistent with the no-gambling
   stance.

## 15. Glossary

- **Board / bench / shop**: fielded units, stored units, the five purchasable slots.
- **Star-up**: three copies of a champion become the next star level.
- **Trait / origin / class**: synergies counted on distinct fielded champions.
- **Augment**: a rule-changing pick at 2-1, 3-2, 4-2.
- **Carousel**: a free pick round every stage.
- **The Market**: the scripted PvE opponent.
- **Cell / cover / exposure**: where a unit stands on the 4 by 7 grid; a back unit is covered by an ally in front of it in its column, exposed without one.
- **Edge / result factor**: a unit's profit minus its penalised drawdown; what that multiplies the unit's size by, between 0 and 2.
- **Lesson**: a plain-language note on what a round just showed; up to three per round.
- **Market slice**: one historical session dealt to the whole lobby for a round.
- **Market pack ("Set")**: a versioned collection of slices a match is pinned to.
- **Replay**: seed plus configuration hash plus actions; reproduces a match exactly.
