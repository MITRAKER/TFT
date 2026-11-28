# Balance

How the balance of the game is measured, where it stands in 0.4.0, what
milestone M3 changed and why, and what the numbers cannot tell yet. Every
balance number here comes from `tools/balance_report.py` on the built-in
starter pack, or is marked as a measurement made during the milestone. The
facts about the pack itself were computed from its file,
`src/tft/packs/starter.json`.

## The method

`tools/balance_report.py` measures two things on a market pack under a rule
set.

**What each class does on its own.** The tool takes every window of
`slice_bars` consecutive bars of the pack (51 windows of 10 bars in the starter
pack) and trades every class's strategy on every symbol in every window, as a
unit with no item and no row effect. A trade gives an *edge*: the strategy's
profit minus `risk_penalty_tenths / 10` times its worst drawdown, in percent.
The edge becomes a *result factor*, the number the unit's size is multiplied
by: 1.00 keeps the size, 0 is a wipe-out and `result_cap_percent / 100` is the
most a unit can grow to.

**Whether a simple way of playing beats the bot.** The tool plays whole
matches in which the first seat follows a probe policy and the other seven
play the greedy bot, and reports the probe seat's mean placement.

It prints four tables:

- **Classes.** One row per class, over every symbol of the pack (29 symbols
  times 51 windows, 1,479 trades per class on the starter pack). *Edge %* is
  the mean edge and *Spread* its standard deviation. *Factor* is the mean
  result factor. *Wiped out* and *Capped* are the shares of trades that ended
  at 0 and at the cap. *Beats the field* is the chance that the class ends a
  window with a higher factor than another class in the same window, each on a
  symbol of the pack; a tie counts half and 50% is even.
- **Class by origin.** The mean result factor of each class on each origin's
  symbols. It shows which pairs of class and origin the pack favours.
- **Champions.** For each champion: the mean factor of its class on its own
  origin's symbols, its size at one star (its power divided by 10), and the
  two multiplied, which is its mean score at one star with no item, trait or
  row effect.
- **Policies.** The mean placement of the probe seat over the given number of
  matches (seeds 0, 1, 2, ...) against seven greedy bots. Lower is better; 4.5
  is the middle of eight seats. The probes are the greedy bot itself, an empty
  board (buys nothing, fields nothing), one unit (plays the bot, then benches
  every unit but the first), every unit in the back rows (plays the bot, then
  moves its units to rows 3 and 2, centre columns first) and every unit in the
  front rows (rows 0 and 1). A probe that places better than the bot has found
  an exploit.

Run it:

```bash
python -m pip install -e . -r requirements-dev.txt   # once: the tool imports the engine
python tools/balance_report.py                        # starter pack, default rules, 60 matches, plain text
python tools/balance_report.py --matches 60 --format markdown   # the tables below
python tools/balance_report.py --matches 0            # the three class tables only
python tools/balance_report.py --pack packs/live.json --rules my-rules.toml
```

The three class tables take under a second. The policy table plays five
probes times `--matches` matches, about 15 seconds for 60 matches on one
core, and the time grows with the number of matches. The output is
deterministic: the same pack, rules and number of matches print the same
tables. The tool exits with status 2 when the pack or the rules cannot be
used.

Two things to keep in mind when reading the policy table:

