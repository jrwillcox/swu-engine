# jabba-the-hutt:01 — Plot keyword

- **Group id (paste this):** `jabba-the-hutt:01`
- **Kind:** keyword
- **Cards:** 2

## Keyword group: **Plot**

Implement the **Plot** keyword engine-side once (Phase 2 pattern: keyword query layer / effective-stats / decision-stack as needed), with synthetic-card framework tests first. Then confirm every card below becomes playable and remove `Plot` from the Phase-2 deferred list in `CLAUDE.md`.

Note: a card may have rules text *beyond* the keyword. Where flagged 'residual text' below, the keyword unblocks the card but its ability text still needs a separate ability registration (re-run the planner after the keyword lands — it will recluster the residual text into an ability group).

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_186 | Garindan | Unit | 2 | 1/3 | Plot |
| SEC_189 | Lurking Snub Fighter | Unit | 3 | 2/3 | Plot |

## Per-card analysis & acceptance criteria

### SEC_186 — Garindan

**Type/Stats:** Unit, cost 2, 1/3  |  Traits: Underworld

**Rules text:**

> When Played: Name a card. Look at an opponent's hand and discard a card with that name from it.
> Plot (When you deploy a leader, you may play this card from your resources, paying its cost. Replace it with the top card of your deck.)

**Residual text (needs separate ability after keyword):** When Played: Name a card. Look at an opponent's hand and discard a card with that name from it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_189 — Lurking Snub Fighter

**Type/Stats:** Unit, cost 3, 2/3  |  Traits: Fighter, Underworld, Vehicle

**Rules text:**

> When Played: You may exhaust a unit.
> Plot (When you deploy a leader, you may play this card from your resources, paying its cost. Replace it with the top card of your deck.)

**Residual text (needs separate ability after keyword):** When Played: You may exhaust a unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

