// Facts derived from the data in one place, so copy never hardcodes numbers.
import type { Data } from "./data";

export interface Facts {
  years: string; // "2021–2025": crash-level metrics
  peopleYears: string; // "2020–2024": people/vehicle metrics (yearly dataset ends earlier)
  minYear: { year: number; crashes: number };
  lastYear: { year: number; crashes: number; deaths: number }; // deaths = fatal crashes
  prevYear: { year: number; crashes: number; deaths: number };
  deathsHighestSince: number | null; // null => highest of the series
  prevHighestSince: number | null;
  amPeak: number;
  pmPeak: number;
  worst: { weekday: number; hour: number; n: number };
  motoShare: number;
  motoPedShare: number;
}

export function derive(d: Data): Facts {
  const [a, b] = d.summary.recent_window;
  const ys = d.yearly;
  const last = ys[ys.length - 1];
  const minYear = ys.reduce((m, r) => (r.crashes < m.crashes ? r : m), ys[0]);
  const prev = ys[ys.length - 2];
  const highestSince = (row: { year: number; deaths: number }) =>
    [...ys].reverse().find((r) => r.year < row.year && r.deaths >= row.deaths)?.year ?? null;
  const [pa, pb] = d.summary.people_window ?? d.summary.recent_window;

  // Weekday (Mon-Fri) profile by hour.
  const wd = Array.from({ length: 24 }, (_, h) =>
    d.clock.weekday_hour.slice(0, 5).reduce((s, row) => s + row[h], 0),
  );
  const argmax = (from: number, to: number) => {
    let best = from;
    for (let h = from; h <= to; h++) if (wd[h] > wd[best]) best = h;
    return best;
  };

  let worst = { weekday: 0, hour: 0, n: -1 };
  d.clock.weekday_hour.forEach((row, w) =>
    row.forEach((n, h) => {
      if (n > worst.n) worst = { weekday: w, hour: h, n };
    }),
  );

  return {
    years: `${a}–${b}`,
    peopleYears: `${pa}–${pb}`,
    minYear: { year: minYear.year, crashes: minYear.crashes },
    lastYear: last,
    prevYear: prev,
    deathsHighestSince: highestSince(last),
    prevHighestSince: highestSince(prev),
    amPeak: argmax(5, 11),
    pmPeak: argmax(12, 21),
    worst,
    motoShare: d.summary.share_crashes_with_motorcycle_recent,
    motoPedShare: d.summary.share_deaths_motorcycle_recent + d.summary.share_deaths_pedestrian_recent,
  };
}
