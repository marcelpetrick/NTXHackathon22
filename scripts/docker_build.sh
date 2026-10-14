#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# docker_build.sh - build the docker image as ntxbci:local (and ntxbci:<version>).
# Exit 0 without building while no Dockerfile exists yet.
# Usage: scripts/docker_build.sh
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f Dockerfile ]] || { echo "no Dockerfile yet"; exit 0; }
docker build -t ntxbci:local -t "ntxbci:$(scripts/version.sh)" .
