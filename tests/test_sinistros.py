import numpy as np
import pandas as pd

from bhtraffic.ingest import pbh, sinistros


def test_column_aliases_unify_boletim():
    for raw in ("Nº_boletim", " NUMERO_BOLETIM", "num_boletim", "n_boletim"):
        assert pbh._norm_col(raw) == "boletim"


def test_fix_coords_legacy_layout_matches_modern():
    # 2011-2015 layout (x*100, y*100 without the leading 7 million) vs 2016+ UTM.
    x, y = sinistros.fix_coords(pd.Series(["0060895200.00", "0000608952.00"]), pd.Series(["0079812300.00", "0007798123.00"]))
    assert np.allclose(x, [608952.0, 608952.0])
    assert np.allclose(y, [7798123.0, 7798123.0])


def test_fix_coords_drops_out_of_bounds():
    x, y = sinistros.fix_coords(pd.Series(["0", "100"]), pd.Series(["0", "100"]))
    assert x.isna().all() and y.isna().all()


def test_flag_placeholders():
    regionais = ["A", "B", "C", "D", "E"] * 30  # 150 crashes, 5 regionals, one spot
    spot = pd.DataFrame({"lat": -19.9058, "lon": -43.9889, "regional": regionais})
    real = pd.DataFrame({"lat": -19.92, "lon": -43.94, "regional": ["CENTRO-SUL"] * 200})
    df = pd.concat([spot, real], ignore_index=True)
    flags = sinistros.flag_placeholders(df)
    assert flags[:150].all() and not flags[150:].any()
