"""Behaviour tests for SKILL.md: the instructions Claude follows must keep the no-blame rules (P1 to P7)."""

import json
import re

from conftest import ROOT

SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")


def test_skill_declines_per_person_breakdowns_and_says_why():
    section = SKILL.split("**If anyone asks for a per-person breakdown**", 1)[1].split("## Inputs", 1)[0]
    assert "decline" in section
    assert "system" in section and "pairing" in section and "anonymised" in section


def test_skill_requires_a_data_governance_check_before_real_data():
    before = SKILL.split("## Workflow", 1)[0]
    assert re.search(r"confirm that their organisation allows sending Jira ticket data to an AI model", before)


def test_skill_names_every_script_in_the_order_it_runs():
    order = ["jira_changelog.py", "anonymise.py", "make_batches.py", "validate_classifications.py", "aggregate.py"]
    workflow = SKILL.split("## Workflow", 1)[1].split("## Not ready yet", 1)[0]
    positions = [workflow.index(f"scripts/{name}") for name in order]
    assert positions == sorted(positions)


def test_skill_never_lowers_the_group_threshold():
    assert "Values below 5 are refused" in SKILL and "never lower" in SKILL


def test_draft_scripts_with_known_problems_are_marked_not_ready():
    not_ready = SKILL.split("## Not ready yet", 1)[1]
    for name in ["link_scm.py", "ticket_signals.py", "szz.py"]:
        assert f"scripts/{name}" in not_ready


def test_skill_md_uses_no_em_dashes():
    assert "\u2014" not in SKILL


def test_evals_cover_the_per_person_refusal():
    evals = json.loads((ROOT / "evals/evals.json").read_text())["evals"]
    assert any("assignee" in e["prompt"] and "refusal" in e["expected_output"] for e in evals)
