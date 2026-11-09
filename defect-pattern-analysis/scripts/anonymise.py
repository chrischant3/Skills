#!/usr/bin/env python3
"""Remove every person identifier from Jira and source control JSON before any analysis.

Runs before any analysis script, classification input or output. With MCP fetching, the
model has seen the raw data once, during the fetch step; with the REST fallback it never
sees names at all.

Usage: anonymise.py <raw_dir> <clean_dir>

Person detection is structural, not a flat key list:
- Jira user objects (Cloud: accountId; Data Center: name, key and emailAddress), GitLab
  users (username), Azure DevOps identities (uniqueName, displayName) and git
  name/email pairs are replaced by {"person": "[person]"}. Status, issue type, component and
  other named Jira entities are never treated as people.
- Changelog items for person fields (assignee, reporter, creator, or any item whose
  value is a known person) keep their shape but lose the person.
- In free text: commit trailers, Jira [~...] mentions, ADF mention nodes and email
  addresses are always removed. Display names, name parts, usernames and account ids
  are removed when they belong to a person found anywhere in the input.
- Every @handle in prose is removed, whether or not the person appears elsewhere in
  the input. Code is protected: handles inside fenced blocks, inline code, Jira
  {code}/{noformat}/{{...}} and ADF code are kept, as are well-known code words
  (@Override, @media, @Test, ...) and handles used like code (@app.route(...),
  @types/node). Addresses such as logo@2x.png aren't handles at all. A handle that
  matches a known person is removed even inside code. The trade-off: an unusual
  annotation written in prose, outside any code formatting, is removed too.

Every person, in structured fields and in text alike, becomes the same plain [person]
placeholder. Nothing counts distinct people, so there is no salt, hash or pseudonym:
two people can't be told apart, and nothing can be reversed or joined across runs.
"""

import json
import re
import sys
from pathlib import Path

import jira_normalise

PLACEHOLDER = "[person]"
TRAILER_PLACEHOLDER = "[trailer removed]"
MARKER = {"by": "anonymise.py", "version": 3}
MARKER_KEY = "_anonymised"
INGEST_REPORT = "_ingest.json"
ISSUE_KEY = re.compile(r"[A-Z][A-Z0-9_]*-\d+")

# Any of these keys marks a dict as a person: Jira Cloud and Data Center users, GitLab
# users, Azure DevOps identities and git author/committer objects.
PERSON_MARKER_KEYS = {"accountId", "emailAddress", "email", "uniqueName", "username", "displayName"}
# Values that identify a person, learnt so they can be removed from free text too.
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
# Code words that look like @handles: annotations, decorators, CSS and Sass at-rules,
# doc tags. Never redacted, even in prose and even if a person's handle matches.
CODE_WORDS = {"override", "media", "import", "keyframes", "font-face", "supports", "charset", "namespace",
              "page", "layer", "container", "test", "param", "return", "returns", "throws", "deprecated",
              "inject", "injectable", "autowired", "component", "service", "bean", "entity", "table", "column",
              "id", "transactional", "before", "after", "beforeeach", "aftereach", "beforeall", "afterall",
              "mock", "injectmocks", "restcontroller", "controller", "repository", "configuration",
              "requestmapping", "getmapping", "postmapping", "putmapping", "deletemapping", "pathvariable",
              "requestbody", "requestparam", "valid", "notnull", "nullable", "nonnull", "suppresswarnings",
              "functionalinterface", "jsonproperty", "jsonignore", "property", "staticmethod", "classmethod",
              "dataclass", "abstractmethod", "cached_property", "input", "output", "viewchild", "hostlistener",
              "ngmodule", "mixin", "include", "extend", "use", "forward", "if", "else", "each", "function",
              "font-feature-values", "counter-style", "property", "layer", "tailwind", "apply", "see", "since",
              "link", "type", "typedef", "example", "todo"}
FILE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "bmp", "pdf", "js", "mjs", "ts", "tsx",
                   "jsx", "css", "scss", "less", "html", "json", "py", "java", "kt", "cs", "go", "rb", "md",
                   "txt", "yml", "yaml", "xml", "lock", "zip", "gz", "jar", "dll"}

TRAILER = re.compile(r"(?im)^[ \t]*(signed-off-by|co-authored-by|reviewed-by|acked-by|tested-by|reported-by):.*$")
JIRA_MENTION = re.compile(r"\[~accountid:[^\]]*\]|\[~[^\]\s][^\]]*\]", re.IGNORECASE)
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.([A-Za-z]{2,24})(?![\w-])")
HANDLE = re.compile(r"(?<![\w@./])@([A-Za-z0-9_](?:[A-Za-z0-9_.\-]*[A-Za-z0-9_])?)")
# Code regions in plain or wiki text: Markdown fences and inline code, Jira {code}, {noformat} and {{...}}.
CODE_REGION = re.compile(r"```.*?```|\{code(?::[^}]*)?\}.*?\{code\}|\{noformat\}.*?\{noformat\}|\{\{.*?\}\}|`[^`\n]+`",
                         re.DOTALL)


def _word_alternation(words, flags=0):
    """Compile a whole-word regex matching any of words, longest first."""
    ordered = sorted({w for w in words if w}, key=len, reverse=True)
    if not ordered:
        return None
    return re.compile(r"(?<![\w])(?:" + "|".join(re.escape(w) for w in ordered) + r")(?![\w])", flags)


