"""Behaviour tests for scripts/jira_changelog.py, the REST fallback for Jira ingestion (F1, known problem 7).

Replays recorded responses: Cloud token paging, Data Center startAt paging, 429s with and
without Retry-After, and changelogs and comments truncated in search results.
"""

import json
from urllib.parse import parse_qsl, urlsplit

import pytest

import jira_changelog
from conftest import load_fixture


class Recorded:
    """A transport that answers only the requests in a recorded fixture."""

    def __init__(self, fixture: dict):
        self.routes = json.loads(json.dumps(fixture["routes"]))
        self.bodies = []

    def __call__(self, method, url, headers, body, timeout):
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query))
        payload = json.loads(body) if body else {}
        self.bodies.append(payload)
        for route in self.routes:
            source = payload if method == "POST" else query
            if (
                route["method"] == method
                and route["path"] == parts.path
                and all(source.get(k) == v for k, v in route["match"].items())
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
        raise AssertionError(f"unrecorded request: {method} {url} {payload}")


def run(fixture_name, tmp_path, **kwargs):
    fixture = load_fixture(f"recorded/{fixture_name}")
    sleeps = []
    transport = Recorded(fixture)
    client = jira_changelog.JiraClient(
        fixture["base_url"],
        fixture["deployment"],
        "Basic dGVzdDpzZWNyZXQtdG9rZW4=",
        transport=transport,
        sleep=sleeps.append,
        **kwargs,
    )
    manifest = jira_changelog.fetch(
        client, "project = ABC AND issuetype = Bug", tmp_path
    )
    return fixture, manifest, sleeps, transport


@pytest.mark.parametrize("fixture_name", ["cloud_search.json", "dc_search.json"])
def test_every_page_is_fetched_with_full_changelog_and_all_comments(
    tmp_path, fixture_name
):
    fixture, manifest, _, _ = run(fixture_name, tmp_path)
    for key, (histories, comments) in fixture["expected"].items():
        issue = json.loads((tmp_path / f"{key}.json").read_text())
        assert len(issue["changelog"]["histories"]) == histories
        assert len(issue["fields"]["comment"]["comments"]) == comments
        assert (
            issue["_ingest"]["changelog_complete"]
            and issue["_ingest"]["comments_complete"]
        )
    assert manifest["fetched"] == len(fixture["expected"]) == manifest["matched"]


def test_full_changelog_pages_are_in_order_without_duplicates(tmp_path):
    run("cloud_search.json", tmp_path)
    ids = [
        h["id"]
        for h in json.loads((tmp_path / "ABC-201.json").read_text())["changelog"][
            "histories"
        ]
    ]
    assert len(ids) == len(set(ids)) == 5


@pytest.mark.parametrize(
    "fixture_name,waits",
    [
        ("cloud_search.json", [2]),
        ("dc_search.json", [1, jira_changelog.DEFAULT_RETRY_AFTER]),
    ],
)
def test_rate_limits_wait_for_retry_after_then_retry(tmp_path, fixture_name, waits):
    _, _, sleeps, _ = run(fixture_name, tmp_path)
    assert sleeps == waits


def test_persistent_rate_limiting_gives_up_with_a_clear_error(tmp_path):
    fixture = {
        "routes": [
            {
                "method": "POST",
                "path": "/rest/api/3/search/jql",
                "match": {},
                "responses": [
                    {"status": 429, "headers": {"Retry-After": "1"}, "body": {}}
                ],
            }
        ]
    }
    client = jira_changelog.JiraClient(
        "https://example.atlassian.net",
        "cloud",
        "Basic x",
        transport=Recorded(fixture),
        sleep=lambda s: None,
        max_retries=3,
    )
    with pytest.raises(RuntimeError, match="rate limit"):
        jira_changelog.fetch(client, "project = ABC", tmp_path)


def test_an_http_error_names_the_status_but_never_the_credentials(tmp_path):
    fixture = {
        "routes": [
            {
                "method": "POST",
                "path": "/rest/api/2/search",
                "match": {},
                "responses": [{"status": 401, "body": {"errorMessages": ["no"]}}],
            }
        ]
    }
    client = jira_changelog.JiraClient(
        "https://jira.example.com",
        "datacenter",
        "Bearer secret-pat-value",
        transport=Recorded(fixture),
        sleep=lambda s: None,
    )
    with pytest.raises(RuntimeError) as err:
        jira_changelog.fetch(client, "project = ABC", tmp_path)
    assert "401" in str(err.value) and "secret-pat-value" not in str(err.value)


def test_credentials_are_never_written_to_disk(tmp_path):
    run("cloud_search.json", tmp_path)
    everything = "".join(p.read_text() for p in tmp_path.iterdir())
    assert (
        "dGVzdDpzZWNyZXQtdG9rZW4=" not in everything
        and "secret-token" not in everything
    )


def test_only_named_fields_are_requested(tmp_path):
    _, _, _, transport = run(
        "cloud_search.json", tmp_path, extra_fields=["customfield_10010"]
    )
    fields = transport.bodies[0]["fields"]
    assert not any("*" in f for f in fields)
    assert {
        "summary",
        "description",
        "comment",
        "components",
        "status",
        "customfield_10010",
    } <= set(fields)


def test_a_manifest_records_how_many_defects_matched(tmp_path):
    _, manifest, _, _ = run("dc_search.json", tmp_path)
    saved = json.loads((tmp_path / jira_changelog.MANIFEST_NAME).read_text())
    assert saved == manifest
    assert (
        saved["source"] == "rest"
        and saved["deployment"] == "datacenter"
        and saved["matched"] == 3
    )


def test_an_unknown_deployment_is_refused():
    with pytest.raises(ValueError, match="cloud or datacenter"):
        jira_changelog.JiraClient("https://x.example.com", "server", "Basic x")


# --- defect definition ------------------------------------------------------------------------


def test_default_query_is_bugs_created_in_the_last_twelve_months():
    assert (
        jira_changelog.build_jql(["ABC"])
        == 'project in ("ABC") AND issuetype in ("Bug") AND created >= -365d ORDER BY created ASC'
    )


def test_query_can_use_several_issue_types_labels_and_a_window():
    jql = jira_changelog.build_jql(
        ["ABC", "XYZ"],
        issue_types=["Bug", "Defect"],
        labels=["escaped"],
        window_days=90,
    )
    assert jql == (
        'project in ("ABC", "XYZ") AND (issuetype in ("Bug", "Defect") OR labels in ("escaped")) '
        "AND created >= -90d ORDER BY created ASC"
    )


def test_labels_alone_replace_the_default_issue_type():
    assert (
        jira_changelog.build_jql(["ABC"], issue_types=[], labels=["defect"])
        == 'project in ("ABC") AND labels in ("defect") AND created >= -365d ORDER BY created ASC'
    )


@pytest.mark.parametrize("bad", ['ABC" OR project != "X', "abc", ""])
def test_project_keys_that_could_alter_the_query_are_refused(bad):
    with pytest.raises(ValueError):
        jira_changelog.build_jql([bad])


def test_specific_keys_can_be_fetched_to_fill_gaps_left_by_the_mcp():
    assert (
        jira_changelog.jql_for_keys(["ABC-1", "ABC-22"])
        == "key in (ABC-1, ABC-22) ORDER BY key ASC"
    )
    with pytest.raises(ValueError):
        jira_changelog.jql_for_keys(["ABC-1) OR (1=1"])
