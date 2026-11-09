"""Behaviour tests for scripts/scm_fetch.py, the source control REST fallback runner (F4).

No test touches the network: fetching is checked with a recorded GitLab transport, and
the command line only up to the point where it would need credentials.
"""

import json

import anonymise
import scm_config
import scm_fetch
import scm_gitlab
from conftest import load_fixture
from test_scm_gitlab import Recorded

CONFIG = ("repos:\n  - platform: gitlab\n    url: https://gitlab.example.com\n    project: group/checkout-service\n"
          "  - platform: azure\n    org: example-org\n    project: Accounts\n    repo: accounts-api\n")


def clean_with_defects(tmp_path):
    raw = tmp_path / "jira_raw"
    raw.mkdir()
    for name in ["jira/cloud_issue_ABC-101.json", "jira/dc_issue_ABC-102.json"]:
        (raw / name.split("/")[1]).write_text(json.dumps(load_fixture(name)))
    anonymise.anonymise_dir(raw, tmp_path / "clean")
    return tmp_path / "clean"


def test_print_since_gives_the_earliest_defect_date(tmp_path, capsys):
    assert scm_fetch.main(["--print-since", "--issues", str(clean_with_defects(tmp_path))]) == 0
    assert capsys.readouterr().out.strip() == "2026-03-04"


def test_ready_repos_are_fetched_and_planned_ones_skipped(tmp_path):
    (tmp_path / "scm.yaml").write_text(CONFIG)
    fixture = load_fixture("recorded/gitlab_rest.json")
    client = scm_gitlab.GitLabClient(fixture["base_url"], "t", transport=Recorded(fixture), sleep=lambda s: None)
    results = scm_fetch.fetch_all(scm_config.load_config(tmp_path / "scm.yaml"), "2026-01-01",
                                  tmp_path / "raw", client_for=lambda repo: client)
    assert results == [{"repo": "group/checkout-service", "changes": 4, "files_written": 15},
                       {"repo": "accounts-api", "skipped": "azure isn't ready yet"}]


def test_a_missing_token_is_named_and_nothing_is_fetched(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    (tmp_path / "scm.yaml").write_text(CONFIG)
    code = scm_fetch.main(["--config", str(tmp_path / "scm.yaml"), "--since", "2026-01-01", "--out", str(tmp_path / "raw")])
    assert code == 2 and "GITLAB_TOKEN" in capsys.readouterr().err
    assert not (tmp_path / "raw").exists()


def test_without_since_or_defects_the_window_is_refused(tmp_path, capsys):
    (tmp_path / "scm.yaml").write_text(CONFIG)
    (tmp_path / "clean").mkdir()
    code = scm_fetch.main(["--config", str(tmp_path / "scm.yaml"), "--issues", str(tmp_path / "clean"),
                           "--out", str(tmp_path / "raw")])
    assert code == 2 and "--since" in capsys.readouterr().err
