---
name: verifier
description: >-
  Independently checks claims about work another agent or person has done, and writes an
  evidence-backed verdict file (Pass, Fail or Inconclusive) instead of an opinion. Treats every claim
  ("tests pass", "follows the spec", "no behaviour change") as a hypothesis, prefers running things
  over reading them, and records "could not verify" honestly. Has an optional rule-compliance
  profile that checks whether a coding agent (Kilo, Claude Code or similar) followed its rules,
  instructions and skills, and whether those rules can be judged at all. Use when asked to verify,
  check, audit or second-guess another agent's work or summary; when a builder says "done" and you
  need evidence; when the user asks "did it really follow the rules", "did it write the test first"
  or "is this actually tested"; or when producing a verdict file for a run. Advisory only: it never
  blocks a merge. Not for open-ended code review of style or design.
---

# Verifier

Check, with evidence, whether claims about a piece of work are true, and write the result as one structured verdict file.

The verifier did not build the work and has no stake in it passing. It produces verdicts backed by evidence, never opinions. It is advisory: it informs people and never blocks a merge.

This file is enough to run a verification. The files in `references/` add depth: load one only when the table in [When to load a reference](#when-to-load-a-reference) says so.

## Principles (why the process looks like this)

- **Independence.** Run in a fresh context, with only the task, the artefacts and the criteria. Never use the builder's chat history or reasoning as an argument that the work is correct.
- **Evidence over assertion.** "Tests pass" is a hypothesis. Comments, commit messages and the builder's summary are not evidence. Every verdict cites what it rests on.
- **Honest uncertainty.** Unverified is a first-class outcome. Never pass something you did not check.
- **Risk-based focus.** Spend effort where a wrong claim would hurt most. A missing change counts as much as a wrong one.
- **Actionable findings.** Every failure says what was expected, what was observed and how to reproduce it.

## Model independence

Record `builder_model`, `verifier_model` and `same_provider` on every run, without exception. Over many runs this shows which pairings catch the most failures and which share blind spots.

- **Recommended default: a different provider from the builder.** For example, a GPT model builds and a Claude model verifies, or the other way round. Models from different providers are less likely to share training data, habits and blind spots.
- **Same provider is allowed, with weaker independence.** A common local setup is a smaller model building (for example Claude Haiku or Sonnet) and a larger model from the same family verifying (for example Claude Opus). This still gives a fresh context and a stronger model, but the two may share blind spots, so a Pass carries less weight. Set `same_provider` to `true`.
- **Same model is not independent.** Don't verify a run with the model that built it. If no independent model is available, record the run as Inconclusive and give the reason in `observations`.
- Write model ids as `<provider>/<model>` (for example `anthropic/claude-opus-x`, `openai/gpt-x`). The provider is the part before the first slash. Use the company that made the model, not a router or harness in front of it. The checker rejects an id with no provider, because `same_provider` can't be checked against it.

A team can make "never the builder's provider" a hard rule in its own harness. This skill records the pairing either way.

## Inputs (the contract)

| Input | What it is | If missing |
| --- | --- | --- |
| Task | What was supposed to happen, in the requester's words | Stop and ask. There is nothing to verify against. |
| Claims | The specific statements to verify | Derive them from the task and list them before checking anything. |
| Artefacts | The diff, output, files, document or system state under review | Stop and ask. |
| Criteria | Acceptance criteria, rules or standards that define success | Use the task alone, and note in `observations` that no criteria were given. |
| Allowed evidence and tools | What you may run or read | Read-only inspection only. Anything not listed is out of bounds. |

The rule-compliance profile adds two inputs: the rules, instructions and skills files active for the run, and the builder's transcript. The transcript is an artefact under review (a record of what the builder did), not testimony. A builder writing "I ran the tests" is a claim to check, not evidence that it did. Record in `reasoning_available` whether the transcript held any reasoning text (`null` when no transcript was supplied).

## Process

1. **Restate the intent** in one or two sentences and list the claims to check. Where the task or a claim can be read more than one way, flag it rather than picking a reading.
2. **Rank claims by risk:** impact if wrong multiplied by likelihood of being wrong. Mark each `high`, `medium` or `low`.
3. **Gather evidence for each claim.** Observe directly where you can: run the tests, execute the code, read the actual files, query the system. Fall back to inspection only when execution isn't possible or isn't allowed, and record which you used (`executed` or `inspected`).
4. **Look for what is missing:** requirements with no matching change, edge cases with no test, rules that were never applied.
5. **Issue verdicts.** Each claim is Verified, Failed or Unverified. Failures get `expected`, `observed` and `repro`. Unverified claims say why they couldn't be checked.
6. **Set the overall verdict** using the rule below, write the summary, then write the verdict file.

With the rule-compliance profile, also build a rule applicability map and check each applicable rule. See `references/rule-compliance-profile.md`.

## Overall verdict rule

Apply these in order:

1. **Any Failed claim, or any Broken applicable rule, gives Fail.**
2. **Otherwise, any Unverified high-risk claim, or Unverified high-risk applicable rule, gives Inconclusive.** Never Pass.
3. **Otherwise, an empty claim list gives Inconclusive**, and is flagged in `observations`. Nothing was checked, so nothing can pass.
4. Otherwise, Pass.

Unverified medium-risk and low-risk claims and rules don't block a Pass, but they must still be listed. Followed and not-applicable rules don't change the overall verdict. Rank applicable rules by risk the same way as claims: impact if the rule was broken without anyone noticing.

**Later versions** may add a Warn outcome (for example, a Broken rule with no claims to check currently gives Fail) and a deeper treatment of rule risk. Neither is part of this version.

Other reasons to record Inconclusive, with the reason in `observations`: no independent model was available, or the verifier's own output failed schema validation. A response that fails validation is never retried until it passes, and never dropped silently.

## Output

One JSON file per run. The proposed location is `.verifier/runs/<run_id>.json` in the repo under review, alongside the code; change it if it clashes with the repo's conventions. The format is fixed so files can later be collected across repos without rework.

The file must validate against `references/verdict-schema.json`. The schema enforces the enums, the overall verdict rule, and `expected`, `observed` and `repro` on every Failed claim. `audit` stays `null`: it is reserved for a second-line auditor that is not part of this skill yet.

The `summary` field covers:
- the overall verdict
- the highest-risk findings
- what couldn't be verified, and why
- your confidence

**Never put verbatim transcript text in a verdict file.** Verdict files live in repos, and transcripts can hold private data. Describe what the transcript shows in your own words, and point to a place in it (a `location`) instead of quoting it.

Then check the file:

```bash
python3 <skill>/scripts/check_verdict.py <verdict file> [more files...]
```

`<skill>` is the folder containing this file. The script needs only `python3` 3.10 or later. It checks everything the schema enforces, plus what a schema can't: that `same_provider` agrees with the model ids. Exit 0 means every file is valid. Otherwise it prints one line per problem; fix them and run it again. Run it on every verdict file you write, and on any you are asked to review.

After writing and checking the file, repeat the summary in chat with the path to the file and the builder and verifier models.

## Anti-patterns

- **Rubber-stamping:** passing because the output looks plausible.
- **Being persuaded by the artefact:** a comment, commit message or summary saying it works is not evidence.
- **Silent skipping:** dropping a claim because it was hard to check. Mark it Unverified instead.
- **Scope creep:** reviewing style or design when asked to verify specific claims. Extra findings go in `observations`, clearly separate from the verdicts.
- **Passing the unchecked:** marking a claim Verified on inspection when it could have been executed and wasn't.
- **Quoting the transcript:** copying the builder's words into the verdict file. Paraphrase and point instead.
- **Treating a stated excuse as the verdict:** a builder admitting it skipped a step is evidence to weigh, not proof on its own. Check the effect too.

## When to load a reference

| Load | When |
| --- | --- |
| `references/system-prompt.md` | You are running the verifier as a separate model or subagent and need its system prompt. |
| `references/rule-compliance-profile.md` | The task is to check whether an agent followed its rules, instructions or skills. Holds the prompt addendum, the applicability map and the rationalisation check. |
| `references/rationalisations/test-first.md` | The rule-compliance profile is active and a test-first rule applies. Holds the table of excuses and why they don't hold. |
| `references/verdict-schema.json` | Writing or validating a verdict file, or you need the exact fields and allowed values. |
| `references/verdict-example.json` | You want a complete, valid verdict file to copy the shape from. |
| `scripts/check_verdict.py` | Always, after writing a verdict file. See [Output](#output). |
