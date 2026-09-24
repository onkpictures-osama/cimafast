# Decisions & Milestones Log

Daily archive of product decisions and shipped milestones, one file per day,
committed to this repo so the team's history survives outside any single chat
session. Companion to `PRODUCT-PLAN.md` (the current state of the plan) — this
is the day-by-day record of how it got there.

Requested by the owner, 2026-09-22.

## Format

`logs/YYYY-MM-DD.md`, written only on days with something to record — no
empty files for a quiet day:

- **Decisions** — owner-level calls from #decisions (scope, priority, money,
  infrastructure/security, production deploys, how the team works).
- **Milestones** — items that shipped to /v1 that day (the ✅ entries in
  `PRODUCT-PLAN.md`), one line each with the roadmap item and what changed.
- **Standup notes** — the day's #standups priority and blockers, when there's
  something worth keeping.

## Source

Each entry is assembled from:

1. `git log` on `preview` for the day's commits — this team already documents
   each decision and milestone as a commit message (e.g. "Log P9: ...",
   "✅ On /v1 ...", "Owner decisions" edits to `PRODUCT-PLAN.md`).
2. That day's diff to `PRODUCT-PLAN.md`'s "Owner decisions" and roadmap ✅
   lines.

No new data is invented for the log; it restates what the plan and the commit
history already say, dated.

## Maintenance

A daily job (owned by infrastructure) appends the day's entry and pushes it to
GitHub on the `preview` branch, the same branch and remote as the rest of this
checkout. This is a public repo — keep entries to product decisions and
shipped work; no credentials, no user/company data, no live-DB content (that
belongs in the private backups repo, see `PRODUCT-PLAN.md` F4).
