import { gsap } from "gsap";
import type { Ctx } from "../i18n";
import type { WhatIf } from "../lib/data";
import { DUR, EASE, prefersReduced } from "../motion/tokens";

// Three scenario cards driven by pre-computed Monte Carlo results (sim/whatif.py).
// Controls only offer values that were actually simulated: no interpolation.

interface Band { lo: number; median: number; hi: number }
interface Card {
  root: HTMLElement;
  value: HTMLElement;
  range: HTMLElement;
  band: HTMLElement;
  mark: HTMLElement;
  zero?: HTMLElement;
  scale: [number, number];
  shown: { v: number };
}

let data: WhatIf | null = null;
let ctx: Ctx;
const cards: Record<string, Card> = {};
let bumpIdx = 3;
let camVariant: "all" | "since2024" = "all";
let rainShare = 50;

const pct = (v: number, [a, b]: [number, number]) => ((v - a) / (b - a)) * 100;

function card(id: string, scale: [number, number]): Card {
  const root = document.querySelector<HTMLElement>(`[data-whatif="${id}"]`)!;
  const c: Card = {
    root,
    value: root.querySelector(".wi__value")!,
    range: root.querySelector(".wi__range")!,
    band: root.querySelector(".wi__band")!,
    mark: root.querySelector(".wi__mark")!,
    zero: root.querySelector<HTMLElement>(".wi__zero") ?? undefined,
    scale,
    shown: { v: 0 },
  };
  if (c.zero) c.zero.style.left = `${pct(0, scale)}%`;
  return c;
}

