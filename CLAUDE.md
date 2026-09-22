# CimaFast Studio

**A software product: an Arabic-first (RTL) ERP for film makers.** Production
companies and crews use it to manage *their* film and series projects — script
import and AI analysis, breakdown, shots, scheduling, official reports. We build
the system; the projects in its database are users' data, to be used as evidence
of how the product is used, never as a production for us to manage. Build for
many companies, many projects, many users. The product roadmap is
`PRODUCT-PLAN.md`.

Users are film makers, not developers: the UI language is Arabic, English is a
secondary toggle. Built on Streamlit today, with new screens (the shooting
schedule, `board/`) on Starlette sharing the data layer in `repo.py`.

**All fixes and updates are deployed to /v1** (https://cimafast.io/v1/, this
checkout when it is `/srv/cimafast-v1`). Production changes only with the owner's
explicit approval of that deploy.

## Stack

| Layer | Choice |
|---|---|
| UI | Streamlit 1.64 (`app.py`, ~2.3k lines) |
| Runtime | Python 3.14, venv at `/srv/cimafast/venv` |
| Data | `database.py` — SQLite locally, Postgres/Supabase when `DATABASE_URL` is set |
| Export | `export.py` — Excel / Word / PDF with Arabic reshaping + bidi |
| Parsing | `script_parser.py` — screenplay parsing, fuzzy duplicate-name merging |

`database.py` translates dialect differences (`?` placeholders, `RETURNING id`,
`INSERT OR IGNORE` → `ON CONFLICT`) so nothing else in the app knows which
backend it is on. **Keep that abstraction** — do not write backend-specific SQL
in `app.py`, `export.py`, or `importer.py`.

Core tables: `projects`, `locations`, `location_variants`, `characters`,
`character_looks`, `scenes`, `shots`, `props`, and the `scene_*` / `shot_*` join
tables.

## Language and UI conventions

- **Code comments are in Egyptian Arabic.** Match the surrounding style; do not
  convert existing comments to English.
- Translation is a direct dictionary in `app.py` where **the Arabic string is the
  key** and the value is its English translation (`tr()` / `t()`). Adding a new
  UI string means adding its Arabic key and English value together.
- Layout direction flips with the language (`_dir`, `_text_align`). Anything new
  that is visually positioned must work in RTL first.

## Production

This app is live at **https://cimafast.io** on this box.

| | |
|---|---|
| Served from | `/srv/cimafast` (this directory) |
| Service | `cimafast.service` → Streamlit on `127.0.0.1:8501` |
| Proxy | Caddy, auto-HTTPS via Let's Encrypt, config `/etc/caddy/Caddyfile` |
| Live data | `/var/lib/cimafast/studio.db` — **outside this tree, never in git** |
| Secret | `/etc/cimafast/secrets.toml` (`[users]` login hashes), symlinked to `.streamlit/secrets.toml` |
| Deploy | `cimafast-update` (pull, deps, restart, health-check, auto-rollback) |
| Logs | `journalctl -u cimafast -f` |

The SQLite path is overridable with `STUDIO_DB_PATH`, which is how production
keeps its data outside the working tree. Never hardcode a path around it.

## Source control

Repo: **https://github.com/onkpictures-osama/cimafast** (public — everything
committed is world-readable). `gh` is authenticated on this box and the git
credential helper is configured, so `git push` works without prompting.

Two checkouts of this repo serve two environments:

| Checkout | Branch | Serves | Role |
|---|---|---|---|
| `/srv/cimafast-v1` | `preview` | https://cimafast.io/v1/ (+ `/v1/board/`), DB copy | **where all work is built and deployed** |
| `/srv/cimafast` | `main` | https://cimafast.io, live data | production — changes only on owner approval |

Streamlit re-reads `app.py` on every session, so a file edited in a served
checkout is live at once. Never edit `/srv/cimafast`. Normal loop: edit in
`/srv/cimafast-v1` → `systemctl restart cimafast-v1` (and `cimafast-board-v1` for
`board/` or `repo.py`) → verify in a browser (`cimafast-smoke`, `pw-python`) →
commit on `preview`. An owner-approved production deploy is `cimafast-update`
only; see `.claude/agents/chief-engineer.md` for how to ship a single change
without shipping everything on the preview.

## Tests

Plain-assert scripts, no pytest, no extra dependency:

```
venv/bin/python tests/test_auth.py         # login logic (pure functions)
venv/bin/python tests/test_login_flow.py   # login screen via Streamlit AppTest
venv/bin/python tests/test_theme.py        # theme tokens, contrast floors, theme flag
```

`test_login_flow.py` runs the real `app.py` against a temp DB via
`STUDIO_DB_PATH` — it must never be pointed at the live database. Fixtures use
throwaway credentials on purpose; see the login hazard below.

`test_gui.py` is an HTTP smoke test against the *running* service on
`127.0.0.1:8501`. Two of its eight checks (`Claude Signature`, `Signup Module`)
look for features that do not exist in this codebase and have failed since
before the theme work — 6/8 is the expected baseline, not a regression.

### Visual regression

