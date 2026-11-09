"""Behaviour tests for scripts/scm_azure.py, the Azure DevOps adapter (F4).

Replays recorded Azure DevOps REST responses: completed pull requests paged by $top and
$skip (with a 429 and Retry-After on the first page), commits paged by continuation
token, and last-iteration changes paged by nextSkip. A second fixture holds the same
pull requests as Claude would save them from an Azure DevOps MCP (text blocks, numeric
status, an abandoned pull request too). Both must give the same changes after
anonymisation, with no person left.
"""

import base64
import json
import re
import shutil
from pathlib import Path

import pytest

import anonymise
import clean_data
import link_scm
import scm_adapter
import scm_azure
from conftest import FIXTURES, all_text_under, load_fixture, person_identifiers
from test_scm_gitlab import Recorded

REPO = {"platform": "azure", "org": "example-org", "project": "Accounts", "repo": "accounts-api", "team": "Accounts",
        "key_pattern": r"ABC[-_ ]?\d+"}
CONFIG = {"min_group_size": None, "default_key_pattern": None, "repos": [REPO]}
SINCE = "2026-01-01"
TOKEN = "azdo-secret-test-pat"
NAME = "Accounts/accounts-api"
# Identifiers only the Azure DevOps fixtures hold: descriptors, a domain account and a team GUID's owner.
AZURE_ONLY = ["aad.UHJpeWFUZXN0d2VsbFN5bnRoZXRpYw", "aad.VG9tYXN6RmFrZW5hbWVTeW50aA", "aad.R3JhY2VQbGFjZWhvbGRlclN5bg",
              "aad.T2x1d2FzZXVuTW9ja2xleVN5bg", "win.RGFuYVNhbXBsZXRvblN5bnRo", "EXAMPLE\\dsampleton", "identityImage",
              "MemberAvatars", "tomasz.f"]


def fetch(tmp_path, fixture=None, **client_kwargs):
    fixture = fixture or load_fixture("recorded/azure_rest.json")
    transport, sleeps = Recorded(fixture), []
    client = scm_azure.AzureDevOpsClient(REPO["org"], TOKEN, transport=transport, sleep=sleeps.append,
                                         **{"page_size": 2, **client_kwargs})
    summary = scm_azure.ADAPTER.fetch(REPO, SINCE, tmp_path / "raw", client)
    return summary, transport, sleeps


def changes_from(raw, tmp_path):
    anonymise.anonymise_dir(raw, tmp_path / "clean", scm_config=CONFIG)
    docs = clean_data.load_clean_documents(tmp_path / "clean")
    found = scm_azure.ADAPTER.changes(docs, REPO)
    return [c for c in found if (c.merged_at or "")[:10] >= SINCE], tmp_path / "clean"


def mcp_raw(tmp_path):
    raw = tmp_path / "mcp_raw"
    shutil.copytree(FIXTURES / "scm/azure_mcp", raw)
    return raw


def requests_to(transport, suffix):
    return [q for _, path, q, _ in transport.requests if path.endswith(suffix)]


# --- fetching: paging, rate limits, credentials ------------------------------------------------

def test_every_page_of_pull_requests_commits_and_changes_is_fetched(tmp_path):
    summary, transport, _ = fetch(tmp_path)
    assert summary == {"repo": NAME, "changes": 4, "files_written": 14}
    assert [q["$skip"] for q in requests_to(transport, "/pullrequests")] == ["0", "0", "2", "4"]
    assert [q.get("continuationToken") for q in requests_to(transport, "/201/commits")] == [None, "tok-201-1"]
    assert [q["$skip"] for q in requests_to(transport, "/201/iterations/2/changes")] == ["0", "2"]
    names = {p.name for p in (tmp_path / "raw").iterdir()}
    prefix = "azure-pr-11111111-2222-4333-8444-555555555555-201"
    assert {f"{prefix}-commits-2.json", f"{prefix}-changes-2.json"} <= names


def test_only_the_last_iteration_of_each_pull_request_is_used_for_changed_files(tmp_path):
    _, transport, _ = fetch(tmp_path)
    changed = sorted(path.rsplit("/pullRequests/", 1)[1] for _, path, _, _ in transport.requests if path.endswith("/changes"))
    assert set(changed) == {"201/iterations/2/changes", "202/iterations/1/changes", "203/iterations/1/changes",
                            "204/iterations/3/changes"}


def test_the_window_comes_from_since_and_older_pull_requests_are_skipped(tmp_path):
    _, transport, _ = fetch(tmp_path)
    for q in requests_to(transport, "/pullrequests"):
        assert (q["searchCriteria.status"], q["searchCriteria.queryTimeRangeType"], q["searchCriteria.minTime"]) == \
            ("completed", "closed", "2026-01-01T00:00:00Z")
    assert not any("/pullRequests/199/" in path for _, path, _, _ in transport.requests)


