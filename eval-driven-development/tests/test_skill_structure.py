"""Structure checks for the eval-driven-development skill and the repo's eval cases.

These need no model and no network. They check that the skill is well formed, that its
links resolve, that every eval case can load, and that nothing private is in the package.
"""

import json
import re
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
ROOT = SKILL_DIR.parent
SKILL = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
CASES = sorted(p for p in (ROOT / "evals").iterdir() if p.is_dir() and p.name != "results")
# The tests hold the patterns they search for, so they are left out of the scan.
PACKAGE_FILES = [p for p in SKILL_DIR.rglob("*.md") if "tests" not in p.relative_to(SKILL_DIR).parts]
GRADER_TYPES = {"regex", "tool_used", "tool_order", "file_exists", "llm", "baseline"}


def frontmatter(text: str) -> str:
    """The settings block at the top of a Markdown file, without its fences."""
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert match, "file must start with a settings block between --- lines"
    return match[1]


def section(heading: str) -> str:
    """The body of one second-level section of SKILL.md."""
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", SKILL, re.M | re.S)
    assert match, f"SKILL.md has no section called {heading!r}"
    return match[1]


def test_frontmatter_names_the_skill_after_its_folder():
    assert re.search(r"^name: eval-driven-development$", frontmatter(SKILL), re.M)


def test_description_says_when_to_use_it_and_when_not_to():
    front = " ".join(frontmatter(SKILL).split())
    assert "Use when" in front and "Not for" in front
    assert len(front) < 1024


@pytest.mark.parametrize("heading", ["Overview", "When to Use", "The Loop", "When an Eval Fails",
                                     "Common Rationalisations", "Red Flags", "Verification"])
def test_skill_has_the_expected_sections(heading):
    assert section(heading).strip()


def test_every_relative_link_resolves():
    for doc in [SKILL_DIR / "SKILL.md", *sorted((SKILL_DIR / "references").glob("*.md"))]:
        for target in re.findall(r"\]\((?!https?://)([^)#]+)", doc.read_text(encoding="utf-8")):
            assert (doc.parent / target).is_file(), f"{doc.name} links to missing {target}"


def test_the_numbered_steps_name_no_runner():
    steps = section("The Loop").split("### 1.", 1)[1]
    assert not re.search(r"claude plugin|whitney|--[a-z]", steps, re.I)


def test_the_skill_states_both_pass_marks():
    assert re.search(r"0\.8 per case.*1\.0 for safety cases", SKILL)


def test_this_skill_has_eval_cases_including_safety_cases():
    own = [c for c in CASES if c.name.startswith("eval-driven-development--")]
    assert len(own) >= 5
    assert any("safety" in frontmatter((c / "prompt.md").read_text(encoding="utf-8")) for c in own)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_each_case_has_a_tagged_prompt_and_a_valid_grader(case):
    front = frontmatter((case / "prompt.md").read_text(encoding="utf-8"))
    skill = case.name.split("--")[0]
    assert (ROOT / skill / "SKILL.md").is_file(), "a case name starts with its skill's folder name"
    assert re.search(rf"^tags: \[{re.escape(skill)}\b", front, re.M)
    graders = sorted((case / "graders").glob("*.md"))
    assert graders, "a case with no grader will not load"
    for grader in graders:
        kind = re.search(r"^type: (\w+)$", frontmatter(grader.read_text(encoding="utf-8")), re.M)
        assert kind and kind[1] in GRADER_TYPES, f"{grader.name} has an unknown grader type"
    assert any("type: llm" in g.read_text(encoding="utf-8") or "type: regex" in g.read_text(encoding="utf-8")
               for g in graders), "each case needs a grader on the result"


def test_model_judges_state_both_outcomes():
    for grader in (ROOT / "evals").glob("*/graders/*.md"):
        text = grader.read_text(encoding="utf-8")
        if "type: llm" in text:
            assert "PASS if" in text and "FAIL if" in text, f"{grader} must state PASS and FAIL"


def test_every_skill_folder_is_listed_in_the_plugin_manifest():
    manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    listed = {Path(p).name for p in manifest["skills"]}
    on_disk = {p.parent.name for p in ROOT.glob("*/SKILL.md")}
    assert listed == on_disk


@pytest.mark.parametrize("path", [*PACKAGE_FILES, *(ROOT / "evals").glob("eval-driven-development--*/**/*.md")],
                         ids=lambda p: str(p.relative_to(ROOT)))
def test_nothing_private_is_in_the_package(path):
    text = path.read_text(encoding="utf-8")
    assert not re.search(r"/Users/|/home/\w", text), "no personal paths"
    for address in re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text):
        assert address.endswith(("example.com", "example.org", "example.net")), f"unexpected address {address}"
    assert not re.search(r"(api[_-]?key|token|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}", text, re.I)
