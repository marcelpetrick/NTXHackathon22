#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# docker_smoke.sh - start ntxbci:local, wait for /healthz, check the dashboard and API
# respond and run the blink-test replay check inside the image; always removes the
# container. Exit 0 while no Dockerfile exists yet.
# Usage: scripts/docker_smoke.sh [image]   (default ntxbci:local)
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f Dockerfile ]] || { echo "no Dockerfile yet"; exit 0; }
image="${1:-ntxbci:local}"
name="ntxbci-smoke-$$"
cid="$(docker run -d --rm --name "$name" -p 127.0.0.1::8000 "$image")"
trap 'docker rm -f "$cid" >/dev/null 2>&1 || true' EXIT
port="$(docker port "$cid" 8000/tcp | head -n1 | sed 's/.*://')"
for _ in $(seq 1 60); do
    curl -fsS "http://127.0.0.1:$port/healthz" >/dev/null 2>&1 && break
    sleep 0.5
done
curl -fsS "http://127.0.0.1:$port/healthz"; echo
curl -fsS "http://127.0.0.1:$port/api/recordings" | head -c 300; echo
curl -fsS "http://127.0.0.1:$port/" | grep -q "NTX"
png="$(mktemp)"
curl -fsS -o "$png" "http://127.0.0.1:$port/plots/blink-test/traces.png"
[[ "$(head -c 4 "$png" | tail -c 3)" == "PNG" ]]
docker run --rm "$image" ntxbci replay blink-test | tail -n 1 | grep -qx PASS
echo "docker smoke ok"
