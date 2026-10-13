import { gsap } from "gsap";
import type { Ctx } from "../i18n";
import type { Risk } from "../lib/data";
import { EASE } from "../motion/tokens";

const NS = "http://www.w3.org/2000/svg";
const W = 640;
const H = 420;
const X0 = 48;
const X1 = 612;
const Y0 = 380; // y = 0
const Y1 = 24; // y = YMAX
const XMAX = 0.3;
const YMAX = 0.75;

const sx = (k: number) => X0 + (k / XMAX) * (X1 - X0);
const sy = (v: number) => Y0 - (v / YMAX) * (Y0 - Y1);
const el = <K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string | number>, parent: Element) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  parent.appendChild(e);
  return e;
};

interface Refs {
  model: SVGPathElement;
  simple: SVGPathElement;
  chance: SVGPathElement;
  marks: SVGGElement[];
  markLabels: SVGTextElement[];
  axisLabels: SVGTextElement[];
  legend: SVGTextElement[];
}
let refs: Refs | null = null;
let data: Risk | null = null;

const path = (k: number[], v: number[]) => k.map((x, i) => `${i ? "L" : "M"}${sx(x).toFixed(1)},${sy(v[i]).toFixed(1)}`).join("");

export function buildRisk(r: Risk | null) {
  const scene = document.querySelector<HTMLElement>("#risk")!;
  if (!r) {
    scene.hidden = true;
    document.querySelector('.nav__links a[href="#risk"]')?.parentElement?.setAttribute("hidden", "");
    return;
  }
  data = r;
  const svg = document.querySelector<SVGSVGElement>("[data-capture]")!;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  for (const v of [0.25, 0.5, 0.75]) el("line", { class: "grid", x1: X0, x2: X1, y1: sy(v), y2: sy(v) }, svg);
  el("line", { class: "axis", x1: X0, x2: X1, y1: Y0, y2: Y0 }, svg);
  const axisLabels: SVGTextElement[] = [];
  for (const k of [0, 0.1, 0.2, 0.3]) axisLabels.push(el("text", { x: sx(k), y: Y0 + 22, "text-anchor": "middle" }, svg));
  for (const v of [0.25, 0.5, 0.75]) axisLabels.push(el("text", { x: X0 - 8, y: sy(v) + 4, "text-anchor": "end" }, svg));

  const chance = el("path", { d: `M${sx(0)},${sy(0)}L${sx(XMAX)},${sy(XMAX)}`, class: "curve curve--chance" }, svg);
  const simple = el("path", { d: path(r.k, r.curves.cellxprofile), class: "curve curve--simple" }, svg);
  const model = el("path", { d: path(r.k, r.curves.model), class: "curve curve--model" }, svg);

  const marks: SVGGElement[] = [];
  const markLabels: SVGTextElement[] = [];
  for (const [k, v] of [[0.05, r.top5], [0.1, r.top10]] as const) {
    const g = el("g", { class: "mark" }, svg);
    el("line", { class: "guide", x1: sx(k), x2: sx(k), y1: Y0, y2: sy(v) }, g);
    el("line", { class: "guide", x1: X0, x2: sx(k), y1: sy(v), y2: sy(v) }, g);
    el("circle", { cx: sx(k), cy: sy(v), r: 5, class: "mark__dot" }, g);
    markLabels.push(el("text", { x: sx(k) + 12, y: sy(v) - 10, class: "mark__label" }, g));
    marks.push(g);
  }
  const legend = [
    el("text", { x: sx(0.3) - 4, y: sy(0.3) + 22, "text-anchor": "end", class: "legend legend--chance" }, svg),
    el("text", { x: sx(0.3) - 4, y: sy(r.curves.model.at(-1)!) - 12, "text-anchor": "end", class: "legend legend--model" }, svg),
  ];
  refs = { model, simple, chance, marks, markLabels, axisLabels, legend };
}

export function riskText(c: Ctx) {
  if (!refs || !data) return;
  const pt = c.lang === "pt";
  const pct = (x: number) => c.pct(x);
  refs.axisLabels.forEach((t, i) => (t.textContent = i < 4 ? pct([0, 0.1, 0.2, 0.3][i]) : pct([0.25, 0.5, 0.75][i - 4])));
  refs.markLabels[0].textContent = `${pct(0.05)} → ${pct(data.top5)}`;
  refs.markLabels[1].textContent = `${pct(0.1)} → ${pct(data.top10)}`;
  refs.legend[0].textContent = pt ? "acaso" : "chance";
  refs.legend[1].textContent = pt ? "modelo e ranking simples" : "model and simple ranking";
  const t = document.querySelector<HTMLTableElement>("[data-capture-table]")!;
  const head = pt ? ["Lugares-horário priorizados", "Sinistros capturados"] : ["Cell-hours prioritised", "Crashes captured"];
  t.innerHTML = `<caption>${pt ? "Curva de concentração" : "Concentration curve"}, ${data.test_year}</caption>
    <tr><th scope="col">${head[0]}</th><th scope="col">${head[1]}</th></tr>
    ${[0.01, 0.05, 0.1, 0.2, 0.3].map((k) => `<tr><td>${pct(k)}</td><td>${pct(data!.curves.model[Math.round(k * 200)])}</td></tr>`).join("")}`;
}

export function riskMotion(isReduced: boolean) {
  if (!refs) return;
  const { model, simple, chance, marks } = refs;
  if (isReduced) {
    gsap.set([model, simple, chance], { strokeDashoffset: 0, clearProps: "strokeDasharray" });
    gsap.set(marks, { opacity: 1 });
    return;
  }
  for (const p of [model, simple, chance]) {
    const len = p.getTotalLength();
    gsap.set(p, { strokeDasharray: len, strokeDashoffset: len });
  }
  gsap.set(marks, { opacity: 0 });
  // Scrubbed: the curve is drawn by the reader's own scroll, so the pace of the
  // reveal is theirs. Short scroll distance keeps it from feeling like a slideshow.
  gsap
    .timeline({
      defaults: { ease: "none" },
      scrollTrigger: { trigger: "[data-capture]", start: "top 80%", end: "center 45%", scrub: 0.6 },
    })
    .to(chance, { strokeDashoffset: 0, duration: 0.6 }, 0)
    .to([simple, model], { strokeDashoffset: 0, duration: 1 }, 0.1)
    .to(marks, { opacity: 1, duration: 0.25, stagger: 0.1, ease: EASE.out }, 0.95);
}
