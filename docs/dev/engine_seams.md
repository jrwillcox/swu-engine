# Engine seams and patterns

The reusable building blocks for encoding cards. When a card resembles an existing
pattern, reuse that pattern by name; don't invent a new one.

- For the full history of a primitive, or precedent for a specific card, search
  [`history/seams_log.md`](history/seams_log.md) and
  [`history/encoding_history.md`](history/encoding_history.md) for the card id.
- For the step-by-step card recipe, see [`encoding_guide.md`](encoding_guide.md).

## Recurring patterns

| Pattern | What it is | Example |
|---|---|---|
| **Thin `CustomEffect` adapter** | The card's ability is one `CustomEffect` that calls a `push_*` helper; no logic in the card. Most decision-kind cards work this way. | Palpatine SOR_135 |
| **Pop, then act** | When a decision resolves into damage or defeat, pop the decision first, so any resulting trigger lands on a clean stack. | `push_distribute_damage` |
| **Don't offer a no-op** | Gate an activated ability or optional trigger with a `Condition`, so it isn't offered when it would change nothing. | Ozzel SOR_129, Han SHD_13 |
| **"If you do" in one effect** | Put a cost and its payoff in a single `CustomEffect`, so an unpaid cost can't grant the payoff. | Bright Hope SOR_99, Kihraxz SHD_118 |
| **Conditional magnitude** | Choose the amount from the board inside a `CustomEffect.target` function, for logic one `Condition` can't express (e.g. either of two aspects). | Zeb Orellios LAW_45 |
| **Shared `event_ctx`** | Sequential effects share the `resolve_effects` decision's `event_ctx`, so the second target can depend on the first. | Nothing Left to Fear LAW_41, Haymaker LAW_168 |
| **Fixed after targeted** | Put a fixed-`SELF` effect after a targeted one, so the resolver prompts once (it consumes the choice at the current `effect_idx`). | The Mandalorian SHD_18, C-3PO SEC_93 |
| **One ability per clause** | Register each single-target clause as its own ability, avoiding the resolver's skip-earlier-effect quirk. | Sabine's Masterpiece JTL_250 |
| **`GrantedAbility`** | "Attached unit gains: '…'". Resolves with the host as source; also fires from a defeated host's detached upgrades (bounties). | Armed to the Teeth SHD_175 |
| **`GrantedAbility(ActivatedAbility(...))`** | An upgrade gives its host an Action. `legal_actions` scans each host's `attached_upgrades` and emits `UseAbility(UPGRADE.instance_id, idx)`; `UseAbility.apply` finds the host (`_find_upgrade_host`) and routes a `DefeatSelf` cost to `_defeat_attached_upgrade`, not `_defeat_unit`. A `push_granted_attack` adapter must `return state`. | Heroic Resolve SHD_155 |
| **`AuraGrantedAbility`** | A source grants a triggered ability to every unit matching a `target` ("Each friendly … unit gains"). Collected on the defeat path (`_collect_triggers`), resolving from the matched unit; `unwrap_granted` unwraps it. Only `WhenDefeated` inner abilities so far. | Gar Saxon SHD_1 |
| **Play from discard** | `_enumerate_discard_play_actions` offers `PlayFromDiscard`, which fires `CardPlayed`/`WhenPlayed` like `PlayCard`. Fed by a `PlayFromDiscardAction` spec gated by a `condition` (SHD_38 uses `ENEMY_UNIT_DEFEATED_THIS_PHASE`), or by `game_memory.free_discard_play_this_phase` (cleared in `clear_phase`) for `PlayFromDiscard(free=True)`. | Brutal Traditions SHD_38, Second Chance SHD_53 |
| **Conditional self-grant** | "While X, this unit gains <keyword>" is `ConstantAbility(target=SELF, KeywordGrant, condition=…)`, read by `has_keyword`. The keyword sanitiser strips the mis-tagged printed keyword. | Hunting Nexu SHD_168, Protector SHD_247 |
| **First-card discard** | "Opponent discards a card" is `DiscardFromHand(chooser="opponent")`, which takes their first card. A documented simplification. | K-2SO SOR_145, Garindan SEC_186 |
| **Decider shift** | A stage decided by the opponent: walk an `order` list, switching `deciding_player_id` and `active_player_index` between stages. | `say_no` SOR_233 |
| **`EACH_*` targets** | `fixed=EACH_FRIENDLY`/`EACH_ENEMY`/`EACH_IN_PLAY` hits every match with no prompt. | many |