A restyle on a live app needs a repeatable pixel check, not one-off screenshots.
The harness starts its own Streamlit on a spare port with a seeded temp DB and a
throwaway login, so it never touches production or the live database:

```
venv/bin/python tests/visual/shots.py   --out /tmp/shots/after  --port 8592
venv/bin/python tests/visual/shots.py   --out /tmp/shots/glass  --port 8593 --theme glass
venv/bin/python tests/visual/compare.py /tmp/shots/before /tmp/shots/after
venv/bin/python tests/visual/blur_depth.py --port 8596        # backdrop-filter nesting
venv/bin/python tests/visual/mobile_ui.py  --port 8607        # phone layout, measured
```

`mobile_ui.py` is the phone check. At 390×844, in both languages, it measures
that no tab falls off-screen, that the active-tab underline still lines up with
the open tab, that the sidebar collapses to an overlay it can reopen, that
nothing sits in two columns, and that every button and input clears 44px. One
PASS/FAIL line per check, non-zero exit on any failure.

54 shots per run: 3 viewports (phone/tablet/desktop) × 2 languages × 9 screens
(login, project list, locations, characters, props, scene editor, shots, final
reports, script analysis). To shoot an older commit for comparison, add a
worktree and point `--tree` at it:

```
git worktree add /tmp/cf-baseline <commit>
venv/bin/python tests/visual/shots.py --out /tmp/shots/before --tree /tmp/cf-baseline --port 8591
git worktree remove /tmp/cf-baseline
```

## Theme layer

All CSS lives in `theme/` — it used to be three separate `st.markdown` blocks
inside `app.py`.

| File | Holds |
|---|---|
| `theme/tokens.py` | every colour, alpha, blur, radius and shadow, for dark and light |
| `theme/contrast.py` | WCAG maths: alpha compositing, luminance, ratio, audit table |
| `theme/classic.py` | the current look, verbatim — the default all users see |
| `theme/glass.py` | the Liquid Glass material layer, flag-gated |
| `theme/inject.py` | the only place that writes CSS into the page |
| `theme/flag.py` | `?theme=glass` resolution; defaults to `classic`, always |
| `theme/components.py` | `glass_panel()` / `glass_card()` helpers |
| `theme/mobile.py` | phone rules, all inside one `@media (max-width: 767px)` |

Rules that are load-bearing:

- **`classic` is the default and must stay pixel-identical.** The glass look ships
  only behind `?theme=glass` until the owner approves flipping it. `.streamlit/
  config.toml` is read once at startup and cannot vary per request, so nothing
  glass-specific belongs in it — that is why radius, borders and light mode are
  in the CSS layer rather than in native theme keys.
- **At most two nested `backdrop-filter` layers.** The third material tier is
  opaque by definition, which is what makes the rule structural instead of a
  thing to remember. `tests/visual/blur_depth.py` measures it in a real browser.
- **Contrast floors are measured, not eyeballed.** Body text ≥ 4.5:1, headings
  ≥ 3:1, in both modes. The gold sidebar holds AA body text only at ≥ 72% tint;
  60% gives 3.69:1 and fails. `tests/test_theme.py` asserts this.
- Fonts are self-hosted in `static/fonts/` via `[[theme.fontFaces]]`, which needs
  `server.enableStaticServing = true`. Do not reintroduce the Google CDN `<link>`
  tags: they were render-blocking and re-injected on every rerun.

## Hazards

- **The login gate fails closed.** Access is a username + password login:
  `_check_login()` in `app.py` for the screen, `auth.py` for the logic
  (PBKDF2-SHA256, per-user salt, constant-time compare). Accounts live in the
  `[users]` table of `/etc/cimafast/secrets.toml` as `username = "<hash>"`, read
  via `st.secrets`, with the `CIMAFAST_USERS` env var (JSON) taking precedence
  for local development. **No plaintext password and no hash belongs in this
  public repo** — not in code, not in tests, not in a commit message.
  - Missing or unreadable accounts lock the app and log why, rather than opening
    it: a lost secrets file takes the site down instead of making it public.
    Running with no login at all requires `CIMAFAST_ALLOW_NO_PASSWORD=1`
    explicitly, which is for local development only and must never be set on this
    box. Keep that fail-closed default and the env-before-`st.secrets` ordering.
  - Add or rotate an account with
    `venv/bin/python auth.py hash`, then edit the `[users]` table. That is a
    secrets-file change only — no deploy, no code change, but the running service
    caches `st.secrets`, so a restart is needed before it takes effect.
  - `APP_PASSWORD` in the secrets file is the superseded single shared password.
    Nothing reads it any more; it is kept only so a rollback past the login
    commit still serves.
- **Never commit** `studio.db*`, `.streamlit/secrets.toml`, or `uploads/` — all
  gitignored. The live DB is real user work.
- Cert renewal uses the HTTP-01 challenge, so **port 80 must stay open**.
- Restarting `cimafast.service` drops every active Streamlit session; users lose
  unsaved form state. Prefer deploying when idle.

## Unrelated services on this box

`/opt/tg-bridge` (`tg-receiver`, `tg-worker`, `tg-watchdog.timer`) is the Telegram
bridge and has nothing to do with this app. Do not restart or reconfigure it as
part of CimaFast work.
