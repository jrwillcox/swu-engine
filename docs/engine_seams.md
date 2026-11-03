# Engine seams and patterns

The reusable building blocks for encoding cards. When a card resembles an existing
pattern, reuse that pattern by name; don't invent a new one.

- For the full history of a primitive, or precedent for a specific card, search
  [`history/seams_log.md`](history/seams_log.md) and
  [`history/encoding_history.md`](history/encoding_history.md) for the card id.
- For the step-by-step card recipe, see [`encoding_guide.md`](encoding_guide.md).

## Recurring patterns

| Pattern | What it is | Canonical card |
|---|---|---|
| **Thin CustomEffect adapter** | A card's trigger/event is one `CustomEffect` that just calls a `push_*` decision helper — no logic in the card. Most decision-kind cards are this. | Palpatine SOR_135 |
| **Pop-then-deal / pop-then-act** | When a decision resolves into damage/defeat, **pop the decision FIRST, then apply**, so a resulting defeat trigger lands on a clean stack. | push_distribute_damage |
| **"Don't offer a no-op"** | Gate an activated ability / optional trigger with a `Condition` so it isn't offered when it would change nothing (protects errata + bot). | Ozzel SOR_129, Han SHD_13 |
| **"If you do" binding** | When a cost and its payoff must be atomic, put BOTH in one `CustomEffect` (not two effects) so an unpaid cost can't apply the payoff and the optional trigger auto-declines with no legal use. | Bright Hope SOR_99, Kihraxz SHD_118 |
| **Conditional magnitude** | Magnitude decided from board state (e.g. 3 vs 5) inside a `CustomEffect.target` fn — expresses OR-of-aspects and other things a single `Condition` can't. | Zeb Orellios LAW_45 |
| **Shared event_ctx for dependent targets** | Two sequential effects share the `resolve_effects` decision's `event_ctx` dict so the 2nd target's eligibility keys off the 1st chosen target. | Nothing Left to Fear LAW_41, Haymaker LAW_168 |
| **Fixed-before-targeted single prompt** | Order a fixed-SELF effect AFTER a targeted one so the resolver prompts exactly once (it consumes the choice at the current `effect_idx` without skipping an earlier gated effect). | The Mandalorian SHD_18, C-3PO SEC_93 |
| **Separate single-effect abilities** | A multi-clause card (each clause one target choice) → register each clause as its own single-effect ability, sidestepping the resolve_effects skip-earlier-no-target wart. | Sabine's Masterpiece JTL_250 |
| **GrantedAbility (resolves from host)** | Upgrade confers "Attached unit gains: '<ability>'" — wrap the ability in `GrantedAbility`; it matches/resolves with the HOST as source. Also fires from a defeated host's detached upgrades (bounties). | Armed to the Teeth SHD_175 |
| **GrantedAbility wrapping an ActivatedAbility** | An upgrade grants its host an *Action* — `GrantedAbility(ActivatedAbility(...))`. The trigger collector skips it (its `.ability` isn't a TriggerAbility); a scan in `legal_actions` walks each host's `attached_upgrades` and emits `UseAbility(UPGRADE.instance_id, idx)`. `UseAbility.apply` finds the host (`_find_upgrade_host`), resolves the effect FROM the host, and routes a `DefeatSelf` cost to `_defeat_attached_upgrade` (detach + owner-discard THIS upgrade) instead of `_defeat_unit`. A push_granted_attack CustomEffect adapter must `return state`. | Heroic Resolve SHD_155 |
| **AuraGrantedAbility (aura grant to a group)** | A SOURCE grants a triggered ability to EVERY unit matching a `target` — "Each friendly … unit gains: '<ability>'", the group analogue of GrantedAbility. Collected at the UnitDefeated defeat path (`_collect_triggers`), resolving from the matched unit; `unwrap_granted` unwraps it. WhenDefeated inner only today; in-play-scan ⇒ leader-side auras are deployed-only for free. | Gar Saxon SHD_1 |
| **Play-from-discard (legal-action source)** | The discard pile as a new ACTION-phase legal-action source (`_enumerate_discard_play_actions` → `PlayFromDiscard`, which mirrors `PlayCard`'s CardPlayed/WhenPlayed firing). Two feeders: (1) `PlayFromDiscardAction` spec = a printed "Action: play this from your discard pile (paying its cost)", gated by a `condition` (SHD_38 reuses `ENEMY_UNIT_DEFEATED_THIS_PHASE`); (2) a granted "When Defeated: for this phase, owner may play it from discard for free" = a phase-scoped per-instance permission (`game_memory.free_discard_play_this_phase`, cleared in `clear_phase`, consumed on replay) → `PlayFromDiscard(free=True)`. | Brutal Traditions SHD_38 / Second Chance SHD_53 |
| **Conditional self-grant + sanitiser** | "While X, this unit gains <keyword>" = `ConstantAbility(target=SELF, KeywordGrant, condition=…)`, read passively by `has_keyword`. The keyword sanitiser strips the mis-tagged printed keyword when such a spec is registered. | Hunting Nexu SHD_168, Protector SHD_247 |
| **First-card discard simplification** | "opponent discards a (named) card" → `DiscardFromHand(chooser="opponent")` drops their first card. Documented deviation; used wherever a look-at-hand-and-pick decision would be overkill. | K-2SO SOR_145, Garindan SEC_186 |
| **Decider-shift decisions** | A decision stage decided by the OPPONENT (or a third player) — walk an `order`/stage list and flip `deciding_player_id`/`active_player_index` between stages. | say_no SOR_233 |
| **EACH_* auto-target** | `fixed=EACH_FRIENDLY/EACH_ENEMY/EACH_IN_PLAY` resolves to every matching card inline, no prompt. | many |

## Decision kinds

A decision kind models a mid-resolution choice: a `push_*` helper puts it on the
decision stack, and its `Action` subclasses resolve it. Reuse an existing kind before
adding one. `granted_attack` and `play_from_hand` in particular have many optional
fields.

| Kind | "…" it models | Canonical card |
|---|---|---|
| `granted_attack` | "Attack with a unit, +X/+Y". Fields: `attacker_predicates`, `attacker_id`, `attacker_trait`, `attacker_arena`, `attacker_cost_max`, `attacker_pilot_related`, `optional`, `repeat`, `allow_exhausted`, `no_base`, `exclude_source`, `grant_keywords` (name or (name,value)), `bonus_trait`, `bonus_if_defender_unit`, `bonus_if_odd_cost_diff_from`, `then_defeat_attacker` (self-defeat the attacker after combat settles — Heroic Sacrifice SOR_150 "gains: 'When this unit deals combat damage: Defeat it'"), `defender_power_bonus`/`defender_hp_bonus` (a stat debuff applied to the CHOSEN unit-defender for this attack, as a this_attack modifier — Jyn Erso SOR_18 "the defender gets −1/−0 for this attack") | Surprise Strike SOR_220 |
| `play_from_hand` | "Play a unit from hand as an ability". Fields: `trait`, `enters_ready`, `then_opponents_ready`, `cost_reduction`, `then_damage`, `cost_max`, `grant_keyword`, `free`, `aspect`, `exclude_aspect`, `from_discard`, `ignore_aspect_penalty`, `defeat_at_regroup`, `grant_keyword_if_credit_spent`, `then_self_base_damage_cost` (deal the played unit's printed cost to your own base — Galactic Ambition SOR_235), `eligible_ids` (whitelist ids → discard-only play), `cost_reduction_if_trait` (a `(trait, reduction)` pair that REPLACES the base `cost_reduction` for a chosen card carrying that trait — "costs 6 less; if a Force unit, costs 8 less instead", Palpatine's Return SHD_94; threaded via `_play_reduction_for` at both the enumeration and apply sites) | Admiral Ozzel SOR_129 |
| `play_event_from_hand` | "Play an EVENT from hand as an ability, at `cost_reduction` off" — the event sibling of `play_from_hand` (events resolve via `_resolve_event_ability`, not the unit path). `push_play_event_from_hand(cost_reduction=)` + `PlayEventFromHand`; gate an activating ability with `Condition.CONTROLLER_CAN_PLAY_EVENT_FROM_HAND(param=reduction)` so the exhaust is never wasted | Bib Fortuna SOR_177 |
| `play_via_smuggle` | "Play a card using Smuggle as an ability, at `cost_reduction` off, then optionally defeat a resource you own" — the Smuggle sibling of `play_event_from_hand` (reuses SmugglePlay mechanics WITHOUT handing the turn over). `push_play_via_smuggle(cost_reduction=, then_defeat_own_resource=)` + `PlayViaSmuggle` + `_smuggle_eligible_from_resources`; gate with `Condition.CONTROLLER_CAN_SMUGGLE(param=reduction)` | Lando Calrissian SHD_17 |
| `play_via_piloting` | "Play a card from your hand using Piloting, at `cost_reduction` off" — the Piloting sibling of `play_via_smuggle` (reuses `_piloting_cost` → `_attach_pilot` but resolves inside the ability, without handing the turn over). `push_play_via_piloting(cost_reduction=)` + `PlayViaPiloting(instance_id, vehicle_target_id)` + `_piloting_eligible_from_hand`, which enumerates **(pilot, host) PAIRS** so a Piloting card with no friendly Vehicle to ride is never offered; gate an activating ability with `Condition.CONTROLLER_CAN_PILOT(param=reduction)` | Wedge Antilles JTL_8 |
| `distribute_damage` | "Deal N divided as you choose" (modes pool/source_pool/sequence; `up_to`) | Palpatine SOR_135 |
| `deck_search` | "Search top N, draw/play chosen, bottom rest random" (`disposition="play"` for search-and-play; `disposition="discard_free_replay"` discards the chosen card + flags `free_discard_play_this_phase` for a free replay — Cobb Vanth SHD_115) | Grand Moff Tarkin SOR_84 |
| `modal` | "Choose one: … then target" (extensible mode set; fungible modes resolve on an arbitrary/throwaway target — e.g. `bomb_ground`/`bomb_space` "choose an arena, deal 3 to each unit in it", Bombing Run SOR_173, pop-then-deal for the multi-defeat) | Leia SOR_189 |
| `say_no` | "Do X unless opponent says no" | I Am Your Father SOR_233 |
| `reveal_top` | "Reveal top N, keep/discard, reorder" (`disposition`, `deal_aspect_damage`) | For a Cause I Believe In SOR_152 |
| `sacrifice_resource` | "You may defeat a friendly resource, then deal N" | Wrecker SHD_154 |
| `opponent_chooses_target` | "Opponent picks their own unit/base, you may damage it" (`ground_only`) | Grey Squadron Y-Wing SHD_246 |
| `reveal_resource_ramp` | "Reveal a resource; if it shares a name with a friendly unique unit, return it to hand + ramp the deck top" (`optional`; only name-matching resources offered; gate `CONTROLLER_HAS_REVEAL_RAMP_RESOURCE`) | Hunter SHD_9 |
| `select_distinct_return_random` | "Choose N discard cards with different names; return 1 of them at random." Forced full selection (no finish/decline) — remaining candidates filtered by name after each pick; auto-finishes at N, then `rng.choice` returns one. Pushed only when ≥N distinct names exist. Also new gate atom `CONTROLLER_DISCARD_DISTINCT_COSTS_MIN` (param) for "while ≥N different costs in your discard, +X/+Y". | Doctor Aphra SHD_15 |
| `repeated_modal` | "Discard up to N; per discard, choose a different option" | Poe Dameron SHD_153 |
| `select_token` | "Give a token to up to N units" (`decider_id`, `after_resolve_idx`) | Medal Ceremony SOR_245 |
| `select_damage` | "Deal 1 to each of up to N units" | IG-2000 JTL_140 |
| `move_upgrade` | "Move an upgrade to another eligible host" | Survivors' Gauntlet SHD_64 |
| `return_from_discard` | "Return up to N eligible cards from discard to hand" (`eligible_instance`) | Razor Crest SHD_44 |
| `resource_from_discard` | "Choose a qualifying discard card → put it into play as a resource (facedown + exhausted per CR)". `push_resource_from_discard(eligible=<CardInstance predicate>, up_to=)`; candidates pre-filtered to the qualifiers (fizzles if none) — the gate ("shares a name with a friendly unit" / "was defeated this phase" via `units_defeated_this_round`) lives in the closure | The Marauder SHD_102 / Spark of Hope SHD_105 |
| `discard_for_experience` | "You may discard a same-named hand card → give 2 Experience to that unit". `push_discard_for_experience`; candidates = hand cards whose name matches a friendly unit in play (auto-picks the token target) | Echo SHD_99 |
| `discard_for_search` | "Discard a card, then search" (generalised; `optional`, `search_name`, windows) | Great Pit LAW_23 / R2-D2 TWI_193 |
| `each_player_defeats` | "Each player defeats one of their own units" | Merciless Contest TWI_238 |
| `bottom_from_hand` | "Put N cards from hand on bottom of deck" | Private Manufacturing TWI_257 |
| `may_discard` | "Opponent may discard a random card, else you get tokens" | Political Pressure TWI_222 |
| `exhaust_for_base_damage` | "Exhaust any number of units → N base damage each" | The Invisible Hand TWI_234 |
| `exhaust_combined_cost` | "Exhaust any number of units" (`budget`, `max_units`, `arena`) | Qui-Gon's Lightsaber LOF_201 |
| `recur_and_buff` | "Recur up to N from discard, buff that many units" | Luminous Beings LOF_104 |
| `pay_resources_for_tokens` | "Pay up to N resources, a token each" | Curious Flock LOF_255 |
| `use_force` | "You may use the Force for a rider" (`decline_penalty`) | Impossible Escape LOF_218 |
| `discard_unit_damage` | "Recycle a discarded unit, deal its power as damage" | Sarlacc LAW_163 |
| `cull_for_damage` | "Give up any number of your own cards (hand / tokens), deal that many damage" | Vader LAW_11, Han LAW_17 |
| `reveal_play_credit` | "Reveal top, a player may play free, another gets credits" | Vermillion LAW_215 |
| `per_exploit_damage` | "Per exploited unit, deal its power to an enemy" | Count Dooku TWI_138 |
| `assign_indirect_damage` | "Deal N indirect (receiver assigns, bypasses shields)" | First Order Stormtrooper JTL_132 |
| `peek_top` | "Look at top card; keep/discard/**play** it" (`may_play_discard` mode) | Ezra Bridger SOR_192 |
| `plot` / `smuggle` / `pilot` | keyword play paths (PlotPlay / SmugglePlay / PilotPlay) | Garindan SEC_186 / Cassian SHD_148 / Dengar JTL_139 |
| `DeployLeaderAsUpgrade` | Deploy a Piloting leader as a Pilot upgrade on a Vehicle | Boba Fett JTL_9 |
| `reveal_cost_damage` | "Choose a unit; reveal from your deck one at a time until you stop or hit N; if the combined cost ≤ M, deal that much to it; bottom the revealed in random order" — a push-your-luck loop (RevealNextCard/StopRevealing; pop-then-deal) | Don't Get Cocky SOR_223 |
| `opponent_split_bounce` | "Choose up to 2 non-leader units; an opponent chooses 1 of them — return that to its owner's hand, put the other on the bottom of its owner's deck." Two-stage decider-shift (controller selects, then opponent picks); 1 pick returns just it, 0 fizzles; reuses `_apply_return_to_hand` / `_apply_put_on_deck`, pop-then-act (SelectSplitBounceUnit/FinishSplitBounce/ChooseSplitReturn) | I Had No Choice SOR_187 |
| `bottom_from_discard` | "Choose up to N cards in a discard pile; put them on the bottom of their owner's deck in a random order." Select-up-to-N over BOTH players' discards; picks shuffled then bottomed onto each card's owner deck (SelectBottomDiscardCard/FinishBottomFromDiscard). (`peek_top` also gained a `may_play` mode + `cost_reduction`/`free` for "look at top, may play it discounted" — You're My Only Hope SOR_246) | Restock SOR_252 |
| `discard_excess_from_hand` | "Each player discards down to N cards of their choice." Symmetric per-stage decider-shift reusing the each_player_defeats `order`/`idx` walk (controller first); a player already at/below N is skipped; records the reveal/discard observer per player (SelectExcessHandCardToDiscard) | Smoke and Cinders SOR_174 |
| `name_and_discard` | "Name a card; an opponent reveals their hand and discards a copy." Private decision carrying opp hand identities (card_id+name only — look_hand hidden-info shape); offers only present names (optimal-play collapse of name-blind, no whiff) then discards one match (NameAndDiscard). `optional` adds `DeclineNameAndDiscard` ("you may"); `discarder_draws` makes the discarding player draw after — models "look at hand, may discard 1, if you do they draw" (Bazine Netal SHD_184) | Chimaera SOR_185 |
| `combined_power_play` | "Choose any number of friendly units; their combined power caps a FREE play from hand; then defeat them." Select-any-number loop (the multi_capture_pairing shape) whose payoff is a DYNAMIC cap: the pooled `compute_power` becomes `push_play_from_hand(free=True, cost_max=…, then_defeat_ids=…)`, and the new `then_defeat_ids` field defers the sacrifice until after the play (so a unit's power still counts while it is spent). Nothing playable ⇒ the defeat settles in `_resolve_combined_power_play` (SelectCombinedPowerUnit/FinishCombinedPowerPlay) | Consolidation of Power TWI_89 |
| `play_captured_card` | "Choose a captured card guarded by a unit you control; you may play it for free under your control." Select-one-from-a-zone (the resource_from_discard pattern): candidates = the Unit captives in the controller's own capture pile (all guarded by their units); the chosen captive leaves the pile and enters play under the controller (owner unchanged) at cost 0, firing its own When Played / keyword triggers (pop-then-act). `up_to` adds `DeclineCapturedPlay` (SelectCapturedToPlay/DeclineCapturedPlay) | Dryden Vos SHD_192 |
| `rescue_guarded` | "The DEFENDING player may rescue a card they own guarded by this unit. If they do, draw N." A binary decision handed to the OPPONENT (the say_no deciding-player shift) that canNOT collapse to an optimal-play default — the rescue costs its owner two cards of tempo for the attacker, so both branches are real. Candidates are only captives the DECIDER owns, guarded by the source; pushed only when one exists. Both actions hand the seat back unconditionally (an On Attack leaves a `pre_attack` bookmark buried below). New shared `actions._rescue_captured_card(s, ci)` = the CR rescue destination, the OWNER'S HAND (vs `_release_captured_cards`' leave-play return to arena); SHD_76 now calls it too (RescueGuardedCard/DeclineRescue) | Cad Bane TWI_187 |
| `reveal_cull_draw` | "Reveal the top N cards of your deck.  An opponent discards X of them.  Draw 1 of the remaining cards and discard the other." A two-stage DECIDER-SHIFT over one fixed revealed set (the say_no SOR_233 seat-flip with a select-N stage on each side): the OPPONENT culls first (`CullRevealedCard`), then the seat moves to the controller, who takes one survivor (`DrawRevealedCard`) and discards the rest. Neither stage collapses to an optimal default — one player is denying, the other keeping — so both are real prompts. The revealed cards stay in the DECK while the decision is open (the deck_search convention: nothing else can happen with a decision pending, so no set-aside zone and conservation holds); `cull` is capped at `len(revealed) - 1` so a short deck still leaves something to draw | Admiral Trench JTL_14 |
| `play_resource_units` | "Reveal any number of resources you control; play each unit revealed this way for free (one at a time)." A repeated single-select LOOP over the controller's Unit resources (revealing a non-unit is pointless → optimal-play collapse offers only units): each pick removes that resource from the row (NOT replaced from deck — the resource count drops, the card's tradeoff) and enters the unit for free; the finish RE-PUSHES the loop with the remaining units BEFORE playing, so the just-played unit's triggers (pushed on top) resolve before the next pick — faithful "one at a time" LIFO. Decline always offered (the "any number", incl. zero); fizzles with no unit resources (SelectResourceUnitToPlay/DeclineResourceUnitPlay) | Endless Legions SHD_109 |

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
