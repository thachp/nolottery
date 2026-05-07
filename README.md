# Nolottery

U.S. lottery draw-game expected-value, draw-result, coverage, and ledger console app.

`nolottery` helps answer two core questions:

- "Which game has the best expected value after ticket cost and taxes?"
- "If I have a small budget, which play gives me the highest chance to win any prize?"

It does not predict lucky numbers with an edge. For fair lottery drawings, one valid number selection has the same odds as any other valid selection. Quick Pick predictions are random valid selections and are labeled as having no odds advantage.

## Questions It Can Help Answer

Beyond the two core questions above, `nolottery` can also help answer:

- "Which supported draw games are least bad by expected value in my selected lottery jurisdiction?"
- "How much does ticket cost and estimated tax change the economics of a game?"
- "Which affordable play style gives me the best hit rate for a specific budget?"
- "If I am going to play for entertainment, which valid numbers are less likely to overlap with common human-picked patterns?"
- "What winning numbers have been drawn recently, based on locally fetched official data?"
- "Do stored draw histories show unusual frequency, pair, triple, or gap patterns worth reviewing?"
- "How much have I spent, won, lost, or earned back over time on real tickets?"

These answers are for EV analysis, budgeting, recordkeeping, and audit-style review. They do not create a way to predict future winning numbers or improve fair drawing odds.

## Jurisdiction Support

Commands default to Washington (`wa`). Use `--jurisdiction` or `-j` to select another lottery jurisdiction where the command supports it:

```bash
uv run lottery analyze cashpop -j wa
uv run lottery fetch daily-3 -j ca
uv run lottery coverage -j ny
```

Coverage uses support statuses rather than a single supported/unsupported flag:

- `cataloged`: the draw game is known for the jurisdiction.
- `rules_verified`: rules metadata has been reviewed.
- `ev_supported`: expected-value commands can use the game.
- `fetch_supported`: official draw results can be fetched or imported.
- `audit_supported`: stored draws can be audited.
- `low_share_supported`: low-share picks can be generated.

Coverage also reports jurisdiction-level statuses:

- `cataloged`: at least one draw-game offering is cataloged for the jurisdiction.
- `catalog_pending`: the state is recognized, but its draw-game offerings are not cataloged yet.
- `no_state_lottery`: the state does not have a state lottery.

Washington draw games currently have EV, fetch, audit, and low-share support:

- Powerball
- Mega Millions
- Lotto
- Hit 5
- Match 4
- Pick 3
- Cash Pop
- Daily Keno

California currently has EV, fetch, audit, and low-share support for its cataloged draw games. New York, Florida, and District of Columbia have representative catalog entries, with New York Numbers/Win 4 and Florida Pick 2/Pick 3/Pick 4/Pick 5 also supporting EV, fetch, and low-share. Arizona, Arkansas, Colorado, Connecticut, Delaware, Georgia, Idaho, Illinois, Indiana, Iowa, Kentucky, Louisiana, Maine, Maryland, and Texas Powerball and Mega Millions support EV, fetch, audit, low-share, and one-page historical backfill from official past winning-number pages.

Every U.S. state code is recognized by coverage. States whose game catalogs have not been verified yet report `catalog_pending`. Alabama, Alaska, Hawaii, Nevada, and Utah report `no_state_lottery`; game capabilities such as EV, recommendations, fetch, backfill, audit, and low-share are intentionally unavailable there until a state lottery exists.

Run coverage to see current status and blocking reasons:

```bash
uv run lottery coverage -j wa
uv run lottery coverage -j ca --output json
uv run lottery coverage -j tx
```

## Features

| Feature                   | Command                                | What it is for                                                                                                                                                                      |
| ------------------------- | -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Expected-value analysis   | `analyze`                              | Calculates gross EV, after-tax EV, net EV after ticket cost, hit rate, and a conservative `PLAY` or `SKIP` decision for EV-supported games in a jurisdiction.                       |
| Game ranking              | `rank`                                 | Compares EV-supported games by their best wager option in the selected jurisdiction.                                                                                                |
| Budget recommendation     | `recommend`                            | Finds the affordable play style with the highest chance of winning any prize for a single ticket budget. It also includes a random valid Quick Pick example with no odds advantage. |
| Low-share pick generation | `low-share`                            | Generates valid number selections that avoid common human picking patterns for low-share-supported games. This is for reducing likely prize sharing, not improving draw odds.        |
| Coverage reporting        | `coverage`                             | Shows known draw games, support statuses, source presence, adapters, reviewed dates, and blocking reasons by jurisdiction.                                                          |
| Official draw fetching    | `fetch`                                | Downloads or imports official draw-result data for fetch-supported game offerings, stores source snapshots, and persists parsed draw results in SQLite.                             |
| Recent draw browser       | `draws`                                | Shows the most recent stored winning numbers, either for one game or all games in the selected jurisdiction, with table or JSON output.                                             |
| Randomness audits         | `audit`                                | Runs screening tests over stored draw history: frequency, chi-square, pair, triple, and gap audits. These are diagnostics, not prediction tools.                                    |
| OpenAI review             | `--evaluate openai`                    | Optional second-pass explanation or decision review for recommendations, audits, and low-share picks using a reduced facts-only payload. Requires `OPENAI_API_KEY`.                 |
| Ticket ledger             | `ledger`                               | Records real tickets, cost, winnings, numbers, multiplier/use details, and summarizes spend, profit, and ROI over time.                                                             |
| Offline fixtures          | `fetch --source-file` / `--source-dir` | Imports already-downloaded official HTML for tests, reproducible analysis, or no-network workflows.                                                                                 |
| JSON output               | `--output json`                        | Produces machine-readable output for scripting, saved reports, or downstream analysis.                                                                                              |

