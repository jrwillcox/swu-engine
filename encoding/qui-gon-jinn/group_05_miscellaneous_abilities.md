# qui-gon-jinn:05 — Miscellaneous abilities

> ✅ **COMPLETE (2026-06-30) — both cards implemented, group done (2/2).** This is
> a planner *input* spec describing the original gap; it is NOT rewritten when the
> work lands, so do not read it as an open to-do. Authoritative status:
> `verify_encoding.py qui-gon-jinn` reports **52/52, all groups done**. Both cards
> below are registered in `src/swu/cards/lof/abilities.py`
> (`@card_ability("LOF", "100")` Kelleran Beq, `@card_ability("LOF", "197")`
> Aethersprite) with tests in `tests/test_lof_cards.py` (`TestKelleranBeq`,
> `TestQuiGonJinnsAethersprite`). LOF_197's duplicate-next-WhenPlayed framework
> (`arm_when_played_redo` / `when_played_redo_charges`) landed in its dedicated
> session — it is **not** escalated/unregistered.

- **Group id (paste this):** `qui-gon-jinn:05`
- **Kind:** ability
- **Cards:** 2

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_100 | Kelleran Beq | Unit | 7 | 7/7 |  |
| LOF_197 | Qui-Gon Jinn's Aethersprite | Unit | 5 | 3/6 |  |

## Per-card analysis & acceptance criteria

### LOF_100 — Kelleran Beq

**Type/Stats:** Unit, cost 7, 7/7  |  Traits: Force, Jedi, Republic

**Rules text:**

> When Played: Search the top 7 cards of your deck for a unit, reveal it, and play it. It costs 3 resources less. (Put the other cards on the bottom of your deck in a random order.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_197 — Qui-Gon Jinn's Aethersprite

**Type/Stats:** Unit, cost 5, 3/6  |  Traits: Fighter, Jedi, Republic, Vehicle

**Rules text:**

> On Attack: The next time you use a “When Played” ability this phase, you may use that ability again.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

