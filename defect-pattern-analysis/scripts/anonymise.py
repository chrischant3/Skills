#!/usr/bin/env python3
"""Anonymise Jira and SCM JSON exports. Usage: anonymise.py <in_dir> <out_dir>"""
import hashlib, json, os, re, secrets, sys
from pathlib import Path

SALT = secrets.token_hex(16)  # per run, never persisted
PERSON_KEYS = {
    "assignee", "reporter", "creator", "author", "updateAuthor",
    "committer", "committer_name", "committer_email", "author_name",
    "author_email", "displayName", "emailAddress", "accountId",
    "name", "username", "uniqueName", "merged_by", "reviewers",
}
MENTION_PATTERNS = [
    re.compile(r"\[~accountid:[^\]]+\]"),   # Jira mentions
    re.compile(r"\[~[^\]]+\]"),
    re.compile(r"@[A-Za-z0-9_.\-]+"),        # GitLab / ADO @mentions
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),  # email addresses
]
SIGNOFF = re.compile(r"(?im)^(signed-off-by|co-authored-by|reviewed-by):.*$")

def pseudonym(value: str) -> str:
    return "person_" + hashlib.sha256((SALT + value).encode()).hexdigest()[:10]

def scrub_text(text: str) -> str:
    text = SIGNOFF.sub("[trailer removed]", text)
    for pat in MENTION_PATTERNS:
        text = pat.sub("[person]", text)
    return text

def scrub(obj, parent_key=None):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in PERSON_KEYS:
                out[k] = scrub_person(v)
            else:
                out[k] = scrub(v, k)
        return out
    if isinstance(obj, list):
        return [scrub(v, parent_key) for v in obj]
    if isinstance(obj, str):
        return scrub_text(obj)
    return obj

def scrub_person(v):
    if v is None:
        return None
    if isinstance(v, list):
        return [scrub_person(x) for x in v]
    if isinstance(v, dict):
        key = v.get("accountId") or v.get("emailAddress") or v.get("displayName") or json.dumps(v, sort_keys=True)
        return {"id": pseudonym(str(key))}
    return pseudonym(str(v))

def main(in_dir, out_dir):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    for p in Path(in_dir).glob("*.json"):
        data = json.loads(p.read_text())
        Path(out_dir, p.name).write_text(json.dumps(scrub(data), indent=2))
    print(f"Anonymised {len(list(Path(in_dir).glob('*.json')))} files -> {out_dir}")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
