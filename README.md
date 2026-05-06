# nolottery

Legal Washington Lottery expected-value analysis console app.

The Python package is `nolottery`; the installed CLI command is `lottery`.

`nolottery` helps answer two different questions:

- "Which game has the best expected value after ticket cost and taxes?"
- "If I have a small budget, which play gives me the highest chance to win any prize?"

It does not predict lucky numbers. For fair lottery drawings, one valid number selection has the same odds as any other valid selection. Suggested numbers are deterministic examples so the CLI can produce a complete ticket recommendation.

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

## Fetching Draw Data

Fetch one game's official past drawing page:

```bash
uv run lottery fetch cashpop
```

Fetch every supported game:

```bash
uv run lottery fetch all
```

For tests or offline analysis, `fetch all` can read local HTML files from a directory. Files must be named by game slug:

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

## JSON Output

Use JSON output for scripting or downstream analysis:

```bash
uv run lottery analyze cashpop --output json
uv run lottery analyze all --output json
uv run lottery recommend --budget 1 --output json
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
