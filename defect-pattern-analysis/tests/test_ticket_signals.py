"""Behaviour tests for scripts/ticket_signals.py: clarity, complexity and flow signals (F6).

Highest risk first: no person, pseudonym, ticket key or small group may reach any output;
then the time-in-status maths, checked against hand-calculated changelogs; then
clarity, complexity, the banded comparison and the command line.

The end-to-end runs use tests/signals_factory.py: 71 synthetic defects in teams of 30, 20,
6, 5, 4, 3, 2 and 1, sent through anonymise.py first like real data. The golden files in
tests/golden_signals/ are the expected outputs. To regenerate them after an intended
change, run with UPDATE_GOLDEN=1 and review the diff.
"""

import csv
import json
import os
import re
import shutil
from pathlib import Path

import pytest

import anonymise
import signals_config
import ticket_signals
from conftest import FIXTURES, all_text_under, person_identifiers
from signals_factory import CONFIG, SMALL_TEAMS, make_links, write_raw

GOLDEN = Path(__file__).resolve().parent / "golden_signals"
OUTPUT_FILES = ["signals.json", "signals.md", "signals_clarity.csv", "signals_complexity.csv", "signals_flow.csv",
                "signals_rework_by_complexity.csv"]
SECTIONS = ("clarity", "complexity", "flow")
COUNT_COLUMNS = {"defects", "with_signal", "with_rework"}


def run(tmp_path, people, links=True, min_group_size=None, period="month", config_text=CONFIG) -> Path:
    raw, clean, out = tmp_path / "raw", tmp_path / "clean", tmp_path / "out"
    issues = write_raw(raw, people)
    anonymise.anonymise_dir(raw, clean)
    (tmp_path / "signals.yaml").write_text(config_text, encoding="utf-8")
    config = signals_config.load_config(tmp_path / "signals.yaml")
    link_data = make_links(issues) if links else None
    ticket_signals.write_signals(clean, config, out, links=link_data, min_group_size=min_group_size, period=period)
    return out


def load(out) -> dict:
    return json.loads((out / "signals.json").read_text())


def all_rows(doc) -> list[dict]:
    return [r for name in SECTIONS for r in doc["sections"][name]["rows"]] + doc["rework_by_complexity"]["rows"]


# --- 1. no person and no small group reaches any output ---------------------------------------------

@pytest.mark.parametrize("links", [True, False])
def test_no_person_placeholder_pseudonym_or_ticket_key_reaches_any_output(tmp_path, people, links):
    out = run(tmp_path, people, links=links)
    text = all_text_under(out)
    leaked = [i for i in person_identifiers(people) if re.search(rf"(?<!\w){re.escape(i)}(?!\w)", text, re.I)]
    assert leaked == []
    assert "[person]" not in text and not re.search(r"person_[0-9a-f]{6,}", text)
    assert not re.search(r"\bABC-\d+\b", text)
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)


def test_only_aggregate_files_are_written_never_a_row_per_ticket(tmp_path, people):
    out = run(tmp_path, people)
    assert sorted(p.name for p in out.iterdir()) == sorted(OUTPUT_FILES)
    assert not (tmp_path / "work").exists()


def _count_values(doc):
    yield from (v for k, v in doc["summary"].items() if k != "source_control")
    for row in all_rows(doc):
        for column in COUNT_COLUMNS & set(row):
            yield row[column]


@pytest.mark.parametrize("k", [5, 6, 8])
def test_no_count_below_the_threshold_reaches_the_json(tmp_path, people, k):
    doc = load(run(tmp_path, people, min_group_size=k))
    counts = list(_count_values(doc))
    assert counts and all(v in (0, "suppressed", None) or (isinstance(v, int) and v >= k) for v in counts)


