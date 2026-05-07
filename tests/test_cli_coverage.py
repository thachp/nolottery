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
