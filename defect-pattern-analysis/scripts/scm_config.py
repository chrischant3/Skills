#!/usr/bin/env python3
"""Read scm.yaml, the source control configuration, with the standard library only.

Only the small part of YAML that scm.yaml needs is understood, and anything else is
refused with the line number, rather than guessed at:
- top-level settings (key: value);
- one top-level list of flat mappings (repos:, each item starting "- key: value");
- comments, plain values, whole numbers, and quoted strings. Single quotes are
  literal ('' is a quote), so use them for regular expressions. Double quotes may
  only escape \\" and \\\\.

Settings:
  min_group_size       optional; checked by suppress.py when it is used.
  default_key_pattern  optional; the key regex for repos without their own.
  repos                required; each needs platform plus that platform's fields,
                       and may set team and key_pattern.
"""

import re
from pathlib import Path

import scm_adapter
import scm_keys

TOP_LEVEL = {"min_group_size", "default_key_pattern", "repos"}
LINE = re.compile(r"^(?P<indent> *)(?P<dash>- +)?(?P<key>[A-Za-z_][\w-]*):(?: +(?P<value>.*?))?\s*$")


def _strip_comment(line: str) -> str:
    """Drop a # comment, unless the # is inside quotes or not preceded by a space."""
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i].rstrip()
    return line.rstrip()


def _scalar(raw: str | None, n: int):
    if raw is None or raw == "":
        return None
    if raw[0] == "'":
        if len(raw) < 2 or raw[-1] != "'":
            raise ValueError(f"line {n}: unterminated single-quoted value")
        return raw[1:-1].replace("''", "'")
    if raw[0] == '"':
        if len(raw) < 2 or raw[-1] != '"':
            raise ValueError(f"line {n}: unterminated double-quoted value")
        inner = raw[1:-1]
        if re.search(r'\\[^"\\]', inner):
            raise ValueError(f"line {n}: backslashes in double quotes aren't supported; use single quotes")
        return inner.replace('\\"', '"').replace("\\\\", "\\")
    if raw[0] in "[{&*!|>":
        raise ValueError(f"line {n}: only plain or quoted values are supported, not {raw[0]!r}")
    return int(raw) if re.fullmatch(r"-?\d+", raw) else raw


def parse(text: str) -> dict:
    """Parse the scm.yaml subset described in this module's docstring into a dict."""
    out, items, current, list_key = {}, None, None, None
    for n, line in enumerate(text.splitlines(), start=1):
        if "\t" in line[:len(line) - len(line.lstrip())]:
            raise ValueError(f"line {n}: indent with spaces, not a tab")
        line = _strip_comment(line)
        if not line.strip():
            continue
        m = LINE.match(line)
        if not m:
            raise ValueError(f"line {n}: not understood: {line.strip()!r}")
        indent, key, value = len(m["indent"]), m["key"], _scalar(m["value"], n)
        if m["dash"]:
            if items is None or indent == 0:
                raise ValueError(f"line {n}: a list item must be indented under a list such as repos:")
            current = {key: value}
            items.append(current)
            item_indent = indent + len(m["dash"])
        elif indent == 0:
            if value is None:
                items, list_key, current = [], key, None
                out[key] = items
            else:
                items, current = None, None
                out[key] = value
        elif current is not None and indent == item_indent:
            if value is None:
                raise ValueError(f"line {n}: nested values aren't supported; each repo setting needs a value")
            current[key] = value
        else:
            raise ValueError(f"line {n}: unexpected indentation")
    return out


def load_config(path) -> dict:
    """Read and check scm.yaml.

    Returns:
        {"min_group_size": int or None, "default_key_pattern": str or None, "repos": [dict, ...]}
    Raises:
        ValueError: naming the line or field at fault.
    """
    config = parse(Path(path).read_text(encoding="utf-8"))
    unknown = set(config) - TOP_LEVEL
    if unknown:
        raise ValueError(f"unknown settings in {path}: {sorted(unknown)}")
    repos = config.get("repos")
    if not isinstance(repos, list) or not repos:
        raise ValueError(f"{path} needs a repos: list with at least one repo")
    size = config.get("min_group_size")
    if size is not None and not isinstance(size, int):
        raise ValueError(f"min_group_size must be a whole number, got {size!r}")
    for pattern in [config.get("default_key_pattern"), *(r.get("key_pattern") for r in repos)]:
        if pattern is not None:
            scm_keys.KeyMatcher(str(pattern))
    for number, repo in enumerate(repos, start=1):
        platform = repo.get("platform")
        if platform not in scm_adapter.known_platforms():
            raise ValueError(f"repo {number}: platform must be one of {sorted(scm_adapter.known_platforms())}, "
                             f"got {platform!r}")
        missing = [f for f in scm_adapter.required_fields(platform) if not repo.get(f)]
        if missing:
            raise ValueError(f"repo {number} ({platform}) is missing {', '.join(missing)}")
    return {"min_group_size": size, "default_key_pattern": config.get("default_key_pattern"), "repos": repos}
