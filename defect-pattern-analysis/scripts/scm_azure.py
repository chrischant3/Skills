#!/usr/bin/env python3
"""Azure DevOps adapter: completed pull requests, with every commit and changed file.

Raw files, written by the REST fallback here or saved by Claude from an Azure DevOps MCP:
  azure-prs-<anything>.json                              pull requests (a list page, or one)
  azure-pr-<repository id>-<pr id>-commits[-N].json      one page of a pull request's commits
  azure-pr-<repository id>-<pr id>-changes[-N].json      one page of its last iteration's changes
  azure-pr-<repository id>-<pr id>-commits-full-<sha>.json  one commit in full, when the list cut its message short

The repository id is the GUID in each pull request's repository.id. Any of these may be
an MCP text block holding the JSON; anonymise.py decodes those. Status may be the word
"completed" (REST) or the number 3 (clients that report the enum as a number); only
completed pull requests count, and closedDate is when they merged.

The REST fallback pages everything: pull requests by $top and $skip, commits by
continuation token (x-ms-continuationtoken), and the last iteration's changes by
nextSkip. Commit lists cut long messages short and set commentTruncated, so a key near
the end would be missed; for those commits it also fetches the full commit. It retries
HTTP 429 after Retry-After. It needs AZDO_PAT, a personal access
token with Code (Read), sent as a Basic auth header and never written or logged.

Names: a repo is shown as <project>/<repo> in every output. The org is never part of a
name, so even an org named after a person (such as a personal organisation) can't reach
work/ or out/. Project and repo names come from scm.yaml and are shown as written there.
Azure DevOps has no personal namespaces like GitLab's, so there is no owner to remove.
"""

import base64
import json
import re
import time
import urllib.parse
from pathlib import Path

import rest_transport
from scm_adapter import Change, SourceControlAdapter

API_VERSION = "7.1"
PAGE_SIZE = 100
BASE_URL = "https://dev.azure.com"
GUID = r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}"
PR_FILE = re.compile(r"azure-prs-[\w.-]*\.json")
PART_FILE = re.compile(rf"azure-pr-({GUID})-(\d+)-(commits|changes)(?:-[\w.-]+)?\.json")
COMPLETED = ("completed", 3)
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
ORG_IN_URL = (re.compile(r"https?://dev\.azure\.com/([^/]+)/", re.I), re.compile(r"https?://([^./]+)\.visualstudio\.com/", re.I))


class AzureDevOpsClient:
    """A small Azure DevOps REST client for one organisation.

    Args:
        org: the organisation name, as in https://dev.azure.com/<org>.
        token: personal access token, sent as Basic auth. Never logged or written.
        transport: callable(method, url, headers, body, timeout) -> (status, headers, body);
            tests pass a recorded one.
        sleep: called with seconds to wait on HTTP 429.
        max_retries: 429 retries per request before giving up.
        page_size: $top for paged lists.
        base_url: the service root, https://dev.azure.com by default.
    """

    def __init__(self, org, token, transport=rest_transport.urllib_transport, sleep=time.sleep, max_retries=5,
                 page_size=PAGE_SIZE, base_url=BASE_URL):
        self.root = f"{base_url.rstrip('/')}/{urllib.parse.quote(org, safe='')}"
        self._auth = "Basic " + base64.b64encode(f":{token}".encode()).decode()
        self._transport = transport
        self._sleep = sleep
        self._max_retries = max_retries
        self.page_size = page_size

    def get(self, path, params=None):
        """GET one resource and return (parsed JSON, response headers)."""
        query = urllib.parse.urlencode({**(params or {}), "api-version": API_VERSION})
        url = f"{self.root}{path}?{query}"
        headers = {"Authorization": self._auth, "Accept": "application/json"}
        for _ in range(self._max_retries + 1):
            status, resp_headers, raw = self._transport("GET", url, headers, None, 60)
            if status == 429:
                self._sleep(rest_transport.retry_after(resp_headers))
                continue
            if status >= 400:
                raise RuntimeError(f"Azure DevOps returned HTTP {status} for GET {path}")
            return json.loads(raw or b"{}"), resp_headers
        raise RuntimeError(f"Azure DevOps rate limit still in force after {self._max_retries} retries for GET {path}")

    def skip_pages(self, path, params=None):
        """Yield each page body of a list paged by $top and $skip; a short page is the last."""
        skip = 0
        while True:
            body, _ = self.get(path, {**(params or {}), "$top": self.page_size, "$skip": skip})
            yield body
            count = len(body.get("value") or [])
            if count < self.page_size:
                return
            skip += count

    def token_pages(self, path, params=None):
        """Yield each page body of a list paged by the x-ms-continuationtoken header."""
        token = None
        while True:
            extra = {"continuationToken": token} if token else {}
            body, headers = self.get(path, {**(params or {}), "$top": self.page_size, **extra})
            yield body
            token = rest_transport.header(headers, "x-ms-continuationtoken")
            if not token:
                return

    def change_pages(self, path):
        """Yield each page body of an iteration's changes, following nextSkip until it runs out."""
        skip, top = 0, self.page_size
        while True:
            body, _ = self.get(path, {"$top": top, "$skip": skip})
            yield body
            if not body.get("nextSkip"):
                return
            skip, top = int(body["nextSkip"]), int(body.get("nextTop") or self.page_size)