## Decision kinds

A decision kind models a mid-resolution choice: a `push_*` helper puts it on the
decision stack, and its `Action` subclasses resolve it. Reuse an existing kind before
adding one; `granted_attack` and `play_from_hand` take many options:

- **`granted_attack`:** `attacker_predicates`, `attacker_id`, `attacker_trait`,
  `attacker_arena`, `attacker_cost_max`, `attacker_pilot_related`, `optional`,
  `repeat`, `allow_exhausted`, `no_base`, `exclude_source`, `grant_keywords` (a name
  or `(name, value)`), `bonus_trait`, `bonus_if_defender_unit`,
  `bonus_if_odd_cost_diff_from`, `then_defeat_attacker` (Heroic Sacrifice SOR_150),
  and `defender_power_bonus`/`defender_hp_bonus`, a `this_attack` debuff on the chosen
  defender (Jyn Erso SOR_18).
- **`play_from_hand`:** `trait`, `enters_ready`, `then_opponents_ready`,
  `cost_reduction`, `then_damage`, `cost_max`, `grant_keyword`, `free`, `aspect`,
  `exclude_aspect`, `from_discard`, `ignore_aspect_penalty`, `defeat_at_regroup`,
  `grant_keyword_if_credit_spent`, `then_self_base_damage_cost` (Galactic Ambition
  SOR_235), `eligible_ids` (restricts the choice, e.g. to discard cards),
  `then_defeat_ids` (Consolidation of Power TWI_89), and `cost_reduction_if_trait`, a
  `(trait, reduction)` pair that replaces `cost_reduction` for a card with that trait
  (Palpatine's Return SHD_94; applied by `_play_reduction_for`).

| Kind | Models | Example |
|---|---|---|
| `granted_attack` | "Attack with a unit; it gets +X/+Y" (options above) | Surprise Strike SOR_220 |
| `play_from_hand` | "Play a unit from your hand" as part of an ability (options above) | Admiral Ozzel SOR_129 |
| `play_event_from_hand` | "Play an event from your hand for N less" (`push_play_event_from_hand(cost_reduction=)`, `PlayEventFromHand`; resolves via `_resolve_event_ability`). Gate with `Condition.CONTROLLER_CAN_PLAY_EVENT_FROM_HAND(param=reduction)`. | Bib Fortuna SOR_177 |
| `play_via_smuggle` | "Play a card using Smuggle for N less, then you may defeat a resource you own" (`push_play_via_smuggle(cost_reduction=, then_defeat_own_resource=)`, `PlayViaSmuggle`, `_smuggle_eligible_from_resources`). Gate with `Condition.CONTROLLER_CAN_SMUGGLE(param=reduction)`. | Lando Calrissian SHD_17 |
| `play_via_piloting` | "Play a card from your hand using Piloting for N less" (`push_play_via_piloting(cost_reduction=)`, `PlayViaPiloting(instance_id, vehicle_target_id)`). `_piloting_eligible_from_hand` lists (pilot, vehicle) pairs, so a pilot with nothing to ride isn't offered. Reuses `_piloting_cost` and `_attach_pilot`. Gate with `Condition.CONTROLLER_CAN_PILOT(param=reduction)`. | Wedge Antilles JTL_8 |
| `distribute_damage` | "Deal N damage divided as you choose" (modes `pool`, `source_pool`, `sequence`; `up_to`) | Palpatine SOR_135 |
| `deck_search` | "Search the top N; take or play one; bottom the rest at random" (`disposition="play"`; `disposition="discard_free_replay"` sets `free_discard_play_this_phase`, Cobb Vanth SHD_115) | Grand Moff Tarkin SOR_84 |
| `modal` | "Choose one: …", then a target. Some modes need no real target, e.g. `bomb_ground`/`bomb_space` (Bombing Run SOR_173). | Leia SOR_189 |
| `say_no` | "Do X unless an opponent says no" | I Am Your Father SOR_233 |
| `reveal_top` | "Reveal the top N; discard any; reorder the rest" (`disposition`, `deal_aspect_damage`) | For a Cause I Believe In SOR_152 |
| `sacrifice_resource` | "You may defeat a friendly resource; if you do, deal N" | Wrecker SHD_154 |
| `opponent_chooses_target` | "An opponent picks one of their units or their base; you may damage it" (`ground_only`) | Grey Squadron Y-Wing SHD_246 |
| `reveal_resource_ramp` | "Reveal a resource that shares a name with a friendly unique unit; return it to hand and resource the top of your deck" (`optional`; gate `CONTROLLER_HAS_REVEAL_RAMP_RESOURCE`) | Hunter SHD_9 |
| `select_distinct_return_random` | "Choose N differently named cards in your discard; return one at random" (`rng.choice`). No decline; pushed only when N distinct names exist. Related gate: `CONTROLLER_DISCARD_DISTINCT_COSTS_MIN`. | Doctor Aphra SHD_15 |
| `repeated_modal` | "Discard up to N; for each, choose a different option" | Poe Dameron SHD_153 |
| `select_token` | "Give a token to each of up to N units" (`decider_id`, `after_resolve_idx`) | Medal Ceremony SOR_245 |
| `select_damage` | "Deal 1 damage to each of up to N units" | IG-2000 JTL_140 |
| `move_upgrade` | "Move an upgrade to another eligible unit" | Survivors' Gauntlet SHD_64 |
| `return_from_discard` | "Return up to N eligible cards from your discard to your hand" (`eligible_instance`) | Razor Crest SHD_44 |
| `resource_from_discard` | "Put a qualifying discard card into play as a resource" (facedown, exhausted). `push_resource_from_discard(eligible=, up_to=)`; the qualifying test lives in `eligible`, a `CardInstance` predicate, e.g. via `units_defeated_this_round`. | The Marauder SHD_102, Spark of Hope SHD_105 |
| `discard_for_experience` | "You may discard a card with the same name as a friendly unit; give that unit 2 Experience" (`push_discard_for_experience`) | Echo SHD_99 |
| `discard_for_search` | "Discard a card, then search your deck" (`optional`, `search_name`) | Great Pit LAW_23, R2-D2 TWI_193 |
| `each_player_defeats` | "Each player defeats one of their own units" | Merciless Contest TWI_238 |
| `bottom_from_hand` | "Put N cards from your hand on the bottom of your deck" | Private Manufacturing TWI_257 |
| `may_discard` | "An opponent may discard a random card; if they don't, you get tokens" | Political Pressure TWI_222 |
| `exhaust_for_base_damage` | "Exhaust any number of units; deal N base damage for each" | The Invisible Hand TWI_234 |
| `exhaust_combined_cost` | "Exhaust any number of units" within a cost budget (`budget`, `max_units`, `arena`) | Qui-Gon's Lightsaber LOF_201 |
| `recur_and_buff` | "Put up to N units from your discard on the bottom of your deck; buff that many units" | Luminous Beings LOF_104 |
| `pay_resources_for_tokens` | "Pay up to N resources; get a token for each" | Curious Flock LOF_255 |
| `use_force` | "You may use the Force for a bonus" (`decline_penalty`) | Impossible Escape LOF_218 |
| `discard_unit_damage` | "Put a unit from your discard on the bottom of your deck; deal damage equal to its power" | Sarlacc LAW_163 |
| `cull_for_damage` | "Give up any number of your own cards (hand or tokens); deal that much damage" | Vader LAW_11, Han LAW_17 |
| `reveal_play_credit` | "Reveal the top card; a player may play it free; the other gets credits" | Vermillion LAW_215 |
| `per_exploit_damage` | "For each exploited unit, deal its power to an enemy" | Count Dooku TWI_138 |
| `assign_indirect_damage` | "Deal N indirect damage" (the receiver assigns it; shields don't apply) | First Order Stormtrooper JTL_132 |
| `peek_top` | "Look at the top card; keep, discard or play it" (`may_play_discard`; `may_play` with `cost_reduction`/`free`, You're My Only Hope SOR_246) | Ezra Bridger SOR_192 |
| `plot` / `smuggle` / `pilot` | Keyword play routes (`PlotPlay`, `SmugglePlay`, `PilotPlay`) | Garindan SEC_186, Cassian SHD_148, Dengar JTL_139 |
| `DeployLeaderAsUpgrade` | Deploy a Piloting leader as a pilot on a vehicle | Boba Fett JTL_9 |
| `reveal_cost_damage` | "Reveal cards one at a time until you stop; if their total cost is at most M, deal that much damage" (`RevealNextCard`, `StopRevealing`) | Don't Get Cocky SOR_223 |
| `opponent_split_bounce` | "Choose up to 2 units; an opponent picks one to return to hand; bottom the other." Controller picks, then opponent (`SelectSplitBounceUnit`, `FinishSplitBounce`, `ChooseSplitReturn`; reuses `_apply_return_to_hand`, `_apply_put_on_deck`). | I Had No Choice SOR_187 |
| `bottom_from_discard` | "Put up to N cards from either discard on the bottom of their owners' decks at random" (`SelectBottomDiscardCard`, `FinishBottomFromDiscard`) | Restock SOR_252 |
| `discard_excess_from_hand` | "Each player discards down to N cards", controller first, reusing the `each_player_defeats` `order`/`idx` walk (`SelectExcessHandCardToDiscard`) | Smoke and Cinders SOR_174 |
| `name_and_discard` | "Name a card; an opponent reveals their hand and discards a copy." Offers only names actually in that hand (`NameAndDiscard`). `optional` adds `DeclineNameAndDiscard`; `discarder_draws` covers Bazine Netal SHD_184. | Chimaera SOR_185 |
| `combined_power_play` | "Choose units; play a card from your hand for free costing up to their combined power; then defeat them" → `push_play_from_hand(free=True, cost_max=…, then_defeat_ids=…)`. If nothing is playable, `_resolve_combined_power_play` still defeats them (`SelectCombinedPowerUnit`, `FinishCombinedPowerPlay`). | Consolidation of Power TWI_89 |
| `play_captured_card` | "Play a card captured by one of your units for free, under your control" (`SelectCapturedToPlay`; `up_to` adds `DeclineCapturedPlay`) | Dryden Vos SHD_192 |
| `rescue_guarded` | "The defending player may rescue a card they own guarded by this unit; if they do, you draw N." Decided by the opponent; always hands the seat back, since an On Attack leaves a `pre_attack` decision beneath it. Uses `actions._rescue_captured_card(s, ci)` (to the owner's hand, unlike `_release_captured_cards`), which SHD_76 also uses (`RescueGuardedCard`, `DeclineRescue`). | Cad Bane TWI_187 |
| `reveal_cull_draw` | "Reveal the top N; an opponent discards X of them; draw 1 of the rest, discard the others." Opponent culls (`CullRevealedCard`), then the controller draws (`DrawRevealedCard`). The cards stay in the deck while it is open; `cull` is capped at `len(revealed) - 1`. | Admiral Trench JTL_14 |
| `play_resource_units` | "Reveal any number of your resources; play each unit revealed for free, one at a time." Each pick leaves the resource row unreplaced. The loop re-pushes itself before playing, so each unit's triggers resolve before the next pick (`SelectResourceUnitToPlay`, `DeclineResourceUnitPlay`). | Endless Legions SHD_109 |

### Adding a decision kind

Only when nothing above fits, and only if it doesn't touch core resolution or the
trigger/decision machinery (otherwise see [the escalation rule](#the-escalation-rule)).

1. **Engine:** the `push_*` helper, its `Action` subclasses and a
   `register_decisions({...})` row, all in the `engine/actions/` module for that
   mechanic. Push the decision only when it can do something.
2. **Invariants:** add the kind to `_KNOWN_DECISION_KINDS` in `engine/invariants.py`.
3. **Web prompt:** add a line to `_PROMPTS` in `web/session.py`.
4. **Bot:** a `HeuristicBot` handler, and a place in its `_SAFE_DEFAULT_ORDER`.
5. **Off-board picks:** if the player chooses cards that aren't clickable on the
   board (deck, discard pile, captured cards), put card views in the context's
   `"candidates"` and add a case to the chooser in `web/src/components/Table.tsx`.
   `tests/test_web_offboard_pickers.py` enforces this and step 3.

The golden files in `tests/fixtures/` (`actions_decision_kinds.json`,
`actions_public_surface.json`) will then fail on purpose. Update them deliberately.

## Engine internals worth knowing

- **Decision stack.** `GameState.pending_decisions` is LIFO. While it is non-empty,
  `legal_actions()` offers only the top decision's options. On resolution it pops and
  sets `active_player_index` to `after_resolve_player_index`. An activated ability
  hands the turn over only if it pushed no decision.
- **Keywords.** Never string-match card text. Use
  `has_keyword(state, ci, Keyword.SENTINEL)` and `keyword_value(state, ci, Keyword.RAID)`
  from `engine/keywords.py`. Numeric values come from `text` (units) or `deploy_box`
  (leaders).
- **Stats.** Use `compute_power(state, ci, is_attacking=...)` and `compute_hp`. They
  include upgrades, modifiers, constant abilities, Grit and (when attacking) Raid.
  Never read `card_def.power` in game logic. `compute_power` floors at 0.
- **Tokens.** Shield and Experience are real card defs. Create them with
  `tokens.attach_token(state, owner_ps, host_ci, "Shield")`. They vanish (are not
  discarded) when their host leaves play, and don't count for card conservation.
- **Combat** (`_resolve_unit_combat` in `actions/combat.py`) follows the rules'
  steps: declare and exhaust → on-attack triggers (Restore, Saboteur) → compute
  powers → simultaneous damage through `_deal_damage_with_shield` → Overwhelm
  spillover → defeat (tokens removed, upgrades discarded).
- **Trigger order.** `keyword_triggers.py` registers Shielded before Ambush, so the
  Shield is attached before the Ambush choice.
- **`PLAY_BUFFER`** holds a card between `PlayCard` and `ExploitCommit`; it counts
  for conservation.
- **State-based defeat.** After every settled action, `apply()` defeats any unit
  whose damage has reached its HP, so a unit dies when a buff wears off.

## Keywords

Every printed keyword is modelled. Tier 1: Sentinel, Overwhelm, Raid, Ambush,
Restore, Saboteur, Shielded, Grit. Later: Exploit, Coordinate, Plot, Hidden, Bounty,
Smuggle, Piloting, Support. Design notes for each are in
[`history/encoding_history.md`](history/encoding_history.md) (Part 2).

## The escalation rule

A small, self-contained primitive (a new effect dataclass with its resolver arm, or
a new decision kind) may be added alongside a card, with synthetic-card tests.

Anything that touches **core resolution**, the **trigger or decision machinery**, or
needs a **replacement-effect system** must stop and be designed in its own session,
never squeezed into a card batch. See
[`design_when_you_draw_observer.md`](design_when_you_draw_observer.md) for a worked
example.
