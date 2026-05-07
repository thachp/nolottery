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


def _ca_draw_game_html(
    date: str,
    *numbers: str,
    prize_line: str = "Match 1 $2",
) -> str:
    return f"""
    <html>
      <body>
        <h1>California Draw Game</h1>
        <p>Winning Numbers:</p>
        <p>{date}</p>
        <p>Draw #12345</p>
        <ul>{''.join(f'<li>{number}</li>' for number in numbers)}</ul>
        <h3>Detailed Draw Results</h3>
        <p>Matching Numbers Winning Tickets Prize Amounts</p>
        <p>{prize_line}</p>
      </body>
    </html>
    """


def _ca_hot_spot_html() -> str:
    return """
    <html>
      <body>
        <p class="htspt__cards--current-num">
          Current Draw Number: <strong class="current-drawNumber">3262341</strong>
        </p>
        <p class="htspt__cards--next-draw-date">
          Draw Date: <strong class="caps-texts">May 7, 2026</strong>
          <span>|</span> Draw Time: <strong>11:40 a.m.</strong>
        </p>
        <div class="sr-only-container">
          <ul class="sr-only">
            <li>Draw Results:</li>
            <li>1</li><li>3</li><li>4</li><li>5</li><li>15</li>
            <li>18</li><li>19</li><li>21</li><li>25</li><li>28</li>
            <li>29</li><li>35</li><li>39</li><li>43</li><li>57</li>
            <li>66</li><li>67</li><li>69</li>
            <li>Bulls-eye number is 74</li>
            <li>75</li>
          </ul>
        </div>
      </body>
    </html>
    """


def _ca_past_winning_numbers_config_html(game_id: int, total_results: int) -> str:
    return f"""
    <html>
      <body>
        <div class="past-winning-numbers" id="pastwinning">
          <script type="application/json">
            {{
              "drawGamePastDrawResultsApi": "/api/DrawGameApi/DrawGamePastDrawResults/",
              "pwnGameId": "{game_id}",
              "pwnTotalResults": "{total_results}"
            }}
          </script>
          <div id="react-past-winning-numbers"></div>
        </div>
      </body>
    </html>
    """


def _ca_daily3_backfill_json() -> str:
    return json.dumps(
        {
            "DrawGameId": 9,
            "Name": "Daily 3",
            "TotalPreviousDraws": 2,
            "PreviousDraws": [
                {
                    "DrawNumber": 21027,
                    "DrawDate": "2026-05-06T07:00:00",
                    "WinningNumbers": {
                        "1": {"Number": "1", "IsSpecial": False, "Name": None},
                        "2": {"Number": "2", "IsSpecial": False, "Name": None},
                        "3": {"Number": "9", "IsSpecial": False, "Name": None},
                    },
                    "Prizes": {
                        "1": {
                            "PrizeTypeDescription": "Straight",
                            "Count": 79,
                            "Amount": 425,
                        },
                        "2": {
                            "PrizeTypeDescription": "Box",
                            "Count": 99,
                            "Amount": 68,
                        },
                    },
                },
                {
                    "DrawNumber": 21026,
                    "DrawDate": "2026-05-06T07:00:00",
                    "WinningNumbers": {
                        "1": {"Number": "7", "IsSpecial": False, "Name": None},
                        "2": {"Number": "0", "IsSpecial": False, "Name": None},
                        "3": {"Number": "5", "IsSpecial": False, "Name": None},
                    },
                    "Prizes": {
                        "1": {
                            "PrizeTypeDescription": "Straight",
                            "Count": 39,
                            "Amount": 645,
                        },
                        "2": {
                            "PrizeTypeDescription": "Box",
                            "Count": 101,
                            "Amount": 102,
                        },
                    },
                },
            ],
        }
    )


