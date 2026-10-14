#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# check_script_docs.sh - every script in scripts/ must have a "# <name> - <purpose>"
# line in its header and be listed in scripts/README.md.
# Usage: scripts/check_script_docs.sh
set -euo pipefail
cd "$(dirname "$0")"
bad=0
for f in *.sh *.py; do
    [[ -f "$f" ]] || continue
    if ! head -n 8 "$f" | grep -q "^# $f - "; then echo "no purpose line: scripts/$f"; bad=1; fi
    if ! grep -q "\`$f\`" README.md; then echo "not documented in scripts/README.md: $f"; bad=1; fi
done
exit "$bad"
