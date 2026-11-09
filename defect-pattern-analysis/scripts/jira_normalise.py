#!/usr/bin/env python3
"""Find Jira issues in raw files of either shape and put them in one standard shape.

Raw files come from two places:
- Claude, saving Atlassian MCP tool results verbatim (a search page, a single issue, a
  list, or an MCP text content block holding JSON).
- scripts/jira_changelog.py, the REST fallback, which writes one file per issue.

This module never removes people; anonymise.py calls it before scrubbing, so nothing
here reaches analysis code or Claude.
"""

import json

MANIFEST_NAME = "_manifest.json"


def issues_from_document(doc) -> list[dict]:
    """Return every Jira issue held in doc, whatever wrapper it arrived in."""
    if isinstance(doc, str):
        try:
            return issues_from_document(json.loads(doc))
        except ValueError:
            return []
    if isinstance(doc, list):
        return [issue for item in doc for issue in issues_from_document(item)]
    if not isinstance(doc, dict):
        return []
    if isinstance(doc.get("key"), str) and isinstance(doc.get("fields"), dict):
        return [doc]
    if isinstance(doc.get("issues"), list):
        return issues_from_document(doc["issues"])
    if isinstance(doc.get("content"), list):
        return [issue for block in doc["content"] if isinstance(block, dict) and block.get("type") == "text"
                for issue in issues_from_document(block.get("text", ""))]
    return []


def _complete(container: dict | None, items_key: str) -> bool:
    """True only when a total is present and the list holds at least that many items."""
    if not isinstance(container, dict) or not isinstance(container.get(items_key), list):
        return False
    total = container.get("total")
    return isinstance(total, int) and total <= len(container[items_key])


def normalise_issue(issue: dict) -> dict:
    """Return a copy of issue with changelog under changelog.histories and an _ingest block.

    _ingest.changelog_complete and _ingest.comments_complete are True only when the data
    proves it (a total no larger than what was received), or when the REST fallback
    already fetched everything.
    """
    out = json.loads(json.dumps(issue))
    changelog = out.get("changelog")
    if isinstance(changelog, dict) and "histories" not in changelog and isinstance(changelog.get("values"), list):
        changelog["histories"] = changelog.pop("values")
    previous = out.get("_ingest") if isinstance(out.get("_ingest"), dict) else {}
    out["_ingest"] = {
        "source": previous.get("source", "unknown"),
        "changelog_complete": bool(previous.get("changelog_complete")) or _complete(out.get("changelog"), "histories"),
        "comments_complete": bool(previous.get("comments_complete")) or _complete(out["fields"].get("comment"), "comments"),
    }
    return out


def _richness(issue: dict) -> tuple:
    ingest = issue["_ingest"]
    histories = (issue.get("changelog") or {}).get("histories") or []
    comments = (issue["fields"].get("comment") or {}).get("comments") or []
    return (ingest["changelog_complete"] + ingest["comments_complete"], len(histories) + len(comments))


def merge_issues(issues: list[dict]) -> list[dict]:
    """Normalise issues and keep the most complete copy of each key, sorted by key."""
    best: dict[str, dict] = {}
    for issue in issues:
        issue = normalise_issue(issue)
        current = best.get(issue["key"])
        if current is None or _richness(issue) > _richness(current):
            best[issue["key"]] = issue
    return [best[k] for k in sorted(best, key=_key_order)]


def _key_order(key: str):
    project, _, number = key.partition("-")
    return (project, int(number) if number.isdigit() else 0, key)


def ingest_report(issues: list[dict], manifest: dict | None) -> dict:
    """Summarise coverage: how many issues, how many matched, and which have gaps."""
    sources = {i["_ingest"]["source"] for i in issues if i["_ingest"]["source"] != "unknown"}
    if manifest and manifest.get("source"):
        sources.add(manifest["source"])
    matched = manifest.get("matched") if manifest else None
    return {
        "issues": len(issues),
        "matched": matched if isinstance(matched, int) else None,
        "sources": sorted(sources),
        "changelog_incomplete": [i["key"] for i in issues if not i["_ingest"]["changelog_complete"]],
        "comments_incomplete": [i["key"] for i in issues if not i["_ingest"]["comments_complete"]],
    }
