"""Seeded synthetic Jira defects with designed status histories, for ticket signal tests.

Each defect walks one of a few paths through a synthetic board (a straight run, a
reopen, a backward move, never started, still open, no history at all). People are
scattered everywhere Jira can hold one: user fields, changelog authors, assignee
changes, comments and mentions, so leak checks have something to find. Some comments
are clarifying questions that name a person, so question detection is proved to work
on anonymised text.

Team sizes are chosen so that groups of 1 to 6 defects exist, for suppression checks.
"""

import json
import random
from datetime import datetime, timedelta, timezone

PROJECT = "ABC"
AC_FIELD = "customfield_10010"
TEAM_SIZES = {
    "Payments": 30,
    "Accounts": 20,
    "Search": 6,
    "Web": 5,
    "Mobile": 4,
    "Notifications": 3,
    "Billing": 2,
    "Checkout": 1,
}
SMALL_TEAMS = ["Mobile", "Notifications", "Billing", "Checkout"]
PATHS = {
    "straight": ["To Do", "In Progress", "In Review", "In Test", "Done"],
    "reopen": [
        "To Do",
        "In Progress",
        "In Review",
        "In Test",
        "Done",
        "In Progress",
        "In Test",
        "Done",
    ],
    "backward": [
        "To Do",
        "In Progress",
        "In Review",
        "In Progress",
        "In Review",
        "In Test",
        "Done",
        "Closed",
    ],
    "never_started": ["To Do", "Done"],
    "open": ["To Do", "In Progress", "In Review"],
    "no_history": [],
}
PATH_WEIGHTS = {
    "straight": 5,
    "reopen": 2,
    "backward": 2,
    "never_started": 1,
    "open": 1,
    "no_history": 1,
}
CONFIG = """# Synthetic board for ticket signal tests.
acceptance_criteria_field: customfield_10010
acceptance_criteria_name: Acceptance Criteria
statuses:
  - project: ABC
    status: To Do
    category: waiting
  - project: ABC
    status: In Progress
    category: started
  - project: ABC
    status: In Review
    category: waiting
  - project: ABC
    status: In Test
    category: active
  - project: ABC
    status: Done
    category: done
  - project: ABC
    status: Closed
    category: done
"""
QUESTIONS = [
    "{mention} can you clarify what should happen when the postcode is empty?",
    "Is the expected behaviour to keep the basket, {name}?",
    "{name}: which of the two totals is correct?",
]
REMARKS = [
    "{name} picked this up. See `src/checkout/total.py` for detail.",
    "Deployed to staging by {mention}. Looks fine.",
    "Logs attached: https://logs.example.com/search?id=42 and nothing else.",
    "Paired on this with {name} and {mention}.",
]


def _user(person: dict, cloud: bool) -> dict:
    if cloud:
        return {
            "accountId": person["account_id"],
            "emailAddress": person["email"],
            "displayName": person["display_name"],
            "active": True,
        }
    return {
        "name": person["dc_username"],
        "key": person["dc_key"],
        "emailAddress": person["email"],
        "displayName": person["display_name"],
        "active": True,
    }


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%S.000+0000")


def _description(rng: random.Random, person: dict) -> str:
    parts = [f"Reported by {person['display_name']} <{person['email']}>."]
    if rng.random() < 0.6:
        parts.append("Steps to reproduce:\n1. Open the basket\n2. Remove the last item")
    if rng.random() < 0.5:
        parts.append("Expected: the total is zero. Actual: the old total stays.")
    if rng.random() < 0.5:
        parts.append("Environment: staging, Chrome 120.")
    if rng.random() < 0.3:
        parts.append(
            "Acceptance criteria: given an empty basket when it loads then the total is zero."
        )
    return "\n".join(parts)


