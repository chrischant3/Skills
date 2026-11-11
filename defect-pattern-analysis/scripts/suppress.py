#!/usr/bin/env python3
"""Small-group suppression: the only way counts reach an output file.

Every count the skill publishes is a cell: the number of defects matching a set of
dimension values, such as {type: checking_validation, period: 2026-03}. publish() builds
every cell for the groupings you name, then hides:

1. Primary: any cell with between 1 and min_group_size - 1 defects.
2. Secondary: enough further cells that no hidden cell can be worked out by subtracting
   visible cells from a visible total (for example a team of 2 hidden next to a team of 8
   and a total of 10), or by a hidden sum that only fits if every hidden cell is 1.

Tables and output files are drawn only from those cells. A table row or column whose
own total is hidden is left out entirely, so a suppressed group is never named; the
output says how many groups were suppressed instead. min_group_size below 5 is refused.

This is a practical guard against the obvious ways of recovering small counts. It is
not a formal statistical disclosure control method.
"""

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_MIN_GROUP_SIZE = 5
SUPPRESSED = "suppressed"
SUPPRESSED_NOTE = (
    "{n} {groups} suppressed: each had fewer than {k} defects, or was hidden so that a "
    "small group can't be worked out from the totals."
)
# Settings are configuration, not results. Only these may be numbers.
NUMERIC_SETTINGS = {"min_group_size"}


def validate_min_group_size(value=None) -> int:
    """Return a usable minimum group size.

    Args:
        value: the requested size, or None for the default of 5.
    Raises:
        ValueError: if value is not a whole number, or is below 5.
    """
    if value is None:
        return DEFAULT_MIN_GROUP_SIZE
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"min_group_size must be a whole number, got {value!r}")
    if value < DEFAULT_MIN_GROUP_SIZE:
        raise ValueError(
            f"min_group_size must be at least {DEFAULT_MIN_GROUP_SIZE} so small groups stay "
            f"hidden; got {value}. Use a higher value for small teams, never a lower one."
        )
    return value


def _label(value) -> str:
    return "none" if value is None or value == "" else str(value)


def _dims(key: frozenset) -> frozenset:
    return frozenset(d for d, _ in key)


class Publication:
    """Suppressed counts for a set of records, and the tables that may be drawn from them.

    Attributes:
        cells: every non-zero cell, keyed by frozenset of (dimension, value) pairs.
        lines: (parent, children) sums the published tables reveal, used for secondary suppression.
        suppressed: the cells that must never be shown.
        min_group_size: the threshold in force.
    """

    def __init__(self, records, combos, min_group_size):
        self.min_group_size = validate_min_group_size(min_group_size)
        self.combos = {frozenset(c) for c in combos}
        # Always work through groupings in the same order. Set order changes from run to run
        # (string hashing is randomised), and the order lines are checked in decides which
        # extra cells secondary suppression hides, so outputs would otherwise differ.
        self._ordered_combos = sorted(self.combos, key=lambda c: (len(c), sorted(c)))
        self.cells: dict[frozenset, int] = Counter()
        self._by_combo: dict[frozenset, list] = defaultdict(list)
        for combo in self._ordered_combos:
            for record in records:
                self.cells[frozenset((d, _label(record.get(d))) for d in combo)] += 1
        for key in self.cells:
            self._by_combo[_dims(key)].append(key)
        self.lines = self._build_lines()
        self.suppressed = self._suppress()
        self._scalars: dict[str, object] = {}

    def _build_lines(self):
        lines = []
        for parent_combo in self._ordered_combos:
            for child_combo in self._ordered_combos:
                if (
                    len(child_combo) == len(parent_combo) + 1
                    and parent_combo < child_combo
                ):
                    for parent in self._by_combo[parent_combo]:
                        children = [
                            c for c in self._by_combo[child_combo] if parent <= c
                        ]
                        lines.append((parent, sorted(children, key=sorted)))
        return lines

    def _suppress(self) -> set:
        k = self.min_group_size
        hidden = {c for c, n in self.cells.items() if 0 < n < k}
        changed = True
        while changed:
            changed = False
            for parent, children in self.lines:
                members = [parent, *children]
                if self._line_is_exposed(parent, children, hidden):
                    candidates = [
                        m for m in members if m not in hidden and self.cells[m] > 0
                    ]
                    pick = min(
                        candidates,
                        key=lambda m: (self.cells[m], m == parent, sorted(m)),
                    )
                    hidden.add(pick)
                    changed = True
        return hidden

    def _line_is_exposed(self, parent, children, hidden) -> bool:
        hidden_members = [m for m in [parent, *children] if m in hidden]
        if len(hidden_members) == 1:
            return True
        hidden_children = [c for c in children if c in hidden]
        if parent in hidden or not hidden_children:
            return False
        hidden_sum = self.cells[parent] - sum(
            self.cells[c] for c in children if c not in hidden
        )
        return hidden_sum == len(hidden_children)

    def _check_combo(self, combo) -> None:
        if frozenset(combo) not in self.combos:
            raise ValueError(
                f"{sorted(combo)} is not a published grouping; add it to the groupings passed to publish()"
            )

    def value(self, key: frozenset):
        """The published count for a cell: a number, or SUPPRESSED."""
        self._check_combo(_dims(key))
        return SUPPRESSED if key in self.suppressed else self.cells.get(key, 0)

    def scalar(self, n: int):
        """Publish a count that isn't built from the records (such as defects matched by the query)."""
        return SUPPRESSED if 0 < n < self.min_group_size else n

    def add_cell(self, name: str, key: frozenset) -> None:
        """Record a named cell's published count (number or SUPPRESSED) for the summary."""
        self._scalars[name] = self.value(key)

    def add_scalar(self, name: str, n: int) -> None:
        """Record a named stand-alone count for the summary, suppressed like any other."""
        self._scalars[name] = self.scalar(n)

    @property
    def summary(self) -> dict:
        return dict(self._scalars)

    def table(self, row_dims, col_dim=None) -> dict:
        """Return a table of rows by row_dims, with optional columns by col_dim.

        Rows whose total is suppressed are left out and only counted, so they are never named.
        Columns are left out the same way when their own total (the col_dim grouping) is suppressed.
        """
        row_dims = tuple(row_dims)
        self._check_combo(row_dims)
        if col_dim:
            self._check_combo(row_dims + (col_dim,))
        rows, hidden_rows = [], 0
        for key in sorted(
            self._by_combo[frozenset(row_dims)],
            key=lambda k: [dict(k)[d] for d in row_dims],
        ):
            if key in self.suppressed:
                hidden_rows += 1
                continue
            labels = {d: dict(key)[d] for d in row_dims}
            values = {}
            if col_dim:
                for child in self._by_combo[frozenset(row_dims + (col_dim,))]:
                    if key <= child:
                        values[dict(child)[col_dim]] = self.value(child)
            rows.append({"labels": labels, "values": values, "total": self.value(key)})
        columns = sorted({c for r in rows for c in r["values"]})
        hidden_columns = 0
        if col_dim and frozenset({col_dim}) in self.combos:
            visible = [
                c
                for c in columns
                if self.value(frozenset({(col_dim, c)})) != SUPPRESSED
            ]
            hidden_columns, columns = len(columns) - len(visible), visible
        for r in rows:
            r["values"] = {c: r["values"].get(c, 0) for c in columns}
        return {
            "row_dims": list(row_dims),
            "column_dim": col_dim,
            "columns": columns,
            "rows": rows,
            "suppressed_rows": hidden_rows,
            "suppressed_columns": hidden_columns,
        }


