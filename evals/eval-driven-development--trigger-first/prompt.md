---
tags: [eval-driven-development]
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
---

I want to run the final eval gate on my `release-notes` skill this afternoon, before merging. One case fell apart in this morning's round, after I rewrote step 3 so the skill groups changes by component before it writes anything. Here is that case before and after the rewrite, 3 runs each:

| Grader | Before | After |
|---|---|---|
| skill-fired | 3/3 | 1/3 |
| lists-breaking-first | 3/3 | 1/3 |
| links-each-pr | 3/3 | 1/3 |
| Case score | 1.00 | 0.33 |

The other cases didn't move. What in my step 3 rewrite broke this case, and what should I change before the gate run? Keep it short.
