"""Behaviour tests for scripts/szz.py: where defects were probably introduced (F5).

Each test builds a small git repo in a temporary folder, with commit dates set so the
introducing commit is known, then links a defect to its fix commit the way
link_scm.py does in work/scm_links.json.
"""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

import anonymise
import szz

AUTHOR = ("Alice Example", "alice@example.com")
REPORTED = datetime(2026, 2, 1, 9, tzinfo=timezone.utc)


class Repo:
    """A throwaway git repo whose commits get the dates the test gives them."""

    def __init__(self, path: Path):
        self.path = path
        path.mkdir(parents=True)
        self.git("init", "-q", "-b", "main")

    def git(self, *args, date="2026-01-01T09:00:00Z") -> str:
        env = {
            **os.environ,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": AUTHOR[0],
            "GIT_AUTHOR_EMAIL": AUTHOR[1],
            "GIT_COMMITTER_NAME": AUTHOR[0],
            "GIT_COMMITTER_EMAIL": AUTHOR[1],
            "GIT_AUTHOR_DATE": date,
            "GIT_COMMITTER_DATE": date,
        }
        done = subprocess.run(
            ["git", "-C", str(self.path), *args],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        return done.stdout.strip()

    def commit(self, files: dict, date: str, message="change") -> str:
        """Write each file (None deletes it), commit on date, and return the sha."""
        for name, text in files.items():
            target = self.path / name
            if text is None:
                target.unlink()
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "--no-gpg-sign", "-m", message, date=date)
        return self.git("rev-parse", "HEAD")


def lines(*items) -> str:
    return "".join(f"{item}\n" for item in items)


def links_for(fixes: dict) -> dict:
    """Synthetic work/scm_links.json: defect key -> list of (repo, [commit ids])."""
    return {
        "since": "2026-01-01",
        "repos": {
            repo: {"platform": "gitlab"}
            for changes in fixes.values()
            for repo, _ in changes
        },
        "defects": {
            key: {
                "repos": sorted({repo for repo, _ in changes}),
                "changes": [
                    {
                        "repo": repo,
                        "kind": "merge_request",
                        "id": str(n),
                        "commits": shas,
                    }
                    for n, (repo, shas) in enumerate(changes, 1)
                ],
            }
            for key, changes in fixes.items()
        },
    }


@pytest.fixture
def repo(tmp_path) -> Repo:
    return Repo(tmp_path / "clones" / "checkout")


def trace_one(repo: Repo, fix: str, reported=REPORTED, name="group/checkout") -> dict:
    result = szz.trace(
        links_for({"ABC-1": [(name, [fix])]}), {"ABC-1": reported}, {name: repo.path}
    )
    return result


def candidates(result, key="ABC-1") -> list[tuple]:
    return sorted(
        (c["repo"], c["path"], c["commit"])
        for c in result["defects"][key]["candidates"]
    )


# --- Tracing --------------------------------------------------------------------


def test_a_changed_line_is_traced_to_the_commit_that_last_changed_it(repo):
    start = repo.commit(
        {"src/checkout/cart.py": lines("a = 1", "b = 2", "c = 3")},
        "2026-01-01T09:00:00Z",
    )
    fix = repo.commit(
        {"src/checkout/cart.py": lines("a = 1", "b = 20", "c = 3")},
        "2026-02-10T09:00:00Z",
    )
    result = trace_one(repo, fix)
    assert candidates(result) == [("group/checkout", "src/checkout/cart.py", start)]
    assert result["defects"]["ABC-1"]["traced"] is True


def test_a_line_last_changed_after_the_report_is_not_a_candidate(repo):
    repo.commit({"app.py": lines("a = 1", "b = 2")}, "2026-01-01T09:00:00Z")
    repo.commit({"app.py": lines("a = 1", "b = 3")}, "2026-02-05T09:00:00Z")
    fix = repo.commit({"app.py": lines("a = 1", "b = 4")}, "2026-02-10T09:00:00Z")
    result = trace_one(repo, fix)
    assert candidates(result) == []
    assert result["coverage"]["candidates_after_report_dropped"] == 1


