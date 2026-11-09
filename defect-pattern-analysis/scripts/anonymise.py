#!/usr/bin/env python3
"""Remove every person identifier from Jira and source control JSON before any analysis.

Usage: anonymise.py <raw_dir> <clean_dir>

Person detection is structural, not a flat key list:
- Jira user objects (Cloud: accountId; Data Center: name, key and emailAddress), GitLab
  users (username), Azure DevOps identities (uniqueName, displayName) and git
  name/email pairs are replaced by a pseudonym. Status, issue type, component and
  other named Jira entities are never treated as people.
- Changelog items for person fields (assignee, reporter, creator, or any item whose
  value is a known person) keep their shape but lose the person.
- In free text: commit trailers, Jira [~...] mentions, ADF mention nodes and email
  addresses are always removed. Display names, name parts, usernames and account ids
  are removed when they belong to a person found anywhere in the input.
- @handles are removed only when they match a known person (their username, email
  local part, a handle built from their name, or a handle that contains one of their
  name parts). This keeps code such as @Override, @media and logo@2x.png intact. The
  trade-off: an @handle for someone who never appears as a user anywhere in the input
  is left alone.

Pseudonyms are salted with a random per-run salt that is held in memory only, so they
cannot be reversed or joined across runs. They exist so scripts can count distinct
people. They never appear in any report.
"""

import hashlib
import hmac
import json
import re
import secrets
import sys
from pathlib import Path

import jira_normalise

PLACEHOLDER = "[person]"
TRAILER_PLACEHOLDER = "[trailer removed]"
MARKER = {"by": "anonymise.py", "version": 2}
MARKER_KEY = "_anonymised"
INGEST_REPORT = "_ingest.json"
ISSUE_KEY = re.compile(r"[A-Z][A-Z0-9_]*-\d+")

# Any of these keys marks a dict as a person: Jira Cloud and Data Center users, GitLab
# users, Azure DevOps identities and git author/committer objects.
PERSON_MARKER_KEYS = {"accountId", "emailAddress", "email", "uniqueName", "username", "displayName"}
# Values worth remembering about a person, in order of preference for their pseudonym key.
PERSON_ID_KEYS = ("accountId", "key", "username", "uniqueName", "name", "emailAddress", "email", "displayName", "id")
# Non-identifying facts on a person object that analysis may need.
PERSON_SAFE_KEYS = {"vote", "isRequired", "hasDeclined", "isFlagged", "date"}
# Flat string fields that hold a person in GitLab and git exports.
PERSON_STRING_KEYS = {"author_name", "author_email", "committer_name", "committer_email",
                      "authorName", "authorEmail", "committerName", "committerEmail"}
PERSON_CHANGELOG_FIELDS = {"assignee", "reporter", "creator"}
# Changelog fields whose from/to strings are names of Jira entities, not free text.
ENTITY_CHANGELOG_FIELDS = {"status", "component", "components", "issuetype", "priority", "resolution",
                           "fix version", "fixversions", "version", "labels", "project"}
# Code words that look like @handles. Never redacted, even if a person's handle matches.
CODE_WORDS = {"override", "media", "import", "keyframes", "font-face", "supports", "charset", "namespace",
              "page", "layer", "container", "test", "param", "return", "returns", "throws", "deprecated",
              "inject", "autowired", "component", "service", "bean", "property", "staticmethod",
              "classmethod", "dataclass", "input", "output", "mixin", "include", "extend", "use", "forward"}
FILE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "bmp", "pdf", "js", "mjs", "ts", "tsx",
                   "jsx", "css", "scss", "less", "html", "json", "py", "java", "kt", "cs", "go", "rb", "md",
                   "txt", "yml", "yaml", "xml", "lock", "zip", "gz", "jar", "dll"}

