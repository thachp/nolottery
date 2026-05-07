from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
import tomllib


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


def load_default_games() -> dict[str, GameMetadata]:
    raw_data = (
        resources.files(__package__)
        .joinpath("data", "washington-games.toml")
        .read_bytes()
    )
    payload = tomllib.loads(raw_data.decode("utf-8"))
    games = {
        game["slug"]: GameMetadata(
            slug=game["slug"],
            name=game["name"],
            source_url=game["source_url"],
            reviewed_on=game["reviewed_on"],
            wager_options=tuple(
                WagerOption(
                    slug=option["slug"],
                    label=option["label"],
                    ticket_cost=float(option["ticket_cost"]),
                    prize_tiers=tuple(
                        PrizeTier(
                            label=tier["label"],
                            probability=float(tier["probability"]),
                            prize=float(tier["prize"]),
                        )
                        for tier in option.get("prize_tiers", ())
                    ),
                )
                for option in game.get("wager_options", ())
            ),
        )
        for game in payload["games"]
    }
    return dict(sorted(games.items()))


def load_default_jurisdictions() -> dict[str, dict[str, object]]:
    raw_data = (
        resources.files(__package__)
        .joinpath("data", "jurisdictions.toml")
        .read_bytes()
    )
    payload = tomllib.loads(raw_data.decode("utf-8"))
    jurisdictions = {}
    for jurisdiction in payload["jurisdictions"]:
        jurisdictions[jurisdiction["code"]] = {
            "name": jurisdiction["name"],
            "offerings": tuple(
                offering["game_slug"]
                for offering in jurisdiction.get("offerings", ())
            ),
        }
    return jurisdictions



DEFAULT_GAMES: dict[str, GameMetadata] = load_default_games()
