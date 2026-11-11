---
name: eval-driven-development
description: >-
  Use this skill before writing, generating, reviewing or running eval cases,
  and before creating, fixing or changing a skill, a prompt, a rules file or
  agent instructions, including when a skill misbehaves and someone wants it
  fixed, before the final eval run before merging or publishing a skill,
  when choosing which models to run evals on, and when summarising eval
  results. It drives changes to model
  behaviour with evals: write a small set of cases first, see them fail,
  make the change, then gate on the suite and a no-skill baseline. Not for
  deterministic code such as scripts and parsers; use test-driven
  development there.
---

# Eval-Driven Development

## Overview

Decide what good looks like before changing how a model behaves. The standard is a small set of eval cases: realistic prompts, each with a few graders. Write the cases, watch them fail, make the change, and merge only when the suite passes and beats the same prompts run without the skill.

Evals borrow the spirit of test-driven development, but they are not unit tests. Every run costs money, takes minutes and can differ from the last one. That changes how many you write and how you read them.

| | Unit tests | Evals |
|---|---|---|
| How many | As many as useful | A small hand-picked set |
| Cost and speed | Free, instant | Paid, minutes |
| Result | Same every run | Varies; run each case several times |
| Verdict | Exact | Pattern checks where possible, a model judge where not |

## When to Use

- Creating a skill, prompt, rules file or agent instructions
- Fixing or changing how one of those behaves
- Adding a rule the model must follow, especially something it must refuse
- Changing the model, or restructuring instructions, and needing to know nothing got worse
- Reporting eval results to someone else

**When not to use:** the change is deterministic code (a script, a parser, a validator). Prove that with a unit test, written first. A change with both parts needs both: tests for the code, evals for the behaviour.

## The Loop

The steps name no tool. Commands and file formats for the runner in use are in a reference file:

- `claude plugin eval`: [references/claude-plugin-eval.md](references/claude-plugin-eval.md)
- Whitney: planned. It will add models from other providers.

### 1. Write the standard first

Before touching the skill, write the eval cases that describe the behaviour you want. A case is a prompt a real user would send, plus what a good response does.

- Start with 5 to 15 cases for a skill. Add one for each real failure you meet later.
- Write each case by hand. Never bulk-generate cases: a few hundred generated prompts cost a lot to run, mostly repeat each other, and bury the cases that matter.
- Include **safety cases**: anything the skill must refuse or must never do. Mark them, because they are held to a stricter pass mark.
- Don't lead the witness. A prompt that names the answer ("…and remember to decline") tests nothing.

See [references/writing-cases.md](references/writing-cases.md) for how to choose cases.

### 2. Pick a few graders per case

Use two or three graders: usually one on the result and one on the process.

- Prefer graders that need no model: a pattern is present or absent, a file was created, a tool was called, one tool was called before another.
- Use a model judge only where those can't decide, and only on short outputs. Write its rubric as explicit PASS and FAIL conditions.
- A grader should fail for one reason. If you can't say what a failure means, split it.

### 3. See it fail

Run the new cases before making the change.

- A new case should fail now. If it passes, either the behaviour already exists or the grader isn't checking it. Find out which before going on.
- Check it fails for the right reason. Read the output, not only the score.
- Run the cases without the skill as well. A case that passes without the skill doesn't measure what the skill adds. Rewrite it so it doesn't hint at the answer, or keep it knowingly as a regression guard.

### 4. Change, run, read

Make the smallest change that should move the failing cases, then re-run them.

- While iterating, run one case, once, to keep cost and time down.
- When a case fails, read the transcript and the grader's reason before editing anything. The fault may be in the skill, the case or the grader.
- Change the skill or the case, never both in one step. If both change, you can't tell which made it pass.

### 5. Gate on the suite and the baseline

Before merging, run the whole suite the way it will be judged.

- Run every case several times (three is the usual default) and with a **baseline**: the same prompts without the skill.
- Pass mark: **0.8 per case, and 1.0 for safety cases**, unless the project sets its own.
- **Ask the user which model to run the gate on** before running it, and offer Sonnet as the default if they have no preference. Then pin that model for every gated run, so a model update isn't mistaken for a regression.
- **Before publishing, run the suite on several models.** People install a skill and use it with whatever model they have, so a skill that passes on one model may fail on another. Ask the user which models to run, offering the provider's main models together as the first option (for Claude: Opus, Sonnet and Haiku). Run each model separately with the same cases and pass mark.
- **Record each model's scores separately**, in a results table with one column per model, and keep it with the change description or release notes. Never average models together; a skill that fails on one model fails for everyone using it.
- Set a cost ceiling on every run.
- Report the scores, the difference from the baseline and the cost as they are. Where the skill scores the same as or worse than the baseline, say so. That case is telling you the skill isn't earning its place there.
- Re-run the whole suite whenever the instructions, the model or the structure changes.

## When an Eval Fails

A failing eval is not permission to change the eval. First decide which of these happened:

1. **The behaviour regressed.** Fix the skill.
2. **The standard changed on purpose.** Update the case, and say so in the change description.
3. **The grader is wrong** (too strict, too loose, or judging the wrong thing). Fix the grader, after confirming from the transcripts that the behaviour is right.

Ask the person who owns the skill before loosening a grader, removing or skipping a case, lowering a pass mark or reducing the number of runs. Never re-run until it happens to pass.

## Common Rationalisations

| Rationalisation | Reality |
|---|---|
| "It's a one-line wording change" | One line of instructions can change behaviour everywhere. One case is cheap. |
| "I'll write the evals after" | Then they describe what the skill does, not what it should do. |
| "More cases means better coverage" | Evals aren't unit tests. A bloated suite is slow, costly and mostly noise. |
| "It passed once" | Model output varies. One pass in three is a failure. |
| "The judge is being picky, loosen it" | Read the transcript first. The judge may be right. |
| "Scores went up, ship it" | Compared with what? Without a baseline you don't know the skill caused it. |
| "It's code, but I'll use an eval anyway" | A model in the loop makes a deterministic check slow, costly and flaky. Write a unit test. |

## Red Flags

- Editing a skill with no failing case that describes the change
- A new case that passes before the change, and nobody asks why
- Cases written by generating variations of each other
- A skill with a must-refuse rule and no safety case for it
- Loosening a grader in the same change that edits the skill
- Results reported without the baseline, the number of runs or the cost
- A summary that mentions the gains and leaves out the cases that got worse

## Verification

Before calling the change done:

- [ ] The cases were written before the change and seen to fail
- [ ] Each case has a result grader, and model judges are used only on short outputs
- [ ] Safety cases exist for every must-refuse rule and pass on every run
- [ ] The full suite passes at the pass mark, run several times per case
- [ ] The baseline was run, and every case with no gain is reported
- [ ] The user chose the model (Sonnet by default), it was pinned, and a cost ceiling was set
- [ ] Before publishing, the suite ran on the models the user picked, and each model's scores were recorded separately
- [ ] No grader, case or pass mark was loosened without the owner's agreement
