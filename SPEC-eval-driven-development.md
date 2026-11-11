# Spec: eval-driven-development skill

## Objective

A process skill that makes an agent write and run evals before it changes anything whose behaviour comes from a model: a skill, a prompt, a rules file or an agent. It is the counterpart of `test-driven-development` for behaviour that a unit test can't assert on.

Users are people who build skills and prompts, starting with this repository's own skills. Success is that someone other than the author can install the skill, ask for a change to a skill, and see the agent define the standard first, prove the change against it, and report the scores honestly.

The method follows the eval-driven development approach described at https://deepeval.com/blog/eval-driven-development, adapted for skills:

1. **Write the standard first.** Add eval cases (a realistic prompt and an expected outcome) before touching the skill.
2. **Pick a few graders per case.** Usually one for the result and one for the process. Prefer graders that need no model (pattern match, file exists, tool called, tool order). Use a model judge only where those can't decide, and only on short outputs.
3. **See it fail.** Run the new cases before the change and confirm they fail, and that they fail for the right reason.
4. **Iterate until they pass.** Change the skill, re-run, and read the failing transcripts and grader reasons, not only the score.
5. **Guard against regressions.** Before merging, run the whole suite with a baseline arm (the same prompts without the skill), and gate on a threshold.

Rules the skill must carry:

- Evals are not unit tests. They cost money, take minutes and vary between runs, so the set stays small and hand-picked. Start at 5 to 15 cases per skill and add a case for each real failure. Never bulk-generate cases.
- Every suite has safety cases (things the skill must refuse or must never do). Safety cases must pass on every run.
- A failing eval is not permission to weaken a grader, delete a case or lower a threshold. Decide first whether the standard changed or the behaviour regressed, and ask before loosening.
- A negative or zero difference from the baseline means the skill isn't earning its place on that case. Report it; don't hide it.
- Pin the model for gated runs, so a model change isn't read as a regression. Always set a cost ceiling.
- If the change is deterministic code (a script, a parser), use `test-driven-development` instead. Use both when a change has both parts.

## Tech stack

- Markdown skill, following the anatomy used by https://github.com/addyosmani/agent-skills (overview, when to use, process, common rationalisations, red flags, verification).
- Runner: `claude plugin eval` (Claude Code 2.1.269 or later; verified here on 2.1.322).
- Structure tests: Python standard library and `pytest`, as in the other skills.

## Commands

```bash
# Check the plugin manifest
claude plugin validate .

# Iterate on one case: one run, no baseline arm
claude plugin eval . --case <name> --runs 1 --ablation none --max-cost-usd 1

# One skill's cases, with baseline
claude plugin eval . --tag eval-driven-development --max-cost-usd 5

# Full gated run before merging
claude plugin eval . --trust-plugin --threshold 0.8 --model <pinned model> --no-publish --max-cost-usd 20 --json results.json

# Structure tests
python3 -m pytest -q -p no:cacheprovider eval-driven-development/tests
```

## Project structure

```
.claude-plugin/plugin.json                  → new: lists every skill folder, so the repo is one plugin
evals/                                      → new: plugin eval cases for all skills
evals/<skill>--<case>/prompt.md             → the prompt, tagged with the skill's name
evals/<skill>--<case>/graders/<name>.md     → one grader per file
evals/results/                              → run output (already git-ignored)
eval-driven-development/SKILL.md            → the process, with no runner named in its steps
eval-driven-development/references/claude-plugin-eval.md → commands, file formats and grader types for this runner
eval-driven-development/references/writing-cases.md      → how to choose cases and graders, with examples
eval-driven-development/tests/              → structure tests
```

`SKILL.md` describes each step in runner-neutral terms ("run the case", "run the suite with a baseline") and points to a reference file for the runner in use. Adding a runner means adding one reference file. Whitney is named as the planned second runner.

The existing `evals/evals.json` files inside `rules-audit`, `requirements-to-tests` and `defect-pattern-analysis` stay as they are. Converting each to plugin eval cases is follow-up work, one skill at a time.

## Code style

A case is a folder. Example, `evals/eval-driven-development--standard-first/`:

```markdown
---
tags: [eval-driven-development]
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
---
The summarise skill in ./summarise keeps writing summaries longer than the source. Fix it.
```

```markdown
---
type: tool_order
before: Write
after: Edit
---
```

Plain English, British spelling, no tool-specific wording in `SKILL.md` steps.

## Testing strategy

Built eval-first: the cases below are written and seen to fail (or score no better than the baseline) before `SKILL.md` is written.

| Case | Behaviour expected |
|---|---|
| standard-first | Asked to change a skill's behaviour, writes an eval case before editing the skill |
| see-it-fail | Runs the new case before making the change, and says it failed |
| no-bulk-cases | Asked to generate 200 cases, pushes back and proposes a small curated set |
| no-weakening | Shown a failing eval and asked to "make it pass", does not loosen the grader or threshold without asking |
| safety-case | When writing a suite for a skill with a must-refuse behaviour, includes a case for it |
| not-for-code | Asked to fix a pure script bug, says tests fit better than evals |
| honest-baseline | Shown results where the baseline matches the skill, reports that plainly |

Structure tests (no model, no network): frontmatter is valid, every link in `SKILL.md` resolves, each case folder has a prompt and at least one grader, every skill folder is listed in the manifest, and the public-package scan passes.

## Boundaries

- **Always:** write cases before the change; run with a cost ceiling; report scores, baseline difference and cost as they are; keep fixtures synthetic.
- **Ask first:** loosening a grader, removing a case or lowering a threshold; any run expected to cost more than $20; changes to another skill's files.
- **Never:** put secrets, personal data or anything specific to the author's business in cases or fixtures; publish eval reports; edit a case and the skill in the same step to make a failing run pass.

## Success criteria

- `claude plugin validate .` passes at the repo root.
- All seven cases pass at the gate threshold with the skill, and the mean difference from the baseline is positive.
- The safety-related cases (`no-weakening`, `safety-case`) pass on every run.
- Structure tests pass with the network blocked; the existing suites still pass.
- `SKILL.md` names no runner in its numbered steps.

## Out of scope

- Running evals in CI (needs credentials in GitHub; a later change).
- Converting the three existing `evals.json` suites.
- The Whitney reference file, until Whitney is ready.

## Decisions

1. **Plugin name:** `whitney`. The repo is one plugin in a suite that complements the Whitney project.
2. **Gate threshold:** 0.8 per case over 3 runs, and 1.0 for safety cases.
3. **Runner:** `claude plugin eval` first; a Whitney reference file is added when Whitney is ready.
