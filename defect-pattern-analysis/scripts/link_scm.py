#!/usr/bin/env python3
"""Usage: link_scm.py --config scm.yaml --issues clean/ --out clean/links.json"""
import argparse, base64, json, os, re
from collections import defaultdict
from pathlib import Path
import requests, yaml

def norm_key(raw):
    m = re.match(r"([A-Za-z][A-Za-z0-9]*)[-_ ]?(\d+)", raw)
    return f"{m.group(1).upper()}-{m.group(2)}" if m else None

def find_keys(text, pattern):
    return {k for k in (norm_key(x) for x in re.findall(pattern, text or "", re.I)) if k}

# ---------- GitLab ----------
def gitlab(repo, since):
    base = repo["url"].rstrip("/") + "/api/v4"
    pid = requests.utils.quote(repo["project"], safe="")
    h = {"PRIVATE-TOKEN": os.environ["GITLAB_TOKEN"]}
    def pages(path, params):
        page = 1
        while True:
            r = requests.get(f"{base}{path}", headers=h, params={**params, "per_page": 100, "page": page}, timeout=60)
            r.raise_for_status()
            items = r.json()
            if not items:
                return
            yield from items
            page += 1
    for mr in pages(f"/projects/{pid}/merge_requests", {"state": "merged", "updated_after": since}):
        text = " ".join([mr.get("title", ""), mr.get("source_branch", ""), mr.get("description") or ""])
        changes = requests.get(f"{base}/projects/{pid}/merge_requests/{mr['iid']}/diffs", headers=h, timeout=60)
        files = [d["new_path"] for d in changes.json()] if changes.ok else []
        commits = requests.get(f"{base}/projects/{pid}/merge_requests/{mr['iid']}/commits", headers=h, timeout=60)
        cs = commits.json() if commits.ok else []
        text += " " + " ".join(c.get("message", "") for c in cs)
        yield {"kind": "mr", "id": mr["iid"], "text": text, "files": files,
               "commits": [c["id"] for c in cs], "merged_at": mr.get("merged_at")}

# ---------- Azure DevOps ----------
def azure(repo, since):
    base = f"https://dev.azure.com/{repo['org']}/{repo['project']}/_apis/git/repositories/{repo['repo']}"
    tok = base64.b64encode(f":{os.environ['AZDO_PAT']}".encode()).decode()
    h = {"Authorization": f"Basic {tok}"}
    v = {"api-version": "7.1"}
    skip = 0
    while True:
        r = requests.get(f"{base}/pullrequests", headers=h, timeout=60,
                         params={**v, "searchCriteria.status": "completed", "$top": 100, "$skip": skip})
        r.raise_for_status()
        prs = r.json().get("value", [])
        if not prs:
            return
        for pr in prs:
            if pr.get("closedDate", "") < since:
                continue
            pid = pr["pullRequestId"]
            text = " ".join([pr.get("title", ""), pr.get("sourceRefName", ""), pr.get("description") or ""])
            cs = requests.get(f"{base}/pullRequests/{pid}/commits", headers=h, params=v, timeout=60).json().get("value", [])
            text += " " + " ".join(c.get("comment", "") for c in cs)
            its = requests.get(f"{base}/pullRequests/{pid}/iterations", headers=h, params=v, timeout=60).json().get("value", [])
            files = []
            if its:
                ch = requests.get(f"{base}/pullRequests/{pid}/iterations/{its[-1]['id']}/changes",
                                  headers=h, params=v, timeout=60).json()
                files = [c["item"]["path"].lstrip("/") for c in ch.get("changeEntries", []) if "item" in c]
            yield {"kind": "pr", "id": pid, "text": text, "files": files,
                   "commits": [c["commitId"] for c in cs], "merged_at": pr.get("closedDate")}
        skip += len(prs)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="scm.yaml")
    ap.add_argument("--issues", default="clean")
    ap.add_argument("--since", default="2025-01-01")
    ap.add_argument("--out", default="clean/links.json")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config))
    defects = {p.stem for p in Path(a.issues).glob("*-*.json")}
    links, coverage = defaultdict(list), {}
    for repo in cfg["repos"]:
        pattern = repo.get("key_pattern", cfg["default_key_pattern"])
        fetch = gitlab if repo["platform"] == "gitlab" else azure
        name = repo.get("project") if repo["platform"] == "gitlab" else repo["repo"]
        total = matched = 0
        for change in fetch(repo, a.since):
            total += 1
            keys = find_keys(change["text"], pattern) & defects
            if keys:
                matched += 1
            for k in keys:
                links[k].append({"repo": name, "team": repo.get("team"), **{x: change[x] for x in ("kind", "id", "files", "commits", "merged_at")}})
        coverage[name] = {"changes": total, "linked_to_defects": matched}
    linked = len(links)
    out = {"links": links, "coverage": coverage,
           "defects_total": len(defects), "defects_linked": linked,
           "defect_link_rate": round(linked / max(len(defects), 1), 3)}
    Path(a.out).write_text(json.dumps(out, indent=2))
    print(f"Linked {linked}/{len(defects)} defects. Per repo: {coverage}")

if __name__ == "__main__":
    main()
