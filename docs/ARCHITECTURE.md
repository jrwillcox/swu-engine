# Architecture

How the engine is put together, and the invariants everything else relies on.
For the reusable engine patterns and decision kinds, see
[`engine_seams.md`](engine_seams.md).

## The two-function contract

```python
legal_actions(state: GameState) -> list[Action]      # never empty while the game is live
apply(state: GameState, action: Action) -> GameState # raises IllegalActionError if not legal
```

Everything is an `Action` — playing a card, attacking, a mulligan keep/redraw, a
regroup resource choice, choosing a target mid-resolution. There is no side
channel and no second way to change the game.

Two consequences worth naming, because the rest of the system leans on them:

- **The client cannot cheat.** `swu.web.session` hands the browser opaque action
  ids drawn from `legal_actions`, so an illegal move is not something the front
  end is able to express, let alone send.
- **The bots are simple.** A bot is a pure function from a redacted view plus the
  enumerated legal actions to a choice. It needs no rules knowledge of its own,
  which is what makes the heuristic safe as a universal fallback.

### Mutation

`apply()` calls `copy.deepcopy(state)` before touching anything. The input state
is **never** modified — enforced by `test_immutability_of_apply`.

`CardDef` objects (the frozen dataclasses in `cards/models.py`) implement
`__deepcopy__` to return `self`, so they are shared across every copy. Only the
mutable wrappers — `CardInstance`, `PlayerState`, `GameState` — are deep-copied.
That is what keeps a per-action deepcopy affordable.

### Determinism

All randomness comes from `state.make_rng()`, which builds a `random.Random` from
`state.rng_state`; the new state stores `rng.getstate()` back. Same seed plus the
same action sequence gives a byte-identical game, which is what makes soak
failures replayable (`scripts/replay.py`) and shrinkable (`scripts/shrink.py`).
Enforced by `test_determinism`.

## State model

### CardDef vs CardInstance

| | |
|---|---|
| **`CardDef`** (`cards/models.py`) | Immutable, loaded from the database, shared across state copies. `Unit`, `Leader`, `Base`, `Event`, `Upgrade`. |
| **`CardInstance`** (`engine/state.py`) | The mutable wrapper: `instance_id`, `owner_id`, `zone`, `exhausted`, `damage`, `face_down`, `deployed`, `epic_action_spent`, `attached_upgrades`. |

### Phase flow

```
SETUP_MULLIGAN → SETUP_RESOURCES → ACTION → REGROUP → ACTION → REGROUP → …
```

Setup phases run sequentially (player 0, then player 1) — a simplification of the
real simultaneous decision that does not affect outcomes.

In the action phase, a player who passes or claims initiative joins
`passed_players` and acts no more that phase; the phase ends when both have. In
regroup, both players draw 2 automatically during the transition, then each
chooses to resource a card or skip, initiative holder first.

### Card conservation

Use `GameState.all_instances_for_player(player_id)` — it searches every zone
**including upgrades attached to an opponent's units**. `PlayerState.all_instances()`
misses cross-player attachments and must not be used for conservation checks.
Enforced by `test_card_conservation_across_game` and the soak oracle.

### Serialisation

`state.to_json()` / `GameState.from_json(data)` round-trip the full state. The
event log is deliberately not restored — replay re-runs the actions instead.
`PlayerView.to_json()` is the compact, redacted form.

## The ability framework

The central idea: **cards are data**. A card ability is a declaration composed
from a fixed vocabulary, not a function.

```
registry.py        the vocabulary  — ability specs, effects, targets, conditions, durations
    │                               and the @card_ability(set, number) registry
    ▼
cards/<set>/abilities.py   the declarations — 2,176 cards, 0 escape hatches
    │
    ▼
resolver.py        the interpreter — turns a spec into state changes, pushing
                                     decisions when a player must choose
```

The four ability kinds mirror the game's own rules text:

| Card text | Spec |
|---|---|
| "When Played:", "When this unit enters play:" | `TriggerAbility(trigger=WhenPlayed(), …)` |
| "On Attack:" | `TriggerAbility(trigger=OnAttack(), …)` |
| "When Defeated:" | `TriggerAbility(trigger=WhenDefeated(), …)` |
| A static, always-on effect | `ConstantAbility(target=…, effects=[StatBonus(…), KeywordGrant(…)])` |
| "Action [cost]:" | `ActivatedAbility(costs=[…], effects=[…])` |

Effects (`DealDamage`, `GiveToken`, `DrawCards`, `ModifyStats`, `GrantKeyword`,
`ReturnToHand`, …) compose with a `TargetSpec` describing *what* may be chosen and
a `Condition` describing *when* the ability applies. `src/swu/cards/sor/abilities.py`
is the smallest full set and the best file to read first.

