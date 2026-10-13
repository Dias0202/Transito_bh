import { gsap } from "gsap";
import type { Ctx } from "../i18n";
import type { YearRow } from "../lib/data";
import { DUR, EASE } from "../motion/tokens";

const NS = "http://www.w3.org/2000/svg";
const W = 640;
const H = 400;
const X0 = 64;
const X1 = 576;

const el = <K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string | number>, parent: Element) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  parent.appendChild(e);
  return e;
};

interface Refs {
  titles: SVGTextElement[];
  endLabels: SVGTextElement[];
  startLabels: SVGTextElement[];
  paths: SVGPathElement[];
  extras: SVGElement[];
}

let refs: Refs | null = null;

export function buildDecade(rows: YearRow[]) {
  const svg = document.querySelector<SVGSVGElement>("[data-linechart]")!;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const x = (i: number) => X0 + ((X1 - X0) * i) / (rows.length - 1);
  const panels = [
    { key: "crashes" as const, top: 36, bottom: 196, cls: "series--crashes" },
    { key: "deaths" as const, top: 256, bottom: 360, cls: "series--deaths" },
  ];
  const r: Refs = { titles: [], endLabels: [], startLabels: [], paths: [], extras: [] };

  for (const p of panels) {
    const vals = rows.map((d) => d[p.key]);
    const lo = Math.min(...vals) * 0.9;
    const hi = Math.max(...vals) * 1.02;
    const y = (v: number) => p.bottom - ((v - lo) / (hi - lo)) * (p.bottom - p.top);
    r.extras.push(el("line", { class: "axis", x1: X0, x2: X1, y1: p.bottom, y2: p.bottom }, svg));
    r.titles.push(el("text", { x: 0, y: p.top - 18, class: p.key === "deaths" ? "label-accent" : "label-strong" }, svg));
    const d = vals.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
    r.paths.push(el("path", { d, class: `series ${p.cls}` }, svg));
    const last = vals.length - 1;
    r.extras.push(el("circle", { cx: x(last), cy: y(vals[last]), r: 4, class: `dot dot--${p.key}` }, svg));
    r.endLabels.push(el("text", { x: x(last) + 10, y: y(vals[last]) + 4, class: p.key === "deaths" ? "label-accent" : "label-strong" }, svg));
    r.extras.push(el("circle", { cx: X0, cy: y(vals[0]), r: 3, class: `dot dot--${p.key}` }, svg));
    r.startLabels.push(el("text", { x: X0 - 10, y: y(vals[0]) + 4, "text-anchor": "end" }, svg));
  }
  // Year ticks: first, minimum-crash year, last.
  const iMin = rows.reduce((m, d, i) => (d.crashes < rows[m].crashes ? i : m), 0);
  for (const i of new Set([0, iMin, rows.length - 1])) {
    r.extras.push(Object.assign(el("text", { x: x(i), y: H - 8, "text-anchor": "middle" }, svg), { textContent: String(rows[i].year) }));
  }
  refs = r;
}

export function decadeText(c: Ctx) {
  if (!refs) return;
  const rows = c.d.yearly;
  const first = rows[0];
  const last = rows[rows.length - 1];
  refs.titles[0].textContent = c.lang === "pt" ? "Sinistros com vítima" : "Injury crashes";
  refs.titles[1].textContent = c.lang === "pt" ? "Sinistros com morte" : "Fatal crashes";
  refs.endLabels[0].textContent = c.num(last.crashes);
  refs.endLabels[1].textContent = c.num(last.deaths);
  refs.startLabels[0].textContent = c.num(first.crashes);
  refs.startLabels[1].textContent = c.num(first.deaths);
}

export function decadeMotion() {
  if (!refs) return;
  const { paths, endLabels, startLabels, extras } = refs;
  for (const p of paths) {
    const len = p.getTotalLength();
    gsap.set(p, { strokeDasharray: len, strokeDashoffset: len });
  }
  const labels = [...endLabels, ...startLabels, ...extras.filter((e) => e.tagName === "circle")];
  gsap.set(labels, { opacity: 0 });
  gsap
    .timeline({ scrollTrigger: { trigger: "#decade .linechart", start: "top 75%", once: true } })
    .to(paths, { strokeDashoffset: 0, duration: DUR.cinematic * 1.6, ease: EASE.inOut, stagger: 0.25 })
    .to(labels, { opacity: 1, duration: DUR.standard, ease: EASE.out, stagger: 0.04 }, "-=0.35");
}
