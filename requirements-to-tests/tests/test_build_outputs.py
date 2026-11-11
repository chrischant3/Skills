"""Behaviour tests for scripts/build_outputs.py (validation + report + workbook)."""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_outputs as bo  # noqa: E402

EXAMPLE = json.loads(
    (ROOT / "references" / "example-analysis.json").read_text(encoding="utf-8")
)


@pytest.fixture
def analysis():
    return copy.deepcopy(EXAMPLE)


def _messages(issues, level):
    return [i["message"] for i in issues if i["level"] == level]


def test_documented_example_is_valid(analysis):
    issues = bo.validate(analysis)
    assert _messages(issues, "error") == []


def test_scenario_tracing_to_unknown_requirement_is_an_error(analysis):
    analysis["scenarios"][0]["req_ids"] = ["R-999"]
    assert any("R-999" in m for m in _messages(bo.validate(analysis), "error"))


def test_duplicate_ids_are_an_error(analysis):
    analysis["requirements"][1]["id"] = "R-001"
    assert any(
        "Duplicate" in m and "R-001" in m
        for m in _messages(bo.validate(analysis), "error")
    )


def test_invalid_enum_value_is_an_error(analysis):
    analysis["requirements"][0]["kind"] = "non-functional"
    assert any("kind" in m for m in _messages(bo.validate(analysis), "error"))


def test_assumption_pointing_at_unknown_question_is_an_error(analysis):
    analysis["scenarios"][1]["assumptions"][0]["question_id"] = "Q-99"
    assert any("Q-99" in m for m in _messages(bo.validate(analysis), "error"))


def test_requirement_with_no_scenario_and_no_question_is_flagged_untested(analysis):
    analysis["scenarios"] = [
        s for s in analysis["scenarios"] if "R-001" not in s["req_ids"]
    ]
    assert any(
        "R-001" in m and "no scenario" in m
        for m in _messages(bo.validate(analysis), "warning")
    )


def test_ignored_requirement_needs_no_scenario(analysis):
    analysis["requirements"][0]["priority"] = "ignore"
    analysis["scenarios"] = [
        s for s in analysis["scenarios"] if "R-001" not in s["req_ids"]
    ]
    assert not any("R-001" in m for m in _messages(bo.validate(analysis), "warning"))


def test_unmeasurable_nfr_without_question_is_flagged(analysis):
    analysis["requirements"][1]["question_ids"] = []
    analysis["questions"][0]["blocks"] = []
    assert any(
        "R-002" in m and "not measurable" in m
        for m in _messages(bo.validate(analysis), "warning")
    )


def test_nfr_not_attached_to_any_function_is_flagged(analysis):
    analysis["requirements"][2]["applies_to"] = []
    assert any(
        "R-003" in m and "function" in m
        for m in _messages(bo.validate(analysis), "warning")
    )


def test_or_inside_a_gherkin_step_is_flagged(analysis):
    analysis["scenarios"][0]["then"] = ["the booking is confirmed or queued"]
    assert any(
        "S-001" in m and '"or"' in m
        for m in _messages(bo.validate(analysis), "warning")
    )


def test_provisional_scenario_without_assumptions_is_flagged(analysis):
    analysis["scenarios"][1]["assumptions"] = []
    assert any(
        "S-002" in m and "provisional" in m
        for m in _messages(bo.validate(analysis), "warning")
    )


def test_measurement_scenario_without_threshold_is_flagged(analysis):
    del analysis["scenarios"][2]["measurement"]["threshold"]
    assert any(
        "S-003" in m and "threshold" in m
        for m in _messages(bo.validate(analysis), "warning")
    )


def test_build_writes_report_and_workbook(tmp_path, analysis):
    src = tmp_path / "analysis.json"
    src.write_text(json.dumps(analysis), encoding="utf-8")
    code = bo.main([str(src), "--out-dir", str(tmp_path), "--stem", "clinic"])
    assert code == 0

    report = (tmp_path / "clinic-requirements-report.md").read_text(encoding="utf-8")
    for heading in ["Summary", "Questions", "Requirements", "Test scenarios", "Gaps"]:
        assert f"## {heading}" in report
    assert "R-003" in report and "S-002" in report
    assert "PROVISIONAL" in report

    import openpyxl

    wb = openpyxl.load_workbook(tmp_path / "clinic-requirements.xlsx")
    assert {"Requirements", "Scenarios", "Questions", "Gaps", "Coverage"} <= set(
        wb.sheetnames
    )
    assert wb["Requirements"].max_row == 1 + len(analysis["requirements"])
    assert wb["Scenarios"].max_row == 1 + len(analysis["scenarios"])
    coverage = {
        row[0]: row for row in wb["Coverage"].iter_rows(min_row=2, values_only=True)
    }
    assert coverage["R-001"][-1] == 1  # one scenario covers R-001


def test_build_refuses_to_write_when_there_are_errors(tmp_path, analysis):
    analysis["scenarios"][0]["req_ids"] = ["R-999"]
    src = tmp_path / "analysis.json"
    src.write_text(json.dumps(analysis), encoding="utf-8")
    code = bo.main([str(src), "--out-dir", str(tmp_path), "--stem", "clinic"])
    assert code == 1
    assert not (tmp_path / "clinic-requirements.xlsx").exists()
