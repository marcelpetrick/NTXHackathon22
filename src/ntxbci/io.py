# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Loaders for the OpenBCI Ganglion exports found in ``Recordings/``.

Three on-disk formats exist:

* OpenBCI GUI ``OpenBCI-RAW-*.txt``: ``%`` header, column header, comma separated.
* BrainFlow ``BrainFlow-RAW-*.csv``: tab separated, no header.
* BrainFlow export with a German locale (``*.cw``): tab separated, comma as decimal mark.

All share the Ganglion column layout: ``0`` sample/packet index, ``1-4`` EXG channels (uV),
``5-7`` accelerometer (g), ``8-12`` "other", ``13`` unix timestamp, ``14`` BrainFlow
marker channel (all zero in every hackathon recording: no events were marked).

During an impedance check the Ganglion sends packets with IDs 201-205 instead of samples;
packet ``200 + k`` carries the impedance of channel ``k`` (``205`` = reference) in column
``7 + k``. The value is electrode + driven ground in kOhm; the OpenBCI GUI displays half of it
as the per-electrode estimate (see :func:`electrode_impedance`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

GANGLION_FS = 200.0
N_EXG = 4
IMPEDANCE_IDS = range(201, 206)
IMPEDANCE_LABELS = ("ch1", "ch2", "ch3", "ch4", "ref")

_COL_INDEX = 0
_COLS_EXG = slice(1, 5)
_COLS_ACCEL = slice(5, 8)
_COL_TS = 13
_COL_MARKER = 14
_MIN_COLS = 14

FloatArray = NDArray[np.float64]


class FormatError(ValueError):
    """Raised when a file does not look like a Ganglion export."""


@dataclass(frozen=True)
class Recording:
    """A continuous EEG recording."""

    path: Path
    fs: float
    sample_index: FloatArray
    exg: FloatArray
    """Shape ``(n_samples, 4)`` in microvolts."""
    accel: FloatArray
    timestamps: FloatArray
    """Unix seconds per sample."""
    markers: FloatArray
    """BrainFlow marker channel (0 = no event)."""

    @property
    def n_samples(self) -> int:
        return int(self.exg.shape[0])

    @property
    def duration(self) -> float:
        """Duration in seconds derived from the sample count."""
        return self.n_samples / self.fs

    @property
    def start(self) -> float:
        return float(self.timestamps[0])

    @property
    def end(self) -> float:
        return float(self.timestamps[-1])

    @property
    def has_markers(self) -> bool:
        return bool(np.any(self.markers != 0))

    @property
    def times(self) -> FloatArray:
        """Seconds since the first sample, from the sample count (uniform grid)."""
        return np.arange(self.n_samples, dtype=np.float64) / self.fs


@dataclass(frozen=True)
class ImpedanceCheck:
    """An impedance check: per-electrode impedance in kOhm (last reading wins)."""

    path: Path
    timestamps: FloatArray
    values: dict[str, float]

    @property
    def start(self) -> float:
        return float(self.timestamps[0])

    @property
    def end(self) -> float:
        return float(self.timestamps[-1])


def _parse_float(token: str, comma_decimal: bool) -> float:
    return float(token.replace(",", ".") if comma_decimal else token)


def _read_table(path: Path) -> tuple[FloatArray, float]:
    """Return the numeric table and the sample rate declared in the file (or default)."""
    fs = GANGLION_FS
    rows: list[list[float]] = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    tab_separated = any("\t" in line for line in lines[:5])
    comma_decimal = tab_separated and any(re.search(r"\d,\d", line) for line in lines[:5])
    for line in lines:
        if not line.strip():
            continue
        if line.startswith("%"):
            match = re.search(r"Sample Rate\s*=\s*([\d.]+)", line)
            if match:
                fs = float(match.group(1))
            continue
        if line.startswith("Sample Index"):
            continue
        # the last column of the GUI export is a formatted datetime string
        tokens = line.split("\t") if tab_separated else [t.strip() for t in line.split(",")][:-1]
        try:
            rows.append([_parse_float(t, comma_decimal) for t in tokens])
        except ValueError as exc:
            raise FormatError(f"{path}: unparsable line {line[:60]!r}") from exc
    if not rows:
        raise FormatError(f"{path}: no data rows")
    width = min(len(r) for r in rows)
    if width < _MIN_COLS:
        raise FormatError(f"{path}: expected >= {_MIN_COLS} columns, got {width}")
    table = np.array([r[:width] for r in rows], dtype=np.float64)
    return table, fs


def is_impedance_table(table: FloatArray) -> bool:
    """True if every row is an impedance packet (IDs 201-205)."""
    ids = table[:, _COL_INDEX]
    return bool(np.all((ids >= IMPEDANCE_IDS.start) & (ids < IMPEDANCE_IDS.stop)))


def load_any(path: Path | str) -> Recording | ImpedanceCheck:
    """Load a file and return a :class:`Recording` or an :class:`ImpedanceCheck`."""
    path = Path(path)
    table, fs = _read_table(path)
    if is_impedance_table(table):
        values: dict[str, float] = {}
        for k, label in enumerate(IMPEDANCE_LABELS, start=1):
            rows = table[table[:, _COL_INDEX] == 200 + k]
            readings = rows[:, 7 + k] if len(rows) else table[:, 7 + k]
            nonzero = readings[readings != 0]
            values[label] = float(nonzero[-1]) if len(nonzero) else float("nan")
        return ImpedanceCheck(path=path, timestamps=table[:, _COL_TS], values=values)
    return Recording(
        path=path,
        fs=fs,
        sample_index=table[:, _COL_INDEX],
        exg=table[:, _COLS_EXG],
        accel=table[:, _COLS_ACCEL],
        timestamps=table[:, _COL_TS],
        markers=table[:, _COL_MARKER] if table.shape[1] > _COL_MARKER else np.zeros(len(table)),
    )


def electrode_impedance(raw_kohm: float) -> float:
    """Per-electrode impedance estimate (kOhm) as shown by the OpenBCI GUI: raw / 2."""
    return raw_kohm / 2.0


def load_recording(path: Path | str) -> Recording:
    """Load an EEG recording; raise :class:`FormatError` for impedance checks."""
    result = load_any(path)
    if not isinstance(result, Recording):
        raise FormatError(f"{path}: is an impedance check, not an EEG recording")
    return result


def load_impedance(path: Path | str) -> ImpedanceCheck:
    """Load an impedance check; raise :class:`FormatError` for EEG recordings."""
    result = load_any(path)
    if not isinstance(result, ImpedanceCheck):
        raise FormatError(f"{path}: is an EEG recording, not an impedance check")
    return result


def load_stimulus_order(path: Path | str) -> list[int]:
    """Parse ``stimulus_order.txt`` (whitespace separated 0/1 labels)."""
    tokens = Path(path).read_text(encoding="utf-8").split()
    labels = [int(t) for t in tokens]
    if any(v not in (0, 1) for v in labels):
        raise FormatError(f"{path}: stimulus labels must be 0 or 1")
    return labels
