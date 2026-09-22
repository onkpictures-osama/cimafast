# B5 — "Subscription Gates" (بوابات الاشتراك)

### Subscription tiers — proposal

🗒️ **Proposed 2026-09-22 by the owner. Not scoped, not built, and explicitly
NOT to be deployed until the owner and Mohamed El-Zayat discuss it.** This
doc exists to hold the numbers and the analysis so that discussion has a
fixed reference, not to describe anything live in the product.

## The numbers as given

### Enterprise (production companies & agencies)

| Tier | $/month | Projects | Seats/project | Tokens/month |
|---|---|---|---|---|
| Standard | 499 | 2 | 15 | 15,000 |
| Pro | 1,299 | 5 | 15 | 45,000 |
| Ultimate | 3,999 | 20 (parallel) | 20 | 150,000 |

### Individual (freelancer / solo filmmaker)

| Tier | $/month | Projects | Seats | Tokens/month |
|---|---|---|---|---|
| Standard | 39 | 2 | 3 | 2,000 |
| Pro | 99 | 5 | 6 | 6,000 |

### "Dummies" (no subscription — pay-as-you-go token packs)

| Pack | Price | Tokens | $/token |
|---|---|---|---|
| Starter | 9 | 700 | 0.0129 |
| Most popular | 29 | 2,500 | 0.0116 |
| Best value | 79 | 7,500 | 0.0105 |

## What I understood from this

Three tiers map to three distinct personas, and the shape of each tier
matches the persona, not just its price:

- **Enterprise** scales *capacity*: projects (2→5→20), seats/project (15→15→20)
  and tokens (15k→45k→150k) all grow together as a company runs more
  productions in parallel. "20 (parallel)" on Ultimate reads as a concurrency
  cap, not just a project count — worth confirming in the discussion.
- **Individual** is much smaller on every axis, but **seats > 1** (3 and 6) even
  though the persona is "solo." That's a deliberate, sensible choice — a
  freelance filmmaker still works with a small crew (an editor, a DP) even
  without being a company — but it means "Individual" shouldn't be marketed
  as strictly solo, or the seat count looks like a mistake.
- **"Dummies"** has no seats and no project count at all — just tokens. That's
  the biggest structural difference, not just a smaller price: this tier
  isn't buying capacity in the ERP sense (companies → projects → memberships,
  per F1) at all. **Open question for the discussion:** does this persona's
  "wizard" flow even create a company/project row in the existing data model,
  or is it a separate lightweight path that bypasses F1 entirely? That's an
  architecture decision, not just a pricing one, and it should be settled
  before this is scoped as buildable work.

### The per-token price runs backwards from what it looks like at first glance

Computing $/token for every tier:

| Tier | $/token |
|---|---|
| Enterprise Standard | 0.0333 |
| Enterprise Pro | 0.0289 |
| Enterprise Ultimate | 0.0267 |
| Individual Standard | 0.0195 |
| Individual Pro | 0.0165 |
| Dummies Starter | 0.0129 |
| Dummies Popular | 0.0116 |
| Dummies Value | 0.0105 |

