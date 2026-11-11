# Project Instructions

## Problem Statement
This project builds AI skills that can be shared publicly. Each skill packages a repeatable workflow so that other people can install it and get the same result, without having to rebuild the workflow themselves.

Skills currently in this project:
- **Testzilla** (specs in `SPEC.md`, `SPEC-change-scope.md` and `CAPABILITY-MAP.md`): a code review Claude Code plugin that assesses complexity, reviews the tests' code, analyses a diff or PR, uncovers code that could be affected by the code changes, and assesses the test coverage of any impacted code.
- **requirements-to-tests** (`requirements-to-tests/`): reads a requirements document and produces a traceable analysis of requirements, ambiguities, missing requirements and test scenarios.

## Primary Users
Members of the public who install the skills. For the current skills, that is software engineers and software testers.

## Success Criteria
A skill is working when someone other than its author can install it, invoke it, and get a useful result. For Testzilla, that result is a report on its findings, suggested resolutions, and an offer to resolve them.

## Technology Stack
Skills are language and framework agnostic.

Testzilla includes these agents:
- **Test Reviewer:** reviews the tests in a diff, PR, or repo, and reports anything that doesn't follow good test automation standards.
- **Mutation Tester:** runs mutation tests on a diff, PR, or repo, and produces a report on the quality of each test it reviewed.

## Deployment Target
Published on the Claude Code plugin marketplace and as a public GitHub repository.

## Additional Context
Follow the patterns and rules in https://github.com/addyosmani/agent-skills/. The agent-skills plugin is being used to develop these skills, and this project should be easy to understand for anyone who uses agent-skills.

Because the skills are shared publicly, they must not contain secrets, personal data, or anything specific to the author's own business.