export function buildWhatIf(w: WhatIf | null) {
  const scene = document.querySelector<HTMLElement>("#whatif")!;
  if (!w) {
    scene.hidden = true;
    document.querySelector('.nav__links a[href="#whatif"]')?.parentElement?.setAttribute("hidden", "");
    return;
  }
  data = w;
  const maxBump = Math.max(...w.bumps.curve.map((x) => x.hi));
  cards.bumps = card("bumps", [0, Math.ceil(maxBump / 50) * 50]);
  const camLo = Math.min(w.cameras.all.lo, w.cameras.since2024.lo);
  const camHi = Math.max(w.cameras.all.hi, w.cameras.since2024.hi);
  cards.cameras = card("cameras", [Math.floor(camLo / 25) * 25, Math.ceil(camHi / 25) * 25]);
  cards.rain = card("rain", [0, Math.ceil(w.first_rain.excess.hi)]);

  const slider = document.querySelector<HTMLInputElement>("[data-bumps-n]")!;
  slider.max = String(w.bumps.curve.length - 1);
  bumpIdx = Math.min(bumpIdx, w.bumps.curve.length - 1);
  slider.value = String(bumpIdx);
  slider.addEventListener("input", () => {
    bumpIdx = Number(slider.value);
    update("bumps");
  });
  document.querySelectorAll<HTMLButtonElement>("[data-cam]").forEach((b) =>
    b.addEventListener("click", () => {
      camVariant = b.dataset.cam as typeof camVariant;
      document.querySelectorAll<HTMLButtonElement>("[data-cam]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      update("cameras");
    }),
  );
  const rs = document.querySelector<HTMLInputElement>("[data-rain-share]")!;
  rs.value = String(rainShare);
  rs.addEventListener("input", () => {
    rainShare = Number(rs.value);
    update("rain");
  });
}

function bandFor(id: string): Band {
  const w = data!;
  if (id === "bumps") return w.bumps.curve[bumpIdx];
  if (id === "cameras") return w.cameras[camVariant];
  const k = rainShare / 100;
  const e = w.first_rain.excess;
  return { lo: e.lo * k, median: e.median * k, hi: e.hi * k };
}

function fmt(v: number) {
  const r = Math.round(v);
  return `${r > 0 ? "" : r < 0 ? "−" : ""}${ctx.num(Math.abs(r))}`;
}

function update(id: string, instant = false) {
  if (!data) return;
  const c = cards[id];
  const b = bandFor(id);
  const t = TEXT[ctx.lang];
  c.range.textContent = t.range(fmt(b.lo), fmt(b.hi));
  const reduced = instant || prefersReduced();
  const x0 = pct(b.lo, c.scale);
  const w = Math.max(0.5, pct(b.hi, c.scale) - x0) / 100;
  const xm = pct(b.median, c.scale);
  if (reduced) {
    c.shown.v = b.median;
    c.value.textContent = fmt(b.median);
    gsap.set(c.band, { xPercent: x0, scaleX: w });
    gsap.set(c.mark, { xPercent: xm });
  } else {
    gsap.to(c.shown, { v: b.median, duration: DUR.standard, ease: EASE.out, overwrite: true, onUpdate: () => { c.value.textContent = fmt(c.shown.v); } });
    gsap.to(c.band, { xPercent: x0, scaleX: w, duration: DUR.standard, ease: EASE.outQuart, overwrite: true });
    gsap.to(c.mark, { xPercent: xm, duration: DUR.standard, ease: EASE.outQuart, overwrite: true });
  }
  const label = c.root.querySelector<HTMLElement>("[data-wi-label]");
  if (label) label.textContent = t.label[id](data, bumpIdx, camVariant, rainShare);
  if (id === "bumps") document.querySelector("[data-bumps-n]")?.setAttribute("aria-valuetext", `${data.bumps.curve[bumpIdx].n}`);
  if (id === "rain") document.querySelector("[data-rain-share]")?.setAttribute("aria-valuetext", `${rainShare}%`);
  document.querySelector(`[data-wi-n="${id}"]`)!.textContent =
    id === "bumps" ? String(data.bumps.curve[bumpIdx].n) : id === "rain" ? `${rainShare}%` : "";
  const crossesZero = b.lo < 0 && b.hi > 0;
  // Cameras stay neutral even when the 90% band clears zero: the 95% CI of the effect does not.
  c.root.classList.toggle("is-uncertain", crossesZero || id === "cameras");
}

const TEXT = {
  pt: {
    range: (a: string, b: string) => `faixa de ${a} a ${b} (90% das simulações)`,
    label: {
      bumps: (w: WhatIf, i: number) =>
        `${w.bumps.curve[i].n} redutores nos pontos de maior sinistralidade em ruas locais, onde acontecem ~${Math.round(w.bumps.curve[i].base)} sinistros por ano a até 100 m.`,
      cameras: (w: WhatIf, _i: number, v: string) =>
        v === "all"
          ? `Radares de volta nos ${w.cameras.sites} pontos ainda sem equipamento. Efeito estimado com todo o período: a faixa inclui zero — não dá para prometer resultado.`
          : `Mesmo cenário, com o efeito estimado só desde 2024 (geocodificação consistente): indício de redução, ainda não confirmado.`,
      rain: (w: WhatIf, _i: number, _v: string, p: number) =>
        `Ações nas ~${Math.round(w.first_rain.hours)} horas por ano de primeira chuva após 3 dias secos, eliminando ${p}% do excesso de sinistros que ela causa.`,
    } as Record<string, (w: WhatIf, i: number, v: string, p: number) => string>,
  },
  en: {
    range: (a: string, b: string) => `range ${a} to ${b} (90% of simulations)`,
    label: {
      bumps: (w: WhatIf, i: number) =>
        `${w.bumps.curve[i].n} speed bumps at the highest-crash places on local streets, where ~${Math.round(w.bumps.curve[i].base)} crashes a year happen within 100 m.`,
      cameras: (w: WhatIf, _i: number, v: string) =>
        v === "all"
          ? `Cameras back at the ${w.cameras.sites} sites still without one. Effect estimated over the whole period: the range includes zero — no result can be promised.`
          : `Same scenario, with the effect estimated only since 2024 (consistent geocoding): a hint of reduction, not confirmed.`,
      rain: (w: WhatIf, _i: number, _v: string, p: number) =>
        `Action during the ~${Math.round(w.first_rain.hours)} hours a year of first rain after 3 dry days, removing ${p}% of the extra crashes it causes.`,
    } as Record<string, (w: WhatIf, i: number, v: string, p: number) => string>,
  },
};

export function whatIfText(c: Ctx) {
  ctx = c;
  if (!data) return;
  for (const id of Object.keys(cards)) update(id, true);
  const s = document.querySelector<HTMLInputElement>("[data-bumps-n]");
  s?.setAttribute("aria-valuetext", `${data.bumps.curve[bumpIdx].n}`);
}

export function whatIfMotion() {
  // Cards reveal with the shared section reveal; values settle once visible.
  if (!data) return;
  for (const id of Object.keys(cards)) update(id, true);
}
