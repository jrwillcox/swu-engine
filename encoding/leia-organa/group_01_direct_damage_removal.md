# leia-organa:01 — Direct damage & removal

- **Group id (paste this):** `leia-organa:01`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_41 | Nothing Left to Fear | Event | 5 |  |  |
| LAW_45 | Zeb Orellios | Unit | 5 | 4/4 | Sentinel |
| JTL_250 | Sabine's Masterpiece | Unit | 3 | 3/3 |  |

## Per-card analysis & acceptance criteria

### LAW_41 — Nothing Left to Fear

**Type/Stats:** Event, cost 5  |  Traits: Innate

**Rules text:**

> Choose a friendly unit and give it +2/+2 for this phase. Then, you may defeat a non-leader unit with power equal to or less than the chosen unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['defeat', 'stat_buff'].

**Existing primitives that should suffice:** DefeatUnit/Upgrade, ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_45 — Zeb Orellios

**Type/Stats:** Unit, cost 5, 4/4  |  Traits: Rebel, Spectre

**Rules text:**

> Sentinel
> When Played: You may deal 3 damage to a ground unit. If you control a Command or Cunning unit, you may deal 5 damage to a ground unit instead.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_250 — Sabine's Masterpiece

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Fighter, Rebel, Spectre, Vehicle

**Rules text:**

> On Attack: If you control a:
> <bullet>Vigilance unit, heal 2 damage from a base.
> Command unit, give an Experience token to a unit.
> Aggression unit, deal 1 damage to a unit or a base.
> Cunning unit, exhaust or ready a resource.</bullet>

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'heal', 'token', 'ready_exhaust', 'ramp'].

**Existing primitives that should suffice:** DealDamage, Heal, GiveToken, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

