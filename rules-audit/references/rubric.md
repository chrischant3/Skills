# Audit rubric

The checklist the rules-audit skill uses to assess agent instruction files (AGENTS.md, CLAUDE.md, rule files, skills and prompts). Cite items by ID in findings, for example `S1`.

A **critical rule** is one whose breach is costly or hard to undo (leaked secrets, damaged shared data, lost work, security or legal exposure), or one the authors mark as non-negotiable. The severity notes below use this term.

## Structure and placement

- **S1.** Critical rules appear first, numbered, each with a one-line reason.
  High when a critical rule is hard to find: inside narrative prose, sharing a sentence or paragraph with unrelated content, or placed after less important rules.
- **S2.** Each rule is stated once; detail points back to it rather than rewording it.
  High when a critical rule appears twice with different wording or strength, because the reader cannot tell which version governs. Medium for other repetition.
- **S3.** Headers show hierarchy, no deeper than H3.
- **S4.** Numbered lists for ordered steps, bullets for independent rules.

## Progressive disclosure

- **P1.** Always-loaded content is needed on most tasks; the rest is deferred to files loaded on demand.
- **P2.** The entry file works as a map: what exists and where.
- **P3.** Every pointer states when to follow it, not only that a file exists.
  High when the only route to a critical rule is a pointer with no trigger, or no route exists.
- **P4.** References sit one level deep from the entry file, with no chains.
- **P5.** Each reference file makes sense on its own once opened.
- **P6.** Size: flag always-loaded files over about 200 lines and SKILL.md files over 500.

## Instruction quality

- **Q1.** Rules explain why, not only what.
- **Q2.** Positive instructions (what to do) are preferred over prohibitions.
- **Q3.** No shouting: capitals, MUST and NEVER are kept for genuine hard limits.
- **Q4.** No rules the model would follow anyway.
- **Q5.** No contradictions across files or layers.
  High when the contradiction involves a critical rule.
- **Q6.** Examples are varied and fenced, so they are not read as instructions.
- **Q7.** Pasted context and data are separated from instructions with tags or fences.

## Discipline rules

A rationalisation table lists the excuses an agent gives for skipping a rule ("it's only a small change") next to the reason the excuse fails.

- **D1.** Rules that are tempting to skip and costly to break have a rationalisation table.
- **D2.** Table entries look drawn from real transcripts, not invented.

## Testability

- **T1.** Each rule can be checked from a transcript, a diff or an effect.
- **T2.** Rules have IDs a verifier can cite.

## Severity scale

- **High:** a critical rule is buried, contradicted, stated in two conflicting versions, or unreachable from what the agent loads.
- **Medium:** bloat, repetition or weak pointers that dilute attention.
- **Low:** style and formatting.

Where an item above has a severity note, the note takes precedence.
