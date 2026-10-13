import numpy as np

from bhtraffic.sim import whatif


def test_lognormal_matches_ci():
    x = whatif.lognormal_from_ci(0.8, 0.72, 0.89, n=200_000)
    lo, mid, hi = np.percentile(x, [2.5, 50, 97.5])
    assert abs(mid - 0.8) < 0.005 and abs(lo - 0.72) < 0.01 and abs(hi - 0.89) < 0.01


def test_summarize_band_order():
    s = whatif.summarize(np.arange(1000.0))
    assert s["lo"] < s["median"] < s["hi"]
