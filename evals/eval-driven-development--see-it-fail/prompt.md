---
tags: [eval-driven-development]
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
---

My `commit-message` skill adds emoji to commit subjects and I want it to stop. I've written an eval case for it: the prompt asks for a commit message, and a pattern check fails if the reply contains an emoji.

My plan: edit the skill to say "no emoji" now, then run the case to confirm it passes. Good to go? One or two sentences.
