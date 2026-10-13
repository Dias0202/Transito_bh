import numpy as np
import pandas as pd
import h3

from bhtraffic.models import risk

CELLS = [h3.latlng_to_cell(-19.92 + i * 0.01, -43.94, 8) for i in range(3)]


def _crashes() -> pd.DataFrame:
    rows = []
    for year in range(2018, 2025):
        for i, cell in enumerate(CELLS):
            for k in range(5 + i):
                rows.append({"boletim": f"{year}-{i}-{k}", "h3": cell, "regional": "CENTRO-SUL", "year": year,
                             "weekday": k % 7, "hour": (7 + k) % 24, "fatal": k == 0, "moto": k % 2 == 0,
                             "velocidade_permitida": 60.0})
    return pd.DataFrame(rows)


def test_panel_shape_and_label():
    c = _crashes()
    p = risk.build_panel(c, 2024, CELLS)
    assert len(p) == len(CELLS) * 7 * 24
    assert p["y"].sum() == (c["year"] == 2024).sum()


def test_panel_features_ignore_target_year():
    c = _crashes()
    extra = c[c["year"] == 2024].copy()
    extra["boletim"] += "-dup"
    a = risk.build_panel(c, 2024, CELLS)
    b = risk.build_panel(pd.concat([c, extra]), 2024, CELLS)
    feats = [f for f in risk.FEATURES if f != "regional"]
    pd.testing.assert_frame_equal(a[feats], b[feats])
    assert b["y"].sum() == 2 * a["y"].sum()


def test_capture_and_deviance():
    y = np.array([0, 0, 5, 5])
    assert risk.capture(y, np.array([0.0, 0.0, 1.0, 1.0]), 0.5) == 1.0
    assert risk.poisson_deviance(y.astype(float), y.astype(float)) < 1e-6
    assert risk.poisson_deviance(y, np.full(4, 2.5)) > 0
