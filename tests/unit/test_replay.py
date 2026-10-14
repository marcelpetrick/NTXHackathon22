# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import json
from pathlib import Path

import pytest

from ntxbci import replay
from ntxbci.events import BlinkParams
from ntxbci.game.model import GameState, LogEntry
from ntxbci.manifest import load_manifest


def test_replay_passes_on_synthetic_blink_test(mini_dataset: Path) -> None:
    report = replay.replay(load_manifest(mini_dataset), "blink")
    assert report.passed, report.problems
    assert report.detection is not None
    assert report.detection.f1 == 1.0
    assert report.game.turns == report.game.blinks_applied == 3
    assert report.deterministic
    data = report.to_dict()
    assert data["passed"] is True
    json.dumps(data)


def test_replay_without_ground_truth(mini_dataset: Path) -> None:
    report = replay.replay(load_manifest(mini_dataset), "s1")
    assert report.detection is None
    assert report.blinks_s == ()
    assert report.passed


def test_replay_fails_when_detector_is_too_strict(mini_dataset: Path) -> None:
    report = replay.replay(
        load_manifest(mini_dataset), "blink", params=BlinkParams(threshold_z=1e6)
    )
    assert not report.passed
    assert "F1 0.000 below" in report.problems[0]


def test_replay_rejects_impedance(mini_dataset: Path) -> None:
    with pytest.raises(ValueError, match="impedance"):
        replay.replay(load_manifest(mini_dataset), "imp-s1")


def test_reaction_check_reports_mismatch_and_late_blinks() -> None:
    state = GameState()
    state.time_s = 2.0
    state.log.append(LogEntry(0.5, "turn:left", 10))
    problems, applied, after = replay._check_reactions([1.0, 5.0], state)
    assert applied == 1
    assert after == 1
    assert "missing turns at ticks [10], unexpected [5]" in problems[0]


def test_play_blinks_without_input_loses_early() -> None:
    state = replay.play_blinks([], duration_s=600)
    assert state.status.value == "lost"
    assert state.time_s < 600