@pytest.mark.parametrize("k", [5, 6, 8])
def test_no_count_below_the_threshold_reaches_any_csv(tmp_path, people, k):
    out = run(tmp_path, people, min_group_size=k)
    for path in out.glob("*.csv"):
        with path.open() as fh:
            rows = list(csv.DictReader(fh))
        assert rows, path.name
        for row in rows:
            for column in COUNT_COLUMNS & set(row):
                value = row[column]
                assert value in ("", "0", "suppressed") or int(value) >= k, (path.name, column, value)


@pytest.mark.parametrize("k", [5, 6, 8])
def test_no_count_below_the_threshold_reaches_the_markdown(tmp_path, people, k):
    lines = (run(tmp_path, people, min_group_size=k) / "signals.md").read_text().splitlines()
    header = None
    checked = 0
    for line in lines:
        if not line.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if set(cells) <= {"---", ""}:
            continue
        for name, value in zip(header, cells):
            if name in {"defects", "with signal", "with rework"}:
                checked += 1
                assert value in ("", "0", "suppressed") or int(value) >= k, (name, value)
    assert checked
    summary = "\n".join(lines).split("## Summary", 1)[1].split("\n## ", 1)[0]
    for value in re.findall(r": (\d+)$", summary, re.M):
        assert int(value) == 0 or int(value) >= k


@pytest.mark.parametrize("k", [5, 6])
def test_small_teams_are_never_named(tmp_path, people, k):
    out = run(tmp_path, people, min_group_size=k)
    text = all_text_under(out)
    for team in SMALL_TEAMS + (["Web"] if k > 5 else []):
        assert team not in text, team
    assert "Payments" in text and "Accounts" in text


def test_a_hidden_count_cannot_be_worked_out_from_its_row(tmp_path, people):
    doc = load(run(tmp_path, people))
    checked = 0
    for row in all_rows(doc):
        count = row.get("with_signal", row.get("with_rework"))
        if isinstance(row.get("defects"), int) and isinstance(count, int):
            checked += 1
            rest = row["defects"] - count
            assert rest == 0 or rest >= 5, row
        if count == "suppressed":
            assert row["defects"] == "suppressed" and row["share"] == "suppressed", row
    assert checked


def test_suppressed_groups_are_counted_not_named(tmp_path, people):
    doc = load(run(tmp_path, people))
    flow = doc["sections"]["flow"]
    assert flow["suppressed_groups"] > 0
    teams = {r["group"] for r in flow["rows"] if r["grouping"] == "team"}
    assert teams.isdisjoint(SMALL_TEAMS)
    assert "suppressed" in (tmp_path / "out" / "signals.md").read_text()


