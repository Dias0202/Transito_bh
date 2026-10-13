import { gsap } from "gsap";
import type { Ctx } from "../i18n";
import type { Congestion } from "../lib/data";
import { ramp } from "../lib/color";
import { DUR, EASE, STAGGER } from "../motion/tokens";

// One row per radar site: a 24-hour strip of the weekday speed index
// (car speed / night free-flow). Rows are ranked by hours below 0.7.
let data: Congestion | null = null;
let strips: HTMLElement[] = [];

const color = ramp("#E4DED4", "#C46A00");
// 1.0 (free flow) -> lightest; 0.3 or less -> deepest amber.
const shade = (v: number | null) => (v === null ? "transparent" : color(Math.min(1, Math.max(0, (1 - v) / 0.7))));

export function buildCongestion(c: Congestion | null) {
  const scene = document.querySelector<HTMLElement>("#congestion")!;
  if (!c || !c.sites.length) {
    scene.hidden = true;
    document.querySelector('.nav__links a[href="#congestion"]')?.parentElement?.setAttribute("hidden", "");
    return;
  }
  data = c;
  const list = document.querySelector<HTMLOListElement>("[data-cong]")!;
  list.innerHTML = c.sites
    .map(
      (s) => `<li class="cg">
        <span class="cg__name"><b>${s.name}</b><span class="cg__dir">${s.dir}</span></span>
        <span class="cg__strip" aria-hidden="true">${s.strip.map((v) => `<i style="background:${shade(v)}"></i>`).join("")}</span>
        <span class="cg__val num"></span>
      </li>`,
    )
    .join("");
  const axis = document.querySelector<HTMLElement>("[data-cong-axis]")!;
  axis.innerHTML = Array.from({ length: 24 }, (_, h) => `<i>${h % 6 === 0 ? h : ""}</i>`).join("");
  strips = [...list.querySelectorAll<HTMLElement>(".cg__strip")];
}

export function congestionText(c: Ctx) {
  if (!data) return;
  const pt = c.lang === "pt";
  document.querySelectorAll<HTMLElement>("[data-cong] .cg").forEach((li, i) => {
    const s = data!.sites[i];
    const hh = pt ? `${s.worst_hour}h` : `${s.worst_hour}:00`;
    li.querySelector(".cg__val")!.textContent = `${c.pct(s.worst)} · ${hh}`;
    li.setAttribute("aria-label", pt
      ? `${s.where}, sentido ${s.dir}: no pior momento (${hh}) a velocidade cai a ${c.pct(s.worst)} da de fluxo livre; ${s.hours} horas por dia útil abaixo de 70%.`
      : `${s.where}, towards ${s.dir}: at its worst (${hh}) speed falls to ${c.pct(s.worst)} of free flow; ${s.hours} weekday hours below 70%.`);
  });
}

export function congestionMotion(reduced: boolean) {
  if (!data || reduced) return;
  // Strips draw left to right, row after row: the day unrolls for each avenue.
  gsap.fromTo(
    strips,
    { clipPath: "inset(0 100% 0 0)" },
    {
      clipPath: "inset(0 0% 0 0)",
      duration: DUR.cinematic,
      ease: EASE.inOut,
      stagger: STAGGER,
      scrollTrigger: { trigger: "[data-cong]", start: "top 75%", once: true },
    },
  );
}
