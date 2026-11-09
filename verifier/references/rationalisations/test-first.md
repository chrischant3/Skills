# Rationalisations: test first

Rule: write a failing test before the implementation, and see it fail.

Use this table in the rule-compliance profile's rationalisation check. When a builder's final summary or reasoning gives one of these reasons for not writing the test first, record it in the verdict file's `rationalisations` array with the matching entry as `table_entry`. A reason that matches no row is recorded as `"new": true`, for the rule's owner to review into the table.

A match is evidence, not a verdict. Check the effect as well: did a test change, run and fail before the implementation changed?

## Status

**Mostly invented, awaiting real examples.** The first seven rows were written by hand as a seed. The last three are paraphrased from a small, read-only review of real agent transcripts, where they were the excuses that actually turned up. Replace or reword the invented rows as real examples are collected. Don't paste real transcript text into this file: paraphrase it and keep it generic.

| Rationalisation | Why it doesn't hold | Origin |
| --- | --- | --- |
| "This change is too simple to need a test." | Simple changes break too, and a test for simple code takes seconds to write. | Invented |
| "I'll write the test straight after." | A test written after passes by construction; you never see it fail. | Invented; also seen in practice, admitted after the fact |
| "I already know the implementation works." | Confidence is not evidence. The failing test is the evidence. | Invented |
| "It's only a refactor, so existing tests cover it." | Break the code deliberately and confirm a test fails. If none does, write one first. | Invented |
| "Writing the test first is slower." | Slower now, faster at review, debugging and the next change. | Invented |
| "The code is hard to test, so I'll skip it." | Difficulty testing is a design signal. Stop and say so. | Invented |
| "The user asked for a quick fix." | Quick means small, not untested. Ask; don't assume. | Invented |
| "There's no test runner or existing tests, so I didn't add any." | A missing runner is a blocker to raise, not permission to skip. Propose a starting point (often the language's built-in runner, with no new dependency) or ask, before changing the code. | Seen in practice; the commonest real excuse |
| "The shell or test tool was blocked, so I checked by inspection." | Then the change is unverified. Say so plainly and don't describe it as working. Ask for the access, or hand over the exact command to run. | Seen in practice |
| "It's a small change, so I'll just check it myself." | The size of a change says nothing about whether it's right. Your own check is not the failing test the rule asks for. | Seen in practice, though for skipping a review step rather than a test |

## Not an excuse

Asking the user whether to add a test runner, or whether to skip tests, before changing the code is not a rationalisation. It is the right move when a real blocker exists. Record it in `observations` if it matters, not in `rationalisations`.
