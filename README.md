# nolottery

Legal Washington Lottery expected-value analysis console app.

`nolottery` helps answer two different questions:

- "Which game has the best expected value after ticket cost and taxes?"
- "If I have a small budget, which play gives me the highest chance to win any prize?"

It does not predict lucky numbers with an edge. For fair lottery drawings, one valid number selection has the same odds as any other valid selection. Quick Pick predictions are random valid selections and are labeled as having no odds advantage.

## Supported Games

Washington draw games currently supported:

- Powerball
- Mega Millions
- Lotto
- Hit 5
- Match 4
- Pick 3
- Cash Pop
- Daily Keno

## How It Works

The app has built-in Washington Lottery prize and odds metadata for each supported game. It uses that metadata to calculate:

- gross expected value
- after-tax expected value
- net expected value after ticket cost
- hit rate, meaning the chance of winning any prize
- a `PLAY` or `SKIP` decision

The default decision is conservative: if the best option is still negative expected value, the app says `SKIP`.

The app can also fetch official Washington Lottery past drawing pages and persist local snapshots in SQLite. Fetching is useful for keeping source HTML and parsed draw results locally, but the EV calculations are based on the configured odds and prize tables.

## Quickstart

Run commands through `uv` from the project root:

```bash
uv run lottery --help
```

Analyze one game:

```bash
uv run lottery analyze cashpop
```

Analyze every supported game:

```bash
uv run lottery analyze all
```

Rank games by best after-tax expected value:

```bash
uv run lottery rank
```

Find the highest hit-rate play within a small budget:

```bash
uv run lottery recommend --budget 1
```

For a $1 budget, this currently recommends a Daily Keno 4-Spot play because it has the highest chance of winning any prize among supported single-ticket options within that budget.

The recommendation output includes a `Quick Pick Prediction` field: a random valid selection with no odds advantage.

Generate lower-share-risk number picks:

```bash
uv run lottery low-share powerball
uv run lottery low-share all --count 5
```

Low-share picks use a transparent heuristic to avoid common human selection
patterns, such as birthday-heavy combinations, sequential runs, tight clusters,
and culturally popular numbers. They do not improve draw odds; they only aim to
reduce overlap with other player-picked combinations if a ticket wins.

Use `--seed` for deterministic output, `--candidates` to control how many random
candidates are scored per wager variation, and JSON output for scripting:

```bash
uv run lottery low-share daily-keno --count 10 --seed 123 --output json
```

Ask OpenAI to evaluate the generated low-share candidates and select an
entertainment pick:

```bash
OPENAI_API_KEY=... uv run lottery low-share powerball --evaluate openai --output json
```

OpenAI receives the generated candidates, their low-share scores, and the
heuristic reasons. It is instructed that low-share scores are not draw-odds
advantages and may only select a candidate as an entertainment choice.

You can optionally exclude exact winning combinations already stored in local
draw history:

```bash
uv run lottery low-share powerball --avoid-recent-winning-combos
uv run lottery low-share powerball --avoid-recent-winning-combos --last 180
```

This history filter is duplicate avoidance only. It does not make any remaining
combination more likely to be drawn.

Ask OpenAI to evaluate the recommendation and return a strict JSON decision:

```bash
OPENAI_API_KEY=... uv run lottery recommend --budget 50 --evaluate openai --output json
```

OpenAI receives a reduced decision payload: budget, affordable candidates, hit rates, ticket costs, net after-tax EV, and deterministic `PLAY`/`SKIP` facts. Quick-pick numbers are omitted because they have no odds advantage. The OpenAI evaluator may return `SKIP`, `PLAY`, or `PLAY_FOR_ENTERTAINMENT`; it must not change the calculated odds or expected values.

## Fetching Draw Data

Fetch one game's official past drawing page. By default this uses the Washington Lottery `Past 180 Days` view:

```bash
uv run lottery fetch cashpop
```

Fetch every supported game:

```bash
uv run lottery fetch all
```

