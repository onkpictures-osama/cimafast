# Liquid Glass redesign — phase → commit map

This file exists because the git log does not tell the truth about this work.
Two early commits carry far more than their subject lines say, so "which commit
was Phase 0?" is not answerable from `git log` alone. Read this before trying to
review or revert any part of the redesign.

The redesign ships **behind `?theme=glass`**. The default look is unchanged and
every one of the 12 live users keeps seeing `classic` until the owner approves
flipping it. Nothing in here changes the default path.

## Where each phase actually landed

| Phase | What it does | Commit |
|---|---|---|
| 0 | theme/ module, self-hosted fonts, `?theme=glass` plumbing — **no visual change** | `e975f97` (see warning below) |
| 0 | screenshot harness (`tests/visual/`) | `348d91f` (see warning below) |
| 0 | theme tests, blur-depth check, docs | `f07e976` (see warning below) |
| 1 | ground mesh gradient + glass base theming | `f07e976` (see warning below) |
| 2 | three material tiers + `cf-*` migration + blur-depth guard | `f4ea08e` (see warning below) |
| 3 | component pass in frequency order | _not yet committed_ |
| 4 | chrome: 72% gold glass sidebar, header, stepper redesign | _not yet committed_ |
| 5 | light mode, reduced-transparency/motion, contrast audit, pointer sheen | _not yet committed_ |
| — | Readex Pro for the whole app — **not behind the flag**, every user sees it | `f97fe5c` |

This table is updated as each phase lands. A row saying _not yet committed_ means
exactly that.

## Where to see it

Published at **https://cimafast.io/v1/** — a second Streamlit (`cimafast-v1.service`,
port 8502, `STREAMLIT_SERVER_BASE_URL_PATH=v1`) with `CIMAFAST_THEME=glass`, behind
a `handle /v1*` block in the Caddyfile. Production on `/` is untouched and still
serves classic to all twelve users; nothing about the flag's default changed.

The preview runs on **its own copy of the database** at
`/var/lib/cimafast-v1/studio.db`, taken through the SQLite backup API. Real
scenes and characters to look at, but clicking around in the preview cannot
reach production data, and two Streamlit processes are never writing one SQLite
file. The unit's `ReadWritePaths` deliberately omits `/var/lib/cimafast`.

Refresh the preview's data from live:

```bash
python3 /opt/cimafast-backup/snapshot_db.py \
    /var/lib/cimafast/studio.db /var/lib/cimafast-v1/studio.db
systemctl restart cimafast-v1
```

`?theme=classic` still works on `/v1` for comparing side by side, because
`flag.py` reads the query param before the environment variable.

Note the file watcher is off in both units, so **a new commit does not reach
`/v1` until `systemctl restart cimafast-v1`**. If the preview looks a phase
behind, that is why.

Unrelated work that got committed in the same window, kept separate on purpose:

| Commit | What it is |
|---|---|
| `15ffcf7` | scene number suffixes (35A) carried through script import. Not redesign. |

## Warning: a fourth commit has a misleading subject line

**`f4ea08e` "Add intelligent location matching and enhanced analysis"** — its
message describes `location_matcher.py` and `enhanced_script_prompt.py` and does
not mention the theme at all, but it also carries the whole of Phase 2:

- `theme/glass.py` (+196): `_material_rules()` (the three `.cf-glass--*` tiers),
  `_cf_surface_rules()` (the `cf-*` migration onto the material), and
  `_blur_guard_rules()` (the structural two-layer blur cap)
- `theme/tokens.py` (+11), `theme/classic.py` (−8/+8)
- `tests/test_theme.py` (+66): the tier, blur-surface and nesting-depth tests

Same pathology as the three commits above, one window later. Phase 2 is complete
and its tests pass (`venv/bin/python tests/test_theme.py` → 14/14); only this map
was stale.


## Warning: three commits have misleading subject lines

Do not rewrite this history — republishing rewritten history on a public repo is
riskier than the mislabelling. Instead, know what is actually inside:

**`e975f97` "Fix sqlite3.Row object AttributeError"** — contains the entire
Phase 0 refactor, not a two-line fix:

- `.streamlit/config.toml` rewritten (+96): `server.enableStaticServing`,
  eleven `[[theme.fontFaces]]` tables
- `app.py` −444 lines: its three inline CSS blocks moved into `theme/`
- `static/fonts/*.woff2` (11 files, 240 KB): IBM Plex Sans Arabic + IBM Plex Sans
- `theme/` (8 modules): `__init__`, `tokens`, `contrast`, `classic`, `glass`,
  `inject`, `flag`, `components`
- `ai_prompt.py`: the `AI_JSON_PROMPT` constant extracted out of `app.py`
  (verified byte-identical, 3983 chars)
- `script_md.py`, `tests/visual/seed.py`
- and the actual titled change: `fetch_all()` returning dicts instead of
  `sqlite3.Row`

That last one is a **global behaviour change for every query in the app** and it
should never have travelled inside a theme commit. It is safe here only because
the one remaining positional row access, `database.py:112`, already guards with
`isinstance(row, dict)`.

