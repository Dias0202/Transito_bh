import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { EVENT_LABELS, type Ctx } from "../i18n";
import type { EffectRow } from "../lib/data";
import { DUR, EASE, STAGGER } from "../motion/tokens";

// Every marker starts on "1 = a comparable hour" and travels to its estimated
// rate ratio when its group is reached: one persistent object per event, so the
// scale itself carries the story (rain right, holidays left, matches stay put).
const GROUPS = [["rain_any", "first_rain"], ["holiday", "carnaval", "optional_day", "day_after_holiday"], ["match"]];
const LO = 0.5;
const HI = 1.5;
export const xPct = (v: number) => (100 * (Math.log(v) - Math.log(LO))) / (Math.log(HI) - Math.log(LO));

interface Row { e: EffectRow; li: HTMLElement; slider: HTMLElement; ci: HTMLElement; value: HTMLElement; label: HTMLElement; group: number }

let rows: Row[] = [];
let state = -1;
let reduced = false;

export function buildRain(events: EffectRow[] | undefined) {
  const scene = document.querySelector<HTMLElement>("#rain")!;
  if (!events?.length) {
    scene.hidden = true;
    document.querySelector('.nav__links a[href="#rain"]')?.parentElement?.setAttribute("hidden", "");
    return;
  }
  const list = document.querySelector<HTMLOListElement>("[data-effects]")!;
  const byId = new Map(events.map((e) => [e.event, e]));
  rows = [];
  GROUPS.forEach((ids, group) =>
    ids.forEach((id) => {
      const e = byId.get(id);
      if (!e) return;
      const li = document.createElement("li");
      li.className = "fx";
      li.dataset.group = String(group);
      li.innerHTML = `<span class="fx__label"></span>
        <span class="fx__track" aria-hidden="true">
          <span class="fx__ci" style="left:${xPct(e.ci_low)}%;width:${xPct(e.ci_high) - xPct(e.ci_low)}%"></span>
          <span class="fx__slider"><i class="fx__dot"></i></span>
        </span>
        <span class="fx__value num"></span>`;
      list.appendChild(li);
      rows.push({
        e, li, group,
        label: li.querySelector(".fx__label")!,
        ci: li.querySelector(".fx__ci")!,
        slider: li.querySelector(".fx__slider")!,
        value: li.querySelector(".fx__value")!,
      });
    }),
  );
  const axis = document.createElement("li");
  axis.className = "fx fx--axis";
  axis.setAttribute("aria-hidden", "true");
  axis.innerHTML = `<span></span><span class="fx__track">${[0.5, 0.7, 1, 1.4]
    .map((v) => `<b style="left:${xPct(v)}%">${String(v)}</b>`)
    .join("")}</span><span></span>`;
  list.appendChild(axis);
  list.closest("figure")!.style.setProperty("--one", `${xPct(1)}%`);
}

const change = (c: Ctx, irr: number) => {
  const d = Math.round((irr - 1) * 100);
  return `${d > 0 ? "+" : d < 0 ? "−" : "±"}${c.num(Math.abs(d))}%`;
};
const significant = (e: EffectRow) => e.ci_low > 1 || e.ci_high < 1;

export function rainText(c: Ctx) {
  for (const r of rows) {
    r.label.textContent = EVENT_LABELS[c.lang][r.e.event] ?? r.e.event;
    // The value is in the DOM from the start (screen readers get every number);
    // only its visibility is choreographed.
    const ci = `${c.num(r.e.ci_low, 2)}–${c.num(r.e.ci_high, 2)}`;
    r.value.textContent = significant(r.e) ? change(c, r.e.irr) : "≈ 0";
    r.value.setAttribute("aria-label", `${change(c, r.e.irr)} (IC 95% ${ci})`);
  }
}

function setState(i: number) {
  if (i === state) return;
  state = i;
  for (const r of rows) {
    const reached = r.group <= i;
    r.li.classList.toggle("is-current", r.group === i);
    r.li.classList.toggle("is-reached", reached);
    r.li.classList.toggle("is-up", reached && significant(r.e) && r.e.irr > 1);
    r.li.classList.toggle("is-down", reached && significant(r.e) && r.e.irr < 1);
    const x = reached ? xPct(r.e.irr) : xPct(1);
    if (reduced) {
      gsap.set(r.slider, { xPercent: x });
      gsap.set([r.ci, r.value], { opacity: reached ? 1 : 0 });
      continue;
    }
    const delay = reached && r.group === i ? GROUPS[r.group].indexOf(r.e.event) * STAGGER * 2 : 0;
    gsap.to(r.slider, { xPercent: x, duration: DUR.cinematic, ease: EASE.inOut, delay, overwrite: true });
    gsap.to(r.ci, { opacity: reached ? 1 : 0, duration: DUR.section, ease: EASE.out, delay: reached ? delay + DUR.standard : 0, overwrite: true });
    gsap.to(r.value, { opacity: reached ? 1 : 0, duration: DUR.standard, ease: EASE.out, delay: reached ? delay + DUR.cinematic * 0.6 : 0, overwrite: true });
  }
}

export function rainMotion(isReduced: boolean) {
  if (!rows.length) return;
  reduced = isReduced;
  state = -1;
  gsap.set(rows.map((r) => r.slider), { xPercent: xPct(1) });
  setState(0);
  // On phones the sticky graphic covers the top ~60% of the screen, so a step
  // must activate while its text is still visible below it.
  const line = window.matchMedia("(max-width: 900px)").matches ? "80%" : "55%";
  gsap.utils.toArray<HTMLElement>("#rain .step").forEach((s, i) =>
    ScrollTrigger.create({
      trigger: s,
      start: `top ${line}`,
      end: `bottom ${line}`,
      onToggle: (self) => {
        s.classList.toggle("is-active", self.isActive);
        if (self.isActive) setState(i);
      },
    }),
  );
  // Deep link or restored scroll past the scene: show the final state.
  const end = ScrollTrigger.create({ trigger: "#rain .scrolly__steps", start: `bottom ${line}` });
  if (end.progress > 0) setState(GROUPS.length - 1);
}
