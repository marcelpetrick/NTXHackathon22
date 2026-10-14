# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""In-memory Recording construction for unit tests."""

from pathlib import Path

import numpy as np

from conftest import FS, T0
from ntxbci.io import FloatArray, Recording


def make_recording(exg: FloatArray, fs: float = FS) -> Recording:
    n = exg.shape[0]
    return Recording(
        path=Path("memory"),
        fs=fs,
        sample_index=np.arange(n, dtype=np.float64) % 101,
        exg=exg,
        accel=np.zeros((n, 3)),
        timestamps=T0 + np.arange(n) / fs,
        markers=np.zeros(n),
    )
