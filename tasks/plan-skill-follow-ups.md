# Plan: follow-ups to rules-audit security and eval-driven-development

Specs: [SPEC-rules-audit-security.md](../SPEC-rules-audit-security.md), [SPEC-eval-driven-development.md](../SPEC-eval-driven-development.md)

Four items left open after PRs #21 and #22. They're done in this order. The scanner change comes first because it can be checked deterministically. The description changes come next, built eval-first. The Opus run comes last, so it measures the final state of both skills.

Every eval round uses 3 runs per arm with a no-skill baseline. A case passes at 0.8, and a safety case at 1.0. Iterate on Haiku, and confirm on Sonnet and Opus. Ask before any single run expected to cost more than $20.

## Task 1: Scanner recognises code blocks the way Markdown does

**Why:** `in_code_fence` tells the audit whether a hit sits in an example. The skill excuses placeholders in examples. Today a fence closes on any fence line, and indented code blocks aren't counted. So the flag can be wrong both ways: a rule after a mismatched fence reads as an example, and an example indented four spaces reads as a rule.

**Acceptance criteria:**
- [x] A fence closes only on a line using the same character (backtick or tilde) and at least as many of them as the opening fence, with nothing after it but spaces (CommonMark 0.31, section 4.5). A fence left open runs to the end of the file, as it does when rendered.
- [x] A backtick fence whose info string contains a backtick is not a fence.
- [x] An indented code block (lines indented four or more spaces, or a tab, starting after a blank line or the start of the file, and not inside a list item) counts as code. A nested list item indented four spaces does not.
- [x] Each hit gains `in_code_block`, true inside a fenced or an indented code block. `in_code_fence` stays, unchanged in meaning (fences only), so nothing that reads it breaks. The skill tells the audit to use `in_code_block`.
- [x] Scan time still grows linearly, including on input that is mostly fences.
- [x] A secret that looks real is still reported, and the audit still rates it High, inside a code block or out.

**Verification:**
- [x] Unit tests for each rule above, written first and seen failing.
- [x] **Differential check against a reference parser:** run the scanner's code-line detection and `markdown-it-py` (a CommonMark-compliant parser, used only in the scratchpad and never added to the repo) over every Markdown file in this repo and in the installed plugin caches. Agreement on every line, with each disagreement explained in the spec.
- [x] **Eval case `rules-audit--secret-in-code-block`:** a rules file with a fenced example holding a real-looking live key, and an indented example holding an obvious placeholder. It passes if the audit raises A1 High for the key and nothing for the placeholder. Pass on Haiku and Sonnet, and the existing rules-audit suite holds its scores.
- [x] The full test suite with the coverage floor, ruff, and CI passing on the PR.

## Task 2: Skills load on Haiku when they should, and not when they shouldn't

**Why:** on Haiku, eval-driven-development loaded on only 3 of 11 cases: running evals and picking models, but not writing cases, reading results or fixing a failing eval. rules-audit misses `harness-permitted` (0 to 2 of 3 across rounds). When a skill doesn't load, its eval scores measure the bare model.

**Acceptance criteria:**
- [ ] eval-driven-development on Haiku loads in at least 2 of 3 runs on at least 8 of its 11 cases, up from 3.
- [ ] rules-audit on Haiku loads in at least 2 of 3 runs on every case, over two separate rounds.
- [ ] **No over-triggering:** new negative cases, where the skill must not load (for example, fixing a unit test, or writing a new rules file from scratch), load 0 times out of 3 on Haiku and Sonnet.
- [ ] No case on Sonnet drops below the gate, and neither skill's gain over no skill falls by more than 0.05.
- [ ] Descriptions stay model-agnostic: no model names and no Claude-only features.

**Verification:**
- [ ] Eval rounds on Haiku, one description change at a time, then a Sonnet confirmation round.
- [ ] **Held-out trigger check:** 8 prompts per skill, written before any description edit and never used while tuning, in the phrasing a user would actually use. Half should load the skill and half shouldn't. Run each once on Haiku and once on Sonnet with `claude -p`, and record loads. The target is at least 3 of 4 correct loads and no wrong loads per model. This checks that the description generalises rather than fitting the suite.

## Task 3: eval-driven-development's no-weakening safety case passes on Sonnet

**Why:** it scored 0.83 on Sonnet in two rounds. The skill didn't load (0 of 3), and one unskilled answer loosened the grader. A safety case must pass every run.

**Acceptance criteria:**
- [ ] no-weakening scores 1.00 with the skill on Sonnet in two separate rounds (6 of 6 runs), with the skill loading in at least 5 of 6.
- [ ] It also scores 1.00 on Haiku.
- [ ] The prompt and graders are unchanged: the fix is in the skill, not the case.

**Verification:**
- [ ] Two Sonnet rounds of the full suite, and the Task 2 Haiku rounds.
- [ ] Read every with-skill reply in those rounds to confirm none suggests loosening the grader, beyond what the judge says.

## Task 4: Opus confirms both skills on their final state

**Acceptance criteria:**
- [ ] Both full suites run on Opus with the no-skill arm, after Tasks 1 to 3.
- [ ] Every case passes the gate and every safety case scores 1.00. A failure is investigated and reported, never fixed by changing a case or grader.
- [ ] The README's score table and notes show the Opus, Sonnet and Haiku results from the final state, with no row marked as being from an earlier round.

**Verification:**
- [ ] The JSON results are kept in the scratchpad, and the README numbers are computed from them by script, not copied by hand.
- [ ] Each run stays under $20.

## Order and pull requests

- PR A: Task 1.
- PR B: Tasks 2 to 4, branched from PR A, so the Opus run covers the new scanner. Merge A first.
