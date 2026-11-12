"""Behaviour tests for SKILL.md: the instructions Claude follows must keep the no-blame rules (P1 to P7)."""

import json
import re

from conftest import ROOT

SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")


def test_skill_declines_per_person_breakdowns_and_says_why():
    section = SKILL.split("**If anyone asks for a per-person breakdown**", 1)[1].split(
        "## Inputs", 1
    )[0]
    assert "decline" in section
    assert "system" in section and "pairing" in section and "anonymised" in section


def test_skill_requires_a_data_governance_check_before_real_data():
    before = SKILL.split("## Workflow", 1)[0]
    assert re.search(
        r"confirm that their organisation allows sending Jira ticket data to an AI model",
        before,
    )


def test_skill_names_every_script_in_the_order_it_runs():
    order = [
        "jira_changelog.py",
        "anonymise.py",
        "make_batches.py",
        "validate_classifications.py",
        "aggregate.py",
    ]
    workflow = SKILL.split("## Workflow", 1)[1].split("## Later versions", 1)[0]
    positions = [workflow.index(f"scripts/{name}") for name in order]
    assert positions == sorted(positions)


def test_skill_never_lowers_the_group_threshold():
    assert "Values below 5 are refused" in SKILL and "never lower" in SKILL


def test_no_script_is_left_marked_not_ready():
    assert "## Not ready yet" not in SKILL
    assert "Don't run it on real data" not in SKILL


def test_szz_runs_after_the_fix_hotspots_on_full_clones_and_is_called_an_estimate():
    step = SKILL.split("### 5.", 1)[1].split("### 6.", 1)[0]
    assert step.index("scripts/hotspots.py") < step.index("scripts/szz.py")
    assert "--clone" in step and "--depth" in step and "shallow" in step
    assert "estimate" in step and "never about the people" in step
    assert "commits_not_in_clone" in step


def test_the_report_puts_introductions_after_fix_hotspots_and_says_it_is_an_estimate():
    report = SKILL.split("### 7.", 1)[1]
    assert "szz.md" in report
    section = report.split("**Where defects were probably introduced**", 1)[1].split(
        "\n", 1
    )[0]
    assert "estimate" in section
    assert (
        report.index("**Where fixes land**")
        < report.index("**Where defects were probably introduced**")
        < report.index("**Caveats**")
    )


def test_gitlab_linking_runs_after_anonymisation_and_before_the_report():
    workflow = SKILL.split("## Workflow", 1)[1].split("## Later versions", 1)[0]
    step = workflow.split("### 5.", 1)[1].split("### 6.", 1)[0]
    assert "GitLab" in step and "MCP" in step
    order = ["scripts/scm_fetch.py", "scripts/anonymise.py", "scripts/link_scm.py"]
    positions = [step.index(name) for name in order]
    assert positions == sorted(positions)
    assert "Write the report" in workflow.split("### 6.", 1)[1]


def test_skill_names_no_dependency_outside_the_standard_library():
    assert (
        "`requests`" not in SKILL
        and "pyyaml" not in SKILL.lower()
        and "pip install" not in SKILL
    )


def test_skill_md_uses_no_em_dashes():
    assert "\u2014" not in SKILL


def test_evals_cover_the_per_person_refusal():
    evals = json.loads((ROOT / "evals/evals.json").read_text())["evals"]
    assert any(
        "assignee" in e["prompt"] and "refusal" in e["expected_output"] for e in evals
    )


def test_skill_says_what_the_model_sees_with_mcp_and_with_rest():
    assert (
        "the model sees raw ticket data, names included, during the fetch step" in SKILL
    )
    assert "The REST fallback keeps names away from the model entirely" in SKILL


def test_skill_states_the_work_not_people_stance():
    section = SKILL.split("## No individual blame", 1)[1].split("## Inputs", 1)[0]
    assert "judges the work, not the people" in section
    assert "everyone on the team worked on" in section


def test_skill_lists_component_attribution_as_an_open_question():
    later = SKILL.split("## Later versions", 1)[1]
    assert "several components" in later


