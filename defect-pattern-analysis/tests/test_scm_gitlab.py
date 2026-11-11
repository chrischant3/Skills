"""Behaviour tests for scripts/scm_gitlab.py, the GitLab adapter (F4, known problem 5).

Replays recorded GitLab REST responses: merge request, commit and diff pages linked by
X-Next-Page (and one page with no paging headers), and a 429 with Retry-After. A second
fixture holds the same data as Claude would save it from a GitLab MCP. Both must
normalise to the same changes, after anonymisation, with no person left.
"""

import json
import re
import shutil
from urllib.parse import parse_qsl, urlsplit

import pytest

import anonymise
import clean_data
import scm_adapter
import scm_gitlab
from conftest import FIXTURES, all_text_under, load_fixture, person_identifiers

REPO = {
    "platform": "gitlab",
    "url": "https://gitlab.example.com",
    "project": "group/checkout-service",
    "team": "Checkout",
    "namespace": "group",
}
CONFIG = {"repos": [REPO]}
SINCE = "2026-01-01"
TOKEN = "glpat-secret-test-token"


class Recorded:
    """A transport that answers only the GET requests in a recorded fixture."""

    def __init__(self, fixture: dict):
        self.routes = json.loads(json.dumps(fixture["routes"]))
        self.requests = []

    def __call__(self, method, url, headers, body, timeout):
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query))
        self.requests.append((method, parts.path, query, headers))
        for route in self.routes:
            if (
                route["method"] == method
                and route["path"] == parts.path
                and all(query.get(k) == v for k, v in route["match"].items())
            ):
                resp = (
                    route["responses"].pop(0)
                    if len(route["responses"]) > 1
                    else route["responses"][0]
                )
                return (
                    resp["status"],
                    resp.get("headers", {}),
                    json.dumps(resp["body"]).encode(),
                )
        raise AssertionError(f"unrecorded request: {method} {url}")


def fetch(tmp_path, fixture=None, **client_kwargs):
    fixture = fixture or load_fixture("recorded/gitlab_rest.json")
    transport, sleeps = Recorded(fixture), []
    client = scm_gitlab.GitLabClient(
        fixture.get("base_url", REPO["url"]),
        TOKEN,
        transport=transport,
        sleep=sleeps.append,
        **client_kwargs,
    )
    summary = scm_gitlab.ADAPTER.fetch(REPO, SINCE, tmp_path / "raw", client)
    return summary, transport, sleeps


def changes_from(raw, tmp_path):
    anonymise.anonymise_dir(raw, tmp_path / "clean", scm_config=CONFIG)
    docs = clean_data.load_clean_documents(tmp_path / "clean")
    found = scm_gitlab.ADAPTER.changes(docs, REPO)
    return [c for c in found if (c.merged_at or "")[:10] >= SINCE], tmp_path / "clean"


def mcp_raw(tmp_path):
    raw = tmp_path / "mcp_raw"
    shutil.copytree(FIXTURES / "scm/gitlab_mcp", raw)
    return raw


# --- fetching: paging, rate limits, credentials ------------------------------------------------


def test_every_page_of_merge_requests_commits_and_diffs_is_fetched(tmp_path):
    summary, transport, _ = fetch(tmp_path)
    assert summary == {
        "repo": "group/checkout-service",
        "changes": 4,
        "files_written": 16,
    }
    pages = {
        (path.rsplit("/", 1)[-1], q["page"])
        for _, path, q, _ in transport.requests
        if "/merge_requests/" in path
    }
    assert {("commits", "2"), ("diffs", "2")} <= pages
    names = sorted(p.name for p in (tmp_path / "raw").iterdir())
    assert (
        "gitlab-mr-4321-12-commits-2.json" in names
        and "gitlab-mr-4321-12-diffs-2.json" in names
    )


def test_the_window_comes_from_since_and_older_merges_are_skipped(tmp_path):
    _, transport, _ = fetch(tmp_path)
    listing = [
        q for _, path, q, _ in transport.requests if path.endswith("/merge_requests")
    ]
    assert all(
        q["updated_after"] == "2026-01-01T00:00:00Z" and q["state"] == "merged"
        for q in listing
    )
    assert not any(
        "/merge_requests/13/" in path for _, path, _, _ in transport.requests
    )


def test_a_page_without_paging_headers_ends_when_it_is_short(tmp_path):
    _, transport, _ = fetch(tmp_path)
    assert [
        q["page"]
        for _, path, q, _ in transport.requests
        if path.endswith("/15/commits")
    ] == ["1"]


