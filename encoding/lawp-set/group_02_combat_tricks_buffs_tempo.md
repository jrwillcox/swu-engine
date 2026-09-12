# lawp-set:02 — Combat tricks, buffs & tempo

- **Group id (paste this):** `lawp-set:02`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LAWP_4 | Chopper | Unit | 2 | 1/2 | Raid |
| LAWP_6 | Maz Kanata | Unit | 5 | 4/4 |  |
| LAWP_9 | Jango Fett | Unit | 6 | 6/5 | Shielded |

## Per-card analysis & acceptance criteria

### LAWP_4 — Chopper

**Type/Stats:** Unit, cost 2, 1/2  |  Traits: Droid, Rebel, Spectre

**Rules text:**

> Raid 1 
> When Played: Give an Experience token to this unit. If you control a Cunning or Vigilance unit, give 2 Experience tokens to him instead.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAWP_6 — Maz Kanata

**Type/Stats:** Unit, cost 5, 4/4  |  Traits: Underworld

**Rules text:**

> When Attack Ends: If this unit survived, search the top 5 cards of your deck for an Underworld unit and play it. It costs 4 resources less and enters play ready. At the start of the regroup phase, put that unit on the bottom of your deck .

**Mechanical analysis:** trigger archetype `phase_boundary`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** CostReduction.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LAWP_9 — Jango Fett

**Type/Stats:** Unit, cost 6, 6/5  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> Shielded 
> On Attack: If this unit is upgraded, exhaust an enemy unit.

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['ready_exhaust'].

**Existing primitives that should suffice:** ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

