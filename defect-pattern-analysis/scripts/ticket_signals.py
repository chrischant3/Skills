#!/usr/bin/env python3
"""Ticket signals: what ticket history says about clarity, complexity and flow (F6).

Usage: ticket_signals.py --config signals.yaml --issues clean/ --out out/
                         [--links work/scm_links.json] [--classified work/classified.json]
                         [--min-group-size 5] [--period month|quarter]

Three separate groups of signals, never combined into one score:
- Clarity: a rubric of the description (steps to reproduce, expected against actual,
  environment, acceptance criteria), description or acceptance criteria edits after work
  started, clarifying-question comments, and reopens.
- Complexity: linked issues and comments; with --links (from step 5), merge or pull
  requests, commits, files changed and repos touched. Without links those are reported
  as not available, never as zero, and a defect with no link is left out of them.
  Lines changed aren't available: diff text is dropped during anonymisation.
- Flow, a property of the system rather than the ticket: lead time, cycle time, active
  and waiting time, flow efficiency, status changes, backward moves and time in each
  status. Status names and categories come from signals.yaml (see signals_config.py).

Then clarity is compared with rework (a reopen or a backward move) within complexity
bands, terciles of files changed, because a complex change is both harder to describe
and more likely to need rework. These are correlations, not causes.

Reads only anonymised data from clean/ (raw data is refused), so clarifying questions
are only ever looked for in text that has already lost its people. Signals are worked
out per defect in memory and never written per defect: every output figure is for a
group (all defects, team, period or defect type) and goes through suppress.py. A group
or population smaller than min_group_size (default 5, never lower) is hidden, along with
enough others that it can't be worked out, and a hidden group is never named. Medians
are used rather than means, because a mean and a count together let a hidden group's
values be worked out from the totals.

A defect whose changelog or comments are incomplete (clean/_ingest.json lists them) is
left out of the signals that need them, rather than counted as zero.

Writes out/signals.json, out/signals.md and one CSV per section:
signals_clarity.csv, signals_complexity.csv, signals_flow.csv and
signals_rework_by_complexity.csv.
"""

import argparse
import csv
import json
import math
import re
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aggregate
import anonymise
import clean_data
import signals_config
import suppress

UTC = timezone.utc
YES, NO, NA = "yes", "no", "n/a"
SECTIONS = ("clarity", "complexity", "flow")
NOT_AVAILABLE = "not available: step 5 did not run"
BAND_NOT_AVAILABLE = (
    "not available: complexity bands need source control links from step 5 "
    "(terciles of files changed)"
)
BANDS = ("low", "middle", "high")
CLARITY_LEVELS = ("lower", "higher")
HIGHER_CLARITY = 3  # rubric score (of 4) at or above which clarity counts as higher

SECTION_TEXT = {
    "clarity": (
        "How clearly the defect was described and understood. The rubric score counts how many of four "
        "parts the description has: steps to reproduce, expected against actual, environment and acceptance "
        "criteria."
    ),
    "complexity": (
        "How much the defect touched. Source control figures count only defects linked in step 5; a "
        "defect with no link is left out, not counted as zero. Lines changed aren't available, because "
        "diff text is dropped during anonymisation."
    ),
    "flow": (
        "Flow describes the system the work moves through (queues, hand-offs and waiting), not the ticket and "
        "not the people working on it. Times are in hours and cover defects that reached a done status. Time "
        "spent done before a reopen, or in a status missing from the config, is neither active nor waiting."
    ),
}
# (section, signal, per-defect key, decimal places) for medians; the population is defects with a value.
NUMERIC = [
    ("clarity", "rubric_score", "rubric_score", 1),
    ("complexity", "linked_issues", "linked_issues", 1),
    ("complexity", "comments", "comments", 1),
    ("complexity", "changes", "changes", 1),
    ("complexity", "commits", "commits", 1),
    ("complexity", "files_changed", "files_changed", 1),
    ("complexity", "repos_touched", "repos_touched", 1),
    ("flow", "lead_time_hours", "lead_hours", 1),
    ("flow", "cycle_time_hours", "cycle_hours", 1),
    ("flow", "active_hours", "active_hours", 1),
    ("flow", "waiting_hours", "waiting_hours", 1),
    ("flow", "flow_efficiency", "flow_efficiency", 2),
    ("flow", "status_changes", "status_changes", 1),
]
SCM_SIGNALS = {"changes", "commits", "files_changed", "repos_touched"}
# (section, signal, per-defect key): yes when the value is true or above zero, n/a when it is unknown.
BINARY = [
    ("clarity", "has_repro_steps", "has_repro_steps"),
    ("clarity", "has_expected_vs_actual", "has_expected_vs_actual"),
    ("clarity", "has_environment", "has_environment"),
    ("clarity", "has_acceptance_criteria", "has_acceptance_criteria"),
    ("clarity", "edited_after_start", "edits_after_start"),
    ("clarity", "clarifying_question", "question_comments"),
    ("clarity", "reopened", "reopens"),
    ("flow", "backward_move", "backward_moves"),
]
SIGNAL_TEXT = {
    "rubric_score": "median rubric score, 0 to 4",
    "has_repro_steps": "description gives steps to reproduce",
    "has_expected_vs_actual": "description gives expected and actual results",
    "has_environment": "description names the environment",
    "has_acceptance_criteria": "acceptance criteria given",
    "edited_after_start": "description or acceptance criteria edited after work started",
    "clarifying_question": "at least one clarifying-question comment",
    "reopened": "reopened at least once",
    "linked_issues": "median linked issues",
    "comments": "median comments",
    "changes": "median merge or pull requests",
    "commits": "median commits",
    "files_changed": "median files changed",
    "repos_touched": "median repos touched",
    "lead_time_hours": "median hours from created to done",
    "cycle_time_hours": "median hours from work started to done",
    "active_hours": "median hours active once started",
    "waiting_hours": "median hours waiting once started",
    "flow_efficiency": "median share of active time in active plus waiting time",
    "status_changes": "median status changes",
    "backward_move": "moved backward on the board at least once",
}
STATUS_SIGNAL = "hours_in_status: "

