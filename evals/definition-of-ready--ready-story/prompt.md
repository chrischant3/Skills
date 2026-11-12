---
tags: [definition-of-ready]
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
---

Is this story ready for the team to pick up next sprint?

```markdown
# Show the due date on each loan

## Description
As a library member, I want to see the due date next to each book on my Loans page, so that I can return books on time and avoid fines. This adds a "Due" column to the existing Loans page. It doesn't change how due dates are calculated, or which loans the page lists (loans not yet returned). "Today" is the date in the library's time zone, as elsewhere on the site.

## Acceptance criteria
1. Every loan on the Loans page shows its due date in the format 14 Mar 2027.
2. A loan due today or in the next 3 days shows the date in bold with the label "Due soon".
3. A loan whose due date is before today shows the date with the label "Overdue".
4. The column is read by screen readers as "Due date".

## Examples
- Given a loan due on 20 Mar 2027 and today is 10 Mar 2027, when I open the Loans page, then I see "20 Mar 2027" with no label.
- Given a loan due on 12 Mar 2027 and today is 10 Mar 2027, when I open the Loans page, then I see "12 Mar 2027" in bold with "Due soon".
- Given a loan due on 9 Mar 2027 and today is 10 Mar 2027, when I open the Loans page, then I see "9 Mar 2027" with "Overdue".

## Dependencies
None. The due date is already returned by the loans API.

## Open questions
None.

## Verification
- Unit tests for the date format (criterion 1) and the three label rules (criteria 2 and 3), passing in CI
- An automated test that the column's accessible name is "Due date" (criterion 4), passing in CI
- Screenshots of each label state attached to the ticket
```
