from typer.testing import CliRunner

from nolottery.cli import app


runner = CliRunner()


def test_ledger_add_prompts_for_ticket_and_summary_reports_roi(tmp_path):
    add_result = runner.invoke(
        app,
        ["--data-dir", str(tmp_path), "ledger", "add"],
        input="\n".join(
            [
                "2026-05-05",
                "cashpop",
                "2026-05-05",
                "1",
                "0",
                "",
                "",
                "7",
                "y",
                "Corner Store",
                "",
            ]
        )
        + "\n",
    )

    assert add_result.exit_code == 0, add_result.output
    assert "Ticket recorded" in add_result.output

    summary_result = runner.invoke(
        app,
        ["--data-dir", str(tmp_path), "ledger", "summary"],
    )

    assert summary_result.exit_code == 0, summary_result.output
    assert "Tickets" in summary_result.output
    assert "$1.00" in summary_result.output
    assert "-100.00%" in summary_result.output

