# Fix hotspots by directory

Each count is the number of defects whose fixes touched the directory (folders cut to depth 2), from changes merged on or after 2026-01-10. A defect counts once per directory, however many files or commits its fix had, and once in each directory it touched, so the counts don't add up to the number of defects. Groups with fewer than 5 defects are suppressed.

## Summary

- defects_with_files: 24

## Directories

| repo | platform | directory | defects |
|---|---|---|---|
| group/checkout-service | gitlab | src/checkout | 9 |
| Accounts/accounts-api | azure | src/Accounts | 8 |
| group/checkout-service | gitlab | tests/checkout | 8 |
| Accounts/accounts-api | azure | tests/Accounts.Tests | 6 |
| [person]/checkout-tool | gitlab | notes/[person] | 5 |

4 groups suppressed: each had fewer than 5 defects, or was hidden so that a small group can't be worked out from the totals.
