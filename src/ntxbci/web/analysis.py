# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Cached per-recording analysis shared by the HTML pages and the JSON API."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import cache
from typing import Any

from ntxbci.events import Blink, detect_blinks
from ntxbci.io import ImpedanceCheck, Recording, electrode_impedance, load_impedance, load_recording
from ntxbci.manifest import Entry, Manifest
from ntxbci.processing import ChannelQuality, quality
from ntxbci.replay import ReplayReport, replay


@dataclass(frozen=True)
class Analysis:
    entry: Entry
    recording: Recording
    quality: tuple[ChannelQuality, ...]
    blinks: tuple[Blink, ...]
    replay: ReplayReport
    impedance: ImpedanceCheck | None

    @property
    def overall(self) -> str:
        statuses = {c.status for c in self.quality}
        return "bad" if "bad" in statuses else "poor" if "poor" in statuses else "good"

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.entry.id,
            "kind": self.entry.kind,
            "start": self.entry.start.isoformat(),
            "duration_s": round(self.recording.duration, 3),
            "quality": self.overall,
            "blinks": len(self.blinks),
            "replay_passed": self.replay.passed,
            "notes": self.entry.notes,
        }

    def details(self) -> dict[str, Any]:
        out = self.summary()
        out["channels"] = [asdict(c) for c in self.quality]
        out["blink_times_s"] = [round(b.time_s, 3) for b in self.blinks]
        out["replay"] = self.replay.to_dict()
        out["impedance_kohm"] = (
            {k: electrode_impedance(v) for k, v in self.impedance.values.items()}
            if self.impedance
            else None
        )
        return out


class Analyzer:
    """Computes and memoises :class:`Analysis` objects for one manifest."""

    def __init__(self, manifest: Manifest) -> None:
        self.manifest = manifest
        self._get = cache(self._compute)

    def recordings(self) -> list[Entry]:
        return [e for e in self.manifest.entries if e.kind != "impedance"]

    def get(self, entry_id: str) -> Analysis:
        entry = self.manifest.get(entry_id)
        if entry.kind == "impedance":
            raise KeyError(entry_id)
        return self._get(entry_id)

    def _compute(self, entry_id: str) -> Analysis:
        entry = self.manifest.get(entry_id)
        rec = load_recording(self.manifest.file(entry))
        imp_entry = self.manifest.impedance_for(entry_id)
        return Analysis(
            entry=entry,
            recording=rec,
            quality=tuple(quality(rec)),
            blinks=tuple(detect_blinks(rec)),
            replay=replay(self.manifest, entry_id),
            impedance=load_impedance(self.manifest.file(imp_entry)) if imp_entry else None,
        )