**The escalation rule.** If a card cannot be expressed in the existing
vocabulary, the answer is to stop and design a new primitive in its own session —
never to reach for bespoke per-card logic. That discipline is why the
`escape_hatch=True` opt-out exists and why nothing uses it. See
[`methodology.md`](methodology.md).

### Mid-resolution choices

Abilities frequently need input partway through resolving ("deal 2 damage to a
unit" — which one?). `engine/decisions.py` holds a **decision stack**: resolution
suspends, a `PendingDecision` is pushed, `legal_actions` offers exactly the legal
choices, and the chosen action resumes resolution. Turn alternation is suspended
while the stack is non-empty.

## Correctness machinery

- **`engine/invariants.py`** — 17 invariants checked after every action in soak
  mode: card conservation by instance identity, zone/tag consistency,
  decision-stack wellformedness, semantic modifier expiry (no `this_attack`
  modifier surviving a settled state), terminal quiescence, periodic
  `from_json(to_json(state))` equality, and **hidden-information leak detection** —
  it serialises `view_for(player)` and string-scans the JSON to prove the
  opponent's hand and deck never appear.
- **`tests/test_hypothesis_engine.py`** — a Hypothesis `RuleBasedStateMachine`
  that drives whole games one legal action at a time, running that same oracle
  after every move and shrinking any failure to a minimal reproducer.
- **`scripts/soak.py`** — the campaign runner: thousands of bot-vs-bot games,
  writing a replayable failure bundle on any invariant break.

## Information hiding

`engine/views.py` builds a `PlayerView`: the state as one player may see it, with
the opponent's hand and deck reduced to counts. The front end renders only this,
and the leak-detection invariant exists to keep it honest.

## Web layer

```
React (web/src)  ──HTTP──►  FastAPI (src/swu/web)  ──►  engine
   renders PlayerView          session.py: opaque       legal_actions / apply
   animates the event log      action ids, drives
                               the bot seat
```

The front end knows **no game rules**. It renders the redacted view, shows the
legal actions the backend assigned, and animates the event stream the engine
emits — the event log doubles as the animation script.

## Reading the code

Roughly in dependency order:

1. `engine/state.py` — the state model and serialisation
2. `engine/actions/` — the contract and every action (`base.py` for the `Action`
   ABC, `api.py` for `legal_actions`/`apply`, then one module per mechanic)
3. `engine/decisions.py` — mid-resolution player input
4. `abilities/registry.py` — the card DSL
5. `abilities/resolver.py` — how specs become state changes
6. `cards/sor/abilities.py` — the smallest full set, as a worked example
7. `engine/invariants.py` — the correctness oracle
8. `engine/views.py` — information hiding
9. `players/heuristic_bot.py` — the bot, with its design rationale at the top
10. `web/app.py` and `web/session.py` — the HTTP surface

### A note on file size

`engine/actions.py` was a single ~25,000-line module, grown a labelled section at
a time across the encoding campaign. It is now the layered 24-module package
described in the [README](../README.md#engineactions--layered-not-one-file), split
as provable text motion rather than as a rewrite. The `push_* / _finish_* /
_*_actions` triplet per decision kind survived the move unchanged; what changed is
that each triplet now lives in the module for its mechanic, and the decision kinds
are claimed from a dispatch table instead of resolved by a 601-line `if
top.kind == "…"` chain.

The per-set `cards/*/abilities.py` files are large for a different and less
interesting reason: they are data.

## Adding things

**A keyword:** add it to the `Keyword` enum in `engine/keywords.py`; add tests in
`tests/test_keywords.py`; for enter-play triggers add a listener in
`keyword_triggers.py` registered on `UnitEntersPlay`; for attack-time effects add
it to the right CR step in `_resolve_unit_combat`.

**An action type:** define the `Action` subclass in the `engine/actions/` module
for its mechanic — **with the handler that emits it**, not in a module named after
the card that motivated it; offer it from `legal_actions()` under the right phase
guard; implement `apply()` (deepcopy first); emit a typed `GameEvent` through the
bus; add the name to the facade's `__all__`; test it. If it introduces a decision
kind, register that kind with `register_decisions({...})` in the same module — a
module-scope call, and the row must live beside its handler, because a row naming
a handler that has moved away fails silently.

**A zone:** add it to the `Zone` enum, add the field to `PlayerState`, and update
`all_instances()`, `all_instances_for_player()` and the JSON helpers together —
conservation checks depend on all four agreeing.

**A card:** follow [`encoding_guide.md`](encoding_guide.md). Never string-match
card text at the point of use; query the keyword layer.
