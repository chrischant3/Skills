#!/usr/bin/env python3
"""Validate an analysis.json and render it as a Markdown report and an xlsx workbook.

Usage:
    build_outputs.py <analysis.json> --out-dir <dir> [--stem <name>]

Writes <stem>-requirements-report.md and <stem>-requirements.xlsx. If validation finds
errors (broken traceability, bad enum values, duplicate IDs) nothing is written and the
exit code is 1. Warnings (untested requirements, vague NFRs, scenario lint) are printed
and also listed in the report, because they are findings the reader should see.

The schema is documented in references/schema.md; references/example-analysis.json is
a valid example.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

KINDS = {"function", "attribute", "constraint", "preference", "expectation", "imposition", "assumption"}
CATEGORIES = {
    "functional", "security", "performance", "data", "reliability", "usability",
    "compatibility", "maintainability", "portability", "safety", "operability", "other",
}
PRIORITIES = {"must", "want", "ignore", "unconfirmed"}
ORIGINS = {"stated", "implied"}
VISIBILITY = {"evident", "hidden", "opaque", "translucent", "frill"}
FORMATS = {"gherkin", "measurement", "checklist", "charter"}
RANGES = {"normal", "abnormal-reasonable", "abnormal-unreasonable"}
STATUSES = {"ready", "provisional"}
LAYERS = {"pre-release", "pipeline", "production"}
RISKS = {"high", "medium", "low"}
LEVELS = {"root", "branch", "twig"}

# Report order: the skill's focus areas first, functional last.
CATEGORY_ORDER = ["security", "performance", "data", "reliability", "operability", "usability",
                  "compatibility", "maintainability", "portability", "safety", "other", "functional"]
LEVEL_ORDER = {"root": 0, "branch": 1, "twig": 2}


def validate(analysis: dict) -> list[dict]:
    """Return a list of {"level": "error"|"warning", "message"} issues for the analysis.

    Errors break traceability or the schema; warnings are quality findings.
    """
    issues: list[dict] = []

    def error(msg):
        issues.append({"level": "error", "message": msg})

    def warn(msg):
        issues.append({"level": "warning", "message": msg})

    functions = analysis.get("functions", [])
    requirements = analysis.get("requirements", [])
    questions = analysis.get("questions", [])
    scenarios = analysis.get("scenarios", [])
    gaps = analysis.get("gaps", [])

    all_ids = [x.get("id") for x in functions + requirements + questions + scenarios]
    for dup, n in Counter(all_ids).items():
        if n > 1:
            error(f"Duplicate id {dup} used {n} times")
    function_ids = {f.get("id") for f in functions}
    req_ids = {r.get("id") for r in requirements}
    question_ids = {q.get("id") for q in questions}

    for f in functions:
        _check_enum(error, f, "visibility", VISIBILITY)

    for r in requirements:
        rid = r.get("id")
        for field in ("text", "source_ref"):
            if not r.get(field):
                error(f"{rid}: missing {field}")
        _check_enum(error, r, "kind", KINDS)
        _check_enum(error, r, "category", CATEGORIES)
        _check_enum(error, r, "priority", PRIORITIES)
        _check_enum(error, r, "origin", ORIGINS)
        for target in r.get("applies_to", []):
            if target != "product-wide" and target not in function_ids:
                error(f"{rid}: applies_to references unknown function {target}")
        for qid in r.get("question_ids", []):
            if qid not in question_ids:
                error(f"{rid}: references unknown question {qid}")

    for q in questions:
        _check_enum(error, q, "level", LEVELS)
        for target in q.get("blocks", []):
            if target not in req_ids and target not in {s.get("id") for s in scenarios}:
                error(f"{q.get('id')}: blocks unknown item {target}")

    for s in scenarios:
        sid = s.get("id")
        for field in ("category", "format", "range", "status", "layer", "risk"):
            allowed = {"category": CATEGORIES, "format": FORMATS, "range": RANGES, "status": STATUSES,
                       "layer": LAYERS, "risk": RISKS}[field]
            _check_enum(error, s, field, allowed)
        if not s.get("req_ids"):
            error(f"{sid}: traces to no requirement")
        for target in s.get("req_ids", []):
            if target not in req_ids:
                error(f"{sid}: traces to unknown requirement {target}")
        for a in s.get("assumptions", []):
            if a.get("question_id") and a["question_id"] not in question_ids:
                error(f"{sid}: assumption references unknown question {a['question_id']}")
        _lint_scenario(warn, s)

    for g in gaps:
        if g.get("question_id") and g["question_id"] not in question_ids:
            error(f"Gap '{g.get('missing', '')[:40]}' references unknown question {g['question_id']}")

    asked_about = {t for q in questions for t in q.get("blocks", [])}
    covered = {t for s in scenarios for t in s.get("req_ids", [])}
    for r in requirements:
        rid = r.get("id")
        if r.get("priority") == "ignore":
            continue
        if rid not in covered:
            warn(f"{rid} has no scenario (untested)")
        is_nfr = r.get("category") not in (None, "functional")
        has_question = bool(r.get("question_ids")) or rid in asked_about
        if is_nfr and not r.get("measurable") and not has_question:
            warn(f"{rid} is not measurable as written and no question asks for a measure")
        if is_nfr and r.get("kind") in {"attribute", "constraint", "preference"} and not r.get("applies_to"):
            warn(f"{rid} is not attached to any function (Gause & Weinberg: attributes modify functions); "
                 "use 'product-wide' only if it truly applies to everything")
    return issues


def _check_enum(error, item: dict, field: str, allowed: set[str]) -> None:
    value = item.get(field)
    if value not in allowed:
        error(f"{item.get('id', '?')}: {field}={value!r} is not one of {sorted(allowed)}")


def _lint_scenario(warn, s: dict) -> None:
    """Apply the BRIEF / strict Given-When-Then rules and measurement completeness checks."""
    sid = s.get("id")
    if s.get("status") == "provisional" and not s.get("assumptions"):
        warn(f"{sid} is provisional but states no assumptions")
    fmt = s.get("format")
    if fmt == "gherkin":
        steps = list(s.get("given", [])) + [s.get("when", "")] + list(s.get("then", []))
        if not s.get("when") or not s.get("then"):
            warn(f"{sid}: a Given/When/Then scenario needs a When and at least one Then")
        if any(re.search(r"\bor\b", step, re.IGNORECASE) for step in steps):
            warn(f'{sid}: "or" inside a step makes the scenario non-deterministic; split it (FORM 3.11)')
        if len([x for x in steps if x]) > 6:
            warn(f"{sid}: more than six steps; check it is Brief and Focused (FORM 2.2)")
    elif fmt == "measurement":
        m = s.get("measurement", {})
        for field in ("metric", "threshold", "load_profile", "oracle"):
            if not m.get(field):
                warn(f"{sid}: measurement scenario has no {field}")
    elif fmt in {"checklist", "charter"} and not s.get("items"):
        warn(f"{sid}: {fmt} has no items")
    if not s.get("basis"):
        warn(f"{sid}: no basis given (cite a BOOK or EXT source)")


# ---------- rendering ----------

def _by_category(items: list[dict]) -> list[tuple[str, list[dict]]]:
    groups = []
    for cat in CATEGORY_ORDER:
        members = [i for i in items if i.get("category") == cat]
        if members:
            groups.append((cat, members))
    return groups


def _scenario_body(s: dict) -> str:
    fmt = s.get("format")
    if fmt == "gherkin":
        lines = []
        for i, g in enumerate(s.get("given", [])):
            lines.append(f"{'Given' if i == 0 else '  And'} {g}")
        lines.append(f" When {s.get('when', '')}")
        for i, t in enumerate(s.get("then", [])):
            lines.append(f"{' Then' if i == 0 else '  And'} {t}")
        return "\n".join(lines)
    if fmt == "measurement":
        m = s.get("measurement", {})
        order = ["metric", "load_profile", "environment", "threshold", "warning", "oracle"]
        return "\n".join(f"{k.replace('_', ' ').capitalize()}: {m[k]}" for k in order if m.get(k))
    return "\n".join(f"- {item}" for item in s.get("items", []))


def render_report(analysis: dict, issues: list[dict]) -> str:
    """Render the analysis as a Markdown report for people to read and act on."""
    doc = analysis.get("document", {})
    reqs, scen = analysis.get("requirements", []), analysis.get("scenarios", [])
    questions, gaps = analysis.get("questions", []), analysis.get("gaps", [])
    functions = {f["id"]: f["name"] for f in analysis.get("functions", [])}
    covered: dict[str, list[str]] = {}
    for s in scen:
        for rid in s.get("req_ids", []):
            covered.setdefault(rid, []).append(s["id"])

    out = [f"# Requirements analysis: {doc.get('title', 'Untitled')}", ""]
    out.append(f"Source: `{doc.get('source_file', '?')}` · analysed {doc.get('analysed_on', '?')}")
    if doc.get("scope_note"):
        out.append(f"\n{doc['scope_note']}")

    cats = Counter(r.get("category") for r in reqs)
    unmeasurable = sum(1 for r in reqs if r.get("category") != "functional" and not r.get("measurable"))
    provisional = sum(1 for s in scen if s.get("status") == "provisional")
    out += ["", "## Summary", "",
            f"- **{len(reqs)} requirements**: " + ", ".join(f"{c} {cats[c]}" for c in CATEGORY_ORDER if cats[c]),
            f"- **{unmeasurable} non-functional requirements are not measurable as written**",
            f"- **{len(scen)} scenarios**: {len(scen) - provisional} ready, {provisional} provisional (they rest on assumptions)",
            f"- **{len(questions)} questions** for stakeholders, **{len(gaps)} gaps** (expected requirements not found)",
            f"- {sum(1 for i in issues if i['level'] == 'warning')} quality warnings (see Validation notes)"]

    out += ["", "## Questions for stakeholders", "",
            "Ordered root first: a wrong answer near the root invalidates more below it (ER1 ch 4).", "",
            "| ID | Question | Ask | Why it matters | Blocks |", "|---|---|---|---|---|"]
    for q in sorted(questions, key=lambda q: (LEVEL_ORDER.get(q.get("level"), 3), q["id"])):
        out.append(f"| {q['id']} | {_cell(q.get('question'))} | {_cell(q.get('ask'))} | {_cell(q.get('why'))} | "
                   f"{', '.join(q.get('blocks', []))} |")

    out += ["", "## Requirements", ""]
    for cat, members in _by_category(reqs):
        out += [f"### {cat.capitalize()}", ""]
        for r in members:
            applies = ", ".join(functions.get(a, a) for a in r.get("applies_to", [])) or "**no function named**"
            tag = " · implied" if r.get("origin") == "implied" else ""
            out.append(f"**{r['id']}** · {r.get('kind')} · priority {r.get('priority')}{tag} · "
                       f"{'measurable' if r.get('measurable') else '**not measurable**'}")
            out.append(f"> {r.get('text')}  ")
            out.append(f"> — {r.get('source_ref')}")
            out.append(f"\nApplies to: {applies}. Scenarios: {', '.join(covered.get(r['id'], [])) or '**none**'}.")
            m = r.get("measure")
            if m:
                out.append("\n" + " · ".join(f"*{k}*: {v}" for k, v in m.items() if v))
            for a in r.get("ambiguities", []):
                out.append(f"\n- Ambiguous \"{a.get('phrase')}\" ({a.get('heuristic')}): " + "; ".join(a.get("readings", [])))
            if r.get("question_ids"):
                out.append(f"\nOpen questions: {', '.join(r['question_ids'])}")
            out.append("")

    out += ["## Test scenarios", ""]
    for cat, members in _by_category(scen):
        out += [f"### {cat.capitalize()}", ""]
        for s in members:
            flag = " · **PROVISIONAL**" if s.get("status") == "provisional" else ""
            out.append(f"#### {s['id']} {s.get('title')}{flag}")
            out.append(f"Traces to {', '.join(s.get('req_ids', []))} · {s.get('format')} · {s.get('range')} use · "
                       f"risk {s.get('risk')} · runs {s.get('layer')}")
            out += ["", "```", _scenario_body(s), "```"]
            for a in s.get("assumptions", []):
                out.append(f"- Assumes: {a.get('text')} ({a.get('question_id', 'no question')})")
            if s.get("basis"):
                out.append(f"- Basis: {'; '.join(s['basis'])}")
            out.append("")

    out += ["## Gaps", "", "Requirements the checklists expected but the document does not state. "
            "These are questions, not invented requirements.", "",
            "| Category | Missing | Why it matters | Basis | Question |", "|---|---|---|---|---|"]
    for g in gaps:
        out.append(f"| {g.get('category')} | {_cell(g.get('missing'))} | {_cell(g.get('why_it_matters'))} | "
                   f"{_cell('; '.join(g.get('basis', [])))} | {g.get('question_id', '')} |")

    out += ["", "## Coverage", "", "| Requirement | Category | Scenarios |", "|---|---|---|"]
    for r in reqs:
        out.append(f"| {r['id']} | {r.get('category')} | {', '.join(covered.get(r['id'], [])) or '—'} |")

    out += ["", "## Validation notes", ""]
    warnings = [i["message"] for i in issues if i["level"] == "warning"]
    out += [f"- {w}" for w in warnings] or ["None."]

    bases = sorted({b for item in reqs + scen + gaps for b in item.get("basis", [])})
    out += ["", "## Sources cited", "", "BOOK = published book on requirements or testing; EXT = external standard.", ""]
    out += [f"- {b}" for b in bases]
    return "\n".join(out) + "\n"


def _cell(text) -> str:
    return str(text or "").replace("|", "\\|").replace("\n", " ")


def write_workbook(analysis: dict, path: Path) -> None:
    """Write one sheet per entity plus a Coverage sheet, ready for filtering or import."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font

    functions = {f["id"]: f["name"] for f in analysis.get("functions", [])}
    scen = analysis.get("scenarios", [])
    covered: dict[str, list[str]] = {}
    for s in scen:
        for rid in s.get("req_ids", []):
            covered.setdefault(rid, []).append(s["id"])

    sheets = {
        "Requirements": (
            ["ID", "Category", "Kind", "Priority", "Origin", "Measurable", "Applies to", "Requirement", "Source",
             "Scale", "Meter", "Benchmark", "Constraint", "Target", "Ambiguities", "Questions", "Basis"],
            [[r["id"], r.get("category"), r.get("kind"), r.get("priority"), r.get("origin"),
              "yes" if r.get("measurable") else "no",
              ", ".join(functions.get(a, a) for a in r.get("applies_to", [])), r.get("text"), r.get("source_ref"),
              *[r.get("measure", {}).get(k, "") for k in ("scale", "meter", "benchmark", "constraint", "target")],
              "\n".join(f"{a.get('phrase')}: {'; '.join(a.get('readings', []))}" for a in r.get("ambiguities", [])),
              ", ".join(r.get("question_ids", [])), "; ".join(r.get("basis", []))]
             for r in analysis.get("requirements", [])],
        ),
        "Scenarios": (
            ["ID", "Title", "Requirements", "Category", "Format", "Range", "Status", "Risk", "Layer", "Scenario",
             "Assumptions", "Basis"],
            [[s["id"], s.get("title"), ", ".join(s.get("req_ids", [])), s.get("category"), s.get("format"),
              s.get("range"), s.get("status"), s.get("risk"), s.get("layer"), _scenario_body(s),
              "\n".join(f"{a.get('text')} ({a.get('question_id', '')})" for a in s.get("assumptions", [])),
              "; ".join(s.get("basis", []))] for s in scen],
        ),
        "Questions": (
            ["ID", "Level", "Question", "Ask", "Why", "Blocks", "Answer"],
            [[q["id"], q.get("level"), q.get("question"), q.get("ask"), q.get("why"), ", ".join(q.get("blocks", [])), ""]
             for q in sorted(analysis.get("questions", []), key=lambda q: (LEVEL_ORDER.get(q.get("level"), 3), q["id"]))],
        ),
        "Gaps": (
            ["Category", "Missing", "Why it matters", "Basis", "Question"],
            [[g.get("category"), g.get("missing"), g.get("why_it_matters"), "; ".join(g.get("basis", [])),
              g.get("question_id", "")] for g in analysis.get("gaps", [])],
        ),
        "Coverage": (
            ["Requirement", "Category", "Priority", "Text", "Scenarios", "Count"],
            [[r["id"], r.get("category"), r.get("priority"), r.get("text"), ", ".join(covered.get(r["id"], [])),
              len(covered.get(r["id"], []))] for r in analysis.get("requirements", [])],
        ),
    }

    wb = Workbook()
    wb.remove(wb.active)
    for title, (headers, rows) in sheets.items():
        ws = wb.create_sheet(title)
        ws.append(headers)
        for row in rows:
            ws.append(row)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for col in ws.columns:
            longest = max(len(str(c.value or "").split("\n")[0]) for c in col)
            ws.column_dimensions[col[0].column_letter].width = min(max(10, longest + 2), 60)
            for c in col[1:]:
                c.alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(path)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: validate, then write report and workbook. Returns 1 on errors."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("analysis", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--stem", default=None, help="file name prefix (default: analysis file's parent name)")
    args = parser.parse_args(argv)

    analysis = json.loads(args.analysis.read_text(encoding="utf-8"))
    issues = validate(analysis)
    for i in issues:
        print(f"{i['level'].upper()}: {i['message']}", file=sys.stderr)
    if any(i["level"] == "error" for i in issues):
        print("Not writing outputs: fix the errors above in analysis.json and rerun.", file=sys.stderr)
        return 1

    stem = args.stem or args.analysis.resolve().parent.name
    args.out_dir.mkdir(parents=True, exist_ok=True)
    report = args.out_dir / f"{stem}-requirements-report.md"
    workbook = args.out_dir / f"{stem}-requirements.xlsx"
    report.write_text(render_report(analysis, issues), encoding="utf-8")
    write_workbook(analysis, workbook)
    print(f"Wrote {report}\nWrote {workbook}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