def test_rate_limits_wait_for_retry_after_then_retry(tmp_path):
    _, _, sleeps = fetch(tmp_path)
    assert sleeps == [4]


def test_persistent_rate_limiting_gives_up_with_a_clear_error(tmp_path):
    fixture = {"routes": [{"method": "GET", "path": "/example-org/Accounts/_apis/git/repositories/accounts-api/pullrequests",
                           "match": {}, "responses": [{"status": 429, "headers": {}, "body": {}}]}]}
    with pytest.raises(RuntimeError, match="rate limit"):
        fetch(tmp_path, fixture, max_retries=2)


def test_an_http_error_names_the_status_but_never_the_token(tmp_path):
    fixture = {"routes": [{"method": "GET", "path": "/example-org/Accounts/_apis/git/repositories/accounts-api/pullrequests",
                           "match": {}, "responses": [{"status": 401, "body": {"message": "TF400813: not authorised"}}]}]}
    with pytest.raises(RuntimeError) as err:
        fetch(tmp_path, fixture)
    assert "401" in str(err.value) and TOKEN not in str(err.value)
    assert base64.b64encode(f":{TOKEN}".encode()).decode() not in str(err.value)


def test_the_token_goes_in_a_basic_auth_header_and_is_never_written(tmp_path):
    _, transport, _ = fetch(tmp_path)
    expected = "Basic " + base64.b64encode(f":{TOKEN}".encode()).decode()
    assert all(h["Authorization"] == expected for *_, h in transport.requests)
    assert all(TOKEN not in path and TOKEN not in json.dumps(q) for _, path, q, _ in transport.requests)
    raw = all_text_under(tmp_path / "raw")
    assert TOKEN not in raw and expected.split()[1] not in raw


def test_the_client_reads_its_token_from_azdo_pat_and_names_it_when_missing():
    with pytest.raises(KeyError, match="AZDO_PAT"):
        scm_azure.ADAPTER.client_from_env(REPO, {})
    assert isinstance(scm_azure.ADAPTER.client_from_env(REPO, {"AZDO_PAT": TOKEN}), scm_azure.AzureDevOpsClient)


# --- normalising: one path for REST and MCP shapes ---------------------------------------------

def test_rest_and_mcp_shapes_normalise_to_the_same_changes(tmp_path):
    fetch(tmp_path / "rest")
    rest, _ = changes_from(tmp_path / "rest/raw", tmp_path / "rest")
    mcp, _ = changes_from(mcp_raw(tmp_path), tmp_path / "mcp")
    assert [c.id for c in rest] == ["201", "202", "203", "204"]
    assert rest == mcp


def test_a_change_holds_every_commit_and_file_from_every_page(tmp_path):
    found, _ = changes_from(mcp_raw(tmp_path), tmp_path)
    pr = next(c for c in found if c.id == "201")
    assert isinstance(pr, scm_adapter.Change)
    assert (pr.repo, pr.kind, pr.merged_at) == (NAME, "pull_request", "2026-04-06T15:30:00Z")
    assert [c["id"][:4] for c in pr.commits] == ["2011", "2012", "2013"]
    assert pr.files == ["src/Accounts/Session/TimeoutPolicy.cs", "src/Accounts/Session/SessionStore.cs",
                        "tests/Accounts.Tests/Session/TimeoutPolicyTests.cs"]
    assert pr.title == "ABC-102 fix session timeout" and pr.source_branch == "fix/session-timeout"


def test_folders_are_not_files_and_abandoned_pull_requests_are_not_changes(tmp_path):
    found, _ = changes_from(mcp_raw(tmp_path), tmp_path)
    assert next(c for c in found if c.id == "202").files == ["src/Accounts/Address/AddressMapper.cs"]
    assert "205" not in [c.id for c in found]


@pytest.mark.parametrize("other", [{"repo": "accounts-web"}, {"project": "Payments"}, {"org": "another-org"}])
def test_pull_requests_from_another_repo_project_or_org_are_ignored(tmp_path, other):
    anonymise.anonymise_dir(mcp_raw(tmp_path), tmp_path / "clean", scm_config=CONFIG)
    docs = clean_data.load_clean_documents(tmp_path / "clean")
    assert scm_azure.ADAPTER.changes(docs, {**REPO, **other}) == []


def test_names_match_without_regard_to_case(tmp_path):
    anonymise.anonymise_dir(mcp_raw(tmp_path), tmp_path / "clean", scm_config=CONFIG)
    docs = clean_data.load_clean_documents(tmp_path / "clean")
    found = scm_azure.ADAPTER.changes(docs, {**REPO, "project": "accounts", "repo": "Accounts-API"})
    assert len(found) == 4


# --- people ------------------------------------------------------------------------------------

