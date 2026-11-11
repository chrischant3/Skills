#!/usr/bin/env python3
"""Count validated classifications by type, theme, trigger, escape stage, team and period.

Usage: aggregate.py --classified work/classified.json --issues clean/ --out out/
                    [--min-group-size 5] [--period month|quarter]

Every count goes through suppress.py, so no group smaller than min_group_size (default 5,
never lower) appears in any output, and a small group can't be worked out from the
totals. Writes out/aggregate.json, one CSV per table and out/tables.md. Outputs hold
counts and labels only: no ticket keys, ticket text or people.

Team is the issue's Jira component. An issue with several components counts once, under
"multiple components"; one with none counts under "no component". So every defect is in
exactly one team, and the team rows add up to the total.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import clean_data
import suppress

UNCLASSIFIED = "unclassified"
NO_COMPONENT = "no component"
MULTIPLE_COMPONENTS = "multiple components"
GROUPINGS = [
    (),
    ("type",),
    ("type", "theme"),
    ("period",),
    ("type", "period"),
    ("type", "theme", "period"),
    ("trigger",),
    ("escape_stage",),
    ("team",),
    ("team", "type"),
]
TABLES = {
    "types": (("type",), None),
    "type_trend": (("type",), "period"),
    "themes": (("type", "theme"), None),
    "theme_trend": (("type", "theme"), "period"),
    "triggers": (("trigger",), None),
    "escape_stages": (("escape_stage",), None),
    "teams": (("team",), "type"),
    "periods": (("period",), None),
}


def period_of(created: str, period: str) -> str:
    """Return YYYY-MM or YYYY-Qn for a Jira created timestamp (its local date as recorded)."""
    year, month = created[:4], int(created[5:7])
    return (
        f"{year}-{month:02d}"
        if period == "month"
        else f"{year}-Q{(month - 1) // 3 + 1}"
    )


def team_of(issue: dict) -> str:
    """The issue's team: its single component, or a fixed label for none or several."""
    names = sorted(
        {
            c.get("name")
            for c in issue["fields"].get("components") or []
            if isinstance(c, dict) and c.get("name")
        }
    )
    if not names:
        return NO_COMPONENT
    return names[0] if len(names) == 1 else MULTIPLE_COMPONENTS


def _canonical_themes(records) -> dict:
    """Map (type, lower-case theme) to one spelling: the most used, then alphabetical."""
    spellings = defaultdict(Counter)
    for r in records:
        if r["status"] != UNCLASSIFIED:
            spellings[(r["defect_type"], r["theme"].lower())][r["theme"]] += 1
    return {
        k: sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        for k, c in spellings.items()
    }


def build_records(issues, classified: dict, period: str) -> list[dict]:
    """Join anonymised issues to their validated classification, one dict of dimensions per defect.

    Raises:
        ValueError: if the classified keys don't match the issues exactly.
    """
    by_key = {r["key"]: r for r in classified["records"]}
    keys = {i["key"] for i in issues}
    if set(by_key) != keys:
        raise ValueError(
            "classified.json doesn't match clean/: rerun validate_classifications.py "
            f"(missing {len(keys - set(by_key))}, extra {len(set(by_key) - keys)})"
        )
    themes = _canonical_themes(classified["records"])
    out = []
    for issue in issues:
        r = by_key[issue["key"]]
        done = r["status"] != UNCLASSIFIED
        out.append(
            {
                "type": r["defect_type"] if done else UNCLASSIFIED,
                "theme": themes[(r["defect_type"], r["theme"].lower())]
                if done
                else UNCLASSIFIED,
                "trigger": r["trigger"] if done else UNCLASSIFIED,
                "escape_stage": r["escape_stage"] if done else UNCLASSIFIED,
                "team": team_of(issue),
                "period": period_of(issue["fields"]["created"], period),
            }
        )
    return out


def aggregate(
    clean_dir, classified_path, out_dir, min_group_size=None, period="month"
) -> suppress.Publication:
    """Build every suppressed table and write all outputs. Returns the Publication."""
    if period not in ("month", "quarter"):
        raise ValueError("period must be month or quarter")
    k = suppress.validate_min_group_size(min_group_size)
    issues = clean_data.load_clean_issues(clean_dir)
    classified = json.loads(Path(classified_path).read_text(encoding="utf-8"))
    pub = suppress.publish(build_records(issues, classified, period), GROUPINGS, k)
    pub.add_cell("defects_analysed", frozenset())
    pub.add_cell("unclassified", frozenset({("type", UNCLASSIFIED)}))
    report = clean_data.load_ingest_report(clean_dir) or {}
    if isinstance(report.get("matched"), int):
        pub.add_scalar("matched_by_query", report["matched"])
    for gap in ("changelog_incomplete", "comments_incomplete"):
        if isinstance(report.get(gap), list):
            pub.add_scalar(f"{gap}_defects", len(report[gap]))
    suppress.write_outputs(
        pub,
        TABLES,
        out_dir,
        settings={
            "taxonomy_version": classified.get("taxonomy_version"),
            "period": period,
            "team_rule": "Jira component; several components count once as 'multiple components'",
        },
    )
    return pub


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Aggregate validated classifications with small-group suppression."
    )
    ap.add_argument("--classified", default="work/classified.json")
    ap.add_argument("--issues", default="clean")
    ap.add_argument("--out", default="out")
    ap.add_argument(
        "--min-group-size",
        type=int,
        default=None,
        help="default 5; values below 5 are refused",
    )
    ap.add_argument("--period", choices=["month", "quarter"], default="month")
    a = ap.parse_args(argv)
    try:
        aggregate(a.issues, a.classified, a.out, a.min_group_size, a.period)
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    print(f"Wrote aggregate.json, CSVs and tables.md -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
