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


def _delaware_powerball_history_html() -> str:
    return """
    <html>
      <body>
        <table class="table-winning-numbers-search-results">
          <tbody>
            <tr>
              <td data-label="Game">
                Powerball
                <p><strong>Powerball</strong> is indicated in Red.</p>
              </td>
              <td data-label="Date">05/06/26</td>
              <td data-label="Winning Numbers">
                <ul>
                  <li>18</li><li>27</li><li>51</li><li>65</li><li>68</li>
                  <li class="ball-color-red">05</li>
                </ul>
              </td>
            </tr>
            <tr>
              <td data-label="Game">Powerball</td>
              <td data-label="Date">05/04/26</td>
              <td data-label="Winning Numbers">
                <ul>
                  <li>30</li><li>36</li><li>42</li><li>60</li><li>63</li>
                  <li class="ball-color-red">13</li>
                </ul>
              </td>
            </tr>
          </tbody>
        </table>
      </body>
    </html>
    """


def _delaware_mega_millions_history_html() -> str:
    return """
    <html>
      <body>
        <table class="table-winning-numbers-search-results">
          <tbody>
            <tr>
              <td data-label="Game">
                Mega Millions
                <p><strong>Mega Ball</strong> is indicated in Gold.</p>
              </td>
              <td data-label="Date">05/05/26</td>
              <td data-label="Winning Numbers">
                <ul>
                  <li>12</li><li>22</li><li>50</li><li>51</li><li>55</li>
                  <li class="ball-color-yellow-orange">10</li>
                </ul>
              </td>
            </tr>
          </tbody>
        </table>
      </body>
    </html>
    """


def _georgia_powerball_history_json() -> str:
    return json.dumps(
        {
            "draws": [
                {
                    "gameName": "POWERBALL",
                    "id": "1942",
                    "status": "CLOSED",
                    "closeTime": 1777946375000,
                    "results": [
                        {
                            "primary": [
                                "30",
                                "36",
                                "42",
                                "60",
                                "63",
                                "M-02",
                                "PB-13",
                            ],
                            "drawType": "Regular",
                        }
                    ],
                },
                {
                    "gameName": "POWERBALL",
                    "id": "1943",
                    "status": "CLOSED",
                    "closeTime": 1778119175000,
                    "results": [
                        {
                            "primary": [
                                "18",
                                "27",
                                "51",
                                "65",
                                "68",
                                "M-03",
                                "PB-05",
                            ],
                            "drawType": "Regular",
                        }
                    ],
                },
                {
                    "gameName": "POWERBALL",
                    "id": "1944",
                    "status": "OPEN",
                    "closeTime": 1778378375000,
                },
            ]
        }
    )


def _georgia_mega_millions_history_json() -> str:
    return json.dumps(
        {
            "draws": [
                {
                    "gameName": "MEGA MILLIONS",
                    "id": "3022",
                    "status": "CLOSED",
                    "closeTime": 1778035505000,
                    "results": [
                        {
                            "primary": [
                                "12",
                                "22",
                                "50",
                                "51",
                                "55",
                                "M-00",
                                "MB-10",
                            ],
                            "drawType": "Regular",
                        }
                    ],
                }
            ]
        }
    )


def _idaho_powerball_history_html() -> str:
    return """
    <html>
      <body>
        <div id="tab4">
          <table>
            <caption>Winning Numbers</caption>
            <tbody>
              <tr>
                <td data-title="Date">05/06/26</td>
                <td data-title="Winning Numbers">
                  <ul class="list-numbers list-numbers--bordered Powerball">
                    <li>18</li><li>27</li><li>51</li><li>65</li><li>68</li>
                    <li class="ball_red">5</li>
                  </ul>
                </td>
              </tr>
              <tr>
                <td data-title="Date">05/04/26</td>
                <td data-title="Winning Numbers">
                  <ul class="list-numbers list-numbers--bordered Powerball">
                    <li>30</li><li>36</li><li>42</li><li>60</li><li>63</li>
                    <li class="ball_red">13</li>
                  </ul>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </body>
    </html>
    """


