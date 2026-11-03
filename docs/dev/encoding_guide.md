# Encoding cards

How to make a card playable. Every card in the current database is encoded; this
guide is for new sets and for fixing existing encodings. For a new release, start
with [`new_releases.md`](new_releases.md).

Reuse what exists: [`engine_seams.md`](engine_seams.md) lists the patterns and
decision kinds, and `src/swu/abilities/registry.py` defines the full vocabulary
(effects, `TargetSpec`, `Condition`, durations, costs).

## Workflow

| Step | Command |
|---|---|
| Find gaps | `python scripts/audit_coverage.py` (whole DB, writes `docs/coverage_report.md`) or `--deck tests/fixtures/<deck>.json` |
| Plan | `python scripts/plan_encoding.py --set <CODE>` (or `--deck …`) groups the gaps into ordered specs under `encoding/<slug>/` |
| Pick the next group | `python scripts/next_group.py --n N`, or the `/encode-next [N]` skill, which runs the whole loop |
| Verify a group | `python scripts/verify_encoding.py <slug> --group NN` |
| Ship a deck | `python scripts/verify_encoding.py <slug> --graduate` (100% playable, suites green, clean soak) |

The planner is offline and deterministic. Each spec file is self-contained: card
text, analysis, suggested primitives and acceptance criteria. Groups that need a new
primitive are flagged as escalations; see
[the escalation rule](engine_seams.md#the-escalation-rule).

Reprints of an encoded card need no work: `src/swu/cards/reprints.py` aliases them.
Check with `python scripts/find_reprints.py --check`.

## Recipe

### 1. Read the card text

```python
import sqlite3
con = sqlite3.connect("data/swu.db")
con.row_factory = sqlite3.Row
row = con.execute(
    "SELECT name, text, deploy_box FROM cards WHERE set_code=? AND card_number=?",
    ("SOR", "59"),
).fetchone()
```

`text` holds a unit's or event's rules; `deploy_box` holds a leader's. Some rows
contain non-breaking spaces (`\xa0`); treat them as spaces.

### 2. Choose the spec

| Card text | Spec |
|---|---|
| "When Played:" | `TriggerAbility(trigger=WhenPlayed(), …)` |
| "On Attack:" | `TriggerAbility(trigger=OnAttack(), …)` |
| "When Defeated:" | `TriggerAbility(trigger=WhenDefeated(), …)` |
| "When this unit defeats a unit" | `TriggerAbility(trigger=OnAttackDefeatsUnit(), …)` |
| An always-on effect | `ConstantAbility(target=…, effects=[StatBonus(…) or KeywordGrant(…)])` |
| "Action [cost]:" | `ActivatedAbility(costs=[…], effects=[…])` (`epic=True` for an Epic Action) |
| An event's text | `EventAbility(effects=[…])` |
| Logic the vocabulary can't express | `CustomEffect(fn=…)` inside any spec's `effects` |

Pure-keyword cards (Grit, Raid, Sentinel, …) need no registration: the keyword
layer handles them.

### 3. Register it

Add a function to `src/swu/cards/<set>/abilities.py`:

```python
@card_ability("SOR", "59")
def _2_1b_surgical_droid():
    """On Attack: You may heal 2 damage from another unit."""
    return TriggerAbility(
        trigger=OnAttack(),
        effects=[Heal(2, TargetSpec(controller="any", kind="unit",
                                    predicates=("not_self",)))],
        optional=True,
    )
```

- The key is the DB's `(set_code, card_number)` string, not zero-padded.
- Return one spec or a list. Name the function after the card; it is never called
  directly.
- A new set module must be imported in `src/swu/cards/__init__.py`.

**Targets.** `TargetSpec` filters by `controller`, `kind`, `arena`, `traits`,
`aspects`, cost and HP bounds and `predicates`. Use `fixed=SELF`, `ATTACKER`,
`DEFENDER` or `EACH_FRIENDLY`/`EACH_ENEMY`/`EACH_IN_PLAY` to skip the choice.

**Costs** for activated abilities: `ExhaustSelf()`, `PayResources(n)`,
`DefeatSelf()`, `UseForce()`, `DiscardCardCost()`.

**Leaders** put both sides in one list, gated with `undeployed_only=True` and
`deployed_only=True`. A leader's own keywords live in `deploy_box`, not `text`. The
deploy threshold is parsed from the epic-action text ("you control N or more
resources"); a leader with any other deploy condition registers a `DeployCondition`
marker, which `_leader_deploy_allowed` reads instead.

**Constant abilities** take only `StatBonus` and `KeywordGrant` effects. They are
read live by `compute_power` and `has_keyword`, so nothing needs to start or stop
them.

### 4. `CustomEffect` rules

```python
def my_effect(state, source_ci, target_id, event_ctx) -> GameState:
    ...  # state is already a copy: mutate it and return it
    return state
```

- Don't `deepcopy` inside it; the resolver already has.
- Give it a `target=TargetSpec(...)` to have the player choose; the choice arrives
  as `target_id`. Without one, `target_id` is `None` and the function must cope.
- Randomness only via `rng = state.make_rng()` then `state.rng_state = rng.getstate()`.
  Modifier ids only via `state.alloc_modifier_id(prefix)`. Global `random` or `uuid`
  breaks deterministic replay.
- `escape_hatch=True` on the decorator marks an ability that is genuinely
  irreducible. None are in use; treat needing one as an escalation.

### 5. Test it

Add a test to `tests/test_<set>_cards.py`, using the helpers in
`tests/test_sor_cards.py` (`_get_card`, `_make_state`, `_place`,
`_fire_when_played`, …) and the `repo` fixture. Assert through `legal_actions` and
`apply`, not internals.

**Put the set and number in every test method name** (e.g. `test_shd_64_moves_upgrade`).
`verify_encoding.py` selects tests with `-k <number>`, so a test without the number
is silently skipped.

Then run the group's `VERIFY:` command, and the fast suite before committing.

## Gotchas

- **`(set_code, card_number)` is not unique.** Leaders share low numbers with
  tokens. The DB `id` is the true key; when resolving a (set, number), prefer the
  non-token row (`audit_coverage.index_by_set_number` does).
- **"Playable" has one definition**: `audit_coverage.has_functional_text`. The
  audit, planner, verifier and coverage tests all use it.
- **`state.find_instance` reaches the discard pile** but not a defeated token. Test
  "defeated this way" against the arena.
- **`compute_power` floors at 0**, so a debuff can't be measured below zero.
- **Assert costs and ramp as deltas.** `_play_event_from_hand` gives resources, and
  `_make_state`'s bases have no aspects.

## Rules notes

The Comprehensive Rules are the authority (not redistributed; download from
<https://starwarsunlimited.com/rules>). Rulings the engine depends on:

- Units enter play exhausted, except Ambush units and a deployed leader, which
  enters ready.
- Drawing from an empty deck deals 3 damage per missing card to your own base.
- A defeated leader returns to its base zone undamaged and can't redeploy.
- The aspect penalty is +2 per unmatched aspect icon, duplicates counted.
