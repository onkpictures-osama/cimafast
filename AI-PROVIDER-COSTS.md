# AI media-generation provider costs — reference for B5 pricing

*Compiled 2026-09-22 by production, at the owner's request, to give the B5
subscription-tier discussion (owner + Mohamed El-Zayat, `SUBSCRIPTIONS-PLAN.md`)
a real cost floor instead of estimates. This is raw vendor pricing plus how it
maps to what CimaFast actually generates — it does not propose tier prices or
margins; that decision stays with B5.*

**Caveat up front:** AI provider pricing moves monthly, sometimes weekly, and
several sources below disagree with each other by 2-3x for the same model,
because third-party resellers wrap the same underlying model at different
markups. Treat every number here as a September 2026 snapshot to build a
*model* from, not a locked-in rate — re-check before any contract is signed.

## 1. What CimaFast actually calls today (evidence)

Only one integration exists right now, in `image_gen.py`: one still image per
call, through OpenRouter, model `google/gemini-3.1-flash-image`, for a
location reference photo only. Character image generation is a disabled stub
(P2). There is no video or voice integration in the codebase at all — those
are 100% new integrations, not upgrades of something running.

This matters for costing: everything below for image generation is "what we'd
pay more of / differently," but video and voice are "what we'd start paying
for the first time."

## 2. Per-unit vendor pricing (September 2026)

### Images

| Provider / model | Price | Notes |
|---|---|---|
| **OpenRouter → Gemini image** (current CimaFast integration) | priced per output token, model-dependent | Gemini/OpenAI/Microsoft models on OpenRouter bill per token, not flat per-image |
| **OpenAI GPT Image 2** (direct API) | $0.006 (low) / $0.053 (medium) / $0.211 (high) per 1024×1024 image | Token-based; batch API is 50% cheaper across the board ($15/$4/$2.50 per 1M tokens vs $30/$8/$5 standard) |
| **Black Forest Labs FLUX.2** | $0.014 (Klein 4B) → $0.03 (Pro) → $0.05 (Flex) → $0.07 (Max) per image, priced per megapixel | Open-weight family; cheapest quality-per-dollar tier found in this search |
| **Adobe Firefly** | ~$0.02/image pay-as-you-go, or committed packets | Only vendor here offering **contractual IP indemnification** on outputs (copyright claims; trademark/publicity excluded) — see §6 |
| **Midjourney** | $10–$120/month subscription seats, no official API | Any "API" access is an unofficial reseller layer on top of a subscription — operationally awkward for a per-company SaaS to depend on |

### Video (per second of output)

| Model | Provider | $/sec (typical) | Range |
|---|---|---|---|
| Luma Ray 2 | Luma Labs | $0.04 | — |
| Veo 3.1 Lite | Google | $0.05 | 720p, no audio |
| Pika 2.2 / Wan 2.6 / Grok Imagine | Pika / Alibaba / xAI | $0.05 | — |
| Hailuo 02 | MiniMax | $0.045 | — |
| Kling 3.0 | Kuaishou | $0.075–$0.10 | up to $0.11 Turbo |
| Seedance 2.0 | ByteDance | $0.092 | — |
| **Seedance 2.5** (asked about) | ByteDance | **$0.10–$2.08/sec** | $0.10 at 480p → $2.08 at 4K w/ audio; ~$0.06–$1.24 for video-to-video |
| Sora 2 | OpenAI | $0.10 | Sora 2 Pro $0.30–$0.70 by resolution. **API is sunsetting 2026-09-24** — do not build against it |
| Runway Gen-4.5 | Runway | $0.12 | separate billing from its consumer subscription |
| Veo 3.1 Standard | Google | $0.40 | 1080p+audio; up to $0.60 at 4K |
| Luma Ray 3 | Luma Labs | $0.21 | HDR/EXR modes cost more |

Working range across all of these: **$0.04–$0.40/sec** for standard
quality, before 4K/audio premiums push individual models past $1/sec
(Seedance 2.5 and Veo at the top end).

### Voice (ElevenLabs — the only major dedicated voice vendor checked)

| Plan | $/month | Credits (~characters) |
|---|---|---|
| Free | $0 | 10,000 |
| Starter | $6 | 30,000 |
| Creator | $22 | 121,000 |
| Pro | $99 | 600,000 |
| Scale | $299 | 1,800,000 |
| Business | $990 | 6,000,000 |
| Enterprise | custom | custom |

API overage: $0.05/1,000 characters (Flash/Turbo) or $0.10/1,000 (Multilingual
v2/v3 — the tier that covers Arabic). Multilingual v2 is 1 credit/character;
Flash/Turbo models are discounted to 0.5–1 credit/character. Unused credits
roll over up to 2 months, capped at 2× the monthly quota.

### Text / LLM (the layer already paying for script analysis)

Not re-priced here in full — `CIMAFAST_IMAGE_MODEL` and the analysis model are
both OpenRouter calls today, and OpenRouter's fee structure (below) already
covers how that's billed. Worth a follow-up pass once B4/B5 numbers firm up,
since script analysis is the other AI cost center besides images/video/voice.

## 3. How OpenRouter actually bills (relevant since it's our one integration today)

