import { gsap } from "gsap";
import type { Ctx } from "../i18n";
import { DUR, EASE, shift } from "../motion/tokens";

const num = () => document.querySelector<HTMLElement>("[data-count]")!;

export function heroText(c: Ctx) {
  num().textContent = c.num(c.d.summary.crashes_last_year);
}

/** Entrance: lines rise in sequence, the number counts up. Never blocks the CTA. */
export function heroMotion(getCtx: () => Ctx) {
  const lines = gsap.utils.toArray<HTMLElement>("[data-hero-line]");
  const target = getCtx().d.summary.crashes_last_year;
  const counter = { v: 0 };
  const tl = gsap.timeline({ defaults: { ease: EASE.outQuart } });
  tl.from(lines, { opacity: 0, y: shift("md"), duration: DUR.section, stagger: 0.08 });
  tl.to(
    counter,
    {
      v: target,
      duration: DUR.cinematic * 1.4,
      ease: "power2.out",
      onUpdate: () => {
        num().textContent = getCtx().num(Math.round(counter.v));
      },
      onComplete: () => heroText(getCtx()),
    },
    0.2,
  );
  return tl;
}
