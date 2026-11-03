# Reprint-duplicate sweep — staged plan

**Goal.** Many cards in `data/swu.db` are *exact reprints* of another card: same
printed face (name, subtitle, type, cost, stats, rules text, deploy box), different
`set_code`/`card_number` and art. Examples: Rio Durant *Beckett's Right Hands*
(`LAW_93` = `P26_2`); Maul *Shadow Collective Visionary* (`J24_4` = `P25_155` =
`P25_165` = `SHD_90`). We want every reprint to be as playable as its twin.

> Note: a shared **name** is NOT enough — "Maul" is four different cards (Leader
> *A Rival in Darkness* `TWI_9`, Unit *Shadow Collective Visionary*, Unit *Master
> of the Shadow Collective* `LAW_54`, …). Duplicates must match the **whole printed
> face**, and members can number 2–5, not just pairs.

## Why this is cheap (the mechanism)

Card abilities are registered in `src/swu/abilities/registry.py::_REGISTRY`, keyed
by `(set_code, card_number)` via the `@card_ability(SET, NUM)` decorator. At
runtime **everything** resolves abilities through
`get_abilities(set_code, card_number)`:

- `src/swu/abilities/resolver.py` (trigger collection, effect resolution, legal
  actions) — every site keys off the instance's own `card_def.set_code/card_number`.
- `src/swu/cards/keyword_sanitizer.py` (`_conditional_self_grant_keywords`,
  `_triggered_self_grant_keywords`) — strips mis-tagged printed keywords **iff** a
  matching self-grant ability is registered for that `(set, number)`.

A reprint already carries correct **stats, keywords, traits, aspects, deploy
thresholds** (they come from its own DB row). The *only* thing it lacks is an
entry in `_REGISTRY`. So we do **not** re-write any card logic — we **alias** the
reprint's registry key to its implemented twin's specs. Because the sanitizer also
reads `get_abilities`, an aliased reprint's mis-tagged keywords get stripped
correctly too, provided the alias is applied at import time (before any card is
hydrated by `repository._hydrate`).

Aliasing is sound: name-based conditions (`ATTACHED_HOST_NAMED`,
`CONTROLLER_CONTROLS_NAMED`, self-name checks) still match (same name); the
`trigger_option` decision addresses abilities by the source's own
`(set, number, ability_idx)`, which now resolves to the aliased specs.

## The identity key

Two rows are the same printed face iff these fields match (whitespace-normalised,
`\xa0` → space; **exclude** token types via `audit_coverage.TOKEN_TYPES`):

```
name, subtitle, type, cost, power, hp, upgrade_power, upgrade_hp,
norm(text), norm(deploy_box), norm(epic_action)
```

## Current sizing (re-run to refresh — DB may change)

- **208** reprint groups (>1 member), **516** members total.
- **38 mirror-gap members** — unregistered, but a twin in the group **is**
  registered → Stage 2 aliases them for free. (Twins span SOR/SHD/TWI/JTL/LOF/
  SEC/LAW; reprints live in promo/starter sets P25/P26/J24/J25/C24/C25/C26/
  JTLP/LOFP/LAWP/SECP and a few cross-shipped-set reprints.)
- **32 groups** — 0 registered members, no functional text → already playable
  (vanilla / keyword-complete). Stage 3 just verifies.
- **150 groups (372 members)** — 0 registered members **with** functional text →
  genuine encodes. Stage 4, iterative. This bucket **overlaps the normal
  deck-encoding backlog** (most are shipped-set cards never pulled into an encoded
  deck), so it is large; treat it as ongoing, not a blocker.

---

## Stage 1 — Detection tooling + the alias mechanism (foundation)

**Deliverables**

