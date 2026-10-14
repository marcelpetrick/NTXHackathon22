# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import numpy as np
import pytest

from conftest import synthetic_exg
from helpers import make_recording
from ntxbci import events


def test_detects_synthetic_blinks() -> None:
    times = (5.0, 8.0, 12.5, 17.0)
    found = events.detect_blinks(make_recording(synthetic_exg(20, blinks=times)))
    assert [b.time_s for b in found] == pytest.approx(times, abs=0.05)
    assert all(b.strength_z > 15 for b in found)


def test_no_blinks_in_noise_and_settle_period_ignored() -> None:
    assert events.detect_blinks(make_recording(synthetic_exg(20, blinks=(1.0,)))) == []


def test_blink_score_short_signal() -> None:
    score = events.blink_score(synthetic_exg(3), 200.0)
    assert np.all(score == 0)


def test_match_events() -> None:
    result = events.match_events([10.4, 15.2, 33.0], [10, 15, 20], tolerance_s=1.0)
    assert result.true_positives == ((10, 10.4), (15, 15.2))
    assert result.false_positives == (33.0,)
    assert result.false_negatives == (20,)
    assert result.precision == pytest.approx(2 / 3)
    assert result.recall == pytest.approx(2 / 3)
    assert result.f1 == pytest.approx(2 / 3)
    assert result.mean_latency_s == pytest.approx(0.3)


def test_match_events_edge_cases() -> None:
    empty = events.match_events([], [], 1.0)
    assert (empty.precision, empty.recall, empty.f1) == (1.0, 1.0, 1.0)
    assert np.isnan(empty.mean_latency_s)
    miss = events.match_events([5.0], [1.0], 1.0)
    assert miss.f1 == 0.0
