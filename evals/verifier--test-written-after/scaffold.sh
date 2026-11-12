#!/usr/bin/env bash
# Builds the repo under review in the agent's working directory, which is
# the directory the eval runner starts this script in: the base project as
# one commit, then the builder's implementation and, after it, the tests.
# Also places the builder's transcript beside the repo. Fixture Python files
# are stored as .py.txt so this repository's own pytest and ruff skip them.
# Needs --scaffold.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
place() { for f in "$1"/*; do n="$(basename "$f")"; cp "$f" "./${n%.txt}"; done; }
commit() {
  git -c user.name=builder -c user.email=builder@example.com \
    -c commit.gpgsign=false commit -q -m "$1"
}
git init -q -b main
place "$here/fixture/base"
git add -A && commit "Initial durations parser"
place "$here/fixture/change"
git add durations.py && commit "Add hours to parse_duration"
git add test_durations.py && commit "Add tests for hours"
cp "$here/fixture/builder-transcript.jsonl" .
# git may not run inside the eval sandbox (the macOS /usr/bin/git shim cannot
# write its cache there), so leave the history readable as a file too.
git log -p > git-history.txt