def _idaho_mega_millions_history_html() -> str:
    return """
    <html>
      <body>
        <div id="tab4">
          <table>
            <caption>Winning Numbers</caption>
            <tbody>
              <tr>
                <td data-title="Date">05/05/26</td>
                <td data-title="Winning Numbers">
                  <ul class="list-numbers list-numbers--bordered MegaMillions">
                    <li>12</li><li>22</li><li>50</li><li>51</li><li>55</li>
                    <li class="ball_yellow">10</li>
                  </ul>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </body>
    </html>
    """


def _illinois_powerball_results_html() -> str:
    return """
    <html>
      <body>
        <h1>Powerball Draw Results</h1>
        <ul>
          <li><a>Wednesday May 6, 2026   18  27  51  65  68  5  x3</a></li>
          <li><a>Monday May 4, 2026   30  36  42  60  63  13  x2</a></li>
        </ul>
      </body>
    </html>
    """


def _illinois_mega_millions_results_html() -> str:
    return """
    <html>
      <body>
        <h1>Mega Millions Draw Results</h1>
        <ul>
          <li><a>Tuesday May 5, 2026   12  22  50  51  55  10</a></li>
        </ul>
      </body>
    </html>
    """


def _indiana_powerball_draw_page_html() -> str:
    return """
    <html>
      <body>
        <section class="drawing-numbers">
          <h2>Winning Numbers</h2>
          <span class="font-weight-bold">Powerball</span>
          <span class="sub-title">Wednesday, May 6th</span>
          <div class="numbers-container">
            <span class="winning-number">18</span>
            <span class="winning-number">27</span>
            <span class="winning-number">51</span>
            <span class="winning-number">65</span>
            <span class="winning-number">68</span>
            <span class="winning-number bonus-number">05</span>
          </div>
          <span class="drawing-sub-title">Power Play: 3x</span>
          <span class="font-weight-bold">Double Play</span>
          <span class="sub-title">Wednesday, May 6th</span>
          <div class="numbers-container">
            <span class="winning-number">04</span>
            <span class="winning-number">21</span>
            <span class="winning-number">36</span>
            <span class="winning-number">48</span>
            <span class="winning-number">69</span>
            <span class="winning-number bonus-number">05</span>
          </div>
        </section>
      </body>
    </html>
    """


def _indiana_mega_millions_draw_page_html() -> str:
    return """
    <html>
      <body>
        <section class="drawing-numbers">
          <h2>Winning Numbers</h2>
          <span class="sub-title">Tuesday, May 5th</span>
          <div class="numbers-container">
            <span class="winning-number">12</span>
            <span class="winning-number">22</span>
            <span class="winning-number">50</span>
            <span class="winning-number">51</span>
            <span class="winning-number">55</span>
            <span class="winning-number bonus-number">10</span>
          </div>
        </section>
      </body>
    </html>
    """


def _iowa_winning_numbers_html() -> str:
    return """
    <html>
      <body>
        <h2>Latest Winning Numbers</h2>
        <h4><a>Powerball</a></h4>
        <p>Drawing Date: 5/6: 18 - 27 - 51 - 65 - 68&nbsp;&nbsp; 5 Power Play: 3</p>
        <p>DOUBLE PLAY</p>
        <p>4 - 21 - 36 - 48 - 69&nbsp;&nbsp; 5</p>
        <h4><a>Mega Millions</a></h4>
        <p>Drawing Date: 5/5: 12 - 22 - 50 - 51 - 55&nbsp; 10</p>
      </body>
    </html>
    """


