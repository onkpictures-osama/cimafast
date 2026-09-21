# CimaFast Studio — Product Plan

*Owned by the orchestrator (product lead). Rewritten 2026-09-21 after the owner
corrected the team's framing: CimaFast is a product — an ERP for film makers —
not a production we run. Every agent reads this before proposing work.*

## What we are building

An Arabic-first ERP that a production company adopts to run **all of its
projects**, films and series, physical and AI-generated: from the screenplay to
breakdown, shots, schedule, shoot days and official reports, with every
department working on the same data.

**Who uses it**
- **Company admin / producer** — owns the company's account, projects, people, money.
- **Production manager / 1st AD** — turns the breakdown into a schedule and shoot days.
- **Department heads** — costume, art, locations, camera, casting, VFX: their slice of the breakdown.
- **AI-generation lead** — prompts, settings and assets for AI-generated productions.
- **The CimaFast operator (owner)** — runs the platform for every company on it.

## Where the product stands (evidence, 2026-09-21)

- **It is not an ERP yet at the account level.** Logins are 13 hard-coded
  usernames in a config file; there are no companies, no users table, no link
  between users and projects (every user sees every project), no roles or
  permissions, no audit trail, no usage analytics.
- **Users stop halfway through the pipeline.** 1 project exists; it has 143
  scenes, 99 locations, 43 characters, 124 props — and 0 shots, 0 reference
  images, no schedule dates. The script-to-breakdown half works; the planning half
  is where users stall.
- **Useful output is hidden.** The AI analysis stores a suggested shot size and
  camera move for 141 of 143 scenes; nothing shows them. AI image generation works
  for locations but is a disabled "coming soon" stub for characters.
- **The data model is too flat for planning.** 99 location records map to about 50
  real sites; the parent/child link exists but nothing uses it; no city or address.
