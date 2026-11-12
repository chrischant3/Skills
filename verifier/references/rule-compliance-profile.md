# Rule-compliance profile

A profile layered on the core verifier. It answers two questions about a coding agent's run (Kilo, Claude Code, or a similar harness):

1. Did the agent follow its rules, instructions and skills on this task?
2. Are those rules any good? Can compliance even be judged from their wording?

Across many runs, per-rule results show which rules are reliably followed, which are ignored and which are unclear. That is feedback on the instructions themselves, not only on the code.

Set `"profile": "rule-compliance"` in the verdict file.

## Additional inputs

- **Active rules, instructions and skills files.** The files the agent actually had loaded for the run, not every file in the repo. Where they live depends on the harness, for example `AGENTS.md`, `CLAUDE.md`, a `.kilo/` or `.claude/` folder, or a skills folder such as `.kilo/skills/`, `.agents/skills/` or `.claude/skills/`. If you can't tell which were loaded, say so in `observations`.
- **The builder's transcript**, alongside the diff. How to export it depends on the harness: Claude Code writes JSONL session files, and Kilo keeps sessions in a local database.

### What the transcript is for

The core verifier never sees the builder's reasoning. This profile does, because "did the agent consider rule X?" can only be answered from the record of what it did. The independence principle still holds in a narrower form:

- The transcript is **evidence of actions** (which files were edited in what order, which commands ran, what the output was).
- It is **never an argument for correctness.** "I ran the tests and they passed" in the transcript is a claim. The tool output that follows it, or a fresh run, is the evidence.
- Some harnesses or models store little or no reasoning. Set `reasoning_available` to `false` when the transcript has no reasoning text, so that "no rationalisations found" is not read as "the agent made no excuses".
- **Never copy transcript text into the verdict file.** Describe what it shows in your own words, and point to where it is.

## Addendum to the system prompt

Append this after the prompt in `system-prompt.md`.

```markdown
You are also checking whether the builder followed its rules, instructions and skills. You will receive those files and the builder's transcript.

The transcript is a record of what the builder did. Use it as evidence of actions (edits, commands, tool output), never as proof that the work is correct.

1. Build an applicability map: for every rule, decide whether it should have applied to this task, and why.
2. For each applicable rule, rank its risk (high, medium, low) and verify compliance from the diff or transcript: Followed, Broken or Unverified, with evidence.
3. Flag rules that should have triggered but show no sign of being considered.
4. Flag rules too ambiguous to judge, and any rules that conflict.
5. If a rule has a rationalisation table, check the builder's final summary and any reasoning against it. Record each excuse you find, whether or not it is in the table, as a pointer to where it is.

Any Broken applicable rule makes the overall verdict Fail. Otherwise, any Unverified high-risk applicable rule makes it Inconclusive. Never copy verbatim text from the transcript into your result.

You are judging the rules as well as the work: say plainly when a rule's wording made compliance impossible to assess.
```

## Applicability map

List every rule in the active files, not only the ones that look relevant. For each one:

| Field | Meaning |
| --- | --- |
| `rule_id` | A stable id. Use the file's own id if it has one; otherwise `<file stem>/<short slug>`, for example `testing/tdd-first`. |
| `applicable` | `true` if the rule should have applied to this task. |
| `risk` | `high`, `medium` or `low` when applicable: impact if the rule was broken without anyone noticing. `null` when not applicable. |
| `applicability_reason` | Why, in one line. "Task adds new behaviour" or "No database change in the diff". |
| `verdict` | `Followed`, `Broken` or `Unverified` when applicable; `null` when not. Any `Broken` makes the overall verdict Fail. An `Unverified` high-risk rule makes it Inconclusive, unless something else fails it. |
| `evidence` | What the verdict rests on. For a rule that isn't applicable, what shows that. |
| `flags` | Any of `not_considered`, `ambiguous`, `conflicts_with:<rule_id>`. |

### Checking compliance by effect

Prefer evidence of effect over evidence of intent. For a test-first rule, for example:

- Did a test file change, and run and fail, before the implementation changed? Check the order of edits and test runs in the transcript, or the commit order.
- Does the new test fail if the change is reverted?
- Is a skipped, deleted or weakened test hiding in the diff?

A builder saying "I wrote the test first" is not evidence. The order of the edits is.

### Flags

- `not_considered`: the rule applied, and nothing in the transcript or diff shows the builder took it into account.
- `ambiguous`: the rule's wording made compliance impossible to judge. Say what was unclear in `evidence`.
- `conflicts_with:<rule_id>`: following this rule would break another one. Flag it on both rules.

## Rationalisation check

A rationalisation is a reason the builder gives for not following a rule: "this is too simple to need a test", "there's no test runner, so I didn't add one". Some rules carry a table of known excuses and why they don't hold; see `rationalisations/`.

- Search the builder's **final summary** first, then any **reasoning** the transcript holds. In practice, excuses mostly appear in final summaries, and many harnesses store little or no reasoning.
- Flag every excuse in a final summary, every time.
- Record each one in the verdict file's optional `rationalisations` array: the `rule_id`, where it came from (`source`), a `location` pointer into the transcript, and the matching `table_entry`. The `location` holds the transcript or session id, the message index and the part or block id, each `null` if the harness doesn't record it. It never holds the text itself.
- An excuse that matches no table entry is recorded with `"new": true` and `"table_entry": null`, for the rule's owner to decide whether it joins the table.
- **A detected excuse is evidence, not a verdict.** Weigh it against the effect-based checks above. A builder that names a real blocker (no runner, shell denied) and stops to ask has not broken a rule by saying so. A builder that skips the test and says nothing has, and only the effect check will catch it.
- Use an empty array when you searched and found nothing. Leave the field out when no search was done (for example, the profile isn't active). That keeps "none found" apart from "not looked for".

Verdict files are stored in repos and transcripts can hold private data, so the excuse itself stays in the transcript. Anyone with access to the transcript can follow the `location` to read it. This holds everywhere in the file, including `evidence`, `summary` and `observations`: when you explain why an excuse matches a table entry, name the entry and the `location`, and describe the excuse in your own words, never in the builder's.
