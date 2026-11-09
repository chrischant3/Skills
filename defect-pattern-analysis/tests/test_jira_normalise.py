"""Behaviour tests for scripts/jira_normalise.py and the raw/ to clean/ step.

Raw data arrives in two shapes: MCP tool results that Claude saved verbatim, and per-issue
files from the REST fallback. Both must end up as one anonymised file per issue, with gaps
in changelog or comments reported so they can be filled.
"""

import json
import re

import anonymise
import jira_normalise
from conftest import all_text_under, load_fixture, person_identifiers


def test_issues_are_found_in_every_raw_shape():
    issue = load_fixture("jira/cloud_issue_ABC-101.json")
    shapes = [issue, {"issues": [issue]}, [issue], {"content": [{"type": "text", "text": json.dumps({"issues": [issue]})}]},
              json.dumps(issue)]
    for shape in shapes:
        assert [i["key"] for i in jira_normalise.issues_from_document(shape)] == ["ABC-101"]


def test_documents_that_are_not_jira_yield_nothing():
    assert jira_normalise.issues_from_document(load_fixture("scm/gitlab_mr.json")) == []
    assert jira_normalise.issues_from_document({"content": [{"type": "text", "text": "not json"}]}) == []


def test_changelog_values_from_the_changelog_endpoint_become_histories():
    issue = jira_normalise.normalise_issue({"key": "ABC-1", "fields": {}, "changelog": {"values": [{"id": "1"}], "total": 1}})
    assert issue["changelog"]["histories"] == [{"id": "1"}]


def test_completeness_is_only_claimed_when_totals_prove_it():
    full = jira_normalise.normalise_issue(load_fixture("jira/cloud_issue_ABC-101.json"))
    assert full["_ingest"]["changelog_complete"] and full["_ingest"]["comments_complete"]
    mcp = jira_normalise.issues_from_document(load_fixture("recorded/mcp_search_result.json"))[0]
    mcp = jira_normalise.normalise_issue(mcp)
    assert not mcp["_ingest"]["changelog_complete"] and not mcp["_ingest"]["comments_complete"]
    truncated = jira_normalise.normalise_issue(
        {"key": "ABC-2", "fields": {"comment": {"comments": [{}], "total": 3}}, "changelog": {"histories": [], "total": 0}})
    assert truncated["_ingest"]["changelog_complete"] and not truncated["_ingest"]["comments_complete"]


def test_the_more_complete_copy_of_an_issue_wins():
    thin = {"key": "ABC-9", "fields": {"summary": "thin", "comment": {"comments": []}}}
    rich = {"key": "ABC-9", "fields": {"summary": "rich", "comment": {"comments": [], "total": 0}},
            "changelog": {"histories": [], "total": 0}}
    merged = jira_normalise.merge_issues([thin, rich, thin])
    assert [i["fields"]["summary"] for i in merged] == ["rich"]


def write_raw(tmp_path, docs: dict):
    raw = tmp_path / "raw"
    raw.mkdir()
    for name, doc in docs.items():
        (raw / name).write_text(json.dumps(doc))
    return raw


def test_raw_mcp_and_rest_data_become_one_clean_file_per_issue(tmp_path):
    raw = write_raw(tmp_path, {
        "mcp-page-1.json": load_fixture("recorded/mcp_search_result.json"),
        "ABC-101.json": load_fixture("jira/cloud_issue_ABC-101.json"),
        "dc.json": {"issues": [load_fixture("jira/dc_issue_ABC-102.json")]},
        "gitlab_mr.json": load_fixture("scm/gitlab_mr.json"),
        "_manifest.json": {"source": "mcp", "jql": "project = ABC", "matched": 3},
    })
    anonymise.anonymise_dir(raw, tmp_path / "clean")
    names = sorted(p.name for p in (tmp_path / "clean").iterdir())
    assert names == ["ABC-101.json", "ABC-102.json", "ABC-401.json", "_ingest.json", "gitlab_mr.json"]


def test_ingest_report_lists_gaps_and_the_matched_count(tmp_path):
    raw = write_raw(tmp_path, {"mcp-page-1.json": load_fixture("recorded/mcp_search_result.json"),
                               "ABC-101.json": load_fixture("jira/cloud_issue_ABC-101.json"),
                               "_manifest.json": {"source": "mcp", "jql": "project = ABC", "matched": 2}})
    anonymise.anonymise_dir(raw, tmp_path / "clean")
    report = json.loads((tmp_path / "clean/_ingest.json").read_text())
    assert report["issues"] == 2 and report["matched"] == 2 and report["sources"] == ["mcp"]
    assert report["changelog_incomplete"] == ["ABC-401"] and report["comments_incomplete"] == ["ABC-401"]


def test_clean_issue_files_hold_no_person_identifiers(tmp_path, people):
    raw = write_raw(tmp_path, {"mcp-page-1.json": load_fixture("recorded/mcp_search_result.json"),
                               "dc.json": {"issues": [load_fixture("jira/dc_issue_ABC-102.json")]}})
    anonymise.anonymise_dir(raw, tmp_path / "clean")
    text = all_text_under(tmp_path / "clean")
    found = [i for i in person_identifiers(people) if re.search(rf"(?<!\w){re.escape(i)}(?!\w)", text, re.I)]
    assert found == []
