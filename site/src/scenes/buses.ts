import { gsap } from "gsap";
import type { BusSnapshot } from "../lib/data";
import { prefersReduced } from "../motion/tokens";

// A single real snapshot, drawn once. Dots never move between positions
// they did not report (no fake liveness).
let canvas: HTMLCanvasElement;
let pts: [number, number, number][] = [];
let bounds: [number, number, number, number] = [0, 1, 0, 1];
const progress = { p: 0 };

export function buildBuses(snap: BusSnapshot | null) {
  canvas = document.querySelector<HTMLCanvasElement>("[data-buscanvas]")!;
  if (!snap) {
    canvas.style.display = "none";
    return;
  }
  // Deterministic shuffle so the fade-in reads as spatially even.
  pts = snap.points
    .map((p, i) => ({ p, k: Math.sin(i * 12.9898) * 43758.5453 }))
    .sort((a, b) => (a.k % 1) - (b.k % 1))
    .map((x) => x.p);
  // Frame on the 1st-99th percentile so a few far-flung garages don't shrink the city.
  const pct = (a: number[], q: number) => [...a].sort((m, n) => m - n)[Math.floor(q * (a.length - 1))];
  const lons = pts.map((p) => p[0]);
  const lats = pts.map((p) => p[1]);
  bounds = [pct(lons, 0.01), pct(lons, 0.99), pct(lats, 0.01), pct(lats, 0.99)];
  new ResizeObserver(() => draw()).observe(canvas);
}

function draw() {
  if (!pts.length) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (!w || !h) return;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  const ctx = canvas.getContext("2d")!;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);

  const [x0, x1, y0, y1] = bounds;
  const kx = Math.cos(((y0 + y1) / 2) * (Math.PI / 180));
  const pad = 12;
  const s = Math.min((w - 2 * pad) / ((x1 - x0) * kx), (h - 2 * pad) / (y1 - y0));
  const ox = (w - (x1 - x0) * kx * s) / 2;
  const oy = (h - (y1 - y0) * s) / 2;

  const n = Math.round(pts.length * progress.p);
  ctx.fillStyle = getComputedStyle(canvas).getPropertyValue("--text-inv-muted").trim() || "#a79f94";
  ctx.globalAlpha = 0.85;
  for (let i = 0; i < n; i++) {
    const [lon, lat] = pts[i];
    ctx.beginPath();
    ctx.arc(ox + (lon - x0) * kx * s, oy + (y1 - lat) * s, 1.6, 0, Math.PI * 2);
    ctx.fill();
  }
}

export function busesMotion() {
  if (!pts.length) return;
  if (prefersReduced()) {
    progress.p = 1;
    draw();
    return;
  }
  progress.p = 0;
  draw();
  // Tween-bound trigger: completes immediately when the page loads past it.
  gsap.to(progress, {
    p: 1,
    duration: 1.2,
    ease: "power1.inOut",
    onUpdate: draw,
    scrollTrigger: { trigger: canvas, start: "top 75%", once: true },
  });
}