def publish(records, combos, min_group_size=None) -> Publication:
    """Build and suppress every cell for the given groupings.

    Args:
        records: one dict per defect, mapping dimension name to value.
        combos: the groupings that may be published, as tuples of dimension names. Include
            () for the overall total and every grouping a table will use.
        min_group_size: threshold (default 5; below 5 is refused).
    """
    return Publication(records, combos, min_group_size)


def _note(n: int, k: int) -> str:
    return SUPPRESSED_NOTE.format(n=n, groups="group" if n == 1 else "groups", k=k)


def _check_settings(settings: dict) -> None:
    for key, value in settings.items():
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and key not in NUMERIC_SETTINGS
        ):
            raise ValueError(
                f"setting {key!r} is a number; counts must go through the Publication, not settings"
            )


def write_outputs(
    pub: Publication, tables: dict, out_dir, settings: dict | None = None
) -> None:
    """Write aggregate.json, one CSV per table and tables.md, all from the suppressed cells.

    Args:
        pub: the Publication to draw from.
        tables: name -> (row_dims, col_dim or None).
        out_dir: folder to write into.
        settings: configuration to record (strings; min_group_size may be a number).
    """
    settings = dict(settings or {})
    _check_settings(settings)
    settings["min_group_size"] = pub.min_group_size
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    built = {name: pub.table(rows, col) for name, (rows, col) in tables.items()}

    (out_dir / "aggregate.json").write_text(
        json.dumps(
            {
                "settings": settings,
                "suppressed_marker": SUPPRESSED,
                "summary": pub.summary,
                "tables": built,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    for name, table in built.items():
        with (out_dir / f"{name}.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh, lineterminator="\n")
            writer.writerow([*table["row_dims"], *table["columns"], "total"])
            for row in table["rows"]:
                writer.writerow(
                    [*row["labels"].values(), *row["values"].values(), row["total"]]
                )
            hidden = table["suppressed_rows"] + table["suppressed_columns"]
            if hidden:
                writer.writerow(
                    [_note(hidden, pub.min_group_size)]
                    + [""] * (len(table["row_dims"]) - 1 + len(table["columns"]) + 1)
                )

    md = [
        "# Defect counts",
        "",
        f"Groups with fewer than {pub.min_group_size} defects are suppressed.",
        "",
    ]
    if pub.summary:
        md += (
            ["## Summary", ""] + [f"- {k}: {v}" for k, v in pub.summary.items()] + [""]
        )
    for name, table in built.items():
        header = [*table["row_dims"], *table["columns"], "total"]
        md += [
            f"## {name}",
            "",
            "| " + " | ".join(header) + " |",
            "|" + "---|" * len(header),
        ]
        for row in table["rows"]:
            cells = [*row["labels"].values(), *row["values"].values(), row["total"]]
            md.append("| " + " | ".join(str(c) for c in cells) + " |")
        hidden = table["suppressed_rows"] + table["suppressed_columns"]
        if hidden:
            md += ["", _note(hidden, pub.min_group_size)]
        md.append("")
    (out_dir / "tables.md").write_text("\n".join(md), encoding="utf-8")
