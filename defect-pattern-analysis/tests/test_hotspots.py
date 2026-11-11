"""Behaviour tests for scripts/hotspots.py: fix hotspots by directory (F4 output, F7).

The run is the 36-defect pipeline fixture plus tests/fixtures/pipeline_scm, which links
24 of them to GitLab merge requests (a group repo and a repo in a personal namespace)
and Azure DevOps pull requests, all through anonymise.py and link_scm.py first.
Planned defects per directory at depth 2, before suppression at 5:
  group/checkout-service   src/checkout 9, tests/checkout 8, src/payments 3, docs 1
  Accounts/accounts-api    src/Accounts 8, tests/Accounts.Tests 6, (root) 5, build 2
  robin.q/checkout-tool    notes/robin.q 5, shown as [person]/checkout-tool and notes/[person]

The golden files in tests/golden_hotspots/ are the expected outputs. To regenerate them
after an intended change, run with UPDATE_GOLDEN=1 and review the diff.
"""

import csv
import json
import os
import re
import shutil
from pathlib import Path

import pytest

import anonymise
import hotspots
import link_scm
import scm_config
from conftest import FIXTURES, all_text_under, person_identifiers

GOLDEN = Path(__file__).resolve().parent / "golden_hotspots"
SCM = FIXTURES / "pipeline_scm"
OWNER = ["robin.q", "Robin", "Quill", "robin.quill"]


def run(tmp_path, depth=None, min_group_size=None) -> Path:
    raw, clean, work, out = (tmp_path / d for d in ("raw", "clean", "work", "out"))
    shutil.copytree(FIXTURES / "pipeline/raw", raw)
    for path in SCM.glob("*.json"):
        shutil.copy(path, raw)
    config = scm_config.load_config(SCM / "scm.yaml")
    anonymise.anonymise_dir(raw, clean, scm_config=config)
    links = link_scm.link(config, clean)
    work.mkdir()
    (work / "scm_links.json").write_text(json.dumps(links))
    hotspots.write_hotspots(
        links, out, **({"depth": depth} if depth else {}), min_group_size=min_group_size
    )
    return out


def rows(out) -> dict:
    data = json.loads((out / "hotspots.json").read_text())
    return {(r["repo"], r["directory"]): r["defects"] for r in data["directories"]}


def links_for(defect_files: dict, platform="gitlab") -> dict:
    """Synthetic links: defect key -> list of (repo, path)."""
    defects = {
        k: {
            "repos": sorted({r for r, _ in files}),
            "changes": [],
            "commits": [],
            "files": [{"repo": r, "path": p} for r, p in files],
        }
        for k, files in defect_files.items()
    }
    repos = {
        r: {
            "platform": platform,
            "team": None,
            "changes_scanned": 50,
            "changes_linked": 10,
            "defects_linked": 10,
        }
        for d in defects.values()
        for r in d["repos"]
    }
    return {
        "since": "2026-01-01",
        "defects_total": len(defects),
        "defects_linked": len(defects),
        "repos": repos,
        "skipped": [],
        "defects": defects,
    }


# --- the counting rule -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path,depth,expected",
    [
        ("src/checkout/address.py", 2, "src/checkout"),
        ("src/checkout/deep/inner/x.py", 2, "src/checkout"),
        ("src/a.py", 2, "src"),
        ("README.md", 2, "(root)"),
        ("/src/Accounts/Session/X.cs", 1, "src"),
        ("a/b/c/d.py", 3, "a/b/c"),
    ],
)
def test_a_file_belongs_to_its_directory_cut_to_the_depth(path, depth, expected):
    assert hotspots.directory_of(path, depth) == expected


def test_a_defect_counts_once_per_directory_however_many_files_it_touched_there(
    tmp_path,
):
    files = {
        f"ABC-{n}": [("group/a", "src/x/one.py"), ("group/a", "tests/x/test_one.py")]
        for n in range(1, 6)
    }
    files["ABC-1"] += [("group/a", f"src/x/generated/f{n}.py") for n in range(40)]
    hotspots.write_hotspots(links_for(files), tmp_path / "out")
    assert rows(tmp_path / "out") == {
        ("group/a", "src/x"): 5,
        ("group/a", "tests/x"): 5,
    }


def test_a_defect_whose_fix_touched_several_directories_counts_in_each(tmp_path):
    files = {
        f"ABC-{n}": [("group/a", "src/a/x.py"), ("group/a", "src/b/y.py")]
        for n in range(1, 7)
    }
    hotspots.write_hotspots(links_for(files), tmp_path / "out")
    assert rows(tmp_path / "out") == {("group/a", "src/a"): 6, ("group/a", "src/b"): 6}


def test_the_same_directory_in_two_repos_is_two_hotspots(tmp_path):
    files = {
        f"ABC-{n}": [("group/a", "src/x.py"), ("group/b", "src/y.py")]
        for n in range(1, 6)
    }
    hotspots.write_hotspots(links_for(files), tmp_path / "out")
    assert rows(tmp_path / "out") == {("group/a", "src"): 5, ("group/b", "src"): 5}


# --- end to end over GitLab and Azure DevOps ---------------------------------------------------


def test_outputs_match_the_golden_files(tmp_path):
    out = run(tmp_path)
    if os.environ.get("UPDATE_GOLDEN"):
        shutil.rmtree(GOLDEN, ignore_errors=True)
        shutil.copytree(out, GOLDEN)
    produced = sorted(p.name for p in out.iterdir())
    assert (
        produced
        == sorted(p.name for p in GOLDEN.iterdir())
        == ["hotspots.csv", "hotspots.json", "hotspots.md"]
    )
    for name in produced:
        assert (out / name).read_text() == (GOLDEN / name).read_text(), name


