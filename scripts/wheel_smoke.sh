#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# wheel_smoke.sh - install the built wheel into a throw-away venv and check that the
# CLI starts and reports the version from pyproject.toml.
# Usage: scripts/wheel_smoke.sh   (run scripts/build_dist.sh first)
set -euo pipefail
cd "$(dirname "$0")/.."
venv="$(mktemp -d)/venv"
uv venv -q "$venv"
uv pip install -q --python "$venv/bin/python" dist/*.whl
expected="$(scripts/version.sh)"
actual="$("$venv/bin/ntxbci" --version)"
echo "$actual"
[[ "$actual" == "ntxbci $expected" ]]