def test_raw_data_is_refused_so_questions_are_only_ever_read_from_anonymised_text(tmp_path, people):
    write_raw(tmp_path / "raw", people)
    (tmp_path / "raw" / "ABC-1.json").write_text(json.dumps({"key": "ABC-1", "fields": {"created": "2026-01-01"}}))
    (tmp_path / "signals.yaml").write_text(CONFIG)
    config = signals_config.load_config(tmp_path / "signals.yaml")
    with pytest.raises(ValueError, match="anonymise.py"):
        ticket_signals.write_signals(tmp_path / "raw", config, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("k", [3, 4])
def test_a_threshold_below_five_is_refused_before_anything_is_written(tmp_path, people, k):
    with pytest.raises(ValueError, match="at least 5"):
        run(tmp_path, people, min_group_size=k)
    assert not (tmp_path / "out").exists()


# --- 2. time in status: hand-calculated changelogs -----------------------------------------------------

WORKFLOW = signals_config.Workflow([("To Do", "waiting"), ("In Progress", "started"), ("In Review", "waiting"),
                                    ("In Test", "active"), ("Done", "done"), ("Closed", "done")])


def issue(transitions, created="2026-03-02T09:00:00.000+0000", complete=True, edits=(), comments=(),
          description="", fields=None):
    """A clean-shaped issue. transitions: (timestamp, from, to); edits: (timestamp, field, fieldId)."""
    histories = [{"id": str(n), "author": {"person": "[person]"}, "created": t,
                  "items": [{"field": "status", "fieldId": "status", "fromString": a, "toString": b}]}
                 for n, (t, a, b) in enumerate(transitions)]
    histories += [{"id": f"e{n}", "author": {"person": "[person]"}, "created": t,
                   "items": [{"field": f, "fieldId": fid, "fromString": "x", "toString": "y"}]}
                  for n, (t, f, fid) in enumerate(edits)]
    body = [{"id": str(n), "body": c} for n, c in enumerate(comments)]
    return {"key": "ABC-1", "fields": {"created": created, "description": description, "components": [],
                                       "project": {"key": "ABC"}, "comment": {"comments": body}, **(fields or {})},
            "changelog": {"histories": histories},
            "_ingest": {"source": "rest", "changelog_complete": complete, "comments_complete": complete}}


def day(d, h):
    return f"2026-03-{d:02d}T{h:02d}:00:00.000+0000"


STRAIGHT = [(day(2, 11), "To Do", "In Progress"), (day(2, 15), "In Progress", "In Review"),
            (day(2, 16), "In Review", "In Test"), (day(2, 18), "In Test", "Done")]


def test_a_straight_run_through_the_board():
    f = ticket_signals.flow_signals(issue(STRAIGHT), WORKFLOW)
    # created 09:00; To Do 2h, In Progress 4h, In Review 1h, In Test 2h, Done at 18:00.
    assert f["completed"] is True and f["started"] is True
    assert f["lead_hours"] == 9 and f["cycle_hours"] == 7
    assert f["active_hours"] == 6 and f["waiting_hours"] == 1
    assert f["flow_efficiency"] == pytest.approx(6 / 7)
    assert f["hours_in_status"] == {"To Do": 2, "In Progress": 4, "In Review": 1, "In Test": 2}
    assert f["status_changes"] == 4 and f["backward_moves"] == 0 and f["reopens"] == 0


def test_a_reopen_extends_cycle_time_and_time_spent_done_is_neither_active_nor_waiting():
    transitions = STRAIGHT + [(day(3, 9), "Done", "In Progress"), (day(3, 12), "In Progress", "Done")]
    f = ticket_signals.flow_signals(issue(transitions), WORKFLOW)
    # Done 18:00 to 09:00 next day (15h) before the reopen; In Progress 3h more; final Done 3 March 12:00.
    assert f["lead_hours"] == 27 and f["cycle_hours"] == 25
    assert f["active_hours"] == 9 and f["waiting_hours"] == 1
    assert f["flow_efficiency"] == pytest.approx(0.9)
    assert f["hours_in_status"] == {"To Do": 2, "In Progress": 7, "In Review": 1, "In Test": 2, "Done": 15}
    assert f["reopens"] == 1 and f["backward_moves"] == 1 and f["status_changes"] == 6


def test_a_backward_move_is_counted_and_its_time_lands_in_the_right_status():
    transitions = [(day(2, 10), "To Do", "In Progress"), (day(2, 12), "In Progress", "In Review"),
                   (day(2, 15), "In Review", "In Progress"), (day(2, 16), "In Progress", "In Review"),
                   (day(2, 17), "In Review", "Done")]
    f = ticket_signals.flow_signals(issue(transitions), WORKFLOW)
    assert f["backward_moves"] == 1 and f["reopens"] == 0
    assert f["active_hours"] == 3 and f["waiting_hours"] == 4 and f["cycle_hours"] == 7 and f["lead_hours"] == 8


def test_a_ticket_never_started_has_a_lead_time_but_no_cycle_time_or_efficiency():
    f = ticket_signals.flow_signals(issue([(day(2, 14), "To Do", "Done")]), WORKFLOW)
    assert f["completed"] is True and f["started"] is False
    assert f["lead_hours"] == 5
    assert f["cycle_hours"] is None and f["active_hours"] is None and f["waiting_hours"] is None
    assert f["flow_efficiency"] is None
    assert f["hours_in_status"] == {"To Do": 5}


def test_an_open_ticket_has_no_lead_or_cycle_time_and_its_current_status_is_not_timed():
    f = ticket_signals.flow_signals(issue([(day(2, 10), "To Do", "In Progress")]), WORKFLOW)
    assert f["completed"] is False and f["started"] is True
    assert f["lead_hours"] is None and f["cycle_hours"] is None and f["flow_efficiency"] is None
    assert f["hours_in_status"] == {} and f["status_changes"] == 1


def test_a_ticket_with_no_status_changes_has_counts_of_zero_and_no_times():
    f = ticket_signals.flow_signals(issue([]), WORKFLOW)
    assert f["completed"] is False and f["started"] is False
    assert f["status_changes"] == 0 and f["backward_moves"] == 0 and f["reopens"] == 0
    assert f["lead_hours"] is None and f["hours_in_status"] == {}


def test_an_incomplete_changelog_gives_unknown_not_zero():
    f = ticket_signals.flow_signals(issue(STRAIGHT, complete=False), WORKFLOW)
    assert all(f[k] is None for k in ["completed", "started", "lead_hours", "cycle_hours", "status_changes",
                                      "backward_moves", "reopens", "flow_efficiency"])
    assert f["hours_in_status"] == {}


def test_moving_between_done_statuses_does_not_move_the_done_time():
    transitions = [(day(2, 10), "To Do", "In Progress"), (day(2, 12), "In Progress", "Done"),
                   (day(4, 12), "Done", "Closed")]
    f = ticket_signals.flow_signals(issue(transitions), WORKFLOW)
    assert f["lead_hours"] == 3 and f["cycle_hours"] == 2 and f["reopens"] == 0 and f["backward_moves"] == 0


def test_a_ticket_created_in_a_started_status_starts_when_it_was_created():
    f = ticket_signals.flow_signals(issue([(day(2, 13), "In Progress", "Done")]), WORKFLOW)
    assert f["started"] is True and f["cycle_hours"] == 4 and f["active_hours"] == 4


def test_time_in_a_status_missing_from_the_config_is_neither_active_nor_waiting():
    transitions = [(day(2, 10), "To Do", "In Progress"), (day(2, 12), "In Progress", "QA Hold"),
                   (day(2, 20), "QA Hold", "In Review"), (day(2, 21), "In Review", "Done")]
    f = ticket_signals.flow_signals(issue(transitions), WORKFLOW)
    assert f["active_hours"] == 2 and f["waiting_hours"] == 1 and f["cycle_hours"] == 11
    assert f["unmapped_statuses"] == {"QA Hold"} and f["backward_moves"] == 0
    assert "QA Hold" not in f["hours_in_status"]


def test_status_names_match_whatever_their_case():
    transitions = [(t, a.upper(), b.lower()) for t, a, b in STRAIGHT]
    f = ticket_signals.flow_signals(issue(transitions), WORKFLOW)
    assert f["cycle_hours"] == 7 and f["unmapped_statuses"] == set()
    assert f["hours_in_status"] == {"To Do": 2, "In Progress": 4, "In Review": 1, "In Test": 2}


def test_histories_are_put_in_time_order_and_offsets_are_respected():
    shuffled = [STRAIGHT[2], STRAIGHT[0], STRAIGHT[3], STRAIGHT[1]]
    shuffled[0] = ("2026-03-02T17:00:00+01:00", "In Review", "In Test")  # 16:00 UTC, written with an offset
    shuffled[2] = ("2026-03-02T18:00:00Z", "In Test", "Done")
    f = ticket_signals.flow_signals(issue(shuffled), WORKFLOW)
    assert f["lead_hours"] == 9 and f["cycle_hours"] == 7 and f["status_changes"] == 4


@pytest.mark.parametrize("value,expected_hour", [
    ("2026-03-02T09:00:00.000+0000", 9), ("2026-03-02T09:00:00.000+01:00", 8), ("2026-03-02T09:00:00Z", 9),
    ("2026-03-02T09:00:00.123456-0230", 11),
])
def test_jira_timestamps_parse_in_every_shape_jira_writes(value, expected_hour):
    assert ticket_signals.parse_time(value).astimezone(ticket_signals.UTC).hour == expected_hour


def test_an_empty_run_writes_outputs_without_crashing(tmp_path):
    clean = tmp_path / "clean"
    clean.mkdir()
    (tmp_path / "signals.yaml").write_text(CONFIG)
    doc = ticket_signals.write_signals(clean, signals_config.load_config(tmp_path / "signals.yaml"), tmp_path / "out")
    assert doc["summary"]["defects_analysed"] == 0
    assert all(doc["sections"][s]["rows"] == [] for s in SECTIONS)
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == sorted(OUTPUT_FILES)


def test_defects_from_a_project_missing_from_the_config_are_refused_by_name(tmp_path, people):
    write_raw(tmp_path / "raw", people)
    anonymise.anonymise_dir(tmp_path / "raw", tmp_path / "clean")
    (tmp_path / "signals.yaml").write_text(CONFIG.replace("project: ABC", "project: XYZ"))
    config = signals_config.load_config(tmp_path / "signals.yaml")
    with pytest.raises(ValueError, match=r"project ABC"):
        ticket_signals.write_signals(tmp_path / "clean", config, tmp_path / "out")
    assert not (tmp_path / "out").exists()


# --- 3. clarity -----------------------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Steps to reproduce:\n1. Open\n2. Close", {"repro_steps"}),
    ("1. Open the basket\n2. Remove an item", {"repro_steps"}),
    ("# Open the basket\n# Remove an item", {"repro_steps"}),
    ("Expected: zero. Actual: ten.", {"expected_vs_actual"}),
    ("We expected it to work.", set()),
    ("Seen on staging in Chrome.", {"environment"}),
    ("Acceptance criteria: totals add up.", {"acceptance_criteria"}),
    ("Given an empty basket\nwhen it loads\nthen the total is zero", {"acceptance_criteria"}),
    ("It is broken.", set()),
])
def test_the_rubric_checks_each_part_of_a_clear_defect(text, expected):
    found = ticket_signals.rubric(text)
    assert set(found) == {"repro_steps", "expected_vs_actual", "environment", "acceptance_criteria"}
    assert {k for k, v in found.items() if v} == expected