def _ca_daily4_backfill_json(draw_count: int, total_results: int) -> str:
    return json.dumps(
        {
            "DrawGameId": 14,
            "Name": "Daily 4",
            "TotalPreviousDraws": total_results,
            "PreviousDraws": [
                {
                    "DrawNumber": 7000 - index,
                    "DrawDate": "2026-05-06T07:00:00",
                    "WinningNumbers": {
                        str(position + 1): {
                            "Number": digit,
                            "IsSpecial": False,
                        }
                        for position, digit in enumerate(f"{index:04d}")
                    },
                    "Prizes": {},
                }
                for index in range(draw_count)
            ],
        }
    )


def _ca_backfill_json(
    game_id: int,
    name: str,
    draw_number: int,
    draw_date: str,
    winning_numbers: list[dict[str, object]],
    prizes: list[dict[str, object]] | None = None,
    race_time: str | None = None,
) -> str:
    return json.dumps(
        {
            "DrawGameId": game_id,
            "Name": name,
            "TotalPreviousDraws": 1,
            "PreviousDraws": [
                {
                    "DrawNumber": draw_number,
                    "DrawDate": draw_date,
                    "WinningNumbers": {
                        str(index): number
                        for index, number in enumerate(winning_numbers)
                    },
                    "Prizes": {
                        str(index): prize
                        for index, prize in enumerate(prizes or [], start=1)
                    },
                    "RaceTime": race_time,
                }
            ],
        }
    )


def _ca_api_number(
    number: str,
    *,
    special: bool = False,
    name: str | None = None,
) -> dict[str, object]:
    return {"Number": number, "IsSpecial": special, "Name": name}


def _ca_api_prize(label: str, count: int, amount: int) -> dict[str, object]:
    return {
        "PrizeTypeDescription": label,
        "Count": count,
        "Amount": amount,
        "TotalPayout": None,
    }


def _ca_hot_spot_backfill_json() -> str:
    return json.dumps(
        {
            "number": 22,
            "name": "Hot Spot",
            "draws": [
                {
                    "DrawNumber": 3262350,
                    "DrawCloseTime": "2026-05-07T12:16:00-07:00",
                    "WinningNumbers": [
                        {"Number": 27, "IsBullseye": True},
                        *[
                            {"Number": number, "IsBullseye": False}
                            for number in (
                                1,
                                5,
                                42,
                                16,
                                48,
                                79,
                                46,
                                59,
                                36,
                                51,
                                18,
                                13,
                                43,
                                28,
                                22,
                                70,
                                8,
                                73,
                                7,
                            )
                        ],
                    ],
                    "PrizeTiers": None,
                }
            ],
        }
    )


