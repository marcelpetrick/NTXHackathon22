# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Blink detection and event matching.

Blinks are large, slow (0.1-0.4 s) deflections that dominate the band 0.5-10 Hz on all
Ganglion channels. The detector band-passes, averages the channels, takes a robust z-score
of the absolute amplitude (median/MAD) and picks peaks above ``threshold_z`` that are at
least ``min_interval_s`` apart. The first ``settle_s`` seconds are ignored: the amplifier
needs ~3 s to settle after a stream starts (visible in every recording).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy import signal

from ntxbci.io import FloatArray, Recording
from ntxbci.processing import bandpass

_MAD_TO_SIGMA = 1.4826


@dataclass(frozen=True)
class BlinkParams:
    low_hz: float = 0.5
    high_hz: float = 10.0
    threshold_z: float = 15.0
    min_interval_s: float = 0.8
    settle_s: float = 3.5


DEFAULT_PARAMS = BlinkParams()


@dataclass(frozen=True)
class Blink:
    time_s: float
    """Seconds since the first sample."""
    strength_z: float


def blink_score(x: FloatArray, fs: float, params: BlinkParams = DEFAULT_PARAMS) -> FloatArray:
    """Robust z-score of the blink-band envelope (one value per sample)."""
    filtered = bandpass(x, fs, params.low_hz, params.high_hz)
    envelope = np.abs(filtered.mean(axis=1))
    settle = min(len(envelope), int(params.settle_s * fs))
    envelope[:settle] = 0.0
    envelope[len(envelope) - min(len(envelope), int(fs)) :] = 0.0  # filter edge at the end
    body = envelope[settle:] if settle < len(envelope) else envelope
    med = float(np.median(body))
    mad = float(np.median(np.abs(body - med))) * _MAD_TO_SIGMA or 1.0
    score: FloatArray = (envelope - med) / mad
    score[:settle] = 0.0
    return score


def detect_blinks(rec: Recording, params: BlinkParams = DEFAULT_PARAMS) -> list[Blink]:
    score = blink_score(rec.exg, rec.fs, params)
    peaks, props = signal.find_peaks(
        score,
        height=params.threshold_z,
        distance=max(1, int(params.min_interval_s * rec.fs)),
    )
    return [
        Blink(time_s=float(p / rec.fs), strength_z=float(h))
        for p, h in zip(peaks, props["peak_heights"], strict=True)
    ]


@dataclass(frozen=True)
class MatchResult:
    true_positives: tuple[tuple[float, float], ...]
    """(expected, detected) pairs."""
    false_positives: tuple[float, ...]
    false_negatives: tuple[float, ...]

    @property
    def precision(self) -> float:
        found = len(self.true_positives) + len(self.false_positives)
        return len(self.true_positives) / found if found else 1.0

    @property
    def recall(self) -> float:
        wanted = len(self.true_positives) + len(self.false_negatives)
        return len(self.true_positives) / wanted if wanted else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    @property
    def mean_latency_s(self) -> float:
        """Mean (detected - expected); NaN without matches."""
        if not self.true_positives:
            return float("nan")
        return float(np.mean([d - e for e, d in self.true_positives]))


def match_events(
    detected: Sequence[float], expected: Sequence[float], tolerance_s: float
) -> MatchResult:
    """Greedy one-to-one matching of detected to expected event times."""
    remaining = sorted(detected)
    pairs: list[tuple[float, float]] = []
    missed: list[float] = []
    for e in sorted(expected):
        candidates = [d for d in remaining if abs(d - e) <= tolerance_s]
        if candidates:
            best = min(candidates, key=lambda d: abs(d - e))
            remaining.remove(best)
            pairs.append((e, best))
        else:
            missed.append(e)
    return MatchResult(tuple(pairs), tuple(remaining), tuple(missed))
