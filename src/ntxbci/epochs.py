# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Epoching under an explicit trial-timing hypothesis.

The sessions have no event markers, so trial onsets are unknown. Everything here takes a
:class:`TrialTiming` - a stated assumption (first onset, trial length) - and labels the
trials with ``stimulus_order.txt``. :func:`scan_timing` compares hypotheses by how well a
leave-one-out nearest-centroid classifier separates the labels on log band power. With
14 trials this is a weak, exploratory signal, never proof of the real timing.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np
from scipy import signal

from ntxbci.io import FloatArray, Recording
from ntxbci.processing import clean

BANDS: dict[str, tuple[float, float]] = {
    "theta": (4.0, 8.0),
    "alpha": (8.0, 13.0),
    "beta": (13.0, 30.0),
}


@dataclass(frozen=True)
class TrialTiming:
    onset_s: float
    """Start of the first trial, seconds since the first sample."""
    trial_s: float

    def onsets(self, n_trials: int) -> list[float]:
        return [self.onset_s + i * self.trial_s for i in range(n_trials)]


@dataclass(frozen=True)
class Epochs:
    data: FloatArray
    """Shape ``(n_trials, n_samples, n_channels)``."""
    labels: tuple[int, ...]
    onsets_s: tuple[float, ...]
    fs: float


def fit_timing(duration_s: float, n_trials: int, onset_s: float = 0.0) -> TrialTiming:
    """Default hypothesis: ``n_trials`` equal trials filling the recording after ``onset_s``."""
    if n_trials <= 0:
        raise ValueError("n_trials must be positive")
    return TrialTiming(onset_s=onset_s, trial_s=(duration_s - onset_s) / n_trials)


def make_epochs(rec: Recording, labels: Sequence[int], timing: TrialTiming) -> Epochs:
    """Cut the cleaned recording into one epoch per label."""
    x = clean(rec)
    # floor keeps start + length inside the recording for fitted timings
    n = int(timing.trial_s * rec.fs)
    onsets = timing.onsets(len(labels))
    starts = [int(o * rec.fs) for o in onsets]
    if n <= 0 or starts[0] < 0 or starts[-1] + n > rec.n_samples:
        raise ValueError(f"timing {timing} does not fit a {rec.duration:.1f}s recording")
    data = np.stack([x[s : s + n] for s in starts])
    return Epochs(data=data, labels=tuple(labels), onsets_s=tuple(onsets), fs=rec.fs)


def band_power_features(epochs: Epochs) -> FloatArray:
    """Log band power per channel and band, shape ``(n_trials, n_channels * n_bands)``."""
    f, p = signal.welch(epochs.data, fs=epochs.fs, nperseg=min(epochs.data.shape[1], 256), axis=1)
    feats = [np.log(p[:, (f >= lo) & (f < hi), :].mean(axis=1)) for lo, hi in BANDS.values()]
    out: FloatArray = np.concatenate(feats, axis=1)
    return out


def loo_accuracy(features: FloatArray, labels: Sequence[int]) -> float:
    """Leave-one-out nearest-centroid accuracy on z-scored features."""
    y = np.asarray(labels)
    if len(set(y.tolist())) < 2:
        raise ValueError("need at least two classes")
    correct = 0
    for i in range(len(y)):
        train = np.arange(len(y)) != i
        mu, sd = features[train].mean(0), features[train].std(0) + 1e-12
        z = (features - mu) / sd
        centroids = {c: z[train & (y == c)].mean(0) for c in set(y[train].tolist())}
        pred = min(centroids, key=lambda c: float(np.sum((z[i] - centroids[c]) ** 2)))
        correct += int(pred == y[i])
    return correct / len(y)


@dataclass(frozen=True)
class TimingScore:
    timing: TrialTiming
    accuracy: float


def scan_timing(
    rec: Recording,
    labels: Sequence[int],
    onsets_s: Iterable[float],
    trial_lengths_s: Iterable[float],
) -> list[TimingScore]:
    """Score every fitting (onset, trial length) hypothesis; best first."""
    scores = []
    lengths = list(trial_lengths_s)
    for onset in onsets_s:
        for length in lengths:
            timing = TrialTiming(onset, length)
            if onset + len(labels) * length > rec.duration:
                continue
            feats = band_power_features(make_epochs(rec, labels, timing))
            scores.append(TimingScore(timing, loo_accuracy(feats, labels)))
    return sorted(scores, key=lambda s: (-s.accuracy, s.timing.onset_s, s.timing.trial_s))
