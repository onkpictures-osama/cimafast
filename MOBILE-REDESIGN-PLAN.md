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

0. ✅ **Safety net + touch targets** — `theme/mobile.py` wired into both
   `inject_base` (login screen) and `inject_main` (everything after);
   buttons/inputs/selects hit the 44px minimum. Verified with the visual
   harness: 0.000% diff at tablet (834px, checked both viewport-only and via
   a clean stash/unstash before-after pair) and desktop (1440px); on phone
   (390px), the login screen now visibly changes (inputs/button grow to
   44px — this was missing before an owner-requested independent review
   caught it, see below) and the rest of the screens change only by the
   few-px reflow from taller buttons. *(this session)*
1. ✅ **Navigation** — the tab bar wraps onto rows instead of scrolling, so
   all seven tabs are visible at 390px; the active-tab underline still tracks
   the open tab exactly; the sidebar's native collapse-to-overlay verified,
   not rebuilt. *(this session — see "Phase 1 result" below)*
2. **Forms, tables, image pickers** — single-column stacking confirmed on
   every tab (locations, characters, scenes, shots, reports). Confirm before
   promising a fix for wide `st.dataframe` grids or anything inside an
   `st.components.v1.html` iframe (e.g. `views/import_tab.py`) — injected page
   CSS cannot reach into either, so those two need a different approach (or
   get explicitly descoped) rather than the same CSS layer.
3. **Typography & density pass** — base font-size/line-height/row-height
   tuned for a phone held at arm's length, re-run the contrast audit.
4. **Full verification** — phone-viewport visual pass across every screen in
   `tests/visual`, zero diff confirmed at tablet/desktop for all of them, run
   once under `--theme classic` and once under `--theme glass` (the harness
   was only ever run against `classic` before this pass).

## Breakpoint

`max-width: 767px` — matches Streamlit's own internal mobile switch exactly:
its frontend bundle defines `breakpoints.md = 768px` and treats
`innerWidth < md` as `isMobile` (`utils.BVKswTgl.js`, confirmed by reading the
shipped JS, not guessed). Below 768px, Streamlit itself already collapses the
sidebar to an overlay and stacks columns — this plan's CSS should kick in for
that exact same range, not some independently-chosen number. (Phase 0
shipped first with an arbitrary `480px` guess; corrected once the real
constant was found — 767px is still comfortably below the harness's `tablet`
viewport at 834px, so the "zero diff at tablet" limit still holds, reverified
above.)

## Known gaps (owner asked for an independent review; findings below)

An independent review of Phase 0 surfaced three real issues, two fixed in
this pass and one left as an open design question for Phase 1+:

- **Fixed:** the mobile CSS was only wired into `inject_main`, so the login
  screen — the first thing a phone user touches — got none of it. Now wired
  into `inject_base` too.
- **Fixed:** the breakpoint (480px) didn't match Streamlit's own mobile
  switch (768px), leaving a band of viewport widths in Streamlit's mobile
  layout without this app's touch-target rules. Corrected above.
- **Closed in Phase 1:** wrapping `stTabs` in CSS to fix the overflow risked
  misplacing the active-tab underline. Measured, not assumed — see below.
- **Still open:** CSS is injected via `st.markdown` after the script body runs,
  so a slow mobile connection can show an unstyled flash before it applies —
  not addressed, and out of scope unless it proves visible in practice.

## Phase 1 result — navigation

The underline risk did not materialise, and now we know exactly why. In
Streamlit 1.64 the active-tab underline is a `.react-aria-SelectionIndicator`
`div` **inside the selected tab** (`position:absolute; left:0; bottom:0`), not
one element floating over the whole tab bar that JS re-positions. Wrapping the
bar therefore cannot move it away from its tab — it moves *with* it.

That is measured, per tab, in `tests/visual/mobile_ui.py`: for all seven tabs,
in Arabic and in English, the gap between the indicator's box and the selected
tab's box is **0.0px** in all three directions, and the indicator is still a
descendant of the tab. If a future Streamlit upgrade moves the indicator out of
the tab, that check fails instead of shipping a misplaced underline.

What changed, measured at 390px:

| | before | after |
|---|---|---|
| tabs off-screen (ar) | 5 of 7 | 0 |
| tab bar horizontal scroll | 353px hidden | 0 |
| tab bar height (ar / en) | 40px, 1 row | 140px / 92px, 3 and 2 rows |
| sidebar expand button | 28×28px | 44×44px |

The cost is real and deliberate: the Arabic tab bar takes three rows (140px of
an 844px screen) because seven 44px-tall targets cannot fit in fewer. The
alternative — keeping the scroller and adding a fade hint — leaves a tab the
user has to discover. Navigation to seven sections beats 100px of scroll.

The sidebar was verified, not rebuilt, as planned: below 768px Streamlit
already collapses it and reopens it as a 300px overlay *over* the content
(main content width unchanged at 390px). The one real bug found there was its
expand button — 28×28px, the only way into the sidebar on a phone, now 44px.