@pytest.mark.parametrize("text,expected", [
    ("[person] can you clarify what should happen when the postcode is empty?", True),
    ("Is the expected behaviour to keep the basket, [person]?", True),
    ("[person]: which of the two totals is correct?", True),
    ("The requirement is unclear to me.", True),
    ("Could you confirm the rounding rule?", True),
    ("Deployed to staging by [person]. Looks fine.", False),
    ("Logs: https://logs.example.com/search?id=42 and nothing else.", False),
    ("Use `a ? b : c` here.", False),
    ("Did the build pass?", False),
])
def test_clarifying_questions_are_recognised_in_anonymised_text(text, expected):
    assert ticket_signals.is_clarifying_question(text) is expected


def test_only_description_and_acceptance_criteria_edits_after_work_started_count():
    edits = [(day(2, 10), "description", "description"),           # before work started
             (day(2, 12), "description", "description"),           # after
             (day(2, 13), "Acceptance Criteria", None),             # Data Center: by name
             (day(2, 14), "Story Points", "customfield_10020"),     # not a clarity field
             (day(2, 14), "AC", "customfield_10010")]               # Cloud: by field id
    settings = {"acceptance_criteria_field": "customfield_10010", "acceptance_criteria_name": "Acceptance Criteria"}
    c = ticket_signals.clarity_signals(issue(STRAIGHT, edits=edits), WORKFLOW, settings)
    assert c["edits_after_start"] == 3


