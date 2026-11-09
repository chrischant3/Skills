# Implementation Plan: change-scope (Testzilla)

Specs: [SPEC.md](../SPEC.md), [SPEC-change-scope.md](../SPEC-change-scope.md) · Map: [CAPABILITY-MAP.md](../CAPABILITY-MAP.md)

## Overview

Build the `change-scope` module — the change-set contract every other Testzilla module consumes — plus the minimum repo scaffolding needed for a valid, CI-verified plugin. Work is sliced by **target kind**: each slice takes one user-facing target (working tree, range/branch, whole repo, PR) all the way from CLI invocation to change-set JSON, so every task ends with something runnable.

## Architecture Decisions

- **One Node script, pure core.** `change-set.js` exposes pure functions (`parseUnifiedDiff`, `classifyRole`, `detectLanguage`, `buildChangeSet`) with a thin CLI shell that performs the `git`/`gh` calls. Pure core is unit-testable without a repo; the shell is exercised by integration tests against temp repos.
- **Node 24, no dependencies.** Matches agent-skills; avoids a supply chain for a plugin people install from a marketplace.
- **Contract before consumers.** The JSON shape in SPEC-change-scope.md is frozen once `impact-analysis` starts consuming it; only additive changes after that.
- **Scaffolding first, minimally.** Only what CI needs to prove a valid plugin: manifests, licence, a skill validator, unit test wiring. The full three-tier eval harness is a separate decision (see Open Questions).
- **Read-only git.** No command that mutates the working tree, refs, or remote state, in any slice.

## Dependency Graph

```
Task 1 (manifests, licence, README)
    └── Task 2 (CI: validate + node --test)
            └── Task 3 (parseUnifiedDiff)
                    └── Task 4 (classifyRole / detectLanguage / skip rules)
                            └── Task 5 (buildChangeSet + CLI: working-tree target)
                                    ├── Task 6 (range + branch targets)
                                    │       └── Task 8 (PR target, needs base-ref resolution from 6)
                                    ├── Task 7 (--repo target)
                                    └── Task 9 (guardrails: size threshold, errors)
                                            └── Task 10 (SKILL.md)
                                                    └── Task 11 (eval case)
```

## Task List

### Phase 1: Foundation
- [ ] Task 1: Plugin manifests, MIT licence, README skeleton
- [ ] Task 2: CI workflow running skill validation and unit tests

### Checkpoint: Foundation
- [ ] `claude plugin validate .` passes
- [ ] `node --test` runs (even with zero tests) and CI is green
- [ ] Plugin installs locally from `./` as a marketplace

### Phase 2: change-scope core
- [ ] Task 3: `parseUnifiedDiff` — unified diff → files + hunks
- [ ] Task 4: File classification — role, language, skip rules
- [ ] Task 5: `buildChangeSet` + CLI for the working-tree target

### Checkpoint: Core
- [ ] `node skills/change-scope/scripts/change-set.js` in a dirty repo prints a valid change set
- [ ] Unit + integration tests pass
- [ ] Review the JSON contract against SPEC-change-scope.md before consumers exist

### Phase 3: Remaining targets
- [ ] Task 6: Range and branch targets with default-branch detection
- [ ] Task 7: `--repo` target
- [ ] Task 8: PR target via `gh`

### Checkpoint: Targets
- [ ] Every target kind in the spec produces a change set or a specific error
- [ ] Branch target and its equivalent explicit range produce identical output

### Phase 4: Surface and verification
- [ ] Task 9: Guardrails — size threshold, error handling, untracked count
- [ ] Task 10: `skills/change-scope/SKILL.md`
- [ ] Task 11: `evals/cases/change-scope.json`

### Checkpoint: Complete
- [ ] All SPEC-change-scope.md success criteria met
- [ ] CI green
- [ ] Human review before `impact-analysis` starts consuming the contract

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Diff parsing edge cases (renames, binary files, no-newline-at-EOF, CRLF) silently corrupt scope | High | Task 3 is TDD with a fixture per edge case before the CLI exists |
| The change-set contract changes after consumers depend on it | High | Checkpoint review at end of Phase 2; additive-only afterwards |
| Test-file heuristics misclassify in unfamiliar ecosystems | Medium | Single extensible table; `role` reported in output so users can spot errors; fixtures in 3+ languages |
| `gh` absent, unauthenticated, or its output format shifts | Medium | Capture `gh` output as fixtures; treat live `gh` as optional in CI; fail with actionable message |
| Building our own eval harness is a large hidden project | Medium | Raised as an open question before Task 11 rather than discovered mid-build |
| Whole-repo target on a large repo produces an unusable change set | Low | Task 9 size threshold asks before proceeding |

## Open Questions

1. **Eval harness.** agent-skills' `run-evals.js` and validators are MIT-licensed. Do we (a) port them with attribution, (b) write our own minimal validator now and defer routing/behavioral evals, or (c) skip evals in v1? This affects Tasks 2 and 11. Proposal: (b).
2. **Fixture languages.** SPEC.md proposes JS/TS, Python, and Java or Go. Confirm the third.
3. **CI on a public repo.** Do behavioral evals (which spend tokens) ever run in CI, or stay local-only?
