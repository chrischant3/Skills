"""Behaviour tests for scripts/link_scm.py: linking defects to merged changes (F4, known problem 5).

The run holds two synthetic defects (ABC-101, ABC-102) and the GitLab MCP fixture, all
through anonymise.py first. Keys are found in an MR title (ABC-101), a commit message on
the second page of an MR's commits (ABC-102) and a lower-case branch name (ABC-102). One
MR has no key, and one was merged before the run's window.
"""

import json
import re
import shutil

import pytest

import anonymise
import link_scm
import scm_config
from conftest import FIXTURES, ROOT, all_text_under, load_fixture, person_identifiers

GITLAB = {"platform": "gitlab", "url": "https://gitlab.example.com", "project": "group/checkout-service", "team": "Checkout"}


def config(*repos, default_key_pattern=None):
    return {"min_group_size": None, "default_key_pattern": default_key_pattern, "repos": list(repos or [GITLAB])}


def make_run(tmp_path, edit=None):
    """Write raw Jira and GitLab MCP data, optionally edit one raw file, then anonymise into clean/."""
    raw = tmp_path / "raw"
    shutil.copytree(FIXTURES / "scm/gitlab_mcp", raw)
    for name in ["jira/cloud_issue_ABC-101.json", "jira/dc_issue_ABC-102.json"]:
        (raw / name.split("/")[1]).write_text(json.dumps(load_fixture(name)))
    if edit:
        edit(raw)
    anonymise.anonymise_dir(raw, tmp_path / "clean")
    return tmp_path / "clean"


def retitle_mr16(title):
    def edit(raw):
        path = raw / "gitlab-mrs-2.json"
        doc = json.loads(path.read_text())
        mrs = json.loads(doc["content"][0]["text"])
        next(m for m in mrs if m["iid"] == 16)["title"] = title
        doc["content"][0]["text"] = json.dumps(mrs)
        path.write_text(json.dumps(doc))
    return edit


# --- per defect -------------------------------------------------------------------------------

def test_each_linked_defect_lists_its_repos_changes_commits_and_files(tmp_path):
    links = link_scm.link(config(), make_run(tmp_path))
    abc101, abc102 = links["defects"]["ABC-101"], links["defects"]["ABC-102"]
    assert abc101["repos"] == ["group/checkout-service"]
    assert [c["id"] for c in abc101["changes"]] == ["12"]
    assert abc101["commits"] == ["1" * 40, "2" * 40]
    assert abc101["files"] == [{"repo": "group/checkout-service", "path": "src/checkout/address.py"},
                               {"repo": "group/checkout-service", "path": "tests/checkout/test_address.py"}]
    assert [c["id"] for c in abc102["changes"]] == ["14", "15"]
    assert abc102["commits"] == ["3" * 40, "4" * 40, "5" * 40]
    assert [f["path"] for f in abc102["files"]] == ["services/accounts/session_filter.py", "docs/sessions.md"]


def test_per_repo_coverage_counts_changes_scanned_and_linked_and_defects_linked(tmp_path):
    links = link_scm.link(config(), make_run(tmp_path))
    assert links["repos"]["group/checkout-service"] == {"platform": "gitlab", "team": "Checkout", "changes_scanned": 4,
                                                        "changes_linked": 3, "defects_linked": 2}
    assert (links["defects_total"], links["defects_linked"]) == (2, 2)


def test_the_window_starts_at_the_earliest_defect_in_the_run(tmp_path):
    links = link_scm.link(config(), make_run(tmp_path))
    assert links["since"] == "2026-03-04"


def test_an_explicit_since_narrows_the_window(tmp_path):
    links = link_scm.link(config(), make_run(tmp_path), since="2026-04-05")
    assert links["repos"]["group/checkout-service"]["changes_scanned"] == 2
    assert list(links["defects"]) == ["ABC-102"]


def test_a_key_for_an_issue_outside_the_run_is_not_a_link(tmp_path):
    links = link_scm.link(config(), make_run(tmp_path, retitle_mr16("ABC-999 unrelated fix")))
    assert "ABC-999" not in links["defects"] and links["repos"]["group/checkout-service"]["changes_linked"] == 3


def test_a_repo_can_declare_its_own_key_pattern(tmp_path):
    clean = make_run(tmp_path, retitle_mr16("ABC_101 follow-up"))
    standard = link_scm.link(config(), clean)
    custom = link_scm.link(config({**GITLAB, "key_pattern": r"ABC[-_ ]?\d+"}), clean)
    assert [c["id"] for c in standard["defects"]["ABC-101"]["changes"]] == ["12"]
    assert [c["id"] for c in custom["defects"]["ABC-101"]["changes"]] == ["12", "16"]


def test_the_config_default_key_pattern_applies_to_repos_without_their_own(tmp_path):
    clean = make_run(tmp_path, retitle_mr16("ABC_101 follow-up"))
    links = link_scm.link(config(default_key_pattern=r"ABC[-_ ]?\d+"), clean)
    assert [c["id"] for c in links["defects"]["ABC-101"]["changes"]] == ["12", "16"]


def test_azure_devops_repos_are_reported_as_not_ready_and_skipped(tmp_path):
    links = link_scm.link(scm_config.load_config(ROOT / "scm.yaml"), make_run(tmp_path))
    assert links["skipped"] == [{"repo": "accounts-api", "platform": "azure", "reason": "not ready yet"}]
    assert list(links["repos"]) == ["group/checkout-service"]


