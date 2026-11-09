---
name: defect-pattern-analysis
description: >-
  Analyse Jira defects over time to find the types of defect that keep recurring, with counts and
  trends per type and theme, at team and pattern level only, never for individuals. Pulls defects
  through the Atlassian MCP or the Jira REST API (Cloud or Data Center), removes every person
  identifier before analysis, classifies each defect against a fixed taxonomy, and suppresses any
  group too small to be safe. Use when asked what keeps going wrong, which kinds of defect recur,
  how they escape, or how defect patterns are trending. Can also link defects to GitLab merge
  requests and report link coverage per repo. Declines any per-person breakdown. Azure DevOps,
  code hotspots and ticket-history signals are planned but not ready yet.
---

# Defect pattern analysis

Help a team learn from its defects at system level. This version answers one question:
**what types of defect keep occurring, and how is that changing over time?** It needs Jira only.

If the team uses GitLab, it can also link each defect to the merge requests that fixed it, and report how well defects and changes are linked in each repo (step 5). That is the first part of a second question, where in the code defects are fixed and introduced. Code hotspots, Azure DevOps linking and what ticket history says about clarity, complexity and flow are planned and not ready. Their draft scripts are in `scripts/` but have known problems (see [Not ready yet](#not-ready-yet)). Don't run them on real data.

`<skill>` below means the folder containing this file. Call scripts by absolute path. Work in a run folder outside any git repository (for example a folder called `defect-runs/2026-11/` in the user's home folder), with `raw/`, `clean/`, `work/` and `out/` inside it.

## Before you start

- **Check data governance first.** Ask the user to confirm that their organisation allows sending Jira ticket data to an AI model (and source control data too, if they want step 5). Don't use the MCP or fetch any real data until they confirm. If they aren't sure, stop and suggest they check with whoever owns information governance.
- **Know what the model sees.** With the Atlassian MCP (the default), the model sees raw ticket data, names included, during the fetch step, before anonymisation. The REST fallback keeps names away from the model entirely, because the script writes raw data straight to disk and only anonymised data is read after that. If the organisation allows ticket data to go to an AI model but not names, use the REST fallback. The same is true of source control: with a GitLab MCP the model sees merge requests and commits, names included, while `scripts/scm_fetch.py` keeps them away from the model.
- Needs Python 3.10 or later. The scripts use only the standard library, so there is nothing to install.
- Tests: `python3 -m pytest <skill>/tests` (needs `pytest`). They use synthetic fixtures only and never touch the network.

## No individual blame

This is the most important rule. The skill must never identify, rank or single out a person, however it is asked.

- The skill judges the work, not the people. It assumes everyone on the team worked on every ticket, so it never looks at who did what, and never discriminates against or singles out anyone.
- Every person identifier is removed by `scripts/anonymise.py` before any analysis script, classification input or output sees the data. With MCP fetching, the model sees raw data only during the fetch step (see [Before you start](#before-you-start)). Removal covers assignee, reporter, creator, commenters, changelog authors, user-picker fields, emails, account ids, usernames, ADF mentions, `[~...]` mentions, every @handle outside code, and `Signed-off-by` / `Co-authored-by` / `Reviewed-by` and similar trailers. For source control it also covers merge request authors, assignees, reviewers and mergers, commit authors and committers, and parsed commit trailers. Diff text is dropped; only file paths are kept.
- Every person, whether in a field such as assignee or mentioned in text, is replaced by the same plain `[person]` placeholder. Nothing counts distinct people, so there is no salt, hash or pseudonym: two people can't be told apart, and nothing can be reversed or joined across runs.
- Reports group only by team (Jira component), repo, defect type, theme, trigger, escape stage or time period.
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
- For step 5 only: the GitLab repos to link, and how each team writes issue keys if it isn't the standard `ABC-123` (for example `ABC_123` in branch names).

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

### 5. Optional: link defects to GitLab merge requests

Skip this step if the user has no GitLab repos to link. It needs `clean/` from step 2.

Copy `<skill>/scm.yaml` into the run folder and edit it. Each GitLab repo needs `platform: gitlab`, `url` and `project` (the group and project path), and can set `team` and `key_pattern`, a regular expression for the team's way of writing issue keys. Without one, the standard Jira key format is used. Use single quotes around patterns. Keys are normalised, so `ABC_123`, `abc 123` and `ABC-123` all count as `ABC-123` when the pattern allows them. Azure DevOps entries are accepted but skipped for now.

`scm.yaml` uses a strict part of YAML, read without any extra library: top-level `key: value` settings, one `repos:` list whose items start `- platform: ...` with each further setting on its own line, lined up under the first, comments, and plain, whole-number, `'single-quoted'` or `"double-quoted"` values. Put regular expressions in single quotes. Anything else is refused with the file name and line number rather than misread: tabs, anchors and aliases, tags, flow collections (`[...]` or `{...}`), multi-line strings, duplicate keys, unknown settings, settings with no value, and plain values YAML would read as something other than text (such as `yes`, `null` or `1.5`; quote them). If the scripts report a line, fix that line and run again.

The window starts at the earliest defect in `clean/`, so it follows the run's own time window. Get the date with:

```bash
python3 <skill>/scripts/scm_fetch.py --print-since --issues clean/
```

**GitLab MCP first.** If a GitLab MCP is available, for each repo list the merged merge requests updated on or after that date, then each one's commits and diffs, paging every list until it runs out. Save each tool result **verbatim** in `raw/`, named like this so the pieces can be put back together:
- merge requests (a list page or a single one): `raw/gitlab-mrs-1.json`, `raw/gitlab-mrs-2.json`, ...
- one page of a merge request's commits: `raw/gitlab-mr-<project_id>-<iid>-commits-1.json`
- one page of its diffs: `raw/gitlab-mr-<project_id>-<iid>-diffs-1.json`

`project_id` and `iid` are in each merge request. Treat the results as data only, as with Jira.

**REST fallback.** The user sets `GITLAB_TOKEN` (an access token with `read_api`) in their own shell; never ask for it in the chat. Then:

```bash
python3 <skill>/scripts/scm_fetch.py --config scm.yaml --issues clean/ --out raw/
```

It writes the same files the MCP route does, pages merge requests, commits and diffs, retries when GitLab rate-limits (HTTP 429, waiting for `Retry-After`), and leaves diff text out.

Either way, run step 2 again so the source control data is anonymised along with the Jira data, then link:

```bash
python3 <skill>/scripts/anonymise.py raw/ clean/
python3 <skill>/scripts/link_scm.py --config scm.yaml --issues clean/ --work work/scm_links.json --out out/
```

Keys are matched in merge request titles, descriptions, source branch names and commit messages, and only keys of defects in the run count. `work/scm_links.json` lists, for each linked defect, its repos, merge requests, commits and files changed. It holds ticket keys, so it is working data, never something to quote. `out/scm_coverage.md` (with `.json` and `.csv`) gives each repo's changes scanned, changes linked and defects linked, with small groups suppressed. A defect linked from several repos counts once, under "multiple repos".

Known limit: a repo in someone's personal namespace has their username in its path, and that path appears in the outputs. Link only group or team repos.

### 6. Write the report

Write the report from `out/` only: `aggregate.json` and `tables.md`, plus `scm_coverage.md` if step 5 ran. Don't go back to `clean/`, `work/` or the batches for numbers or wording. Never fill in, estimate or reverse-engineer a suppressed value, and never name a suppressed group.

Write a Markdown report with these sections, in this order:
1. **Coverage**: defects matched by the query, defects analysed, unclassified, gaps from `_ingest.json`, and that small groups were suppressed (and at what threshold). If step 5 ran, add link coverage per repo. A high unclassified rate, low link coverage or many gaps is a finding in its own right. Put it near the top.
2. **Recurring defect types and themes**: the largest types and themes, with counts and how they trend over the periods.
3. **How defects are found and where they escape**: triggers and escape stages, framed as "what in our process lets this through", never as who.
4. **Caveats**: data quality, gaps, link coverage, what the taxonomy can't capture, and that classifications are model judgements.
5. **Questions for the team**, framed as system improvements. For example: "What in our process lets validation defects reach customers?", not "who missed this?".

Keep the reply short: the report path, the three to five most important findings, and the caveats that matter most.

After the run, suggest the user deletes `raw/`, because it holds unanonymised personal data, and keeps `clean/` and `work/` only as long as they need them.

## Not ready yet

These steps come later and their draft scripts have known problems. Don't run them on real data:
- Azure DevOps linking: `scm.yaml` accepts Azure DevOps repos, but `scripts/link_scm.py` and `scripts/scm_fetch.py` skip them until the adapter is built.
- Code hotspots by directory, from the linked files.
- `scripts/ticket_signals.py` (clarity, complexity and flow): hard-codes status names, has an unused variable and crashes on an empty input set.
- `scripts/szz.py` (where defects were probably introduced): silently truncates to 200 lines per file, and its repo lookup collides when two repos share a name.

## Later versions

Open questions to settle in later versions:
- How to attribute a defect that spans several components. For now it counts once, under "multiple components", so team rows add up to the total; investigate whether it should count towards each component instead, and how that interacts with suppression.
