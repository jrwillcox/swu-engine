# lof-set:16 — Combat tricks, buffs & tempo

- **Group id (paste this):** `lof-set:16`
- **Kind:** ability
- **Cards:** 7

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| LOF_215 | Ascension Cable | Upgrade | 2 |  | Saboteur |
| LOF_216 | Disturbance in the Force | Event | 1 |  |  |
| LOF_220 | Shien Flurry | Event | 1 |  | Ambush |
| LOF_221 | Trust Your Instincts | Event | 1 |  |  |
| LOF_223 | Force Illusion | Event | 2 |  | Sentinel |
| LOF_224 | Pounce | Event | 2 |  |  |
| LOF_225 | Three Lessons | Event | 2 |  | Hidden |

## Per-card analysis & acceptance criteria

### LOF_215 — Ascension Cable

**Type/Stats:** Upgrade, cost 2  |  Traits: Item

**Rules text:**

> Attach to a non-Vehicle unit.
> Attached unit gains Saboteur. (When this unit attacks, ignore Sentinel and defeat the defender's Shields.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_216 — Disturbance in the Force

**Type/Stats:** Event, cost 1  |  Traits: Force

**Rules text:**

> If a friendly unit left play this phase, the Force is with you (create your Force token) and you may give a Shield token to a unit.

**Mechanical analysis:** trigger archetype `event`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_220 — Shien Flurry

**Type/Stats:** Event, cost 1  |  Traits: Learned

**Rules text:**

> Play a Force unit from your hand (paying its cost). It gains Ambush for this phase. The next time it would be dealt damage this phase, prevent 2 of that damage.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword, push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_221 — Trust Your Instincts

**Type/Stats:** Event, cost 1  |  Traits: Force

**Rules text:**

> Use the Force. If you do, attack with a unit. It gets +2/+0 for this attack and deals its combat damage before the defender. (If the defender is defeated, it deals no combat damage.)

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack, force-token.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_223 — Force Illusion

**Type/Stats:** Event, cost 2  |  Traits: Force, Trick

**Rules text:**

> Exhaust an enemy unit. A friendly unit gains Sentinel for this phase.

**Mechanical analysis:** trigger archetype `constant`; effect families ['ready_exhaust', 'keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword, ExhaustCard/ReadyCard.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_224 — Pounce

**Type/Stats:** Event, cost 2  |  Traits: Trick

**Rules text:**

> Attack with a Creature unit. It gets +4/+0 for this attack.

**Mechanical analysis:** trigger archetype `event`; effect families ['stat_buff', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### LOF_225 — Three Lessons

**Type/Stats:** Event, cost 2  |  Traits: Learned

**Rules text:**

> Play a unit from your hand (paying its cost). It gains Hidden for this phase. Give an Experience token and a Shield token to it.

**Mechanical analysis:** trigger archetype `constant`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken, push_play_from_hand.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

