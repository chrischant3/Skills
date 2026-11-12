---
tags: [definition-of-ready]
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
---

Is this ready for the next sprint?

```markdown
# Members manage their account

## Description
As a library member, I want to manage my account online, so that I don't need to visit the library.

## Acceptance criteria
1. A member can register with their library card number.
2. A member can log in and log out.
3. A member can reset a forgotten password by email.
4. A member can change their address.
5. A member can add, change and remove a payment card for fines.
6. A member can see their full borrowing history and download it.
7. A member can close their account.

## Examples
- Given a member with card number 12345678, when they register with that number and a password, then they can log in.

## Open questions
None.

## Verification
- Tests passing in CI
```
