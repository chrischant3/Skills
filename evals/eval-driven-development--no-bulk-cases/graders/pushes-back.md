---
type: llm
---

PASS if the reply declines or pushes back on producing 200 generated cases, and recommends a small hand-picked set instead (roughly 5 to 15 to start, grown from real failures), giving a reason such as cost, run time, or low-quality generated cases.
FAIL if it agrees to produce all 200, or confirms the other 195 will follow, without raising any objection.