TRAILER = re.compile(r"(?im)^[ \t]*(signed-off-by|co-authored-by|reviewed-by|acked-by|tested-by|reported-by):.*$")
JIRA_MENTION = re.compile(r"\[~accountid:[^\]]*\]|\[~[^\]\s][^\]]*\]", re.IGNORECASE)
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.([A-Za-z]{2,24})(?![\w-])")
PSEUDONYM = re.compile(r"person_[0-9a-f]{12}")
HANDLE = re.compile(r"(?<![\w@./])@([A-Za-z0-9_](?:[A-Za-z0-9_.\-]*[A-Za-z0-9_])?)")


def _word_alternation(words, flags=0):
    """Compile a whole-word regex matching any of words, longest first."""
    ordered = sorted({w for w in words if w}, key=len, reverse=True)
    if not ordered:
        return None
    return re.compile(r"(?<![\w])(?:" + "|".join(re.escape(w) for w in ordered) + r")(?![\w])", flags)


def _already_clean(value: str) -> bool:
    return value == PLACEHOLDER or PSEUDONYM.fullmatch(value) is not None


def is_person(obj) -> bool:
    """True if obj is a structural person record (user, identity or git signature)."""
    return isinstance(obj, dict) and any(k in obj for k in PERSON_MARKER_KEYS)


def _person_values(obj: dict) -> list[str]:
    return [str(obj[k]) for k in PERSON_ID_KEYS if isinstance(obj.get(k), (str, int)) and str(obj[k]).strip()]


