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
    expected = {
        "ny": ("New York", {"numbers", "win-4", "take-5", "pick-10"}),
        "fl": (
            "Florida",
            {"florida-fantasy-5", "florida-lotto", "florida-pick-5"},
        ),
        "dc": ("District of Columbia", {"dc-3", "dc-4", "dc-5"}),
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
        assert all(
            game["support_statuses"] == ["cataloged"]
            for game in payload["games"]
        )
        assert all(
            game["blocking_reason"] == "Rules and fetch adapter pending"
            for game in payload["games"]
        )
