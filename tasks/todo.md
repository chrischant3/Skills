# Task List: change-scope (Testzilla)

Plan: [plan.md](plan.md) · Spec: [SPEC-change-scope.md](../SPEC-change-scope.md)

## Phase 1: Foundation

## Task 1: Plugin manifests, MIT licence, README skeleton

**Description:** Make this repo a valid, installable Claude Code plugin and its own marketplace, so everything after it can be verified by tooling rather than by eye.

**Acceptance criteria:**
- [ ] `.claude-plugin/plugin.json` declares name `testzilla`, version `0.1.0`, MIT licence, repo/homepage, and `skills`/`commands`/`agents` paths
- [ ] `.claude-plugin/marketplace.json` lists the plugin with a GitHub source
- [ ] `LICENSE` is MIT; `README.md` states what Testzilla does, install instructions, and links the specs

**Verification:**
- [ ] `claude plugin validate .` exits 0
- [ ] Manual: `claude plugin marketplace add ./` then `claude plugin install testzilla@testzilla` succeeds

**Dependencies:** None
**Files likely touched:** `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `LICENSE`, `README.md`
**Estimated scope:** Small

## Task 2: CI workflow running skill validation and unit tests

**Description:** Stand up the verification loop before any logic exists: a skill/manifest validator and the Node test runner, wired into GitHub Actions.

**Acceptance criteria:**
- [ ] `scripts/validate-skills.js` checks every `skills/*/SKILL.md` for valid frontmatter, `name` matching its directory, kebab-case, and a description with a "Use when" trigger; exits non-zero with a specific message on failure
- [ ] `scripts/validate-skills-test.js` covers at least one passing and one failing case
- [ ] `.github/workflows/ci.yml` runs `node scripts/validate-skills.js`, `node --test`, and `claude plugin validate .` on push and PR

**Verification:**
- [ ] `node --test` passes locally
- [ ] `node scripts/validate-skills.js` exits 0 with no skills present and non-zero against a deliberately broken fixture
- [ ] CI green on the first push

**Dependencies:** Task 1
**Files likely touched:** `scripts/validate-skills.js`, `scripts/validate-skills-test.js`, `.github/workflows/ci.yml`
**Estimated scope:** Medium

### Checkpoint: Foundation
- [ ] `claude plugin validate .` passes
- [ ] `node --test` runs and CI is green
- [ ] Plugin installs locally from `./`
- [ ] Review with human before proceeding

## Phase 2: change-scope core

## Task 3: `parseUnifiedDiff` — unified diff to files and hunks

**Description:** The pure heart of the module: turn `git diff` output into structured file entries with hunk ranges. TDD, no git calls, no CLI.

**Acceptance criteria:**
- [ ] Handles added, modified, deleted and renamed files, including `old_path` for renames
- [ ] Extracts every hunk's `old_start`/`old_lines`/`new_start`/`new_lines`, and counts lines added/removed
- [ ] Binary files are returned flagged rather than throwing; malformed input raises a descriptive error

**Verification:**
- [ ] Tests pass: `node --test skills/change-scope/scripts/change-set.test.js`
- [ ] Cases exist for rename, binary, no-newline-at-EOF, multi-hunk, and empty diff

**Dependencies:** Task 2
**Files likely touched:** `skills/change-scope/scripts/change-set.js`, `skills/change-scope/scripts/change-set.test.js`
**Estimated scope:** Medium

## Task 4: File classification — role, language, skip rules

**Description:** Decide what each changed file *is*, so downstream modules can tell tests from source without language-specific config.

**Acceptance criteria:**
- [ ] `classifyRole` returns source/test/config/docs/generated/binary using the single heuristics table in the spec, and correctly identifies test files in at least JS/TS, Python, Java and Go conventions
- [ ] `detectLanguage` maps extensions to a language, returning `null` for unknown without failing
- [ ] Lockfiles, vendored directories and generated files land in `skipped` with a reason

**Verification:**
- [ ] Tests pass: `node --test skills/change-scope/scripts/change-set.test.js`
- [ ] A table-driven test asserts classification for at least 20 representative paths

**Dependencies:** Task 3
**Files likely touched:** `skills/change-scope/scripts/change-set.js`, `skills/change-scope/scripts/change-set.test.js`
**Estimated scope:** Small

## Task 5: `buildChangeSet` + CLI for the working-tree target

**Description:** First end-to-end slice: run the script in a dirty repo and get the full change set for staged and unstaged changes to tracked files.

**Acceptance criteria:**
- [ ] `buildChangeSet` assembles `target`, `files`, `skipped` and `summary` exactly as SPEC-change-scope.md defines
- [ ] With no argument, the CLI diffs tracked changes against `HEAD`, excludes untracked files, and reports their count in `summary.untracked_ignored`
- [ ] Output is valid JSON on stdout; diagnostics go to stderr

**Verification:**
- [ ] Integration test builds a temp git repo with staged, unstaged and untracked changes and asserts the change set; the temp repo is removed afterwards
- [ ] Manual: run it in this repo with local edits present

**Dependencies:** Task 4
**Files likely touched:** `skills/change-scope/scripts/change-set.js`, `skills/change-scope/scripts/change-set.test.js`
**Estimated scope:** Medium

### Checkpoint: Core
- [ ] Working-tree target produces a valid change set in a real repo
- [ ] Unit and integration tests pass
- [ ] JSON contract reviewed against the spec with the human before consumers exist

## Phase 3: Remaining targets

## Task 6: Range and branch targets with default-branch detection

**Description:** Support `<base>..<head>`, `<base>...<head>` and a bare branch name, resolving the default branch to find the merge base.

**Acceptance criteria:**
- [ ] `..` and `...` range semantics are both honoured and recorded in `target`
- [ ] A bare branch diffs from its merge-base with the detected default branch (`origin/HEAD`, then `main`, then `master`; ask if none)
- [ ] A branch target and its equivalent explicit merge-base range produce identical `files` output

**Verification:**
- [ ] Integration test creates a temp repo with a diverged branch and asserts both forms match
- [ ] Unknown ref exits non-zero with an actionable message and no partial JSON

**Dependencies:** Task 5
**Files likely touched:** `skills/change-scope/scripts/change-set.js`, `skills/change-scope/scripts/change-set.test.js`
**Estimated scope:** Medium

## Task 7: `--repo` target

**Description:** Whole-repo review: every tracked file, status `unchanged`, no hunks — the mode used when reviewing an existing codebase rather than a change.

**Acceptance criteria:**
- [ ] Lists all tracked files with `status: "unchanged"` and `hunks: []`
- [ ] Role, language and skip rules apply identically to the diff-based targets
- [ ] `summary` reports zero lines added/removed

**Verification:**
- [ ] Integration test against a temp repo asserts file count and shape
- [ ] Manual: run against this repo

**Dependencies:** Task 5
**Files likely touched:** `skills/change-scope/scripts/change-set.js`, `skills/change-scope/scripts/change-set.test.js`
**Estimated scope:** Small

## Task 8: PR target via `gh`

**Description:** Accept a PR number or URL, resolving base and head through `gh` and reusing the existing diff pipeline.

**Acceptance criteria:**
- [ ] `gh pr view`/`gh pr diff` supply base, head and diff; the parsed result matches the equivalent local range
- [ ] Missing `gh`, unauthenticated `gh`, or a base ref absent locally each produce a distinct actionable error and exit non-zero — never a `git fetch`
- [ ] Tests use captured `gh` fixtures, so CI needs no network or credentials

**Verification:**
- [ ] Tests pass with `gh` stubbed
- [ ] Manual: run against a real PR in a repo you own

**Dependencies:** Task 6
**Files likely touched:** `skills/change-scope/scripts/change-set.js`, `skills/change-scope/scripts/change-set.test.js`, `evals/fixtures/gh/*.json`
**Estimated scope:** Medium

### Checkpoint: Targets
- [ ] Every target kind produces a change set or a specific error
- [ ] Branch and explicit-range forms agree
- [ ] Review with human before proceeding

## Phase 4: Surface and verification

## Task 9: Guardrails — size threshold, errors, untracked count

**Description:** Make failure modes and oversized targets safe and legible rather than confusing.

**Acceptance criteria:**
- [ ] Over 200 changed files or 5,000 changed lines sets a `needs_confirmation` flag with the counts, so the skill can ask before continuing
- [ ] Non-git directory, unknown ref and detached-HEAD-without-default-branch each exit non-zero with a distinct message and emit no partial JSON
- [ ] Every `skipped` entry carries a reason

**Verification:**
- [ ] Tests cover each error path and the threshold boundary
- [ ] Manual: run in a non-git directory

**Dependencies:** Task 6, Task 7
**Files likely touched:** `skills/change-scope/scripts/change-set.js`, `skills/change-scope/scripts/change-set.test.js`
**Estimated scope:** Small

## Task 10: `skills/change-scope/SKILL.md`

**Description:** The agent-facing skill: when to resolve scope, how to run the script, how to present scope to the user, and what to do at the confirmation threshold.

**Acceptance criteria:**
- [ ] Frontmatter `name: change-scope` with a third-person description containing "Use when" triggers, under 1024 characters
- [ ] Sections follow agent-skills anatomy: Overview, When to Use, Process, Common Rationalizations, Red Flags, Verification
- [ ] Documents the change-set contract by reference and states the read-only boundary

**Verification:**
- [ ] `node scripts/validate-skills.js` exits 0
- [ ] Manual: the skill triggers in a session that asks "what changed on this branch?"

**Dependencies:** Task 9
**Files likely touched:** `skills/change-scope/SKILL.md`
**Estimated scope:** Small

## Task 11: `evals/cases/change-scope.json`

**Description:** Trigger and behavioral eval coverage for the skill, in the agent-skills case format. Scope depends on Open Question 1 in the plan.

**Acceptance criteria:**
- [ ] At least 3 positive triggers and 2 negative triggers (each with an `owner`)
- [ ] At least 1 behavioral eval backed by a fixture repo under `evals/fixtures/`
- [ ] The case file validates against whatever runner Open Question 1 settles on

**Verification:**
- [ ] The eval runner (or validator) passes on the case file
- [ ] Manual: the negative prompts do not route to `change-scope`

**Dependencies:** Task 10
**Files likely touched:** `evals/cases/change-scope.json`, `evals/fixtures/**`
**Estimated scope:** Small

### Checkpoint: Complete
- [ ] All SPEC-change-scope.md success criteria met
- [ ] CI green
- [ ] Human review before `impact-analysis` consumes the contract

---

# Task List: defect-pattern-analysis

Skill: [SKILL.md](../defect-pattern-analysis/SKILL.md) · Runbook: [testing-runbook.md](../docs/testing-runbook.md)

## Task 1: Manual test against a real Jira project

**Description:** Every phase is built and covered by automated tests on synthetic data. This task is the first run by hand against real defects, to find what the tests can't: unclear steps, error messages that don't help, wrong classifications and a report that reads badly. Keep the run's `raw/`, `clean/`, `work/` and `out/` folders outside this repository, and describe any problem in general terms, without ticket text or names.

**Acceptance criteria:**
- [ ] Steps 1 to 4 run on a small date range or one team: fetch into `raw/`, anonymise into `clean/`, classify, and count into `out/`
- [ ] Spot-check `clean/`: no names, emails, account ids or @handles remain
- [ ] Spot-check about ten classifications against the tickets: the type and theme are right, and anything unclear is left unclassified rather than guessed
- [ ] The coverage numbers in `out/` make sense for the query (defects matched, analysed and unclassified, ingest gaps)
- [ ] Step 5 runs against at least one GitLab or Azure DevOps repo: link coverage, fix hotspots and the introduction estimate (`szz.py`, with a local clone)
- [ ] Step 6 runs: clarity, complexity and flow come out as separate sections, with nothing grouped by person
- [ ] Step 7: `report.py --out out/` writes the report, the write slots are filled, and `report.py --out out/ --check out/report.md` passes
- [ ] The report reads well to someone who didn't run it, and its questions for the team are about the system, not people

**Verification:**
- [ ] Manual: each step above completed, or the failure noted with the command and error message
- [ ] Manual: a list of what went wrong or felt awkward, turned into issues or follow-up tasks

**Dependencies:** None
**Files likely touched:** none (findings become follow-up tasks)
**Estimated scope:** Medium