def _items(doc) -> list:
    """The records a raw or clean document holds, whatever wrapper it arrived in."""
    if isinstance(doc, list):
        return [x for item in doc for x in (_items(item) if isinstance(item, list) else [item])]
    if isinstance(doc, dict):
        for key in ("value", "changeEntries", "items", "pullRequests", "commits", "changes"):
            if isinstance(doc.get(key), list) and "pullRequestId" not in doc:
                return _items(doc[key])
        return [doc]
    return []


def _org_of(pr: dict) -> str | None:
    """The organisation in a pull request's URLs, if they show it."""
    for url in (pr.get("url"), (pr.get("repository") or {}).get("url")):
        for pattern in ORG_IN_URL:
            found = pattern.match(url) if isinstance(url, str) else None
            if found:
                return urllib.parse.unquote(found.group(1))
    return None


def _belongs_to(pr: dict, repo: dict) -> bool:
    repository = pr.get("repository") if isinstance(pr.get("repository"), dict) else {}
    project = repository.get("project") if isinstance(repository.get("project"), dict) else {}
    if str(repository.get("name", "")).lower() != repo["repo"].lower():
        return False
    if project.get("name") is not None and str(project["name"]).lower() != repo["project"].lower():
        return False
    org = _org_of(pr)
    return org is None or org.lower() == repo["org"].lower()


def _path(entry) -> str | None:
    """The file path a change entry names, without the leading slash; None for folders."""
    item = entry.get("item") if isinstance(entry, dict) else None
    if not isinstance(item, dict) or item.get("isFolder") or item.get("gitObjectType") == "tree":
        return None
    path = item.get("path") or entry.get("originalPath")
    return path.lstrip("/") if isinstance(path, str) and path.strip("/") else None


def _dedupe(values):
    seen, out = set(), []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


