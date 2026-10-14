#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# build_dist.sh - build sdist and wheel into dist/ (cleaned first).
# Usage: scripts/build_dist.sh
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf dist
uv build
