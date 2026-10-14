# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# screenshots.py - regenerate the real UI screenshots used in README.md: the dashboard,
# the blink-test detail page (headless Chromium against a live server) and a game frame
# from the blink-test replay.
# Usage: uv run python scripts/screenshots.py [OUT_DIR]   (default docs/media)
"""Capture README screenshots from the running application."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import uvicorn
from playwright.sync_api import sync_playwright

from ntxbci.web import create_app


def _serve() -> tuple[str, uvicorn.Server]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(), port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            httpx.get(f"{url}/healthz")
            break
        except httpx.TransportError:
            time.sleep(0.1)
    return url, server


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    url, server = _serve()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 860}, device_scale_factor=1)
        page.goto(url)
        page.screenshot(path=str(out_dir / "dashboard.png"), full_page=True)
        page.goto(f"{url}/recordings/blink-test")
        page.wait_for_function("[...document.images].every(i => i.complete && i.naturalWidth > 0)")
        page.screenshot(path=str(out_dir / "blink-test.png"), full_page=True)
        browser.close()
    server.should_exit = True
    env = {**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}
    subprocess.run(
        [
            sys.executable,
            "-m",
            "ntxbci.cli",
            "replay",
            "blink-test",
            "--headless",
            "--screenshot",
            str(out_dir / "game-replay.png"),
        ],
        check=True,
        env=env,
        stdout=subprocess.DEVNULL,
    )
    for name in ("dashboard.png", "blink-test.png", "game-replay.png"):
        print(out_dir / name)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/media"))