class AzureDevOpsAdapter(SourceControlAdapter):
    """Source control adapter for Azure DevOps Services (Azure Repos)."""

    platform = "azure"
    required_fields = ("org", "project", "repo")

    def owns_file(self, name: str) -> bool:
        return name.startswith("azure-") and name.endswith(".json")

    def repo_name(self, repo: dict, documents: dict) -> str:
        return f"{repo['project']}/{repo['repo']}"

    def client_from_env(self, repo: dict, environ) -> AzureDevOpsClient:
        """Build a client from AZDO_PAT. Raises KeyError naming the variable if it is missing."""
        if not environ.get("AZDO_PAT"):
            raise KeyError("AZDO_PAT")
        return AzureDevOpsClient(repo["org"], environ["AZDO_PAT"])

    def fetch(self, repo: dict, since: str, out_dir, client: AzureDevOpsClient) -> dict:
        if not DATE.fullmatch(str(since)):
            raise ValueError(f"since must be a date like 2026-01-31, got {since!r}")
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        base = (f"/{urllib.parse.quote(repo['project'], safe='')}/_apis/git/repositories/"
                f"{urllib.parse.quote(repo['repo'], safe='')}")
        listing = {"searchCriteria.status": "completed", "searchCriteria.queryTimeRangeType": "closed",
                   "searchCriteria.minTime": f"{since}T00:00:00Z"}
        changes = written = 0
        for page in client.skip_pages(f"{base}/pullrequests", listing):
            for pr in _items(page):
                closed = pr.get("closedDate")
                if not (isinstance(closed, str) and closed[:10] >= since):
                    continue
                rid, pid = pr["repository"]["id"], int(pr["pullRequestId"])
                _write(out_dir / f"azure-prs-{rid}-{pid}.json", pr)
                written += 1
                for n, body in enumerate(client.token_pages(f"{base}/pullRequests/{pid}/commits"), start=1):
                    _write(out_dir / f"azure-pr-{rid}-{pid}-commits-{n}.json", body)
                    written += 1
                    for commit in _items(body):
                        if isinstance(commit, dict) and commit.get("commentTruncated") and commit.get("commitId"):
                            sha = str(commit["commitId"])
                            full, _ = client.get(f"{base}/commits/{urllib.parse.quote(sha, safe='')}")
                            _write(out_dir / f"azure-pr-{rid}-{pid}-commits-full-{sha}.json", full)
                            written += 1
                iterations, _ = client.get(f"{base}/pullRequests/{pid}/iterations")
                last = max((int(i["id"]) for i in _items(iterations) if isinstance(i, dict) and "id" in i), default=None)
                if last is not None:
                    path = f"{base}/pullRequests/{pid}/iterations/{last}/changes"
                    for n, body in enumerate(client.change_pages(path), start=1):
                        _write(out_dir / f"azure-pr-{rid}-{pid}-changes-{n}.json", body)
                        written += 1
                changes += 1
        return {"repo": self.repo_name(repo, {}), "changes": changes, "files_written": written}

    def changes(self, documents: dict, repo: dict) -> list[Change]:
        prs, commits, files = {}, {}, {}
        for name in sorted(documents, key=_natural):
            doc = documents[name]
            part = PART_FILE.fullmatch(name)
            if part:
                key = (part[1].lower(), int(part[2]))
                for item in _items(doc):
                    if not isinstance(item, dict):
                        continue
                    if part[3] == "commits":
                        commits.setdefault(key, []).append(item)
                    else:
                        files.setdefault(key, []).append(_path(item))
            elif PR_FILE.fullmatch(name):
                for pr in _items(doc):
                    if isinstance(pr, dict) and "pullRequestId" in pr and isinstance(pr.get("repository"), dict):
                        prs.setdefault((str(pr["repository"].get("id", "")).lower(), int(pr["pullRequestId"])), pr)
        name = self.repo_name(repo, documents)
        out = []
        for key, pr in sorted(prs.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            if pr.get("status") not in COMPLETED or not _belongs_to(pr, repo):
                continue
            pr_commits = [*(c for c in pr.get("commits") or [] if isinstance(c, dict)), *commits.get(key, [])]
            unique = {}
            for c in pr_commits:
                sha = c.get("commitId")
                # A full commit beats one whose message was cut short, whichever file came first.
                if sha and (sha not in unique or unique[sha].get("commentTruncated")):
                    unique[sha] = c
            embedded = [_path(c) for c in pr.get("changes") or []]
            out.append(Change(
                repo=name, kind="pull_request", id=str(pr["pullRequestId"]), merged_at=pr.get("closedDate"),
                title=pr.get("title") or "", description=pr.get("description") or "",
                source_branch=re.sub(r"^refs/heads/", "", pr.get("sourceRefName") or ""),
                commits=[{"id": sha, "message": c.get("comment") or ""} for sha, c in unique.items()],
                files=_dedupe([*embedded, *files.get(key, [])])))
        return out


def _natural(name: str):
    """Sort file names so page 10 comes after page 9."""
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", name)]


def _write(path: Path, doc) -> None:
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")


ADAPTER = AzureDevOpsAdapter()
