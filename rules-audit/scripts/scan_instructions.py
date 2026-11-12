#!/usr/bin/env python3
"""Scan agent instruction files for content a reader can miss: hidden characters, secrets and blobs.

Usage: python3 scan_instructions.py FILE [FILE ...]

Prints JSON: {"files": [...], "hits": [...]}. Each hit names the file, line,
rubric check (A1 secrets, A3 hidden content), kind, a short detail, and
whether the line is inside a fenced code block. The scanner never prints a
secret's value, only a masked form and its length. It reports what it finds;
the audit decides what each hit means (a placeholder in a fenced example is
usually fine). Exit code 0 when the files were scanned, 2 on a usage error or
a missing file.

Standard library only, Python 3.10 or later.
"""

import json
import re
import sys
from urllib.parse import urlparse

ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff", "\u00ad"}
BIDI = {chr(c) for c in [*range(0x202A, 0x202F), *range(0x2066, 0x206A)]}
TAG_START, TAG_END = 0xE0000, 0xE007F

FENCE = re.compile(r"^ {0,3}(```|~~~)")
HTML_COMMENT = re.compile(r"<!--(.*?)(?:-->|\Z)", re.DOTALL)
REMOTE_IMAGE = re.compile(
    r"!\[[^\]]*\]\(\s*(https?://[^)\s]+)|<img\b[^>]*\bsrc\s*=\s*[\"']?(https?://[^\"'\s>]+)",
    re.IGNORECASE,
)
BASE64_RUN = re.compile(r"[A-Za-z0-9+/_-]{40,}={0,2}")
HEX_RUN = re.compile(r"\b[0-9a-fA-F]{64,}\b")

SECRET_ASSIGNMENT = re.compile(
    r"\b([A-Za-z0-9_]*(?:token|secret|password|passwd|api[_-]?key|access[_-]?key"
    r"|private[_-]?key|credentials?)[A-Za-z0-9_]*)\s*[:=]\s*[\"'`]?(<[^>\n]*>|[^\s\"'`]+)",
    re.IGNORECASE,
)
URL_CREDENTIALS = re.compile(
    r"\b[a-z][a-z0-9+.-]*://([^\s:/@]+):([^\s@/]+)@", re.IGNORECASE
)
PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
PLACEHOLDER_WORDS = (
    "your",
    "example",
    "placeholder",
    "changeme",
    "dummy",
    "fake",
    "redacted",
    "xxx",
)


def scan_text(text):
    """Return the hits for one file's text, ordered by line.

    Each hit is a dict with check, kind, line, detail and in_code_fence.
    Invisible-character hits add decoded (the text hidden in tag
    characters, or None); secret hits add looks_like_placeholder.
    """
    if text.startswith("\ufeff"):
        # A byte order mark at the very start is an encoding marker, not hidden content.
        text = " " + text[1:]
    lines = text.split("\n")
    fenced = _fenced_lines(lines)
    hits = []
    for number, line in enumerate(lines, start=1):
        for hit in _line_hits(line):
            hit["line"] = number
            hits.append(hit)
    hits.extend(_html_comments(text))
    for hit in hits:
        hit["in_code_fence"] = hit["line"] in fenced
    hits.sort(key=lambda h: h["line"])
    return [_ordered(h) for h in hits]


def main(argv):
    """Scan each file named in argv and print the JSON report. Returns the exit code."""
    if not argv:
        print("usage: scan_instructions.py FILE [FILE ...]", file=sys.stderr)
        return 2
    hits = []
    for path in argv:
        try:
            raw = open(path, "rb").read()
        except OSError as error:
            print(f"cannot read {path}: {error.strerror}", file=sys.stderr)
            return 2
        try:
            file_hits = scan_text(raw.decode("utf-8"))
        except UnicodeDecodeError:
            file_hits = [
                {
                    "check": None,
                    "kind": "unreadable",
                    "line": None,
                    "detail": "not UTF-8 text, so it was not scanned",
                    "in_code_fence": False,
                }
            ]
        hits.extend({"file": path, **hit} for hit in file_hits)
    print(json.dumps({"files": list(argv), "hits": hits}, ensure_ascii=True, indent=2))
    return 0


def _fenced_lines(lines):
    """Return the numbers of lines inside (or delimiting) fenced code blocks."""
    fenced, inside = set(), False
    for number, line in enumerate(lines, start=1):
        is_fence = bool(FENCE.match(line))
        if inside or is_fence:
            fenced.add(number)
        if is_fence:
            inside = not inside
    return fenced


