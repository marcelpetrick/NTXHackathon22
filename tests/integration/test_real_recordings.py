# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""The manifest must describe the shipped recordings exactly."""

from pathlib import Path

import numpy as np

from ntxbci import io
from ntxbci.manifest import load_manifest, verify


def test_manifest_matches_files(real_root: Path) -> None:
    assert verify(load_manifest(real_root)) == []


def test_no_recording_has_event_markers(real_root: Path) -> None:
    m = load_manifest(real_root)
    for entry in m.entries:
        if entry.kind != "impedance":
            assert not io.load_recording(m.file(entry)).has_markers, entry.id


def test_impedance_checks_precede_their_session(real_root: Path) -> None:
    m = load_manifest(real_root)
    for imp in m.by_kind("impedance"):
        assert imp.impedance_for is not None
        session = m.get(imp.impedance_for)
        gap = (session.start - imp.start).total_seconds()
        assert 0 < gap < 30
        check = io.load_impedance(m.file(imp))
        assert all(0 < v < 100 for v in check.values.values())


def test_session5_brainflow_duplicates_gui_export(real_root: Path) -> None:
    m = load_manifest(real_root)
    gui = io.load_recording(m.file(m.get("session5")))
    bf = io.load_recording(m.file(m.get("session5-brainflow")))
    n = min(gui.n_samples, bf.n_samples)
    np.testing.assert_allclose(gui.exg[:n], bf.exg[:n], atol=1e-3)


def test_stimulus_order(real_root: Path) -> None:
    m = load_manifest(real_root)
    assert io.load_stimulus_order(real_root / m.stimulus_order) == [
        1,
        1,
        1,
        1,
        0,
        1,
        0,
        0,
        0,
        1,
        1,
        0,
        0,
        0,
    ]
