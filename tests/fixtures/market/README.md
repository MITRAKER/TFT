# Market fixtures

Real Yahoo Finance responses captured in October 2026, taken from the
MIT-licensed [Day Trader skill](https://github.com/Jakeschincariol/day-trader-skill)
by Jake Schincariol (`tests/fixtures/trader-scanner` and `trader-timemachine`).

| File | Contents |
| --- | --- |
| `spark-3mo-a.json`, `spark-3mo-b.json` | Yahoo *spark* responses: three months of daily closes for 19 symbols each |
| `TSLA-60d5m.json.gz` | Yahoo *chart* response: 60 days of 5-minute TSLA bars |

They are the offline source of the starter market pack (`src/tft/packs/starter.json`)
and of every test that replays a market slice. Yahoo's endpoints are unofficial;
the data is used here as a historical fixture, not as a live feed.
