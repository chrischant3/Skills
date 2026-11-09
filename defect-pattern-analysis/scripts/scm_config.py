#!/usr/bin/env python3
"""Read scm.yaml, the source control configuration, with the standard library only.

Only a small, strict part of YAML is understood. Anything else is refused with the file
name and line number, never guessed at, so a config can't be silently misread.

Supported:
- top-level settings, one per line: key: value
- one top-level list, repos:, of flat mappings. Each item starts "- key: value" and
  carries on with "key: value" lines indented to line up with the first key.
- comments (# after a space, or on a line of their own) and blank lines.
- values: whole numbers, plain text, 'single-quoted' text (literal; '' is a quote, so
  use these for regular expressions) and "double-quoted" text (only \\" and \\\\ escapes).

Refused, naming the line: tabs, a byte order mark, document markers (--- and ...),
anchors (&) and aliases (*), tags (!), flow collections ([...] and {...}), multi-line
strings (| and >, or plain text carried onto the next line), duplicate keys, unknown
settings, settings without a value, inconsistent indentation, and plain values YAML
would read as something other than text (true, yes, no, null, ~, 1.5, 0x1F, text
holding ": "). Quote those to use them as text.

Settings:
  min_group_size       optional; checked by suppress.py when it is used.
  default_key_pattern  optional; the key regex for repos without their own.
  repos                required; each needs platform plus that platform's fields,
                       and may set team, key_pattern and the platform's optional fields.
"""

import re
from pathlib import Path

import scm_adapter
import scm_keys

LIST_KEY = "repos"
TOP_LEVEL = {"min_group_size", "default_key_pattern", LIST_KEY}
COMMON_REPO_FIELDS = {"platform", "team", "key_pattern"}
LINE = re.compile(r"^(?P<indent> *)(?P<dash>- +)?(?P<key>[A-Za-z_][\w-]*):(?: +(?P<value>.*?))?\s*$")
RESERVED_WORDS = {"true", "false", "yes", "no", "on", "off", "y", "n", "null", "~"}
NON_TEXT_NUMBER = re.compile(r"[-+]?(\d[\d_]*\.\d*|\.\d+|\d+(\.\d*)?[eE][-+]?\d+|0[xX][0-9a-fA-F]+|0[oO]?[0-7]+"
                             r"|\.(inf|Inf|INF|nan|NaN|NAN))")
INDICATORS = {"&": "anchors (&) aren't supported", "*": "aliases (*) aren't supported",
              "!": "tags (!) aren't supported", "[": "flow collections ([...]) aren't supported",
              "{": "flow collections ({...}) aren't supported", "|": "multi-line strings (|) aren't supported",
              ">": "multi-line strings (>) aren't supported", "%": "% is reserved in YAML; quote the value",
              "@": "@ is reserved in YAML; quote the value", "`": "` is reserved in YAML; quote the value"}


def _strip_comment(line: str) -> str:
    """Drop a # comment, unless the # is inside quotes or not preceded by a space."""
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] == " "):
            return line[:i].rstrip()
    return line.rstrip()


def _scalar(raw: str | None, n: int):
    """Turn one value into str or int, refusing anything this reader might misread."""
    if raw is None or raw == "":
        return None
    if raw[0] == "'":
        inner = raw[1:-1]
        if len(raw) < 2 or raw[-1] != "'":
            raise ValueError(f"line {n}: unterminated single-quoted value")
        if "'" in inner.replace("''", ""):
            raise ValueError(f"line {n}: text after a single-quoted value's closing quote; use one quoted value")
        return inner.replace("''", "'")
    if raw[0] == '"':
        inner = raw[1:-1]
        if len(raw) < 2 or raw[-1] != '"':
            raise ValueError(f"line {n}: unterminated double-quoted value")
        if re.search(r'(?<!\\)"', inner):
            raise ValueError(f"line {n}: text after a double-quoted value's closing quote; use one quoted value")
        if re.search(r'\\[^"\\]', inner):
            raise ValueError(f"line {n}: backslashes in double quotes aren't supported; use single quotes")
        return inner.replace('\\"', '"').replace("\\\\", "\\")
    if raw[0] in INDICATORS:
        raise ValueError(f"line {n}: {INDICATORS[raw[0]]}")
    if re.fullmatch(r"-?(0|[1-9]\d*)", raw):
        return int(raw)
    if raw.lower() in RESERVED_WORDS or NON_TEXT_NUMBER.fullmatch(raw) or ": " in raw or raw.endswith(":"):
        raise ValueError(f"line {n}: YAML wouldn't read {raw!r} as plain text; quote it, for example '{raw}'")
    return raw


