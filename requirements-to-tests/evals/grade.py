#!/usr/bin/env python3
"""Grade eval runs with regex assertions over each run's Markdown + xlsx text.

Usage: grade.py <iteration-dir>
Writes grading.json into every eval-N-<name>/<config>/run-K/ directory, in the skill-creator schema
(expectations[] with text/passed/evidence, plus summary).
"""

import json
import re
import sys
from pathlib import Path

import openpyxl


def corpus(outputs: Path) -> tuple[str, list[str]]:
    parts, sheets = [], []
    for md in outputs.rglob("*.md"):
        if md.name != "source.md":
            parts.append(md.read_text(encoding="utf-8", errors="replace"))
    for x in outputs.rglob("*.xlsx"):
        wb = openpyxl.load_workbook(x, read_only=True, data_only=True)
        for ws in wb.worksheets:
            sheets.append(ws.title)
            for row in ws.iter_rows(values_only=True):
                parts.append(" | ".join("" if v is None else str(v) for v in row))
    return "\n".join(parts), sheets


def near(text: str, anchor: str, pattern: str, window: int = 600) -> str | None:
    for m in re.finditer(re.escape(anchor), text):
        chunk = text[max(0, m.start() - window // 3) : m.end() + window]
        hit = re.search(pattern, chunk, re.IGNORECASE)
        if hit:
            return chunk[max(0, hit.start() - 60) : hit.end() + 60].replace("\n", " ")
    return None


def has(text: str, pattern: str) -> str | None:
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return text[max(0, m.start() - 60) : m.end() + 60].replace("\n", " ") if m else None


def common(text, sheets, outputs, ids):
    checks = []
    md = [
        p
        for p in outputs.rglob("*.md")
        if p.name not in {"source.md", "final_reply.md"}
    ]
    xl = list(outputs.rglob("*.xlsx"))
    checks.append(
        (
            "Produces a Markdown report and an xlsx workbook",
            bool(md and xl),
            f"md={[p.name for p in md]} xlsx={[p.name for p in xl]}",
        )
    )
    missing = [i for i in ids if i not in text]
    checks.append(
        (
            "Every requirement ID in the source document appears in the outputs",
            not missing,
            f"missing: {missing}" if missing else f"all {len(ids)} present",
        )
    )
    scen_sheet = [s for s in sheets if re.search(r"scen|test", s, re.I)]
    checks.append(
        ("Workbook has a scenarios/tests sheet", bool(scen_sheet), str(sheets))
    )
    ev = has(text, r"provisional|assum(ed|ption)")
    checks.append(
        ("Assumptions behind scenarios are explicitly marked", bool(ev), ev or "none")
    )
    q = len(re.findall(r"\?\s*(\||$)", text, re.M))
    checks.append(
        (
            "At least 8 stakeholder questions",
            q >= 8,
            f"{q} question marks at cell/line end",
        )
    )
    lib = has(
        text,
        r"Weinberg|Gause|Exploring Requirements|\bER[12]\b|Adzic|Cockburn|Clokie|DevOps Handbook|Kelly",
    )
    checks.append(
        ("Cites the requirements/testing books as a basis", bool(lib), lib or "none")
    )
    return checks


SPECIFIC = {
    "clinic-portal-docx": (
        [
            "BK-1",
            "BK-2",
            "BK-3",
            "REC-1",
            "REC-2",
            "REC-3",
            "SEC-1",
            "SEC-2",
            "SEC-3",
            "SEC-4",
            "PERF-1",
            "PERF-2",
            "PERF-3",
            "DATA-1",
            "DATA-2",
            "DATA-3",
            "DATA-4",
            "A-1",
        ],
        [
            (
                "SEC-1 'secure / best practice' flagged as vague or untestable",
                lambda t: near(
                    t,
                    "SEC-1",
                    r"vague|not measurable|untestable|ambigu|unmeasurable|not testable",
                ),
            ),
            (
                "A-1 'no audit logging' assumption challenged",
                lambda t: near(
                    t,
                    "A-1",
                    r"challeng|risk|reject|unsafe|contradict|disagree|dangerous|should not|must be",
                ),
            ),
            (
                "SEC-4 'admins see all data' questioned (least privilege)",
                lambda t: near(
                    t,
                    "SEC-4",
                    r"least privilege|excessive|restrict|justif|break.?glass|too broad|all data",
                ),
            ),
            (
                "Gap: one patient accessing another patient's records",
                lambda t: has(t, r"(another|other|different) patient"),
            ),
            (
                "Health data treated as special category data",
                lambda t: has(t, r"special category"),
            ),
            (
                "Lockout boundary scenario (4th vs 5th failure)",
                lambda t: has(
                    t, r"(four|4)(th)? (consecutive )?(failed|failure|wrong|incorrect)"
                ),
            ),
        ],
    ),
    "payouts-api-pdf": (
        [
            "NFR-P1",
            "NFR-P2",
            "NFR-P3",
            "NFR-P4",
            "NFR-A1",
            "NFR-A2",
            "NFR-A3",
            "NFR-S1",
            "NFR-S2",
            "NFR-S3",
            "NFR-S4",
            "NFR-D1",
            "NFR-D2",
            "NFR-D3",
            "NFR-D4",
        ],
        [
            (
                "NFR-P1 missing tail/max or load conditions flagged",
                lambda t: near(
                    t,
                    "NFR-P1",
                    r"p99|99th|tail|max(imum)?\b|remaining 5|what load|under what",
                ),
            ),
            (
                "Peak (Black Friday ~5x) load profile used",
                lambda t: has(t, r"black friday|5\s?x|five times|10 ?(million|m)\b"),
            ),
            (
                "NFR-P4 'load quickly' flagged vague",
                lambda t: near(
                    t,
                    "NFR-P4",
                    r"vague|not measurable|untestable|ambigu|unmeasurable|not testable|no (number|threshold)",
                ),
            ),
            (
                "NFR-A2 tested as RTO/RPO restore drill",
                lambda t: has(t, r"RTO.*RPO|RPO.*RTO"),
            ),
            ("Rate limit boundary (100 vs 101 req/s)", lambda t: has(t, r"\b101\b")),
            (
                "NFR-D4 duplicate/idempotency scenario",
                lambda t: near(t, "NFR-D4", r"idempot|duplicate|twice|retry"),
            ),
        ],
    ),
    "crm-migration-xlsx": (
        [
            "MIG-01",
            "MIG-02",
            "MIG-03",
            "MIG-04",
            "MIG-05",
            "DAT-01",
            "DAT-02",
            "DAT-03",
            "DAT-04",
            "REP-01",
            "ACC-01",
            "PER-01",
            "PER-02",
            "INT-01",
        ],
        [
            (
                "MIG-02 'no data loss' made testable via reconciliation",
                lambda t: has(t, r"reconcil"),
            ),
            (
                "DAT-02 asks what 'inactive' means",
                lambda t: near(
                    t,
                    "DAT-02",
                    r"inactiv\w*.{0,80}(defin|mean|count|what)|(defin|mean|what).{0,80}inactiv",
                ),
            ),
            (
                "DAT-02 six-year boundary examples",
                lambda t: has(
                    t, r"(5 years|6 years|six years).{0,200}(day|month|boundary)"
                ),
            ),
            (
                "Gap: rollback / fallback if migration fails",
                lambda t: has(t, r"roll ?back|fall ?back|back-?out"),
            ),
            (
                "PER-01 needs a legacy baseline measurement",
                lambda t: near(
                    t,
                    "PER-01",
                    r"baseline|benchmark|measure (the )?legacy|current (value|timings?)",
                ),
            ),
            (
                "DAT-03 region access boundary scenario",
                lambda t: near(
                    t, "DAT-03", r"other region|another region|different region|outside"
                ),
            ),
        ],
    ),
}


def main(iteration: Path) -> None:
    for eval_dir in sorted(p for p in iteration.glob("eval-*") if p.is_dir()):
        ids, specific = SPECIFIC[re.sub(r"^eval-\d+-", "", eval_dir.name)]
        for run in sorted(eval_dir.glob("*/run-*")):
            outputs = run / "outputs"
            text, sheets = corpus(outputs)
            results = common(text, sheets, outputs, ids)
            for name, fn in specific:
                ev = fn(text)
                results.append((name, bool(ev), ev or "not found"))
            expectations = [
                {"text": n, "passed": p, "evidence": e} for n, p, e in results
            ]
            passed = sum(e["passed"] for e in expectations)
            grading = {
                "expectations": expectations,
                "summary": {
                    "passed": passed,
                    "failed": len(expectations) - passed,
                    "total": len(expectations),
                    "pass_rate": round(passed / len(expectations), 3),
                },
            }
            (run / "grading.json").write_text(
                json.dumps(grading, indent=2), encoding="utf-8"
            )
            print(f"{eval_dir.name}/{run.parent.name}: {passed}/{len(expectations)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
