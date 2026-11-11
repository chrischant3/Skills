#!/usr/bin/env python3
"""REST fallback for Jira ingestion: defects with full changelog and every comment.

Use it when the Atlassian MCP isn't available, or didn't return complete changelogs and
comments (clean/_ingest.json lists the gaps; pass those keys with --keys).

Usage:
  jira_changelog.py --deployment cloud --project ABC --out raw/
  jira_changelog.py --deployment datacenter --project ABC --issue-type Bug --label escaped --days 180 --out raw/
  jira_changelog.py --deployment cloud --keys ABC-1,ABC-7 --out raw/
  jira_changelog.py --deployment cloud --jql "project = ABC AND issuetype = Bug" --out raw/

Deployment (also settable as JIRA_DEPLOYMENT):
  cloud       POST /rest/api/3/search/jql, nextPageToken paging. Needs JIRA_BASE_URL,
              JIRA_EMAIL and JIRA_API_TOKEN.
  datacenter  POST /rest/api/2/search, startAt paging. Needs JIRA_BASE_URL and JIRA_PAT
              (a personal access token).

Writes raw/<KEY>.json per issue and raw/_manifest.json with the query and how many
defects matched. Credentials are read from the environment and never written. Retries
HTTP 429 after the Retry-After delay. Standard library only.
"""

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

import rest_transport
from rest_transport import DEFAULT_RETRY_AFTER, urllib_transport  # noqa: F401  (kept importable from here)

MANIFEST_NAME = "_manifest.json"
DEFAULT_WINDOW_DAYS = 365
PAGE_SIZE = 100
FIELDS = [
    "summary",
    "description",
    "issuetype",
    "status",
    "priority",
    "labels",
    "components",
    "project",
    "created",
    "updated",
    "resolutiondate",
    "resolution",
    "issuelinks",
    "assignee",
    "reporter",
    "creator",
    "comment",
    "fixVersions",
    "versions",
]
DEPLOYMENTS = {"cloud", "datacenter"}
PROJECT_KEY = re.compile(r"[A-Z][A-Z0-9_]+")
ISSUE_KEY = re.compile(r"[A-Z][A-Z0-9_]+-\d+")


def _quote(value: str) -> str:
    if any(c in value for c in '"\\\n'):
        raise ValueError(
            f"value {value!r} contains characters that could change the query"
        )
    return f'"{value}"'


def build_jql(
    projects, issue_types=("Bug",), labels=(), window_days=DEFAULT_WINDOW_DAYS
) -> str:
    """Build the defect query.

    Args:
        projects: Jira project keys.
        issue_types: issue types that count as defects (default Bug). Pass [] to use labels only.
        labels: labels that also mark a defect.
        window_days: how far back to look, by created date (default 365).
    Raises:
        ValueError: for a malformed project key or a value that could alter the query.
    """
    if not projects or not all(
        isinstance(p, str) and PROJECT_KEY.fullmatch(p) for p in projects
    ):
        raise ValueError(f"project keys must look like ABC; got {projects!r}")
    if not isinstance(window_days, int) or window_days <= 0:
        raise ValueError("window_days must be a positive whole number")
    conditions = []
    if issue_types:
        conditions.append(f"issuetype in ({', '.join(_quote(t) for t in issue_types)})")
    if labels:
        conditions.append(f"labels in ({', '.join(_quote(label) for label in labels)})")
    if not conditions:
        raise ValueError("give at least one issue type or label that marks a defect")
    defect = (
        conditions[0] if len(conditions) == 1 else "(" + " OR ".join(conditions) + ")"
    )
    project = f"project in ({', '.join(_quote(p) for p in projects)})"
    return f"{project} AND {defect} AND created >= -{window_days}d ORDER BY created ASC"


def jql_for_keys(keys) -> str:
    """Query for specific issues, for filling gaps the MCP left."""
    if not keys or not all(ISSUE_KEY.fullmatch(k) for k in keys):
        raise ValueError(f"issue keys must look like ABC-123; got {keys!r}")
    return f"key in ({', '.join(keys)}) ORDER BY key ASC"


