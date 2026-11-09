---
name: defect-pattern-analysis
description: Analyse Jira defects over time to find recurring defect types, where they occur and get fixed in the codebase (GitLab, Azure DevOps), and what ticket history says about clarity, complexity and flow. Team and pattern level only, never individuals. Use when asked what keeps going wrong, where defects cluster, or how ticket quality relates to rework.
---

# Defect Pattern Analysis

## Purpose
Answer three questions, in priority order:
1. What types of defect keep occurring? (always)
2. Where in the codebase are defects fixed, and where were they likely introduced? (if source control links exist)
3. What does ticket history tell us about clarity, complexity and flow? (if changelog data is available)

## Non-negotiable: no individual blame
- Run `scripts/anonymise.py` on ALL Jira and source control data before any analysis or classification. Claude must never see assignee, reporter, commenter or commit author identities.
- Report only at team, component, repo or directory level.
- Suppress any group with fewer than `min_group_size` tickets (default 5). Say it was suppressed, not what it contained.
- If anyone asks for a per-person breakdown, decline and explain that the skill is designed for system-level learning. Most variation comes from the system, not the people in it.
- Authorship is often shared (pairing, mobbing, one person committing for several), so per-author data would be wrong as well as harmful.

## Inputs to gather before starting
Ask for anything missing. Do not guess.
- Jira project key(s) and time window (default: last 12 months)
- What counts as a defect: issue type(s) and/or labels (default: issuetype = Bug)
- Source control: GitLab and/or Azure DevOps, with the repos in scope
- Each team's issue key convention, if non-standard (a regex per repo). Default: `[A-Z][A-Z0-9]+-\d+`
- Minimum group size for reporting (default 5)

## Workflow

### 1. Pull defects
Use the Atlassian MCP JQL search, e.g.
`project in (KEY) AND issuetype = Bug AND created >= -365d ORDER BY created ASC`
Paginate until complete. Record the total so coverage can be reported.
If the MCP does not return the changelog, use `scripts/jira_changelog.py` (Jira REST, `expand=changelog`).

### 2. Anonymise
`python scripts/anonymise.py raw/ clean/`. Everything after this step reads from `clean/` only.

### 3. Classify defect types (priority output)
Classify each defect with a fixed taxonomy so results are comparable between runs. Use the ODC-inspired scheme in `reference/taxonomy.md`:
- Defect type: function/logic, assignment/initialisation, interface/integration, checking/validation, timing/concurrency, data/config, build/package/deploy, documentation, UX/content
- Trigger: how it was found (test, review, production, monitoring, customer report)
- Escape stage: where it should have been caught
Record a confidence for each classification. Anything under 0.6 goes in `unclassified`, not a forced bucket.
Then find recurring themes within each type: cluster on summary, description and resolution comments, and name each cluster in plain language (e.g. "null handling on optional address fields").

### 4. Trace to code (stretch)
`python scripts/link_scm.py --config scm.yaml` matches issue keys in commit messages, branch names and MR/PR titles using each repo's regex. Output: files and directories touched by fixes.
Optional: `python scripts/szz.py` runs a simplified SZZ (git blame on lines changed by fix commits) to estimate where defects were introduced. Label this output as an estimate, because SZZ is noisy around refactors and formatting changes.
Report hotspots by directory or module, never by author.

### 5. Ticket signals (stretch)
`python scripts/ticket_signals.py clean/` computes three SEPARATE signal groups. Never combine them into one score.
- Clarity: description edits after work started, acceptance criteria changes after start, comments that are questions or clarification requests, reopen count, rubric score (repro steps, expected vs actual, environment, acceptance criteria)
- Complexity: number of linked issues, comment volume on technical discussion, number of commits, number of MRs/PRs, files and lines changed, number of repos touched
- Flow (system, not ticket): time in each status, start-to-done cycle time, waiting statuses (review, blocked, ready for test), status ping-pong (backward transitions)
Then relate clarity to rework (reopens, backward transitions, extra MRs) and state plainly that complexity confounds this. These are correlations, not causes.

## Output
A markdown report with:
1. Coverage: defects found, classified, unclassified, linked to code, suppressed groups
2. Top recurring defect types and themes, with counts and trend over time
3. Codebase hotspots for fixes and estimated introduction points (if available)
4. Clarity, complexity and flow findings, reported separately
5. Caveats: data quality, link coverage per repo, confounders
6. Questions for the team, framed as system improvements ("what in our process lets validation defects escape to production?"), never as judgements

## Data quality is a finding
If link coverage is low, or many tickets cannot be classified, report that prominently. It tells you something useful about the system and limits how far the rest can be trusted.
