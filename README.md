# nolottery

Legal Washington Lottery expected-value analysis console app.

The Python package is `nolottery`; the installed CLI command is `lottery`.

## Current scope

- Washington draw games: Powerball, Mega Millions, Lotto, Hit 5, Match 4, Pick 3, Cash Pop, and Daily Keno
- Official Washington Lottery pages as source data
- SQLite local persistence
- Expected value is primary; hit rate is displayed separately
- `SKIP` is the default recommendation when all options are negative EV
- Simple configurable tax and bankroll settings in code
- Prompt-based ticket ledger

## Commands

```bash
uv run lottery fetch cashpop
uv run lottery analyze cashpop
uv run lottery analyze daily-keno
uv run lottery recommend --budget 1
uv run lottery rank
uv run lottery ledger add
uv run lottery ledger summary
```

Use JSON output for scripting:

```bash
uv run lottery analyze cashpop --output json
uv run lottery recommend --budget 1 --output json
```

## Development

```bash
uv run --extra dev pytest
```
