#!/usr/bin/env python3
"""Prepare anonymised defects for Claude to classify: batched, trimmed and person-free.

Usage: make_batches.py <clean_dir> <batch_dir> [--max-tickets 20] [--max-chars 40000]

Reads only anonymised issues from clean/ (raw data is refused). Each ticket keeps what
classification needs: summary, type, status, priority, components, labels, resolution,
dates, description and comment text. People are left out entirely, pseudonyms included:
Claude never needs them. Long text is trimmed, keeping the start and end, and says so.

Writes <batch_dir>/batch-NNN.json files.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import clean_data

TAXONOMY = "references/taxonomy.md"
RESPONSE_SHAPE = ("A JSON list with one object per ticket: key, defect_type, trigger, escape_stage, confidence "
                  "(0 to 1), theme (your own words, never copied ticket text), reason (one line; required when "
                  "confidence is below 0.6 or defect_type is unclassified). Values must come from the taxonomy.")
PSEUDONYM = re.compile(r"person_[0-9a-f]{12}")


def _trim(text: str, limit: int) -> tuple[str, bool]:
    text = text.strip()
    if len(text) <= limit:
        return text, False
    head = int(limit * 0.7)
    tail = limit - head
    cut = len(text) - head - tail
    return f"{text[:head]}\n[... {cut} characters trimmed ...]\n{text[-tail:]}", True


def ticket_for_claude(issue: dict, field_chars: int = 4000, comment_chars: int = 800, max_comments: int = 12) -> dict:
    """Return the trimmed, person-free view of one issue that Claude classifies."""
    f = issue["fields"]
    name = lambda v: (v or {}).get("name") if isinstance(v, dict) else None  # noqa: E731
    description, trimmed = _trim(clean_data.text_of(f.get("description")), field_chars)
    comments = [c for c in ((f.get("comment") or {}).get("comments") or [])]
    texts = []
    for c in comments:
        text, cut = _trim(clean_data.text_of(c.get("body")), comment_chars)
        trimmed = trimmed or cut
        texts.append(text)
    if len(texts) > max_comments:
        keep = max_comments // 2
        texts = texts[:keep] + [f"[{len(texts) - 2 * keep} comments omitted]"] + texts[-keep:]
        trimmed = True
    return {
        "key": issue["key"],
        "summary": clean_data.text_of(f.get("summary")).strip(),
        "issue_type": name(f.get("issuetype")),
        "status": name(f.get("status")),
        "priority": name(f.get("priority")),
        "components": [c.get("name") for c in f.get("components") or [] if isinstance(c, dict)],
        "labels": list(f.get("labels") or []),
        "resolution": name(f.get("resolution")),
        "created": f.get("created"),
        "resolved": f.get("resolutiondate"),
        "description": description,
        "comments": texts,
        "comment_count": len(comments),
        "trimmed": trimmed,
    }


def make_batches(issues, max_tickets: int = 20, max_chars: int = 40000, **trim) -> list[list[dict]]:
    """Group tickets into batches of at most max_tickets and roughly max_chars of JSON each.

    A single ticket bigger than max_chars gets a batch of its own.

    Raises:
        ValueError: if a pseudonym appears in any ticket text, which would mean a person slipped through.
    """
    batches, current, size = [], [], 0
    for issue in issues:
        ticket = ticket_for_claude(issue, **trim)
        encoded = json.dumps(ticket)
        if PSEUDONYM.search(encoded):
            raise ValueError(f"a pseudonym appears in the text of {ticket['key']}; stopping so it can't reach Claude")
        if current and (len(current) >= max_tickets or size + len(encoded) > max_chars):
            batches.append(current)
            current, size = [], 0
        current.append(ticket)
        size += len(encoded)
    if current:
        batches.append(current)
    return batches


def write_batches(clean_dir, out_dir, max_tickets: int = 20, max_chars: int = 40000) -> int:
    """Write batch-NNN.json files for every issue in clean_dir. Returns the number of batches."""
    batches = make_batches(clean_data.load_clean_issues(clean_dir), max_tickets, max_chars)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for n, tickets in enumerate(batches, start=1):
        doc = {"batch": n, "of": len(batches), "taxonomy": TAXONOMY, "respond_with": RESPONSE_SHAPE, "tickets": tickets}
        (out_dir / f"batch-{n:03d}.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return len(batches)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Batch anonymised defects for classification.")
    ap.add_argument("clean_dir")
    ap.add_argument("batch_dir")
    ap.add_argument("--max-tickets", type=int, default=20)
    ap.add_argument("--max-chars", type=int, default=40000)
    a = ap.parse_args(argv)
    n = write_batches(a.clean_dir, a.batch_dir, a.max_tickets, a.max_chars)
    print(f"Wrote {n} batches -> {a.batch_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
