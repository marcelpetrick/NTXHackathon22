#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# version.sh - print the project version from pyproject.toml.
# Usage: scripts/version.sh
set -euo pipefail
cd "$(dirname "$0")/.."
sed -n 's/^version = "\(.*\)"$/\1/p' pyproject.toml | head -n 1
