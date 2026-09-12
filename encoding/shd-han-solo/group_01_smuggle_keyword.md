# shd-han-solo:01 — Smuggle keyword

- **Group id (paste this):** `shd-han-solo:01`
- **Kind:** keyword
- **Cards:** 7
- **⚠ New primitives suspected:** grant-keyword-to-resources — see escalation rule; do NOT jam a core-resolution change into a card batch.

## Keyword group: **Smuggle**

Implement the **Smuggle** keyword engine-side once (Phase 2 pattern: keyword query layer / effective-stats / decision-stack as needed), with synthetic-card framework tests first. Then confirm every card below becomes playable and remove `Smuggle` from the Phase-2 deferred list in `CLAUDE.md`.

Note: a card may have rules text *beyond* the keyword. Where flagged 'residual text' below, the keyword unblocks the card but its ability text still needs a separate ability registration (re-run the planner after the keyword lands — it will recluster the residual text into an ability group).

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_148 | Cassian Andor | Unit | 3 | 3/5 | Smuggle |
| SHD_149 | Nite Owl Skirmisher | Unit | 3 | 4/3 | Smuggle |
| SHD_160 | Reckless Gunslinger | Unit | 1 | 2/1 | Smuggle |
| SHD_174 | Hotshot DL-44 Blaster | Upgrade | 1 |  | Smuggle |
| SHD_175 | Armed to the Teeth | Upgrade | 2 |  | Smuggle |
| SHD_248 | Tech | Unit | 3 | 2/5 | Smuggle |
| SHD_252 | Smuggler's Aid | Event | 1 |  | Smuggle |

## Per-card analysis & acceptance criteria

### SHD_148 — Cassian Andor

**Type/Stats:** Unit, cost 3, 3/5  |  Traits: Rebel

**Rules text:**

> Smuggle [5 resources Aggression Heroism] (If this card is a resource, you may play him for his smuggle cost. Replace it with the top card of your deck.)
> When played using Smuggle: Ready this unit.

**Residual text (needs separate ability after keyword):** When played using Smuggle: Ready this unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_149 — Nite Owl Skirmisher

**Type/Stats:** Unit, cost 3, 4/3  |  Traits: Mandalorian, Trooper

**Rules text:**

> Smuggle [5 resources Aggression Heroism] (If this card is a resource, you may play it for its smuggle cost. Replace it with the top card of your deck.)

**Mechanical analysis:** trigger archetype `static`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_160 — Reckless Gunslinger

**Type/Stats:** Unit, cost 1, 2/1  |  Traits: Underworld

**Rules text:**

> When Played: Deal 1 damage to each base.
> Smuggle [3 resources Aggression] (If this card is a resource, you may play it for its smuggle cost. Replace it with the top card of your deck.)

**Residual text (needs separate ability after keyword):** When Played: Deal 1 damage to each base.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['damage'].

**Existing primitives that should suffice:** DealDamage.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_174 — Hotshot DL-44 Blaster

**Type/Stats:** Upgrade, cost 1  |  Traits: Item, Weapon

**Rules text:**

> Attach to a non-VEHICLE unit.
> 
> Smuggle [3 resources, cunning]
> 
> When played using Smuggle: Attack with attached unit.

**Residual text (needs separate ability after keyword):** Attach to a non-VEHICLE unit. When played using Smuggle: Attack with attached unit.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['attack_grant'].

**Existing primitives that should suffice:** push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_175 — Armed to the Teeth

**Type/Stats:** Upgrade, cost 2  |  Traits: Supply, Weapon

**Rules text:**

> Attached unit gains: “On Attack: Give another friendly unit +2/+0 for this phase.”
> Smuggle [4 resources Aggression] (If this card is a resource, you may play it for its smuggle cost. Replace it with the top card of your deck.)

**Residual text (needs separate ability after keyword):** Attached unit gains: “On Attack: Give another friendly unit +2/+0 for this phase.”

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['stat_buff'].

**Existing primitives that should suffice:** ModifyStats/StatBonus.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_248 — Tech

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: Clone, Fringe

**Rules text:**

> Each friendly resource gains Smuggle. The gained Smuggle cost is that card's cost plus 2 resources and its aspect icons.
> Smuggle [4 resources Heroism]

**Residual text (needs separate ability after keyword):** Each friendly resource gains Smuggle. The gained Smuggle cost is that card's cost plus 2 resources and its aspect icons.

**Mechanical analysis:** trigger archetype `constant`; effect families ['ramp'].

**⚠ Suspected NEW primitive:** grant-keyword-to-resources. If implementing it touches core resolution / the trigger / decision machinery, STOP and flag for a dedicated framework session.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_252 — Smuggler's Aid

**Type/Stats:** Event, cost 1  |  Traits: Supply

**Rules text:**

> Heal 3 damage from your base.
> Smuggle [3 resources Heroism] (If this card is a resource, you may play it for its smuggle cost. Replace it with the top card of your deck.)

**Residual text (needs separate ability after keyword):** Heal 3 damage from your base.

**Mechanical analysis:** trigger archetype `event`; effect families ['heal'].

**Existing primitives that should suffice:** Heal.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

