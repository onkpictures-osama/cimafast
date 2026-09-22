# A dedicated screenwriting app with a CimaFast-native script format

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
