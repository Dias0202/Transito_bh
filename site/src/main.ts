import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/scenes.css";

import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { DICT, makeCtx, type Ctx, type Lang } from "./i18n";
import { loadCore, type Data } from "./lib/data";
import { derive, type Facts } from "./lib/facts";
import { DUR, EASE, FULL, REDUCED, STAGGER, shift } from "./motion/tokens";
import { heroMotion, heroText } from "./scenes/hero";
import { buildDecade, decadeMotion, decadeText } from "./scenes/decade";
import { buildClock, clockMotion, clockText } from "./scenes/clock";
import { buildMap, mapMotion, mapText } from "./scenes/map";
import { whoMotion, whoText } from "./scenes/who";
import { buildBuses, busesMotion } from "./scenes/buses";
import { buildRain, rainMotion, rainText } from "./scenes/rain";
import { buildRisk, riskMotion, riskText } from "./scenes/risk";
import { frontsText, methodText } from "./scenes/content";

gsap.registerPlugin(ScrollTrigger);
// Dev-only handle for inspecting timelines from the console.
if (import.meta.env.DEV) Object.assign(window, { gsap, ScrollTrigger });
// Dev-only: `?reduce-motion` simulates the OS setting (automation browsers can't emulate it).
if (import.meta.env.DEV && new URLSearchParams(location.search).has("reduce-motion")) {
  const real = window.matchMedia.bind(window);
  window.matchMedia = (q: string) =>
    q.includes("prefers-reduced-motion") ? real(/:\s*reduce\b/.test(q) ? "(min-width: 0px)" : "(max-width: 0px)") : real(q);
}

const LANG_KEY = "transito-bh:lang";

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(LANG_KEY);
    if (saved === "pt" || saved === "en") return saved;
  } catch {
    /* storage blocked: fall through */
  }
  return navigator.language?.toLowerCase().startsWith("pt") ? "pt" : "en";
}

let ctx: Ctx;

function applyText(c: Ctx) {
  const t = DICT[c.lang];
  document.documentElement.lang = c.lang === "pt" ? "pt-BR" : "en";
  document.querySelectorAll<HTMLElement>("[data-i18n]").forEach((el) => {
    const fn = t[el.dataset.i18n!];
    if (fn) el.textContent = fn(c);
  });
  document.querySelectorAll<HTMLElement>("[data-i18n-attr]").forEach((el) => {
    const [attr, key] = el.dataset.i18nAttr!.split(":");
    const fn = t[key];
    if (fn) el.setAttribute(attr, fn(c));
  });
  const stamp = document.querySelector<HTMLElement>("[data-bus-stamp]");
  if (stamp) stamp.textContent = t["buses.stamp"](c);
  heroText(c);
  decadeText(c);
  clockText(c);
  mapText(c);
  whoText(c);
  rainText(c);
  riskText(c);
  frontsText(c);
  methodText(c);
}

function setLang(lang: Lang, d: Data, f: Facts) {
  ctx = makeCtx(lang, d, f);
  applyText(ctx);
  try {
    localStorage.setItem(LANG_KEY, lang);
  } catch {
    /* ignore */
  }
  ScrollTrigger.refresh();
}

/** The nav adopts the theme of the scene under the viewport centre (250ms crossfade). */
function themeAndNav() {
  const html = document.documentElement;
  const links = new Map(
    [...document.querySelectorAll<HTMLAnchorElement>(".nav__links a")].map((a) => [a.hash.slice(1), a]),
  );
  document.querySelectorAll<HTMLElement>("[data-scene]").forEach((scene) =>
    ScrollTrigger.create({
      trigger: scene,
      start: "top 50%",
      end: "bottom 50%",
      onToggle: (self) => {
        if (!self.isActive) return;
        html.dataset.theme = scene.dataset.theme;
        links.forEach((a, id) => a.setAttribute("aria-current", String(id === scene.id)));
      },
    }),
  );
  const bar = document.querySelector<HTMLElement>("[data-progress]")!;
  ScrollTrigger.create({
    start: 0,
    end: "max",
    onUpdate: (self) => gsap.set(bar, { scaleX: self.progress }),
  });
}

/** Section headings: motion varies with semantic weight (eyebrow < title < lead). */
function reveals() {
  const groups = gsap.utils.toArray<HTMLElement>("[data-scene]:not(.hero)");
  for (const g of groups) {
    const els = g.querySelectorAll<HTMLElement>("[data-reveal]");
    if (!els.length) continue;
    const dist = (el: HTMLElement) => (el.tagName === "H2" ? shift("lg") : el.classList.contains("eyebrow") ? shift("sm") : shift("md"));
    // Tween-bound trigger (not an onEnter callback): if the page loads already
    // past it (deep link, restored scroll), GSAP renders the end state.
    gsap.fromTo(
      els,
      { opacity: 0, y: (_i: number, el: HTMLElement) => dist(el) },
      {
        opacity: 1,
        y: 0,
        duration: DUR.section,
        ease: EASE.outQuart,
        stagger: STAGGER * 1.5,
        scrollTrigger: { trigger: els[0], start: "top 85%", once: true },
      },
    );
  }
  // ML fronts enter as a group, one after another.
  gsap.from("[data-fronts] .front", {
    opacity: 0,
    y: shift("md"),
    duration: DUR.section,
    ease: EASE.outQuart,
    stagger: STAGGER * 1.5,
    scrollTrigger: { trigger: "[data-fronts]", start: "top 80%", once: true },
  });
}

async function boot() {
  let d: Data;
  try {
    d = await loadCore();
  } catch (err) {
    console.error(err);
    document.querySelector("main")!.insertAdjacentHTML(
      "afterbegin",
      `<p style="padding:96px 16px">Não foi possível carregar os dados. / Could not load data.</p>`,
    );
    return;
  }
  const f = derive(d);
  ctx = makeCtx(initialLang(), d, f);

  buildDecade(d.yearly);
  buildClock(ctx);
  buildMap(ctx);
  buildBuses(d.bus);
  buildRain(d.effects?.events);
  buildRisk(d.risk);
  applyText(ctx);

  document.querySelector("[data-lang-toggle]")!.addEventListener("click", () => {
    setLang(ctx.lang === "pt" ? "en" : "pt", d, f);
  });

  await document.fonts?.ready;
  themeAndNav();
  mapMotion();
  busesMotion();

  const mm = gsap.matchMedia();
  mm.add(FULL, () => {
    heroMotion(() => ctx);
    reveals();
    decadeMotion();
    clockMotion(false);
    whoMotion();
    rainMotion(false);
    riskMotion(false);
  });
  mm.add(REDUCED, () => {
    clockMotion(true);
    rainMotion(true);
    riskMotion(true);
  });

  // In-page links: native smooth scroll unless reduced motion.
  document.querySelectorAll<HTMLAnchorElement>('a[href^="#"]').forEach((a) =>
    a.addEventListener("click", (e) => {
      const target = document.querySelector(a.hash);
      if (!target) return;
      e.preventDefault();
      target.scrollIntoView({ behavior: window.matchMedia(REDUCED).matches ? "auto" : "smooth" });
      history.replaceState(null, "", a.hash);
    }),
  );
}

boot();
