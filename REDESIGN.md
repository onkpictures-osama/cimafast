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
| 0 | theme tests, blur-depth check, docs | _not yet committed_ |
| 1 | ground mesh gradient + glass base theming | _not yet committed_ |
| 2 | three material tiers + `cf-*` migration | _not yet committed_ |
| 3 | component pass in frequency order | _not yet committed_ |
| 4 | chrome: 72% gold glass sidebar, header, stepper redesign | _not yet committed_ |
| 5 | light mode, reduced-transparency/motion, contrast audit, pointer sheen | _not yet committed_ |

This table is updated as each phase lands. A row saying _not yet committed_ means
exactly that.

Unrelated work that got committed in the same window, kept separate on purpose:

| Commit | What it is |
|---|---|
| `15ffcf7` | scene number suffixes (35A) carried through script import. Not redesign. |

## Warning: two commits have misleading subject lines

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
