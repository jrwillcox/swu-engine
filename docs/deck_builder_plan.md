# Custom Deck Builder — staged implementation plan

A per-user, "Spotify-playlist"-style custom deck builder. Each whitelisted user
curates 0+ custom decks; complete ones surface in the start-screen deck dropdown
for use by the player **or** the bot opponent. Cards are added quickly from the
Card Explorer while a live panel shows the target deck's contents and remaining
space. SWU deckbuilding rules are enforced.

This doc is the **source of truth**. Implement one stage per clean session
(prompt: "Read docs/deck_builder_plan.md and implement Stage N"). Each stage is
self-contained, lists the files it touches, its acceptance criteria, and its
tests. Backend stages land before the frontend stages that consume them.

---

## Design decisions (read once, up front)

- **Identity by DB `id`, not (set, number).** The whole app already keys cards by
  the unique DB primary key `id` (the Card Explorer, the image endpoint, the game
  serializer). Custom decks store **card ids**, sidestepping the Leader/Token
  `(set, number)` collision entirely (see "Gotchas" in
  [`encoding_guide.md`](encoding_guide.md)).
- **Per-user, server-backed, file storage** — mirror the existing `auth.py` /
  `bugs.py` pattern. Decks live under `data_dir()/custom_decks/<username>/<id>.json`
  (path overridable via `SWU_CUSTOM_DECKS` for tests). `data/` survives deploys
  (`deploy.ps1` mirrors code only), so a user's decks persist and DEV/DEPLOYED stay
  separate — the same guarantee `users.json` and `bug_reports/` rely on.
- **Drafts allowed.** A deck may be saved half-built (incomplete). `complete` is a
  *derived* property (see rules). Only **complete** decks appear in the game
  dropdown; **all** (incl. drafts) appear in the Deck Manager.
- **Custom deck key = `custom:<username>:<id>`.** `resolve_deck` in
  `src/swu/web/decks.py` gains a branch for this prefix so a game can be created
  from a custom deck with no change to the game-creation path (the `deck` field
  already accepts either a catalog key or a path — extend it to this third form).
- **The existing `swu.deckSelection` localStorage seam** in
  `web/src/components/CardExplorer.tsx` (a single anonymous `{cardId: count}` map,
  `MAX_COPIES = 3`) is the precursor to this feature; Stage 5 evolves it into
  server-backed multi-deck editing.

### SWU deckbuilding rules to enforce

- Exactly **1 Leader** and exactly **1 Base** (1 copy each). The user mused about
  "1–3" — that is not a real rule; enforce exactly 1 of each.
- Exactly **50** other cards (units / events / upgrades) for a *complete* deck.
- **Max 3 copies** of any card by default.
- **Per-card overrides:** some cards raise the cap. The override is printed in the
  card `text`: e.g. Swarming Vulture Droid (JTL_256, JTLP_20) — *"A deck can have
  up to 15 copies of this card."* Parse `"A deck can have up to (\d+) copies"` →
  that number; else 3. This is the `deckbuild_max_copies(card)` function.
- **Uniqueness caveat (decide explicitly):** the *game-legality* validator
  `swu/cards/decklist.py::validate_decklist` currently limits **unique** cards to 1
  copy in the deck. That is stricter than real SWU deckbuilding (a unique card may
  have up to 3 copies in a deck; the "unique" rule only forbids two *in play*).
  **For the deck builder use `deckbuild_max_copies` (3 / override), NOT the
  unique→1 rule.** Leave `validate_decklist` alone (it gates loaded fixtures); the
  builder gets its own copy-limit function so we don't regress existing decks.

### Data model (`CustomDeck`)

```
id:        str            # slug: "<YYYYMMDD-hhmm>-<name-slug>", stable
name:      str            # user-facing, renameable
owner:     str            # lowercased username
leader_id: int | null     # DB card id
base_id:   int | null     # DB card id
cards:     {str(id): int} # DB card id -> count (non-leader/base cards)
created:   ISO8601
updated:   ISO8601
```

Derived (never stored): `count` = sum(cards.values()); `complete` = leader_id and
base_id set AND count == 50 AND every entry within its `deckbuild_max_copies`;
`errors` = list of human-readable rule violations (for the Deck Manager to show).