def test_edits_after_start_are_unknown_for_a_ticket_never_started_or_with_gaps():
    settings = {}
    assert ticket_signals.clarity_signals(issue([]), WORKFLOW, settings)["edits_after_start"] is None
    assert ticket_signals.clarity_signals(issue(STRAIGHT, complete=False), WORKFLOW, settings)["edits_after_start"] is None


def test_the_acceptance_criteria_field_counts_towards_the_rubric():
    settings = {"acceptance_criteria_field": "customfield_10010"}
    with_ac = issue(STRAIGHT, fields={"customfield_10010": "Totals add up."})
    assert ticket_signals.clarity_signals(with_ac, WORKFLOW, settings)["rubric"]["acceptance_criteria"] is True
    assert ticket_signals.clarity_signals(issue(STRAIGHT), WORKFLOW, settings)["rubric"]["acceptance_criteria"] is False


def test_question_comments_are_counted_and_unknown_when_comments_are_incomplete():
    comments = ["Can you clarify the rounding rule?", "Done.", "Which total is correct?"]
    assert ticket_signals.clarity_signals(issue(STRAIGHT, comments=comments), WORKFLOW, {})["question_comments"] == 2
    assert ticket_signals.clarity_signals(issue(STRAIGHT, comments=comments, complete=False), WORKFLOW,
                                          {})["question_comments"] is None


