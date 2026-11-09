#!/usr/bin/env python3
"""Usage: jira_changelog.py --jql "project = ABC AND issuetype = Bug AND created >= -365d" --out raw/"""
import argparse, json, os, time
from pathlib import Path
import requests

BASE = os.environ["JIRA_BASE_URL"].rstrip("/")
AUTH = (os.environ["JIRA_EMAIL"], os.environ["JIRA_API_TOKEN"])
FIELDS = ["summary", "description", "issuetype", "status", "priority", "labels",
          "components", "created", "resolutiondate", "resolution", "issuelinks",
          "assignee", "reporter", "comment", "fixVersions", "customfield_*"]

def search(jql, page_size=100):
    token = None
    while True:
        body = {"jql": jql, "maxResults": page_size, "fields": FIELDS, "expand": "changelog"}
        if token:
            body["nextPageToken"] = token
        r = requests.post(f"{BASE}/rest/api/3/search/jql", json=body, auth=AUTH, timeout=60)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 10)))
            continue
        r.raise_for_status()
        data = r.json()
        yield from data.get("issues", [])
        token = data.get("nextPageToken")
        if not token:
            break

def full_changelog(key):
    """Search results cap changelog length; page the rest."""
    start, out = 0, []
    while True:
        r = requests.get(f"{BASE}/rest/api/3/issue/{key}/changelog",
                         params={"startAt": start, "maxResults": 100}, auth=AUTH, timeout=60)
        r.raise_for_status()
        d = r.json()
        out.extend(d.get("values", []))
        if d.get("isLast", True):
            return out
        start += len(d.get("values", []))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jql", required=True)
    ap.add_argument("--out", default="raw")
    a = ap.parse_args()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    n = 0
    for issue in search(a.jql):
        cl = issue.get("changelog", {})
        if cl.get("total", 0) > len(cl.get("histories", [])):
            issue["changelog"] = {"histories": full_changelog(issue["key"])}
        Path(a.out, f"{issue['key']}.json").write_text(json.dumps(issue, indent=2))
        n += 1
    print(f"Fetched {n} issues -> {a.out}")

if __name__ == "__main__":
    main()
