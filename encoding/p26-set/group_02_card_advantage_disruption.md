# p26-set:02 — Card advantage & disruption

- **Group id (paste this):** `p26-set:02`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| P26_266 | Admiral Holdo | Unit | 5 | 3/7 |  |
| P26_269 | I've Got A Bad Feeling | Event | 4 |  |  |
| P26_273 | Jar Jar Binks | Unit | 2 | 1/5 |  |

## Per-card analysis & acceptance criteria

### P26_266 — Admiral Holdo

**Type/Stats:** Unit, cost 5, 3/7  |  Traits: Official, Resistance

**Rules text:**

> Draw 1 more card during the regroup phase.

**Mechanical analysis:** trigger archetype `static`; effect families ['draw'].

**Existing primitives that should suffice:** DrawCards.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P26_269 — I've Got A Bad Feeling

**Type/Stats:** Event, cost 4  |  Traits: Innate

**Rules text:**

> Return a non–leader unit to its owner's hand.
> Give a Shield token to a friendly unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['return_hand', 'token'].

**Existing primitives that should suffice:** ReturnToHand, GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### P26_273 — Jar Jar Binks

**Type/Stats:** Unit, cost 2, 1/5  |  Traits: Gungan, Official, Republic

**Rules text:**

> On Attack: Discard a card from your deck. If it costs 6 or more, this unit gets +4/+0 for this attack.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['discard', 'stat_buff'].

**Existing primitives that should suffice:** DiscardFromHand, ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

