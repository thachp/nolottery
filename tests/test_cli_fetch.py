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


def _texas_powerball_history_html() -> str:
    return """
    <html>
      <body>
        <h1>Powerball Winning Numbers</h1>
        <table>
          <thead>
            <tr>
              <th>Draw Date</th>
              <th>Winning Numbers</th>
              <th>Powerball</th>
              <th>Power Play</th>
              <th>Estimated Jackpot</th>
              <th>Jackpot Winners</th>
              <th>Jackpot Option</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>05/06/2026</td>
              <td>18 - 27 - 51 - 65 - 68</td>
              <td>5</td>
              <td>3</td>
              <td>$30 Million</td>
              <td>Roll</td>
              <td></td>
            </tr>
            <tr>
              <td>05/04/2026</td>
              <td>30 - 36 - 42 - 60 - 63</td>
              <td>13</td>
              <td>2</td>
              <td>$20 Million</td>
              <td>Roll</td>
              <td></td>
            </tr>
          </tbody>
        </table>
      </body>
    </html>
    """


def _arizona_powerball_past_180_text() -> str:
    return """
    Past 180 Days Drawing Information
    Arizona Lottery
    POWERBALL
    DRAW DATE 2026-05-06 | DAY WED | EXP DATE 2026-11-02 |
    WINNING NUMBERS 18 - 27 - 51 - 65 - 68 | POWER BALL 5 |
    POWER PLAY 3 | EST JACKPOT $30,000,000
    DRAW DATE 2026-05-04 | DAY MON | EXP DATE 2026-10-31 |
    WINNING NUMBERS 30 - 36 - 42 - 60 - 63 | POWER BALL 13 |
    POWER PLAY 2 | EST JACKPOT $20,000,000
    """


def _arizona_mega_millions_past_180_text() -> str:
    return """
    Past 180 Days Drawing Information
    Arizona Lottery
    MEGA MILLIONS
    DRAW DATE 2026-05-05 | DAY TUE | EXP DATE 2026-11-01 |
    WINNING NUMBERS 5 - 11 - 22 - 25 - 69 | MEGA BALL 21 |
    MEGAPLIER 3 | EST JACKPOT $323,000,000
    """


def _arkansas_powerball_history_html() -> str:
    return """
    <html>
      <body>
        <h1>Powerball Winning Numbers</h1>
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Ball #1</th>
              <th>Ball #2</th>
              <th>Ball #3</th>
              <th>Ball #4</th>
              <th>Ball #5</th>
              <th>PB</th>
              <th>Power Play</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>05/06/2026</td><td>18</td><td>27</td><td>51</td><td>65</td><td>68</td><td>5</td><td>3</td></tr>
            <tr><td>05/04/2026</td><td>30</td><td>36</td><td>42</td><td>60</td><td>63</td><td>13</td><td>2</td></tr>
          </tbody>
        </table>
      </body>
    </html>
    """


def _arkansas_mega_millions_history_html() -> str:
    return """
    <html>
      <body>
        <h1>Mega Millions Winning Numbers</h1>
        <table>
          <tbody>
            <tr><td>05/05/2026</td><td>12</td><td>22</td><td>50</td><td>51</td><td>55</td><td>10</td></tr>
          </tbody>
        </table>
      </body>
    </html>
    """


def _colorado_powerball_history_html() -> str:
    return """
    <html>
      <body>
        <h1>Powerball Drawing History</h1>
        <h2>May 2026</h2>
        <a>Wednesday, 5/6/26</a>
        <p>Powerball Numbers</p>
        <p>18 27 51 65 68</p>
        <p>5</p>
        <p>x3</p>
        <p>$30,000,000 Jackpot</p>
        <a>Monday, 5/4/26</a>
        <p>Powerball Numbers</p>
        <p>30 36 42 60 63</p>
        <p>13</p>
        <p>x2</p>
        <p>$20,000,000 Jackpot</p>
      </body>
    </html>
    """


