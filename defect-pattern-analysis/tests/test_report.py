"""Behaviour tests for scripts/report.py: the report and its check (F7).

out/ is built from the golden outputs of aggregate.py, hotspots.py and ticket_signals.py,
plus link coverage and an introduction estimate written by the real writers from small
synthetic inputs. The golden files come from different fixture runs, which doesn't
matter here: the report only arranges what is in out/.
"""

import json
import re
import shutil
from pathlib import Path

import pytest

import link_scm
import report
import szz

TESTS = Path(__file__).resolve().parent
ALL = ("scm", "hotspots", "szz", "signals")


def coverage_links(linked=6, total=20) -> dict:
    return {
        "since": "2026-01-10",
        "defects_total": total,
        "defects_linked": linked,
        "repos": {
            "group/checkout-service": {
                "platform": "gitlab",
                "team": "Checkout",
                "changes_scanned": 40,
                "changes_linked": 9,
                "defects_linked": linked,
            }
        },
        "skipped": [],
        "defects": {
            f"ABC-{n}": {"repos": ["group/checkout-service"]} for n in range(linked)
        },
    }


def szz_result(traced=6) -> dict:
    coverage = dict.fromkeys(szz.COVERAGE_KEYS, 0)
    coverage.update(
        defects_linked=traced + 2,
        defects_traced=traced,
        fix_commits_blamed=traced,
        commits_not_in_clone=7,
        repos_without_clone=[],
    )
    return {
        "since": "2026-01-10",
        "coverage": coverage,
        "defects": {
            f"ABC-{n}": {
                "traced": True,
                "candidates": [
                    {"repo": "group/checkout-service", "path": "src/checkout/a.py"}
                ],
            }
            for n in range(traced)
        },
        "lag_days": [10.0 + n for n in range(traced)],
    }


def make_out(tmp_path, steps=ALL, links=None) -> Path:
    out = tmp_path / "out"
    out.mkdir(parents=True)
    for name in ("aggregate.json", "tables.md"):
        shutil.copy(TESTS / "golden" / name, out)
    if "hotspots" in steps:
        for name in ("hotspots.json", "hotspots.md"):
            shutil.copy(TESTS / "golden_hotspots" / name, out)
    if "signals" in steps:
        for name in ("signals.json", "signals.md"):
            shutil.copy(TESTS / "golden_signals" / name, out)
    if "scm" in steps:
        link_scm.write_coverage(links or coverage_links(), out)
    if "szz" in steps:
        szz.write_szz(szz_result(), out)
    return out


def headings(text: str) -> list[str]:
    return re.findall(r"^## (.+)$", text, re.M)


def fill(text: str, words="The largest groups are shown above.") -> str:
    """Replace every write slot, as the person or agent writing the report would."""
    return re.sub(r"<!-- write: .*? -->", words, text, flags=re.S)


# --- Writing the report -----------------------------------------------------------


def test_sections_follow_the_order_the_skill_sets_out(tmp_path):
    text = report.render(report.build(make_out(tmp_path)))
    assert headings(text) == [
        "1. Coverage",
        "2. Recurring defect types and themes",
        "3. Where fixes land",
        "4. Where defects were probably introduced",
        "5. How defects are found and where they escape",
        "6. Clarity",
        "7. Complexity",
        "8. Flow",
        "9. Caveats",
        "10. Questions for the team",
    ]


def test_a_step_that_did_not_run_is_said_in_one_line_not_left_out(tmp_path):
    text = report.render(report.build(make_out(tmp_path, steps=())))
    assert len(headings(text)) == 10
    fixes = text.split("## 3. Where fixes land", 1)[1].split("## 4.", 1)[0]
    assert "Step 5 didn't run" in fixes and "<!-- write:" not in fixes
    assert "Step 6 didn't run" in text.split("## 6. Clarity", 1)[1].split("## 7.")[0]


def test_tables_are_copied_from_out_unchanged(tmp_path):
    out = make_out(tmp_path)
    text = report.render(report.build(out))
    for source in ("tables.md", "hotspots.md", "szz.md", "signals.md"):
        table_rows = [
            line
            for line in (out / source).read_text().splitlines()
            if line.startswith("| ") and "---" not in line
        ]
        assert table_rows and all(row in text for row in table_rows), source


def test_the_introduction_estimate_is_labelled_an_estimate(tmp_path):
    text = report.render(report.build(make_out(tmp_path)))
    section = text.split("## 4.", 1)[1].split("## 5.", 1)[0]
    assert "estimate" in section.lower()


def test_low_link_coverage_and_gaps_are_findings_at_the_top(tmp_path):
    text = report.render(report.build(make_out(tmp_path)))
    coverage = text.split("## 1. Coverage", 1)[1].split("## 2.", 1)[0]
    assert "Low link coverage" in coverage and "0.3" in coverage


