"""Behaviour tests for the skill as a public package: self-contained, nothing tied to one person's machine or employer."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TEXT_SUFFIXES = {".md", ".json", ".py", ".yaml", ".csv", ".txt"}
PACKAGE_FILES = sorted(
    p for p in ROOT.rglob("*")
    if p.suffix in TEXT_SUFFIXES and "__pycache__" not in p.parts and p.name != Path(__file__).name
)

# Phrases that only make sense on the author's machine or in the private notes the skill was built from.
PRIVATE_PATTERNS = [
    r"~/",
    r"/Users/",
    r"skills-to-develop",
    r"HANDOVER",
    r"draft-implementation",
    r"claude\.ai/artifact",
]


@pytest.mark.parametrize("path", PACKAGE_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_references_to_private_documents(path):
    text = path.read_text(encoding="utf-8")
    hits = [pat for pat in PRIVATE_PATTERNS if re.search(pat, text)]
    assert hits == []


@pytest.mark.parametrize("path", PACKAGE_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_fixture_emails_use_reserved_example_domains(path):
    domains = set(re.findall(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)", path.read_text(encoding="utf-8")))
    real = {d for d in domains if not re.search(r"(^|\.)example\.(com|org|net)$", d) and not re.search(r"\.(png|jpe?g|svg|webp|gif)$", d)}
    assert real == set()


def test_every_reference_named_in_skill_md_exists():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    named = set(re.findall(r"(?:reference|scripts)/[\w.-]+", skill))
    missing = [n for n in sorted(named) if not (ROOT / n).exists()]
    assert named and missing == []


def test_every_reference_file_is_signposted_from_skill_md():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    unlisted = [p.name for p in (ROOT / "reference").iterdir() if f"reference/{p.name}" not in skill]
    assert unlisted == []