- **Performance and structure** were rebuilt on /v1 (below); production still runs
  the old code (16 s per click with this project's data).

## Principles

1. **Multi-company from the start.** No feature may assume one company, project or team.
2. **Arabic-first.** RTL and Egyptian usage are the main path, not an edge case.
3. **Evidence over opinion.** Every item says what in the data or code justifies it.
4. **Everything ships to /v1 first.** Production only on the owner's approval.
5. **Show what we already know.** Surfacing stored data beats building new AI.

## Roadmap

Each item: *problem → what we build → done when*. Owner agent in brackets.

### Phase 0 — ERP foundations (before a second company can use CimaFast)

- **F1 Companies, users and project access** [chief-engineer, infrastructure]
  Accounts live in a config file and every user sees every project. → Users,
  companies and memberships in the database; each project belongs to a company;
  invite by email, password reset, deactivate. *Done when* two companies can use
  CimaFast side by side and never see each other's projects.
  ✅ **On /v1 2026-09-21.** Accounts moved from secrets.toml into the database
  on first start (every password unchanged); existing users and projects sit in
  "الشركة الافتراضية". The team page (`/v1/board/team/`, linked from the
  sidebar) lets a company admin add people (one-time temporary password, changed
  at first login), change roles, reset passwords, remove and re-add people, and
  rename the company; the operator creates companies. Verified in a browser: a
  second company's admin sees none of the first company's projects (404 on the
  board API, 403 on its team), and a company admin can never modify the
  operator's account. Still to come: invite by email (needs an outbound mail provider).
- **F2 Roles and permissions** [orchestrator, infrastructure]
  Anyone can delete any project. → Company admin, producer, production manager,
  department head, viewer; destructive actions need the right role. *Done when* a
  viewer cannot change data and only an admin can delete a project.
  ✅ **On /v1 2026-09-21.** One rule table (`permissions.py`) checked by the data
  layer itself, so every write from every screen and the board API passes through
  it. Viewers browse and export only (the board is read-only, and script analysis
  and image generation are refused before any money is spent); department heads,
  production managers and producers edit; producers and production managers also
  create projects; only the company admin deletes a project or manages the team.
  Verified in a browser for viewer and department head. Next refinement: department
  heads limited to their own department's data.
- **F3 Audit trail and usage events** [infrastructure]
  Nobody can see who changed what, or which features are used. → An append-only
  log of changes (who, what, when, before/after) and of key usage events (login,
  screen, export). *Done when* any change can be traced and the agents report
  adoption from events rather than guessing.
- **F4 Off-site encrypted backups** [infrastructure] — ✅ **done 2026-09-21.**
  Nightly: encrypted on the server (gpg AES-256), pushed to the private repo
  github.com/onkpictures-osama/cimafast-backups, then downloaded back, decrypted
  and restore-drilled. Documented in that repo's README and
  `/opt/cimafast-backup/README.md`.

### Phase 1 — A home for every user

- **H1 User home (concierge)** [production, chief-engineer]
  After login, users land in whatever project was open last; tools are scattered.
  → A home page: my companies and projects (with progress and next step), my
  tools grouped by production phase, what needs me by role, continue where I left
  off, search across my projects. *Done when* a new user reaches their first
  useful action from the home page without help. **Build plan:
  `HOME-PAGE-PLAN.md`** (covers H1 and H2).
- **H2 Deep links** [chief-engineer] — `?project=` and `?tab=` so every card,
  notification and agent post opens the exact screen (supported by `st.tabs(default=)`).
- **H3 Onboarding** [production] — a sample project and a guided first import,
  so a new company sees the full pipeline before loading its own script.

### Phase 2 — Complete the core pipeline (where users stall today)

- **P1 Starter shots from the AI analysis** [universal-creative, chief-engineer]
  141 scenes carry suggested shots nobody sees; 0 shots exist. → Show the
  suggestion on each scene and create editable starter shots per scene or in bulk.
- **P2 Reference images at scale** [universal-creative] — character image
  generation (today a stub) at parity with locations; bulk "generate missing".
- **P3 Location model** [universal-creative, production] — sites and rooms
  (parent/child), city and address, a merge tool for duplicates. Scheduling,
  scouting and call sheets all depend on it.
- **P4 Analysis reliability and cost** [universal-creative, infrastructure] — a
  run that returns 0 scenes is a failure, not "done"; never charge twice for the
  same file; show AI spend per project and company.
- **P5 Looks and continuity** [universal-creative] — scenes that note a look
  change create or link a look; continuity-sensitive props tracked across scenes.

### Phase 3 — Scheduling and shoot days (the heart of a production ERP)

- **S1 Stripboard** — built on /v1 (`/v1/board/`): drag-and-drop, suggested
  schedule, company-move and day/night warnings, cast DOOD.
- **S2 Calendar** — a start date and working days turn the stripboard into dates.
- **S3 Call sheets** — generated per shoot day from the schedule, cast and locations.
- **S4 Cast and crew directory** — contacts, availability, and the DOOD per person.

### Phase 4 — ERP breadth

- **B1 Budget and costs** — budget lines per department, actuals, reports.
- **B2 Daily production reports** — what was shot vs planned, per day.
- **B3 Vendors, equipment and rentals.**
- **B4 AI-generated production module** — versioned prompts, generation settings,
  digital-asset tracking, linked to scenes and shots.

### Continuous

Performance, the Arabic/RTL design system (glass redesign phases 3–5), test
coverage, security review, and moving screens from Streamlit to the new frontend
one at a time as they are rebuilt.

## On /v1, awaiting the owner's approval for production

- Faster clicks (16 s → about 2.5 s): editors built only when opened.
- Library-first screens with Arabic-aware search; scenes as a table; one progress line.
- Reports that show what is missing; exports always built from current data.
- `app.py` split into views; SQLite in WAL mode; all queries in a data layer (`repo.py`).
- The shooting-schedule board (S1) at `/v1/board/`.

## How the agents use this plan

Proposals reference an item here (e.g. "F1") or argue for adding one. The
orchestrator reorders items only with evidence, and brings scope or priority
changes to the owner in #decisions. Work that users do inside the product is
never a decision for the owner.

## Owner decisions

1. **Order** — decided 2026-09-21: Phase 0 (ERP foundations) first. "OK, go."
2. **Off-site backups** — decided 2026-09-21: GitHub, with proper documentation.
3. **Promoting /v1 to production** — the owner decides when. Agents do not raise it.
