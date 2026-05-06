import json
import sqlite3

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


def _drawing_html(date: str, number: str) -> str:
    return _drawings_html((date, number))


def _drawings_html(*draws: tuple[str, str]) -> str:
    tables = "\n".join(
        f"""
        <table class="table-viewport-large">
          <thead>
            <tr>
              <th><p class="h2-like">{date}</p></th>
              <th>Prize Amount</th><th>WA Winners</th><th>Total</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td class="game-balls" rowspan="1"><ul><li>{number}</li></ul></td>
              <td>$500</td><td>1</td><td>$500</td>
            </tr>
          </tbody>
        </table>
        """
        for date, number in draws
    )
    return f"""
    <html>
      <body>
        <select aria-label="Amount Of Drawings Menu">
          <option value="180 day">Past 180 Days</option>
          <option value="2026 year">2026</option>
          <option value="2025 year">2025</option>
        </select>
        {tables}
      </body>
    </html>
    """


def _drawings_without_prizes_html(date: str, *numbers: str) -> str:
    return f"""
    <html>
      <body>
        <table class="table-viewport-large">
          <thead>
            <tr>
              <th><p class="h2-like">{date}</p></th>
              <th>Prize Amount</th><th>WA Winners</th><th>Total</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td class="game-balls"><ul>{''.join(f'<li>{number}</li>' for number in numbers)}</ul></td>
            </tr>
          </tbody>
        </table>
      </body>
    </html>
    """


