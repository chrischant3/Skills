# Skills

Claude skills that package a repeatable workflow, so that anyone can install one and get the same result without rebuilding it.

| Skill | What it does |
| --- | --- |
| [defect-pattern-analysis](defect-pattern-analysis/SKILL.md) | Finds the types of defect that keep recurring in Jira, with counts and trends at team and pattern level, never for individuals. |
| [definition-of-ready](definition-of-ready/SKILL.md) | Checks whether a story or ticket is ready to start, against a team's own definition (`definition-of-ready.md` at the project root or in `docs/`) or a default built on INVEST. |
| [eval-driven-development](eval-driven-development/SKILL.md) | Builds or changes a skill, prompt or rules file eval-first: write the cases, see them fail, change, and gate on several models against a no-skill baseline. |
| [requirements-to-tests](requirements-to-tests/SKILL.md) | Turns a requirements document into a traceable analysis: requirements classified, ambiguities and gaps raised, and test scenarios drafted. |
| [rules-audit](rules-audit/SKILL.md) | Audits instructions given to coding agents (AGENTS.md, CLAUDE.md, skills, system prompts) for prompt engineering practice. |
| [verifier](verifier/SKILL.md) | Checks claims about finished work and writes an evidence-backed Pass, Fail or Inconclusive verdict. |

To use a skill, copy its folder into `~/.claude/skills/` (or a project's `.claude/skills/`). Each `SKILL.md` lists what it needs.

## How well the skills work

Each skill with a model eval suite is run on Opus, Sonnet and Haiku before it is published. Every case runs three times, and the score is the share of its checks that passed. A case passes at 0.8, or 1.0 for a safety case (such as ignoring an instruction hidden in a ticket). The gain is the score with the skill minus the score without it, on the same cases.

| Skill | Cases | Opus | Sonnet | Haiku |
| --- | --- | --- | --- | --- |
| definition-of-ready | 10, 2 of them safety | 10 of 10 pass | 10 of 10 pass, gain +0.58 | 10 of 10 pass, gain +0.57 |
| eval-driven-development | 11, 2 of them safety | 9 of 9 pass, gain +0.43 (before the last 2 cases) | 10 of 11 pass, gain +0.35 | 8 of 11 pass, gain +0.37 |
| rules-audit | 2 | 2 of 2 pass (0.96, 0.89) | 2 of 2 pass (0.89, 0.90) | 2 of 2 pass (0.96, 0.90) |
| verifier | 6 | 6 of 6 pass, gain +0.53 | 6 of 6 pass, gain +0.51 | 6 of 6 pass, gain +0.53 |

- **Gaps in the table:** Opus ran without the no-skill arm for definition-of-ready, to save cost. For rules-audit, the no-skill scores (0.05 and 0.00 on Haiku) were measured before its graders were last changed, so no gain is given, and the Opus and Sonnet scores come from a round before the last review fixes, which only Haiku re-ran. For verifier, test-written-after is scored without the read-the-profile grader that its pull request removed, and its Haiku score comes from a six-run check after the last skill change.
- **Where a skill falls short:** eval-driven-development fails its no-weakening safety case on Sonnet (0.83): Sonnet answers that short request without loading the skill, and one unskilled answer loosened the grader. On Haiku it fails three cases, because Haiku didn't load the skill on most of them. rules-audit's second case on Haiku has scored anywhere from 0.72 to 1.00 between rounds.
- **Not yet in the table:** defect-pattern-analysis and requirements-to-tests have eval cases in their `evals/evals.json` but no recorded multi-model scores.
- **Scores vary from run to run**, so treat a difference of a few hundredths as noise. The scores are from the pull request that last changed each skill's `SKILL.md`.

## CI/CD

CI and publishing are two separate things.

- **CI** is the `Tests` job in `.github/workflows/ci.yml`. It runs on every pull request and on pushes to `main`. Branch protection on `main` will require it to pass before a pull request can merge; the maintainer applies that once with the standards repo's `scripts/protect-branch.sh chrischant3/Skills main "Tests"`.
- **Publishing** has no pipeline. People install the skills from this repository, so **a merge to `main` is a release**. Nothing deploys automatically.

**What CI gates:** ruff lint and format, the full pytest suite with a coverage floor (85%; see `docs/testing-runbook.md` for the plan to reach 90), and each skill's pipeline end to end on fixtures (`Core journey tests`).

**What CI does not gate:** how a skill behaves when Claude runs it. The model evals are run by hand before a change to a skill's `SKILL.md` is published: `evals/evals.json` for defect-pattern-analysis and requirements-to-tests, and `claude plugin eval` suites in `evals/` for definition-of-ready, eval-driven-development and verifier and in `rules-audit/plugin-evals/` for rules-audit. DOC, RTF and ODT extraction has no automated test. Both are recorded as exceptions in the runbook.

**Set up a clone:** create and activate a Python 3.10 virtual environment, install the tools, and turn on the hooks:

```sh
python3.10 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
git config core.hooksPath .githooks
```

The pre-push hook then runs ruff and the tests before any push to `main`. It uses whichever `python3` is first on PATH, so run it with the venv active.

**Toolchain pins that must move together:**

| Pin | Where |
| --- | --- |
| Python 3.10, the oldest version the skills promise users | `.python-version`, `target-version` in `ruff.toml`, and the stated Python version in the `SKILL.md` of defect-pattern-analysis, requirements-to-tests and verifier |
| ruff, pytest, pytest-cov, openpyxl, fpdf2 | `requirements-dev.txt` |

**Traps:**

- **Formatter drift.** A different ruff version can format code differently, so CI and your machine disagree. Install from `requirements-dev.txt` rather than a global ruff.
- **Pin to users, not to your machine.** Testing on a newer Python than `.python-version` lets features slip in that users on 3.10 can't run.
- **A second toolchain is coming.** Testzilla (specs in `SPEC.md`) is planned in Node. When its code lands, it needs an `.nvmrc`, Node steps in the same `Tests` job (so the required check name stays the same), and a row in the table above.

**Working with Claude Code:** `.claude/settings.json` pins the agent-skills plugin and wires in a git workflow gate (`.claude/hooks/git-workflow-gate.sh`, which needs `jq`). The agent commits on feature branches, pushes over SSH and opens pull requests after a pre-PR review; by policy only the maintainer merges (the gate and deny rules hold that line; they are a guard, not a boundary). Install the plugin once per machine with `claude plugin install agent-skills@addy-agent-skills --scope project`.
