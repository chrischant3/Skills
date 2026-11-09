#!/usr/bin/env python3
"""GitLab adapter: merged merge requests, with every commit and changed file.

Raw files, written by the REST fallback here or saved by Claude from a GitLab MCP:
  gitlab-project-<anything>.json                the project (optional; says what kind of namespace it is in)
  gitlab-mrs-<anything>.json                    merge requests (a list page, or one MR)
  gitlab-mr-<project_id>-<iid>-commits[-N].json one page of an MR's commits
  gitlab-mr-<project_id>-<iid>-diffs[-N].json   one page of an MR's diffs (paths are used)

Any of these may be an MCP text block holding the JSON; anonymise.py decodes those. The
REST fallback pages everything (merge requests, commits and diffs) by X-Next-Page,
retries HTTP 429 after Retry-After, and writes diffs without their bodies.

Personal namespaces: a repo's path starts with its namespace, which for a repo in a
person's own namespace is their username. A repo counts as personal if GitLab says its
namespace kind is "user", or scm.yaml says namespace: user, or neither says it is a
group (the safe default, since MCP results often don't carry the namespace). The owner
is then removed by anonymise.py and shown as [person] in every name, e.g.
[person]/checkout-tool.

The REST fallback needs GITLAB_TOKEN (a personal or project access token with read_api).
The token is sent as a header and never written.
"""

import json
import re
import time
import urllib.parse
from pathlib import Path

import rest_transport
from scm_adapter import Change, SourceControlAdapter

PAGE_SIZE = 100
MR_FILE = re.compile(r"gitlab-mrs-[\w.-]*\.json")
PROJECT_FILE = re.compile(r"gitlab-project-[\w.-]*\.json")
NAMESPACE_KINDS = ("group", "user")
OWNER_PLACEHOLDER = "[person]"
PART_FILE = re.compile(r"gitlab-mr-(\d+)-(\d+)-(commits|diffs)(?:-[\w.-]+)?\.json")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class GitLabClient:
    """A small GitLab REST client for one instance.

    Args:
        base_url: e.g. https://gitlab.example.com
        token: access token, sent as PRIVATE-TOKEN. Never logged or written.
        transport: callable(method, url, headers, body, timeout) -> (status, headers, body);
            tests pass a recorded one.
        sleep: called with seconds to wait on HTTP 429.
        max_retries: 429 retries per request before giving up.
    """

    def __init__(self, base_url, token, transport=rest_transport.urllib_transport, sleep=time.sleep, max_retries=5):
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._transport = transport
        self._sleep = sleep
        self._max_retries = max_retries

    def get(self, path, params=None):
        """GET one resource and return its parsed JSON."""
        return self._get(path, params or {})[0]

    def _get(self, path, params):
        url = f"{self.base_url}/api/v4{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
        headers = {"PRIVATE-TOKEN": self._token, "Accept": "application/json"}
        for _ in range(self._max_retries + 1):
            status, resp_headers, raw = self._transport("GET", url, headers, None, 60)
            if status == 429:
                self._sleep(rest_transport.retry_after(resp_headers))
                continue
            if status >= 400:
                raise RuntimeError(f"GitLab returned HTTP {status} for GET {path}")
            return json.loads(raw or b"[]"), resp_headers
        raise RuntimeError(f"GitLab rate limit still in force after {self._max_retries} retries for GET {path}")

    def pages(self, path, params=None):
        """Yield each page (a list) of a paged GitLab list endpoint, following X-Next-Page.

        If a response has no X-Next-Page header, a page shorter than the page size is the last.
        """
        page = 1
        while True:
            items, headers = self._get(path, {**(params or {}), "per_page": PAGE_SIZE, "page": page})
            items = items if isinstance(items, list) else []
            yield items
            next_page = rest_transport.header(headers, "X-Next-Page")
            if next_page is None:
                if len(items) < PAGE_SIZE:
                    return
                page += 1
            elif str(next_page).strip().isdigit():
                page = int(next_page)
            else:
                return


def _on_or_after(timestamp, since: str) -> bool:
    return isinstance(timestamp, str) and timestamp[:10] >= since


def _items(doc) -> list:
    """The list of records a raw or clean document holds, whatever wrapper it arrived in."""
    if isinstance(doc, list):
        return [x for item in doc for x in (_items(item) if isinstance(item, list) else [item])]
    if isinstance(doc, dict):
        for key in ("items", "merge_requests", "commits", "diffs", "changes", "data"):
            if isinstance(doc.get(key), list) and "iid" not in doc:
                return _items(doc[key])
        return [doc]
    return []


def _mr_path(mr: dict) -> str | None:
    full = (mr.get("references") or {}).get("full") if isinstance(mr.get("references"), dict) else None
    if isinstance(full, str) and "!" in full:
        return full.rsplit("!", 1)[0]
    web_url = mr.get("web_url")
    if isinstance(web_url, str) and "/-/merge_requests/" in web_url:
        return urllib.parse.urlsplit(web_url.split("/-/merge_requests/")[0]).path.strip("/")
    return None


def _dedupe(values):
    seen, out = set(), []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _redacted(project: str) -> str:
    """The project path with its namespace owner replaced, e.g. [person]/checkout-tool."""
    rest = project.strip("/").split("/", 1)
    return f"{OWNER_PLACEHOLDER}/{rest[1]}" if len(rest) == 2 else OWNER_PLACEHOLDER


