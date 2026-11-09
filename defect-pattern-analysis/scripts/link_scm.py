#!/usr/bin/env python3
"""Link defects to the merged changes that mention them, and report link coverage per repo.

Usage: link_scm.py --config scm.yaml --issues clean/ --work work/scm_links.json --out out/
                   [--since 2026-01-31] [--min-group-size 5]

Reads only anonymised data from clean/: the Jira defects and the source control
documents that anonymise.py wrote (raw data is refused). For each configured repo, the
platform's adapter turns those documents into changes, and the repo's key_pattern (or
the config's default_key_pattern, or the standard Jira key format) finds issue keys in
each change's title, description, source branch and commit messages. Only keys of
defects in the run count.

The window starts at --since, or by default at the earliest created date among the
defects in clean/, so it follows the run's own time window. Changes merged before it
are not scanned.

Writes:
- work/scm_links.json: per defect, its repos, changes, commits and files changed; per
  repo, changes scanned, changes linked and defects linked. It holds ticket keys, so it
  is working data, never a report.
- out/scm_coverage.json, .csv and .md: link coverage per repo, every count through
  suppress.py. A defect linked from several repos counts once, under "multiple repos",
  so the repo rows add up to the total.

Works the same for GitLab and Azure DevOps. Repos on platforms that aren't ready yet are listed as skipped.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import clean_data
import scm_adapter
import scm_config
import scm_keys
import suppress

MULTIPLE_REPOS = "multiple repos"


def _label(repo: dict) -> str:
    """A name for a repo whose platform has no adapter yet."""
    return str(repo.get("repo") or repo.get("project") or repo.get("platform"))


def link(config: dict, clean_dir, since: str | None = None) -> dict:
    """Link every defect in clean_dir to the changes that mention it.

    Args:
        config: as scm_config.load_config() returns it.
        clean_dir: the run's clean/ folder (anonymised Jira and source control data).
        since: ISO date the window starts on; default the earliest defect's created date.
    Returns:
        {"since", "defects_total", "defects_linked", "repos": {name: coverage}, "skipped": [...],
         "defects": {key: {"repos", "changes", "commits", "files"}}}
    Raises:
        ValueError: if clean_dir holds raw data, two repos share a name, or there is no window.
    """
    issues = clean_data.load_clean_issues(clean_dir)
    documents = clean_data.load_clean_documents(clean_dir)
    defect_keys = {i["key"] for i in issues}
    projects = {k.split("-")[0] for k in defect_keys}
    since = since or clean_data.earliest_created(issues)
    if not since:
        raise ValueError("no defects in clean/ to take the window from; pass --since")

    coverage, skipped, defects = {}, [], {}
    for repo in config["repos"]:
        platform = repo["platform"]
        if not scm_adapter.is_ready(platform):
            skipped.append({"repo": _label(repo), "platform": platform, "reason": "not ready yet"})
            continue
        adapter = scm_adapter.adapter_for(platform)
        name = adapter.repo_name(repo, documents)
        if name in coverage:
            raise ValueError(f"two repos have the same name {name!r}; each repo must be listed once")
        matcher = scm_keys.KeyMatcher(repo.get("key_pattern") or config.get("default_key_pattern"), projects)
        scanned, linked, repo_defects = 0, 0, set()
        for change in adapter.changes(documents, repo):
            if not (change.merged_at or "")[:10] >= since:
                continue
            scanned += 1
            keys = set().union(*(matcher.find(t) for t in change.texts())) & defect_keys
            if keys:
                linked += 1
            for key in keys:
                repo_defects.add(key)
                _add_change(defects.setdefault(key, {"repos": [], "changes": [], "commits": [], "files": []}), change)
        coverage[name] = {"platform": platform, "team": repo.get("team"), "changes_scanned": scanned,
                          "changes_linked": linked, "defects_linked": len(repo_defects)}
    ordered = {k: defects[k] for k in sorted(defects, key=lambda k: (k.split("-")[0], int(k.split("-")[1])))}
    return {"since": since, "defects_total": len(defect_keys), "defects_linked": len(ordered), "repos": coverage,
            "skipped": skipped, "defects": ordered}


def _add_change(entry: dict, change) -> None:
    if change.repo not in entry["repos"]:
        entry["repos"].append(change.repo)
    entry["changes"].append({"repo": change.repo, "kind": change.kind, "id": change.id, "merged_at": change.merged_at})
    for commit in change.commits:
        if commit["id"] not in entry["commits"]:
            entry["commits"].append(commit["id"])
    for path in change.files:
        item = {"repo": change.repo, "path": path}
        if item not in entry["files"]:
            entry["files"].append(item)


def write_coverage(links: dict, out_dir, min_group_size=None) -> None:
    """Write out/scm_coverage.json, .csv and .md, with every count suppressed by suppress.py.

    Args:
        links: as link() returns it.
        out_dir: the run's out/ folder.
        min_group_size: threshold (default 5; below 5 is refused).
    """
    size = suppress.validate_min_group_size(min_group_size)
    records = [{"repo": d["repos"][0] if len(d["repos"]) == 1 else MULTIPLE_REPOS} for d in links["defects"].values()]
    pub = suppress.publish(records, [(), ("repo",)], size)
    pub.add_scalar("defects_in_run", links["defects_total"])
    pub.add_cell("defects_linked", frozenset())
    linked, total = pub.summary["defects_linked"], pub.summary["defects_in_run"]
    rate = round(linked / total, 3) if isinstance(linked, int) and isinstance(total, int) and total else suppress.SUPPRESSED
    summary = {**pub.summary, "defect_link_rate": rate}

    rows = [{"repo": name, "team": cov.get("team"), "changes_scanned": pub.scalar(cov["changes_scanned"]),
             "changes_linked": pub.scalar(cov["changes_linked"]),
             "defects_linked": pub.value(frozenset({("repo", name)}))} for name, cov in links["repos"].items()]
    if any(r["repo"] == MULTIPLE_REPOS for r in records):
        rows.append({"repo": MULTIPLE_REPOS, "team": None, "changes_scanned": "", "changes_linked": "",
                     "defects_linked": pub.value(frozenset({("repo", MULTIPLE_REPOS)}))})
    hidden = sum(r["defects_linked"] == suppress.SUPPRESSED for r in rows)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = {"settings": {"min_group_size": size, "since": links["since"]}, "suppressed_marker": suppress.SUPPRESSED,
           "summary": summary, "repos": rows, "skipped": links["skipped"]}
    (out_dir / "scm_coverage.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    columns = ["repo", "team", "changes_scanned", "changes_linked", "defects_linked"]
    with (out_dir / "scm_coverage.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([row[c] if row[c] is not None else "" for c in columns])

    md = ["# Source control link coverage", "", f"Changes merged on or after {links['since']}. "
          f"Groups with fewer than {size} defects are suppressed.", "", "## Summary", ""]
    md += [f"- {k}: {v}" for k, v in summary.items()] + ["", "## Repos", "",
                                                         "| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    md += ["| " + " | ".join("" if row[c] is None else str(row[c]) for c in columns) + " |" for row in rows]
    if hidden:
        md += ["", suppress.SUPPRESSED_NOTE.format(n=hidden, groups="group" if hidden == 1 else "groups", k=size)]
    if links["skipped"]:
        md += ["", "## Not linked yet", ""] + [f"- {s['repo']} ({s['platform']}): {s['reason']}" for s in links["skipped"]]
    (out_dir / "scm_coverage.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Link defects to merged changes and report coverage per repo.")
    ap.add_argument("--config", default="scm.yaml")
    ap.add_argument("--issues", default="clean")
    ap.add_argument("--work", default="work/scm_links.json")
    ap.add_argument("--out", default="out")
    ap.add_argument("--since", help="ISO date the window starts on (default: the earliest defect in clean/)")
    ap.add_argument("--min-group-size", type=int, default=None)
    a = ap.parse_args(argv)
    try:
        config = scm_config.load_config(a.config)
        size = suppress.validate_min_group_size(a.min_group_size or config.get("min_group_size"))
        links = link(config, a.issues, a.since)
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    work = Path(a.work)
    work.parent.mkdir(parents=True, exist_ok=True)
    work.write_text(json.dumps(links, indent=2) + "\n", encoding="utf-8")
    write_coverage(links, a.out, size)
    print(f"Linked {links['defects_linked']} of {links['defects_total']} defects since {links['since']}. "
          f"Links -> {work}, coverage -> {a.out}/scm_coverage.md")
    for s in links["skipped"]:
        print(f"Skipped {s['repo']} ({s['platform']}): {s['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
