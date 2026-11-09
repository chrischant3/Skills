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
                      "team": "Checkout"}
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
