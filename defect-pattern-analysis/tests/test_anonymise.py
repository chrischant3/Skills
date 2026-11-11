"""Behaviour tests for scripts/anonymise.py (P1 to P3, F2, known problems 1 and 2).

P1 here means no identifier survives into clean/, so none reaches analysis code,
classification input or output. (With MCP fetching the model sees raw data only during
the fetch step, which these tests can't cover.)

Highest risk first: a person identifiable after anonymisation. Then the plain placeholder
that replaces every person (no salt, hash or pseudonym), then damage to non-person data.
"""

import json
import re
import shutil
from pathlib import Path

import pytest

import anonymise
from conftest import FIXTURES, all_text_under, load_fixture, person_identifiers
from factory import gitlab_users, make_dataset

STATIC_FIXTURES = [
    "jira/cloud_issue_ABC-101.json",
    "jira/dc_issue_ABC-102.json",
    "scm/gitlab_mr.json",
    "scm/azure_pr.json",
]


def leaks(text: str, identifiers: set[str]) -> list[str]:
    """Return the identifiers that still appear in text (whole word, any case)."""
    return sorted(
        i
        for i in identifiers
        if re.search(rf"(?<![\w]){re.escape(i)}(?![\w])", text, re.IGNORECASE)
    )


def run_dir(tmp_path: Path, docs: dict[str, object]) -> Path:
    raw, clean = tmp_path / "raw", tmp_path / "clean"
    raw.mkdir(parents=True)
    for name, doc in docs.items():
        (raw / name).write_text(json.dumps(doc), encoding="utf-8")
    anonymise.anonymise_dir(raw, clean, scm_config={"repos": []})
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
def test_no_seeded_identifier_survives_in_generated_jira_datasets(
    tmp_path, people, identifiers, seed
):
    docs = {f"{d['key']}.json": d for d in make_dataset(seed, people)}
    clean = run_dir(tmp_path, docs)
    assert leaks(all_text_under(clean), identifiers) == []


@pytest.mark.parametrize("seed", range(20))
def test_source_control_handles_in_jira_text_are_removed_when_scm_data_is_in_the_run(
    tmp_path, people, identifiers, seed
):
    docs = {f"{d['key']}.json": d for d in make_dataset(seed, people, scm_handles=True)}
    docs["gitlab_users.json"] = gitlab_users(people)
    clean = run_dir(tmp_path, docs)
    assert leaks(all_text_under(clean), identifiers) == []


def test_a_nickname_handle_is_redacted_from_jira_data_alone():
    """'@seun.m' can't be tied to Oluwaseun Mockley without his SCM username, but every handle in prose goes."""
    a = anonymise.Anonymiser()
    a.learn([load_fixture("jira/cloud_issue_ABC-101.json")])
    assert a.scrub_text("cc @seun.m") == "cc [person]"


@pytest.mark.parametrize("seed", range(20))
def test_source_control_handles_in_jira_text_are_removed_even_without_scm_data(
    tmp_path, people, identifiers, seed
):
    docs = {f"{d['key']}.json": d for d in make_dataset(seed, people, scm_handles=True)}
    clean = run_dir(tmp_path, docs)
    assert leaks(all_text_under(clean), identifiers) == []


PERSON = {"person": "[person]"}


def test_jira_user_objects_become_the_placeholder_wherever_they_appear():
    issue = scrub_all([load_fixture("jira/cloud_issue_ABC-101.json")])[0]
    f = issue["fields"]
    for user in [
        f["assignee"],
        f["reporter"],
        f["creator"],
        f["customfield_10050"],
        *f["customfield_10051"],
        f["comment"]["comments"][0]["author"],
        issue["changelog"]["histories"][0]["author"],
    ]:
        assert user == PERSON


def test_data_center_user_objects_lose_username_and_key():
    issue = scrub_all([load_fixture("jira/dc_issue_ABC-102.json")])[0]
    assert issue["fields"]["assignee"] == PERSON