1. `scripts/find_reprints.py` — re-runnable, offline. Reuses
   `scripts.audit_coverage` (`load_cards`, `_load_registry`, `classify`,
   `is_playable`, `TOKEN_TYPES`) so its verdicts agree with every other tool.
   - Groups all non-token rows by the identity key above.
   - For each multi-member group, classifies every member with `audit.classify`
     and buckets the group:
     - **`mirror`** — ≥1 member registered (`implemented`/`escape-hatch`) AND ≥1
       not: emit each gap member → chosen canonical (prefer a shipped-set,
       non-escape-hatch member; deterministic tiebreak by set then number).
     - **`already_playable`** — 0 registered, every member `is_playable`
       (vanilla / keyword-complete).
     - **`keyword_deferred`** — 0 registered, any member `keyword-deferred`
       (needs an engine keyword, not a per-card encode; usually already done
       engine-side — verify in Stage 3).
     - **`needs_encoding`** — 0 registered, ≥1 member `text-bearing`.
   - Prints a human summary and writes `docs/reprints_worklist.json` (buckets +
     per-group members with labels). A `--check` flag exits non-zero if any
     `mirror` gap is still un-aliased (for CI / Stage-2 acceptance).
2. `src/swu/cards/reprints.py`:
   - `REPRINT_ALIASES: dict[tuple[str, str], tuple[str, str]]` — `reprint → canonical`
     (empty in this stage).
   - `_face_key(row) -> tuple` and a DB reader, OR import the shared identity-key
     helper used by `find_reprints.py` (put the helper in ONE place — e.g.
     `reprints.py` — and have the script import it, so they can never diverge).
   - `apply_reprint_aliases()`: for each `(reprint, canonical)`, **assert the two
     DB faces are identical** (guard against future data drift — raise a clear
     error naming both keys if not), then set
     `_REGISTRY[reprint] = _REGISTRY[canonical]` and, if the canonical is in
     `_ESCAPE_HATCH`, add the reprint too. Assert the canonical is actually
     registered (fail loud if a canonical was renumbered away).
3. Wire it: add `import swu.cards.reprints` **last** in
   `src/swu/cards/__init__.py`, and call `apply_reprint_aliases()` at import
   (after all set modules have registered).
4. `tests/test_reprints.py`: with the (empty) table, `apply_reprint_aliases()` is
   a no-op; `find_reprints.py --check` passes; the identity-key helper round-trips
   the two worked examples (`LAW_93`/`P26_2` group; the Maul *Shadow Collective
   Visionary* group has ≥2 members).

**Acceptance:** `python scripts/find_reprints.py` runs, writes the worklist, and
the fast test suite stays green. No behaviour change yet (empty alias table).

**Ready-made prompt**

```
Read docs/reprint_duplicates_plan.md (Stage 1) and docs/encoding_guide.md.
Implement Stage 1 ONLY:

1. Create scripts/find_reprints.py — a re-runnable, offline reprint detector built
   ON TOP of scripts/audit_coverage.py (reuse load_cards, _load_registry, classify,
   is_playable, TOKEN_TYPES so verdicts agree with the rest of the toolchain).
   Group all non-token DB rows by the printed-face identity key defined in the plan
   (whitespace-normalised, \xa0 -> space). For each group with >1 member, classify
   every member and bucket the group into: mirror / already_playable /
   keyword_deferred / needs_encoding (definitions in the plan). For the `mirror`
   bucket, map each unregistered gap member to a canonical (prefer a shipped-set,
   non-escape-hatch member; deterministic tiebreak). Print a summary and write
   docs/reprints_worklist.json. Add a --check flag that exits non-zero if any
   `mirror` gap is not yet present in REPRINT_ALIASES.

2. Create src/swu/cards/reprints.py with an EMPTY REPRINT_ALIASES dict, the
   canonical identity-key helper (imported by find_reprints.py so the two never
   diverge), and apply_reprint_aliases() which — for each reprint->canonical —
   asserts the two DB faces are identical and the canonical is registered, then
   copies _REGISTRY[canonical] (and _ESCAPE_HATCH membership) onto the reprint key.

3. Wire `import swu.cards.reprints` LAST in src/swu/cards/__init__.py and invoke
   apply_reprint_aliases() at import (after all set modules load).

4. Add tests/test_reprints.py: empty table is a no-op; --check passes; the identity
   helper correctly groups LAW_93 with P26_2 and finds the Maul "Shadow Collective
   Visionary" group.

Do NOT populate REPRINT_ALIASES yet. Run: python scripts/find_reprints.py and the
fast test tier. Report the bucket counts.
```

