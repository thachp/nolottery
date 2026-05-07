import json

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