def _kentucky_powerball_history_json() -> str:
    return json.dumps(
        {
            "GAME_NUMBER": [12],
            "DRAW_HISTORY": [
                {
                    "DRAW_DATE": 1778068800000,
                    "DRAW_VALUES": [
                        {"DRAW_NUMBER_POSITION": 1, "DRAW_VALUE": 18},
                        {"DRAW_NUMBER_POSITION": 2, "DRAW_VALUE": 27},
                        {"DRAW_NUMBER_POSITION": 3, "DRAW_VALUE": 51},
                        {"DRAW_NUMBER_POSITION": 4, "DRAW_VALUE": 65},
                        {"DRAW_NUMBER_POSITION": 5, "DRAW_VALUE": 68},
                    ],
                    "SPECIAL_ARGS": {"POWERBALL": 5, "POWERPLAY": 3},
                },
                {
                    "DRAW_DATE": 1777896000000,
                    "DRAW_VALUES": [
                        {"DRAW_NUMBER_POSITION": 1, "DRAW_VALUE": 30},
                        {"DRAW_NUMBER_POSITION": 2, "DRAW_VALUE": 36},
                        {"DRAW_NUMBER_POSITION": 3, "DRAW_VALUE": 42},
                        {"DRAW_NUMBER_POSITION": 4, "DRAW_VALUE": 60},
                        {"DRAW_NUMBER_POSITION": 5, "DRAW_VALUE": 63},
                    ],
                    "SPECIAL_ARGS": {"POWERBALL": 13, "POWERPLAY": 2},
                },
            ],
        }
    )


def _kentucky_mega_millions_history_json() -> str:
    return json.dumps(
        {
            "GAME_NUMBER": [26],
            "DRAW_HISTORY": [
                {
                    "DRAW_DATE": 1777982400000,
                    "DRAW_VALUES": [
                        {"DRAW_NUMBER_POSITION": 1, "DRAW_VALUE": 12},
                        {"DRAW_NUMBER_POSITION": 2, "DRAW_VALUE": 22},
                        {"DRAW_NUMBER_POSITION": 3, "DRAW_VALUE": 50},
                        {"DRAW_NUMBER_POSITION": 4, "DRAW_VALUE": 51},
                        {"DRAW_NUMBER_POSITION": 5, "DRAW_VALUE": 55},
                    ],
                    "SPECIAL_ARGS": {"MEGABALL": 10, "MULTIPLIER": 0},
                }
            ],
        }
    )


def _louisiana_powerball_latest_draw_html() -> str:
    return """
    <html>
      <body>
        <main>
          <h1>Powerball</h1>
          <a>View Latest Draw: May 06, 2026</a>
          <ul>
            <li>18</li><li>27</li><li>51</li><li>65</li><li>68</li><li>05</li>
          </ul>
          <p>3x Power Play</p>
        </main>
      </body>
    </html>
    """


def _louisiana_mega_millions_latest_draw_html() -> str:
    return """
    <html>
      <body>
        <main>
          <h1>Mega Millions</h1>
          <a>View Latest Draw: May 05, 2026</a>
          <ul>
            <li>12</li><li>22</li><li>50</li><li>51</li><li>55</li><li>10</li>
          </ul>
        </main>
      </body>
    </html>
    """


def _maine_home_page_html() -> str:
    return """
    <html>
      <body>
        <img alt="Powerball">
        <h2>Wednesday 05/06/2026</h2>
        <p>18 27 51 65 68 PB 5 Power Play x 3</p>
        <img alt="Mega Millions">
        <h2>Tuesday 05/05/2026</h2>
        <p>12 22 50 51 55 MB 10</p>
      </body>
    </html>
    """


def _maryland_winning_numbers_html() -> str:
    return """
    <html>
      <body>
        <h4>Mega Millions</h4>
        <table>
          <tr>
            <td>05/05/26</td>
            <td><ul><li>12</li><li>22</li><li>50</li><li>51</li><li>55</li></ul></td>
            <td><ul><li>10</li></ul></td>
            <td>N/A</td>
          </tr>
        </table>
        <h4>Powerball</h4>
        <table>
          <tr>
            <td>05/06/26</td>
            <td><ul><li>18</li><li>27</li><li>51</li><li>65</li><li>68</li></ul></td>
            <td><ul><li>05</li></ul></td>
            <td>x3</td>
          </tr>
          <tr>
            <td>05/04/26</td>
            <td><ul><li>30</li><li>36</li><li>42</li><li>60</li><li>63</li></ul></td>
            <td><ul><li>13</li></ul></td>
            <td>x2</td>
          </tr>
        </table>
      </body>
    </html>
    """


