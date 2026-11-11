"""Behaviour tests for scripts/signals_config.py: status names and categories per project (F6).

signals.yaml uses the same strict part of YAML as scm.yaml, so every mistake is refused
with the file name and the line at fault, never guessed at.
"""

import pytest

import signals_config
from conftest import ROOT

ITEM = "  - project: ABC\n    status: {status}\n    category: {category}\n"
BOARD = "statuses:\n" + "".join(ITEM.format(status=s, category=c) for s, c in [
    ("To Do", "waiting"), ("In Progress", "started"), ("In Review", "waiting"), ("Done", "done")])


def load(tmp_path, text):
    path = tmp_path / "signals.yaml"
    path.write_text(text, encoding="utf-8")
    return signals_config.load_config(path)


def refused(tmp_path, text) -> str:
    with pytest.raises(ValueError) as err:
        load(tmp_path, text)
    message = str(err.value)
    assert message.startswith(str(tmp_path / "signals.yaml") + ": line ")
    return message


def test_the_example_config_shipped_with_the_skill_reads_as_expected():
    config = signals_config.load_config(ROOT / "signals.yaml")
    assert config["min_group_size"] == 5
    workflow = config["workflows"]["ABC"]
    assert workflow.category("In Progress") == "started" and workflow.category("Done") == "done"
    assert workflow.category("Ready for Test") == "waiting"


def test_statuses_keep_their_order_and_categories_per_project(tmp_path):
    text = BOARD + ITEM.format(status="Doing", category="started").replace("ABC", "XYZ") \
        + ITEM.format(status="Shipped", category="done").replace("ABC", "XYZ")
    config = load(tmp_path, "min_group_size: 7\nacceptance_criteria_field: customfield_10010\n" + text)
    assert config["min_group_size"] == 7 and config["acceptance_criteria_field"] == "customfield_10010"
    assert config["acceptance_criteria_name"] is None
    abc, xyz = config["workflows"]["ABC"], config["workflows"]["XYZ"]
    assert abc.statuses == ("To Do", "In Progress", "In Review", "Done")
    assert abc.position("in review") == 2 and abc.position("Doing") is None
    assert abc.category("IN PROGRESS") == "started" and abc.category("Doing") is None
    assert xyz.statuses == ("Doing", "Shipped")


def test_a_workflow_can_be_built_in_code_for_tests_and_other_scripts():
    workflow = signals_config.Workflow([("Open", "waiting"), ("Fixing", "started"), ("Fixed", "done")])
    assert workflow.category("fixing") == "started" and workflow.position("Fixed") == 2


@pytest.mark.parametrize("text,line,words", [
    ("colour: blue\n" + BOARD, 1, ["unknown setting 'colour'"]),
    (BOARD.replace("    category: done", "    category: done\n    colour: blue"), 14, ["unknown setting 'colour'", "status"]),
    (BOARD.replace("category: started", "category: busy"), 7, ["busy", "started, active, waiting or done"]),
    (BOARD.replace("status: In Review", "status: In Progress"), 9, ["In Progress", "line 6"]),
    (BOARD.replace("status: In Review", "status: in progress"), 9, ["in progress", "line 6"]),
    (BOARD.replace("    status: Done\n", ""), 11, ["missing status"]),
    (BOARD.replace("category: started", "category: active"), 2, ["ABC", "started"]),
    (BOARD.replace("category: done", "category: waiting"), 2, ["ABC", "done"]),
    (BOARD.replace("project: ABC", "project: abc", 1), 2, ["project key"]),
    ("min_group_size: five\n" + BOARD, 1, ["whole number"]),
    ("statuses:\n", 1, ["at least one status"]),
    ("min_group_size: 5\n", 1, ["no statuses"]),
    (BOARD.replace("status: To Do", "status: [To Do]"), 3, ["flow collections"]),
    (BOARD + "statuses:\n", 14, ["duplicate setting 'statuses'"]),
    ("acceptance_criteria_field:\n" + BOARD, 1, ["needs a value"]),
])
def test_mistakes_are_refused_naming_the_line(tmp_path, text, line, words):
    message = refused(tmp_path, text)
    assert f": line {line}:" in message, message
    for word in words:
        assert word in message, (word, message)


def test_values_yaml_would_misread_must_be_quoted(tmp_path):
    message = refused(tmp_path, BOARD.replace("status: To Do", "status: Yes"))
    assert "line 3:" in message and "quote" in message
    config = load(tmp_path, BOARD.replace("status: To Do", "status: 'Yes'"))
    assert config["workflows"]["ABC"].statuses[0] == "Yes"
