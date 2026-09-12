# padme-amidala:02 — Combat tricks, buffs & tempo

- **Group id (paste this):** `padme-amidala:02`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SEC_96 | Ahsoka Tano | Unit | 3 | 2/5 |  |
| SEC_98 | Captain Typho | Unit | 4 | 4/5 | Sentinel |
| SEC_99 | Naboo Royal Starship | Unit | 4 | 2/5 | Overwhelm, Plot, Raid |
| JTL_111 | Seasoned Fleet Admiral | Unit | 2 | 1/4 | Raid |
| SEC_111 | Jar Jar Binks | Unit | 2 | 2/1 | Plot |
| SEC_116 | Nubian Star Skiff | Unit | 4 | 4/4 | Restore |
| JTL_123 | Dogfight | Event | 1 |  |  |

## Per-card analysis & acceptance criteria

### SEC_96 — Ahsoka Tano

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: Force, Jedi, Republic

**Rules text:**

> When this unit completes an attack (and survives): You may disclose CommandHeroism. If you do, attack with another unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack, disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_98 — Captain Typho

**Type/Stats:** Unit, cost 4, 4/5  |  Traits: Naboo, Republic, Trooper

**Rules text:**

> Sentinel
> When this unit is attacked: You may disclose CommandHeroism. If you do, heal 1 damage from your base.

**Mechanical analysis:** trigger archetype `static`; effect families ['heal'].

**Existing primitives that should suffice:** Heal, disclose.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_99 — Naboo Royal Starship

**Type/Stats:** Unit, cost 4, 2/5  |  Traits: Naboo, Transport, Vehicle

**Rules text:**

> Each friendly leader unit gains Raid 2 and Overwhelm.
> Plot (When you deploy a leader, you may play this card from your resources, paying its cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_111 — Seasoned Fleet Admiral

**Type/Stats:** Unit, cost 2, 1/4  |  Traits: Official, Rebel, Twi'lek

**Rules text:**

> Raid 1
> When an opponent draws 1 or more cards during the action phase: You may give an Experience token to a unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_111 — Jar Jar Binks

**Type/Stats:** Unit, cost 2, 2/1  |  Traits: Gungan, Naboo, Official, Republic

**Rules text:**

> When Played: You may give another friendly unit +2/+2 for this phase.
> Plot (When you deploy a leader, you may play this card from your resources, paying its cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SEC_116 — Nubian Star Skiff

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Naboo, Transport, Vehicle

**Rules text:**

> While you control an Official unit, this unit gains Restore 2. (When this unit attacks, heal 2 damage from your base.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_123 — Dogfight

**Type/Stats:** Event, cost 1  |  Traits: Tactic

**Rules text:**

> Attack with a unit, even if it's exhausted. That unit can't attack bases for this attack.

**Mechanical analysis:** trigger archetype `event`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