- **No markup on model price.** OpenRouter passes through the underlying
  provider's per-token rate as-is.
- **The fee is on credit purchases**, not usage: 5.5% (non-crypto, $0.80
  minimum) or 5% (crypto).
- **BYOK (bring your own provider key)** removes that fee entirely for the
  first $25,000/month of list-price inference, then charges 5% of list price
  after that.
- Practical read: at CimaFast's current single-digit-project volume,
  OpenRouter's convenience (one integration, many models, no separate
  contracts with Google/OpenAI/ByteDance) is worth the 5.5%. If a single
  provider's volume grows large under one Enterprise company, BYOK becomes
  the cheaper path *for that company specifically* — worth flagging to
  infrastructure once real usage numbers exist, not a decision to make now.

### 3.1 Can we rely on it? (added 2026-09-22, at the owner's request)

**For what's running today (one image call, low volume): fine, no reason to
change it.** For hard-wiring the whole B4 AI-generation module around it,
specifically for Enterprise customers paying $499–3,999/month: no, not as the
only path, for three concrete reasons —

1. **No SLA, and a real outage history.** OpenRouter publishes no contractual
   uptime commitment. It had documented outages on 2026-02-17 and -19 (35–38
   minutes each, 80–90% request failure during the worse one), caused by a
   failure in *OpenRouter's own* third-party caching dependency — meaning the
   risk isn't just "OpenRouter goes down," it's "whatever OpenRouter itself
   depends on goes down." Independent reviews land on the same read: fine for
   prototyping and low-stakes use, not something to build a paid workload's
   uptime story on without a fallback.
2. **It doesn't cover the whole media stack anyway.** ElevenLabs — the voice
   vendor this whole report is keyed to for Arabic support — is not one of
   OpenRouter's providers; OpenRouter's own TTS offerings (GPT-4o Mini TTS,
   Gemini Flash TTS, Voxtral) are a different, unevaluated set of voices. Any
   voice feature needs a **direct ElevenLabs integration** regardless of what
   happens with image/video, so "OpenRouter as our models provider" was never
   going to be a single answer to B4 in the first place.
3. **The current choice was convenience, not evaluation.** `image_gen.py`'s
   own comment says why OpenRouter: *"ده الحساب الوحيد على السيرفر اللي عنده
   موديلات بتطلّع صور"* — it's the only account already on the server with
   image-capable models, not a reliability decision. Worth knowing before it
   gets treated as a settled architecture choice.

**Data handling — one good default, one hard rule.** OpenRouter defaults to
Zero Data Retention (prompts/images not stored) unless prompt logging is
opted into. **Never opt into that** — enabling it hands OpenRouter an
irrevocable right to commercial use of whatever was sent, which for CimaFast
means client scripts, character and location descriptions: exactly the user
data this product exists to protect, not something to trade for a 1%
discount. Separately, ZDR only covers OpenRouter's own layer — the request
still lands on the underlying provider (Google/OpenAI/ByteDance) under *its*
retention policy, which OpenRouter doesn't override. Worth a plain sentence
in any Enterprise DPA rather than assuming "OpenRouter says ZDR" settles it.

**What I'd flag to chief-engineer/infrastructure, since the integration
architecture is their call, not mine:** the `generated_assets` rework already
recommended for B4 should sit behind a provider interface, not hardcode
OpenRouter the way `image_gen.py` does today — so an outage or a pricing
change upstream doesn't take every company's AI features down at once, and
so an Enterprise customer who needs Firefly-class indemnification for
client-facing work has a path that doesn't go through an aggregator with no
SLA.

### 3.2 What else is out there (added 2026-09-22, at the owner's request)

Checked for a provider that covers image + video + voice + text under one
roof *and* can be relied on. Short answer: **nothing does all four with a
real SLA and full indemnification — the two properties trade off against
each other**, and the realistic answer is 2-3 providers behind the
abstraction layer above, not one.

| Provider | Type | Breadth | Reliability | Indemnification | Gap for us |
|---|---|---|---|---|---|
| **OpenRouter** (current) | Aggregator | image, video, text, some TTS | No SLA; 2 outages in 2026 | None | No ElevenLabs; single point of failure |
| **Eden AI** | Aggregator | 500+ models — text, image, video, voice, OCR, translation | Claims 99.99% uptime; **built-in automatic fallback to a backup provider** if the primary fails or hits limits; GDPR, EU infra | Not offered | Smaller/newer track record than OpenRouter; unclear if ElevenLabs is one of its providers |
| **fal.ai** | Aggregator, media-first | 600+ models — image/video/audio/3D; thinner on text | Enterprise tier: 99.99% uptime SLA, SOC 2, private endpoints, dedicated infra | Not offered | Enterprise pricing not public; built for media, not a text/LLM replacement |
| **Microsoft Foundry** (Azure, renamed from AI Foundry Jan 2026) | Hyperscaler | OpenAI's own models (GPT Image, was Sora) + a catalog of thousands (Anthropic, Mistral, Meta, Cohere, NVIDIA, Hugging Face) | Enterprise SLA on Azure-sold models | ✅ Customer Copyright Commitment — **but only for Microsoft's own hosted output**, not the resold third-party catalog | No ElevenLabs, no ByteDance/Kling; indemnity doesn't extend to everything in the catalog |
| **Google Vertex AI** | Hyperscaler | Imagen (image), Veo (video), Gemini (text), Chirp (voice) — Google's own stack | Published SLA, financial credits on breach | ✅ two-part indemnity (training data + output) for Google's own generative services | Narrow roster — no OpenAI/ByteDance/ElevenLabs; native voice isn't ElevenLabs-quality for Arabic |
| **AWS Bedrock** | Hyperscaler + marketplace | Amazon Nova (image/video) + growing third-party marketplace (Anthropic, Stability, Luma) | Tiered (Standard/Priority/Flex); SLA not fully published per-service | ✅ uncapped indemnity — **for Amazon's own models only**, third-party marketplace models unconfirmed | Amazon's own video/image models are mid-churn (Nova Reel v1 / Nova Canvas both EOL 2026-09-30, replaced by Luma Ray v2 on the same platform) |
| **ElevenLabs** (direct) | Specialist, voice only | Voice/TTS only — best Arabic multilingual coverage found in this whole search | Own enterprise tier | Unconfirmed | Not full-stack by design; has to be paired with something else regardless |

