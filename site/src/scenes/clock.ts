import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { WEEKDAYS_SHORT, DICT, type Ctx } from "../i18n";
import { ramp } from "../lib/color";
import { DUR, EASE, STAGGER } from "../motion/tokens";

let cells: HTMLElement[][] = [];
let rowLabels: HTMLElement[] = [];
let note: HTMLElement;
let state = -1;
let reduced = false;
let primer = { w: 0, h: 8 };

export function buildClock(c: Ctx) {
  const grid = document.querySelector<HTMLElement>("[data-heatmap]")!;
  const m = c.d.clock.weekday_hour;
  const max = Math.max(...m.flat());
  const color = ramp("#E4DED4", "#C46A00");
  primer = { w: 0, h: c.f.amPeak };

  cells = [];
  rowLabels = [];
  m.forEach((row) => {
    const lab = document.createElement("span");
    lab.className = "heatmap__rowlabel";
    grid.appendChild(lab);
    rowLabels.push(lab);
    cells.push(
      row.map((n) => {
        const cell = document.createElement("span");
        cell.className = "heatmap__cell";
        cell.style.background = color((n / max) ** 0.85);
        grid.appendChild(cell);
        return cell;
      }),
    );
  });
  grid.appendChild(document.createElement("span"));
  for (let h = 0; h < 24; h++) {
    const s = document.createElement("span");
    s.className = "heatmap__hour";
    s.textContent = h % 3 === 0 ? String(h) : "";
    grid.appendChild(s);
  }
  note = document.createElement("p");
  note.className = "heatmap__note";
  note.setAttribute("aria-live", "polite");
  grid.appendChild(note);
}

export function clockText(c: Ctx) {
  rowLabels.forEach((l, i) => (l.textContent = WEEKDAYS_SHORT[c.lang][i]));
  // Hidden table: the values colour alone cannot carry.
  const t = document.querySelector<HTMLTableElement>("[data-heatmap-table]")!;
  const hours = Array.from({ length: 24 }, (_, h) => `<th scope="col">${h}h</th>`).join("");
  const rows = c.d.clock.weekday_hour
    .map((r, w) => `<tr><th scope="row">${WEEKDAYS_SHORT[c.lang][w]}</th>${r.map((n) => `<td>${c.num(n)}</td>`).join("")}</tr>`)
    .join("");
  t.innerHTML = `<caption>${DICT[c.lang]["clock.tableCaption"](c)}</caption><tr><td></td>${hours}</tr>${rows}`;
  setNote(c);
}

let lastCtx: Ctx;
function setNote(c: Ctx) {
  lastCtx = c;
  const wd = WEEKDAYS_SHORT[c.lang];
  const m = c.d.clock.weekday_hour;
  const unit = c.lang === "pt" ? "sinistros" : "crashes";
  const hh = (h: number) => (c.lang === "pt" ? `${h}h` : `${h}:00`);
  const fmt = (w: number, h: number) => `${wd[w]} ${hh(h)} · ${c.num(m[w][h])} ${unit}`;
  const peaks = c.lang === "pt" ? `Picos: ${c.f.amPeak}h e ${c.f.pmPeak}h` : `Peaks: ${c.f.amPeak}:00 and ${c.f.pmPeak}:00`;
  note.textContent =
    state <= 0 ? fmt(primer.w, primer.h) : state === 1 ? peaks : fmt(c.f.worst.weekday, c.f.worst.hour);
}

function setState(i: number) {
  if (i === state) return;
  const prev = state;
  state = i;
  const f = lastCtx.f;
  const all = cells.flat();
  const p = cells[primer.w][primer.h];
  const peak = cells[f.worst.weekday][f.worst.hour];
  p.classList.toggle("is-primer", i === 0);
  peak.classList.toggle("is-peak", i === 2);
  setNote(lastCtx);
  if (reduced) return;
  if (i === 0) {
    gsap.to(all.filter((x) => x !== p), { opacity: 0.12, duration: DUR.standard, ease: EASE.out, overwrite: true });
    gsap.to(p, { opacity: 1, duration: DUR.standard, overwrite: true });
  } else if (prev <= 0) {
    // Rows fill weekday by weekday, Monday first.
    cells.forEach((row, w) =>
      gsap.to(row, { opacity: 1, duration: DUR.section, ease: EASE.outQuart, delay: w * STAGGER * 1.5, stagger: 0.008, overwrite: true }),
    );
  }
}

export function clockMotion(isReduced: boolean) {
  reduced = isReduced;
  state = -1;
  if (reduced) gsap.set(cells.flat(), { opacity: 1 });
  setState(0);
  const steps = gsap.utils.toArray<HTMLElement>("#clock .step");
  steps.forEach((s, i) =>
    ScrollTrigger.create({
      trigger: s,
      start: "top 55%",
      end: "bottom 55%",
      onToggle: (self) => {
        s.classList.toggle("is-active", self.isActive);
        if (self.isActive) setState(i);
      },
    }),
  );
}
