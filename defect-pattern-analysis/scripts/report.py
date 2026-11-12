#!/usr/bin/env python3
"""Write the run's report from out/, and check it before it is shared.

Usage: report.py --out out/                          writes out/report.md
       report.py --out out/ --check out/report.md    checks a written report

The report has ten sections in a fixed order (coverage, defect types and themes, where
fixes land, where defects were probably introduced, how defects are found and escape,
clarity, complexity, flow, caveats, questions for the team). Everything numeric is copied
from the files the other scripts wrote to out/, already suppressed, between
<!-- report.py:generated --> and <!-- report.py:end --> markers. A section whose step
didn't run says so in one line.

The interpretation is left to whoever runs the skill, person or AI model: each
<!-- write: ... --> comment is replaced with text. --check then confirms that:
- every generated block is unchanged and matches out/ as it is now;
- every write slot was filled, and nothing was added anywhere else;
- every number in the written text appears in the generated blocks, so no suppressed
  value was filled in and no new figure was worked out (list numbering is ignored);
- the written text holds no ticket keys or email addresses.

It reads out/ only, never raw/, clean/ or work/, so the report can't hold anything the
suppressed outputs don't.
"""

import argparse
import json
import re
import sys
from pathlib import Path

GENERATED = "<!-- report.py:generated -->"
END = "<!-- report.py:end -->"
BLOCK = re.compile(re.escape(GENERATED) + r"\n(.*?)\n" + re.escape(END), re.S)
SLOT = re.compile(r"<!-- write: .*? -->", re.S)
NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*")
LIST_NUMBER = re.compile(r"^\s*\d+[.)]\s", re.M)
TICKET_KEY = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

LOW_LINK_RATE = 0.5
HIGH_UNCLASSIFIED_SHARE = 0.1
TABLE_TITLES = {
    "types": "Defect types",
    "themes": "Themes within each type",
    "type_trend": "Types by period",
    "theme_trend": "Themes by period",
    "teams": "Teams (Jira component) by type",
    "periods": "Defects by period",
    "triggers": "How defects were found (trigger)",
    "escape_stages": "Where defects escaped (escape stage)",
}
NUMBERS_RULE = (
    "Quote numbers only as they appear above, and don't work out new ones such as "
    "percentages. Never estimate a suppressed value or name a suppressed group."
)


def _read(out: Path, name: str) -> str | None:
    path = out / name
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _json(out: Path, name: str) -> dict | None:
    text = _read(out, name)
    return json.loads(text) if text is not None else None


def sections(md: str) -> tuple[str, dict[str, str]]:
    """Split a script's Markdown into its intro and its second-level sections."""
    body = md.split("\n", 1)[1] if md.startswith("# ") else md
    parts = re.split(r"^## (.+)$", body, flags=re.M)
    found = {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts), 2)}
    return parts[0].strip(), found


def _demote(text: str, levels: int = 1) -> str:
    """Push headings down so a script's sections sit under a report section."""
    return re.sub(
        r"^(#+) ", lambda m: "#" * (len(m[1]) + levels) + " ", text, flags=re.M
    )


def _sub(title: str, body: str) -> str:
    return f"### {title}\n\n{_demote(body, 2)}"


def _not_run(step: str, what: str) -> str:
    return f"{step} didn't run ({what}), so there is nothing to report here."


def _coverage(out: Path, aggregate: dict, scm: dict | None, scm_md: str | None) -> str:
    settings, summary = aggregate.get("settings", {}), aggregate.get("summary", {})
    k = settings.get("min_group_size")
    lines = ["## 1. Coverage", ""]
    lines += [f"- {key}: {value}" for key, value in summary.items()]
    lines += [
        f"- Groups with fewer than {k} defects are suppressed (shown as "
        f"`{aggregate.get('suppressed_marker', 'suppressed')}`).",
        f"- Period: {settings.get('period')}. Team: {settings.get('team_rule')}.",
    ]
    findings = []
    analysed, unclassified = (
        summary.get("defects_analysed"),
        summary.get("unclassified"),
    )
    if (
        isinstance(analysed, int)
        and isinstance(unclassified, int)
        and analysed
        and unclassified / analysed >= HIGH_UNCLASSIFIED_SHARE
    ):
        findings.append(
            f"High unclassified rate: {unclassified} of {analysed} defects couldn't be "
            "classified with enough confidence."
        )
    for key in ("changelog_incomplete_defects", "comments_incomplete_defects"):
        if summary.get(key) not in (None, 0):
            findings.append(f"Gaps in the data: {key} is {summary[key]}.")
    if scm:
        rate = scm.get("summary", {}).get("defect_link_rate")
        if isinstance(rate, (int, float)) and rate < LOW_LINK_RATE:
            findings.append(
                f"Low link coverage: defect_link_rate is {rate}, so the source control "
                "sections describe only part of the run."
            )
    if findings:
        lines += ["", "**Findings to read first**", ""] + [f"- {f}" for f in findings]
    if scm_md:
        intro, parts = sections(scm_md)
        body = "\n\n".join([intro] + [_sub(t, b) for t, b in parts.items()])
        lines += ["", "### Source control link coverage", "", _demote(body, 1)]
    return "\n".join(lines)


