---
type: llm
---

PASS if the plan puts writing an eval case (a prompt with an expected outcome or a check on summary length) BEFORE the step that changes the skill's instructions.
FAIL if the plan changes the skill first, or contains no eval case at all, or only tests the change afterwards.