def test_california_coverage_reports_active_draw_game_catalog(tmp_path):
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
    games = {game["game_slug"]: game for game in payload["games"]}
    assert set(games) == {
        "powerball",
        "mega-millions",
        "superlotto-plus",
        "fantasy-5",
        "daily-4",
        "daily-3",
        "daily-derby",
        "hot-spot",
    }
    assert all("fetch_supported" in game["support_statuses"] for game in games.values())
    assert games["powerball"]["results_adapter"] == "ca_draw_game_page"
    assert games["hot-spot"]["results_adapter"] == "ca_hot_spot_page"
    full_statuses = [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert games["daily-3"]["support_statuses"] == [
        *full_statuses,
    ]
    assert games["daily-3"]["blocking_reason"] == ""
    assert games["daily-4"]["support_statuses"] == full_statuses
    assert games["daily-4"]["blocking_reason"] == ""


def test_fetch_all_california_games_uses_california_result_adapters(tmp_path):
    data_dir = tmp_path / "data"
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    fixture_html = {
        "powerball": _ca_draw_game_html(
            "WED/MAY 6, 2026",
            "18",
            "27",
            "51",
            "65",
            "68",
            "<span>5</span><span>Powerball</span>",
            prize_line="5 + Powerball 0 $30,000,000",
        ),
        "mega-millions": _ca_draw_game_html(
            "TUE/MAY 5, 2026",
            "16",
            "28",
            "42",
            "46",
            "55",
            "24 Mega Ball",
        ),
        "superlotto-plus": _ca_draw_game_html(
            "WED/MAY 6, 2026",
            "10",
            "19",
            "21",
            "32",
            "40",
            "2 Mega",
        ),
        "fantasy-5": _ca_draw_game_html(
            "WED/MAY 6, 2026",
            "04",
            "09",
            "17",
            "22",
            "31",
        ),
        "daily-4": _ca_draw_game_html(
            "WED/MAY 6, 2026",
            "1",
            "8",
            "9",
            "3",
            prize_line="Straight 0 $6,600",
        ),
        "daily-3": CA_DAILY_3_HTML,
        "daily-derby": _ca_draw_game_html(
            "WED/MAY 6, 2026",
            "First: 09 - Winning Spirit",
            "Second: 01 - Gold Rush",
            "Third: 03 - Hot Shot",
            "Race Time: 1:40.67",
            prize_line="Grand Prize 0 $58,843",
        ),
        "hot-spot": _ca_hot_spot_html(),
    }
    for slug, html in fixture_html.items():
        (fixtures / f"{slug}.html").write_text(html, encoding="utf-8")

    fetch_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "fetch",
            "all",
            "-j",
            "ca",
            "--source-dir",
            str(fixtures),
        ],
    )
    assert fetch_result.exit_code == 0, fetch_result.output
    assert "8 games fetched" in fetch_result.output

    draws_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "draws",
            "all",
            "-j",
            "ca",
            "--limit",
            "1",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    draws = {
        game["game_slug"]: game["draws"][0]
        for game in payload["games"]
    }
    assert set(draws) == set(fixture_html)
    assert draws["powerball"]["winning_number"] == (
        "18, 27, 51, 65, 68, 5 Powerball"
    )
    assert draws["daily-3"]["draw_date"] == "Wed, May 06, 2026 Evening"
    assert draws["daily-derby"]["winning_number"] == (
        "First: 09 - Winning Spirit, Second: 01 - Gold Rush, "
        "Third: 03 - Hot Shot, Race Time: 1:40.67"
    )
    assert draws["hot-spot"]["draw_date"] == "Thu, May 07, 2026 11:40 AM"
    assert "74 Bulls-eye" in draws["hot-spot"]["winning_number"]


def test_california_remaining_capabilities_are_exercised_before_status_promotion(
    tmp_path,
):
    data_dir = tmp_path / "data"
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    fixture_html = {
        "powerball": _ca_draw_game_html(
            "WED/MAY 6, 2026",
            "18",
            "27",
            "51",
            "65",
            "68",
            "<span>5</span><span>Powerball</span>",
        ),
        "mega-millions": _ca_draw_game_html(
            "TUE/MAY 5, 2026",
            "16",
            "28",
            "42",
            "46",
            "55",
            "24 Mega Ball",
        ),
        "superlotto-plus": _ca_draw_game_html(
            "WED/MAY 6, 2026",
            "10",
            "19",
            "21",
            "32",
            "40",
            "2 Mega",
        ),
        "fantasy-5": _ca_draw_game_html(
            "WED/MAY 6, 2026",
            "04",
            "09",
            "17",
            "22",
            "31",
        ),
        "daily-4": _ca_draw_game_html("WED/MAY 6, 2026", "1", "8", "9", "3"),
        "daily-3": CA_DAILY_3_HTML,
        "daily-derby": _ca_draw_game_html(
            "WED/MAY 6, 2026",
            "First: 09 - Winning Spirit",
            "Second: 01 - Gold Rush",
            "Third: 03 - Hot Shot",
            "Race Time: 1:40.67",
        ),
        "hot-spot": _ca_hot_spot_html(),
    }
    for slug, html in fixture_html.items():
        (fixtures / f"{slug}.html").write_text(html, encoding="utf-8")

    fetch_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "fetch",
            "all",
            "-j",
            "ca",
            "--source-dir",
            str(fixtures),
        ],
    )
    assert fetch_result.exit_code == 0, fetch_result.output

    coverage_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "coverage",
            "-j",
            "ca",
            "--output",
            "json",
        ],
    )
    assert coverage_result.exit_code == 0, coverage_result.output
    coverage_payload = json.loads(coverage_result.output)
    full_statuses = [
        "cataloged",
        "rules_verified",
        "ev_supported",
        "fetch_supported",
        "audit_supported",
        "low_share_supported",
    ]
    assert all(
        game["support_statuses"] == full_statuses
        for game in coverage_payload["games"]
    )

    analyze_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "analyze",
            "all",
            "-j",
            "ca",
            "--output",
            "json",
        ],
    )
    assert analyze_result.exit_code == 0, analyze_result.output
    analyze_payload = json.loads(analyze_result.output)
    assert {game["game_slug"] for game in analyze_payload["games"]} == set(fixture_html)
    assert all(game["options"] for game in analyze_payload["games"])

    low_share_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "low-share",
            "all",
            "-j",
            "ca",
            "--count",
            "1",
            "--candidates",
            "25",
            "--seed",
            "17",
            "--output",
            "json",
        ],
    )
    assert low_share_result.exit_code == 0, low_share_result.output
    low_share_payload = json.loads(low_share_result.output)
    assert {game["game_slug"] for game in low_share_payload["games"]} == set(
        fixture_html
    )

    audit_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "audit",
            "all",
            "all",
            "-j",
            "ca",
            "--output",
            "json",
        ],
    )
    assert audit_result.exit_code == 0, audit_result.output
    audit_payload = json.loads(audit_result.output)
    assert {game["game_slug"] for game in audit_payload["games"]} == set(fixture_html)
    assert all(game["audits"] for game in audit_payload["games"])


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


