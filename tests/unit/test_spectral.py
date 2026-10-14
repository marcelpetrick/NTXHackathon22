# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import numpy as np
import pytest

from ntxbci import spectral

FS = 200.0


def test_dynamic_spectrum_peak_and_shape() -> None:
    t = np.arange(int(10 * FS)) / FS
    x = np.sin(2 * np.pi * 12 * t) + np.random.default_rng(0).normal(0, 0.1, len(t))
    ds = spectral.dynamic_spectrum(x, FS, nperseg=200)
    assert ds.power.shape == (len(ds.times_s), len(ds.freqs_hz))
    assert len(ds.times_s) == 1 + (len(x) - 200) // 100
    assert np.all(ds.power.sum(axis=1) > 0)  # no zero rows (notebook bug)
    assert ds.freqs_hz[np.argmax(ds.power.mean(0))] == pytest.approx(12, abs=0.5)
    alpha = ds.band(8, 13)
    assert alpha.freqs_hz.min() >= 8
    assert alpha.power.shape[0] == ds.power.shape[0]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"x": np.zeros((4, 2))}, "1-D"),
        ({"x": np.zeros(500), "noverlap": 256}, "noverlap"),
        ({"x": np.zeros(10)}, "shorter"),
    ],
)
def test_dynamic_spectrum_errors(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        spectral.dynamic_spectrum(fs=FS, **kwargs)  # type: ignore[arg-type]


def test_autocovariance() -> None:
    x = np.array([1.0, 2.0, 3.0, 4.0])
    assert spectral.autocovariance(x, 0) == pytest.approx(30 / 4)
    assert spectral.autocovariance(x, 1) == pytest.approx((2 + 6 + 12) / 3)
    with pytest.raises(ValueError, match="lag"):
        spectral.autocovariance(x, 4)


def test_ar_recovers_coefficients_and_whitens() -> None:
    rng = np.random.default_rng(1)
    e = rng.normal(size=20000)
    x = np.zeros_like(e)
    for t in range(2, len(x)):
        x[t] = 0.6 * x[t - 1] - 0.3 * x[t - 2] + e[t]
    a = spectral.ar_coefficients(x, 2)
    np.testing.assert_allclose(a, [0.6, -0.3], atol=0.03)
    r = spectral.whiten(x, 2)
    assert len(r) == len(x) - 2
    lag1 = np.corrcoef(r[:-1], r[1:])[0, 1]
    assert abs(lag1) < 0.03
    assert spectral.whiten(x, 0) is x
