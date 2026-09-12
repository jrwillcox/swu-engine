# lof-set:08 — Combat tricks, buffs & tempo

- **Group id (paste this):** `lof-set:08`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_4 | Kanan Jarrus | Leader | 6 | 3/6 | Shielded |
| LOF_5 | Morgan Elsbeth | Leader | 5 | 3/6 |  |
| LOF_6 | Supreme Leader Snoke | Leader | 6 | 4/7 |  |
| LOF_7 | Avar Kriss | Leader | 9 | 4/10 | Overwhelm |
| LOF_8 | Obi-Wan Kenobi | Leader | 5 | 3/6 |  |
| LOF_13 | Barriss Offee | Leader | 6 | 4/7 |  |
| LOF_14 | Grand Inquisitor | Leader | 5 | 3/5 | Shielded |

## Per-card analysis & acceptance criteria

### LOF_4 — Kanan Jarrus

**Type/Stats:** Leader, cost 6, 3/6  |  Traits: Force, Jedi, Rebel, Spectre

**Rules text:**

> Action [1 resource, Exhaust]: Give a Shield token to a Creature or Spectre unit.
> Shielded (When you deploy this leader, give a Shield token to him.)
> While you control another Creature or Spectre unit, this unit gets +2/+2.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['token', 'stat_buff'].

**Existing primitives that should suffice:** GiveToken, ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_5 — Morgan Elsbeth

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Force, Imperial, Night

**Rules text:**

> Action [Exhaust]: Choose a friendly unit that attacked this phase. Play a unit from your hand that shares a keyword with the chosen unit. It costs 1 resource less.
> On Attack: The next unit you play this phase costs 1 resource less if it shares a keyword with a friendly unit.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ramp'].

**Existing primitives that should suffice:** push_play_from_hand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_6 — Supreme Leader Snoke

**Type/Stats:** Leader, cost 6, 4/7  |  Traits: First Order, Force, Official

**Rules text:**

> Action [1 resource, Exhaust]: Give an Experience token to the unit with the most power among friendly Villainy units. (If multiple units are tied, choose one.)
> On Attack: Give an Experience token to the unit with the most power among friendly Villainy units.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_7 — Avar Kriss

**Type/Stats:** Leader, cost 9, 4/10  |  Traits: Force, Jedi, Republic

**Rules text:**

> Action [Exhaust]: The Force is with you (create your Force token).
> While the Force is with you, this unit gets +4/+0 and gains Overwhelm.
> Epic Action: If the number of resources you control plus the number of times you used the Force this phase is 9 or more, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['stat_buff', 'keyword_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_8 — Obi-Wan Kenobi

**Type/Stats:** Leader, cost 5, 3/6  |  Traits: Force, Jedi, Republic

**Rules text:**

> Action [Exhaust, use the Force (lose your Force token)]: Give an Experience token to a unit without an Experience token on it.
> On Attack: You may give an Experience token to another unit without an Experience token on it.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['token'].

**Existing primitives that should suffice:** force-token, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_13 — Barriss Offee

**Type/Stats:** Leader, cost 6, 4/7  |  Traits: Force, Jedi, Republic

**Rules text:**

> Action [Exhaust, use the Force (lose your Force token)]: Play an event from your hand. It costs 1 resource less.
> Action [use the Force]: Play an event from your hand. It costs 1 resource less.
> Epic Action: If you control 6 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['ramp'].

**Existing primitives that should suffice:** force-token, push_play_from_hand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_14 — Grand Inquisitor

**Type/Stats:** Leader, cost 5, 3/5  |  Traits: Force, Imperial, Inquisitor

**Rules text:**

> Action [Exhaust, use the Force (lose your Force token)]: Attack with a friendly unit. The defender gets –2/–0 for this attack.
> Shielded (When you deploy this leader, give a Shield token to him.)
> On Attack: The defender gets –2/–0 for this attack.
> Epic Action: If you control 5 or more resources, deploy this leader.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['attack_grant'].

**Existing primitives that should suffice:** force-token, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