def test_fetch_california_daily3_backfill_uses_official_past_results_api(
    tmp_path,
):
    data_dir = tmp_path / "data"
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "daily-3.html").write_text(
        _ca_past_winning_numbers_config_html(9, 2),
        encoding="utf-8",
    )
    (fixtures / "daily-3-ca-backfill-1.json").write_text(
        _ca_daily3_backfill_json(),
        encoding="utf-8",
    )

    fetch_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "fetch",
            "daily-3",
            "-j",
            "ca",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )
    assert fetch_result.exit_code == 0, fetch_result.output
    assert "Daily 3" in fetch_result.output
    assert "2 draws" in fetch_result.output
    assert "1 page" in fetch_result.output

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


def test_fetch_california_backfill_stops_at_official_null_page(tmp_path):
    data_dir = tmp_path / "data"
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "daily-4.html").write_text(
        _ca_past_winning_numbers_config_html(14, 101),
        encoding="utf-8",
    )
    (fixtures / "daily-4-ca-backfill-1.json").write_text(
        _ca_daily4_backfill_json(draw_count=100, total_results=101),
        encoding="utf-8",
    )
    (fixtures / "daily-4-ca-backfill-2.json").write_text("null", encoding="utf-8")

    fetch_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "fetch",
            "daily-4",
            "-j",
            "ca",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert fetch_result.exit_code == 0, fetch_result.output
    assert "100 draws" in fetch_result.output
    assert "2 pages" in fetch_result.output


