#!/usr/bin/env python3
"""Estimate where defects were introduced, by blaming the lines their fixes changed (SZZ).

Usage: szz.py --links work/scm_links.json --issues clean/ --clone NAME=PATH [--clone ...]
              [--work work/szz.json] [--out out/] [--depth 2] [--min-group-size 5]
              [--config scm.yaml]

For each fix commit link_scm.py linked to a defect, this blames, in the commit's parent,
every line the fix removed or changed. The commits that last changed those lines are the
candidate introducers. It reads local clones, so it works the same for every platform.

- NAME is the repo's name as work/scm_links.json and out/scm_coverage.md show it (such
  as group/checkout-service), so two repos with the same last name never collide.
- Lines that only changed whitespace, and comment-only lines, are not blamed. Commits
  listed in a repo's .git-blame-ignore-revs are looked past.
- A candidate committed after the defect was reported is dropped.
- Merge commits, commits missing from the clone, and fixes that only add lines can't be
  traced. Each is counted in the summary, never skipped silently.

Outputs:
- work/szz.json: per defect, where its candidate introducers are (repo and cleaned
  path), and the lags as a sorted list not tied to any defect. It holds ticket keys, so
  it is working data, never a report.
- out/szz.json, .csv and .md: per repo and directory, the number of distinct defects
  with a candidate introducer there, every count through suppress.py, and the median
  days from the newest candidate to the report. Every output says it is an estimate.

No output holds an author, a commit id or a commit time. Blame's author and committer fields are
discarded as they are parsed. Paths in a clone are raw data (a folder can be named after
a person), so a path is used only when link_scm.py already listed it for that repo, from
data anonymise.py cleaned, and is shown in that cleaned form. Other paths are counted as
paths_not_in_linked_changes and never shown. Repo names come from work/scm_links.json.
"""

import argparse
import csv
import json
import os
import re
import statistics
import subprocess
import sys
from pathlib import Path

import clean_data
import hotspots
import scm_config
import suppress
import ticket_signals

# SHA-1 ids are 40 hex characters and SHA-256 ids 64; abbreviated ids have at least 7.
COMMIT_ID = re.compile(r"[0-9a-f]{7,64}")
BLAME_HEADER = re.compile(r"^([0-9a-f]{40}|[0-9a-f]{64}) \d+ \d+")
PLACEHOLDER = "[person]"
GIT_TIMEOUT_SECONDS = 300
# A comment-only line: #, //, /*, a * continuing a block comment, or -- (SQL, Lua).
COMMENT = re.compile(r"^\s*(#|//|/\*|\*(\s|/|$)|--(\s|$))")
IGNORE_REVS = ".git-blame-ignore-revs"
ESTIMATE_NOTE = (
    "An estimate. SZZ blames the lines each fix changed, so refactors, moved code and fixes "
    "that only add lines make it miss or mislead. Treat these directories as prompts for a "
    "conversation about the code, not as facts, and never about the people who worked on it."
)
COUNT_RULE = (
    "distinct defects with a candidate introducing line in the directory; a defect counts "
    "once in each directory, however many lines or commits it traced to"
)
GROUPINGS = hotspots.GROUPINGS
COVERAGE_KEYS = [
    "defects_linked",
    "defects_traced",
    "fix_commits_blamed",
    "commits_not_in_clone",
    "merge_commits_skipped",
    "commits_with_nothing_to_blame",
    "blame_failures",
    "candidates_after_report_dropped",
    "defects_without_report_date",
    "paths_not_in_linked_changes",
]


