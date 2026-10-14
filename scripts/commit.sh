#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# commit.sh - the commit workflow: bump version, run the full pipeline, commit with a
# conventional message and push. Aborts (nothing committed) if red; rerunning after a fix
# does not bump a second time.
# Usage: scripts/commit.sh [patch|minor] "type(scope): message" [--fast] [-- NEW_PATH...]
#   --fast     run ./localPipeline.sh --fast (only for docs-only changes)
#   NEW_PATH   untracked files/dirs that belong to this commit; tracked changes are always
#              staged. Any other untracked file aborts the commit, so stray artefacts can
#              never sneak into an "atomic" commit.
set -euo pipefail
cd "$(dirname "$0")/.."
part="$1"; msg="$2"; shift 2
pipeline_args=()
while (($#)) && [[ "$1" != "--" ]]; do pipeline_args+=("$1"); shift; done
[[ "${1:-}" == "--" ]] && shift
new_paths=("$@")

stray="$(git ls-files --others --exclude-standard)"
if ((${#new_paths[@]})); then
    claimed="$(git ls-files --others --exclude-standard -- "${new_paths[@]}")"
    stray="$(comm -23 <(sort <<<"$stray") <(sort <<<"$claimed"))"
fi
if [[ -n "$stray" ]]; then
    echo "untracked files not named after '--' (add them or gitignore them):" >&2
    sed 's/^/  /' <<<"$stray" >&2
    exit 1
fi

# bump only once per commit: a retry after a red pipeline keeps the already bumped version
if [[ "$(git show HEAD:pyproject.toml | sed -n 's/^version = "\(.*\)"$/\1/p' | head -n1)" == "$(scripts/version.sh)" ]]; then
    new="$(scripts/bump_version.sh "$part")"
else
    new="$(scripts/version.sh)"
fi
if ! ./localPipeline.sh "${pipeline_args[@]}"; then
    echo "pipeline red - not committing (version left at $new in working tree)" >&2
    exit 1
fi
git add -u
((${#new_paths[@]})) && git add -- "${new_paths[@]}"
git commit -q -m "$msg" -m "Version: $new"
git push -q origin HEAD
git log --oneline -1