# --- reading timestamps and changelogs ----------------------------------------------------------

_TIME = re.compile(
    r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}:?\d{2})?"
)


def parse_time(value) -> datetime | None:
    """Parse a Jira timestamp in any shape Jira writes (+0000, +00:00, Z, with or without a fraction).

    A timestamp with no zone is taken as UTC. Returns None for anything else.
    """
    match = _TIME.fullmatch(value.strip()) if isinstance(value, str) else None
    if not match:
        return None
    base, fraction, zone = match.groups()
    moment = datetime.strptime(base, "%Y-%m-%dT%H:%M:%S")
    if fraction:
        moment = moment.replace(microsecond=int((fraction[1:] + "000000")[:6]))
    if zone in (None, "Z"):
        return moment.replace(tzinfo=UTC)
    digits = zone[1:].replace(":", "")
    offset = timedelta(hours=int(digits[:2]), minutes=int(digits[2:]))
    return moment.replace(tzinfo=timezone(offset if zone[0] == "+" else -offset))


def _hours(delta: timedelta) -> float:
    return max(delta.total_seconds(), 0) / 3600


def _changelog_complete(issue: dict) -> bool:
    return bool((issue.get("_ingest") or {}).get("changelog_complete"))


def _comments_complete(issue: dict) -> bool:
    return bool((issue.get("_ingest") or {}).get("comments_complete"))


def _histories(issue: dict) -> list[tuple]:
    """(time, history) pairs in time order; histories with no readable time are left out."""
    found = [
        (parse_time(h.get("created")), n, h)
        for n, h in enumerate((issue.get("changelog") or {}).get("histories") or [])
        if isinstance(h, dict)
    ]
    return [
        (t, h)
        for t, _, h in sorted((x for x in found if x[0]), key=lambda x: (x[0], x[1]))
    ]


def status_transitions(issue: dict) -> list[tuple]:
    """Every status change as (time, from status, to status), in time order."""
    return [
        (t, item.get("fromString"), item.get("toString"))
        for t, h in _histories(issue)
        for item in h.get("items") or []
        if str(item.get("field", "")).casefold() == "status"
    ]


# --- flow -----------------------------------------------------------------------------------------


def _unknown_flow() -> dict:
    return {
        "completed": None,
        "started": None,
        "started_at": None,
        "lead_hours": None,
        "cycle_hours": None,
        "active_hours": None,
        "waiting_hours": None,
        "flow_efficiency": None,
        "status_changes": None,
        "backward_moves": None,
        "reopens": None,
        "hours_in_status": {},
        "unmapped_statuses": set(),
    }


def _done_at(transitions, workflow):
    """When the final run of done statuses began, so Done -> Closed doesn't move it."""
    i = len(transitions) - 1
    while i > 0 and workflow.category(transitions[i][1]) == "done":
        i -= 1
    return transitions[i][0]


