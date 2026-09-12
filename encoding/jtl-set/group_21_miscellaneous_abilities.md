# jtl-set:21 — Miscellaneous abilities

- **Group id (paste this):** `jtl-set:21`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_6 | Darth Vader | Leader | 6 | 5/6 |  |
| JTL_13 | Poe Dameron | Leader | 5 | 4/6 |  |
| JTL_18 | Kazuda Xiono | Leader | 4 | 2/5 |  |
| JTL_24 | Data Vault | Base |  | None/33 |  |
| JTL_25 | Thermal Oscillator | Base |  | None/27 |  |
| JTL_35 | Tam Ryvora | Unit | 3 | 2/5 | Piloting |
| JTL_38 | Corvus | Unit | 5 | 4/5 | Restore |

## Per-card analysis & acceptance criteria

### JTL_6 — Darth Vader

**Type/Stats:** Leader, cost 6, 5/6  |  Traits: Force, Imperial, Pilot, Sith

**Rules text:**

> Action [Exhaust]: If you attacked with a non-token Vehicle unit this phase, create a TIE Fighter token.
> 
> Attached unit is a leader unit.
> When deployed as an upgrade: Create 2 TIE Fighter tokens.
> 
> Epic Action: If you control 6 or more resources, choose one:
> Deploy this leader.
> Deploy this leader as an upgrade on a friendly Vehicle unit without a Pilot on it.

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['—'].

**Existing primitives that should suffice:** push_modal, create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_13 — Poe Dameron

**Type/Stats:** Leader, cost 5, 4/6  |  Traits: Pilot, Resistance

**Rules text:**

> Action [1 resource, Exhaust]: Flip this leader and attach him as an upgrade to a friendly Vehicle unit without a Pilot on it.
> 
> Action [1 resource]: Attach this upgrade to a friendly Vehicle unit without a Pilot on it. Use this ability only once each round.
> 
> Epic Action: If you control 5 or more resources, deploy this leader (as a unit).

**Mechanical analysis:** trigger archetype `epic_action`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_18 — Kazuda Xiono

**Type/Stats:** Leader, cost 4, 2/5  |  Traits: Pilot, Resistance

**Rules text:**

> Action [Exhaust]: A friendly unit loses all abilities for this round. Take an extra action after this one.
> On Attack: Choose any number of friendly units. They lose all abilities for this round.
> Attached unit is a leader unit. It gains: “On Attack: Choose any number of friendly units. They lose all abilities for this round.”
> 
> Epic Action: If you control 4 or more resources, choose one:
> Deploy this leader.
> Deploy this leader as an upgrade on a friendly Vehicle unit without a Pilot on it.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Existing primitives that should suffice:** push_modal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_24 — Data Vault

**Type/Stats:** Base

**Rules text:**

> Your minimum deck size is increased by 10 cards.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_25 — Thermal Oscillator

**Type/Stats:** Base

**Rules text:**

> Your minimum deck size is decreased by 5 cards.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_35 — Tam Ryvora

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: First Order, Pilot

**Rules text:**

> Piloting [2 resources Vigilance Villainy] (You may play this as an upgrade on a friendly Vehicle without a Pilot.)
> Attached unit gains: “On Attack: Give an enemy unit in this arena –1/–1 for this phase.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_38 — Corvus

**Type/Stats:** Unit, cost 5, 4/5  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> Restore 2
> When Played: You may attach a friendly Pilot unit or upgrade to this unit. (Defeat all upgrades on that Pilot and remove all damage from it.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

