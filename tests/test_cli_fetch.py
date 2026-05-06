from typer.testing import CliRunner

from nolottery.cli import app


runner = CliRunner()


DRAWING_HTML = """
<html>
  <body>
    <table class="table-viewport-large">
      <thead>
        <tr>
          <th><p class="h2-like">Mon, May 04, 2026</p></th>
          <th>Prize Amount</th><th>WA Winners</th><th>Total</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td class="game-balls" rowspan="2"><ul><li>04</li></ul></td>
          <td>$500</td><td>2</td><td>$1,000</td>
        </tr>
        <tr><td>$100</td><td>3</td><td>$300</td></tr>
        <tr><td>Totals</td><td>5</td><td>$1,300</td></tr>
      </tbody>
    </table>
  </body>
</html>
"""


def test_fetch_cashpop_persists_official_page_snapshot_and_draws(tmp_path):
    fixture = tmp_path / "cashpop.html"
    fixture.write_text(DRAWING_HTML, encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "fetch",
            "cashpop",
            "--source-file",
            str(fixture),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Cash Pop" in result.output
    assert "1 draw" in result.output
    assert "2 prize rows" in result.output


def test_fetch_all_accepts_one_fixture_directory_for_all_games(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    for game in [
        "cashpop",
        "daily-keno",
        "hit-5",
        "lotto",
        "match-4",
        "mega-millions",
        "pick-3",
        "powerball",
    ]:
        (fixtures / f"{game}.html").write_text(DRAWING_HTML, encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "fetch",
            "all",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Cash Pop" in result.output
    assert "Daily Keno" in result.output
    assert "Powerball" in result.output
    assert "8 games fetched" in result.output