def flow_signals(issue: dict, workflow) -> dict:
    """Work out one defect's flow signals from its status history.

    Time in a status runs from entering it to leaving it; the status a defect is in now
    is not timed. Lead time runs from created to done, cycle time from the first move
    into a started status (or creation, if it was created in one) to done. Done means the
    defect's last status is a done status; it is reached when the final run of done
    statuses began. Within the cycle, time in started and active statuses is active and
    time in waiting statuses is waiting. A reopen is a move from a done status to any
    other; a backward move is a move to a status listed earlier for the project.

    Args:
        issue: an anonymised issue.
        workflow: its project's signals_config.Workflow.
    Returns:
        A dict of signals, hours as floats. Values are None when unknown: all of them when
        the changelog is incomplete, times when the defect isn't done, and cycle, active,
        waiting and efficiency when work never started.
    """
    if not _changelog_complete(issue):
        return _unknown_flow()
    created = parse_time(issue["fields"].get("created"))
    transitions = status_transitions(issue)
    out = _unknown_flow()
    out["status_changes"] = len(transitions)
    out["backward_moves"] = sum(
        1
        for _, a, b in transitions
        if workflow.position(a) is not None
        and workflow.position(b) is not None
        and workflow.position(b) < workflow.position(a)
    )
    out["reopens"] = sum(
        1
        for _, a, b in transitions
        if workflow.category(a) == "done" and workflow.category(b) != "done"
    )
    out["unmapped_statuses"] = {
        s
        for _, a, b in transitions
        for s in (a, b)
        if s and workflow.category(s) is None
    }
    out["completed"] = (
        bool(transitions) and workflow.category(transitions[-1][2]) == "done"
    )

    segments = (
        [(transitions[0][1], created, transitions[0][0])]
        if transitions and created
        else []
    )
    segments += [(b, t, nxt[0]) for (t, _, b), nxt in zip(transitions, transitions[1:])]
    if created and transitions and workflow.category(transitions[0][1]) == "started":
        started_at = created
    else:
        started_at = next(
            (t for t, _, b in transitions if workflow.category(b) == "started"), None
        )
    out["started"], out["started_at"] = started_at is not None, started_at
    if not out["completed"]:
        return out

    done_at = _done_at(transitions, workflow)
    out["lead_hours"] = _hours(done_at - created) if created else None
    hours_in = {}
    for status, start, end in segments:
        name = workflow.name(status)
        if name and start and end <= done_at:
            hours_in[name] = hours_in.get(name, 0) + _hours(end - start)
    out["hours_in_status"] = hours_in
    if started_at is None or started_at > done_at:
        return out
    active = waiting = 0.0
    for status, start, end in segments:
        if start is None:
            continue
        span = _hours(min(end, done_at) - max(start, started_at))
        category = workflow.category(status)
        if category in ("started", "active"):
            active += span
        elif category == "waiting":
            waiting += span
    out.update(
        cycle_hours=_hours(done_at - started_at),
        active_hours=active,
        waiting_hours=waiting,
        flow_efficiency=active / (active + waiting) if active + waiting else None,
    )
    return out


# --- clarity --------------------------------------------------------------------------------------

STEPS = re.compile(
    r"\b(steps to (reproduce|recreate)|repro(duction)? steps|to reproduce)\b", re.I
)
NUMBERED = re.compile(r"(?m)^[ \t]*1[.)][ \t]+\S.*\n[ \t]*2[.)][ \t]+\S")
WIKI_NUMBERED = re.compile(r"(?m)^[ \t]*#[ \t]+\S.*\n[ \t]*#[ \t]+\S")
EXPECTED = re.compile(r"\bexpected\b", re.I)
ACTUAL = re.compile(r"\bactual\b", re.I)
ENVIRONMENT = re.compile(
    r"\b(environment|env|browser|device|operating system|os version|app version|version \d"
    r"|v\d+(\.\d+)+|prod|production|staging|uat|sit|pre-?prod|chrome|firefox|safari|ios"
    r"|android|windows|macos)\b",
    re.I,
)
ACCEPTANCE = re.compile(
    r"\bacceptance criteria\b|\bgiven\b.+?\bwhen\b.+?\bthen\b", re.I | re.S
)
URL = re.compile(r"\b(?:https?://|www\.)\S+", re.I)
CLARIFY = re.compile(
    r"\b(clarify|clarification|unclear|not clear|ambiguous|please confirm|can you confirm"
    r"|could you confirm)\b",
    re.I,
)
QUESTION_CUE = re.compile(
    r"\b(should|expected|expect|supposed|meant|mean|intended|which|correct|requirements?"
    r"|criteria|behaviou?r|confirm)\b",
    re.I,
)


def rubric(text: str) -> dict:
    """Which of the four parts of a clear defect description the text has.

    Returns:
        {"repro_steps", "expected_vs_actual", "environment", "acceptance_criteria"}: bools.
    """
    text = text or ""
    return {
        "repro_steps": bool(
            STEPS.search(text) or NUMBERED.search(text) or WIKI_NUMBERED.search(text)
        ),
        "expected_vs_actual": bool(EXPECTED.search(text) and ACTUAL.search(text)),
        "environment": bool(ENVIRONMENT.search(text)),
        "acceptance_criteria": bool(ACCEPTANCE.search(text)),
    }


def _has_ordered_list(value) -> bool:
    """True if Atlassian Document Format holds a numbered list (lost when flattened to text)."""
    if isinstance(value, dict):
        return value.get("type") == "orderedList" or _has_ordered_list(
            value.get("content")
        )
    return isinstance(value, list) and any(_has_ordered_list(v) for v in value)


