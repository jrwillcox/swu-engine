# Design note — `WhenYouUseForce` observer trigger (Stage 4 batch 17)

## Leverage ranking (one line)

The iterative-encode phase is over; the two remaining single-group *new-observer*
cards are the top of the roadmap. Ranking the remaining primitives by groups
cleared / new primitive: **all remaining options clear exactly 1 group each**
(confirmed by scanning `needs_encoding` — "when you use the Force" hits only Yoda
LOF_101; "second card each phase" only Ki-Adi TWI_64). Tie-break 1 (smallest
engine surface / closest mirror) picks **Yoda LOF_101 — a `WhenYouUseForce`
observer**, an *exact* mirror of the `WhenYouDraw` ledger+settle observer built
last session (batch 16) that reuses the existing Force-token machinery
(qui-gon-jinn:06). Ki-Adi's "opponent's 2nd card each phase" would need a NEW
per-phase play counter (a further seam), so it loses the tie-break.

## The two cards the primitive serves

- **Yoda LOF_101** (Unit 5/9, cost 8) — canonical.
  - "When Played: You may use the Force. If you do, heal 5 damage from a base."
  - "When you use the Force: You may deal damage to a unit equal to twice the
    number of units you control."
  - Rules box: "Using the Force for Yoda's 'When Played' ability triggers his
    second ability."
- Siblings (same printed face): **J25_11**, **LOFP_6**.

## Why ONE primitive (not two)

The card's first ability is already expressible with the existing Force-token
primitive (an optional `WhenPlayed` gated by `CONTROLLER_HAS_FORCE_TOKEN` whose
`CustomEffect` spends the token and heals — the Infused Brawler LOF_156 pattern).
The *only* new thing is the **`WhenYouUseForce` observer** for the second ability.
The observer's second ability payoff ("damage equal to twice the units you
control") reuses the existing `DealDamageEqualTo` effect with one new `count`
string (`source_controller_units_x2`) — a trivial additive arm, not a primitive.

## The primitive — an exact `WhenYouDraw` mirror

`WhenYouDraw` / `WhenDealNonCombatDamage` established the **ledger + settle-drain
observer** pattern: a deep-call event is recorded into a `GameMemory` list, then
drained at the `apply()` settle-point (only while the stack is clear) so the
observer resolves on a clean stack rather than mid-resolution. `WhenYouUseForce`
is the same shape, with one wrinkle: unlike draws (which have ONE site,
`_draw_cards`), the Force-token spend is **dispersed across 8 sites** (6 card
`CustomEffect` fns + 2 engine sites: the `UseForce` ability cost and the
`use_force` decision's `UseForceOption`). So step one is to **consolidate all 8
into a single chokepoint** — the analogue of `_draw_cards` being the one draw
site. That consolidation is a mechanical refactor, not a second primitive.

### Engine pieces

1. **`registry.WhenYouUseForce`** — new frozen-dataclass trigger (event is None; a
   synthesised observer fire). Docstring mirrors `WhenYouDraw`.
2. **`GameMemory.force_uses: list`** (state.py) — ledger of player_ids who spent a
   Force token since the last settle; serialised in `to_dict`/`from_dict`; always
   empty between actions (drained every settle); no phase/round clear. No phase
   guard on recording (Yoda's text has no "action phase" restriction; Force is
   only ever spent in ACTION anyway).
3. **`actions.spend_force_token(s, ps) -> bool`** — the single chokepoint. Returns
   False if the player had no token (so the 6 card fns keep their "if you do"
   early-return); otherwise clears `ps.has_force_token` and appends `ps.player_id`
   to `force_uses`. Replaces all 8 dispersed `ps.has_force_token = False` sites.
4. **`actions._fire_force_observers(s)`** — drains `force_uses` at the settle-point
   (right after `_fire_draw_observers` in `apply()`), firing
   `fire_triggered_abilities(s, None, event_ctx={"force_used_player_id": pid})`.
   Exact mirror of `_fire_draw_observers`.
5. **`resolver._trigger_matches` arm** — `WhenYouUseForce` matches when
   `event_ctx.get("force_used_player_id") == source_ci.owner_id` ("when YOU use").
   **No new collection site**: Yoda observes from in-play, so the existing arena
   scan already collects it (simpler than `WhenYouDraw`, which needed a hand scan
   for the drawn-card flavour).
6. **`resolver._scaling_magnitude` arm** — `source_controller_units_x2` = 2 × total
   units the source controller has in both arenas (for the payoff).

No new decision kind → reuses `trigger_option`/`resolve_effects`, so **no**
`invariants._KNOWN_DECISION_KINDS` / `web/session._PROMPTS` / HeuristicBot change
(identical to the two prior observers).

## Why no self-chain gate (unlike Boba JTL_9)

Boba's `WhenDealNonCombatDamage` needed a `SOURCE_READY` gate because its own
payoff *deals non-combat damage* (re-firing the observer). Yoda's payoff *deals
damage* (which does not spend the Force), so using the Force never re-triggers
itself — no gate needed. Yoda's own `WhenPlayed` spends the token exactly once.

## Encoding — Yoda LOF_101

```python
@card_ability("LOF", "101")
def _yoda_my_ally_is_the_force():
    return [
        # "When Played: You may use the Force. If you do, heal 5 damage from a base."
        TriggerAbility(
            trigger=WhenPlayed(), optional=True,
            condition=ConditionCheck(Condition.CONTROLLER_HAS_FORCE_TOKEN),
            effects=[CustomEffect(fn=_yoda_use_force_heal)]),   # spend token, heal 5 own base
        # "When you use the Force: You may deal damage to a unit equal to twice
        #  the number of units you control."
        TriggerAbility(
            trigger=WhenYouUseForce(), optional=True,
            effects=[DealDamageEqualTo(
                target=TargetSpec(controller="any", kind="unit"),
                count="source_controller_units_x2")]),
    ]
```

`_yoda_use_force_heal` = `spend_force_token(state, ps)` (early-return if no token),
then heal the controller's own base by 5 (the "a base" convention — never the
enemy's). The token spend records into `force_uses`, so at settle the second
ability's `WhenYouUseForce` observer fires (Yoda is in play). The observer is
optional (the "you may deal damage") and `DealDamageEqualTo` prompts for the unit
via the standard resolve_effects `ChooseTarget`.

## Siblings aliased (`REPRINT_ALIASES` "batch 17")

`("J25","11"): ("LOF","101")`, `("LOFP","6"): ("LOF","101")`.

## Tests — `tests/test_lof_cards.py::TestYodaLOF101`

- `test_lof_101_when_played_use_force_heals_and_triggers_second`: Yoda's owner has
  a Force token + a damaged own base + controls N units; play/fire WhenPlayed,
  accept → base healed 5 AND the WhenYouUseForce observer fires → deal 2N to a
  chosen enemy unit.
- `test_lof_101_decline_when_played_no_force_used`: decline the WhenPlayed → token
  kept, base not healed, second ability not fired.
- `test_lof_101_use_force_via_ability_cost_fires_observer`: spend the token via a
  different route (`spend_force_token` directly) with Yoda in play → observer
  offered; assert `source_controller_units_x2` magnitude.
- `test_lof_101_second_ability_decline_deals_nothing`: accept WhenPlayed but
  decline the WhenYouUseForce → base healed, no damage.