Regular fetches keep prior draw rows and persist only draw results newer than the
latest stored draw date for that game.

Backfill all available yearly pages for one game:

```bash
uv run lottery fetch cashpop --backfill
```

Backfill all available yearly pages for every supported game:

```bash
uv run lottery fetch all --backfill
```

Backfill mode first reads the normal past-drawings page, discovers the year options published by Washington Lottery, then fetches each yearly page. Stored draw rows for that game are replaced by the combined parsed yearly results.

For tests or offline analysis, fetch commands can read local HTML files from a directory. Current-window files are named by game slug:

```bash
uv run lottery fetch all --source-dir ./fixtures
```

Expected file names include:

```text
cashpop.html
daily-keno.html
hit-5.html
lotto.html
match-4.html
mega-millions.html
pick-3.html
powerball.html
```

Backfill fixture files add the year to the file name:

```text
cashpop-2026.html
cashpop-2025.html
daily-keno-2026.html
daily-keno-2025.html
```

## Randomness Audits

Audit commands inspect stored draw history from `draw_results`. Fetch or backfill draw data first, then run audits against perfect uniform randomness:

```bash
uv run lottery audit frequency cashpop
uv run lottery audit chi-square powerball
uv run lottery audit pairs hit-5
uv run lottery audit triples daily-keno
uv run lottery audit gaps cashpop
uv run lottery audit all
```

Every focused audit command accepts a game slug or `all`, plus `--output table|json` and `--last N`. `--last N` uses the most recent N valid parsed draws after malformed rows are skipped.

`audit all` runs frequency, chi-square, pair distribution, triple distribution, and draw-gap audits across every supported game by default. You can scope it to one game:

```bash
uv run lottery audit all cashpop
```

JSON output for `audit all` is compact by default. Add `--details` to include full buckets and per-number gap values:

```bash
uv run lottery audit all --output json
uv run lottery audit all --output json --details
```

Ask OpenAI to explain audit results:

```bash
OPENAI_API_KEY=... uv run lottery audit all cashpop --evaluate openai --output json
OPENAI_API_KEY=... uv run lottery audit frequency cashpop --evaluate openai
```

OpenAI receives compact audit facts, including statuses, p-values, draw counts,
warnings, and notable bucket summaries. It is instructed not to treat audit
signals as proof of bias or as a way to predict future winning numbers.

Audit statuses are `OK`, `WARN`, `INSUFFICIENT_DATA`, or `NOT_APPLICABLE`. Chi-square tests use SciPy p-values and mark `WARN` when `p < 0.01`; sparse tests are marked `INSUFFICIENT_DATA` when expected bucket counts are below 5. Pair and triple audits include chi-square summaries, but they are often sparse for large games. Gap audits report per-number gap statistics and use a pooled geometric chi-square test over completed gaps only.

Statistical warnings are screening signals, not proof of non-random drawing behavior.

## JSON Output

Use JSON output for scripting or downstream analysis:

```bash
uv run lottery analyze cashpop --output json
uv run lottery analyze all --output json
uv run lottery recommend --budget 1 --output json
uv run lottery recommend --budget 50 --evaluate openai --output json
uv run lottery audit all --output json
uv run lottery audit all cashpop --evaluate openai --output json
uv run lottery low-share powerball --output json
uv run lottery low-share powerball --evaluate openai --output json
```

## Ticket Ledger

The ledger records actual tickets bought and prizes won. This is separate from EV analysis and helps compare real results against recommendations over time.

Add a ticket:

```bash
uv run lottery ledger add
```

Summarize spending, winnings, profit, and ROI:

```bash
uv run lottery ledger summary
```

## Data Storage

By default, local data is stored in:

```text
~/.nolottery/lottery.sqlite3
```

Use `--data-dir` to isolate data for experiments or tests:

```bash
uv run lottery --data-dir /tmp/nolottery analyze all
```

## Development

```bash
uv run --extra dev pytest
```

## License

MIT. See [LICENSE](LICENSE).