def _massachusetts_draw_results_json() -> str:
    return json.dumps(
        {
            "winningNumbers": [
                {
                    "gameIdentifier": "powerball",
                    "drawDate": "2026-05-06",
                    "winningNumbers": [18, 27, 51, 65, 68],
                    "extras": {"powerball": 5, "powerplay": 3},
                    "status": "COMPLETE",
                },
                {
                    "gameIdentifier": "mega_millions",
                    "drawDate": "2026-05-05",
                    "winningNumbers": [12, 22, 50, 51, 55],
                    "extras": {"megaball": 10},
                    "status": "COMPLETE",
                },
            ]
        }
    )


def _michigan_draw_history_json() -> str:
    return json.dumps(
        {
            "data": {
                "gameByCode": {
                    "logicalGameIdentifier": "POWERBALL",
                    "drawResultsBetweenDates": [
                        {
                            "drawDate": "2026-05-06T04:00:00.000Z",
                            "drawSequence": 1,
                            "hasPayoutData": True,
                            "isBonusDraw": False,
                            "winningNumbers": {
                                "drawNumbers": [18, 27, 51, 65, 68],
                                "powerball": 5,
                                "powerplay": 3,
                                "megaball": None,
                                "megaplier": None,
                            },
                        },
                        {
                            "drawDate": "2026-05-06T04:00:00.000Z",
                            "drawSequence": 2,
                            "hasPayoutData": True,
                            "isBonusDraw": False,
                            "winningNumbers": {
                                "drawNumbers": [4, 21, 36, 48, 69],
                                "powerball": 5,
                                "powerplay": 0,
                                "megaball": None,
                                "megaplier": None,
                            },
                        },
                        {
                            "drawDate": "2026-05-05T04:00:00.000Z",
                            "drawSequence": 1,
                            "hasPayoutData": True,
                            "isBonusDraw": False,
                            "winningNumbers": {
                                "drawNumbers": [12, 22, 50, 51, 55],
                                "powerball": None,
                                "powerplay": None,
                                "megaball": 10,
                                "megaplier": None,
                            },
                        },
                    ],
                }
            }
        }
    )


def _minnesota_winning_numbers_html() -> str:
    return """
    <html>
      <body>
        <figure class="card card--lottery card--winning-numbers">
          <h4>Powerball</h4>
          <ul class="lottery-number-list" aria-label="Winning numbers">
            <li class="lottery-number-list-item">18</li>
            <li class="lottery-number-list-item">27</li>
            <li class="lottery-number-list-item">51</li>
            <li class="lottery-number-list-item">65</li>
            <li class="lottery-number-list-item">68</li>
            <li class="lottery-number-list-item power-ball">5</li>
            <li class="multiplier">x3</li>
          </ul>
          <p class="lottery-drawing"><span>May 6th, 2026</span></p>
        </figure>
        <figure class="card card--lottery card--winning-numbers">
          <h4>Mega Millions</h4>
          <ul class="lottery-number-list" aria-label="Winning numbers">
            <li class="lottery-number-list-item">12</li>
            <li class="lottery-number-list-item">22</li>
            <li class="lottery-number-list-item">50</li>
            <li class="lottery-number-list-item">51</li>
            <li class="lottery-number-list-item">55</li>
            <li class="lottery-number-list-item power-ball">10</li>
          </ul>
          <p class="lottery-drawing"><span>May 5th, 2026</span></p>
        </figure>
      </body>
    </html>
    """


