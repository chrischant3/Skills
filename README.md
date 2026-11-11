# Skills

Claude skills that package a repeatable workflow, so that anyone can install one and get the same result without rebuilding it.

| Skill | What it does |
| --- | --- |
| [defect-pattern-analysis](defect-pattern-analysis/SKILL.md) | Finds the types of defect that keep recurring in Jira, with counts and trends at team and pattern level, never for individuals. |
| [requirements-to-tests](requirements-to-tests/SKILL.md) | Turns a requirements document into a traceable analysis: requirements classified, ambiguities and gaps raised, and test scenarios drafted. |
| [rules-audit](rules-audit/SKILL.md) | Audits instructions given to coding agents (AGENTS.md, CLAUDE.md, skills, system prompts) for prompt engineering practice. |
| [verifier](verifier/SKILL.md) | Checks claims about finished work and writes an evidence-backed Pass, Fail or Inconclusive verdict. |

To use a skill, copy its folder into `~/.claude/skills/` (or a project's `.claude/skills/`). Each `SKILL.md` lists what it needs.

## CI/CD

CI and publishing are two separate things.

- **CI** is the `Tests` job in `.github/workflows/ci.yml`. It runs on every pull request and on pushes to `main`. Branch protection on `main` requires it to pass before a pull request can merge.
- **Publishing** has no pipeline. People install the skills from this repository, so **a merge to `main` is a release**. Nothing deploys automatically.

**What CI gates:** ruff lint and format, the full pytest suite with a coverage floor (82%; see `docs/testing-runbook.md` for the plan to reach 90), and each skill's pipeline end to end on fixtures (`Core journey tests`).

**What CI does not gate:** how a skill behaves when Claude runs it. Those model evals (`*/evals/evals.json`) are run by hand before a change to a skill's `SKILL.md` is published. DOC, RTF and ODT extraction is only tested on a Mac. Both are recorded as exceptions in the runbook.

**Before pushing to `main`:** run `git config core.hooksPath .githooks` once per clone. The pre-push hook then runs ruff and the tests before any push to `main`.

**Toolchain pins that must move together:**

| Pin | Where |
| --- | --- |
| Python 3.10, the oldest version the skills promise users | `.python-version`, `target-version` in `ruff.toml`, and the "3.10 or later" line in the `SKILL.md` of defect-pattern-analysis, requirements-to-tests and verifier |
| ruff, pytest, pytest-cov, openpyxl, fpdf2 | `requirements-dev.txt` |

**Traps:**

- **Formatter drift.** A different ruff version can format code differently, so CI and your machine disagree. Install from `requirements-dev.txt` rather than a global ruff.
- **Pin to users, not to your machine.** Testing on a newer Python than `.python-version` lets features slip in that users on 3.10 can't run.
- **A second toolchain is coming.** Testzilla (specs in `SPEC.md`) is planned in Node. When its code lands, it needs an `.nvmrc`, Node steps in the same `Tests` job (so the required check name stays the same), and a row in the table above.

**Working with Claude Code:** `.claude/settings.json` pins the agent-skills plugin and wires in a git workflow gate (`.claude/hooks/git-workflow-gate.sh`, which needs `jq`). The agent commits on feature branches, pushes over SSH and opens pull requests after a pre-PR review; only the maintainer merges. Install the plugin once per machine with `claude plugin install agent-skills@addy-agent-skills --scope project`.