def is_clarifying_question(text: str) -> bool:
    """True if anonymised comment text asks to clarify what is wanted.

    Code and links are ignored, so a ? in code or a query string never counts. A comment
    counts when it says clarify, unclear, please confirm and the like, or asks a question
    about what should happen, what was expected or meant, which option is correct, or the
    requirements. Other questions ("did the build pass?") don't count.
    """
    prose = URL.sub(" ", anonymise.CODE_REGION.sub(" ", text or ""))
    if CLARIFY.search(prose):
        return True
    return any(QUESTION_CUE.search(q) for q in re.findall(r"[^.?!\n]*\?", prose))


def _clarity_fields(settings: dict) -> tuple[set, set]:
    names, ids = {"description"}, {"description"}
    if settings.get("acceptance_criteria_name"):
        names.add(settings["acceptance_criteria_name"].casefold())
    if settings.get("acceptance_criteria_field"):
        ids.add(settings["acceptance_criteria_field"].casefold())
        names.add(settings["acceptance_criteria_field"].casefold())
    return names, ids


def clarity_signals(
    issue: dict, workflow, settings: dict, flow: dict | None = None
) -> dict:
    """Work out one defect's clarity signals.

    Args:
        issue: an anonymised issue.
        workflow: its project's signals_config.Workflow.
        settings: the config, for acceptance_criteria_field and acceptance_criteria_name.
        flow: flow_signals() for the issue, if already worked out.
    Returns:
        {"rubric": {...}, "rubric_score", "edits_after_start", "question_comments", "reopens"}.
        Edits are None when the changelog is incomplete or work never started; question
        comments are None when the comments are incomplete.
    """
    flow = flow or flow_signals(issue, workflow)
    fields = issue["fields"]
    description = fields.get("description")
    ac_field = settings.get("acceptance_criteria_field")
    ac_text = clean_data.text_of(fields.get(ac_field)).strip() if ac_field else ""
    found = rubric(clean_data.text_of(description) + "\n" + ac_text)
    found["repro_steps"] = found["repro_steps"] or _has_ordered_list(description)
    found["acceptance_criteria"] = found["acceptance_criteria"] or bool(ac_text)

    edits = None
    if _changelog_complete(issue) and flow["started_at"] is not None:
        names, ids = _clarity_fields(settings)
        edits = sum(
            1
            for t, h in _histories(issue)
            if t > flow["started_at"]
            for item in h.get("items") or []
            if str(item.get("field") or "").casefold() in names
            or str(item.get("fieldId") or "").casefold() in ids
        )
    questions = None
    if _comments_complete(issue):
        comments = (fields.get("comment") or {}).get("comments") or []
        questions = sum(
            1
            for c in comments
            if is_clarifying_question(clean_data.text_of(c.get("body")))
        )
    return {
        "rubric": found,
        "rubric_score": sum(found.values()),
        "edits_after_start": edits,
        "question_comments": questions,
        "reopens": flow["reopens"],
    }


# --- complexity -----------------------------------------------------------------------------------


def complexity_signals(issue: dict, link: dict | None) -> dict:
    """Work out one defect's complexity signals.

    Args:
        issue: an anonymised issue.
        link: its entry in work/scm_links.json, or None when it has none (or step 5 didn't run).
    Returns:
        {"linked_issues", "comments", "changes", "commits", "files_changed", "repos_touched"}.
        Comments are None when incomplete; the source control counts are None without a link.
    """
    fields = issue["fields"]
    links = fields.get("issuelinks")
    out = {
        "linked_issues": len(links) if isinstance(links, list) else 0,
        "comments": len((fields.get("comment") or {}).get("comments") or [])
        if _comments_complete(issue)
        else None,
        "changes": None,
        "commits": None,
        "files_changed": None,
        "repos_touched": None,
    }
    if link:
        out.update(
            changes=len(link.get("changes") or []),
            commits=len(link.get("commits") or []),
            files_changed=len(
                {(f.get("repo"), f.get("path")) for f in link.get("files") or []}
            ),
            repos_touched=len(link.get("repos") or []),
        )
    return out


def tercile_cuts(values) -> tuple | None:
    """The upper bounds of the low and middle thirds of values, or None if there are none.

    A value up to the first cut is low, up to the second is middle, and above it is high.
    Ties stay together, so a band can be empty when many values are equal.
    """
    ordered = sorted(values)
    if not ordered:
        return None
    n = len(ordered)
    return ordered[math.ceil(n / 3) - 1], ordered[math.ceil(2 * n / 3) - 1]


def _band(value, cuts) -> str:
    if value is None or cuts is None:
        return NA
    return "low" if value <= cuts[0] else "middle" if value <= cuts[1] else "high"


def _band_ranges(cuts) -> dict:
    low, high = cuts
    return {
        "low": f"up to {low} files",
        "middle": f"{low + 1} to {high} files" if high > low else "empty",
        "high": f"more than {high} files",
    }


# --- per-defect records and suppression -----------------------------------------------------------


def _flag(value) -> str:
    if value is None:
        return NA
    return YES if value is True or (not isinstance(value, bool) and value > 0) else NO


def _numeric_dim(signal: str) -> str:
    return f"has {signal}"


def _binary_dim(signal: str) -> str:
    return signal


