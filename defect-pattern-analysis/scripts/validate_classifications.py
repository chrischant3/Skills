#!/usr/bin/env python3
"""Check Claude's per-ticket classifications against the taxonomy before anything is counted.

Usage: validate_classifications.py <classifications_dir_or_file> --issues clean/ --out work/classified.json
                                   [--taxonomy reference/taxonomy.md]

Each input file holds a JSON list of records (or {"classifications": [...]}), one per ticket:
  key, defect_type, trigger, escape_stage, confidence (0 to 1), theme, reason

Rules:
- Every anonymised defect in clean/ is classified exactly once; no unknown keys.
- defect_type, trigger and escape_stage must be values from the taxonomy, spelt exactly.
- Confidence below 0.6, or defect_type "unclassified", makes the ticket unclassified. It
  then needs a one-line reason.
- A classified ticket needs a theme: one line, at most 80 characters, in Claude's own
  words, with no handles, emails, mentions or pseudonyms.
- No other fields are allowed, so person data can't be carried into the counts.

If anything is wrong, every problem is printed and nothing is written, so the bad
records can be fixed and the check run again.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import clean_data

CONFIDENCE_FLOOR = 0.6
UNCLASSIFIED = "unclassified"
FIELDS = {"key", "defect_type", "trigger", "escape_stage", "confidence", "theme", "reason"}
THEME_MAX = 80
REASON_MAX = 200
UNSAFE_TEXT = [
    (re.compile(r"@"), "an @handle or email"),
    (re.compile(r"\[~"), "a Jira mention"),
    (re.compile(r"person_[0-9a-f]{12}"), "a pseudonym"),
    (re.compile(r"\[person\]"), "a redacted person"),
]
DEFAULT_TAXONOMY = Path(__file__).resolve().parent.parent / "reference" / "taxonomy.md"


def load_taxonomy(path) -> dict:
    """Read the version and allowed values from reference/taxonomy.md.

    Returns {"version", "defect_type": [...], "trigger": [...], "escape_stage": [...]}.
    """
    text = Path(path).read_text(encoding="utf-8")
    version = re.search(r"^# Defect taxonomy (v\S+)", text, re.M)
    sections = dict(re.findall(r"^## ([^\n(]+?)\s*(?:\([^)]*\))?\n(.*?)(?=^## |\Z)", text, re.M | re.S))
    types = re.findall(r"^- ([a-z_]+):", sections.get("Defect type", ""), re.M)
    listed = lambda name: [v.strip() for v in sections.get(name, "").strip().split(",") if v.strip()]  # noqa: E731
    taxonomy = {"version": version.group(1) if version else None, "defect_type": types,
                "trigger": listed("Trigger"), "escape_stage": listed("Escape stage")}
    if not taxonomy["version"] or not all(taxonomy[k] for k in ("defect_type", "trigger", "escape_stage")):
        raise ValueError(f"could not read the taxonomy from {path}")
    return taxonomy


def _one_line(value, limit) -> bool:
    return isinstance(value, str) and value.strip() != "" and "\n" not in value and len(value.strip()) <= limit


def _unsafe(value: str) -> str | None:
    return next((what for pattern, what in UNSAFE_TEXT if pattern.search(value)), None)


def _check_record(rec, taxonomy, summaries) -> tuple[dict | None, list[str]]:
    key = rec.get("key") if isinstance(rec, dict) else None
    if not isinstance(rec, dict) or not isinstance(key, str):
        return None, [f"record {rec!r}: each record must be an object with a string key"]
    errors = []
    extra = sorted(set(rec) - FIELDS)
    if extra:
        errors.append(f"{key}: fields {extra} are not allowed; only {sorted(FIELDS)}")
    conf = rec.get("confidence")
    if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
        errors.append(f"{key}: confidence must be a number from 0 to 1, got {conf!r}")
        conf = None
    for field in ("defect_type", "trigger", "escape_stage"):
        value = rec.get(field)
        allowed = taxonomy[field] + ([UNCLASSIFIED] if field == "defect_type" else [])
        if value is not None and value not in allowed:
            errors.append(f"{key}: {field} {value!r} is not in taxonomy {taxonomy['version']}")
    unclassified = rec.get("defect_type") == UNCLASSIFIED or (conf is not None and conf < CONFIDENCE_FLOOR)
    reason, theme = rec.get("reason"), rec.get("theme")
    if unclassified:
        if not _one_line(reason, REASON_MAX):
            errors.append(f"{key}: unclassified tickets need a one-line reason of at most {REASON_MAX} characters")
        elif _unsafe(reason):
            errors.append(f"{key}: reason contains {_unsafe(reason)}")
    else:
        for field in ("defect_type", "trigger", "escape_stage"):
            if rec.get(field) is None:
                errors.append(f"{key}: {field} is required for a classified ticket")
        if not _one_line(theme, THEME_MAX):
            errors.append(f"{key}: theme must be one line of 1 to {THEME_MAX} characters")
        elif _unsafe(theme):
            errors.append(f"{key}: theme contains {_unsafe(theme)}")
        elif summaries.get(key) and theme.strip().lower() == summaries[key].strip().lower():
            errors.append(f"{key}: theme copies the ticket summary; describe it in your own words")
        if reason is not None and (not _one_line(reason, REASON_MAX) or _unsafe(reason)):
            errors.append(f"{key}: reason must be one safe line of at most {REASON_MAX} characters")
    if errors:
        return None, errors
    return {"key": key, "status": UNCLASSIFIED if unclassified else "classified",
            "defect_type": rec.get("defect_type") if not unclassified else None,
            "theme": " ".join(theme.split()) if not unclassified else None,
            "trigger": rec.get("trigger") if not unclassified else None,
            "escape_stage": rec.get("escape_stage") if not unclassified else None,
            "confidence": conf, "reason": reason.strip() if isinstance(reason, str) else None}, []


def validate(records, issue_keys, taxonomy, summaries=None) -> tuple[dict, list[str]]:
    """Validate records against the taxonomy and the set of anonymised defects.

    Args:
        records: Claude's per-ticket objects.
        issue_keys: every key in clean/.
        taxonomy: from load_taxonomy().
        summaries: optional key -> summary, to catch themes copied from the ticket.
    Returns:
        (result, errors). result is {"taxonomy_version", "records"}; use it only if errors is empty.
    """
    summaries = summaries or {}
    known, seen, errors, accepted = set(issue_keys), set(), [], []
    for rec in records:
        checked, problems = _check_record(rec, taxonomy, summaries)
        errors += problems
        key = rec.get("key") if isinstance(rec, dict) else None
        if isinstance(key, str):
            if key in seen:
                errors.append(f"{key}: classified more than once")
            elif key not in known:
                errors.append(f"{key}: not in clean/ (no such anonymised defect)")
            seen.add(key)
        if checked and checked["key"] in known:
            accepted.append(checked)
    missing = sorted(known - seen)
    if missing:
        errors.append(f"missing classifications for: {', '.join(missing)}")
    accepted.sort(key=lambda r: r["key"])
    return {"taxonomy_version": taxonomy["version"], "records": accepted}, errors


def _read_records(source: Path) -> list:
    paths = sorted(source.glob("*.json")) if source.is_dir() else [source]
    records = []
    for path in paths:
        doc = json.loads(path.read_text(encoding="utf-8"))
        records += doc.get("classifications", []) if isinstance(doc, dict) else doc
    return records


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Validate classifications against the taxonomy.")
    ap.add_argument("classifications", help="a JSON file, or a folder of them")
    ap.add_argument("--issues", default="clean")
    ap.add_argument("--taxonomy", default=str(DEFAULT_TAXONOMY))
    ap.add_argument("--out", default="work/classified.json")
    a = ap.parse_args(argv)
    issues = clean_data.load_clean_issues(a.issues)
    summaries = {i["key"]: clean_data.text_of(i["fields"].get("summary")) for i in issues}
    result, errors = validate(_read_records(Path(a.classifications)), list(summaries), load_taxonomy(a.taxonomy), summaries)
    if errors:
        print(f"{len(errors)} problem(s); nothing written:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    n_un = sum(r["status"] == UNCLASSIFIED for r in result["records"])
    print(f"Validated {len(result['records'])} classifications ({n_un} unclassified) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
