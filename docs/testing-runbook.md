# Testing runbook

How this repo is actually tested. Read it before testing, and update it when the tests or the way they run changes.

## Exceptions

Departures from the quality rules in the engineering standards. An undocumented gap is a defect; a documented one is a decision.

| Rule | Where | Why | What covers the risk instead | Revisit |
| --- | --- | --- | --- | --- |
| 10 (90% coverage) | The whole repo: 82.95% measured on 2026-11-11, gated at 82% in CI | CI arrived after the code | Every script not listed in the next rows is at 80% or more | Raise `--cov-fail-under` each time a file below gains tests; aim for 90 |
| 10 | `defect-pattern-analysis/scripts/szz.py` (0%) | No tests exist; it shells out to `git blame` on cloned repos | Nothing automated. Its output is labelled an estimate in the report. Accepted | Before the next behaviour change to `szz.py` |
| 10 | `requirements-to-tests/evals/grade.py` (0%), `requirements-to-tests/evals/make_fixtures.py` (54%) | Eval tooling, run by hand, not shipped to users | Nothing automated for `grade.py`; `make_fixtures.py` is partly covered by `tests/test_make_fixtures.py`. Accepted | When the evals run in CI |
| 10 | `verifier/scripts/check_verdict.py` (0% measured) | Its tests run it as a subprocess, which coverage doesn't follow by default | `verifier/tests/test_check_verdict.py` exercises it end to end | Turn on coverage's subprocess patching, then raise the floor |
| 10 | `defect-pattern-analysis/scripts/rest_transport.py` (56%) | Thin HTTP wrapper; the untested lines are the live network calls | Callers are tested with fake transports. Accepted | When the wrapper grows logic of its own |
| 11 (E2E on the real stack) | Each skill as Claude runs it | A skill's real journey is a model invoking it. Those runs are non-deterministic and cost money, so they can't run on every PR | Each skill's deterministic pipeline runs on fixtures in CI (core journeys below). The model evals are run by hand before a change to that skill's `SKILL.md` is published: `evals/evals.json` for defect-pattern-analysis and requirements-to-tests, `rules-audit/plugin-evals/` for rules-audit, `evals/verifier--*` for verifier (see Running the model evals) | When a cheap, repeatable way to run model evals in CI exists |
| 11 | DOC, RTF, ODT and CSV input to `requirements-to-tests/scripts/extract.py` | DOC/RTF/ODT go through macOS `textutil`; CSV has no test yet | Nothing automated. For DOC/RTF/ODT the error tells the user to save as .docx or .pdf. Accepted | Add an RTF test (skipped without `textutil`) and a CSV test |

## Core user journeys

Each skill's deterministic pipeline, run on synthetic fixtures. No test calls a live API.

| Journey | Test | Runs in CI |
| --- | --- | --- |
| Defect pattern analysis: raw Jira fixtures through to suppressed counts (phases 1–3, no SCM linking) | `defect-pattern-analysis/tests/test_pipeline.py` | Yes, `Core journey tests` step |
| Requirements to tests: extract a PDF, DOCX, XLSX or text document, then build the traceable outputs | `requirements-to-tests/tests/test_extract.py`, `requirements-to-tests/tests/test_build_outputs.py` | Yes, `Core journey tests` step |
| Verifier: check a verdict file against the format | `verifier/tests/test_check_verdict.py` | Yes, `Core journey tests` step |

SCM linking in defect-pattern-analysis is covered by its unit tests (`test_link_scm.py`, `test_scm_*.py`), not by a journey. `rules-audit` is Markdown only. `rules-audit/tests/test_skill_package.py` checks in CI that the files an agent loads are well formed: links resolve, code fences close, rubric IDs exist, tables are not ragged. Its behaviour is covered by its model evals (see Exceptions).

## Running the suite

**Prerequisites:** a Python 3.10 virtual environment, activated (`python3.10 -m venv .venv && . .venv/bin/activate`), then `pip install -r requirements-dev.txt`, and poppler's `pdftotext` on PATH (`brew install poppler` or `apt-get install poppler-utils`). Without `pdftotext` or `fpdf2` the PDF tests are skipped, not failed.

**Unit tests:** `python -m pytest` — expected: about 1090 passed, exit 0.

**Coverage:** `python -m pytest --cov=defect-pattern-analysis/scripts --cov=requirements-to-tests/scripts --cov=requirements-to-tests/evals --cov=verifier/scripts --cov-report=term-missing --cov-fail-under=82` — expected: 82.95% or more, exit 0.

**Core journeys:** `python -m pytest defect-pattern-analysis/tests/test_pipeline.py requirements-to-tests/tests/test_extract.py requirements-to-tests/tests/test_build_outputs.py verifier/tests/test_check_verdict.py` — expected: 106 passed, exit 0.

**Lint and format:** `ruff check . && ruff format --check .` — expected: no errors, exit 0.

## Running the model evals

Each model eval run is a full Claude session on your own account, so it costs money and its scores vary from run to run. Run them before publishing a change to a skill's `SKILL.md`, not on every change.

**rules-audit:** from `rules-audit/`, run `claude plugin eval . --eval-dir plugin-evals --model haiku --scaffold --max-cost-usd 2`. Expected: a report with a score for each of the two cases, exit 0 or 1 (exit 1 means a case scored below 1.0, which is normal). `--scaffold` is required: each case's `scaffold.sh` copies its fixture into the agent's working folder, and without it the agent can't find the file it is asked to audit. Iterate on Haiku; use Sonnet or Opus for a final confirming run. Reports go to `plugin-evals/results/` (git-ignored); keep any you want in `reports-local/` (also git-ignored).

**verifier:** from the repository root, run `claude plugin eval . --tag verifier --threshold 0.8 --model sonnet --scaffold --allow-tools Bash Write --max-cost-usd 5`. Expected: a score for each of the six cases, exit 0 when every case scores 0.8 or more. `--allow-tools Bash Write` is required, because the verifier runs the code under review and writes a verdict file. `--scaffold` builds each case's small git repo in the agent's working folder; each scaffold also writes `git-history.txt`, because `git` does not run inside the eval sandbox on macOS. A full Sonnet run costs about $3.50; iterate on Haiku (`--model haiku`, about $0.30). Reports go to `evals/results/` (git-ignored); keep any you want in `verifier/reports-local/` (also git-ignored).