def _mississippi_home_page_html() -> str:
    return """
    <html>
      <body>
        <div class="drawgamewrap powerballwrap">
          <a href="https://www.mslottery.com/games/powerball/">Powerball</a>
          <p class="latestdraw">05/06 Winning Numbers</p>
          <div class="lotto-numbers">
            <span><i>18</i></span><span><i>27</i></span>
            <span><i>51</i></span><span><i>65</i></span>
            <span><i>68</i></span><span><i class="powerball">5</i></span>
          </div>
        </div>
        <div class="drawgamewrap megamillionswrap">
          <a href="https://www.mslottery.com/games/mega-millions/">Mega Millions</a>
          <p class="latestdraw">05/05 Winning Numbers</p>
          <div class="lotto-numbers">
            <span><i>12</i></span><span><i>22</i></span>
            <span><i>50</i></span><span><i>51</i></span>
            <span><i>55</i></span><span><i class="powerball">10</i></span>
          </div>
        </div>
      </body>
    </html>
    """


def _missouri_winning_numbers_html() -> str:
    return """
    <html>
      <body>
        <table class="table table_game">
          <tbody>
            <tr>
              <td>2026-05-06</td>
              <td>
                <div class="num-list">
                  <div class="num num_small">18</div>
                  <div class="num num_small">27</div>
                  <div class="num num_small">51</div>
                  <div class="num num_small">65</div>
                  <div class="num num_small">68</div>
                  <div class="num num_small num_red">5</div>
                </div>
              </td>
            </tr>
            <tr>
              <td>2026-05-05</td>
              <td>
                <div class="num-list">
                  <div class="num num_small">12</div>
                  <div class="num num_small">22</div>
                  <div class="num num_small">50</div>
                  <div class="num num_small">51</div>
                  <div class="num num_small">55</div>
                  <div class="num num_small num_yellow">10</div>
                </div>
              </td>
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


def test_fetch_reports_kansas_powerball_result_history_blocker(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "fetch",
            "powerball",
            "-j",
            "ks",
            "--backfill",
        ],
    )

    assert result.exit_code != 0
    assert "fetch support pending for game: powerball" in result.output


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


def test_fetch_delaware_powerball_backfill_reads_official_history_fixture(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball-de-backfill.html").write_text(
        _delaware_powerball_history_html(),
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
            "de",
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
            "de",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "de",
            "draw_date": "Wed, May 06, 2026",
            "winning_number": "18, 27, 51, 65, 68, 05 Powerball",
        },
        {
            "jurisdiction_code": "de",
            "draw_date": "Mon, May 04, 2026",
            "winning_number": "30, 36, 42, 60, 63, 13 Powerball",
        },
    ]


def test_fetch_delaware_mega_millions_backfill_reads_official_history_fixture(
    tmp_path,
):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "mega-millions-de-backfill.html").write_text(
        _delaware_mega_millions_history_html(),
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
            "de",
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
            "de",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "de",
            "draw_date": "Tue, May 05, 2026",
            "winning_number": "12, 22, 50, 51, 55, 10 Mega Ball",
        }
    ]


def test_fetch_georgia_powerball_backfill_reads_official_json_fixture(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball-ga-backfill.json").write_text(
        _georgia_powerball_history_json(),
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
            "ga",
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
            "ga",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "ga",
            "draw_date": "Wed, May 06, 2026",
            "winning_number": "18, 27, 51, 65, 68, 05 Powerball",
        },
        {
            "jurisdiction_code": "ga",
            "draw_date": "Mon, May 04, 2026",
            "winning_number": "30, 36, 42, 60, 63, 13 Powerball",
        },
    ]


def test_fetch_georgia_mega_millions_backfill_reads_official_json_fixture(
    tmp_path,
):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "mega-millions-ga-backfill.json").write_text(
        _georgia_mega_millions_history_json(),
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
            "ga",
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
            "ga",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "ga",
            "draw_date": "Tue, May 05, 2026",
            "winning_number": "12, 22, 50, 51, 55, 10 Mega Ball",
        }
    ]


def test_fetch_idaho_powerball_backfill_reads_official_draw_page_fixture(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball-id-backfill.html").write_text(
        _idaho_powerball_history_html(),
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
            "id",
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
            "id",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "id",
            "draw_date": "Wed, May 06, 2026",
            "winning_number": "18, 27, 51, 65, 68, 5 Powerball",
        },
        {
            "jurisdiction_code": "id",
            "draw_date": "Mon, May 04, 2026",
            "winning_number": "30, 36, 42, 60, 63, 13 Powerball",
        },
    ]


def test_fetch_idaho_mega_millions_backfill_reads_official_draw_page_fixture(
    tmp_path,
):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "mega-millions-id-backfill.html").write_text(
        _idaho_mega_millions_history_html(),
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
            "id",
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
            "id",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "id",
            "draw_date": "Tue, May 05, 2026",
            "winning_number": "12, 22, 50, 51, 55, 10 Mega Ball",
        }
    ]


def test_fetch_illinois_powerball_backfill_reads_official_results_fixture(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball-il-backfill.html").write_text(
        _illinois_powerball_results_html(),
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
            "il",
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
            "il",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "il",
            "draw_date": "Wed, May 06, 2026",
            "winning_number": "18, 27, 51, 65, 68, 5 Powerball",
        },
        {
            "jurisdiction_code": "il",
            "draw_date": "Mon, May 04, 2026",
            "winning_number": "30, 36, 42, 60, 63, 13 Powerball",
        },
    ]


def test_fetch_illinois_mega_millions_backfill_reads_official_results_fixture(
    tmp_path,
):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "mega-millions-il-backfill.html").write_text(
        _illinois_mega_millions_results_html(),
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
            "il",
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
            "il",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "il",
            "draw_date": "Tue, May 05, 2026",
            "winning_number": "12, 22, 50, 51, 55, 10 Mega Ball",
        }
    ]


def test_fetch_indiana_powerball_backfill_reads_official_draw_page_fixture(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball-in-backfill.html").write_text(
        _indiana_powerball_draw_page_html(),
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
            "in",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Powerball" in result.output
    assert "1 draw" in result.output
    assert "1 page" in result.output

    draws_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "draws",
            "powerball",
            "-j",
            "in",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "in",
            "draw_date": "Wed, May 06, 2026",
            "winning_number": "18, 27, 51, 65, 68, 05 Powerball",
        }
    ]


def test_fetch_indiana_mega_millions_backfill_reads_official_draw_page_fixture(
    tmp_path,
):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "mega-millions-in-backfill.html").write_text(
        _indiana_mega_millions_draw_page_html(),
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
            "in",
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
            "in",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "in",
            "draw_date": "Tue, May 05, 2026",
            "winning_number": "12, 22, 50, 51, 55, 10 Mega Ball",
        }
    ]


def test_fetch_iowa_powerball_backfill_reads_official_winning_numbers_fixture(
    tmp_path,
):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball-ia-backfill.html").write_text(
        _iowa_winning_numbers_html(),
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
            "ia",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Powerball" in result.output
    assert "1 draw" in result.output
    assert "1 page" in result.output

    draws_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "draws",
            "powerball",
            "-j",
            "ia",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "ia",
            "draw_date": "Wed, May 06, 2026",
            "winning_number": "18, 27, 51, 65, 68, 5 Powerball",
        }
    ]


def test_fetch_iowa_mega_millions_backfill_reads_official_winning_numbers_fixture(
    tmp_path,
):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "mega-millions-ia-backfill.html").write_text(
        _iowa_winning_numbers_html(),
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
            "ia",
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
            "ia",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "ia",
            "draw_date": "Tue, May 05, 2026",
            "winning_number": "12, 22, 50, 51, 55, 10 Mega Ball",
        }
    ]


def test_fetch_kentucky_powerball_backfill_reads_official_json_fixture(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball-ky-backfill.json").write_text(
        _kentucky_powerball_history_json(),
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
            "ky",
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
            "ky",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "ky",
            "draw_date": "Wed, May 06, 2026",
            "winning_number": "18, 27, 51, 65, 68, 5 Powerball",
        },
        {
            "jurisdiction_code": "ky",
            "draw_date": "Mon, May 04, 2026",
            "winning_number": "30, 36, 42, 60, 63, 13 Powerball",
        },
    ]


def test_fetch_kentucky_mega_millions_backfill_reads_official_json_fixture(
    tmp_path,
):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "mega-millions-ky-backfill.json").write_text(
        _kentucky_mega_millions_history_json(),
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
            "ky",
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
            "ky",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "ky",
            "draw_date": "Tue, May 05, 2026",
            "winning_number": "12, 22, 50, 51, 55, 10 Mega Ball",
        }
    ]


def test_fetch_louisiana_powerball_backfill_reads_official_latest_draw_fixture(
    tmp_path,
):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball-la-backfill.html").write_text(
        _louisiana_powerball_latest_draw_html(),
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
            "la",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Powerball" in result.output
    assert "1 draw" in result.output
    assert "1 page" in result.output

    draws_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "draws",
            "powerball",
            "-j",
            "la",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "la",
            "draw_date": "Wed, May 06, 2026",
            "winning_number": "18, 27, 51, 65, 68, 05 Powerball",
        }
    ]


def test_fetch_louisiana_mega_millions_backfill_reads_official_latest_draw_fixture(
    tmp_path,
):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "mega-millions-la-backfill.html").write_text(
        _louisiana_mega_millions_latest_draw_html(),
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
            "la",
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
            "la",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "la",
            "draw_date": "Tue, May 05, 2026",
            "winning_number": "12, 22, 50, 51, 55, 10 Mega Ball",
        }
    ]


def test_fetch_maine_powerball_backfill_reads_official_home_page_fixture(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball-me-backfill.html").write_text(
        _maine_home_page_html(),
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
            "me",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Powerball" in result.output
    assert "1 draw" in result.output
    assert "1 page" in result.output

    draws_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "draws",
            "powerball",
            "-j",
            "me",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "me",
            "draw_date": "Wed, May 06, 2026",
            "winning_number": "18, 27, 51, 65, 68, 5 Powerball",
        }
    ]


def test_fetch_maine_mega_millions_backfill_reads_official_home_page_fixture(
    tmp_path,
):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "mega-millions-me-backfill.html").write_text(
        _maine_home_page_html(),
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
            "me",
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
            "me",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "me",
            "draw_date": "Tue, May 05, 2026",
            "winning_number": "12, 22, 50, 51, 55, 10 Mega Ball",
        }
    ]


def test_fetch_maryland_powerball_backfill_reads_official_results_fixture(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball-md-backfill.html").write_text(
        _maryland_winning_numbers_html(),
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
            "md",
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
            "md",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "md",
            "draw_date": "Wed, May 06, 2026",
            "winning_number": "18, 27, 51, 65, 68, 05 Powerball",
        },
        {
            "jurisdiction_code": "md",
            "draw_date": "Mon, May 04, 2026",
            "winning_number": "30, 36, 42, 60, 63, 13 Powerball",
        },
    ]


def test_fetch_maryland_mega_millions_backfill_reads_official_results_fixture(
    tmp_path,
):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "mega-millions-md-backfill.html").write_text(
        _maryland_winning_numbers_html(),
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
            "md",
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
            "md",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "md",
            "draw_date": "Tue, May 05, 2026",
            "winning_number": "12, 22, 50, 51, 55, 10 Mega Ball",
        }
    ]


def test_fetch_massachusetts_powerball_backfill_reads_official_json_fixture(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball-ma-backfill.json").write_text(
        _massachusetts_draw_results_json(),
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
            "ma",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Powerball" in result.output
    assert "1 draw" in result.output
    assert "1 page" in result.output

    draws_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "draws",
            "powerball",
            "-j",
            "ma",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "ma",
            "draw_date": "Wed, May 06, 2026",
            "winning_number": "18, 27, 51, 65, 68, 5 Powerball",
        }
    ]


def test_fetch_massachusetts_mega_millions_backfill_reads_official_json_fixture(
    tmp_path,
):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "mega-millions-ma-backfill.json").write_text(
        _massachusetts_draw_results_json(),
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
            "ma",
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
            "ma",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "ma",
            "draw_date": "Tue, May 05, 2026",
            "winning_number": "12, 22, 50, 51, 55, 10 Mega Ball",
        }
    ]


def test_fetch_michigan_powerball_backfill_reads_official_graphql_fixture(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball-mi-backfill.json").write_text(
        _michigan_draw_history_json(),
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
            "mi",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Powerball" in result.output
    assert "1 draw" in result.output
    assert "1 page" in result.output

    draws_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "draws",
            "powerball",
            "-j",
            "mi",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "mi",
            "draw_date": "Wed, May 06, 2026",
            "winning_number": "18, 27, 51, 65, 68, 5 Powerball",
        }
    ]


def test_fetch_michigan_mega_millions_backfill_reads_official_graphql_fixture(
    tmp_path,
):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "mega-millions-mi-backfill.json").write_text(
        _michigan_draw_history_json(),
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
            "mi",
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
            "mi",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "mi",
            "draw_date": "Tue, May 05, 2026",
            "winning_number": "12, 22, 50, 51, 55, 10 Mega Ball",
        }
    ]


def test_fetch_minnesota_powerball_backfill_reads_official_page_fixture(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball-mn-backfill.html").write_text(
        _minnesota_winning_numbers_html(),
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
            "mn",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Powerball" in result.output
    assert "1 draw" in result.output
    assert "1 page" in result.output

    draws_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "draws",
            "powerball",
            "-j",
            "mn",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "mn",
            "draw_date": "Wed, May 06, 2026",
            "winning_number": "18, 27, 51, 65, 68, 5 Powerball",
        }
    ]


def test_fetch_minnesota_mega_millions_backfill_reads_official_page_fixture(
    tmp_path,
):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "mega-millions-mn-backfill.html").write_text(
        _minnesota_winning_numbers_html(),
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
            "mn",
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
            "mn",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "mn",
            "draw_date": "Tue, May 05, 2026",
            "winning_number": "12, 22, 50, 51, 55, 10 Mega Ball",
        }
    ]


def test_fetch_mississippi_powerball_backfill_reads_official_home_fixture(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball-ms-backfill.html").write_text(
        _mississippi_home_page_html(),
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
            "ms",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Powerball" in result.output
    assert "1 draw" in result.output
    assert "1 page" in result.output

    draws_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "draws",
            "powerball",
            "-j",
            "ms",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "ms",
            "draw_date": "Wed, May 06, 2026",
            "winning_number": "18, 27, 51, 65, 68, 5 Powerball",
        }
    ]


def test_fetch_mississippi_mega_millions_backfill_reads_official_home_fixture(
    tmp_path,
):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "mega-millions-ms-backfill.html").write_text(
        _mississippi_home_page_html(),
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
            "ms",
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
            "ms",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "ms",
            "draw_date": "Tue, May 05, 2026",
            "winning_number": "12, 22, 50, 51, 55, 10 Mega Ball",
        }
    ]


def test_fetch_missouri_powerball_backfill_reads_official_page_fixture(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "powerball-mo-backfill.html").write_text(
        _missouri_winning_numbers_html(),
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
            "mo",
            "--backfill",
            "--source-dir",
            str(fixtures),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Powerball" in result.output
    assert "1 draw" in result.output
    assert "1 page" in result.output

    draws_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "data"),
            "draws",
            "powerball",
            "-j",
            "mo",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "mo",
            "draw_date": "Wed, May 06, 2026",
            "winning_number": "18, 27, 51, 65, 68, 5 Powerball",
        }
    ]


def test_fetch_missouri_mega_millions_backfill_reads_official_page_fixture(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "mega-millions-mo-backfill.html").write_text(
        _missouri_winning_numbers_html(),
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
            "mo",
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
            "mo",
            "--output",
            "json",
        ],
    )

    assert draws_result.exit_code == 0, draws_result.output
    payload = json.loads(draws_result.output)
    assert payload["games"][0]["draws"] == [
        {
            "jurisdiction_code": "mo",
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
