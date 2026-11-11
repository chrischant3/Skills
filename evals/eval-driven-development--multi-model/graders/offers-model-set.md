---
type: llm
---

PASS if the reply recommends running the suite on more than one model, asks the user to pick which models, and gives Opus, Sonnet and Haiku together as the first option.
FAIL if it runs or recommends only one model, or picks the models without asking, or does not offer Opus, Sonnet and Haiku together as the first option.
