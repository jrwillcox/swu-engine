# Framework escalation — the `WhenYouDraw` observer (batch 16)

## Leverage ranking (from the batch-14 roadmap)

| Primitive | Groups cleared | Surface | Second-primitive dep? |
|---|---|---|---|
| **when-you-draw observer** | **2** (LAW_52, LOF_148) | new trigger + ledger + settle-drain (mirror of `WhenDealNonCombatDamage`) | none |
| new observers (TWI_64 Ki-Adi, LOF_101 Yoda) | 1 each | new trigger + firing site | none |
| self-contained decision kinds (LOF_42, LAW_32, LOF_200, LAW_80, SOR_87) | 1 each | new decision kind | some |
| multi-decider return-then-replay (LOF_185, LAW_93) | 1 (two-card) | new multi-decider | yes |
| capture variants / dmg-prevention / keyword-copy / combat-timing / phase-structure | 1 each | heavy | some |

**Pick: the when-you-draw observer** — most groups per primitive (2), smallest surface
(an exact mirror of the existing `WhenDealNonCombatDamage` ledger+settle observer), no
dependency on a second unbuilt primitive.

## The two cards

- **LAW_52 The Mandalorian** (Unit 6/5): `When Played: Draw a card.` + `When you draw 1
  or more cards during the action phase: Give a Shield token to this unit.` An **in-play
  observer** (unit in an arena watches its controller's draws) — the clean mirror of
  `WhenYouPlayCard`/`CardPlayed`.
- **LOF_148 Rey** (Unit 5/5): `When you draw this card during the action phase: If you
  control an Aggression leader or base, you may reveal this card from your hand. If you
  do, deal 2 damage to a unit and 2 damage to a base.` Fires from the card **while it is
  in hand** — a second collection site + resolving an ability whose source is a hand card
  (works because `find_instance` scans `all_instances()`, which includes hand, and the
  effects target the board, not the source).

## Why one primitive (not two)

`WhenYouDraw` is ONE new trigger kind. Firing it from the draw chokepoint is ONE new
firing site. Collecting it from two places — in-play units (LAW_52) and the just-drawn
hand cards (LOF_148) — is part of the SAME trigger's collection, exactly like `WhenDefeated`
is already collected from three sites (in-play, the defeated-in-limbo card, defeated
upgrades). Resolving from a hand source needs no new machinery: `find_instance` already
locates hand cards and the effects address the board.

## Why a ledger + settle-drain (not inline firing)

`_draw_cards` is called deep inside effect resolution (WhenPlayed `DrawCards`, activated
abilities, mid-`resolve_effects`). Firing an observer inline would push a decision onto a
mid-resolution stack. The `WhenDealNonCombatDamage` (Boba Fett JTL_9) pattern solves this
exactly: record into a `GameMemory` ledger during the deep call, drain it at the `apply()`
settle-point (only while the stack is clear). Adopt it verbatim.

## Engine pieces (all additive; mirror `WhenDealNonCombatDamage`)

1. **registry.py** — `@dataclass(frozen=True) class WhenYouDraw: on_self: bool = False`
   (exported alongside the other triggers). `event` is None (a synthesised observer fire).
2. **registry.py Condition** — new atom `CONTROLLER_HAS_ASPECT_LEADER_OR_BASE` + an
   `evaluate` arm (LOF_148's "control an Aggression leader or base" gate; reads
   `ps.base_instance` / `ps.leader_instance` aspects).
3. **state.py `GameMemory`** — new ledger `action_phase_draws: list` (entries
   `{"player_id", "card_ids": [...]}`); serialised in `to_dict`/`from_dict` (like
   `noncombat_damage_dealers`; drained every settle, so no phase/round clear).
4. **actions.py `_draw_cards`** — track the drawn card ids; when `s.phase == ACTION` and
   ≥1 card was drawn, append one `{player_id, card_ids}` entry (one entry per draw *event*
   = one Shield per event for LAW_52). Empty-deck "draws" (base damage, 0 cards) do not
   record — "draw 1 or more cards".
5. **actions.py `_fire_draw_observers(s)`** — settle-point drain (mirror
   `_fire_noncombat_damage_observers`): pop one entry, `fire_triggered_abilities(s, None,
   event_ctx={"drew_player_id": pid, "drawn_card_ids": [...]})`, re-sweep; called in
   `apply()` right after `_fire_noncombat_damage_observers`.
6. **resolver.py `_trigger_matches`** — `WhenYouDraw` arm: `on_self` → `source_ci.instance_id
   in event_ctx["drawn_card_ids"]`; else → `event_ctx["drew_player_id"] == source_ci.owner_id`.
7. **resolver.py `_collect_triggers`** — new site: for each id in `event_ctx["drawn_card_ids"]`,
   find it in the drawer's hand and collect its `WhenYouDraw(on_self=True)` triggers (the
   in-play observer LAW_52 is already collected by the existing arena scan).

No new decision kind (reuses `trigger_option`/`resolve_effects`), so **no** `invariants`
/ `web/session` / bot change — identical to the non-combat-damage observer.

## Card encodings

- **LAW_52**: `[TriggerAbility(WhenPlayed(), [DrawCards(1)]),
  TriggerAbility(WhenYouDraw(), [GiveToken("Shield", TargetSpec(fixed=SELF))])]`.
- **LOF_148**: `TriggerAbility(WhenYouDraw(on_self=True), optional=True,
  condition=ConditionCheck(CONTROLLER_HAS_ASPECT_LEADER_OR_BASE, param="Aggression"),
  effects=[DealDamage(2, any unit), DealDamage(2, any base)])`. The "you may reveal from
  hand" IS the optional trigger's Accept/Decline (reveal modelled as a documented no-op —
  the card stays in hand); "if you control an Aggression leader or base" gates collection.

## Siblings to alias

- Rey LOF_148 ← J25_13, LOFP_9, P25_71
- The Mandalorian LAW_52 ← C26_2
