#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# localPipeline.sh - the single quality gate for this repository.
# GitHub Actions runs exactly this script, so "green locally" == "green in CI".
#
# Usage: ./localPipeline.sh [--fast] [--no-docker] [--report-dir DIR]
#   --fast        skip e2e tests and docker stages (quick inner loop)
#   --no-docker   skip docker build + smoke test
#   --report-dir  keep stage logs, junit.xml and coverage.xml in DIR
#
# Stages: sync, format, lint, typecheck, headers, scripts-doc, tests (unit +
# integration, coverage >= 95 %), e2e, build, wheel smoke, docker build, docker smoke.
# Exit code is non-zero if any stage fails; a summary is printed at the end.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

FAST=0
DOCKER=1
REPORT_DIR=""
while (($#)); do
    case "$1" in
        --fast) FAST=1; DOCKER=0 ;;
        --no-docker) DOCKER=0 ;;
        --report-dir) REPORT_DIR="$2"; shift ;;
        -h|--help) sed -n '4,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

LOG_DIR="${REPORT_DIR:-$(mktemp -d)}"
mkdir -p "$LOG_DIR"
declare -a SUMMARY=()
FAILED=0

stage() {
    local name="$1"; shift
    local log="$LOG_DIR/${name}.log"
    local start=$SECONDS
    printf '==> %-14s ' "$name"
    if "$@" >"$log" 2>&1; then
        printf 'ok   (%ss)\n' $((SECONDS - start))
        SUMMARY+=("ok    $name")
    else
        printf 'FAIL (%ss)\n' $((SECONDS - start))
        tail -n 40 "$log" | sed 's/^/    | /'
        SUMMARY+=("FAIL  $name   (log: $log)")
        FAILED=1
    fi
}

skip() { printf '==> %-14s skipped\n' "$1"; SUMMARY+=("skip  $1"); }

export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy MPLBACKEND=Agg

stage sync        uv sync --frozen --all-extras
stage format      uv run ruff format --check .
stage lint        uv run ruff check .
stage typecheck   uv run mypy
stage headers     scripts/check_headers.sh
stage scripts-doc scripts/check_script_docs.sh
stage tests       uv run pytest -m "not e2e" --cov --cov-report=term \
                      --cov-report="xml:$LOG_DIR/coverage.xml" --junitxml="$LOG_DIR/junit.xml"
if ((FAST)); then
    skip e2e
else
    stage e2e     scripts/run_e2e.sh
fi
stage build       scripts/build_dist.sh
stage wheel-smoke scripts/wheel_smoke.sh
if ((DOCKER)); then
    stage docker-build scripts/docker_build.sh
    stage docker-smoke scripts/docker_smoke.sh
else
    skip docker-build
    skip docker-smoke
fi

echo
echo "Summary (logs in $LOG_DIR):"
printf '  %s\n' "${SUMMARY[@]}"
if ((FAILED)); then echo "PIPELINE FAILED"; exit 1; fi
echo "PIPELINE GREEN"