def _line_hits(line):
    """Return the hits found within a single line, without line numbers."""
    return [
        hit
        for hit in (
            _invisible(line),
            _bidi(line),
            *_secrets(line),
            *_remote_images(line),
            *_blobs(line),
        )
        if hit
    ]


def _invisible(line):
    tags = [c for c in line if TAG_START <= ord(c) <= TAG_END]
    zero_width = [c for c in line if c in ZERO_WIDTH]
    if not tags and not zero_width:
        return None
    parts = []
    if tags:
        parts.append(f"{len(tags)} tag characters")
    if zero_width:
        parts.append(f"{len(zero_width)} zero-width characters")
    decoded = (
        "".join(
            chr(ord(c) - TAG_START) for c in tags if 0x20 <= ord(c) - TAG_START < 0x7F
        )
        or None
    )
    return {
        "check": "A3",
        "kind": "invisible-unicode",
        "detail": ", ".join(parts),
        "decoded": decoded,
    }


def _bidi(line):
    count = sum(1 for c in line if c in BIDI)
    if not count:
        return None
    return {
        "check": "A3",
        "kind": "bidi-control",
        "detail": f"{count} bidirectional control characters",
    }


def _secrets(line):
    hits = []
    for match in SECRET_ASSIGNMENT.finditer(line):
        name, value = match.group(1), match.group(2)
        masked, hidden = _mask(value)
        hits.append(
            _secret_hit(
                f"{name} = {masked} ({hidden} characters hidden)",
                _is_placeholder(value),
            )
        )
    for match in URL_CREDENTIALS.finditer(line):
        password = match.group(2)
        hits.append(
            _secret_hit(
                f"password in a URL for user {match.group(1)} ({len(password)} characters hidden)",
                _is_placeholder(password),
            )
        )
    if PRIVATE_KEY.search(line):
        hits.append(_secret_hit("private key block", False))
    return hits


def _secret_hit(detail, placeholder):
    return {
        "check": "A1",
        "kind": "secret",
        "detail": detail,
        "looks_like_placeholder": placeholder,
    }


def _mask(value):
    """Keep a short prefix such as dpl_ when the value has one, and hide the rest."""
    prefix = re.match(r"[A-Za-z]{1,5}[_-]", value)
    kept = prefix.group(0) if prefix and len(value) > len(prefix.group(0)) else ""
    return kept + "****", len(value) - len(kept)


def _is_placeholder(value):
    lowered = value.lower()
    return (
        lowered.startswith(("<", "{", "$"))
        or any(word in lowered for word in PLACEHOLDER_WORDS)
        or len(set(lowered)) <= 2
    )


def _remote_images(line):
    hits = []
    for match in REMOTE_IMAGE.finditer(line):
        host = urlparse(match.group(1) or match.group(2)).netloc
        hits.append(
            {
                "check": "A3",
                "kind": "remote-image",
                "detail": f"image loaded from {host}",
            }
        )
    return hits


def _blobs(line):
    hits = []
    for match in BASE64_RUN.finditer(line):
        run = match.group(0)
        # Paths and snake_case words are long too; encoded data mixes cases and digits.
        if (
            any(c.isupper() for c in run)
            and any(c.islower() for c in run)
            and any(c.isdigit() for c in run)
        ):
            hits.append(
                {
                    "check": "A3",
                    "kind": "encoded-blob",
                    "detail": f"{len(run)}-character base64-like string",
                }
            )
    for match in HEX_RUN.finditer(line):
        hits.append(
            {
                "check": "A3",
                "kind": "encoded-blob",
                "detail": f"{len(match.group(0))}-character hex string",
            }
        )
    return hits


def _html_comments(text):
    hits = []
    for match in HTML_COMMENT.finditer(text):
        body = " ".join(match.group(1).split())
        hits.append(
            {
                "check": "A3",
                "kind": "html-comment",
                "line": text.count("\n", 0, match.start()) + 1,
                "detail": "hidden when rendered: "
                + (body[:100] + ("..." if len(body) > 100 else "")),
            }
        )
    return hits


def _ordered(hit):
    """Put the common fields first so the JSON reads the same for every kind."""
    keys = ["check", "kind", "line", "detail", "in_code_fence"]
    return {
        **{k: hit[k] for k in keys},
        **{k: v for k, v in hit.items() if k not in keys},
    }


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
