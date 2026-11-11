# Project Instructions

## Problem Statement

This project builds AI skills that can be shared publicly. Each skill packages a repeatable workflow so that other people can install it and get the same result, without having to rebuild the workflow themselves.

Skills currently in this project:

- **Testzilla** (specs in `SPEC.md`, `SPEC-change-scope.md` and `CAPABILITY-MAP.md`): a code review Claude Code plugin that assesses complexity, reviews the tests' code, analyses a diff or PR, uncovers code that could be affected by the code changes, and assesses the test coverage of any impacted code.
- **requirements-to-tests** (`requirements-to-tests/`): reads a requirements document and produces a traceable analysis of requirements, ambiguities, missing requirements and test scenarios.
- **Exploratory Test Session Orchestrator** (`test-orchestrator/`, specs in `SPEC.md` and `CAPABILITY-MAP.md`): a test lead agent runs persona-driven exploratory testing sessions against a web app, an API or a requirement, independently verifies what the sessions find, and produces a consolidated report of confirmed defects, observations and unconfirmed findings.

## Primary Users

Members of the public who install the skills. For the current skills, that is software engineers and software testers.

## Success Criteria

A skill is working when someone other than its author can install it, invoke it, and get a useful result. For Testzilla, that result is a report on its findings, suggested resolutions, and an offer to resolve them.

## Technology Stack

Skills are language and framework agnostic.

## Anatomy of a Skill

We follow the example set by agent-skills. See `docs/skill-anatomy.md`.

Testzilla includes these agents:

- **Test Reviewer:** reviews the tests in a diff, PR, or repo, and reports anything that doesn't follow good test automation standards.
- **Mutation Tester:** runs mutation tests on a diff, PR, or repo, and produces a report on the quality of each test it reviewed.

## Deployment Target

Published on the Claude Code plugin marketplace and as a public GitHub repository.

## Additional Context

Follow the patterns and rules in <https://github.com/addyosmani/agent-skills/>. The agent-skills plugin is being used to develop these skills, and this project should be easy to understand for anyone who uses agent-skills.

Because the skills are shared publicly, they must not contain secrets, personal data, or anything specific to the author's own business.

## Development Lifecycle

Follow this process when developing in this project, loading the specified skills for each step.

  1. Define: spec-driven-development
  2. Plan: planning-and-task-breakdown
  3. Build: incremental-implementation + test-driven-development, plus eval-driven-development when the change affects how a model behaves (a skill, prompt or rules file)
  4. Verify: test-driven-development, plus eval-driven-development for model behaviour, plus browser-testing-with-devtools when the change has a web UI
  5. Review before merging: code-review-and-quality + code-simplification + security-and-hardening + performance-optimization
  6. Ship: shipping-and-launch

## Signing Commits

Only the project owner signs commits, in their own terminal. Agents commit with `git commit --no-gpg-sign` and never load the signing key into `ssh-agent` or save its passphrase.

Sign only the newest commit on a branch, once per pull request:

```bash
git commit --amend -S --no-edit && git log -1 --format='%G? %GK'
```

The output should be `G` followed by the signing key's fingerprint. One signature is enough because each commit records the ID of the one before it, so a signature on the newest commit covers every earlier commit on the branch. Nothing in this repository checks signatures on individual commits.

After signing, and before pushing, check that only the signature changed: the newest commit's files and parent must match the unsigned version.
