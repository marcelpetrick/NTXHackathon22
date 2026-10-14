# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Processing on the shipped recordings."""

from pathlib import Path

from ntxbci import io
from ntxbci.epochs import fit_timing, make_epochs
from ntxbci.events import detect_blinks, match_events
from ntxbci.manifest import load_manifest
from ntxbci.processing import quality


def test_blink_detector_matches_protocol(real_root: Path) -> None:
    m = load_manifest(real_root)
    entry = m.get("blink-test")
    assert entry.events is not None
    blinks = detect_blinks(io.load_recording(m.file(entry)))
    result = match_events(
        [b.time_s for b in blinks], entry.events.times_s, entry.events.tolerance_s
    )
    assert result.f1 == 1.0, result


def test_sessions_have_usable_quality(real_root: Path) -> None:
    m = load_manifest(real_root)
    for entry in m.by_kind("eeg"):
        statuses = {c.status for c in quality(io.load_recording(m.file(entry)))}
        assert "bad" not in statuses, entry.id


def test_default_epoching_of_every_session(real_root: Path) -> None:
    m = load_manifest(real_root)
    labels = io.load_stimulus_order(real_root / m.stimulus_order)
    for entry in m.by_kind("eeg"):
        rec = io.load_recording(m.file(entry))
        ep = make_epochs(rec, labels, fit_timing(rec.duration, len(labels)))
        assert ep.data.shape[0] == 14
