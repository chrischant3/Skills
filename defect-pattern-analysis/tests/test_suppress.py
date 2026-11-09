"""Behaviour tests for scripts/suppress.py: small groups never reach any output (P5, known problem 3).

Fixtures hold groups of 1 to 6 tickets. Thresholds below 5 are refused, so suppression is
checked at 5, 6 and 7, in every output format (JSON, CSV, Markdown).
"""

import csv
import json
import random
import re

import pytest

import suppress

COMBOS = [(), ("team",), ("type",), ("period",), ("team", "type"), ("type", "period")]
TABLES = {"by_team": (("team",), "type"), "by_type": (("type",), "period"), "teams": (("team",), None)}


def records_with_group_sizes(sizes: dict[str, int]) -> list[dict]:
    """One record per ticket; team <name> has the given number of tickets."""
    out = []
    for team, n in sizes.items():
        for i in range(n):
            out.append({"team": team, "type": ["function_logic", "checking_validation"][i % 2],
                        "period": ["2026-01", "2026-02"][i % 2]})
    return out


def write(tmp_path, records, k, tables=TABLES):
    pub = suppress.publish(records, COMBOS, k)
    suppress.write_outputs(pub, tables, tmp_path, settings={"min_group_size": k})
    return pub


def published_counts(tmp_path) -> dict[str, list]:
    """Every count cell from every output format."""
    data = json.loads((tmp_path / "aggregate.json").read_text())
    from_json = [v for t in data["tables"].values() for row in t["rows"] for v in [*row["values"].values(), row["total"]]]
    from_csv = []
    for path in tmp_path.glob("*.csv"):
        with path.open() as fh:
            for row in csv.DictReader(fh):
                from_csv += [v for k, v in row.items() if k not in ("team", "type", "period", "theme") and v]
    from_md = []
    lines = (tmp_path / "tables.md").read_text().splitlines()
    for line, following in zip(lines, lines[1:] + [""]):
        is_header = set(following) <= set("|- ") and following.startswith("|")
        if line.startswith("|") and not set(line) <= set("|- ") and not is_header:
            from_md += [c.strip() for c in line.strip("|").split("|")[1:]]
    return {"json": from_json, "csv": from_csv, "md": from_md}


def derivable(pub) -> set:
    """Play an attacker: solve every published sum for hidden cells. Returns hidden cells recovered."""
    known = {c: n for c, n in pub.cells.items() if c not in pub.suppressed}
    recovered = set()
    changed = True
    while changed:
        changed = False
        for parent, children in pub.lines:
            members = [parent, *children]
            unknown = [m for m in members if m not in known]
            if len(unknown) == 1:
                m = unknown[0]
                known[m] = (known[parent] - sum(known[c] for c in children if c != m)) if m != parent \
                    else sum(known[c] for c in children)
                recovered.add(m)
                changed = True
            elif unknown and parent in known and len(unknown) == known[parent] - sum(known[c] for c in children if c in known):
                for m in unknown:
                    known[m] = 1
                    recovered.add(m)
                changed = True
    return recovered


# --- min_group_size ----------------------------------------------------------------------

@pytest.mark.parametrize("value", [1, 2, 3, 4, 0, -5])
def test_thresholds_below_five_are_refused(value):
    with pytest.raises(ValueError, match="at least 5"):
        suppress.validate_min_group_size(value)


@pytest.mark.parametrize("value", [True, 5.5, "5"])
def test_non_integer_thresholds_are_refused(value):
    with pytest.raises(ValueError):
        suppress.validate_min_group_size(value)


@pytest.mark.parametrize("value,expected", [(None, 5), (5, 5), (6, 6), (25, 25)])
def test_thresholds_of_five_or_more_are_accepted(value, expected):
    assert suppress.validate_min_group_size(value) == expected


def test_publish_refuses_a_low_threshold():
    with pytest.raises(ValueError):
        suppress.publish(records_with_group_sizes({"A": 6}), COMBOS, 3)


# --- groups of 1 to 6, at every allowed threshold, in every format ----------------------------

@pytest.mark.parametrize("k", [5, 6, 7])
@pytest.mark.parametrize("fmt", ["json", "csv", "md"])
def test_no_count_below_threshold_appears_in_any_format(tmp_path, k, fmt):
    write(tmp_path, records_with_group_sizes({f"T{n}": n for n in range(1, 7)}), k)
    for value in published_counts(tmp_path)[fmt]:
        assert value in (0, "0", suppress.SUPPRESSED) or int(value) >= k, value


