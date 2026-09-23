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
6. **Three stages, always.** Every film or series moves through three sequential
   stages — **pre-production → production → post-production** — whether the
   track is Classic (physical shoot) or AI-generated. They can overlap at the
   edges in practice, but the product's roadmap and navigation must still read
   as three distinct, ordered stages, so a user always knows exactly which one
   their project is in. No feature is scoped without saying which stage it
   serves. *(Owner, 2026-09-23.)*

## The three stages, mapped

- **Pre-production** — script → breakdown → shots → schedule → call sheets,
  before a single frame is shot or generated. This is where CimaFast has lived
  since day one and is still finishing: Phase 2 and Phase 3 below.
- **Production** — the shoot itself (Classic) or the generation run itself
  (AI-generated): what was actually captured or generated, day by day, against
  what was planned. Exists today only as two under-built items inside Phase 4
  (B2, B4) — undersized relative to being its own stage.
- **Post-production** — everything after the last shot or generation until
  delivery: editing, color, score, sound design, mix, VFX/CGI, graphics and
  mastering. **Does not exist in the product at all today** — no table, no
  screen, no report covers any of it. See the new item under Phase 4.

## Roadmap

Each item: *problem → what we build → done when*. Owner agent in brackets.

### Phase 0 — ERP foundations (before a second company can use CimaFast) — cross-stage

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
  ✅ **On /v1 2026-09-21.** Two tables kept apart: `audit_log` (accountability —
  who changed what, with the old and new values) and `usage_events` (adoption —
  login, screen, export, AI run). Audit rows are written by the data layer
  itself, on the same cursor as the change, so no screen can forget to log and
  the log commits or rolls back with the change. Both scoped per company: a
  company admin sees their company, the operator sees all, everyone else is
  refused. Viewing at `/v1/board/activity/` (Arabic/RTL): usage over the last
  7/30/90 days, plus a filterable table of changes with before/after. Secrets
  are never stored (a password column is logged as *changed*, never with its
  value); a 143-scene import is one row, not thousands; a failed log never
  breaks a user's save. Tests: `tests/test_audit.py` (22 checks).
  Still to come: retention/pruning of old rows, and exporting the log to a file.
- **F4 Off-site encrypted backups** [infrastructure] — ✅ **done 2026-09-21.**
  Nightly: encrypted on the server (gpg AES-256), pushed to the private repo
  github.com/onkpictures-osama/cimafast-backups, then downloaded back, decrypted
  and restore-drilled. Documented in that repo's README and
  `/opt/cimafast-backup/README.md`.

### Phase 1 — A home for every user — cross-stage

- **H1 User home (concierge)** [production, chief-engineer]
  After login, users land in whatever project was open last; tools are scattered.
  → A home page: my companies and projects (with progress and next step), my
  tools grouped by production phase, what needs me by role, continue where I left
  off, search across my projects. *Done when* a new user reaches their first
  useful action from the home page without help. **Build plan:
  `HOME-PAGE-PLAN.md`** (covers H1 and H2).
  ✅ **On /v1 2026-09-21** (owner: "home first", before F3): https://cimafast.io/v1/home/.
  Arabic only for now.
- **H2 Deep links** [chief-engineer] — `?project=` and `?tab=` so every card,
  notification and agent post opens the exact screen (supported by `st.tabs(default=)`). ✅ **On /v1 2026-09-21**, with lazy tabs.
- **H3 Onboarding** [production] — a sample project and a guided first import,
  so a new company sees the full pipeline before loading its own script.
- **H4 Targeted change notifications** [production, infrastructure] —
  🗒️ **Specified 2026-09-23** [production]. `F3`'s audit trail records who
  changed what but nothing pushes it to the people it affects — a department
  head only finds out a location or shoot day changed by opening the app and
  looking. Builds on `audit_log`: attach the department/role a change concerns
  (not just the user who made it), surface it as a notification (bell icon on
  home + sidebar) that deep-links straight to the changed item via the
  existing `H2` mechanism. *Done when* a change to a scene's location or a
  shoot day's schedule is visible, same session, to the department it
  concerns, without a manual refresh.
  ✅ **On /v1 2026-09-23.** Every audit row is tagged with the departments it
  concerns (department read from the user's job title; an unclear title sees
  everything). Bell in the sidebar and on `/v1/home/`, polling every 30s; a
  scene notification opens that scene's edit form (`&item=`), a shoot-day one
  opens the schedule board.
