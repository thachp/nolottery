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


def test_coverage_reports_state_without_lottery_as_supported_jurisdiction(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "al",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "al"
    assert payload["jurisdiction"] == "Alabama"
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
            "ga",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "ga"
    assert payload["jurisdiction"] == "Georgia"
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
