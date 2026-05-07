# Model Lottery Expansion Around Jurisdictions, Game Rules, and Game Offerings

Nolottery will model lottery expansion around **Lottery Jurisdictions**, shared **Game Rules**, and jurisdiction-specific **Game Offerings** instead of duplicating each draw game per state or treating all games as global. This keeps national games such as Powerball and Mega Millions from being copied across jurisdictions while still allowing each lottery authority to define its own availability, official result sources, tax treatment, ledger identity, and support status.

## Considered Options

- Duplicate every draw game per jurisdiction, such as `wa-powerball` and `ca-powerball`.
- Treat each draw game as global and attach jurisdiction details only where needed.
- Use shared **Game Rules Versions** plus jurisdiction-specific **Game Offerings**.

## Consequences

- Commands, database keys, fetch snapshots, draw results, and ledger entries need jurisdiction-aware identity.
- CLI commands select jurisdiction with `--jurisdiction` / `-j`; commands that support cross-jurisdiction comparison may accept `all` explicitly.
- Storage should use composite jurisdiction/game identity for game offerings instead of parsing a combined offering slug.
- Existing local Washington data should migrate automatically to jurisdiction code `wa`.
- Jurisdiction, rules, offering, source, support-status, and tax metadata should live in versioned data files while Python modules keep behavior; shared game rules versions should be represented once and referenced by jurisdiction-specific offerings.
- Game rules versions should include a structured number-format model used for validation, quick-pick generation, draw parsing, audits, and low-share eligibility.
- Official result fetching should use source-specific adapters behind a shared normalized draw-result shape.
- Ranking and recommendation default to one jurisdiction, with cross-jurisdiction comparison available only when explicitly requested.
- Coverage reporting should expose known draw games, support statuses, source presence, reviewed dates, adapters, and blocking reasons per jurisdiction.
- JSON outputs should include jurisdiction identity and a lightweight schema version when the jurisdiction-aware payload shape lands.
