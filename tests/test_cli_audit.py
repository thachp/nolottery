import json

from typer.testing import CliRunner

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
