#!/usr/bin/env bash
# Copies this case's fixture into the agent's working directory, which is
# the directory the eval runner starts this script in.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -R "$here/version-b" "./version-b"
