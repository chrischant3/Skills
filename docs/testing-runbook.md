# Testing runbook

How this repo is actually tested. Read it before testing, and update it when the tests or the way they run changes.

## Exceptions

Departures from the quality rules in the engineering standards. An undocumented gap is a defect; a documented one is a decision.

| Rule | Where | Why | What covers the risk instead | Revisit |
| --- | --- | --- | --- | --- |
| 10 (90% coverage) | The whole repo: 83% measured on 2026-11-11, gated at 82% in CI | CI arrived after the code. The biggest gaps are `defect-pattern-analysis/scripts/szz.py` (0%), `verifier/scripts/check_verdict.py` (0% measured: its tests run it as a subprocess, which coverage doesn't follow), `requirements-to-tests/evals/grade.py` (0%), `requirements-to-tests/evals/make_fixtures.py` (54%) and `defect-pattern-analysis/scripts/rest_transport.py` (56%) | Every other script is at 80% or more; `check_verdict.py` is exercised end to end by `verifier/tests/test_check_verdict.py` | Raise `--cov-fail-under` each time one of these files gains tests; aim for 90 |
| 11 (E2E on the real stack) | Each skill as Claude runs it (`*/evals/evals.json`) | A skill's real journey is a model invoking it. Those runs are non-deterministic and cost money, so they can't run on every PR | The deterministic pipeline of each skill runs end to end on fixtures in CI (core journeys below). Run the model evals by hand before publishing a change to a skill's `SKILL.md` | When a cheap, repeatable way to run model evals in CI exists |
| 11 (E2E) | DOC, RTF and ODT input to `requirements-to-tests/scripts/extract.py` | It converts these with macOS `textutil`, which the Linux CI runner doesn't have | PDF, xlsx, csv and text input are tested in CI; DOC/RTF/ODT are tested on a Mac | If extraction moves to a cross-platform converter |

## Core user journeys

Each skill's deterministic pipeline, run on synthetic fixtures. No test calls a live API.

| Journey | Test | Runs in CI |
| --- | --- | --- |
| Defect pattern analysis: Jira and SCM fixtures through to the golden outputs | `defect-pattern-analysis/tests/test_pipeline.py` | Yes, `Core journey tests` step |
| Requirements to tests: extract a document, then build the traceable outputs | `requirements-to-tests/tests/test_extract.py`, `requirements-to-tests/tests/test_build_outputs.py` | Yes, `Core journey tests` step |
| Verifier: check a verdict file against the format | `verifier/tests/test_check_verdict.py` | Yes, `Core journey tests` step |

`rules-audit` is Markdown only; its behaviour is covered by its model evals (see Exceptions).

## Running the suite

**Prerequisites:** Python 3.10 (`.python-version`), `pip install -r requirements-dev.txt`, and poppler's `pdftotext` on PATH (`brew install poppler` or `apt-get install poppler-utils`). Without `pdftotext` or `fpdf2` the PDF tests are skipped, not failed.

**Unit tests:** `python -m pytest` — expected: about 1076 passed, exit 0.

**Coverage:** `python -m pytest --cov=defect-pattern-analysis/scripts --cov=requirements-to-tests/scripts --cov=requirements-to-tests/evals --cov=verifier/scripts --cov-report=term-missing --cov-fail-under=82` — expected: 83% or more, exit 0.

**Core journeys:** `python -m pytest defect-pattern-analysis/tests/test_pipeline.py requirements-to-tests/tests/test_extract.py requirements-to-tests/tests/test_build_outputs.py verifier/tests/test_check_verdict.py` — expected: 106 passed, exit 0.

**Lint and format:** `ruff check . && ruff format --check .` — expected: no errors, exit 0.
