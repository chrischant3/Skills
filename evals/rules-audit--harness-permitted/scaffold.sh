#!/usr/bin/env bash
# Copies this case's fixture into the agent's working directory, which is
# the directory the eval runner starts this script in, and drops the
# .fixture suffix. The fixtures hold deliberately unsafe instructions, so
# they are stored as *.fixture: under their real names (AGENTS.md,
# CLAUDE.md, .claude/settings.json) an agent working in this repository
# would load them. Needs --scaffold.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -R "$here/fixture/." .
find . -name '*.fixture' -type f | while read -r f; do mv "$f" "${f%.fixture}"; done
