// Mirrors src/styles/tokens.css. GSAP takes seconds.
export const DUR = {
  micro: 0.18,
  standard: 0.32,
  theme: 0.25,
  section: 0.6,
  cinematic: 0.9,
} as const;

export const STAGGER = 0.06;

// Built-in GSAP eases closest to the CSS curves (no extra plugin).
export const EASE = {
  out: "power2.out", // ~ cubic-bezier(0,0,.5,1)
  outQuart: "power3.out", // ~ ease-out-quart
  inOut: "power2.inOut", // camera, scrubbed progress
  exit: "power2.in",
} as const;

export const REDUCED = "(prefers-reduced-motion: reduce)";
export const FULL = "(prefers-reduced-motion: no-preference)";

export const prefersReduced = () => window.matchMedia(REDUCED).matches;

export const shift = (size: "sm" | "md" | "lg") => {
  const mobile = window.matchMedia("(max-width: 768px)").matches;
  return { sm: 8, md: mobile ? 12 : 16, lg: mobile ? 20 : 32 }[size];
};
