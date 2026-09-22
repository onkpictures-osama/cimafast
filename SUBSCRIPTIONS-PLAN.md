# Subscription tiers — proposal

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

## Renaming — matched to the three personas described

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
  filmmaker/artist framing with **Creator** or **Indie** (the latter carries
  real meaning in the film world — "independent filmmaker" — that "Individual"
  doesn't).
- **"Enterprise" →** already the standard SaaS term and matches "production
  companies and agencies" directly; I'd keep it rather than reach for
  **"Studio,"** since the product itself is already called "CimaFast Studio"
  and reusing the word for a pricing tier invites confusion. **"Agency"** is
  a reasonable alternative given agencies were named explicitly, if the
  owner wants something more specific than the generic SaaS term.

None of this is decided — it's framed as options for the discussion with
Mohamed El-Zayat, not a recommendation to act on unilaterally.
