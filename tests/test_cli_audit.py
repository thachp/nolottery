import json

from typer.testing import CliRunner

from nolottery import db
from nolottery.cli import app


runner = CliRunner()


def _drawings_html(*draws: tuple[str, tuple[str, ...]]) -> str:
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
              <td class="game-balls" rowspan="1">
                <ul>{''.join(f'<li>{number}</li>' for number in numbers)}</ul>
              </td>
              <td>$500</td><td>1</td><td>$500</td>
            </tr>
          </tbody>
        </table>
        """
        for date, numbers in draws
    )
    return f"<html><body>{tables}</body></html>"


def _idaho_draw_page_html(*draws: tuple[str, tuple[str, ...]]) -> str:
    rows = "\n".join(
        f"""
        <tr>
          <td data-title="Date">{date}</td>
          <td data-title="Winning Numbers">
            <ul>{''.join(f'<li>{number}</li>' for number in numbers)}</ul>
          </td>
        </tr>
        """
        for date, numbers in draws
    )
    return f"<html><body><table><tbody>{rows}</tbody></table></body></html>"


def test_audit_frequency_reports_uniform_cashpop_buckets(tmp_path):
    data_dir = tmp_path / "data"
    fixture = tmp_path / "cashpop.html"
    fixture.write_text(
        _drawings_html(
            ("Mon, May 04, 2026", ("04",)),
            ("Tue, May 05, 2026", ("05",)),
            ("Wed, May 06, 2026", ("04",)),
        ),
        encoding="utf-8",
    )
    fetch_result = runner.invoke(
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
    assert fetch_result.exit_code == 0, fetch_result.output

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "audit",
            "frequency",
            "cashpop",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["game_slug"] == "cashpop"
    assert payload["pool"] == "numbers"
    assert payload["test"] == "frequency"
    assert payload["draw_count"] == 3
    assert payload["status"] == "INSUFFICIENT_DATA"
    assert payload["expected_per_bucket"] == 0.2
    assert payload["buckets"][3]["value"] == 4
    assert payload["buckets"][3]["observed"] == 2
    assert payload["buckets"][4]["value"] == 5
    assert payload["buckets"][4]["observed"] == 1


def test_audit_chi_square_reports_powerball_pools_separately(tmp_path):
    data_dir = tmp_path / "data"
    fixture = tmp_path / "powerball.html"
    fixture.write_text(
        _drawings_html(
            ("Mon, May 04, 2026", ("01", "02", "03", "04", "05", "06")),
            ("Tue, May 05, 2026", ("02", "03", "04", "05", "06", "07")),
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

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "audit",
            "chi-square",
            "powerball",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert [audit["pool"] for audit in payload["audits"]] == ["white", "powerball"]
    assert payload["audits"][0]["test"] == "chi-square"
    assert payload["audits"][0]["degrees_of_freedom"] == 68
    assert payload["audits"][1]["degrees_of_freedom"] == 25


def test_audit_frequency_parses_active_idaho_game_pools(tmp_path):
    data_dir = tmp_path / "data"
    cases = {
        "idaho-cash": (
            _idaho_draw_page_html(
                ("05/06/26", ("02", "05", "17", "23", "43")),
                ("05/05/26", ("05", "06", "15", "17", "22")),
            ),
            ["numbers"],
        ),
        "idaho-pick-3": (
            _idaho_draw_page_html(
                ("05/07/26", ("4", "1", "3", "8")),
                ("05/06/26", ("1", "2", "3", "6")),
            ),
            ["position_1", "position_2", "position_3"],
        ),
        "idaho-pick-4": (
            _idaho_draw_page_html(
                ("05/07/26", ("6", "8", "2", "8", "24")),
                ("05/06/26", ("1", "2", "3", "4", "10")),
            ),
            ["position_1", "position_2", "position_3", "position_4"],
        ),
        "lotto-america": (
            _idaho_draw_page_html(
                ("05/06/26", ("03", "06", "07", "18", "49", "10")),
                ("05/04/26", ("09", "10", "12", "50", "52", "03")),
            ),
            ["white", "star_ball"],
        ),
        "millionaire-for-life": (
            _idaho_draw_page_html(
                ("05/06/26", ("06", "18", "30", "32", "43", "01")),
                ("05/05/26", ("14", "20", "23", "30", "55", "02")),
            ),
            ["white", "life_ball"],
        ),
    }

    for game_slug, (html, expected_pools) in cases.items():
        fixture = tmp_path / f"{game_slug}.html"
        fixture.write_text(html, encoding="utf-8")
        fetch_result = runner.invoke(
            app,
            [
                "--data-dir",
                str(data_dir),
                "fetch",
                game_slug,
                "-j",
                "id",
                "--source-file",
                str(fixture),
            ],
        )
        assert fetch_result.exit_code == 0, fetch_result.output

        result = runner.invoke(
            app,
            [
                "--data-dir",
                str(data_dir),
                "audit",
                "frequency",
                game_slug,
                "-j",
                "id",
                "--output",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        if len(expected_pools) == 1:
            assert payload["pool"] == expected_pools[0]
            assert payload["draw_count"] == 2
        else:
            assert [audit["pool"] for audit in payload["audits"]] == expected_pools
            assert all(audit["draw_count"] == 2 for audit in payload["audits"])


def test_audit_frequency_parses_active_oregon_game_pools(tmp_path):
    conn = db.connect(tmp_path)
    rows = [
        ("or", "oregon-megabucks", "Wed, May 06, 2026", "03, 09, 10, 28, 31, 39"),
        ("or", "oregon-megabucks", "Sat, May 02, 2026", "04, 10, 19, 27, 33, 42"),
        (
            "or",
            "oregon-keno",
            "Thu, May 07, 2026 17:00",
            "05, 07, 08, 10, 11, 13, 16, 17, 20, 22, "
            "28, 32, 33, 35, 41, 44, 45, 56, 70, 72, 54 Bulls-eye",
        ),
        (
            "or",
            "oregon-keno",
            "Thu, May 07, 2026 17:04",
            "01, 04, 05, 06, 08, 13, 15, 25, 31, 36, "
            "38, 42, 48, 52, 55, 59, 61, 64, 73, 79, 36 Bulls-eye",
        ),
        ("or", "oregon-cash-pop", "Thu, May 07, 2026 17:00", "08"),
        ("or", "oregon-cash-pop", "Thu, May 07, 2026 18:00", "14"),
        ("or", "oregon-pick-4", "Thu, May 07, 2026 13:00", "06, 4, 0, 7"),
        ("or", "oregon-pick-4", "Thu, May 07, 2026 16:00", "03, 9, 2, 9"),
        ("or", "oregon-win-for-life", "Wed, May 06, 2026", "07, 45, 52, 54"),
        ("or", "oregon-win-for-life", "Mon, May 04, 2026", "06, 23, 61, 73"),
    ]
    conn.executemany(
        """
        insert into draw_results (
            jurisdiction_code,
            game_slug,
            draw_date,
            winning_number,
            prize_amount,
            wa_winners,
            total
        )
        values (?, ?, ?, ?, 0, 0, 0)
        """,
        rows,
    )
    conn.commit()

    cases = {
        "oregon-megabucks": ["numbers"],
        "oregon-keno": ["numbers", "bulls_eye"],
        "oregon-cash-pop": ["numbers"],
        "oregon-pick-4": ["position_1", "position_2", "position_3", "position_4"],
        "oregon-win-for-life": ["numbers"],
    }

    for game_slug, expected_pools in cases.items():
        result = runner.invoke(
            app,
            [
                "--data-dir",
                str(tmp_path),
                "audit",
                "frequency",
                game_slug,
                "-j",
                "or",
                "--output",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        if len(expected_pools) == 1:
            assert payload["pool"] == expected_pools[0]
            assert payload["draw_count"] == 2
        else:
            assert [audit["pool"] for audit in payload["audits"]] == expected_pools
            assert all(audit["draw_count"] == 2 for audit in payload["audits"])


def test_audit_pairs_includes_combination_chi_square_and_full_json_buckets(tmp_path):
    data_dir = tmp_path / "data"
    fixture = tmp_path / "hit-5.html"
    fixture.write_text(
        _drawings_html(
            ("Mon, May 04, 2026", ("01", "02", "03", "04", "05")),
            ("Tue, May 05, 2026", ("01", "02", "06", "07", "08")),
        ),
        encoding="utf-8",
    )
    fetch_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "fetch",
            "hit-5",
            "--source-file",
            str(fixture),
        ],
    )
    assert fetch_result.exit_code == 0, fetch_result.output

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "audit",
            "pairs",
            "hit-5",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["game_slug"] == "hit-5"
    assert payload["pool"] == "numbers"
    assert payload["test"] == "pairs"
    assert payload["status"] == "INSUFFICIENT_DATA"
    assert payload["expected_per_bucket"] == 20 / 861
    assert payload["degrees_of_freedom"] == 860
    assert payload["buckets"][0]["combination"] == [1, 2]
    assert payload["buckets"][0]["observed"] == 2
    assert any(bucket["observed"] == 0 for bucket in payload["buckets"])


def test_audit_gaps_reports_completed_gap_chi_square_and_current_gap(tmp_path):
    data_dir = tmp_path / "data"
    fixture = tmp_path / "cashpop.html"
    fixture.write_text(
        _drawings_html(
            ("Mon, May 04, 2026", ("01",)),
            ("Tue, May 05, 2026", ("02",)),
            ("Wed, May 06, 2026", ("01",)),
            ("Thu, May 07, 2026", ("01",)),
        ),
        encoding="utf-8",
    )
    fetch_result = runner.invoke(
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
    assert fetch_result.exit_code == 0, fetch_result.output

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "audit",
            "gaps",
            "cashpop",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["game_slug"] == "cashpop"
    assert payload["pool"] == "numbers"
    assert payload["test"] == "gaps"
    assert payload["status"] == "INSUFFICIENT_DATA"
    assert payload["completed_gap_count"] == 2
    assert payload["values"][0]["value"] == 1
    assert payload["values"][0]["appearances"] == 3
    assert payload["values"][0]["current_gap"] == 0
    assert payload["values"][0]["max_gap"] == 1
    assert payload["values"][0]["average_gap"] == 0.5
    assert payload["gap_buckets"][0]["gap"] == "0"
    assert payload["gap_buckets"][-1]["gap"].startswith(">=")


def test_audit_all_returns_compact_matrix_unless_details_are_requested(tmp_path):
    data_dir = tmp_path / "data"
    fixture = tmp_path / "cashpop.html"
    fixture.write_text(
        _drawings_html(
            ("Mon, May 04, 2026", ("01",)),
            ("Tue, May 05, 2026", ("02",)),
            ("Wed, May 06, 2026", ("01",)),
        ),
        encoding="utf-8",
    )
    fetch_result = runner.invoke(
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
    assert fetch_result.exit_code == 0, fetch_result.output

    compact_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "audit",
            "all",
            "cashpop",
            "--output",
            "json",
        ],
    )
    detailed_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "audit",
            "all",
            "cashpop",
            "--output",
            "json",
            "--details",
        ],
    )

    assert compact_result.exit_code == 0, compact_result.output
    compact_payload = json.loads(compact_result.output)
    audits = compact_payload["games"][0]["audits"]
    assert [audit["test"] for audit in audits] == [
        "frequency",
        "chi-square",
        "pairs",
        "triples",
        "gaps",
    ]
    assert "buckets" not in audits[0]
    assert "values" not in audits[-1]

    assert detailed_result.exit_code == 0, detailed_result.output
    detailed_payload = json.loads(detailed_result.output)
    assert "buckets" in detailed_payload["games"][0]["audits"][0]
    assert "values" in detailed_payload["games"][0]["audits"][-1]


def test_audit_last_counts_recent_valid_draws_after_skipping_invalid_rows(tmp_path):
    data_dir = tmp_path / "data"
    fixture = tmp_path / "cashpop.html"
    fixture.write_text(
        _drawings_html(
            ("Mon, May 04, 2026", ("01",)),
            ("Tue, May 05, 2026", ("99",)),
            ("Wed, May 06, 2026", ("02",)),
            ("Thu, May 07, 2026", ("03",)),
        ),
        encoding="utf-8",
    )
    fetch_result = runner.invoke(
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
    assert fetch_result.exit_code == 0, fetch_result.output

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "audit",
            "frequency",
            "cashpop",
            "--last",
            "2",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["draw_count"] == 2
    assert any(
        "1 draws had unparseable or invalid winning_number values" == warning
        for warning in payload["warnings"]
    )
    assert payload["buckets"][0]["observed"] == 0
    assert payload["buckets"][1]["observed"] == 1
    assert payload["buckets"][2]["observed"] == 1


def test_audit_pick3_pairs_preserve_front_and_back_positions(tmp_path):
    data_dir = tmp_path / "data"
    fixture = tmp_path / "pick-3.html"
    fixture.write_text(
        _drawings_html(
            ("Mon, May 04, 2026", ("012",)),
            ("Tue, May 05, 2026", ("011",)),
        ),
        encoding="utf-8",
    )
    fetch_result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "fetch",
            "pick-3",
            "--source-file",
            str(fixture),
        ],
    )
    assert fetch_result.exit_code == 0, fetch_result.output

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "audit",
            "pairs",
            "pick-3",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert [audit["pool"] for audit in payload["audits"]] == [
        "front_pair",
        "back_pair",
    ]
    front_pair = payload["audits"][0]["buckets"][1]
    back_pair_12 = payload["audits"][1]["buckets"][12]
    back_pair_11 = payload["audits"][1]["buckets"][11]
    assert front_pair["combination"] == "01"
    assert front_pair["observed"] == 2
    assert back_pair_12["combination"] == "12"
    assert back_pair_12["observed"] == 1
    assert back_pair_11["combination"] == "11"
    assert back_pair_11["observed"] == 1


def test_audit_all_can_ask_openai_to_explain_compact_results(
    tmp_path,
    monkeypatch,
):
    data_dir = tmp_path / "data"
    fixture = tmp_path / "cashpop.html"
    fixture.write_text(
        _drawings_html(
            ("Mon, May 04, 2026", ("01",)),
            ("Tue, May 05, 2026", ("02",)),
            ("Wed, May 06, 2026", ("01",)),
        ),
        encoding="utf-8",
    )
    fetch_result = runner.invoke(
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
    assert fetch_result.exit_code == 0, fetch_result.output
    call = {}

    def fake_explain(payload, model):
        call["payload"] = payload
        call["model"] = model
        return {
            "summary": "The audits are too sparse to support a bias conclusion.",
            "overall_status": "INSUFFICIENT_DATA",
            "notable_findings": ["Expected bucket counts are below reliable thresholds."],
            "limitations": ["Historical audits do not predict future winning numbers."],
            "recommended_next_steps": ["Fetch more historical draw data."],
            "facts_used": {
                "audit_count": payload["facts"]["audit_count"],
                "warn_count": payload["facts"]["warn_count"],
                "insufficient_data_count": payload["facts"]["insufficient_data_count"],
                "not_applicable_count": payload["facts"]["not_applicable_count"],
                "max_draw_count": payload["facts"]["max_draw_count"],
            },
        }

    monkeypatch.setattr("nolottery.cli.explain_audits_with_openai", fake_explain)
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "audit",
            "all",
            "cashpop",
            "--evaluate",
            "openai",
            "--openai-model",
            "gpt-test",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["evaluation"]["overall_status"] == "INSUFFICIENT_DATA"
    assert call["model"] == "gpt-test"
    assert call["payload"]["facts"]["audit_count"] == 5
    assert call["payload"]["facts"]["max_draw_count"] == 3
    assert "Historical audit results do not identify winning future numbers." in json.dumps(
        call["payload"]
    )
    assert '"buckets":' not in json.dumps(call["payload"])
    assert "notable_buckets" in json.dumps(call["payload"])
