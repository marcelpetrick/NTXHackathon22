# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""The installed entry point replays the real blink test end to end (incl. game window)."""

import json
import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def test_replay_entry_point(tmp_path: Path) -> None:
    shot = tmp_path / "replay.png"
    env = {**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}
    proc = subprocess.run(
        ["ntxbci", "replay", "blink-test", "--headless", "--screenshot", str(shot)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS" in proc.stdout
    assert "game over: won" in proc.stdout
    assert shot.stat().st_size > 1000
    report = json.loads(
        subprocess.run(
            ["ntxbci", "replay", "blink-test", "--json"],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        ).stdout
    )
    assert report["detection"]["f1"] == 1.0