---

## Stage 1 — Image/token collision audit + repair (the reported Ahsoka bug) — DONE 2026-07-02

**Landed:** `scripts/audit_images.py` (pure `audit_images(db_file, data_dir) ->
ImageAudit` core + CLI, respects `SWU_DB`/`--db`, exits non-zero on collisions or
missing files, docstring documents the manual DEV→DEPLOYED data-sync commands);
cache-bust hardening — `cards.image_version(card_id, face, variant)` (mtime,
lru_cached) threaded into `serializers._card_image_url` as `&v=<mtime>` so the
`immutable`-cached image endpoint never serves stale corrected art (the iPad
Safari repro). Audit run against **both** instances' DBs: **both CLEAN** — 0
collisions, 0 missing, 29 collision-groups OK, 54 informational stale files (the
old number-only `1_front.png` leftovers). Tests: `tests/test_audit_images.py`
(6) + `test_web_api.py` cache-bust assertion; full web suite green.



**Independent of the deck builder; quick; fixes a live player-facing bug.** Do it
first so players stop seeing the wrong art.

**Finding established (2026-07-02).** The bug is **not reproducible in the current
code/data**, and DEV == DEPLOYED (in tandem), so stale deployed data is ruled out:
- `data/swu.db` has **0** image-path collisions.
- Token units load by name → their correct unique id (Battle Droid=14030,
  Clone Trooper=14035); `image_file_for_card` resolves those to the droid/clone
  files, never a lightsaber (Ahsoka's Padawan Lightsaber = TWI_248, id 15601 →
  `images/TWI/248_front.png`, shared by no token).
- Every frontend image URL is built from the **unique `card_id`**
  (`/api/cards/<id>/image` — `ui.tsx`, `serializers.py`); nothing keys on
  set+number or name.

**Prime remaining suspect: a stale iPad browser cache.** The 2026-06-27
image-collision fix (`project_image_collisions.md`) renamed image files from
number-based to id-based, changing *what art a given `/api/cards/<id>/image` URL
returns* — but the URL string never changed. Safari may still serve the old
(collided) image it cached before the fix, so a droid token whose URL once
returned the wrong art keeps showing it until the cache is busted.

**The fix:** (1) add a cache-busting version token to `_card_image_url` in
`serializers.py` (e.g. `?v=<image file mtime>` per card id) so a corrected image
is never served stale — this is the real defensive fix; (2) confirm with the audit
script below; (3) have the player hard-reload / clear their browser cache once. If it still
repros after cache-busting, gather specifics (which deck/card, the token unit in
an arena vs an attached upgrade, a screenshot + the report's `game.json`) — it
would then be a genuinely new mechanism, not the known collision.

**Goal.** Ship a repeatable audit script and confirm/repair the deployed data.

- New `scripts/audit_images.py`: for the given DB (respecting `SWU_DB`), report
  (a) any two card ids sharing an `image_front_path`/`image_back_path`
  (collisions), (b) referenced image files missing on disk, (c) on-disk files not
  referenced by any card (stale, e.g. the old number-only `1_front.png` scheme),
  and (d) an explicit check of every Leader/Token that share a `(set, number)`
  and of Ahsoka's Padawan Lightsaber TWI_248. Exit non-zero if (a) or (b) is
  non-empty. Reuse the existing id-based naming logic from
  `scripts/fix_image_collisions.py` / `scripts/fetch_images.py`.
- Run it against **both** instances' DBs (`swu-game/data/swu.db` and
  `swu-game-deployed/data/swu.db`) via `SWU_DB`. If the deployed DB shows the
  collision or missing/misnamed token images, repair it: re-run
  `scripts/fix_image_collisions.py` + image fetch on the deployed `data/`, or copy
  the corrected `swu.db` + `images/` from DEV to DEPLOYED (data is not code, so
  this is a manual data sync — document the exact command in the script's
  `--help`/docstring).
- Optional hardening: add a cache-busting query (`?v=<image mtime or card updated>`)
  to `_card_image_url` in `serializers.py` so a corrected image is never served
  from a stale browser cache. Keep it cheap (only if the bug proves to be caching).