def _drawing_with_extra_ball_cell_html(
    date: str,
    primary_numbers: tuple[str, ...],
    extra_numbers: tuple[str, ...],
) -> str:
    primary_items = "".join(f"<li>{number}</li>" for number in primary_numbers)
    extra_items = "".join(f"<li>{number}</li>" for number in extra_numbers)
    return f"""
    <html>
      <body>
        <table class="table-viewport-large">
          <thead>
            <tr>
              <th><p class="h2-like">{date}</p></th>
              <th>Prize Amount</th><th>WA Winners</th><th>Total</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td class="game-balls"><ul>{primary_items}</ul></td>
              <td>$4</td><td>1</td><td>$4</td>
            </tr>
            <tr>
              <td class="game-balls"><ul>{extra_items}</ul></td>
              <td>$4</td><td>1</td><td>$4</td>
            </tr>
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


def test_fetch_persists_draw_numbers_when_prize_rows_are_absent(tmp_path):
    data_dir = tmp_path / "data"
    fixture = tmp_path / "powerball.html"
    fixture.write_text(
        _drawings_without_prizes_html(
            "Mon, May 04, 2026",
            "01",
            "02",
            "03",
            "04",
            "05",
            "06",
        ),
        encoding="utf-8",
    )

    fetch_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "fetch",
            "powerball",
            "--source-file",
            str(fixture),
        ],
    )
    assert fetch_result.exit_code == 0, fetch_result.output
    assert "1 draw" in fetch_result.output
    assert "0 prize rows" in fetch_result.output

    draws_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "draws",
            "powerball",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "draw_date": "Mon, May 04, 2026",
            "winning_number": "01, 02, 03, 04, 05, 06",
        }
    ]


def test_fetch_uses_first_ball_cell_when_a_draw_table_has_extra_ball_cells(tmp_path):
    data_dir = tmp_path / "data"
    fixture = tmp_path / "powerball.html"
    fixture.write_text(
        _drawing_with_extra_ball_cell_html(
            "Mon, May 04, 2026",
            ("01", "02", "03", "04", "05", "06"),
            ("07", "08", "09", "10", "11", "12"),
        ),
        encoding="utf-8",
    )

    fetch_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "fetch",
            "powerball",
            "--source-file",
            str(fixture),
        ],
    )
    assert fetch_result.exit_code == 0, fetch_result.output

    draws_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "draws",
            "powerball",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"][0]["winning_number"] == (
        "01, 02, 03, 04, 05, 06"
    )


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


def test_fetch_persists_only_draws_newer_than_latest_stored_date(tmp_path):
    data_dir = tmp_path / "data"
    fixture = tmp_path / "cashpop.html"
    fixture.write_text(_drawing_html("Mon, May 04, 2026", "04"), encoding="utf-8")

    first_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "fetch",
            "cashpop",
            "--source-file",
            str(fixture),
        ],
    )
    assert first_result.exit_code == 0, first_result.output

    fixture.write_text(
        _drawings_html(
            ("Tue, May 05, 2026", "05"),
            ("Mon, May 04, 2026", "04"),
        ),
        encoding="utf-8",
    )
    second_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "fetch",
            "cashpop",
            "--source-file",
            str(fixture),
        ],
    )

    assert second_result.exit_code == 0, second_result.output
    assert "1 draw" in second_result.output
    with sqlite3.connect(data_dir / "lottery.sqlite3") as conn:
        rows = conn.execute(
            """
            select draw_date, winning_number
            from draw_results
            where game_slug = 'cashpop'
            order by draw_date
            """
        ).fetchall()
    assert rows == [
        ("Mon, May 04, 2026", "04"),
        ("Tue, May 05, 2026", "05"),
    ]


def test_fetch_backfill_reads_yearly_pages_from_source_dir(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "cashpop.html").write_text(
        _drawing_html("Mon, May 04, 2026", "04"),
        encoding="utf-8",
    )
    (fixtures / "cashpop-2026.html").write_text(
        _drawing_html("Mon, May 04, 2026", "04"),
        encoding="utf-8",
    )
    (fixtures / "cashpop-2025.html").write_text(
        _drawing_html("Wed, Jan 01, 2025", "07"),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "fetch",
            "cashpop",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Cash Pop" in result.output
    assert "2 draws" in result.output
    assert "2 pages" in result.output


def test_fetch_all_backfill_reads_yearly_pages_for_every_game(tmp_path):
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
        (fixtures / f"{game}.html").write_text(
            _drawing_html("Mon, May 04, 2026", "04"),
            encoding="utf-8",
        )
        (fixtures / f"{game}-2026.html").write_text(
            _drawing_html("Mon, May 04, 2026", "04"),
            encoding="utf-8",
        )
        (fixtures / f"{game}-2025.html").write_text(
            _drawing_html("Wed, Jan 01, 2025", "07"),
            encoding="utf-8",
        )

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "fetch",
            "all",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Cash Pop" in result.output
    assert "Powerball" in result.output
    assert "2 pages" in result.output
    assert "8 games fetched" in result.output


def test_draws_lists_recent_numbers_newest_first_and_deduped(tmp_path):
    data_dir = tmp_path / "data"
    fixture = tmp_path / "cashpop.html"
    fixture.write_text(DRAWING_HTML, encoding="utf-8")
    first_fetch = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "fetch",
            "cashpop",
            "--source-file",
            str(fixture),
        ],
    )
    assert first_fetch.exit_code == 0, first_fetch.output

    fixture.write_text(
        _drawing_html("Tue, May 05, 2026", "05"),
        encoding="utf-8",
    )
    second_fetch = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "fetch",
            "cashpop",
            "--source-file",
            str(fixture),
        ],
    )
    assert second_fetch.exit_code == 0, second_fetch.output

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "draws",
            "cashpop",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    draws = payload["games"][0]["draws"]
    assert draws == [
        {"draw_date": "Tue, May 05, 2026", "winning_number": "05"},
        {"draw_date": "Mon, May 04, 2026", "winning_number": "04"},
    ]


def test_draws_all_includes_each_supported_game(tmp_path):
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
        (fixtures / f"{game}.html").write_text(
            _drawing_html("Mon, May 04, 2026", "04"),
            encoding="utf-8",
        )
    fetch_result = runner.invoke(
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
    assert fetch_result.exit_code == 0, fetch_result.output

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "draws",
            "all",
            "--limit",
            "1",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert [game["game_slug"] for game in payload["games"]] == [
        "cashpop",
        "daily-keno",
        "hit-5",
        "lotto",
        "match-4",
        "mega-millions",
        "pick-3",
        "powerball",
    ]
    assert all(game["draws"] for game in payload["games"])
