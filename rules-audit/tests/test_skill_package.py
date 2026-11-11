"""Deterministic checks on the files an agent loads when it runs this skill.

Each check guards a property that changes what the agent sees: a missing
reference file, an unclosed code fence or a broken table alters the
instructions themselves, not just their style. They need no model, so they
are free to run on every change.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "SKILL.md"
INSTRUCTION_FILES = [SKILL, *sorted((ROOT / "references").glob("*.md"))]
FILE_IDS = [str(p.relative_to(ROOT)) for p in INSTRUCTION_FILES]

# From docs/skill-anatomy.md ("Keep SKILL.md under 500 lines").
MAX_SKILL_LINES = 500
# The skill loader's limit on the description field.
MAX_DESCRIPTION_CHARS = 1024
FENCE = re.compile(r"^\s*(```|~~~)")


def read(path: Path) -> str:
    """Return a file's text as UTF-8."""
    return path.read_text(encoding="utf-8")


def frontmatter(text: str) -> dict[str, str]:
    """Parse the leading YAML frontmatter into top-level keys and values.

    Handles plain values and folded (`>-`) blocks, which is all this skill
    uses; returns an empty dict when the file has no frontmatter.
    """
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        return {}
    fields: dict[str, str] = {}
    key = None
    for line in match.group(1).splitlines():
        top = re.match(r"^([\w-]+):\s*(.*)$", line)
        if top:
            key, value = top.groups()
            fields[key] = "" if value in (">-", ">", "|", "|-") else value
        elif key and line.startswith(" "):
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return fields


def lines_outside_fences(text: str) -> list[str]:
    """Return the lines that are not inside fenced code blocks."""
    kept, in_fence = [], False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            kept.append(line)
    return kept


def local_links(text: str) -> list[str]:
    """Return the targets of markdown links that point at files in the package."""
    targets = re.findall(r"\]\(([^)\s]+)\)", text)
    return [
        t.split("#")[0]
        for t in targets
        if not re.match(r"^[a-z]+:", t) and not t.startswith("#")
    ]


def table_cell_count(row: str) -> int:
    """Count the cells in a markdown table row.

    Pipes inside backticks and escaped pipes (`\\|`) are content, not
    column separators.
    """
    row = re.sub(r"`[^`]*`", "code", row).replace("\\|", "")
    return row.strip().strip("|").count("|") + 1


def tables(text: str) -> list[list[str]]:
    """Return each markdown table outside code fences as a list of its rows."""
    found, current = [], []
    for line in lines_outside_fences(text) + [""]:
        if line.lstrip().startswith("|"):
            current.append(line.strip())
        elif current:
            found.append(current)
            current = []
    return found


def test_frontmatter_names_the_skill_after_its_directory():
    fields = frontmatter(read(SKILL))
    assert fields.get("name") == ROOT.name
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fields["name"])


def test_description_is_present_and_within_the_loader_limit():
    description = frontmatter(read(SKILL)).get("description", "")
    assert description
    assert len(description) <= MAX_DESCRIPTION_CHARS


def test_skill_md_stays_under_the_size_limit():
    assert len(read(SKILL).splitlines()) < MAX_SKILL_LINES


@pytest.mark.parametrize("path", INSTRUCTION_FILES, ids=FILE_IDS)
def test_code_fences_are_closed(path):
    # An unclosed fence turns every following instruction into example text.
    fences = [line for line in read(path).splitlines() if FENCE.match(line)]
    assert len(fences) % 2 == 0


@pytest.mark.parametrize("path", INSTRUCTION_FILES, ids=FILE_IDS)
def test_every_local_link_resolves(path):
    missing = [t for t in local_links(read(path)) if not (path.parent / t).exists()]
    assert missing == []


def test_every_reference_file_is_linked_from_skill_md():
    linked = {(SKILL.parent / t).resolve() for t in local_links(read(SKILL))}
    unlinked = [p.name for p in INSTRUCTION_FILES[1:] if p.resolve() not in linked]
    assert unlinked == []


@pytest.mark.parametrize("path", INSTRUCTION_FILES[1:], ids=FILE_IDS[1:])
def test_reference_files_do_not_chain_to_other_files(path):
    # References sit one level deep from SKILL.md (rubric item P4).
    chained = [t for t in local_links(read(path)) if t.endswith(".md")]
    assert chained == []


def test_rubric_ids_cited_in_skill_md_exist_in_the_rubric():
    defined = set(
        re.findall(
            r"^- \*\*([A-Z]\d+)\.\*\*", read(ROOT / "references" / "rubric.md"), re.M
        )
    )
    cited = set(re.findall(r"\b([SPQDT]\d)\b", read(SKILL)))
    assert defined
    assert cited - defined == set()


@pytest.mark.parametrize("path", INSTRUCTION_FILES, ids=FILE_IDS)
def test_table_rows_match_their_header(path):
    ragged = [
        row
        for table in tables(read(path))
        for row in table
        if table_cell_count(row) != table_cell_count(table[0])
    ]
    assert ragged == []


@pytest.mark.parametrize("path", INSTRUCTION_FILES, ids=FILE_IDS)
def test_headings_go_no_deeper_than_h3(path):
    # Rubric item S3; the skill should pass its own rubric.
    deep = [
        line for line in lines_outside_fences(read(path)) if re.match(r"^#{4,}\s", line)
    ]
    assert deep == []
