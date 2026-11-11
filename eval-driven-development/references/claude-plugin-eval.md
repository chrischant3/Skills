# Running evals with `claude plugin eval`

`claude plugin eval` ships with Claude Code (2.1.269 or later). It starts a fresh, isolated session for each run, sends the case's prompt, and grades the result. By default it runs each case three times with the plugin and three times without it, and reports the difference.

Official documentation: https://code.claude.com/docs/en/plugin-evals

## What it needs

It evaluates a **plugin**, not a bare skill folder. If your skills aren't in a plugin yet, add a manifest at the root that lists them:

```json
{
  "name": "my-skills",
  "version": "0.1.0",
  "description": "What these skills do.",
  "skills": ["./my-skill", "./another-skill"]
}
```

Save it as `.claude-plugin/plugin.json` and check it with `claude plugin validate .`.

## Where cases live

```
evals/
├── <case-name>/
│   ├── prompt.md            # settings at the top, then the prompt
│   └── graders/<name>.md    # one grader per file
└── results/<timestamp>/     # written by each run; keep it out of git
```

A case needs at least one grader or it won't load. When one plugin holds several skills, start each case name with its skill and tag it, so you can run one skill's cases with `--tag`.

`prompt.md`:

```markdown
---
tags: [my-skill]
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
---

The summaries from my summarise skill are longer than the source. How would you fix it?
```

Only read-only tools are allowed unless you grant more with `--allow-tools`. Unknown settings are errors.

## Graders

| Type | Passes when | Settings |
|---|---|---|
| `regex` | the pattern is found (or not found) | `pattern`, `flags`, `match: not_contains`, `target` |
| `tool_used` | a tool was called a number of times in range | `tool`, `input_match`, `min`, `max` |
| `tool_order` | one tool was first called before another | `before`, `after` |
| `file_exists` | the run created a file matching a path | `path`, `exists` |
| `llm` | a model judge votes PASS in at least 2 of 3 votes | rubric in the file body, `focus` |
| `baseline` | a judge finds the run at least as good as a saved transcript | `baseline_file` |

A pattern grader:

```markdown
---
type: regex
pattern: 'unit test|pytest'
flags: i
---
```

A model judge. State both outcomes:

```markdown
---
type: llm
---

PASS if the plan writes an eval case before the step that changes the skill.
FAIL if the plan changes the skill first, or has no eval case.
```

A check that the skill was used. When a baseline arm runs, this is shown as an indicator and left out of the score, because the baseline can't use the skill:

```markdown
---
type: tool_used
tool: Skill
input_match: 'my-skill'
---
```

Patterns are JavaScript regular expressions. Use `flags: i`, not `(?i)`. By default `regex` and `llm` read the last message; set `target` or `focus` to `trace`, `files` or a produced file to read something else.

## Commands for each step of the loop

**See it fail, and iterate** (one case, one run, no baseline):

```bash
claude plugin eval . --case <case-name> --runs 1 --ablation none --max-cost-usd 1
```

**Check what the cases measure** (run them before the skill exists, or compare with the baseline):

```bash
claude plugin eval . --tag <skill> --max-cost-usd 5
```

**Gate before merging** (all cases, three runs each, with baseline, model pinned):

Ask the user which model to use first. If they have no preference, use Sonnet (`--model sonnet`). For results you can compare across weeks, give the full model ID rather than the alias, because an alias moves to newer models.

```bash
claude plugin eval . --tag <skill> --threshold 0.8 --model sonnet --max-cost-usd 20 --no-publish
claude plugin eval . --tag safety --threshold 1.0 --model sonnet --max-cost-usd 10 --no-publish
```

**Before publishing, run on several models.** Ask the user which models to run. Offer Opus, Sonnet and Haiku together as the first option. The tool takes one `--model` per run, so run the gate once per model and write each result to its own file:

```bash
for model in opus sonnet haiku; do
  claude plugin eval . --tag <skill> --threshold 0.8 --model "$model" --max-cost-usd 20 --no-publish --json "results-$model.json"
done
```

Record the scores as a table with one column per model, for example:

| Case | Opus | Sonnet | Haiku |
|---|---|---|---|
| keeps-action-items | 1.00 | 1.00 | 0.67 |

Each model's `aggregates.overallScore` and each case's `aggregates.score` in its result file give these numbers. Opus costs the most per run and Haiku the least, so set the cost ceiling per model. `claude plugin eval` runs Claude models only; models from other providers will come with Whitney.

The tool has one `--threshold` per run, so tag safety cases `safety` and gate them in a second run at 1.0.

Useful options: `-j <n>` runs up to 8 sessions at once; `--json <file>` writes the full result; `--judge-model <model>` changes the judge; `--trust-plugin` skips the first-run trust question (needed where there is no terminal, such as CI).

## Reading the result

The summary lists each case with its score **with** the plugin, **without** it, and the difference. A run's score is the share of its graders that passed; a case's score is the mean over its runs. The command exits 0 when every case meets the threshold, 1 when one doesn't, and 2 when it stopped early at the cost ceiling. The difference from the baseline never changes the exit code, so read it yourself. [reading-scores.md](reading-scores.md) explains what good scores look like.

Each run also writes `aggregate-result.json` and a self-contained `report.html` under `evals/results/<timestamp>/`. Open the report to read transcripts and each grader's reason.

If the difference is negative, check the judge before blaming the skill: try a stronger `--judge-model`, and read the transcripts it failed.

## Limits to know

- Each run is a full paid session. A suite of 10 cases at the defaults is 60 sessions.
- Runs don't load your settings, memory, other plugins or `CLAUDE.md`. That is deliberate, and it means a skill that depends on them will behave differently.
- The isolation limits what a run can reach but is not a security boundary. Only evaluate plugins you trust.
