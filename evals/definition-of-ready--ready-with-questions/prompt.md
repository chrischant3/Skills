---
tags: [definition-of-ready]
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
---

Can you check whether this one's ready? Planning is tomorrow.

```markdown
# Let members choose Welsh or English for reminder emails

## Description
As a library member, I want to choose whether my reminder emails are in Welsh or English, so that I can read them in my preferred language. This adds a language choice to the Preferences page and uses it when sending reminders.

## Acceptance criteria
1. The Preferences page has a "Reminder email language" choice with the options English and Cymraeg.
2. Members who haven't made a choice, including existing members, get English.
3. Reminder emails are sent in the language chosen.
4. Changing the choice takes effect for the next reminder sent.

## Examples
- Given a member who has chosen Cymraeg, when a reminder is sent, then the email subject and body are in Welsh.
- Given a member who has made no choice, when a reminder is sent, then the email is in English.

## Dependencies
The Welsh email text has been translated and approved, and is in the content store.

## Open questions
- Should the overdue notice (a separate email, not a reminder) also follow this choice? Not needed for this story: the overdue notice stays English-only until a later story.

## Verification
- Tests for both languages and the default, passing in CI
- A sample Welsh reminder email checked by the translator
```
