"""Behaviour tests for scripts/anonymise.py (P1 to P3, F2, known problems 1 and 2).

Highest risk first: a person identifiable after anonymisation. Then pseudonym and salt
handling, then damage to non-person data.
"""

import json
import re
import shutil
from pathlib import Path

import pytest

import anonymise
from conftest import FIXTURES, all_text_under, load_fixture, person_identifiers
from factory import gitlab_users, make_dataset

STATIC_FIXTURES = ["jira/cloud_issue_ABC-101.json", "jira/dc_issue_ABC-102.json",
                   "scm/gitlab_mr.json", "scm/azure_pr.json"]


def leaks(text: str, identifiers: set[str]) -> list[str]:
    """Return the identifiers that still appear in text (whole word, any case)."""
    return sorted(i for i in identifiers
                  if re.search(rf"(?<![\w]){re.escape(i)}(?![\w])", text, re.IGNORECASE))


def run_dir(tmp_path: Path, docs: dict[str, object]) -> Path:
    raw, clean = tmp_path / "raw", tmp_path / "clean"
    raw.mkdir(parents=True)
    for name, doc in docs.items():
        (raw / name).write_text(json.dumps(doc), encoding="utf-8")
    anonymise.anonymise_dir(raw, clean)
    return clean


def static_docs() -> dict[str, object]:
    return {Path(f).name: load_fixture(f) for f in STATIC_FIXTURES}


def scrub_all(docs: list) -> list:
    a = anonymise.Anonymiser()
    a.learn(docs)
    return [a.scrub(d) for d in docs]


# --- P1: no person identifier survives -------------------------------------------------

def test_no_seeded_identifier_survives_in_any_static_fixture(tmp_path, identifiers):
    clean = run_dir(tmp_path, static_docs())
    assert leaks(all_text_under(clean), identifiers) == []


@pytest.mark.parametrize("seed", range(40))
def test_no_seeded_identifier_survives_in_generated_jira_datasets(tmp_path, people, identifiers, seed):
    docs = {f"{d['key']}.json": d for d in make_dataset(seed, people)}
    clean = run_dir(tmp_path, docs)
    assert leaks(all_text_under(clean), identifiers) == []


@pytest.mark.parametrize("seed", range(20))
def test_source_control_handles_in_jira_text_are_removed_when_scm_data_is_in_the_run(tmp_path, people, identifiers, seed):
    docs = {f"{d['key']}.json": d for d in make_dataset(seed, people, scm_handles=True)}
    docs["gitlab_users.json"] = gitlab_users(people)
    clean = run_dir(tmp_path, docs)
    assert leaks(all_text_under(clean), identifiers) == []


def test_a_nickname_handle_is_not_caught_from_jira_data_alone():
    """Documented limit: '@seun.m' for Oluwaseun Mockley can't be tied to him without his SCM username."""
    a = anonymise.Anonymiser()
    a.learn([load_fixture("jira/cloud_issue_ABC-101.json")])
    assert a.scrub_text("cc @seun.m") == "cc @seun.m"


def test_jira_user_objects_become_pseudonyms_wherever_they_appear():
    issue = scrub_all([load_fixture("jira/cloud_issue_ABC-101.json")])[0]
    f = issue["fields"]
    for user in [f["assignee"], f["reporter"], f["creator"], f["customfield_10050"], *f["customfield_10051"],
                 f["comment"]["comments"][0]["author"], issue["changelog"]["histories"][0]["author"]]:
        assert set(user) == {"pseudonym"}
        assert re.fullmatch(r"person_[0-9a-f]{12}", user["pseudonym"])


def test_data_center_user_objects_lose_username_and_key():
    issue = scrub_all([load_fixture("jira/dc_issue_ABC-102.json")])[0]
    assert set(issue["fields"]["assignee"]) == {"pseudonym"}


def test_jira_mention_syntaxes_are_redacted():
    cloud, dc = scrub_all([load_fixture("jira/cloud_issue_ABC-101.json"), load_fixture("jira/dc_issue_ABC-102.json")])
    plain = cloud["fields"]["comment"]["comments"][1]["body"]
    assert "[~accountid:" not in plain and "[person] please check" in plain
    assert "[~" not in dc["fields"]["description"] and "Sign in as [person] on SIT" in dc["fields"]["description"]
    assert "[~" not in dc["fields"]["comment"]["comments"][0]["body"]


def test_adf_mention_nodes_keep_their_shape_but_lose_the_person():
    issue = scrub_all([load_fixture("jira/cloud_issue_ABC-101.json")])[0]
    node = issue["fields"]["description"]["content"][0]["content"][1]
    assert node == {"type": "mention", "attrs": {"text": "[person]"}}


def test_known_handles_and_handles_built_from_known_names_are_redacted():
    issue = scrub_all([load_fixture("jira/cloud_issue_ABC-101.json")])[0]
    body = issue["fields"]["comment"]["comments"][1]["body"]
    assert "cc [person] and [person]." in body


