# ic27-set:03 — Direct damage & removal

- **Group id (paste this):** `ic27-set:03`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| IC27_147 | Asajj Ventress | Unit | 6 | 5/7 |  |
| IC27_151 | R2-D2 | Unit | 1 | 1/3 |  |
| IC27_185 | I Am Your Father | Event | 3 |  |  |

## Per-card analysis & acceptance criteria

### IC27_147 — Asajj Ventress

**Type/Stats:** Unit, cost 6, 5/7  |  Traits: Force, Separatist, Sith

**Rules text:**

> If a friendly non-leader ground unit would deal combat damage while attacking a base, you may reveal this unit from your hand and pay 5 resourcesCunningVillainy. If you do, return the attacker to its owner's hand and put this unit into play as the attacker. She deals combat damage to that base instead.

**Mechanical analysis:** trigger archetype `constant`; effect families ['damage', 'return_hand'].

**Existing primitives that should suffice:** DealDamage, ReturnToHand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_151 — R2-D2

**Type/Stats:** Unit, cost 1, 1/3  |  Traits: Droid, Rebel

**Rules text:**

> On Attack: Choose one: 
> Ready a resource.
> Deal 1 damage to a ground unit.
> Look at the top card of your deck. You may discard it.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['damage', 'discard', 'ready_exhaust', 'ramp', 'search'].

**Existing primitives that should suffice:** DealDamage, DiscardFromHand, ExhaustCard/ReadyCard, push_modal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### IC27_185 — I Am Your Father

**Type/Stats:** Event, cost 3  |  Traits: Gambit

**Rules text:**

> Deal 7 damage to an enemy unit unless its controller says “no.” If they do, draw 3 cards.

**Mechanical analysis:** trigger archetype `event`; effect families ['damage', 'draw'].

**Existing primitives that should suffice:** DealDamage, DrawCards, push_say_no.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