**`348d91f` "Fix sqlite3.Row AttributeError globally in fetch_all"** — contains
`ai_jobs.py`, `script_parser.py` changes, and 388 lines of screenshot harness.

**`f07e976` "Remove outdated auto-link characters button"** — contains the rest
of Phase 0 *and* all of Phase 1, not just the `app.py` button removal:

- `REDESIGN.md`, `REDESIGN-PLAN.md`, and the theme/hazards sections of `CLAUDE.md`
- `tests/test_theme.py` (+259) and `tests/visual/blur_depth.py` (+103)
- `theme/glass.py` (+131): the mesh-gradient ground, the type rules and the
  concentric radius rules — i.e. Phase 1 in full
- `theme/tokens.py`, `theme/inject.py`, `theme/classic.py` adjustments
- and the actual titled change: the legacy character-linking expander in `app.py`

Phase 1's "Streamlit built-in theme settings" half is deliberately *not* there:
`.streamlit/config.toml` is read once at service start and cannot vary per
request, so anything glass-specific has to live in the CSS layer or it would
change the default look for every user. See CLAUDE.md.

## How to undo each piece

Reverting by commit does not work cleanly for `e975f97` and `348d91f`, because
each mixes the redesign with a database fix. Undo by path instead.

Turn the glass look off for everyone (it is already off by default — this is
only if someone flips it):

```
# nothing to do: theme/flag.py returns "classic" unless ?theme=glass is in the URL
```

Back out the whole redesign but keep the database fixes:

```
git rm -r theme/ static/fonts/ tests/visual/ tests/test_theme.py REDESIGN.md
git checkout 6d387ca -- app.py .streamlit/config.toml
# then re-apply ai_prompt.py's import if you keep ai_prompt.py
```

Back out one later phase only — the Phase 1–5 commits are clean and touch
`theme/` and `tests/` only, so `git revert <hash>` works on any of them
individually. They do not touch `app.py` at all, by design: another session was
editing `app.py` concurrently, and a theme layer that needs no application
changes is the safer shape anyway.

Go back to the Google Fonts CDN (not recommended — it was render-blocking and
re-injected on every rerun):

```
git checkout 6d387ca -- .streamlit/config.toml
# and restore the two <link> tags at the top of theme/classic.py's MAIN_CSS
```

## Regenerating the visual baseline

`/tmp` does not survive a reboot. The before-set is kept at:

```
/var/lib/cimafast/visual-baseline/6d387ca/     # 30 PNGs, the pre-redesign look
```

That directory is outside the git tree on purpose (same reasoning as
`studio.db`): binary screenshots do not belong in a public repo, and the live
box is where they are useful.

**The `6d387ca` set is no longer a flag-off regression reference.** It predates
both the font change (`font = "sans serif"` plus Google-CDN `<link>` tags → the
self-hosted `Readex Pro` faces now in `.streamlit/config.toml`) and four commits
of unrelated feature work (episodes, AI analysis, scene suffixes). Shooting
`classic` at `f07e976` against it gives 4/30 identical, with the differences
concentrated exactly where you would expect: typography everywhere, and the
analysis screen where new UI landed. Keep it as the record of the pre-redesign
look; do not read a `DIFF` against it as a regression.

For "did this phase change the default look?" use the flag-off set shot at the
commit you are building on:

```
/var/lib/cimafast/visual-baseline/f07e976-classic/   # 30 PNGs, classic at f07e976
/var/lib/cimafast/visual-baseline/f07e976-glass/     # 30 PNGs, glass at f07e976 (end of phase 1)
```

The `-glass` set is the other half of the same idea: each phase's glass shots
compared against the previous phase's show exactly which screens that phase
touched, which is how you catch a selector that reached further than intended.

To rebuild it from scratch:

```
git worktree add /tmp/cf-baseline 6d387ca
cp tests/visual/{shots,seed,compare}.py /tmp/cf-baseline/tests/visual/ 2>/dev/null || \
  mkdir -p /tmp/cf-baseline/tests/visual && \
  cp tests/visual/{shots,seed,compare}.py /tmp/cf-baseline/tests/visual/
venv/bin/python tests/visual/shots.py --out /tmp/shots/before \
    --tree /tmp/cf-baseline --port 8591
cp -r /tmp/shots/before /var/lib/cimafast/visual-baseline/6d387ca
git worktree remove /tmp/cf-baseline
```

The harness needs Playwright and Chromium, which are installed in the venv
(`playwright==1.63.0`, chromium-headless-shell 1243). If the venv is rebuilt:

```
venv/bin/pip install playwright==1.63.0
venv/bin/python -m playwright install --with-deps chromium
```

It starts its own Streamlit on a spare port against a seeded temp database and a
throwaway login, so it never reads or writes the live `studio.db` and never
touches port 8501.

## Comparing

```
venv/bin/python tests/visual/shots.py   --out /tmp/shots/glass --port 8592 --theme glass
venv/bin/python tests/visual/compare.py /var/lib/cimafast/visual-baseline/6d387ca \
                                        /tmp/shots/glass --diff-dir /tmp/shots/diff
```

For the flag-off path the two sets must match. For `--theme glass` they are
supposed to differ — the comparison is there to show you *which* screens changed
and to catch a screen you did not mean to touch.
