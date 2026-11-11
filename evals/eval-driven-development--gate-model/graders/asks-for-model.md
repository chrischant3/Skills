---
type: llm
---

PASS if the reply asks the user which model they want the final run to use, or tells them to choose and set one, AND offers Opus as the default if they have no preference.
FAIL if it picks a model without asking the user, or leaves the model unset, or offers a default other than Opus.
