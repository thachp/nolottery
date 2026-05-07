# Nolottery

Nolottery supports lottery draw-game analysis, budgeting, draw-result review, and recordkeeping without claiming a prediction edge.

## Language

**Draw Game**:
A lottery game where winning numbers or entries are selected in scheduled drawings and prizes are determined from the player's selected or assigned entries.
_Avoid_: Scratcher, instant ticket, raffle, promotion

**Lottery Jurisdiction**:
A government lottery authority whose rules, sources, taxes, and available draw games may differ from other authorities.
_Avoid_: State

**Game Rules**:
The number format, wager options, prize tiers, and odds that define how a draw game is played.
_Avoid_: Game metadata

**Game Rules Version**:
A specific effective-period version of game rules that can be safely reused by game offerings with the same number format, wager options, prize tiers, and odds.
_Avoid_: Game name

**Number Format**:
The structured definition of a draw game's number pools, selection counts, order rules, repeat rules, bonus numbers, sessions, and display labels.
_Avoid_: Slug-specific number logic

**Game Add-On**:
An optional feature attached to a base wager that changes ticket cost, prize treatment, odds, or draw participation.
_Avoid_: Extra option

**Game Offering**:
A draw game made available by a specific lottery jurisdiction with jurisdiction-specific sources, taxes, and availability.
_Avoid_: State game, local game

**Known Draw Game**:
A draw game identified as offered by a lottery jurisdiction, whether or not Nolottery can analyze or fetch it yet.
_Avoid_: Unsupported game

**Verified Catalog**:
The human-reviewed list of known draw games and support statuses for a lottery jurisdiction.
_Avoid_: Scraped catalog

**Support Status**:
The current capability level Nolottery provides for a known draw game, such as cataloged, rules verified, EV supported, fetch supported, audit supported, or low-share supported.
_Avoid_: Supported boolean

**Results Source**:
An official page, API, or file published by a lottery jurisdiction for draw results.
_Avoid_: URL

**Results Adapter**:
A source-specific fetcher and parser that converts a results source into normalized draw results.
_Avoid_: Generic parser

**Structured Draw Result**:
A normalized draw result that preserves display text while separately identifying primary numbers, bonus numbers, ordered digits, sessions, and source details where applicable.
_Avoid_: Winning number string

**Draw Event**:
A specific scheduled drawing for a game offering, identified by date plus session or source draw identifier when needed.
_Avoid_: Draw date

**Fixed Prize Rules**:
Prize tiers and odds that are stable enough to use from reviewed rules metadata.
_Avoid_: Static jackpot

**Variable Prize Estimate**:
A draw-specific advertised or current prize amount used when a prize tier is not fixed.
_Avoid_: Hardcoded jackpot

**Rule Verification**:
Confirmation that a game offering's number format, wager options, ticket costs, prize tiers, odds, source links, reviewed date, and tax assumptions are sufficient for EV analysis.
_Avoid_: Metadata present

**Jurisdiction Tax Treatment**:
The default tax assumptions tied to prizes from a lottery jurisdiction.
_Avoid_: State tax rate

**Player Tax Profile**:
A player's optional override for federal, jurisdiction, and local tax assumptions used in after-tax EV.
_Avoid_: Global tax setting

**Single-Ticket Recommendation**:
A recommendation that selects the best one ticket or play option within a budget rather than allocating the entire budget across multiple tickets.
_Avoid_: Portfolio recommendation

## Relationships

- A **Lottery Jurisdiction** offers zero or more **Game Offerings**.
- A **Lottery Jurisdiction** has one **Verified Catalog**.
- A **Lottery Jurisdiction** has one default **Jurisdiction Tax Treatment**.
- A **Known Draw Game** may become a supported **Game Offering** once its rules and sources are verified.
- A **Known Draw Game** has one or more **Support Statuses**.
- A **Game Offering** references exactly one **Draw Game**.
- A **Game Offering** uses exactly one **Game Rules Version**.
- A **Game Offering** must pass **Rule Verification** before it is EV supported.
- A **Game Offering** has one or more **Results Sources** when fetch support is available.
- A ledger entry records a ticket for exactly one **Game Offering**.
- A ledger entry should preserve the **Game Rules Version** that applied when the ticket was purchased or drawn.
- A **Results Adapter** parses one family of **Results Sources**.
- A **Results Adapter** produces **Structured Draw Results**.
- A **Structured Draw Result** belongs to exactly one **Draw Event**.
- A **Structured Draw Result** should reference the active **Game Rules Version** when it can be resolved.
- **Game Rules** may contain **Fixed Prize Rules** and may require a **Variable Prize Estimate** for current EV analysis.
- A **Game Rules Version** has exactly one **Number Format**.
- A **Game Rules Version** may define one or more **Game Add-Ons**.
- A **Player Tax Profile** may override **Jurisdiction Tax Treatment** for after-tax EV.
- A **Draw Game** has one or more wager options.
- A **Draw Game** produces repeated official drawing results.
- Ranking and recommendation compare **Game Offerings** within one **Lottery Jurisdiction** unless cross-jurisdiction comparison is explicitly requested.
- A **Single-Ticket Recommendation** chooses one **Game Offering** and wager option within the requested budget.
- Cross-jurisdiction output compares **Game Offerings** but does not imply purchase availability for the player.

## Example dialogue

