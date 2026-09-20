# Liquid Glass for CimaFast Studio — plan

Approved by the owner: **full redesign** (layout included, not just a reskin),
**dark and light mode**, **gold sidebar as 72% tinted glass**, and everything
shipped **behind `?theme=glass`** until the owner approves it for all users.
Progress and the phase→commit map are in `REDESIGN.md`.

## Direction
Liquid Glass is a material: translucent layers floating over a background that
shows through them. So the background comes first — a fixed mesh gradient built
from CimaFast's own colours (navy base, indigo pools, a faint gold glow, one cool
teal accent), with content scrolling over it. The brand gold `#E8B923` stays as
the accent colour. Signature detail: a highlight on each glass panel that follows
the mouse pointer (a fixed highlight on touch screens).

## Tokens
- Glass: regular 62% tint · blur 24px · saturate 180% — clear 38% · blur 12px
  (over images only) — opaque 100% (dense text: tables, long Arabic)
- Edge: 1px hairline rgba(255,255,255,.12) + inset top highlight .18
- Radius: 22 / 14 / 10 · Shadow 0 8px 32px rgba(0,0,0,.35)
- Type: Readex Pro everywhere, Arabic and Latin (owner's decision; replaces IBM Plex / SF Pro)

## Hard limits
- Text contrast ≥4.5:1 (headings ≥3:1), in both modes
- Gold sidebar ≥72% tint (5.32:1); 60% fails (4.19:1)
- No more than two blurred layers stacked anywhere (phones)
- Every check runs in Arabic (right-to-left) and English

## Phases
0. Safety net, no visual change: screenshot harness, CSS moved into theme/, fonts
   hosted locally, the flag
1. Background gradient + Streamlit's built-in theme settings
2. Glass building blocks (3 levels) + move the existing `cf-*` styles onto them
3. Restyle widgets, most-used first (selectbox, inputs, forms, buttons, alerts…)
4. Frame of the app: gold glass sidebar, header, redesigned step indicator
5. Light mode, fallbacks for users who turn off transparency or motion,
   contrast audit, pointer highlight
6. Replacing emoji with a proper icon set — needs a separate decision from the owner
