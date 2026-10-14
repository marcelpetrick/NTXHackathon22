# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
from pathlib import Path

import numpy as np
import pytest

from conftest import FS, T0, Writer, synthetic_exg
from ntxbci import io


def test_gui_txt_roundtrip(write_gui_txt: Writer) -> None:
    exg = synthetic_exg(2)
    rec = io.load_recording(write_gui_txt(exg))
    assert rec.fs == FS
    assert rec.n_samples == 400
    assert rec.duration == pytest.approx(2.0)
    np.testing.assert_allclose(rec.exg, exg, rtol=1e-12)
    assert rec.accel.shape == (400, 3)
    assert rec.start == pytest.approx(T0)
    assert rec.end > rec.start
    assert rec.times[-1] == pytest.approx(399 / FS)
    assert not rec.has_markers


def test_markers_and_missing_marker_column(tmp_path: Path) -> None:
    base = [0.0, 1, 2, 3, 4, 0, 0, 1, 0, 0, 0, 0, 0, T0]
    path = tmp_path / "m.csv"
    path.write_text("\t".join(str(v) for v in [*base, 3.0]) + "\n", encoding="utf-8")
    assert io.load_recording(path).has_markers
    path.write_text("\t".join(str(v) for v in base) + "\n", encoding="utf-8")
    rec = io.load_recording(path)
    assert not rec.has_markers
    assert rec.markers.shape == (1,)


def test_electrode_impedance() -> None:
    assert io.electrode_impedance(56.0) == 28.0


@pytest.mark.parametrize("comma", [False, True])
def test_brainflow_formats(write_brainflow: Writer, comma: bool) -> None:
    exg = synthetic_exg(1)
    rec = io.load_recording(write_brainflow(exg, comma_decimal=comma))
    np.testing.assert_allclose(rec.exg, exg, atol=1e-5)
    assert rec.fs == io.GANGLION_FS


def test_impedance(write_impedance: Writer) -> None:
    imp = io.load_impedance(write_impedance((37, 35, 47, 16, 28)))
    assert imp.values == {"ch1": 37, "ch2": 35, "ch3": 47, "ch4": 16, "ref": 28}
    assert imp.end > imp.start


def test_impedance_missing_channel_is_nan(tmp_path: Path) -> None:
    row = [201.0, *([0.0] * 7), 37.0, 0, 0, 0, 0, T0, 0.0]
    path = tmp_path / "imp.csv"
    path.write_text("\t".join(str(v) for v in row) + "\n", encoding="utf-8")
    imp = io.load_impedance(path)
    assert imp.values["ch1"] == 37
    assert np.isnan(imp.values["ref"])


def test_kind_mismatch_raises(write_gui_txt: Writer, write_impedance: Writer) -> None:
    with pytest.raises(io.FormatError, match="impedance check"):
        io.load_recording(write_impedance())
    with pytest.raises(io.FormatError, match="EEG recording"):
        io.load_impedance(write_gui_txt(synthetic_exg(1)))


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("", "no data rows"),
        ("%only header\n", "no data rows"),
        ("1\t2\t3\n", "expected >= 14"),
        ("a\tb\n", "unparsable"),
    ],
)
def test_bad_files(tmp_path: Path, content: str, message: str) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(io.FormatError, match=message):
        io.load_any(path)


def test_stimulus_order(tmp_path: Path) -> None:
    path = tmp_path / "s.txt"
    path.write_text("1 1 0\n0 ", encoding="utf-8")
    assert io.load_stimulus_order(path) == [1, 1, 0, 0]
    path.write_text("1 2", encoding="utf-8")
    with pytest.raises(io.FormatError):
        io.load_stimulus_order(path)


def test_blank_lines_are_skipped(tmp_path: Path) -> None:
    row = "\t".join(str(v) for v in [0.0, 1, 2, 3, 4, 0, 0, 1, 0, 0, 0, 0, 0, T0, 0])
    path = tmp_path / "b.csv"
    path.write_text(f"{row}\n\n{row}\n", encoding="utf-8")
    assert io.load_recording(path).n_samples == 2
