# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Matplotlib figures rendered to PNG bytes (Agg backend, no display needed)."""

from __future__ import annotations

import io

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from ntxbci.events import DEFAULT_PARAMS, blink_score
from ntxbci.processing import clean
from ntxbci.spectral import dynamic_spectrum
from ntxbci.web.analysis import Analysis

PLOTS = ("traces", "blinks", "spectrogram")
_INK = "#1f2933"
_ACCENT = "#d9480f"
_TRUTH = "#2b8a3e"
_CHANNEL_COLOURS = ("#1c7ed6", "#7048e8", "#0ca678", "#f08c00")


def _png(fig: Figure) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _mark_events(ax: Axes, a: Analysis) -> None:
    for b in a.blinks:
        ax.axvline(b.time_s, color=_ACCENT, lw=0.8, alpha=0.7)
    if a.entry.events is not None:
        for t in a.entry.events.times_s:
            ax.axvline(t, color=_TRUTH, lw=1.2, ls="--", alpha=0.8)


def traces(a: Analysis) -> bytes:
    rec = a.recording
    x = clean(rec)
    t = rec.times
    body = t >= DEFAULT_PARAMS.settle_s  # scale without the amplifier start-up transient
    fig, axes = plt.subplots(4, 1, figsize=(11, 5.2), sharex=True)
    for ch, ax in enumerate(axes):
        ax.plot(t, x[:, ch], lw=0.4, color=_CHANNEL_COLOURS[ch])
        ax.set_ylabel(f"ch{ch + 1}\nµV", color=_INK)
        lim = max(50.0, float(np.max(np.abs(x[body, ch]))) * 1.1)
        ax.set_ylim(-lim, lim)
        _mark_events(ax, a)
        ax.spines[["top", "right"]].set_visible(False)
    axes[-1].set_xlabel("time [s]")
    axes[0].set_title(
        "EEG, notch 50 Hz + band-pass 1-40 Hz  (orange: detected blinks"
        + (", green dashed: protocol)" if a.entry.events else ")"),
        loc="left",
    )
    return _png(fig)


def blinks(a: Analysis) -> bytes:
    rec = a.recording
    score = blink_score(rec.exg, rec.fs)
    fig, ax = plt.subplots(figsize=(11, 2.6))
    ax.plot(rec.times, score, lw=0.6, color=_INK)
    ax.axhline(DEFAULT_PARAMS.threshold_z, color=_ACCENT, ls=":", lw=1, label="threshold")
    _mark_events(ax, a)
    ax.set_xlabel("time [s]")
    ax.set_ylabel("blink z-score")
    ax.set_title("Blink detector score (robust z of 0.5-10 Hz envelope)", loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper right", frameon=False)
    return _png(fig)


def spectrogram(a: Analysis) -> bytes:
    rec = a.recording
    x = clean(rec).mean(axis=1)
    ds = dynamic_spectrum(x, rec.fs, nperseg=256).band(1, 40)
    fig, ax = plt.subplots(figsize=(11, 3.2))
    db = 10 * np.log10(ds.power.T + 1e-12)
    lo, hi = np.percentile(db, [2, 99.5])
    mesh = ax.pcolormesh(
        ds.times_s, ds.freqs_hz, db, shading="auto", cmap="magma", vmin=lo, vmax=hi
    )
    fig.colorbar(mesh, ax=ax, label="dB")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("Hz")
    ax.set_title("Multitaper dynamic spectrum (channel mean)", loc="left")
    return _png(fig)


RENDERERS = {"traces": traces, "blinks": blinks, "spectrogram": spectrogram}
