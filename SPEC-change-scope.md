# Spec: change-scope

Module id: `change-scope` · Depends on: — · Status: draft — awaiting review

## Objective

Every other module needs the same answer first: *what changed?* `change-scope` turns a user's target into one normalized **change set** so impact-analysis, complexity-review, test-reviewer, and mutation-tester never parse diffs themselves or disagree about scope.

**Acceptance criteria**
- Given each supported target form, produces a change set matching the contract below.
- Classifies each file's role (source / test / config / docs / generated / binary) using language-agnostic heuristics.
- Refuses with a clear message — never guesses — when the target can't be resolved.

## Supported Targets

| Input | Resolution |
|---|---|
| *(empty)* | Staged + unstaged changes to tracked files vs `HEAD`. Untracked files are excluded, but counted in `summary.untracked_ignored` so the user knows |
| `<base>..<head>` / `<base>...<head>` | `git diff` with the given range semantics |
| `<branch>` | Diff from merge-base with the default branch to `<branch>` |
| PR number or URL | `gh pr diff` + `gh pr view` for base/head; if `gh` is missing or unauthenticated, stop and tell the user how to fix it |
| `--repo` | All tracked files, status `unchanged`, no hunks (whole-repo review) |

Default branch is detected from `origin/HEAD`, falling back to `main` then `master`; if none exist, ask.

## Change Set Contract

The provider contract that downstream modules depend on. Additive changes only once another module consumes it.

```json
{
  "target": { "kind": "working-tree|range|branch|pr|repo", "input": "feature/x", "base": "a1b2c3d", "head": "e4f5a6b" },
  "files": [
    {
      "path": "src/cart/total.py",
      "old_path": null,
      "status": "added|modified|deleted|renamed|unchanged",
      "role": "source|test|config|docs|generated|binary",
      "language": "python",
      "hunks": [{ "old_start": 10, "old_lines": 4, "new_start": 10, "new_lines": 9 }]
    }
  ],
  "skipped": [{ "path": "package-lock.json", "reason": "lockfile" }],
  "summary": { "files": 12, "source": 7, "test": 4, "other": 1, "lines_added": 240, "lines_removed": 31, "untracked_ignored": 2 }
}
```

- `language` from file extension map; `null` if unknown (never blocks).
- `role: test` heuristics: path segments `test`, `tests`, `__tests__`, `spec`; names `*_test.*`, `test_*.*`, `*.test.*`, `*.spec.*`, `*Test.*`, `*Tests.*`. Heuristics live in one table so they're easy to extend.
- `skipped`: lockfiles, vendored dirs (`vendor/`, `node_modules/`, `third_party/`), generated markers, binaries.

## Implementation Shape

- `skills/change-scope/SKILL.md` — when/how to resolve a target; how to present scope to the user.
- `skills/change-scope/scripts/change-set.js` — Node 24, no deps. Pure functions (`parseUnifiedDiff`, `classifyRole`, `detectLanguage`) plus a CLI that shells to `git`/`gh` and prints the JSON.

## Commands

```
node skills/change-scope/scripts/change-set.js [target]     # prints change set JSON
node --test skills/change-scope/scripts/change-set.test.js
```

## Testing Strategy

- **Unit (`node --test`):** diff parsing (add/modify/delete/rename, multiple hunks, no-newline-at-EOF, binary markers), role classification table, language detection.
- **Integration:** each test builds a throwaway git repo in a temp dir and exercises every target kind except PR; PR resolution is tested with `gh` output captured as fixtures.
- **Evals:** `evals/cases/change-scope.json` — ≥3 positive, ≥2 negative triggers, 1 behavioral eval.

## Boundaries

- **Always:** Read-only git operations only. Report `skipped` files and why.
- **Ask first:** Targets over 200 changed files or 5,000 changed lines — offer to narrow scope before continuing.
- **Never:** `git checkout`, `stash`, `fetch`, or anything that alters the working tree or refs. If a PR's base ref isn't available locally, stop and tell the user to fetch it.

## Success Criteria

1. Unit + integration tests pass for every target kind.
2. The same change set is produced for equivalent inputs (e.g. branch name vs explicit merge-base range).
3. Missing `gh`, unknown ref, or non-git directory each yield a specific actionable error, exit non-zero, and no partial JSON.

## Resolved Decisions

- Tracked files only; untracked files are never reviewed, only counted.
- Never `git fetch` — an unavailable base ref is an error with instructions.

## Open Questions

None blocking.