# --- 4. complexity --------------------------------------------------------------------------------------

def test_source_control_complexity_is_unknown_not_zero_when_there_is_no_link():
    one = issue(STRAIGHT, fields={"issuelinks": [{}, {}]}, comments=["a", "b", "c"])
    c = ticket_signals.complexity_signals(one, None)
    assert c["linked_issues"] == 2 and c["comments"] == 3
    assert c["changes"] is None and c["commits"] is None and c["files_changed"] is None and c["repos_touched"] is None
    link = {"repos": ["a", "b"], "changes": [{}, {}, {}], "commits": ["1", "2"],
            "files": [{"repo": "a", "path": "x"}, {"repo": "b", "path": "x"}, {"repo": "a", "path": "y"}]}
    c = ticket_signals.complexity_signals(one, link)
    assert (c["changes"], c["commits"], c["files_changed"], c["repos_touched"]) == (3, 2, 3, 2)


def test_without_source_control_links_the_scm_signals_are_reported_as_not_available(tmp_path, people):
    doc = load(run(tmp_path, people, links=False))
    signals = {r["signal"] for r in doc["sections"]["complexity"]["rows"]}
    assert signals == {"linked_issues", "comments"}
    assert doc["summary"]["source_control"] == "not available: step 5 did not run"
    assert doc["rework_by_complexity"]["rows"] == [] and "not available" in doc["rework_by_complexity"]["note"]
    assert "not available" in (tmp_path / "out" / "signals.md").read_text()


def test_with_links_only_linked_defects_count_towards_scm_signals(tmp_path, people):
    out = run(tmp_path, people)
    doc = load(out)
    overall = {r["signal"]: r for r in doc["sections"]["complexity"]["rows"] if r["grouping"] == "all"}
    linked = len(make_links(write_raw(tmp_path / "again", people))["defects"])
    assert overall["files_changed"]["defects"] == linked < doc["summary"]["defects_analysed"]
    assert overall["linked_issues"]["defects"] == doc["summary"]["defects_analysed"]


# --- 5. three separate groups, and clarity against rework within complexity bands -----------------------

def test_clarity_complexity_and_flow_are_three_separate_sections_never_one_score(tmp_path, people):
    out = run(tmp_path, people)
    doc = load(out)
    names = {s: {r["signal"] for r in doc["sections"][s]["rows"]} for s in SECTIONS}
    assert names["clarity"].isdisjoint(names["complexity"]) and names["clarity"].isdisjoint(names["flow"])
    assert names["complexity"].isdisjoint(names["flow"])
    assert "rubric_score" in names["clarity"] and "cycle_time_hours" in names["flow"]
    assert not any(re.search(r"overall|combined|total_score", n) for s in names.values() for n in s)
    md = (out / "signals.md").read_text()
    assert md.index("## Clarity") < md.index("## Complexity") < md.index("## Flow")


