// Aggregates exported by `python -m bhtraffic.export.site`. Real data only.

export interface Summary {
  first_year: number;
  last_year: number;
  recent_window: [number, number];
  people_window?: [number, number];
  complete_through?: string;
  fatal_crashes_last_year?: number;
  crashes_total: number;
  crashes_last_year: number;
  crashes_per_day_last_year: number;
  deaths_total: number;
  deaths_recent: number;
  share_crashes_with_motorcycle_recent: number;
  share_deaths_motorcycle_recent: number;
  share_deaths_pedestrian_recent: number;
  geocode_placeholders_removed: number;
  share_without_coords: number;
  share_hour_informed: number;
}

export interface YearRow { year: number; crashes: number; deaths: number }

export interface Clock { weekday_hour: number[][]; n: number } // [weekday 0=Mon][hour]

export interface Regional {
  regional: string;
  crashes: number;
  fatal_crashes: number;
  top_cell: string;
  top_cell_crashes: number;
  center: [number, number]; // lon, lat
}

export interface Vehicles {
  involved: Record<string, number>;
  deaths_by_road_user: Record<string, number>;
  deaths_pedestrians: number;
  moto_by_year: Record<string, number>;
}

export interface BusSnapshot {
  ts_utc: string;
  ts_brt: string;
  vehicles: number;
  lines: number;
  median_speed_kmh: number;
  share_reporting_under_5kmh: number;
  median_speed_moving_kmh: number;
  points: [number, number, number][]; // lon, lat, speed
}

export interface HexCollection {
  type: "FeatureCollection";
  features: {
    type: "Feature";
    properties: { h3: string; n: number; fatal: number; regional: string | null };
    geometry: { type: "Polygon"; coordinates: number[][][] };
  }[];
}

export interface EffectRow { event: string; irr: number; ci_low: number; ci_high: number }
export interface Effects { hours: number; crashes: number; matches: number; through?: string; events: EffectRow[] }

export interface Risk {
  test_year: number;
  cells: number;
  slots: number;
  crashes: number;
  k: number[]; // share of cell-hours prioritised, 0..0.30
  curves: { model: number[]; cellxprofile: number[] }; // share of crashes captured
  top5: number;
  top10: number;
  top5_simple: number;
  tie_ci_top5: [number, number];
}

export interface WIBand { median: number; lo: number; hi: number }
export interface WhatIf {
  window: string;
  bumps: { effect: number; effect_ci: [number, number]; candidates: number; curve: (WIBand & { n: number; base: number })[] };
  cameras: { sites: number; base: number; all: WIBand; since2024: WIBand };
  first_rain: { hours: number; crashes: number; excess: WIBand; rain_hours: number; rain_excess: WIBand };
}

export interface Data {
  summary: Summary;
  yearly: YearRow[];
  clock: Clock;
  regionals: Regional[];
  vehicles: Vehicles;
  bus: BusSnapshot | null;
  effects: Effects | null;
  risk: Risk | null;
  whatif: WhatIf | null;
}

const base = `${import.meta.env.BASE_URL}data/`;

async function get<T>(name: string): Promise<T> {
  const r = await fetch(`${base}${name}.json`);
  if (!r.ok) throw new Error(`${name}.json: HTTP ${r.status}`);
  return r.json() as Promise<T>;
}

export async function loadCore(): Promise<Data> {
  const [summary, yearly, clock, regionals, vehicles, bus, effects, risk, whatif] = await Promise.all([
    get<Summary>("summary"),
    get<YearRow[]>("yearly"),
    get<Clock>("clock"),
    get<Regional[]>("regionals"),
    get<Vehicles>("vehicles"),
    get<BusSnapshot>("bus").catch(() => null),
    // Model outputs are optional: their scenes hide when a file is missing.
    get<Effects>("effects").catch(() => null),
    get<Risk>("risk").catch(() => null),
    get<WhatIf>("whatif").catch(() => null),
  ]);
  return { summary, yearly, clock, regionals, vehicles, bus, effects, risk, whatif };
}

// Hexes are the largest file; only fetched when the map scene is near.
export const loadHexes = () => get<HexCollection>("hexes");