---

## Stage 2 — Mirror the free wins (the 38 mirror-gaps)

**What.** Populate `REPRINT_ALIASES` from the worklist's `mirror` bucket. This
makes every reprint whose twin is already implemented fully playable, at ~zero
risk (pure data + a face-identity guard).

**Deliverables**

- `REPRINT_ALIASES` filled with every `mirror` entry from
  `docs/reprints_worklist.json` (regenerate first).
- `tests/test_reprints.py` extended: for every alias,
  `get_abilities(reprint) is get_abilities(canonical)` (same list object), faces
  match, and `audit.classify(reprint, …)` is `implemented`/`escape-hatch` (i.e.
  now playable). Assert `find_reprints.py --check` passes.
- Update `CLAUDE.md` (a short "Reprint aliasing" note) and add a memory entry.

**Acceptance:** `python scripts/find_reprints.py --check` exits 0 (no mirror-gaps
left); fast + medium tiers green; `audit_coverage` playable count rises by the
number of aliased members.

**Ready-made prompt**

```
Read docs/reprint_duplicates_plan.md (Stage 2). Stage 1 tooling exists. Do Stage 2:

1. Run `python scripts/find_reprints.py` to regenerate docs/reprints_worklist.json.
2. Populate REPRINT_ALIASES in src/swu/cards/reprints.py with EVERY entry in the
   worklist's `mirror` bucket (reprint -> canonical). Do not hand-edit canonicals;
   take them from the worklist.
3. Extend tests/test_reprints.py: for each alias, assert get_abilities(reprint) is
   the canonical's list, the DB faces are identical, and audit.classify now labels
   the reprint implemented/escape-hatch. Assert `find_reprints.py --check` exits 0.
4. Run the fast tier, then the medium tier (soak). Confirm audit_coverage's playable
   total went up by the number of aliased cards.
5. Add a one-line "Reprint aliasing" note to CLAUDE.md and record it in memory.

Report: how many aliases added, and the before/after audit playable counts.
```

---

## Stage 3 — Verify the already-playable / keyword-deferred groups

**What.** The `already_playable` (32) and `keyword_deferred` groups need **no
per-card code** — the keyword/vanilla engine already handles them. This stage
*proves* that and catches any misclassification (e.g. a reprint of a card that
relies on a Phase-7 keyword the engine now supports — Smuggle/Plot/Hidden/Piloting
— which should read as playable, not a gap).

**Deliverables**

- A test (or an assertion mode in `find_reprints.py`) that every member of these
  buckets satisfies `audit.is_playable(classify(...))` OR, for `keyword_deferred`,
  that its keyword is in the "implemented engine-side" set
  (`audit_coverage.PHASE2_KEYWORDS` + the Phase-7 list). Any member that fails is
  reported as a real gap and moved to the Stage-4 worklist.
- No `REPRINT_ALIASES` changes expected (these need no registration). If a
  keyword-deferred reprint turns out to have a registered twin after all, it moves
  to Stage 2's mirror bucket instead.

**Acceptance:** the verification passes with an empty "unexpected gap" list, or the
exceptions are re-bucketed and documented.

**Ready-made prompt**

```
Read docs/reprint_duplicates_plan.md (Stage 3). Verify the already_playable and
keyword_deferred reprint buckets from docs/reprints_worklist.json need no work:

1. For every member of both buckets, confirm audit_coverage.classify labels it
   playable (vanilla/keyword-complete/implemented) OR — for keyword-deferred — that
   its keyword is implemented engine-side (PHASE2_KEYWORDS + the Phase-7 keywords:
   Smuggle, Plot, Hidden, Piloting, Coordinate, Bounty-as-template, Exploit).
2. Add this as a regression check (a test, or a `find_reprints.py --verify-playable`
   mode). List any member that is NOT actually playable.
3. Re-bucket exceptions: if it has a registered twin -> add to REPRINT_ALIASES
   (Stage 2 style) with a test; otherwise add it to the Stage-4 needs_encoding list.

Report the exceptions found (expect few or none) and how each was resolved.
```

