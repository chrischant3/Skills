#!/usr/bin/env python3
"""Scan agent instruction files for content a reader can miss: hidden characters, secrets and blobs.

Usage: python3 scan_instructions.py FILE [FILE ...]

Prints JSON: {"files": [...], "hits": [...]}. Each hit names the file, line,
rubric check (A1 secrets, A3 hidden content), kind, a short detail, and
whether the line is inside a code block (fenced, or indented as Markdown
allows). The scanner never prints a
secret's value, only a masked form and its length; text it quotes from the
file (comment bodies, text hidden in tag characters) has secrets masked too.
It reports what it finds; the audit decides what each hit means (a
placeholder in a fenced example is usually fine). A file that can't be read
is reported as a hit and the others are still scanned. Exit code 0 when at
least one file was scanned, 2 on a usage error or when none could be read.

Standard library only, Python 3.10 or later.
"""

import json
import re
import sys
from urllib.parse import urlparse

from code_blocks import code_lines

ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff", "\u00ad"}
BIDI = {
    chr(c)
    for c in [*range(0x202A, 0x202F), *range(0x2066, 0x206A), 0x200E, 0x200F, 0x061C]
}
VARIATION_SELECTORS = {
    chr(c) for c in [*range(0xFE00, 0xFE10), *range(0xE0100, 0xE01F0)]
}
TAG_START, TAG_END = 0xE0000, 0xE007F

HTML_COMMENT = re.compile(r"<!--(.*?)(?:-->|\Z)", re.DOTALL)
REMOTE_IMAGE = re.compile(
    r"!\[[^\]]*\]\(\s*(https?://[^)\s]+)|<img\b[^>]*\bsrc\s*=\s*[\"']?(https?://[^\"'\s>]+)",
    re.IGNORECASE,
)
BASE64_RUN = re.compile(r"[A-Za-z0-9+/_-]{40,}={0,2}")
HEX_RUN = re.compile(r"\b[0-9a-fA-F]{64,}\b")

