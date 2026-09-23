# Build plan — Profile pictures (الصورة الشخصية)

*Requested by Mohamed El-Zayat (co-founder), 2026-09-23: "start putting a plan to
add profile pictures for users and a way to upload it and save it easily and
smoothly."*

🗒️ **Proposal for discussion — not scoped, not built, not deployed.** Same
status as `SCRIPT-EDITOR-PLAN.md` / `ACTOR-CASTING-PLAN.md` when they were first
written. Everything below was checked against the code before being written; the
file/line citations are real and the open questions are left open on purpose.

*Relates to `PRODUCT-PLAN.md` → Continuous → "Redesign the Streamlit app
sidebar", which explicitly deferred this: "a user avatar photo (no such feature
exists yet — accounts have no photo field or upload path) … avatar is a
placeholder (initials) rather than real photo upload **unless the owner asks for
upload as its own feature**." This is that ask.*

---

## 1. The problem

Every place CimaFast shows who you are, it shows two letters in a yellow circle.

- `app.py:548-560` — the sidebar account row draws `_initials` from
  `display_name`.
- `board/app.py:422-425` + `board/templates/home.html:20` — the home page header
  does the same.
- `board/static/team.js:43-51` — the team table shows the name as plain text,
  with no avatar at all.
- `board/static/activity.js:103` — the activity log shows a bare username.

Both initials blocks carry the same comment, written when the sidebar was
redesigned on 2026-09-23 (`app.py:541-547`): *"مفيش ميزة صور حسابات في البرنامج
لسه (مفيش عمود صورة في جدول users، ولا مسار رفع) — ده خارج نطاق الشغلانة دي
عمدًا (تخزين/اعتدال/خصوصية محتاجين قرار لوحدهم)."* The code deferred this
decision deliberately. This doc is the decision.

