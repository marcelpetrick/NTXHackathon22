#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# commit.sh - the commit workflow: bump version, run the full pipeline, commit all
# changes with a conventional message and push. Aborts (nothing committed) if red;
# rerunning after a fix does not bump a second time.
# Usage: scripts/commit.sh [patch|minor] "type(scope): message" [--fast]
#   --fast  run ./localPipeline.sh --fast (only for docs-only changes)
set -euo pipefail
cd "$(dirname "$0")/.."
part="$1"; msg="$2"; shift 2
# bump only once per commit: a retry after a red pipeline keeps the already bumped version
if [[ "$(git show HEAD:pyproject.toml | sed -n 's/^version = "\(.*\)"$/\1/p' | head -n1)" == "$(scripts/version.sh)" ]]; then
    new="$(scripts/bump_version.sh "$part")"
else
    new="$(scripts/version.sh)"
fi
if ! ./localPipeline.sh "$@"; then
    echo "pipeline red - not committing (version left at $new in working tree)" >&2
    exit 1
fi
git add -A
git commit -q -m "$msg" -m "Version: $new"
git push -q origin HEAD
git log --oneline -1