def defect_signals(issue: dict, workflow, settings: dict, link: dict | None) -> dict:
    """Every signal for one defect, flat. Held in memory only; never written per defect."""
    flow = flow_signals(issue, workflow)
    clarity = clarity_signals(issue, workflow, settings, flow)
    out = {
        **{k: v for k, v in flow.items() if k != "started_at"},
        **complexity_signals(issue, link),
        "rubric_score": clarity["rubric_score"],
        "edits_after_start": clarity["edits_after_start"],
        "question_comments": clarity["question_comments"],
    }
    out.update({f"has_{k}": v for k, v in clarity["rubric"].items()})
    return out


def _statuses(config: dict) -> list[str]:
    names = []
    for workflow in config["workflows"].values():
        names += [s for s in workflow.statuses if s not in names]
    return names


def build_records(
    issues, config, links, types, period
) -> tuple[list, list, set, tuple | None]:
    """Per defect: a record of dimensions (for suppression) and its signal values.

    Returns:
        (records, values, unmapped status names, tercile cuts of files changed or None).
    """
    statuses = _statuses(config)
    linked = (links or {}).get("defects") or {}
    values, unmapped = [], set()
    for issue in issues:
        workflow = config["workflows"][issue["key"].split("-")[0]]
        v = defect_signals(issue, workflow, config, linked.get(issue["key"]))
        unmapped |= v["unmapped_statuses"]
        values.append(v)
    cuts = (
        tercile_cuts(
            [v["files_changed"] for v in values if v["files_changed"] is not None]
        )
        if links
        else None
    )
    records = []
    for issue, v in zip(issues, values):
        created = issue["fields"].get("created")
        record = {
            "team": aggregate.team_of(issue),
            "period": aggregate.period_of(created, period)
            if isinstance(created, str)
            else "unknown",
        }
        if types is not None:
            record["type"] = types[issue["key"]]
        for _, signal, key, _ in NUMERIC:
            record[_numeric_dim(signal)] = YES if v[key] is not None else NO
        for _, signal, key in BINARY:
            record[_binary_dim(signal)] = _flag(v[key])
        for status in statuses:
            record[_numeric_dim(STATUS_SIGNAL + status)] = (
                YES if status in v["hours_in_status"] else NO
            )
        record["done"] = _flag(v["completed"])
        record["unmapped status"] = (
            NA if v["completed"] is None else YES if v["unmapped_statuses"] else NO
        )
        rework = (
            None
            if v["reopens"] is None
            else (v["reopens"] or 0) + (v["backward_moves"] or 0)
        )
        record["band"] = _band(v["files_changed"], cuts)
        record["clarity"] = "higher" if v["rubric_score"] >= HIGHER_CLARITY else "lower"
        record["rework"] = _flag(rework)
        records.append(record)
    return records, values, unmapped, cuts


def _groupings(types) -> list[tuple]:
    out = [("all", ()), ("team", ("team",)), ("period", ("period",))]
    return out + [("type", ("type",))] if types is not None else out


def _combos(groupings, signal_dims) -> list[tuple]:
    combos = []
    for _, dims in groupings:
        combos.append(dims)
        combos += [dims + (d,) for d in signal_dims]
    combos += [
        ("done",),
        ("unmapped status",),
        ("band",),
        ("band", "clarity"),
        ("band", "clarity", "rework"),
    ]
    return combos


def _median(numbers, digits) -> float:
    return round(float(statistics.median(numbers)), digits)


def _members(records, values, key: frozenset):
    return [v for r, v in zip(records, values) if all(r.get(d) == x for d, x in key)]


def _numeric_row(
    pub, records, values, base, grouping, group, signal, getter, digits
) -> dict:
    n = pub.value(base | {(_numeric_dim(signal), YES)})
    median = suppress.SUPPRESSED if n == suppress.SUPPRESSED else None
    if isinstance(n, int) and n > 0:
        median = _median(
            [
                getter(v)
                for v in _members(records, values, base | {(_numeric_dim(signal), YES)})
            ],
            digits,
        )
    return {
        "grouping": grouping,
        "group": group,
        "signal": signal,
        "defects": n,
        "median": median,
    }


def _binary_counts(pub, key: frozenset, dim: str) -> tuple:
    yes, no = pub.value(key | {(dim, YES)}), pub.value(key | {(dim, NO)})
    if suppress.SUPPRESSED in (yes, no):
        return suppress.SUPPRESSED, suppress.SUPPRESSED, suppress.SUPPRESSED
    total = yes + no
    return total, yes, round(yes / total, 2) if total else None


