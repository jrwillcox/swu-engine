# Phase 3 — Ability Framework Design

**Status**: Design document (Step 0). Do not implement until reviewed and approved.

**CR authority**: the official Comprehensive Rules PDF (download from
https://starwarsunlimited.com/rules — not redistributed in this repo) — verify
every rule cited here before coding.  
Sections to read before implementation: §6 (ability types), §7 (ability resolution, ordering,
partial resolution), §Attacks (trigger timing relative to damage), and the glossary entries for
Triggered Ability, Constant Ability, Activated Ability, and Replacement Effect.

---

## 1. Goals and Constraints

| Goal | How |
|------|-----|
| Declarative definitions | Most abilities are data (specs + primitives), not imperative code |
| LLM-translatable | A later phase uses an LLM to generate definitions; the format must be constrained enough to validate mechanically |
| Engine-safe | Every resolution is a `GameState → GameState` deepcopy-then-mutate; no side channels |
| Ordered | Simultaneous triggers produce deterministic outcomes via the decision stack |
| Backward-compatible | Cards with no registry entry behave exactly as today; nothing unimplemented breaks |

---

## 2. Ability Types

SWU has five ability types (CR §6). Phase 3 implements four; replacement effects remain narrow.

### 2.1 Triggered Abilities

Fire automatically when their **trigger condition** is met. Mandatory triggers resolve without
extra player input; optional triggers ("you may") present a yes/no decision first.

**Trigger conditions** (CR §6.5):

| Condition class | Fires when | Event matched |
|-----------------|-----------|---------------|
| `WhenPlayed` | Source card enters play | `UnitEntersPlay` (units/leaders) or `CardPlayed` (events/upgrades) |
| `WhenDefeated` | Source card is defeated | `UnitDefeated` |
| `OnAttack` | Source card is declared as attacker | `AttackDeclared` where `attacker_instance_id == source.instance_id` |
| `WhenUnitDefeated(filter)` | Any unit matching `filter` is defeated | `UnitDefeated` — `filter` evaluated from source owner's perspective |
| `WhenUnitEntersPlay(filter)` | A unit matching `filter` enters play | `UnitEntersPlay` |
| `WhenCombatDamageDealt(filter)` | Source deals combat damage to a card matching `filter` | synthesised after combat step |
| `OnAttackDefeatsUnit` | Source attacks and the defender is defeated this attack | synthesised after combat step |
| `WhenEventPlayed(filter)` | An event matching `filter` is played | `CardPlayed` where card type is Event |
| `PhaseStart(phase)` | Named phase begins | `PhaseChanged` |
| `RoundStart` | New round begins | `RoundStarted` |

The source card must be in play when the trigger condition is met, with two exceptions:
- `WhenDefeated`: fires at the moment the card is being defeated (the source is in the process of moving to discard).
- `WhenPlayed`: fires at the moment the card finishes entering play.

**Optional triggers** push a `PendingDecision(kind="trigger_option")` with a yes/no choice.
If the player declines, no effects resolve.

### 2.2 Constant (Static) Abilities

Active continuously while the source card is in play. Never applied as one-shot events —
always **recomputed from current game state** every time relevant.

Two sub-types:

- **Stat/keyword modifier**: grants +N power, +N HP, or a keyword to target cards.
  Routed through `compute_power()` and `has_keyword()` (see §8.3).
- **Rule modifier**: changes game rules ("events cost 1 more", "can't be attacked unless
  gains Sentinel"). Checked at the point where the rule is evaluated.

**Conditional statics** have a `Condition` that must evaluate True for the effect to apply.
Conditions are typed atoms (not strings), so LLM-generated definitions can be validated:

```python
class Condition(Enum):
    SOURCE_UNDAMAGED              # source.damage == 0
    SOURCE_DAMAGED                # source.damage > 0
    CONTROLLER_HAS_INITIATIVE     # source owner holds initiative
    CONTROLLER_N_PLUS_RESOURCES   # needs parameter: n
    CONTROLLER_HAS_TRAIT_UNIT     # needs parameter: trait string
    CONTROLLER_IS_LEADER_UNIT     # source owner has their leader deployed as a unit
```

Constant abilities do **not** create Modifier records. They are re-evaluated on every call
to `compute_power()` / `has_keyword()`.

### 2.3 Activated Abilities

Used as explicit actions during the action phase. All costs must be payable for the action
to appear in `legal_actions()`.

**Cost types**:

| Cost class | Effect |
|------------|--------|
| `ExhaustSelf` | Exhaust the source card |
| `PayResources(n)` | Exhaust n ready resources |
| `DefeatSelf` | Defeat the source card as cost |
| `DiscardCard(count)` | Discard from controller's hand |

**Leader undeployed side**: The `deploy_box` field contains the leader's ability while
undeployed. Two formats appear:
- `"On Attack: ..."` → a **triggered** ability that fires when the undeployed leader attacks.
- `"Action [cost]: ..."` → an **activated** ability that appears as a new action type.

For SOR Luke and Vader, the deploy_box text uses "On Attack", which is a triggered ability.

**Deployed leader**: The deployed leader is a unit in an arena. Its abilities come from the
same `deploy_box` text (the ability persists after deploy; both sides share the same
"On Attack" text). If a leader has different deployed-unit-only abilities, they would be in
the `text` field (verify per card).

**Epic Action**: `DeployLeader` is the existing Epic Action. Future base Epic Actions
(e.g. Tarkintown: "Deal 3 damage to a damaged non-leader unit") follow the same once-per-game
pattern, tracked via `CardInstance.epic_action_spent`.

### 2.4 Event Card Effects

An event card's entire text is resolved as a single ability when the card is played.
The event is moved to discard first, then effects resolve. Effects use the same primitives
and targeting as triggered abilities.

In `PlayCard.apply()`, after moving the event to discard and firing `CardPlayed`, the engine
looks up the event's ability definition and queues effect resolution. If effects require
targeting, decisions are pushed; the active player does not switch until all decisions resolve.

### 2.5 Replacement Effects (narrow)

Two narrow replacement effects are implemented. Do not build a general system; if a
starter deck card genuinely needs a new one, implement it narrowly and log it here.

1. **Shield** — intercept damage → defeat shield token.
2. **Relentless (SOR_89), event-ability suppression** — "The first event played by each
   opponent each round loses all abilities." Modelled as a constant marker effect
   `SuppressFirstEnemyEvent` carried by a `ConstantAbility` (passive while in play; no
   action starts/stops it, and it ends the instant Relentless leaves play). Detection is
   centralised at the single event-resolution chokepoint `_resolve_event_ability`
   (actions.py), which both `PlayCard` paths route through:
   - `GameMemory.events_played_this_round: set[player_id]` records who has played ≥1 event
     this round (recorded on *every* event play, so "first" is correct even for events with
     no registered ability). Cleared in `GameMemory.clear_round()`.
   - On a player's first event, if an *opponent* controls a unit whose abilities include
     `SuppressFirstEnemyEvent` (`_find_event_suppressor`), the event's abilities are skipped
     (cost still paid, card still discarded) and an `EventAbilitiesSuppressed` event is
     logged. "Each opponent" is honoured: a Relentless never blanks its own controller's
     events.

   The stat/keyword consumers (`compute_power`, `has_keyword`) ignore the marker — it is not
   a StatBonus/KeywordGrant — so Relentless is classified as a passive constant ability
   (zero resolver fires expected) by the soak coverage analysis.

---

## 3. Effect Primitives

A library of small, composable, frozen-dataclass operations. Effects execute sequentially
in the order listed in the ability definition. Each primitive takes resolved targets and
produces state changes + events.

**Target references (fixed, no player choice)**:

```python
SELF      = "self"       # the source card
ATTACKER  = "attacker"   # current attack's attacker (attack-context only)
DEFENDER  = "defender"   # current attack's defender (attack-context only)
EACH_COLLECTED = "each_collected"  # each card collected by a preceding ForEach
```

**Primitive catalogue** (grow strictly on demand from real cards):

| Primitive | Key parameters | Notes |
|-----------|---------------|-------|
| `DealDamage` | `amount: int`, `target: TargetSpec` | Shield intercepts if present |
| `Heal` | `amount: int`, `target: TargetSpec` | target may be unit or base |
| `DefeatUnit` | `target: TargetSpec` | emits `UnitDefeated`; triggers WhenDefeated |
| `DefeatAllUnits` | `filter: TargetSpec` | collect all matches first, then defeat simultaneously (see §7.3) |
| `GiveToken` | `token_type: str`, `target: TargetSpec` | "Shield" or "Experience" |
| `DrawCards` | `count: int`, `player: str` | player: `"controller"` / `"opponent"` / `"each"` |
| `DiscardFromHand` | `count: int`, `chooser: str` | chooser: who chooses which card |
| `ReturnToHand` | `target: TargetSpec` | moves card to owner's hand |
| `ExhaustCard` | `target: TargetSpec` | exhaust |
| `ReadyCard` | `target: TargetSpec` | ready |
| `ModifyStats` | `power: int`, `hp: int`, `target: TargetSpec`, `duration: Duration` | creates a Modifier record; negative allowed |
| `GrantKeyword` | `keyword: str`, `value: int`, `target: TargetSpec`, `duration: Duration` | creates a Modifier record |
| `RevokeKeyword` | `keyword: str`, `target: TargetSpec`, `duration: Duration` | e.g. "loses Sentinel" |
| `ResourceCard` | `target: TargetSpec` | move card to RESOURCES zone, face-down, ready |
| `MarkNoReadyThisRound` | `target: TargetSpec` | for "can't ready this round" effects |
| `ConditionalEffect` | `condition: Condition`, `if_true: list[Effect]`, `if_false: list[Effect]` | "if you control a FORCE unit" |
| `ForEachEffect` | `collection: CollectionSpec`, `effect: Effect` | "for each X, do Y" |

**Not in Phase 3** (deferred): SearchDeck, PlayFromHand, TakeControl, CreateTokenUnit,
complex card-reveal effects, cost reduction effects. Add only as a starter deck card demands.

---

## 4. Targeting System

### 4.1 TargetSpec

```python
@dataclass(frozen=True)
class TargetSpec:
    controller: str = "any"     # "friendly" | "enemy" | "any"
                                # relative to the source card's owner
    kind: str = "unit"          # "unit" | "base" | "upgrade" | "unit_or_base"
    arena: Optional[str] = None # "ground" | "space" | None (any arena or not applicable)
    traits: tuple[str, ...] = ()     # card must have ALL listed traits (e.g. ("Rebel",))
    aspects: tuple[str, ...] = ()    # card must match aspect name
    predicates: tuple[str, ...] = () # see below
    cost_max: Optional[int] = None   # unit cost ≤ N
    hp_remaining_max: Optional[int] = None  # remaining hp ≤ N
    power_max: Optional[int] = None
    count: int = 1                   # exact number to select ("a unit" = 1)
    count_max: Optional[int] = None  # for "up to N units" (count is minimum, usually 0)
    optional: bool = False           # "you may" — player may decline targeting entirely
    chooser: str = "controller"      # "controller" | "opponent" | "controller_of_target"
    fixed: Optional[str] = None      # SELF, ATTACKER, DEFENDER — no player choice
```

**Predicate values**:
```
"damaged"         # ci.damage > 0
"undamaged"       # ci.damage == 0
"exhausted"       # ci.exhausted
"ready"           # not ci.exhausted
"non_leader"      # not isinstance(ci.card_def, Leader)
"non_unique"      # not ci.card_def.is_unique
"not_self"        # ci.instance_id != source.instance_id
"leader_unit"     # isinstance(ci.card_def, Leader) and ci.deployed
```

### 4.2 Resolution Flow

1. **Fixed targets** (`fixed` is set, or AOE collections): no decision pushed. Effect applies
   immediately to the fixed card or all qualifying cards.
2. **Single required choice**: push `PendingDecision(kind="target", context={spec, effect_id,
   legal_target_ids})`. Player picks from legal targets; effect applied to chosen card.
3. **Optional single choice** (`optional=True`): push `PendingDecision(kind="target_optional",
   context={..., may_decline=True})`. Player may choose a target or pass.
4. **Sequential multi-target effects** (multiple `DealDamage` calls each needing a target):
   push decisions onto the stack in **reverse order** so the first decision surfaces first
   (LIFO). Each resolves independently.

### 4.3 Partial Resolution (CR §7.x — verify exact section)

Per CR: if an ability cannot fully resolve (no legal targets for one effect), it resolves
as much as possible. Specifically:
- If the **first** effect of a mandatory triggered ability has no legal targets, that
  individual effect does nothing; subsequent effects still attempt to resolve.
- If the **only** effect has no legal targets, the ability fizzles entirely but still
  "resolved" (so ordering decisions already paid are not refunded).
- Optional effects (`optional=True`) that have no legal targets are simply skipped.

**Test these paths explicitly**: targeting fizzle, partial resolution, optional decline.

---

## 5. Modifier System

Stat and keyword modifiers applied by ability *effects* (not constant abilities) are stored
as records and cleaned up at duration boundaries.

```python
@dataclass
class Modifier:
    modifier_id: str              # unique within the game
    source_instance_id: str       # creating card (for lifetime cleanup)
    target_instance_id: Optional[str]  # specific card, or None for category
    target_spec: Optional[TargetSpec]  # for category (e.g. "all friendly Rebel units")
    kind: str                     # "power" | "hp" | "keyword_grant" | "keyword_revoke"
    value: Any                    # int for stat mods, str for keyword
    duration: "Duration"
```

```python
class Duration(Enum):
    PERMANENT    = "permanent"    # until source leaves play
    THIS_PHASE   = "this_phase"   # cleared at phase boundary
    THIS_ATTACK  = "this_attack"  # cleared after attack damage/defeat resolves
    THIS_ROUND   = "this_round"   # cleared at end of regroup
```

**Cleanup hooks**:
- `THIS_ATTACK`: removed at the end of `_resolve_unit_combat()` and `_resolve_base_attack()`,
  after all triggered abilities from that attack have resolved.
- `THIS_PHASE`: removed at ACTION→REGROUP and REGROUP→ACTION transitions.
- `THIS_ROUND`: removed at the end of the regroup phase (before ready-all step).
- `PERMANENT`: removed in `_defeat_unit()` when `source_instance_id` is the defeated card.

`GameState` gets a new field: `modifiers: list[Modifier] = field(default_factory=list)`.
This field round-trips through JSON as a list of dicts.

**Distinction**: `ConstantAbility` effects (§2.2) do NOT create Modifier records.
They are always re-evaluated dynamically. Only ability *effects* that create temporary
stat/keyword changes use the Modifier system.

---

## 6. Game Memory

A `GameMemory` dataclass tracks transient facts that card text references. Add fields only
as real starter-deck cards demand them. All fields clear at the appropriate boundary.

```python
@dataclass
class GameMemory:
    # Cleared at start of each action phase (REGROUP→ACTION)
    units_played_this_phase: dict[str, list[str]] = field(default_factory=dict)
    # player_id → [instance_ids played]

    units_defeated_this_phase: list[str] = field(default_factory=list)
    # [instance_ids] — needed for Emperor's Legion

    bases_damaged_this_phase: dict[str, bool] = field(default_factory=dict)
    # player_id (owner of the base) → bool — needed for Forced Surrender

    units_attacked_this_phase: set[str] = field(default_factory=set)
    # instance_ids — needed for Medal Ceremony

    # Cleared at each round start
    unique_units_defeated_this_round: set[str] = field(default_factory=set)
    # card_uids (not instance_ids) — needed for Agent Kallus once-per-round check
```

`GameState` gets: `game_memory: GameMemory = field(default_factory=GameMemory)`.
Round-trips through JSON as plain dicts/lists.

**How it's populated**: ability resolution functions (in the effect primitive implementations)
call helpers like `game_memory.units_played_this_phase[player_id].append(instance_id)`.
Phase/round transition hooks clear the relevant fields.

---

## 7. Trigger Resolution and Ordering

### 7.1 Collection

After each event fires through the `TriggerBus`, a new function:

```python
def collect_ability_triggers(state: GameState, event: GameEvent) -> list[TriggerSpec]:
```

scans all units in all arenas plus leaders in base_zone, finds all `TriggerAbility` specs
whose trigger condition matches the event, and returns them. Keyword triggers (Shielded,
Ambush) remain registered directly on the bus as before and are not affected.

### 7.2 Simultaneous Trigger Ordering (CR §7.5 — verify exact rule)

Per CR (verify section): when multiple abilities trigger from the same event:
1. If all triggers are from the same player: that player chooses the order.
2. If triggers are from both players: the initiative holder orders all of their own triggers;
   the other player orders theirs; then both sets interleave with initiative holder's
   triggers going first in the combined sequence.

Implementation:
- If only one trigger fires: push its resolution directly as `PendingDecision(kind="resolve_trigger")`.
- If multiple triggers from one player: push `PendingDecision(kind="order_triggers")` for that player.
- If multiple triggers from both players: two ordering decisions, initiative holder first.
- After ordering, push the triggers as resolution decisions in reverse order (LIFO) so the
  first in the chosen order resolves first.

### 7.3 Nesting

When a trigger resolves and its effects cause new events (e.g. a "When Played" effect defeats
a unit, firing "When Defeated"), the new triggers from that event are collected and pushed
onto the stack after the current effect completes. The stack naturally handles this.

**Critical test case**: A unit trade (both units deal lethal damage simultaneously). Both
`UnitDefeated` events fire. Any `WhenDefeated` triggers from BOTH units must be collected
together (they fired simultaneously) before any individual trigger resolves. Test this path
explicitly.

**AOE defeat simultaneity** (Superlaser Blast): defeat all units by collecting the full
set first, moving all to discard (zone changes only), emitting all `UnitDefeated` events,
then collecting and ordering all `WhenDefeated` triggers as a single simultaneous batch.
Do not interleave zone changes with trigger resolution.

### 7.4 New Decision Kinds

| Kind | Context keys | Who decides |
|------|-------------|-------------|
| `"trigger_option"` | `ability_key`, `source_id` | source card's controller |
| `"order_triggers"` | `trigger_keys: list[str]`, `for_player_id` | that player |
| `"resolve_trigger"` | `ability_key`, `source_id`, `event_snapshot` | — (auto-resolve, no choice needed; the resolution may push further decisions) |
| `"target"` | `spec_repr`, `effect_key`, `source_id`, `legal_target_ids: list` | chooser per spec |
| `"target_optional"` | same + `may_decline: True` | chooser per spec |

---

## 8. Card Ability Registry

### 8.1 File Layout

```
src/swu/abilities/
    __init__.py     # re-exports get_abilities(), card_ability()
    registry.py     # AbilitySpec types, primitives, TargetSpec, Condition, etc.
    sor.py          # SOR card definitions
    (future sets added here)
```

### 8.2 Registration Decorator

```python
# registry.py

_REGISTRY: dict[tuple[str, str], list[AbilitySpec]] = {}
_ESCAPE_HATCH: set[tuple[str, str]] = set()

def card_ability(set_code: str, card_number: str, escape_hatch: bool = False):
    def decorator(fn: Callable[[], list[AbilitySpec]]):
        _REGISTRY[(set_code, card_number)] = fn()
        if escape_hatch:
            _ESCAPE_HATCH.add((set_code, card_number))
        return fn
    return decorator

def get_abilities(set_code: str, card_number: str) -> list[AbilitySpec]:
    return _REGISTRY.get((set_code, card_number), [])
```

A card with no entry in `_REGISTRY` → `get_abilities()` returns `[]` → no ability effects fired
→ the card behaves exactly as it does today.

### 8.3 Engine Hooks

| Engine point | Existing code | New action |
|-------------|--------------|------------|
| `PlayCard` — unit enters play | `_put_unit_in_play()` → `UnitEntersPlay` fires | After bus fire: call `collect_ability_triggers(state, UnitEntersPlay)` for `WhenPlayed` |
| `PlayCard` — event card | Move to discard | Look up EventAbility, push effect resolution |
| `_defeat_unit()` | Move to discard, strip tokens | Fire `UnitDefeated`; collect `WhenDefeated` from defeated card and `WhenUnitDefeated` from all others |
| Attack pipeline (step 2) | Restore/Saboteur inline | Collect `OnAttack` triggers from attacker after `AttackDeclared` fires |
| Attack pipeline (after defeat check) | — | Collect `OnAttackDefeatsUnit` if applicable |
| `legal_actions()` — action phase | PlayCard, AttackWithUnit, Pass, etc. | Add `UseAbility(source_id, ability_index)` for each affordable `ActivatedAbility` on units/leaders in play |
| `compute_power(state, ci)` | Grit, Raid, upgrades | + scan modifiers (kind="power") + scan ConstantAbility records |
| `has_keyword(state, ci, kw)` | Native keywords | + scan modifiers (kind="keyword_grant"/"revoke") + scan ConstantAbility records |

### 8.4 Leaders — Both Sides

Leaders register one entry keyed to `(set_code, card_number)`. Abilities whose trigger
condition applies to both the undeployed and deployed state need no side discrimination —
`OnAttack()` fires whenever the leader is declared as attacker, regardless of deployment
state.

If a leader has abilities that apply only while deployed (i.e., unit-side abilities in the
`text` field, not in `deploy_box`), those trigger specs carry `deployed_only=True`. The
trigger collection skips them when the leader is in base_zone.

### 8.5 Escape Hatch

Register with `escape_hatch=True` for cards that cannot be expressed declaratively:

```python
@card_ability("SOR", "xxx", escape_hatch=True)
def some_card():
    return [CustomAbility(resolve_fn=_resolve_some_card)]
```

`CustomAbility.resolve_fn(state, source_ci, event) -> GameState` is an imperative function
that directly mutates a deepcopy of state. The audit script counts escape-hatch registrations.
Target: **zero** in the SOR starter decks.

---

## 9. Integration — Breaking Changes to Existing Engine

These changes are required before any card can be implemented. Note them carefully as they
touch existing tests.

### 9.1 `effective_hp()` and `is_defeated()` need state access

**Problem**: `CardInstance.effective_hp()` and `is_defeated()` currently only sum upgrade
HP. Once ConstantAbility stat modifiers exist (e.g. General Veers giving +1 HP to all
Imperial units), the "true" max HP depends on game state.

**Fix**: Add `compute_hp(state: GameState, ci: CardInstance) -> int` to `actions.py`
alongside the existing `compute_power()`. Audit every call to `ci.effective_hp()` and
`ci.is_defeated()` and replace with `compute_hp()` / `ci.damage >= compute_hp(state, ci)`.

`PlayerState.is_eliminated` reads `b.card_def.hp` (a base's HP is fixed — bases are not
modified by constant abilities in the starter decks, so this is safe to leave as-is for
Phase 3; flag for future).

### 9.2 Undeployed leader attack action

**Problem**: `AttackWithUnit` calls `_find_in_arenas()` which only looks in `ground_arena`
and `space_arena`. The leader in `base_zone` cannot currently be declared as attacker.

**Fix**: Add `AttackWithLeader` action (or extend `AttackWithUnit` to detect the leader
in base_zone). The undeployed leader may only attack the opponent's base, not units (verify
with CR). Its combat stats come from new `Leader` model fields (see §9.3).

In `legal_actions()`, offer `AttackWithLeader` when: the game is in ACTION phase, the leader
is in base_zone, not exhausted, and the leader has not been eliminated.

### 9.3 Undeployed leader stats not in DB

**Problem**: The DB `Leader.power` and `Leader.hp` fields store the **deployed unit** stats.
The **undeployed** leader has different printed stats (e.g. Luke: 2 power / 4 HP undeployed
vs. 4/7 deployed; Vader: 2/8 undeployed vs. 5/8 deployed — **verify against physical cards**).

**Fix**: Add `leader_power: int` and `leader_hp: int` fields to the `Leader` dataclass (the
deployed-side stats remain `power`/`hp`). Populate from a hardcoded mapping in the card ability
registry until the DB is updated. Example in `sor.py`:

```python
LEADER_UNDEPLOYED_STATS: dict[str, tuple[int, int]] = {
    "005": (2, 4),   # Luke — verify against physical card
    "010": (2, 8),   # Vader — verify against physical card
}
```

### 9.4 `WhenDefeated` — SELF reference after zone change

When a `WhenDefeated` ability fires, the source card has already moved to discard. Effects
referencing `fixed=SELF` must locate the card by `instance_id` in the discard pile. The
ability resolution context carries the `source_instance_id` and the `owner_id` so effects
can find it. Verify that `find_instance()` (which already searches all zones) handles this.

### 9.5 `compute_power()` / `has_keyword()` must scan ConstantAbility records

Each call to `compute_power(state, ci)` must:
1. Apply existing Grit/Raid/upgrade logic (unchanged).
2. Scan `state.modifiers` for records targeting `ci`.
3. Scan all in-play cards for `ConstantAbility` specs; if `ci` matches the spec's target and
   the condition is met, apply the stat/keyword effect.

Step 3 is O(N×M) (cards in play × cards in play). For a 2-player game with ~20 units this
is fine; no optimization needed in Phase 3.

---

## 10. Paper Dry-Run — 10 Cards

Each card: the would-be definition, a resolution trace, and issues found.

---

### Card 1 — Death Trooper (SOR #033)

**Card**: Unit · Cost 3 · 3/3 · Ground · Villainy  
**Text**: "When Played: Deal 2 damage to a friendly ground unit and 2 damage to an enemy ground unit."

**Definition**:
```python
@card_ability("SOR", "033")
def death_trooper():
    return [
        TriggerAbility(
            trigger=WhenPlayed(),
            optional=False,
            effects=[
                DealDamage(amount=2, target=TargetSpec(
                    controller="friendly", kind="unit", arena="ground",
                )),
                DealDamage(amount=2, target=TargetSpec(
                    controller="enemy", kind="unit", arena="ground",
                )),
            ],
        ),
    ]
```

**Resolution trace**:
Player A plays Death Trooper into ground arena. `_put_unit_in_play()` runs. `UnitEntersPlay`
fires → Shielded/Ambush bus listeners check (neither applies). Then `collect_ability_triggers`
finds `WhenPlayed`. Mandatory trigger: no `trigger_option` decision.

Two effects need targets. Push decisions in reverse LIFO order:
- Push enemy-unit decision (resolves second)
- Push friendly-unit decision (resolves first)

Player A picks a friendly ground unit → deal 2 damage (Shield intercept checked). Stack pops.
Player A picks an enemy ground unit → deal 2 damage. Stack pops. Turn switches to B.

**Fizzle path**: If no enemy ground unit exists, second DealDamage has no legal targets →
effect does nothing. First DealDamage still resolves (partial resolution applies).
Test this explicitly.

**Issues found**: None.

---

### Card 2 — Superlaser Technician (SOR #083)

**Card**: Unit · Cost 3 · 2/1 · Ground · Villainy  
**Text**: "When Defeated: You may put this unit into play as a resource and ready it."

**Definition**:
```python
@card_ability("SOR", "083")
def superlaser_technician():
    return [
        TriggerAbility(
            trigger=WhenDefeated(),
            optional=True,
            effects=[
                ResourceCard(target=TargetSpec(fixed=SELF)),
                # ResourceCard moves the card from its current zone (discard) to resources,
                # face-down, exhausted=False. The instance remains in play as a resource.
            ],
        ),
    ]
```

**Note**: No separate `ReadyCard` is needed — `ResourceCard` places the card in resources
in a ready state (exhausted=False) by definition.

**Resolution trace**:
Superlaser Technician is defeated (e.g. in combat). `_defeat_unit()` moves it to discard,
emits `UnitDefeated`. `WhenDefeated` trigger fires. Optional → push `trigger_option`.
Player A says yes → `ResourceCard(fixed=SELF)` resolves: locate the Technician in discard
(by instance_id from event context), move it to `ps.resources`, set `face_down=True`,
`exhausted=False`, `zone=Zone.RESOURCES`. The card is now a ready resource.

**Key design requirement**: The `WhenDefeated` ability resolution context must carry the
`source_instance_id` and `source_owner_id`. Effects using `fixed=SELF` resolve to
`state.find_instance(source_instance_id)` which searches all zones including discard.

**Issues found**: SELF reference after zone change — documented in §9.4. No new issues.

---

### Card 3 — 2-1B Surgical Droid (SOR #059)

**Card**: Unit · Cost 1 · 1/3 · Ground · Vigilance  
**Text**: "On Attack: You may heal 2 damage from another unit."

**Definition**:
```python
@card_ability("SOR", "059")
def surgical_droid():
    return [
        TriggerAbility(
            trigger=OnAttack(),
            optional=True,
            effects=[
                Heal(amount=2, target=TargetSpec(
                    controller="any", kind="unit",
                    predicates=("not_self",),
                    optional=False,  # if player chose to use the ability, they must pick a target
                )),
            ],
        ),
    ]
```

**Resolution trace**:
2-1B Surgical Droid attacks an enemy base. `AttackDeclared` fires. `collect_ability_triggers`
finds `OnAttack`. Optional → push `trigger_option`. Player says yes → push `target` decision:
any unit, not self. Player picks a target (could be any unit on the board, any player's).
Heal(2) applied to chosen unit. Trigger fully resolved. Attack damage then resolves normally.

**CR check**: Confirm with CR §Attacks that on-attack triggers resolve **before** combat
damage is assigned. The existing code already handles Restore (heals base) and Saboteur
as pre-damage on-attack steps — this new trigger sits in the same window.

**Issues found**: None.

---

### Card 4 — General Veers (SOR #230)

**Card**: Unit · Cost 3 · 3/3 · Ground · Command/Villainy  
**Text**: "Other friendly Imperial units get +1/+1."

**Definition**:
```python
@card_ability("SOR", "230")
def general_veers():
    return [
        ConstantAbility(
            target=TargetSpec(
                controller="friendly",
                kind="unit",
                traits=("Imperial",),
                predicates=("not_self",),
            ),
            effects=[StatBonus(power=1, hp=1)],
        ),
    ]
```

**Resolution**: No event fires. Every call to `compute_power(state, ci)` for a friendly
Imperial unit (not Veers) checks: is Veers in play and owned by the same player? If yes: +1.
Every call to `compute_hp(state, ci)` for the same units: +1. If Veers is defeated, the
constant ability disappears from the next `compute_power` call — no cleanup needed.

**Issue found — breaking change**: `compute_hp(state, ci)` does not yet exist. The current
`ci.effective_hp()` only sums upgrade HP. After this change, `is_defeated(state)` depends
on `compute_hp(state, ci)` — see §9.1 for the full fix.

---

### Card 5 — Vigilant Honor Guards (SOR #048)

**Card**: Unit · Cost 5 · 4/6 · Ground · Heroism/Vigilance  
**Text**: "While this unit is undamaged, it gains Sentinel."

**Definition**:
```python
@card_ability("SOR", "048")
def vigilant_honor_guards():
    return [
        ConstantAbility(
            target=TargetSpec(fixed=SELF),
            condition=Condition.SOURCE_UNDAMAGED,
            effects=[KeywordGrant(keyword="Sentinel")],
        ),
    ]
```

**Resolution**: `has_keyword(state, honor_guards_ci, Keyword.SENTINEL)` is called. Framework
checks ConstantAbility records: Vigilant Honor Guards has one. Target = SELF → matches.
Condition = `SOURCE_UNDAMAGED` → `honor_guards_ci.damage == 0` → True or False.
If True, Sentinel is granted. If any damage is on the unit, Sentinel is absent. No Modifier
record is created; this is fully dynamic.

**Issues found**: Needs typed `Condition` atoms (not strings) — documented in §2.2.
Interaction with existing Sentinel targeting in `legal_actions()` works automatically since
`has_keyword()` will return the correct value.

---

### Card 6 — Vanquish (SOR #078)

**Card**: Event · Cost 5 · Heroism  
**Text**: "Defeat a non-leader unit."

**Definition**:
```python
@card_ability("SOR", "078")
def vanquish():
    return [
        EventAbility(
            effects=[
                DefeatUnit(target=TargetSpec(
                    controller="any",
                    kind="unit",
                    predicates=("non_leader",),
                )),
            ],
        ),
    ]
```

**Resolution**: Player A plays Vanquish (cost 5). Event moves to discard. `EventAbility`
resolves: one target needed. Push `target` decision: any non-leader unit. Player picks target.
`DefeatUnit` calls `_defeat_unit(state, owner_ps, target_ci)`. `UnitDefeated` fires. Any
`WhenDefeated` or `WhenUnitDefeated` triggers collected and pushed. Turn switches to B after
all decisions clear.

**Fizzle**: If no non-leader units exist anywhere, `DefeatUnit` has no legal targets →
ability fizzles. Player still spent the 5 resources.

**Issues found**: `predicates=("non_leader",)` needs clear definition — a Leader in an
arena (`ci.card_def` is `Leader` and `ci.deployed == True`) must be filtered out.
`"non_leader"` predicate: `not isinstance(ci.card_def, Leader)`.

---

### Card 7 — Superlaser Blast (SOR #043)

**Card**: Event · Cost 8 · Villainy  
**Text**: "Defeat all units."

**Definition**:
```python
@card_ability("SOR", "043")
def superlaser_blast():
    return [
        EventAbility(
            effects=[
                DefeatAllUnits(filter=TargetSpec(controller="any", kind="unit")),
            ],
        ),
    ]
```

**`DefeatAllUnits` resolution** (special primitive, not a loop):
1. Collect all units in both arenas for both players that match `filter` (including deployed
   leaders — they are units; the filter `kind="unit"` includes them).
2. Perform zone changes for all collected units simultaneously: each moves to its owner's
   discard, tokens are stripped, regular upgrades detach.
3. Emit `UnitDefeated` for each.
4. Collect all `WhenDefeated` triggers from all defeated cards, and all `WhenUnitDefeated`
   triggers from any survivors.
5. Push ordering decision for the combined simultaneous trigger batch (§7.2).

**Why a dedicated primitive**: This ensures simultaneity. If implemented as a `ForEach` loop,
the first unit's `WhenDefeated` trigger would fire and potentially resolve before the second
unit's zone change, creating incorrect ordering. The CR requires simultaneous defeat to be
treated as a single event.

**Issues found**: Need to decide whether deployed leaders count as "units" for Superlaser
Blast. Per CR, leader units ARE units — they should be defeated by "defeat all units." Verify
with CR and physical card. If yes, the defeated leader should return to base_zone with
`epic_action_spent=True` (existing behavior in `_defeat_unit` already handles this for leaders).

---

### Card 8 — Luke Skywalker, Faithful Friend (SOR #005, Leader)

**Undeployed deploy_box**: "On Attack: You may give another unit a Shield token."  
**Deployed unit**: 4/7 · Ground · Heroism  
**Deployed ability**: Same as undeployed ("On Attack: You may give another unit a Shield token.")

**Undeployed stats**: 2 power / 4 HP — **NOT in DB; must be added manually.** See §9.3.

**Definition**:
```python
@card_ability("SOR", "005")
def luke_faithful_friend():
    return [
        TriggerAbility(
            trigger=OnAttack(),  # fires whether deployed or not
            optional=True,
            effects=[
                GiveToken(token_type="Shield", target=TargetSpec(
                    controller="any",
                    kind="unit",
                    predicates=("not_self",),
                )),
            ],
        ),
    ]
```

**Resolution trace (undeployed)**:
Player A takes `AttackWithLeader` action (new action type — §9.2). Luke (in base_zone,
2/4) exhausts and attacks opponent's base. `AttackDeclared` fires. `collect_ability_triggers`
finds `OnAttack` trigger. Optional → push `trigger_option`. Player says yes → push `target`
decision: any unit, not Luke himself. Player picks any unit (friendly or enemy, any arena).
`GiveToken("Shield", target)` → `attach_token(state, owner_ps, target_ci, "Shield")`.
Trigger resolves. Then base-attack damage resolves (Luke deals 2 damage to opponent's base).

**Deployed**: Identical flow, except Luke is in the ground arena and can attack units or the
base via `AttackWithUnit`.

**Issues found**: `AttackWithLeader` action does not yet exist (§9.2). Undeployed stats not
in DB (§9.3). Both must be implemented before this card test can pass.

---

### Card 9 — Darth Vader, Dark Lord of the Sith (SOR #010, Leader)

**Undeployed deploy_box**: "On Attack: You may deal 2 damage to a unit."  
**Deployed unit**: 5/8 · Ground · Villainy  
**Deployed ability**: Same as undeployed.

**Undeployed stats**: 2 power / 8 HP — **NOT in DB; must be added manually.**

**Definition**:
```python
@card_ability("SOR", "010")
def darth_vader_dark_lord():
    return [
        TriggerAbility(
            trigger=OnAttack(),
            optional=True,
            effects=[
                DealDamage(amount=2, target=TargetSpec(
                    controller="any",
                    kind="unit",
                )),
            ],
        ),
    ]
```

**Note**: "a unit" has no controller restriction — Vader may target any unit (friendly or
enemy). Shields are checked for the chosen target.

**Resolution trace (deployed)**:
Vader (deployed, ground arena, 5/8) attacks an enemy unit. `AttackDeclared` fires.
`OnAttack` trigger fires. Optional → `trigger_option`. Player says yes → `target` decision:
any unit. Player picks a unit (could be the current defender, a different unit, or a
friendly unit). DealDamage(2) resolves → Shield check on target → damage applied.
Then combat damage between Vader and the original defender resolves.

**Issues found**: Same as Luke — `AttackWithLeader` needed for undeployed Vader. Also note:
the DealDamage effect triggers its own damage events. If the chosen target is defeated by the
2 damage, `UnitDefeated` fires and any WhenDefeated triggers are collected. This must nest
correctly without disrupting the ongoing attack.

---

### Card 10 — Gideon Hask (SOR #036)

**Card**: Unit · Cost 5 · 5/5 · Ground · Villainy  
**Text**: "When an enemy unit is defeated: Give an Experience token to a friendly unit."

**Definition**:
```python
@card_ability("SOR", "036")
def gideon_hask():
    return [
        TriggerAbility(
            trigger=WhenUnitDefeated(
                filter=TargetSpec(controller="enemy", kind="unit"),
                # "enemy" is relative to Gideon's owner, evaluated at trigger-collection time
            ),
            optional=False,
            effects=[
                GiveToken(token_type="Experience", target=TargetSpec(
                    controller="friendly",
                    kind="unit",
                )),
            ],
        ),
    ]
```

**Resolution trace**:
Player A's unit defeats Player B's unit. `UnitDefeated` fires for Player B's unit.
`collect_ability_triggers` checks all in-play cards. Gideon Hask (Player B's card in play)
has `WhenUnitDefeated(filter={controller="enemy"})`. From Gideon's perspective (owner = B),
the defeated unit (owned by B) is... wait — the defeated unit is B's unit. From Gideon's
perspective, B's units are "friendly", A's units are "enemy". So this trigger fires when
**A's** (enemy from Gideon's perspective) unit is defeated.

If Player **A** had a Gideon Hask and Player **B**'s unit was defeated: from A's Gideon,
B's unit is "enemy" → trigger fires. Correct.

**Trigger-collection perspective**: `filter.controller` is evaluated relative to the source
card's `owner_id`. The collection function must pass `source.owner_id` as the reference
player when evaluating the filter.

**Simultaneous trigger test**: If Player A and Player B each have a Gideon Hask in play,
and a unit from each player is defeated simultaneously (e.g. a combat trade), both Gideons
trigger simultaneously from the same `UnitDefeated` events. Push ordering decisions for both
players. This directly tests the simultaneous-trigger-from-both-players path.

**Issues found**: Perspective tracking in `collect_ability_triggers` — the function must know
which player owns each source card to evaluate "enemy/friendly" in the trigger filter.
Straightforward: `filter.controller` is evaluated as: if `"enemy"`, the defeated unit's
`owner_id != source.owner_id`; if `"friendly"`, `owner_id == source.owner_id`.

---

## 11. Summary of Issues Found in Dry-Run

These must be resolved in the framework design before implementation begins:

| # | Issue | Impact | Fix |
|---|-------|--------|-----|
| 1 | `compute_hp(state, ci)` doesn't exist | All ConstantAbility HP buffs, is_defeated checks | Add to `actions.py`; update all `effective_hp()` call sites |
| 2 | `is_defeated(state)` needs state | Several paths in actions.py | Either add state param or route through `compute_hp()` inline |
| 3 | Undeployed leader can't attack | Luke/Vader undeployed abilities | Add `AttackWithLeader` action |
| 4 | Undeployed leader stats not in DB | Luke, Vader (and all leaders) | Add `Leader.leader_power` / `Leader.leader_hp` fields; populate from ability registry initially |
| 5 | SELF reference after WhenDefeated zone change | Superlaser Technician | Resolution context carries `source_instance_id`; `find_instance()` searches discard |
| 6 | Condition predicates must be typed atoms | LLM-generability | Use `Condition` enum, not strings |
| 7 | `DefeatAllUnits` simultaneity | Superlaser Blast correctness | Dedicated primitive, defer trigger collection until all zone changes complete |
| 8 | `"non_leader"` predicate semantics | Vanquish | `not isinstance(ci.card_def, Leader)` |
| 9 | Trigger filter perspective | Gideon Hask, all `WhenUnitDefeated` triggers | `collect_ability_triggers` passes `source.owner_id` to resolve "friendly/enemy" |
| 10 | `DefeatAllUnits` and deployed leaders | Superlaser Blast scope | Verify with CR whether leader units are defeated; they likely are |

---

## 12. Scope Notes — What Stays Deferred

The following are explicitly **not** in Phase 3 even though the brief mentioned some of them:

| Feature | Reason deferred |
|---------|----------------|
| Smuggle | Not in SOR starter decks. Remains in CLAUDE.md deferred list. |
| Hidden, Piloting, Bounty, Coordinate, Plot, Support | Not in SOR starter decks. |
| "Choose two" / modal events (Vigilance, Command, Aggression, Cunning) | Not in SOR starter decks. |
| SearchDeck / deck-reveal abilities | Not in SOR starter decks (verify Search Your Feelings). |
| TakeControl (Change of Heart) | Not in starters. |
| Self-modifying event costs (Bamboozle, Force Choke discount) | Not in starters. |
| Token unit creation (TIE Fighters, etc.) | Not in starters. |
| Replacement effects beyond Shield | None expected in starters. |
| "Exact damage equal to X" where X is a computed board quantity requiring iteration | Implement only if a starter card requires it. |

**Note on Resupply (SOR #126)**: "Put this event into play as a resource." If in the
starter decks, this is achievable via `ResourceCard(target=SELF)` on an `EventAbility`.

---

## 13. Order of Work (Phase 3)

1. **This document** — reviewed and approved. [STOP]
2. Fetch authoritative SOR starter decklists → show to user for confirmation. [STOP]
3. Framework core implementation:
   - `AbilitySpec` types, TargetSpec, Condition atoms, Duration, Modifier, all primitives in `registry.py`
   - `compute_hp(state, ci)` added to `actions.py`; `effective_hp()` call sites updated
   - `AttackWithLeader` action added
   - `Leader.leader_power` / `leader_hp` fields added
   - `collect_ability_triggers()` function
   - New `PendingDecision` kinds wired into `legal_actions()` and `apply()`
   - Modifier cleanup hooks at phase/round transitions
   - `GameMemory` added to `GameState`
   - Full test suite against synthetic cards (no real card definitions yet)
4. Implement common cards, batch by batch, commons first. Full test suite between batches.
5. Leaders last.
6. Golden scenarios + soak.
7. Audit rerun, CLAUDE.md update.
