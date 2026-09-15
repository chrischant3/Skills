# Capability Map: Testzilla

Approved 2026-09-15. Module ids are stable — do not rename. This map is the index of which specs exist.

| Module id | Kind | Responsibility | Depends on | Spec |
|---|---|---|---|---|
| `change-scope` | skill + script | Resolve a target (diff, PR, branch, repo) into a normalized change set | — | [SPEC-change-scope.md](SPEC-change-scope.md) |
| `impact-analysis` | skill | Find dependents of changed code, locate their tests, check they exist/pass, measure coverage | `change-scope` | not yet written |
| `complexity-review` | skill | Assess complexity added by the change; could it be simpler? | `change-scope` | not yet written |
| `test-reviewer` | agent | Review tests against test automation standards (independence, coverage, setup/teardown, repeatability) | `change-scope` | not yet written |
| `mutation-tester` | agent | Run the project's mutation tool over changed + impacted code; per-test quality report | `change-scope`, `impact-analysis` | not yet written |
| `review-report` | skill + command | Orchestrate modules, merge into one ranked report, suggest fixes, offer to apply | all above | not yet written |

Build order: `change-scope` → `impact-analysis`, `complexity-review`, `test-reviewer` (parallel) → `mutation-tester` → `review-report`

## Deferred to v2

Recorded from the original notes; not in v1 scope.

| Candidate module id | Responsibility |
|---|---|
| `performance-review` | Has performance been checked? |
| `security-review` | Is security intact? |
| `standards-audit` | Standards and compliance checks |
