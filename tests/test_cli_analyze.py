import json

import pytest
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


def test_analyze_accepts_explicit_washington_jurisdiction(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "analyze",
            "cashpop",
            "-j",
            "wa",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "wa"
    assert payload["game_slug"] == "cashpop"


def test_analyze_supports_florida_pick_3_rules(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "analyze",
            "florida-pick-3",
            "-j",
            "fl",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "fl"
    assert payload["game_slug"] == "florida-pick-3"
    assert payload["best_option"] == "Straight $1"
    assert payload["options"][0]["slug"] == "straight-1"
    assert payload["options"][0]["ticket_cost"] == 1.0
    assert payload["options"][0]["hit_rate"] == 0.001


def test_analyze_supports_new_york_numbers_rules(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "analyze",
            "numbers",
            "-j",
            "ny",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "ny"
    assert payload["game_slug"] == "numbers"
    assert payload["best_option"] == "Straight $1"
    assert payload["options"][0]["slug"] == "straight-1"
    assert payload["options"][0]["ticket_cost"] == 1.0
    assert payload["options"][0]["hit_rate"] == 0.001


def test_analyze_supports_other_florida_and_new_york_fixed_digit_rules(tmp_path):
    cases = [
        ("fl", "florida-pick-2", 0.01, 50),
        ("fl", "florida-pick-4", 0.0001, 5000),
        ("fl", "florida-pick-5", 0.00001, 50000),
        ("ny", "win-4", 0.0001, 5000),
    ]

    for jurisdiction, game_slug, probability, prize in cases:
        result = runner.invoke(
            app,
            [
                "--data-dir",
                str(tmp_path / jurisdiction / game_slug),
                "analyze",
                game_slug,
                "-j",
                jurisdiction,
                "--output",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["jurisdiction_code"] == jurisdiction
        assert payload["game_slug"] == game_slug
        assert payload["options"][0]["slug"] == "straight-1"
        assert payload["options"][0]["hit_rate"] == probability
        assert payload["options"][0]["gross_ev"] == prize * probability


def test_analyze_supports_active_idaho_draw_games(tmp_path):
    expected_best_options = {
        "idaho-cash": "Two Plays $1",
        "idaho-pick-3": "Exact Order $1",
        "idaho-pick-4": "Exact Order $1",
        "lotto-america": "Standard $1",
        "millionaire-for-life": "Standard $5",
    }

    for game_slug, best_option in expected_best_options.items():
        result = runner.invoke(
            app,
            [
                "--data-dir",
                str(tmp_path / game_slug),
                "analyze",
                game_slug,
                "-j",
                "id",
                "--output",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["jurisdiction_code"] == "id"
        assert payload["game_slug"] == game_slug
        assert payload["best_option"] == best_option
        assert payload["options"]


def test_analyze_supports_active_oregon_draw_games(tmp_path):
    expected_best_options = {
        "oregon-megabucks": "Standard $1",
        "oregon-keno": "2-Spot $1",
        "oregon-cash-pop": "1 POP $1",
        "oregon-pick-4": "Straight $1",
        "oregon-win-for-life": "Standard $2",
    }

    for game_slug, best_option in expected_best_options.items():
        result = runner.invoke(
            app,
            [
                "--data-dir",
                str(tmp_path / game_slug),
                "analyze",
                game_slug,
                "-j",
                "or",
                "--output",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["jurisdiction_code"] == "or"
        assert payload["game_slug"] == game_slug
        assert payload["best_option"] == best_option
        assert payload["options"]


def test_analyze_supports_active_colorado_draw_games(tmp_path):
    expected_best_options = {
        "colorado-lotto-plus": "Standard $2",
        "colorado-cash-5": "Standard $1",
        "colorado-pick-3": "Exact Order $1",
        "millionaire-for-life": "Standard $5",
    }

    for game_slug, best_option in expected_best_options.items():
        result = runner.invoke(
            app,
            [
                "--data-dir",
                str(tmp_path / game_slug),
                "analyze",
                game_slug,
                "-j",
                "co",
                "--output",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["jurisdiction_code"] == "co"
        assert payload["game_slug"] == game_slug
        assert payload["best_option"] == best_option
        assert payload["options"]


def test_analyze_supports_active_texas_local_draw_games(tmp_path):
    expected_best_options = {
        "texas-lotto": "Standard $1",
        "texas-two-step": "Standard $1",
        "texas-cash-five": "Standard $1",
        "texas-all-or-nothing": "Standard $2",
        "texas-pick-3": "Exact Order $1",
        "texas-daily-4": "Exact Order $1",
    }

    for game_slug, best_option in expected_best_options.items():
        result = runner.invoke(
            app,
            [
                "--data-dir",
                str(tmp_path / game_slug),
                "analyze",
                game_slug,
                "-j",
                "tx",
                "--output",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["jurisdiction_code"] == "tx"
        assert payload["game_slug"] == game_slug
        assert payload["best_option"] == best_option
        assert payload["options"]


def test_analyze_reports_cataloged_game_without_ev_support(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "analyze",
            "new-york-lotto",
            "-j",
            "ny",
            "--output",
            "json",
        ],
    )

    assert result.exit_code != 0
    assert "EV support pending for game: new-york-lotto" in result.output


def test_analyze_all_skips_cataloged_new_york_games_without_ev_support(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "analyze",
            "all",
            "-j",
            "ny",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "ny"
    game_slugs = {game["game_slug"] for game in payload["games"]}
    assert "numbers" in game_slugs
    assert "new-york-lotto" not in game_slugs


def test_analyze_rejects_unknown_jurisdiction(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "analyze",
            "cashpop",
            "-j",
            "xx",
            "--output",
            "json",
        ],
    )

    assert result.exit_code != 0
    assert "unknown jurisdiction: xx" in result.output


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


def test_recommend_defaults_to_best_small_budget_hit_rate(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "nolottery.cli._generated_at",
        lambda: "2026-05-06T14:32:10-07:00",
        raising=False,
    )

    result = runner.invoke(
        app,
        ["--data-dir", str(tmp_path), "recommend"],
    )

    assert result.exit_code == 0, result.output
    assert "Generated at: 2026-05-06T14:32:10-07:00" in result.output
    assert "Daily Keno" in result.output
    assert "4-Spot" in result.output
    assert "1:3.86" in result.output
    assert "Example" not in result.output
    assert "Prediction method" in result.output
    assert "no odds advantage" in result.output


def test_recommend_can_return_json(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "nolottery.cli._generated_at",
        lambda: "2026-05-06T14:32:10-07:00",
        raising=False,
    )

    result = runner.invoke(
        app,
        ["--data-dir", str(tmp_path), "recommend", "--output", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["generated_at"] == "2026-05-06T14:32:10-07:00"
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


def test_recommend_supports_new_york_numbers(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "recommend",
            "-j",
            "ny",
            "--budget",
            "1",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "ny"
    assert payload["best"]["game_slug"] == "numbers"
    assert payload["best"]["number_selection"] == [1, 2, 3]
    assert payload["best"]["prediction_method"] == "quick-pick-random-no-edge"
    assert len(payload["best"]["prediction"]) == 3


def test_recommend_supports_florida_pick_2(tmp_path):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "recommend",
            "-j",
            "fl",
            "--budget",
            "1",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["jurisdiction_code"] == "fl"
    assert payload["best"]["game_slug"] == "florida-pick-2"
    assert payload["best"]["number_selection"] == [1, 2]
    assert len(payload["best"]["prediction"]) == 2


@pytest.mark.parametrize(
    ("jurisdiction_code", "jurisdiction_name"),
    [
        ("al", "Alabama"),
        ("ak", "Alaska"),
    ],
)
def test_recommend_reports_no_state_lottery(
    tmp_path,
    jurisdiction_code,
    jurisdiction_name,
):
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(tmp_path),
            "recommend",
            "-j",
            jurisdiction_code,
            "--output",
            "json",
        ],
    )

    assert result.exit_code != 0
    assert f"No EV-supported games for {jurisdiction_name}" in result.output
    assert "No state lottery" in result.output
    assert "established" in result.output


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
    monkeypatch.setattr(
        "nolottery.cli._generated_at",
        lambda: "2026-05-06T14:32:10-07:00",
        raising=False,
    )

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
    assert output["generated_at"] == "2026-05-06T14:32:10-07:00"
    assert output["evaluation"]["decision"] == "SKIP"
    assert call["model"] == "gpt-test"
    assert call["payload"]["generated_at"] == "2026-05-06T14:32:10-07:00"
    assert call["payload"]["deterministic_decision"] == "SKIP"
    assert call["payload"]["best_hit_rate_option"]["candidate_slug"] == "cashpop:10-pop"
    assert "prediction" not in json.dumps(call["payload"])
    assert "number_selection" not in json.dumps(call["payload"])