def test_flow_is_reported_as_a_property_of_the_system(tmp_path, people):
    md = (run(tmp_path, people) / "signals.md").read_text()
    flow = md.split("## Flow", 1)[1].split("\n## ", 1)[0]
    assert "system" in flow and "not" in flow


@pytest.mark.parametrize("values,expected", [
    ([1, 2, 3, 4, 5, 6, 7, 8, 9], (3, 6)),
    ([1, 1, 1, 1, 2, 2, 9, 9, 9], (1, 2)),
    ([4, 4, 4, 4], (4, 4)),
    ([], None),
])
def test_complexity_bands_are_terciles_of_files_changed(values, expected):
    assert ticket_signals.tercile_cuts(values) == expected


def test_clarity_and_rework_are_compared_within_complexity_bands_and_called_correlations(tmp_path, people):
    out = run(tmp_path, people)
    doc = load(out)
    band = doc["rework_by_complexity"]
    assert band["band_by"] == "files_changed"
    assert set(band["bands"]) == {"low", "middle", "high"}
    assert all(r["band"] in band["bands"] and r["clarity"] in ("lower", "higher") for r in band["rows"])
    md = out.joinpath("signals.md").read_text()
    section = md.split("## Clarity and rework within complexity bands", 1)[1]
    assert "correlation" in section and "not cause" in section


def test_rework_is_counted_per_band_and_clarity_level_with_hand_checked_figures():
    # 60 defects with 1 to 60 files changed: terciles cut at 20 and 40. In every band, ten
    # defects are clearly described (rubric 3) and ten aren't (rubric 0); half of the
    # unclear ones were reopened, none of the clear ones.
    clear = "Steps to reproduce:\n1. Open\n2. Pay\nExpected: zero. Actual: ten.\nSeen on staging."
    reopen = STRAIGHT + [(day(3, 9), "Done", "In Progress"), (day(3, 12), "In Progress", "Done")]
    issues, defects = [], {}
    for n in range(1, 61):
        is_clear = n % 2 == 0
        rework = not is_clear and n % 4 == 1
        one = issue(reopen if rework else STRAIGHT, description=clear if is_clear else "Broken.",
                    fields={"components": [{"name": "Payments"}]})
        one["key"] = f"ABC-{n}"
        issues.append(one)
        defects[one["key"]] = {"repos": ["r"], "changes": [{}], "commits": ["c"],
                               "files": [{"repo": "r", "path": f"f{i}"} for i in range(n)]}
    links = {"defects": defects}
    doc, _ = ticket_signals.build_signals(issues, {"workflows": {"ABC": WORKFLOW}}, links)
    band = doc["rework_by_complexity"]
    assert band["bands"] == {"low": "up to 20 files", "middle": "21 to 40 files", "high": "more than 40 files"}
    assert [(r["band"], r["clarity"], r["defects"], r["with_rework"], r["share"]) for r in band["rows"]] == [
        ("low", "lower", 10, 5, 0.5), ("low", "higher", 10, 0, 0.0),
        ("middle", "lower", 10, 5, 0.5), ("middle", "higher", 10, 0, 0.0),
        ("high", "lower", 10, 5, 0.5), ("high", "higher", 10, 0, 0.0)]


# --- 6. outputs, golden file and command line -----------------------------------------------------------

def test_outputs_match_the_golden_files(tmp_path, people):
    out = run(tmp_path, people)
    if os.environ.get("UPDATE_GOLDEN"):
        shutil.rmtree(GOLDEN, ignore_errors=True)
        shutil.copytree(out, GOLDEN)
    produced = sorted(p.name for p in out.iterdir())
    assert produced == sorted(p.name for p in GOLDEN.iterdir())
    for name in produced:
        assert (out / name).read_text() == (GOLDEN / name).read_text(), name


def test_the_period_can_be_a_quarter(tmp_path, people):
    doc = load(run(tmp_path, people, period="quarter"))
    periods = {r["group"] for r in doc["sections"]["flow"]["rows"] if r["grouping"] == "period"}
    assert periods and all(re.fullmatch(r"2026-Q[12]", p) for p in periods)


