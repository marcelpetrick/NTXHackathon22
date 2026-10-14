# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""The recording manifest (``Recordings/manifest.json``) and its verification."""

from __future__ import annotations

import datetime as dt
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ntxbci.io import ImpedanceCheck, Recording, load_any

Kind = Literal["eeg", "impedance", "blink_test"]
KINDS: tuple[Kind, ...] = ("eeg", "impedance", "blink_test")
MANIFEST_NAME = "manifest.json"
DATA_ENV = "NTXBCI_DATA"
_START_TOLERANCE_S = 0.5
_DURATION_TOLERANCE_S = 0.1


@dataclass(frozen=True)
class Events:
    label: str
    times_s: tuple[float, ...]
    tolerance_s: float


@dataclass(frozen=True)
class Entry:
    id: str
    kind: Kind
    path: str
    start: dt.datetime
    notes: str = ""
    duration_s: float | None = None
    impedance_for: str | None = None
    duplicate_of: str | None = None
    events: Events | None = None


@dataclass(frozen=True)
class Manifest:
    root: Path
    device: str
    notes: tuple[str, ...]
    stimulus_order: str
    entries: tuple[Entry, ...] = field(default_factory=tuple)

    def get(self, entry_id: str) -> Entry:
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        raise KeyError(entry_id)

    def file(self, entry: Entry) -> Path:
        return self.root / entry.path

    def by_kind(self, kind: Kind) -> list[Entry]:
        return [e for e in self.entries if e.kind == kind]

    def impedance_for(self, entry_id: str) -> Entry | None:
        return next((e for e in self.entries if e.impedance_for == entry_id), None)


def default_data_root() -> Path:
    """``$NTXBCI_DATA`` if set, otherwise ``Recordings/`` of the source checkout."""
    env = os.environ.get(DATA_ENV)
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "Recordings"


def _entry(raw: dict[str, Any]) -> Entry:
    kind = raw["kind"]
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r} for {raw.get('id')!r}")
    ev = raw.get("events")
    events = (
        Events(
            label=str(ev["label"]),
            times_s=tuple(float(t) for t in ev["times_s"]),
            tolerance_s=float(ev["tolerance_s"]),
        )
        if ev
        else None
    )
    return Entry(
        id=str(raw["id"]),
        kind=kind,
        path=str(raw["path"]),
        start=dt.datetime.fromisoformat(raw["start"]),
        notes=str(raw.get("notes", "")),
        duration_s=float(raw["duration_s"]) if "duration_s" in raw else None,
        impedance_for=raw.get("impedance_for"),
        duplicate_of=raw.get("duplicate_of"),
        events=events,
    )


def load_manifest(root: Path | str | None = None) -> Manifest:
    root = Path(root) if root is not None else default_data_root()
    raw = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
    entries = tuple(_entry(e) for e in raw["recordings"])
    ids = [e.id for e in entries]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate recording ids in manifest")
    return Manifest(
        root=root,
        device=str(raw.get("device", "")),
        notes=tuple(raw.get("notes", ())),
        stimulus_order=str(raw["stimulus_order"]),
        entries=entries,
    )


def verify(manifest: Manifest) -> list[str]:
    """Check the manifest against the files on disk; return a list of problems."""
    problems: list[str] = []
    listed = {e.path for e in manifest.entries} | {manifest.stimulus_order, MANIFEST_NAME}
    for path in sorted(p for p in manifest.root.rglob("*") if p.is_file()):
        rel = path.relative_to(manifest.root).as_posix()
        if rel not in listed:
            problems.append(f"{rel}: not listed in manifest")
    if not (manifest.root / manifest.stimulus_order).is_file():
        problems.append(f"{manifest.stimulus_order}: missing")
    ids = {e.id for e in manifest.entries}
    for entry in manifest.entries:
        problems.extend(_verify_entry(manifest, entry, ids))
    return problems


def _verify_entry(manifest: Manifest, entry: Entry, ids: set[str]) -> list[str]:
    path = manifest.file(entry)
    if not path.is_file():
        return [f"{entry.id}: file {entry.path} missing"]
    problems: list[str] = []
    for ref in (entry.impedance_for, entry.duplicate_of):
        if ref is not None and ref not in ids:
            problems.append(f"{entry.id}: references unknown id {ref!r}")
    data = load_any(path)
    expected_type = ImpedanceCheck if entry.kind == "impedance" else Recording
    if not isinstance(data, expected_type):
        problems.append(f"{entry.id}: kind {entry.kind!r} does not match file content")
        return problems
    if abs(data.start - entry.start.timestamp()) > _START_TOLERANCE_S:
        problems.append(f"{entry.id}: start differs from file ({data.start})")
    if (
        isinstance(data, Recording)
        and entry.duration_s is not None
        and abs(data.duration - entry.duration_s) > _DURATION_TOLERANCE_S
    ):
        problems.append(f"{entry.id}: duration {data.duration:.2f}s != {entry.duration_s}s")
    return problems
