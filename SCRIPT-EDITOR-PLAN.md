# P8 — "Living Script" (السيناريو الحي)

### A dedicated screenwriting app with a CimaFast-native script format

⭐ **Highlighted 2026-09-22 — priority discussion topic, the team will work
on this.** Not scoped, not built, **not to be deployed** — recorded so the
discussion has a fixed reference, same status as `P6`/`P7` in
`PRODUCT-PLAN.md` and `SUBSCRIPTIONS-PLAN.md`, but explicitly called out as
one the owner wants kept in view rather than left as a plain backlog line.

## The idea, as described

A dedicated writing application — "a Word, but for screenwriters" — where a
script writer works in standard screenplay format (the format the
screenwriting manuals describe: scene headings, character cues, dialogue,
action lines) and, while writing, tags story elements inline: character
names, the decor/location a scene belongs to, props. The app runs
auto-detection as they write and asks short clarifying questions in place —
*"what is this: a location state, a different outfit for a character, an
extra look for a character, whose prop is this, is this dialogue or
description?"* — so that by the time the writer is done, the full story's
detail, down to its most complex parts, already exists as structured data
**inside the script file itself**, not as prose to be reverse-engineered
later.

The output isn't a `.docx` or `.pdf` — it's a new, CimaFast-owned file
format/extension for this editor, produced by the tool screenwriters would
use to write.

## Who reaches this tool, and why (owner's elaboration, 2026-09-22)

Real production practice, as described: work on a film or series starts from
three roles — producer, director, script writer. That triangle decides how
production will run, what gets written, where the story goes, and its size
and detail. On an Enterprise subscription, these three are the company's
first users.

Most of the time in real production the script isn't written cold: a
treatment/synopsis tracks the story's events as an idea first, and only
after the trio agrees does the writer produce the actual script — precisely
so the writer doesn't write pages the director rejects, or that turn out not
to be production-feasible, unless the script was already written in full
independently of that agreement. So the producer, director and writer are
usually all present *at the writing stage itself*, not just reviewing a
finished draft afterward.

Two entry paths follow from that: the writer opens their own account and
either brings an old script to load into the new editor to keep working on
it, or the producer creates the writer's CimaFast account and hands them an
existing script to put on the system.

## The confirm flow, more concretely

As the writer works — fresh or imported — the system walks the script line
by line, proposes tags, and asks for confirmation on each: *"Is this a
location state? Clothing for a character? Are these two character names
actually the same person?"* Two ways this could surface, both raised in the
same breath: a running questionnaire the writer works through, or a mark/
highlight directly on the specific lines or names that still have open
questions, so the writer goes and resolves those in place. Either way, the
writer keeps confirming until the script reads as unambiguous to the system —
at which point everything downstream (breakdown, shots, reports) is grounded
in something the writer actually attested to, not a guess.

## Role-based default views — a related but distinct idea, worth scoping separately

Once inside, each role should see the part of the system relevant to their
work, not the same undifferentiated view everyone gets today. As described:
script writer and director mainly work from shot lists (their découpage);
the producer mainly works from reports; producer and director can both see
everything, but each role still has its own prioritized lists within that.

**Checked against the current code before recording this — partial
infrastructure already exists, this isn't a blank page:**
- `home.py`'s `needs_you()` already surfaces role- and job-title-specific
  "needs your attention" items per project (e.g. a `manager`-role user whose
  job title contains "مخرج" (director) already gets shot-related alerts
  pointing at the shots tab — already close to what's being asked for the
  director role).
- But there is **no formal `director` or `script writer` role** in the
  permission system — `permissions.py`'s role set is
  `{operator, admin, producer, manager, department}` (F2). "Director" and
  "script writer" exist today only as free-text job-title keywords matched
  inside `home.py`'s rule table, which is fragile (depends on the exact
  Arabic word appearing in a free-text job-title field) and only drives a
  "needs attention" alert list, not a full default view.
- And **reports aren't a target in that rule table at all today** — nothing
  currently makes a producer's default view be reports.

So this piece isn't "build a new role system from scratch" — it's extending
the existing `home.py`/H1 mechanism (and possibly promoting director/script-
writer to real roles in F2) rather than inventing a parallel one. Worth
scoping as its own conversation once P8 itself is further along, since it's
really about *every* role's home experience, not specific to the script
editor.

## Why this matters (analysis)

**This is the source-fidelity answer to `P6`, not a separate idea.** `P6`
proposed learning from users' linking choices after the fact — mining
`scene_props`/`character_looks`/etc. once a project is already underway — to
pre-fill future analysis. This proposal captures the same information at the
one moment it's known with certainty: when the writer decides it. A writer
tagging "this is Nadia's new look, she's changed clothes after the fire"
while typing it is ground truth; an AI inferring the same thing from finished
prose, or CimaFast inferring it from how other users tagged similar scenes,
is a guess. If this ships, it doesn't just add a feature — it changes what
`P6`'s dataset is: instead of being built by mining edits after import, it
could be captured live, tagged by the person who actually knows the answer.
Worth raising in the same discussion as `P6`/`P7`, not on its own.

It also serves the standing rule that extracted data must mirror what the
writer actually wrote, never invent content
(`cimafast-never-invent-data` — a durable product principle already in
force): a writer confirming their own tag in real time is the strongest
possible version of that rule, stronger than any AI parser applied
afterward.

## Open questions worth raising in the discussion, not decided here

- **Adoption friction of a brand-new file extension.** Professional
  screenwriters already have tools and muscle memory — Final Draft (`.fdx`),
  Fountain (a plain-text screenplay format already used industry-wide),
  Celtx, WriterDuet. Asking them to adopt a wholly new proprietary format is
  a real behavior-change cost, separate from whether the editor itself is
  good. Worth considering whether the new format should be an *extension* of
  an existing open one (e.g. Fountain plus embedded tag metadata) rather than
  invented from zero — same benefit (tags travel inside the file), much
  lower adoption cost, and an easier import path for scripts already written
  elsewhere.
- **Interruption vs. flow.** Asking "what is this?" for every tag while
  someone is mid-scene risks breaking a writer's flow, which screenwriters
  protect fiercely. Likely answer, consistent with how `P6` is framed
  elsewhere in the plan ("AI proposes, human edits, never silently
  overrides"): auto-detect and tag with a best guess inline, let the writer
  confirm or correct with a light touch (not a blocking dialog), rather than
  stopping them to ask every time.
- **Where this app lives relative to the existing importer.** Today CimaFast
  ingests an already-written script (Word/text/JSON) and reconstructs
  structure after the fact (`script_parser.py`, `ai_jobs.py`,
  `location_matcher.py`). This proposal is a second, earlier entry point —
  worth deciding whether it replaces the importer for scripts written inside
  CimaFast, or sits alongside it for scripts that arrive from elsewhere.
- **Scope.** A real screenplay text editor with live auto-detection is a
  substantial standalone application, not a small feature — closer to a new
  product surface than a tab. Worth sizing honestly against the rest of the
  roadmap before it's scoped as buildable work.