- **H5 Item-level comments** [production, chief-engineer] —
  🗒️ **Specified 2026-09-23** [production]. No communication path exists
  inside the product at all — not a team chat, not a comment. The workflow
  need is narrower than a chat: a note thread on a specific item (a scene, a
  location, a shoot day), the way a production actually leaves feedback on one
  thing, not an open channel. A bridge to an outside channel (email/WhatsApp)
  is a distinct, bigger decision and is not part of this item. *Done when* a
  user can leave and read a comment on a scene/location/shoot day, and the
  people it notifies (via H4) can jump straight to the thread.

### Phase 2 — Complete the core pipeline (where users stall today) — pre-production

- **P1 Starter shots from the AI analysis** [universal-creative, chief-engineer]
  141 scenes carry suggested shots nobody sees; 0 shots exist. → Show the
  suggestion on each scene and create editable starter shots per scene or in bulk.
- **P2 Reference images at scale** [universal-creative, chief-engineer] —
  character image generation (today a stub) at parity with locations; bulk
  "generate missing". 🗒️ **Scoped 2026-09-23, from owner feedback:** the
  location generator (`image_gen.py`, `ui.render_image_picker`) only ever sends
  a text prompt — no reference image in or out, and the "extra details" box the
  user sees is blank; the full prompt it builds from the location's own
  description is assembled server-side and never shown. Character generation
  isn't a lesser version of this — it's `st.info("🔒 ميزة توليد صور الشخصيات
  الذكية قيد التطوير")` (`views/characters.py:116`), a dead radio option. →
  1) **Reference-image input**, not just text: let the user attach the actor's
  own photo and/or a background/location photo alongside the prompt, so the
  generated image is conditioned on them, not description alone — needs
  `image_gen.generate_image` to send image content, not just a text message,
  and confirmation the OpenRouter model accepts multi-image input (fall back to
  a model that does if `google/gemini-3.1-flash-image` doesn't).
  2) **A few quick picks, not free text** — shot size reusing the existing
  `SHOT_SIZE_OPTIONS` vocabulary (already used for shots, never offered here)
  plus one or two more (e.g. indoor/outdoor light). Minimal copy — one line of
  instruction, no paragraphs.
  3) **The prompt box arrives pre-filled**, composed from what script analysis
  already stored for that character/look (`personality_notes`, and for the
  look: `apparent_age`, `makeup_state`, `hair_state`, `wardrobe_description`,
  `description`) or that location — editable before generating, not a blank
  box the user fills from memory of their own script.
  *Done when:* a character with a filled-in look but no reference image can
  generate one — the prompt box already reads a real paragraph built from that
  look's stored fields, the user can attach the cast actor's photo and a
  location/background photo, pick a shot size, and get an image conditioned on
  both — with parity on the location side (prompt visible and editable there
  too, not just characters).
- **P3 Location model** [universal-creative, production] — sites and rooms
  (parent/child), city and address, a merge tool for duplicates. Scheduling,
  scouting and call sheets all depend on it.
- **P4 Analysis reliability and cost** [universal-creative, infrastructure] — a
  run that returns 0 scenes is a failure, not "done"; never charge twice for the
  same file; show AI spend per project and company.
