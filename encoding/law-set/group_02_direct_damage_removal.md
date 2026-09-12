# law-set:02 — Direct damage & removal

- **Group id (paste this):** `law-set:02`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAW_47 | Baze Malbus | Unit | 7 | 6/8 | Sentinel |
| LAW_51 | Beilert Valance | Unit | 5 | 3/6 |  |
| LAW_56 | Cassian Andor | Unit | 4 | 4/4 |  |
| LAW_58 | Honor-Bound Partisan | Unit | 2 | 2/2 |  |
| LAW_62 | Defiant Hammerhead | Unit | 6 | 6/6 |  |
| LAW_64 | Zuckuss | Unit | 4 | 3/5 | Saboteur |
| LAW_76 | Vult Skerris's Defender | Unit | 3 | 3/3 |  |

## Per-card analysis & acceptance criteria

### LAW_47 — Baze Malbus

**Type/Stats:** Unit, cost 7, 6/8  |  Traits: Rebel

**Rules text:**

> Sentinel
> When 1 or more damage is healed from this unit: You may deal that much damage to a unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_51 — Beilert Valance

**Type/Stats:** Unit, cost 5, 3/6  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> On Attack: Draw a card. You may deal damage to a ground unit equal to the number of cards you've drawn this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'draw'].

**Existing primitives that should suffice:** DealDamage, DrawCards, scaling-magnitude.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_56 — Cassian Andor

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Rebel

**Rules text:**

> When a friendly unit's attack ends: If the defending unit was defeated, deal 2 damage to a base.

**Mechanical analysis:** trigger archetype `static`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_58 — Honor-Bound Partisan

**Type/Stats:** Unit, cost 2, 2/2  |  Traits: Rebel, Twi'lek

**Rules text:**

> When Played: Deal 1 damage to a base.
> When Defeated: The next unit you play this phase costs 1 resource less.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'ramp'].

**Existing primitives that should suffice:** DealDamage, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_62 — Defiant Hammerhead

**Type/Stats:** Unit, cost 6, 6/6  |  Traits: Capital Ship, Rebel, Vehicle

**Rules text:**

> On Attack: If this unit is attacking a unit, you may give this unit +4/+0 for this attack. If you do, defeat this unit after completing this attack.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['defeat', 'stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_64 — Zuckuss

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> Saboteur
> On Attack: If you control another Bounty Hunter unit, you may deal damage equal to this unit's power to a ground unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAW_76 — Vult Skerris's Defender

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Fighter, Imperial, Vehicle

**Rules text:**

> When Played: If you discarded a card from your hand or deck this phase, give a Shield token to this unit.
> On Attack: You may deal 1 damage to a space unit and exhaust it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage', 'token', 'ready_exhaust'].

**Existing primitives that should suffice:** DealDamage, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

