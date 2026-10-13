import { gsap } from "gsap";
import { ROAD_USERS, type Ctx } from "../i18n";
import { DUR, EASE, STAGGER } from "../motion/tokens";

export function whoText(c: Ctx) {
  const list = document.querySelector<HTMLOListElement>("[data-bars]")!;
  const entries = Object.entries(c.d.vehicles.deaths_by_road_user)
    .filter(([k]) => k !== "other")
    .sort((a, b) => b[1] - a[1]);
  const max = entries[0][1];
  list.innerHTML = entries
    .map(
      ([k, n]) => `<li class="bar${k === "motorcycle" ? " bar--accent" : ""}">
        <span class="bar__label">${ROAD_USERS[c.lang][k] ?? k}</span>
        <span class="bar__track" aria-hidden="true"><span class="bar__fill" style="width:${((n / max) * 100).toFixed(1)}%"></span></span>
        <span class="bar__value">${c.num(n)}</span>
      </li>`,
    )
    .join("");
}

export function whoMotion() {
  const fills = gsap.utils.toArray<HTMLElement>("[data-bars] .bar__fill");
  gsap.from(fills, {
    scaleX: 0,
    duration: DUR.section,
    ease: EASE.outQuart,
    // The accent (largest, first) bar draws last.
    stagger: { each: STAGGER * 1.5, from: "end" },
    scrollTrigger: { trigger: "[data-bars]", start: "top 70%", once: true },
  });
}