- **P5 Looks and continuity** [universal-creative] — scenes that note a look
  change create or link a look; continuity-sensitive props tracked across scenes.
  🔎 **Scoped 2026-09-23**, after an owner report that "adding a state to a
  character doesn't work well." Read `views/characters.py`, `repo.py`,
  `views/shots.py`, `views/scenes.py`, `importer.py`, `database.py` end to end;
  the look feature is half-built, not absent:
  - `character_looks` already has `is_default`, but no code path ever sets or
    shows it except `importer.py`'s AI-import, which auto-creates one
    `'المظهر الافتراضي'` row per character. A character added by hand from
    "➕ إضافة شخصية جديدة" in `views/characters.py` gets **zero** looks — and
    with zero looks it cannot be cast in a shot at all (`look_labels_of_project`
    only returns rows that exist), which is very likely the "مش شغال كويس"
    the report is about: the character exists, but nothing tells the user why
    it's missing from every shot's cast picker until they find the separately
    hidden "➕ إضافة مظهر إضافي لشخصية" expander.
  - There is no way anywhere in the UI to mark a look as the primary one or to
    change which look is primary once a character has more than one — the
    `is_default` flag is write-only from one code path (import) and read
    nowhere.
  - `scene_characters` only stores `character_id` — it has no `look_id`.
    Looks can only be assigned at the **shot** level
    (`shot_characters.look_id`), so "which state is this character in for this
    scene" is not representable at all until the user builds a shot; a scene
    with no shots yet (most scenes, per P1) has no recorded look for anyone in
    it, and per-scene continuity/costume reports have nothing to read.
  - The shot-level look picker (`views/shots.py`) is a flat, unscoped
    `look_labels_of_project(project_id)` — every look of every character in
    the whole project, not filtered to the cast already chosen for that scene.
    On a real feature-length project this is a long unsorted list to search
    every time, and nothing stops a shot from casting a character/look that
    was never added to the scene.
  - The AI already detects this exact problem — `ai_prompt.py`'s
    `look_change_notes` ("لو أي شخصية غيّرت شكلها أو ملابسها أو حالتها الجسدية
    خلال المشهد") — but the note is dead text: `importer.py` stores it on the
    scene, `repo.py` only ever counts it (`scenes_with_look_change`), and
    `home.py` shows just that count as a dashboard tile. The actual sentence
    the AI wrote about *what* changed is never shown to the user and never
    turns into a look.
  - **Proposed shape**, in order of dependency: (1) every character always has
    exactly one default look — create it automatically on manual add too, and
    block deleting the last remaining look; (2) put looks on the character
    card itself as first-class — "المظهر الرئيسي" plus a list of additional
    looks, each with a "خليه الأساسي" action, instead of a separate hidden
    expander named "إضافي"; (3) add `scene_characters.look_id` (nullable →
    defaults to the character's current default look), with a per-scene
    picker so wardrobe/continuity has an answer at the scene grain, not only
    once shots exist; (4) scope the shot-level look picker to the scene's cast
    and default each character to whatever look was set for the scene, with
    an explicit override only when a shot needs a different look than the
    rest of its scene; (5) turn `look_change_notes` into an action, not a
    stat — surface it on the scene as "الذكاء الاصطناعي رصد تغيير مظهر لـ
    [الشخصية] هنا، تحب تضيف مظهر جديد؟", pre-filling the new look's
    description from the AI's own sentence and offering to set it as this
    scene's look going forward. *Downstream cost of not doing this:* every
    costume/continuity report the product could offer (`export.py`) has
    nothing to group by below "whole character," so a wardrobe department
    still needs to rebuild this by hand from the script exactly as if
    CimaFast never analyzed it.
- ⭐ **P6 "Production Memory" (ذاكرة الإنتاج) — learn from users' own
  linking choices, feed it back into analysis**
  [universal-creative, infrastructure] — 🗒️ **Proposed 2026-09-22, not
  scoped yet — topic to discuss at length with the owner and Ziad before
  building.** Today every project starts analysis from a blank slate: a
  location or character comes out of script analysis as a bare name, and a
  user fills in its description and every prop/wardrobe link by hand, even
  though users make the same kind of linking decision constantly across
  their own projects. Checked the codebase for any existing learning loop —
  there isn't one (`audit_log`/`usage_events` record *that* a field changed,
  not a queryable "what got linked to what" dataset; `location_matcher.py`
  is a fixed regex/dictionary matcher, not learning). Idea: capture what
  users actually choose and add while working inside their projects (a
  database of real linking decisions — locations, characters, descriptions,
  which props/wardrobe belong to which character/scene) and feed it back
  into script analysis, the very first step, so locations, characters, their
  descriptions and full details come out pre-filled instead of empty. Users
  can still edit anything the AI got wrong — analysis proposes, it never
  silently overrides a human edit. *Open questions for that discussion:*
  what counts as a reusable pattern vs. one company's private data (must not
  leak one company's project details into another's, per Principle 1);
  what "done" looks like; who owns the review before this goes further than
  a proposal.