def test_jira_mention_syntaxes_are_redacted():
    cloud, dc = scrub_all(
        [
            load_fixture("jira/cloud_issue_ABC-101.json"),
            load_fixture("jira/dc_issue_ABC-102.json"),
        ]
    )
    plain = cloud["fields"]["comment"]["comments"][1]["body"]
    assert "[~accountid:" not in plain and "[person] please check" in plain
    assert (
        "[~" not in dc["fields"]["description"]
        and "Sign in as [person] on SIT" in dc["fields"]["description"]
    )
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
    assert (
        "customer.one@example.com" not in text and "Customer contact: [person]." in text
    )


def test_commit_trailers_are_removed():
    dc, gitlab, azure = scrub_all(
        [
            load_fixture("jira/dc_issue_ABC-102.json"),
            load_fixture("scm/gitlab_mr.json"),
            load_fixture("scm/azure_pr.json"),
        ]
    )
    assert dc["fields"]["description"].endswith("[trailer removed]")
    assert (
        gitlab["commits"][0]["message"]
        == "Fix null address line\n\nABC-101\n\n[trailer removed]\n[trailer removed]"
    )
    assert "Reviewed-by" not in azure["commits"][0]["comment"]


def test_display_names_and_their_parts_are_redacted_in_free_text():
    cloud, dc = scrub_all(
        [
            load_fixture("jira/cloud_issue_ABC-101.json"),
            load_fixture("jira/dc_issue_ABC-102.json"),
        ]
    )
    comment = cloud["fields"]["comment"]["comments"][0]["body"]["content"][0][
        "content"
    ][1]["text"]
    assert (
        comment
        == " can you confirm the repro? Thanks [person], and [person] said it started after the release."
    )
    assert (
        dc["fields"]["comment"]["comments"][1]["body"]
        == "Chrome 128. [person] and I paired on it; [person] reviewed."
    )


def test_changelog_person_fields_become_the_placeholder():
    cloud, dc = scrub_all(
        [
            load_fixture("jira/cloud_issue_ABC-101.json"),
            load_fixture("jira/dc_issue_ABC-102.json"),
        ]
    )
    for item in [
        cloud["changelog"]["histories"][1]["items"][0],
        dc["changelog"]["histories"][1]["items"][0],
    ]:
        assert (item["from"], item["fromString"], item["to"], item["toString"]) == (
            "[person]",
        ) * 4


def test_gitlab_people_become_the_placeholder_and_paths_are_kept():
    mr = scrub_all([load_fixture("scm/gitlab_mr.json")])[0]
    for user in [mr["author"], mr["merged_by"], *mr["reviewers"], *mr["assignees"]]:
        assert user == PERSON
    commit = mr["commits"][0]
    for key in ["author_name", "author_email", "committer_name", "committer_email"]:
        assert commit[key] == "[person]"
    assert mr["description"].startswith("Closes ABC-101. cc [person] [person]")
    assert mr["diffs"][0]["new_path"] == "src/checkout/address.py"
    assert mr["source_branch"] == "fix/ABC-101-address"


def test_azure_devops_identities_and_guid_mentions_are_removed():
    pr = scrub_all([load_fixture("scm/azure_pr.json")])[0]
    for ident in [
        pr["createdBy"],
        pr["closedBy"],
        pr["reviewers"][0],
        pr["commits"][0]["author"],
        pr["commits"][0]["committer"],
    ]:
        assert ident["person"] == "[person]" and not {
            "displayName",
            "uniqueName",
            "name",
            "email",
            "id",
        } & set(ident)
    assert pr["reviewers"][0]["vote"] == 10
    assert pr["description"] == "Retries with backoff. @<[person]> please review."
    assert pr["changes"][0]["item"]["path"] == "/src/Accounts/TimeoutPolicy.cs"


def test_azure_devops_mentions_of_people_found_nowhere_else_are_removed():
    doc = {
        "description": "Thanks @<00000000-0000-4000-8000-0000000000aa>, and @<0000000A-0000-4000-8000-0000000000BB>."
    }
    assert scrub_all([doc])[0]["description"] == "Thanks @<[person]>, and @<[person]>."


