"""SUMO pilot: Av. Presidente Antônio Carlos (Lagoinha -> Pampulha), weekday 7-8h.

Baseline calibrated to BHTrans radar counts; validated against radar speeds.
Scenario: speed limit 60 -> 50 km/h on the avenue. Everything runs locally with
the open-source SUMO package (eclipse-sumo); no paid compute.

Steps
1. Network: OSM extract (motorway..tertiary + links) -> netconvert.
2. Radar sites -> network edges (nearest edge named "Antônio Carlos" whose heading
   matches the radar direction; Bairro/Centro = southbound).
3. Demand: candidate routes (randomTrips + duarouter), then routeSampler picks
   routes so that edge counts match the radar counts for the target hour.
4. Run 15 min warm-up + 60 min; edgeData speeds at radar edges vs radar speeds.
5. Scenario run with maxSpeed 50 km/h on the avenue (TraCI), same demand & seed.

    python -m bhtraffic.sim.sumo_pilot   # -> processed/sim/sumo_antonio_carlos.json
"""
from __future__ import annotations

import glob
import json
import math
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd

from bhtraffic.config import processed_dir, raw_dir

HOUR = 7
WARMUP_S = 900
SIM_S = 3600
SEEDS = [1, 2, 3]
AVENUE = "Antônio Carlos"
SCENARIO_KMH = 50
# Radar 331 ("oposto ao nº 8.281") has coordinates ~3 km off the avenue; its pair 338
# ("nº 8.271") marks the real spot (see docs/data_audit.md).
COORD_FIX = {331: 338}


def sumo_home() -> Path:
    import sumo

    return Path(sumo.SUMO_HOME)


def run(cmd: list[str]) -> None:
    env = {**os.environ, "SUMO_HOME": str(sumo_home())}
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")


def work() -> Path:
    return raw_dir("sumo")


def radar_targets() -> pd.DataFrame:
    """Mean weekday vehicles per class at HOUR and median car speed, per radar site x direction."""
    d = processed_dir("radares")
    dim = pd.concat([pd.read_parquet(f) for f in glob.glob(str(d / "*_radars.parquet"))]).drop_duplicates(["id_endereco", "sentido"])
    dim = dim[dim["endereco"].str.contains(AVENUE, na=False)].copy()
    for bad, good in COORD_FIX.items():
        g = dim.loc[dim["id_endereco"] == good, ["lat", "lon"]].iloc[0]
        dim.loc[dim["id_endereco"] == bad, ["lat", "lon"]] = g.values
    agg = pd.concat([pd.read_parquet(f) for f in glob.glob(str(d / "*.parquet")) if not f.endswith("_radars.parquet")])
    a = agg[agg["id_endereco"].isin(dim["id_endereco"]) & (agg["bin"].dt.weekday < 5) & (agg["bin"].dt.hour == HOUR)].copy()
    a["date"] = a["bin"].dt.date
    vol = a.groupby(["id_endereco", "sentido", "classe", "date"])["n"].sum().groupby(["id_endereco", "sentido", "classe"]).mean().unstack(fill_value=0)
    spd = a[a["classe"] == "car"].groupby(["id_endereco", "sentido"])["vel_mean"].median().rename("speed_kmh")
    days = a.groupby(["id_endereco", "sentido"])["date"].nunique().rename("days")
    t = dim.set_index(["id_endereco", "sentido"])[["endereco", "lat", "lon"]].join(vol).join(spd).join(days).reset_index()
    return t.dropna(subset=["speed_kmh"])


def build_network() -> Path:
    w = work()
    net = w / "antonio_carlos.net.xml.gz"
    if not net.exists():
        osm = w / "antonio_carlos.osm"
        if not osm.exists():
            raise FileNotFoundError(f"{osm}: download the OSM extract first (see docs/roadmap.md, F5)")
        b = sumo_home() / "bin"
        # Signals only where OSM has them (the avenue is largely grade-separated), actuated
        # control instead of fixed default cycles; v1 guessed signals and gridlocked.
        run([str(b / "netconvert"), "--osm-files", str(osm), "-o", str(net), "--geometry.remove", "--roundabouts.guess",
             "--ramps.guess", "--junctions.join", "--tls.discard-simple", "--tls.join", "--tls.default-type", "actuated",
             "--keep-edges.components", "1", "--remove-edges.isolated", "--output.street-names",
             "--osm.speedlimit-none", "60"])
    return net