def test_hotspots_cover_both_platforms_largest_first(tmp_path):
    out = run(tmp_path)
    data = json.loads((out / "hotspots.json").read_text())
    assert [
        (r["repo"], r["platform"], r["directory"], r["defects"])
        for r in data["directories"]
    ] == [
        ("group/checkout-service", "gitlab", "src/checkout", 9),
        ("Accounts/accounts-api", "azure", "src/Accounts", 8),
        ("group/checkout-service", "gitlab", "tests/checkout", 8),
        ("Accounts/accounts-api", "azure", "tests/Accounts.Tests", 6),
        ("[person]/checkout-tool", "gitlab", "notes/[person]", 5),
    ]
    assert (
        data["settings"]["depth"] == 2 and data["summary"]["defects_with_files"] == 24
    )


def test_small_directories_are_suppressed_with_enough_others_that_they_cannot_be_worked_out(
    tmp_path,
):
    out = run(tmp_path)
    data = json.loads((out / "hotspots.json").read_text())
    assert data["suppressed_directories"] == 4
    # build (2) is the only small Azure DevOps directory, so (root) (5) is hidden with it.
    assert ("Accounts/accounts-api", "(root)") not in rows(out)
    with (out / "hotspots.csv").open() as fh:
        named = {row[2] for row in list(csv.reader(fh))[1:] if len(row) > 2}
    assert named.isdisjoint({"src/payments", "docs", "build", "(root)"})
    md = (out / "hotspots.md").read_text()
    assert "src/payments" not in md and "| docs |" not in md and "| build |" not in md
    assert "4 groups suppressed" in md


def numbers_in(out):
    found = []
    for path in out.iterdir():
        text = re.sub(
            r"\d+ groups? suppressed|fewer than \d+ defects|depth \d+|\"(depth|suppressed_directories)\": \d+",
            "",
            path.read_text(),
        )
        text = re.sub(r"\d{4}-\d{2}-\d{2}", "", text)
        found += [int(n) for n in re.findall(r"(?<![\w.-])\d+(?![\w.-])", text)]
    return found


@pytest.mark.parametrize("k", [5, 6, 8])
@pytest.mark.parametrize("depth", [1, 2, 3])
def test_no_count_below_the_threshold_reaches_any_hotspot_output(tmp_path, k, depth):
    out = run(tmp_path, depth=depth, min_group_size=k)
    found = numbers_in(out)
    assert found and all(n == 0 or n >= k for n in found)


def test_the_depth_is_configurable(tmp_path):
    # At depth 1, src/payments joins src, and docs (1) is alone, so tests (8) is hidden with it.
    assert rows(run(tmp_path, depth=1)) == {
        ("group/checkout-service", "src"): 11,
        ("Accounts/accounts-api", "src"): 8,
        ("Accounts/accounts-api", "tests"): 6,
        ("[person]/checkout-tool", "notes"): 5,
    }


def test_outputs_hold_paths_only_never_people_owners_or_ticket_keys(tmp_path, people):
    out = run(tmp_path)
    for folder in ["work", "out"]:
        text = all_text_under(tmp_path / folder)
        assert [
            i
            for i in person_identifiers(people)
            if re.search(rf"(?<!\w){re.escape(i)}(?!\w)", text, re.I)
        ] == [], folder
        assert [o for o in OWNER if o.lower() in text.lower()] == [], folder
        assert "example-org" not in text, folder
    text = all_text_under(out)
    assert not re.search(r"\bABC[-_ ]?\d+\b", text, re.I)
    assert "[person]/checkout-tool" in text and "notes/[person]" in text


# --- the command line --------------------------------------------------------------------------


def test_the_command_line_reads_links_and_writes_hotspots_to_out(tmp_path):
    run(tmp_path)
    out = tmp_path / "cli_out"
    assert (
        hotspots.main(
            [
                "--links",
                str(tmp_path / "work/scm_links.json"),
                "--out",
                str(out),
                "--depth",
                "1",
            ]
        )
        == 0
    )
    assert ("Accounts/accounts-api", "src") in rows(out)


def test_the_command_line_takes_the_threshold_from_the_config(tmp_path):
    run(tmp_path)
    (tmp_path / "scm.yaml").write_text(
        "min_group_size: 9\n" + (SCM / "scm.yaml").read_text().split("\n", 1)[1]
    )
    assert (
        hotspots.main(
            [
                "--links",
                str(tmp_path / "work/scm_links.json"),
                "--out",
                str(tmp_path / "cli_out"),
                "--config",
                str(tmp_path / "scm.yaml"),
            ]
        )
        == 0
    )
    assert rows(tmp_path / "cli_out") == {("group/checkout-service", "src/checkout"): 9}


@pytest.mark.parametrize(
    "args,message",
    [(["--min-group-size", "4"], "at least 5"), (["--depth", "0"], "depth")],
)
def test_the_command_line_refuses_a_low_threshold_or_depth(
    tmp_path, capsys, args, message
):
    run(tmp_path)
    code = hotspots.main(
        [
            "--links",
            str(tmp_path / "work/scm_links.json"),
            "--out",
            str(tmp_path / "cli_out"),
            *args,
        ]
    )
    assert (
        code == 2
        and message in capsys.readouterr().err
        and not (tmp_path / "cli_out").exists()
    )
