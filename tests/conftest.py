# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Shared fixtures: synthetic Ganglion files in all three on-disk formats."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from ntxbci.manifest import default_data_root

FS = 200.0
T0 = 1667068518.8  # 2022-10-29T20:35:18.800+02:00

Writer = Callable[..., Path]


def synthetic_exg(
    seconds: float, blinks: tuple[float, ...] = (), seed: int = 0
) -> NDArray[np.float64]:
    """4-channel noise + 10 Hz alpha, with large frontal blink deflections at ``blinks``."""
    rng = np.random.default_rng(seed)
    n = int(seconds * FS)
    t = np.arange(n) / FS
    x = rng.normal(0, 10, (n, 4)) + 15 * np.sin(2 * np.pi * 10 * t)[:, None]
    for b in blinks:
        x += (400 * np.exp(-(((t - b) / 0.08) ** 2)))[:, None] * np.array([1.0, 0.8, 0.6, 0.9])
    out: NDArray[np.float64] = x
    return out


def _rows(exg: np.ndarray, t0: float) -> list[list[float]]:
    rows = []
    for i, sample in enumerate(exg):
        rows.append([float(i % 101), *sample, 0.0, 0.02, 0.99, *([0.0] * 5), t0 + i / FS, 0.0])
    return rows


@pytest.fixture
def write_gui_txt(tmp_path: Path) -> Writer:
    def write(exg: np.ndarray, name: str = "OpenBCI-RAW-test.txt", t0: float = T0) -> Path:
        path = tmp_path / name
        lines = [
            "%OpenBCI Raw EEG Data",
            "%Number of channels = 4",
            f"%Sample Rate = {FS:.0f} Hz",
            "%Board = OpenBCI_GUI$BoardGanglionBLE",
            "Sample Index, EXG Channel 0, EXG Channel 1, EXG Channel 2, EXG Channel 3, "
            "Accel Channel 0, Accel Channel 1, Accel Channel 2, Other, Other, Other, Other, "
            "Other, Timestamp, Other, Timestamp (Formatted)",
        ]
        lines += [
            ", ".join(repr(float(v)) for v in r) + ", 2022-10-29 20:35:18.800"
            for r in _rows(exg, t0)
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    return write


@pytest.fixture
def write_brainflow(tmp_path: Path) -> Writer:
    def write(
        exg: np.ndarray, name: str = "BrainFlow-RAW-test.csv", comma_decimal: bool = False
    ) -> Path:
        path = tmp_path / name
        out = []
        for r in _rows(exg, T0):
            line = "\t".join(f"{v:.6f}" for v in r)
            out.append(line.replace(".", ",") if comma_decimal else line)
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
        return path

    return write


@pytest.fixture
def write_impedance(tmp_path: Path) -> Writer:
    def write(values: tuple[float, ...] = (37, 35, 47, 16, 28), name: str = "imp.csv") -> Path:
        path = tmp_path / name
        out = []
        current = [0.0] * 5
        for step in range(8):
            k = step % 5
            current[k] = values[k]
            row = [201.0 + k, *([0.0] * 7), *current, T0 + step * 0.84, 0.0]
            out.append("\t".join(f"{v:.6f}" for v in row))
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
        return path

    return write


@pytest.fixture
def mini_dataset(tmp_path: Path, write_gui_txt: Writer, write_impedance: Writer) -> Path:
    """A tiny data root with a manifest: one EEG session, one impedance, one blink test."""
    root = tmp_path / "data"
    root.mkdir()
    eeg = write_gui_txt(synthetic_exg(20, seed=1), name="data/eeg.txt")
    imp = write_impedance(name="data/imp.csv")
    blink_times = (5.0, 10.0, 15.0)
    blink = write_gui_txt(synthetic_exg(20, blinks=blink_times, seed=2), name="data/blink.txt")
    (root / "stimulus_order.txt").write_text("1 0 1 1\n", encoding="utf-8")
    start = "2022-10-29T20:35:18.800+02:00"
    manifest = {
        "schema": 1,
        "device": "synthetic",
        "notes": ["test data"],
        "stimulus_order": "stimulus_order.txt",
        "recordings": [
            {"id": "s1", "kind": "eeg", "path": eeg.name, "start": start, "duration_s": 20.0},
            {
                "id": "imp-s1",
                "kind": "impedance",
                "path": imp.name,
                "start": start,
                "impedance_for": "s1",
            },
            {
                "id": "blink",
                "kind": "blink_test",
                "path": blink.name,
                "start": start,
                "duration_s": 20.0,
                "events": {"label": "blink", "times_s": list(blink_times), "tolerance_s": 0.5},
            },
        ],
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


@pytest.fixture(scope="session")
def real_root() -> Path:
    root = default_data_root()
    if not (root / "manifest.json").is_file():  # pragma: no cover - data ships with the repo
        pytest.skip("real recordings not available")
    return root
