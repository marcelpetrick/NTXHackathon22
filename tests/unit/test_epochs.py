# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import numpy as np
import pytest

from conftest import FS
from helpers import make_recording
from ntxbci import epochs

LABELS = (1, 0, 1, 1, 0, 0, 1, 0)


def _labelled_recording(onset: float, trial: float, total: float) -> np.ndarray:
    """Alpha bursts in label-1 trials, starting at ``onset``."""
    rng = np.random.default_rng(3)
    n = int(total * FS)
    t = np.arange(n) / FS
    x = rng.normal(0, 5, (n, 4))
    for i, lab in enumerate(LABELS):
        if lab:
            m = (t >= onset + i * trial) & (t < onset + (i + 1) * trial)
            x[m] += 40 * np.sin(2 * np.pi * 10 * t[m])[:, None]
    return x


def test_timing_helpers() -> None:
    timing = epochs.fit_timing(duration_s=100, n_trials=10, onset_s=10)
    assert timing.trial_s == 9
    assert timing.onsets(3) == [10, 19, 28]
    with pytest.raises(ValueError, match="positive"):
        epochs.fit_timing(10, 0)


def test_make_epochs_shape_and_errors() -> None:
    rec = make_recording(_labelled_recording(2, 4, 40))
    ep = epochs.make_epochs(rec, LABELS, epochs.TrialTiming(2, 4))
    assert ep.data.shape == (8, 800, 4)
    assert ep.labels == LABELS
    with pytest.raises(ValueError, match="does not fit"):
        epochs.make_epochs(rec, LABELS, epochs.TrialTiming(10, 4))


def test_features_separate_labels_at_true_timing() -> None:
    rec = make_recording(_labelled_recording(2, 4, 40))
    feats = epochs.band_power_features(epochs.make_epochs(rec, LABELS, epochs.TrialTiming(2, 4)))
    assert feats.shape == (8, 12)
    assert epochs.loo_accuracy(feats, LABELS) == 1.0


def test_loo_needs_two_classes() -> None:
    with pytest.raises(ValueError, match="two classes"):
        epochs.loo_accuracy(np.zeros((3, 2)), [1, 1, 1])


def test_scan_timing_finds_true_hypothesis() -> None:
    rec = make_recording(_labelled_recording(2, 4, 40))
    scores = epochs.scan_timing(rec, LABELS, onsets_s=[0, 2, 9], trial_lengths_s=[4, 5])
    best = scores[0]
    assert (best.timing.onset_s, best.timing.trial_s) == (2, 4)
    assert best.accuracy == 1.0
    assert all(s.timing.onset_s + 8 * s.timing.trial_s <= 40 for s in scores)