- **It is noisy.** The bot's placement in the probe seat has a standard
  deviation of about 2.4 places (computed from the 240 matches the tool plays
  for the bot's row with `--matches 240`; the tool prints only the mean). A
  mean over 60 matches therefore has a standard error of about 0.3 places,
  and over 240 matches about 0.15. A smaller difference is not a finding.
- **The probe sits in the first seat, and ties go against the first seat.**
  Seats eliminated in the same round are ranked in reverse seat order, so the
  first seat is placed last among them. Compare a probe with the bot's row of
  the table, not with 4.5.

## The current tables

The output of `python tools/balance_report.py --matches 60 --format markdown`
for 0.4.0 with the default rules:

Pack starter: 29 symbols, 2026-07-27 to 2026-10-19, 51 windows of 10 bars.

### Classes

Edge is the profit minus the penalised drawdown; the factor is what it multiplies a unit's size by. Beats the field is the chance of out-scoring another class on the same window; 50% is even.

| Class | Edge % | Spread | Factor | Wiped out | Capped | Beats the field |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Scalper | -1.79 | 6.27 | 0.88 | 9% | 1% | 51% |
| Swing | -1.97 | 8.40 | 0.82 | 11% | 6% | 45% |
| Momentum | -0.76 | 2.79 | 0.92 | 0% | 0% | 54% |
| Contrarian | -0.68 | 2.52 | 0.93 | 0% | 0% | 55% |
| Hedger | -0.27 | 5.71 | 0.93 | 0% | 6% | 47% |
| Arbitrageur | -1.07 | 3.31 | 0.90 | 3% | 0% | 57% |
| Quant | -0.99 | 2.00 | 0.90 | 0% | 0% | 51% |
| Whale | -3.03 | 12.60 | 0.78 | 24% | 10% | 41% |

### Class by origin

The mean result factor of each class on each origin's symbols; 1.00 keeps the size.

| Class | Equities | Tech | Crypto | Commodities | Bonds | Forex |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Scalper | 0.96 | 0.92 | 0.67 | 0.86 | 0.99 | 0.95 |
| Swing | 0.74 | 1.04 | 0.67 | 0.73 | 0.81 | 0.72 |
| Momentum | 0.96 | 0.94 | 0.87 | 0.92 | 0.92 | 0.93 |
| Contrarian | 0.89 | 0.98 | 0.87 | 0.93 | 0.96 | 0.99 |
| Hedger | 0.87 | 1.09 | 0.91 | 0.83 | 0.85 | 0.76 |
| Arbitrageur | 1.02 | 0.87 | 0.63 | 1.04 | 1.09 | 1.06 |
| Quant | 0.90 | 0.93 | 0.83 | 0.90 | 0.92 | 0.94 |
| Whale | 0.68 | 1.04 | 0.62 | 0.66 | 0.74 | 0.61 |

### Champions

The size is the unit's power at one star; the score is the size times the factor.

| Champion | Cost | Origin | Class | Factor | Size | Score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Pip Squeak | 1 | Forex | Scalper | 0.95 | 1.0 | 0.95 |
| Index Drone | 1 | Equities | Quant | 0.90 | 1.0 | 0.90 |
| Hodl Hamster | 1 | Crypto | Contrarian | 0.87 | 1.0 | 0.87 |
| Barrel Bo | 1 | Commodities | Swing | 0.73 | 1.0 | 0.73 |
| Coupon Clerk | 1 | Bonds | Hedger | 0.85 | 1.0 | 0.85 |
| Candle Reader | 1 | Tech | Momentum | 0.94 | 1.0 | 0.94 |
| Gap Gazelle | 2 | Equities | Momentum | 0.96 | 1.4 | 1.35 |
| Mean Reverend | 2 | Equities | Contrarian | 0.89 | 1.4 | 1.24 |
| Spread Spider | 2 | Forex | Arbitrageur | 1.06 | 1.4 | 1.48 |
| Gold Bug | 2 | Commodities | Hedger | 0.83 | 1.4 | 1.16 |
| Stable Coin | 2 | Crypto | Hedger | 0.91 | 1.4 | 1.28 |
| Yield Yeti | 2 | Bonds | Swing | 0.81 | 1.4 | 1.13 |
| Breakout Bull | 3 | Equities | Momentum | 0.96 | 2.0 | 1.93 |
| Bear Baron | 3 | Equities | Contrarian | 0.89 | 2.0 | 1.78 |
| Vol Vampire | 3 | Tech | Quant | 0.93 | 2.0 | 1.87 |
| Carry Caravan | 3 | Forex | Swing | 0.72 | 2.0 | 1.44 |
| Miner Mole | 3 | Crypto | Scalper | 0.67 | 2.0 | 1.34 |
| Crude Colossus | 3 | Commodities | Momentum | 0.92 | 2.0 | 1.84 |
| Market Maker | 4 | Equities | Arbitrageur | 1.02 | 2.8 | 2.84 |
| Fed Whisperer | 4 | Bonds | Quant | 0.92 | 2.8 | 2.56 |
| Flash Crash | 4 | Tech | Scalper | 0.92 | 2.8 | 2.57 |
| Whale Watcher | 4 | Crypto | Whale | 0.62 | 2.8 | 1.72 |
| Black Swan | 5 | Equities | Contrarian | 0.89 | 4.0 | 3.55 |
| Central Banker | 5 | Bonds | Whale | 0.74 | 4.0 | 2.98 |
| Algo Overlord | 5 | Tech | Quant | 0.93 | 4.0 | 3.74 |

### Policies

The mean placement of one seat over 60 matches against 7 greedy bots; 4.5 is even, lower is better. A probe that places better than the bot is an exploit.

| Policy | Mean placement |
| --- | ---: |
| greedy bot (default formation) | 4.70 |
| empty board | 8.00 |
| one unit | 8.00 |
| every unit in the back rows | 4.67 |
| every unit in the front rows | 6.00 |

### What the tables say

- No class gains on average. Every mean edge is negative (-0.27 to -3.03) and
  every mean factor is below 1.00 (0.78 to 0.93): on this pack the average
  unit ends a round smaller than it started.
- No class dominates. "Beats the field" runs from 41% (Whale) to 57%
  (Arbitrageur). The Whale is the weakest class: it is wiped out in 24% of
  its trades.
- The pack favours Tech. It is the only origin on which the classes that hold
  a position through the slice average above 1.00 (Swing 1.04, Hedger 1.09,
  Whale 1.04). The Crypto stand-ins are the worst origin for six of the eight
  classes. The Arbitrageur, which does not care about direction, averages
  above 1.00 on four origins and 0.63 on Crypto, where more than half of the
  daily moves are beyond its quiet range of 2 percent.
- Cost orders the champions with three exceptions, all of them a weak class
  on a weak origin: Whale Watcher (cost 4, 1.72) scores less than four of the
  six 3-cost champions, and Miner Mole (cost 3, 1.34) and Carry Caravan
  (cost 3, 1.44) score less than the 2-cost Spread Spider (1.48). The table
  leaves out traits, stars, items and rows.
- Not fielding units loses: an empty board and a single unit place last in
  every match. Putting every unit in the front rows costs more than a place
  (6.00). Putting every unit in the back rows places level with the default
  formation (4.67 against 4.70); see *The grid* below.

## What M3 changed and why

The "before" numbers in this section were measured during the milestone on
the starter pack (51 windows of 10 bars, 29 symbols). Where the current tool
reproduces one, that is said.

### A score can no longer be negative

In 0.3.0 a unit's score was its size times its risk-adjusted return:
`size * (profit - 0.5 * drawdown)`. That is negative whenever the trade
loses, and on the starter pack it usually was: 78 percent of board scores were
negative. A negative total turned everything that should help into a cost:
trait and augment bonuses, stars and size items all multiplied the loss. The
best move was not to play. Over 80 matches against seven bots a seat that
fielded nothing placed 1.89 on average and a seat that fielded one unit placed
1.80, where 4.50 is even.

Since 0.4.0 a unit's score is its size times a result factor: 100 percent
plus `result_weight` (10) percent per percent of edge, kept between 0 and
`result_cap_percent` (200) percent. A flat trade keeps the size, an edge of
-10 percent or worse wipes the unit out, and an edge of +10 percent or better
doubles it. The factor is never negative, so a fielded unit can only add to
its board's score, and the bonuses multiply a total that is never negative.

After the change the same probes placed 8.00 and 8.00, and the bot 4.67
(60 matches). The current tool reproduces those three numbers with
`arb_capture_percent = 25`, the value at the time; with the released value of
20 they are the 8.00, 8.00 and 4.70 of the table above.

### The strategies were brought closer together

Mean edge per class, before the tuning (with a risk penalty of 0.5) and now:

| Class | Before | Now |
| --- | ---: | ---: |
| Arbitrageur | +2.33 | -1.07 |
| Hedger | -0.11 | -0.27 |
| Swing | -3.08 | -1.97 |
| Scalper | -4.53 | -1.79 |
| Whale | -6.26 | -3.03 |

Before, the Arbitrageur was positive in every window: it earned a share of
every move, up or down, and nothing could go against it. The Whale, the
Scalper and the Swing lost heavily. What changed:

- **Risk penalty** 0.5 to 0.3 (`risk_penalty_tenths` 5 to 3): a drawdown
  weighs less in every edge.
- **Arbitrageur**: it now earns `arb_capture_percent` (20) percent of the
  part of a bar's move up to `arb_quiet_move_tenths` (2.0 percent) and loses
  `arb_adverse_percent` (50) percent of the part beyond it, like a market
  maker run over by a big move. Its drawdown is now measured on its own path.
- **Scalper**: it trades a bar only after a bar that moved at least
  `scalp_threshold_tenths` (1.5 percent), instead of every bar, so it pays
  costs less often.
- **Whale**: leverage 2.0 to 1.5 (`whale_leverage_tenths` 20 to 15).
- **Hedger**: premium 0.5 to 1.0 percent a slice (`hedge_premium_tenths`
  5 to 10).

Momentum, Contrarian and Quant kept their strategies; the lower penalty moved
their mean edges from -0.98, -0.88 and -1.37 to -0.76, -0.68 and -0.99. The
range of the class means went from 8.6 points to 2.8.

The "before" column can be checked with the current tool and a rules file
that sets `risk_penalty_tenths = 5`, `hedge_premium_tenths = 5`,
`whale_leverage_tenths = 20`, `scalp_threshold_tenths = 0`,
`arb_quiet_move_tenths = 1000000` and `arb_adverse_percent = 0`. It prints the
same means for the Hedger, the Swing, the Scalper and the Whale. The
Arbitrageur comes out at +2.58, not +2.33, because in 0.3.0 it added its
captures up instead of compounding them and counted its trading costs as its
drawdown. In that run it beats the field 84% of the time and the Whale 36%.

### The grid

The first grid of the milestone had row sizes of 80, 90, 100 and 120 percent,
row shields of 30, 15, 0 and 0 percent, a cover shield of 25 percent and an
exposure penalty of 25 percent. With the new scoring a seat that put every
unit in the back rows placed 3.08 against bots on the default formation,
which placed 4.78; every unit in the front rows placed 6.27 (60 matches).
Standing at the back was simply better.

The grid was retuned to sizes of 90, 95, 100 and 110 percent, shields of 40,
20, 0 and 0 percent, a cover shield of 25 percent and an exposure penalty of
50 percent. The default rows, which first put Hedger and Arbitrageur in
front, now follow each class's drawdowns: Whale and Swing stand in the front
row, Scalper and Hedger in the second row, every other class in the back row.

What the current tool measures for the two formation probes:

| Rules | Matches | Bot, default formation | Back rows | Front rows |
| --- | ---: | ---: | ---: | ---: |
| Retuned grid with `arb_capture_percent = 25`, as it was when the grid was retuned | 60 | 4.67 | 4.75 | 6.03 |
| Released rules | 60 | 4.70 | 4.67 | 6.00 |
| Released rules | 240 | 4.68 | 4.56 | 6.00 |
| The first grid numbers, everything else as released | 60 | 4.82 | 4.00 | 6.92 |

The last row differs from the 3.08, 4.78 and 6.27 above because its bots
stand on the new default rows. It shows the same thing: the first numbers
favour the back.

The front rows are clearly worse than the default. The back rows are no
longer clearly better: the gap went from 1.7 places to 0.03 over 60 matches
and 0.12 over 240, which is inside the noise of the measurement. That is not
proof that the default formation is the best one. The tool cannot tell the
two apart at this number of matches, and on the released rules the back-row
probe was not behind the bot in either run.

### Survivors

The winner's surviving units are added to the stage's base damage, so the
margin of a fight decides how much a loss hurts. In 0.3.0 the margin was the
difference of the two scores over the sum of their absolute values. With
scores that are never negative that left one survivor in 80 percent of
fights. The margin is now the share of the winning score that was not needed
to win, `(winner - loser) / winner`: 12 against 9 keeps a quarter of the
winner's units, 12 against nothing keeps them all, and at least one unit
survives.

## Known limits

- **One pack, one period.** The starter pack is 60 trading days, 2026-07-27
  to 2026-10-19. Its 51 windows overlap: two neighbouring windows share nine
  of their ten days, so they are not 51 independent samples. In that period
  all nine Tech stand-ins rose (12.7 percent on average, first close to last
  close) and the other five origins fell on average (Equities 3.6 percent,
  Crypto 9.7, Commodities 5.4, Bonds 1.7, Forex 10.5); 13 of the 20 symbols
  outside Tech fell. So the classes that hold a long position look weak
  outside Tech and the Arbitrageur looks strong. Another period would rank
  the classes differently. The numbers are tuned to this one.
- **The origins are stand-ins.** Every symbol is a US stock playing the part
  of a market (`STARTER_ORIGINS` in `tools/build_market_pack.py`): Equities
  is KO, BAC, HD, CCL, RCL and BRK-B; Tech is AAPL, MSFT, GOOGL, META, NVDA,
  AMD, INTC, AMZN and TSLA; Crypto is AMC, PLUG, LCID, RIVN, PLTR and SOFI;
  Commodities is XOM, GE and F; Bonds is CI, PNC and BLK; Forex is JPM and
  MS. The pack holds no bond, currency, commodity or crypto prices. What the
  tables say about an origin is a statement about those stocks.
- **Daily closes only.** 28 of the 29 symbols have bars whose open, high and
  low equal the close; only TSLA has real highs and lows. On those 28 symbols
  a stop or a target can only trigger on a close.
- **The tables trade symbols a match never uses.** In a match the column
  picks the symbol, and the board has seven columns, so a Tech unit trades
  one of the first seven Tech symbols. AMZN and TSLA are in the tables and
  never in a match on this pack.
- **One bot.** Every opponent is the same greedy policy: it buys what it can
  afford, fields its strongest units on their default cells, buys experience
  when it has gold to spare, and crafts and equips items at once. It never
  rerolls, sells, moves a unit or chooses between augments. "Level with the
  bot" is a low bar and says nothing about play against people.
- **Classes are measured bare.** The class tables use a unit with no item,
  star, trait or row effect. How those interact is only measured through the
  bot matches.
- **No playtest.** The playtest with ten external players that closes
  milestone M3 has not happened. Everything above is bots and replayed bars.

## What to do next

1. **More packs and regimes.** Build packs from other periods (a falling
   market, a flat one) and from real asset classes with real highs and lows,
   and run the tool on each with `--pack`. A balance number should hold on
   several packs before it is trusted.
2. **A second bot policy.** A bot that rerolls, saves for interest and
   positions its units, so that the policy table measures against something
   that plays back, and probes that test the economy as well as the board.
3. **A sharper policy table.** More matches by default, the standard error
   next to each mean, and the probe moved through the seats so that
   tie-breaking does not count against it.
4. **The playtest.** Ten external players and the median round time, the
   exit criteria of milestone M3 in [PRD.md](PRD.md).
