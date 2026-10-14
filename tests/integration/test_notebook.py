# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""The notebook must run top to bottom against the shipped recordings."""

from pathlib import Path

import nbformat
from nbclient import NotebookClient

NOTEBOOK = Path(__file__).resolve().parents[2] / "notebooks" / "dynamic_spectrum.ipynb"


def test_notebook_executes(real_root: Path) -> None:
    nb = nbformat.read(NOTEBOOK, as_version=4)
    NotebookClient(nb, timeout=300, kernel_name="python3").execute()
    outputs = "".join(
        o.get("text", "") for c in nb.cells if c.cell_type == "code" for o in c.get("outputs", [])
    )
    assert "detected blinks" in outputs
    assert "alpha power over time" in outputs
