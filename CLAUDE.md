# CimaFast Studio

Arabic-first (RTL) film/TV pre-production manager built on Streamlit. Users are
Egyptian film crew, not developers: the UI language is Arabic, English is a
secondary toggle.

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

`/srv/cimafast` is both the git working tree and the directory systemd serves
from. Editing a file here changes production on the next restart, whether or not
you commit — committing is for history, not for making a change live. And
`cimafast-update` runs `git pull --ff-only`, so it aborts on a tree with modified
tracked files. Normal loop: edit → verify → commit → push → `cimafast-update`.

## Tests

Plain-assert scripts, no pytest, no extra dependency:

```
venv/bin/python tests/test_auth.py         # login logic (pure functions)
venv/bin/python tests/test_login_flow.py   # login screen via Streamlit AppTest
```

`test_login_flow.py` runs the real `app.py` against a temp DB via
`STUDIO_DB_PATH` — it must never be pointed at the live database. Fixtures use
throwaway credentials on purpose; see the login hazard below.

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
