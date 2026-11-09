#!/usr/bin/env python3
"""Usage: ticket_signals.py --issues clean/ --links clean/links.json --out clean/signals.csv"""
import argparse, csv, json, re
from datetime import datetime
from pathlib import Path

# Adjust per board. Anything not listed counts as 'other'.
STATUS_ORDER = ["To Do", "Ready", "In Progress", "In Review", "Ready for Test", "In Test", "Done"]
ACTIVE = {"In Progress", "In Test"}
WAITING = {"Ready", "In Review", "Ready for Test", "Blocked"}
STARTED = {"In Progress"}
DONE = {"Done", "Closed", "Resolved"}
CLARITY_FIELDS = {"description", "summary", "Acceptance Criteria", "acceptance criteria"}
QUESTION = re.compile(r"\?|\b(clarify|unclear|what do you mean|confirm|which one|expected behaviou?r)\b", re.I)
RUBRIC = {
    "repro_steps": re.compile(r"steps to reproduce|repro|\b1\.\s", re.I),
    "expected_actual": re.compile(r"expected.*actual|actual.*expected", re.I | re.S),
    "environment": re.compile(r"environment|browser|device|version|\b(prod|staging|uat|sit)\b", re.I),
    "acceptance": re.compile(r"acceptance criteria|given .* when .* then", re.I | re.S),
}

def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None

def text_of(v):
    """Flatten Atlassian Document Format or plain text."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return " ".join(text_of(x) for x in ([v.get("text", "")] + v.get("content", [])))
    if isinstance(v, list):
        return " ".join(text_of(x) for x in v)
    return str(v)

def signals(issue, links):
    f = issue["fields"]
    created = ts(f["created"])
    hist = sorted(issue.get("changelog", {}).get("histories", []), key=lambda h: h["created"])
    transitions, edits_after_start, started_at, done_at = [], 0, None, None
    for h in hist:
        t = ts(h["created"])
        for item in h["items"]:
            if item["field"] == "status":
                transitions.append((t, item["fromString"], item["toString"]))
                if item["toString"] in STARTED and not started_at:
                    started_at = t
                if item["toString"] in DONE:
                    done_at = t
            elif item["field"] in CLARITY_FIELDS and started_at:
                edits_after_start += 1

    # Flow: time in status
    in_status, prev_t, prev_s = {}, created, "To Do"
    for t, frm, to in transitions:
        in_status[frm] = in_status.get(frm, 0) + (t - prev_t).total_seconds() / 3600
        prev_t, prev_s = t, to
    backwards = sum(1 for _, frm, to in transitions
                    if frm in STATUS_ORDER and to in STATUS_ORDER and STATUS_ORDER.index(to) < STATUS_ORDER.index(frm))
    reopens = sum(1 for _, frm, to in transitions if frm in DONE and to not in DONE)
    active_h = sum(v for k, v in in_status.items() if k in ACTIVE)
    waiting_h = sum(v for k, v in in_status.items() if k in WAITING)

    # Clarity
    desc = text_of(f.get("description"))
    comments = f.get("comment", {}).get("comments", [])
    q_comments = sum(1 for c in comments if QUESTION.search(text_of(c.get("body"))))
    rubric = {k: bool(p.search(desc)) for k, p in RUBRIC.items()}

    # Complexity
    lk = links.get(issue["key"], [])
    files = {fp for l in lk for fp in l["files"]}
    return {
        "key": issue["key"],
        "team": (f.get("components") or [{}])[0].get("name", "unassigned"),
        # clarity
        "clarity_rubric_score": sum(rubric.values()),
        **{f"clarity_has_{k}": v for k, v in rubric.items()},
        "clarity_edits_after_start": edits_after_start,
        "clarity_question_comments": q_comments,
        "clarity_reopens": reopens,
        # complexity
        "complexity_linked_issues": len(f.get("issuelinks", [])),
        "complexity_comments": len(comments),
        "complexity_mrs": len(lk),
        "complexity_commits": len({c for l in lk for c in l["commits"]}),
        "complexity_files": len(files),
        "complexity_repos": len({l["repo"] for l in lk}),
        # flow (system)
        "flow_cycle_hours": round((done_at - started_at).total_seconds() / 3600, 1) if started_at and done_at else None,
        "flow_lead_hours": round((done_at - created).total_seconds() / 3600, 1) if done_at else None,
        "flow_active_hours": round(active_h, 1),
        "flow_waiting_hours": round(waiting_h, 1),
        "flow_efficiency": round(active_h / (active_h + waiting_h), 2) if active_h + waiting_h else None,
        "flow_status_changes": len(transitions),
        "flow_backward_transitions": backwards,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--issues", default="clean")
    ap.add_argument("--links", default="clean/links.json")
    ap.add_argument("--out", default="clean/signals.csv")
    a = ap.parse_args()
    links = json.loads(Path(a.links).read_text())["links"] if Path(a.links).exists() else {}
    rows = [signals(json.loads(p.read_text()), links) for p in Path(a.issues).glob("*-*.json")]
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote signals for {len(rows)} tickets -> {a.out}")

if __name__ == "__main__":
    main()
