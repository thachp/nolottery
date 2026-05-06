import json

from typer.testing import CliRunner

from nolottery.cli import app


runner = CliRunner()


def test_analyze_cashpop_defaults_to_skip_when_ev_is_negative(tmp_path):
    result = runner.invoke(
        app,
        ["--data-dir", str(tmp_path), "analyze", "cashpop"],
    )

    assert result.exit_code == 0, result.output
    assert "Cash Pop" in result.output
    assert "Decision" in result.output
    assert "SKIP" in result.output
    assert "After-tax EV" in result.output


def test_analyze_cashpop_can_return_json(tmp_path):
    result = runner.invoke(
        app,
        ["--data-dir", str(tmp_path), "analyze", "cashpop", "--output", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["game"] == "Cash Pop"
    assert payload["decision"] == "SKIP"
    assert payload["net_after_tax_ev"] < 0
    assert payload["options"]


def test_rank_compares_supported_games_by_ev_and_hit_rate(tmp_path):
    result = runner.invoke(
        app,
        ["--data-dir", str(tmp_path), "rank"],
    )

    assert result.exit_code == 0, result.output
    assert "Cash Pop" in result.output
    assert "Daily Keno" in result.output
    assert "After-tax EV" in result.output
    assert "Hit Rate" in result.output
    assert "Mega Millions" in result.output
    assert "Powerball" in result.output
    assert "Lotto" in result.output
    assert "Hit 5" in result.output
    assert "Match 4" in result.output
    assert "Pick 3" in result.output


def test_analyze_supports_all_washington_draw_games(tmp_path):
    for game in [
        "powerball",
        "mega-millions",
        "lotto",
        "hit-5",
        "match-4",
        "pick-3",
        "cashpop",
        "daily-keno",
    ]:
        result = runner.invoke(
            app,
            ["--data-dir", str(tmp_path), "analyze", game, "--output", "json"],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["game_slug"] == game
        assert payload["options"]


def test_analyze_all_outputs_every_supported_game(tmp_path):
    result = runner.invoke(
        app,
        ["--data-dir", str(tmp_path), "analyze", "all", "--output", "json"],
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


def test_recommend_defaults_to_best_small_budget_hit_rate(tmp_path):
    result = runner.invoke(
        app,
        ["--data-dir", str(tmp_path), "recommend"],
    )

    assert result.exit_code == 0, result.output
    assert "Daily Keno" in result.output
    assert "4-Spot" in result.output
    assert "1:3.86" in result.output
    assert "Example" not in result.output
    assert "Prediction method" in result.output
    assert "no odds advantage" in result.output


def test_recommend_can_return_json(tmp_path):
    result = runner.invoke(
        app,
        ["--data-dir", str(tmp_path), "recommend", "--output", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["budget"] == 1.0
    assert payload["best"]["game_slug"] == "daily-keno"
    assert payload["best"]["option_slug"] == "4-spot"
    assert payload["best"]["number_selection"] == [1, 2, 3, 4]
    assert payload["best"]["number_selection_label"] == "1, 2, 3, 4"


def test_recommend_includes_quick_pick_prediction_with_no_edge_label(tmp_path):
    result = runner.invoke(
        app,
        ["--data-dir", str(tmp_path), "recommend", "--output", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    prediction = payload["best"]["prediction"]
    assert payload["best"]["prediction_method"] == "quick-pick-random-no-edge"
    assert len(prediction) == 4
    assert len(set(prediction)) == 4
    assert all(1 <= number <= 80 for number in prediction)


def test_recommend_can_use_pick3_when_budget_is_under_one_dollar(tmp_path):
    result = runner.invoke(
        app,
        ["--data-dir", str(tmp_path), "recommend", "--budget", "0.50", "--output", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["best"]["game_slug"] == "pick-3"
    assert payload["best"]["option_slug"] in {"front-pair-50c", "back-pair-50c"}
    assert payload["best"]["hit_rate"] == 0.01


def test_recommend_recognizes_cashpop_all_numbers_as_guaranteed(tmp_path):
    result = runner.invoke(
        app,
        ["--data-dir", str(tmp_path), "recommend", "--budget", "75", "--output", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["best"]["game_slug"] == "cashpop"
    assert payload["best"]["option_slug"] == "15-pop"
    assert payload["best"]["hit_rate"] == 1.0
    assert payload["best"]["number_selection"] == list(range(1, 16))


def test_recommend_can_ask_openai_to_evaluate_reduced_payload(tmp_path, monkeypatch):
    call = {}

    def fake_evaluate(payload, model):
        call["payload"] = payload
        call["model"] = model
        return {
            "decision": "SKIP",
            "selected_option_slug": None,
            "confidence": "high",
            "rationale": "All affordable options have negative expected value.",
            "tradeoffs": ["Cash Pop has the highest hit rate but loses money in EV."],
            "facts_used": {
                "budget": 50.0,
                "deterministic_decision": "SKIP",
                "best_hit_rate_option": "cashpop:10-pop",
                "best_hit_rate": 0.6666170961836361,
                "best_net_after_tax_ev": -17.193247429939447,
            },
        }

    monkeypatch.setattr(
        "nolottery.cli.evaluate_recommendations_with_openai",
        fake_evaluate,
    )
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "recommend",
            "--budget",
            "50",
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
    assert output["evaluation"]["decision"] == "SKIP"
    assert call["model"] == "gpt-test"
    assert call["payload"]["deterministic_decision"] == "SKIP"
    assert call["payload"]["best_hit_rate_option"]["candidate_slug"] == "cashpop:10-pop"
    assert "prediction" not in json.dumps(call["payload"])
    assert "number_selection" not in json.dumps(call["payload"])
