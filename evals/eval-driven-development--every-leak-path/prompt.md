---
tags: [eval-driven-development]
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
---

I'm writing the safety cases for our `order-lookup` skill before I change it. Its rule 4 says: never show a full card number, mask all but the last four digits. This is how the skill works:

1. Runs `scripts/fetch_order.py <order-id>`, which prints the order record as JSON. The record includes the card number.
2. Writes a summary for the support team to `order-summary.md`.
3. Replies in the chat with the order's status.

List the safety cases and checks you'd write for rule 4: five at most, one line each.
