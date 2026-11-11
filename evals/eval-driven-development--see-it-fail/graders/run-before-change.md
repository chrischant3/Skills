---
type: llm
---

PASS if the reply says to run the new eval case now, before changing the skill, and says it should FAIL at this point (and that a pass now would mean the case or its check is wrong or isn't testing the behaviour).
FAIL if the next step is to edit the skill, or if it says to run the case but doesn't say a failure is the expected result.
