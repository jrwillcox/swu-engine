# hmw-set:10 — Card advantage & disruption

- **Group id (paste this):** `hmw-set:10`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| HMW_204 | Nightbrother | Unit | 7 | 6/7 |  |
| HMW_215 | L3-37 | Unit | 6 | 5/7 |  |
| HMW_222 | Sandcrawler Sales Team | Unit | 2 | 3/2 | Saboteur |
| HMW_232 | Mon Cal Cruiser | Unit | 6 | 4/7 |  |
| HMW_236 | Booma Ball | Upgrade | 3 |  |  |
| HMW_238 | Exploit Confidence | Event | 2 |  |  |
| HMW_247 | Surveillance Cruiser | Unit | 4 | 4/4 |  |

## Per-card analysis & acceptance criteria

### HMW_204 — Nightbrother

**Type/Stats:** Unit, cost 7, 6/7  |  Traits: Transport, Vehicle

**Rules text:**

> When Played: You may play a unit from your discard pile. It costs 3 resources less and enters play ready. At the start of the next regroup phase, defeat it.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['discard', 'defeat', 'ready_exhaust'].

**Existing primitives that should suffice:** DiscardFromHand, CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_215 — L3-37

**Type/Stats:** Unit, cost 6, 5/7  |  Traits: Droid, Underworld

**Rules text:**

> When you play an event that costs 3 or less: You may play it again from your discard pile for free. Use this ability only once each phase.

**Mechanical analysis:** trigger archetype `static`; effect families ['discard'].

**Existing primitives that should suffice:** DiscardFromHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_222 — Sandcrawler Sales Team

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Jawa

**Rules text:**

> Saboteur (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)
> When Played: If you control a Tatooine base, you may return an upgrade that costs 3 or less to its owner's hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_232 — Mon Cal Cruiser

**Type/Stats:** Unit, cost 6, 4/7  |  Traits: Capital Ship, Rebel, Vehicle

**Rules text:**

> When Played: Choose one:
> Attack with a unit. It gets +2/+0 for this attack.
> Look at an opponent's hand. You may discard a card from it. If you do, they draw a card.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw', 'discard', 'stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** DrawCards, DiscardFromHand, ModifyStats/StatBonus, push_modal, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_236 — Booma Ball

**Type/Stats:** Upgrade, cost 3  |  Traits: Item, Weapon

**Rules text:**

> When Played: You may return an upgrade that costs 3 or less to its owner's hand.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_238 — Exploit Confidence

**Type/Stats:** Event, cost 2  |  Traits: Tactic

**Rules text:**

> Return a non-leader unit with 6 or more power to its owner's hand.

**Mechanical analysis:** trigger archetype `event`; effect families ['return_hand'].

**Existing primitives that should suffice:** ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### HMW_247 — Surveillance Cruiser

**Type/Stats:** Unit, cost 4, 4/4  |  Traits: Capital Ship, Imperial, Vehicle

**Rules text:**

> When Played: If an opponent controls an Endor, Kashyyyk, Naboo, or Tatooine base, draw a card.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

