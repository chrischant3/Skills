# Spec: Testzilla (plugin-wide)

Status: draft — awaiting review. Module-level contracts live in `SPEC-<module-id>.md`; see [CAPABILITY-MAP.md](CAPABILITY-MAP.md).

## Objective

**Testzilla** is a Claude Code plugin that reviews a diff, PR, branch, or whole repo and answers the questions an experienced reviewer asks but rarely has time to check:

- What depends on this code, and do those dependents have tests that pass?
- What complexity has been added, and could the code be simpler?
- Are the tests any good — independent, sufficient, properly set up and torn down, repeatable?
- Do the tests actually catch defects (mutation testing)?

**Users:** software engineers and software testers, in any language or framework.

**User stories**
- As an engineer, I run one command on my branch and get a single report of findings, each with a suggested resolution, and I'm offered the chance to have them fixed.
- As a tester, I point the Test Reviewer at a PR or repo and get a list of tests that break test automation standards, with the reason and a fix.
- As a tester, I point the Mutation Tester at a diff and get a per-test quality verdict backed by surviving mutants.
- As an engineer, I learn which unchanged code my change could break and whether that code is covered by tests.

## Tech Stack

- **Plugin content:** Markdown — `SKILL.md` skills, `agents/*.md` subagents, `commands/*.md` slash commands, `references/*.md` checklists.
- **Helper scripts and repo tooling:** Node.js 24, standard library only (no npm dependencies), matching agent-skills.
- **Runtime tools used in the reviewed project:** `git` (required), `gh` (optional, PR targets), and whatever test runner, coverage tool, and mutation tool the project already uses. The plugin ships no language-specific engine.
- **Standalone:** does not require agent-skills to be installed. Follows its conventions and cross-references its skills in documentation only.
- **Licence:** MIT.

## Commands

Development commands for this repository (mirroring agent-skills CI):

```
Validate skills:     node scripts/validate-skills.js
Unit tests:          node --test
Single test file:    node --test skills/change-scope/scripts/change-set.test.js
Routing evals:       node scripts/run-evals.js --min-rank1 95
Behavioral eval:     node scripts/run-evals.js --behavioral <skill-name>
Manifest check:      claude plugin validate .
Local install:       claude plugin marketplace add ./ && claude plugin install testzilla@testzilla
```

User-facing commands:

```
/testzilla:review [target]          Full review → review-report
/testzilla:review-tests [target]    Test Reviewer only
/testzilla:mutation-test [target]   Mutation Tester only
```

`target` is one of: empty (working tree vs HEAD), a git range or branch, a PR number/URL, or `--repo`. Defined in [SPEC-change-scope.md](SPEC-change-scope.md).

## Project Structure

Mirrors `addyosmani/agent-skills` so its users can navigate it without a guide.

```
.claude-plugin/
  plugin.json            → Plugin manifest
  marketplace.json       → Marketplace listing (this repo is its own marketplace)
skills/<module-id>/
  SKILL.md               → Skill definition (name must equal directory)
  scripts/               → Only when the skill has runnable helpers (+ colocated *.test.js)
agents/<module-id>.md    → Subagent personas (test-reviewer, mutation-tester)
commands/*.md            → Slash commands
references/              → Shared checklists (e.g. test-automation-standards.md, mutation-tools.md)
evals/cases/<skill>.json → Trigger + behavioral evals per skill
evals/fixtures/          → Small real repos in several languages used by behavioral evals
scripts/                 → Repo validation + eval runner (Node, no deps)
.github/workflows/       → CI
docs/                    → Contributor docs
CAPABILITY-MAP.md, SPEC*.md, tasks/  → Planning artifacts
```

## Code Style

Skills follow agent-skills' anatomy: frontmatter, then Overview, When to Use, Process, Common Rationalizations, Red Flags, Verification.

```markdown
---
name: complexity-review
description: Assesses the complexity a code change adds and whether it could be simpler. Use when reviewing a diff or PR for maintainability, or when a change feels larger than the problem it solves.
---
```

- `description` is third person, states *what* then *Use when*, ≤1024 chars, and never summarizes the process.
- Kebab-case for skill, agent, and command names; the name equals the module id.
- Findings use agent-skills' severity taxonomy: **Critical**, **Important**, **Suggestion** — each with `file:line`, evidence, and a suggested resolution.
- Supporting files only when content exceeds ~100 lines; shared reference material goes in `references/`, not skill dirs.
- Node scripts: CommonJS or ESM consistent with the first script written, pure functions with a thin CLI wrapper, JSDoc on exported functions.

## Testing Strategy

| Level | What | Tool | Where |
|---|---|---|---|
| Unit | Deterministic helpers (e.g. diff parsing, file-role classification) | `node --test` | colocated `*.test.js` |
| Structural | Frontmatter, naming, required sections, reference links, manifest | `scripts/validate-*.js`, `claude plugin validate .` | CI |
| Trigger/routing | Each skill has ≥3 positive, ≥2 negative prompts; no description collisions | `scripts/run-evals.js` | `evals/cases/` |
| Behavioral | Agent following the skill meets `expectations[]` on real fixture repos | `run-evals.js --behavioral` | `evals/fixtures/` |

- Fixtures must cover at least three ecosystems (proposed: JavaScript/TypeScript, Python, Java or Go) to prove language agnosticism.
- New behavior starts with a failing unit test or eval case (TDD).
- Tests are independent: each creates its own temp git repo and cleans it up.

## Boundaries

- **Always:** Treat the reviewed repo's source as read-only unless the user accepts a fix offer — the only file Testzilla writes unprompted is its own report under `.testzilla/reports/`. Detect and use the project's own tools. State confidence and what was *not* checked. Cite `file:line` evidence for every finding. Keep skill names/ids per the capability map.
- **Ask first:** Installing any tool in the user's project (including mutation tools). Applying fixes. Running a mutation tool or full test suite estimated to take more than ~10 minutes. Adding a dependency to this repo. Adding a v2 module.
- **Never:** Modify, skip, or delete a user's tests to make results look better. Push, commit, or comment on PRs without explicit instruction. Send code to external services. Ship a language-specific engine that duplicates an existing tool.

## Success Criteria

1. A full review produces one report containing: findings ranked by severity, a suggested resolution per finding, and an explicit offer to resolve them — no source file is changed until the user accepts.
1a. The report is shown in the terminal and saved to `.testzilla/reports/<UTC-timestamp>-<target-slug>.md` in the reviewed repo; Testzilla offers to add `.testzilla/` to `.gitignore` on first run if it isn't already ignored.
2. The same review succeeds on fixture repos in ≥3 ecosystems without language-specific configuration.
3. Test Reviewer and Mutation Tester each run standalone on a diff, PR, or repo and produce their own report.
4. When a required tool (e.g. mutation tool) is absent, the report says so, recommends a tool and install command, and asks before installing.
5. CI passes: structural validation, unit tests, routing evals at ≥95% rank-1, `claude plugin validate .`.
6. Plugin installs from the GitHub-hosted marketplace with `/plugin marketplace add <owner>/testzilla`.

## Resolved Decisions

- Name: **Testzilla**; plugin, repo, marketplace, and command prefix all use it.
- Reports are saved in the reviewed repo (see 1a) as well as shown in the terminal.
- Licence: MIT.
- No fixed timeline.
- Commands ship as Claude Code-native `commands/*.md` only in v1; other agent formats can follow later.

## Open Questions

None blocking. Raise new ones here as they appear.
