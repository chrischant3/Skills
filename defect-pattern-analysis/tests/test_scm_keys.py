"""Table-driven tests for scripts/scm_keys.py: finding Jira keys in source control text (F4).

Covers the standard key format, custom team conventions declared per repo, normalisation
and near-misses: suffixed keys, URLs, version strings and encodings such as UTF-8.
"""

import pytest

import scm_keys

PROJECTS = {"ABC", "MEM"}


@pytest.mark.parametrize(
    "text,expected",
    [
        ("ABC-101 fix address line 2", {"ABC-101"}),
        ("fix/abc-101-address", {"ABC-101"}),
        ("Closes ABC-101, ABC-102.", {"ABC-101", "ABC-102"}),
        ("(ABC-7) and [MEM-8]", {"ABC-7", "MEM-8"}),
        ("feature_ABC-9_retry", {"ABC-9"}),
        ("ABC-101 again ABC-101", {"ABC-101"}),
        ("ABC-0042 padded", {"ABC-42"}),
        ("See https://jira.example.com/browse/ABC-12 for detail", {"ABC-12"}),
        ("Merge branch 'fix/ABC-5' into 'main'", {"ABC-5"}),
    ],
)
def test_standard_keys_are_found_and_normalised(text, expected):
    assert scm_keys.KeyMatcher(projects=PROJECTS).find(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "ABC-12a is a build tag",
        "XABC-12 belongs to another project",
        "OTHER-9 is not one of ours",
        "files are saved as UTF-8",
        "bump to release v1-2",
        "ABC_101 uses an underscore",
        "abc 101 uses a space",
        "logo at https://cdn.example.com/ABC-12/logo.png",
        "see https://gitlab.example.com/group/abc-1/-/issues/3",
        "",
    ],
)
def test_near_misses_are_not_keys_with_the_standard_pattern(text):
    assert scm_keys.KeyMatcher(projects=PROJECTS).find(text) == set()


@pytest.mark.parametrize(
    "text,expected",
    [
        ("MEM_123 login fix", {"MEM-123"}),
        ("mem 123 login fix", {"MEM-123"}),
        ("MEM-123 login fix", {"MEM-123"}),
        ("MEM123 login fix", {"MEM-123"}),
        ("feature/mem_45-login", {"MEM-45"}),
        ("MEM-12a is a build tag", set()),
        ("MEMO-12 is another word", set()),
        ("XMEM-1 is another project", set()),
    ],
)
def test_a_custom_team_convention_is_normalised(text, expected):
    assert (
        scm_keys.KeyMatcher(r"MEM[-_ ]?\d+", projects=PROJECTS).find(text) == expected
    )


def test_a_custom_pattern_that_wraps_the_key_is_still_normalised():
    matcher = scm_keys.KeyMatcher(r"\[ABC#\d+\]", projects=PROJECTS)
    assert matcher.find("Fixes [ABC#77] and [ABC#78]") == {"ABC-77", "ABC-78"}


def test_without_a_project_list_every_well_formed_key_is_returned():
    assert scm_keys.KeyMatcher().find("ABC-1 and OTHER-2") == {"ABC-1", "OTHER-2"}


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("MEM_123", "MEM-123"),
        ("mem 123", "MEM-123"),
        ("MEM-123", "MEM-123"),
        ("ab2-5", "AB2-5"),
        ("[ABC#77]", "ABC-77"),
        ("no digits", None),
    ],
)
def test_normalise_key(raw, expected):
    assert scm_keys.normalise_key(raw) == expected


@pytest.mark.parametrize("bad", ["(", "[A-Z", ""])
def test_an_unusable_pattern_is_refused_with_a_clear_error(bad):
    with pytest.raises(ValueError, match="key_pattern"):
        scm_keys.KeyMatcher(bad)
