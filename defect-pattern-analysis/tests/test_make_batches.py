"""Behaviour tests for scripts/make_batches.py: batched, trimmed, anonymised input for Claude (F3)."""

import json
import re

import pytest

import anonymise
import make_batches
from conftest import all_text_under, load_fixture, person_identifiers


@pytest.fixture
def clean_dir(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    for name in ["jira/cloud_issue_ABC-101.json", "jira/dc_issue_ABC-102.json"]:
        (raw / name.split("/")[1]).write_text(json.dumps(load_fixture(name)))
    anonymise.anonymise_dir(raw, tmp_path / "clean")
    return tmp_path / "clean"


def issue(key, description="Short description.", comments=()):
    return {"key": key, "fields": {"summary": f"Summary {key}", "issuetype": {"name": "Bug"}, "status": {"name": "Done"},
                                   "components": [{"name": "Payments"}], "labels": [], "created": "2026-01-01T00:00:00.000+0000",
                                   "description": description,
                                   "comment": {"comments": [{"body": c, "author": {"pseudonym": "person_0123456789ab"}} for c in comments]}}}


def test_raw_unanonymised_input_is_refused(tmp_path):
    (tmp_path / "ABC-101.json").write_text(json.dumps(load_fixture("jira/cloud_issue_ABC-101.json")))
    with pytest.raises(ValueError, match="anonymise"):
        make_batches.write_batches(tmp_path, tmp_path / "batches")


def test_batches_hold_no_people_and_no_pseudonyms(clean_dir, tmp_path, people):
    make_batches.write_batches(clean_dir, tmp_path / "batches")
    text = all_text_under(tmp_path / "batches")
    assert not re.search(r"person_[0-9a-f]{12}", text)
    assert [i for i in person_identifiers(people) if re.search(rf"(?<!\w){re.escape(i)}(?!\w)", text, re.I)] == []


def test_tickets_carry_what_classification_needs(clean_dir, tmp_path):
    make_batches.write_batches(clean_dir, tmp_path / "batches")
    batch = json.loads((tmp_path / "batches/batch-001.json").read_text())
    first = batch["tickets"][0]
    assert first["key"] == "ABC-101" and first["issue_type"] == "Bug" and first["status"] == "In Progress"
    assert first["components"] == ["Payments"] and first["summary"].startswith("Checkout fails")
    assert "@Override" in first["description"] and "assets/logo@2x.png" in first["description"]
    assert len(first["comments"]) == 2
    assert batch["taxonomy"] == "reference/taxonomy.md"


def test_long_descriptions_are_trimmed_and_say_so():
    ticket = make_batches.ticket_for_claude(issue("ABC-1", "x" * 10_000), field_chars=1000)
    assert len(ticket["description"]) < 1100 and "characters trimmed" in ticket["description"]
    assert ticket["trimmed"] is True


def test_short_text_is_left_whole():
    ticket = make_batches.ticket_for_claude(issue("ABC-1", "All good."))
    assert ticket["description"] == "All good." and ticket["trimmed"] is False


def test_long_comment_threads_keep_the_first_and_last_comments():
    ticket = make_batches.ticket_for_claude(issue("ABC-1", comments=[f"comment {n}" for n in range(30)]), max_comments=6)
    assert ticket["comments"][:3] == ["comment 0", "comment 1", "comment 2"]
    assert ticket["comments"][-3:] == ["comment 27", "comment 28", "comment 29"]
    assert any("24 comments omitted" in c for c in ticket["comments"])
    assert ticket["comment_count"] == 30


def test_every_ticket_lands_in_exactly_one_batch_within_limits():
    issues = [issue(f"ABC-{n}", "y" * (300 * (n % 5))) for n in range(1, 48)]
    batches = make_batches.make_batches(issues, max_tickets=10, max_chars=3000)
    keys = [t["key"] for b in batches for t in b]
    assert sorted(keys) == sorted(i["key"] for i in issues) and len(keys) == len(set(keys))
    assert all(len(b) <= 10 for b in batches)
    assert all(len(json.dumps(b)) <= 3000 or len(b) == 1 for b in batches)


def test_a_pseudonym_that_slipped_into_text_stops_the_batch():
    leaky = issue("ABC-1", "assigned to person_0123456789ab")
    with pytest.raises(ValueError, match="pseudonym"):
        make_batches.make_batches([leaky])
