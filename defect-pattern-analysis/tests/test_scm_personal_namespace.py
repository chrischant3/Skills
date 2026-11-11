"""Behaviour tests: a repo in someone's personal namespace never puts their username in any output.

The fixture repo is robin.q/checkout-tool. Robin Quill owns it but appears nowhere else,
so only the namespace rule can remove the name. A repo is personal if GitLab says its
namespace kind is "user", if scm.yaml says namespace: user, or if neither says it is a
group (the safe default, for MCP results that carry no namespace).
"""

import json
import shutil

import pytest

import anonymise
import link_scm
import scm_config
import scm_fetch
import scm_gitlab
from conftest import FIXTURES, all_text_under, load_fixture
from test_scm_gitlab import Recorded

PERSONAL = {
    "platform": "gitlab",
    "url": "https://gitlab.example.com",
    "project": "robin.q/checkout-tool",
}
GROUP = {
    "platform": "gitlab",
    "url": "https://gitlab.example.com",
    "project": "group/checkout-service",
}
REDACTED = "[person]/checkout-tool"
OWNER = ["robin.q", "Robin", "Quill"]


def config(*repos):
    return {"min_group_size": None, "default_key_pattern": None, "repos": list(repos)}


def jira_raw(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for name in ["jira/cloud_issue_ABC-101.json", "jira/dc_issue_ABC-102.json"]:
        (raw / name.split("/")[1]).write_text(json.dumps(load_fixture(name)))
    return raw


def rest_raw(tmp_path, repo, fixture="recorded/gitlab_rest_personal.json"):
    raw = jira_raw(tmp_path)
    recording = load_fixture(fixture)
    client = scm_gitlab.GitLabClient(
        recording["base_url"], "t", transport=Recorded(recording), sleep=lambda s: None
    )
    summary = scm_gitlab.ADAPTER.fetch(repo, "2026-01-01", raw, client)
    return raw, summary


def mcp_raw(tmp_path):
    raw = jira_raw(tmp_path)
    for path in (FIXTURES / "scm/gitlab_mcp_personal").iterdir():
        shutil.copy(path, raw)
    return raw


def run(tmp_path, raw, cfg):
    anonymise.anonymise_dir(raw, tmp_path / "clean", scm_config=cfg)
    links = link_scm.link(cfg, tmp_path / "clean")
    (tmp_path / "work").mkdir()
    (tmp_path / "work/scm_links.json").write_text(json.dumps(links))
    link_scm.write_coverage(links, tmp_path / "out")
    return links


def assert_owner_absent(tmp_path):
    for folder in ["clean", "work", "out"]:
        names = " ".join(p.name for p in (tmp_path / folder).rglob("*"))
        text = all_text_under(tmp_path / folder) + names
        assert [o for o in OWNER if o.lower() in text.lower()] == [], folder


@pytest.mark.parametrize("namespace", [None, "user", "group"])
def test_gitlab_saying_the_namespace_is_a_user_redacts_the_owner_whatever_the_config_says(
    tmp_path, namespace
):
    repo = {**PERSONAL, **({"namespace": namespace} if namespace else {})}
    raw, summary = rest_raw(tmp_path, repo)
    links = run(tmp_path, raw, config(repo))
    assert summary["repo"] == REDACTED
    assert list(links["repos"]) == [REDACTED] and links["defects"]["ABC-101"][
        "repos"
    ] == [REDACTED]
    assert REDACTED in (tmp_path / "out/scm_coverage.md").read_text()
    assert_owner_absent(tmp_path)


@pytest.mark.parametrize("namespace", ["user", None])
def test_without_namespace_data_a_repo_is_personal_unless_config_marks_it_a_group(
    tmp_path, namespace
):
    repo = {**PERSONAL, **({"namespace": namespace} if namespace else {})}
    links = run(tmp_path, mcp_raw(tmp_path), config(repo))
    assert list(links["repos"]) == [REDACTED]
    assert [c["id"] for c in links["defects"]["ABC-101"]["changes"]] == ["3"]
    assert_owner_absent(tmp_path)


def test_a_group_repo_with_no_namespace_data_is_treated_as_personal_by_default(
    tmp_path,
):
    raw = jira_raw(tmp_path)
    for path in (FIXTURES / "scm/gitlab_mcp").iterdir():
        shutil.copy(path, raw)
    links = run(tmp_path, raw, config(GROUP))
    assert (
        list(links["repos"]) == ["[person]/checkout-service"]
        and links["defects_linked"] == 2
    )


def test_a_group_namespace_keeps_its_name_when_gitlab_or_config_says_so(tmp_path):
    raw, summary = rest_raw(tmp_path / "a", GROUP, "recorded/gitlab_rest.json")
    assert summary["repo"] == "group/checkout-service"
    assert list(run(tmp_path / "a", raw, config(GROUP))["repos"]) == [
        "group/checkout-service"
    ]
    raw = jira_raw(tmp_path / "b")
    for path in (FIXTURES / "scm/gitlab_mcp").iterdir():
        shutil.copy(path, raw)
    marked = {**GROUP, "namespace": "group"}
    assert list(run(tmp_path / "b", raw, config(marked))["repos"]) == [
        "group/checkout-service"
    ]


def test_source_control_data_is_not_anonymised_without_the_config(tmp_path):
    with pytest.raises(ValueError, match="scm.yaml"):
        anonymise.anonymise_dir(mcp_raw(tmp_path), tmp_path / "clean")
    assert not (tmp_path / "clean").exists()


def test_the_anonymise_command_takes_the_config(tmp_path, capsys):
    raw = mcp_raw(tmp_path)
    (tmp_path / "scm.yaml").write_text(
        "repos:\n  - platform: gitlab\n    url: https://gitlab.example.com\n"
        "    project: robin.q/checkout-tool\n"
    )
    assert anonymise.main([str(raw), str(tmp_path / "clean")]) == 2
    assert "--scm-config" in capsys.readouterr().err
    assert (
        anonymise.main(
            [
                str(raw),
                str(tmp_path / "clean"),
                "--scm-config",
                str(tmp_path / "scm.yaml"),
            ]
        )
        == 0
    )
    assert "robin.q" not in all_text_under(tmp_path / "clean")


def test_the_fetch_command_never_prints_the_owner(tmp_path, capsys):
    recording = load_fixture("recorded/gitlab_rest_personal.json")
    client = scm_gitlab.GitLabClient(
        recording["base_url"], "t", transport=Recorded(recording), sleep=lambda s: None
    )
    results = scm_fetch.fetch_all(
        config(PERSONAL), "2026-01-01", tmp_path / "raw", client_for=lambda repo: client
    )
    assert results[0]["repo"] == REDACTED


@pytest.mark.parametrize("value", ["team", "'personal'", "1"])
def test_an_unknown_namespace_kind_in_config_is_refused_naming_the_line(
    tmp_path, value
):
    path = tmp_path / "scm.yaml"
    path.write_text(
        "repos:\n  - platform: gitlab\n    url: https://g.example.com\n    project: g/p\n"
        f"    namespace: {value}\n"
    )
    with pytest.raises(ValueError, match="line 5: namespace must be"):
        scm_config.load_config(path)