def test_an_azure_devops_identity_ref_without_a_name_is_still_a_person():
    ref = {
        "id": "00000000-0000-4000-8000-0000000000cc",
        "descriptor": "aad.ZmFrZS1kZXNjcmlwdG9y",
        "imageUrl": "https://dev.azure.com/example-org/_api/_common/identityImage?id=00000000-0000-4000-8000-0000000000cc",
        "_links": {
            "avatar": {
                "href": "https://dev.azure.com/example-org/_apis/GraphProfile/MemberAvatars/aad.ZmFr"
            }
        },
    }
    doc = {"autoCompleteSetBy": ref, "description": "Set by aad.ZmFrZS1kZXNjcmlwdG9y."}
    clean = scrub_all([doc])[0]
    assert clean["autoCompleteSetBy"] == PERSON
    assert clean["description"] == "Set by [person]."


def test_the_account_part_of_a_domain_unique_name_is_removed_from_text():
    doc = {
        "reviewers": [
            {"displayName": "Robin Quill", "uniqueName": "EXAMPLE\\rquill", "id": "x1"}
        ],
        "description": "Ask EXAMPLE\\rquill, or rquill directly.",
    }
    assert scrub_all([doc])[0]["description"] == "Ask [person], or [person] directly."


# --- P1 for source control data and MCP results ----------------------------------------------


def mcp_text_block(value) -> dict:
    """Wrap value the way an MCP tool result holds JSON: as text inside a content block."""
    return {"content": [{"type": "text", "text": json.dumps(value)}]}


def test_people_inside_an_mcp_text_block_are_learnt_so_their_plain_names_go_everywhere(
    tmp_path, identifiers
):
    issue = load_fixture("jira/cloud_issue_ABC-101.json")
    mr = load_fixture("scm/gitlab_mr.json")
    mr["description"] = "Tomasz Fakename and Priya said this fixes it"
    clean = run_dir(
        tmp_path,
        {
            "mcp-page-1.json": mcp_text_block({"issues": [issue]}),
            "gitlab-mrs-1.json": mcp_text_block([mr]),
        },
    )
    assert leaks(all_text_under(clean), identifiers) == []
    assert (
        json.loads((clean / "gitlab-mrs-1.json").read_text())["items"][0]["author"]
        == PERSON
    )


def test_a_numeric_user_id_does_not_remove_the_same_number_from_text():
    mr = load_fixture("scm/gitlab_mr.json")
    mr["title"] = "ABC-501 and ABC-502 fix, 501 lines"
    out = scrub_all([mr])[0]
    assert out["title"] == "ABC-501 and ABC-502 fix, 501 lines"
    assert out["author"] == PERSON


def test_gitlab_commit_trailer_fields_lose_every_value():
    commit = {
        "id": "a" * 40,
        "message": "Fix",
        "author_name": "Priya Testwell",
        "trailers": {"Co-authored-by": "Unseen Contributor <unseen@example.com>"},
        "extended_trailers": {"Reviewed-by": ["Another Outsider <other@example.com>"]},
    }
    out = json.dumps(scrub_all([commit])[0])
    assert "Unseen" not in out and "Outsider" not in out and "example.com" not in out
    assert "Co-authored-by" in out and "Reviewed-by" in out


@pytest.mark.parametrize(
    "trailer", ["Approved-by", "Helped-by", "Suggested-by", "Co-developed-by"]
)
def test_other_person_trailers_in_commit_messages_are_removed(trailer):
    a = anonymise.Anonymiser()
    assert (
        a.scrub_text(f"Fix it\n\n{trailer}: Unseen Contributor <u@example.com>")
        == "Fix it\n\n[trailer removed]"
    )


def test_diff_bodies_are_dropped_but_paths_kept():
    diff = {
        "old_path": "CODEOWNERS",
        "new_path": "CODEOWNERS",
        "diff": "+/src/ Unseen Contributor",
        "new_file": False,
    }
    out = scrub_all([[diff]])[0][0]
    assert out == {
        "old_path": "CODEOWNERS",
        "new_path": "CODEOWNERS",
        "diff": "[diff removed]",
        "new_file": False,
    }