**The pattern worth internalizing:** every hyperscaler now indemnifies —
but only its *own* first-party models, never the third-party models it
resells on the same marketplace. That's exactly where Seedance, Kling and
most non-Western video models live, and none of them carry indemnification
from anyone in this table. So "indemnified" and "broad model selection"
are, in practice, opposite ends of the same shelf, not two features one
vendor offers together.

**What this means for the provider question:** no single answer replaces
"can we rely on OpenRouter" with one better vendor. The shape that actually
covers image + video + voice + text + reliability + indemnification is
three providers, not one — which is exactly why the provider-interface
recommendation in §3.1 matters more than which single vendor wins:

1. **Eden AI** (or fal.ai for media specifically) behind the abstraction
   layer, for breadth and its built-in fallback routing — the direct
   upgrade over OpenRouter's no-fallback, no-SLA setup for everyday
   generation.
2. **One hyperscaler** — Microsoft Foundry is the closer fit today since
   image generation already runs on an OpenAI model — as the indemnified
   path specifically for anything Enterprise-tier or client-facing, used
   deliberately rather than for every generation.
3. **ElevenLabs, direct, non-negotiable** — none of the bundles above
   carry it, and it's the only vendor found with real Arabic multilingual
   voice quality.

This is a shortlist for chief-engineer/infrastructure to pressure-test and
contract, not a vendor decision made here.

## 4. Translating unit prices into CimaFast actions

These are the numbers B5's "tokens/month" figures need to be checked against
— right now nothing defines what a "token" in the subscription tiers actually
buys.