def _already_clean(value: str) -> bool:
    return value == PLACEHOLDER


def is_person(obj) -> bool:
    """True if obj is a structural person record (user, identity or git signature)."""
    return isinstance(obj, dict) and any(k in obj for k in PERSON_MARKER_KEYS)


def _person_values(obj: dict) -> list[str]:
    return [str(obj[k]) for k in PERSON_ID_KEYS if isinstance(obj.get(k), (str, int)) and str(obj[k]).strip()]


class Anonymiser:
    """Learns who the people are in a set of documents, then scrubs them.

    Call learn() with every document in the run before scrub(), so a person named in
    one file is removed from all of them.
    """

    def __init__(self):
        self._identifiers: set[str] = set()     # lower-case identifiers of known people
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
        for v in values:
            self._identifiers.add(v.lower())
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

    def _compiled(self):
        if self._patterns is None:
            parts = {p for p in self._name_parts if p.lower() not in self._protected}
            self._patterns = (_word_alternation(self._literals, re.IGNORECASE), _word_alternation(parts))
        return self._patterns

    def _is_known_handle(self, handle: str) -> bool:
        h = handle.lower()
        if h in self._handles:
            return True
        name_parts = {p.lower() for p in self._name_parts} - self._protected - CODE_WORDS
        return any(seg in name_parts for seg in re.split(r"[._\-]", h) if len(seg) >= 3)

    def _handle_replacement(self, match, in_code: bool) -> str:
        handle = match.group(1)
        if handle.lower() in CODE_WORDS:
            return match.group(0)
        if self._is_known_handle(handle):
            return PLACEHOLDER
        following = match.string[match.end():match.end() + 1]
        if in_code or following in ("(", "/"):
            return match.group(0)
        return PLACEHOLDER

    def _scrub_handles(self, text: str, in_code: bool) -> str:
        if in_code:
            return HANDLE.sub(lambda m: self._handle_replacement(m, True), text)
        out, last = [], 0
        for region in CODE_REGION.finditer(text):
            out.append(HANDLE.sub(lambda m: self._handle_replacement(m, False), text[last:region.start()]))
            out.append(HANDLE.sub(lambda m: self._handle_replacement(m, True), region.group(0)))
            last = region.end()
        out.append(HANDLE.sub(lambda m: self._handle_replacement(m, False), text[last:]))
        return "".join(out)

    def scrub_text(self, text: str, in_code: bool = False) -> str:
        """Remove person identifiers from free text, leaving code and file paths intact.

        Args:
            text: the text to clean.
            in_code: True when the whole string is code (such as an ADF code block), so
                @handles are kept unless they match a known person.
        """
        literals, name_parts = self._compiled()
        text = TRAILER.sub(TRAILER_PLACEHOLDER, text)
        text = JIRA_MENTION.sub(PLACEHOLDER, text)
        text = EMAIL.sub(lambda m: m.group(0) if m.group(1).lower() in FILE_EXTENSIONS else PLACEHOLDER, text)
        text = self._scrub_handles(text, in_code)
        if literals:
            text = literals.sub(PLACEHOLDER, text)
        if name_parts:
            text = name_parts.sub(PLACEHOLDER, text)
        return text

    def _scrub_person(self, obj: dict) -> dict:
        out = {"person": PLACEHOLDER}
        out.update({k: v for k, v in obj.items() if k in PERSON_SAFE_KEYS})
        return out

    def _scrub_changelog_item(self, item: dict) -> dict:
        out = {}
        for k, v in item.items():
            if k in ("from", "to", "fromString", "toString") and v is not None:
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
        return any(isinstance(item.get(k), str) and item[k].lower() in self._identifiers for k in ("from", "to"))

    def scrub(self, obj, in_code: bool = False):
        """Return a copy of obj with every person replaced by the [person] placeholder.

        in_code is set internally for ADF code blocks and code-marked text.
        """
        if isinstance(obj, list):
            return [self.scrub(v, in_code) for v in obj]
        if isinstance(obj, str):
            return self.scrub_text(obj, in_code)
        if not isinstance(obj, dict):
            return obj
        marks = obj.get("marks") if isinstance(obj.get("marks"), list) else []
        in_code = in_code or obj.get("type") == "codeBlock" or any(
            isinstance(m, dict) and m.get("type") == "code" for m in marks)
        if is_person(obj):
            return self._scrub_person(obj)
        if obj.get("type") == "mention" and isinstance(obj.get("attrs"), dict):
            return {"type": "mention", "attrs": {"text": PLACEHOLDER}}
        if "field" in obj and ("fromString" in obj or "toString" in obj) and self._is_person_item(obj):
            return self._scrub_changelog_item(obj)
        out = {}
        for k, v in obj.items():
            if k in PERSON_STRING_KEYS and isinstance(v, str):
                out[k] = PLACEHOLDER
            else:
                out[k] = self.scrub(v, in_code)
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
        print(next(line for line in __doc__.splitlines() if line.startswith("Usage:")), file=sys.stderr)
        return 2
    n = anonymise_dir(args[0], args[1])
    print(f"Anonymised {n} files -> {args[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
