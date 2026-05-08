import json

import pytest
from typer.testing import CliRunner

from nolottery.cli import app


runner = CliRunner()
FULL_SUPPORT_STATUSES = [
    "cataloged",
    "rules_verified",
    "ev_supported",
    "fetch_supported",
    "audit_supported",
    "low_share_supported",
]
NATIONAL_GAME_SLUGS = {"powerball", "mega-millions"}


def _assert_supported_national_games(games):
    for game_slug in NATIONAL_GAME_SLUGS:
        assert games[game_slug]["support_statuses"] == FULL_SUPPORT_STATUSES
        assert games[game_slug]["results_adapter"] == "official_national_results_page"


def _assert_cataloged_local_blockers(games):
    assert all(
        game["support_statuses"] == ["cataloged"]
        for game_slug, game in games.items()
        if game_slug not in NATIONAL_GAME_SLUGS
    )
    assert all(
        game["blocking_reason"] == "Rules and fetch adapter pending"
        for game_slug, game in games.items()
        if game_slug not in NATIONAL_GAME_SLUGS
    )


@pytest.mark.parametrize(
    "jurisdiction",
    ["oh", "ok", "or", "pa", "ri", "sc", "sd", "tn", "vt", "va", "wv", "wi", "wy"],
)
def test_coverage_reports_supported_national_games_for_remaining_states(
    tmp_path,
    jurisdiction,
):
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
    games = {game["game_slug"]: game for game in payload["games"]}
    _assert_supported_national_games(games)


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
        "ny": {
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
        "fl": {
            "cash4life",
            "florida-cash-pop",
            "florida-fantasy-5",
            "florida-lotto",
            "florida-pick-2",
            "florida-pick-3",
            "florida-pick-4",
            "florida-pick-5",
            "jackpot-triple-play",
            "mega-millions",
            "powerball",
        },
        "dc": {"powerball", "mega-millions", "lotto-america"},
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
        if jurisdiction != "dc":
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
        if jurisdiction == "dc":
            for game_slug in ev_supported[jurisdiction]:
                game = next(
                    game for game in payload["games"] if game["game_slug"] == game_slug
                )
                assert game["support_statuses"] == [
                    "cataloged",
                    "rules_verified",
                    "ev_supported",
                    "fetch_supported",
                    "audit_supported",
                    "low_share_supported",
                ]
                assert game["results_adapter"] == "dc_past_draw_numbers"


def test_coverage_reports_dc_past_drawing_capabilities(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "dc",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    games = {game["game_slug"]: game for game in payload["games"]}

    assert set(games) == {
        "dc-3",
        "dc-4",
        "dc-5",
        "powerball",
        "mega-millions",
        "lotto-america",
        "millionaire-for-life",
        "dc-keno",
        "race2riches",
    }
    for game in games.values():
        assert "fetch_supported" in game["support_statuses"]
        assert "audit_supported" in game["support_statuses"]
        assert game["results_adapter"] == "dc_past_draw_numbers"


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
            if jurisdiction == "fl":
                assert game["support_statuses"] == FULL_SUPPORT_STATUSES
                assert game["blocking_reason"] == ""
                assert game["results_adapter"] == "fl_history_pdf"
            else:
                assert game["support_statuses"] == FULL_SUPPORT_STATUSES
                assert game["blocking_reason"] == ""
                assert game["results_adapter"] == "ny_open_data_socrata"


def test_coverage_reports_new_york_past_drawing_capabilities(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "ny",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    games = {game["game_slug"]: game for game in payload["games"]}

    assert set(games) == {
        "powerball",
        "new-york-lotto",
        "mega-millions",
        "millionaire-for-life",
        "numbers",
        "win-4",
        "take-5",
        "quick-draw",
        "pick-10",
    }
    for game in games.values():
        assert "fetch_supported" in game["support_statuses"]
        assert "audit_supported" in game["support_statuses"]
        assert game["results_adapter"] == "ny_open_data_socrata"


def test_coverage_reports_florida_full_history_fetch_support(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "fl"),
            "coverage",
            "-j",
            "fl",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    games = {game["game_slug"]: game for game in payload["games"]}
    assert {
        game_slug
        for game_slug, game in games.items()
        if "fetch_supported" in game["support_statuses"]
    } == {
        "cash4life",
        "florida-cash-pop",
        "florida-fantasy-5",
        "florida-lotto",
        "florida-pick-2",
        "florida-pick-3",
        "florida-pick-4",
        "florida-pick-5",
        "jackpot-triple-play",
        "mega-millions",
        "powerball",
    }
    assert {
        games[game_slug]["results_adapter"]
        for game_slug in games
        if "fetch_supported" in games[game_slug]["support_statuses"]
    } == {"fl_history_pdf"}


@pytest.mark.parametrize(
    ("jurisdiction", "name"),
    [
        ("al", "Alabama"),
        ("hi", "Hawaii"),
        ("nv", "Nevada"),
        ("ut", "Utah"),
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


def test_coverage_has_no_remaining_state_catalog_pending_jurisdictions(tmp_path):
    for jurisdiction in (
        "az",
        "ar",
        "co",
        "ct",
        "de",
        "ga",
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
        "nh",
        "nj",
        "nm",
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
        "vt",
        "va",
        "wv",
        "wi",
        "wy",
    ):
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
        assert payload["jurisdiction_support_statuses"] != ["catalog_pending"]
        assert payload["games"]


def test_coverage_reports_wyoming_full_draw_game_catalog(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "wy",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "wy"
    assert payload["jurisdiction"] == "Wyoming"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "lucky-for-life",
        "mega-millions",
        "millionaire-for-life",
        "powerball",
        "wyoming-2by2",
        "wyoming-cowboy-draw",
        "wyoming-keno",
    }
    assert games["lucky-for-life"]["blocking_reason"] == (
        "Retired after February 2026; historical adapter pending"
    )
    assert games["wyoming-cowboy-draw"]["support_statuses"] == ["cataloged"]
    assert games["wyoming-cowboy-draw"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_wisconsin_full_draw_game_catalog(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "wi",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "wi"
    assert payload["jurisdiction"] == "Wisconsin"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "mega-millions",
        "powerball",
        "wisconsin-all-or-nothing",
        "wisconsin-badger-5",
        "wisconsin-megabucks",
        "wisconsin-pick-3",
        "wisconsin-pick-4",
        "wisconsin-supercash",
    }
    assert games["wisconsin-megabucks"]["support_statuses"] == ["cataloged"]
    assert games["wisconsin-megabucks"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_west_virginia_full_draw_game_catalog(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "wv",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "wv"
    assert payload["jurisdiction"] == "West Virginia"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "lotto-america",
        "mega-millions",
        "millionaire-for-life",
        "powerball",
        "west-virginia-cash-25",
        "west-virginia-cash-pop",
        "west-virginia-daily-3",
        "west-virginia-daily-4",
        "west-virginia-keno",
    }
    assert games["west-virginia-cash-25"]["support_statuses"] == ["cataloged"]
    assert games["west-virginia-cash-25"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_virginia_full_draw_game_catalog(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "va",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "va"
    assert payload["jurisdiction"] == "Virginia"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "cash4life",
        "mega-millions",
        "millionaire-for-life",
        "powerball",
        "virginia-bank-a-million",
        "virginia-cash-5",
        "virginia-cash-pop",
        "virginia-keno",
        "virginia-pick-3",
        "virginia-pick-4",
        "virginia-pick-5",
    }
    assert games["cash4life"]["blocking_reason"] == (
        "Retired after February 2026; historical adapter pending"
    )
    assert games["virginia-bank-a-million"]["support_statuses"] == ["cataloged"]
    assert games["virginia-bank-a-million"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_vermont_full_draw_game_catalog(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "vt",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "vt"
    assert payload["jurisdiction"] == "Vermont"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "lucky-for-life",
        "mega-millions",
        "millionaire-for-life",
        "powerball",
        "vermont-gimme-5",
        "vermont-megabucks",
        "vermont-pick-3",
        "vermont-pick-4",
    }
    assert games["lucky-for-life"]["blocking_reason"] == (
        "Retired after February 2026; historical adapter pending"
    )
    assert games["vermont-megabucks"]["support_statuses"] == ["cataloged"]
    assert games["vermont-megabucks"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_tennessee_full_draw_game_catalog(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "tn",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "tn"
    assert payload["jurisdiction"] == "Tennessee"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "cash4life",
        "lotto-america",
        "mega-millions",
        "millionaire-for-life",
        "powerball",
        "tennessee-cash",
        "tennessee-cash-3",
        "tennessee-cash-4",
        "tennessee-daily-jackpot",
        "tennessee-keno-to-go",
    }
    assert games["cash4life"]["blocking_reason"] == (
        "Retired after February 2026; historical adapter pending"
    )
    assert games["tennessee-cash"]["support_statuses"] == ["cataloged"]
    assert games["tennessee-cash"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_new_hampshire_full_draw_game_catalog(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "nh",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "nh"
    assert payload["jurisdiction"] == "New Hampshire"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "lucky-for-life",
        "mega-millions",
        "new-hampshire-gimme-5",
        "new-hampshire-keno-603",
        "new-hampshire-megabucks",
        "new-hampshire-pick-3",
        "new-hampshire-pick-4",
        "powerball",
    }
    assert all(
        game["blocking_reason"] == "Rules and fetch adapter pending"
        for game_slug, game in games.items()
        if game_slug not in {"powerball", "mega-millions"}
    )
    for game_slug in ("powerball", "mega-millions"):
        assert games[game_slug]["support_statuses"] == [
            "cataloged",
            "rules_verified",
            "ev_supported",
            "fetch_supported",
            "audit_supported",
            "low_share_supported",
        ]
        assert games[game_slug]["results_adapter"] == "official_national_results_page"
    assert all(
        game["support_statuses"] == ["cataloged"]
        for game_slug, game in games.items()
        if game_slug not in {"powerball", "mega-millions"}
    )


def test_coverage_reports_new_jersey_full_draw_game_catalog(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "nj",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "nj"
    assert payload["jurisdiction"] == "New Jersey"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "mega-millions",
        "millionaire-for-life",
        "new-jersey-cash-5",
        "new-jersey-cash-pop",
        "new-jersey-pick-3",
        "new-jersey-pick-4",
        "new-jersey-pick-6",
        "new-jersey-quick-draw",
        "powerball",
    }
    _assert_supported_national_games(games)
    _assert_cataloged_local_blockers(games)


def test_coverage_reports_new_mexico_full_draw_game_catalog(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "nm",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "nm"
    assert payload["jurisdiction"] == "New Mexico"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "lotto-america",
        "mega-millions",
        "new-mexico-pick-3-plus",
        "new-mexico-pick-4-plus",
        "new-mexico-roadrunner-cash",
        "powerball",
    }
    _assert_supported_national_games(games)
    _assert_cataloged_local_blockers(games)


def test_coverage_reports_north_carolina_full_draw_game_catalog(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "nc",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "nc"
    assert payload["jurisdiction"] == "North Carolina"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "mega-millions",
        "millionaire-for-life",
        "north-carolina-cash-5",
        "north-carolina-cash-pop",
        "north-carolina-pick-3",
        "north-carolina-pick-4",
        "powerball",
    }
    _assert_supported_national_games(games)
    _assert_cataloged_local_blockers(games)


def test_coverage_reports_north_dakota_full_draw_game_catalog(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "nd",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "nd"
    assert payload["jurisdiction"] == "North Dakota"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "lotto-america",
        "lucky-for-life",
        "mega-millions",
        "millionaire-for-life",
        "north-dakota-2by2",
        "powerball",
    }
    assert games["lucky-for-life"]["blocking_reason"] == (
        "Retired after February 2026; historical adapter pending"
    )
    _assert_supported_national_games(games)
    assert all(
        game["support_statuses"] == ["cataloged"]
        for slug, game in games.items()
        if slug not in NATIONAL_GAME_SLUGS
    )
    supported_blockers = {
        game["blocking_reason"]
        for slug, game in games.items()
        if slug not in {"lucky-for-life", *NATIONAL_GAME_SLUGS}
    }
    assert supported_blockers == {"Rules and fetch adapter pending"}


def test_coverage_reports_ohio_full_draw_game_catalog(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "oh",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "oh"
    assert payload["jurisdiction"] == "Ohio"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "lucky-for-life",
        "mega-millions",
        "millionaire-for-life",
        "ohio-classic-lotto",
        "ohio-keno",
        "ohio-pick-3",
        "ohio-pick-4",
        "ohio-pick-5",
        "ohio-rolling-cash-5",
        "powerball",
    }
    assert games["lucky-for-life"]["blocking_reason"] == (
        "Retired after February 2026; historical adapter pending"
    )
    assert games["ohio-keno"]["support_statuses"] == ["cataloged"]


def test_coverage_reports_oklahoma_full_draw_game_catalog(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "ok",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "ok"
    assert payload["jurisdiction"] == "Oklahoma"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "lotto-america",
        "lucky-for-life",
        "mega-millions",
        "millionaire-for-life",
        "oklahoma-cash-5",
        "oklahoma-pick-3",
        "powerball",
    }
    assert games["lucky-for-life"]["blocking_reason"] == (
        "Retired after February 2026; historical adapter pending"
    )
    assert games["oklahoma-cash-5"]["support_statuses"] == ["cataloged"]


def test_coverage_reports_oregon_full_draw_game_catalog(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "or",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "or"
    assert payload["jurisdiction"] == "Oregon"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "mega-millions",
        "oregon-cash-pop",
        "oregon-keno",
        "oregon-lucky-lines",
        "oregon-megabucks",
        "oregon-pick-4",
        "oregon-win-for-life",
        "powerball",
    }
    assert games["oregon-lucky-lines"]["blocking_reason"] == (
        "Retired after January 2025; historical adapter pending"
    )
    for game_slug in (
        "oregon-megabucks",
        "oregon-keno",
        "oregon-cash-pop",
        "oregon-pick-4",
        "oregon-win-for-life",
    ):
        assert games[game_slug]["support_statuses"] == [
            "cataloged",
            "rules_verified",
            "ev_supported",
            "fetch_supported",
            "audit_supported",
            "low_share_supported",
        ]
        assert games[game_slug]["results_adapter"] == "or_lottery_api"
        assert games[game_slug]["blocking_reason"] == ""
    assert games["oregon-lucky-lines"]["support_statuses"] == ["cataloged"]


def test_coverage_reports_pennsylvania_full_draw_game_catalog(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "pa",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "pa"
    assert payload["jurisdiction"] == "Pennsylvania"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "cash4life",
        "mega-millions",
        "millionaire-for-life",
        "pennsylvania-cash-5",
        "pennsylvania-cash-pop",
        "pennsylvania-derby-cash",
        "pennsylvania-keno",
        "pennsylvania-match-6",
        "pennsylvania-pick-2",
        "pennsylvania-pick-3",
        "pennsylvania-pick-4",
        "pennsylvania-pick-5",
        "pennsylvania-treasure-hunt",
        "powerball",
    }
    assert games["cash4life"]["blocking_reason"] == (
        "Retired after February 2026; historical adapter pending"
    )
    assert games["pennsylvania-match-6"]["support_statuses"] == ["cataloged"]


def test_coverage_reports_rhode_island_full_draw_game_catalog(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "ri",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "ri"
    assert payload["jurisdiction"] == "Rhode Island"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "lucky-for-life",
        "mega-millions",
        "millionaire-for-life",
        "powerball",
        "rhode-island-bingo",
        "rhode-island-keno",
        "rhode-island-numbers",
        "rhode-island-wild-money",
    }
    assert games["lucky-for-life"]["blocking_reason"] == (
        "Retired after February 2026; historical adapter pending"
    )
    assert games["rhode-island-wild-money"]["support_statuses"] == ["cataloged"]


def test_coverage_reports_south_carolina_full_draw_game_catalog(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "sc",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "sc"
    assert payload["jurisdiction"] == "South Carolina"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "mega-millions",
        "powerball",
        "south-carolina-cash-pop",
        "south-carolina-palmetto-cash-5",
        "south-carolina-pick-3",
        "south-carolina-pick-4",
    }
    _assert_supported_national_games(games)
    _assert_cataloged_local_blockers(games)


def test_coverage_reports_south_dakota_full_draw_game_catalog(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "sd",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "sd"
    assert payload["jurisdiction"] == "South Dakota"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "lotto-america",
        "mega-millions",
        "millionaire-for-life",
        "powerball",
        "south-dakota-dakota-cash",
    }
    _assert_supported_national_games(games)
    _assert_cataloged_local_blockers(games)


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
    for game_slug in (
        "idaho-cash",
        "idaho-pick-3",
        "idaho-pick-4",
        "lotto-america",
        "millionaire-for-life",
    ):
        assert games[game_slug]["support_statuses"] == [
            "cataloged",
            "rules_verified",
            "ev_supported",
            "fetch_supported",
            "audit_supported",
            "low_share_supported",
        ]
        assert games[game_slug]["results_adapter"] == "id_draw_page"
        assert games[game_slug]["blocking_reason"] == ""
    assert games["lucky-for-life"]["support_statuses"] == ["cataloged"]
    assert games["lucky-for-life"]["blocking_reason"] == (
        "Retired after February 2026; historical adapter pending"
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


def test_coverage_reports_kansas_catalog_and_supported_national_games(tmp_path):
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
    assert games["powerball"]["support_statuses"] == [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert games["powerball"]["results_adapter"] == "official_national_results_page"
    assert games["mega-millions"]["support_statuses"] == [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert games["mega-millions"]["results_adapter"] == (
        "official_national_results_page"
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


def test_coverage_reports_montana_catalog_and_supported_national_games(tmp_path):
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
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "lotto-america",
        "mega-millions",
        "millionaire-for-life",
        "montana-big-sky-bonus",
        "montana-cash",
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
    assert games["mega-millions"]["results_adapter"] == (
        "mt_winning_numbers_table"
    )
    assert games["montana-cash"]["support_statuses"] == ["cataloged"]
    assert games["montana-cash"]["blocking_reason"] == (
        "Rules and fetch adapter pending"
    )


def test_coverage_reports_nebraska_full_fetch_supported_catalog(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "ne",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "ne"
    assert payload["jurisdiction"] == "Nebraska"
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "lotto-america",
        "lucky-for-life",
        "mega-millions",
        "millionaire-for-life",
        "nebraska-2by2",
        "nebraska-myday",
        "nebraska-pick-3",
        "nebraska-pick-4",
        "nebraska-pick-5",
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
    assert games["mega-millions"]["results_adapter"] == "ne_draw_results_page"
    for game_slug in set(games) - {"lucky-for-life"}:
        assert "fetch_supported" in games[game_slug]["support_statuses"]
        assert "audit_supported" in games[game_slug]["support_statuses"]
        assert games[game_slug]["results_adapter"] == "ne_draw_results_page"
    assert games["nebraska-pick-5"]["blocking_reason"] == "Rules verification pending"
    assert games["lucky-for-life"]["blocking_reason"] == (
        "Retired after February 2026; historical adapter pending"
    )


def test_coverage_reports_colorado_full_draw_game_catalog(tmp_path):
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
    full_support_statuses = [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert all(
        games[game_slug]["support_statuses"] == full_support_statuses
        for game_slug in {
            "colorado-cash-5",
            "colorado-lotto-plus",
            "colorado-pick-3",
            "millionaire-for-life",
        }
    )
    assert all(
        games[game_slug]["results_adapter"] == "co_drawing_history"
        for game_slug in {
            "colorado-cash-5",
            "colorado-lotto-plus",
            "colorado-pick-3",
            "millionaire-for-life",
        }
    )
    assert all(
        games[game_slug]["blocking_reason"] == ""
        for game_slug in {
            "colorado-cash-5",
            "colorado-lotto-plus",
            "colorado-pick-3",
            "millionaire-for-life",
        }
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


def test_coverage_reports_texas_full_draw_game_catalog(tmp_path):
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
    assert set(games) == {
        "mega-millions",
        "powerball",
        "texas-all-or-nothing",
        "texas-cash-five",
        "texas-daily-4",
        "texas-lotto",
        "texas-pick-3",
        "texas-two-step",
    }
    assert all(
        games[game_slug]["support_statuses"]
        == [
            "cataloged",
            "rules_verified",
            "ev_supported",
            "fetch_supported",
            "audit_supported",
            "low_share_supported",
        ]
        for game_slug in {"mega-millions", "powerball"}
    )
    assert all(
        games[game_slug]["results_adapter"] == "tx_winning_numbers"
        for game_slug in {
            "mega-millions",
            "powerball",
            "texas-all-or-nothing",
            "texas-cash-five",
            "texas-daily-4",
            "texas-lotto",
            "texas-pick-3",
            "texas-two-step",
        }
    )
    assert all(
        games[game_slug]["support_statuses"]
        == [
            "cataloged",
            "rules_verified",
            "ev_supported",
            "fetch_supported",
            "audit_supported",
            "low_share_supported",
        ]
        for game_slug in {
            "texas-all-or-nothing",
            "texas-cash-five",
            "texas-daily-4",
            "texas-lotto",
            "texas-pick-3",
            "texas-two-step",
        }
    )
    assert all(
        games[game_slug]["blocking_reason"] == ""
        for game_slug in {
            "texas-all-or-nothing",
            "texas-cash-five",
            "texas-daily-4",
            "texas-lotto",
            "texas-pick-3",
            "texas-two-step",
        }
    )
