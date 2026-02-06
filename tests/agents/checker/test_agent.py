"""Unit tests for CheckerAgent."""

from src.agents.checker.agent import CheckerAgent


def test_checker_flags_source_mismatch() -> None:
    """Checker flags prepared values that differ from source values."""
    agent = CheckerAgent()
    report = agent.run_check(
        task_id=101,
        source_values={"wages": 1000},
        prepared_values={"wages": 1200},
    )

    assert report.task_id == 101
    assert report.status == "flagged"
    assert report.approval_blocked is True
    assert report.flag_count == 1
    assert report.flags[0].code == "SOURCE_MISMATCH"
    assert report.flags[0].field == "wages"


def test_checker_flags_prior_year_variance_without_reason() -> None:
    """Checker flags large prior-year variance when reason is missing."""
    agent = CheckerAgent()
    report = agent.run_check(
        task_id=102,
        source_values={"schedule_c_income": 25000},
        prepared_values={"schedule_c_income": 25000},
        prior_year_values={"schedule_c_income": 15000},
        documented_reasons={},
    )

    assert any(
        flag.code == "PRIOR_YEAR_VARIANCE_NO_REASON"
        and flag.field == "schedule_c_income"
        for flag in report.flags
    )


def test_checker_skips_variance_flag_when_reason_present() -> None:
    """Checker does not flag large variance when reviewer reason is documented."""
    agent = CheckerAgent()
    report = agent.run_check(
        task_id=103,
        source_values={"schedule_c_income": 25000},
        prepared_values={"schedule_c_income": 25000},
        prior_year_values={"schedule_c_income": 15000},
        documented_reasons={"schedule_c_income": "Client added a second contract."},
    )

    assert not any(
        flag.code == "PRIOR_YEAR_VARIANCE_NO_REASON" for flag in report.flags
    )


def test_checker_reports_injected_error_detection_rate() -> None:
    """Checker computes detection rate from intentionally injected error fields."""
    agent = CheckerAgent()
    report = agent.run_check(
        task_id=104,
        source_values={"wages": 1000, "interest": 100},
        prepared_values={"wages": 900, "interest": 120},
        injected_error_fields=["wages", "interest", "dividends"],
    )

    assert report.error_detection_rate is not None
    assert report.error_detection_rate == (2 / 3)

