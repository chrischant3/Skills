"""Shared test setup: puts scripts/ on the import path and loads the synthetic fixtures.

Every fixture is synthetic. No test calls a live API or MCP server.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def load_fixture(relative: str):
    """Return the parsed JSON fixture at tests/fixtures/<relative>."""
    return json.loads((FIXTURES / relative).read_text(encoding="utf-8"))


@pytest.fixture
def people():
    """The synthetic people seeded into every fixture."""
    return load_fixture("people.json")["people"]


@pytest.fixture
def identifiers(people):
    """Every string that identifies a seeded person, for leak checks."""
    return person_identifiers(people)


def person_identifiers(people) -> set[str]:
    """Collect names, name parts, emails, account ids, usernames and handles for the given people."""
    found = set()
    for p in people:
        found.update({p["display_name"], p["email"], p["account_id"], p["dc_username"], p["dc_key"],
                      p["scm_username"], p["ado_unique_name"], p["ado_id"]})
        found.update(part for part in p["display_name"].split() if len(part) >= 3)
    found.update(load_fixture("people.json")["customer_emails"])
    return found


def all_text_under(path: Path) -> str:
    """Concatenate every file under path, so a leak anywhere is found."""
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(path.rglob("*")) if p.is_file())