class Anonymiser:
    """Learns who the people are in a set of documents, then scrubs them.

    Call learn() with every document in the run before scrub(), so a person named in
    one file is removed from all of them.

    Args:
        salt: bytes for the pseudonym HMAC. Leave as None in real runs to draw a fresh
            random salt; it is held in memory only and never written anywhere.
    """

    def __init__(self, salt: bytes | None = None):
        self._salt = salt if salt is not None else secrets.token_bytes(32)
        self._canonical: dict[str, str] = {}   # any identifier (lower case) -> canonical identifier
        self._literals: set[str] = set()        # removed as whole words, any case
        self._name_parts: set[str] = set()      # capitalised name parts, removed case-sensitively
        self._handles: set[str] = set()         # lower-case @handles
        self._protected: set[str] = set()       # lower-case words from Jira entity names
        self._patterns = None

    # --- learning --------------------------------------------------------------------

    def learn(self, docs) -> None:
        """Record every person and every protected entity name found in docs."""
        for doc in docs:
            self._walk(doc)
        self._patterns = None

    def _walk(self, obj) -> None:
        if isinstance(obj, list):
            for item in obj:
                self._walk(item)
            return
        if not isinstance(obj, dict):
            return
        if is_person(obj):
            self._add_person(_person_values(obj), obj.get("displayName") or obj.get("name"),
                             learn_name=obj.get("accountType") != "app")
            return
        if obj.get("type") == "mention" and isinstance(obj.get("attrs"), dict):
            attrs = obj["attrs"]
            text = str(attrs.get("text", "")).lstrip("@")
            self._add_person([str(v) for v in (attrs.get("id"), text) if v], text)
            return
        for role in ("author", "committer"):
            values = [obj[k] for k in (f"{role}_name", f"{role}_email", f"{role}Name", f"{role}Email")
                      if isinstance(obj.get(k), str)]
            if values:
                self._add_person(values, values[0])
        if "field" in obj and ("fromString" in obj or "toString" in obj):
            self._learn_changelog_item(obj)
        name = obj.get("name")
        if isinstance(name, str) and any(k in obj for k in ("id", "self", "key")):
            self._protect(name)
        if isinstance(obj.get("labels"), list):
            for label in obj["labels"]:
                if isinstance(label, str):
                    self._protect(label)
        for value in obj.values():
            self._walk(value)

    def _learn_changelog_item(self, item: dict) -> None:
        field = str(item.get("fieldId") or item.get("field") or "").lower()
        self._protect(str(item.get("field", "")))
        if field in PERSON_CHANGELOG_FIELDS:
            for raw, shown in (("from", "fromString"), ("to", "toString")):
                values = [str(v) for v in (item.get(raw), item.get(shown)) if v]
                if values:
                    self._add_person(values, item.get(shown))
        elif field in ENTITY_CHANGELOG_FIELDS:
            for shown in ("fromString", "toString"):
                if isinstance(item.get(shown), str):
                    self._protect(item[shown])

    def _protect(self, name: str) -> None:
        self._protected.update(w.lower() for w in re.findall(r"[\w'-]+", name))

    def _add_person(self, values: list[str], display: str | None, learn_name: bool = True) -> None:
        values = [v for v in values if v.strip() and not _already_clean(v)]
        if not values:
            return
        canonical = next((self._canonical[v.lower()] for v in values if v.lower() in self._canonical), values[0])
        for v in values:
            self._canonical.setdefault(v.lower(), canonical)
            if len(v) >= 3:
                self._literals.add(v)
            if "@" in v:
                self._handles.add(v.split("@")[0].lower())
            elif " " not in v:
                self._handles.add(v.lower())
        if display and learn_name and not _already_clean(display):
            self._learn_name(display)

    def _learn_name(self, display: str) -> None:
        parts = [p for p in re.split(r"[\s]+", display.strip()) if p]
        self._literals.add(display)
        capitalised = [p for p in parts if p[:1].isupper() and len(p) >= 2]
        self._name_parts.update(capitalised)
        low = [p.lower() for p in capitalised]
        if len(low) >= 2:
            first, last = low[0], low[-1]
            self._handles.update({f"{first}.{last}", f"{first}{last}", f"{first}_{last}", f"{first}-{last}",
                                  f"{first[0]}{last}", f"{first[0]}.{last}", f"{first}{last[0]}", f"{first}.{last[0]}"})
        self._handles.update(low)

    # --- scrubbing -------------------------------------------------------------------

    def pseudonym(self, value: str) -> str:
        """Return the salted pseudonym for an identifier, consistent for one person within a run."""
        canonical = self._canonical.get(str(value).lower(), str(value))
        digest = hmac.new(self._salt, canonical.lower().encode("utf-8"), hashlib.sha256).hexdigest()
        return "person_" + digest[:12]

    def _compiled(self):
        if self._patterns is None:
            parts = {p for p in self._name_parts if p.lower() not in self._protected}
            self._patterns = (_word_alternation(self._literals, re.IGNORECASE), _word_alternation(parts))
        return self._patterns

    def _is_person_handle(self, handle: str) -> bool:
        h = handle.lower()
        if h in CODE_WORDS:
            return False
        if h in self._handles:
            return True
        name_parts = {p.lower() for p in self._name_parts} - self._protected - CODE_WORDS
        return any(seg in name_parts for seg in re.split(r"[._\-]", h) if len(seg) >= 3)

    def scrub_text(self, text: str) -> str:
        """Remove person identifiers from free text, leaving code and file paths intact."""
        literals, name_parts = self._compiled()
        text = TRAILER.sub(TRAILER_PLACEHOLDER, text)
        text = JIRA_MENTION.sub(PLACEHOLDER, text)
        text = EMAIL.sub(lambda m: m.group(0) if m.group(1).lower() in FILE_EXTENSIONS else PLACEHOLDER, text)
        text = HANDLE.sub(lambda m: PLACEHOLDER if self._is_person_handle(m.group(1)) else m.group(0), text)
        if literals:
            text = literals.sub(PLACEHOLDER, text)
        if name_parts:
            text = name_parts.sub(PLACEHOLDER, text)
        return text

    def _scrub_person(self, obj: dict) -> dict:
        values = _person_values(obj)
        out = {"pseudonym": self.pseudonym(values[0]) if values else self.pseudonym(json.dumps(obj, sort_keys=True))}
        out.update({k: v for k, v in obj.items() if k in PERSON_SAFE_KEYS})
        return out

    def _scrub_changelog_item(self, item: dict) -> dict:
        out = {}
        for k, v in item.items():
            if k in ("from", "to") and v is not None:
                out[k] = v if _already_clean(str(v)) else self.pseudonym(str(v))
            elif k in ("fromString", "toString") and v is not None:
                out[k] = PLACEHOLDER
            else:
                out[k] = self.scrub(v)
        return out

    def _is_person_item(self, item: dict) -> bool:
        field = str(item.get("fieldId") or item.get("field") or "").lower()
        if field in PERSON_CHANGELOG_FIELDS:
            return True
        if field in ENTITY_CHANGELOG_FIELDS:
            return False
        return any(isinstance(item.get(k), str) and item[k].lower() in self._canonical for k in ("from", "to"))

    def scrub(self, obj):
        """Return a copy of obj with every person replaced by a pseudonym or placeholder."""
        if isinstance(obj, list):
            return [self.scrub(v) for v in obj]
        if isinstance(obj, str):
            return self.scrub_text(obj)
        if not isinstance(obj, dict):
            return obj
        if is_person(obj):
            return self._scrub_person(obj)
        if obj.get("type") == "mention" and isinstance(obj.get("attrs"), dict):
            return {"type": "mention", "attrs": {"text": PLACEHOLDER}}
        if "field" in obj and ("fromString" in obj or "toString" in obj) and self._is_person_item(obj):
            return self._scrub_changelog_item(obj)
        out = {}
        for k, v in obj.items():
            if k in PERSON_STRING_KEYS and isinstance(v, str):
                out[k] = self.pseudonym(v)
            else:
                out[k] = self.scrub(v)
        return out


