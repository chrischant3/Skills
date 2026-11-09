#!/usr/bin/env python3
"""Read anonymised data from clean/, refusing anything anonymise.py didn't write.

Every analysis script loads issues through here, so raw data can't reach analysis code,
classification input or any output by mistake (P1). With MCP fetching, the model sees
raw data only during the fetch step, before this point.
"""

import json
from pathlib import Path

import anonymise
import jira_normalise


def _load_marked(path: Path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not anonymise.is_marked(doc):
        raise ValueError(f"{path} was not written by anonymise.py. Run anonymise.py on raw data first "
                         "and point this script at its output.")
    return doc


def load_clean_issues(clean_dir) -> list[dict]:
    """Return every anonymised Jira issue in clean_dir, sorted by key.

    Raises:
        ValueError: if any JSON file there (other than _-prefixed reports) wasn't written by anonymise.py.
    """
    issues = []
    for path in sorted(Path(clean_dir).glob("*.json")):
        if path.name.startswith("_"):
            continue
        doc = _load_marked(path)
        if isinstance(doc.get("key"), str) and isinstance(doc.get("fields"), dict):
            issues.append(doc)
    return jira_normalise.merge_issues(issues)


def load_ingest_report(clean_dir) -> dict | None:
    """Return clean/_ingest.json if present, else None."""
    path = Path(clean_dir) / anonymise.INGEST_REPORT
    return _load_marked(path) if path.exists() else None


def text_of(value) -> str:
    """Flatten Atlassian Document Format (Cloud) or wiki/plain text (Data Center) to plain text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(text_of(v) for v in value)
    if isinstance(value, dict):
        kind = value.get("type")
        if kind == "text":
            return value.get("text", "")
        if kind == "mention":
            return (value.get("attrs") or {}).get("text", "")
        if kind == "hardBreak":
            return "\n"
        inner = text_of(value.get("content", []))
        if kind in ("paragraph", "heading", "codeBlock", "blockquote", "listItem", "rule"):
            return inner + "\n"
        return inner
    return str(value)
