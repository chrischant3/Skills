# Held-out trigger prompts

Prompts for checking that a skill's description generalises: that the skill loads when someone needs it and stays out of the way when they don't. Each prompt has one grader, `loads-when-it-should`. It expects the skill to load (`min: 1`), or never to load (`max: 0`).

They were written before the description changes they check, and they are never used while tuning a description. Tuning against them would measure the tuning, not the description. They sit outside `evals/` so the gated suite doesn't run them.

Run them once per model, with no baseline arm:

```bash
claude plugin eval . --eval-dir evals-heldout --ablation none --runs 1 --model <model> --trust-plugin --no-publish --json held-out.json
```