def test_emails_are_redacted_including_people_not_in_the_data():
    issue = scrub_all([load_fixture("jira/cloud_issue_ABC-101.json")])[0]
    text = json.dumps(issue)
    assert "customer.one@example.com" not in text and "Customer contact: [person]." in text


def test_commit_trailers_are_removed():
    dc, gitlab, azure = scrub_all([load_fixture("jira/dc_issue_ABC-102.json"), load_fixture("scm/gitlab_mr.json"),
                                   load_fixture("scm/azure_pr.json")])
    assert dc["fields"]["description"].endswith("[trailer removed]")
    assert gitlab["commits"][0]["message"] == "Fix null address line\n\nABC-101\n\n[trailer removed]\n[trailer removed]"
    assert "Reviewed-by" not in azure["commits"][0]["comment"]


def test_display_names_and_their_parts_are_redacted_in_free_text():
    cloud, dc = scrub_all([load_fixture("jira/cloud_issue_ABC-101.json"), load_fixture("jira/dc_issue_ABC-102.json")])
    comment = cloud["fields"]["comment"]["comments"][0]["body"]["content"][0]["content"][1]["text"]
    assert comment == " can you confirm the repro? Thanks [person], and [person] said it started after the release."
    assert dc["fields"]["comment"]["comments"][1]["body"] == "Chrome 128. [person] and I paired on it; [person] reviewed."


def test_changelog_person_fields_are_pseudonymised():
    cloud, dc = scrub_all([load_fixture("jira/cloud_issue_ABC-101.json"), load_fixture("jira/dc_issue_ABC-102.json")])
    for item in [cloud["changelog"]["histories"][1]["items"][0], dc["changelog"]["histories"][1]["items"][0]]:
        assert item["fromString"] == "[person]" and item["toString"] == "[person]"
        assert item["from"].startswith("person_") and item["to"].startswith("person_")


def test_gitlab_people_are_pseudonymised_and_paths_kept():
    mr = scrub_all([load_fixture("scm/gitlab_mr.json")])[0]
    for user in [mr["author"], mr["merged_by"], *mr["reviewers"], *mr["assignees"]]:
        assert set(user) == {"pseudonym"}
    commit = mr["commits"][0]
    for key in ["author_name", "author_email", "committer_name", "committer_email"]:
        assert commit[key].startswith("person_")
    assert mr["description"].startswith("Closes ABC-101. cc [person] [person]")
    assert mr["diffs"][0]["new_path"] == "src/checkout/address.py"
    assert mr["source_branch"] == "fix/ABC-101-address"


def test_azure_devops_identities_and_guid_mentions_are_removed():
    pr = scrub_all([load_fixture("scm/azure_pr.json")])[0]
    for ident in [pr["createdBy"], pr["closedBy"], pr["reviewers"][0], pr["commits"][0]["author"], pr["commits"][0]["committer"]]:
        assert "pseudonym" in ident and not {"displayName", "uniqueName", "name", "email"} & set(ident)
    assert pr["reviewers"][0]["vote"] == 10
    assert pr["description"] == "Retries with backoff. @<[person]> please review."
    assert pr["changes"][0]["item"]["path"] == "/src/Accounts/TimeoutPolicy.cs"


# --- P2 and P3: pseudonyms and salt --------------------------------------------------------

def test_the_same_person_gets_the_same_pseudonym_within_a_run():
    issue = scrub_all([load_fixture("jira/cloud_issue_ABC-101.json")])[0]
    assert issue["fields"]["assignee"] == issue["fields"]["comment"]["comments"][0]["author"]
    assert issue["fields"]["reporter"] != issue["fields"]["assignee"]


def test_pseudonyms_differ_between_runs_so_they_cannot_be_joined(tmp_path):
    first = json.loads((run_dir(tmp_path / "a", static_docs()) / "ABC-101.json").read_text())
    second = json.loads((run_dir(tmp_path / "b", static_docs()) / "ABC-101.json").read_text())
    assert first["fields"]["assignee"] != second["fields"]["assignee"]