def match_edges(net_path: Path, t: pd.DataFrame) -> pd.DataFrame:
    import sumolib

    net = sumolib.net.readNet(str(net_path))
    out = []
    for r in t.itertuples():
        x, y = net.convertLonLat2XY(r.lon, r.lat)
        southbound = r.sentido.startswith("Bairro")
        best = None
        for e, dist in net.getNeighboringEdges(x, y, 120):
            if AVENUE not in (e.getName() or ""):
                continue
            (x0, y0), (x1, y1) = e.getShape()[0], e.getShape()[-1]
            if (y1 < y0) != southbound:
                continue
            if best is None or dist < best[1]:
                best = (e.getID(), dist, e.getLaneNumber())
        out.append({"edge": best[0] if best else None, "match_m": best[1] if best else None, "lanes": best[2] if best else None})
    return pd.concat([t.reset_index(drop=True), pd.DataFrame(out)], axis=1)


def write_counts(t: pd.DataFrame, path: Path) -> None:
    root = ET.Element("data")
    iv = ET.SubElement(root, "interval", id="h", begin="0", end=str(SIM_S + WARMUP_S))
    for r in t.dropna(subset=["edge"]).itertuples():
        total = getattr(r, "car", 0) + getattr(r, "motorcycle", 0) + getattr(r, "truck_bus", 0)
        # Warm-up period gets the same hourly rate.
        ET.SubElement(iv, "edge", id=r.edge, entered=str(int(round(total * (SIM_S + WARMUP_S) / 3600))))
    ET.ElementTree(root).write(path)


def write_vtypes(t: pd.DataFrame, path: Path) -> dict:
    tot = t[["car", "motorcycle", "truck_bus"]].sum()
    share = (tot / tot.sum()).round(4).to_dict()
    root = ET.Element("additional")
    dist = ET.SubElement(root, "vTypeDistribution", id="mix")
    ET.SubElement(dist, "vType", id="car", vClass="passenger", speedFactor="normc(1,0.1,0.6,1.4)", probability=str(share["car"]))
    ET.SubElement(dist, "vType", id="moto", vClass="motorcycle", speedFactor="normc(1.05,0.12,0.6,1.5)", probability=str(share["motorcycle"]))
    ET.SubElement(dist, "vType", id="truck_bus", vClass="truck", speedFactor="normc(0.95,0.08,0.6,1.2)", probability=str(share["truck_bus"]))
    ET.ElementTree(root).write(path)
    return share


MIN_AVENUE_M = 1000


def filter_corridor_routes(net_path: Path, src: Path, dst: Path) -> int:
    import sumolib

    net = sumolib.net.readNet(str(net_path))
    on_avenue = {e.getID(): e.getLength() for e in net.getEdges() if AVENUE in (e.getName() or "")}
    root = ET.parse(src).getroot()
    out = ET.Element("routes")
    n = 0
    for veh in root.iter("vehicle"):
        r = veh.find("route")
        if r is None:
            continue
        edges = r.get("edges", "").split()
        if sum(on_avenue.get(e, 0) for e in edges) < MIN_AVENUE_M:
            continue
        # Cut to the avenue span: vehicles are inserted on the (multi-lane) avenue itself.
        # v2 started them on single-lane side streets and insertion queued for ~20 min,
        # starving the avenue. Side-street merges become insertions: a stated simplification.
        idx = [i for i, e in enumerate(edges) if e in on_avenue]
        edges = edges[idx[0]: idx[-1] + 1]
        ET.SubElement(out, "route", id=f"c{n}", edges=" ".join(edges))
        n += 1
    ET.ElementTree(out).write(dst)
    return n


def build_demand(net: Path, t: pd.DataFrame) -> Path:
    w = work()
    tools = sumo_home() / "tools"
    cand = w / "candidates.rou.xml"
    if not cand.exists():
        run([sys.executable, str(tools / "randomTrips.py"), "-n", str(net), "-o", str(w / "trips.xml"), "-r", str(cand),
             "-e", "40000", "-p", "0.5", "--fringe-factor", "20", "--min-distance", "1500", "--seed", "42",
             "--validate", "--remove-loops"])
    # Keep only candidate routes that use the avenue for at least MIN_AVENUE_M: the
    # pilot models corridor traffic, not the whole network around it.
    corridor = w / "candidates_corridor.rou.xml"
    filter_corridor_routes(net, cand, corridor)
    cand = corridor
    counts = w / "counts.xml"
    write_counts(t, counts)
    sampled = w / "sampled.rou.xml"
    run([sys.executable, str(tools / "routeSampler.py"), "-r", str(cand), "-d", str(counts), "-o", str(sampled),
         "--attributes", 'type="mix" departLane="best" departSpeed="max"', "--optimize", "full", "--seed", "42",
         "-b", "0", "-e", str(SIM_S + WARMUP_S)])
    return sampled


