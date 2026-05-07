from nolottery import db
from nolottery.metadata import load_default_games, load_default_jurisdictions


US_STATE_CODES = {
    "al",
    "ak",
    "az",
    "ar",
    "ca",
    "co",
    "ct",
    "de",
    "fl",
    "ga",
    "hi",
    "id",
    "il",
    "in",
    "ia",
    "ks",
    "ky",
    "la",
    "me",
    "md",
    "ma",
    "mi",
    "mn",
    "ms",
    "mo",
    "mt",
    "ne",
    "nv",
    "nh",
    "nj",
    "nm",
    "ny",
    "nc",
    "nd",
    "oh",
    "ok",
    "or",
    "pa",
    "ri",
    "sc",
    "sd",
    "tn",
    "tx",
    "ut",
    "vt",
    "va",
    "wa",
    "wv",
    "wi",
    "wy",
}


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

    assert US_STATE_CODES.issubset(jurisdictions)
    assert "dc" in jurisdictions
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
    assert {
        offering["game_slug"] for offering in jurisdictions["ca"]["offerings"]
    } == {
        "powerball",
        "mega-millions",
        "superlotto-plus",
        "fantasy-5",
        "daily-4",
        "daily-3",
        "daily-derby",
        "hot-spot",
    }
    assert "new-york-lotto" in {
        offering["game_slug"] for offering in jurisdictions["ny"]["offerings"]
    }
    assert "florida-cash-pop" in {
        offering["game_slug"] for offering in jurisdictions["fl"]["offerings"]
    }
    assert "dc-keno" in {
        offering["game_slug"] for offering in jurisdictions["dc"]["offerings"]
    }


def test_remaining_state_catalog_marks_jurisdiction_level_blockers():
    jurisdictions = load_default_jurisdictions()

    assert jurisdictions["al"]["support_statuses"] == ("no_state_lottery",)
    assert jurisdictions["al"]["blocking_reason"] == "No state lottery established"
    assert jurisdictions["al"]["offerings"] == ()
    assert jurisdictions["hi"]["support_statuses"] == ("no_state_lottery",)
    assert jurisdictions["hi"]["blocking_reason"] == "No state lottery established"
    assert jurisdictions["hi"]["offerings"] == ()
    assert jurisdictions["nv"]["support_statuses"] == ("no_state_lottery",)
    assert jurisdictions["nv"]["blocking_reason"] == "No state lottery established"
    assert jurisdictions["nv"]["offerings"] == ()

    assert jurisdictions["sd"]["support_statuses"] == ("catalog_pending",)
    assert jurisdictions["sd"]["blocking_reason"] == (
        "Lottery jurisdiction offering catalog pending"
    )
    assert jurisdictions["sd"]["offerings"] == ()


def test_jurisdiction_offering_can_override_shared_game_results_source(tmp_path):
    conn = db.connect(tmp_path)

    washington_powerball = db.get_game(conn, "powerball", "wa")
    california_powerball = db.get_game(conn, "powerball", "ca")

    assert washington_powerball is not None
    assert california_powerball is not None
    assert washington_powerball.source_url.startswith("https://www.walottery.com/")
    assert (
        california_powerball.source_url
        == "https://www.calottery.com/en/draw-games/powerball"
    )
