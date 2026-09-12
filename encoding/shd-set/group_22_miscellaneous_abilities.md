# shd-set:22 — Miscellaneous abilities

- **Group id (paste this):** `shd-set:22`
- **Kind:** ability
- **Cards:** 5

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_215 | Smuggler's Starfighter | Unit | 3 | 2/2 | Smuggle |
| SHD_219 | Enfys Nest | Unit | 6 | 5/4 | Ambush |
| SHD_224 | Boba Fett's Armor | Upgrade | 2 |  |  |
| SHD_250 | Tarfful | Unit | 7 | 3/9 | Restore |
| SHD_256 | Mercenary Gunship | Unit | 2 | 3/2 |  |

## Per-card analysis & acceptance criteria

### SHD_215 — Smuggler's Starfighter

**Type/Stats:** Unit, cost 3, 2/2  |  Traits: Transport, Underworld, Vehicle

**Rules text:**

> When Played: If you control another Underworld unit, give an enemy unit –3/–0 for this phase.
> Smuggle [4 resources Cunning] (If this card is a resource, you may play it for its smuggle cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `when_played`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_219 — Enfys Nest

**Type/Stats:** Unit, cost 6, 5/4  |  Traits: Underworld

**Rules text:**

> Ambush (When you play this unit, it may ready and attack an enemy unit.)
> While a friendly unit (including this one) is attacking using Ambush, the defender gets –3/–0.

**Mechanical analysis:** trigger archetype `constant`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_224 — Boba Fett's Armor

**Type/Stats:** Upgrade, cost 2  |  Traits: Armor, Item

**Rules text:**

> Attach to a non-Vehicle unit.
> If attached unit is Boba Fett and damage would be dealt to him, prevent 2 of that damage.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_250 — Tarfful

**Type/Stats:** Unit, cost 7, 3/9  |  Traits: Wookiee

**Rules text:**

> Restore 2
> When a friendly Wookiee unit is dealt combat damage and isn't defeated: That unit deals that much damage to an enemy ground unit.

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_256 — Mercenary Gunship

**Type/Stats:** Unit, cost 2, 3/2  |  Traits: Fighter, Underworld, Vehicle

**Rules text:**

> Action [4 resources]: Take control of this unit. Any player may use this ability.

**Mechanical analysis:** trigger archetype `activated`; effect families ['—'].

**Existing primitives that should suffice:** control-change.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

