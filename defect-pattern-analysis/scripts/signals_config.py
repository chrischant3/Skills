#!/usr/bin/env python3
"""Read signals.yaml: each project's status names and what they mean, for ticket signals.

Status names differ from board to board, so ticket_signals.py never assumes any. This
file lists them, per Jira project, in workflow order, each with one category:

  started  work begins here, and time here is active. Cycle time starts at the first
           move into a started status.
  active   work is happening. Time here counts as active.
  waiting  queued, blocked or waiting for someone. Once work has started, time here
           counts as waiting.
  done     finished. Lead and cycle time end at the last move into done.

A move to a status listed earlier for the same project is a backward move.

It uses the same strict part of YAML as scm.yaml (see scm_config.py), so tabs, anchors,
flow collections, multi-line strings, duplicate keys, unknown settings and values YAML
would misread are refused with the file name and line number. Settings:

  min_group_size             optional; checked by suppress.py when it is used.
  acceptance_criteria_field  optional; the field id holding acceptance criteria, such as
                             customfield_10010. Its text counts towards the clarity rubric,
                             and edits to it after work started count as clarity edits.
  acceptance_criteria_name   optional; the same field's name, as Data Center changelogs
                             record it (they carry no field id).
  statuses                   required; a list of items, each with project, status and category.
"""

import re
from pathlib import Path

import scm_config

LIST_KEY = "statuses"
TOP_LEVEL = {"min_group_size", "acceptance_criteria_field", "acceptance_criteria_name", LIST_KEY}
STATUS_FIELDS = ("project", "status", "category")
CATEGORIES = ("started", "active", "waiting", "done")
PROJECT_KEY = re.compile(r"[A-Z][A-Z0-9_]+")


class Workflow:
    """One project's statuses, in workflow order, each with its category.

    Status names are matched without regard to case, as Jira treats them.

    Args:
        statuses: (status name, category) pairs in workflow order.
    """

    def __init__(self, statuses):
        self.statuses = tuple(name for name, _ in statuses)
        self._category = {name.casefold(): category for name, category in statuses}
        self._position = {name.casefold(): n for n, name in enumerate(self.statuses)}
        self._name = {name.casefold(): name for name in self.statuses}

    def category(self, status: str | None) -> str | None:
        """The status's category, or None if the status isn't configured."""
        return self._category.get((status or "").casefold())

    def position(self, status: str | None) -> int | None:
        """The status's place in workflow order (0 first), or None if it isn't configured."""
        return self._position.get((status or "").casefold())

    def name(self, status: str | None) -> str | None:
        """The status's name as the config spells it, or None if it isn't configured."""
        return self._name.get((status or "").casefold())


def _check(config: dict, lines: dict) -> dict:
    for key, value in config.items():
        n = lines[key]
        if key not in TOP_LEVEL:
            raise ValueError(f"line {n}: unknown setting {key!r}; expected one of {sorted(TOP_LEVEL)}")
        if key != LIST_KEY and isinstance(value, list):
            raise ValueError(f"line {n}: {key} needs a value" if not value else f"line {n}: {key} can't be a list")
    if LIST_KEY not in config:
        raise ValueError(f"line 1: no {LIST_KEY}: list; add one item per status with project, status and category")
    items, n = config[LIST_KEY], lines[LIST_KEY]
    if not isinstance(items, list):
        raise ValueError(f"line {n}: {LIST_KEY} must be a list of items, each starting with '- project:'")
    if not items:
        raise ValueError(f"line {n}: {LIST_KEY} needs at least one status")
    size = config.get("min_group_size")
    if size is not None and not isinstance(size, int):
        raise ValueError(f"line {lines['min_group_size']}: min_group_size must be a whole number, got {size!r}")
    for key in ("acceptance_criteria_field", "acceptance_criteria_name"):
        if key in config:
            config[key] = str(config[key])

    projects: dict[str, list] = {}
    first_line: dict[str, int] = {}
    seen: dict[tuple, int] = {}
    for i, item in enumerate(items):
        start = lines[(LIST_KEY, i)]
        for key in item:
            if key not in STATUS_FIELDS:
                raise ValueError(f"line {lines[(LIST_KEY, i, key)]}: unknown setting {key!r} for a status; "
                                 f"expected one of {list(STATUS_FIELDS)}")
        missing = [f for f in STATUS_FIELDS if item.get(f) in (None, "")]
        if missing:
            raise ValueError(f"line {start}: status item {i + 1} is missing {', '.join(missing)}")
        project, status, category = (str(item[f]) for f in STATUS_FIELDS)
        if not PROJECT_KEY.fullmatch(project):
            raise ValueError(f"line {lines[(LIST_KEY, i, 'project')]}: {project!r} isn't a Jira project key "
                             "(capital letters and digits, such as ABC)")
        if category not in CATEGORIES:
            raise ValueError(f"line {lines[(LIST_KEY, i, 'category')]}: category {category!r} isn't one of "
                             "started, active, waiting or done")
        status_line = lines[(LIST_KEY, i, "status")]
        if (project, status.casefold()) in seen:
            raise ValueError(f"line {status_line}: status {status!r} is listed twice for {project} "
                             f"(first on line {seen[(project, status.casefold())]})")
        seen[(project, status.casefold())] = status_line
        first_line.setdefault(project, start)
        projects.setdefault(project, []).append((status, category))

    for project, statuses in projects.items():
        for needed in ("started", "done"):
            if not any(c == needed for _, c in statuses):
                raise ValueError(f"line {first_line[project]}: project {project} has no {needed} status; "
                                 f"give at least one status the category {needed}")
    return {project: Workflow(statuses) for project, statuses in projects.items()}


def load_config(path) -> dict:
    """Read and check signals.yaml.

    Returns:
        {"min_group_size": int or None, "acceptance_criteria_field": str or None,
         "acceptance_criteria_name": str or None, "workflows": {project key: Workflow}}
    Raises:
        ValueError: "<path>: line N: ..." naming the line at fault.
    """
    try:
        config, lines = scm_config.parse_with_lines(Path(path).read_text(encoding="utf-8"), list_key=LIST_KEY)
        workflows = _check(config, lines)
    except ValueError as err:
        raise ValueError(f"{path}: {err}") from None
    return {"min_group_size": config.get("min_group_size"),
            "acceptance_criteria_field": config.get("acceptance_criteria_field"),
            "acceptance_criteria_name": config.get("acceptance_criteria_name"),
            "workflows": workflows}
