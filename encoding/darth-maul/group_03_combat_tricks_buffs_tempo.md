# darth-maul:03 — Combat tricks, buffs & tempo

- **Group id (paste this):** `darth-maul:03`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_63 | Oggdo Bogdo | Unit | 3 | 5/5 |  |
| LOF_140 | Darth Maul's Lightsaber | Upgrade | 3 |  | Overwhelm |
| LOF_233 | Scimitar | Unit | 4 | 3/4 |  |

## Per-card analysis & acceptance criteria

### LOF_63 — Oggdo Bogdo

**Type/Stats:** Unit, cost 3, 5/5  |  Traits: Creature

**Rules text:**

> This unit can't attack unless it's damaged.
> When this unit attacks and defeats a unit: Heal 2 damage from this unit.

**Mechanical analysis:** trigger archetype `on_defeats`; effect families ['heal'].

**Existing primitives that should suffice:** Heal, push_say_no.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_140 — Darth Maul's Lightsaber

**Type/Stats:** Upgrade, cost 3  |  Traits: Item, Lightsaber, Weapon

**Rules text:**

> Attach to a friendly non-Vehicle unit.
> When Played: If attached unit is Darth Maul, you may attack with him. For this attack, he gains Overwhelm and can't attack bases.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['keyword_grant', 'attack_grant'].

**Existing primitives that should suffice:** GrantKeyword, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_233 — Scimitar

**Type/Stats:** Unit, cost 4, 3/4  |  Traits: Sith, Transport, Vehicle

**Rules text:**

> While this unit is damaged, it gets +3/+0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

