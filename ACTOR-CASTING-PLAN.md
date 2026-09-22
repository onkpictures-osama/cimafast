# P9 — "Talent Vault" (خزانة المواهب)

⭐ 🗒️ **Proposed 2026-09-22 — topic for discussion/analysis, not scoped, not
built, not to be deployed.** Same status as P6/P7/P8/B5: recorded now,
deployed only after a decision is made. This doc holds the idea and the
analysis so that decision has a fixed reference.

## The idea, as described

A new role: **Actor**. An actor's own view of the system shows their scenes
with full shot detail, their wardrobe, the props/accessories they'll be
holding, and everything about actor direction that the director and script
writer defined for them.

Separately, a **casting feature** for directors and producers: a section
where they can search and shortlist actors — famous or not yet famous —
across the platform, not just people already on their project.

**Actor accounts and profiles:** anyone can register and identify themselves
as an actor at signup. That gets them a profile page: photos (which must be
refreshed every 3 months), height, weight, look, hobbies, skills relevant to
casting (can drive a car/motorcycle, can swim, smokes), well-known videos on
social media, showreel links, and past work/credits.

**AI-assisted suggestions:** when a director/producer asks the system for
casting suggestions on a role, it searches the registered-actor pool and
proposes matches — tying directly into script analysis, since a character's
described specs (physical description, skills, etc.) are what gets matched
against actor profiles.

## What already exists today (checked before writing this, not assumed)

- No `actors` table, no actor account type, no profile/portfolio data model,
  no cross-project search, no matching engine — this is new from zero.
- `casting_director` already exists as a seeded job title
  (`scripts/migrate_tenancy.py`), and `home.py`'s rule table already nudges a
  job title containing "كاستينج"/"اختيار الممثلين" toward the characters tab
  when reference images are missing — a thin existing thread, not
  infrastructure to build on.
- "أيام الممثلين (DOOD)" (Day Out of Days) already tracks which shoot days a
  *character* works (`repo.py`, `board/app.py`) — that's schedule data about
  a character-in-a-project, unrelated to a real actor's own profile.
- `PROJECT_ROLE_OPTIONS` already lists "مسؤول اختيار الممثلين (Casting
  Director)" as a selectable project role string (`database.py`) — cosmetic,
  not a permission or data model.

## Why this is a different shape of feature than everything else so far (analysis)

**This is the first feature that needs to cross company boundaries on
purpose.** Principle 1 in `PRODUCT-PLAN.md` is "multi-company from the
start... no feature may assume one company, project or team" — every table
so far is strictly scoped to one company (F1/F2's whole point). An actor
directory searchable by "famous or not yet famous" actors across the
platform is, by design, the opposite: one shared pool every company's
director/producer can search. That's not a bug to route around, it's a
deliberate exception this needs to state explicitly and design for (who can
see an actor's profile: every company on the platform, or only companies
that have cast them before, or an opt-in visibility the actor controls?).

**It's the second real-person data-ownership question the product has had**
(the first being P6/P8's "whose data is this" question for script choices).
An actor's height, weight, habits (smoking), and photos are personal data
about a real individual who isn't necessarily a member of any company —
they may have no relationship to a production until they're cast. That's a
different consent model than "a producer's own project data": the actor
needs to control what's visible and to whom, not just be a row a company
owns.

**It reads together with P7 ("Universal Analyst"), not separately.** The
matching feature ("suggest an actor for this role") only works if script
analysis already extracts a character's physical/skill specs in a
structured, comparable shape — which is exactly what P7 is about developing.
Worth discussing these two in the same pass.

**Photo freshness (every 3 months) is a real product mechanism, not a
detail.** Nothing in the product today expires or nags about stale data on a
timer — this would be the first. Needs a decision: does a stale profile just
get flagged, drop out of search results, or trigger a reminder to the actor?

## Open questions for the discussion (not decided here)

- Is the talent pool platform-wide (any company can search any registered
  actor), or does each company keep its own roster, or is visibility
  opt-in/per-actor?
- Is "Actor" a formal role in the existing `admin/producer/manager/
  department/viewer` set (F2), or a separate account type outside the
  company/project permission model entirely, since an actor may belong to no
  company until cast?
- Who can see the sensitive fields (weight, smoking, etc.) — every
  director/producer on the platform, or only once a conversation/shortlist
  has started?
- How is photo staleness enforced, and what happens to a stale profile?
- Honest scope check: an actor directory + profile system + a matching
  engine is a substantial subsystem on its own (accounts, profiles, search,
  freshness tracking, cross-company visibility rules) — closer in size to P8
  than to a single roadmap line, worth sizing that way before it's scoped as
  buildable work.
