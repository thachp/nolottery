import json

import pytest
from typer.testing import CliRunner

from nolottery.cli import app


runner = CliRunner()


def test_coverage_reports_washington_game_support_statuses(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "wa",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "wa"
    assert payload["jurisdiction"] == "Washington"
    cashpop = next(
        game for game in payload["games"] if game["game_slug"] == "cashpop"
    )
    assert cashpop["game"] == "Cash Pop"
    assert cashpop["results_adapter"] == "wa_past_drawings"
    assert cashpop["support_statuses"] == [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]


def test_coverage_reports_representative_catalog_jurisdictions(tmp_path):
    ev_supported = {
        "ny": {"numbers", "win-4"},
        "fl": {
            "florida-pick-2",
            "florida-pick-3",
            "florida-pick-4",
            "florida-pick-5",
        },
        "dc": set(),
    }
    expected = {
        "ny": (
            "New York",
            {
                "powerball",
                "new-york-lotto",
                "mega-millions",
                "millionaire-for-life",
                "numbers",
                "win-4",
                "take-5",
                "quick-draw",
                "pick-10",
            },
        ),
        "fl": (
            "Florida",
            {
                "florida-cash-pop",
                "florida-pick-2",
                "florida-pick-3",
                "florida-pick-4",
                "florida-pick-5",
                "florida-fantasy-5",
                "cash4life",
                "jackpot-triple-play",
                "florida-lotto",
                "mega-millions",
                "powerball",
            },
        ),
        "dc": (
            "District of Columbia",
            {
                "dc-3",
                "dc-4",
                "dc-5",
                "powerball",
                "mega-millions",
                "lotto-america",
                "millionaire-for-life",
                "dc-keno",
                "race2riches",
            },
        ),
    }

    for jurisdiction, (name, game_slugs) in expected.items():
        result = runner.invoke(
            app,
            [
                "--data-dir",
                str(tmp_path / jurisdiction),
                "coverage",
                "-j",
                jurisdiction,
                "--output",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["jurisdiction"] == name
        assert {game["game_slug"] for game in payload["games"]} == game_slugs
        catalog_only_games = (
            game
            for game in payload["games"]
            if game["game_slug"] not in ev_supported[jurisdiction]
        )
        assert all(
            game["support_statuses"] == ["cataloged"]
            for game in catalog_only_games
        )
        assert all(
            game["blocking_reason"] == "Rules and fetch adapter pending"
            for game in payload["games"]
            if game["game_slug"] not in ev_supported[jurisdiction]
        )


def test_coverage_reports_florida_and_new_york_ev_supported_games(tmp_path):
    expected = {
        "fl": {
            "florida-pick-2",
            "florida-pick-3",
            "florida-pick-4",
            "florida-pick-5",
        },
        "ny": {"numbers", "win-4"},
    }

    for jurisdiction, game_slugs in expected.items():
        result = runner.invoke(
            app,
            [
                "--data-dir",
                str(tmp_path / jurisdiction),
                "coverage",
                "-j",
                jurisdiction,
                "--output",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        for game_slug in game_slugs:
            game = next(
                game for game in payload["games"] if game["game_slug"] == game_slug
            )
            assert game["support_statuses"] == [
                "cataloged",
                "rules_verified",
                "ev_supported",
                "fetch_supported",
                "low_share_supported",
            ]
            assert game["blocking_reason"] == "Audit support pending"
            assert game["results_adapter"] in {
                "fl_pick_history_pdf",
                "ny_daily_numbers_socrata",
            }


@pytest.mark.parametrize(
    ("jurisdiction", "name"),
    [
        ("al", "Alabama"),
        ("hi", "Hawaii"),
    ],
)
def test_coverage_reports_state_without_lottery_as_supported_jurisdiction(
    tmp_path,
    jurisdiction,
    name,
):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            jurisdiction,
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == jurisdiction
    assert payload["jurisdiction"] == name
    assert payload["jurisdiction_support_statuses"] == ["no_state_lottery"]
    assert payload["blocking_reason"] == "No state lottery established"
    assert payload["games"] == []


def test_coverage_reports_pending_state_catalog_as_supported_jurisdiction(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "mt",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "mt"
    assert payload["jurisdiction"] == "Montana"
    assert payload["jurisdiction_support_statuses"] == ["catalog_pending"]
    assert payload["blocking_reason"] == "Lottery jurisdiction offering catalog pending"
    assert payload["games"] == []


def test_coverage_reports_connecticut_catalog_and_supported_national_games(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "ct",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "ct"
    assert payload["jurisdiction"] == "Connecticut"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "connecticut-cash5",
        "connecticut-keno",
        "connecticut-lotto",
        "connecticut-play3-day",
        "connecticut-play3-night",
        "connecticut-play4-day",
        "connecticut-play4-night",
        "mega-millions",
        "millionaire-for-life",
        "powerball",
    }
    assert games["powerball"]["support_statuses"] == [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert games["mega-millions"]["results_adapter"] == "ct_winning_numbers_ajax"
    assert games["connecticut-lotto"]["support_statuses"] == ["cataloged"]
    assert games["connecticut-lotto"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_delaware_catalog_and_supported_national_games(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "de",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "de"
    assert payload["jurisdiction"] == "Delaware"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "delaware-keno",
        "delaware-multi-win-lotto",
        "delaware-play-3",
        "delaware-play-4",
        "delaware-play-5",
        "lotto-america",
        "lucky-for-life",
        "mega-millions",
        "powerball",
    }
    assert games["powerball"]["support_statuses"] == [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert games["mega-millions"]["results_adapter"] == "de_search_winners"
    assert games["delaware-play-3"]["support_statuses"] == ["cataloged"]
    assert games["delaware-play-3"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_georgia_catalog_and_supported_national_games(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "ga",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "ga"
    assert payload["jurisdiction"] == "Georgia"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "cash4life",
        "georgia-all-or-nothing",
        "georgia-cash-3",
        "georgia-cash-4",
        "georgia-cash-pop",
        "georgia-five",
        "georgia-jumbo-bucks-lotto",
        "georgia-keno",
        "georgia-fantasy-5",
        "mega-millions",
        "millionaire-for-life",
        "powerball",
    }
    assert games["powerball"]["support_statuses"] == [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert games["mega-millions"]["results_adapter"] == "ga_draw_games_json"
    assert games["georgia-cash-3"]["support_statuses"] == ["cataloged"]
    assert games["georgia-cash-3"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_idaho_catalog_and_supported_national_games(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "id",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "id"
    assert payload["jurisdiction"] == "Idaho"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "idaho-cash",
        "idaho-pick-3",
        "idaho-pick-4",
        "lotto-america",
        "lucky-for-life",
        "mega-millions",
        "millionaire-for-life",
        "powerball",
    }
    assert games["powerball"]["support_statuses"] == [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert games["mega-millions"]["results_adapter"] == "id_draw_page"
    assert games["idaho-cash"]["support_statuses"] == ["cataloged"]
    assert games["idaho-cash"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_illinois_catalog_and_supported_national_games(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "il",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "il"
    assert payload["jurisdiction"] == "Illinois"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "illinois-hotwins",
        "illinois-lotto",
        "illinois-lucky-day-lotto",
        "illinois-pick-3",
        "illinois-pick-4",
        "mega-millions",
        "powerball",
    }
    assert games["powerball"]["support_statuses"] == [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert games["mega-millions"]["results_adapter"] == "il_results_page"
    assert games["illinois-lotto"]["support_statuses"] == ["cataloged"]
    assert games["illinois-lotto"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_indiana_catalog_and_supported_national_games(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "in",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "in"
    assert payload["jurisdiction"] == "Indiana"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "indiana-cash-5",
        "indiana-cash-pop",
        "indiana-daily-3",
        "indiana-daily-4",
        "indiana-hoosier-lotto",
        "indiana-quick-draw",
        "mega-millions",
        "millionaire-for-life",
        "powerball",
    }
    assert games["powerball"]["support_statuses"] == [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert games["mega-millions"]["results_adapter"] == "in_draw_page"
    assert games["indiana-cash-5"]["support_statuses"] == ["cataloged"]
    assert games["indiana-cash-5"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_iowa_catalog_and_supported_national_games(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "ia",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "ia"
    assert payload["jurisdiction"] == "Iowa"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "iowa-pick-3",
        "iowa-pick-4",
        "lotto-america",
        "mega-millions",
        "millionaire-for-life",
        "powerball",
    }
    assert games["powerball"]["support_statuses"] == [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert games["mega-millions"]["results_adapter"] == "ia_winning_numbers_page"
    assert games["iowa-pick-3"]["support_statuses"] == ["cataloged"]
    assert games["iowa-pick-3"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_kansas_catalog_with_result_source_blockers(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "ks",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "ks"
    assert payload["jurisdiction"] == "Kansas"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "kansas-2by2",
        "kansas-keno",
        "kansas-pick-3",
        "kansas-racetrax",
        "kansas-super-kansas-cash",
        "lotto-america",
        "mega-millions",
        "millionaire-for-life",
        "powerball",
    }
    assert games["powerball"]["support_statuses"] == ["cataloged"]
    assert games["powerball"]["blocking_reason"] == (
        "Official public result history source pending"
    )
    assert games["kansas-super-kansas-cash"]["support_statuses"] == ["cataloged"]


def test_coverage_reports_kentucky_catalog_and_supported_national_games(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "ky",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "ky"
    assert payload["jurisdiction"] == "Kentucky"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "kentucky-cash-ball",
        "kentucky-cash-pop",
        "kentucky-keno",
        "kentucky-pick-3",
        "kentucky-pick-4",
        "lucky-for-life",
        "mega-millions",
        "millionaire-for-life",
        "powerball",
    }
    assert games["powerball"]["support_statuses"] == [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert games["mega-millions"]["results_adapter"] == "ky_winning_numbers_json"
    assert games["kentucky-cash-ball"]["support_statuses"] == ["cataloged"]
    assert games["kentucky-cash-ball"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_louisiana_catalog_and_supported_national_games(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "la",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "la"
    assert payload["jurisdiction"] == "Louisiana"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "louisiana-easy-5",
        "louisiana-lotto",
        "louisiana-pick-3",
        "louisiana-pick-4",
        "louisiana-pick-5",
        "mega-millions",
        "powerball",
    }
    assert games["powerball"]["support_statuses"] == [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert games["mega-millions"]["results_adapter"] == "la_latest_draw_page"
    assert games["louisiana-lotto"]["support_statuses"] == ["cataloged"]
    assert games["louisiana-lotto"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_maines_catalog_and_supported_national_games(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "me",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "me"
    assert payload["jurisdiction"] == "Maine"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "lotto-america",
        "lucky-for-life",
        "maine-cash-pop",
        "maine-gimme-5",
        "maine-megabucks",
        "maine-pick-3",
        "maine-pick-4",
        "mega-millions",
        "millionaire-for-life",
        "powerball",
    }
    assert games["powerball"]["support_statuses"] == [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert games["mega-millions"]["results_adapter"] == "me_home_page"
    assert games["maine-megabucks"]["support_statuses"] == ["cataloged"]
    assert games["maine-megabucks"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_maryland_catalog_and_supported_national_games(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "md",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "md"
    assert payload["jurisdiction"] == "Maryland"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "cash4life",
        "maryland-bonus-match-5",
        "maryland-cash-pop",
        "maryland-keno",
        "maryland-multi-match",
        "maryland-pick-3",
        "maryland-pick-4",
        "maryland-pick-5",
        "maryland-racetrax",
        "mega-millions",
        "powerball",
    }
    assert games["powerball"]["support_statuses"] == [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert games["mega-millions"]["results_adapter"] == "md_winning_numbers_page"
    assert games["maryland-bonus-match-5"]["support_statuses"] == ["cataloged"]
    assert games["maryland-bonus-match-5"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_massachusetts_catalog_and_supported_national_games(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "ma",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "ma"
    assert payload["jurisdiction"] == "Massachusetts"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "lucky-for-life",
        "massachusetts-keno",
        "massachusetts-mass-cash",
        "massachusetts-megabucks",
        "massachusetts-numbers-game",
        "massachusetts-wheel-of-luck",
        "mega-millions",
        "millionaire-for-life",
        "powerball",
    }
    assert games["powerball"]["support_statuses"] == [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert games["mega-millions"]["results_adapter"] == "ma_draw_results_json"
    assert games["massachusetts-mass-cash"]["support_statuses"] == ["cataloged"]
    assert games["massachusetts-mass-cash"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_michigan_catalog_and_supported_national_games(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "mi",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "mi"
    assert payload["jurisdiction"] == "Michigan"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "lucky-for-life",
        "mega-millions",
        "michigan-cash-pop",
        "michigan-club-keno",
        "michigan-daily-3",
        "michigan-daily-4",
        "michigan-fantasy-5",
        "michigan-keno",
        "michigan-lotto-47",
        "michigan-poker-lotto",
        "millionaire-for-life",
        "powerball",
    }
    assert games["powerball"]["support_statuses"] == [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert games["mega-millions"]["results_adapter"] == "mi_graphql_draw_history"
    assert games["michigan-lotto-47"]["support_statuses"] == ["cataloged"]
    assert games["michigan-lotto-47"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_minnesota_catalog_and_supported_national_games(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "mn",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "mn"
    assert payload["jurisdiction"] == "Minnesota"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "lotto-america",
        "mega-millions",
        "minnesota-gopher-5",
        "minnesota-north-5",
        "minnesota-pick-3",
        "powerball",
    }
    assert games["powerball"]["support_statuses"] == [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert games["mega-millions"]["results_adapter"] == "mn_winning_numbers_page"
    assert games["minnesota-gopher-5"]["support_statuses"] == ["cataloged"]
    assert games["minnesota-gopher-5"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_mississippi_catalog_and_supported_national_games(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "ms",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "ms"
    assert payload["jurisdiction"] == "Mississippi"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "lotto-america",
        "mega-millions",
        "millionaire-for-life",
        "mississippi-cash-3",
        "mississippi-cash-4",
        "mississippi-cash-pop",
        "mississippi-match-5",
        "powerball",
    }
    assert games["powerball"]["support_statuses"] == [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert games["mega-millions"]["results_adapter"] == "ms_home_page"
    assert games["mississippi-match-5"]["support_statuses"] == ["cataloged"]
    assert games["mississippi-match-5"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_missouri_catalog_and_supported_national_games(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "mo",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "mo"
    assert payload["jurisdiction"] == "Missouri"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "cash4life",
        "mega-millions",
        "missouri-cash-pop",
        "missouri-lotto",
        "missouri-millions",
        "missouri-pick-3",
        "missouri-pick-4",
        "missouri-show-me-cash",
        "powerball",
    }
    assert games["powerball"]["support_statuses"] == [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert games["mega-millions"]["results_adapter"] == "mo_winning_numbers_page"
    assert games["missouri-show-me-cash"]["support_statuses"] == ["cataloged"]
    assert games["missouri-show-me-cash"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_colorado_catalog_and_supported_national_games(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "co",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "co"
    assert payload["jurisdiction"] == "Colorado"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "colorado-cash-5",
        "colorado-lotto-plus",
        "colorado-pick-3",
        "mega-millions",
        "millionaire-for-life",
        "powerball",
    }
    assert games["powerball"]["support_statuses"] == [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert games["mega-millions"]["results_adapter"] == "co_drawing_history"
    assert games["colorado-lotto-plus"]["support_statuses"] == ["cataloged"]
    assert games["colorado-lotto-plus"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_arkansas_catalog_and_supported_national_games(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "ar",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "ar"
    assert payload["jurisdiction"] == "Arkansas"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "arkansas-cash-3",
        "arkansas-cash-4",
        "arkansas-lotto",
        "arkansas-natural-state-jackpot",
        "lucky-for-life",
        "mega-millions",
        "millionaire-for-life",
        "powerball",
    }
    assert games["powerball"]["support_statuses"] == [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert games["mega-millions"]["results_adapter"] == "ar_did_i_win_date"
    assert games["arkansas-lotto"]["support_statuses"] == ["cataloged"]
    assert games["arkansas-lotto"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_arizona_catalog_and_backfill_supported_national_games(
    tmp_path,
):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "az",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "az"
    assert payload["jurisdiction"] == "Arizona"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "arizona-fantasy-5",
        "arizona-pick-3",
        "arizona-the-pick",
        "arizona-triple-twist",
        "mega-millions",
        "powerball",
    }
    assert games["powerball"]["support_statuses"] == [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert games["mega-millions"]["results_adapter"] == "az_past_180_pdf"
    assert games["arizona-the-pick"]["support_statuses"] == ["cataloged"]
    assert games["arizona-the-pick"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_texas_backfill_supported_national_games(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "tx",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "tx"
    assert payload["jurisdiction"] == "Texas"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {"mega-millions", "powerball"}
    assert all(
        game["support_statuses"]
        == [
            "cataloged",
            "rules_verified",
            "ev_supported",
            "fetch_supported",
            "audit_supported",
            "low_share_supported",
        ]
        for game in games.values()
    )
    assert all(
        game["results_adapter"] == "tx_winning_numbers"
        for game in games.values()
    )
