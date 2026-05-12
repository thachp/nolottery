import json

import pytest
from typer.testing import CliRunner

from nolottery import db
from nolottery.cli import app
from nolottery.low_share import generate_low_share_options


runner = CliRunner()


def test_low_share_powerball_returns_seeded_json(tmp_path):
    args = [
        "--data-dir",
        str(tmp_path),
        "low-share",
        "powerball",
        "--count",
        "2",
        "--candidates",
        "20",
        "--seed",
        "7",
        "--output",
        "json",
    ]

    first = runner.invoke(app, args)
    second = runner.invoke(app, args)

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert json.loads(first.output) == json.loads(second.output)
    payload = json.loads(first.output)
    assert payload["seed"] == 7
    assert payload["games"][0]["game_slug"] == "powerball"
    picks = payload["games"][0]["options"][0]["picks"]
    assert len(picks) == 2
    assert picks[0]["method"] == "low-share-heuristic-no-odds-edge"
    assert "low_share_score" in picks[0]
    assert len(picks[0]["reasons"]) >= 2
    assert picks[0]["label"].startswith("White:")


def test_low_share_daily_keno_generates_multiple_picks_for_every_variation(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "low-share",
            "daily-keno",
            "--count",
            "2",
            "--candidates",
            "50",
            "--seed",
            "3",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    options = payload["games"][0]["options"]
    assert len(options) == 10
    assert {option["option_slug"] for option in options} == {
        "1-spot",
        "2-spot",
        "3-spot",
        "4-spot",
        "5-spot",
        "6-spot",
        "7-spot",
        "8-spot",
        "9-spot",
        "10-spot",
    }
    assert all(len(option["picks"]) == 2 for option in options)


def test_low_share_supports_florida_and_new_york_digit_games(tmp_path):
    for jurisdiction, game_slug, digits in [
        ("fl", "florida-pick-2", 2),
        ("fl", "florida-pick-3", 3),
        ("fl", "florida-pick-4", 4),
        ("fl", "florida-pick-5", 5),
        ("ny", "numbers", 3),
        ("ny", "win-4", 4),
    ]:
        result = runner.invoke(
            app,
            [
                "--data-dir",
                str(tmp_path / jurisdiction),
                "low-share",
                game_slug,
                "-j",
                jurisdiction,
                "--count",
                "2",
                "--candidates",
                "20",
                "--seed",
                "4",
                "--output",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        picks = payload["games"][0]["options"][0]["picks"]
        assert len(picks) == 2
        assert all(len(pick["numbers"]) == digits for pick in picks)


def test_low_share_supports_active_idaho_draw_games(tmp_path):
    for game_slug, number_count in [
        ("idaho-cash", 5),
        ("idaho-pick-3", 3),
        ("idaho-pick-4", 4),
        ("lotto-america", 6),
        ("millionaire-for-life", 6),
    ]:
        result = runner.invoke(
            app,
            [
                "--data-dir",
                str(tmp_path / game_slug),
                "low-share",
                game_slug,
                "-j",
                "id",
                "--count",
                "2",
                "--candidates",
                "20",
                "--seed",
                "4",
                "--output",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        picks = payload["games"][0]["options"][0]["picks"]
        assert len(picks) == 2
        assert all(len(pick["numbers"]) == number_count for pick in picks)


def test_low_share_supports_active_oregon_draw_games(tmp_path):
    for game_slug, expected_options, first_option_count in [
        ("oregon-megabucks", {"standard"}, 6),
        (
            "oregon-keno",
            {
                "1-spot",
                "2-spot",
                "3-spot",
                "4-spot",
                "5-spot",
                "6-spot",
                "7-spot",
                "8-spot",
                "9-spot",
                "10-spot",
            },
            1,
        ),
        ("oregon-cash-pop", {"one-pop"}, 1),
        ("oregon-pick-4", {"straight-1"}, 4),
        ("oregon-win-for-life", {"standard"}, 4),
    ]:
        result = runner.invoke(
            app,
            [
                "--data-dir",
                str(tmp_path / game_slug),
                "low-share",
                game_slug,
                "-j",
                "or",
                "--count",
                "2",
                "--candidates",
                "50",
                "--seed",
                "4",
                "--output",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        options = payload["games"][0]["options"]
        assert {option["option_slug"] for option in options} == expected_options
        picks = options[0]["picks"]
        assert len(picks) == 2
        assert all(len(pick["numbers"]) == first_option_count for pick in picks)


def test_low_share_supports_active_colorado_draw_games(tmp_path):
    for game_slug, first_option_count in [
        ("colorado-lotto-plus", 6),
        ("colorado-cash-5", 5),
        ("colorado-pick-3", 3),
        ("millionaire-for-life", 6),
    ]:
        result = runner.invoke(
            app,
            [
                "--data-dir",
                str(tmp_path / game_slug),
                "low-share",
                game_slug,
                "-j",
                "co",
                "--count",
                "2",
                "--candidates",
                "50",
                "--seed",
                "4",
                "--output",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        picks = payload["games"][0]["options"][0]["picks"]
        assert len(picks) == 2
        assert all(len(pick["numbers"]) == first_option_count for pick in picks)


def test_low_share_supports_active_texas_local_draw_games(tmp_path):
    for game_slug, first_option_count in [
        ("texas-lotto", 6),
        ("texas-two-step", 5),
        ("texas-cash-five", 5),
        ("texas-all-or-nothing", 12),
        ("texas-pick-3", 3),
        ("texas-daily-4", 4),
    ]:
        result = runner.invoke(
            app,
            [
                "--data-dir",
                str(tmp_path / game_slug),
                "low-share",
                game_slug,
                "-j",
                "tx",
                "--count",
                "2",
                "--candidates",
                "50",
                "--seed",
                "4",
                "--output",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        picks = payload["games"][0]["options"][0]["picks"]
        assert len(picks) == 2
        assert all(len(pick["numbers"]) == first_option_count for pick in picks)


def test_low_share_supports_active_nebraska_local_draw_games(tmp_path):
    for game_slug, first_option_count in [
        ("lotto-america", 6),
        ("lucky-for-life", 6),
        ("millionaire-for-life", 6),
        ("nebraska-pick-5", 5),
        ("nebraska-pick-4", 4),
        ("nebraska-pick-3", 3),
        ("nebraska-myday", 3),
        ("nebraska-2by2", 4),
    ]:
        result = runner.invoke(
            app,
            [
                "--data-dir",
                str(tmp_path / game_slug),
                "low-share",
                game_slug,
                "-j",
                "ne",
                "--count",
                "2",
                "--candidates",
                "50",
                "--seed",
                "4",
                "--output",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        picks = payload["games"][0]["options"][0]["picks"]
        assert len(picks) == 2
        assert all(len(pick["numbers"]) == first_option_count for pick in picks)


def test_low_share_supports_arkansas_lucky_for_life_lucky_ball(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "low-share",
            "lucky-for-life",
            "-j",
            "ar",
            "--count",
            "1",
            "--candidates",
            "5",
            "--seed",
            "4",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    pick = payload["games"][0]["options"][0]["picks"][0]
    assert pick["numbers"] == [4, 15, 19, 34, 35, 12]
    assert pick["label"] == "White: 4, 15, 19, 34, 35; Lucky Ball: 12"
    assert "bonus ball avoids popular numbers" in pick["reasons"]


def test_low_share_supports_arkansas_millionaire_for_life(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "low-share",
            "millionaire-for-life",
            "-j",
            "ar",
            "--count",
            "1",
            "--candidates",
            "5",
            "--seed",
            "4",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    pick = payload["games"][0]["options"][0]["picks"][0]
    assert pick["numbers"] == [4, 15, 19, 49, 52, 5]
    assert pick["label"] == "White: 4, 15, 19, 49, 52; Life Ball: 5"
    assert "bonus ball avoids popular numbers" in pick["reasons"]


@pytest.mark.parametrize(
    ("game_slug", "expected_length"),
    [
        ("lucky-for-life", 6),
        ("millionaire-for-life", 6),
    ],
)
def test_low_share_supports_massachusetts_life_games(
    tmp_path,
    game_slug,
    expected_length,
):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "low-share",
            game_slug,
            "-j",
            "ma",
            "--count",
            "1",
            "--candidates",
            "5",
            "--seed",
            "4",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    pick = payload["games"][0]["options"][0]["picks"][0]
    assert len(pick["numbers"]) == expected_length
    assert pick["label"] != "n/a"
    assert pick["reasons"]


@pytest.mark.parametrize(
    ("game_slug", "expected_length"),
    [
        ("michigan-daily-3", 3),
        ("michigan-daily-4", 4),
        ("michigan-cash-pop", 1),
        ("michigan-club-keno", 1),
        ("michigan-fantasy-5", 5),
        ("michigan-keno", 10),
        ("michigan-lotto-47", 6),
        ("michigan-poker-lotto", 5),
        ("millionaire-for-life", 6),
    ],
)
def test_low_share_supports_michigan_local_games(
    tmp_path,
    game_slug,
    expected_length,
):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "low-share",
            game_slug,
            "-j",
            "mi",
            "--count",
            "1",
            "--candidates",
            "5",
            "--seed",
            "4",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    pick = payload["games"][0]["options"][0]["picks"][0]
    assert len(pick["numbers"]) == expected_length
    assert pick["label"] != "n/a"
    assert pick["reasons"]


def test_low_share_supports_dc_millionaire_for_life(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "low-share",
            "millionaire-for-life",
            "-j",
            "dc",
            "--count",
            "1",
            "--candidates",
            "5",
            "--seed",
            "4",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    pick = payload["games"][0]["options"][0]["picks"][0]
    assert len(pick["numbers"]) == 6
    assert pick["label"] != "n/a"
    assert pick["reasons"]


def test_low_share_supports_minnesota_lotto_america(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "low-share",
            "lotto-america",
            "-j",
            "mn",
            "--count",
            "1",
            "--candidates",
            "5",
            "--seed",
            "4",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    pick = payload["games"][0]["options"][0]["picks"][0]
    assert len(pick["numbers"]) == 6
    assert pick["label"] != "n/a"
    assert pick["reasons"]


def test_low_share_supports_minnesota_pick_3(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "low-share",
            "minnesota-pick-3",
            "-j",
            "mn",
            "--count",
            "1",
            "--candidates",
            "5",
            "--seed",
            "4",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    pick = payload["games"][0]["options"][0]["picks"][0]
    assert len(pick["numbers"]) == 3
    assert pick["label"] != "n/a"
    assert pick["reasons"]


@pytest.mark.parametrize(
    ("game_slug", "expected_length"),
    [
        ("dc-3", 3),
        ("dc-4", 4),
        ("dc-5", 5),
    ],
)
def test_low_share_supports_dc_fixed_prize_digit_games(
    tmp_path,
    game_slug,
    expected_length,
):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "low-share",
            game_slug,
            "-j",
            "dc",
            "--count",
            "1",
            "--candidates",
            "5",
            "--seed",
            "4",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    pick = payload["games"][0]["options"][0]["picks"][0]
    assert len(pick["numbers"]) == expected_length
    assert pick["label"] != "n/a"
    assert pick["reasons"]


@pytest.mark.parametrize(
    ("game_slug", "expected_length"),
    [
        ("georgia-cash-3", 3),
        ("georgia-cash-4", 4),
        ("georgia-cash-pop", 1),
        ("georgia-five", 5),
        ("millionaire-for-life", 6),
    ],
)
def test_low_share_supports_georgia_local_games(
    tmp_path,
    game_slug,
    expected_length,
):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "low-share",
            game_slug,
            "-j",
            "ga",
            "--count",
            "1",
            "--candidates",
            "5",
            "--seed",
            "4",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    pick = payload["games"][0]["options"][0]["picks"][0]
    assert len(pick["numbers"]) == expected_length
    assert pick["label"] != "n/a"
    assert pick["reasons"]


@pytest.mark.parametrize(
    ("game_slug", "expected_length"),
    [
        ("mississippi-cash-3", 3),
        ("mississippi-cash-4", 4),
    ],
)
def test_low_share_supports_mississippi_digit_games(
    tmp_path,
    game_slug,
    expected_length,
):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "low-share",
            game_slug,
            "-j",
            "ms",
            "--count",
            "1",
            "--candidates",
            "5",
            "--seed",
            "4",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    pick = payload["games"][0]["options"][0]["picks"][0]
    assert len(pick["numbers"]) == expected_length
    assert pick["label"] != "n/a"
    assert pick["reasons"]


@pytest.mark.parametrize(
    ("game_slug", "expected_length"),
    [
        ("arkansas-cash-3", 3),
        ("arkansas-cash-4", 4),
        ("arkansas-lotto", 6),
        ("arkansas-natural-state-jackpot", 5),
    ],
)
def test_low_share_supports_arkansas_local_draw_games(
    tmp_path,
    game_slug,
    expected_length,
):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "low-share",
            game_slug,
            "-j",
            "ar",
            "--count",
            "1",
            "--candidates",
            "5",
            "--seed",
            "4",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    pick = payload["games"][0]["options"][0]["picks"][0]
    assert len(pick["numbers"]) == expected_length
    assert pick["label"] != "n/a"
    assert pick["reasons"]


@pytest.mark.parametrize(
    ("game_slug", "expected_length"),
    [
        ("quick-draw", 20),
        ("pick-10", 10),
    ],
)
def test_low_share_supports_new_york_fixed_prize_local_games(
    tmp_path,
    game_slug,
    expected_length,
):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "low-share",
            game_slug,
            "-j",
            "ny",
            "--count",
            "1",
            "--candidates",
            "5",
            "--seed",
            "4",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    pick = payload["games"][0]["options"][0]["picks"][0]
    assert len(pick["numbers"]) == expected_length
    assert pick["label"] != "n/a"
    assert pick["reasons"]


def test_low_share_reports_cataloged_game_without_low_share_support(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "low-share",
            "new-york-lotto",
            "-j",
            "ny",
            "--output",
            "json",
        ],
    )

    assert result.exit_code != 0
    assert "low-share support pending for game: new-york-lotto" in result.output


def test_low_share_table_includes_score_and_no_odds_disclaimer(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "low-share",
            "hit-5",
            "--count",
            "1",
            "--candidates",
            "10",
            "--seed",
            "11",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Low-Share Score" in result.output
    assert "Hit 5" in result.output
    assert "Low-share picks do not improve draw odds" in result.output


def test_low_share_warns_when_avoiding_recent_combos_without_draw_data(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "low-share",
            "powerball",
            "--count",
            "1",
            "--candidates",
            "10",
            "--avoid-recent-winning-combos",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Warning:" in result.output
    assert "no stored draw data was available" in result.output


def test_low_share_can_exclude_exact_stored_winning_combo(tmp_path):
    conn = db.connect(tmp_path)
    conn.execute(
        """
        insert into draw_results (
            game_slug,
            draw_date,
            winning_number,
            prize_amount,
            wa_winners,
            total
        )
        values (?, ?, ?, ?, ?, ?)
        """,
        ("powerball", "Mon, May 04, 2026", "09, 16, 18, 33, 64, 25", 4.0, 1, 4.0),
    )
    conn.commit()
    game = db.get_game(conn, "powerball")
    assert game is not None

    results = generate_low_share_options(
        conn,
        game,
        count=1,
        candidates=1,
        seed=1,
        avoid_recent_winning_combos=True,
    )

    assert results[0].picks == ()
    assert (
        "requested 1 picks but only 0 unique candidates were available"
        in results[0].warnings
    )


def test_low_share_can_ask_openai_to_evaluate_generated_candidates(
    tmp_path,
    monkeypatch,
):
    call = {}

    def fake_evaluate(payload, model):
        call["payload"] = payload
        call["model"] = model
        best = payload["best_low_share_candidate"]
        return {
            "decision": "PLAY_FOR_ENTERTAINMENT",
            "selected_candidate_id": best["candidate_id"],
            "selected_game_slug": best["game_slug"],
            "selected_option_slug": best["option_slug"],
            "confidence": "medium",
            "rationale": "This candidate has the strongest low-share heuristic score.",
            "tradeoffs": ["The pick has no draw-odds advantage."],
            "facts_used": {
                "candidate_count": payload["facts"]["candidate_count"],
                "best_candidate_id": best["candidate_id"],
                "best_low_share_score": best["low_share_score"],
                "no_odds_edge": True,
            },
        }

    monkeypatch.setattr(
        "nolottery.cli.evaluate_low_share_with_openai",
        fake_evaluate,
    )
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "low-share",
            "hit-5",
            "--count",
            "2",
            "--candidates",
            "20",
            "--seed",
            "9",
            "--evaluate",
            "openai",
            "--openai-model",
            "gpt-test",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    output = json.loads(result.output)
    assert output["evaluation"]["decision"] == "PLAY_FOR_ENTERTAINMENT"
    assert call["model"] == "gpt-test"
    assert call["payload"]["facts"]["no_odds_edge"] is True
    assert len(call["payload"]["candidates"]) == 2
    assert call["payload"]["candidates"][0]["candidate_id"].startswith("hit-5:")
    assert "numbers" in call["payload"]["candidates"][0]
    assert "Do not claim any candidate has better draw odds." in json.dumps(
        call["payload"]
    )