> **Dev:** "Should we include scratchers when adding other states?"
> **Domain expert:** "No, this expansion is only for **Draw Games**."
> **Dev:** "Should we call Washington a state in the model?"
> **Domain expert:** "No, use **Lottery Jurisdiction** so DC, Puerto Rico, and other non-state authorities fit too."
> **Dev:** "Should every jurisdiction get its own Powerball rules?"
> **Domain expert:** "No, Powerball uses shared **Game Rules**, while each jurisdiction has its own **Game Offering**."
> **Dev:** "Can California Daily 3 reuse Washington Pick 3 because the names are similar?"
> **Domain expert:** "Only if they share the same **Game Rules Version**; similar names are not enough."
> **Dev:** "Can quick picks keep branching on game slug?"
> **Domain expert:** "No, quick picks should come from the **Number Format**."
> **Dev:** "Should a Washington user see Florida games in the default recommendation?"
> **Domain expert:** "No, recommendations default to one **Lottery Jurisdiction** unless cross-jurisdiction comparison is explicitly requested."
> **Dev:** "Should we hide California Daily 3 until it is implemented?"
> **Domain expert:** "No, record it as a **Known Draw Game** so coverage gaps are explicit."
> **Dev:** "Can scraped game-list pages decide coverage automatically?"
> **Domain expert:** "No, discovery can suggest entries, but the **Verified Catalog** is authoritative."
> **Dev:** "Is a game supported if we only know its name?"
> **Domain expert:** "No, that is cataloged; full initial support means EV and fetch support."
> **Dev:** "Can one parser fetch every jurisdiction?"
> **Domain expert:** "No, each source family needs a **Results Adapter** that reads its official **Results Source**."
> **Dev:** "Can Powerball EV use a jackpot value reviewed last month?"
> **Domain expert:** "Only as stale metadata; current EV needs a **Variable Prize Estimate**."
> **Dev:** "Can we enable EV if we know the ticket cost but not every prize tier?"
> **Domain expert:** "No, **Rule Verification** must pass before EV support is enabled."
> **Dev:** "Can one global state tax rate work for every recommendation?"
> **Domain expert:** "No, start with **Jurisdiction Tax Treatment** and allow a **Player Tax Profile** override."
> **Dev:** "Is a ledger ticket for Pick 3 enough if we add California and Washington?"
> **Domain expert:** "No, a ledger ticket must identify the specific **Game Offering**."
> **Dev:** "Can old ledger entries always use today's rules?"
> **Domain expert:** "No, a ledger entry should preserve the applicable **Game Rules Version**."
> **Dev:** "Can audits parse winning numbers from display strings?"
> **Domain expert:** "No, adapters should produce **Structured Draw Results** while preserving the original display text."
> **Dev:** "Can a historical draw be stored if we cannot resolve its old rules version?"
> **Domain expert:** "Yes, but its **Game Rules Version** should be unresolved until backfilled."
> **Dev:** "Is the draw date enough to identify a Pick 3 result?"
> **Domain expert:** "No, use a **Draw Event** because some games have multiple sessions per date."
> **Dev:** "Can Power Play be a note outside the rules?"
> **Domain expert:** "No, a **Game Add-On** can change cost, prize treatment, odds, or draw participation."
> **Dev:** "Should recommendation spend the whole budget across multiple tickets?"
> **Domain expert:** "No, the current command gives a **Single-Ticket Recommendation**."
> **Dev:** "Can cross-jurisdiction ranking tell a Washington player to buy a California ticket?"
> **Domain expert:** "No, it compares offerings but does not imply purchase availability."

## Flagged ambiguities

- "every game" was used broadly; resolved: it means every supported **Draw Game**, not scratchers, instant tickets, raffles, second-chance promotions, or online-only instant products.
- "state" was used for expansion scope; resolved: use **Lottery Jurisdiction** because the supported lottery authorities are not always U.S. states.
- "best game" was ambiguous across jurisdictions; resolved: default rankings and recommendations are jurisdiction-scoped.
- "unsupported game" was too vague; resolved: use **Known Draw Game** for a jurisdiction draw game that has been identified but is not fully supported yet.
- "catalog" was ambiguous; resolved: **Verified Catalog** is human-reviewed and authoritative even if discovery tooling suggests entries.
- "supported" was ambiguous; resolved: use **Support Status** rather than a single boolean, with EV and fetch support as the first completeness target.
- "source URL" was too implementation-shaped; resolved: use **Results Source** for official draw-result publications and **Results Adapter** for source-specific parsing.
- "prize table" was ambiguous; resolved: distinguish **Fixed Prize Rules** from **Variable Prize Estimate**.
- "verified" was implicit; resolved: **Rule Verification** is the gate for EV support.
- "tax rate" was too broad; resolved: distinguish **Jurisdiction Tax Treatment** from **Player Tax Profile**.
- "winning number" was too presentation-focused; resolved: use **Structured Draw Result** for normalized parsed draw data.
- "draw date" was too weak as an identity; resolved: use **Draw Event** for date plus session or source draw identifier.
- "number selection" was too hardcoded; resolved: use **Number Format** for valid pick generation, validation, and display.
- "add-on" was underspecified; resolved: **Game Add-On** is part of a game rules version when it changes cost, prizes, odds, or draw participation.
- "recommendation" was ambiguous; resolved: the current recommendation workflow is a **Single-Ticket Recommendation**.
- "cross-jurisdiction recommendation" was ambiguous; resolved: cross-jurisdiction output is comparison unless player purchase eligibility is explicitly modeled.