def _section_rows(pub, records, values, groupings, statuses, links) -> dict:
    sections = {
        s: {"description": SECTION_TEXT[s], "rows": [], "suppressed_groups": 0}
        for s in SECTIONS
    }
    for grouping, dims in groupings:
        table = pub.table(dims)
        for s in SECTIONS:
            sections[s]["suppressed_groups"] += table["suppressed_rows"]
        for row in table["rows"]:
            base = frozenset(row["labels"].items())
            group = "all defects" if grouping == "all" else row["labels"][dims[0]]
            for section, signal, key, digits in NUMERIC:
                if signal in SCM_SIGNALS and links is None:
                    continue
                sections[section]["rows"].append(
                    _numeric_row(
                        pub,
                        records,
                        values,
                        base,
                        grouping,
                        group,
                        signal,
                        lambda v, k=key: v[k],
                        digits,
                    )
                )
            for section, signal, _ in BINARY:
                defects, count, share = _binary_counts(pub, base, _binary_dim(signal))
                sections[section]["rows"].append(
                    {
                        "grouping": grouping,
                        "group": group,
                        "signal": signal,
                        "defects": defects,
                        "with_signal": count,
                        "share": share,
                    }
                )
            for status in statuses:
                row = _numeric_row(
                    pub,
                    records,
                    values,
                    base,
                    grouping,
                    group,
                    STATUS_SIGNAL + status,
                    lambda v, s=status: v["hours_in_status"][s],
                    1,
                )
                if (
                    row["defects"] != 0
                ):  # a status no done defect in the group entered says nothing
                    sections["flow"]["rows"].append(row)
    return sections


def _rework_rows(pub, cuts) -> dict:
    if cuts is None:
        return {
            "band_by": "files_changed",
            "bands": {},
            "note": BAND_NOT_AVAILABLE,
            "rows": [],
            "suppressed_groups": 0,
        }
    table = pub.table(("band", "clarity"))
    ranges = _band_ranges(cuts)
    rows = []
    for row in table["rows"]:
        band, clarity = row["labels"]["band"], row["labels"]["clarity"]
        if band == NA:
            continue
        defects, count, share = _binary_counts(
            pub, frozenset(row["labels"].items()), "rework"
        )
        rows.append(
            {
                "band": band,
                "files_changed": ranges[band],
                "clarity": clarity,
                "defects": defects,
                "with_rework": count,
                "share": share,
            }
        )
    hidden = sum(
        1
        for key in pub.suppressed
        if {d for d, _ in key} == {"band", "clarity"} and dict(key)["band"] != NA
    )
    order = {b: n for n, b in enumerate(BANDS)}
    rows.sort(key=lambda r: (order[r["band"]], CLARITY_LEVELS.index(r["clarity"])))
    return {
        "band_by": "files_changed",
        "bands": ranges,
        "note": (
            "Rework means the defect was reopened or moved backward on the board. Clarity is higher with a "
            f"rubric score of {HIGHER_CLARITY} or more out of 4. Compare clarity within a band, not across "
            "bands. These are correlations, not causes."
        ),
        "rows": rows,
        "suppressed_groups": hidden,
    }


def build_signals(
    issues, config, links=None, types=None, min_group_size=None, period="month"
) -> tuple[dict, set]:
    """Work out every signal and suppress every group, without writing anything.

    Args:
        issues: anonymised issues, as clean_data.load_clean_issues() returns them.
        config: as signals_config.load_config() returns it.
        links: work/scm_links.json as link_scm.link() wrote it, or None if step 5 didn't run.
        types: {issue key: defect type} from validated classifications, or None.
        min_group_size: threshold (default 5; below 5 is refused).
        period: "month" or "quarter".
    Returns:
        (doc, unmapped): the document written to signals.json, and status names seen in the
        changelogs but missing from the config (for the command line to report, never written).
    Raises:
        ValueError: for a threshold below 5, an unknown period, or a project missing from the config.
    """
    size = suppress.validate_min_group_size(min_group_size)
    if period not in ("month", "quarter"):
        raise ValueError("period must be month or quarter")
    missing = sorted(
        {i["key"].split("-")[0] for i in issues} - set(config["workflows"])
    )
    if missing:
        raise ValueError(
            f"no statuses in the config for project {', '.join(missing)}; add that board's statuses "
            "to signals.yaml"
        )
    statuses = _statuses(config)
    records, values, unmapped, cuts = build_records(
        issues, config, links, types, period
    )
    signal_dims = (
        [_numeric_dim(s) for _, s, _, _ in NUMERIC]
        + [_binary_dim(s) for _, s, _ in BINARY]
        + [_numeric_dim(STATUS_SIGNAL + s) for s in statuses]
    )
    groupings = _groupings(types)
    pub = suppress.publish(records, _combos(groupings, signal_dims), size)

    pub.add_cell("defects_analysed", frozenset())
    pub.add_cell(
        "changelog_incomplete_defects",
        frozenset({(_numeric_dim("status_changes"), NO)}),
    )
    pub.add_cell(
        "comments_incomplete_defects", frozenset({(_numeric_dim("comments"), NO)})
    )
    pub.add_cell("defects_done", frozenset({("done", YES)}))
    pub.add_cell(
        "defects_with_unmapped_statuses", frozenset({("unmapped status", YES)})
    )
    summary = dict(pub.summary)
    if links is None:
        summary["source_control"] = NOT_AVAILABLE
    else:
        summary["source_control"] = "available"
        summary["defects_linked_to_source_control"] = pub.value(
            frozenset({(_numeric_dim("files_changed"), YES)})
        )

    doc = {
        "settings": {
            "min_group_size": size,
            "period": period,
            "groupings": [g for g, _ in groupings],
            "acceptance_criteria_field": config.get("acceptance_criteria_field"),
            "acceptance_criteria_name": config.get("acceptance_criteria_name"),
            "statuses": {
                p: [{"status": s, "category": w.category(s)} for s in w.statuses]
                for p, w in sorted(config["workflows"].items())
            },
        },
        "suppressed_marker": suppress.SUPPRESSED,
        "summary": summary,
        "sections": _section_rows(pub, records, values, groupings, statuses, links),
        "rework_by_complexity": _rework_rows(pub, cuts),
    }
    return doc, unmapped