def test_whitespace_only_and_comment_only_changes_are_not_blamed(repo):
    repo.commit(
        {"app.py": lines("def f():", "    return 1", "# old note", "x = 1")},
        "2026-01-01T09:00:00Z",
    )
    fix = repo.commit(
        {"app.py": lines("def f():", "        return 1", "# new note", "x = 1")},
        "2026-02-10T09:00:00Z",
    )
    assert candidates(trace_one(repo, fix)) == []


def test_commits_listed_in_the_ignore_revs_file_are_looked_past(repo):
    start = repo.commit({"app.py": lines("a = 'x'", "b = 'y'")}, "2026-01-01T09:00:00Z")
    tidy = repo.commit({"app.py": lines('a = "x"', 'b = "y"')}, "2026-01-10T09:00:00Z")
    repo.commit({".git-blame-ignore-revs": lines(tidy)}, "2026-01-11T09:00:00Z")
    fix = repo.commit({"app.py": lines('a = "x"', 'b = "z"')}, "2026-02-10T09:00:00Z")
    assert candidates(trace_one(repo, fix)) == [("group/checkout", "app.py", start)]


def test_every_changed_line_is_blamed_not_only_the_first_200(repo):
    body = [f"v{n} = {n}" for n in range(300)]
    start = repo.commit({"big.py": lines(*body)}, "2026-01-01T09:00:00Z")
    late = list(body)
    late[249] = "v249 = 'changed before the report'"
    middle = repo.commit({"big.py": lines(*late)}, "2026-01-20T09:00:00Z")
    fix = repo.commit(
        {"big.py": lines(*(f"v{n} = {n} + 1" for n in range(300)))},
        "2026-02-10T09:00:00Z",
    )
    assert candidates(trace_one(repo, fix)) == sorted(
        [("group/checkout", "big.py", start), ("group/checkout", "big.py", middle)]
    )


def test_two_repos_with_the_same_last_name_are_kept_apart(tmp_path):
    one, two = Repo(tmp_path / "a" / "api"), Repo(tmp_path / "b" / "api")
    start_one = one.commit({"one.py": lines("x = 1")}, "2026-01-01T09:00:00Z")
    fix_one = one.commit({"one.py": lines("x = 2")}, "2026-02-10T09:00:00Z")
    start_two = two.commit({"two.py": lines("y = 1")}, "2026-01-02T09:00:00Z")
    fix_two = two.commit({"two.py": lines("y = 2")}, "2026-02-10T09:00:00Z")
    result = szz.trace(
        links_for({"ABC-1": [("team-a/api", [fix_one]), ("team-b/api", [fix_two])]}),
        {"ABC-1": REPORTED},
        {"team-a/api": one.path, "team-b/api": two.path},
    )
    assert candidates(result) == [
        ("team-a/api", "one.py", start_one),
        ("team-b/api", "two.py", start_two),
    ]


def test_a_fix_that_only_adds_lines_has_nothing_to_blame_and_is_counted(repo):
    repo.commit({"app.py": lines("a = 1")}, "2026-01-01T09:00:00Z")
    fix = repo.commit({"app.py": lines("a = 1", "check(a)")}, "2026-02-10T09:00:00Z")
    result = trace_one(repo, fix)
    assert result["defects"]["ABC-1"]["traced"] is False
    assert result["coverage"]["commits_with_nothing_to_blame"] == 1


def test_a_commit_missing_from_the_clone_is_counted_not_silent(repo):
    repo.commit({"app.py": lines("a = 1")}, "2026-01-01T09:00:00Z")
    result = trace_one(repo, "f" * 40)
    assert result["coverage"]["commits_not_in_clone"] == 1
    assert result["defects"]["ABC-1"]["traced"] is False


def test_a_commit_id_that_is_not_a_sha_is_never_passed_to_git(repo, tmp_path):
    repo.commit({"app.py": lines("a = 1")}, "2026-01-01T09:00:00Z")
    planted = tmp_path / "planted"
    result = trace_one(repo, f"--output={planted}")
    assert not planted.exists()
    assert result["coverage"]["commits_not_in_clone"] == 1


