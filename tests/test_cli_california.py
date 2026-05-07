import json

from typer.testing import CliRunner

from nolottery.cli import app


runner = CliRunner()


CA_DAILY_3_HTML = """
<html>
  <body>
    <h1>Daily 3</h1>
    <h3>Detailed Draw Results</h3>
    <p>WED/MAY 6, 2026 - EVENING | Draw #21027</p>
    <h4>Winning Numbers</h4>
    <ul><li>1</li><li>2</li><li>9</li></ul>
    <p>Matching Numbers Winning Tickets Prize Amounts</p>
    <p>Straight 79 $425</p>
    <p>Box 99 $68</p>
    <p>WED/MAY 6, 2026 - MIDDAY | Draw #21026</p>
    <h4>Winning Numbers</h4>
    <ul><li>7</li><li>0</li><li>5</li></ul>
    <p>Matching Numbers Winning Tickets Prize Amounts</p>
    <p>Straight 39 $645</p>
    <p>Box 101 $102</p>
  </body>
</html>
"""


def test_california_daily3_coverage_marks_ev_blocked(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "coverage",
            "-j",
            "ca",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "ca"
    assert payload["jurisdiction"] == "California"
    assert payload["games"] == [
        {
            "jurisdiction_code": "ca",
            "game_slug": "daily-3",
            "game": "Daily 3",
            "support_statuses": [
                "cataloged",
                "rules_verified",
                "fetch_supported",
            ],
            "reviewed_on": "2026-05-07",
            "results_adapter": "ca_daily3_page",
            "rule_source_present": True,
            "results_source_present": True,
            "blocking_reason": "EV pending variable pari-mutuel prize estimates",
        }
    ]


def test_fetch_california_daily3_parses_midday_and_evening_draws(tmp_path):
    data_dir = tmp_path / "data"
    fixture = tmp_path / "daily-3.html"
    fixture.write_text(CA_DAILY_3_HTML, encoding="utf-8")

    fetch_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "fetch",
            "daily-3",
            "-j",
            "ca",
            "--source-file",
            str(fixture),
        ],
    )
    assert fetch_result.exit_code == 0, fetch_result.output
    assert "Daily 3" in fetch_result.output
    assert "2 draws" in fetch_result.output

    draws_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "draws",
            "daily-3",
            "-j",
            "ca",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "ca",
            "draw_date": "Wed, May 06, 2026 Evening",
            "winning_number": "1, 2, 9",
        },
        {
            "jurisdiction_code": "ca",
            "draw_date": "Wed, May 06, 2026 Midday",
            "winning_number": "7, 0, 5",
        },
    ]