# --- P2 and P3: one plain placeholder, no salt, hash or pseudonym ---------------------------


def test_different_people_become_the_same_placeholder_so_no_one_can_be_told_apart():
    issue = scrub_all([load_fixture("jira/cloud_issue_ABC-101.json")])[0]
    f = issue["fields"]
    assert (
        f["assignee"]
        == f["reporter"]
        == f["comment"]["comments"][0]["author"]
        == PERSON
    )


def test_no_hash_or_pseudonym_of_a_person_is_written(tmp_path):
    text = all_text_under(run_dir(tmp_path, static_docs()))
    assert "pseudonym" not in text
    assert not re.search(r"person_[0-9a-f]+", text)
    without_commit_ids = re.sub(
        r"\b[0-9a-f]{40}\b", "", text
    )  # git SHAs are data, not people
    assert not re.search(r"\b[0-9a-f]{12,}\b", without_commit_ids)


def test_output_is_identical_between_runs_because_nothing_is_salted(tmp_path):
    first = all_text_under(run_dir(tmp_path / "a", static_docs()))
    second = all_text_under(run_dir(tmp_path / "b", static_docs()))
    assert first == second


def test_the_anonymiser_takes_no_salt():
    with pytest.raises(TypeError):
        anonymise.Anonymiser(salt=b"anything")


def test_only_cleaned_files_are_written(tmp_path):
    clean = run_dir(tmp_path, static_docs())
    assert sorted(p.name for p in clean.iterdir()) == [
        "ABC-101.json",
        "ABC-102.json",
        "_ingest.json",
        "azure_pr.json",
        "gitlab_mr.json",
    ]
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
    assert (
        f["status"]["name"] == "In Progress"
        and f["status"]["statusCategory"]["name"] == "In Progress"
    )
    assert f["issuetype"]["name"] == "Bug"
    assert [c["name"] for c in f["components"]] == ["Payments"]
    assert f["priority"]["name"] == "High"
    assert f["project"]["name"] == "Alpha Billing" and f["project"]["key"] == "ABC"
    assert f["labels"] == ["checkout", "regression"]
    assert f["fixVersions"][0]["name"] == "2026.03"
    (status_item,) = issue["changelog"]["histories"][0]["items"]
    assert (
        status_item["field"],
        status_item["fromString"],
        status_item["toString"],
    ) == ("status", "To Do", "In Progress")
    component_item = issue["changelog"]["histories"][2]["items"][0]
    assert (component_item["field"], component_item["toString"]) == (
        "Component",
        "Payments",
    )


def test_resolution_and_data_center_status_names_survive():
    issue = scrub_all([load_fixture("jira/dc_issue_ABC-102.json")])[0]
    assert issue["fields"]["status"]["name"] == "Ready for Test"
    assert issue["fields"]["resolution"]["name"] == "Fixed"
    assert (
        issue["changelog"]["histories"][0]["items"][0]["toString"] == "Ready for Test"
    )


def test_code_and_file_paths_in_ticket_text_survive():
    cloud, dc = scrub_all(
        [
            load_fixture("jira/cloud_issue_ABC-101.json"),
            load_fixture("jira/dc_issue_ABC-102.json"),
        ]
    )
    text = json.dumps(cloud) + json.dumps(dc)
    for kept in [
        "@Override",
        "@media (max-width: 600px)",
        "@media print",
        "assets/logo@2x.png",
        "src/main/java/com/example/checkout/AddressValidator.java",
        "POST /api/v2/checkout",
        "com/example/accounts/SessionFilter.java:88",
        "The @Override on timeout() looks wrong.",
    ]:
        assert kept in text.replace("\\n", "\n"), kept