def test_salt_is_never_written_to_disk(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    salt = b"known-test-salt-0123456789abcdef"
    raw = tmp_path / "raw"
    raw.mkdir()
    for name, doc in static_docs().items():
        (raw / name).write_text(json.dumps(doc), encoding="utf-8")
    anonymise.anonymise_dir(raw, tmp_path / "clean", anonymiser=anonymise.Anonymiser(salt=salt))
    everything = b"".join(p.read_bytes() for p in tmp_path.rglob("*") if p.is_file())
    assert salt not in everything and salt.hex().encode() not in everything


def test_each_anonymiser_draws_a_fresh_salt():
    assert anonymise.Anonymiser().pseudonym("acc-1") != anonymise.Anonymiser().pseudonym("acc-1")


def test_only_cleaned_files_are_written(tmp_path):
    clean = run_dir(tmp_path, static_docs())
    assert sorted(p.name for p in clean.iterdir()) == ["ABC-101.json", "ABC-102.json", "_ingest.json",
                                                       "azure_pr.json", "gitlab_mr.json"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["clean", "raw"]


def test_cleaned_documents_carry_the_anonymised_marker(tmp_path):
    clean = run_dir(tmp_path, static_docs())
    for p in clean.iterdir():
        assert json.loads(p.read_text())["_anonymised"]["by"] == "anonymise.py"


def test_anonymising_twice_is_harmless():
    a = anonymise.Anonymiser()
    doc = load_fixture("jira/cloud_issue_ABC-101.json")
    a.learn([doc])
    once = a.scrub(doc)
    b = anonymise.Anonymiser()
    b.learn([once])
    assert b.scrub(once)["fields"]["summary"] == once["fields"]["summary"]
    assert b.scrub(once)["fields"]["assignee"] == once["fields"]["assignee"]


# --- F2: no damage to non-person data (known problems 1 and 2) -----------------------------

def test_structural_names_survive_unchanged():
    issue = scrub_all([load_fixture("jira/cloud_issue_ABC-101.json")])[0]
    f = issue["fields"]
    assert f["status"]["name"] == "In Progress" and f["status"]["statusCategory"]["name"] == "In Progress"
    assert f["issuetype"]["name"] == "Bug"
    assert [c["name"] for c in f["components"]] == ["Payments"]
    assert f["priority"]["name"] == "High"
    assert f["project"]["name"] == "Alpha Billing" and f["project"]["key"] == "ABC"
    assert f["labels"] == ["checkout", "regression"]
    assert f["fixVersions"][0]["name"] == "2026.03"
    status_item, = issue["changelog"]["histories"][0]["items"]
    assert (status_item["field"], status_item["fromString"], status_item["toString"]) == ("status", "To Do", "In Progress")
    component_item = issue["changelog"]["histories"][2]["items"][0]
    assert (component_item["field"], component_item["toString"]) == ("Component", "Payments")


def test_resolution_and_data_center_status_names_survive():
    issue = scrub_all([load_fixture("jira/dc_issue_ABC-102.json")])[0]
    assert issue["fields"]["status"]["name"] == "Ready for Test"
    assert issue["fields"]["resolution"]["name"] == "Fixed"
    assert issue["changelog"]["histories"][0]["items"][0]["toString"] == "Ready for Test"


def test_code_and_file_paths_in_ticket_text_survive():
    cloud, dc = scrub_all([load_fixture("jira/cloud_issue_ABC-101.json"), load_fixture("jira/dc_issue_ABC-102.json")])
    text = json.dumps(cloud) + json.dumps(dc)
    for kept in ["@Override", "@media (max-width: 600px)", "@media print", "assets/logo@2x.png",
                 "src/main/java/com/example/checkout/AddressValidator.java", "POST /api/v2/checkout",
                 "com/example/accounts/SessionFilter.java:88", "The @Override on timeout() looks wrong."]:
        assert kept in text.replace("\\n", "\n"), kept


@pytest.mark.parametrize("snippet", ["@Override public String toString() { return id; }",
                                     "@media (max-width: 600px) { .nav { display: none; } }",
                                     "@Test void rejectsEmptyPostcode() {}",
                                     "@app.route('/checkout') def checkout(): pass",
                                     "@import url('theme.css');",
                                     "@keyframes spin { to { transform: rotate(1turn); } }",
                                     "see icons/arrow@3x.webp and build@v2 tag"])
def test_code_that_looks_like_a_mention_survives(people, snippet):
    a = anonymise.Anonymiser()
    a.learn([{"fields": {"assignee": {"accountId": p["account_id"], "displayName": p["display_name"]}}} for p in people])
    assert a.scrub_text(snippet) == snippet


def test_a_name_part_that_is_also_a_component_name_is_kept_in_the_component():
    issue = {"key": "ABC-1", "fields": {
        "components": [{"id": "1", "name": "Search"}],
        "assignee": {"accountId": "acc-robin", "displayName": "Robin Search"},
        "description": "Robin Search says Search is slow; Robin will look."}}
    out = scrub_all([issue])[0]
    assert out["fields"]["components"][0]["name"] == "Search"
    assert out["fields"]["description"] == "[person] says Search is slow; [person] will look."


def test_handles_for_people_absent_from_the_data_are_left_alone():
    """Documented trade-off: only handles that match a known person are redacted, so code survives."""
    a = anonymise.Anonymiser()
    a.learn([load_fixture("jira/cloud_issue_ABC-101.json")])
    assert a.scrub_text("ask @outsider") == "ask @outsider"


def test_non_json_and_unrelated_files_are_ignored(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    shutil.copy(FIXTURES / "jira/cloud_issue_ABC-101.json", raw)
    (raw / "notes.txt").write_text("Priya Testwell")
    anonymise.anonymise_dir(raw, tmp_path / "clean")
    assert sorted(p.name for p in (tmp_path / "clean").iterdir()) == ["ABC-101.json", "_ingest.json"]


def test_identifier_list_used_by_these_tests_is_not_empty(people):
    assert len(person_identifiers(people)) > 30
