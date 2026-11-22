# ic27-set:11 — Combat tricks, buffs & tempo

- **Group id (paste this):** `ic27-set:11`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| IC27_77 | Mon Mothma | Unit | 4 | 3/6 | Overwhelm |
| IC27_79 | Qui-Gon Jinn | Unit | 5 | 5/5 | Sentinel |
| IC27_81 | Mace Windu | Unit | 6 | 5/5 | Ambush |
| IC27_83 | Padmé Amidala | Unit | 8 | 5/7 | Sentinel |
| IC27_85 | Inspiring Mentor | Upgrade | 2 |  |  |
| IC27_86 | Enfys Nest | Unit | 5 | 4/6 | Ambush, Overwhelm |
| IC27_89 | Maz Kanata | Unit | 2 | 2/1 | Hidden |

## Per-card analysis & acceptance criteria

### IC27_77 — Mon Mothma

**Type/Stats:** Unit, cost 4, 3/6  |  Traits: Official, Rebel

**Rules text:**

> When Played: You may attack with another unit, even if it's exhausted. For this attack, it gains Overwhelm and can't attack bases.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['keyword_grant', 'attack_grant'].

**Existing primitives that should suffice:** GrantKeyword, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_79 — Qui-Gon Jinn

**Type/Stats:** Unit, cost 5, 5/5  |  Traits: Force, Jedi, Republic

**Rules text:**

> Sentinel (Enemy units in this arena must attack a Sentinel when they attack you.)
> When Played: Give another friendly unit +2/+2 for this phase.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_81 — Mace Windu

**Type/Stats:** Unit, cost 6, 5/5  |  Traits: Force, Jedi, Republic

**Rules text:**

> Ambush
> On Attack: Give an Experience token to this unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_83 — Padmé Amidala

**Type/Stats:** Unit, cost 8, 5/7  |  Traits: Naboo, Official, Republic

**Rules text:**

> Sentinel (Enemy units in this arena must attack a Sentinel when they attack you.)
> Other friendly Heroism units get +3/+3.

**Mechanical analysis:** trigger archetype `static`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_85 — Inspiring Mentor

**Type/Stats:** Upgrade, cost 2  |  Traits: Innate

**Rules text:**

> Attach to a non-Vehicle unit.
> Attached unit gains: “On Attack/When Defeated: Give an Experience token to another friendly unit.”

**Mechanical analysis:** trigger archetype `when_defeated`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_86 — Enfys Nest

**Type/Stats:** Unit, cost 5, 4/6  |  Traits: Underworld

**Rules text:**

> Ambush (When you play this unit, she may attack an enemy unit.)
> While attacking a unit that costs 3 or less, this unit gets +2/+0 and gains Overwhelm.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'keyword_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_89 — Maz Kanata

**Type/Stats:** Unit, cost 2, 2/1  |  Traits: Underworld

**Rules text:**

> Hidden (This unit can't be attacked if she was played this phase.)
> When you resource a card (including during the regroup phase): Give an Experience token to this unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['token', 'ramp'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

