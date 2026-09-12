# mv26-set:01 — Card advantage & disruption

- **Group id (paste this):** `mv26-set:01`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| MV26_2 | Razor Crest | Unit | 4 | 3/5 | Saboteur |

## Per-card analysis & acceptance criteria

### MV26_2 — Razor Crest

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Mandalorian, Transport, Vehicle

**Rules text:**

> Saboteur 
> On Attack: You may discard a card from your hand. If you do, this unit gets +2/+0 for this attack.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['discard', 'stat_buff'].

**Existing primitives that should suffice:** DiscardFromHand, ModifyStats/StatBonus, play-from-hand-act-on-result.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