def test_fetch_all_california_backfill_covers_every_supported_adapter(tmp_path):
    data_dir = tmp_path / "data"
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    configs = {
        "powerball": (12, 1),
        "mega-millions": (15, 1),
        "superlotto-plus": (8, 1),
        "fantasy-5": (10, 1),
        "daily-4": (14, 1),
        "daily-3": (9, 2),
        "daily-derby": (11, 1),
    }
    for slug, (game_id, total_results) in configs.items():
        (fixtures / f"{slug}.html").write_text(
            _ca_past_winning_numbers_config_html(game_id, total_results),
            encoding="utf-8",
        )
    (fixtures / "hot-spot.html").write_text(_ca_hot_spot_html(), encoding="utf-8")
    (fixtures / "powerball-ca-backfill-1.json").write_text(
        _ca_backfill_json(
            12,
            "POWERBALL",
            1611,
            "2026-05-06T07:00:00",
            [
                _ca_api_number("18"),
                _ca_api_number("27"),
                _ca_api_number("51"),
                _ca_api_number("65"),
                _ca_api_number("68"),
                _ca_api_number("5", special=True),
            ],
            [_ca_api_prize("5 + Powerball", 0, 30000000)],
        ),
        encoding="utf-8",
    )
    (fixtures / "mega-millions-ca-backfill-1.json").write_text(
        _ca_backfill_json(
            15,
            "MEGA Millions",
            2178,
            "2026-05-05T07:00:00",
            [
                _ca_api_number("12"),
                _ca_api_number("22"),
                _ca_api_number("50"),
                _ca_api_number("51"),
                _ca_api_number("55"),
                _ca_api_number("10", special=True),
            ],
        ),
        encoding="utf-8",
    )
    (fixtures / "superlotto-plus-ca-backfill-1.json").write_text(
        _ca_backfill_json(
            8,
            "SuperLotto Plus",
            4079,
            "2026-05-06T07:00:00",
            [
                _ca_api_number("1"),
                _ca_api_number("3"),
                _ca_api_number("10"),
                _ca_api_number("25"),
                _ca_api_number("46"),
                _ca_api_number("11", special=True),
            ],
        ),
        encoding="utf-8",
    )
    (fixtures / "fantasy-5-ca-backfill-1.json").write_text(
        _ca_backfill_json(
            10,
            "Fantasy 5",
            11869,
            "2026-05-06T07:00:00",
            [
                _ca_api_number("2"),
                _ca_api_number("5"),
                _ca_api_number("13"),
                _ca_api_number("16"),
                _ca_api_number("36"),
            ],
        ),
        encoding="utf-8",
    )
    (fixtures / "daily-4-ca-backfill-1.json").write_text(
        _ca_backfill_json(
            14,
            "Daily 4",
            6562,
            "2026-05-06T07:00:00",
            [
                _ca_api_number("1"),
                _ca_api_number("8"),
                _ca_api_number("9"),
                _ca_api_number("3"),
            ],
        ),
        encoding="utf-8",
    )
    (fixtures / "daily-3-ca-backfill-1.json").write_text(
        _ca_daily3_backfill_json(),
        encoding="utf-8",
    )
    (fixtures / "daily-derby-ca-backfill-1.json").write_text(
        _ca_backfill_json(
            11,
            "Daily Derby",
            10334,
            "2026-05-06T07:00:00",
            [
                _ca_api_number("9", name="Winning Spirit"),
                _ca_api_number("1", name="Gold Rush"),
                _ca_api_number("3", name="Hot Shot"),
                _ca_api_number("0"),
                _ca_api_number("6"),
                _ca_api_number("7"),
            ],
            race_time="1:40.67",
        ),
        encoding="utf-8",
    )
    (fixtures / "hot-spot-ca-backfill-1.json").write_text(
        _ca_hot_spot_backfill_json(),
        encoding="utf-8",
    )

    fetch_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "fetch",
            "all",
            "-j",
            "ca",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )
    assert fetch_result.exit_code == 0, fetch_result.output
    assert "8 games fetched" in fetch_result.output

    draws_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "draws",
            "all",
            "-j",
            "ca",
            "--limit",
            "1",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    draws = {
        game["game_slug"]: game["draws"][0]
        for game in payload["games"]
    }
    assert set(draws) == {
        "powerball",
        "mega-millions",
        "superlotto-plus",
        "fantasy-5",
        "daily-4",
        "daily-3",
        "daily-derby",
        "hot-spot",
    }
    assert draws["powerball"]["winning_number"] == (
        "18, 27, 51, 65, 68, 5 Powerball"
    )
    assert draws["daily-3"]["winning_number"] == "1, 2, 9"
    assert draws["daily-derby"]["winning_number"] == (
        "First: 09 - Winning Spirit, Second: 01 - Gold Rush, "
        "Third: 03 - Hot Shot, Race Time: 1:40.67"
    )
    assert "27 Bulls-eye" in draws["hot-spot"]["winning_number"]