SECRET_ASSIGNMENT = re.compile(
    # The name parts are capped at 40 characters: unbounded runs backtrack
    # quadratically on a long line of repeated keywords, which a planted file
    # could use to stall the audit.
    r"\b([A-Za-z0-9_]{0,40}(?:token|secret|password|passwd|api[_-]?key|access[_-]?key"
    r"|private[_-]?key|credentials?)[A-Za-z0-9_]{0,40})\s*[:=]\s*[\"'`]?(<[^>\n]*>|[^\s\"'`]+)",
    re.IGNORECASE,
)
URL_CREDENTIALS = re.compile(
    r"\b[a-z][a-z0-9+.-]*://([^\s:/@]+)(?::([^\s@/]+))?@", re.IGNORECASE
)
# Credentials with a well-known shape, found even when nothing names them.
KNOWN_TOKEN = re.compile(
    r"\b(?:AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|sk_(?:live|test)_[A-Za-z0-9]{8,}"
    r"|xox[abpr]-[A-Za-z0-9-]{10,})\b"
    r"|\bBearer\s+([A-Za-z0-9._~+/=-]{16,})"
)
# A URL username this long is more likely a token than a person's login.
TOKEN_LIKE_USERNAME = 16
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

    Each hit is a dict with check, kind, line, detail, in_code_fence (inside
    a fenced code block) and in_code_block (inside a fenced or an indented one).
    Invisible-character hits add decoded (the text hidden in tag
    characters, or None); secret hits add looks_like_placeholder.
    """
    if text.startswith("\ufeff"):
        # A byte order mark at the very start is an encoding marker, not hidden content.
        text = " " + text[1:]
    lines = text.split("\n")
    fenced, code = code_lines(lines)
    hits = []
    for number, line in enumerate(lines, start=1):
        for hit in _line_hits(line):
            hit["line"] = number
            hits.append(hit)
    hits.extend(_html_comments(text))
    for hit in hits:
        hit["in_code_fence"] = hit["line"] in fenced
        hit["in_code_block"] = hit["line"] in code
    hits.sort(key=lambda h: h["line"])
    return [_ordered(h) for h in hits]


def main(argv):
    """Scan each file named in argv and print the JSON report. Returns the exit code."""
    if not argv:
        print("usage: scan_instructions.py FILE [FILE ...]", file=sys.stderr)
        return 2
    hits, scanned = [], 0
    for path in argv:
        try:
            raw = open(path, "rb").read()
        except OSError as error:
            print(f"cannot read {path}: {error.strerror}", file=sys.stderr)
            hits.append(
                {
                    "file": path,
                    **_file_problem("missing", f"cannot read: {error.strerror}"),
                }
            )
            continue
        scanned += 1
        try:
            file_hits = scan_text(raw.decode("utf-8"))
        except UnicodeDecodeError:
            file_hits = [
                _file_problem("unreadable", "not UTF-8 text, so it was not scanned")
            ]
        hits.extend({"file": path, **hit} for hit in file_hits)
    print(json.dumps({"files": list(argv), "hits": hits}, ensure_ascii=True, indent=2))
    return 0 if scanned else 2


def _file_problem(kind, detail):
    return {
        "check": None,
        "kind": kind,
        "line": None,
        "detail": detail,
        "in_code_fence": False,
        "in_code_block": False,
    }


def _line_hits(line):
    """Return the hits found within a single line, without line numbers."""
    secrets, secret_spans = _secrets(line)
    return [
        hit
        for hit in (
            _invisible(line),
            _bidi(line),
            *secrets,
            *_remote_images(line),
            *_blobs(line, secret_spans),
        )
        if hit
    ]


def _invisible(line):
    tags = [c for c in line if TAG_START <= ord(c) <= TAG_END]
    zero_width = [c for c in line if c in ZERO_WIDTH]
    # A selector after an emoji or ideograph is normal; after plain text or another
    # selector it carries nothing visible, which is how "emoji smuggling" hides data.
    selectors = [
        c
        for i, c in enumerate(line)
        if c in VARIATION_SELECTORS
        and (i == 0 or ord(line[i - 1]) < 0x2000 or line[i - 1] in VARIATION_SELECTORS)
    ]
    if not tags and not zero_width and not selectors:
        return None
    parts = []
    if tags:
        parts.append(f"{len(tags)} tag characters")
    if zero_width:
        parts.append(f"{len(zero_width)} zero-width characters")
    if selectors:
        parts.append(f"{len(selectors)} stray variation selectors")
    decoded = (
        _redact(
            "".join(
                chr(ord(c) - TAG_START)
                for c in tags
                if 0x20 <= ord(c) - TAG_START < 0x7F
            )
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
        "detail": f"{count} bidirectional control or direction mark characters",
    }


def _secrets(line):
    """Return the secret hits in a line and the character spans they cover."""
    hits, spans = [], []
    for match in SECRET_ASSIGNMENT.finditer(line):
        name, value = match.group(1), match.group(2)
        if value.isdigit() and len(value) < 8:
            continue  # max_tokens: 4096 is a setting, not a credential
        masked, hidden = _mask(value)
        hits.append(
            _secret_hit(
                f"{name} = {masked} ({hidden} characters hidden)",
                _is_placeholder(value),
            )
        )
        spans.append(match.span(2))
    for match in URL_CREDENTIALS.finditer(line):
        user, password = match.group(1), match.group(2)
        if password is None and len(user) < TOKEN_LIKE_USERNAME:
            continue  # git@host and similar logins
        hidden = len(user) + len(password or "")
        hits.append(
            _secret_hit(
                f"credentials in a URL, user {_mask(user)[0]} ({hidden} characters hidden)",
                _is_placeholder(password or user),
            )
        )
        spans.append(match.span(1))
    for match in KNOWN_TOKEN.finditer(line):
        if _overlaps(match.span(), spans):
            continue  # already reported as URL credentials
        value = match.group(1) or match.group(0)
        masked, hidden = _mask(value)
        hits.append(_secret_hit(f"token {masked} ({hidden} characters hidden)", False))
        spans.append(match.span())
    if PRIVATE_KEY.search(line):
        hits.append(_secret_hit("private key block", False))
    return hits, spans


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


def _overlaps(span, spans):
    """True when span shares any character with one of spans."""
    return any(span[0] < end and start < span[1] for start, end in spans)


def _redact(text):
    """Return text with every secret value it contains masked."""

    def mask_assigned_value(match):
        name_and_separator = match.group(0)[: match.start(2) - match.start()]
        return name_and_separator + _mask(match.group(2))[0]

    def mask_url_userinfo(match):
        scheme = match.group(0).split("//")[0]
        return scheme + "//****@"

    text = SECRET_ASSIGNMENT.sub(mask_assigned_value, text)
    text = URL_CREDENTIALS.sub(mask_url_userinfo, text)
    return KNOWN_TOKEN.sub(lambda match: _mask(match.group(0))[0], text)


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
        host = urlparse(match.group(1) or match.group(2)).hostname
        hits.append(
            {
                "check": "A3",
                "kind": "remote-image",
                "detail": f"image loaded from {host}",
            }
        )
    return hits


def _blobs(line, secret_spans):
    hits = []
    for match in BASE64_RUN.finditer(line):
        run = match.group(0)
        if _overlaps(match.span(), secret_spans):
            continue  # already reported, masked, as a secret
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
    hits, line, counted_to = [], 1, 0
    for match in HTML_COMMENT.finditer(text):
        line += text.count("\n", counted_to, match.start())
        counted_to = match.start()
        body = _redact(" ".join(match.group(1).split()))
        hits.append(
            {
                "check": "A3",
                "kind": "html-comment",
                "line": line,
                "detail": "hidden when rendered: "
                + (body[:100] + ("..." if len(body) > 100 else "")),
            }
        )
    return hits


def _ordered(hit):
    """Put the common fields first so the JSON reads the same for every kind."""
    keys = ["check", "kind", "line", "detail", "in_code_fence", "in_code_block"]
    return {
        **{k: hit[k] for k in keys},
        **{k: v for k, v in hit.items() if k not in keys},
    }


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
