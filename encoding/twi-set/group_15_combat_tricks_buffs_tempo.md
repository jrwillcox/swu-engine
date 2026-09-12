# twi-set:15 — Combat tricks, buffs & tempo

- **Group id (paste this):** `twi-set:15`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| TWI_119 | Nameless Valor | Upgrade | 1 |  | Overwhelm |
| TWI_120 | Strategic Acumen | Upgrade | 1 |  |  |
| TWI_122 | Squad Support | Upgrade | 3 |  |  |
| TWI_129 | In Defense of Kamino | Event | 4 |  | Restore |
| TWI_130 | Bo-Katan Kryze | Unit | 2 | 2/3 | Overwhelm, Saboteur |
| TWI_134 | Asajj Ventress | Unit | 4 | 2/4 | Exploit |
| TWI_137 | Savage Opress | Unit | 7 | 7/7 |  |

## Per-card analysis & acceptance criteria

### TWI_119 — Nameless Valor

**Type/Stats:** Upgrade, cost 1  |  Traits: Learned

**Rules text:**

> Attach to a token unit.
> Attached unit gains Overwhelm. (When attacking an enemy unit, deal excess damage to the opponent's base.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_120 — Strategic Acumen

**Type/Stats:** Upgrade, cost 1  |  Traits: Learned

**Rules text:**

> Attached unit gains: “Action [Exhaust]: Play a unit from your hand. It costs 1 resource less.”

**Mechanical analysis:** trigger archetype `activated`; effect families ['ramp'].

**Existing primitives that should suffice:** push_play_from_hand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_122 — Squad Support

**Type/Stats:** Upgrade, cost 3  |  Traits: Learned

**Rules text:**

> Attach to a non-leader unit.
> Attached unit gains: “This unit gets +1/+1 for each Trooper unit you control.”

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_129 — In Defense of Kamino

**Type/Stats:** Event, cost 4  |  Traits: Republic

**Rules text:**

> For this phase, each friendly Republic unit gains Restore 2 and: “When Defeated: Create a Clone Trooper token.”

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_130 — Bo-Katan Kryze

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Mandalorian, Trooper

**Rules text:**

> While you control another Mandalorian unit, this unit gains Overwhelm and Saboteur.
> While you control another Trooper unit, this unit gets +1/+0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'keyword_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_134 — Asajj Ventress

**Type/Stats:** Unit, cost 4, 2/4  |  Traits: Force, Separatist, Sith

**Rules text:**

> Exploit 2 (While playing this card, defeat up to 2 units you control. This card costs 2 resources less for each unit defeated this way.)
> On Attack: If you've attacked with another Separatist unit this phase, this unit gets +3/+0 for this phase.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### TWI_137 — Savage Opress

**Type/Stats:** Unit, cost 7, 7/7  |  Traits: Force, Night, Underworld

**Rules text:**

> When Played: If you control fewer units (including this one) than an opponent, ready this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

