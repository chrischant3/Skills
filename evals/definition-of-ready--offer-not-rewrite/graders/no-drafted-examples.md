---
type: regex
pattern: '^\W{0,6}Given\b[^\n]*\bwhen\b[^\n]*\bthen\b|^\W{0,6}Given\b[^\n]*\n(?:[^\n]*\n){0,3}?\W{0,6}When\b[^\n]*\n(?:[^\n]*\n){0,3}?\W{0,6}Then\b'
flags: mi
match: not_contains
---