def parse_with_lines(text: str, list_key: str = LIST_KEY) -> tuple[dict, dict]:
    """Parse the supported subset into a dict, plus the line each part came from.

    Args:
        text: the file's contents.
        list_key: the name of the one top-level list, used in messages and in the line map.
            Other config files that share this subset (such as signals.yaml) pass their own.
    Returns:
        (data, lines): lines maps a top-level key to its line, (list_key, i) to item i's
        first line, and (list_key, i, key) to that setting's line.
    Raises:
        ValueError: "line N: ..." for anything outside the subset.
    """
    out, lines = {}, {}
    items = current = None
    dash_indent = item_indent = None
    for n, line in enumerate(text.splitlines(), start=1):
        if n == 1 and line.startswith("﻿"):
            raise ValueError("line 1: the file starts with a byte order mark; save it as plain UTF-8")
        if "\t" in line:
            raise ValueError(f"line {n}: tab characters aren't supported; use spaces")
        line = _strip_comment(line)
        if not line.strip():
            continue
        if line.strip() in ("---", "...") or line.startswith(("--- ", "... ")):
            raise ValueError(f"line {n}: document markers (--- and ...) aren't supported; use one document")
        dash = re.match(r"^( *)- +([\[{])", line)
        if dash:
            raise ValueError(f"line {n}: flow collections ({dash[2]}...) aren't supported; write one key per line")
        m = LINE.match(line)
        if not m:
            raise ValueError(f"line {n}: not understood: {line.strip()!r}")
        indent, key, value = len(m["indent"]), m["key"], _scalar(m["value"], n)
        if m["dash"]:
            if items is None or indent == 0:
                raise ValueError(f"line {n}: a list item must be indented under {list_key}:")
            if dash_indent is not None and indent != dash_indent:
                raise ValueError(f"line {n}: unexpected indentation; list items must line up")
            if value is None:
                raise ValueError(f"line {n}: {key} needs a value")
            dash_indent, item_indent = indent, indent + len(m["dash"])
            current = {key: value}
            items.append(current)
            lines[(list_key, len(items) - 1)] = n
            lines[(list_key, len(items) - 1, key)] = n
        elif indent == 0:
            if key in out:
                raise ValueError(f"line {n}: duplicate setting {key!r} (first on line {lines[key]})")
            lines[key] = n
            if value is None:
                items, current, dash_indent = [], None, None
                out[key] = items
            else:
                items = current = None
                out[key] = value
        elif current is not None and indent == item_indent:
            if key in current:
                first = lines[(list_key, len(items) - 1, key)]
                item = "repo" if list_key == LIST_KEY else "item"
                raise ValueError(f"line {n}: duplicate setting {key!r} in this {item} (first on line {first})")
            if value is None:
                raise ValueError(f"line {n}: {key} needs a value")
            current[key] = value
            lines[(list_key, len(items) - 1, key)] = n
        else:
            raise ValueError(f"line {n}: unexpected indentation")
    return out, lines


def parse(text: str) -> dict:
    """Parse the supported subset described in this module's docstring into a dict."""
    return parse_with_lines(text)[0]


def _check(config: dict, lines: dict) -> None:
    for key, value in config.items():
        n = lines[key]
        if key not in TOP_LEVEL:
            raise ValueError(f"line {n}: unknown setting {key!r}; expected one of {sorted(TOP_LEVEL)}")
        if key != LIST_KEY and isinstance(value, list):
            raise ValueError(f"line {n}: {key} needs a value" if not value else f"line {n}: {key} can't be a list")
    if LIST_KEY not in config:
        raise ValueError(f"line 1: no {LIST_KEY}: list; add one with at least one repo")
    repos, n = config[LIST_KEY], lines[LIST_KEY]
    if not isinstance(repos, list):
        raise ValueError(f"line {n}: {LIST_KEY} must be a list of repos, each starting with '- platform:'")
    if not repos:
        raise ValueError(f"line {n}: {LIST_KEY} needs at least one repo")
    size = config.get("min_group_size")
    if size is not None and not isinstance(size, int):
        raise ValueError(f"line {lines['min_group_size']}: min_group_size must be a whole number, got {size!r}")
    if config.get("default_key_pattern") is not None:
        _check_pattern(config["default_key_pattern"], lines["default_key_pattern"])
    platforms = sorted(scm_adapter.known_platforms())
    for i, repo in enumerate(repos):
        start = lines[(LIST_KEY, i)]
        platform = repo.get("platform")
        if platform not in platforms:
            raise ValueError(f"line {start}: platform must be one of {platforms}, got {platform!r}")
        required = scm_adapter.required_fields(platform)
        allowed = COMMON_REPO_FIELDS | set(required) | set(scm_adapter.optional_fields(platform))
        for key in repo:
            if key not in allowed:
                raise ValueError(f"line {lines[(LIST_KEY, i, key)]}: unknown setting {key!r} for a {platform} repo; "
                                 f"expected one of {sorted(allowed)}")
        missing = [f for f in required if repo.get(f) in (None, "")]
        if missing:
            raise ValueError(f"line {start}: repo {i + 1} ({platform}) is missing {', '.join(missing)}")
        if "key_pattern" in repo:
            _check_pattern(repo["key_pattern"], lines[(LIST_KEY, i, "key_pattern")])
        for key in scm_adapter.optional_fields(platform):
            if key in repo:
                scm_adapter.check_optional_field(platform, key, repo[key], lines[(LIST_KEY, i, key)])


def _check_pattern(pattern, n: int) -> None:
    try:
        scm_keys.KeyMatcher(str(pattern))
    except ValueError as err:
        raise ValueError(f"line {n}: {err}") from None


def load_config(path) -> dict:
    """Read and check scm.yaml.

    Returns:
        {"min_group_size": int or None, "default_key_pattern": str or None, "repos": [dict, ...]}
    Raises:
        ValueError: "<path>: line N: ..." naming the line at fault.
    """
    try:
        config, lines = parse_with_lines(Path(path).read_text(encoding="utf-8"))
        _check(config, lines)
    except ValueError as err:
        raise ValueError(f"{path}: {err}") from None
    return {"min_group_size": config.get("min_group_size"), "default_key_pattern": config.get("default_key_pattern"),
            "repos": config[LIST_KEY]}
