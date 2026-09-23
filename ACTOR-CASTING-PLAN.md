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

## Open questions — resolved 2026-09-23 [production]

- **Visibility: platform-wide, visible-by-default, two tiers.** Public tier
  (name, photo, category, headline credits, links) open to any logged-in
  producer/director once the actor completes a minimum profile — that's the
  whole point of a cross-company pool. Sensitive tier (exact measurements,
  contact, habits, skill detail) gated per-company until that company has
  shortlisted the actor for a role — protects contact info from blanket
  exposure while matching how casting actually works today. Actor can toggle
  "discoverable in search" off entirely, and can opt individual sensitive
  fields (e.g. skills) to always-public if they want to be found on that
  basis. Admin-seeded real-person profiles just render sensitive fields
  "غير متوفر" — no separate claim/verify workflow.
- **Actor is a platform-level account type, not an F2 company role.** A new
  `actors` table sits beside `projects`/`companies`, not nested under one
  company — an actor may belong to zero companies until cast. A join table
  (e.g. `character_actor_casting`: actor_id, project_id, character_id, role/
  date) links a specific actor to a specific character within a project once
  cast, the same shape as the existing scene/shot join tables. The actor's
  own cross-project dashboard is a query filtered by `actor_id` through that
  join table — not F2 permission-table membership in every company that's
  cast them.
- **Sensitive fields gated to an active casting relationship** (shortlisted
  or cast), not open to every browsing company. Log who unlocked it — gives
  the actor visibility into who has their contact info, and costs nothing
  extra since it's just the shortlist row.
- **Photo staleness: visual timestamp badge only, v1.** Store
  `last_photo_update`; show "آخر تحديث: قبل كذا شهر" once >3 months old, to
  both the actor and browsing producers. Do not drop stale profiles from
  search — that punishes actors silently. No notification/email nudge in
  v1 — no notification system exists yet in this product; that's a follow-up
  once one does, not something to bolt on one-off here.
- **UI pattern confirmed**: the owner's alphabet-jump list with a thumbnail
  per row is the right fit — casting is a recognition task, not a
  data-comparison task, and a producer usually already has a name or short
  mental list in mind. Reserve a filterable grid for a later, separate
  AI-matching surface (ties to P7). Default the jump index to Arabic order
  (أ ب ت ث...) since the product is Arabic-first, with English as the
  explicit toggle — not English-first with an RTL patch after.
- Honest scope check (from the original proposal) stands and is now being
  acted on: this is a substantial subsystem (accounts, profiles, search,
  freshness tracking, cross-company visibility, a new join table) — being
  built in phases, starting with the data model + search UI + safe seed
  data (chief-engineer, in progress 2026-09-23), matching engine (P7 tie-in)
  deliberately deferred to a later pass.

## 2026-09-23 — owner requested this be built, with a data-safety boundary

Owner asked directly for this ("يا هندسة عاوزين نضيف في الشخصيات كمان اسم
الممثل وصورته... اعمل بروفايل لابرام سمير وسارة درزاوي وأحمد زاهر... وأي
ممثل اشتغل مع سترايك ميديا... املى الداتا بتاعة بروفايلاتهم صح... فيه
مواقع زي elcinema.com تقدر تجمع منها معلومات"), including named real actors
as seed/demo profiles with full detail (measurements, contact numbers,
hobbies, smoking, driving/swimming ability) sourced from elcinema.com and
social media, to demo and "publish" as templates.

**This moves P9 from "proposed" to "being built" — the system itself is
approved.** But the specific ask to fill named real actors' profiles with
scraped/inferred phone numbers, body measurements and personal habits is a
real problem, not a scoping nuance, and the orchestrator is drawing this
line rather than deferring it:

- **Real, named, identifiable people** (Ibrahim Samir, Sara Aldarzawy, Ahmed
  Zaher, Ahmed El Rafei, Ahmed Fouad Selim, Hussein Fahmy, Kareem Afifi,
  Tamer Hosny, and any real Strike Media roster) get **only what a
  legitimate public source actually states** — real name, public bio,
  filmography/credits, and a properly licensed/attributed public photo if
  one is used, pulled from sources like elcinema.com with the source kept.
  **Fields with no legitimate public source — phone number, body
  measurements, smoking, driving/swimming ability, hobbies — stay empty and
  marked "غير متوفر" for these real people, never invented.** A phone number
  or a personal habit attributed to Tamer Hosny that CimaFast's own agents
  made up is a defamation and privacy problem the moment anyone sees it,
  demo or not — this isn't a company's project data, it's a real person's
  name with fabricated personal claims attached, in a product real
  companies use. No agent is to invent these fields for a real, named
  person, under any framing ("just a placeholder," "just a demo").
- To actually demo the feature's full richness (all fields filled, matching
  working end to end) without that risk: **build 2-3 clearly fictional demo
  actors** (invented names, AI-generated or stock photos, full fields —
  measurements, contact, skills, habits, links) alongside the real actors'
  public-only profiles. The fictional ones carry the rich data that shows
  off the system; the real ones stay honest and sparse until an actor
  actually registers and fills their own profile in, which is the real
  product mechanism this was designed around in the first place (see "Actor
  accounts and profiles" above).
- This also answers one of the open questions above in practice: real actors
  should **self-register and own their data**, not be admin-seeded with
  invented personal details. Seed data proves the UI; it should not be the
  product's answer to "whose data is this."

[production, universal-creative] to resolve the remaining open questions
(visibility model, formal role vs. separate account type) while
[chief-engineer] starts on the data model and the alphabet-jump search UI
described by the owner (type a letter → long filtered name list appears
immediately with a small thumbnail per row; select → full profile) against
the safe seed set above.
