# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""NTX Hackathon 2022 BCI toolkit."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ntxbci")
except PackageNotFoundError:  # pragma: no cover - only when running from a raw checkout
    __version__ = "0.0.0"

__all__ = ["__version__"]
