#!/usr/bin/env python3
"""Check verifier verdict files against the verdict format.

Usage: python3 check_verdict.py <verdict.json> [more.json ...]

Checks what references/verdict-schema.json enforces (required fields, enums, the overall
verdict rule, repro details on failed claims, no transcript text in rationalisations), plus
one cross-field check a schema can't express: same_provider must agree with the providers
named in builder_model and verifier_model.

The provider is the part of a model id before the first "/" (compared case-insensitively).
An id with no "/" is an error, not a skipped check: without a provider, same_provider can't
be confirmed, and a record of independence that can't be confirmed is not worth keeping.

Exit status: 0 if every file is valid, 1 if any file is invalid, 2 on a usage error.
Needs only Python 3.10 or later.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

TOP_LEVEL_FIELDS = [
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
OPTIONAL_TOP_LEVEL_FIELDS = ["rationalisations"]
CLAIM_FIELDS = [
    "claim",
    "risk",
    "verdict",
    "method",
    "evidence",
    "expected",
    "observed",
    "repro",
]
RULE_FIELDS = [
    "rule_id",
    "applicable",
    "risk",
    "applicability_reason",
    "verdict",
    "evidence",
    "flags",
]
RATIONALISATION_FIELDS = ["rule_id", "location", "source", "table_entry", "new"]
LOCATION_FIELDS = ["transcript_id", "message_index", "part_id"]

RISKS = ["high", "medium", "low"]
OVERALL_VERDICTS = ["Pass", "Fail", "Inconclusive"]
CLAIM_VERDICTS = ["Verified", "Failed", "Unverified"]
RULE_VERDICTS = ["Followed", "Broken", "Unverified"]
METHODS = ["executed", "inspected"]
PROFILES = [None, "rule-compliance"]
SOURCES = ["final_summary", "reasoning", "other_transcript"]
FLAG_PATTERN = re.compile(r"^(not_considered|ambiguous|conflicts_with:.+)$")


def provider_of(model_id):
    """Return the lower-cased provider prefix of a model id, or None if it has none."""
    if not isinstance(model_id, str) or "/" not in model_id:
        return None
    provider, _, model = model_id.partition("/")
    return provider.lower() if provider and model else None


def is_text(value):
    return isinstance(value, str) and value != ""


class Checker:
    """Collects problems for one verdict file as "<field path>: <message>" strings."""

    def __init__(self):
        self.problems = []

    def add(self, path, message):
        self.problems.append(f"{path}: {message}")

    def fields(self, obj, path, required, optional=()):
        """Report missing and unknown keys. Returns False if obj is not an object."""
        if not isinstance(obj, dict):
            self.add(path or "file", "must be an object")
            return False
        prefix = f"{path}." if path else ""
        for key in required:
            if key not in obj:
                self.add(f"{prefix}{key}", "missing required field")
        for key in obj:
            if key not in required and key not in optional:
                self.add(f"{prefix}{key}", "unknown field")
        return True

    def text(self, obj, key, path, nullable=False):
        if key not in obj:
            return
        value = obj[key]
        if value is None and nullable:
            return
        if not is_text(value):
            self.add(
                path, "must be a non-empty string" + (" or null" if nullable else "")
            )

    def choice(self, obj, key, path, allowed):
        if key in obj and obj[key] not in allowed:
            self.add(path, f"is {obj[key]!r}; must be one of {allowed}")

    def boolean(self, obj, key, path, nullable=False):
        if key not in obj:
            return
        value = obj[key]
        if isinstance(value, bool) or (nullable and value is None):
            return
        self.add(path, "must be true or false" + (" or null" if nullable else ""))

    def items(self, obj, key, path):
        """Return the list at obj[key], reporting a non-list. Missing keys give an empty list."""
        value = obj.get(key, [])
        if not isinstance(value, list):
            self.add(path, "must be a list")
            return []
        return value


def check_claim(c, claim, path):
    if not c.fields(claim, path, CLAIM_FIELDS):
        return
    c.text(claim, "claim", f"{path}.claim")
    c.text(claim, "evidence", f"{path}.evidence")
    c.choice(claim, "risk", f"{path}.risk", RISKS)
    c.choice(claim, "verdict", f"{path}.verdict", CLAIM_VERDICTS)
    c.choice(claim, "method", f"{path}.method", METHODS + [None])
    for key in ("expected", "observed", "repro"):
        c.text(claim, key, f"{path}.{key}", nullable=True)
    verdict = claim.get("verdict")
    if verdict == "Failed":
        for key in ("expected", "observed", "repro"):
            if key in claim and not is_text(claim[key]):
                c.add(
                    f"{path}.{key}",
                    "a Failed claim must say what was expected, observed and how to reproduce it",
                )
    if verdict in ("Verified", "Failed") and claim.get("method", "missing") is None:
        c.add(
            f"{path}.method",
            f"a {verdict} claim must say how it was checked (executed or inspected)",
        )


def check_rule(c, rule, path):
    if not c.fields(rule, path, RULE_FIELDS):
        return
    c.text(rule, "rule_id", f"{path}.rule_id")
    c.text(rule, "applicability_reason", f"{path}.applicability_reason")
    c.text(rule, "evidence", f"{path}.evidence")
    c.boolean(rule, "applicable", f"{path}.applicable")
    flags = c.items(rule, "flags", f"{path}.flags")
    for i, flag in enumerate(flags):
        if not isinstance(flag, str) or not FLAG_PATTERN.match(flag):
            c.add(
                f"{path}.flags[{i}]",
                f"is {flag!r}; must be not_considered, ambiguous or conflicts_with:<rule_id>",
            )
    if len(set(map(json.dumps, flags))) != len(flags):
        c.add(f"{path}.flags", "must not repeat a flag")
    if rule.get("applicable") is True:
        c.choice(rule, "verdict", f"{path}.verdict", RULE_VERDICTS)
        c.choice(rule, "risk", f"{path}.risk", RISKS)
    elif rule.get("applicable") is False:
        if rule.get("verdict") is not None:
            c.add(f"{path}.verdict", "must be null when the rule is not applicable")
        if rule.get("risk") is not None:
            c.add(f"{path}.risk", "must be null when the rule is not applicable")


def check_rationalisation(c, entry, path):
    if not c.fields(entry, path, RATIONALISATION_FIELDS):
        return
    c.text(entry, "rule_id", f"{path}.rule_id")
    c.choice(entry, "source", f"{path}.source", SOURCES)
    c.boolean(entry, "new", f"{path}.new")
    if entry.get("new") is True and entry.get("table_entry") is not None:
        c.add(f"{path}.table_entry", "must be null when the excuse is new")
    if entry.get("new") is False and not is_text(entry.get("table_entry")):
        c.add(
            f"{path}.table_entry",
            "must name the matching table entry when the excuse is not new",
        )
    if "location" in entry:
        location = entry["location"]
        loc_path = f"{path}.location"
        if c.fields(location, loc_path, LOCATION_FIELDS):
            c.text(
                location, "transcript_id", f"{loc_path}.transcript_id", nullable=True
            )
            c.text(location, "part_id", f"{loc_path}.part_id", nullable=True)
            index = location.get("message_index")
            valid_index = index is None or (
                isinstance(index, int) and not isinstance(index, bool) and index >= 0
            )
            if not valid_index:
                c.add(
                    f"{loc_path}.message_index",
                    "must be a non-negative integer or null",
                )


def expected_overall_verdict(claims, rules):
    """Apply the overall verdict rule. Returns (verdict, reason)."""
    claims = [x for x in claims if isinstance(x, dict)]
    rules = [x for x in rules if isinstance(x, dict) and x.get("applicable") is True]
    for i, claim in enumerate(claims):
        if claim.get("verdict") == "Failed":
            return "Fail", f"claim {i} is Failed"
    for rule in rules:
        if rule.get("verdict") == "Broken":
            return "Fail", f"rule {rule.get('rule_id')!r} is Broken"
    for i, claim in enumerate(claims):
        if claim.get("verdict") == "Unverified" and claim.get("risk") == "high":
            return "Inconclusive", f"claim {i} is Unverified and high-risk"
    for rule in rules:
        if rule.get("verdict") == "Unverified" and rule.get("risk") == "high":
            return (
                "Inconclusive",
                f"rule {rule.get('rule_id')!r} is Unverified and high-risk",
            )
    if not claims:
        return "Inconclusive", "the claim list is empty"
    return "Pass", "no claim or rule failed or is high-risk and unverified"


def check_providers(c, data):
    providers = {}
    for key in ("builder_model", "verifier_model"):
        if key not in data:
            continue
        if not is_text(data[key]):
            c.add(key, "must be a non-empty string")
            continue
        providers[key] = provider_of(data[key])
        if providers[key] is None:
            c.add(
                key,
                f"{data[key]!r} has no provider prefix; write it as <provider>/<model>",
            )
    same = data.get("same_provider")
    if (
        len(providers) == 2
        and None not in providers.values()
        and isinstance(same, bool)
    ):
        actual = providers["builder_model"] == providers["verifier_model"]
        if same != actual:
            c.add(
                "same_provider",
                f"is {str(same).lower()}, but the model ids name providers "
                f"{providers['builder_model']!r} and {providers['verifier_model']!r}",
            )


def check_date(c, data):
    if "date" not in data:
        return
    value = data["date"]
    try:
        if not isinstance(value, str):
            raise ValueError
        # Python 3.10's fromisoformat doesn't accept a trailing Z.
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        c.add("date", f"{value!r} is not an ISO 8601 date-time")


def check_verdict(data):
    """Return a list of problems with a parsed verdict file. An empty list means it is valid."""
    c = Checker()
    if not c.fields(data, "", TOP_LEVEL_FIELDS, OPTIONAL_TOP_LEVEL_FIELDS):
        return c.problems
    for key in ("run_id", "repo", "task", "summary"):
        c.text(data, key, key)
    check_date(c, data)
    check_providers(c, data)
    c.boolean(data, "same_provider", "same_provider")
    c.boolean(data, "reasoning_available", "reasoning_available", nullable=True)
    c.choice(data, "profile", "profile", PROFILES)
    c.choice(data, "overall_verdict", "overall_verdict", OVERALL_VERDICTS)
    if "audit" in data and data["audit"] is not None:
        c.add("audit", "must be null until the auditor exists")
    for i, note in enumerate(c.items(data, "observations", "observations")):
        if not is_text(note):
            c.add(f"observations[{i}]", "must be a non-empty string")

    claims = c.items(data, "claims", "claims")
    rules = c.items(data, "rules", "rules")
    for i, claim in enumerate(claims):
        check_claim(c, claim, f"claims[{i}]")
    for i, rule in enumerate(rules):
        check_rule(c, rule, f"rules[{i}]")
    if "rationalisations" in data:
        for i, entry in enumerate(
            c.items(data, "rationalisations", "rationalisations")
        ):
            check_rationalisation(c, entry, f"rationalisations[{i}]")

    if (
        data.get("overall_verdict") in OVERALL_VERDICTS
        and "claims" in data
        and "rules" in data
    ):
        expected, reason = expected_overall_verdict(claims, rules)
        if data["overall_verdict"] != expected:
            c.add(
                "overall_verdict",
                f"is {data['overall_verdict']!r}, but the verdict rule gives "
                f"{expected!r} because {reason}",
            )
    return c.problems


def check_file(path):
    """Return a list of problems with the verdict file at path."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        return [f"cannot read file: {error.strerror}"]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        return [f"not valid JSON: {error}"]
    return check_verdict(data)


def main(argv):
    if not argv:
        print("usage: check_verdict.py <verdict.json> [more.json ...]", file=sys.stderr)
        return 2
    failed = False
    for path in argv:
        for problem in check_file(path):
            failed = True
            print(f"{path}: {problem}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