def test_two_repos_with_the_same_name_are_refused(tmp_path):
    with pytest.raises(ValueError, match="same name"):
        link_scm.link(config(GITLAB, {**GITLAB, "url": "https://other.example.com"}), make_run(tmp_path))


def test_unanonymised_source_control_data_is_refused(tmp_path):
    clean = make_run(tmp_path)
    shutil.copy(FIXTURES / "scm/gitlab_mcp/gitlab-mrs-1.json", clean / "gitlab-mrs-9.json")
    with pytest.raises(ValueError, match="anonymise"):
        link_scm.link(config(), clean)


def test_no_person_reaches_the_links(tmp_path, people):
    text = json.dumps(link_scm.link(config(), make_run(tmp_path)))
    assert [i for i in person_identifiers(people) if re.search(rf"(?<!\w){re.escape(i)}(?!\w)", text, re.I)] == []
    assert "[person]" not in text


# --- reported coverage goes through suppress.py --------------------------------------------------

def numbers_in(out):
    found = []
    for path in out.iterdir():
        text = re.sub(r"\d+ groups? suppressed|fewer than \d+ defects", "", path.read_text())
        text = re.sub(r"\d{4}-\d{2}-\d{2}", "", text)
        found += [int(n) for n in re.findall(r"(?<![\w.-])\d+(?![\w.-])", text)]
    return found


def synthetic_links(per_repo: dict, multiple: int = 0, changes=40):
    defects, n = {}, 0
    for repo, count in per_repo.items():
        for _ in range(count):
            n += 1
            defects[f"ABC-{n}"] = {"repos": [repo], "changes": [], "commits": [], "files": []}
    for _ in range(multiple):
        n += 1
        defects[f"ABC-{n}"] = {"repos": list(per_repo), "changes": [], "commits": [], "files": []}
    repos = {r: {"platform": "gitlab", "team": None, "changes_scanned": changes, "changes_linked": c + multiple,
                 "defects_linked": c + multiple} for r, c in per_repo.items()}
    return {"since": "2026-01-01", "defects_total": n + 10, "defects_linked": n, "repos": repos, "skipped": [],
            "defects": defects}


@pytest.mark.parametrize("k", [5, 6, 8])
def test_no_count_below_the_threshold_reaches_any_coverage_output(tmp_path, k):
    link_scm.write_coverage(synthetic_links({"group/a": 9, "group/b": 2, "group/c": 7}, multiple=1, changes=3),
                            tmp_path / "out", min_group_size=k)
    assert all(n == 0 or n >= k for n in numbers_in(tmp_path / "out"))


def test_a_small_repo_cannot_be_worked_out_from_the_totals(tmp_path):
    link_scm.write_coverage(synthetic_links({"group/a": 9, "group/b": 2}), tmp_path / "out", min_group_size=5)
    data = json.loads((tmp_path / "out/scm_coverage.json").read_text())
    rows = {r["repo"]: r["defects_linked"] for r in data["repos"]}
    assert rows["group/b"] == "suppressed"
    assert "suppressed" in (data["summary"]["defects_linked"], rows["group/a"])
    assert data["summary"]["defect_link_rate"] == "suppressed" or data["summary"]["defects_linked"] != "suppressed"


def test_coverage_outputs_hold_no_ticket_keys_or_people(tmp_path, people):
    clean = make_run(tmp_path)
    link_scm.write_coverage(link_scm.link(config(), clean), tmp_path / "out")
    text = all_text_under(tmp_path / "out")
    assert not re.search(r"\bABC-\d+\b", text)
    assert [i for i in person_identifiers(people) if re.search(rf"(?<!\w){re.escape(i)}(?!\w)", text, re.I)] == []
    assert {p.name for p in (tmp_path / "out").iterdir()} == {"scm_coverage.json", "scm_coverage.csv", "scm_coverage.md"}


def test_the_command_line_writes_links_to_work_and_coverage_to_out(tmp_path):
    clean = make_run(tmp_path)
    (tmp_path / "scm.yaml").write_text("repos:\n  - platform: gitlab\n    url: https://gitlab.example.com\n"
                                      "    project: group/checkout-service\n    team: Checkout\n")
    code = link_scm.main(["--config", str(tmp_path / "scm.yaml"), "--issues", str(clean),
                          "--work", str(tmp_path / "work/scm_links.json"), "--out", str(tmp_path / "out")])
    assert code == 0
    assert json.loads((tmp_path / "work/scm_links.json").read_text())["defects_linked"] == 2
    assert (tmp_path / "out/scm_coverage.md").exists()


def test_the_command_line_refuses_a_threshold_below_five(tmp_path, capsys):
    clean = make_run(tmp_path)
    (tmp_path / "scm.yaml").write_text("repos:\n  - platform: gitlab\n    url: https://gitlab.example.com\n"
                                      "    project: group/checkout-service\n")
    code = link_scm.main(["--config", str(tmp_path / "scm.yaml"), "--issues", str(clean), "--work",
                          str(tmp_path / "work/l.json"), "--out", str(tmp_path / "out"), "--min-group-size", "4"])
    assert code == 2 and "at least 5" in capsys.readouterr().err and not (tmp_path / "out").exists()