def make_issue(rng: random.Random, number: int, team: str, people: list[dict]) -> dict:
    """Return one synthetic defect in the REST shape, with a designed status history."""
    cloud = number % 2 == 0
    pick = lambda: _user(rng.choice(people), cloud)  # noqa: E731
    created = datetime(2026, 1 + number % 6, 1 + number % 27, 9, 0, tzinfo=timezone.utc)
    path = rng.choices(list(PATH_WEIGHTS), weights=list(PATH_WEIGHTS.values()))[0]
    statuses = PATHS[path]
    histories, moment = [], created
    for n, (frm, to) in enumerate(zip(statuses, statuses[1:])):
        moment += timedelta(hours=rng.randint(1, 48))
        histories.append(
            {
                "id": f"{number}-s{n}",
                "author": pick(),
                "created": _stamp(moment),
                "items": [
                    {
                        "field": "status",
                        "fieldtype": "jira",
                        "fieldId": "status",
                        "from": "1",
                        "fromString": frm,
                        "to": "2",
                        "toString": to,
                    }
                ],
            }
        )
        if to == "In Progress" and n == 0 and rng.random() < 0.4:
            edit_at = moment + timedelta(hours=1)
            field = rng.choice(
                [("description", "description"), ("Acceptance Criteria", AC_FIELD)]
            )
            histories.append(
                {
                    "id": f"{number}-e{n}",
                    "author": pick(),
                    "created": _stamp(edit_at),
                    "items": [
                        {
                            "field": field[0],
                            "fieldtype": "jira",
                            "fieldId": field[1],
                            "fromString": "old text",
                            "toString": "new text",
                        }
                    ],
                }
            )
    a, b = rng.sample(people, 2)
    histories.append(
        {
            "id": f"{number}-a",
            "author": pick(),
            "created": _stamp(created),
            "items": [
                {
                    "field": "assignee",
                    "fieldtype": "jira",
                    "fieldId": "assignee",
                    "from": a["dc_username"],
                    "fromString": a["display_name"],
                    "to": b["dc_username"],
                    "toString": b["display_name"],
                }
            ],
        }
    )
    rng.shuffle(histories)
    comments = []
    for n in range(rng.randint(0, 5)):
        person = rng.choice(people)
        template = rng.choice(QUESTIONS if rng.random() < 0.3 else REMARKS)
        comments.append(
            {
                "id": f"{number}-c{n}",
                "author": pick(),
                "created": _stamp(created),
                "body": template.format(
                    name=person["display_name"].split()[0],
                    mention=f"[~{person['dc_username']}]"
                    if not cloud
                    else f"[~accountid:{person['account_id']}]",
                ),
            }
        )
    changelog_total = len(histories) + (3 if number % 11 == 5 else 0)
    comment_total = len(comments) + (2 if number % 13 == 7 else 0)
    fields = {
        "summary": f"Wrong total in {team}",
        "issuetype": {"id": "1", "name": "Bug"},
        "status": {"name": statuses[-1] if statuses else "To Do"},
        "components": [{"id": "100", "name": team}],
        "project": {"id": "1", "key": PROJECT, "name": "Alpha Billing"},
        "created": _stamp(created),
        "assignee": pick(),
        "reporter": pick(),
        "creator": pick(),
        "description": _description(rng, rng.choice(people)),
        "issuelinks": [
            {
                "type": {"name": "Relates"},
                "outwardIssue": {"key": f"{PROJECT}-{900 + k}"},
            }
            for k in range(rng.randint(0, 3))
        ],
        "comment": {
            "comments": comments,
            "total": comment_total,
            "maxResults": len(comments),
            "startAt": 0,
        },
    }
    if rng.random() < 0.4:
        fields[AC_FIELD] = (
            f"Given a basket when {rng.choice(people)['display_name']} pays then the total is right."
        )
    return {
        "id": str(number),
        "key": f"{PROJECT}-{number}",
        "fields": fields,
        "changelog": {
            "startAt": 0,
            "total": changelog_total,
            "maxResults": len(histories),
            "histories": histories,
        },
    }


def make_dataset(people: list[dict], seed: int = 7) -> list[dict]:
    """Return every synthetic defect, team by team, from a fixed seed."""
    rng = random.Random(seed)
    issues, number = [], 1
    for team, size in TEAM_SIZES.items():
        for _ in range(size):
            issues.append(make_issue(rng, number, team, people))
            number += 1
    return issues


def make_links(issues: list[dict], seed: int = 7) -> dict:
    """Synthetic work/scm_links.json for about three quarters of the defects, as link_scm.py writes it."""
    rng = random.Random(seed)
    defects = {}
    for issue in issues:
        if rng.random() < 0.25:
            continue
        repos = ["group/checkout-service"] + (
            ["Accounts/accounts-api"] if rng.random() < 0.3 else []
        )
        files = [
            {"repo": rng.choice(repos), "path": f"src/module{n}/file{n}.py"}
            for n in range(rng.randint(1, 12))
        ]
        changes = [
            {
                "repo": r,
                "kind": "merge_request",
                "id": str(rng.randint(1, 500)),
                "merged_at": "2026-06-01T00:00:00Z",
            }
            for r in repos
            for _ in range(rng.randint(1, 2))
        ]
        defects[issue["key"]] = {
            "repos": repos,
            "changes": changes,
            "commits": [
                f"{rng.getrandbits(40):010x}" for _ in range(rng.randint(1, 6))
            ],
            "files": files,
        }
    repos = {
        "group/checkout-service": {
            "platform": "gitlab",
            "team": None,
            "changes_scanned": 60,
            "changes_linked": 30,
            "defects_linked": 30,
        }
    }
    return {
        "since": "2026-01-01",
        "defects_total": len(issues),
        "defects_linked": len(defects),
        "repos": repos,
        "skipped": [],
        "defects": defects,
    }


def write_raw(raw_dir, people: list[dict], seed: int = 7) -> list[dict]:
    """Write the dataset to raw_dir as one MCP-style search page plus a manifest. Returns the issues."""
    issues = make_dataset(people, seed)
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "mcp-page-1.json").write_text(
        json.dumps({"issues": issues, "total": len(issues)}), encoding="utf-8"
    )
    (raw_dir / "_manifest.json").write_text(
        json.dumps({"source": "mcp", "jql": "project = ABC", "matched": len(issues)}),
        encoding="utf-8",
    )
    return issues