**Acceptance.** `python scripts/audit_images.py` prints a clean report (0
collisions, 0 missing) for the DEV DB; running it against the deployed DB either
confirms clean or the repair makes it clean; the droid token renders its own art
in a live game on the instance players use.

**Tests.** `tests/test_audit_images.py` — a synthetic DB with a deliberate
collision is flagged; a clean DB passes; the TWI_248 / token checks assert the
right ids resolve to the right paths.

---

## Stage 2 — Backend: deck store + deckbuilding rules (no UI, no routes)

**Goal.** The storage + rules core, fully unit-tested, callable in isolation.

- New `src/swu/cards/deckrules.py`:
  - `deckbuild_max_copies(card) -> int` — parse `"A deck can have up to (\d+)
    copies of this card"` from `card.text` (normalise `\xa0`); default 3.
  - `deck_errors(leader, base, cards, repo) -> list[str]` — the builder's rule
    checker (exactly-1-leader, exactly-1-base, ==50 others for complete, per-card
    copy cap via `deckbuild_max_copies`). Distinct from
    `decklist.validate_decklist` (which keeps its game-legality unique→1 rule).
- New `src/swu/web/deckstore.py`:
  - `CustomDeck` Pydantic model (fields above) + `DeckSummary` (id, name, count,
    complete) for list views.
  - `DeckStore` (thread-safe, file-backed, `SWU_CUSTOM_DECKS` override → else
    `data_dir()/custom_decks`): `list_decks(user)`, `get(user, id)`,
    `create(user, name)`, `rename(user, id, name)`, `set_cards(user, id, *,
    leader_id, base_id, cards)` (or granular `add_card`/`remove_card`),
    `delete(user, id)`. Ids are slugs (stable); a deck is one JSON file under the
    owner's folder. Compute `complete`/`errors` on read via `deckrules` +
    the card repository (`CardRepository`, DB id → card).
  - Card-id validation: reject ids that are not real non-token cards; enforce that
    a card placed in the leader slot is a `Leader`, base slot is a `Base`, and the
    50-pool holds neither Leaders/Bases nor Token types.

**Acceptance.** `DeckStore` round-trips a deck to disk; rules compute correctly
incl. the Swarming Vulture Droid 15-copy override; drafts persist; delete removes
the file.

**Tests.** `tests/test_deckstore.py` — create/rename/delete, add/remove cards, copy
caps (3 default, 15 override, over-cap error), leader/base slot type enforcement,
complete/incomplete derivation, multi-user isolation (user A can't see user B's
decks), `SWU_CUSTOM_DECKS` honoured.

---

## Stage 3 — Backend: API routes + catalog/resolve integration — DONE 2026-07-02

**Landed:** auth-gated CRUD routes in `app.py` (`GET/POST /api/decks/custom`,
`GET/PATCH/DELETE /api/decks/custom/{id}`, granular `POST …/{id}/cards`
`{card_id, delta}`), all `Depends(current_user)` (401 unsigned; 404 on another
user's id via the store's per-user folder scoping — owner isolation is intrinsic,
no extra check). PATCH uses `model_fields_set` to tell "omitted" from "explicit
null" (an explicit `null` clears the leader/base slot). A **shared singleton**
`deckstore.get_deck_store()` (lazy, honours `SWU_CUSTOM_DECKS`) backs BOTH the
routes and `resolve_deck`, so a game created from a `custom:…` key sees exactly
what the routes wrote (tests reset it via `monkeypatch.setattr(deckstore,
"_SINGLETON", DeckStore(root))`). `decks.resolve_deck` gained a `custom:<user>:<id>`
branch (`deckstore.resolve_custom_deck` + `parse_custom_key`) that expands to a flat
`[leader, base, *pool]` card list and raises `FileNotFoundError` (→ HTTP 400) when
missing/incomplete. `/api/decks` now takes an optional bearer header and **appends
the caller's *complete* customs** after the official decks, each `DeckChoice`
tagged `kind` (new field; `"official"` default, `"custom"` for customs, key
`custom:<user-lc>:<id>`, label `"<name> (custom)"`); anonymous → official only.
New request models in `models.py` (`CreateCustomDeckRequest` /
`PatchCustomDeckRequest` / `CardDeltaRequest`). Tests:
`tests/test_web_deckbuilder.py` (19) — CRUD, owner isolation (404), unsigned
(401), catalog merge (only complete customs, `kind` tags), `resolve_deck`,
incomplete→400, and a **full HTTP game with a custom deck on each seat**. All
99 web-suite tests (deckstore + deckbuilder + web_api + bugs + auth) green.