def run(tmp_path, raw, cfg=CONFIG):
    for name in ["jira/cloud_issue_ABC-101.json", "jira/dc_issue_ABC-102.json"]:
        (raw / name.split("/")[1]).write_text(json.dumps(load_fixture(name)))
    anonymise.anonymise_dir(raw, tmp_path / "clean", scm_config=cfg)
    links = link_scm.link(cfg, tmp_path / "clean")
    (tmp_path / "work").mkdir()
    (tmp_path / "work/scm_links.json").write_text(json.dumps(links))
    link_scm.write_coverage(links, tmp_path / "out")
    return links


@pytest.mark.parametrize("shape", ["rest", "mcp"])
def test_no_person_survives_under_clean_work_or_out(tmp_path, people, shape):
    if shape == "rest":
        fetch(tmp_path)
        raw = tmp_path / "raw"
    else:
        raw = mcp_raw(tmp_path)
    run(tmp_path, raw)
    for folder in ["clean", "work", "out"]:
        text = all_text_under(tmp_path / folder)
        assert [i for i in person_identifiers(people) if re.search(rf"(?<!\w){re.escape(i)}(?!\w)", text, re.I)] == [], folder
        assert [i for i in AZURE_ONLY if i.lower() in text.lower()] == [], folder
        assert "dsampleton" not in text.lower(), folder


def test_mentions_trailers_and_every_identity_field_become_the_placeholder(tmp_path):
    anonymise.anonymise_dir(mcp_raw(tmp_path), tmp_path / "clean", scm_config=CONFIG)
    docs = clean_data.load_clean_documents(tmp_path / "clean")
    prs = {p["pullRequestId"]: p for name, doc in docs.items() if name.startswith("azure-prs-") for p in doc}
    pr = prs[201]
    for ref in [pr["createdBy"], pr["closedBy"], pr["autoCompleteSetBy"], *pr["reviewers"]]:
        assert set(ref) <= {"person", "vote", "hasDeclined", "isFlagged", "isRequired"} and ref["person"] == "[person]"
    assert pr["lastMergeCommit"]["author"] == {"person": "[person]", "date": "2026-04-06T15:30:00Z"}
    assert pr["description"] == "Retries with backoff.\n\nReviewed by @<[person]>"
    assert prs[204]["description"] == "Fixes ABC-101 follow-up. cc @<[person]> and [person]"
    commits = docs["azure-pr-11111111-2222-4333-8444-555555555555-201-commits-1.json"]
    assert commits[0]["comment"] == "Add retry policy\n\n[trailer removed]"
    assert {commits[0][k]["person"] for k in ("author", "committer")} == {"[person]"}


def test_the_org_never_reaches_work_or_out(tmp_path):
    run(tmp_path, mcp_raw(tmp_path))
    for folder in ["work", "out"]:
        assert "example-org" not in all_text_under(tmp_path / folder)
    assert scm_azure.ADAPTER.repo_name(REPO, {}) == NAME


# --- linking -----------------------------------------------------------------------------------

def test_keys_are_found_in_titles_descriptions_branches_and_commits_with_the_repo_pattern(tmp_path):
    links = run(tmp_path, mcp_raw(tmp_path))
    assert links["repos"][NAME] == {"platform": "azure", "team": "Accounts", "changes_scanned": 4,
                                    "changes_linked": 3, "defects_linked": 2}
    assert [c["id"] for c in links["defects"]["ABC-101"]["changes"] if c["repo"] == NAME] == ["202", "204"]
    assert [c["id"] for c in links["defects"]["ABC-102"]["changes"] if c["repo"] == NAME] == ["201", "204"]


def test_without_the_repo_pattern_a_branch_written_abc_101_is_not_a_link(tmp_path):
    cfg = {**CONFIG, "repos": [{k: v for k, v in REPO.items() if k != "key_pattern"}]}
    links = run(tmp_path, mcp_raw(tmp_path), cfg)
    assert [c["id"] for c in links["defects"]["ABC-101"]["changes"]] == ["204"]


def test_the_adapter_is_registered_for_its_platform():
    assert scm_adapter.adapter_for("azure") is scm_azure.ADAPTER
    assert scm_adapter.is_ready("azure")
    assert scm_azure.ADAPTER.required_fields == ("org", "project", "repo")
    assert scm_azure.ADAPTER.owns_file("azure-prs-1.json") and not scm_azure.ADAPTER.owns_file("gitlab-mrs-1.json")


def test_raw_azure_devops_data_is_not_anonymised_without_the_config(tmp_path):
    with pytest.raises(ValueError, match="scm.yaml"):
        anonymise.anonymise_dir(mcp_raw(tmp_path), tmp_path / "clean")


def test_fixture_people_are_synthetic():
    assert "None of these people are real" in load_fixture("recorded/azure_rest.json")["note"]
    assert Path(FIXTURES / "scm/azure_mcp").is_dir()
