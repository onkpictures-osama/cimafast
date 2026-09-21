# Mobile-first UI adaptation — plan

Requested by the owner (2026-09-21): adapt the UI to fit mobile screens. Scope
is deliberately narrow — **CSS-only presentation layer, auto-applied by the
browser's own viewport width, zero backend involvement**:

- No changes to `repo.py`, `database.py`, schema, or any Python business logic.
- No new URL flag, no device sniffing, no session-state branching. A phone
  gets the mobile rules because its viewport matches a CSS `@media` query —
  the exact same page Streamlit already serves. Nothing to opt into, nothing
  a desktop user can trigger by accident.
- Ships through the same `theme/inject.py` pipeline as `classic.py` /
  `glass.py`, so RTL logic stays in one place. Applies on top of whichever
  variant is active (glass is still flag-gated behind `?theme=glass`; mobile
  rules apply regardless).

## Why this and not a flag

The Liquid Glass redesign (`REDESIGN-PLAN.md`) needed a flag because it swaps
the whole visual material and needs owner sign-off before every user sees it.
Mobile fit isn't a matter of taste to gate — it's the app being broken on a
screen size real users are on today. A `@media (max-width: …)` block is
self-gating: it can only ever affect narrow viewports, is invisible to the
existing desktop/tablet baselines, and needs no Python code path at all.

## Evidence (from the existing visual harness, not guesswork)

`tests/visual/shots.py` already captures a `phone` viewport (390×844) at every
checkpoint. The on-disk baseline at `/var/lib/cimafast/visual-baseline/` is
stale — it predates a UX round that already removed the old 5-card stage
strip (`tests/test_ux_round2.py::test_the_five_stage_cards_are_gone`) in
favour of a single `.cf-progress` bar — so it does not reflect current
`HEAD`. Fresh shots taken against current `HEAD` this session are the real
source of truth:

1. **The progress bar is already fine on phone** — no work needed there; the
   card-strip cramping this plan first flagged turned out to be a stale-
   baseline artifact, not a current bug (corrected after Phase 0 testing).
2. **The tab bar** (`stTabs`, native Streamlit widget) still overflows on the
   reports screen at 390px — a "‹" scroll arrow appears and at least one tab
   (e.g. "الأماكن") is pushed off-screen with no visible label hinting it's
   there. Confirmed on current `HEAD`, not the stale baseline.

Still to confirm per-screen in Phase 1 (not assumed): dense forms,
image-picker columns, and report tables/dataframes on the characters/scenes/
shots tabs.

## Hard limits

- Zero diff at `tablet` (834px) and `desktop` (1440px) viewports — proven by
  running the existing visual harness, not asserted.
- Touch targets ≥44px (already the standard on the sidebar settings button,
  `theme/classic.py:215-217` — extend it, don't invent a new number).
- Text contrast rules from `theme/contrast.py` still hold.
- Every check runs in Arabic (RTL) and English.
- Deploys to `/v1` only, same as every other CimaFast change (`deploy-to-v1`
  policy); production untouched without the owner's explicit approval.

## Phases

0. **Safety net + touch targets** — `theme/mobile.py` wired into
   `theme/inject.py`; buttons/inputs/selects hit the 44px minimum. Proven
   with the visual harness to be a no-op above 480px and on 4/5 phone
   screens; the 5th shows only the expected few-px reflow from taller
   buttons. *(this session)*
1. **Navigation** — tab bar legible without a hidden/cut-off tab; sidebar
   collapse behavior confirmed sane (Streamlit's native collapse already
   triggers on narrow viewports — verify, don't rebuild).
2. **Forms, tables, image pickers** — single-column stacking confirmed on
   every tab (locations, characters, scenes, shots, reports), wide dataframes
   get a horizontal-scroll container instead of squeezing columns unreadable.
3. **Typography & density pass** — base font-size/line-height/row-height
   tuned for a phone held at arm's length, re-run the contrast audit.
4. **Full verification** — phone-viewport visual pass across every screen in
   `tests/visual`, zero diff confirmed at tablet/desktop for all of them.

## Breakpoint

`max-width: 480px` — comfortably below the harness's `tablet` viewport
(834px), so phones get the rules and tablets don't, matching "mobile
screens" literally rather than "anything not desktop."
