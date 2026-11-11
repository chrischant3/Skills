---
tags: [definition-of-ready]
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
---

Here's a ticket for next sprint. Ready to go?

```markdown
# Members can renew a loan online

## Description
As a library member, I want to renew a book from my Loans page, so that I don't have to visit or phone the library. A Renew button is added to each loan.

## Examples
- Given a loan due on 20 Mar 2027 with no reservations, when I press Renew, then the due date moves to 3 Apr 2027.
- Given a loan that another member has reserved, when I press Renew, then I see "This book is reserved and can't be renewed".

## Dependencies
The renew endpoint already exists in the loans API.

## Open questions
None.

## Verification
- Tests for renew and reserved, passing in CI
```
