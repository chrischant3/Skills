"""Behaviour tests for scripts/validate_classifications.py: Claude's JSON checked against the taxonomy (F3, problem 4)."""

import json

import pytest

import validate_classifications as vc
from conftest import ROOT

TAXONOMY = vc.load_taxonomy(ROOT / "references/taxonomy.md")
KEYS = ["ABC-1", "ABC-2", "ABC-3"]


def record(key="ABC-1", **overrides):
    base = {
        "key": key,
        "defect_type": "checking_validation",
        "trigger": "customer_report",
        "escape_stage": "automated_test",
        "confidence": 0.8,
        "theme": "Missing null checks on optional fields",
    }
    base.update(overrides)
    return base


def check(records, keys=KEYS):
    return vc.validate(records, keys, TAXONOMY)


def all_three(**overrides_for_first):
    return [record("ABC-1", **overrides_for_first), record("ABC-2"), record("ABC-3")]


def test_taxonomy_is_read_from_the_reference_file():
    assert TAXONOMY["version"] == "v1"
    assert (
        len(TAXONOMY["defect_type"]) == 9
        and "checking_validation" in TAXONOMY["defect_type"]
    )
    assert TAXONOMY["trigger"][0] == "unit_test" and len(TAXONOMY["trigger"]) == 8
    assert (
        TAXONOMY["escape_stage"][-1] == "release" and len(TAXONOMY["escape_stage"]) == 7
    )


def test_valid_records_are_accepted():
    result, errors = check(all_three())
    assert errors == []
    assert [r["status"] for r in result["records"]] == ["classified"] * 3
    assert result["taxonomy_version"] == "v1"


@pytest.mark.parametrize(
    "field,value",
    [
        ("defect_type", "logic"),
        ("trigger", "gut_feel"),
        ("escape_stage", "nobody"),
        ("defect_type", "Checking_Validation"),
    ],
)
def test_values_outside_the_taxonomy_are_rejected(field, value):
    _, errors = check(all_three(**{field: value}))
    assert len(errors) == 1 and "ABC-1" in errors[0] and field in errors[0]


@pytest.mark.parametrize("confidence", [0.0, 0.3, 0.59])
def test_low_confidence_goes_to_unclassified_with_its_reason(confidence):
    result, errors = check(
        all_three(
            confidence=confidence, reason="No repro steps or expected result given."
        )
    )
    assert errors == []
    first = result["records"][0]
    assert (
        first["status"] == "unclassified"
        and first["reason"] == "No repro steps or expected result given."
    )


def test_exactly_point_six_is_confident_enough():
    result, _ = check(all_three(confidence=0.6))
    assert result["records"][0]["status"] == "classified"


def test_low_confidence_without_a_reason_is_rejected():
    _, errors = check(all_three(confidence=0.4))
    assert len(errors) == 1 and "reason" in errors[0]


def test_explicitly_unclassified_needs_only_a_reason():
    result, errors = check(
        all_three(
            defect_type="unclassified",
            trigger=None,
            escape_stage=None,
            theme=None,
            confidence=0.2,
            reason="Description is empty.",
        )
    )
    assert errors == [] and result["records"][0]["status"] == "unclassified"


@pytest.mark.parametrize("confidence", [1.5, -0.1, "high", None, True])
def test_confidence_must_be_a_number_from_zero_to_one(confidence):
    _, errors = check(all_three(confidence=confidence))
    assert len(errors) == 1 and "confidence" in errors[0]


def test_every_defect_must_be_classified_once_and_only_known_keys_accepted():
    _, errors = check([record("ABC-1"), record("ABC-1"), record("ABC-9")])
    text = " ".join(errors)
    assert "ABC-1" in text and "more than once" in text
    assert "ABC-9" in text and "not in clean" in text
    assert "ABC-2" in text and "ABC-3" in text and "missing" in text


def test_fields_outside_the_schema_are_rejected_so_people_cannot_be_smuggled_in():
    _, errors = check(all_three(assignee="someone"))
    assert len(errors) == 1 and "assignee" in errors[0]


@pytest.mark.parametrize(
    "theme",
    [
        "",
        "   ",
        "x" * 81,
        "Two\nlines",
        "Asked @someone about it",
        "Raised by a.person@example.com",
        "Mentioned [~someone]",
        "Work by [person]",
    ],
)
def test_unsafe_or_unusable_themes_are_rejected(theme):
    _, errors = check(all_three(theme=theme))
    assert len(errors) == 1 and "theme" in errors[0]


def test_a_theme_copied_from_the_ticket_summary_is_rejected():
    _, errors = vc.validate(
        all_three(theme="Checkout fails when address line 2 is empty"),
        KEYS,
        TAXONOMY,
        summaries={"ABC-1": "Checkout fails when address line 2 is empty"},
    )
    assert len(errors) == 1 and "own words" in errors[0]


def test_a_multi_line_reason_is_rejected():
    _, errors = check(all_three(confidence=0.1, reason="line one\nline two"))
    assert len(errors) == 1 and "reason" in errors[0]


def test_cli_writes_nothing_when_there_are_errors(tmp_path, capsys):
    clean = tmp_path / "clean"
    clean.mkdir()
    for key in KEYS:
        (clean / f"{key}.json").write_text(
            json.dumps(
                {
                    "_anonymised": {"by": "anonymise.py", "version": 2},
                    "key": key,
                    "fields": {"summary": "s"},
                }
            )
        )
    inbox = tmp_path / "classifications"
    inbox.mkdir()
    (inbox / "batch-001.json").write_text(json.dumps(all_three(defect_type="nonsense")))
    out = tmp_path / "classified.json"
    code = vc.main([str(inbox), "--issues", str(clean), "--out", str(out)])
    assert code == 1 and not out.exists() and "nonsense" in capsys.readouterr().err

    (inbox / "batch-001.json").write_text(json.dumps({"classifications": all_three()}))
    assert vc.main([str(inbox), "--issues", str(clean), "--out", str(out)]) == 0
    assert [r["key"] for r in json.loads(out.read_text())["records"]] == KEYS
