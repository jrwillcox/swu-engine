# the-mandalorian:01 — Bounty keyword

- **Group id (paste this):** `the-mandalorian:01`
- **Kind:** keyword
- **Cards:** 4

## Bounty cards — the keyword is ALREADY implemented (do NOT build it)

**Correction to the planner's default boilerplate.** Bounty is *not* a deferred
Phase-3 keyword. It was implemented as a **convention** in `shd-han-solo:02` and is
documented in `CLAUDE.md` (Phase 2 → "Bounty"). The audit still lists these cards
as `keyword-deferred` only because `audit_coverage.PHASE3_KEYWORDS` still names
"Bounty" — a known wart (Bounty has no single engine toggle, unlike Smuggle). Do
**not** touch the keyword layer, add a keyword, or edit any deferred list.
**Registering each card's ability below flips it to `implemented` directly** — the
audit's registry check in `classify()` takes priority over the keyword label.

**The convention** (precedent: `src/swu/cards/shd/abilities.py` →
`_unlicensed_headhunter` SHD_165, ~lines 188–213): a "Bounty — <effect>" ability is
the reminder text "when this unit is defeated/captured, your opponent collects its
bounty." Model it as a normal `WhenDefeated` `TriggerAbility` whose effect resolves
from the **collector = the ENEMY of the dying unit's controller**. Express "your
opponent collects" by writing the effect from the **enemy perspective**
(`controller="enemy"`, fixed sentinels like `EACH_ENEMY`). No change to the
trigger/decision machinery.

**Bounty-granting UPGRADES** (here: Public Enemy SHD_68, Wanted SHD_221, Rich
Reward SHD_261): the upgrade confers the bounty on its *host*, so wrap the
`WhenDefeated` `TriggerAbility` in a **`GrantedAbility`** (precedent: Armed to the
Teeth SHD_175 / The Darksaber SHD_126) so it resolves from the host.

**Convention limitation:** it covers only deterministic / "all enemies" / single
fixed-target bounties. A bounty that needs the *collector to choose* among targets
would need the deciding-player seam — flag it if so. Audit each effect below.

### Per-card encoding notes
- **Chain Code Collector (SHD_216) is NOT a bounty-granter** — it is miscategorised
  here by the planner. It is `Ambush` (keyword layer, already done) **+** "On
  Attack: if the *defender has a Bounty*, it gets −4/−0 for this attack." That needs
  (a) a way to ask "does this unit have a Bounty" — and bounties are modelled as
  abilities/granted upgrades, **not** a queryable keyword state, so this likely
  needs a small new "target-has-bounty" predicate/condition — and (b) an `OnAttack`
  `ModifyStats(power=-4, hp=0, duration=THIS_ATTACK)` on the defender. Encode it as
  a combat trick; if the has-bounty query needs more than a predicate, flag it.
- **Rich Reward (SHD_261)** "Give an Experience token to each of up to 2 units"
  is an *up-to-N* choice — `GiveToken`'s `count` is the token quantity, not a target
  count, so use the **`select_token`** decision (precedent: Medal Ceremony SOR_245
  `push_select_token`), resolved from the collector's perspective.
- **Wanted (SHD_221)** "Ready 2 friendly resources" (from the collector's side) may
  need a small ready-resources effect — check the effect registry before writing.

## Cards

| id | name | type | cost | P/HP | keywords |
|----|------|------|-----:|------|----------|
| SHD_68 | Public Enemy | Upgrade | 0 |  | Bounty |
| SHD_216 | Chain Code Collector | Unit | 4 | 4/2 | Ambush, Bounty |
| SHD_221 | Wanted | Upgrade | 0 |  | Bounty |
| SHD_261 | Rich Reward | Upgrade | 1 |  | Bounty |

## Per-card analysis & acceptance criteria

### SHD_68 — Public Enemy

**Type/Stats:** Upgrade, cost 0  |  Traits: Bounty, Condition

**Rules text:**

> Attached unit gains: “Bounty — Give a Shield token to a unit.” (When this unit is defeated or captured, its opponent collects its bounty.)

**Residual text (needs separate ability after keyword):** Attached unit gains: “Bounty — Give a Shield token to a unit.” (When this unit is defeated or captured, its opponent collects its bounty.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_216 — Chain Code Collector

**Type/Stats:** Unit, cost 4, 4/2  |  Traits: Bounty Hunter, Underworld

**Rules text:**

> Ambush (When you play this unit, it may ready and attack an enemy unit.)
> On Attack: If the defender has a Bounty, it gets –4/–0 for this attack.

**Residual text (needs separate ability after keyword):** Ambush (When you play this unit, it may ready and attack an enemy unit.)

**Mechanical analysis:** trigger archetype `on_attack`; effect families ['—'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_221 — Wanted

**Type/Stats:** Upgrade, cost 0  |  Traits: Bounty, Condition

**Rules text:**

> Attached unit gains: “Bounty — Ready 2 friendly resources.” (When this unit is defeated or captured, its opponent collects its bounty.)

**Residual text (needs separate ability after keyword):** Attached unit gains: “Bounty — Ready 2 friendly resources.” (When this unit is defeated or captured, its opponent collects its bounty.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['ready_exhaust'].

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

### SHD_261 — Rich Reward

**Type/Stats:** Upgrade, cost 1  |  Traits: Bounty, Condition

**Rules text:**

> Attached unit gains: “Bounty — Give an Experience token to each of up to 2 units.” (When this unit is defeated or captured, its opponent collects its bounty.)

**Residual text (needs separate ability after keyword):** Attached unit gains: “Bounty — Give an Experience token to each of up to 2 units.” (When this unit is defeated or captured, its opponent collects its bounty.)

**Mechanical analysis:** trigger archetype `constant`; effect families ['token'].

**Existing primitives that should suffice:** GiveToken.

**Acceptance criteria:** one focused test named for the card asserting the behaviour through public engine interfaces (`legal_actions`/`apply`), and the card classifies as `implemented` (or better) in the deck audit.