| CimaFast action | Real-world unit | Cost at typical vendor |
|---|---|---|
| One location reference image (today's feature) | 1 image, standard quality | ~$0.02–$0.05 (Firefly/FLUX) to ~$0.05–$0.21 (GPT Image 2 medium/high) |
| One character reference image (P2, not shipped) | 1 image | same range as above |
| One generated shot, 5 seconds, standard quality | 5 sec video | $0.20–$0.60 (Luma/Veo Lite/Pika) to $1.00–$2.00 (Kling/Seedance/Runway) |
| One generated shot, 5 seconds, premium (4K/audio) | 5 sec video | $2–$10 (Veo Standard/4K, Seedance 2.5 4K) |
| One page of dialogue voiceover (~250 characters/line × ~8 lines) | ~2,000 characters | ~$0.10–$0.20 at ElevenLabs API overage rates; effectively free within any paid plan's monthly credits |

A single AI-generated scene with 3 shots (video) and a couple of voice lines
easily lands **$3–$20** in raw vendor cost depending on quality tier — video
is the line item that actually drives cost at enterprise scale, not images or
voice.

## 5. A worked token model, against B5's actual draft numbers

*Added 2026-09-22, second pass, at the owner's request to relate these costs
directly to the draft tiers in `SUBSCRIPTIONS-PLAN.md`. This is a proposed
model to check the draft numbers against — not a repricing of B5, which stays
the owner/Mohamed's call.*

### 5.1 Define what a token is worth

To make cost mix-independent (so it doesn't matter whether a company spends
its pool on images, video or voice — every token should cost us the same),
peg **1 token = $0.03 of vendor cost**, and size each action's token price off
the section-2 numbers so it always redeems exactly $0.03 of real spend at
*standard* quality:

| Action (standard quality) | Vendor cost | Tokens |
|---|---|---|
| 1 image (FLUX Pro / Firefly / GPT Image medium, blended) | ~$0.03 | **1 token** |
| 1 second of standard video (Luma/Veo Lite/Pika/Kling/Seedance range, blended ~$0.09) | ~$0.09 | **3 tokens** |
| 1,000 voice characters, Arabic-capable Multilingual tier | ~$0.10–0.12 | **4 tokens** |
| 1 second of premium video (4K/HDR/audio — Veo Standard, Seedance 2.5 4K) | $0.40–2.08 | **15–70 tokens** |

The wide premium-video range is the point, not a flaw: it makes the most
expensive generations self-limiting (a company burns its month's pool in
minutes of 4K instead of hours of draft-quality work) rather than needing a
separate hard block.

### 5.2 What that means for B5's draft prices, at full redemption

Vendor cost = tokens included × $0.03, regardless of mix, by construction
above. This is the **floor** case — every token in the plan actually spent:

| Tier | Price | Tokens | Vendor cost (@ $0.03/token) | Margin |
|---|---|---|---|---|
| Enterprise Standard | $499 | 15,000 | $450 | **+$49 (9.8%)** |
| Enterprise Pro | $1,299 | 45,000 | $1,350 | **–$51 (–3.9%)** |
| Enterprise Ultimate | $3,999 | 150,000 | $4,500 | **–$501 (–12.5%)** |
| Individual Standard | $39 | 2,000 | $60 | **–$21 (–53.8%)** |
| Individual Pro | $99 | 6,000 | $180 | **–$81 (–81.8%)** |
| Go/Dummies Starter | $9 | 700 | $21 | **–$12 (–133%)** |
| Go/Dummies Popular | $29 | 2,500 | $75 | **–$46 (–158%)** |
| Go/Dummies Value | $79 | 7,500 | $225 | **–$146 (–184%)** |

**Every tier except Enterprise Standard loses money on vendor cost alone if
subscribers actually use their full monthly pool** — before hosting, support,
or anything else. The Go/Dummies packs are the worst: the owner's own framing
of that persona is "fast, full video generation" — i.e. the *most* expensive
media type, spent by a persona with the *least* price headroom.

### 5.3 What it would take to be sustainable

Targeting a conventional ~70% gross margin (cost ≤ 30% of price) at full
redemption, the needed vendor cost per token is **$0.003–$0.01** across these
tiers — roughly a third to a tenth of the $0.03 "1 standard image" basis
above. Three levers get there, usable in combination:

1. **Cheaper default quality.** $0.01/token is close to GPT Image 2's *low*
   quality tier ($0.006/image) or a short clip at the cheapest video models
   (Luma Ray 2 $0.04/sec) — i.e., default generations should be draft/preview
   quality, with a real cost step-up (more tokens, or a separate purchase) to
   render something at final/delivery quality. This also maps well onto how
   production actually works: previs and option-exploring should be cheap and
   plentiful, a chosen final frame is generated once.
2. **Smaller allotments or higher prices** — a straight 3–10x cut to tokens
   included, or 3–10x on price, closes the same gap without touching quality.
3. **Bet on redemption rate below 100%**, which is normal — most SaaS AI
   quotas are not fully drained every month. This is the riskiest lever
   because **we have no usage data yet** (0 paid subscribers today) to know
   what the real redemption rate will be; treat it as a hope, not a plan,
   until the metering in §5.4 exists and reports real numbers.

Lever 1 is the one I'd weight heaviest from a production-workflow angle: it
mirrors how the Go/Dummies persona's own use case (throwaway social content)
and the Enterprise persona's use case (iterate cheap, finalize once) actually
differ, rather than selling the same token at the same value to both.

### 5.4 Estimated plan — concrete numbers, prices unchanged

Working the three levers from §5.3 against the actual draft numbers, without
touching any price:

**Enterprise + Individual (5 tiers): keep the token counts as drafted.**
Redefine "1 token" as one *draft-quality* generation (~$0.008 blended vendor
cost — GPT Image 2 low tier is $0.006/image; a short clip at the cheapest
video model prorated in) instead of the $0.03 standard-quality basis in
§5.1, with a paid step-up (more tokens, or a separate charge) to render
anything at final/delivery quality. At $0.008/token, full redemption:

| Tier | Price | Tokens | Cost | Margin |
|---|---|---|---|---|
| Enterprise Standard | $499 | 15,000 | $120 | **76%** |
| Enterprise Pro | $1,299 | 45,000 | $360 | **72%** |
| Enterprise Ultimate | $3,999 | 150,000 | $1,200 | **70%** |
| Individual Standard | $39 | 2,000 | $16 | **59%** |
| Individual Pro | $99 | 6,000 | $48 | **52%** |

No number in `SUBSCRIPTIONS-PLAN.md` needs to move for these five — this is
a product decision (draft-quality default, paid finishing step), not a
pricing one.

**Go/Dummies: the token counts as drafted don't survive at any reasonable
cost basis**, because this persona is defined as video-only (the most
expensive media type) at the industry's lowest price point — even the
cheapest video model (~$0.045/sec, e.g. Luma Ray 2 blended) makes an abstract
"token" pool the wrong shape for this tier. Recommend dropping the "tokens"
framing here entirely and selling by **video count** instead — it also
matches this persona's own mental model ("10 videos for my ad") better than
an abstract number:

| Pack | Price | Videos (5 sec, cheapest model) | Cost (@ $0.045/sec) | Margin |
|---|---|---|---|---|
| Go Starter | $9 | 12 | $2.70 | **70%** |
| Go Popular | $29 | 39 | $8.78 | **70%** |
| Go Value | $79 | 105 | $23.63 | **70%** |

That's a cut from the drafted 700/2,500/7,500 "tokens" to 12/39/105 videos —
a real number, not a rounding difference, because the drafted counts were
priced as if this tier generated images, not the video it's actually meant
to generate. Worth stating plainly in the Mohamed discussion: **this
persona's price points ($9–79) support single-digit-to-low-double-digit
videos per month at current vendor rates, not hundreds.**

### 5.5 Rate card targeting exactly 50% profit margin

*Added 2026-09-22, third pass — a specific target margin (50%) instead of the
ranges above. This uses the mix-independent standard-quality token from §5.1
throughout ($0.03 vendor cost per token), not the draft-quality basis in
§5.4, so it holds regardless of whether a customer spends tokens on images,
video or voice — no quality-tiering build required to make this one true.*

**Reading of "50% profit":** 50% gross margin on revenue, i.e. resale price =
2× vendor cost. (If "50%" was meant as a 50% *markup on cost* instead, that's
a 33% margin — a materially different, cheaper card. Flagging the two
readings explicitly since they're often conflated and the gap between them
is exactly the gap between the two tables below.)

**Core rate: $0.06 per token** (cost $0.03, profit $0.03) — resells at 2× cost
against §5.1's conversion table, so every action costs the customer the same
$0.06/token whether it's an image, a second of standard video, or 250 voice
characters. Token counts below are floored (rounded down), so real margin is
≥50%, never under.

| Tier | Price/mo | Tokens | Vendor cost | CimaFast profit | Margin |
|---|---|---|---|---|---|
| Enterprise Standard | $499 | 8,300 | $249 | $250 | 50.1% |
| Enterprise Pro | $1,299 | 21,650 | $650 | $650 | 50.0% |
| Enterprise Ultimate | $3,999 | 66,650 | $2,000 | $2,000 | 50.0% |
| Individual Standard | $39 | 650 | $19.50 | $19.50 | 50.0% |
| Individual Pro | $99 | 1,650 | $49.50 | $49.50 | 50.0% |

**Go/Dummies — same $0.06/token rate, expressed as video clips** (5 sec,
standard quality — 15 tokens/clip, $0.90 resale per clip, $0.45 cost):

| Pack | Price | Clips | Vendor cost | CimaFast profit | Margin |
|---|---|---|---|---|---|
| Go Starter | $9 | 10 | $4.50 | $4.50 | 50.0% |
| Go Popular | $29 | 32 | $14.40 | $14.60 | 50.3% |
| Go Value | $79 | 87 | $39.15 | $39.85 | 50.4% |

**What each allotment converts to**, for sales conversations (pick one
media type as the full pool — real usage will mix, which only helps margin
since the table above is already the floor case):

| Tier | All-images | All-video (5-sec clips) | All-voice (chars) |
|---|---|---|---|
| Enterprise Standard | 8,300 images | 553 clips | 2,075,000 |
| Enterprise Pro | 21,650 images | 1,443 clips | 5,412,500 |
| Enterprise Ultimate | 66,650 images | 4,443 clips | 16,662,500 |
| Individual Standard | 650 images | 43 clips | 162,500 |
| Individual Pro | 1,650 images | 110 clips | 412,500 |

This is a straight 2x-cost resale card — it says nothing about whether $499
for 8,300 tokens (vs the drafted 15,000) still reads as good value against
what a production company would pay a vendor directly, or against a
competitor. That comparison, and whether 50% is even the right target given
Enterprise's real value is infrastructure/seats/collaboration and not tokens
(per the owner's own reasoning already in `SUBSCRIPTIONS-PLAN.md`), is the
part that's still the owner/Mohamed's call, not a costing question.

### 5.6 The other reading: 50% markup on cost, and the two cards compared

*Added 2026-09-22, fourth pass, at the owner's request to compare against
§5.5.* Same $0.03/token cost basis, same conversion table, but resold at
**1.5× cost ($0.045/token) instead of 2× ($0.06/token)** — a 50% markup on
cost nets a **33.3% margin**, not 50%. Same flooring convention (round token
counts down), so real margin is ≥33.3%.

| Tier | Price/mo | Tokens | Vendor cost | CimaFast profit | Margin |
|---|---|---|---|---|---|
| Enterprise Standard | $499 | 11,088 | $332.64 | $166.36 | 33.3% |
| Enterprise Pro | $1,299 | 28,866 | $865.98 | $433.02 | 33.3% |
| Enterprise Ultimate | $3,999 | 88,866 | $2,665.98 | $1,333.02 | 33.3% |
| Individual Standard | $39 | 866 | $25.98 | $13.02 | 33.4% |
| Individual Pro | $99 | 2,200 | $66.00 | $33.00 | 33.3% |

Go/Dummies, same clip framing (15 tokens/clip, cost $0.45, resale $0.675):

| Pack | Price | Clips | Vendor cost | CimaFast profit | Margin |
|---|---|---|---|---|---|
| Go Starter | $9 | 13 | $5.85 | $3.15 | 35.0% |
| Go Popular | $29 | 42 | $18.90 | $10.10 | 34.8% |
| Go Value | $79 | 117 | $52.65 | $26.35 | 33.4% |

**Side by side** — same prices, what changes is what the customer gets and
what CimaFast keeps:

| Tier | Tokens @ 50% margin | Tokens @ 33% margin | Customer gets | CimaFast profit @ 50% | CimaFast profit @ 33% | CimaFast gives up |
|---|---|---|---|---|---|---|
| Enterprise Standard | 8,300 | 11,088 | **+33.6%** more tokens | $250 | $166.36 | **–33.5%** profit |
| Enterprise Pro | 21,650 | 28,866 | +33.3% | $650 | $433.02 | –33.4% |
| Enterprise Ultimate | 66,650 | 88,866 | +33.3% | $2,000 | $1,333.02 | –33.3% |
| Individual Standard | 650 | 866 | +33.2% | $19.50 | $13.02 | –33.2% |
| Individual Pro | 1,650 | 2,200 | +33.3% | $49.50 | $33.00 | –33.3% |
| Go Starter | 10 clips | 13 clips | +30% | $4.50 | $3.15 | –30% |
| Go Popular | 32 clips | 42 clips | +31% | $14.60 | $10.10 | –30.8% |
| Go Value | 87 clips | 117 clips | +34% | $39.85 | $26.35 | –33.9% |

The trade is consistent and mechanical, because both cards share the same
cost basis: **the 33%-margin card gives the customer about a third more
tokens for the same price, and costs CimaFast about a third of its profit
per subscription to do it.** Neither is "correct" — it's a straight choice
between a stronger unit-economics floor (50%, cushions against real usage
running hotter than assumed, e.g. more premium 4K than modeled) and a more
generous-looking allotment at the same sticker price (33%, better for
competing on "tokens included" against Kling/Runway/Pika-style consumer
credit counts). Worth deciding alongside, not before, real redemption data —
the safer sequence is still: launch metered, watch actual usage, then lock
whichever margin target the real numbers support.

### 5.7 Rebuilt against the recommended provider stack (added 2026-09-22)

§5.1's $0.03/token cost basis was "cheapest price found anywhere," not tied
to a real vendor relationship. Reworking it against the three-provider stack
from §3.2 — fal.ai (breadth, no separate fee layer, used as primary),
Eden AI (fallback only, +5.5% fee, rarely triggered), Microsoft Foundry
(indemnified path), ElevenLabs (voice, direct) — changes two things: the
numbers barely move, but *where the money goes* and *what's actually
enforceable* both become concrete.

**Updated cost basis, by provider:**

| Action | Provider (primary) | Cost | vs. §5.1 basis |
|---|---|---|---|
| Draft/default image | fal.ai | ~$0.02 | slightly cheaper than $0.03 |
| Draft/default video, standard quality (per sec) | fal.ai (Seedance/Kling/Veo Lite/Luma, blended) | ~$0.09 | unchanged |
| **Indemnified/finishing image** (new) | **Microsoft Foundry** (Azure-hosted GPT Image 2) | $0.053 (medium) – $0.211 (high) | new — Enterprise-tier only |
| Voice, Arabic-capable | ElevenLabs (direct) | ~$0.11/1,000 chars | unchanged |
| Fallback surcharge | Eden AI, only during a fal.ai outage | +5.5% on whatever it routes | new, but rare enough to ignore in the blended rate |

The $0.03/token anchor from §5.1 still holds for everyday (draft) generation
— fal.ai prices land close enough to the old "found anywhere" number that
every rate card in §5.4–§5.6 stands as computed. What's new is a second,
pricier lane:

**Indemnified tokens, added to the existing conversion table, same $0.03
cost-per-token / $0.06 resale-per-token rate as §5.5** (rounded up, not
down, since these protect a legal claim, not just a margin target):

| Action | Cost | Tokens (cost basis) | Resale value |
|---|---|---|---|
| 1 indemnified image, medium quality (Foundry) | $0.053 | **2 tokens** | $0.12 (56% margin) |
| 1 indemnified image, high quality (Foundry) | $0.211 | **7 tokens** | $0.42 (50% margin) |

**Recommendation: give Enterprise tiers a small *ring-fenced* indemnified
sub-allotment**, not a blend into the general pool — e.g. 10% of Enterprise
Standard's 8,300-token pool (≈830 tokens ≈ 415 indemnified medium-quality
images) reserved for client-facing/delivery work, with the rest spent at
the cheaper fal.ai draft rate for previs and iteration. This is the direct
product answer to "can we sell this to a production company that needs
legally-safe deliverables": yes, but only the Foundry-routed share of their
usage carries that protection — worth saying so explicitly in whatever
Enterprise sells this, so "indemnified" isn't implied for the whole plan
when it only covers the images actually generated through that path.

**Go/Dummies stays entirely on fal.ai** — no Foundry video option exists (it
doesn't host Seedance/Kling/Veo), and this persona's price point doesn't
support the indemnified lane's cost anyway; the clip-count numbers in §5.5
and §5.6 are unchanged.

### 5.8 What has to be built before any of this is real

None of §5.1–5.3 can be enforced today — there is no token ledger, no
quality-tiering, and no quota check anywhere in the code (the gap already
flagged for B4: `usage_events` logs *that* a generation happened, not its
token cost, and there is no cap enforcement at all). §5.7 adds two more
build items on top: a provider-abstraction layer (`image_gen.py` today
hardcodes OpenRouter — fal.ai/Eden/Foundry/ElevenLabs all need to sit behind
one interface, per §3.1) and a way to ring-fence the indemnified sub-pool so
it can't silently be spent as regular draft tokens. Recommended sequence
unchanged: ship metering and a soft quota warning first, watch real
redemption rates for a month even at $0 (or founding-customer) pricing, then
lock tier numbers against real data instead of the vendor-list-price worst
case above.

## 6. EGP sales rate card (at $1 = 52 EGP)

*Added 2026-09-22, at the owner's request.* Straight FX conversion of the
§5.5 (50%-margin) card, then rounded per tier the way each persona actually
shops — Enterprise/Individual round to a clean professional number (this is
a B2B invoice, not an impulse buy); Go/Dummies rounds to the "٩٩"-ending
charm price that's the Egyptian retail norm, since that persona is closer to
a consumer purchase than a software contract. Every rounding stayed within
~1.5% of the raw conversion, and where it could go either way it was rounded
**up**, not down, so EGP pricing never quietly erodes the 50% margin target.

| Tier | USD price | Raw EGP (×52) | **Rate card price** | Tokens | Rounding vs. raw |
|---|---|---|---|---|---|
| Enterprise Standard | $499 | 25,948 | **26,000 EGP** | 8,300 | +0.2% |
| Enterprise Pro | $1,299 | 67,548 | **67,500 EGP** | 21,650 | –0.07% |
| Enterprise Ultimate | $3,999 | 207,948 | **208,000 EGP** | 66,650 | +0.02% |
| Individual Standard | $39 | 2,028 | **2,000 EGP** | 650 | –1.4% |
| Individual Pro | $99 | 5,148 | **5,150 EGP** | 1,650 | +0.04% |
| Go Starter | $9 | 468 | **499 EGP** | 10 clips | +6.6% |
| Go Popular | $29 | 1,508 | **1,499 EGP** | 32 clips | –0.6% |
| Go Value | $79 | 4,108 | **4,099 EGP** | 87 clips | –0.2% |

**The one caution that matters more than the rounding:** every vendor behind
this card — fal.ai, Eden AI, Microsoft Foundry, ElevenLabs — bills in USD.
Pricing the subscription in EGP fixes *revenue* in EGP while *cost* stays
tied to the dollar; if EGP weakens against the dollar after these prices are
set, the 50% margin computed today erodes in real terms even though the EGP
number on the invoice never changes — this isn't a hypothetical for the
Egyptian pound specifically. Two ways to protect against it, worth deciding
alongside the rate card rather than after it ships:

1. **Re-peg periodically** — review the EGP card against the live FX rate on
   a fixed schedule (quarterly is reasonable for a subscription business)
   rather than leaving it static indefinitely.
2. **Bill Enterprise in USD, EGP only for Individual/Go** — production
   companies large enough for the Enterprise tier are often already used to
   USD-denominated software contracts (matches how many of the vendors in
   this report themselves bill), which moves the FX exposure off CimaFast's
   books entirely for the highest-cost tiers; keep EGP for the
   locally-anchored Individual/Go personas where a USD price would be a
   worse buying experience.

## 7. Non-cost factors that matter for selling *enterprise* specifically

- **IP indemnification.** A production company paying $499-3,999/month is a
  business, not a hobbyist — if a generated asset gets a copyright claim,
  "the AI made it" isn't a defense they can offer a broadcaster or investor.
  Adobe Firefly is the only vendor in this list with a contractual
  indemnification offer (copyright only, not trademark/publicity). Worth a
  question for infrastructure/legal on whether Enterprise tiers need a
  Firefly-class option specifically for anything client-facing, separate from
  cheaper models used for internal previs.
- **Arabic support.** The product is Arabic-first; ElevenLabs' Multilingual
  v2/v3 (the pricier per-character tier) is what actually covers Arabic
  voice — the cheap Flash/Turbo tier is English-only. Any voice-cost estimate
  for CimaFast has to use the Multilingual rate, not the headline cheap one.
- **No official Midjourney API.** If image quality comparisons ever put
  Midjourney on the table, every access path is an unofficial reseller
  wrapping a personal-use subscription — a real risk to build an Enterprise
  feature on top of; FLUX/GPT Image/Firefly are the vendors with real
  commercial APIs.
- **Sora 2 API is sunsetting 2026-09-24** — two days from today. Do not scope
  anything against it.

## 8. Products per month, benchmarked against Magnific and Higgsfield

*Added 2026-09-22, at the owner's request.* "Products" = finished pieces —
images, 5-second standard video clips, or voice minutes — a token pool
actually converts to in a month, using the §5.5 (50%-margin) allotments and
the §5.1 conversion table (1 image = 1 token, 1 five-second clip = 15
tokens, 1,000 voice characters = 4 tokens).

### Market benchmark first

| Platform | Price/mo | What it gives (real, published) |
|---|---|---|
| Higgsfield Starter | $19 | ~14–24 videos |
| Higgsfield Plus | $59 | ~36–62 videos |
| Higgsfield Ultra | $129 | ~76–131 videos |
| Magnific entry | $16 | ~133 images/mo equivalent, or ~21 four-sec videos/mo if spent entirely on video (credits pool *annually*, not monthly) |

### Enterprise + Individual — three usage scenarios per tier

All-images and all-video are the outer bounds (spend the whole pool on one
media type); "typical mix" assumes a production workflow — mostly stills for
previs/location work, some shots, occasional voice scratch tracks (60%
images / 30% video / 10% voice by token spend for Enterprise; individual
freelancers skew more video-heavy, 40/40/20).

| Tier | Tokens/mo | All-images | All-video (5-sec clips) | Typical mix |
|---|---|---|---|---|
| Enterprise Standard | 8,300 | 8,300 images | 553 clips | ~4,980 images + 166 clips + ~83 pages of voice |
| Enterprise Pro | 21,650 | 21,650 images | 1,443 clips | ~12,990 images + 433 clips + ~216 pages of voice |
| Enterprise Ultimate | 66,650 | 66,650 images | 4,443 clips | ~39,990 images + 1,333 clips + ~666 pages of voice |
| Individual Standard | 650 | 650 images | 43 clips | ~260 images + 17 clips + ~13 pages of voice |
| Individual Pro | 1,650 | 1,650 images | 110 clips | ~660 images + 44 clips + ~33 pages of voice |

(voice "pages" = ~2,000 characters, one script page of dialogue, from §4)

### Go/Dummies vs. the benchmark, directly

This is the tier that actually competes with Magnific/Higgsfield head-on —
same persona (quick social content), same unit (a short video clip):

| CimaFast pack | Price | Clips | vs. benchmark at similar price |
|---|---|---|---|
| Go Starter | $9 | 10 (5-sec) | Higgsfield $19 gives 14–24 — CimaFast is **half the price** for roughly half the clips |
| Go Popular | $29 | 32 (5-sec) | Higgsfield $59 gives 36–62 — again about half price, proportionally similar output |
| Go Value | $79 | 87 (5-sec) | Higgsfield $129 gives 76–131 — CimaFast is 61% of the price for a **comparable or slightly higher** clip count |

**The read:** at every comparable price point, CimaFast's clip count lands
in the same range as Higgsfield's, at roughly half to two-thirds the price —
not because the allotments are generous, but because our vendor stack
(fal.ai-routed Seedance/Kling/Veo Lite/Luma, blended ~$0.09/sec) is
genuinely cheaper than what Higgsfield's own $0.74–1.27/video implies they're
paying or willing to charge. Two honest readings, not one: either there's
real pricing headroom here (Go could charge closer to Higgsfield's rate and
still clear 50% margin with room to spare), or Higgsfield's higher price
reflects something not modeled here — a costlier/better model, its own
margin target, or brand positioning. Worth treating as a ceiling to test
against, not proof the current numbers are correct.

## Sources

- [Image Generation Models Compared — OpenRouter Blog](https://openrouter.ai/blog/insights/image-generation-models-compared/)
- [OpenRouter Image Generation docs](https://openrouter.ai/docs/guides/overview/multimodal/image-generation)
- [GPT Image 2 API Pricing — Unifically](https://unifically.com/blogs/gpt-image-2)
- [OpenAI GPT Image API Pricing — AI Free API](https://www.aifreeapi.com/en/posts/openai-image-generation-api-pricing)
- [Seedance 2.5 — OpenRouter](https://openrouter.ai/bytedance/seedance-2.5)
- [Seedance 2.5 Pricing Compared — CellCog](https://cellcog.ai/blog/seedance-2-5-pricing/)
- [ElevenLabs Pricing 2026 — Flexprice](https://flexprice.io/blog/elevenlabs-pricing-breakdown)
- [ElevenLabs official pricing](https://elevenlabs.io/pricing)
- [Runway API Pricing — docs.dev.runwayml.com](https://docs.dev.runwayml.com/guides/pricing/)
- [Kling API Pricing — Renderful](https://renderful.ai/blog/kling-api-pricing)
- [Veo 3.1 API Pricing — Atlas Cloud](https://www.atlascloud.ai/blog/tips/veo-3.1-api-pricing)
- [Sora 2 Pricing / sunset — CostGoat](https://costgoat.com/pricing/sora)
- [Luma AI Pricing — eesel AI](https://www.eesel.ai/blog/luma-ai-pricing)
- [Midjourney Pricing 2026 — eesel AI](https://www.eesel.ai/blog/midjourney-pricing)
- [FLUX API Pricing 2026 — Price Per Token](https://pricepertoken.com/flux-pricing)
- [Black Forest Labs official pricing](https://docs.bfl.ml/quick_start/pricing)
- [AI Video Generation API Pricing (July 2026) — BuildMVPFast](https://www.buildmvpfast.com/api-costs/ai-video)
- [OpenRouter Pricing / BYOK — Omid Saffari](https://omidsaffari.com/blog/openrouter-pricing)
- [Adobe Firefly indemnification — LicenseOrg](https://www.licenseorg.com/blog/adobe-firefly-indemnification-explained)
- [Adobe Firefly for business](https://business.adobe.com/products/firefly-business/firefly-ai-approach.html)
