#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# bump_version.sh - bump the semver in pyproject.toml and refresh uv.lock.
# Usage: scripts/bump_version.sh [patch|minor|major]   (default: patch)
# Policy: every commit bumps patch; a major feature bumps minor.
set -euo pipefail
cd "$(dirname "$0")/.."
part="${1:-patch}"
IFS=. read -r major minor patch <<<"$(scripts/version.sh)"
case "$part" in
    patch) patch=$((patch + 1)) ;;
    minor) minor=$((minor + 1)); patch=0 ;;
    major) major=$((major + 1)); minor=0; patch=0 ;;
    *) echo "usage: $0 [patch|minor|major]" >&2; exit 2 ;;
esac
new="$major.$minor.$patch"
sed -i "0,/^version = \".*\"$/s//version = \"$new\"/" pyproject.toml
uv lock -q
echo "$new"
