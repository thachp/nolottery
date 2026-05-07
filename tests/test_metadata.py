from nolottery.metadata import load_default_games, load_default_jurisdictions


def test_load_default_games_reads_bundled_metadata_files():
    games = load_default_games()

    assert {
        "cashpop",
        "daily-3",
        "numbers",
        "florida-fantasy-5",
        "dc-3",
    }.issubset(games)
    assert games["cashpop"].name == "Cash Pop"
    assert games["cashpop"].wager_options[0].slug == "one-pop"
    assert games["daily-3"].name == "Daily 3"


def test_load_default_jurisdictions_reads_bundled_catalog():
    jurisdictions = load_default_jurisdictions()

    assert tuple(jurisdictions) == ("wa", "ca", "ny", "fl", "dc")
    assert jurisdictions["wa"]["name"] == "Washington"
    assert tuple(
        offering["game_slug"] for offering in jurisdictions["wa"]["offerings"]
    ) == (
        "powerball",
        "mega-millions",
        "lotto",
        "hit-5",
        "match-4",
        "pick-3",
        "cashpop",
        "daily-keno",
    )
    assert jurisdictions["ny"]["offerings"][0]["game_slug"] == "numbers"
    assert jurisdictions["fl"]["offerings"][0]["game_slug"] == "florida-fantasy-5"
    assert jurisdictions["dc"]["offerings"][0]["game_slug"] == "dc-3"
