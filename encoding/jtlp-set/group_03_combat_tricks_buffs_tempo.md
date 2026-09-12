# jtlp-set:03 — Combat tricks, buffs & tempo

- **Group id (paste this):** `jtlp-set:03`
- **Kind:** ability
- **Cards:** 3

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| JTLP_3 | Hera Syndulla | Unit | 2 | 2/3 | Piloting, Restore |
| JTLP_5 | Leia Organa | Unit | 3 | 3/4 | Restore |
| JTLP_13 | Captain Tarkin | Unit | 3 | 2/5 | Overwhelm |

## Per-card analysis & acceptance criteria

### JTLP_3 — Hera Syndulla

**Type/Stats:** Unit, cost 2, 2/3  |  Traits: Pilot, Rebel, Spectre, Twi'lek

**Rules text:**

> Restore 1
> Piloting [2 resources Vigilance Heroism]
> Attached unit gains Restore 1.

**Mechanical analysis:** trigger archetype `constant`; effect families ['keyword_grant'].

**Existing primitives that should suffice:** GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTLP_5 — Leia Organa

**Type/Stats:** Unit, cost 3, 3/4  |  Traits: Official, Rebel

**Rules text:**

> Restore 1
> When Played: You may attack with a Pilot unit or a unit with a Pilot on it. It gets +1/+0 and gains Restore 1 for this attack.

**Mechanical analysis:** trigger archetype `when_played`; effect families ['stat_buff', 'keyword_grant', 'attack_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword, push_granted_attack.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### JTLP_13 — Captain Tarkin

**Type/Stats:** Unit, cost 3, 2/5  |  Traits: Official, Republic

**Rules text:**

> Each friendly Vehicle unit gets +1/+0 and gains Overwhelm.

**Mechanical analysis:** trigger archetype `constant`; effect families ['stat_buff', 'keyword_grant'].

**Existing primitives that should suffice:** ModifyStats/StatBonus, GrantKeyword.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

