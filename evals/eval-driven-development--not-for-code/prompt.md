---
tags: [eval-driven-development]
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
---

We do eval-driven development on this repo now. My skill ships a helper, `scripts/parse_dates.py`, and it returns March for the input `2026-02-30` when it should raise an error. I'm about to fix it. Write me the eval case that proves the fix: the prompt and one grader. Keep it short.
