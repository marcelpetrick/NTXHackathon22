# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Filtering and signal-quality metrics for Ganglion EEG."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy import signal

from ntxbci.io import FloatArray, Recording

MAINS_HZ = 50.0  # recorded in Germany
Status = Literal["good", "poor", "bad"]

# thresholds in microvolts on the 1-40 Hz band-passed signal
_GOOD_STD_UV = 50.0
_BAD_STD_UV = 1000.0
_ARTEFACT_UV = 150.0
_POOR_ARTEFACT_FRACTION = 0.05


def bandpass(x: FloatArray, fs: float, low: float, high: float, order: int = 4) -> FloatArray:
    """Zero-phase Butterworth band-pass along axis 0 (DC removed first)."""
    sos = signal.butter(order, [low, high], btype="bandpass", fs=fs, output="sos")
    centred = x - np.median(x, axis=0)
    out: FloatArray = signal.sosfiltfilt(sos, centred, axis=0)
    return out


def notch(x: FloatArray, fs: float, freq: float = MAINS_HZ, quality: float = 30.0) -> FloatArray:
    """Zero-phase IIR notch (mains interference) along axis 0."""
    b, a = signal.iirnotch(freq, quality, fs=fs)
    out: FloatArray = signal.filtfilt(b, a, x, axis=0)
    return out


def clean(rec: Recording, low: float = 1.0, high: float = 40.0) -> FloatArray:
    """Standard EEG cleaning: mains notch, then band-pass ``low``-``high`` Hz."""
    x = rec.exg
    if rec.fs / 2 > MAINS_HZ:
        x = notch(x, rec.fs)
    return bandpass(x, rec.fs, low, min(high, rec.fs / 2 - 1))


@dataclass(frozen=True)
class ChannelQuality:
    channel: int
    std_uv: float
    artefact_fraction: float
    line_noise_ratio: float
    """Power at mains frequency relative to the 40-60 Hz neighbourhood (raw signal)."""
    flat: bool
    status: Status


def _line_noise_ratio(x: FloatArray, fs: float) -> float:
    if fs / 2 <= MAINS_HZ + 5:
        return float("nan")
    f, p = signal.welch(x - np.mean(x), fs=fs, nperseg=min(len(x), int(fs * 2)))
    at_mains = p[np.argmin(np.abs(f - MAINS_HZ))]
    band = p[(f >= 40) & (f <= 60) & (np.abs(f - MAINS_HZ) > 2)]
    return float(at_mains / np.median(band)) if len(band) and np.median(band) > 0 else 0.0


def quality(rec: Recording) -> list[ChannelQuality]:
    """Per-channel quality summary used by the CLI and the dashboard."""
    filtered = clean(rec)
    result = []
    for ch in range(rec.exg.shape[1]):
        raw = rec.exg[:, ch]
        std = float(np.std(filtered[:, ch]))
        flat = bool(np.ptp(raw) == 0)
        artefacts = float(np.mean(np.abs(filtered[:, ch]) > _ARTEFACT_UV))
        status: Status
        if flat or std > _BAD_STD_UV:
            status = "bad"
        elif std > _GOOD_STD_UV or artefacts > _POOR_ARTEFACT_FRACTION:
            status = "poor"
        else:
            status = "good"
        result.append(
            ChannelQuality(
                channel=ch,
                std_uv=std,
                artefact_fraction=artefacts,
                line_noise_ratio=_line_noise_ratio(raw, rec.fs),
                flat=flat,
                status=status,
            )
        )
    return result
