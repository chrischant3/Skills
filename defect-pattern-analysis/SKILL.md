---
name: defect-pattern-analysis
description: >-
  Analyse Jira defects over time to find the types of defect that keep recurring, with counts and
  trends per type and theme, at team and pattern level only, never for individuals. Pulls defects
  through the Atlassian MCP or the Jira REST API (Cloud or Data Center), removes every person
  identifier before analysis, classifies each defect against a fixed taxonomy, and suppresses any
  group too small to be safe. Use when asked what keeps going wrong, which kinds of defect recur,
  how they escape, or how defect patterns are trending. Can also link defects to GitLab merge
  requests and Azure DevOps pull requests, report link coverage per repo and show which
  directories fixes land in, and can report what ticket history says about
  clarity, complexity and flow, as three separate groups of signals. Declines any per-person
  breakdown. Estimates of where defects were introduced are planned but not ready yet.
---

# Defect pattern analysis

Help a team learn from its defects at system level. This version answers one question:
**what types of defect keep occurring, and how is that changing over time?** It needs Jira only.

If the team uses GitLab or Azure DevOps, it can also link each defect to the merge requests or pull requests that fixed it, report how well defects and changes are linked in each repo, and show which directories fixes land in most (step 5). That answers a second question, where in the code defects are fixed. With local clones of those repos, it can also estimate where defects were probably introduced (the end of step 5). Step 6 reads ticket history for signs of unclear work, genuine complexity and flow problems.

