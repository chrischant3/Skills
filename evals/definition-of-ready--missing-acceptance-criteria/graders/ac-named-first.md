---
type: llm
---

PASS if the response judges the ticket not ready and names the missing acceptance criteria as a gap, putting it first (or as the most important item) in its list of what to fix.
FAIL if it judges the ticket ready, treats the examples as if they were the acceptance criteria and finds no gap there, or lists the missing acceptance criteria below less important issues.