@pytest.mark.parametrize(
    "snippet",
    [
        "@Override public String toString() { return id; }",
        "@media (max-width: 600px) { .nav { display: none; } }",
        "@Test void rejectsEmptyPostcode() {}",
        "@app.route('/checkout') def checkout(): pass",
        "@import url('theme.css');",
        "@keyframes spin { to { transform: rotate(1turn); } }",
        "see icons/arrow@3x.webp and build@v2 tag",
    ],
)
def test_code_that_looks_like_a_mention_survives(people, snippet):
    a = anonymise.Anonymiser()
    a.learn(
        [
            {
                "fields": {
                    "assignee": {
                        "accountId": p["account_id"],
                        "displayName": p["display_name"],
                    }
                }
            }
            for p in people
        ]
    )
    assert a.scrub_text(snippet) == snippet


def test_a_name_part_that_is_also_a_component_name_is_kept_in_the_component():
    issue = {
        "key": "ABC-1",
        "fields": {
            "components": [{"id": "1", "name": "Search"}],
            "assignee": {"accountId": "acc-robin", "displayName": "Robin Search"},
            "description": "Robin Search says Search is slow; Robin will look.",
        },
    }
    out = scrub_all([issue])[0]
    assert out["fields"]["components"][0]["name"] == "Search"
    assert (
        out["fields"]["description"]
        == "[person] says Search is slow; [person] will look."
    )


@pytest.mark.parametrize(
    "text,expected",
    [
        ("ask @outsider", "ask [person]"),
        ("Thanks @Sam.", "Thanks [person]."),
        ("@j-doe and @sam_k agreed", "[person] and [person] agreed"),
        ("pinged @ops.oncall at 3am", "pinged [person] at 3am"),
        ("(cc @bob)", "(cc [person])"),
    ],
)
def test_handles_for_people_absent_from_the_data_are_redacted_in_prose(text, expected):
    a = anonymise.Anonymiser()
    a.learn([load_fixture("jira/cloud_issue_ABC-101.json")])
    assert a.scrub_text(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "```\n@outsider was here\n@CustomAnnotation\n```",
        "run `@outsider/cli build` first",
        "{code:java}\n@CustomAnnotation\nclass A {}\n{code}",
        "{noformat}@outsider{noformat}",
        "use {{@outsider}} as the scope",
        "install @types/node and @angular/core",
        "@app.route('/checkout') and @pytest.fixture(scope='module')",
    ],
)
def test_unknown_handles_inside_code_are_kept(text):
    a = anonymise.Anonymiser()
    a.learn([load_fixture("jira/cloud_issue_ABC-101.json")])
    assert a.scrub_text(text) == text


def test_known_people_are_redacted_even_inside_code():
    a = anonymise.Anonymiser()
    a.learn([load_fixture("jira/cloud_issue_ABC-101.json")])
    assert a.scrub_text("```\n// asked @priya.t\n```") == "```\n// asked [person]\n```"


def test_adf_code_is_kept_but_prose_handles_go():
    doc = {
        "key": "ABC-1",
        "fields": {
            "description": {
                "type": "doc",
                "content": [
                    {
                        "type": "codeBlock",
                        "content": [
                            {"type": "text", "text": "@CustomAnnotation\nclass A {}"}
                        ],
                    },
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": "@Inline",
                                "marks": [{"type": "code"}],
                            },
                            {"type": "text", "text": " reviewed by @outsider"},
                        ],
                    },
                ],
            }
        },
    }
    content = scrub_all([doc])[0]["fields"]["description"]["content"]
    assert content[0]["content"][0]["text"] == "@CustomAnnotation\nclass A {}"
    assert content[1]["content"][0]["text"] == "@Inline"
    assert content[1]["content"][1]["text"] == " reviewed by [person]"


def test_non_json_and_unrelated_files_are_ignored(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    shutil.copy(FIXTURES / "jira/cloud_issue_ABC-101.json", raw)
    (raw / "notes.txt").write_text("Priya Testwell")
    anonymise.anonymise_dir(raw, tmp_path / "clean")
    assert sorted(p.name for p in (tmp_path / "clean").iterdir()) == [
        "ABC-101.json",
        "_ingest.json",
    ]


def test_identifier_list_used_by_these_tests_is_not_empty(people):
    assert len(person_identifiers(people)) > 30