- ⭐ **P7 "Universal Analyst" (العقل الشامل) — a universal script-analysis
  prompt across production types**
  [universal-creative] — 🗒️ **Proposed 2026-09-22, not scoped yet — same
  discussion as P6.** The analysis prompt today isn't developed to
  distinguish a series from a feature film from an ad from a short video, or
  a professional production user from someone with no industry background.
  Idea: develop the core analysis prompt so the same agent reads screenplay
  or brief-style input across all of those production shapes and industry
  norms, and adapts its questions/explanations to how much the user already
  knows about the craft — still bound by the existing rule that extracted
  data must mirror the source exactly, never invent content
  (`cimafast-never-invent-data`).
- ⭐ **P8 "Living Script" (السيناريو الحي) — a dedicated screenwriting app
  with a CimaFast-native script format**
  [universal-creative] — **Highlighted 2026-09-22 — priority discussion
  topic, not scoped, not built, not to be deployed.** A "Word, but for
  screenwriters": writers work in standard screenplay format and tag
  characters/decor/props inline as they write, with auto-detection asking
  short clarifying questions ("is this a location state, a different
  outfit, whose prop is this, dialogue or description?"), so the full
  story's detail exists as structured data inside the script file itself —
  saved in a new CimaFast-owned format instead of `.docx`/`.pdf`. This is
  the source-fidelity version of P6 (tag it live, at the moment the writer
  knows the answer, instead of inferring it later) — read together with P6
  in that discussion, not separately. Full writeup, analysis and open
  questions (adoption cost of a new file format, flow vs. interruption,
  relationship to the existing importer, honest scope) in
  **`SCRIPT-EDITOR-PLAN.md`**.
- ⭐ **P9 "Talent Vault" (خزانة المواهب) — an Actor role and a cross-company
  casting directory** [chief-engineer, universal-creative, production] —
  🗒️ **Proposed 2026-09-22; owner requested it be built 2026-09-23, with a
  data-safety boundary the orchestrator set: real named actors get only
  legitimate public bio/filmography data, never invented phone
  numbers/measurements/habits — see `ACTOR-CASTING-PLAN.md`'s 2026-09-23
  section for the full reasoning and the safe seed-data approach (fictional
  demo actors carry the rich data, real actors stay honest and sparse until
  they self-register).** A new Actor
  role (their own scenes/shots/wardrobe/props/direction notes), plus a
  searchable directory any director/producer can cast from — actors
  self-register with photos (refreshed every 3 months), measurements, looks,
  skills, showreel links and credits — and an AI matching feature that
  proposes actors for a role from a character's analyzed specs (reads
  together with P7). The first feature that needs to deliberately cross
  company boundaries (a shared talent pool, not per-company data) and the
  first with a real person's personal data to protect, not a company's.
  Full analysis and open questions (platform-wide vs. per-company
  visibility, formal role vs. separate account type, who sees sensitive
  fields, honest scope) in **`ACTOR-CASTING-PLAN.md`**.

### Phase 3 — Scheduling and shoot days (the heart of a production ERP) — pre-production, ending at the handoff into production

- **S1 Stripboard** — built on /v1 (`/v1/board/`): drag-and-drop, suggested
  schedule, company-move and day/night warnings, cast DOOD.
  🗒️ **Gap found 2026-09-23** [production]: `board/app.py` and `board.html`
  schedule scenes onto a day; shots (`اللقطات`) live in a separate, unrelated
  tab and never attach to a shoot day. A schedule a camera department can
  actually shoot from needs the shot list under each scene, not just the scene.
  *Done when* a shoot day in the board shows each scene's shots (type, setup,
  who owns it), not scenes alone.
- **S2 Calendar** — a start date and working days turn the stripboard into dates.
- **S3 Call sheets** — generated per shoot day from the schedule, cast and locations.
  🗒️ **Specified 2026-09-23** [production]: not built yet — no reference to a
  call sheet anywhere in `export.py` or the board. Needed as a printable/
  shareable per-day report (Arabic RTL, matches the brand guide per the
  exported-reports item above): every scene scheduled that day with its time,
  every cast member called with call time, the day's locations and addresses,
  weather/notes field. Pulls only from data already in the schedule (S1+S4) —
  no separate data entry. *Done when* a production manager picks a shoot day on
  the board and exports a call sheet PDF with cast call times and locations
  filled in from existing data, no manual re-entry.
- **S4 Cast and crew directory** — contacts, availability, and the DOOD per person.

