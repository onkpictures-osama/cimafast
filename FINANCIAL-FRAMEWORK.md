# CimaFast financial framework

🗒️ **Synthesis, 2026-09-22 — not decided, not built, not deployed.** This
pulls the revenue model in `SUBSCRIPTIONS-PLAN.md` and the cost model in
`AI-PROVIDER-COSTS.md` into one reference so pricing, cost and margin are
governed together instead of drifting across two documents. It restates
numbers already worked out in those two files rather than re-deriving them —
see them for the full methodology and sourcing. Like both source docs, this
is explicitly **not** a decision: tier pricing stays the owner's and Mohamed
El-Zayat's call, not something an agent locks in.

## 1. Revenue model — three tiers, three personas

| Persona | Tiers | What it's buying |
|---|---|---|
| **Enterprise** (production companies/agencies) | Standard $499 · Pro $1,299 · Ultimate $3,999 /mo | Operational infrastructure — projects, seats, collaboration, reports/scheduling/call-sheets, hosted DB — with AI tokens bundled in, not sold as the product |
| **Individual/Artist** (any creative role — director, editor, art director, VFX, etc., not just "filmmaker") | Standard $39 · Pro $99 /mo | Smaller-scale version of the same operational product, still multi-seat (3–6) since even solo artists work with a small crew |
| **Go/Creator** (no subscription, "Dummies" internally — rename before anything customer-facing) | Starter $9 · Popular $29 · Value $79, pay-as-you-go | Fast, full video generation for reach/virality — not the ERP product at all; may not even create a `companies`/`projects` row (open question, §9) |