def test_good_link_coverage_is_not_called_low(tmp_path):
    out = make_out(tmp_path, links=coverage_links(linked=18, total=20))
    assert "Low link coverage" not in report.render(report.build(out))


def test_the_caveats_say_what_the_estimate_could_not_trace(tmp_path):
    text = report.render(report.build(make_out(tmp_path)))
    caveats = text.split("## 9. Caveats", 1)[1].split("## 10.", 1)[0]
    assert "commits_not_in_clone: 7" in caveats
    assert "correlations, not causes" in caveats


def test_nothing_names_a_model_or_vendor(tmp_path):
    text = report.render(report.build(make_out(tmp_path)))
    assert not re.search(r"claude|anthropic|openai|gpt|gemini", text, re.I)


# --- Checking the report ----------------------------------------------------------


def checked(tmp_path, edit) -> list[str]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    out = make_out(tmp_path)
    text = edit(report.render(report.build(out)))
    return report.check(text, out)


def test_a_report_with_every_slot_filled_from_the_numbers_shown_passes(tmp_path):
    assert (
        checked(tmp_path, lambda t: fill(t, "Checking validation leads with 14.")) == []
    )


def test_an_unfilled_slot_fails(tmp_path):
    problems = checked(tmp_path, lambda t: t)
    assert problems and all("not written yet" in p for p in problems)


def test_an_edited_number_in_a_generated_block_fails(tmp_path):
    def edit(text):
        return fill(text).replace(
            "| checking_validation | 14 |", "| checking_validation | 15 |"
        )

    assert any("changed" in p for p in checked(tmp_path, edit))


def test_a_number_not_shown_anywhere_fails(tmp_path):
    blocks = [
        t
        for kind, t in report.build(make_out(tmp_path / "probe"))
        if kind == "generated"
    ]
    shown = report.allowed_numbers(blocks)
    unseen = str(next(n for n in range(1, 100) if str(n) not in shown))

    def edit(text):
        return fill(text).replace(
            "The largest groups are shown above.", f"Payments had {unseen} defects.", 1
        )

    problems = checked(tmp_path / "run", edit)
    assert any(
        f"number {unseen} " in p and "isn't in the generated" in p for p in problems
    )


def test_a_section_number_does_not_make_a_small_number_quotable(tmp_path):
    blocks = [t for kind, t in report.build(make_out(tmp_path)) if kind == "generated"]
    assert "10" not in report.allowed_numbers(
        [b for b in blocks if b.startswith("## 10.")]
    )


def test_list_numbering_in_written_text_is_not_a_number(tmp_path):
    def edit(text):
        return fill(text, "1. What lets these through?\n12. Who reviews it?")

    problems = checked(tmp_path, edit)
    assert problems == [] or all("12" not in p for p in problems)


def test_a_ticket_key_or_email_in_written_text_fails(tmp_path):
    for n, words in enumerate(("See ABC-123 for detail.", "Ask robin@example.com.")):
        problems = checked(tmp_path / str(n), lambda t, w=words: fill(t, w))
        assert any("ticket key" in p or "email" in p for p in problems), words


def test_text_added_outside_a_slot_fails(tmp_path):
    def edit(text):
        text = fill(text)
        start = report.GENERATED + "\n## 2. Recurring"
        return text.replace(start, "Team X is slow.\n\n" + start, 1)

    assert any("outside" in p for p in checked(tmp_path, edit))


def test_a_report_out_of_date_with_out_fails(tmp_path):
    out = make_out(tmp_path)
    text = fill(report.render(report.build(out)))
    (out / "hotspots.md").unlink()
    (out / "hotspots.json").unlink()
    assert report.check(text, out)


# --- Command line ------------------------------------------------------------------


def test_the_command_line_writes_the_report_and_checks_it(tmp_path, capsys):
    out = make_out(tmp_path)
    assert report.main(["--out", str(out)]) == 0
    path = out / "report.md"
    assert path.exists()
    assert report.main(["--out", str(out), "--check", str(path)]) == 1
    assert "not written yet" in capsys.readouterr().out
    path.write_text(fill(path.read_text()))
    assert report.main(["--out", str(out), "--check", str(path)]) == 0


def test_the_command_line_needs_the_counts_from_step_4(tmp_path, capsys):
    (tmp_path / "out").mkdir()
    assert report.main(["--out", str(tmp_path / "out")]) == 2
    assert "aggregate.py" in capsys.readouterr().err


def test_the_report_is_written_from_out_only(tmp_path):
    out = make_out(tmp_path)
    for name in ("raw", "clean", "work"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "ABC-1.json").write_text(json.dumps({"key": "ABC-1"}))
    text = report.render(report.build(out))
    assert "ABC-1" not in text


@pytest.mark.parametrize("steps", [(), ALL])
def test_the_report_holds_no_ticket_keys(tmp_path, steps):
    text = report.render(report.build(make_out(tmp_path, steps=steps)))
    assert not re.search(r"\b[A-Z][A-Z0-9]+-\d+\b", text)