`<skill>` below means the folder containing this file. Call scripts by absolute path. Work in a run folder outside any git repository (for example a folder called `defect-runs/2026-11/` in the user's home folder), with `raw/`, `clean/`, `work/` and `out/` inside it.

## Before you start

- **Check data governance first.** Ask the user to confirm that their organisation allows sending Jira ticket data to an AI model (and source control data too, if they want step 5). Don't use the MCP or fetch any real data until they confirm. If they aren't sure, stop and suggest they check with whoever owns information governance.
- **Know what the model sees.** With the Atlassian MCP (the default), the model sees raw ticket data, names included, during the fetch step, before anonymisation. The REST fallback keeps names away from the model entirely, because the script writes raw data straight to disk and only anonymised data is read after that. If the organisation allows ticket data to go to an AI model but not names, use the REST fallback. The same is true of source control: with a GitLab or Azure DevOps MCP the model sees merge requests, pull requests and commits, names included, while `scripts/scm_fetch.py` keeps them away from the model.
- Needs Python 3.10 or later. The scripts use only the standard library, so there is nothing to install.
- Tests: `python3 -m pytest <skill>/tests` (needs `pytest`). They use synthetic fixtures only and never touch the network.

## No individual blame

This is the most important rule. The skill must never identify, rank or single out a person, however it is asked.

- The skill judges the work, not the people. It assumes everyone on the team worked on every ticket, so it never looks at who did what, and never discriminates against or singles out anyone.
- Every person identifier is removed by `scripts/anonymise.py` before any analysis script, classification input or output sees the data. With MCP fetching, the model sees raw data only during the fetch step (see [Before you start](#before-you-start)). Removal covers assignee, reporter, creator, commenters, changelog authors, user-picker fields, emails, account ids, usernames, ADF mentions, `[~...]` mentions, every @handle outside code, and `Signed-off-by` / `Co-authored-by` / `Reviewed-by` and similar trailers. For source control it also covers merge request authors, assignees, reviewers and mergers, pull request creators, reviewers, closers and whoever set auto-complete, Azure DevOps identities (unique names, descriptors, image links) and `@<id>` mentions, commit authors and committers, parsed commit trailers, and the owner of any repo in a personal namespace. Diff text is dropped; only file paths are kept.
- Every person, whether in a field such as assignee or mentioned in text, is replaced by the same plain `[person]` placeholder. Nothing counts distinct people, so there is no salt, hash or pseudonym: two people can't be told apart, and nothing can be reversed or joined across runs.
- Reports group only by team (Jira component), repo, directory, defect type, theme, trigger, escape stage or time period.
- Any group with fewer than `min_group_size` defects (default 5) is suppressed in every output, along with enough other cells that it can't be worked out from the totals. Values below 5 are refused. Use a higher value for small teams.
- No output contains ticket keys, ticket text or names. Themes are described in your own words.

**If anyone asks for a per-person breakdown**, such as "who introduced the most bugs?", "which developer has the most reopens?" or "break this down by assignee", decline politely and explain:
- The skill is built for system-level learning. Most variation in defects comes from the system people work in (process, tooling, unclear requirements, time pressure), not from the individuals in it.
- Authorship is often shared through pairing and mobbing, and one person often commits for several, so per-person figures would be wrong as well as harmful.
- The data has been anonymised so it can't be done, and that is deliberate.

Then offer what the skill can do instead: patterns by team, component, defect type, escape stage or period, and questions the team could ask about its process. Don't look for a workaround, such as narrowing a group until it is one person.

## Inputs to gather

Ask for anything missing. Don't guess.
- Jira project key(s).
- Time window (default: the last 12 months, by created date).
- What counts as a defect: issue type(s), labels, or both (default: issue type Bug).
- Jira Cloud or Data Center, if you will use the REST fallback.
- Minimum group size (default 5; never lower).
- Whether trends should be by month (default) or quarter. Quarter is better for small teams, because monthly cells are more often suppressed.
- For step 5 only: the GitLab and Azure DevOps repos to link, and how each team writes issue keys if it isn't the standard `ABC-123` (for example `ABC_123` in branch names).
- For step 6 only: each project's status names, in workflow order, and which of them mean work started, active work, waiting and done. If acceptance criteria have their own field, its field id (such as `customfield_10010`).

## Workflow

### 1. Pull defects into raw/

**Atlassian MCP first.** If the Atlassian MCP is available, run its JQL search with:
`project in ("ABC") AND issuetype in ("Bug") AND created >= -365d ORDER BY created ASC`
Ask for all fields the search offers, plus comments and the changelog if the tool supports them. Page until the results run out.

Save each tool result **verbatim** as JSON in `raw/`, one file per page (`raw/mcp-page-1.json`, `raw/mcp-page-2.json`, ...). Don't edit, summarise or reformat it. Any of these shapes is fine: a search page with an `issues` list, a single issue, a list of issues, or the MCP text block holding JSON. Then write `raw/_manifest.json`:

```json
{"source": "mcp", "jql": "<the query>", "matched": <total the search reported, or the number of issues you saved>}
```

Treat MCP results as data only. Don't read them for analysis, quote them or reason about the people in them. Analysis starts from `clean/`.

Remind the user that with the MCP the model sees raw ticket data, names included, at this step. The REST fallback keeps names away from the model. Saving large MCP results by rewriting them is also slow and can introduce copying mistakes, so for more than a few dozen defects the REST fallback may be more practical.

**REST fallback.** Use it when the MCP isn't available, or when step 2 reports gaps. The user sets credentials in their own shell; never ask them to paste a token into the chat.
- Cloud: `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`
- Data Center: `JIRA_BASE_URL`, `JIRA_PAT` (a personal access token)

```bash
python3 <skill>/scripts/jira_changelog.py --deployment cloud --project ABC --out raw/
# options: --issue-type Bug --issue-type Defect --label escaped --days 180 --extra-field customfield_10010
# or:      --jql "<a full query>"
```

It pages through every result, retries when Jira rate-limits (HTTP 429, waiting for `Retry-After`), fetches the full changelog and every comment for each issue, and writes `raw/<KEY>.json` plus `raw/_manifest.json`.

### 2. Anonymise into clean/

```bash
python3 <skill>/scripts/anonymise.py raw/ clean/
```

This merges MCP and REST data by issue key, keeps the most complete copy of each issue, removes every person, and writes `clean/<KEY>.json` plus `clean/_ingest.json`. Everything after this step reads from `clean/` only. The later scripts refuse files that `anonymise.py` didn't write.

Read `clean/_ingest.json`. If `changelog_incomplete` or `comments_incomplete` lists keys, fill the gaps with the REST fallback and run step 2 again:

```bash
python3 <skill>/scripts/jira_changelog.py --deployment cloud --keys ABC-12,ABC-40 --out raw/
```

If the gaps can't be filled, carry on and report them as a data quality caveat. Missing comments make classification less reliable.

Known limits of anonymisation: a plain name with no @ ("Sam said...") is removed only when it belongs to someone found somewhere in the data, so the name of someone who never appears as a user, such as a customer, can survive in `clean/`. An @handle inside code formatting is kept unless it matches a known person. Don't repeat any name or handle you notice. The outputs never contain ticket text, so it can't reach a report.

### 3. Classify each defect (the priority output)

```bash
python3 <skill>/scripts/make_batches.py clean/ work/batches/
```

Read each `work/batches/batch-NNN.json` and classify every ticket against `references/taxonomy.md`. Load that file before you start, and keep to it exactly so results compare between runs.

For each ticket, give:
- `defect_type`, `trigger` and `escape_stage`, spelt exactly as in the taxonomy. One defect type per ticket: the root cause, not the symptom.
- `confidence` from 0 to 1. Below 0.6, the ticket is unclassified. Don't force it into a type.
- `theme`: a short name for the recurring pattern, in your own words (for example "null handling on optional address fields"). It must not be copied from the ticket, and must not contain names, handles, emails or ticket keys. Classify all batches first, then reuse the same theme name for the same pattern across batches, so themes count properly.
- `reason`: one line, required when confidence is below 0.6 or `defect_type` is `unclassified` (usually missing information, which is itself a finding).

Write one JSON list per batch to `work/classifications/batch-NNN.json`:

```json
[{"key": "ABC-12", "defect_type": "checking_validation", "trigger": "customer_report",
  "escape_stage": "automated_test", "confidence": 0.8, "theme": "Null handling on optional address fields"},
 {"key": "ABC-13", "defect_type": "unclassified", "trigger": null, "escape_stage": null,
  "confidence": 0.2, "theme": null, "reason": "No expected or actual result given."}]
```

Then validate:

```bash
python3 <skill>/scripts/validate_classifications.py work/classifications/ --issues clean/ --out work/classified.json
```

If it lists problems, fix those records and run it again. It writes nothing until every defect is classified once with values from the taxonomy.

### 4. Count, with small groups suppressed

```bash
python3 <skill>/scripts/aggregate.py --classified work/classified.json --issues clean/ --out out/
# options: --min-group-size 8   --period quarter
```

This writes `out/aggregate.json`, one CSV per table and `out/tables.md`. The tables are: types, type_trend, themes, theme_trend, triggers, escape_stages, teams (by type) and periods. Team is the Jira component. A defect with several components counts once under "multiple components".

`suppressed` in a cell means the count is hidden. A note under each table says how many groups were left out. If most trend cells are suppressed, run again with `--period quarter`.

### 5. Optional: link defects to GitLab or Azure DevOps, and find fix hotspots

Skip this step if the user has no GitLab or Azure DevOps repos to link. It needs `clean/` from step 2. One run can mix both platforms.

Copy `<skill>/scm.yaml` into the run folder and edit it. Each GitLab repo needs `platform: gitlab`, `url` and `project` (the group and project path), and can set `namespace`. Each Azure DevOps repo needs `platform: azure`, `org`, `project` and `repo`. Any repo can set `team` and `key_pattern`, a regular expression for the team's way of writing issue keys. Without one, the standard Jira key format is used. Use single quotes around patterns. Keys are normalised, so `ABC_123`, `abc 123` and `ABC-123` all count as `ABC-123` when the pattern allows them.

An Azure DevOps repo is shown as `<project>/<repo>`, such as `Accounts/accounts-api`, in `work/` and `out/`; the org never appears there, so an org named after a person (as personal organisations often are) can't reach a report. Azure DevOps has no personal namespaces like GitLab's. Project and repo names are shown as written in `scm.yaml`, so if one is named after a person, say so to the user before running.

On GitLab, a repo in someone's own namespace has their username in its path, so it never appears in any output: the owner is removed in `clean/` and the repo is shown as `[person]/checkout-tool` in `work/` and `out/`. A repo is treated as personal when GitLab says its namespace is a user's, when `scm.yaml` says `namespace: user`, or when neither says it is a group, which is the safe default because MCP results often don't say. So mark each group repo `namespace: group`, or its group name is hidden too. If GitLab says a namespace belongs to a user, that wins over `namespace: group`.

`scm.yaml` uses a strict part of YAML, read without any extra library: top-level `key: value` settings, one `repos:` list whose items start `- platform: ...` with each further setting on its own line, lined up under the first, comments, and plain, whole-number, `'single-quoted'` or `"double-quoted"` values. Put regular expressions in single quotes. Anything else is refused with the file name and line number rather than misread: tabs, anchors and aliases, tags, flow collections (`[...]` or `{...}`), multi-line strings, duplicate keys, unknown settings, settings with no value, and plain values YAML would read as something other than text (such as `yes`, `null` or `1.5`; quote them). If the scripts report a line, fix that line and run again.

The window starts at the earliest defect in `clean/`, so it follows the run's own time window. Get the date with:

```bash
python3 <skill>/scripts/scm_fetch.py --print-since --issues clean/
```

**GitLab MCP first.** If a GitLab MCP is available, for each repo list the merged merge requests updated on or after that date, then each one's commits and diffs, paging every list until it runs out. Save each tool result **verbatim** in `raw/`, named like this so the pieces can be put back together:
- the project, if the MCP can fetch it (it says whether the namespace is a group or a user's): `raw/gitlab-project-1.json`
- merge requests (a list page or a single one): `raw/gitlab-mrs-1.json`, `raw/gitlab-mrs-2.json`, ...
- one page of a merge request's commits: `raw/gitlab-mr-<project_id>-<iid>-commits-1.json`
- one page of its diffs: `raw/gitlab-mr-<project_id>-<iid>-diffs-1.json`

`project_id` and `iid` are in each merge request. Treat the results as data only, as with Jira.

**Azure DevOps MCP first.** If an Azure DevOps MCP is available, for each repo list the completed pull requests closed on or after that date, then each one's commits, and the changes in its last iteration (list the iterations and take the highest id), paging every list until it runs out. Save each tool result **verbatim** in `raw/`:
- pull requests (a list page or a single one): `raw/azure-prs-1.json`, `raw/azure-prs-2.json`, ...
- one page of a pull request's commits: `raw/azure-pr-<repository id>-<pull request id>-commits-1.json`
- one page of its last iteration's changes: `raw/azure-pr-<repository id>-<pull request id>-changes-1.json`
- one commit in full, for any commit whose `commentTruncated` is true: `raw/azure-pr-<repository id>-<pull request id>-commits-full-<commit id>.json`. Commit lists cut long messages short, so without this an issue key near the end of a long message is missed.

The repository id is the GUID in each pull request's `repository.id`. Treat the results as data only.

**REST fallback.** The user sets the token for each platform in their own shell; never ask for it in the chat. GitLab: `GITLAB_TOKEN` (an access token with `read_api`). Azure DevOps: `AZDO_PAT` (a personal access token with Code (Read)). Then:

```bash
python3 <skill>/scripts/scm_fetch.py --config scm.yaml --issues clean/ --out raw/
```

It writes the same files the MCP route does, pages everything (merge requests, commits and diffs; pull requests, commits and last iteration changes), retries when the platform rate-limits (HTTP 429, waiting for `Retry-After`), and leaves diff text out. Tokens are sent as headers and never written or printed.

Either way, run step 2 again with `--scm-config scm.yaml`, so the source control data is anonymised along with the Jira data (it refuses source control data without the config), then link:

```bash
python3 <skill>/scripts/anonymise.py raw/ clean/ --scm-config scm.yaml
python3 <skill>/scripts/link_scm.py --config scm.yaml --issues clean/ --work work/scm_links.json --out out/
```

Keys are matched in merge request and pull request titles, descriptions, source branch names and commit messages, and only keys of defects in the run count. Only merged merge requests and completed pull requests count. `work/scm_links.json` lists, for each linked defect, its repos, changes, commits and files changed. It holds ticket keys, so it is working data, never something to quote. `out/scm_coverage.md` (with `.json` and `.csv`) gives each repo's changes scanned, changes linked and defects linked, with small groups suppressed. A defect linked from several repos counts once, under "multiple repos".

Then count where fixes land:

```bash
python3 <skill>/scripts/hotspots.py --links work/scm_links.json --config scm.yaml --out out/
# options: --depth 3   --min-group-size 8
```

`out/hotspots.md` (with `.json` and `.csv`) gives, for each repo and directory, the number of defects whose fixes touched a file in that directory. It counts defects, not files or commits, so one large fix counts once, the same as a one-line fix. A defect whose fix touched several directories counts once in each, so the counts don't add up to the number of defects. A directory is the folder path cut to `--depth` parts (default 2, such as `src/checkout`); files at the top of a repo count under `(root)`. Directories with fewer than `min_group_size` defects are suppressed, with enough others in the same repo that they can't be worked out, and are never named. The output holds repo names and paths only, never authors. A path inside a personal-namespace repo shows the owner as `[person]`, as the repo name does.

**Optionally, estimate where defects were introduced.** Skip this unless the user has local clones of the linked repos and wants it. For each fix commit linked in `work/scm_links.json`, `szz.py` blames, in the commit's parent, the lines the fix removed or changed. The commits that last changed those lines before the defect was reported are the candidate introducers. This is the SZZ method, and its result is an estimate.

The user clones each repo themselves, with full history: a shallow clone (`--depth`) stops blame at its cut-off. If the team squashes merge requests or pull requests, the fix commits may not be on the main branch. On GitLab, fetch them before running with `git fetch origin '+refs/merge-requests/*/head:refs/remotes/origin/mr/*'`. Elsewhere, `commits_not_in_clone` in the output shows how many were missing. Never run `git log` or `git blame` on the clones yourself, because their output names authors; leave reading them to the script.

Name each clone by the repo's name as `out/scm_coverage.md` shows it:

```bash
python3 <skill>/scripts/szz.py --links work/scm_links.json --issues clean/ --config scm.yaml \
  --clone group/checkout-service=clones/checkout-service \
  --clone Accounts/accounts-api=clones/accounts-api \
  --work work/szz.json --out out/
# options: --depth 3   --min-group-size 8
```

Whitespace-only and comment-only changes aren't blamed, commits listed in a repo's `.git-blame-ignore-revs` are looked past, and candidates committed after the defect was reported are dropped. `out/szz.md` (with `.json` and `.csv`) gives, for each repo and directory, the number of defects with a candidate introducer there, counted and suppressed the same way as the fix hotspots, and the median days from the newest candidate to the report (suppressed when fewer than `min_group_size` defects were traced). Its summary counts what couldn't be traced: `commits_not_in_clone` (often squashed merges), `merge_commits_skipped`, `commits_with_nothing_to_blame` (fixes that only add lines, which SZZ can't trace), `paths_not_in_linked_changes` (see below), `blame_failures`, `defects_without_report_date` and `repos_without_clone` (a count; the names are in `work/szz.json`). `candidates_after_report_dropped` counts lines last changed after the defect was reported, which can't have introduced it. A high count in any of these is a caveat for the report. `work/szz.json` holds ticket keys, so it is working data, never something to quote. No output holds an author, a commit id or a commit time, and the lags aren't kept against their defects, so nothing ties a defect to the person whose commit was blamed. A clone's paths are raw data, and a folder can be named after a person, so a path is used only if `link_scm.py` already listed it for that repo from the anonymised data, and is shown in that cleaned form. Other paths, such as the old path of a renamed file, are counted as `paths_not_in_linked_changes` and never shown. Treat the result as an estimate: refactors and moved code mislead it, and it is a prompt for a conversation about the code, never about the people who worked on it.

### 6. Optional: ticket signals (clarity, complexity and flow)

Skip this step if the user only wants defect types. It needs `clean/` from step 2 with complete changelogs and comments (fill the gaps `clean/_ingest.json` lists first, as step 2 says). It uses `work/scm_links.json` if step 5 ran.

Copy `<skill>/signals.yaml` into the run folder and edit it. List every status on each project's board, in workflow order, as one item each with `project`, `status` and `category`. A move to a status listed earlier is a backward move. The categories are:
- `started`: work begins here, and time here is active. Cycle time starts at the first move into a started status.
- `active`: work is happening. Time here is active.
- `waiting`: queued, blocked or waiting for someone. Once work has started, time here is waiting.
- `done`: finished. Lead and cycle time end at the defect's last move into done from a status that isn't done, so moving from one done status to another doesn't change them.

Each project needs at least one started and one done status. Status names come only from this file, never from a built-in list, because every board names them differently. If acceptance criteria have their own field, set `acceptance_criteria_field` to its id, and `acceptance_criteria_name` to its name for Data Center changelogs. With the REST fallback, fetch that field with `--extra-field customfield_10010` in step 1. `signals.yaml` uses the same strict part of YAML as `scm.yaml`, and any mistake, such as an unknown setting or category, a status listed twice or a project with no done status, is refused with the file name and line number.

```bash
python3 <skill>/scripts/ticket_signals.py --config signals.yaml --issues clean/ --out out/ --links work/scm_links.json
# options: --classified work/classified.json (also group by defect type)   --min-group-size 8   --period quarter
```

Leave out `--links` if step 5 didn't run. This writes `out/signals.md`, `out/signals.json` and one CSV per section. There are three separate groups of signals, never combined into one score:
- **Clarity**: a rubric score (steps to reproduce, expected against actual, environment, acceptance criteria), description or acceptance criteria edits after work started, comments asking clarifying questions, and reopens.
- **Complexity**: linked issues and comments; with links, merge or pull requests, commits, files changed and repos touched. Without links those are reported as not available, not as zero, and a defect with no link is left out of them rather than counted as zero. Lines changed aren't available, because diff text is dropped during anonymisation.
- **Flow**, which describes the system the work moves through, not the ticket or the people: lead time, cycle time, active and waiting time, flow efficiency, status changes, backward moves and time in each status.

Every figure is for all defects, a team, a period or a defect type, never a person, and goes through the same suppression as step 4: a group or count below `min_group_size` is suppressed and never named. Figures are medians or the number and share of defects showing a signal; nothing is written per defect. Clarifying questions are looked for only in anonymised comments. A defect with an incomplete changelog or incomplete comments is left out of the signals that need them, not counted as zero.

It also compares clarity with rework (a reopen or a backward move) within each complexity band, the terciles of files changed, because a complex change is both harder to describe and more likely to need rework. Without links there are no bands, so it doesn't make the comparison. These are correlations, not causes: say so whenever you report them.

The command line lists any status it found in the changelogs that `signals.yaml` doesn't have. Time in those statuses is neither active nor waiting, so add them and run again.

### 7. Write the report

The report is written in two parts: a script lays out every number and table, and you write the interpretation. Run:

```bash
python3 <skill>/scripts/report.py --out out/
```

It writes `out/report.md` from `out/` only (`aggregate.json` and `tables.md`, plus `scm_coverage.md`, `hotspots.md` and `szz.md` if step 5 wrote them, and `signals.md` if step 6 ran), with small groups already suppressed. Everything between `<!-- report.py:generated -->` and `<!-- report.py:end -->` is copied from those files: don't edit it. A section whose step didn't run says so in one line.

Replace each `<!-- write: ... -->` comment with the text it asks for, and write nothing anywhere else. Use only what the report shows: don't go back to `clean/`, `work/` or the batches for numbers or wording. Quote numbers only as they appear in the report, and don't work out new ones such as percentages. Never fill in, estimate or reverse-engineer a suppressed value, and never name a suppressed group. Then check it:

```bash
python3 <skill>/scripts/report.py --out out/ --check out/report.md
```

The check fails if a generated block was changed, a write slot is still empty, text was added outside a slot, or the written text holds a number not shown in the report, a ticket key or an email address. Fix each problem it lists and run it again until it passes. Don't share the report before then.

The report's sections, and what to write in each slot:
1. **Coverage** (all generated): defects matched by the query, defects analysed, unclassified, ingest gaps, the suppression threshold and, if step 5 ran, link coverage per repo. A high unclassified rate, gaps and low link coverage are listed as findings to read first. Mention them in your reply.
2. **Recurring defect types and themes**: the largest types and themes, with counts and how they trend over the periods.
3. **Where fixes land** (only if step 5 ran): the directories with the most defects fixed in them, from `hotspots.md`. Say that a directory where many fixes land is where defects are found and fixed, not necessarily where they were introduced, and that it reflects the code, not the people working in it.
4. **Where defects were probably introduced** (only if `szz.py` ran): the directories from `szz.md`, labelled an estimate. Say that SZZ blames the lines each fix changed, so refactors, moved code and fixes that only add lines mislead or escape it, give the counts it couldn't trace, and that it reflects the code, not the people working in it.
5. **How defects are found and where they escape**: triggers and escape stages, framed as "what in our process lets this through", never as who.
6. **Clarity** (only if step 6 ran): how completely defects were described, edits after work started, clarifying questions and reopens.
7. **Complexity** (only if step 6 ran): linked issues, comments and, with links, the size of the fixes.
8. **Flow** (only if step 6 ran): lead and cycle time, waiting, flow efficiency and backward moves, framed as how the system moves work, never as how fast anyone works. Keep clarity, complexity and flow as three separate sections and never combine them into one score. Report clarity against rework only within complexity bands, and say these are correlations, not causes.
9. **Caveats**: data quality, gaps, link coverage, what the taxonomy can't capture, that classifications are model judgements, if `szz.py` ran, the commits and repos it couldn't trace, and, if step 6 ran, confounders such as complexity and statuses missing from `signals.yaml`.
10. **Questions for the team**, framed as system improvements. For example: "What in our process lets validation defects reach customers?", not "who missed this?".

Keep the reply short: the report path, the three to five most important findings, and the caveats that matter most.

After the run, suggest the user deletes `raw/`, because it holds unanonymised personal data, and keeps `clean/` and `work/` only as long as they need them.

## Later versions

Open questions to settle in later versions:
- How to attribute a defect that spans several components. For now it counts once, under "multiple components", so team rows add up to the total; investigate whether it should count towards each component instead, and how that interacts with suppression.
- Azure DevOps Server (on-premises). Only Azure DevOps Services (`dev.azure.com`) is supported. An on-premises server needs an optional `url` setting per repo in `scm.yaml`; add it when someone needs it.
