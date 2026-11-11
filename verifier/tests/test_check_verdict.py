"""Behaviour tests for check_verdict.py: run the checker on verdict files and assert on its exit code and messages."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_verdict.py"
EXAMPLE = ROOT / "references" / "verdict-example.json"
SCHEMA = ROOT / "references" / "verdict-schema.json"


def verified_claim(**overrides):
    claim = {
        "claim": "All unit tests pass",
        "risk": "high",
        "verdict": "Verified",
        "method": "executed",
        "evidence": "Ran the test suite: 12 passed, 0 failed",
        "expected": None,
        "observed": None,
        "repro": None,
    }
    claim.update(overrides)
    return claim


def failed_claim(**overrides):
    fields = {
        "verdict": "Failed",
        "expected": "0 failures",
        "observed": "1 failure",
        "repro": "Run the test suite",
    }
    fields.update(overrides)
    return verified_claim(**fields)


def rule(**overrides):
    entry = {
        "rule_id": "testing/tdd-first",
        "applicable": True,
        "risk": "high",
        "applicability_reason": "Task adds new behaviour",
        "verdict": "Followed",
        "evidence": "Test file edited and run before the implementation",
        "flags": [],
    }
    entry.update(overrides)
    return entry


def not_applicable_rule():
    return rule(
        rule_id="database/migrations",
        applicable=False,
        risk=None,
        verdict=None,
        applicability_reason="No database change",
        evidence="Diff touches no schema",
    )


def rationalisation(**overrides):
    entry = {
        "rule_id": "testing/tdd-first",
        "location": {"transcript_id": "session-1", "message_index": 3, "part_id": None},
        "source": "final_summary",
        "table_entry": "I'll write the test straight after.",
        "new": False,
    }
    entry.update(overrides)
    return entry


def valid_verdict(**overrides):
    verdict = {
        "run_id": "2026-11-08T14-32-05Z-a1b2c3",
        "date": "2026-11-08T14:32:05Z",
        "repo": "example-org/example-repo",
        "task": "Add a cache",
        "builder_model": "openai/gpt-x",
        "verifier_model": "anthropic/claude-opus-x",
        "same_provider": False,
        "profile": "rule-compliance",
        "reasoning_available": False,
        "overall_verdict": "Pass",
        "summary": "Pass. All claims verified by execution. High confidence.",
        "claims": [verified_claim()],
        "rules": [rule(), not_applicable_rule()],
        "rationalisations": [],
        "observations": [],
        "audit": None,
    }
    verdict.update(overrides)
    return verdict


def run_checker(*paths):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, paths)],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout + result.stderr


def check(tmp_path, data, name="verdict.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return run_checker(path)


def assert_invalid(tmp_path, data, *expected_fragments):
    code, output = check(tmp_path, data)
    assert code != 0, output
    for fragment in expected_fragments:
        assert fragment in output, output


# Valid files


def test_committed_example_passes():
    code, output = run_checker(EXAMPLE)
    assert code == 0, output


def test_minimal_valid_verdict_passes(tmp_path):
    code, output = check(tmp_path, valid_verdict())
    assert code == 0, output


def test_rationalisations_field_is_optional(tmp_path):
    data = valid_verdict()
    del data["rationalisations"]
    code, output = check(tmp_path, data)
    assert code == 0, output


def test_core_profile_with_no_transcript_passes(tmp_path):
    code, output = check(
        tmp_path, valid_verdict(profile=None, reasoning_available=None, rules=[])
    )
    assert code == 0, output


# Command line


def test_no_arguments_is_a_usage_error():
    code, output = run_checker()
    assert code != 0
    assert "usage" in output.lower()


def test_reports_only_the_invalid_file_among_several(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(valid_verdict()), encoding="utf-8")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(valid_verdict(overall_verdict="Maybe")), encoding="utf-8")
    code, output = run_checker(good, bad)
    assert code != 0
    assert "bad.json" in output
    assert "good.json" not in output


def test_missing_file_is_reported(tmp_path):
    code, output = run_checker(tmp_path / "nope.json")
    assert code != 0
    assert "nope.json" in output


def test_invalid_json_is_reported(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    code, output = run_checker(path)
    assert code != 0
    assert "broken.json" in output
    assert "JSON" in output


# Required fields and shapes

REQUIRED = [
    "run_id",
    "date",
    "repo",
    "task",
    "builder_model",
    "verifier_model",
    "same_provider",
    "profile",
    "reasoning_available",
    "overall_verdict",
    "summary",
    "claims",
    "rules",
    "observations",
    "audit",
]


@pytest.mark.parametrize("field", REQUIRED)
def test_each_missing_required_field_is_reported(tmp_path, field):
    data = valid_verdict()
    del data[field]
    assert_invalid(tmp_path, data, field, "missing")


def test_required_list_matches_schema():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert sorted(schema["required"]) == sorted(REQUIRED)


def test_unknown_top_level_field_is_reported(tmp_path):
    assert_invalid(tmp_path, valid_verdict(extra=1), "extra")


def test_empty_summary_is_reported(tmp_path):
    assert_invalid(tmp_path, valid_verdict(summary=""), "summary")


def test_same_provider_must_be_boolean(tmp_path):
    assert_invalid(tmp_path, valid_verdict(same_provider="no"), "same_provider")


def test_reasoning_available_must_be_boolean_or_null(tmp_path):
    assert_invalid(
        tmp_path, valid_verdict(reasoning_available="no"), "reasoning_available"
    )


def test_audit_must_be_null(tmp_path):
    assert_invalid(tmp_path, valid_verdict(audit={}), "audit")


# Enums


@pytest.mark.parametrize(
    "overrides, fragment",
    [
        ({"overall_verdict": "pass"}, "overall_verdict"),
        ({"profile": "kilo"}, "profile"),
        ({"claims": [verified_claim(risk="critical")]}, "claims[0].risk"),
        ({"claims": [verified_claim(verdict="Probably")]}, "claims[0].verdict"),
        ({"claims": [verified_claim(method="guessed")]}, "claims[0].method"),
        ({"rules": [rule(verdict="Ignored")]}, "rules[0].verdict"),
        ({"rules": [rule(risk="critical")]}, "rules[0].risk"),
        ({"rules": [rule(flags=["weird"])]}, "rules[0].flags"),
        (
            {"rationalisations": [rationalisation(source="chat")]},
            "rationalisations[0].source",
        ),
    ],
)
def test_invalid_enum_values_are_reported(tmp_path, overrides, fragment):
    assert_invalid(tmp_path, valid_verdict(**overrides), fragment)


def test_conflicts_with_flag_is_accepted(tmp_path):
    data = valid_verdict(
        rules=[rule(flags=["conflicts_with:deps/ask-first", "ambiguous"])]
    )
    code, output = check(tmp_path, data)
    assert code == 0, output


# Claim and rule details


@pytest.mark.parametrize("field", ["expected", "observed", "repro"])
def test_failed_claim_needs_expected_observed_and_repro(tmp_path, field):
    claim = failed_claim(**{field: None})
    assert_invalid(
        tmp_path,
        valid_verdict(claims=[claim], overall_verdict="Fail"),
        f"claims[0].{field}",
    )


def test_verified_claim_needs_a_method(tmp_path):
    assert_invalid(
        tmp_path,
        valid_verdict(claims=[verified_claim(method=None)]),
        "claims[0].method",
    )


def test_unverified_claim_may_have_no_method(tmp_path):
    claims = [
        verified_claim(),
        verified_claim(risk="low", verdict="Unverified", method=None),
    ]
    code, output = check(tmp_path, valid_verdict(claims=claims))
    assert code == 0, output


def test_not_applicable_rule_must_have_null_verdict_and_risk(tmp_path):
    entry = not_applicable_rule()
    entry["verdict"] = "Followed"
    entry["risk"] = "low"
    assert_invalid(
        tmp_path, valid_verdict(rules=[entry]), "rules[0].verdict", "rules[0].risk"
    )


def test_applicable_rule_needs_verdict_and_risk(tmp_path):
    assert_invalid(
        tmp_path,
        valid_verdict(rules=[rule(verdict=None, risk=None)]),
        "rules[0].verdict",
        "rules[0].risk",
    )


# Rationalisations


def test_quote_in_rationalisation_is_rejected(tmp_path):
    entry = rationalisation(quote="I skipped the test")
    assert_invalid(
        tmp_path, valid_verdict(rationalisations=[entry]), "rationalisations[0].quote"
    )


def test_text_in_location_is_rejected(tmp_path):
    entry = rationalisation()
    entry["location"]["text"] = "copied words"
    assert_invalid(
        tmp_path,
        valid_verdict(rationalisations=[entry]),
        "rationalisations[0].location.text",
    )


def test_location_needs_every_pointer_field(tmp_path):
    entry = rationalisation()
    del entry["location"]["part_id"]
    assert_invalid(
        tmp_path,
        valid_verdict(rationalisations=[entry]),
        "rationalisations[0].location.part_id",
    )


def test_location_index_must_be_a_non_negative_integer(tmp_path):
    entry = rationalisation()
    entry["location"]["message_index"] = -1
    assert_invalid(
        tmp_path,
        valid_verdict(rationalisations=[entry]),
        "rationalisations[0].location.message_index",
    )


def test_new_excuse_must_have_null_table_entry(tmp_path):
    entry = rationalisation(new=True)
    assert_invalid(
        tmp_path,
        valid_verdict(rationalisations=[entry]),
        "rationalisations[0].table_entry",
    )


def test_known_excuse_must_name_its_table_entry(tmp_path):
    entry = rationalisation(table_entry=None)
    assert_invalid(
        tmp_path,
        valid_verdict(rationalisations=[entry]),
        "rationalisations[0].table_entry",
    )


# Overall verdict rule


@pytest.mark.parametrize(
    "claims, rules, verdict",
    [
        ([failed_claim()], [rule()], "Fail"),
        ([verified_claim()], [rule(verdict="Broken")], "Fail"),
        ([], [rule(verdict="Broken")], "Fail"),
        ([failed_claim()], [rule(verdict="Unverified")], "Fail"),
        ([verified_claim(verdict="Unverified", method=None)], [rule()], "Inconclusive"),
        ([verified_claim()], [rule(verdict="Unverified")], "Inconclusive"),
        ([], [rule()], "Inconclusive"),
        ([], [], "Inconclusive"),
        (
            [verified_claim(risk="low", verdict="Unverified", method=None)],
            [rule(risk="low", verdict="Unverified")],
            "Pass",
        ),
        ([verified_claim()], [rule(), not_applicable_rule()], "Pass"),
    ],
)
def test_overall_verdict_rule(tmp_path, claims, rules, verdict):
    for candidate in ("Pass", "Fail", "Inconclusive"):
        code, output = check(
            tmp_path,
            valid_verdict(
                claims=copy.deepcopy(claims),
                rules=copy.deepcopy(rules),
                overall_verdict=candidate,
            ),
        )
        if candidate == verdict:
            assert code == 0, output
        else:
            assert code != 0, f"{candidate} accepted, expected {verdict}"
            assert "overall_verdict" in output
            assert verdict in output


# Provider cross-check


@pytest.mark.parametrize(
    "builder, verifier, same",
    [
        ("openai/gpt-x", "anthropic/claude-opus-x", False),
        ("anthropic/claude-haiku-x", "anthropic/claude-opus-x", True),
        ("Anthropic/claude-haiku-x", "anthropic/claude-opus-x", True),
    ],
)
def test_same_provider_matching_model_ids_passes(tmp_path, builder, verifier, same):
    code, output = check(
        tmp_path,
        valid_verdict(
            builder_model=builder, verifier_model=verifier, same_provider=same
        ),
    )
    assert code == 0, output


@pytest.mark.parametrize(
    "builder, verifier, same",
    [
        ("openai/gpt-x", "anthropic/claude-opus-x", True),
        ("anthropic/claude-haiku-x", "anthropic/claude-opus-x", False),
    ],
)
def test_same_provider_disagreeing_with_model_ids_is_reported(
    tmp_path, builder, verifier, same
):
    data = valid_verdict(
        builder_model=builder, verifier_model=verifier, same_provider=same
    )
    assert_invalid(tmp_path, data, "same_provider")


@pytest.mark.parametrize("field", ["builder_model", "verifier_model"])
def test_model_id_without_provider_prefix_is_reported(tmp_path, field):
    assert_invalid(
        tmp_path, valid_verdict(**{field: "claude-opus-x"}), field, "provider"
    )
