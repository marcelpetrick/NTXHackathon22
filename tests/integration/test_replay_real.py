# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""The replay check on the real blink test is the end-to-end regression baseline."""

from pathlib import Path

from ntxbci.manifest import load_manifest
from ntxbci.replay import replay


def test_blink_test_replay_passes(real_root: Path) -> None:
    report = replay(load_manifest(real_root), "blink-test")
    assert report.passed, report.problems
    assert report.detection is not None
    assert report.detection.expected == report.detection.detected == 10
    assert report.game.blinks_applied == 10
    assert report.game.status == "won"  # the recorded blinks keep Pacman alive


def test_every_recording_replays_consistently(real_root: Path) -> None:
    m = load_manifest(real_root)
    for entry in m.entries:
        if entry.kind != "impedance":
            report = replay(m, entry.id)
            assert report.passed, (entry.id, report.problems)
