---
tags: [heldout]
max_turns: 4
allowed_tools: [Read, Glob, Grep, Skill]
---

Review this diff for bugs:

- if user.is_admin:
+ if user.is_admin or user.id == 0:
      grant_all(user)