The *cheapest* tokens are in the no-subscription "Dummies" packs, and the
*most expensive* tokens are in the priciest Enterprise tier — the opposite of
the usual SaaS pattern where paying more gets you a volume discount. That's
not necessarily wrong: Enterprise's price is mostly buying seats, parallel
projects and collaboration infrastructure, with tokens bundled in, not buying
tokens as the main product — so a per-token comparison across tiers is
comparing different things. But it's worth the two of you stating that logic
explicitly (and deciding if it's the intended story), because a customer who
compares tiers by $/token alone will read it as "Enterprise is a worse deal,"
which undercuts the upsell unless the seats/projects value is made obvious in
how it's marketed.

## Renaming — matched to the three personas described (first pass)

The owner's framing was: a plain **user** with no industry background, who
uses a **wizard** to quickly create a story and simple details for an ad or a
social-media video without going deep into detail; separately, **filmmakers**
or any kind of individual **artist**; separately, **giant production
companies** running five, ten, twenty productions at once.

- **"Dummies" → not this, anywhere customer-facing.** It's a fine internal
  shorthand but reads as "for stupid people" to an actual customer, in both
  English and Arabic. Options that keep the "quick, no depth, no commitment"
  meaning without the insult: **Go**, **Quick Create**, **Starter**, or
  **Social** (ties directly to the stated use case — ads and social-media
  video). Given the product's own name is "CimaFast," **"CimaFast Go"** reads
  well as a tier name across both languages.
- **"Individual" →** already accurate and neutral; could sharpen toward the
  filmmaker/artist framing with **Creator** or **Indie**.
- **"Enterprise" →** already the standard SaaS term and matches "production
  companies and agencies" directly; I'd keep it rather than reach for
  **"Studio,"** since the product itself is already called "CimaFast Studio"
  and reusing the word for a pricing tier invites confusion. **"Agency"** is
  a reasonable alternative given agencies were named explicitly, if the
  owner wants something more specific than the generic SaaS term.

*(Superseded in part by the refined pass below — kept here so the discussion
can see how the naming moved, not just where it landed.)*

None of this is decided — it's framed as options for the discussion with
Mohamed El-Zayat, not a recommendation to act on unilaterally.

## Why Enterprise's value is bigger than tokens (owner's reasoning, 2026-09-22)

The owner's own explanation for the per-token asymmetry above, worth keeping
verbatim in substance: an Enterprise subscription buys the right to run
projects on a database that **stays with us on our servers** — the same
infrastructure that, in aggregate across many individual subscribers, holds a
large base of users. On top of that sits everything a company actually pays
for when it runs a production and can't afford to get wrong: reports,
scheduling, call sheets, analytics, image/video generation, deep day-to-day
use of the system. That operational load costs a production company real
money to run without CimaFast; the system replaces that cost, which is where
Enterprise's value actually sits — not in the raw token count. The cheap,
no-subscription tier has a different goal entirely: fast, full video
generation aimed at reach/virality, not running an operation. This confirms
the read above (Enterprise's price is buying operational infrastructure, not
tokens) directly from the source rather than as an inference — good to state
this explicitly in however the tiers get marketed, per the note above.

## Naming — refined 2026-09-22

The owner liked the first pass but sharpened both personas:

- **The professional/artist tier is not just "filmmaker."** It has to read as
  belonging to *any* creative role in the industry, whatever their job title
  is — director, editor, art director, stylist, VFX supervisor, and so on —
  tied to the word **"artist"** specifically. That rules out **"Indie"** (too
  director/filmmaker-coded) and **"Creator"** (now claimed by the other tier,
  see below). Two options that fit an "artist, any role" framing:
  - **Artist** — the literal, direct match for what was asked: unambiguous in
    both languages (فنان), and doesn't privilege one role (a stylist and a
    VFX supervisor are equally "an artist") the way "filmmaker" or "Indie" do.
  - **Atelier** — more evocative/premium ("an artist's workshop"), still
    reads as artist-coded, a step up in tone from the plain word if that's
    wanted.
  - **"Studio"** was raised again on this round. It still collides with the
    product's own name ("CimaFast Studio" selling a "Studio" tier reads as
    "upgrade to Studio" inside Studio) — flagging that tension again rather
    than dropping it, since the call is the owner's and Mohamed El-Zayat's,
    not mine to override twice.
- **Enterprise stays Enterprise** (or another grand/prestigious word in that
  register) — the owner confirmed this direction rather than asking for a
  change, consistent with the reasoning above: this tier's story is scale and
  operational weight, and "Enterprise" already signals that without
  competing with the artist-tier naming.
- **The no-subscription/wizard tier's persona got more concrete:** not just
  "someone with no industry background," but specifically e.g. a shop owner
  who wants a quick social-media ad, or a content creator who wants a video
  made fast. The owner's own words for this persona were **"Content
  creator"** — which means **"Creator"** (my first-pass suggestion for the
  *Individual* tier) actually belongs here instead, not on the artist tier;
  noted above so the two tiers don't end up competing for the same name.
  Candidates for this tier now: **Creator**, **Social**, or **CimaFast Go**
  (from the first pass) — all still consistent with "quick, no depth, no
  commitment."