**Goal.** Expose the store over HTTP (auth-gated per user) and let a game be
created from a custom deck.

- Routes in `src/swu/web/app.py`, all `Depends(current_user)` (the `bugs.py`
  pattern), a `DeckStore` singleton like `AUTH`/`STORE`:
  - `GET  /api/decks/custom` → `list[DeckSummary]` (the caller's decks).
  - `POST /api/decks/custom` `{name}` → `CustomDeck` (create empty draft).
  - `GET  /api/decks/custom/{id}` → `CustomDeck`.
  - `PATCH /api/decks/custom/{id}` `{name?, leader_id?, base_id?, cards?}` →
    `CustomDeck` (rename and/or edit; partial). Include granular
    `POST /api/decks/custom/{id}/cards` `{card_id, delta}` for the Explorer's fast
    +/- if a full-map PATCH proves chatty.
  - `DELETE /api/decks/custom/{id}` → `{ok: true}`.
  - Return 404 for another user's deck id (owner check), 401 when unsigned.
- `src/swu/web/decks.py`:
  - `resolve_deck(deck)` gains a `custom:<username>:<id>` branch → load via
    `DeckStore`, build the flat `list[AnyCard]` (leader + base + expanded cards)
    through the `CardRepository` by DB id. Raise `FileNotFoundError` (existing
    contract → 400) if missing/incomplete.
  - Extend the catalog surfaced to the start screen: `GET /api/decks` (or a new
    `include_custom` param) accepts the optional bearer header and **appends the
    caller's *complete* custom decks** after the official ones, each `DeckChoice`
    tagged `kind: "custom"` (add a `kind` field: `"official"` default). Anonymous
    → official only. Custom `DeckChoice.key` = `custom:<username>:<id>`.

**Acceptance.** Full CRUD over HTTP with auth; a game created via `POST /api/games`
with `deck: "custom:<user>:<id>"` on either seat plays to a winner; `/api/decks`
lists official + the caller's complete customs.

**Tests.** `tests/test_web_deckbuilder.py` — CRUD happy paths, owner isolation
(user B gets 404 on user A's deck), unsigned → 401, `resolve_deck` builds a custom
deck, a **full game over HTTP with a custom deck on each side** (the
`test_web_api.py` full-game pattern), catalog merge shows only complete customs.

---

## Stage 4 — Frontend: Deck Manager (playlist CRUD) — DONE 2026-07-02

**Landed:** new `web/src/components/DeckManager.tsx` — an App-level full-screen
mode (reusing the `.explorer` shell) reached from a new **🃏 My decks** button on
`NewGameScreen` (shown only when signed in). Lists the caller's decks with a
**Complete/Draft** pill (the `errors` join as its `title` tooltip), `count/50`,
and 👑 leader / 🛡 base name badges (resolved via `api.catalog()` into an
id→card map — best-effort, falls back to `#<id>`). **New deck** (inline name
input → `POST`, then opens the fresh deck), inline **rename** (row → input →
`PATCH {name}`), and **Delete** behind the existing `ConfirmDialog`. Opening a
deck shows a **read-only** contents view (leader/base slots, errors list, and the
pool grouped by name `×count`) — Stage 5 turns this into the Explorer add-mode
deep-link. Client: `api.customDecks.{list,create,get,patch,delete,cards}` +
`CustomDeck`/`CustomDeckSummary`/`PatchCustomDeckRequest` types; `DeckChoice`
gained the optional `kind` field (Stage 3); shared `web/src/game/deckbuild.ts`
(`DECK_SIZE`/`DEFAULT_MAX_COPIES`). App-level mode switch + `"decks"` added to
`ScreenId` (so a bug filed from the manager is labelled). Tests:
`web/tests/deckmanager.test.tsx` (5) — renders pills/counts, create posts, rename
patches, delete-behind-confirm, open-shows-contents. Full web suite **110 tests
green**; `tsc --noEmit` + `vite build` clean.

**Goal.** A screen to make/rename/delete decks and see their state — the "playlist"
management surface.

- New `web/src/components/DeckManager.tsx`: lists the user's custom decks (name,
  `count/50` + leader/base badges, a "Complete"/"Draft" pill, `errors` tooltip),
  with **New deck** (name prompt → create), inline **rename**, and **Delete**
  behind an **"Are you sure?"** confirm dialog (reuse the existing `ConfirmDialog`
  pattern used for enemy-attach). Opening a deck can deep-link into the Explorer in
  add-mode (Stage 5) or show a read-only contents list for now.
- `web/src/api/client.ts` + `web/src/api/types.ts`: `CustomDeckSummary`,
  `CustomDeck`, and `api.customDecks.*` (list/create/get/patch/delete/cards)
  client methods (bearer header via the existing auth plumbing).
- Entry point: a **"My decks"** button on `NewGameScreen.tsx` (near "Browse the
  card explorer"), shown only when signed in. App-level mode switch (like the
  explorer) in `App.tsx`.

**Acceptance.** A signed-in user can create, rename, and delete a deck (with
confirm); drafts persist across reloads; counts/complete badges reflect the deck.

**Tests.** `web/tests/deckmanager.test.tsx` — renders decks, create posts, rename
patches, delete shows confirm then deletes, complete/draft pill logic.

---

## Stage 5 — Frontend: Card Explorer "add to deck" mode + live deck panel — DONE 2026-07-02

**Landed:** an **"Adding to" selector** in the Card Explorer toolbar (shown once
the caller's decks load via `api.customDecks.list`; absent for anonymous/no-deck).
Picking a deck enters **add mode**: the per-tile and zoom `+`/`−` steppers now edit
that **server** deck instead of the anonymous `swu.deckSelection` (back-compat kept
verbatim when "None (just browsing)" is selected). A pool card uses the granular
`POST …/{id}/cards {card_id, delta}` endpoint; a **Leader**/**Base** card fills its
slot via `PATCH {leader_id|base_id}` (a **ConfirmDialog** gates replacing an
occupied slot). Edits are **optimistic + serialised** (a `writeChain` promise + a
`seqRef`/`activeDeckRef` guard) so rapid clicks apply in order and only the latest
write's server truth for the still-active deck is committed; a failed write
re-syncs from `GET`. `+` is disabled at a card's **`deckbuild_max_copies`** (new
field on the explorer payload — `explorer.py` calls `deckrules.deckbuild_max_copies`;
default 3, Swarming Vulture Droid = 15) and when the **50-pool is full**, each with
an explanatory `title`. A compact **live deck rail** (`DeckPanel`) shows the deck
name + Complete/Draft pill, running **X/50** + "N to go", the 👑 leader / 🛡 base
slots (each clearable), and the pool listed `SET NUM · Name ×count` (each with a
`−`), names resolved from the catalog id→card map. Tiles already in the deck show
their `×count` badge (the existing `xtile-count`). Tests:
`web/tests/explorer_addmode.test.tsx` (6 — enter add mode + rail, granular add/
remove, cap disables `+`, leader slot via PATCH, anonymous back-compat) +
`ExplorerCard.deckbuild_max_copies` type. Full web suite **116 tests green**;
`tsc --noEmit` + `vite build` clean; backend `tests/test_explorer.py` green.

**Goal.** The seamless bulk-add experience with visible remaining space.

- In `web/src/components/CardExplorer.tsx`, add an **"Adding to: [deck ▾]"**
  selector in the toolbar (the user's decks + "None"). When a deck is chosen the
  explorer is in **add mode**: the per-tile `+`/`−` steppers and the zoom
  `+`/`−` now edit **that server deck** (debounced `cards` PATCH or the granular
  `/cards` delta endpoint), not the anonymous `swu.deckSelection`. Adding a card
  whose type is Leader/Base fills the deck's **leader/base slot** (replace the
  current one, with a small confirm if occupied). Disable `+` at a card's
  `deckbuild_max_copies` and when the 50-pool is full; show why.
- A compact **deck panel** (side rail or bottom drawer) listing the current
  deck's contents to save space: `SET NUM · Name ×count`, grouped
  (Leader / Base / deck), with the running **total (X/50)** and **remaining**.
  Cards already in the deck show their count on the tile (the existing
  `xtile-count` badge).
- Keep the anonymous `swu.deckSelection` path working when **no** deck is selected
  (back-compat), or migrate it into a "scratch" deck — pick one and note it.

**Acceptance.** With a deck selected, clicking `+` on several cards updates the
server deck and the live panel; caps are enforced with clear messaging; leader/base
slotting works; the panel shows total and remaining at a glance.

**Tests.** `web/tests/explorer_addmode.test.tsx` — selecting a deck enters add
mode, `+`/`−` hit the API, cap disables `+`, leader card fills the leader slot,
panel totals update.

---

## Stage 6 — Frontend: start-screen dropdown + play with custom decks (end-to-end) — DONE 2026-07-02

**Landed:** the two `deck-col` button lists on `NewGameScreen` are now two
grouped `<select>` dropdowns (**You** / **Opponent (bot)**), each an `<optgroup
label="Official">` (built-in + graduated) followed by an `<optgroup
label="Custom">` (rendered only when the caller has complete customs), split by the
Stage-3 `DeckChoice.kind` (a missing `kind` → "official" for back-compat). The
leader/base sub-label rides along as each option's `title` tooltip **and** a live
`.deck-col-meta` line under the select for the current pick. To surface customs at
all, `api.decks()` now sends the bearer header (`authHeaders()`) so the backend
appends the caller's complete customs; anonymous → official only. The selected
`key` (a plain catalog key or `custom:<user>:<id>`) flows unchanged into
`NewGameRequest.deck` → Stage 3's `resolve_deck`. **400 guard already covered:**
`POST /api/games` maps `resolve_custom_deck`'s `FileNotFoundError` ("Custom deck
'…' is incomplete." / "… not found") to HTTP 400, and `useGame.newGame` already
surfaces `ApiError.message` as the `error` prop rendered on the start card — so a
deck gone incomplete/deleted since load fails gracefully with a clear message, no
new code. New CSS `.deck-select` / `.deck-col-meta`. Tests:
`web/tests/newgame.test.tsx` extended (grouped optgroups + option order, sane
defaults, posts the selected custom key) — **119 web tests green**; `tsc --noEmit`
+ `vite build` clean. The backend integration anchor (a full HTTP game with a
`custom:` deck on each seat) is the Stage-3 test. Remaining: the manual UI smoke
pass on the instance players use (the maintainer owns this). **All 6 stages landed —
FEATURE COMPLETE.**

**Goal.** The start screen uses dropdowns; complete custom decks are selectable for
either seat; a game runs on them.

- Replace the two `deck-col` button columns in `NewGameScreen.tsx` with two
  `<select>` dropdowns (**You** / **Opponent**), each grouped with `<optgroup>`:
  **Official** (built-in + graduated) then **Custom** (the caller's complete decks
  only). Use `DeckChoice.kind` from Stage 3. Keep the leader/base sub-label where
  space allows (as an option title/tooltip).
- The selected `key` (a plain catalog key or `custom:<user>:<id>`) flows into the
  existing `NewGameRequest.deck` unchanged — Stage 3's `resolve_deck` handles it.
- Guard: if a chosen custom deck became incomplete/deleted since load, surface the
  400 from `POST /api/games` gracefully.

**Acceptance.** Official + complete custom decks appear grouped in both dropdowns;
starting a game with a custom deck on either side deals and plays; the manual UI
smoke pass (pick a custom deck, start, take a turn) works on the instance players use.

**Tests.** `web/tests/newgame.test.tsx` (extend) — dropdown renders grouped
official/custom, defaults sane, posts the selected key. Backend: a full HTTP game
with a `custom:` deck (covered in Stage 3) is the integration anchor.

---

## Ordering rationale

1 (images) is independent and fixes a live bug fast. 2→3 build the backend core
then expose it. 4 (make decks) precedes 5 (add cards needs a deck to add to)
precedes 6 (select decks needs complete decks to select). Every frontend stage
consumes an already-tested backend contract.