Full tier tables, the per-token pricing analysis, and the naming discussion
(**Artist**/**Atelier** for Individual, **Creator**/**Social**/**CimaFast Go**
for the no-subscription tier, **Enterprise** unchanged) are in
`SUBSCRIPTIONS-PLAN.md` — this framework doesn't repeat them.

**Governing logic, from the owner directly (2026-09-22):** Enterprise's price
is buying the infrastructure a production company would otherwise have to
run itself; Go is a different product goal entirely (virality, not
operations). This is *why* the per-token price is allowed to run backwards
from typical SaaS (cheapest tokens in the no-subscription tier, priciest in
top Enterprise) — the two tiers are not selling the same thing, so comparing
them by $/token alone is misleading and needs to be said explicitly in how
tiers are marketed.

## 2. Cost structure

### 2.1 What's actually modeled: AI generation

The only cost basis worked out so far is AI media generation, from
`AI-PROVIDER-COSTS.md`. One mix-independent unit ties images, video and voice
together:

| Action (standard quality) | Vendor cost | = tokens |
|---|---|---|
| 1 image | ~$0.03 | 1 |
| 1 sec standard video | ~$0.09 | 3 |
| 1,000 voice characters (Arabic-capable) | ~$0.10–0.12 | 4 |
| 1 sec premium video (4K/HDR/audio) | $0.40–2.08 | 15–70 |

At this $0.03/token cost basis and the tier token counts as currently
drafted, **every tier except Enterprise Standard loses money on vendor cost
alone if subscribers use their full monthly pool** — Go/Dummies worst of all
(–133% to –184% margin), because it's priced at the industry's lowest point
while defined as video-only, the most expensive media type. This is the
single most important number in this framework: the draft prices and the
draft token counts are not consistent with each other yet.

### 2.2 What's NOT modeled — a real gap, not an oversight

This framework only prices the AI-generation layer. It does **not** yet
include, and has no sourced numbers for:

- **Hosting/infrastructure** — VPS, bandwidth, storage, backups (F4).
- **Text/LLM cost** — script analysis and the OpenRouter text calls that
  already run today (`AI-PROVIDER-COSTS.md` §2 flags this as a follow-up,
  not yet priced).
- **Payment processing fees** (Stripe/PayPal-class, typically 2.9%+$0.30, or
  an Egyptian gateway's equivalent for the EGP card).
- **Support, success, and account management** for Enterprise accounts.
- **Customer acquisition cost.**

No number below should be read as "the margin" — it's "the AI-generation
margin," a necessary input, not the whole P&L. Flagging this explicitly
rather than presenting a partial number as complete (per the standing rule
that CimaFast data work must never imply more than what's actually sourced).

## 3. Margin policy — two cards, one decision needed

`AI-PROVIDER-COSTS.md` §5.5–5.6 worked out two complete rate cards against
the same $0.03/token cost basis. The only variable between them is resale
price per token:

| | Resale rate | Margin | Enterprise Standard tokens | Go Starter clips |
|---|---|---|---|---|
| **Card A (50% margin)** | $0.06/token | 50.0–50.4% | 8,300 (vs. 15,000 drafted) | 10 (5-sec clips) |
| **Card B (33% margin, "50% markup on cost")** | $0.045/token | 33.3–35.0% | 11,088 | 13 |

They trade off mechanically: Card B gives customers ~33% more tokens at the
same sticker price and costs CimaFast about a third of its profit per
subscription to do it. Neither is more "correct" — Card A is the safer
floor if usage runs hotter than modeled, Card B looks more generous next to
Kling/Runway/Pika-style consumer credit counts. **This needs an explicit
owner+Mohamed pick, since every other number in this framework (tokens
included, EGP price, Go clip counts) is downstream of it.** Recommend Card A
(50%) as the working default until that conversation happens, since it's the
safer error to default to — cheaper to loosen later than to have sold Card B
and have to claw back.

**The highest-leverage lever either way:** default generations at
draft/preview quality with a paid step-up to finish, which alone gets the
Enterprise/Individual tiers to 70%+ margin *without changing any listed
price* (§5.4). This mirrors how production actually works — cheap, plentiful
previs; a chosen final frame rendered once — so it's a product decision, not
just a pricing one, and should be scoped alongside whichever margin card is
picked.

## 4. Go/Creator: sell clips, not tokens

The drafted 700/2,500/7,500 "tokens" for this tier don't survive at any
reasonable cost basis, because they were priced as if this tier generated
images. **Recommendation: drop "tokens" for this tier entirely and sell by
video-clip count**, which also matches the persona's own mental model
("10 videos for my ad"):

| Pack | Price | Clips (5-sec) at 50% margin | at 33% margin |
|---|---|---|---|
| Go Starter | $9 | 10 | 13 |
| Go Popular | $29 | 32 | 42 |
| Go Value | $79 | 87 | 117 |

Benchmarked against Higgsfield/Magnific, CimaFast's clip counts land in the
same range at roughly half to two-thirds the price at every comparable price
point (`AI-PROVIDER-COSTS.md` §8) — real headroom to test, or a sign
Higgsfield is pricing in something not modeled here (better model, its own
margin target, brand). Not proof either way on its own.

## 5. Currency: EGP card and FX exposure

`AI-PROVIDER-COSTS.md` §6 has the full EGP card (×52, rounded per persona
convention — clean numbers for Enterprise/Individual, "٩٩"-charm pricing for
Go). The framework-level point: **every vendor cost here bills in USD; an
EGP-denominated subscription fixes revenue in EGP while cost stays tied to
the dollar.** If EGP weakens, the margin computed today erodes silently —
the invoice number never changes but the real margin does. Two mitigations,
not mutually exclusive, need a decision:

1. **Re-peg the EGP card on a fixed schedule** (quarterly is reasonable).
2. **Bill Enterprise in USD, EGP only for Individual/Go** — moves FX
   exposure off CimaFast's books for the highest-cost tiers, and matches how
   Enterprise-scale software is usually already bought.

## 6. Vendor strategy

Current state: one integration (OpenRouter, image only), chosen for
convenience — "the only account already on the server with image-capable
models" — not reliability. OpenRouter has no SLA and two documented 2026
outages. Recommended target (`AI-PROVIDER-COSTS.md` §3.2), a 3-provider stack
behind one abstraction interface rather than hardcoding a single vendor:

1. **fal.ai** (or Eden AI) — breadth + built-in fallback routing, everyday
   generation.
2. **One hyperscaler** (Microsoft Foundry fits today since image gen already
   runs on an OpenAI model) — indemnified path, Enterprise-tier/client-facing
   work only, not the whole pool.
3. **ElevenLabs, direct** — the only vendor found with real Arabic
   multilingual voice quality; not covered by any of the aggregators above.

No hyperscaler indemnifies third-party models it resells (Seedance, Kling,
etc.) — indemnification and model breadth trade off against each other, so
"indemnified" should only ever be claimed for the Foundry-routed share of
usage, never the whole plan (§3.1's ring-fence recommendation, §7 below).

## 7. What has to be built before any of this is enforceable

None of the above can actually be charged for yet:

- **No token ledger** — `usage_events` logs that a generation happened, not
  its token cost.
- **No quota enforcement** anywhere in the code.
- **No provider abstraction** — `image_gen.py` hardcodes OpenRouter directly.
- **No ring-fenced indemnified sub-pool** — needed once Foundry is added, so
  indemnified capacity can't silently be spent as regular draft tokens.

Recommended build sequence (unchanged from `AI-PROVIDER-COSTS.md` §5.8):
ship metering + a soft quota warning first, watch real redemption for at
least a month (even at $0 / founding-customer pricing), then lock tier
numbers against real usage data instead of the vendor-list-price worst case
this framework is built on. **Nothing in this document should be treated as
final pricing until that real-usage pass happens** — everything above is a
floor-case model against list prices with 0 paying subscribers today.

## 8. Governance

- Pricing/margin decisions are **owner + Mohamed El-Zayat**, not an agent
  call — matches how both source docs were scoped from the start.
- Re-check vendor pricing before any contract is signed — AI provider prices
  move monthly/weekly and this framework is a September 2026 snapshot.
- Re-peg the EGP card on a fixed cadence (§5) once it ships.
- Revisit the margin-card choice (§3) and the quality-tiering lever once
  real redemption data exists — don't let a floor-case model calcify into
  permanent policy.
- Record each pricing/margin decision in `logs/YYYY-MM-DD.md` the way other
  owner decisions already are (`PRODUCT-PLAN.md` § Owner decisions), so this
  framework's assumptions stay traceable to when and why they were set.

## 9. Open decisions (consolidated)

1. **Margin target: Card A (50%) or Card B (33%)?** Everything downstream
   (tokens included, EGP price, Go clip counts) depends on this pick. (§3)
2. **Draft-quality default + paid finishing step** — product decision, not
   just pricing, but the single highest-leverage margin lever available.
   (§3)
3. **Does the Go/Creator tier create a `companies`/`projects` row at all**,
   or is it a separate lightweight path outside the F1 data model? Settle
   before scoping as buildable work — it's architecture, not pricing.
   (`SUBSCRIPTIONS-PLAN.md`)
4. **Tier naming** — Artist vs. Atelier for Individual; Creator vs. Social
   vs. CimaFast Go for the no-subscription tier. (`SUBSCRIPTIONS-PLAN.md`)
5. **EGP re-peg cadence, and whether Enterprise bills in USD instead.** (§5)
6. **Indemnified sub-pool sizing** for Enterprise once Foundry is added —
   `AI-PROVIDER-COSTS.md` §3.2/§5.7 floats ~10% of the pool as a starting
   point, not a decision.
