# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""CLI commands against the synthetic dataset and the real recordings."""

import json
from pathlib import Path

import numpy as np
import pytest

from ntxbci import __version__, cli

Capture = pytest.CaptureFixture[str]


def _run(capsys: Capture, *argv: str) -> tuple[int, str]:
    code = cli.main(list(argv))
    return code, capsys.readouterr().out


def test_version(capsys: Capture) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_command_required(capsys: Capture) -> None:
    with pytest.raises(SystemExit):
        cli.main([])
    assert "required" in capsys.readouterr().err


def test_inventory_text_and_json(capsys: Capture, real_root: Path) -> None:
    code, out = _run(capsys, "--data", str(real_root), "inventory")
    assert code == 0
    assert "manifest check: OK" in out
    assert "impedance-before-session3" in out
    code, out = _run(capsys, "--data", str(real_root), "inventory", "--json")
    data = json.loads(out)
    assert data["problems"] == []
    assert len(data["recordings"]) == 9


def test_inventory_reports_problems(capsys: Capture, mini_dataset: Path) -> None:
    (mini_dataset / "stray.txt").write_text("x", encoding="utf-8")
    code, out = _run(capsys, "--data", str(mini_dataset), "inventory")
    assert code == 1
    assert "! stray.txt: not listed" in out


def test_quality(capsys: Capture, mini_dataset: Path) -> None:
    code, out = _run(capsys, "--data", str(mini_dataset), "quality", "s1")
    assert code == 0
    assert "ch4: good" in out
    _, out = _run(capsys, "--data", str(mini_dataset), "quality", "s1", "--json")
    assert len(json.loads(out)) == 4


def test_blinks(capsys: Capture, mini_dataset: Path) -> None:
    code, out = _run(capsys, "--data", str(mini_dataset), "blinks", "blink")
    assert code == 0
    assert "3 blinks" in out
    assert "F1=1.00" in out
    _, out = _run(capsys, "--data", str(mini_dataset), "blinks", "s1", "--json")
    assert json.loads(out) == {"blinks": []}


def test_epochs_export(capsys: Capture, mini_dataset: Path, tmp_path: Path) -> None:
    out_file = tmp_path / "ep.npz"
    code, out = _run(
        capsys, "--data", str(mini_dataset), "epochs", "s1", "--onset", "1", "--out", str(out_file)
    )
    assert code == 0
    assert "ASSUMED timing" in out
    with np.load(out_file) as npz:
        assert npz["data"].shape[0] == 4
        assert list(npz["labels"]) == [1, 0, 1, 1]
        assert json.loads(str(npz["hypothesis"])) == {"onset_s": 1.0, "trial_s": 4.75}
    code, _ = _run(
        capsys, "--data", str(mini_dataset), "epochs", "s1", "--trial", "4", "--out", str(out_file)
    )
    assert code == 0


def test_scan_timing(capsys: Capture, mini_dataset: Path) -> None:
    args = ["--data", str(mini_dataset), "scan-timing", "s1", "--onsets", "0:2:1", "--lengths", "4"]
    code, out = _run(capsys, *args)
    assert code == 0
    assert "exploratory only" in out
    _, out = _run(capsys, *args, "--json", "--top", "2")
    assert len(json.loads(out)) == 2


def test_bad_range(capsys: Capture) -> None:
    with pytest.raises(SystemExit):
        cli.main(["scan-timing", "x", "--onsets", "1:2"])
    assert "start:stop:step" in capsys.readouterr().err


def test_spectrum_csv(capsys: Capture, mini_dataset: Path, tmp_path: Path) -> None:
    out_file = tmp_path / "spec.csv"
    code, _ = _run(
        capsys,
        "--data",
        str(mini_dataset),
        "spectrum",
        "s1",
        "--channel",
        "2",
        "--out",
        str(out_file),
    )
    assert code == 0
    header, *rows = out_file.read_text(encoding="utf-8").splitlines()
    assert header.startswith("time_s,1.")
    assert len(rows) > 10


def test_replay_pass_fail_and_window(capsys: Capture, mini_dataset: Path, tmp_path: Path) -> None:
    shot = tmp_path / "replay.png"
    code, out = _run(
        capsys,
        "--data",
        str(mini_dataset),
        "replay",
        "blink",
        "--headless",
        "--screenshot",
        str(shot),
    )
    assert code == 0
    assert "PASS" in out
    assert "game over:" in out
    assert shot.is_file()
    code, out = _run(capsys, "--data", str(mini_dataset), "replay", "s1", "--json")
    assert code == 0
    assert json.loads(out)["detection"] is None
    code, out = _run(capsys, "--data", str(mini_dataset), "replay", "blink", "--threshold", "1e6")
    assert code == 1
    assert "FAIL" in out


def test_play_headless(capsys: Capture, tmp_path: Path) -> None:
    code, out = _run(
        capsys, "play", "--headless", "--seconds", "1", "--screenshot", str(tmp_path / "p.png")
    )
    assert code == 0
    assert "game over: lost" in out or "game over: won" in out


def test_errors_exit_2(capsys: Capture, mini_dataset: Path) -> None:
    assert cli.main(["--data", str(mini_dataset), "quality", "nope"]) == 2
    assert "error:" in capsys.readouterr().err
    assert cli.main(["--data", str(mini_dataset), "replay", "imp-s1"]) == 2
