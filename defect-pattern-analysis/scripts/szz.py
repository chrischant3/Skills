#!/usr/bin/env python3
"""Usage: szz.py --links clean/links.json --clones clones/ --issues clean/ --out clean/szz.json"""

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

COMMENT = re.compile(r"^\s*(#|//|/\*|\*|--)")


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    ).stdout


def changed_lines(repo, sha):
    """Old-side line numbers removed/modified by a commit, per file."""
    diff = git(repo, "show", "--unified=0", "--no-color", "-w", sha)
    out, path, old_line = defaultdict(list), None, 0
    for line in diff.splitlines():
        if line.startswith("--- a/"):
            path = line[6:]
        elif line.startswith("--- /dev/null"):
            path = None
        elif line.startswith("@@") and path:
            old_line = int(re.match(r"@@ -(\d+)", line).group(1))
        elif line.startswith("-") and not line.startswith("---") and path:
            content = line[1:]
            if content.strip() and not COMMENT.match(content):
                out[path].append(old_line)
            old_line += 1
    return out


def blame(repo, sha, path, lines):
    args = ["blame", "--porcelain", "-w"]
    if (Path(repo) / ".git-blame-ignore-revs").exists():
        args += ["--ignore-revs-file", ".git-blame-ignore-revs"]
    for n in lines:
        args += ["-L", f"{n},{n}"]
    raw = git(repo, *args, f"{sha}^", "--", path)
    commits, times = set(), {}
    for line in raw.splitlines():
        m = re.match(r"^([0-9a-f]{40}) ", line)
        if m:
            cur = m.group(1)
            commits.add(cur)
        elif line.startswith("committer-time "):
            times[cur] = int(line.split()[1])
    return {c: times.get(c) for c in commits}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--links", default="clean/links.json")
    ap.add_argument("--clones", default="clones")
    ap.add_argument("--issues", default="clean")
    ap.add_argument("--out", default="clean/szz.json")
    a = ap.parse_args()
    links = json.loads(Path(a.links).read_text())["links"]
    dir_counts, lags, per_issue = Counter(), [], {}
    for key, changes in links.items():
        issue = json.loads(Path(a.issues, f"{key}.json").read_text())
        reported = datetime.fromisoformat(
            issue["fields"]["created"].replace("Z", "+00:00")
        ).timestamp()
        introducers = {}
        for ch in changes:
            repo = Path(a.clones, ch["repo"].split("/")[-1])
            if not repo.exists():
                continue
            for sha in ch["commits"]:
                for path, lines in changed_lines(repo, sha).items():
                    if not lines:
                        continue
                    for c, t in blame(repo, sha, path, lines[:200]).items():
                        if t and t < reported:
                            introducers[c] = (path, t)
        for c, (path, t) in introducers.items():
            dir_counts[str(Path(path).parent)] += 1
            lags.append((reported - t) / 86400)
        per_issue[key] = sorted({str(Path(p).parent) for p, _ in introducers.values()})
    lags.sort()
    out = {
        "estimate_note": "SZZ output is an estimate. Treat hotspots as prompts for conversation, not facts.",
        "introduction_hotspots": dir_counts.most_common(25),
        "median_days_introduced_to_reported": lags[len(lags) // 2] if lags else None,
        "per_issue_dirs": per_issue,
    }
    Path(a.out).write_text(json.dumps(out, indent=2))
    print(
        f"SZZ traced {sum(1 for v in per_issue.values() if v)}/{len(links)} linked defects"
    )


if __name__ == "__main__":
    main()
