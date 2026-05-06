from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PrizeTier:
    label: str
    probability: float
    prize: float


@dataclass(frozen=True)
class WagerOption:
    slug: str
    label: str
    ticket_cost: float
    prize_tiers: tuple[PrizeTier, ...]


@dataclass(frozen=True)
class GameMetadata:
    slug: str
    name: str
    source_url: str
    reviewed_on: str
    wager_options: tuple[WagerOption, ...]


def _past_drawings_url(game_name: str) -> str:
    return (
        "https://www.walottery.com/WinningNumbers/PastDrawings.aspx?"
        f"gamename={game_name}&unitcount=180&unittype=day"
    )


def _cashpop_options() -> tuple[WagerOption, ...]:
    base_tiers = (
        PrizeTier("$500", 1 / 7_500, 500),
        PrizeTier("$250", 1 / 4_500, 250),
        PrizeTier("$200", 1 / 2_630, 200),
        PrizeTier("$125", 1 / 675, 125),
        PrizeTier("$100", 1 / 150, 100),
        PrizeTier("$70", 1 / 120, 70),
        PrizeTier("$50", 1 / 90, 50),
        PrizeTier("$35", 1 / 75, 35),
        PrizeTier("$25", 1 / 40, 25),
    )
    return tuple(
        WagerOption(
            slug="one-pop" if count == 1 else f"{count}-pop",
            label=f"{count} POP{'s' if count != 1 else ''}",
            ticket_cost=count * 5.0,
            prize_tiers=tuple(
                PrizeTier(tier.label, tier.probability * count, tier.prize)
                for tier in base_tiers
            ),
        )
        for count in range(1, 16)
    )


def _multiplied_mega_millions_tiers(
    label: str,
    outcome_probability: float,
    prizes_by_multiplier: tuple[tuple[str, float], ...],
) -> tuple[PrizeTier, ...]:
    multiplier_probabilities = {
        "10X": 5 / 160,
        "5X": 10 / 160,
        "4X": 20 / 160,
        "3X": 50 / 160,
        "2X": 75 / 160,
    }
    return tuple(
        PrizeTier(
            f"{label} {multiplier}",
            outcome_probability * multiplier_probabilities[multiplier],
            prize,
        )
        for multiplier, prize in prizes_by_multiplier
    )


