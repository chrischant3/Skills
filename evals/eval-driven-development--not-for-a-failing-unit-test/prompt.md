---
tags: [eval-driven-development, trigger-guard]
max_turns: 4
allowed_tools: [Read, Glob, Grep, Skill]
---

This test started failing after I refactored the date helper. What's wrong?

```python
def parse_date(text):
    year, month, day = (int(p) for p in text.split("-"))
    return date(year, 1, 1) + timedelta(days=day - 1 + sum(DAYS_IN[:month - 1]))

def test_rejects_february_30():
    with pytest.raises(ValueError):
        parse_date("2026-02-30")
```

It gets 2 March back instead of an error.
