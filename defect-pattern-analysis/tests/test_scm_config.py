"""Behaviour tests for scripts/scm_config.py: reading scm.yaml with the standard library only (F4)."""

import pytest

import scm_config
from conftest import ROOT


def load(tmp_path, text):
    path = tmp_path / "scm.yaml"
    path.write_text(text, encoding="utf-8")
    return scm_config.load_config(path)


def test_the_example_config_shipped_with_the_skill_reads_as_expected():
    config = scm_config.load_config(ROOT / "scm.yaml")
    assert config["min_group_size"] == 5
    assert config["default_key_pattern"] == r"[A-Z][A-Z0-9]+-\d+"
    gitlab, azure = config["repos"]
    assert gitlab == {"platform": "gitlab", "url": "https://gitlab.example.com", "project": "group/checkout-service",
                      "team": "Checkout", "namespace": "group"}
    assert azure == {"platform": "azure", "org": "example-org", "project": "Accounts", "repo": "accounts-api",
                     "team": "Accounts", "key_pattern": r"ACC[-_ ]?\d+"}


def test_quoting_and_comments_follow_yaml_rules(tmp_path):
    config = load(tmp_path, """
# a comment line
repos:
  - platform: gitlab   # trailing comment
    url: "https://gitlab.example.com"
    project: 'group/it''s-a-repo'
    key_pattern: 'MEM[-_ ]?\\d+ # not a comment'
""")
    repo, = config["repos"]
    assert repo["url"] == "https://gitlab.example.com"
    assert repo["project"] == "group/it's-a-repo"
    assert repo["key_pattern"] == r"MEM[-_ ]?\d+ # not a comment"


def test_defaults_apply_when_optional_settings_are_missing(tmp_path):
    config = load(tmp_path, "repos:\n  - platform: gitlab\n    url: https://gitlab.example.com\n    project: g/p\n")
    assert config["default_key_pattern"] is None and config["min_group_size"] is None


@pytest.mark.parametrize("text,problem", [
    ("repos: [a, b]\n", "line 1"),
    ("repos:\n  - platform: gitlab\n    nested:\n      deeper: 1\n", "line 3"),
    ("repos:\n\t- platform: gitlab\n", "tab"),
    ("repos:\n  - platform: gitlab\n    url: \"bad\\d\"\n", "single quotes"),
    ("min_group_size: 5\n", "repos"),
    ("repos:\n  - platform: bitbucket\n", "platform"),
    ("repos:\n  - platform: gitlab\n    project: g/p\n", "url"),
    ("repos:\n  - platform: azure\n    org: o\n    project: p\n", "repo"),
    ("repos:\n  - platform: gitlab\n    url: https://g.example.com\n    project: g/p\n    key_pattern: '('\n", "key_pattern"),
    ("min_group_size: five\nrepos:\n  - platform: gitlab\n    url: https://g.example.com\n    project: g/p\n", "min_group_size"),
])
def test_unsupported_or_incomplete_config_is_refused_with_a_clear_error(tmp_path, text, problem):
    with pytest.raises(ValueError, match=problem):
        load(tmp_path, text)


# --- anything outside the supported subset fails loudly, naming the line ----------------------------

REPO = "repos:\n  - platform: gitlab\n    url: https://g.example.com\n    project: g/p\n"  # lines 1 to 4


@pytest.mark.parametrize("text,line,hint", [
    ("base: &defaults\n" + REPO, 1, "anchor"),
    (REPO + "    team: *defaults\n", 5, "alias"),
    ("repos:\n  - {platform: gitlab, url: x, project: g/p}\n", 2, "flow"),
    ("repos: [gitlab]\n", 1, "flow"),
    (REPO + "    team: |\n      Checkout\n", 5, "multi-line"),
    (REPO + "    team: >\n      Checkout\n", 5, "multi-line"),
    (REPO + "    team: Check\n      out\n", 6, "not understood"),
    (REPO + "    team: 'Check\n      out'\n", 5, "unterminated"),
    ("repos:\n\t- platform: gitlab\n", 2, "tab"),
    (REPO + "    team:\tCheckout\n", 5, "tab"),
    (REPO + "repos:\n  - platform: gitlab\n", 5, "duplicate"),
    (REPO + "    url: https://other.example.com\n", 5, "duplicate"),
    ("min_group_size: 5\nmin_group_size: 6\n" + REPO, 2, "duplicate"),
    ("min_grup_size: 5\n" + REPO, 1, "unknown setting"),
    (REPO + "    key_patern: 'ABC-\\d+'\n", 5, "unknown setting"),
    ("---\n" + REPO, 1, "document marker"),
    (REPO + "...\n", 5, "document marker"),
    (REPO + "    team: yes\n", 5, "quote"),
    (REPO + "    team: null\n", 5, "quote"),
    (REPO + "    team: ~\n", 5, "quote"),
    (REPO + "    team: 1.5\n", 5, "quote"),
    (REPO + "    team: 0x1F\n", 5, "quote"),
    (REPO + "    team: a: b\n", 5, "quote"),
    (REPO + "    team: 'a' 'b'\n", 5, "single-quoted"),
    (REPO + "    team: \"a\" \"b\"\n", 5, "double-quoted"),
    (REPO + "    team: !!str x\n", 5, "tag"),
    (REPO + "    team:\n", 5, "needs a value"),
    ("default_key_pattern:\n" + REPO, 1, "needs a value"),
    ("repos:\n  - platform: gitlab\n     url: https://g.example.com\n", 3, "indentation"),
    ("repos:\n  - platform: gitlab\n    url: https://g.example.com\n    project: g/p\n   - platform: gitlab\n", 5,
     "indentation"),
    ("repos:\n  - platform: gitlab\n    url: https://g.example.com\n    project: g/p\n  -\n", 5, "not understood"),
    ("repos:\n", 1, "at least one repo"),
    ("repos: gitlab\n", 1, "list"),
    ("min_group_size:\n  - platform: gitlab\n" + REPO, 1, "list"),
    ("﻿repos:\n", 1, "byte order mark"),
])
def test_yaml_outside_the_supported_subset_is_refused_naming_the_line(tmp_path, text, line, hint):
    with pytest.raises(ValueError) as err:
        load(tmp_path, text)
    message = str(err.value)
    assert f"line {line}:" in message and hint in message, message


def test_errors_say_which_file_was_being_read(tmp_path):
    with pytest.raises(ValueError, match="scm.yaml"):
        load(tmp_path, "repos: [gitlab]\n")
