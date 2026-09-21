# Build plan — User Home (الاستقبال) · PRODUCT-PLAN items H1 + H2

*Owners: production (requirements) and chief-engineer (build). Deploys to /v1.
Written 2026-09-21. Replaces the chat draft from earlier that day, which used one
user's project as its examples and put the team's internal Discord standup on a
customer-facing page — both wrong for a product.*

## 1. The problem

CimaFast is an ERP a production company uses for all its projects. Today, after
login, every user lands inside whichever project was open last, on the same seven
tabs, whatever their job. The project picker is a dropdown in the sidebar; "new
project" is an expander under it; exports sit at the bottom of the last tab; the
AI analysis is inside the import tab; the shooting schedule is a separate page
(/v1/board/). A costume designer and a producer see the same screen and must
hunt for their part of it.

## 2. The outcome

After login, every user lands on **their home**, which answers within seconds:
**what am I working on · what needs me · where is the tool for it.**

*Done when:* a user who has never seen CimaFast reaches a useful action in their
own area (e.g. a costume designer opens the looks that need attention) from the
home page, without help, on desktop and on a phone, in Arabic and English.

## 3. The page, top to bottom

1. **Header** — name and role ("مصممة الأزياء"), language toggle, logout.
2. **Continue** — one button back to the last project and screen this user had open.
3. **My projects** — a card per project the user can access: name, type (فيلم /
   مسلسل / إعلان…), a progress bar across the pipeline stages, the **next step**
   for that project, last updated. Buttons: open · stripboard · reports.
   **+ New project** lives here, not in the sidebar.
4. **Needs you** — role-aware items computed from the user's own projects (§5),
   each one a deep link to the exact screen.
5. **Tools** — every capability grouped by production phase, one line each on
   what it is for, with a *preview* badge for /v1-only tools:
   Script (import · AI analysis · outside-the-app analysis) → Breakdown
   (locations · characters & looks · props · scenes) → Shots → Schedule
   (stripboard · cast days) → Reports (Excel / Word / PDF, one click each).
6. **Search** — one box across all the user's projects: scenes, characters,
   locations, props (Arabic-aware, reusing `search.py`).

Not on the page: the team's Discord or the agents — those are how *we* build
CimaFast, not something our customers use.

## 4. Deep links (H2) — the prerequisite

Every card, task and tool opens an exact screen, so the Streamlit app must accept:

- `?project=<id>` — selects that project (sets the sidebar selector's default).
- `?tab=<name>` — opens that tab. Streamlit 1.64 supports `st.tabs(default=…)`.
  Adopting `on_change="rerun"` on the tabs at the same time makes only the open
  tab run — another large speed-up on top of the lazy editors already on /v1.
- `?scene=<id>` / `?location=<id>` (later) — open that item's editor.

## 5. "Needs you" — rules by role

Rules run on each project the user can access. Each rule has a role list, a
count, a sentence, and a deep link. First set (all computable today):

| Role | Rule | Link |
|---|---|---|
| producer, company admin | project has scenes but no shooting days / days without dates | stripboard |
| assistant director | scenes not scheduled; days mixing day and night | stripboard |
| director, DOP | scenes with no shots; scenes with an unused AI shot suggestion (after P1) | shots |
| costume designer | scenes noting a look change with no second look for that character | characters |
| art director, locations | locations with no reference image; props not marked for continuity | locations / props |
| casting director | characters with no reference image | characters |
| screenwriter | AI analysis that failed or returned 0 scenes; unconfirmed import | import |
| everyone | shots waiting for review | shots |

Gaps the rules expose in the **data model** (feed PRODUCT-PLAN, not this build):
there is no actor-per-character field for casting, and no VFX fields for the VFX
supervisor. Until those exist, those roles get the generic items only.

## 6. Accounts, roles and access — now vs after F1

**Now (this build, on /v1):** accounts are 13 usernames in `secrets.toml`, and
most of them are already job titles (`producer`, `director`, `dop`,
`costume_designer`, `assistant_director`…). A small `user_profile` table holds
`username, role, display_name, last_project_id, last_tab, updated_at`, seeded by
mapping those usernames to roles. Every user still sees every project — that is
today's product behaviour, and the home page does not change it.

**After F1/F2 (companies, users, permissions):** "my projects" becomes the
projects the user is a member of, a company switcher appears for people in more
than one company, and admin tiles (people, invites) appear for company admins.
The home page is written against a `projects_for_user(user)` function in
`repo.py`, so F1 changes that one function, not the page.

## 7. How it is built

- **Where:** a new route in the Starlette app next to the stripboard —
  `/v1/home/` — same shared login cookie, same data layer (`repo.py`), same
  self-hosted fonts, RTL-first, no build step, no CDN.
- **Data layer (`repo.py`):** `projects_for_user`, `project_progress`,
  `next_step`, `needs_you(user)`, `search_projects(user, q)`, `touch_last_visit`.
- **Streamlit side (/v1):** read `?project=` / `?tab=`; write the last project
  and tab to `user_profile`; a "🏠 الرئيسية" link in the sidebar.
- **Landing:** on /v1, after login, redirect to `/v1/home/`.
- **Tests:** repo unit tests for every rule (on a throwaway database), a
  browser end-to-end run (log in → home → each card and task link opens the right
  screen), RTL and mobile screenshots, and the whole-app pre-flight.

## 8. Slices (each ships to /v1 and is verified before the next)

| Slice | Contents | Size |
|---|---|---|
| A | Deep links in the Streamlit app (§4) + lazy tabs | ~½ day |
| B | Home page: header, projects with progress and next step, tools, new project | ~1 day |
| C | `user_profile`, continue-where-you-left-off, landing redirect | ~½ day |
| D | "Needs you" rules (§5) with tests | ~1 day |
| E | Search across projects | ~½ day |
| F | After F1/F2: membership-based projects, company switcher, admin tiles | with F1 |

## 9. What is measured

With F3 (usage events) in place: time from login to first action, share of
users who open a tool other than import, and whether "needs you" counts fall
week over week. Until F3 exists, only the counts in §5 are observable.

## 10. Owner decisions

None needed to build this on /v1. Making it the landing page **in production**
is part of the owner's decision on promoting /v1.
