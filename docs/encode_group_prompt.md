# Standing encoding prompt

Keep this file handy. To encode one group, paste its **group id** into the
placeholder at the very bottom (`GROUP TO ENCODE:`) and run a fresh Claude Code
session in `swu-game/` with this file as the prompt. One group per session.

---

You are encoding one group of cards for the SWU game engine. Work **only** on the
group whose id is given at the bottom of this prompt. Be surgical: the engine is
frozen except for the genuinely engine-level mechanics noted below.

## 1. Read the context

1. Read `docs/encoding_guide.md` (the recipe) and `docs/engine_seams.md` (patterns,
   decision kinds, engine internals and the escalation rule).
2. Resolve the group id `<slug>:NN` to its spec file: it is
   `encoding/<slug>/group_NN_*.md`. Read that file completely. It lists every
   card with full rules text, a mechanical analysis, the existing primitives that
   should suffice, any suspected new primitive, residual-text notes, and per-card
   acceptance criteria. Also skim `encoding/<slug>/MANIFEST.md` for dependencies —
   **if this group lists "Depends on", confirm those groups are already done**
   (the verifier will not let the deck graduate otherwise).

The spec tells you the group **kind**. Follow the matching path below.

## 2. If this is a KEYWORD group

The cards are blocked *only* by a deferred keyword. Do **not** encode them one by
one — implement the keyword **once, engine-side**, following the Phase 2 pattern.

1. Add the keyword to the `Keyword` enum (`src/swu/engine/keywords.py`) and wire
   whatever layer it needs: the keyword query layer (`has_keyword`/`keyword_value`),
   the effective-stats layer (`compute_power`), enter-play/attack triggers
   (`keyword_triggers.py`), and/or the pending-decision stack, as was done for
   Sentinel, Ambush and Exploit. A new decision kind follows "Adding a decision
   kind" in `docs/engine_seams.md`.
2. **Write synthetic-card framework tests first** (in `tests/test_keywords.py` or
   a new `tests/test_<keyword>.py`): construct a minimal state exercising the
   keyword via the public `legal_actions`/`apply` interface, independent of any
   specific card.
3. Then confirm **every card listed in the spec** becomes playable. A keyword
   card may have **residual ability text** (flagged in the spec); the keyword
   unblocks the card, but the residual text still needs a separate ability
   registration — note which cards still need that (a later ability group will
   pick them up after a planner re-run; do not encode the residual text here
   unless it is trivial and clearly in scope).
4. **Record it**: add the keyword to the list in `docs/engine_seams.md`, and a note on
   the seam to `docs/history/seams_log.md`.

## 3. If this is an ABILITY group

Encode each card as **declarative ability definitions** per the Phase 3 framework
in `src/swu/cards/<set>/abilities.py` (create the set module if it does not exist,
mirroring `src/swu/cards/sor/abilities.py`, and ensure it is imported so the
`@card_ability` decorators run).

- Compose **existing primitives** (the spec lists the ones that should suffice).
- Use the `CustomEffect` / `escape_hatch=True` hatch **only** when the text is
  genuinely irreducible — and call out each escape-hatch use prominently in your
  report.
- Write **one focused test per card**, named for the card (a `Test<CardName>`
  class in `tests/test_<set>_cards.py`), asserting behaviour through the public
  engine interfaces (`legal_actions`/`apply`) — not internal state pokes.
  **Put each card's number in its test method names** (e.g.
  `def test_shd_64_moves_upgrade(...)`). The verifier's focused-test gate
  (`verify_encoding.py --group NN`) builds its `pytest -k` expression from the
  group's **card numbers**, not the class names — so a `Test<CardName>` class
  whose method names omit the number selects **zero** tests and reports a
  spurious `FAIL` even though the tests pass. Embedding the number (set+number is
  clearest) makes the gate find them.

## 4. New primitives — the escalation rule

If a card needs a primitive that does not exist yet:

- A **small, clearly-scoped** new primitive (a new effect dataclass + its resolver
  arm, or a self-contained decision kind) may be added inline **with
  synthetic-card tests**, following the existing primitive patterns.
- But if it would touch **core resolution**, the **trigger/decision machinery**,
  or needs a **replacement-effect system** — **STOP**. Do not jam it into a card
  batch. Implement the rest of the group (or report that the whole group is
  blocked), and flag the primitive clearly for a dedicated framework session.
  This protects the frozen-engine guarantees. The spec already names the suspected
  new primitive for groups of kind "New primitive: …" — those are expected to be
  escalations, often one card each.

## 5. Run the checks

In `swu-game/`, using the project venv (`.venv/Scripts/python.exe`):

```bash
# the group's new tests
.venv/Scripts/python.exe -m pytest tests/test_<file>.py -q -k "<CardOrKeyword>"
# the fast suite (must stay green)
.venv/Scripts/python.exe -m pytest -q
# re-run the deck audit / progress
.venv/Scripts/python.exe scripts/verify_encoding.py <slug> --group NN
```

Fix any regression before reporting.

## 6. Report (concise, for human review)

- **Per card:** the definition approach (which primitives/spec), the test result,
  and — **prominently** — any escape-hatch or new-primitive use.
- The deck's **new readiness** (N/M cards playable) from the verifier.
- End with: the **exact verifier command** to run, and the **next group id** from
  the MANIFEST (the lowest-seq group not yet complete whose dependencies are met).

---

GROUP TO ENCODE: <paste group id here>