def mark(doc):
    """Wrap or tag a cleaned document so later scripts can check it was anonymised."""
    if isinstance(doc, dict):
        return {MARKER_KEY: dict(MARKER), **doc}
    return {MARKER_KEY: dict(MARKER), "items": doc}


def is_marked(doc) -> bool:
    """True if doc was written by anonymise.py."""
    return isinstance(doc, dict) and isinstance(doc.get(MARKER_KEY), dict) and doc[MARKER_KEY].get("by") == MARKER["by"]


def anonymise_dir(in_dir, out_dir, anonymiser: Anonymiser | None = None) -> int:
    """Anonymise every *.json file in in_dir into out_dir. Returns the number of files written.

    Jira issues, in any shape jira_normalise understands (MCP results or REST files), are
    merged by key and written one file per issue as <KEY>.json, with _ingest.json
    reporting coverage and gaps. Any other JSON (such as source control exports) keeps
    its file name. Every input is read before any is written, so a person named in one
    file is removed from all of them. Nothing else is written.
    """
    in_dir, out_dir = Path(in_dir), Path(out_dir)
    if in_dir.resolve() == out_dir.resolve():
        raise ValueError("clean output must go to a different folder from the raw input")
    manifest, docs = None, []
    for path in sorted(p for p in in_dir.glob("*.json") if p.is_file()):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if path.name == jira_normalise.MANIFEST_NAME:
            manifest = doc
        else:
            docs.append((path, doc))
    anonymiser = anonymiser or Anonymiser()
    anonymiser.learn([doc for _, doc in docs])

    jira_issues, others = [], []
    for path, doc in docs:
        found = jira_normalise.issues_from_document(doc)
        if found:
            jira_issues += found
        else:
            others.append((path, doc))
    issues = jira_normalise.merge_issues(jira_issues)

    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for issue in issues:
        if not ISSUE_KEY.fullmatch(issue["key"]):
            raise ValueError(f"unexpected issue key {issue['key']!r}")
        _write(out_dir / f"{issue['key']}.json", mark(anonymiser.scrub(issue)))
        written += 1
    for path, doc in others:
        _write(out_dir / path.name, mark(anonymiser.scrub(doc)))
        written += 1
    if issues:
        _write(out_dir / INGEST_REPORT, mark(anonymiser.scrub(jira_normalise.ingest_report(issues, manifest))))
        written += 1
    return written


def _write(path: Path, doc) -> None:
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print(__doc__.splitlines()[2], file=sys.stderr)
        return 2
    n = anonymise_dir(args[0], args[1])
    print(f"Anonymised {n} files -> {args[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
