# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Multitaper dynamic spectrum and AR whitening (from ``get_dynamic_spectrum.ipynb``).

Ported from the hackathon notebook, whose ``dynamic_spectral`` was adapted from ``mtcsd``
in the labbox Matlab toolbox (Partha Mitra, Ken Harris). Fixes against the notebook:

* the AR autocovariance indexed ``X[i - p]`` with negative indices (wrapping around to the
  end of the signal); it now uses ``sum x[t] x[t + p]``, and Yule-Walker is solved as a
  Toeplitz system;
* trailing segments that did not fit were left as all-zero rows; only full segments are
  returned now, together with their centre times.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import fft, linalg
from scipy.signal import detrend, windows

from ntxbci.io import FloatArray


@dataclass(frozen=True)
class DynamicSpectrum:
    times_s: FloatArray
    """Segment centres."""
    freqs_hz: FloatArray
    power: FloatArray
    """Shape ``(n_segments, n_freqs)``, one-sided."""

    def band(self, low: float, high: float) -> DynamicSpectrum:
        keep = (self.freqs_hz >= low) & (self.freqs_hz <= high)
        return DynamicSpectrum(self.times_s, self.freqs_hz[keep], self.power[:, keep])


def dynamic_spectrum(
    x: FloatArray,
    fs: float,
    *,
    nperseg: int = 256,
    noverlap: int | None = None,
    nfft: int | None = None,
    nw: float = 3.0,
    ntapers: int | None = None,
) -> DynamicSpectrum:
    """Multitaper (Slepian) power spectrum of a 1-D signal over sliding segments."""
    if x.ndim != 1:
        raise ValueError("x must be 1-D")
    nfft = nfft or 2 * nperseg
    noverlap = nperseg // 2 if noverlap is None else noverlap
    ntapers = ntapers or int(2 * nw - 1)
    step = nperseg - noverlap
    if step <= 0:
        raise ValueError("noverlap must be smaller than nperseg")
    if len(x) < nperseg:
        raise ValueError("signal shorter than one segment")
    nsegs = 1 + (len(x) - nperseg) // step
    tapers = windows.dpss(nperseg, nw, Kmax=ntapers)
    starts = np.arange(nsegs) * step
    segs = np.stack([detrend(x[s : s + nperseg], type="constant") for s in starts])
    tapered = segs[:, None, :] * tapers[None, :, :]
    spec = fft.rfft(tapered, n=nfft, axis=-1) / np.sqrt(2)
    power: FloatArray = ((np.abs(spec) ** 2).sum(axis=1) / ntapers).astype(np.float64)
    freqs: FloatArray = np.asarray(fft.rfftfreq(nfft, 1 / fs), dtype=np.float64)
    times: FloatArray = ((starts + nperseg / 2) / fs).astype(np.float64)
    return DynamicSpectrum(times, freqs, power)


def autocovariance(x: FloatArray, lag: int) -> float:
    """Biased-by-count estimator ``sum_t x[t] x[t+lag] / (n - lag)``."""
    n = len(x)
    if not 0 <= lag < n:
        raise ValueError("lag out of range")
    return float(np.dot(x[: n - lag], x[lag:]) / (n - lag))


def ar_coefficients(x: FloatArray, order: int) -> FloatArray:
    """Yule-Walker AR(``order``) coefficients ``a`` with ``x[t] ~ sum_k a[k] x[t-1-k]``."""
    r = np.array([autocovariance(x, k) for k in range(order + 1)])
    a: FloatArray = linalg.solve_toeplitz(r[:order], r[1 : order + 1])
    return a


def whiten(x: FloatArray, order: int) -> FloatArray:
    """Residual of an AR(``order``) fit (pre-whitening); returns ``x`` for order 0."""
    if order == 0:
        return x
    xc = x - np.mean(x)
    a = ar_coefficients(xc, order)
    pred = np.zeros(len(xc) - order)
    for k in range(order):
        pred += a[k] * xc[order - 1 - k : len(xc) - 1 - k]
    out: FloatArray = xc[order:] - pred
    return out