def test_a_merge_commit_is_skipped_and_counted(repo):
    repo.commit({"app.py": lines("a = 1")}, "2026-01-01T09:00:00Z")
    repo.git("checkout", "-q", "-b", "side")
    repo.commit({"side.py": lines("s = 1")}, "2026-01-02T09:00:00Z")
    repo.git("checkout", "-q", "main")
    repo.commit({"app.py": lines("a = 2")}, "2026-01-03T09:00:00Z")
    repo.git("merge", "-q", "--no-ff", "--no-edit", "side", date="2026-02-10T09:00:00Z")
    merge = repo.git("rev-parse", "HEAD")
    result = trace_one(repo, merge)
    assert result["coverage"]["merge_commits_skipped"] == 1
    assert candidates(result) == []


def test_a_linked_repo_with_no_clone_is_listed(repo):
    fix = repo.commit({"app.py": lines("a = 1")}, "2026-01-01T09:00:00Z")
    result = szz.trace(
        links_for({"ABC-1": [("group/elsewhere", [fix])]}),
        {"ABC-1": REPORTED},
        {"group/checkout": repo.path},
    )
    assert result["coverage"]["repos_without_clone"] == ["group/elsewhere"]
    assert result["defects"]["ABC-1"]["traced"] is False


def test_a_renamed_file_is_blamed_under_its_old_path(repo):
    start = repo.commit(
        {"old/name.py": lines("a = 1", "b = 2", "c = 3", "d = 4")},
        "2026-01-01T09:00:00Z",
    )
    fix = repo.commit(
        {"old/name.py": None, "new/name.py": lines("a = 1", "b = 9", "c = 3", "d = 4")},
        "2026-02-10T09:00:00Z",
    )
    assert candidates(trace_one(repo, fix)) == [
        ("group/checkout", "old/name.py", start)
    ]


def test_a_removed_sql_comment_does_not_hide_the_lines_after_it(repo):
    start = repo.commit(
        {"q.sql": lines("-- note", "select 1;", "select 2;")}, "2026-01-01T09:00:00Z"
    )
    fix = repo.commit({"q.sql": lines("select 3;")}, "2026-02-10T09:00:00Z")
    assert candidates(trace_one(repo, fix)) == [("group/checkout", "q.sql", start)]


def test_a_file_that_is_not_utf8_is_traced_without_crashing(repo):
    target = repo.path / "legacy.txt"
    target.write_bytes("caf\xe9 = 1\nb = 2\n".encode("latin-1"))
    start = repo.commit({}, "2026-01-01T09:00:00Z")
    target.write_bytes("caf\xe9 = 2\nb = 2\n".encode("latin-1"))
    fix = repo.commit({}, "2026-02-10T09:00:00Z")
    assert candidates(trace_one(repo, fix)) == [("group/checkout", "legacy.txt", start)]


@pytest.mark.parametrize("name", ["my dir/a b.py", 'we"ird/a.py', "back\\slash/a.py"])
def test_paths_git_quotes_or_pads_are_still_traced(repo, name):
    start = repo.commit({name: lines("a = 1")}, "2026-01-01T09:00:00Z")
    fix = repo.commit({name: lines("a = 2")}, "2026-02-10T09:00:00Z")
    result = trace_one(repo, fix)
    assert candidates(result) == [("group/checkout", name, start)]
    assert result["coverage"]["blame_failures"] == 0


def test_people_named_in_paths_are_masked_like_the_rest_of_the_run(tmp_path):
    clone = Repo(tmp_path / "clones" / "tool")
    clone.commit(
        {
            "notes/robin.q/plan.py": lines("a = 1"),
            "docs/alice-example/x.py": lines("b = 1"),
            "src/checkout/y.py": lines("c = 1"),
        },
        "2026-01-01T09:00:00Z",
    )
    fix = clone.commit(
        {
            "notes/robin.q/plan.py": lines("a = 2"),
            "docs/alice-example/x.py": lines("b = 2"),
            "src/checkout/y.py": lines("c = 2"),
        },
        "2026-02-10T09:00:00Z",
    )
    name = "[person]/checkout-tool"
    result = szz.trace(
        links_for({"ABC-1": [(name, [fix])]}),
        {"ABC-1": REPORTED},
        {name: clone.path},
        people=["robin.q"],
    )
    paths = sorted(c["path"] for c in result["defects"]["ABC-1"]["candidates"])
    assert paths == [
        "docs/[person]/x.py",
        "notes/[person]/plan.py",
        "src/checkout/y.py",
    ]