## How It Works

The app has bundled, reviewed metadata for known draw games by lottery jurisdiction. Washington and California currently have full EV metadata for their supported draw games. Representative New York, Florida, DC, and Texas entries are present in the coverage catalog with their current support statuses. Other U.S. states are recognized as jurisdictions so expansion blockers are explicit instead of appearing as unknown jurisdiction errors.

For EV-supported games, the app uses reviewed prize and odds metadata to calculate:

- gross expected value
- after-tax expected value
- net expected value after ticket cost
- hit rate, meaning the chance of winning any prize
- a `PLAY` or `SKIP` decision

The default decision is conservative: if the best option is still negative expected value, the app says `SKIP`.

The app can also fetch official draw-result pages for fetch-supported game offerings and persist local snapshots in SQLite. Fetching is useful for keeping source HTML and parsed draw results locally, powering recent-draw views, avoiding exact recent winning combinations in low-share generation, and running randomness audits. The EV calculations still come from configured odds and prize metadata or future variable prize estimates, not from historical draw frequency.

Important limits:

- The app does not predict future winning numbers.
- Historical frequency, pair, triple, or gap results do not create an odds edge.
- Low-share picks do not make a combination more likely to be drawn.
- OpenAI evaluation is constrained to explain or choose among calculated facts; it must not alter odds or expected values.

## Quickstart

Run commands through `uv` from the project root:

```bash
uv run lottery --help
```

Analyze one game:

```bash
uv run lottery analyze cashpop
uv run lottery analyze cashpop -j wa
```

Analyze every EV-supported game in the default jurisdiction:

```bash
uv run lottery analyze all
```

Rank games by best after-tax expected value:

```bash
uv run lottery rank
uv run lottery rank -j wa
```

Analyze one game or all games as JSON:

```bash
uv run lottery analyze cashpop --output json
uv run lottery analyze all --output json
uv run lottery coverage -j ca --output json
```

Find the highest hit-rate play within a small budget:

```bash
uv run lottery recommend --budget 1
```

For a $1 budget, this currently recommends a Daily Keno 4-Spot play because it has the highest chance of winning any prize among supported single-ticket options within that budget.

The recommendation output includes a `Generated at` timestamp and a `Quick Pick Prediction` field. The timestamp is a full ISO 8601 local-time snapshot for the recommendation run; the Quick Pick Prediction is a random valid selection with no odds advantage and can change between runs.

For budgets under $1, the recommender can select eligible lower-cost options, such as Pick 3 pair plays. For larger budgets, it may select high-hit-rate multi-number wager styles, while still reporting the net after-tax EV and conservative decision.

Ask OpenAI to evaluate the recommendation and return a strict JSON decision:

```bash
OPENAI_API_KEY=... uv run lottery recommend --budget 50 --evaluate openai --output json
```

OpenAI receives a reduced decision payload: `generated_at`, budget, affordable candidates, hit rates, ticket costs, net after-tax EV, and deterministic `PLAY`/`SKIP` facts. Quick-pick numbers are omitted because they have no odds advantage. The OpenAI evaluator may return `SKIP`, `PLAY`, or `PLAY_FOR_ENTERTAINMENT`; it must not change the calculated odds or expected values.

## Low-Share Picks

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

You can optionally exclude exact winning combinations already stored in local draw history:

```bash
uv run lottery low-share powerball --avoid-recent-winning-combos
uv run lottery low-share powerball --avoid-recent-winning-combos --last 180
```

This history filter is duplicate avoidance only. It does not make any remaining
combination more likely to be drawn.

## Expected-Value Commands

Use `analyze` when you want the detailed economics for one game or every EV-supported game in a jurisdiction:

```bash
uv run lottery analyze powerball
uv run lottery analyze powerball -j wa
uv run lottery analyze all --output json
```

Use `rank` when you want a quick cross-game comparison:

```bash
uv run lottery rank
uv run lottery rank -j wa
```

Use `recommend` when you have a single-ticket budget and care about the highest hit rate rather than best EV:

```bash
uv run lottery recommend --budget 0.50
uv run lottery recommend --budget 75 --output json
uv run lottery recommend -j wa --budget 75 --output json
```

Recommendation JSON includes a top-level `generated_at` timestamp in full ISO 8601 local time with offset, captured once for the whole response.

## Coverage

Use `coverage` to inspect known draw games and the current support level for a lottery jurisdiction:

```bash
uv run lottery coverage -j wa
uv run lottery coverage -j ca --output json
uv run lottery coverage -j tx
```