def _colorado_mega_millions_history_html() -> str:
    return """
    <html>
      <body>
        <h1>Mega Millions Drawing History</h1>
        <a>Tuesday, 2/3/26</a>
        <p>Mega Millions Numbers</p>
        <p>5 11 22 25 69</p>
        <p>21</p>
        <p>$323,000,000 Jackpot</p>
      </body>
    </html>
    """


def _connecticut_powerball_history_html() -> str:
    return """
    <form>
      <table id="gvWinningNumbers">
        <thead>
          <tr>
            <th>Drawing</th>
            <th>Draw Date</th>
            <th>Winning Numbers</th>
            <th>Power<br>Ball</th>
            <th>Power<br>Play</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Powerball</td>
            <td>5/6/2026</td>
            <td>18 - 27 - 51 - 65 - 68</td>
            <td>5</td>
            <td>3</td>
          </tr>
          <tr>
            <td>Double Play</td>
            <td>5/6/2026</td>
            <td>4 - 21 - 36 - 48 - 69</td>
            <td>5</td>
            <td>-</td>
          </tr>
          <tr>
            <td>Powerball</td>
            <td>5/4/2026</td>
            <td>30 - 36 - 42 - 60 - 63</td>
            <td>13</td>
            <td>2</td>
          </tr>
        </tbody>
      </table>
    </form>
    """