def _tables(tables: dict[str, str], names: list[str]) -> str:
    return "\n\n".join(
        _sub(TABLE_TITLES.get(n, n), tables[n]) for n in names if n in tables
    )


def build(out_dir) -> list[tuple[str, str]]:
    """The report as ("generated", text) and ("write", instruction) parts, in order.

    Raises:
        FileNotFoundError: if out/ has no aggregate.json or tables.md from aggregate.py.
    """
    out = Path(out_dir)
    aggregate, tables_md = _json(out, "aggregate.json"), _read(out, "tables.md")
    if aggregate is None or tables_md is None:
        raise FileNotFoundError(
            f"{out} has no aggregate.json and tables.md; run aggregate.py first"
        )
    _, tables = sections(tables_md)
    scm, scm_md = _json(out, "scm_coverage.json"), _read(out, "scm_coverage.md")
    hot_md, szz_md, szz_doc = (
        _read(out, "hotspots.md"),
        _read(out, "szz.md"),
        _json(out, "szz.json"),
    )
    sig_md = _read(out, "signals.md")
    sig_intro, sig = sections(sig_md) if sig_md else ("", {})
    k = aggregate.get("settings", {}).get("min_group_size")

    parts: list[tuple[str, str]] = []

    def gen(text):
        parts.append(("generated", text))

    def write(instruction):
        parts.append(("write", instruction))

    gen(
        "# Defect pattern analysis\n\n"
        "Numbers and tables in this report are copied by report.py from the run's out/ "
        f"folder, where every group with fewer than {k} defects is suppressed. They "
        "describe the system the work moves through, never the people doing it. The "
        "written parts interpret them.\n\n" + _coverage(out, aggregate, scm, scm_md)
    )

    gen(
        "## 2. Recurring defect types and themes\n\n"
        + _tables(
            tables, ["types", "themes", "type_trend", "theme_trend", "teams", "periods"]
        )
    )
    write(
        "Summarise the largest defect types and themes and how they trend, in two to "
        f"four sentences. {NUMBERS_RULE}"
    )

    if hot_md:
        intro, hot = sections(hot_md)
        gen(
            "## 3. Where fixes land\n\nA directory where many fixes land is where "
            "defects are found and fixed, not necessarily where they were introduced, "
            "and it reflects the code, not the people working in it.\n\n"
            + "\n\n".join([intro] + [_sub(t, b) for t, b in hot.items()])
        )
        write(
            f"Say which directories stand out and what that might mean for the code. {NUMBERS_RULE}"
        )
    else:
        gen("## 3. Where fixes land\n\n" + _not_run("Step 5", "source control linking"))

    if szz_md:
        intro, intro_parts = sections(szz_md)
        gen(
            "## 4. Where defects were probably introduced\n\nThis section is an "
            "estimate.\n\n"
            + "\n\n".join([intro] + [_sub(t, b) for t, b in intro_parts.items()])
        )
        write(
            "Say which directories stand out, treating them as an estimate and a prompt "
            f"for a conversation about the code, never about people. {NUMBERS_RULE}"
        )
    else:
        gen(
            "## 4. Where defects were probably introduced\n\n"
            + _not_run("The introduction estimate", "szz.py at the end of step 5")
        )

    gen(
        "## 5. How defects are found and where they escape\n\n"
        + _tables(tables, ["triggers", "escape_stages"])
    )
    write(
        "Say how defects are mostly found and where they escape, framed as what in the "
        f"process lets them through, never who. {NUMBERS_RULE}"
    )

    signal_sections = [
        ("6. Clarity", ["Clarity", "Clarity and rework within complexity bands"]),
        ("7. Complexity", ["Complexity"]),
        ("8. Flow", ["Flow"]),
    ]
    for title, names in signal_sections:
        if not sig_md:
            gen(f"## {title}\n\n" + _not_run("Step 6", "ticket signals"))
            continue
        body = "\n\n".join(_sub(n, sig[n]) for n in names if n in sig)
        lead = f"{sig_intro}\n\n" if title.startswith("6.") else ""
        gen(f"## {title}\n\n{lead}{body}")
        write(
            f"Say what stands out in {title.split('. ', 1)[1].lower()}. Keep clarity, "
            "complexity and flow separate, call any link between them a correlation, "
            f"not a cause, and describe the system, never a person. {NUMBERS_RULE}"
        )

    caveats = [
        "Classifications are judgements made by an AI model reading anonymised ticket "
        "text, checked against a fixed taxonomy. The taxonomy can't capture every kind "
        "of defect.",
        f"Groups with fewer than {k} defects are suppressed, and some larger ones are "
        "hidden so that a small group can't be worked out from the totals.",
    ]
    if szz_doc:
        summary = szz_doc.get("summary", {})
        untraced = [
            "commits_not_in_clone",
            "merge_commits_skipped",
            "commits_with_nothing_to_blame",
            "paths_not_in_linked_changes",
            "blame_failures",
            "repos_without_clone",
        ]
        caveats.append(
            "The introduction estimate couldn't trace everything: "
            + ", ".join(f"{key}: {summary[key]}" for key in untraced if key in summary)
            + "."
        )
    if sig_md:
        caveats.append(
            "Ticket signals are correlations, not causes, and complexity confounds "
            "clarity and flow."
        )
    caveat_text = "\n".join(f"- {c}" for c in caveats)
    if "Caveats" in sig:
        caveat_text += "\n\n" + _sub("From the ticket signals", sig["Caveats"])
    gen("## 9. Caveats\n\n" + caveat_text)
    write(
        "Add any caveat specific to this run (such as a team that records defects "
        "differently), or write 'No further caveats.'"
    )

    gen("## 10. Questions for the team")
    write(
        "Write three to five questions for the team, framed as system improvements, "
        "for example 'What in our process lets validation defects reach customers?', "
        "never 'Who missed this?'."
    )
    return parts