# --- writing --------------------------------------------------------------------------------------

SECTION_COLUMNS = [
    "grouping",
    "group",
    "signal",
    "defects",
    "with_signal",
    "share",
    "median",
]
REWORK_COLUMNS = ["band", "files_changed", "clarity", "defects", "with_rework", "share"]


def _cell(value) -> str:
    return "" if value is None else str(value)


def _write_csv(path: Path, columns, rows, note: str | None) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([_cell(row.get(c)) for c in columns])
        if note:
            writer.writerow([note] + [""] * (len(columns) - 1))


def _note(n: int, k: int) -> str | None:
    return (
        suppress.SUPPRESSED_NOTE.format(
            n=n, groups="group" if n == 1 else "groups", k=k
        )
        if n
        else None
    )


def _md_table(header, rows) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    return lines + ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]


def _markdown(doc: dict) -> str:
    k = doc["settings"]["min_group_size"]
    md = [
        "# Ticket signals",
        "",
        "Three separate groups of signals: clarity, complexity and flow. They are never combined into one score. "
        "Every figure is for a group of defects (all defects, a team, a period or a defect type), never a person. "
        f"Groups with fewer than {k} defects are suppressed, and a suppressed group is never named. Figures are "
        "medians, or the number and share of defects showing a signal. At most they show correlations, not causes.",
        "",
        "## Summary",
        "",
    ]
    md += [f"- {key}: {value}" for key, value in doc["summary"].items()]
    titles = {"clarity": "Clarity", "complexity": "Complexity", "flow": "Flow"}
    for name in SECTIONS:
        section = doc["sections"][name]
        md += ["", f"## {titles[name]}", "", section["description"], ""]
        signals = [
            r for r in section["rows"] if not r["signal"].startswith(STATUS_SIGNAL)
        ]
        used = sorted(
            {r["signal"] for r in signals}, key=lambda s: list(SIGNAL_TEXT).index(s)
        )
        md += [f"- {s}: {SIGNAL_TEXT[s]}" for s in used] + [""]
        md += _md_table(
            [
                "grouping",
                "group",
                "signal",
                "defects",
                "with signal",
                "share",
                "median",
            ],
            [
                [
                    r["grouping"],
                    r["group"],
                    r["signal"],
                    r["defects"],
                    r.get("with_signal"),
                    r.get("share"),
                    r.get("median"),
                ]
                for r in signals
            ],
        )
        if name == "flow":
            in_status = [
                r for r in section["rows"] if r["signal"].startswith(STATUS_SIGNAL)
            ]
            md += [
                "",
                "### Time in each status",
                "",
                "Median hours spent in each status by done defects that entered it, before they were done.",
                "",
            ]
            md += _md_table(
                ["grouping", "group", "status", "defects", "median hours"],
                [
                    [
                        r["grouping"],
                        r["group"],
                        r["signal"][len(STATUS_SIGNAL) :],
                        r["defects"],
                        r["median"],
                    ]
                    for r in in_status
                ],
            )
        if name == "complexity" and doc["summary"]["source_control"] == NOT_AVAILABLE:
            md += [
                "",
                "Merge or pull requests, commits, files changed and repos touched: "
                + NOT_AVAILABLE
                + ".",
            ]
        note = _note(section["suppressed_groups"], k)
        if note:
            md += ["", note]
    band = doc["rework_by_complexity"]
    md += ["", "## Clarity and rework within complexity bands", ""]
    if not band["bands"]:
        md += [
            band["note"][0].upper()
            + band["note"][1:]
            + ". Without them, don't relate clarity to rework: a complex "
            "change is both harder to describe and more likely to need rework, so the comparison would mislead. "
            "These would be correlations, not causes."
        ]
    else:
        md += [
            "Bands are terciles of files changed among defects linked to source control: "
            + ", ".join(f"{b} ({band['bands'][b]})" for b in BANDS)
            + ". "
            + band["note"],
            "",
        ]
        md += _md_table(
            ["band", "files changed", "clarity", "defects", "with rework", "share"],
            [[r[c] for c in REWORK_COLUMNS] for r in band["rows"]],
        )
        if not band["rows"]:
            md += [
                "",
                "Every band and clarity group was too small to show. A longer time window may help.",
            ]
        note = _note(band["suppressed_groups"], k)
        if note:
            md += ["", note]
    md += [
        "",
        "## Caveats",
        "",
        "- Signals are read from ticket history and text, so they show how the work was recorded as well as how "
        "it went.",
        "- Defects with an incomplete changelog or incomplete comments are left out of the signals that need them, "
        "never counted as zero.",
        "- Time in a status missing from signals.yaml is neither active nor waiting; add missing statuses and run "
        "again if defects_with_unmapped_statuses is high.",
        "- Clarifying questions are found by wording, in anonymised comments, and will miss some and catch others.",
        "",
    ]
    return "\n".join(md)


