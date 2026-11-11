"""Seeded generator of synthetic Jira issues for property-style tests.

Each issue scatters the synthetic people across every place Jira can hold a person:
user fields, comments, changelog authors and items, mentions, @handles, emails and
commit-style trailers. It also plants non-person text that must survive: status and
component names, file paths and code such as @Override and @media.
"""

import random

CLOUD = "https://example.atlassian.net"
DC = "https://jira.example.com"
STATUSES = ["To Do", "In Progress", "In Review", "Ready for Test", "Done"]
COMPONENTS = ["Payments", "Accounts", "Search", "Notifications", "Checkout"]
ISSUE_TYPES = ["Bug", "Defect"]
CODE_SNIPPETS = [
    "@Override public String toString() { return id; }",
    "@media (max-width: 600px) { .nav { display: none; } }",
    "@Test void rejectsEmptyPostcode() {}",
    "@app.route('/checkout') def checkout(): pass",
    "@import url('theme.css');",
]
PATHS = [
    "src/main/java/com/example/checkout/AddressValidator.java",
    "assets/logo@2x.png",
    "web/styles/print.css",
    "services/accounts/session_filter.py",
]


def _mention_forms(person, flavour, scm_handles):
    first, last = person["display_name"].split()
    forms = [
        person["display_name"],
        first,
        f"{last}'s",
        person["email"],
        f"<{person['email']}>",
        f"@{first.lower()}",
        f"@{first.lower()}.{last.lower()}",
        f"@{first[0].lower()}{last.lower()}",
        f"Co-authored-by: {person['display_name']} <{person['email']}>",
        f"Signed-off-by: {person['display_name']} <{person['email']}>",
        f"Reviewed-by: {person['display_name']} <{person['email']}>",
    ]
    if scm_handles:
        forms.append(f"@{person['scm_username']}")
    if flavour == "cloud":
        forms.append(f"[~accountid:{person['account_id']}]")
    else:
        forms += [
            f"[~{person['dc_username']}]",
            f"@{person['dc_username']}",
            person["dc_username"],
        ]
    return forms


def _user(person, flavour):
    if flavour == "cloud":
        return {
            "self": f"{CLOUD}/rest/api/3/user?accountId={person['account_id']}",
            "accountId": person["account_id"],
            "emailAddress": person["email"],
            "displayName": person["display_name"],
            "active": True,
            "avatarUrls": {
                "48x48": f"https://avatar.example.com/{person['account_id']}.png"
            },
            "accountType": "atlassian",
        }
    return {
        "self": f"{DC}/rest/api/2/user?username={person['dc_username']}",
        "name": person["dc_username"],
        "key": person["dc_key"],
        "emailAddress": person["email"],
        "displayName": person["display_name"],
        "active": True,
    }


def _sentence(rng, people, flavour, scm_handles):
    person = rng.choice(people)
    form = rng.choice(_mention_forms(person, flavour, scm_handles))
    keep = rng.choice(CODE_SNIPPETS + PATHS + [f"moved to {s}" for s in STATUSES])
    return f"{form} looked at this. See {keep} for detail."


def _body(rng, people, flavour, scm_handles, sentences=3):
    text = "\n".join(
        _sentence(rng, people, flavour, scm_handles) for _ in range(sentences)
    )
    if flavour == "cloud" and rng.random() < 0.5:
        person = rng.choice(people)
        return {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "mention",
                            "attrs": {
                                "id": person["account_id"],
                                "text": "@" + person["display_name"],
                            },
                        },
                        {"type": "text", "text": " " + text},
                    ],
                }
            ],
        }
    return text


def make_issue(
    rng: random.Random,
    key: str,
    people,
    flavour: str,
    created: str,
    component: str | None = None,
    issue_type: str = "Bug",
    scm_handles: bool = False,
) -> dict:
    """Return one synthetic Jira issue in the REST shape for flavour ('cloud' or 'dc').

    scm_handles adds source control usernames (which Jira alone cannot know) to the text.
    """
    pick = lambda: _user(rng.choice(people), flavour)  # noqa: E731
    component = component or rng.choice(COMPONENTS)
    status = rng.choice(STATUSES)
    histories = []
    for n in range(rng.randint(1, 4)):
        frm, to = rng.sample(STATUSES, 2)
        histories.append(
            {
                "id": f"{key}-h{n}",
                "author": pick(),
                "created": created,
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
    a, b = rng.sample(people, 2)
    ident = (
        (lambda p: p["account_id"])
        if flavour == "cloud"
        else (lambda p: p["dc_username"])
    )
    histories.append(
        {
            "id": f"{key}-assign",
            "author": pick(),
            "created": created,
            "items": [
                {
                    "field": "assignee",
                    "fieldtype": "jira",
                    "fieldId": "assignee",
                    "from": ident(a),
                    "fromString": a["display_name"],
                    "to": ident(b),
                    "toString": b["display_name"],
                }
            ],
        }
    )
    comments = [
        {
            "id": f"{key}-c{n}",
            "author": pick(),
            "updateAuthor": pick(),
            "created": created,
            "body": _body(rng, people, flavour, scm_handles, 2),
        }
        for n in range(rng.randint(1, 4))
    ]
    return {
        "id": key.split("-")[1],
        "key": key,
        "self": f"{CLOUD if flavour == 'cloud' else DC}/rest/api/2/issue/{key}",
        "fields": {
            "summary": f"{rng.choice(['Error', 'Crash', 'Wrong total'])} in {component}",
            "issuetype": {"id": "1", "name": issue_type, "subtask": False},
            "status": {
                "id": "3",
                "name": status,
                "statusCategory": {
                    "id": 4,
                    "key": "indeterminate",
                    "name": "In Progress",
                },
            },
            "priority": {"id": "2", "name": "High"},
            "components": [{"id": "100", "name": component}],
            "project": {"id": "1", "key": key.split("-")[0], "name": "Alpha Billing"},
            "labels": ["regression"],
            "created": created,
            "resolutiondate": None,
            "assignee": pick(),
            "reporter": pick(),
            "creator": pick(),
            "customfield_10050": pick(),
            "customfield_10051": [pick(), pick()],
            "description": _body(rng, people, flavour, scm_handles, 4),
            "comment": {
                "comments": comments,
                "total": len(comments),
                "maxResults": len(comments),
                "startAt": 0,
            },
        },
        "changelog": {
            "startAt": 0,
            "total": len(histories),
            "maxResults": len(histories),
            "histories": histories,
        },
    }


def make_dataset(
    seed: int, people, count: int = 6, scm_handles: bool = False
) -> list[dict]:
    """Return count synthetic issues, alternating Cloud and Data Center shapes, from a fixed seed."""
    rng = random.Random(seed)
    return [
        make_issue(
            rng,
            f"ABC-{seed * 100 + n}",
            people,
            "cloud" if n % 2 == 0 else "dc",
            f"2026-0{1 + n % 9}-1{n % 9}T10:00:00.000+0000",
            scm_handles=scm_handles,
        )
        for n in range(count)
    ]


def gitlab_users(people) -> list[dict]:
    """GitLab user objects for people, as a source control export would hold them."""
    return [
        {
            "id": 500 + n,
            "username": p["scm_username"],
            "name": p["display_name"],
            "state": "active",
        }
        for n, p in enumerate(people)
    ]