def test_the_example_config_shipped_with_the_skill_works_on_the_pipeline_fixture(tmp_path):
    from conftest import ROOT
    anonymise.anonymise_dir(FIXTURES / "pipeline/raw", tmp_path / "clean")
    config = signals_config.load_config(ROOT / "signals.yaml")
    doc = ticket_signals.write_signals(tmp_path / "clean", config, tmp_path / "out")
    assert doc["summary"]["defects_analysed"] == 36


def write_cli_inputs(tmp_path, people):
    issues = write_raw(tmp_path / "raw", people)
    anonymise.anonymise_dir(tmp_path / "raw", tmp_path / "clean")
    (tmp_path / "signals.yaml").write_text(CONFIG)
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "scm_links.json").write_text(json.dumps(make_links(issues)))


def test_the_command_line_writes_every_output(tmp_path, people):
    write_cli_inputs(tmp_path, people)
    code = ticket_signals.main(["--config", str(tmp_path / "signals.yaml"), "--issues", str(tmp_path / "clean"),
                                "--links", str(tmp_path / "work/scm_links.json"), "--out", str(tmp_path / "out")])
    assert code == 0 and sorted(p.name for p in (tmp_path / "out").iterdir()) == sorted(OUTPUT_FILES)


def test_the_command_line_takes_the_threshold_from_the_config(tmp_path, people):
    write_cli_inputs(tmp_path, people)
    (tmp_path / "signals.yaml").write_text("min_group_size: 9\n" + CONFIG)
    assert ticket_signals.main(["--config", str(tmp_path / "signals.yaml"), "--issues", str(tmp_path / "clean"),
                                "--out", str(tmp_path / "out")]) == 0
    assert load(tmp_path / "out")["settings"]["min_group_size"] == 9


def test_the_command_line_groups_by_defect_type_when_given_classifications(tmp_path, people):
    write_cli_inputs(tmp_path, people)
    keys = [json.loads(p.read_text())["key"] for p in sorted((tmp_path / "clean").glob("ABC-*.json"))]
    records = [{"key": k, "status": "classified", "defect_type": "checking_validation" if n % 2 else "interface",
                "theme": "t"} for n, k in enumerate(keys)]
    (tmp_path / "work" / "classified.json").write_text(json.dumps({"records": records}))
    assert ticket_signals.main(["--config", str(tmp_path / "signals.yaml"), "--issues", str(tmp_path / "clean"),
                                "--classified", str(tmp_path / "work/classified.json"),
                                "--out", str(tmp_path / "out")]) == 0
    types = {r["group"] for r in load(tmp_path / "out")["sections"]["clarity"]["rows"] if r["grouping"] == "type"}
    assert types == {"checking_validation", "interface"}


@pytest.mark.parametrize("args,message", [
    (["--min-group-size", "4"], "at least 5"),
    (["--period", "week"], "invalid choice"),
])
def test_the_command_line_refuses_bad_settings_and_writes_nothing(tmp_path, people, capsys, args, message):
    write_cli_inputs(tmp_path, people)
    try:
        code = ticket_signals.main(["--config", str(tmp_path / "signals.yaml"), "--issues", str(tmp_path / "clean"),
                                    "--out", str(tmp_path / "out"), *args])
    except SystemExit as exc:
        code = exc.code
    assert code == 2 and message in capsys.readouterr().err and not (tmp_path / "out").exists()


def test_the_command_line_reports_a_config_error_with_its_file_and_line(tmp_path, people, capsys):
    write_cli_inputs(tmp_path, people)
    (tmp_path / "signals.yaml").write_text(CONFIG.replace("category: active", "category: busy"))
    code = ticket_signals.main(["--config", str(tmp_path / "signals.yaml"), "--issues", str(tmp_path / "clean"),
                                "--out", str(tmp_path / "out")])
    err = capsys.readouterr().err
    assert code == 2 and "signals.yaml: line 16:" in err and "busy" in err and not (tmp_path / "out").exists()