DEFAULT_GAMES: dict[str, GameMetadata] = {
    "powerball": GameMetadata(
        slug="powerball",
        name="Powerball",
        source_url=_past_drawings_url("powerball"),
        reviewed_on="2026-05-05",
        wager_options=(
            WagerOption(
                slug="standard",
                label="Standard $2",
                ticket_cost=2.0,
                prize_tiers=(
                    PrizeTier("5 White + Powerball", 1 / 292_000_000, 13_500_000),
                    PrizeTier("5 White", 1 / 11_700_000, 1_000_000),
                    PrizeTier("4 White + Powerball", 1 / 913_000, 50_000),
                    PrizeTier("4 White", 1 / 36_500, 100),
                    PrizeTier("3 White + Powerball", 1 / 14_500, 100),
                    PrizeTier("3 White", 1 / 580, 7),
                    PrizeTier("2 White + Powerball", 1 / 701, 7),
                    PrizeTier("1 White + Powerball", 1 / 92.0, 4),
                    PrizeTier("Powerball", 1 / 38.3, 4),
                ),
            ),
        ),
    ),
    "mega-millions": GameMetadata(
        slug="mega-millions",
        name="Mega Millions",
        source_url=_past_drawings_url("megamillions"),
        reviewed_on="2026-05-05",
        wager_options=(
            WagerOption(
                slug="standard",
                label="Standard $5",
                ticket_cost=5.0,
                prize_tiers=(
                    PrizeTier("5 White + Mega Ball", 1 / 290_000_000, 86_300_000),
                    *_multiplied_mega_millions_tiers(
                        "5 White",
                        1 / 12_600_000,
                        (
                            ("10X", 10_000_000),
                            ("5X", 5_000_000),
                            ("4X", 4_000_000),
                            ("3X", 3_000_000),
                            ("2X", 2_000_000),
                        ),
                    ),
                    *_multiplied_mega_millions_tiers(
                        "4 White + Mega Ball",
                        1 / 894_000,
                        (
                            ("10X", 100_000),
                            ("5X", 50_000),
                            ("4X", 40_000),
                            ("3X", 30_000),
                            ("2X", 20_000),
                        ),
                    ),
                    *_multiplied_mega_millions_tiers(
                        "4 White",
                        1 / 38_900,
                        (
                            ("10X", 5_000),
                            ("5X", 2_500),
                            ("4X", 2_000),
                            ("3X", 1_500),
                            ("2X", 1_000),
                        ),
                    ),
                    *_multiplied_mega_millions_tiers(
                        "3 White + Mega Ball",
                        1 / 14_000,
                        (
                            ("10X", 2_000),
                            ("5X", 1_000),
                            ("4X", 800),
                            ("3X", 600),
                            ("2X", 400),
                        ),
                    ),
                    *_multiplied_mega_millions_tiers(
                        "3 White",
                        1 / 607,
                        (
                            ("10X", 100),
                            ("5X", 50),
                            ("4X", 40),
                            ("3X", 30),
                            ("2X", 20),
                        ),
                    ),
                    *_multiplied_mega_millions_tiers(
                        "2 White + Mega Ball",
                        1 / 665,
                        (
                            ("10X", 100),
                            ("5X", 50),
                            ("4X", 40),
                            ("3X", 30),
                            ("2X", 20),
                        ),
                    ),
                    *_multiplied_mega_millions_tiers(
                        "1 White + Mega Ball",
                        1 / 86.0,
                        (
                            ("10X", 70),
                            ("5X", 35),
                            ("4X", 28),
                            ("3X", 21),
                            ("2X", 14),
                        ),
                    ),
                    *_multiplied_mega_millions_tiers(
                        "Mega Ball",
                        1 / 35.0,
                        (
                            ("10X", 50),
                            ("5X", 25),
                            ("4X", 20),
                            ("3X", 15),
                            ("2X", 10),
                        ),
                    ),
                ),
            ),
        ),
    ),
    "lotto": GameMetadata(
        slug="lotto",
        name="Lotto",
        source_url=_past_drawings_url("lotto"),
        reviewed_on="2026-05-05",
        wager_options=(
            WagerOption(
                slug="two-plays",
                label="Two Plays $1",
                ticket_cost=1.0,
                prize_tiers=(
                    PrizeTier("6 White", 2 / 6_990_000, 550_000),
                    PrizeTier("5 White", 2 / 27_100, 1_000),
                    PrizeTier("4 White", 2 / 516, 30),
                    PrizeTier("3 White", 2 / 28.3, 3),
                ),
            ),
        ),
    ),
    "hit-5": GameMetadata(
        slug="hit-5",
        name="Hit 5",
        source_url=_past_drawings_url("hit5"),
        reviewed_on="2026-05-05",
        wager_options=(
            WagerOption(
                slug="standard",
                label="Standard $1",
                ticket_cost=1.0,
                prize_tiers=(
                    PrizeTier("5 White", 1 / 851_000, 115_000),
                    PrizeTier("4 White", 1 / 4_600, 150),
                    PrizeTier("3 White", 1 / 128, 15),
                    PrizeTier("2 White", 1 / 11.0, 1),
                ),
            ),
        ),
    ),
    "match-4": GameMetadata(
        slug="match-4",
        name="Match 4",
        source_url=_past_drawings_url("match4"),
        reviewed_on="2026-05-05",
        wager_options=(
            WagerOption(
                slug="standard",
                label="Standard $2",
                ticket_cost=2.0,
                prize_tiers=(
                    PrizeTier("4 White", 1 / 10_600, 10_000),
                    PrizeTier("3 White", 1 / 133, 20),
                    PrizeTier("2 White", 1 / 9.32, 2),
                ),
            ),
        ),
    ),
    "pick-3": GameMetadata(
        slug="pick-3",
        name="Pick 3",
        source_url=_past_drawings_url("pick3"),
        reviewed_on="2026-05-05",
        wager_options=(
            WagerOption(
                slug="straight-50c",
                label="Straight $0.50",
                ticket_cost=0.5,
                prize_tiers=(PrizeTier("Straight", 1 / 1_000, 250),),
            ),
            WagerOption(
                slug="straight-1",
                label="Straight $1",
                ticket_cost=1.0,
                prize_tiers=(PrizeTier("Straight", 1 / 1_000, 500),),
            ),
            WagerOption(
                slug="box-6-way-50c",
                label="6-Way Box $0.50",
                ticket_cost=0.5,
                prize_tiers=(PrizeTier("6-Way Box", 1 / 167, 40),),
            ),
            WagerOption(
                slug="box-6-way-1",
                label="6-Way Box $1",
                ticket_cost=1.0,
                prize_tiers=(PrizeTier("6-Way Box", 1 / 167, 80),),
            ),
            WagerOption(
                slug="box-3-way-50c",
                label="3-Way Box $0.50",
                ticket_cost=0.5,
                prize_tiers=(PrizeTier("3-Way Box", 1 / 333, 80),),
            ),
            WagerOption(
                slug="box-3-way-1",
                label="3-Way Box $1",
                ticket_cost=1.0,
                prize_tiers=(PrizeTier("3-Way Box", 1 / 333, 160),),
            ),
            WagerOption(
                slug="straight-box-6-way",
                label="6-Way Straight/Box $1",
                ticket_cost=1.0,
                prize_tiers=(
                    PrizeTier("Straight", 1 / 1_000, 290),
                    PrizeTier("Box", 5 / 1_000, 40),
                ),
            ),
            WagerOption(
                slug="straight-box-3-way",
                label="3-Way Straight/Box $1",
                ticket_cost=1.0,
                prize_tiers=(
                    PrizeTier("Straight", 1 / 1_000, 330),
                    PrizeTier("Box", 2 / 1_000, 80),
                ),
            ),
            WagerOption(
                slug="front-pair-50c",
                label="Front Pair $0.50",
                ticket_cost=0.5,
                prize_tiers=(PrizeTier("Front Pair", 1 / 100, 25),),
            ),
            WagerOption(
                slug="front-pair-1",
                label="Front Pair $1",
                ticket_cost=1.0,
                prize_tiers=(PrizeTier("Front Pair", 1 / 100, 50),),
            ),
            WagerOption(
                slug="back-pair-50c",
                label="Back Pair $0.50",
                ticket_cost=0.5,
                prize_tiers=(PrizeTier("Back Pair", 1 / 100, 25),),
            ),
            WagerOption(
                slug="back-pair-1",
                label="Back Pair $1",
                ticket_cost=1.0,
                prize_tiers=(PrizeTier("Back Pair", 1 / 100, 50),),
            ),
            WagerOption(
                slug="superbox-6-way-3",
                label="6-Way Superbox $3",
                ticket_cost=3.0,
                prize_tiers=(PrizeTier("6-Way Superbox", 1 / 167, 250),),
            ),
            WagerOption(
                slug="superbox-6-way-6",
                label="6-Way Superbox $6",
                ticket_cost=6.0,
                prize_tiers=(PrizeTier("6-Way Superbox", 1 / 167, 500),),
            ),
            WagerOption(
                slug="superbox-3-way-150c",
                label="3-Way Superbox $1.50",
                ticket_cost=1.5,
                prize_tiers=(PrizeTier("3-Way Superbox", 1 / 333, 250),),
            ),
            WagerOption(
                slug="superbox-3-way-3",
                label="3-Way Superbox $3",
                ticket_cost=3.0,
                prize_tiers=(PrizeTier("3-Way Superbox", 1 / 333, 500),),
            ),
        ),
    ),
    "cashpop": GameMetadata(
        slug="cashpop",
        name="Cash Pop",
        source_url=_past_drawings_url("cashpop"),
        reviewed_on="2026-05-05",
        wager_options=_cashpop_options(),
    ),
    "daily-keno": GameMetadata(
        slug="daily-keno",
        name="Daily Keno",
        source_url=_past_drawings_url("dailykeno"),
        reviewed_on="2026-05-05",
        wager_options=(
            WagerOption(
                slug="10-spot",
                label="10-Spot $1",
                ticket_cost=1.0,
                prize_tiers=(
                    PrizeTier("Match 10", 1 / 8_910_000, 100_000),
                    PrizeTier("Match 9", 1 / 163_000, 5_000),
                    PrizeTier("Match 8", 1 / 7_380, 500),
                    PrizeTier("Match 7", 1 / 621, 50),
                    PrizeTier("Match 6", 1 / 87.1, 5),
                    PrizeTier("Match 5", 1 / 19.4, 2),
                    PrizeTier("Match 0", 1 / 21.8, 3),
                ),
            ),
            WagerOption(
                slug="9-spot",
                label="9-Spot $1",
                ticket_cost=1.0,
                prize_tiers=(
                    PrizeTier("Match 9", 1 / 1_380_000, 25_000),
                    PrizeTier("Match 8", 1 / 30_700, 2_500),
                    PrizeTier("Match 7", 1 / 1_690, 100),
                    PrizeTier("Match 6", 1 / 175, 10),
                    PrizeTier("Match 5", 1 / 30.7, 5),
                    PrizeTier("Match 4", 1 / 8.76, 1),
                ),
            ),
            WagerOption(
                slug="8-spot",
                label="8-Spot $1",
                ticket_cost=1.0,
                prize_tiers=(
                    PrizeTier("Match 8", 1 / 230_000, 10_000),
                    PrizeTier("Match 7", 1 / 6_230, 500),
                    PrizeTier("Match 6", 1 / 423, 50),
                    PrizeTier("Match 5", 1 / 54.6, 5),
                    PrizeTier("Match 4", 1 / 12.3, 2),
                ),
            ),
            WagerOption(
                slug="7-spot",
                label="7-Spot $1",
                ticket_cost=1.0,
                prize_tiers=(
                    PrizeTier("Match 7", 1 / 41_000, 2_500),
                    PrizeTier("Match 6", 1 / 1_370, 100),
                    PrizeTier("Match 5", 1 / 116, 10),
                    PrizeTier("Match 4", 1 / 19.2, 2),
                    PrizeTier("Match 3", 1 / 5.70, 1),
                ),
            ),
            WagerOption(
                slug="6-spot",
                label="6-Spot $1",
                ticket_cost=1.0,
                prize_tiers=(
                    PrizeTier("Match 6", 1 / 7_750, 1_000),
                    PrizeTier("Match 5", 1 / 323, 40),
                    PrizeTier("Match 4", 1 / 35.0, 4),
                    PrizeTier("Match 3", 1 / 7.70, 1),
                ),
            ),
            WagerOption(
                slug="5-spot",
                label="5-Spot $1",
                ticket_cost=1.0,
                prize_tiers=(
                    PrizeTier("Match 5", 1 / 1_550, 200),
                    PrizeTier("Match 4", 1 / 82.7, 17),
                    PrizeTier("Match 3", 1 / 11.9, 2),
                ),
            ),
            WagerOption(
                slug="4-spot",
                label="4-Spot $1",
                ticket_cost=1.0,
                prize_tiers=(
                    PrizeTier("Match 4", 1 / 326, 24),
                    PrizeTier("Match 3", 1 / 23.1, 5),
                    PrizeTier("Match 2", 1 / 4.70, 1),
                ),
            ),
            WagerOption(
                slug="3-spot",
                label="3-Spot $1",
                ticket_cost=1.0,
                prize_tiers=(
                    PrizeTier("Match 3", 1 / 72.0, 16),
                    PrizeTier("Match 2", 1 / 7.21, 2),
                ),
            ),
            WagerOption(
                slug="2-spot",
                label="2-Spot $1",
                ticket_cost=1.0,
                prize_tiers=(PrizeTier("Match 2", 1 / 16.6, 8),),
            ),
            WagerOption(
                slug="1-spot",
                label="1-Spot $1",
                ticket_cost=1.0,
                prize_tiers=(PrizeTier("Match 1", 1 / 4.00, 2),),
            ),
        ),
    ),
}