Catalog-only games are visible in coverage but excluded from EV commands until rules metadata is verified. Catalog-pending jurisdictions are accepted by coverage and excluded from game commands until their official game offerings, result sources, and backfill adapters are added.

## Fetching Draw Data

Fetch one game's official draw-result source. Washington uses the Washington Lottery `Past 180 Days` view:

```bash
uv run lottery fetch cashpop
uv run lottery fetch cashpop -j wa
```

California Daily 3 uses a California-specific parser:

```bash
uv run lottery fetch daily-3 -j ca
uv run lottery draws daily-3 -j ca --output json
```

Fetch every fetch-supported game in the selected jurisdiction:

```bash
uv run lottery fetch all
uv run lottery fetch all -j wa
```

Regular fetches keep prior draw rows and persist only draw results newer than the
latest stored draw date for that game.

The Washington parser handles current Washington Lottery table variants, including draw tables with no prize rows and tables that contain extra `game-balls` cells in prize rows. In those cases it still stores the draw date and first winning-number cell, while reporting zero prize rows when prize data is absent.

Show recent stored winning numbers:

```bash
uv run lottery draws all
uv run lottery draws cashpop --limit 10
uv run lottery draws daily-3 -j ca --limit 10
```

Use JSON output for scripting:

```bash
uv run lottery draws all --output json
uv run lottery draws all -j wa --output json
```

Backfill all available yearly pages for one game:

```bash
uv run lottery fetch cashpop --backfill
```

Backfill all available yearly pages for every fetch-supported game in the selected jurisdiction:

```bash
uv run lottery fetch all --backfill
```

Backfill mode first reads the normal past-drawings page for a fetch-supported adapter, discovers the year options when the adapter supports them, then fetches each yearly page. Stored draw rows for that game offering are replaced by the combined parsed yearly results.

For tests or offline analysis, fetch commands can read local HTML files from a single file or a directory:

```bash
uv run lottery fetch cashpop --source-file ./fixtures/cashpop.html
uv run lottery fetch daily-3 -j ca --source-file ./fixtures/daily-3.html
uv run lottery fetch all --source-dir ./fixtures
```

Current-window directory files are named by game slug:

```bash
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

## Recent Draws

Use `draws` to inspect parsed winning numbers already stored in the local database:

```bash
uv run lottery draws
uv run lottery draws all --limit 5
uv run lottery draws powerball --limit 20 --output json
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

What each audit is for:

- `frequency`: counts how often each number or number pool appears, then compares observed counts with a uniform expectation.
- `chi-square`: reports the same uniformity test as a focused chi-square command, split by game-specific pools such as white balls and bonus balls.
- `pairs`: checks within-draw pair distributions, useful for spotting unusual pair concentration in games where the sample size is large enough.
- `triples`: checks within-draw triple distributions. This is often sparse for large games and may be marked `INSUFFICIENT_DATA`.
- `gaps`: reviews draw intervals between appearances for each number and uses a pooled geometric chi-square screen over completed gaps.
- `all`: runs the full audit matrix across one game or every audit-supported game in the selected jurisdiction.

Every focused audit command accepts a game slug or `all`, plus `--output table|json` and `--last N`. `--last N` uses the most recent N valid parsed draws after malformed rows are skipped.

`audit all` runs frequency, chi-square, pair distribution, triple distribution, and draw-gap audits across every audit-supported game in the selected jurisdiction by default. You can scope it to one game:

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

## OpenAI Evaluation

OpenAI evaluation is optional and available on:

```bash
uv run lottery recommend --evaluate openai
uv run lottery low-share powerball --evaluate openai
uv run lottery audit all cashpop --evaluate openai
```

Use it when you want a concise narrative explanation or a constrained entertainment decision over already-calculated facts. Set `OPENAI_API_KEY` in the environment and optionally choose a model:

```bash
OPENAI_API_KEY=... uv run lottery audit all --evaluate openai --openai-model gpt-5.2 --output json
```

The OpenAI payloads intentionally omit or constrain data that could imply false precision. Recommendation evaluation omits Quick Pick numbers. Low-share evaluation includes candidate scores and reasons but labels them as no-odds-advantage. Audit explanation includes p-values, statuses, warnings, and notable buckets, with instructions not to present audit signals as proof of bias or predictability.

## JSON Output

Use JSON output for scripting or downstream analysis:

```bash
uv run lottery analyze cashpop --output json
uv run lottery analyze all --output json
uv run lottery coverage -j ca --output json
uv run lottery recommend --budget 1 --output json
uv run lottery recommend --budget 50 --evaluate openai --output json
uv run lottery draws all --output json
uv run lottery audit all --output json
uv run lottery audit all cashpop --evaluate openai --output json
uv run lottery low-share powerball --output json
uv run lottery low-share powerball --evaluate openai --output json
```

Jurisdiction-aware JSON outputs include `jurisdiction_code` where the result is scoped to one jurisdiction.

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

The add flow prompts for purchase date, game, draw date, cost, winnings, option, multiplier/use details, numbers, whether the ticket followed the recommendation, retailer, and notes. The summary aggregates total tickets, total spent, total won, profit, and ROI percentage.

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
