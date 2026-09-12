# jtl-set:22 — Miscellaneous abilities

- **Group id (paste this):** `jtl-set:22`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTL_39 | Chimaera | Unit | 6 | 5/6 |  |
| JTL_47 | Admiral Yularen | Unit | 3 | 1/5 | Grit, Restore, Sentinel, Shielded |
| JTL_49 | L3-37 | Unit | 3 | 3/3 | Piloting |
| JTL_52 | D'Qar Cargo Frigate | Unit | 5 | 6/7 |  |
| JTL_54 | Gold Leader | Unit | 6 | 5/5 | Shielded |
| JTL_56 | Hondo Ohnaka | Unit | 4 | 3/5 | Shielded |
| JTL_59 | Corporate Defense Shuttle | Unit | 2 | 3/5 |  |

## Per-card analysis & acceptance criteria

### JTL_39 — Chimaera

**Type/Stats:** Unit, cost 6, 5/6  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> When Played: You may use a “When Defeated” ability on another friendly unit.
> When Defeated: Create 2 TIE Fighter tokens.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Existing primitives that should suffice:** create-token-unit.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_47 — Admiral Yularen

**Type/Stats:** Unit, cost 3, 1/5  |  Traits: Official, Republic

**Rules text:**

> When Played: Choose Grit, Restore 1, Sentinel, or Shielded. While this unit is in play, each friendly Vehicle unit gains the chosen keyword.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_49 — L3-37

**Type/Stats:** Unit, cost 3, 3/3  |  Traits: Droid, Pilot, Underworld

**Rules text:**

> If this unit would be defeated, you may instead attach her as an upgrade to a friendly Vehicle unit without a Pilot on it. (She's no longer a unit. Defeat all upgrades on her and remove all damage from her.)
> Piloting [3 resources Vigilance Heroism]

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_52 — D'Qar Cargo Frigate

**Type/Stats:** Unit, cost 5, 6/7  |  Traits: Capital Ship, Resistance, Vehicle

**Rules text:**

> This unit gets –1/–0 for each damage on it.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_54 — Gold Leader

**Type/Stats:** Unit, cost 6, 5/5  |  Traits: Rebel, Transport, Vehicle

**Rules text:**

> Shielded (When you play this unit, give a Shield token to it.)
> While this unit is defending, the attacker gets –1/–0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_56 — Hondo Ohnaka

**Type/Stats:** Unit, cost 4, 3/5  |  Traits: Underworld

**Rules text:**

> Shielded
> On Attack: You may take control of a non-Pilot upgrade on a unit and attach it to a different eligible unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Existing primitives that should suffice:** control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTL_59 — Corporate Defense Shuttle

**Type/Stats:** Unit, cost 2, 3/5  |  Traits: Separatist, Transport, Vehicle

**Rules text:**

> This unit can't attack.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