def test_a_defect_with_no_report_date_is_counted_apart(repo):
    repo.commit({"app.py": lines("a = 1")}, "2026-01-01T09:00:00Z")
    fix = repo.commit({"app.py": lines("a = 2")}, "2026-02-10T09:00:00Z")
    result = szz.trace(
        links_for({"ABC-1": [("group/checkout", [fix])]}),
        {},
        {"group/checkout": repo.path},
    )
    assert result["coverage"]["defects_without_report_date"] == 1
    assert result["coverage"]["candidates_after_report_dropped"] == 0
    assert result["defects"]["ABC-1"]["traced"] is False


# --- Publishing -------------------------------------------------------------------


def five_defects(repo: Repo, directory="src/checkout", count=5) -> tuple[dict, dict]:
    """count defects, each fixed by changing a line first written on 2026-01-01."""
    files = {f"{directory}/f{n}.py": lines(f"x = {n}") for n in range(count)}
    repo.commit(files, "2026-01-01T09:00:00Z")
    fixes = {}
    for n in range(count):
        sha = repo.commit(
            {f"{directory}/f{n}.py": lines(f"x = {n + 100}")},
            f"2026-02-{10 + n}T09:00:00Z",
        )
        fixes[f"ABC-{n + 1}"] = [("group/checkout", [sha])]
    return links_for(fixes), {key: REPORTED for key in fixes}


def test_directories_count_distinct_defects_and_are_labelled_an_estimate(
    repo, tmp_path
):
    links, reported = five_defects(repo)
    result = szz.trace(links, reported, {"group/checkout": repo.path})
    szz.write_szz(result, tmp_path / "out")
    doc = json.loads((tmp_path / "out/szz.json").read_text())
    assert doc["directories"] == [
        {"repo": "group/checkout", "directory": "src/checkout", "defects": 5}
    ]
    assert "estimate" in doc["settings"]["note"].lower()
    md = (tmp_path / "out/szz.md").read_text()
    assert "estimate" in md.lower() and "| group/checkout | src/checkout | 5 |" in md


def test_the_median_days_from_last_change_to_report_is_published_for_enough_defects(
    repo, tmp_path
):
    links, reported = five_defects(repo)
    szz.write_szz(
        szz.trace(links, reported, {"group/checkout": repo.path}), tmp_path / "out"
    )
    doc = json.loads((tmp_path / "out/szz.json").read_text())
    assert doc["summary"]["median_days_last_changed_to_reported"] == 31.0


def test_small_groups_and_the_median_of_too_few_defects_are_suppressed(repo, tmp_path):
    links, reported = five_defects(repo, count=4)
    szz.write_szz(
        szz.trace(links, reported, {"group/checkout": repo.path}), tmp_path / "out"
    )
    doc = json.loads((tmp_path / "out/szz.json").read_text())
    assert doc["directories"] == []
    assert doc["suppressed_directories"] == 1
    assert (
        doc["summary"]["median_days_last_changed_to_reported"]
        == doc["suppressed_marker"]
    )
    assert "4" not in (tmp_path / "out/szz.csv").read_text().split("\n", 1)[1]


def test_a_threshold_below_five_is_refused(repo, tmp_path):
    links, reported = five_defects(repo)
    result = szz.trace(links, reported, {"group/checkout": repo.path})
    with pytest.raises(ValueError):
        szz.write_szz(result, tmp_path / "out", min_group_size=4)
    assert not (tmp_path / "out").exists()


def test_no_author_or_ticket_key_reaches_the_outputs(repo, tmp_path):
    links, reported = five_defects(repo)
    szz.write_szz(
        szz.trace(links, reported, {"group/checkout": repo.path}), tmp_path / "out"
    )
    for path in (tmp_path / "out").iterdir():
        text = path.read_text()
        assert AUTHOR[0] not in text and AUTHOR[1] not in text and "Alice" not in text
        assert "ABC-" not in text