### Phase 4 — ERP breadth

Split by stage, per Principle 6 — this phase is where the **production** and
**post-production** stages actually live in the plan, alongside cross-stage
business items. Today only the cross-stage items and two thin production items
exist; post-production is entirely new.

**Cross-stage**
- **B1 Budget and costs** — budget lines per department, actuals, reports.
- **B3 Vendors, equipment and rentals.**
- ⭐ **B5 "Subscription Gates" (بوابات الاشتراك) — subscription tiers &
  pricing** [orchestrator] — 🗒️ **Proposed
  2026-09-22, not scoped, explicitly not to be deployed until the owner and
  Mohamed El-Zayat discuss it.** Three tiers by persona — a no-subscription
  wizard-driven tier for a non-industry user making quick ads/social video, an
  Individual tier for freelancers/filmmakers/artists, an Enterprise tier for
  production companies and agencies running many parallel productions.
  Numbers, analysis and open naming/architecture questions in
  **`SUBSCRIPTIONS-PLAN.md`**.

**Production stage** (the shoot itself, or the generation run itself)
- **B2 Daily production reports** — what was shot vs planned, per day.
- **B4 AI-generated production module** — versioned prompts, generation settings,
  digital-asset tracking, linked to scenes and shots.

**Post-production stage** (everything after the last shot/generation until delivery)
- ⭐ **PP1 "لوحة حالة البوست بروداكشن" (Post-Production Status Board)**
  [production, chief-engineer] — 🗒️ **Proposed 2026-09-23, owner approved
  adding it to the plan the same day ("يلا حطه"); not yet scoped for a build
  order — that is the orchestrator's call.**
  *Evidence:* the product has zero tables, screens or reports for any of the
  seven post-production departments — editing, color grading, score, sound
  design, ADR & final mix, VFX/CGI, and titles/graphics & mastering/QC. A
  production manager or post-producer today tracks this outside CimaFast
  entirely (WhatsApp, a shared spreadsheet, a Drive folder), and there is no
  single place a director or producer can check the state of all seven
  departments at once. Checked the well-known purpose-built tools in this
  space (ftrack/Backlight, Autodesk ShotGrid, Frame.io, Wipster, PIX System,
  Kollaborate, Signiant Media Shuttle) — they are shot-tracking or
  review-and-approve tools built for VFX pipelines or big-studio dailies, not
  a lightweight cross-department status report a producer can hand a director
  who never opens the app; that gap is exactly what small and mid-size
  productions fall back to spreadsheets for, and it's what this item closes.
  *What we build:* a per-project board with one card per department showing
  status (لم يبدأ / جارٍ / في المراجعة / معتمد / محتاج تعديل), the assigned
  studio or freelancer with contact info and location, one or two external
  preview links (Google Drive or whatever the vendor already uses — a URL
  field, never file hosting inside CimaFast), and a lightweight comment
  thread per department. New tables (`post_departments`, `post_status`,
  `post_links`, `post_comments`), each project-scoped and going through the
  existing `audit_log`/permissions layers untouched. A one-click exported
  report (PDF/Word, `export.py` pattern) listing all seven departments' status,
  last update and vendor contact, so a director or producer gets the full
  picture without logging in; any department untouched for 7+ days is flagged
  stale on that report. The department list differs slightly by project track
  (Classic vs. AI-generated) but shares the same tables, screen and report —
  distinct labels, one data model, per how the two tracks are meant to stay
  coherent.
  *Done when:* a post-producer on a real project can update every department's
  status, attach a preview link and a vendor contact, leave a comment, and
  export one report that shows a director/producer the full seven-department
  picture without opening the app — in under two minutes, with stale
  departments visibly flagged.

### Continuous

Performance, the Arabic/RTL design system (glass redesign phases 3–5), test
coverage, security review, and moving screens from Streamlit to the new frontend
one at a time as they are rebuilt.

