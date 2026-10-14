#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# run_e2e.sh - run the end-to-end tests (pytest -m e2e). Installs the Playwright
# Chromium browser on first use. Exit 0 if there are no e2e tests yet.
# Usage: scripts/run_e2e.sh
set -euo pipefail
cd "$(dirname "$0")/.."
if uv run python -c "import playwright" 2>/dev/null; then
    uv run playwright install chromium >/dev/null
fi
set +e
uv run pytest -m e2e -p no:cacheprovider
rc=$?
set -e
# pytest exit code 5 == no tests collected
if [[ $rc -eq 5 ]]; then echo "no e2e tests collected"; exit 0; fi
exit "$rc"
