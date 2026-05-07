from nolottery.metadata import load_default_games, load_default_jurisdictions


def test_load_default_games_reads_bundled_metadata_files():
    games = load_default_games()

    assert tuple(games) == (
        "cashpop",
        "daily-3",
        "daily-keno",
        "hit-5",
        "lotto",
        "match-4",
        "mega-millions",
        "pick-3",
        "powerball",
    )
    assert games["cashpop"].name == "Cash Pop"
    assert games["cashpop"].wager_options[0].slug == "one-pop"
    assert games["daily-3"].name == "Daily 3"


def test_load_default_jurisdictions_reads_bundled_catalog():
    jurisdictions = load_default_jurisdictions()

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