def _git(repo: Path, *args) -> subprocess.CompletedProcess:
    """Run git in repo. A run that times out comes back as a failure (returncode -1)."""
    # GIT_DIR, GIT_WORK_TREE and the like override -C, so none is passed on. The -c
    # settings pin the output format, so a user's own git config can't change what is parsed.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    command = [
        "git",
        "-C",
        str(repo),
        "-c",
        "core.quotePath=false",
        "-c",
        "log.showSignature=false",
        *args,
    ]
    try:
        return subprocess.run(
            command,
            capture_output=True,
            env=env,
            timeout=GIT_TIMEOUT_SECONDS,
            # Source files needn't be UTF-8. surrogateescape keeps any byte, so a path
            # read here can be passed back to git unchanged.
            encoding="utf-8",
            errors="surrogateescape",
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(command, -1, "", "timed out")


def _parents(repo: Path, sha: str) -> list[str] | None:
    """The commit's parents, or None if the clone doesn't have it."""
    done = _git(repo, "rev-list", "--parents", "-n", "1", f"{sha}^{{commit}}", "--")
    if done.returncode != 0 or not done.stdout.strip():
        return None
    return done.stdout.split()[1:]


def changed_lines(repo: Path, sha: str) -> dict[str, list[int]] | None:
    """Per old path, the old-side line numbers the commit removed or changed.

    Whitespace-only changes, blank lines and comment-only lines are left out.
    Returns None if git show failed.
    """
    done = _git(
        repo,
        "show",
        "--format=",
        "--unified=0",
        "--no-color",
        "--no-ext-diff",
        "--no-textconv",
        "--src-prefix=a/",
        "--dst-prefix=b/",
        "-M",
        "-w",
        sha,
        "--",
    )
    if done.returncode != 0:
        return None
    diff = done.stdout
    out: dict[str, list[int]] = {}
    path, old_line, in_header = None, 0, False
    for line in diff.splitlines():
        # File headers come only between "diff --git" and the first hunk, so a removed
        # line that starts "--" (such as an SQL comment) is never read as one.
        if line.startswith("diff --git "):
            path, in_header = None, True
        elif in_header and line.startswith("--- "):
            path = _old_path(line[4:])
        elif line.startswith("@@"):
            in_header = False
            old_line = int(re.match(r"@@ -(\d+)", line).group(1))
        elif in_header:
            continue
        elif line.startswith("-") and path:
            content = line[1:]
            if content.strip() and not COMMENT.match(content):
                out.setdefault(path, []).append(old_line)
            old_line += 1
    return out


_ESCAPES = {
    "a": 7,
    "b": 8,
    "t": 9,
    "n": 10,
    "v": 11,
    "f": 12,
    "r": 13,
    '"': 34,
    "\\": 92,
}


def _old_path(header: str) -> str | None:
    """The path in a diff's "--- " header, or None for a new file (/dev/null).

    git ends the header with a tab when the path has a space, and wraps a path with
    quotes, backslashes or control characters in C-style quotes.
    """
    header = header.removesuffix("\t")
    if header.startswith('"') and header.endswith('"'):
        raw, body, i = bytearray(), header[1:-1], 0
        while i < len(body):
            if body[i] == "\\" and i + 1 < len(body):
                if body[i + 1] in "01234567":
                    raw.append(int(body[i + 1 : i + 4], 8))
                    i += 4
                    continue
                raw.append(_ESCAPES.get(body[i + 1], ord(body[i + 1])))
                i += 2
                continue
            raw += body[i].encode("utf-8", "surrogateescape")
            i += 1
        header = raw.decode("utf-8", "surrogateescape")
    return header[2:] if header.startswith("a/") else None


def _ranges(numbers: list[int]) -> list[str]:
    """Collapse line numbers into git blame -L ranges, so every line is blamed in one call."""
    ranges, start, prev = [], None, None
    for n in sorted(set(numbers)):
        if start is not None and n == prev + 1:
            prev = n
            continue
        if start is not None:
            ranges.append(f"{start},{prev}")
        start = prev = n
    if start is not None:
        ranges.append(f"{start},{prev}")
    return ranges


def blame(repo: Path, sha: str, path: str, numbers: list[int]) -> dict[str, int] | None:
    """The commits that last changed the given lines in sha's parent, with commit times.

    Returns {commit: unix committer time}, or None if git blame failed. Author and
    committer names and emails are read past, never kept.
    """
    args = ["blame", "--porcelain", "-w"]
    if (repo / IGNORE_REVS).is_file():
        args += ["--ignore-revs-file", IGNORE_REVS]
    for span in _ranges(numbers):
        args += ["-L", span]
    done = _git(repo, *args, f"{sha}^", "--", path)
    if done.returncode != 0:
        return None
    times, current = {}, None
    for line in done.stdout.splitlines():
        header = BLAME_HEADER.match(line)
        if header:
            current = header.group(1)
            times.setdefault(current, None)
        elif line.startswith("committer-time ") and current:
            times[current] = int(line.split()[1])
    return {c: t for c, t in times.items() if t is not None}


def clean_paths(links: dict) -> dict:
    """Per repo, a function from a path in the clone to its anonymised form, or None.

    Paths from a clone are raw data: a folder can be named after a person. So a path is
    used only when it is one link_scm.py already listed for that repo, from data
    anonymise.py cleaned, and then in that cleaned form. A cleaned path's [person] stands
    for any text within one folder name.
    """
    listed: dict[str, set[str]] = {}
    for defect in links["defects"].values():
        for item in defect.get("files") or []:
            listed.setdefault(item["repo"], set()).add(item["path"])

    def lookup_for(paths: set[str]):
        patterns = [
            (
                re.compile(re.escape(p).replace(re.escape(PLACEHOLDER), r"[^/]+?")),
                p,
            )
            for p in sorted(paths)
            if PLACEHOLDER in p
        ]

        def lookup(path: str) -> str | None:
            if path in paths and PLACEHOLDER not in path:
                return path
            return next((p for rx, p in patterns if rx.fullmatch(path)), None)

        return lookup

    return {repo: lookup_for(paths) for repo, paths in listed.items()}


def trace(links: dict, reported: dict, clones: dict) -> dict:
    """Find candidate introducers for every linked defect.

    Args:
        links: work/scm_links.json, as link_scm.link() returns it.
        reported: defect key -> aware datetime the defect was reported (created in Jira).
        clones: repo name (as in links) -> path of a local clone.
    Returns:
        {"defects": {key: {"traced", "candidates": [{"repo", "path"}]}}, "coverage":
         {...}, "since": links' since, "lag_days": sorted days from each traced defect's
         newest candidate to its report}. Paths are in their anonymised form. No commit
         id or commit time is kept, and the lags aren't keyed by defect, so nothing ties
         a defect to the commit (and so the person) blamed for it.
    """
    coverage = dict.fromkeys(COVERAGE_KEYS, 0)
    without_clone: set[str] = set()
    lookups = clean_paths(links)
    defects, lags = {}, []
    for key, defect in links["defects"].items():
        coverage["defects_linked"] += 1
        when = reported.get(key)
        cutoff = when.timestamp() if when else None
        found: dict[tuple, int] = {}
        if cutoff is None:
            # Without a report date nothing can be told apart from the fix itself.
            coverage["defects_without_report_date"] += 1
            defects[key] = {"traced": False, "candidates": []}
            continue
        for change in defect.get("changes") or []:
            repo_name = change["repo"]
            clone = clones.get(repo_name)
            if clone is None:
                without_clone.add(repo_name)
                continue
            clone = Path(clone)
            lookup = lookups.get(repo_name, lambda path: None)
            for sha in change.get("commits") or []:
                parents = _parents(clone, sha) if COMMIT_ID.fullmatch(sha) else None
                if parents is None:
                    coverage["commits_not_in_clone"] += 1
                    continue
                if len(parents) != 1:
                    coverage[
                        "merge_commits_skipped"
                        if parents
                        else "commits_with_nothing_to_blame"
                    ] += 1
                    continue
                changed = changed_lines(clone, sha)
                if changed is None:
                    coverage["blame_failures"] += 1
                    continue
                if not changed:
                    coverage["commits_with_nothing_to_blame"] += 1
                    continue
                coverage["fix_commits_blamed"] += 1
                for path, numbers in changed.items():
                    shown = lookup(path)
                    if shown is None:
                        coverage["paths_not_in_linked_changes"] += 1
                        continue
                    blamed = blame(clone, sha, path, numbers)
                    if blamed is None:
                        coverage["blame_failures"] += 1
                        continue
                    for commit, at in blamed.items():
                        if at >= cutoff:
                            coverage["candidates_after_report_dropped"] += 1
                            continue
                        found[(repo_name, commit, shown)] = at
        places = sorted({(repo_name, path) for repo_name, _commit, path in found})
        defects[key] = {
            "traced": bool(places),
            "candidates": [{"repo": r, "path": path} for r, path in places],
        }
        if found:
            coverage["defects_traced"] += 1
            lags.append(round((cutoff - max(found.values())) / 86400, 1))
    coverage["repos_without_clone"] = sorted(without_clone)
    # Lags are sorted and kept apart from their defects: a lag next to its defect gives
    # the day of the blamed commit, and so the commit and its author.
    return {
        "since": links.get("since"),
        "coverage": coverage,
        "defects": defects,
        "lag_days": sorted(lags),
    }


def build_records(result: dict, depth: int) -> list[dict]:
    """One record per (defect, repo, directory) with a candidate, so each defect counts once there."""
    records = []
    for defect in result["defects"].values():
        places = {
            (c["repo"], hotspots.directory_of(c["path"], depth))
            for c in defect["candidates"]
        }
        records += [{"repo": r, "directory": d} for r, d in sorted(places)]
    return records


def write_szz(
    result: dict, out_dir, depth: int = hotspots.DEFAULT_DEPTH, min_group_size=None
) -> None:
    """Write out/szz.json, .csv and .md, with every count suppressed by suppress.py.

    Args:
        result: as trace() returns it.
        out_dir: the run's out/ folder.
        depth: how many folder levels name a directory (default 2).
        min_group_size: threshold (default 5; below 5 is refused).
    Raises:
        ValueError: for a threshold below 5 or a depth below 1, before anything is written.
    """
    size = suppress.validate_min_group_size(min_group_size)
    depth = hotspots.validate_depth(depth)
    pub = suppress.publish(build_records(result, depth), GROUPINGS, size)
    coverage = result["coverage"]
    for name in COVERAGE_KEYS:
        pub.add_scalar(name, coverage[name])
    lags = result["lag_days"]
    summary = {
        **pub.summary,
        # A median of a handful of defects is close to one defect's own history, so it is
        # held back below the threshold, like any small count.
        "median_days_last_changed_to_reported": (
            round(statistics.median(lags), 1)
            if len(lags) >= size
            else suppress.SUPPRESSED
        ),
        # A count of repos, not of defects, and repo names stay in work/.
        "repos_without_clone": len(coverage["repos_without_clone"]),
    }
    table = pub.table(("repo", "directory"))
    rows = sorted(
        (
            {
                "repo": r["labels"]["repo"],
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
    doc = {
        "settings": {
            "note": ESTIMATE_NOTE,
            "min_group_size": size,
            "depth": depth,
            "since": result.get("since"),
            "count_rule": COUNT_RULE,
        },
        "suppressed_marker": suppress.SUPPRESSED,
        "summary": summary,
        "directories": rows,
        "suppressed_directories": hidden,
    }
    (out_dir / "szz.json").write_text(
        json.dumps(doc, indent=2) + "\n", encoding="utf-8"
    )

    columns = ["repo", "directory", "defects"]
    note = suppress.SUPPRESSED_NOTE.format(
        n=hidden, groups="group" if hidden == 1 else "groups", k=size
    )
    with (out_dir / "szz.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([row[c] for c in columns])
        if hidden:
            writer.writerow([note, "", ""])

    md = [
        "# Where defects were probably introduced (estimate)",
        "",
        ESTIMATE_NOTE,
        "",
        f"Each count is the number of defects with a candidate introducing line in the directory "
        f"(folders cut to depth {depth}), from fixes merged on or after {result.get('since')}. A defect "
        "counts once per directory and once in each directory it traced to, so the counts don't add "
        f"up to the number of defects. Groups with fewer than {size} defects are suppressed.",
        "",
        "## Summary",
        "",
    ]
    md += [f"- {k}: {v}" for k, v in summary.items()]
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
    (out_dir / "szz.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def parse_clones(values: list[str], links: dict) -> dict[str, Path]:
    """Turn --clone NAME=PATH values into {name: path}.

    Raises:
        ValueError: for a value without =, a name not in the links, or a path that isn't a git clone.
    """
    known = set(links.get("repos") or {}) | {
        c["repo"] for d in links["defects"].values() for c in d.get("changes") or []
    }
    clones = {}
    for value in values:
        name, sep, path = value.partition("=")
        if not sep or not name or not path:
            raise ValueError("each --clone must be NAME=PATH")
        if name not in known:
            raise ValueError(
                f"--clone names {name!r}, which isn't a repo in the links; use the name "
                "scm_coverage.md shows"
            )
        folder = Path(path).expanduser()
        if not (folder / ".git").exists():
            # The path isn't echoed: a local path can hold the user's name.
            raise ValueError(f"the --clone path for {name} is not a git clone")
        clones[name] = folder
    return clones


def reported_dates(clean_dir) -> dict:
    """Defect key -> when it was reported, from the created dates in clean/."""
    return {
        issue["key"]: when
        for issue in clean_data.load_clean_issues(clean_dir)
        if (when := ticket_signals.parse_time(issue["fields"].get("created")))
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Estimate where defects were introduced, with small groups suppressed."
    )
    ap.add_argument("--links", default="work/scm_links.json")
    ap.add_argument("--issues", default="clean")
    ap.add_argument(
        "--clone",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="a repo's name, as in the links, and its local clone; repeat for each repo",
    )
    ap.add_argument("--work", default="work/szz.json")
    ap.add_argument("--out", default="out")
    ap.add_argument("--depth", type=int, default=hotspots.DEFAULT_DEPTH)
    ap.add_argument("--min-group-size", type=int, default=None)
    ap.add_argument("--config", help="scm.yaml, for its min_group_size")
    a = ap.parse_args(argv)
    try:
        config = scm_config.load_config(a.config) if a.config else None
        configured = config.get("min_group_size") if config else None
        size = suppress.validate_min_group_size(a.min_group_size or configured)
        depth = hotspots.validate_depth(a.depth)
        links = json.loads(Path(a.links).read_text(encoding="utf-8"))
        if not isinstance(links, dict) or not isinstance(links.get("defects"), dict):
            raise ValueError(f"{a.links} has no defects; write it with link_scm.py")
        clones = parse_clones(a.clone, links)
        reported = reported_dates(a.issues)
    except (ValueError, OSError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    result = trace(links, reported, clones)
    work = Path(a.work)
    work.parent.mkdir(parents=True, exist_ok=True)
    work.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    write_szz(result, a.out, depth, size)
    c = result["coverage"]
    print(
        f"SZZ traced {c['defects_traced']} of {c['defects_linked']} linked defects (an estimate). "
        f"Wrote szz.json, .csv and .md -> {a.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
