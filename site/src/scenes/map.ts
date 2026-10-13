import { ScrollTrigger } from "gsap/ScrollTrigger";
import type { Map as MLMap } from "maplibre-gl";
import { DICT, regionalStep, type Ctx } from "../i18n";
import { loadHexes, type Regional } from "../lib/data";
import { rampStops } from "../lib/color";
import { DUR, prefersReduced } from "../motion/tokens";

const STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
// Background-only fallback if the basemap host is unreachable: hexes still render.
const FALLBACK_STYLE = { version: 8 as const, sources: {}, layers: [{ id: "bg", type: "background" as const, paint: { "background-color": "#14120f" } }] };
const OVERVIEW = { center: [-43.955, -19.885] as [number, number], zoom: 10.9 };
const TOUR_SIZE = 5;

interface Chapter { kind: "intro" | "regional" | "outro"; r?: Regional }

let chapters: Chapter[] = [];
let map: MLMap | null = null;
let current = 0;

export function buildMap(c: Ctx) {
  chapters = [
    { kind: "intro" },
    ...c.d.regionals.slice(0, TOUR_SIZE).map((r) => ({ kind: "regional" as const, r })),
    { kind: "outro" },
  ];
  const host = document.querySelector<HTMLElement>("[data-map-steps]")!;
  host.innerHTML = chapters
    .map((_, i) => `<div class="mapstep" data-chapter="${i}"><p class="mapstep__card"></p></div>`)
    .join("");

  const legend = document.querySelector<HTMLElement>("[data-map-legend]")!;
  const stops = rampStops("#2A2621", "#F2A516", 5);
  legend.innerHTML = `<span data-l="lo"></span><i style="background:linear-gradient(90deg,${stops.join(",")})"></i><span data-l="hi"></span>`;
}

export function mapText(c: Ctx) {
  const t = DICT[c.lang];
  document.querySelectorAll<HTMLElement>("[data-chapter]").forEach((el, i) => {
    const ch = chapters[i];
    const p = el.querySelector("p")!;
    if (ch.kind === "intro") p.textContent = t["map.intro"](c);
    else if (ch.kind === "outro") p.textContent = t["map.outro"](c);
    else {
      const [name, ...rest] = regionalStep(c, ch.r!).split(":");
      p.innerHTML = `<strong>${name}</strong>:${rest.join(":")}`;
    }
  });
  const legend = document.querySelector<HTMLElement>("[data-map-legend]")!;
  legend.querySelector('[data-l="lo"]')!.textContent = t["map.legendLow"](c);
  legend.querySelector('[data-l="hi"]')!.textContent = t["map.legendHigh"](c);
}

async function initMap() {
  const container = document.querySelector<HTMLElement>("[data-map]")!;
  try {
    const [{ default: maplibregl }, hexes] = await Promise.all([
      import("maplibre-gl"),
      loadHexes(),
      import("maplibre-gl/dist/maplibre-gl.css"),
    ]);
    const style = await fetch(STYLE).then((r) => (r.ok ? r.json() : FALLBACK_STYLE)).catch(() => FALLBACK_STYLE);
    map = new maplibregl.Map({
      container,
      style,
      center: OVERVIEW.center,
      zoom: OVERVIEW.zoom,
      interactive: false, // narrative map: never traps page scroll
      attributionControl: { compact: true },
      fadeDuration: 0,
    });
    map.on("load", () => {
      if (!map) return;
      const firstSymbol = map.getStyle().layers.find((l) => l.type === "symbol")?.id;
      const ns = hexes.features.map((f) => f.properties.n).sort((a, b) => a - b);
      const q = (p: number) => ns[Math.floor(p * (ns.length - 1))];
      const stops = rampStops("#2A2621", "#F2A516", 5);
      const breaks = [q(0.2), q(0.5), q(0.8), q(0.95), q(1)];
      const colorExpr: unknown[] = ["interpolate", ["linear"], ["get", "n"]];
      breaks.forEach((b, i) => colorExpr.push(b + i * 1e-6, stops[i]));
      map.addSource("hex", { type: "geojson", data: hexes as GeoJSON.FeatureCollection });
      map.addLayer(
        { id: "hex-fill", type: "fill", source: "hex", paint: { "fill-color": colorExpr as never, "fill-opacity": 0.85 } },
        firstSymbol,
      );
      // Style-spec transition; typed loosely in maplibre's TS defs.
      map.setPaintProperty("hex-fill", "fill-opacity-transition", { duration: prefersReduced() ? 0 : DUR.section * 1000, delay: 0 });
      map.addLayer(
        { id: "hex-top", type: "line", source: "hex", filter: ["==", ["get", "h3"], ""], paint: { "line-color": "#F3EFE8", "line-width": 2 } },
        firstSymbol,
      );
      go(current, true);
    });
  } catch (err) {
    console.warn("[map] unavailable:", err);
    container.textContent = "";
  }
}

function go(i: number, instant = false) {
  current = i;
  if (!map || !map.isStyleLoaded() || !map.getLayer("hex-fill")) return;
  const ch = chapters[i];
  const mobile = window.matchMedia("(max-width: 750px)").matches;
  const cam =
    ch.kind === "regional"
      ? { center: ch.r!.center, zoom: mobile ? 12 : 12.6 }
      : { center: OVERVIEW.center, zoom: mobile ? 9.9 : OVERVIEW.zoom };
  if (instant || prefersReduced()) map.jumpTo(cam);
  else map.easeTo({ ...cam, duration: DUR.cinematic * 1000, easing: (t) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2) });

  const reg = ch.kind === "regional" ? ch.r!.regional : null;
  map.setPaintProperty("hex-fill", "fill-opacity", reg ? ["case", ["==", ["get", "regional"], reg], 0.9, 0.22] : 0.85);
  map.setFilter("hex-top", ["==", ["get", "h3"], reg ? ch.r!.top_cell : ""]);
}

export function mapMotion() {
  // Lazy-init one viewport ahead of the scene. Callbacks don't fire for a trigger
  // the page loaded past (deep link), so also check progress after creation.
  let started = false;
  const start = () => {
    if (started) return;
    started = true;
    void initMap();
  };
  const lazy = ScrollTrigger.create({ trigger: "#map", start: "top bottom+=100%", onEnter: start, onEnterBack: start });
  if (lazy.progress > 0) start();
  document.querySelectorAll<HTMLElement>("[data-chapter]").forEach((el, i) =>
    ScrollTrigger.create({
      trigger: el,
      start: "top 60%",
      end: "bottom 60%",
      onToggle: (self) => self.isActive && go(i),
    }),
  );
}