def write_outputs(doc: dict, out_dir) -> None:
    """Write signals.json, signals.md and one CSV per section from an already suppressed document."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    k = doc["settings"]["min_group_size"]
    (out_dir / "signals.json").write_text(
        json.dumps(doc, indent=2) + "\n", encoding="utf-8"
    )
    for name in SECTIONS:
        section = doc["sections"][name]
        _write_csv(
            out_dir / f"signals_{name}.csv",
            SECTION_COLUMNS,
            section["rows"],
            _note(section["suppressed_groups"], k),
        )
    band = doc["rework_by_complexity"]
    _write_csv(
        out_dir / "signals_rework_by_complexity.csv",
        REWORK_COLUMNS,
        band["rows"],
        _note(band["suppressed_groups"], k) if band["bands"] else band["note"],
    )
    (out_dir / "signals.md").write_text(_markdown(doc), encoding="utf-8")


def types_from_classified(issues, classified: dict) -> dict:
    """Map each issue key to its validated defect type (unclassified when it has none).

    Raises:
        ValueError: if the classified keys don't match the issues exactly.
    """
    by_key = {r["key"]: r for r in classified.get("records") or []}
    keys = {i["key"] for i in issues}
    if set(by_key) != keys:
        raise ValueError(
            "classified.json doesn't match clean/: rerun validate_classifications.py "
            f"(missing {len(keys - set(by_key))}, extra {len(set(by_key) - keys)})"
        )
    return {
        k: r["defect_type"]
        if r.get("status") != aggregate.UNCLASSIFIED
        else aggregate.UNCLASSIFIED
        for k, r in by_key.items()
    }


def write_signals(
    clean_dir,
    config,
    out_dir,
    links=None,
    classified=None,
    min_group_size=None,
    period="month",
) -> dict:
    """Read clean/, work out every signal, suppress small groups and write all outputs.

    Args:
        clean_dir: the run's clean/ folder; raw data is refused.
        config: as signals_config.load_config() returns it.
        out_dir: the run's out/ folder.
        links: work/scm_links.json's contents, or None.
        classified: work/classified.json's contents, or None.
        min_group_size: threshold; default the config's, else 5. Below 5 is refused.
        period: "month" or "quarter".
    Returns:
        The document written to signals.json.
    Raises:
        ValueError: before anything is written, for raw data, a low threshold or a config gap.
    """
    issues = clean_data.load_clean_issues(clean_dir)
    types = (
        types_from_classified(issues, classified) if classified is not None else None
    )
    size = (
        min_group_size if min_group_size is not None else config.get("min_group_size")
    )
    doc, _ = build_signals(issues, config, links, types, size, period)
    write_outputs(doc, out_dir)
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Clarity, complexity and flow signals from ticket history, "
        "with small groups suppressed."
    )
    ap.add_argument("--config", default="signals.yaml")
    ap.add_argument("--issues", default="clean")
    ap.add_argument("--out", default="out")
    ap.add_argument("--links", help="work/scm_links.json from step 5, if it ran")
    ap.add_argument(
        "--classified", help="work/classified.json, to group by defect type too"
    )
    ap.add_argument(
        "--min-group-size",
        type=int,
        default=None,
        help="default 5, or the config's; below 5 is refused",
    )
    ap.add_argument("--period", choices=["month", "quarter"], default="month")
    a = ap.parse_args(argv)
    try:
        config = signals_config.load_config(a.config)
        issues = clean_data.load_clean_issues(a.issues)
        links = (
            json.loads(Path(a.links).read_text(encoding="utf-8")) if a.links else None
        )
        classified = (
            json.loads(Path(a.classified).read_text(encoding="utf-8"))
            if a.classified
            else None
        )
        types = (
            types_from_classified(issues, classified)
            if classified is not None
            else None
        )
        doc, unmapped = build_signals(
            issues,
            config,
            links,
            types,
            a.min_group_size or config.get("min_group_size"),
            a.period,
        )
    except (ValueError, OSError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    write_outputs(doc, a.out)
    print(f"Wrote signals.json, signals.md and CSVs -> {a.out}")
    if unmapped:
        print(
            "Statuses missing from the config (their time is neither active nor waiting): "
            + ", ".join(sorted(unmapped))
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