def test_rate_limits_wait_for_retry_after_then_retry(tmp_path):
    _, _, sleeps = fetch(tmp_path)
    assert sleeps == [3]


def test_persistent_rate_limiting_gives_up_with_a_clear_error(tmp_path):
    fixture = {
        "routes": [
            {
                "method": "GET",
                "path": "/api/v4/projects/group%2Fcheckout-service",
                "match": {},
                "responses": [{"status": 429, "headers": {}, "body": {}}],
            }
        ]
    }
    with pytest.raises(RuntimeError, match="rate limit"):
        fetch(tmp_path, fixture, max_retries=2)


def test_an_http_error_names_the_status_but_never_the_token(tmp_path):
    fixture = {
        "routes": [
            {
                "method": "GET",
                "path": "/api/v4/projects/group%2Fcheckout-service",
                "match": {},
                "responses": [{"status": 401, "body": {"message": "401 Unauthorized"}}],
            }
        ]
    }
    with pytest.raises(RuntimeError) as err:
        fetch(tmp_path, fixture)
    assert "401" in str(err.value) and TOKEN not in str(err.value)


def test_the_token_goes_in_a_header_and_is_never_written(tmp_path):
    _, transport, _ = fetch(tmp_path)
    assert all(h["PRIVATE-TOKEN"] == TOKEN for *_, h in transport.requests)
    assert all(
        TOKEN not in path and TOKEN not in json.dumps(q)
        for _, path, q, _ in transport.requests
    )
    assert TOKEN not in all_text_under(tmp_path / "raw")


def test_diff_bodies_are_never_written_to_raw(tmp_path):
    fetch(tmp_path)
    for path in (tmp_path / "raw").glob("*-diffs-*.json"):
        assert all("diff" not in d for d in json.loads(path.read_text()))


# --- normalising: one path for REST and MCP shapes ---------------------------------------------


def test_rest_and_mcp_shapes_normalise_to_the_same_changes(tmp_path):
    fetch(tmp_path / "rest")
    rest, _ = changes_from(tmp_path / "rest/raw", tmp_path / "rest")
    mcp, _ = changes_from(mcp_raw(tmp_path), tmp_path / "mcp")
    assert [c.id for c in rest] == ["12", "14", "15", "16"]
    assert rest == mcp


def test_a_change_holds_every_commit_and_file_from_every_page(tmp_path):
    found, _ = changes_from(mcp_raw(tmp_path), tmp_path)
    mr12 = next(c for c in found if c.id == "12")
    assert isinstance(mr12, scm_adapter.Change)
    assert (mr12.repo, mr12.kind, mr12.merged_at) == (
        "group/checkout-service",
        "merge_request",
        "2026-03-06T15:00:00Z",
    )
    assert [c["id"] for c in mr12.commits] == ["1" * 40, "2" * 40]
    assert mr12.files == ["src/checkout/address.py", "tests/checkout/test_address.py"]
    assert (
        mr12.title.startswith("ABC-101") and mr12.source_branch == "fix/ABC-101-address"
    )


def test_changes_from_another_repo_are_ignored(tmp_path):
    anonymise.anonymise_dir(mcp_raw(tmp_path), tmp_path / "clean", scm_config=CONFIG)
    docs = clean_data.load_clean_documents(tmp_path / "clean")
    assert (
        scm_gitlab.ADAPTER.changes(docs, {**REPO, "project": "group/other-service"})
        == []
    )


@pytest.mark.parametrize("shape", ["rest", "mcp"])
def test_no_person_survives_into_clean_or_the_changes(tmp_path, people, shape):
    if shape == "rest":
        fetch(tmp_path)
        raw = tmp_path / "raw"
    else:
        raw = mcp_raw(tmp_path)
    found, clean = changes_from(raw, tmp_path)
    text = all_text_under(clean) + json.dumps([c.__dict__ for c in found])
    assert [
        i
        for i in person_identifiers(people)
        if re.search(rf"(?<!\w){re.escape(i)}(?!\w)", text, re.I)
    ] == []
    for handle in ["priya.t", "tomasz.f", "grace.p", "seun.m", "dana.s"]:
        assert handle not in text


def test_the_adapter_is_registered_for_its_platform():
    assert scm_adapter.adapter_for("gitlab") is scm_gitlab.ADAPTER
    assert scm_gitlab.ADAPTER.required_fields == ("url", "project")