- **Redesign the Streamlit app sidebar** [chief-engineer] —
  🗒️ **Found 2026-09-23** (owner shared a reference mockup, approved the
  direction: "Yes"). Current sidebar (just tightened for spacing on
  2026-09-23) keeps the documented brand rule — sidebar = the yellow field,
  navy mark (`theme/brand.py`: "سطح فاتح أو الحقل الأصفر → الشخصية كحلي").
  The owner's reference is a deliberate departure from that: dark/navy
  background with the yellow-mark variant, a user avatar photo (no such
  feature exists yet — accounts have no photo field or upload path), English
  taglines not present anywhere in the brand system ("IDEAS TO SCREEN",
  "GOOD STORIES GO FURTHER" — need Arabic-first equivalents, this product is
  Arabic-first per CLAUDE.md), and "الرئيسية"/"المشاريع" as top-level
  drill-down nav items instead of the current flat "مشاريعي أول حاجة تحت
  اللوجو" structure from the 2026-09-22 redesign. *Done when* the sidebar
  matches the approved direction, `theme/brand.py`'s documented surface rule
  is updated to record the sidebar as an intentional exception (not left to
  read as a bug), avatar is a placeholder (initials) rather than real photo
  upload unless the owner asks for upload as its own feature, and the
  MEDIA/STUDIO wordmark inconsistency (flagged 2026-09-23, still open) is
  resolved as part of the same pass since the logo is being touched anyway.

- **Bring exported reports onto the brand guide** [chief-engineer] —
  🗒️ **Found 2026-09-23** (owner: "use branding guidelines for reports").
  `export.py`'s Excel/Word/PDF reports use hardcoded colours (`NAVY #12203D`,
  `YELLOW #E8B923`) from before the brand system existed, and carry no
  CimaFast logo at all — while `theme/brand.py` and `theme/tokens.py` already
  hold the official palette (Navy `#212F70`, Yellow `#FECA05`, Ink `#1B254B`)
  and the approved logo assets (`static/brand/`) used everywhere else in the
  app. *Done when* every exported report (Excel, Word, PDF) uses the official
  brand colours and carries the approved logo, per the brand guide already
  encoded in `theme/brand.py`, with the classic screens' look untouched.

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
4. **Daily decisions/milestones log** — decided 2026-09-22: archive it on
   GitHub, one dated file per day in `logs/` (see `logs/README.md`), sourced
   from commit history and this plan. [infrastructure] to automate.
5. **Sidebar redesign direction** — decided 2026-09-23: owner shared a dark-
   background reference mockup and approved it ("Yes") over the yellow-field
   look the brand guide currently documents for the sidebar. Treated as an
   intentional, scoped exception to that rule, not a reversal of it elsewhere.
6. **Three-stage framing** — decided 2026-09-23: the product and this plan
   always organize around three sequential stages — pre-production →
   production → post-production — for both Classic and AI-generated tracks,
   so a user always knows which stage their project is in. Recorded as
   Principle 6 and in "The three stages, mapped" above.
7. **Post-production status board approved onto the plan** — decided
   2026-09-23 ("يلا حطه"): the post-production stage does not exist in the
   product yet; owner approved adding **PP1** (Phase 4) to this plan.
   Build order/priority is still the orchestrator's call, not decided here.
8. **Sequencing the 2026-09-23 Phase 1/3 additions (H4, H5, S1's shots gap,
   S3)** — decided 2026-09-23, orchestrator, no owner call needed (this is
   priority ordering inside the approved plan, not a scope change):
   **H4 before S3.** H4 is the cheaper build — it only attaches a
   department/role to existing `audit_log` rows and surfaces them through the
   `H2` deep-link mechanism already on /v1 — and `H5` cannot start without it
   (its own done-when clause needs H4 to exist). S3 cannot start immediately
   either way: it depends on `S2` (Calendar — no start date/working days yet)
   and `S4` (Cast and crew directory — no call times stored yet), neither
   built, so H4 has room to land first without costing S3 any time. Landing
   it first also means that by the time call sheets ship, an in-app answer
   already exists to the exact gap flagged — a call sheet going stale the
   moment the schedule changes. Order: **H4 → S1's shots-on-board gap (can run
   in parallel with H4; board/ vs app.py, different surface) → S2 + S4 (S3's
   own unbuilt data prerequisites) → S3 → H5** (blocked on H4 by its own
   spec). Ahead of all of it: **P9 (Talent Vault) and P2 (reference images)
   are already mid-build in this checkout** (uncommitted `views/actors.py`,
   `image_gen.py`, `views/characters.py`, etc.) and hold chief-engineer's
   capacity until that work lands — this ordering applies to what comes after.