def simulate(net: Path, routes: Path, vtypes: Path, seed: int, limit_kmh: float | None, tag: str) -> Path:
    import traci

    w = work()
    edgedata = w / f"edgedata_{tag}_{seed}.xml"
    add = w / f"edgedata_{tag}_{seed}.add.xml"
    add.write_text(f'<additional><edgeData id="ed" file="{edgedata.name}" begin="{WARMUP_S}" end="{WARMUP_S + SIM_S}" excludeEmpty="true"/></additional>')
    trip = w / f"tripinfo_{tag}_{seed}.xml"
    cmd = [str(sumo_home() / "bin" / "sumo"), "-n", str(net), "-r", str(routes), "-a", f"{vtypes},{add}",
           "--seed", str(seed), "--begin", "0", "--end", str(WARMUP_S + SIM_S + 1800), "--tripinfo-output", str(trip),
           "--no-step-log", "true", "--no-warnings", "true", "--time-to-teleport", "300", "--ignore-route-errors", "true"]
    traci.start(cmd)
    if limit_kmh is not None:
        for e in traci.edge.getIDList():
            if e.startswith(":"):
                continue
            if AVENUE in (traci.edge.getStreetName(e) or ""):
                traci.edge.setMaxSpeed(e, limit_kmh / 3.6)
    while traci.simulation.getMinExpectedNumber() > 0 and traci.simulation.getTime() < WARMUP_S + SIM_S + 1800:
        traci.simulationStep()
    traci.close()
    return edgedata


def read_edge_speeds(path: Path) -> dict[str, tuple[float, float]]:
    out = {}
    for e in ET.parse(path).getroot().iter("edge"):
        if "speed" in e.attrib:
            out[e.get("id")] = (float(e.get("speed")) * 3.6, float(e.get("entered", 0)))
    return out


def corridor_time(net_path: Path, edgedata: Path) -> float:
    """Travel time (s) along the avenue edges, summed over both directions, from mean edge speeds."""
    import sumolib

    net = sumolib.net.readNet(str(net_path))
    sp = read_edge_speeds(edgedata)
    tt = 0.0
    for e in net.getEdges():
        if AVENUE in (e.getName() or "") and e.getID() in sp and sp[e.getID()][0] > 0:
            tt += e.getLength() / (sp[e.getID()][0] / 3.6)
    return tt


def main() -> None:
    net = build_network()
    t = match_edges(net, radar_targets())
    w = work()
    vtypes = w / "vtypes.add.xml"
    share = write_vtypes(t, vtypes)
    routes = build_demand(net, t)
    res: dict = {"hour": HOUR, "seeds": SEEDS, "mix": share, "sites": [], "scenario_kmh": SCENARIO_KMH}
    runs = {"base": [], "limit50": []}
    for seed in SEEDS:
        runs["base"].append(simulate(net, routes, vtypes, seed, None, "base"))
        runs["limit50"].append(simulate(net, routes, vtypes, seed, SCENARIO_KMH, "limit50"))
    sims = {k: [read_edge_speeds(p) for p in v] for k, v in runs.items()}
    for r in t.itertuples():
        if not r.edge:
            continue
        row = {"id": int(r.id_endereco), "sentido": r.sentido, "edge": r.edge, "match_m": round(r.match_m, 1),
               "radar_veh_h": round(r.car + r.motorcycle + r.truck_bus), "radar_speed": round(r.speed_kmh, 1), "radar_days": int(r.days)}
        for k, lst in sims.items():
            v = [s[r.edge] for s in lst if r.edge in s]
            row[f"{k}_speed"] = round(float(np.mean([x[0] for x in v])), 1) if v else None
            row[f"{k}_veh_h"] = round(float(np.mean([x[1] for x in v]))) if v else None
        res["sites"].append(row)
    s = pd.DataFrame(res["sites"]).dropna(subset=["base_speed"])
    res["validation"] = {
        "speed_mae_kmh": float((s["base_speed"] - s["radar_speed"]).abs().mean()),
        "speed_bias_kmh": float((s["base_speed"] - s["radar_speed"]).mean()),
        "count_geh_mean": float(np.mean([math.sqrt(2 * (a - b) ** 2 / max(a + b, 1)) for a, b in zip(s["base_veh_h"], s["radar_veh_h"])])),
    }
    tb = [corridor_time(net, p) for p in runs["base"]]
    tl = [corridor_time(net, p) for p in runs["limit50"]]
    res["corridor_time_s"] = {"base": float(np.mean(tb)), "limit50": float(np.mean(tl)),
                              "delta_s": float(np.mean(tl) - np.mean(tb)), "seeds_base": tb, "seeds_limit50": tl}
    # Mean speed change at radar edges, fed to the Power Model for the safety side.
    res["radar_edges_mean_speed"] = {"base": float(s["base_speed"].mean()), "limit50": float(s["limit50_speed"].mean())}
    out = processed_dir("sim") / "sumo_antonio_carlos.json"
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False), "utf-8")
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