def _connecticut_mega_millions_history_html() -> str:
    return """
    <form>
      <table id="gvWinningNumbers">
        <thead>
          <tr>
            <th>Draw Date</th>
            <th>Winning Numbers</th>
            <th>Mega Ball</th>
            <th>Megaplier*</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>5/5/2026</td>
            <td>12 - 22 - 50 - 51 - 55</td>
            <td>10</td>
            <td>-</td>
          </tr>
        </tbody>
      </table>
    </form>
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
            "jurisdiction_code": "wa",
            "draw_date": "Mon, May 04, 2026",
            "winning_number": "01, 02, 03, 04, 05, 06",
        }
    ]


def test_fetch_and_draws_accept_explicit_washington_jurisdiction(tmp_path):
    data_dir = tmp_path / "data"
    fixture = tmp_path / "cashpop.html"
    fixture.write_text(DRAWING_HTML, encoding="utf-8")

    fetch_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "fetch",
            "cashpop",
            "-j",
            "wa",
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
            "cashpop",
            "-j",
            "wa",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["jurisdiction_code"] == "wa"
    assert payload["games"][0]["jurisdiction_code"] == "wa"
    assert payload["games"][0]["draws"][0]["jurisdiction_code"] == "wa"


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


def test_fetch_florida_pick3_backfill_reads_official_history_fixture(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "florida-pick-3-fl-backfill.txt").write_text(
        """
        FLORIDA LOTTERY Winning Numbers History
        PICK 3
        E: Evening and M: Midday drawing results
        05/06/26 E 5 - 1 - 7 FB 2     05/06/26 M 3 - 7 - 2 FB 3
        05/05/26 E 8 - 0 - 1 FB 1
        """,
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "fetch",
            "florida-pick-3",
            "-j",
            "fl",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Pick 3" in result.output
    assert "3 draws" in result.output

    draws_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "draws",
            "florida-pick-3",
            "-j",
            "fl",
            "--limit",
            "3",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "fl",
            "draw_date": "Wed, May 06, 2026 Evening",
            "winning_number": "5, 1, 7",
        },
        {
            "jurisdiction_code": "fl",
            "draw_date": "Wed, May 06, 2026 Midday",
            "winning_number": "3, 7, 2",
        },
        {
            "jurisdiction_code": "fl",
            "draw_date": "Tue, May 05, 2026 Evening",
            "winning_number": "8, 0, 1",
        },
    ]


def test_fetch_new_york_numbers_backfill_reads_official_json_fixture(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "numbers-ny-backfill.json").write_text(
        json.dumps(
            [
                {
                    "draw_date": "2026-05-06T00:00:00.000",
                    "midday_daily": "319",
                    "evening_daily": "402",
                    "midday_win_4": "5954",
                    "evening_win_4": "2653",
                },
                {
                    "draw_date": "2026-05-05T00:00:00.000",
                    "midday_daily": "531",
                    "evening_daily": "745",
                    "midday_win_4": "4734",
                    "evening_win_4": "7556",
                },
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "fetch",
            "numbers",
            "-j",
            "ny",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Numbers" in result.output
    assert "4 draws" in result.output

    draws_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "draws",
            "numbers",
            "-j",
            "ny",
            "--limit",
            "2",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "ny",
            "draw_date": "Wed, May 06, 2026 Evening",
            "winning_number": "402",
        },
        {
            "jurisdiction_code": "ny",
            "draw_date": "Wed, May 06, 2026 Midday",
            "winning_number": "319",
        },
    ]


def test_fetch_reports_cataloged_game_without_fetch_support(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "fetch",
            "new-york-lotto",
            "-j",
            "ny",
            "--backfill",
        ],
    )

    assert result.exit_code != 0
    assert "fetch support pending for game: new-york-lotto" in result.output


def test_fetch_texas_powerball_backfill_reads_official_history_fixture(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball.html").write_text(
        _texas_powerball_history_html(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "fetch",
            "powerball",
            "-j",
            "tx",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Powerball" in result.output
    assert "2 draws" in result.output
    assert "1 page" in result.output

    draws_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "draws",
            "powerball",
            "-j",
            "tx",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "tx",
            "draw_date": "Wed, May 06, 2026",
            "winning_number": "18, 27, 51, 65, 68, 5 Powerball",
        },
        {
            "jurisdiction_code": "tx",
            "draw_date": "Mon, May 04, 2026",
            "winning_number": "30, 36, 42, 60, 63, 13 Powerball",
        },
    ]


def test_fetch_arizona_powerball_backfill_reads_official_past_180_fixture(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball-az-backfill.txt").write_text(
        _arizona_powerball_past_180_text(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "fetch",
            "powerball",
            "-j",
            "az",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Powerball" in result.output
    assert "2 draws" in result.output
    assert "1 page" in result.output

    draws_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "draws",
            "powerball",
            "-j",
            "az",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "az",
            "draw_date": "Wed, May 06, 2026",
            "winning_number": "18, 27, 51, 65, 68, 5 Powerball",
        },
        {
            "jurisdiction_code": "az",
            "draw_date": "Mon, May 04, 2026",
            "winning_number": "30, 36, 42, 60, 63, 13 Powerball",
        },
    ]


def test_fetch_all_arizona_backfill_uses_supported_national_games(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball-az-backfill.txt").write_text(
        _arizona_powerball_past_180_text(),
        encoding="utf-8",
    )
    (fixtures / "mega-millions-az-backfill.txt").write_text(
        _arizona_mega_millions_past_180_text(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "fetch",
            "all",
            "-j",
            "az",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Powerball" in result.output
    assert "Mega Millions" in result.output
    assert "2 games fetched" in result.output


def test_fetch_arkansas_powerball_backfill_reads_official_history_fixture(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball-ar-backfill.html").write_text(
        _arkansas_powerball_history_html(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "fetch",
            "powerball",
            "-j",
            "ar",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Powerball" in result.output
    assert "2 draws" in result.output

    draws_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "draws",
            "powerball",
            "-j",
            "ar",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "ar",
            "draw_date": "Wed, May 06, 2026",
            "winning_number": "18, 27, 51, 65, 68, 5 Powerball",
        },
        {
            "jurisdiction_code": "ar",
            "draw_date": "Mon, May 04, 2026",
            "winning_number": "30, 36, 42, 60, 63, 13 Powerball",
        },
    ]


def test_fetch_all_arkansas_backfill_uses_supported_national_games(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball-ar-backfill.html").write_text(
        _arkansas_powerball_history_html(),
        encoding="utf-8",
    )
    (fixtures / "mega-millions-ar-backfill.html").write_text(
        _arkansas_mega_millions_history_html(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "fetch",
            "all",
            "-j",
            "ar",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Powerball" in result.output
    assert "Mega Millions" in result.output
    assert "2 games fetched" in result.output


def test_fetch_colorado_powerball_backfill_reads_official_history_fixture(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball-co-backfill.html").write_text(
        _colorado_powerball_history_html(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "fetch",
            "powerball",
            "-j",
            "co",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Powerball" in result.output
    assert "2 draws" in result.output

    draws_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "draws",
            "powerball",
            "-j",
            "co",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "co",
            "draw_date": "Wed, May 06, 2026",
            "winning_number": "18, 27, 51, 65, 68, 5 Powerball",
        },
        {
            "jurisdiction_code": "co",
            "draw_date": "Mon, May 04, 2026",
            "winning_number": "30, 36, 42, 60, 63, 13 Powerball",
        },
    ]


def test_fetch_all_colorado_backfill_uses_supported_national_games(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball-co-backfill.html").write_text(
        _colorado_powerball_history_html(),
        encoding="utf-8",
    )
    (fixtures / "mega-millions-co-backfill.html").write_text(
        _colorado_mega_millions_history_html(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "fetch",
            "all",
            "-j",
            "co",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Powerball" in result.output
    assert "Mega Millions" in result.output
    assert "2 games fetched" in result.output


def test_fetch_connecticut_powerball_backfill_reads_official_ajax_fixture(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball-ct-backfill.html").write_text(
        _connecticut_powerball_history_html(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "fetch",
            "powerball",
            "-j",
            "ct",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Powerball" in result.output
    assert "2 draws" in result.output
    assert "1 page" in result.output

    draws_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "draws",
            "powerball",
            "-j",
            "ct",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "ct",
            "draw_date": "Wed, May 06, 2026",
            "winning_number": "18, 27, 51, 65, 68, 5 Powerball",
        },
        {
            "jurisdiction_code": "ct",
            "draw_date": "Mon, May 04, 2026",
            "winning_number": "30, 36, 42, 60, 63, 13 Powerball",
        },
    ]


def test_fetch_connecticut_mega_millions_backfill_reads_official_ajax_fixture(
    tmp_path,
):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "mega-millions-ct-backfill.html").write_text(
        _connecticut_mega_millions_history_html(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "fetch",
            "mega-millions",
            "-j",
            "ct",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Mega Millions" in result.output
    assert "1 draw" in result.output
    assert "1 page" in result.output

    draws_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "draws",
            "mega-millions",
            "-j",
            "ct",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "ct",
            "draw_date": "Tue, May 05, 2026",
            "winning_number": "12, 22, 50, 51, 55, 10 Mega Ball",
        }
    ]


def test_fetch_all_backfill_uses_supported_subset_for_florida(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    for game_slug, digits in {
        "florida-pick-2": "5 - 7",
        "florida-pick-3": "5 - 1 - 7",
        "florida-pick-4": "9 - 3 - 3 - 6",
        "florida-pick-5": "2 - 5 - 6 - 0 - 1",
    }.items():
        (fixtures / f"{game_slug}-fl-backfill.txt").write_text(
            f"05/06/26 E {digits} FB 2",
            encoding="utf-8",
        )

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "fetch",
            "all",
            "-j",
            "fl",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "4 games fetched" in result.output
    assert "Fantasy 5" not in result.output


def test_fetch_all_backfill_uses_supported_subset_for_new_york(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    for game_slug in ("numbers", "win-4"):
        (fixtures / f"{game_slug}-ny-backfill.json").write_text(
            json.dumps(
                [
                    {
                        "draw_date": "2026-05-06T00:00:00.000",
                        "midday_daily": "319",
                        "evening_daily": "402",
                        "midday_win_4": "5954",
                        "evening_win_4": "2653",
                    }
                ]
            ),
            encoding="utf-8",
        )

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "fetch",
            "all",
            "-j",
            "ny",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "2 games fetched" in result.output
    assert "Numbers" in result.output
    assert "Win 4" in result.output
    assert "LOTTO" not in result.output


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
        {
            "jurisdiction_code": "wa",
            "draw_date": "Tue, May 05, 2026",
            "winning_number": "05",
        },
        {
            "jurisdiction_code": "wa",
            "draw_date": "Mon, May 04, 2026",
            "winning_number": "04",
        },
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
