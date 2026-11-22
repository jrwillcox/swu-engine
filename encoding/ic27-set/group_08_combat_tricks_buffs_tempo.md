# ic27-set:08 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ic27-set:08`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| IC27_1 | Darth Vader | Leader | 7 | 5/7 |  |
| IC27_2 | Rey | Leader | 5 | 3/6 |  |
| IC27_4 | Mace Windu | Leader | 6 | 4/7 | Restore |
| IC27_7 | Asajj Ventress | Leader | 6 | 5/6 | Saboteur |
| IC27_13 | Nute Gunray | Unit | 1 | 1/4 | Restore |
| IC27_21 | General Grievous | Unit | 4 | 4/5 |  |
| IC27_23 | Grand Moff Tarkin | Unit | 5 | 3/6 | Sentinel |

## Per-card analysis & acceptance criteria

### IC27_1 — Darth Vader

**Type/Stats:** Leader, cost 7, 5/7  |  Traits: Force, Imperial, Sith

**Rules text:**

> Action [1 resource, Exhaust, defeat a friendly unit]: Draw a card and heal 2 damage from your base.
> On Attack: You may defeat another friendly unit. If you do, draw a card and heal 2 damage from your base.
> Epic Action: If you control 7 or more resources, deploy this leader. (Flip him, ready him, and move him to the ground arena.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['heal', 'draw', 'defeat', 'ready_exhaust'].

**Existing primitives that should suffice:** Heal, DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_2 — Rey

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Force, Resistance

**Rules text:**

> Action [1 resource, Exhaust]: Give an Experience token to a damaged unit.
> On Attack: You may give an Experience token to a damaged unit.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_4 — Mace Windu

**Type/Stats:** Leader, cost 6, 4/7  |  Traits: Force, Jedi, Republic

**Rules text:**

> Action [1 resource, Exhaust]: Attack with a unit. It gains Restore 2 for this attack. (When it attacks, heal 2 damage from your base.)
> Restore 2
> When Deployed: Resource the top card of your deck.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['keyword_grant', 'ramp', 'attack_grant'].

**Existing primitives that should suffice:** GrantKeyword, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_7 — Asajj Ventress

**Type/Stats:** Leader, cost 6, 5/6  |  Traits: Force, Separatist, Sith

**Rules text:**

> Action [Exhaust]: Attack with a unit. After completing this attack, if the attacker survived, you may ready a resource.
> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> On Attack: You may ready a resource.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust', 'ramp', 'attack_grant'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_13 — Nute Gunray

**Type/Stats:** Unit, cost 1, 1/4  |  Traits: Official, Separatist

**Rules text:**

> Each other friendly Separatist unit gains Restore 1. (When it attacks, heal 1 damage from your base.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_21 — General Grievous

**Type/Stats:** Unit, cost 4, 4/5  |  Traits: Official, Separatist

**Rules text:**

> When you play an upgrade on this unit: Choose one that hasn't been chosen this phase:
> Give an Experience token to him.
> Heal 3 damage from your base.
> Draw a card.

**Mechanical analysis:** trigger archetype `static`; effect families ['heal', 'draw', 'token'].

**Existing primitives that should suffice:** Heal, DrawCards, GiveToken, push_modal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_23 — Grand Moff Tarkin

**Type/Stats:** Unit, cost 5, 3/6  |  Traits: Imperial, Official

**Rules text:**

> Each friendly unit with Sentinel gets +1/+1.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

