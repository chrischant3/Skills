"""End-to-end behaviour of phases 1 to 3: raw Jira data to suppressed counts, with no SCM config.

The golden files in tests/golden/ are the expected outputs for tests/fixtures/pipeline. To
regenerate them after an intended change, run with UPDATE_GOLDEN=1 and review the diff.
"""

import json
import os
import re
import shutil
from pathlib import Path

import pytest

import aggregate
import anonymise
import jira_changelog
import make_batches
import validate_classifications
from conftest import FIXTURES, all_text_under, load_fixture, person_identifiers
from test_jira_changelog import Recorded

GOLDEN = Path(__file__).resolve().parent / "golden"
PIPELINE = FIXTURES / "pipeline"


def run_pipeline(tmp_path, min_group_size=None, period="month") -> Path:
    clean, work, out = tmp_path / "clean", tmp_path / "work", tmp_path / "out"
    anonymise.anonymise_dir(PIPELINE / "raw", clean)
    make_batches.write_batches(clean, work / "batches")
    assert (
        validate_classifications.main(
            [
                str(PIPELINE / "classifications"),
                "--issues",
                str(clean),
                "--out",
                str(work / "classified.json"),
            ]
        )
        == 0
    )
    aggregate.aggregate(clean, work / "classified.json", out, min_group_size, period)
    return out


def raw_issues():
    return [
        i
        for name in ["mcp-page-1.json", "mcp-page-2.json"]
        for i in json.loads((PIPELINE / "raw" / name).read_text())["issues"]
    ]


def test_outputs_match_the_golden_files(tmp_path):
    out = run_pipeline(tmp_path)
    if os.environ.get("UPDATE_GOLDEN"):
        shutil.rmtree(GOLDEN, ignore_errors=True)
        shutil.copytree(out, GOLDEN)
    produced = sorted(p.name for p in out.iterdir())
    assert produced == sorted(p.name for p in GOLDEN.iterdir())
    for name in produced:
        assert (out / name).read_text() == (GOLDEN / name).read_text(), name


def test_outputs_cover_coverage_types_themes_and_trends(tmp_path):
    data = json.loads((run_pipeline(tmp_path) / "aggregate.json").read_text())
    assert (
        data["summary"]["defects_analysed"] == 36
        and data["summary"]["matched_by_query"] == 36
    )
    assert {"types", "themes", "type_trend", "theme_trend"} <= set(data["tables"])
    themes = {
        r["labels"]["theme"]: r["total"] for r in data["tables"]["themes"]["rows"]
    }
    assert (
        themes["Null handling on optional address fields"] == 9
    )  # two spellings merged


@pytest.mark.parametrize("k", [5, 6, 7])
def test_no_count_below_the_threshold_reaches_any_output(tmp_path, k):
    out = run_pipeline(tmp_path, min_group_size=k)
    data = json.loads((out / "aggregate.json").read_text())
    counts = list(data["summary"].values()) + [
        v
        for t in data["tables"].values()
        for r in t["rows"]
        for v in [*r["values"].values(), r["total"]]
    ]
    assert all(v in (0, "suppressed") or v >= k for v in counts)
    for path in [*out.glob("*.csv"), out / "tables.md"]:
        text = re.sub(
            r"\d+ groups? suppressed", "", path.read_text()
        )  # counts of groups, not of defects
        text = text.replace(f"fewer than {k} defects", "")
        for number in re.findall(r"(?<![\w.-])\d+(?![\w.-])", text):
            assert int(number) == 0 or int(number) >= k, (path.name, number)


def test_no_person_pseudonym_ticket_key_or_ticket_text_reaches_any_output(
    tmp_path, people
):
    out = run_pipeline(tmp_path)
    text = all_text_under(out)
    assert [
        i
        for i in person_identifiers(people)
        if re.search(rf"(?<!\w){re.escape(i)}(?!\w)", text, re.I)
    ] == []
    assert not re.search(r"person_[0-9a-f]{12}", text) and "[person]" not in text
    assert not re.search(r"\bABC-\d+\b", text)
    for issue in raw_issues():
        assert issue["fields"]["summary"] not in text


def test_no_person_reaches_clean_or_the_batches_for_claude(tmp_path, people):
    run_pipeline(tmp_path)
    for folder in ["clean", "work/batches"]:
        text = all_text_under(tmp_path / folder)
        assert [
            i
            for i in person_identifiers(people)
            if re.search(rf"(?<!\w){re.escape(i)}(?!\w)", text, re.I)
        ] == []
    assert not re.search(
        r"person_[0-9a-f]{12}", all_text_under(tmp_path / "work/batches")
    )


def test_quarterly_trends_show_more_than_monthly_ones(tmp_path):
    def visible_cells(out):
        rows = json.loads((out / "aggregate.json").read_text())["tables"]["type_trend"][
            "rows"
        ]
        return sum(
            isinstance(v, int) and v > 0 for r in rows for v in r["values"].values()
        )

    assert visible_cells(
        run_pipeline(tmp_path / "q", period="quarter")
    ) > visible_cells(run_pipeline(tmp_path / "m"))


def test_aggregate_refuses_a_threshold_below_five(tmp_path, capsys):
    run_pipeline(tmp_path)
    code = aggregate.main(
        [
            "--classified",
            str(tmp_path / "work/classified.json"),
            "--issues",
            str(tmp_path / "clean"),
            "--out",
            str(tmp_path / "out4"),
            "--min-group-size",
            "4",
        ]
    )
    assert (
        code == 2
        and "at least 5" in capsys.readouterr().err
        and not (tmp_path / "out4").exists()
    )


def test_aggregate_refuses_classifications_that_do_not_match_clean(tmp_path):
    run_pipeline(tmp_path)
    classified = json.loads((tmp_path / "work/classified.json").read_text())
    classified["records"] = classified["records"][1:]
    (tmp_path / "short.json").write_text(json.dumps(classified))
    with pytest.raises(ValueError, match="doesn't match"):
        aggregate.aggregate(
            tmp_path / "clean", tmp_path / "short.json", tmp_path / "out2"
        )


def test_aggregate_refuses_raw_input(tmp_path):
    run_pipeline(tmp_path)
    raw_clean = tmp_path / "rawclean"
    raw_clean.mkdir()
    for issue in raw_issues():
        (raw_clean / f"{issue['key']}.json").write_text(json.dumps(issue))
    with pytest.raises(ValueError, match="anonymise"):
        aggregate.aggregate(
            raw_clean, tmp_path / "work/classified.json", tmp_path / "out3"
        )


@pytest.mark.parametrize("fixture_name", ["cloud_search.json", "dc_search.json"])
def test_rest_fallback_data_comes_out_of_anonymise_with_no_people(
    tmp_path, people, fixture_name
):
    fixture = load_fixture(f"recorded/{fixture_name}")
    client = jira_changelog.JiraClient(
        fixture["base_url"],
        fixture["deployment"],
        "Basic x",
        transport=Recorded(fixture),
        sleep=lambda s: None,
    )
    jira_changelog.fetch(client, "project = ABC", tmp_path / "raw")
    anonymise.anonymise_dir(tmp_path / "raw", tmp_path / "clean")
    text = all_text_under(tmp_path / "clean")
    assert [
        i
        for i in person_identifiers(people)
        if re.search(rf"(?<!\w){re.escape(i)}(?!\w)", text, re.I)
    ] == []
    report = json.loads((tmp_path / "clean/_ingest.json").read_text())
    assert (
        report["changelog_incomplete"] == []
        and report["comments_incomplete"] == []
        and report["sources"] == ["rest"]
    )
