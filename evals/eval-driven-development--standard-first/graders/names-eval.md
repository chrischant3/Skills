---
type: regex
# An eval, a grader, a test set or suite, or cases the plan writes. A plan that
# says "write the failing cases first" names an eval without using the word.
pattern: '\beval|\bgraders?\b|\btest (?:set|suite)\b|\b(?:test|failing|eval) cases?\b|\b(?:hand-)?write (?:the |a few |some |\d+ to \d+ )?(?:\w+ )?(?:cases|prompts)\b'
flags: i
---