class JiraClient:
    """A small Jira REST client for Cloud or Data Center.

    Args:
        base_url: e.g. https://your-site.atlassian.net
        deployment: "cloud" or "datacenter".
        auth_header: the full Authorization header value. Never logged or written.
        transport: callable(method, url, headers, body, timeout) -> (status, headers, body);
            tests pass a recorded one.
        sleep: called with seconds to wait on HTTP 429.
        max_retries: 429 retries per request before giving up.
        extra_fields: extra field ids to request, such as an acceptance criteria custom field.
    """

    def __init__(
        self,
        base_url,
        deployment,
        auth_header,
        transport=urllib_transport,
        sleep=time.sleep,
        max_retries=5,
        extra_fields=(),
    ):
        if deployment not in DEPLOYMENTS:
            raise ValueError(
                f"deployment must be cloud or datacenter, got {deployment!r}"
            )
        self.base_url = base_url.rstrip("/")
        self.deployment = deployment
        self._auth = auth_header
        self._transport = transport
        self._sleep = sleep
        self._max_retries = max_retries
        self.fields = FIELDS + [f for f in extra_fields if f not in FIELDS]
        self.api = "/rest/api/3" if deployment == "cloud" else "/rest/api/2"

    def request(self, method, path, params=None, body=None) -> dict:
        """Send a request, retrying 429s. Returns parsed JSON. Raises RuntimeError on other errors."""
        url = (
            self.base_url
            + path
            + ("?" + urllib.parse.urlencode(params) if params else "")
        )
        headers = {"Authorization": self._auth, "Accept": "application/json"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        for _ in range(self._max_retries + 1):
            status, resp_headers, raw = self._transport(method, url, headers, data, 60)
            if status == 429:
                self._sleep(rest_transport.retry_after(resp_headers))
                continue
            if status >= 400:
                raise RuntimeError(f"Jira returned HTTP {status} for {method} {path}")
            return json.loads(raw or b"{}")
        raise RuntimeError(
            f"Jira rate limit still in force after {self._max_retries} retries for {method} {path}"
        )

    def search(self, jql):
        """Yield every issue matching jql, then return the total Jira reported (None on Cloud)."""
        if self.deployment == "cloud":
            token = None
            while True:
                body = {
                    "jql": jql,
                    "maxResults": PAGE_SIZE,
                    "fields": self.fields,
                    "expand": "changelog",
                }
                if token:
                    body["nextPageToken"] = token
                page = self.request("POST", f"{self.api}/search/jql", body=body)
                yield from page.get("issues", [])
                token = page.get("nextPageToken")
                if not token or page.get("isLast"):
                    return None
        start, total = 0, None
        while True:
            page = self.request(
                "POST",
                f"{self.api}/search",
                body={
                    "jql": jql,
                    "startAt": start,
                    "maxResults": PAGE_SIZE,
                    "fields": self.fields,
                    "expand": ["changelog"],
                },
            )
            issues = page.get("issues", [])
            total = page.get("total", total)
            yield from issues
            start += len(issues)
            if not issues or (total is not None and start >= total):
                return total

    def full_changelog(self, key) -> list:
        """Every changelog entry for an issue."""
        if self.deployment == "datacenter":
            issue = self.request(
                "GET",
                f"{self.api}/issue/{key}",
                params={"expand": "changelog", "fields": "summary"},
            )
            return (issue.get("changelog") or {}).get("histories", [])
        start, out = 0, []
        while True:
            page = self.request(
                "GET",
                f"{self.api}/issue/{key}/changelog",
                params={"startAt": start, "maxResults": PAGE_SIZE},
            )
            values = page.get("values", [])
            out.extend(values)
            start += len(values)
            if page.get("isLast", True) or not values:
                return out

    def all_comments(self, key) -> list:
        """Every comment on an issue, not the capped list embedded in search results."""
        start, out = 0, []
        while True:
            page = self.request(
                "GET",
                f"{self.api}/issue/{key}/comment",
                params={"startAt": start, "maxResults": PAGE_SIZE},
            )
            comments = page.get("comments", [])
            out.extend(comments)
            start += len(comments)
            if not comments or start >= page.get("total", start):
                return out


def _has_all(container, items_key) -> bool:
    if not isinstance(container, dict) or not isinstance(
        container.get(items_key), list
    ):
        return False
    total = container.get("total")
    return isinstance(total, int) and total <= len(container[items_key])


def fetch(client: JiraClient, jql: str, out_dir, write_manifest: bool = True) -> dict:
    """Fetch every matching issue, complete its changelog and comments, and write raw files.

    Returns the manifest: source, deployment, jql, matched and fetched counts.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fetched = 0
    results = client.search(jql)
    total = None
    while True:
        try:
            issue = next(results)
        except StopIteration as done:
            total = done.value
            break
        key = issue["key"]
        if not ISSUE_KEY.fullmatch(key):
            raise RuntimeError(f"unexpected issue key {key!r}")
        if not _has_all(issue.get("changelog"), "histories"):
            histories = client.full_changelog(key)
            issue["changelog"] = {
                "startAt": 0,
                "maxResults": len(histories),
                "total": len(histories),
                "histories": histories,
            }
        fields = issue.setdefault("fields", {})
        if not _has_all(fields.get("comment"), "comments"):
            comments = client.all_comments(key)
            fields["comment"] = {
                "startAt": 0,
                "maxResults": len(comments),
                "total": len(comments),
                "comments": comments,
            }
        issue["_ingest"] = {
            "source": "rest",
            "changelog_complete": True,
            "comments_complete": True,
        }
        (out_dir / f"{key}.json").write_text(
            json.dumps(issue, indent=2), encoding="utf-8"
        )
        fetched += 1
    manifest = {
        "source": "rest",
        "deployment": client.deployment,
        "jql": jql,
        "matched": total if isinstance(total, int) else fetched,
        "fetched": fetched,
    }
    if write_manifest:
        (out_dir / MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
    return manifest


def _auth_from_env(deployment: str) -> str:
    if deployment == "cloud":
        token = base64.b64encode(
            f"{os.environ['JIRA_EMAIL']}:{os.environ['JIRA_API_TOKEN']}".encode()
        ).decode()
        return f"Basic {token}"
    return f"Bearer {os.environ['JIRA_PAT']}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--deployment",
        default=os.environ.get("JIRA_DEPLOYMENT"),
        choices=sorted(DEPLOYMENTS),
    )
    ap.add_argument(
        "--project", action="append", default=[], help="project key; repeat for several"
    )
    ap.add_argument(
        "--issue-type",
        action="append",
        default=None,
        help="defect issue type (default Bug); repeat for several",
    )
    ap.add_argument(
        "--label",
        action="append",
        default=[],
        help="label that also marks a defect; repeat for several",
    )
    ap.add_argument(
        "--days",
        type=int,
        default=DEFAULT_WINDOW_DAYS,
        help="window by created date (default 365)",
    )
    ap.add_argument(
        "--keys", help="comma-separated issue keys to fetch, to fill gaps the MCP left"
    )
    ap.add_argument(
        "--jql", help="a full query instead of --project/--issue-type/--label/--days"
    )
    ap.add_argument(
        "--extra-field",
        action="append",
        default=[],
        help="extra field id, e.g. customfield_10010",
    )
    ap.add_argument("--out", default="raw")
    a = ap.parse_args(argv)
    if not a.deployment:
        ap.error("set --deployment or JIRA_DEPLOYMENT to cloud or datacenter")
    if a.keys:
        jql = jql_for_keys([k.strip() for k in a.keys.split(",") if k.strip()])
    elif a.jql:
        jql = a.jql
    else:
        types = (
            a.issue_type if a.issue_type is not None else ([] if a.label else ["Bug"])
        )
        jql = build_jql(a.project, types, a.label, a.days)
    missing = [
        v
        for v in (
            ["JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"]
            if a.deployment == "cloud"
            else ["JIRA_BASE_URL", "JIRA_PAT"]
        )
        if not os.environ.get(v)
    ]
    if missing:
        ap.error("missing environment variables: " + ", ".join(missing))
    client = JiraClient(
        os.environ["JIRA_BASE_URL"],
        a.deployment,
        _auth_from_env(a.deployment),
        extra_fields=a.extra_field,
    )
    manifest = fetch(client, jql, a.out, write_manifest=not a.keys)
    print(
        f"Fetched {manifest['fetched']} of {manifest['matched']} matching issues -> {a.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