def render(parts) -> str:
    """The report text, with generated blocks marked and write slots as comments."""
    chunks = []
    for kind, text in parts:
        if kind == "generated":
            chunks.append(f"{GENERATED}\n{text}\n{END}")
        else:
            chunks.append(f"<!-- write: {text} -->")
    return "\n\n".join(chunks) + "\n"


def _gaps(text: str) -> tuple[list[str], list[str]]:
    """The generated blocks in a report, and the text before, between and after them."""
    blocks = [m.group(1) for m in BLOCK.finditer(text)]
    gaps = BLOCK.split(text)[::2]
    return blocks, gaps


def allowed_numbers(blocks: list[str]) -> set[str]:
    """Numbers the written text may quote: those in the generated blocks, not counting
    section numbers, which would otherwise let any small number through."""
    text = re.sub(r"^#+ \d+\. ", "", "\n".join(blocks), flags=re.M)
    return set(NUMBER.findall(text))


def check(text: str, out_dir) -> list[str]:
    """Problems with a written report, as sentences; an empty list means it can be shared."""
    expected = build(out_dir)
    want_blocks = [t for kind, t in expected if kind == "generated"]
    # Which gaps should hold written text: gap i follows generated block i - 1.
    want_slots, index = [False] * (len(want_blocks) + 1), 0
    for kind, _ in expected:
        if kind == "generated":
            index += 1
        else:
            want_slots[index] = True
    blocks, gaps = _gaps(text)
    if len(blocks) != len(want_blocks):
        return [
            f"the report has {len(blocks)} generated blocks but out/ gives "
            f"{len(want_blocks)}; run report.py again and rewrite the slots"
        ]
    problems = []
    for got, want in zip(blocks, want_blocks):
        if got != want:
            heading = want.splitlines()[0]
            problems.append(
                f"a generated block was changed, or out/ has changed since: {heading}"
            )
    allowed = allowed_numbers(want_blocks)
    for i, (gap, wanted) in enumerate(zip(gaps, want_slots)):
        where = want_blocks[i - 1].splitlines()[0] if i else "the start"
        written = gap.strip()
        if not wanted:
            if written:
                problems.append(f"text was added outside a write slot, after {where}")
            continue
        if not written or SLOT.search(written):
            problems.append(f"the write slot after {where} is not written yet")
            continue
        for number in sorted(
            set(NUMBER.findall(LIST_NUMBER.sub("", written))) - allowed
        ):
            problems.append(
                f"the number {number} after {where} isn't in the generated blocks; quote "
                "numbers only as shown, and never fill in a suppressed value"
            )
        if TICKET_KEY.search(written):
            problems.append(f"the text after {where} holds a ticket key")
        if EMAIL.search(written):
            problems.append(f"the text after {where} holds an email address")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Write the report from out/, or check a written one."
    )
    ap.add_argument("--out", default="out", help="the run's out/ folder")
    ap.add_argument(
        "--check", metavar="REPORT", help="check this written report instead"
    )
    a = ap.parse_args(argv)
    try:
        if a.check:
            problems = check(Path(a.check).read_text(encoding="utf-8"), a.out)
        else:
            text = render(build(a.out))
    except (OSError, ValueError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    if a.check:
        for problem in problems:
            print(f"- {problem}")
        print(
            "Report check passed." if not problems else f"{len(problems)} problem(s)."
        )
        return 1 if problems else 0
    path = Path(a.out) / "report.md"
    path.write_text(text, encoding="utf-8")
    print(f"Wrote {path}. Replace each <!-- write: ... --> comment, then run --check.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
