# c24-set:02 — Combat tricks, buffs & tempo

- **Group id (paste this):** `c24-set:02`
- **Kind:** ability
- **Cards:** 1

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| C24_5 | Asajj Ventress | Unit | 4 | 2/4 | Exploit |

## Per-card analysis & acceptance criteria

### C24_5 — Asajj Ventress

**Type/Stats:** Unit, cost 4, 2/4  |  Traits: Force, Separatist, Sith

**Rules text:**

> Exploit 2
> 
> On Attack: If you've attacked with another SEPARATIST unit this phase, this unit gets +3/+0 for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

