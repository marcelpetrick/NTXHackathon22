# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import json
from pathlib import Path

import pytest

from ntxbci import manifest as mf


def _edit(root: Path, fn: object) -> None:
    path = root / "manifest.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    fn(raw)  # type: ignore[operator]
    path.write_text(json.dumps(raw), encoding="utf-8")


def test_load_and_query(mini_dataset: Path) -> None:
    m = mf.load_manifest(mini_dataset)
    assert m.device == "synthetic"
    assert [e.id for e in m.by_kind("eeg")] == ["s1"]
    assert m.get("blink").events is not None
    imp = m.impedance_for("s1")
    assert imp is not None
    assert imp.id == "imp-s1"
    assert m.impedance_for("blink") is None
    assert m.file(m.get("s1")).is_file()
    with pytest.raises(KeyError):
        m.get("nope")
    assert mf.verify(m) == []


def test_verify_reports_problems(mini_dataset: Path) -> None:
    (mini_dataset / "stray.txt").write_text("x", encoding="utf-8")
    (mini_dataset / "stimulus_order.txt").unlink()

    def mutate(raw: dict[str, list[dict[str, object]]]) -> None:
        rec = raw["recordings"]
        rec[0]["duration_s"] = 99.0
        rec[0]["start"] = "2022-10-29T20:00:00+02:00"
        rec[1]["impedance_for"] = "ghost"
        rec[2]["kind"] = "impedance"
        rec.append({"id": "gone", "kind": "eeg", "path": "gone.txt", "start": rec[0]["start"]})

    _edit(mini_dataset, mutate)
    problems = "\n".join(mf.verify(mf.load_manifest(mini_dataset)))
    for needle in [
        "stray.txt: not listed",
        "stimulus_order.txt: missing",
        "s1: duration",
        "s1: start differs",
        "unknown id 'ghost'",
        "blink: kind 'impedance' does not match",
        "gone: file gone.txt missing",
    ]:
        assert needle in problems


def test_invalid_manifests(mini_dataset: Path) -> None:
    _edit(mini_dataset, lambda raw: raw["recordings"][0].update(kind="video"))
    with pytest.raises(ValueError, match="unknown kind"):
        mf.load_manifest(mini_dataset)
    _edit(mini_dataset, lambda raw: raw["recordings"][0].update(kind="eeg", id="blink"))
    with pytest.raises(ValueError, match="duplicate"):
        mf.load_manifest(mini_dataset)


def test_default_data_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(mf.DATA_ENV, str(tmp_path))
    assert mf.default_data_root() == tmp_path
    monkeypatch.delenv(mf.DATA_ENV)
    assert mf.default_data_root().name == "Recordings"
