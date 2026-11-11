#!/usr/bin/env python3
"""Fix hotspots by directory: how many defects had fixes that touched each directory, per repo.

Usage: hotspots.py --links work/scm_links.json --out out/ [--depth 2] [--min-group-size 5]
                   [--config scm.yaml]

Reads the links link_scm.py wrote (built only from anonymised data in clean/), so it
works the same for every platform: GitLab, Azure DevOps or both in one run.

The counting rule: a directory's count is the number of distinct defects whose linked
changes touched at least one file in it. Files, commits and changes are never counted,
so one large fix (or a defect fixed in many commits) counts once, the same as a
one-line fix. A defect whose fix touched several directories counts once in each, so
directory counts don't add up to the number of defects.

A file's directory is its folder path cut to --depth parts (default 2, such as
src/checkout). Files at the top of a repo count under "(root)". The same directory in
two repos is two hotspots.

Every count goes through suppress.py: a directory with fewer than min_group_size
defects (default 5, never lower) is hidden, along with enough others in its repo that
it can't be worked out, and a hidden directory is never named. Outputs hold repo names
and directory paths only: no authors, ticket keys or ticket text. A repo in a personal
namespace is already shown as [person]/name, and its owner's name in any path is
already [person], because anonymise.py removed it before linking.

Writes out/hotspots.json, out/hotspots.csv and out/hotspots.md.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import scm_config
import suppress

DEFAULT_DEPTH = 2
ROOT = "(root)"
COUNT_RULE = (
    "distinct defects whose linked changes touched a file in the directory; files, commits and changes "
    "are not counted, and a defect counts once in each directory its fix touched"
)
# The () and ("repo",) cells count defect-directory pairs. They are never published; they
# give secondary suppression the sums it protects (a partition of the pairs), so a hidden
# directory always has company in its repo.
GROUPINGS = [(), ("repo",), ("repo", "directory")]


def directory_of(path: str, depth: int = DEFAULT_DEPTH) -> str:
    """The folder path of a file, cut to depth parts; ROOT for a file at the top of the repo."""
    folders = [p for p in path.strip("/").split("/") if p][:-1]
    return "/".join(folders[:depth]) if folders else ROOT


def validate_depth(depth) -> int:
    """Return depth if it is a whole number of at least 1. Raises ValueError otherwise."""
    if isinstance(depth, bool) or not isinstance(depth, int) or depth < 1:
        raise ValueError(f"depth must be a whole number of at least 1, got {depth!r}")
    return depth


def build_records(links: dict, depth: int = DEFAULT_DEPTH) -> list[dict]:
    """One record per (defect, repo, directory) its fix touched, so each directory counts each defect once."""
    records = []
    for defect in links["defects"].values():
        touched = {
            (f["repo"], directory_of(f["path"], depth))
            for f in defect.get("files") or []
        }
        records += [
            {"repo": repo, "directory": directory}
            for repo, directory in sorted(touched)
        ]
    return records


def write_hotspots(
    links: dict, out_dir, depth: int = DEFAULT_DEPTH, min_group_size=None
) -> None:
    """Write out/hotspots.json, .csv and .md, with every count suppressed by suppress.py.

    Args:
        links: as link_scm.link() returns it.
        out_dir: the run's out/ folder.
        depth: how many folder levels name a directory (default 2).
        min_group_size: threshold (default 5; below 5 is refused).
    Raises:
        ValueError: for a threshold below 5 or a depth below 1, before anything is written.
    """
    size = suppress.validate_min_group_size(min_group_size)
    depth = validate_depth(depth)
    pub = suppress.publish(build_records(links, depth), GROUPINGS, size)
    pub.add_scalar(
        "defects_with_files",
        sum(bool(d.get("files")) for d in links["defects"].values()),
    )
    table = pub.table(("repo", "directory"))
    platforms = {name: repo.get("platform") for name, repo in links["repos"].items()}
    rows = sorted(
        (
            {
                "repo": r["labels"]["repo"],
                "platform": platforms.get(r["labels"]["repo"]),
                "directory": r["labels"]["directory"],
                "defects": r["total"],
            }
            for r in table["rows"]
        ),
        key=lambda r: (-r["defects"], r["repo"].lower(), r["directory"].lower()),
    )
    hidden = table["suppressed_rows"]

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    settings = {
        "min_group_size": size,
        "depth": depth,
        "since": links.get("since"),
        "count_rule": COUNT_RULE,
    }
    doc = {
        "settings": settings,
        "suppressed_marker": suppress.SUPPRESSED,
        "summary": pub.summary,
        "directories": rows,
        "suppressed_directories": hidden,
    }
    (out_dir / "hotspots.json").write_text(
        json.dumps(doc, indent=2) + "\n", encoding="utf-8"
    )

    columns = ["repo", "platform", "directory", "defects"]
    note = suppress.SUPPRESSED_NOTE.format(
        n=hidden, groups="group" if hidden == 1 else "groups", k=size
    )
    with (out_dir / "hotspots.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([row[c] for c in columns])
        if hidden:
            writer.writerow([note, "", "", ""])

    md = [
        "# Fix hotspots by directory",
        "",
        f"Each count is the number of defects whose fixes touched the directory (folders cut to depth {depth}), "
        f"from changes merged on or after {links.get('since')}. A defect counts once per directory, however many "
        "files or commits its fix had, and once in each directory it touched, so the counts don't add up to the "
        f"number of defects. Groups with fewer than {size} defects are suppressed.",
        "",
        "## Summary",
        "",
    ]
    md += [f"- {k}: {v}" for k, v in pub.summary.items()]
    md += [
        "",
        "## Directories",
        "",
        "| " + " | ".join(columns) + " |",
        "|" + "---|" * len(columns),
    ]
    md += ["| " + " | ".join(str(row[c]) for c in columns) + " |" for row in rows]
    if hidden:
        md += ["", note]
    (out_dir / "hotspots.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Count defects per directory their fixes touched, with small groups suppressed."
    )
    ap.add_argument("--links", default="work/scm_links.json")
    ap.add_argument("--out", default="out")
    ap.add_argument(
        "--depth",
        type=int,
        default=DEFAULT_DEPTH,
        help="folder levels that name a directory (default 2)",
    )
    ap.add_argument(
        "--min-group-size",
        type=int,
        default=None,
        help="default 5, or the config's; below 5 is refused",
    )
    ap.add_argument("--config", help="scm.yaml, for its min_group_size")
    a = ap.parse_args(argv)
    try:
        configured = (
            scm_config.load_config(a.config).get("min_group_size") if a.config else None
        )
        size = suppress.validate_min_group_size(a.min_group_size or configured)
        depth = validate_depth(a.depth)
        links = json.loads(Path(a.links).read_text(encoding="utf-8"))
    except (ValueError, OSError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    write_hotspots(links, a.out, depth, size)
    print(f"Wrote hotspots.json, .csv and .md (depth {depth}) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
