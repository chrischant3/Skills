---
type: llm
---

PASS if the reply says an eval case is the wrong tool for this fix because the script is deterministic code, and recommends a unit test instead (it may include the unit test).
FAIL if it writes an eval case (a prompt for a model plus a grader) as the proof without saying a unit test is the better fit.
