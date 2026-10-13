# Trânsito BH — Design & Motion Spec

Research date: 2026-10-13. Stack: Vite + TypeScript (vanilla) + GSAP ScrollTrigger + MapLibre GL. Bilingual PT-BR / EN.

**Evidence labels.** **OBS** means observed in fetched HTML/CSS or page text. **INF** means inferred from that evidence. **PROP** means a project proposal with no external source. None of the reference sites was watched in a browser, so no claims about how their motion *feels* are made here.

---

## 1. Creative direction: Quiet Precision

- **One idea per viewport.** Each scene makes a single claim, backed by one real number or one chart. The copy is short and declarative, and it ends with a period.
- **The data moves, the page doesn't.** Motion explains a change of state (filled → empty, overview → hotspot, now → forecast). Nothing moves just for decoration.
- **Amber is a signal, not a theme.** It marks the current focus only: the active hexagon, the headline number, the peak hour. Everything else is warm neutral.
- **Light ↔ dark carries meaning.** Light scenes are analysis and reading (clock, vehicle mix, ML, methods). Dark scenes are the city and the street (hero, map, live buses).
- **Honesty is part of the aesthetic.** ML status labels, sources and data gaps get the same typographic care as the headline.

## 2. Reference table

| Reference | Principle to adopt | Motion technique | Scene / component | Adaptation | Evidence |
|---|---|---|---|---|---|
| **Apple AirPods Pro** (apple.com/airpods-pro) | Each section is its own named scroll scene. Short headline, then one stat, then detail on demand. | Per-section scroll groups; staggered fade-in; parallax image; video scrub; 250ms linear background-color transition | All scenes; light/dark switch; hero | One `ScrollTrigger` timeline per scene (`data-scene="clock"`), like Apple's `data-anim-scroll-group`. Fade the body background over 250ms linear when a scene enters. Use a stagger for chart labels only. | **OBS:** HTML has 16 `data-anim-scroll-group` sections ("Welcome", "Highlights", "Noise Control"…), 19 `StaggeredFadeIn`, `ParallaxImage`, `VideoScrub`, sections tagged `background-alt`, and 149 `theme-dark` / 65 `theme-light` selectors in CSS. CSS has `--aap-background-transition-duration:250ms`, `transition:transform .3s cubic-bezier(0,0,0.5,1)`, `opacity 400ms ease-in-out`, and card fade-in at 600ms opacity / 400ms y with fade-out at 300ms. Headline type: `typography-headline-standalone` 96→80→48px, weight 600, line-height ≈1.04, letter-spacing −0.015em. **INF:** the `startframe` / `endframe` image names suggest scroll-scrubbed media. Stagger values and sticky behaviour were not verified. |
| **Linear** (linear.app) | Fast, restrained state feedback, built on a small named set of durations and easings. | Token-driven transitions (`--speed-quickTransition:.1s`, `--speed-regularTransition:.25s`, `--duration:.18s`) | Micro-interactions: language toggle, tooltips, ML status chips, legend hover | Copy the *system* (named tokens, short durations, out-curves for UI), not the look. | **OBS:** CSS defines the full Penner easing library (e.g. `--ease-out-quart:cubic-bezier(.165,.84,.44,1)`, `--ease-out-expo:cubic-bezier(.19,1,.22,1)`) and a title scale `--title-1…9-size` from 1.0625rem to 4.5rem. `prefers-reduced-motion` appears on 16 lines of the bundled CSS. `--color-bg-primary` has three values (#08090a, #000212, #fff). **INF / not verified:** which curve is used where, and which background is the homepage default. The page text shows a hero, then a "Fig 0.1–0.3" feature triplet, then 4 alternating feature blocks: strict, repeated hierarchy. |
| **Mapbox storytelling template** (github.com/mapbox/storytelling) | Chapters map 1:1 to camera states. Camera moves are triggered, not scrubbed. | `flyTo` / `easeTo` / `jumpTo` per chapter; layer `opacity` set on `onChapterEnter` / `onChapterExit`; Scrollama triggers | Scene 3 (map), scene 5 (buses) | `chapters[]` config with `{center, zoom, pitch, bearing}` plus H3 layer opacity per region. Run it through ScrollTrigger rather than Scrollama. | **OBS (README):** the config keys listed above; `mapAnimation` defaults to `flyTo`; text alignment falls back to `center` below 750px; layers should stay "visible with zero opacity" so they load. No default flyTo duration is documented. **INF:** MapLibre GL exposes the same `flyTo` / `easeTo` / `jumpTo` API (Mapbox GL v1 fork). Verify when implementing. |
| **The Pudding, "How to implement scrollytelling"** (pudding.cool/process) | Monitor scroll, never hijack it. Sticky graphic plus text steps. | Steps trigger at about 50% of viewport height; IntersectionObserver-based (Scrollama) | Scenes 2–5 trigger logic | ScrollTrigger `start: "top 50%"` for step triggers. No `scroll-snap`, no wheel interception. | **OBS:** article text quotes scrolljacking as "generally considered bad practice", gives offsets of `'50%'` / `'onCenter'`, and mentions throttling. |
| **"Where the Shadow Fell"** (eclipses.bogachev.fr, via Awwwards Data-Viz listing) | Teach the encoding before the reader explores. Use a worked example first, then the full dataset. | Loader with a live count ("Charting 11,898 eclipses…"); "How to read" primer; worked example → free exploration | Scene 2 legend primer; scene 3 (one hotspot explained before all of them); hero counter | Before the heatmap fills, show one labelled cell ("Fri 18h = N crashes"). Before the map tour, explain one hexagon. | **OBS:** page text shows the narrative structure. **Not inspectable:** motion and visualisation are JS-rendered and were absent from the fetched content. |

**Inspected, not adopted.**
- **Awwwards Animation listing:** 31 sites, with no tags or descriptions on the page, so suitability couldn't be judged from it. Only one Awwwards site (above) was actually opened. No other Awwwards site is claimed as a reference.
- **Motionographer homepage:** the current features are studio profiles, anniversary news and title-sequence news. Nothing on it informs a web-motion decision.
- **Reuters / NYT traffic scrollytelling:** a search found no reachable relevant piece.
- **The kinetic-type rules in §6 are project decisions,** not Motionographer findings.

## 3. Motion tokens

```css
:root {
  /* durations */
  --dur-micro: 180ms;      /* OBS Linear --duration:.18s (usage unverified) */
  --dur-standard: 320ms;   /* OBS-aligned: Apple .3s transform / 400ms opacity */
  --dur-theme: 250ms;      /* OBS Apple --aap-background-transition-duration (linear) */
  --dur-section: 600ms;    /* OBS-aligned: Apple card content fade-in 600ms */
  --dur-cinematic: 900ms;  /* PROP: map camera, hero number count-up end */
  --stagger: 60ms;         /* PROP: Apple uses StaggeredFadeIn, value not observed */

  /* easing */
  --ease-out: cubic-bezier(0, 0, 0.5, 1);          /* OBS Apple transform */
  --ease-out-quart: cubic-bezier(.165, .84, .44, 1); /* OBS Linear token: entrances */
  --ease-in-out: cubic-bezier(.645, .045, .355, 1);  /* OBS Linear in-out-cubic: camera, scrub */
  --ease-exit: cubic-bezier(.4, 0, 1, 1);            /* PROP: exits, faster than entrances */
  --ease-linear: linear;                              /* theme colour, scrubbed progress */

  /* translation */
  --shift-sm: 8px;  --shift-md: 16px;  --shift-lg: 32px;  /* desktop */
}
@media (max-width: 768px) { :root { --shift-md: 12px; --shift-lg: 20px; } }
@media (prefers-reduced-motion: reduce) {
  :root { --shift-sm: 0; --shift-md: 0; --shift-lg: 0; --dur-cinematic: 0ms; --stagger: 0ms; }
}
```

**GSAP mapping (PROP).**
- Easings: `CustomEase.create("qp-out","0,0,0.5,1")`. Use `"power3.out"` ≈ ease-out-quart and `"power2.inOut"` for camera.
- Durations in GSAP are in seconds (0.32, 0.6, 0.9).

**Rules.**
- Entrances use opacity plus a vertical shift of at most `--shift-lg`.
- Exits take 0.7× the entrance duration.
- Nothing scales above 1.02.
- No rotation, and no blur above 4px.

**Reduced motion.**
- Keep opacity crossfades at `--dur-micro`; this is a state change, not a removal.
- No transforms, no scrub, no pins longer than one viewport.
- Map camera uses `jumpTo`.
- Counters show their final value.
- **How JS honours it.** The CSS variables only reach CSS transitions. Wrap all GSAP setup in `gsap.matchMedia()` with a `(prefers-reduced-motion: reduce)` branch. The map controller checks `matchMedia('(prefers-reduced-motion: reduce)').matches` to choose `jumpTo` over `easeTo`.

## 4. Per-scene motion spec

All triggers use `ScrollTrigger`, with step start at `"top 50%"` (Pudding), and the page scrolls natively.

| # | Scene | Theme | What moves | Trigger | Pin | Mobile (<768px) | Reduced motion |
|---|---|---|---|---|---|---|---|
| 1 | **Hero.** Headline plus one number. | dark | Number counts up over `--dur-cinematic`, `tnum`. Headline lines fade up (`--shift-md`, 60ms per line, *never* per character). Amber appears on the number only. | Page load (after fonts ready) | No | Same, with smaller shift | Final number shown, static |
| 2 | **Traffic clock** (7×24 heatmap) | light | Primer cell is labelled first (Shadow Fell device). Rows then fill weekday by weekday, scrubbed. The peak cell turns amber with an annotation on the last step. | 3 text steps beside a sticky chart | Sticky chart for about 2 viewports (CSS `position:sticky`; ScrollTrigger only reads progress) | Chart stacks above text; sticky region shrinks to 1.5 viewports; hour axis labelled every 3h | Full heatmap shown at once, with annotations as static text |
| 3 | **Map: hotspot tour** (H3) | dark | Camera `easeTo` per region chapter (`--dur-cinematic`, in-out). Region hex layer opacity goes 0→1 on enter and 1→0.25 on exit. Active hex gets an amber stroke. | One step per region; `onEnter` / `onEnterBack` | Map pinned while chapters scroll over it (template pattern) | Text cards centred over the map, solid `--ink-2` with `--text-inv` (template's <750px behaviour); pitch 0; `cooperativeGestures`-style scroll so the map never traps the page | `jumpTo`; layers switch with no fade |
| 4 | **Who crashes** (vehicle mix) | light | Horizontal bars grow from 0 (`--dur-section`, ease-out-quart, 60ms stagger). The motorcycle bar is amber and draws last. | Enters at 60% of viewport, plays once | No | Same; labels above bars | Bars static |
| 5 | **Buses right now** | dark | GPS dots fade in by snapshot timestamp (one pass, about 1.2s total). A "snapshot at HH:MM" stamp is always visible. No fake live animation. | Enters viewport | Optional short pin (1 viewport) | Static map image fallback if WebGL is unavailable | Dots shown at once |
| 6 | **What ML can do** (4 fronts) | light | 4 cards stagger in. Status chips (e.g. "prototype", "planned") have a micro hover. No progress bars that imply completion. | Enters viewport | No | Single column | Static |
| 7 | **Methods & sources** | light | Nothing beyond the standard fade-up of the heading. | — | No | — | — |

**Theme switch.**
- Set `data-theme` on `<body>` from ScrollTrigger `onToggle` at each scene boundary.
- `background-color` and `color` transition over `--dur-theme` linear (Apple pattern).
- MapLibre style stays dark; the canvas sits on the ink background so the seam disappears.

**Performance.**
- Animate transforms and opacity only.
- Lazy-init MapLibre when scene 3 comes within 1 viewport.
- Set `will-change` only during active tweens (INF from Apple's `WillChange` component name).

## 5. Visual tokens

### Colour

Contrast was computed with the WCAG 2.x relative-luminance formula. Text needs 4.5:1, large text and non-text graphics need 3:1.

| Token | Hex | Use | Contrast |
|---|---|---|---|
| `--paper` | `#F6F3EE` | light scene background | — |
| `--paper-2` | `#ECE7DF` | light surface / cards | — |
| `--ink` | `#14120F` | dark scene background | — |
| `--ink-2` | `#1F1C18` | dark surface / map cards | — |
| `--text` | `#1A1714` | body on light | 16.1 on paper, 14.5 on paper-2 |
| `--text-muted` | `#5E574E` | secondary on light | 6.4 on paper, 5.8 on paper-2 |
| `--text-inv` | `#F3EFE8` | body on dark | 16.3 on ink, 14.8 on ink-2 |
| `--text-inv-muted` | `#A79F94` | secondary on dark | 7.2 on ink, 6.5 on ink-2 |
| `--amber` | `#F2A516` | accent on **dark**: number, active hex, peak cell | 9.1 on ink. **Never text on light (1.9).** |
| `--amber-text` | `#8F5400` | accent *text* on **light** | 5.5 on paper, 5.0 on paper-2 |
| `--amber-graphic` | `#C46A00` | amber marks on light (bars, peak cell) | 3.5 on paper (≥3:1 non-text) |
| `--rule` | `#CFC7BB` | hairlines on light (decorative) | 1.5, not information-bearing |
| `--on-amber` | `#14120F` | text on amber fills | 9.1 |

**Heatmap ramp (light scene).** A sequential ramp runs from `#E4DED4` (low) to `--amber-graphic` (peak).
- Low cells are deliberately close to the background (1.2:1), so values must also be available as a tooltip and an accessible table.
- Peak against paper is 3.5:1.
- Generate the intermediate steps in OKLCH and validate monotonic lightness.

**Map (dark).** The hex ramp runs from `#2A2621` (1.24:1 vs ink, so it reads as near-background; same label/tooltip rule) to `--amber`.

### Typography

- **Families:** Google Fonts `Inter Tight` (display, 600/700) and `Inter` (body, 400/500), `&subset=latin-ext` for PT-BR diacritics.
- **Numbers:** `font-variant-numeric: tabular-nums` for counters, axes and tables.
- **Display headlines:** letter-spacing −0.015em, line-height 1.04–1.08. These values were observed in Apple's headline CSS.
- **Bilingual copy:** PT-BR usually runs longer than EN (rule of thumb, PROP), so layouts must not depend on fixed line breaks. Use `text-wrap: balance` on headings.
- **Number formatting:** use `Intl.NumberFormat(locale)` (1.234 vs 1,234).

```css
--fs-hero:    clamp(3rem, 2rem + 6vw, 7.5rem);   /* headline number: 48 → 120px */
--fs-display: clamp(2.25rem, 1.6rem + 3vw, 5rem); /* scene titles: 36 → 80px */
--fs-h3:      clamp(1.5rem, 1.2rem + 1.2vw, 2rem);
--fs-lead:    clamp(1.125rem, 1rem + .5vw, 1.375rem);
--fs-body:    1rem;  --fs-small: .875rem;  --fs-caption: .75rem; /* captions uppercase +.06em */
--lh-body: 1.55;  --measure: 62ch;
```

### Spacing & grid

- **Spacing:** a 4px base, with `--space: 4 8 12 16 24 32 48 64 96 128 192` (px).
- **Scene padding:** `clamp(96px, 14vh, 192px)` vertical, so each scene gets a full breath.
- **Grid:** 12 columns, max 1280px, gutter `clamp(16px, 2vw, 32px)`, side margin 16px on mobile.
- **Text steps:** occupy columns 1–5 next to a sticky graphic in columns 6–12. On mobile they fall to a single column.
- **Hero number:** sits on the grid, not centred by default (PROP). That keeps it typographic, not a slide.

## 6. Anti-patterns (do not ship)

- **Generic AI aesthetics:** purple/blue gradients, mesh blobs, emoji icons, "✨" eyebrows, three identical feature cards with icons.
- **Glass and glow:** glassmorphism (backdrop-blur panels), glowing or animated gradient borders, neon on dark. Map cards are solid `--ink-2`.
- **Character-level animation as a default:** split-text letter reveals, scramble, or typewriter. Lines only, and only in the hero.
- **Forced slideshow:** `scroll-snap` mandatory, wheel hijacking, or locking scroll until an animation ends (Pudding: monitor, don't hijack).
- **Long pins and unrequested motion:** pins longer than about 2 viewports; parallax on data marks; auto-rotating maps (the template's 24s rotate is off); looping motion not started by the reader.
- **Fake liveness:** bus dots animating between positions they never reported; ML charts implying production accuracy that doesn't exist.
- **Accent overuse:** amber on more than one focal element per viewport, amber as body text on light, or red/green semantic pairs. The site uses one accent.
- **Unreadable data:** heatmap or map values available only through colour. Always pair them with a label, tooltip or table.