The gap is sharper than cosmetics. CimaFast is a multi-company ERP where a crew
of 20+ people share one project's data, and the product already leans on
person-identity in three places — the team roster, the audit trail ("who changed
this scene"), and the "needs you" list. A crew recognises each other by face
faster than by a Latin username like `costume_designer`, especially in an
Arabic-first product where the username is the one field that is forced to be
English (`board/templates/team.html:62`: `pattern="[A-Za-z0-9._\-]+"`).

There is also a consistency problem the product created for itself this week:
actors already have photos (`actors.photo_path`, `database.py:541`, shipping as
part of P9), so the talent vault shows faces while the crew using it does not.

## 2. The outcome

Any logged-in user can set their own profile picture in under 15 seconds, from a
phone, without reading instructions — and it then appears everywhere their
identity appears, in both the Streamlit app and the board/home pages.

*Done when:* a department-head user on a phone opens their account section,
picks a photo from their camera roll, sees it immediately, saves it once, and
finds it in the sidebar, on the home page header and in their company's team
list — in Arabic RTL and in English — with a user who has set no photo still
seeing the current initials circle, unchanged.

---

## 3. Where a profile picture lives in the data model

**Decision: per user account, on the `users` table. Not per membership.**

Checked against the real schema rather than assumed
(`database.py:404-426` for Postgres, `database.py:739-763` for SQLite — the dual
DDL that `CLAUDE.md` warns is load-bearing):

- `users` is **global**, not company-scoped: `username TEXT NOT NULL UNIQUE`,
  with no `company_id` column. It holds the things that are true about a person
  regardless of who they work for — `display_name`, `email`, `job_title`,
  `password_hash`.
- `memberships` is the per-company join (`UNIQUE(company_id, user_id)`) and
  carries only `role` and `active` — the things that change per company.
- `accounts.companies_for(username)` (`accounts.py:211`) returns a list, and the
  home page renders a company switcher over it. So one person belonging to
  several companies is a real, supported case in F1, not hypothetical.

A face does not change when a freelance 1st AD switches from one production
company to another. Putting the photo on `memberships` would mean the same
person maintains N photos and re-uploads for every company that hires them —
the opposite of "easily and smoothly". It would also make the audit trail
ambiguous: `audit_log.username` (`database.py:779`) is a plain username with no
company key on the *actor*, so an avatar next to an audit row could not be
resolved to a single membership anyway.

**Proposed migration — additive, two columns, no data movement:**

```
ALTER TABLE users ADD COLUMN avatar_path TEXT;
ALTER TABLE users ADD COLUMN avatar_updated_at TEXT;
```

This matches the shape already used for actors (`photo_path` /
`photo_updated_at`, `database.py:541-542`) and the additive-migration pattern
`scripts/migrate_tenancy.py:95` documents ("كل جملها CREATE TABLE IF NOT EXISTS
/ ALTER TABLE ADD COLUMN — يعني بتزوّد بس"). Both DDL branches in `database.py`
must be edited, and the column added to the existing-database upgrade path — a
`users` row with `avatar_path IS NULL` is the normal state, not an error, so
there is nothing to backfill and nothing to roll back but a dropped column.

`avatar_updated_at` is worth having from day one for cache-busting (§6), not for
freshness nagging — the 3-month refresh rule in `ACTOR-CASTING-PLAN.md` is about
casting photos and does **not** apply to crew avatars.

> **Open — for infrastructure, not decided here:** whether to also record
> `avatar_source` (`upload` / `generated` / `gravatar`). Costs one nullable
> column now and is awkward to add later if an auto-avatar path ever appears.
> Recommend adding it; flagging rather than deciding because it is a schema call
> on the live `users` table.

---

## 4. Storage backend — where the bytes go

**Decision: local disk, reusing the path that already exists. R2 is not worth it
for this feature, on its own terms.**

`FINANCIAL-FRAMEWORK.md:716` recommends Cloudflare R2 ($0.015/GB-month, $0
egress) for **AI-generated images and video**, where the projected bill is
$300–600/month across 1,000 subscribers because the media is measured in
megabytes per asset and grows without bound.

Profile pictures are not that problem. At the 512×512 WebP this plan proposes
(§7), one avatar is roughly 30 KB. A thousand users is about **30 MB total** —
**under $0.01/month at R2's own price**. Cost is not an argument in either
direction here, so the decision has to be made on operational grounds, and on
those grounds local disk wins for a first version:

- **The path already exists and is proven.** `ui.py:180-198`
  (`save_uploaded_image` → `uploads/<subfolder>/<uuid>.<ext>`) and
  `ui.py:271-275` (`image_abs_path`) are what character reference images,
  location images, shot storyboards and actor photos all use today. Actor photos
  landed this week at `uploads/actors/<id>/avatar.png`. Profile pictures become
  `uploads/users/<id>/…` — one more subfolder, zero new infrastructure.
- **R2 has no abstraction layer to plug into yet.** `FINANCIAL-FRAMEWORK.md`
  recommends R2 *"once a provider-abstraction layer exists"*. It does not exist.
  Building one for 30 MB of avatars means credentials in secrets, a new network
  dependency in the upload path, a new failure mode when R2 is unreachable, and
  a signed-URL or proxy story for private images — all to solve a cost problem
  that is a rounding error of a rounding error.
- **Going local now does not block going to R2 later.** The DB stores a relative
  path string, so the migration is: copy the tree up, rewrite the column, swap
  the resolver in `ui.py`. Avatars are in fact the *ideal* first payload for
  that abstraction layer when it is built for AI media — small, non-critical,
  regenerable by asking the user to re-upload.

### ⚠️ The real risk with local disk, and it is pre-existing

**`uploads/` is not in the off-site backup today.** `.gitignore:18` ignores
`uploads/`, and `/opt/cimafast-backup/backup.sh:89-92` builds `worktree.tar.gz`
from `git ls-files --cached --others --exclude-standard` — tracked files plus
untracked-**and-not-ignored** files. Ignored directories are excluded. The daily
snapshot therefore contains `repo.bundle`, the worktree, `studio.db` and
`secrets/`, and **none of the uploaded images**.

This is not introduced by this feature — it already means every character
reference image, location photo, storyboard and actor headshot on production is
unprotected, while the F4 line in `PRODUCT-PLAN.md:96` reads as though user data
is covered. Profile pictures would silently inherit the same gap, with the extra
sting that a user who loses their photo *notices*.

> **⚠️ For infrastructure sign-off, not decided here:** either add `uploads/` to
> the F4 snapshot (a `tar` of the uploads tree next to `studio.db`, which also
> grows the encrypted daily snapshot), or make the R2 call now specifically to
> get durability rather than cost. **This should be resolved before profile
> pictures ship, and the backup gap for existing images is worth fixing
> regardless of what happens to this plan.** Recommend filing it as its own
> issue.

> **Open — for infrastructure:** whether `/v1` and production sharing a `venv`
> symlink but *not* an uploads tree causes confusion when the preview DB is
> refreshed from live (`snapshot_db.py`). A refreshed preview DB will contain
> `avatar_path` values pointing at files that exist only on production's disk.
> Today the same is already true of actor and reference images; the resolver at
> `ui.py:271-275` returns `None` for a missing file and callers degrade to no
> image, so the failure mode is "avatar missing on /v1", not a crash. Worth
> confirming that is acceptable rather than assuming.

---

## 5. Upload UX in Streamlit, and where it lives

### 5.1 Where the "my account" surface is today

There is no account settings **page**. Self-service account actions are exactly
one — change your own password — and it exists in two places:

- **Board / team page**: `board/templates/team.html:90-93`, a card headed
  *"حسابي — تغيير كلمة السر"*, posting to `POST /api/me/password`
  (`board/app.py:584` → `api_my_password`, `board/app.py:370` →
  `accounts.change_own_password`). Checked `team_page` (`board/app.py`): it
  requires a logged-in user but **not** admin — the admin-only sections are
  gated separately, so the "حسابي" card is reachable by every role including
  `department` and viewers. This is the natural home.
- **Streamlit**: `app.py:249-267`, but only as a *forced* interstitial when
  `must_change_password` is set. It is not reachable voluntarily.

**Proposal: the "حسابي" card on `/v1/team/` becomes the single account section**
— rename it *"حسابي"* with the avatar above the password fields — and the
Streamlit sidebar avatar (`app.py:548-560`) becomes a link into it rather than
growing its own editor. One place to change your account beats two.

> **Open — a genuine product call, for the owner:** the above puts the upload in
> the **board** (Starlette + HTML form), not in Streamlit. That is the better
> long-term home — `PRODUCT-PLAN.md`'s Continuous section says screens move
> *from* Streamlit *to* the new frontend — and `python-multipart 0.0.32` is
> already installed, so no new dependency. But Mohamed's request names uploading
> generically, and the Streamlit app is where crew spend their day. The two
> options are:
> - **(a) Board only** — one account section, the direction the product is
>   already moving, needs a new `POST /api/me/avatar` multipart route.
> - **(b) Streamlit too** — a second uploader inside a `⚙️ الإعدادات` expander,
>   reusing `st.file_uploader` and `save_uploaded_image` verbatim, which is a
>   half-day rather than a day but creates a second place to maintain.
>
> Recommend **(a)**, with the Streamlit sidebar avatar clickable through to it.
> Flagging rather than deciding because "where users go to do this" is a product
> decision, not an engineering one.

### 5.2 If Streamlit (option b), the concrete shape

`st.file_uploader` with the repo's existing constants, so nothing new is
invented:

```python
st.file_uploader(t("صورة شخصية"), type=IMAGE_TYPES, key="my_avatar")
```

- `IMAGE_TYPES = ["png", "jpg", "jpeg", "webp"]` (`ui.py:183`) — already the
  app-wide list, already used by characters, shots, locations and actors.
- **Not** `render_image_picker` (`ui.py:230-268`), despite it existing and
  offering upload/camera/AI-generate. Its third option generates an image from a
  prompt, which is right for a location and wrong for a person's face. Camera
  capture (`st.camera_input`) *is* worth keeping for a crew member at a desk —
  see the open question in §6.

**Size cap must be enforced in code, not in config.** `.streamlit/config.toml`
does not set `server.maxUploadSize`, so Streamlit's 200 MB default applies. It
cannot simply be lowered: the same setting governs the screenplay uploader
(`views/import_tab.py:255`, `type=["docx","txt","pdf","json"]`), and a script
`.docx` with embedded images can legitimately be tens of megabytes. So the
avatar cap is a `len(uploaded_file.getvalue())` check inside the handler, with a
readable Arabic error — see §8.

---

## 6. "Easily and smoothly" — the actual bar

This is the part of the request that is not "does it work". Five things, each
with the specific failure it prevents:

1. **Immediate preview, before saving.** The moment a file is chosen, show it at
   the final circular crop, at real avatar size (~96 px) *and* at the ~28 px the
   sidebar actually uses. A photo that looks fine at full size and unrecognisable
   at 28 px is the single most common avatar disappointment, and seeing both
   sizes before committing removes the upload-look-reupload loop entirely.

2. **One save, one rerun, land where you were.** Streamlit's model makes this the
   hard part: `st.file_uploader` reruns the script on selection, and today's
   image handlers follow the save with an explicit `st.rerun()`
   (`ui.py:261-264`) which throws away scroll position. Mitigations, in order of
   preference: put the whole thing inside an `st.form` so the rerun happens once
   on submit rather than on every widget touch; keep the account section inside
   an expander whose open/closed state is held in `session_state` so it survives
   the rerun; and show the saved state with the existing `mark_saved` /
   `show_saved_badge` helpers (`ui.py`, already used by characters and shots)
   rather than a `st.success` banner that shifts the layout down.
   **If option (a) in §5.1 is chosen, this problem mostly disappears** — a
   `fetch()` POST from `team.js` updates the `<img>` in place with no page
   reload at all, which is a meaningfully smoother experience than anything
   achievable inside Streamlit's rerun model. That is a real argument for (a)
   beyond architecture tidiness.

3. **Errors in Arabic, in plain words, never a traceback.** Every rejection path
   gets a sentence a film crew member understands, in the register
   `permissions.py:31-38` already uses. Draft strings:
   - wrong type → *"الصورة لازم تكون PNG أو JPG أو WEBP."*
   - too large → *"الصورة كبيرة أوي — أقصى حجم ٥ ميجا. جرّب صورة أصغر."*
   - unreadable/corrupt → *"مقدرناش نقرا الصورة دي. جرّب صورة تانية."*
   Each needs an entry in `i18n.py`'s `TRANSLATIONS` (the Arabic-keyed dict that
   `t()` reads, `i18n.py:518-523`) so the English toggle works, per the repo
   convention that new UI strings carry both the Arabic key and the English
   value.

4. **The placeholder is the existing initials circle — do not invent a second
   one.** `app.py:551` and `board/app.py:425` compute identical initials from
   `display_name`, drawn in brand yellow-on-navy. Users with no photo see exactly
   what they see today; nothing regresses on day one, and the feature degrades
   gracefully forever. Two details worth getting right: the initials logic
   (`"".join(w[0] for w in _display_name.split()[:2])`) already handles Arabic
   names correctly since it slices words not bytes, and `.upper()` is a no-op on
   Arabic — but `_initials` must stay wrapped for RTL so a two-letter Arabic
   initial pair reads right-to-left.

5. **Removing the photo is one click and obvious.** A *"🗑️ شيل الصورة"* button,
   matching `ui.py:265` verbatim, that nulls the column and deletes the file.
   Users are more willing to upload when undo is visible.

**Cache-busting:** browsers will cache `/v1/uploads/users/7/avatar.webp`
aggressively, so a replaced photo would appear not to have changed — which reads
as a broken save. Two options: append `?v=<avatar_updated_at>` to the URL (why
§3 proposes that column), or keep the UUID filename scheme `save_uploaded_image`
already uses (`ui.py:194`) so every upload gets a fresh path. **Recommend the
UUID filename** — it is what the codebase already does, it needs no query-string
discipline at every call site, and it makes the old file's deletion explicit.

---

## 7. Image handling — resize and crop

**Yes, this needs server-side processing. A modern phone photo is 3–8 MB and
4000 px wide; storing it to render at 28 px is wasteful in disk, in page weight,
and in how long the sidebar takes to paint.**

**Pillow is already available and needs no new install.** `pip show pillow`
reports **12.3.0**, `Required-by: reportlab, streamlit` — it is a hard transitive
dependency of two things the app cannot run without. It is *not* listed in
`requirements.txt`, which currently ends at `psycopg2-binary`. If this plan is
built, **add `pillow>=10.0.0` to `requirements.txt` explicitly** — relying on a
transitive dependency for a feature is how a future Streamlit release quietly
breaks avatars.

Proposed processing, on save:

1. Open with `PIL.Image.open()` and call `.verify()` — this is also the real
   file-type validation (§8), not a separate step.
2. Apply EXIF orientation (`ImageOps.exif_transpose`). Without it, photos taken
   in portrait on a phone appear rotated 90°, which looks like a bug and is one
   of the most common avatar complaints.
3. Centre-crop to square, then resize to **512×512** (`ImageOps.fit`, LANCZOS).
   512 covers every display size in the product with room for a future larger
   profile view; a second 96×96 thumbnail is not worth the complexity at this
   volume.
4. Strip metadata by re-encoding — GPS coordinates in a crew member's selfie
   should not be sitting on our disk.
5. Save as **WebP, quality 85**. Roughly 30 KB, supported by every browser this
   product targets, and already in `IMAGE_TYPES` so it is an accepted input too.
   Storing one normalised format means display code never branches on extension.

Note this diverges from `save_uploaded_image` (`ui.py:186-198`), which writes the
uploaded bytes through untouched and keeps the caller's extension. **Proposal: do
not change that shared function** — characters, locations and shots depend on its
current behaviour, and reference images genuinely want full resolution. Add a
sibling, e.g. `save_avatar_image(uploaded_file, subfolder)` in `ui.py`, next to
it. Smallest change that fully solves it.

---

## 8. Security and validation

**The existing upload path trusts the browser.** `ui.py:193` takes the extension
straight from the filename — `ext = os.path.splitext(uploaded_file.name)[1] or
".png"` — and writes the bytes unexamined. Streamlit's `type=` parameter filters
by **extension**, not content, so today a file named `x.png` containing anything
at all is written to disk under an attacker-chosen extension. This is a
pre-existing property of every image upload in the app, not something profile
pictures introduce; it matters more here because profile pictures are the first
image upload aimed at *every* user rather than at the small set of people doing
breakdown work.

Proposed for the avatar path specifically:

- **Content validation, not extension trust.** `Image.open()` +
  `.verify()` + an allow-list check on `img.format` in `{PNG, JPEG, WEBP}`.
  Because step §7 re-encodes to WebP, the bytes written to disk are bytes Pillow
  produced, never bytes the user supplied — which closes the polyglot-file class
  of problem rather than trying to detect it.
- **Hard size cap, checked before decode.** Reject on `len(getvalue())` over
  **5 MB** with the message in §6. Checked first so a malicious 200 MB upload is
  refused before Pillow is asked to parse it.
- **Decompression-bomb guard.** Pillow raises `DecompressionBombWarning` above
  ~89M pixels by default; set an explicit, much lower
  `Image.MAX_IMAGE_PIXELS` for this path (e.g. 50M) and treat the exception as
  the "مقدرناش نقرا الصورة" error.
- **Server-chosen filename and path.** Keep `uuid4().hex` (`ui.py:194`) and
  build the directory from the integer `users.id`, never from anything the user
  types. Worth noting `image_abs_path` (`ui.py:274`) does
  `os.path.join(dirname(__file__), rel_path)` with no traversal check — safe
  today only because every stored path is written by our own code. If avatars
  ship, that function is worth a `os.path.realpath` containment check, since it
  will now be resolving paths on behalf of a route that takes a user id from a
  URL.
- **Who may change whose photo.** Setting an avatar is a self-service action on
  your own account, like `change_own_password` — it should go through the same
  "acting on myself" path and **not** be a `permissions.py` capability. A viewer
  must be able to set their own photo. Concretely this means the write runs
  under `permissions.system()` (`permissions.py:97-103`) with the username taken
  from the session, exactly as `accounts.change_own_password` does — never from
  the request body. Whether a **company admin** may change or remove a *team
  member's* photo is a separate question, below.
- **Audit.** Write an `audit_log` row on avatar set/remove (entity `users`,
  action `update`), with the path — not the bytes — as the change value, matching
  how F3 already handles sensitive columns (`PRODUCT-PLAN.md:92`: a password
  column is logged as *changed*, never with its value).
- **Serving.** There is no `/uploads` mount in the board app today — checked:
  `board/app.py:585-589` mounts only `/static`, `/fonts` and `/brand`. A new
  route is needed for the board and home pages to render avatars in `<img>`
  tags. It should be an authenticated route that looks the path up by user id
  and streams the file, **not** a blanket `StaticFiles` mount on `uploads/` —
  that directory also contains every project's character, location and
  storyboard images, and mounting it would expose one company's reference
  material to any other company, breaking the F1 isolation that was the whole
  point of the tenancy work.

> **⚠️ For infrastructure sign-off, not decided here** — three items, all in
> their remit per `PRODUCT-PLAN.md`'s F-series ownership:
> 1. The `uploads/` backup gap (§4) — **resolve before shipping.**
> 2. The serving route above, specifically the isolation argument against a
>    static mount.
> 3. Whether a 5 MB cap and a 512 px normalisation are the right numbers, and
>    whether avatar uploads need any rate limiting (a user re-uploading in a
>    loop is not a realistic threat at this scale, but it is their call).

> **Open — a product call, for the owner:** **content moderation.** Nothing in
> this plan prevents a user uploading something offensive as their avatar, and
> it would then appear next to their name in every colleague's team list. At
> current scale (one company, 13 accounts) this is a non-issue. At the
> 1,000-subscriber scale `FINANCIAL-FRAMEWORK.md` models, it is not. The cheap
> first answer is the one already implied by §8: a **company admin can remove a
> member's photo** (not replace it) from the team page, which handles the
> realistic case without building anything. Recommend that; flagging because it
> is a policy decision about what companies can do to their staff's accounts.

> **Open — smaller:** should `st.camera_input` be offered alongside file upload,
> as `render_image_picker` (`ui.py:249`) already does for locations? Convenient
> for someone at a desk, and the code exists. The comment at `ui.py:247-248`
> notes the camera must stay behind an explicit choice so the browser does not
> prompt for camera permission on every page open — that constraint carries over.

---

## 9. Where the picture displays

Four surfaces exist today; all four are found in the code, not guessed. Every
one falls back to the current initials circle when `avatar_path IS NULL`.

| Where | File | Today | With this plan |
|---|---|---|---|
| Streamlit sidebar account row | `app.py:548-560` | initials, ~28 px | photo, same circle, same size |
| Home page header | `board/app.py:422-425`, `board/templates/home.html:20` | initials in `.who__avatar` | photo, same slot |
| Team member table | `board/static/team.js:43-51` | name text, no avatar | small avatar before the name |
| Activity log rows | `board/static/activity.js:103` | bare username | *open — see below* |

- **Sidebar and home header** are the two the owner will look at first, and both
  already have a styled circular element to drop an `<img>` into. The sidebar
  one is the same element the approved sidebar redesign mockup shows a photo in
  (`PRODUCT-PLAN.md`, Continuous), so this closes that loop. The home header's
  span carries `aria-hidden="true"` (`board/templates/home.html:20`) because the
  name sits right beside it — an `<img>` replacing it should keep that, or carry
  `alt=""`, rather than repeating the name to a screen reader.
- **Team table** is where avatars earn their keep — a roster of 20 names reads
  far faster with faces. `row()` in `team.js` builds cells with
  `document.createElement`/`textContent` (no `innerHTML` on user data — keep it
  that way; an avatar is an `<img>` element with a `src` we construct, never an
  interpolated HTML string).
- **Activity log** is the one to think about rather than default to yes. It is a
  dense table read for *what changed*; 200 tiny faces could easily make it
  slower to scan, and it is also the one place where an avatar could be
  misleading if a user was removed and re-added.

> **Open — a design call, better answered by looking at it than by arguing:**
> avatars in the activity log — yes or no. Cheap to try both once §9's first
> three are built.

Not in scope: the login screen (no user is known yet), and exported reports
(`export.py`) — crew faces in an official PDF call sheet is a real idea, but it
belongs with the "bring exported reports onto the brand guide" item in
`PRODUCT-PLAN.md`, not here.

---

## 10. Slices

Each ships to /v1 and is verified in a real browser before the next, per
`CLAUDE.md`.

| Slice | Contents | Size |
|---|---|---|
| A | Schema: two columns on `users`, both DDL branches + upgrade path; `repo.py` getter/setter; tests | ~½ day |
| B | `save_avatar_image()` in `ui.py` (Pillow: verify, EXIF, crop, 512 WebP, strip metadata) + validation and Arabic error strings in `i18n.py`; unit tests on real image bytes incl. a corrupt file and an oversize one | ~½ day |
| C | The upload surface in the "حسابي" card (§5.1 option a or b), with preview at both sizes and remove | ~1 day |
| D | The authenticated serving route (§8) + avatar in sidebar and home header, with initials fallback | ~½ day |
| E | Avatar in the team table; RTL and phone verification in a real browser | ~½ day |
| — | **Blocking, not a slice:** `uploads/` backup gap (§4) resolved with infrastructure | — |

Testing note: `PRODUCT-PLAN.md` records `script_parser.py` and the
SQLite/Postgres translation as the highest-value test targets. Slice B is a good
citizen here — image validation is pure-function logic with obvious edge cases
(corrupt bytes, a `.png` that is really a PDF, a 10000×10 panorama, an EXIF-
rotated portrait), and is cheap to cover properly.

---

## 11. Decisions needed before this is built

**Owner / co-founder:**
1. **Where the upload lives** — board account section only, or Streamlit too
   (§5.1). Recommend board-only, with the sidebar avatar linking to it.
2. **Admin removal of a member's photo** as the moderation answer (§8).
   Recommend yes — remove, not replace.

**Infrastructure:**
3. **The `uploads/` backup gap** (§4) — blocking, and worth fixing for the
   existing images regardless of this feature.
4. **The authenticated serving route**, specifically not a static mount on
   `uploads/` (§8).
5. **`avatar_source` column now or never** (§3); caps and limits (§8).

**Design:**
6. Avatars in the activity log — yes or no (§9).

Nothing here changes what a user's data means, costs money, or is irreversible,
so once 1–5 are answered this is straightforward build work.
