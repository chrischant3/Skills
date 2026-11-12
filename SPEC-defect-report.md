# Spec: defect-pattern-analysis report (phase 7)

## Objective

Turn the run's `out/` files into one Markdown report in a fixed order, so that the report is the same whichever AI model (or person) runs the skill. Numbers and tables are written by a script and can't be mis-copied or filled in. The interpretation (what stands out, questions for the team) is written by whoever runs the skill, in marked places, and a check confirms the result before it is shared.

Users: the team lead or tester who runs the skill, and the team who reads the report.

## Behaviour

`scripts/report.py --out out/` writes `out/report.md` from `out/` only. It never reads `raw/`, `clean/` or `work/`.

Sections, in order (as step 7 of `SKILL.md` lists them):

1. Coverage: defects matched, analysed and unclassified, ingest gaps, the suppression threshold, link coverage per repo if step 5 ran, and generated findings for a high unclassified rate, gaps and low link coverage.
2. Recurring defect types and themes: the type, theme, trend, team and period tables.
3. Where fixes land: `hotspots.md`, if step 5 ran.
4. Where defects were probably introduced: `szz.md`, labelled an estimate, if it ran.
5. How defects are found and where they escape: the trigger and escape stage tables.
6. Clarity, 7. Complexity, 8. Flow: from `signals.md`, if step 6 ran. The rework-by-complexity comparison goes under Clarity.
9. Caveats: a generated list, plus run-specific caveats.
10. Questions for the team.

A section whose step didn't run says so in one line instead.

**Generated blocks** sit between `<!-- report.py:generated -->` and `<!-- report.py:end -->` and must not be edited. **Write slots** are `<!-- write: instruction -->` comments, replaced with text.

`scripts/report.py --out out/ --check out/report.md` exits 0 only if:

- every generated block matches what `out/` produces now, in order;
- every write slot has been replaced with text, and no other text was added outside the slots;
- every number in the written text appears in the generated blocks (so no suppressed value is filled in and no new figure is worked out), ignoring list numbering;
- the written text holds no ticket keys or email addresses.

Otherwise it lists each problem and exits 1. Missing `aggregate.json` or `tables.md` exits 2.

## Boundaries

- Always: read only `out/`; show suppressed values as the scripts wrote them.
- Never: name a suppressed group, add a per-person view, or depend on a particular model or vendor.

## Testing

`tests/test_report.py`, from fixtures built with the real writers and the golden outputs: section order, optional sections, verbatim tables, generated findings, and each `--check` rule failing and passing.