---

## Stage 4 — Encode the genuine duplicate groups (iterative)

**What.** The `needs_encoding` bucket (≈150 groups): no member is implemented and
the card has functional text. For each group, encode **one** canonical member with
the standard per-card recipe (docs/encoding_guide.md),
then **alias the siblings** into `REPRINT_ALIASES`. So each encode makes the whole
group playable.

**Scope reality.** This overlaps the normal deck-encoding backlog and is large. Do
it in **small batches** (5–8 groups per session), prioritising groups whose
canonical is a **shipped-set** card (SOR/SHD/TWI/JTL/LOF/SEC/LAW) — those are the
ones most likely to appear in real decks. Pure promo-only groups can be deferred.
Do NOT batch escalations (new engine primitives) with ordinary cards — if a group
needs a new primitive, STOP and flag it for its own session, exactly as
`plan_encoding.py` does. Prefer picking canonicals that are plain (no new primitive)
so the batch stays low-risk.

**Per-group loop**

1. Read the canonical's DB text (Step 1). Choose the ability spec (Step 2).
2. Register `@card_ability(canonical_set, canonical_num)` in that set's
   `abilities.py` (Steps 3–10). Reuse existing primitives; escalate if needed.
3. Add `tests/test_<set>_cards.py::Test<Card>` with the card number in each method
   name (the verifier's `-k` gate keys off numbers).
4. Add every sibling to `REPRINT_ALIASES` (canonical → sibling), with the
   face-identity guard from Stage 1 covering them.
5. `find_reprints.py` should now bucket that group as fully covered.

**Acceptance (per batch):** the batch's cards audit as `implemented`; siblings audit
as playable via the alias; fast tier green; `find_reprints.py` shows the batch's
groups resolved.

**Ready-made prompt**

```
Read docs/reprint_duplicates_plan.md (Stage 4) and the recipe in
docs/encoding_guide.md. Work ONE batch of the needs_encoding reprint bucket.

1. Run `python scripts/find_reprints.py` to refresh docs/reprints_worklist.json.
   From the needs_encoding bucket pick the next 5-8 groups whose CANONICAL member
   is in a shipped set (SOR/SHD/TWI/JTL/LOF/SEC/LAW) and looks implementable with
   EXISTING primitives (skip anything that smells like a new engine primitive —
   flag those for their own session, do not encode them here).
2. For each chosen group: encode the canonical member per the docs/encoding_guide.md recipe
   (register in the correct src/swu/cards/<set>/abilities.py, reuse primitives),
   add a focused test with the card number in each method name.
3. Add every sibling of each encoded group to REPRINT_ALIASES in
   src/swu/cards/reprints.py (guarded face-identity aliasing from Stage 1).
4. Run: pytest the new tests, then the fast tier. Run `python scripts/find_reprints.py`
   and confirm the batch's groups are now fully covered (no members text-bearing).
5. Record what was done in memory and, if a new primitive was needed anywhere,
   STOP and report it as a flagged escalation instead of encoding it.

List the groups done, the primitives reused, and any escalations flagged.
```

---

## Notes / guardrails

- **Face-identity guard is mandatory.** If a future DB refresh changes one member's
  text but not another's, `apply_reprint_aliases()` must raise rather than silently
  alias a now-different card. Keep the guard strict (compare the same normalised
  fields the identity key uses).
- **Canonical choice is deterministic and shipped-set-preferred**, so re-running
  the detector never churns the alias table.
- **Tokens excluded** (`audit_coverage.TOKEN_TYPES`) — a Leader and its same-numbered
  Token are not reprints of each other (see "Gotchas" in docs/encoding_guide.md).
- Re-run `python scripts/find_reprints.py` at the top of every stage — the DB and
  the registry both move as decks graduate.
