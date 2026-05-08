import json

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
