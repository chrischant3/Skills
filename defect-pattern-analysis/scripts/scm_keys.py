#!/usr/bin/env python3
"""Find Jira issue keys in source control text: titles, descriptions, branch names, commits.

Each repo can declare its own key_pattern (a regular expression) in scm.yaml, for teams
whose convention isn't the standard Jira key, such as ACC_123 in branch names. Matching
ignores case, and every match is normalised to the standard form, so MEM_123, mem 123 and
MEM-123 all become MEM-123.

Near-misses are rejected:
- A match must stand on its own: ABC-12a and XABC-12 are not ABC-12.
- Keys inside URLs are ignored (a path such as /ABC-12/logo.png isn't a reference),
  except Jira links of the form .../browse/ABC-12.
- With a project list, only keys from those projects count, so strings that look like
  keys but aren't, such as UTF-8 or v1-2, are dropped.
"""

import re

STANDARD_KEY_PATTERN = r"[A-Z][A-Z0-9]+-\d+"
URL = re.compile(r"https?://\S+")
JIRA_BROWSE = re.compile(r"/browse/([A-Za-z][A-Za-z0-9]*-\d+)(?![\w])")
KEY_PARTS = re.compile(r"([A-Za-z][A-Za-z0-9]*?)[-_ #]?(\d+)\W*$")


def normalise_key(raw: str) -> str | None:
    """Return raw as a standard key such as MEM-123, or None if it holds no key.

    The project part is the letters and digits before the last run of digits, with one
    optional separator (-, _, space or #) between them. Leading zeros are dropped.
    """
    match = KEY_PARTS.search(raw.strip())
    if not match:
        return None
    return f"{match.group(1).upper()}-{int(match.group(2))}"


def _without_urls(text: str) -> str:
    """Replace each URL with the Jira key it links to (for /browse/ links) or a space."""

    def keep_jira_link(url):
        found = JIRA_BROWSE.search(url.group(0))
        return f" {found.group(1)} " if found else " "

    return URL.sub(keep_jira_link, text)


class KeyMatcher:
    """Finds normalised issue keys in text for one repo's convention.

    Args:
        pattern: the repo's key_pattern regex, or None for the standard Jira key format.
            Matched without regard to case.
        projects: Jira project keys in the run. When given, keys from other projects are
            dropped. Leave empty to return every well-formed key.
    Raises:
        ValueError: if pattern is empty or isn't a valid regular expression.
    """

    def __init__(self, pattern: str | None = None, projects=()):
        pattern = STANDARD_KEY_PATTERN if pattern is None else pattern
        if not isinstance(pattern, str) or not pattern.strip():
            raise ValueError("key_pattern must be a non-empty regular expression")
        try:
            re.compile(
                pattern
            )  # on its own first, so wrapping can't hide an unbalanced bracket
            self._regex = re.compile(
                rf"(?<![A-Za-z0-9])(?:{pattern})(?![A-Za-z0-9])", re.IGNORECASE
            )
        except re.error as err:
            raise ValueError(
                f"key_pattern {pattern!r} is not a valid regular expression: {err}"
            ) from None
        self._projects = {p.upper() for p in projects}

    def find(self, text: str | None) -> set[str]:
        """Return the set of normalised keys in text."""
        keys = set()
        for match in self._regex.finditer(_without_urls(text or "")):
            key = normalise_key(match.group(0))
            if key and (not self._projects or key.split("-")[0] in self._projects):
                keys.add(key)
        return keys