def _namespace_kinds(repo: dict, documents: dict) -> set[str]:
    """Namespace kinds GitLab reported for repo in any project document (raw or clean)."""
    names = {repo["project"].strip("/").lower(), _redacted(repo["project"]).lower()}
    kinds = set()
    for name, doc in documents.items():
        if PROJECT_FILE.fullmatch(name):
            for item in _items(doc):
                if isinstance(item, dict) and str(item.get("path_with_namespace", "")).lower() in names:
                    namespace = item.get("namespace")
                    if isinstance(namespace, dict) and namespace.get("kind"):
                        kinds.add(str(namespace["kind"]))
    return kinds


def is_personal(repo: dict, documents: dict) -> bool:
    """True unless GitLab or scm.yaml says the repo is in a group, and neither says it is a user's."""
    kinds = _namespace_kinds(repo, documents) | ({repo["namespace"]} if repo.get("namespace") else set())
    return "user" in kinds or "group" not in kinds


class GitLabAdapter(SourceControlAdapter):
    """Source control adapter for GitLab (gitlab.com or self-managed)."""

    platform = "gitlab"
    required_fields = ("url", "project")
    optional_fields = ("namespace",)

    def check_field(self, key: str, value) -> None:
        if key == "namespace" and value not in NAMESPACE_KINDS:
            raise ValueError(f"namespace must be group or user, got {value!r}")

    def owns_file(self, name: str) -> bool:
        return name.startswith("gitlab-") and name.endswith(".json")

    def personal_owner(self, repo: dict, documents: dict) -> str | None:
        return repo["project"].strip("/").split("/")[0] if is_personal(repo, documents) else None

    def repo_name(self, repo: dict, documents: dict) -> str:
        return _redacted(repo["project"]) if is_personal(repo, documents) else repo["project"].strip("/")

    def client_from_env(self, repo: dict, environ) -> GitLabClient:
        """Build a client from GITLAB_TOKEN. Raises KeyError naming the variable if it is missing."""
        if not environ.get("GITLAB_TOKEN"):
            raise KeyError("GITLAB_TOKEN")
        return GitLabClient(repo["url"], environ["GITLAB_TOKEN"])

    def fetch(self, repo: dict, since: str, out_dir, client: GitLabClient) -> dict:
        if not DATE.fullmatch(str(since)):
            raise ValueError(f"since must be a date like 2026-01-31, got {since!r}")
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        project = "/projects/" + urllib.parse.quote(repo["project"], safe="")
        meta = client.get(project)
        meta_doc = {f"gitlab-project-{meta.get('id', 'repo')}.json": meta}
        _write(out_dir / next(iter(meta_doc)), meta)
        listing = {"state": "merged", "updated_after": f"{since}T00:00:00Z", "order_by": "updated_at",
                   "sort": "asc", "scope": "all"}
        changes, written = 0, 1
        for page in client.pages(f"{project}/merge_requests", listing):
            for mr in page:
                if not _on_or_after(mr.get("merged_at"), since):
                    continue
                pid, iid = int(mr["project_id"]), int(mr["iid"])
                _write(out_dir / f"gitlab-mrs-{pid}-{iid}.json", mr)
                written += 1
                for kind in ("commits", "diffs"):
                    for n, items in enumerate(client.pages(f"{project}/merge_requests/{iid}/{kind}"), start=1):
                        if kind == "diffs":
                            items = [{k: v for k, v in d.items() if k != "diff"} for d in items]
                        _write(out_dir / f"gitlab-mr-{pid}-{iid}-{kind}-{n}.json", items)
                        written += 1
                changes += 1
        return {"repo": self.repo_name(repo, meta_doc), "changes": changes, "files_written": written}

    def changes(self, documents: dict, repo: dict) -> list[Change]:
        mrs, commits, files = {}, {}, {}
        for name in sorted(documents, key=_natural):
            doc = documents[name]
            part = PART_FILE.fullmatch(name)
            if part:
                key = (int(part[1]), int(part[2]))
                for item in _items(doc):
                    if not isinstance(item, dict):
                        continue
                    if part[3] == "commits":
                        commits.setdefault(key, []).append(item)
                    else:
                        files.setdefault(key, []).append(item.get("new_path") or item.get("old_path"))
            elif MR_FILE.fullmatch(name):
                for mr in _items(doc):
                    if isinstance(mr, dict) and "iid" in mr and "project_id" in mr:
                        mrs.setdefault((int(mr["project_id"]), int(mr["iid"])), mr)
        # In clean/, a personal repo's paths already read [person]/name.
        wanted = {repo["project"].strip("/").lower(), _redacted(repo["project"]).lower()}
        name = self.repo_name(repo, documents)
        out = []
        for key, mr in sorted(mrs.items(), key=lambda kv: kv[0]):
            path = _mr_path(mr)
            if path is None or path.lower() not in wanted:
                continue
            mr_commits = [*(mr.get("commits") or []), *commits.get(key, [])]
            unique = {c.get("id"): c for c in mr_commits if isinstance(c, dict) and c.get("id")}
            embedded = [d.get("new_path") or d.get("old_path") for d in [*(mr.get("diffs") or []), *(mr.get("changes") or [])]
                        if isinstance(d, dict)]
            out.append(Change(
                repo=name, kind="merge_request", id=str(mr["iid"]), merged_at=mr.get("merged_at"),
                title=mr.get("title") or "", description=mr.get("description") or "",
                source_branch=mr.get("source_branch") or "",
                commits=[{"id": sha, "message": c.get("message") or c.get("title") or ""} for sha, c in unique.items()],
                files=_dedupe([*embedded, *files.get(key, [])])))
        return out


def _natural(name: str):
    """Sort file names so page 10 comes after page 9."""
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", name)]


def _write(path: Path, doc) -> None:
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")


ADAPTER = GitLabAdapter()