# --- Command line ------------------------------------------------------------------


def write_clean(tmp_path, keys) -> Path:
    raw, clean = tmp_path / "raw", tmp_path / "clean"
    raw.mkdir()
    for key in keys:
        issue = {
            "key": key,
            "fields": {"summary": "s", "created": "2026-02-01T09:00:00.000+0000"},
        }
        (raw / f"{key}.json").write_text(json.dumps(issue))
    anonymise.anonymise_dir(raw, clean)
    return clean


def test_the_command_line_writes_working_data_to_work_and_counts_to_out(repo, tmp_path):
    links, _ = five_defects(repo)
    (tmp_path / "links.json").write_text(json.dumps(links))
    clean = write_clean(tmp_path, links["defects"])
    code = szz.main(
        [
            "--links",
            str(tmp_path / "links.json"),
            "--issues",
            str(clean),
            "--clone",
            f"group/checkout={repo.path}",
            "--work",
            str(tmp_path / "work/szz.json"),
            "--out",
            str(tmp_path / "out"),
        ]
    )
    assert code == 0
    work = json.loads((tmp_path / "work/szz.json").read_text())
    assert set(work["defects"]) == set(links["defects"])
    assert {p.name for p in (tmp_path / "out").iterdir()} == {
        "szz.json",
        "szz.csv",
        "szz.md",
    }
    for text in [p.read_text() for p in (tmp_path / "work").iterdir()]:
        assert AUTHOR[0] not in text and AUTHOR[1] not in text


@pytest.mark.parametrize(
    "clone",
    ["no-equals-sign", "group/unknown={repo}", "group/checkout={missing}"],
    ids=["malformed", "unknown repo", "missing folder"],
)
def test_the_command_line_refuses_a_bad_clone_mapping(repo, tmp_path, capsys, clone):
    links, _ = five_defects(repo)
    (tmp_path / "links.json").write_text(json.dumps(links))
    clean = write_clean(tmp_path, links["defects"])
    value = clone.format(repo=repo.path, missing=tmp_path / "nowhere")
    code = szz.main(
        [
            "--links",
            str(tmp_path / "links.json"),
            "--issues",
            str(clean),
            "--clone",
            value,
            "--work",
            str(tmp_path / "work/szz.json"),
            "--out",
            str(tmp_path / "out"),
        ]
    )
    assert code == 2 and "error:" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_the_command_line_needs_the_config_to_mask_a_personal_repo(tmp_path, capsys):
    clone = Repo(tmp_path / "clones" / "tool")
    fix = clone.commit({"a.py": lines("a = 1")}, "2026-01-01T09:00:00Z")
    links = links_for({"ABC-1": [("[person]/checkout-tool", [fix])]})
    (tmp_path / "links.json").write_text(json.dumps(links))
    clean = write_clean(tmp_path, links["defects"])
    code = szz.main(
        [
            "--links",
            str(tmp_path / "links.json"),
            "--issues",
            str(clean),
            "--clone",
            f"[person]/checkout-tool={clone.path}",
            "--out",
            str(tmp_path / "out"),
        ]
    )
    assert code == 2 and "--config" in capsys.readouterr().err


def test_the_command_line_refuses_links_it_cannot_read(tmp_path, capsys):
    (tmp_path / "links.json").write_text(json.dumps({"since": "2026-01-01"}))
    code = szz.main(
        ["--links", str(tmp_path / "links.json"), "--out", str(tmp_path / "out")]
    )
    assert code == 2 and "error:" in capsys.readouterr().err


def test_the_command_line_refuses_unanonymised_issues(repo, tmp_path, capsys):
    links, _ = five_defects(repo)
    (tmp_path / "links.json").write_text(json.dumps(links))
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "ABC-1.json").write_text(json.dumps({"key": "ABC-1", "fields": {}}))
    code = szz.main(
        [
            "--links",
            str(tmp_path / "links.json"),
            "--issues",
            str(raw),
            "--clone",
            f"group/checkout={repo.path}",
            "--out",
            str(tmp_path / "out"),
        ]
    )
    assert code == 2 and "anonymise" in capsys.readouterr().err
