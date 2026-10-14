# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import numpy as np

from conftest import FS, synthetic_exg
from helpers import make_recording
from ntxbci import processing


def _tone(freq: float, seconds: float = 4.0) -> np.ndarray:
    t = np.arange(int(seconds * FS)) / FS
    return np.sin(2 * np.pi * freq * t)[:, None]


def test_bandpass_keeps_passband_and_removes_stopband() -> None:
    kept = processing.bandpass(_tone(10), FS, 1, 40)
    removed = processing.bandpass(_tone(80), FS, 1, 40)
    assert np.std(kept[100:-100]) > 0.6
    assert np.std(removed[100:-100]) < 0.05


def test_notch_removes_mains() -> None:
    assert np.std(processing.notch(_tone(50), FS)[200:-200]) < 0.05


def test_clean_skips_notch_when_nyquist_too_low() -> None:
    rec = make_recording(synthetic_exg(4)[::4], fs=50.0)
    assert processing.clean(rec).shape == rec.exg.shape


def test_quality_statuses() -> None:
    exg = synthetic_exg(10)
    exg[:, 1] *= 20  # noisy -> poor
    exg[:, 2] *= 500  # huge -> bad
    exg[:, 3] = 0.0  # flat -> bad
    q = processing.quality(make_recording(exg))
    assert [c.status for c in q] == ["good", "poor", "bad", "bad"]
    assert q[3].flat
    assert q[0].line_noise_ratio < 5


def test_quality_detects_line_noise() -> None:
    exg = synthetic_exg(10) + 200 * _tone(50, 10)
    assert processing.quality(make_recording(exg))[0].line_noise_ratio > 100


def test_line_noise_nan_for_low_rate() -> None:
    rec = make_recording(synthetic_exg(8)[::2], fs=100.0)
    assert np.isnan(processing.quality(rec)[0].line_noise_ratio)
