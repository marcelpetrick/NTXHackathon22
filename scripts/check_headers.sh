#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# check_headers.sh - verify every tracked/new source file carries an SPDX license header.
# Checks *.py and *.sh files (plus Dockerfile) outside third-party folders.
# Usage: scripts/check_headers.sh        exit 1 and list offenders if any are missing
set -euo pipefail
cd "$(dirname "$0")/.."
missing=0
while IFS= read -r f; do
    [[ -f "$f" ]] || continue
    if ! head -n 5 "$f" | grep -q 'SPDX-License-Identifier:'; then
        echo "missing SPDX header: $f"
        missing=1
    fi
done < <(git ls-files --cached --others --exclude-standard -- '*.py' '*.sh' 'Dockerfile' ':!pacman')
exit "$missing"
