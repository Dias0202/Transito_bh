import pandas as pd

from bhtraffic.ingest import calendar, inmet
from bhtraffic.models import temporal

MATCH_CSV = '''"ID","rodata","data","hora","mandante","visitante","formacao_mandante","formacao_visitante","tecnico_mandante","tecnico_visitante","vencedor","arena","mandante_Placar","visitante_Placar","mandante_Estado","visitante_Estado"
"1","1","05/03/2023","16:00","Cruzeiro","Atletico-MG","","","","","-"," Mineirão","1","1","MG","MG"
"2","1","05/03/2023","16:00","Gremio","Vasco","","","","","-"," Arena do Grêmio","1","0","RS","RJ"
"3","2","12/03/2023","18:30","Atletico-MG","Santos","","","","","-","Arena MRV","2","0","MG","SP"
'''

INMET_CSV = "\n".join(["meta"] * 8 + [
    "Data;Hora UTC;PRECIPITAÇÃO TOTAL, HORÁRIO (mm);TEMPERATURA DO AR - BULBO SECO, HORARIA (°C);UMIDADE RELATIVA DO AR, HORARIA (%)",
    "2019/01/01;0000 UTC;0;21,5;86",
    "2019/01/01;0100 UTC;2,4;20,9;90",
    "2019/01/01;0200 UTC;-9999;-9999;-9999",
])


def test_holidays_include_bh_municipal_and_corpus_christi():
    h = calendar.holidays_table(range(2023, 2024))
    d = h.set_index("date")
    assert d.loc["2023-08-15", "kind"] == "public"
    assert d.loc["2023-12-08", "kind"] == "public"
    assert (h[h["name"].str.contains("Corpus Christi")]["kind"] == "public").all()
    assert h["carnaval"].sum() == 2


def test_matches_keep_only_bh_stadiums():
    m = calendar.matches_table(MATCH_CSV)
    assert list(m["stadium"]) == ["mineirao", "arena_mrv"]
    assert m["classico"].tolist() == [True, False]
    assert m["kickoff"].iat[1] == pd.Timestamp("2023-03-12 18:30")


def test_inmet_parse_utc_to_brt_and_missing():
    w = inmet.parse_station_csv(INMET_CSV)
    assert w["ts"].iat[0] == pd.Timestamp("2018-12-31 22:00")  # 00 UTC = 21h/22h BRT (DST in 2019)
    assert w["rain_mm"].iat[1] == 2.4
    assert pd.isna(w["rain_mm"].iat[2])


def test_match_window_and_first_rain():
    hol = calendar.holidays_table(range(2023, 2024))
    mat = calendar.matches_table(MATCH_CSV)
    ts = pd.date_range("2023-01-01", "2023-12-31 23:00", freq="h")
    rain = pd.Series(0.0, index=ts)
    rain["2023-03-20 15:00"] = 3.0  # after weeks of dry hours -> first rain
    rain["2023-03-20 16:00"] = 1.0  # still raining, no longer "first"
    weather = pd.DataFrame({"ts": ts, "rain_mm": rain.to_numpy()})
    f = temporal.hourly_frame(hol, mat, weather, years=(2023, 2023)).set_index("ts")
    k = pd.Timestamp("2023-03-05 16:00")
    assert f.loc[k - pd.Timedelta(hours=2), "match"] == 1
    assert f.loc[k + pd.Timedelta(hours=3), "match"] == 1
    assert f.loc[k + pd.Timedelta(hours=4), "match"] == 0
    assert f.loc[k, "classico"] == 1
    assert f.loc["2023-03-20 15:00", "first_rain"] == 1
    assert f.loc["2023-03-20 16:00", "first_rain"] == 0
    assert f.loc["2023-08-15 10:00", "holiday"] == 1