@pytest.mark.parametrize("k,visible", [(5, ["T5", "T6"]), (6, ["T6"]), (7, [])])
def test_only_teams_at_or_above_threshold_are_named(tmp_path, k, visible):
    write(tmp_path, records_with_group_sizes({f"T{n}": n for n in range(1, 7)}), k)
    for name in [f"T{n}" for n in range(1, 7)]:
        shown = any(re.search(rf"\b{name}\b", p.read_text()) for p in tmp_path.iterdir())
        assert shown == (name in visible), name


@pytest.mark.parametrize("k", [5, 6, 7])
def test_outputs_say_groups_were_suppressed_without_saying_what_they_held(tmp_path, k):
    write(tmp_path, records_with_group_sizes({f"T{n}": n for n in range(1, 7)}), k)
    data = json.loads((tmp_path / "aggregate.json").read_text())
    assert data["tables"]["teams"]["suppressed_rows"] == (k - 1 if k <= 6 else 6)
    assert "suppressed" in (tmp_path / "tables.md").read_text()
    assert "suppressed" in (tmp_path / "teams.csv").read_text()


def test_a_dataset_smaller_than_the_threshold_publishes_no_counts(tmp_path):
    write(tmp_path, records_with_group_sizes({"A": 4}), 5)
    for values in published_counts(tmp_path).values():
        assert all(v in (0, "0", suppress.SUPPRESSED) for v in values)


# --- no working it out by subtraction -------------------------------------------------------

def test_a_single_small_group_cannot_be_found_by_subtracting_from_the_total():
    pub = suppress.publish(records_with_group_sizes({"A": 8, "B": 2}), COMBOS, 5)
    assert pub.value(frozenset({("team", "B")})) == suppress.SUPPRESSED
    assert derivable(pub) == set()


def test_two_groups_of_one_cannot_be_pinned_by_their_sum():
    pub = suppress.publish(records_with_group_sizes({"A": 9, "B": 1, "C": 1}), COMBOS, 5)
    assert derivable(pub) == set()


@pytest.mark.parametrize("seed", range(60))
def test_random_datasets_leak_nothing_by_subtraction(seed):
    rng = random.Random(seed)
    records = [{"team": rng.choice("ABCDE"), "type": rng.choice(["logic", "data", "ux", "timing"]),
                "period": rng.choice(["2026-01", "2026-02", "2026-03"])} for _ in range(rng.randint(3, 60))]
    k = rng.choice([5, 6, 7])
    pub = suppress.publish(records, COMBOS, k)
    assert all(pub.cells[c] >= k for c in pub.cells if c not in pub.suppressed)
    assert derivable(pub) == set()


# --- every output goes through the suppression step --------------------------------------------

def test_a_table_outside_the_suppressed_groupings_is_refused():
    pub = suppress.publish(records_with_group_sizes({"A": 6}), COMBOS, 5)
    with pytest.raises(ValueError, match="not a published grouping"):
        pub.table(("team",), "period")


def test_settings_cannot_carry_extra_counts(tmp_path):
    pub = suppress.publish(records_with_group_sizes({"A": 6}), COMBOS, 5)
    with pytest.raises(ValueError):
        suppress.write_outputs(pub, TABLES, tmp_path, settings={"defects_in_team_b": 2})


def test_scalar_counts_from_outside_the_records_are_suppressed_too():
    pub = suppress.publish(records_with_group_sizes({"A": 6}), COMBOS, 5)
    assert pub.scalar(3) == suppress.SUPPRESSED and pub.scalar(0) == 0 and pub.scalar(12) == 12


def test_visible_counts_are_correct(tmp_path):
    write(tmp_path, records_with_group_sizes({"A": 6, "B": 7}), 5)
    teams = {r["labels"]["team"]: r["total"] for r in json.loads((tmp_path / "aggregate.json").read_text())["tables"]["teams"]["rows"]}
    assert teams == {"A": 6, "B": 7}


def test_a_column_whose_own_total_is_suppressed_is_not_named(tmp_path):
    records = records_with_group_sizes({"A": 6, "B": 6})
    records.append({"team": "A", "type": "rare_type", "period": "2026-01"})
    pub = write(tmp_path, records, 5)
    table = pub.table(("team",), "type")
    # Hiding rare_type forces a second type to be hidden too, or it could be found from the total.
    assert "rare_type" not in table["columns"] and table["suppressed_columns"] >= 1
    assert not any("rare_type" in p.read_text() for p in tmp_path.iterdir())
