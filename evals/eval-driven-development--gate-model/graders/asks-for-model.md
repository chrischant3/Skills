---
type: llm
---

PASS if the reply asks the user which model or models the final run should use, or tells them to choose, AND offers Sonnet as the default if they have no preference.
FAIL if it picks a model without asking the user, or leaves the model unset, or offers a default other than Sonnet.