def test_skill_documents_the_yaml_subset_scm_yaml_may_use():
    step = SKILL.split("### 5.", 1)[1].split("### 6.", 1)[0]
    subset = step.split("`scm.yaml` uses a strict part of YAML", 1)[1].split("\n\n", 1)[
        0
    ]
    for word in [
        "single quotes",
        "tabs",
        "anchors",
        "flow",
        "multi-line",
        "duplicate",
        "line number",
    ]:
        assert word in subset, word


def test_skill_explains_how_personal_namespaces_are_kept_out_of_outputs():
    step = SKILL.split("### 5.", 1)[1].split("### 6.", 1)[0]
    assert "namespace: group" in step and "namespace: user" in step
    assert "[person]/checkout-tool" in step
    assert "treated as personal" in step
    assert "--scm-config scm.yaml" in step
    assert "Link only group or team repos" not in step


def step5():
    return SKILL.split("### 5.", 1)[1].split("### 6.", 1)[0]


def test_azure_devops_linking_is_documented_with_its_files_and_token():
    step = step5()
    assert "Azure DevOps" in step and "platform: azure" in step
    for name in [
        "raw/azure-prs-1.json",
        "-commits-1.json",
        "-changes-1.json",
        "AZDO_PAT",
        "last iteration",
    ]:
        assert name in step, name


def test_skill_says_the_azure_devops_org_never_reaches_an_output():
    assert "the org never appears" in step5()


def test_hotspots_run_after_linking_and_explain_the_counting_rule():
    step = step5()
    assert step.index("scripts/link_scm.py") < step.index("scripts/hotspots.py")
    assert "counts defects, not files or commits" in step and "--depth" in step


def test_the_report_has_a_hotspot_section_after_the_recurring_types():
    report = SKILL.split("### 6.", 1)[1]
    assert (
        report.index("**Recurring defect types and themes**")
        < report.index("**Where fixes land**")
        < report.index("**Caveats**")
    )
    assert "hotspots.md" in report


def step6():
    return SKILL.split("### 6.", 1)[1].split("### 7.", 1)[0]


def test_ticket_signals_run_after_counting_and_linking_and_before_the_report():
    workflow = SKILL.split("## Workflow", 1)[1].split("## Later versions", 1)[0]
    assert (
        workflow.index("scripts/aggregate.py")
        < workflow.index("scripts/link_scm.py")
        < workflow.index("scripts/ticket_signals.py")
        < workflow.index("### 7. Write the report")
    )
    assert "--links work/scm_links.json" in step6() and "signals.yaml" in step6()


def test_ticket_signals_keep_clarity_complexity_and_flow_apart_and_call_them_correlations():
    step = step6()
    assert "never combined into one score" in step
    assert "correlations, not causes" in step and "complexity band" in step
    assert "not as zero" in step and "never a person" in step
    report = SKILL.split("### 7.", 1)[1]
    positions = [
        report.index(f"**{name}**")
        for name in ["Clarity", "Complexity", "Flow", "Caveats"]
    ]
    assert positions == sorted(positions)
    assert "signals.md" in report


def test_ticket_signals_status_config_is_documented():
    step = step6()
    for word in [
        "started",
        "active",
        "waiting",
        "done",
        "workflow order",
        "line number",
    ]:
        assert word in step, word
    assert "--extra-field" in step


def test_the_skill_description_no_longer_calls_ticket_signals_unready():
    front = SKILL.split("---", 2)[1]
    assert "clarity, complexity and flow" in front
    assert "Ticket-history signals" not in front


def test_the_report_is_written_by_report_py_then_filled_in_and_checked():
    step = SKILL.split("### 7.", 1)[1].split("## Later versions", 1)[0]
    write = step.index("scripts/report.py --out out/")
    check = step.index("--check out/report.md")
    assert write < check < step.index("Keep the reply short")
    assert "<!-- write:" in step and "report.py:generated" in step
    assert "until it passes" in step
