# SWU Game Engine — Developer Reference

## Phase 7 status (in progress — 2026-06-16): systematic deck-encoding workflow

The machinery to take any unshipped deck from "partly implemented" to "shippable",
**one small group per session, human-in-the-loop.**

**The expansion workflow (plan → paste id → encode → verify → graduate):**
1. **Plan** (free, deterministic, offline — no LLM, no network):
   `python scripts/plan_encoding.py --deck tests/fixtures/<deck>.json` (or
   `--set SHD`). Finds every not-yet-playable card, clusters the gaps into ordered
   **groups**, and writes `encoding/<slug>/{MANIFEST.md, manifest.json,
   group_NN_*.md}`. Three group **kinds**: `keyword` (blocked only by a deferred
   keyword — implement the keyword once, engine-side, to unlock all listed cards),
   `ability` (text-bearing cards clustered by mechanical bucket, capped at 7), and
   one escalation group **per** suspected new primitive (`New primitive: <name>`).
   Order: keyword groups first, then simple ability groups, then escalations last.
   Re-runnable: stable group ids persisted in `manifest.json`; a re-run refreshes
   progress and never clobbers a spec whose cards are all playable.
2. **Encode** one group: paste its id (e.g. `shd-han-solo:03`) into the
   bottom of `docs/encode_group_prompt.md` and run a fresh session with that as
   the prompt. The spec file is fully self-contained (rules text, mechanical
   analysis, existing primitives that suffice, suspected new primitives, residual
   text, per-card acceptance criteria).
3. **Verify**: `python scripts/verify_encoding.py <slug> [--group NN]` re-runs the
   audit, refreshes `MANIFEST.md`/`manifest.json` progress in place, runs the
   group's focused tests, and prints the next suggested group (lowest-seq
   incomplete group whose deps are met).
4. **Graduate**: `python scripts/verify_encoding.py <slug> --graduate` runs the
   gate — 100% of cards `implemented`+, fast+medium suites green, a clean
   deck-specific soak — and on a full pass marks the deck shippable in
   `docs/decks_status.md` (the human still owns the final manual UI smoke pass).

**Classification note:** functional-text detection is now a **single canonical
rule** — `audit_coverage.has_functional_text(full_text, keywords)` (strip reminder
parentheticals + keyword cost brackets, subtract the card's own keyword names; any
remaining prose word ⇒ functional text). `plan_encoding.has_functional_text`
delegates to it, and the verifier reuses the planner's `classify_card`, so the
audit, planner, verifier, and `tests/test_deck_coverage.py` all agree. This
replaced the old `audit_coverage._has_ability_text` trigger-word pattern list,
which mislabelled every plain-effect event ("Deal 2 damage") and conditional
static ("While X, this unit gains …") as *vanilla* and so over-reported the
headline "playable" count by ~700 cards (2026-06-17). `_has_ability_text` remains
only as a deprecated single-arg shim (no keyword context). At campaign-setup the
honest full-DB count was **1213 playable / 1394 text-bearing gaps / 29
keyword-deferred** (Support only); it drifts as the campaign lands cards —
regenerate anytime with `scripts/audit_coverage.py`.
NOTE: `(set_code, card_number)` is NOT unique — every Leader (numbered 1, 2, 3, …)
collides with a Token reusing that low number (29 keys; see Phase 5 image note).
The true unique key is the DB `id`. When a (set, number) reference must be
resolved (deck audits, `load_details`), prefer the **non-token** row:
`audit_coverage.index_by_set_number` and `plan_encoding.load_details` both do this
(`audit_coverage.TOKEN_TYPES`), so a deck's leader no longer mis-resolves to its
token. The whole-DB report counts every physical row by `id` (tokens included as
their own rows). With this, the audit and planner classifiers agree on every key.

**The new-primitive escalation rule (protects the frozen engine):** a small,
self-contained new primitive (a new effect dataclass + its resolver arm, or a new
decision kind) may be added inline **with synthetic-card tests**. But anything
touching core resolution, the trigger/decision machinery, or needing a
replacement-effect system must **STOP and be flagged for a dedicated framework
session** — never jammed into a card batch. The planner pre-flags suspected new
primitives as their own one-card groups so this is visible up front.

**Reprint aliasing (2026-07-04):** exact printed-face duplicates (promos/variants
of an implemented card) are made playable for free by `src/swu/cards/reprints.py`'s
`REPRINT_ALIASES` (reprint→canonical), applied LAST in `cards/__init__.py` to copy
`_REGISTRY[canonical]` (+ escape-hatch) onto the reprint key; regenerate/verify with
`python scripts/find_reprints.py [--check]` (47 mirror aliases landed → audit
playable 744→791). See [[project-reprint-duplicates]].

### Gap-filling campaign (all remaining sets)

The precon/starter decks are done; the rest of the DB (~1400 text-bearing gaps plus
Support in ASH) is being filled **set by set** with a single reusable command. Setup
pre-generated a plan for every set into `encoding/<code>-set/` (deterministic,
offline, free). The recurring loop is one skill:

- **`/encode-next [N]`** (default 3 groups) — pulls the next N incomplete groups from
  the global queue, implements + tests them, runs **one** fast suite for the batch,
  and stops at a clean boundary. Stateless: works identically after /compact, /clear,
  or a restart (nothing to resume).
- **`scripts/next_group.py --n N`** is the queue walker the skill uses: it replans
  every set, refreshes manifests in place, and prints the next groups (spec path,
  remaining `cards=`, ready `VERIFY:` command) with flags **ESCALATION** (needs a new
  primitive → STOP & flag), **KEYWORD-ENGINE** (Support), **KEYWORD-RESIDUAL**. The
  campaign order is its `SET_ORDER` constant (8 main expansions in release order, then
  IBH, the 2026 starter, then promos/tokens — 24 sets, ~231 groups).
- **Cadence**: focused `-k` VERIFY per group; **one** fast suite per batch (not per
  group); medium tier + `audit_coverage.py` only at a set MILESTONE. Never
  `--graduate` or soak a `*-set` slug — sets aren't decks.
- **Support** (ASH) WAS the last KEYWORD-ENGINE group and **landed in ash-set:01**;
  `"Support"` is now PHASE2 and `PHASE3_KEYWORDS` is empty, so no set plans a keyword
  group any more. Its residual-text cards landed in the next batch, completing
  `ash-set:01` (29/29) alongside `ash-set:02`.
- **Doc/memory discipline**: batches write NO per-card notes here and NO
  `docs/history/encoding_history.md` campaign entries — progress lives in the regenerated
  `encoding/<slug>-set/manifest.json`/`MANIFEST.md` + `docs/coverage_report.md`. One
  memory topic file tracks the campaign: `project_gap_campaign.md` (persistent memory).

## Engine seams & patterns catalog

> The full blow-by-blow encoding log for every deck lives in
> **`docs/history/encoding_history.md`** (and the `memory/` topic files). This section is the
> distilled, reusable version: the patterns, decision kinds, effects, and gotchas you
> reach for when encoding the remaining cards. When a card looks like an existing
> pattern, copy that pattern — do **not** invent a new one. Search
> `docs/history/encoding_history.md` for the canonical card (e.g. "SOR_135") to see the full
> reasoning and test names.

### Decks fully encoded (all graduate-eligible unless noted)

shd-han-solo · sabine-mean-green · the-mandalorian · moff-gideon · leia-organa ·
ahsoka-tano · general-grievous · jabba-the-hutt · boba-fett · han-solo · darth-maul ·
qui-gon-jinn · chancellor-palpatine · padme-amidala — **all 52/52, graduate-eligible**.
(qui-gon-jinn's LOF_197 Aethersprite "duplicate-the-next-WhenPlayed" IS implemented —
`arm_when_played_redo`, `src/swu/cards/lof/abilities.py`.) Everything else in the DB is
the **gap-filling campaign** — see below.

### The recurring encoding patterns (reuse these by name)

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

### Decision kinds (each = a `push_*` helper + actions; register in 4 places, see below)

Reuse an existing kind before adding one. `granted_attack` and `play_from_hand` in
particular have accreted many optional fields — check them first.

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

**Adding a NEW decision kind** (only when nothing above fits, and it must not touch
core resolution or the trigger/decision machinery — else STOP and escalate): register
it in **four** places — `invariants._KNOWN_DECISION_KINDS`, `web/session.py` (`_PROMPTS`
+ any stage/label), a `HeuristicBot` handler + safe-default order, and its `push_*`
helper + `Action` subclasses. Push the decision **only when it can do something**.

### New effect / spec primitives (declarative, non-decision)

- **`excludes_event_targets` predicate + `StatBonus.count="controller_resources"` +
  `Condition.ANY_BASE_DAMAGE_MIN` + `peek_top` mode `may_draw_or_discard_heal`** — the
  sor-set:13–15 combat-tricks batch. `excludes_event_targets` reads an accumulating
  `event_ctx["excluded_target_ids"]` set (the plural of `excludes_event_target`) for
  multi-target "another … a third" chains (Attack Pattern Delta SOR_106);
  `controller_resources` scales a SELF StatBonus by resources controlled (97th Legion
  SOR_118); `ANY_BASE_DAMAGE_MIN` gates on *either* base's damage (Guerilla Attack Pod
  SOR_148); `may_draw_or_discard_heal` is a mandatory binary peek (draw vs discard+heal
  N, no keep) via `push_peek_top(discard_heal=N)` (Reinforcement Walker SOR_119).
- **sor-set:17 misc-abilities batch** — five additive play/attack/stat reads, no core-machinery
  touch: **`OpponentPlayTax(amount, card_type)`** marker adds to a card's cost when an ENEMY
  in-play unit carries it (`_opponent_play_tax` in `_play_cost`; the dual of the discount
  patterns — Del Meeko SOR_34 "opponent events cost 1 more"); **`NextPlayDiscount.exclude_aspects`**
  disqualifies a card carrying any listed aspect ("next non-[Heroism]/non-[Villainy] card" —
  Bendu SOR_56); **`StandingPlayDiscount` `applies_to="upgrade_on_source"`** + `target_host_id`
  threaded through `_standing_play_discount(_sources)`/`_consume_standing_discount` for a
  host-scoped once-per-round upgrade discount (Guardian of the Whills SOR_61 "first upgrade on
  this unit each round costs 1 less"); **`CannotAttackBases`** marker (own card OR an attached
  upgrade, `_cannot_attack_bases`) drops the base-attack option at enumeration (Entrenched
  SOR_72); **`ForbidNamedCardPlay`** marker makes an enemy namer's `named_card` bar that card at
  the play-legality seam (`_named_card_play_forbidden`), distinct from Galen's ability-suppression
  naming (Regional Governor SOR_62). Also: an upgrade-borne **`while_defending` ConstantAbility**
  now debuffs the attacker — `_constant_ability_power_bonus` scans the defender's attached
  upgrades (Electrostaff SOR_71, Lando LAW_108's ability on an upgrade). SOR_54 Jedi Lightsaber
  reused the Corrupted Saber LOF_187 GrantedAbility+`SOURCE_HAS_TRAIT` pattern (no new seam).
  **`game_memory.bases_cannot_heal_this_phase`** — a global phase-scoped "bases can't be healed"
  lock (Wolffe SOR_160), the heal-side mirror of CannotAttackBases: `_bases_cannot_heal(state)`
  read at every base-heal chokepoint (`_apply_restore`, `_apply_heal` on a Base target, the
  Redemption heal-distribution, Reinforcement Walker's discard-heal, the collector heal_base);
  default inert, cleared at the phase rollover. (`push_search_and_play_multiple` also gained a
  `max_units` cap — "up to N units" — for U-Wing Reinforcement SOR_104, reusing SOR_87's flow.)
  **`Condition.CONTROLLER_PLAYED_OTHER_CARD_THIS_PHASE`** (sor-set:19) — gates a trigger on the
  controller's `game_memory.cards_played_this_phase` count ≥2 ("if you played another card this
  phase"; the source's own play is already counted before trigger collection — Lothal Insurgent
  SOR_190). Same batch, no new seam: Disarm SOR_216 = targeted `ModifyStats(-4/0, THIS_PHASE)`
  event; Lando SOR_197 = CustomEffect auto-returning ≤2 of the controller's own resources to hand
  (the K-2SO SOR_145 fungible-resource auto-select convention).
  **`Condition.CONTROLLER_ATTACKED_OTHER_TRAIT_UNIT_THIS_PHASE(param=trait)`** (shd-set:01) — a
  friendly unit (≠ the source) with the trait is in `game_memory.units_attacked_this_round` ("if you
  attacked with a(nother) <trait> unit this phase"; attacks only happen in ACTION and the set clears
  at the round rollover, so this-round ≈ this-phase — the `attacked_this_phase` predicate precedent).
  The source-exclusion lets one atom serve both Bo-Katan Kryze SHD_12 clauses ("a Mandalorian unit"
  undeployed, where the undeployed leader never attacked, and "another Mandalorian" on her On Attack).
- **shd-set:02–04 direct-damage batch** — four small additive seams, no core-machinery touch:
  **`push_select_damage(decider_id=, after_resolve_idx=)`** — the `select_damage` decision now
  accepts a COLLECTOR-decider override (mirrors `push_select_token`), modelling a "Bounty — Deal N
  damage to a unit" where the collector picks the target (Val SHD_58, Wanted Insurgents SHD_167; "up
  to 1" collapses to mandatory in optimal play). **`DealDamageEqualTo` count `"source_damage"`** —
  damage currently on the source unit ("for each damage on this unit", Krrsantan SHD_139 On Attack).
  **`Condition.ENEMY_CONTROLS_BOUNTY_UNIT`** — an enemy unit carries a Bounty (reuses
  `resolver._unit_has_bounty`); gates Krrsantan's "if an enemy unit has a Bounty, you may ready this
  unit". **CardPlayed observer fire threads `event_ctx["played_card_id"]`** (`actions/api.py`, PlayCard
  observer fire) so a "When you play an upgrade …: deal 1 to THAT unit" observer can locate the
  played upgrade's host by scanning in-play units (Dengar SHD_133); purely additive (existing
  WhenYouPlayCard observers ignore the key).
- **shd-set:03–05 direct-damage batch** — three small additive seams, no core-machinery touch:
  **`DealDamageEqualTo` count `"event_played_card_cost"`** — the opponent's just-played card's
  printed cost, recorded into `event_ctx` by the `WhenOpponentPlaysCard` matcher and threaded into
  `_scaling_magnitude(event_ctx=)`; "deal damage equal to that card's cost" to an enemy
  `ground_or_base` (Krayt Dragon SHD_172). **`Condition.SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE`** —
  the generic once-per-round gate for a TRIGGERED ability: the trigger's CustomEffect marks
  `f"{iid}:trig"` in `game_memory.activated_abilities_used_this_round`, the condition gates
  collection (offered ≤1×/round), so declining an optional trigger does not spend the use (the Bossk
  recollect pattern, but for any trigger — Toro Calican SHD_239). **Regroup token-defeat sweep** —
  `_enter_regroup` now also detaches any attached-upgrade TOKEN flagged `defeat_at_regroup` (mirrors
  the unit `defeat_at_regroup` sweep); a WhenPlayed CustomEffect gives a Shield via `attach_token`
  and sets the flag (Jetpack SHD_225). Also this batch (pure reuse): Ma Klounkee SHD_229 = the In
  Pursuit TWI_221 "If you do" pattern (`requires_prior_target`); Detention Block Rescue SHD_180 =
  Zeb LAW_45 conditional-magnitude (6 if the target guards captured cards, via `captured_by` scan);
  Vambrace Flamethrower SHD_177 = GrantedAbility(OnAttack)+`push_distribute_damage`. SHD_170 IG-11's
  capture-replacement clause and SHD_163/226 stay FLAGGED escalations (replacement effect /
  any-player discard observer / play-defeated-unit-under-control).
- **shd-set:03 framework session (two new self-contained seams)** — **`pay_and_steal_upgrade`
  decision kind** (`actions.push_pay_and_steal_upgrade` / `StealUpgrade` / `DeclineStealUpgrade` /
  `_stealable_upgrades`): pay a (non-token) upgrade's printed cost on another NON-Vehicle unit
  (`_exhaust_resources`), then RELOCATE it onto the source via `_relocate_upgrade` ("take control" is
  implicit — control follows the host) when `_upgrade_target_spec`/`_spec_matches_ci` admits the
  source, else `_apply_defeat_unit` it (Pre Vizsla SHD_142; the `move_upgrade` SHD_64 sibling, plus
  pay + cross-control + defeat-if-can't-attach). **Forced-attack COMPULSION**
  (`game_memory.forced_attack` dict `{player_id, unit_id}`, phase-scoped): read at the ACTION-phase
  legal-action seam `actions._forced_attack_actions` — while set and the flagged player is active and
  the unit is able, `legal_actions` returns ONLY that unit's attacks (a unit target if any, else
  base), else the compulsion is vacuous; consumed by the flagged player's next action in
  `actions.apply` and cleared at phase rollover (Give In to Your Anger SHD_144). Both registered in
  all the usual places (`_KNOWN_DECISION_KINDS`, `_decision_legal_actions`, web `DECISION_PROMPTS`,
  bot `_SAFE_DEFAULT_ORDER`).
- **`WhenPlayerDiscardsFromHand`** — settle-drain observer for "When A PLAYER discards a card from
  their hand" (Migs Mayfeld SHD_163). Any-player (NO owner guard, like
  `WhenIndirectDamageDealtToUnit`) and DISCARD-only: a dedicated discard-only ledger
  `game_memory.hand_discards` is fed by `actions.record_hand_discard(..., kind="discard")` (the
  disclose reveal path passes `kind="reveal"` and is excluded), drained at the settle-point by
  `actions._fire_hand_discard_observers`. Not a decision kind — reuses `optional` (the "you may"),
  `DealDamage(unit_or_base)`, and the shared `SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE` limiter (Toro
  SHD_239 `{instance_id}:trig` marker) for "once each round". (shd-set:04 framework session)
- **shd-set:11–13 leaders & combat-tricks batch** — six small additive seams, no core-machinery
  touch: **`push_deck_search(decider_id=)`** — a COLLECTOR-decided deck search over the decider's
  own deck (mirrors `push_select_token`'s decider_id; after_resolve stays the current active player):
  a bounty's "search YOUR deck" resolves for the OPPONENT of the dying host (Enticing Reward SHD_222).
  **`_resolve_granted_bounty` `next_unit_discount:N` key** — a phase-granted `granted_bounties` arm
  (The Client SHD_31 seam) recording a pending `NextPlayDiscount` for the collector's next unit
  (Jabba the Hutt SHD_6 "next unit you play costs N less"). **`WhenYouPlayCard.via_smuggle`** — a
  controller-observer for "when you play a card USING Smuggle" (reads `event_ctx["via_smuggle"]`,
  unlike the self-firing `WhenPlayedViaSmuggle` — Hondo Ohnaka SHD_5). **`WhenYouPlayCard.has_any_keyword`
  filter + `has_any_keyword` TargetSpec predicate + `keywords.has_any_keyword()`** — "a unit that has
  1 or more keywords" (Boba Fett SHD_8 trigger + deployed aura); the helper is a LIGHTWEIGHT check
  (printed keywords minus revokes + modifier grants only) BECAUSE iterating `has_keyword` over the
  Keyword enum recurses through the very aura target that uses the predicate (aura-only-granted
  keywords are a documented non-count). **`DiscardCardCost`** — an activated-ability cost spec
  ("discard a card from your hand"), parallel to `ExhaustSelf`/`PayResources`/`DefeatSelf`/`UseForce`;
  wired at the UseAbility payment site + all three `legal_actions` affordability checks; first-card
  discard (Kylo Ren SHD_11 undeployed). **`Condition.ENEMY_UNIT_UPGRADED`** — any enemy arena unit
  carries ≥1 attached upgrade (Shield/Experience tokens count; Sugi SHD_52), the enemy-arena-scan
  sibling of `ENEMY_HAS_DAMAGED_UNIT`. Concord Dawn SHD_42 reused `while_target_defending` with
  `fixed=SELF` for "+2/+0 while defending". GOTCHA: a "may exhaust, if you do buff a TARGET" trigger
  must be ONE `CustomEffect.target` (Kylo SHD_141 pattern), not `[no-target CustomEffect, targeted
  ModifyStats]` — the two-effect form leaves the modifier unapplied.
- **shd-set:14–16 combat-tricks batch** — four small additive engine seams, no core-machinery
  touch: **`DealDamageEqualTo count="source_power"`** — damage equal to the source's *effective*
  power via `compute_power` (Crosshair SHD_87 "deals damage equal to his power"). **`defeated_upgraded`
  TargetSpec predicate** — reads `event_ctx["defeated_upgrades"]` (the snapshot `_defeat_unit` stashes
  before detaching), because the plain `upgraded` predicate reads empty at `UnitDefeated` (attached_upgrades
  already cleared); gates a `WhenUnitDefeated(controller="enemy")` observer on "an *upgraded* enemy unit
  is defeated" (Punishing One SHD_137, once/round via `SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE`).
  **Combat `event_ctx["attack_defeated_defender"]` key** — the defeated defender's id threaded at BOTH
  `OnAttackDefeatsUnit` fire sites (purely additive, like `played_card_id`), so an OnAttackDefeatsUnit
  CustomEffect can locate the just-defeated defender in its owner's discard (Arquitens SHD_122 "put the
  defeated unit into play as a resource under your control" — relocates it facedown into the attacker
  controller's resource row, control-follows-holder). **`push_granted_attack(repeat_max=N)`** — caps the
  `repeat` re-push at N attacks ("Attack with up to 3 units", Headhunting SHD_145; None = the unbounded
  Mon Mothma SEC_103 "any number"). Also this batch (self-contained card-module effect, no engine change):
  Unexpected Escape SHD_76 "rescue a captured card" returns a captive to its OWNER'S HAND (the CR rescue
  destination — the mirror of `_release_captured_cards`, which returns to arena), auto-rescuing only
  controller-owned captives (the beneficial subset, collapsing the "you may"). PURE REUSE: SHD_86 Warbird /
  SHD_112 Gamorrean / SHD_169 Clan Challengers = SELF conditional StatBonus/KeywordGrant (Scimitar LOF_233 /
  Protector SHD_247); SHD_101 Adelphi = push_granted_attack with the +2/0 decided from the fixed round
  initiative at resolution (no new field); SHD_103 Rieekan = conditional-magnitude CustomEffect.target
  (has_keyword ? Experience : this-phase `keyword_grant` Sentinel modifier); SHD_116/185 = printed Bounty
  reusing `_price_on_your_head_bounty` / the Wanted SHD_221 collector-ready-resources pattern; SHD_117/140/182
  = CostReduction / WhenPlayed gated by `ENEMY_CONTROLS_BOUNTY_UNIT` / `ENEMY_UNIT_DEFEATED_THIS_PHASE`.
  ESCALATION FLAGGED (shd-set:16, NOT built): SHD_155 Heroic Resolve = an UPGRADE granting an ACTIVATED
  ("Action") ability to its host with a "defeat THIS upgrade" cost — the legal_actions activated-ability
  enumeration only scans a unit's OWN abilities (never an upgrade-granted ActivatedAbility) and `DefeatSelf`
  defeats the host, not the upgrade ⇒ core legal-actions/UseAbility machinery, a dedicated framework session.
- **shd-set:18 combat-tricks batch** — two small additive engine seams, no core-machinery
  touch: **`KeywordIfPlayedFromHand(keyword)`** marker (registry) — `_put_unit_in_play` grants
  the keyword as a this-phase modifier BEFORE the enter-play keyword bus (so a granted Ambush
  triggers on entry) ONLY when `play_source=="hand"`; a Smuggle/discard/plot/token entry does
  not.  The printed keyword the API mistags on such a card is stripped by NEW keyword-sanitiser
  rule 6 (`_played_from_hand_grant_keywords`) so the marker — not an always-on printed bar —
  owns it (Millennium Falcon SHD_204 → Ambush).  **`game_memory.lose_at_regroup: set`**
  (serialized) — player_ids forced to LOSE at the next regroup start; `_enter_regroup` marks each
  listed player's base defeated (→ `is_eliminated` → `_check_game_over`) as its first action, then
  clears the set (Final Showdown SHD_208 = ready-each-friendly CustomEffect + schedule).  PURE
  REUSE this batch: SHD_211 Fugitive Wookiee "Bounty — Exhaust a unit" = `is_bounty` WhenDefeated
  CustomEffect resolving for the collector (opponent of `event_ctx["defeated_controller_id"]`) with
  the exhaust target AUTO-PICKED (Xanadu Blood SHD_191 documented auto-exhaust); SHD_212 Privateer
  Scyk = SELF KeywordGrant("Shielded") gated `CONTROLLER_HAS_OTHER_ASPECT_UNIT("Cunning")` (Hunter
  of the Haxion Brood SHD_186 conditional-Shielded pattern).
- **shd-set:18 framework session (the two escalations, now built)** — **`let_wookiee_win`
  decision kind** (Let the Wookiee Win SHD_205): a cross-decider two-stage modal — the OPPONENT
  picks the mode (`push_let_wookiee_win`, `deciding_player_id=opponent`), then `ChooseWookieeMode`
  either readies up to 6 of the CONTROLLER's resources (fungible, resolved inline) or shifts the
  decision to the controller (reassign BOTH `deciding_player_id` and active seat — apply's
  decision-stack re-pin reads `deciding_player_id`) for `ChooseWookieeReadyUnit`, which readies a
  chosen friendly unit and, if it is a Wookiee, chains into `push_granted_attack(attacker_id=…,
  power_bonus=2)`.  (push_modal is controller-only and can't chain an attack, hence its own kind.)
  **`change_resource_control(s, resource_ci, new_controller_id, *, link_to)` + the
  `_revert_orphaned_resource_control` settle sweep** (DJ SHD_213): resource control is implicit like
  unit control (whoever's `resources` row holds it; `owner_id` unchanged) — the seam relocates a
  resource between rows and stamps `control_linked_to` = the thief unit's id (the Maul LAW_54 field,
  which `_revert_linked_control` never touches for resources since they aren't in an arena); the
  settle sweep in `apply` returns the resource to its owner once the thief leaves play by any path.
  DJ = WhenPlayedViaSmuggle CustomEffect stealing an auto-picked READY enemy resource.  The
  ControlChanged event for a (face-down) resource carries a neutral `card_name` to avoid leaking it.
- **shd-set:19 combat-tricks batch** — four small additive engine seams, no core-machinery
  touch: **`WhenYouPlayCard.non_unit`** filter — fires only for a played event/upgrade and
  records `event_ctx["cost_le_threshold"]` like the other filters, so the TWI_184 "exhaust a unit
  costing ≤ the played card" pattern works for "a non-unit card" + the Toro SHD_239 once-per-round
  gate (Tobias Beckett SHD_217).  **`pay_or_exhaust` `pay_amount` context field + single-target
  `push_pay_or_exhaust`** — generalises the Eye of Aldhani SEC_73 fixed-1-resource pay to N, and
  pushes a one-unit decision addressed to the CHOSEN target's controller ("Exhaust a unit unless
  its controller pays 2", Look the Other Way SHD_227).  **`push_granted_attack(cross_arena=,
  bonus_if_defender_ground=)`** — a decision-scoped temporary CrossArenaAttack (the space attacker
  may reach the ground arena for THIS attack, threaded into `_enumerate_attacks` + the
  AttackWithUnit cross-arena guard) plus an arena-gated bonus (the attacker `power_bonus`/`hp_bonus`
  AND the `defender_*_bonus` debuff apply only vs a ground unit-defender) — Swoop Down SHD_230.
  **`WhenEnemyAttacksYourBase`** observer trigger — fires (collected at the existing base-attack
  `fire_triggered_abilities` site) when an opponent declares an attack on the source controller's
  base (AttackDeclared with a None defender + enemy attacker); records the attacker's arena in
  `event_ctx["same_arena"]` for a "friendly unit in the same arena" `GiveToken` (Kragan Gorr
  SHD_241).  PURE REUSE this batch: SHD_232 Relentless Pursuit = the Take Captive SHD_131 two
  dependent-CustomEffect capture (captor cost → `cost_le_threshold` ceiling) + a Bounty-Hunter-gated
  Shield in the first effect (so it lands even when no enemy is captured).
- **shd-set:20 misc-abilities batch** — three small additive seams, no core-machinery touch:
  **`push_play_upgrade_from_hand` choose-upgrade mode + `cost_reduction`** — the ASH_42
  play-an-upgrade-from-hand decision now also accepts `upgrade_id=None` (the controller PICKS an
  affordable hand upgrade, enumerated as (upgrade × legal host) action pairs carried on
  `PlayUpgradeFromHand.upgrade_id`) played at `cost_reduction` off via `_pay_play_cost` (Fenn Rau
  SHD_67 "play an upgrade from hand, it costs 2 less"; the second clause reuses the Kylo LOF_229
  `WhenYouPlayCard(card_type="upgrade", on_self=True)` observer + a targeted `ModifyStats`).
  **`game_memory.base_attackers_this_round`** (dict base_owner → [attacker ids], serialized,
  round-cleared) recorded at the base-attack DECLARE step + the **`attacked_your_base_this_phase`**
  predicate — "an enemy unit that attacked your base this phase" (Ephant Mon SHD_88, then a
  shared-event_ctx `_apply_capture` by a chosen friendly unit in the prey's arena via
  `same_arena_as_event`). **`eligible_host_for_event_upgrade`** predicate — reads
  `event_ctx["evidence_upgrade_id"]` and admits any legal `_eligible_upgrade_targets` host, so a
  chosen upgrade can be relocated onto a chosen host (Evidence of the Crime SHD_77 "take control of
  an upgrade ≤3 and attach it to an eligible unit" = two shared-event_ctx CustomEffects +
  `_relocate_upgrade`; control follows the host). PURE REUSE: SHD_16 Fennec (play_from_hand
  `cost_max`+`grant_keyword="Ambush"`, Energy Conversion Lab SOR_22) / SHD_51 Mystic Reflection
  (conditional-magnitude `ModifyStats` via a CustomEffect, Zeb LAW_45).
- **Unified `state.ability_suppressed(state, ci)` read-layer + `SuppressHostAbilities` marker**
  (framework session, shd-set:20 escalations) — the ~10 ability-read guards (has_keyword/keyword_value,
  `_collect_triggers`, both constant-stat-bonus scans, the arena UseAbility enumeration, the TraitGrant
  scan) now call ONE predicate that folds all three suppression sources: Mind Trick LOF_202's phase-scoped
  per-instance `abilities_suppressed`, Galen Erso P25_31's persistent name scan `is_name_suppressed`, and
  the NEW upgrade-borne `SuppressHostAbilities` marker (a pure registry spec on an upgrade; detected by
  scanning a host's `attached_upgrades`). Derived from the upgrade's presence, so both "can't gain
  abilities" (reads short-circuit) and persistence (lifts on detach) fall out for free — no stored flag
  (Imprisoned SHD_72). Add a future suppression source in this one predicate.
- **jtl-set:10–11 card-advantage & leaders batch** — nine small additive seams, no core-machinery
  touch (the new `play_via_piloting` decision kind has its own catalog row above).
  **`game_memory.foreign_free_discard_play_this_phase`** (dict permitted_player → [instance_ids],
  serialized, phase-cleared) — the CROSS-PILE sibling of Second Chance SHD_53's
  `free_discard_play_this_phase`: a player may play, for free, a card sitting in ANOTHER player's
  discard pile.  `_enumerate_discard_play_actions` gains a section (b2) scanning the other players'
  piles, and `PlayFromDiscard.apply` falls back to a scan of every discard when the card is not in
  the active player's own; the card enters under whoever plays it while `owner_id` — and therefore
  the pile it returns to — is unchanged (Stolen AT-Hauler JTL_221 "Choose an opponent.  For this
  phase, they may play this unit from its owner's discard pile for free").
  **`TargetSpec.cost_max_if_exhausted`** — a PER-CANDIDATE conditional cost cap ("a non-leader unit
  that costs 2 or less **or** an exhausted non-leader unit that costs 4 or less" = `cost_max=2` +
  `cost_max_if_exhausted=4`, Razor Crest JTL_223); the candidate-state sibling of `cost_max_boost`,
  which reads the source controller's board.  **`TargetSpec.trait_or_upgrade_trait`** — the
  DISJUNCTIVE trait filter "a <Trait> unit or a unit with a <Trait> upgrade on it" (Admiral Holdo
  JTL_7): the unit's own effective traits, else the printed traits of anything attached — in JTL that
  second arm is usually a trait-carrying Pilot riding a Vehicle.  **`same_arena_as_source` predicate**
  — "another unit in this arena" anchored on the SOURCE unit (the `same_arena_as_host` sibling for an
  ability resolving from a unit rather than an upgrade's host; Major Vonreg JTL_11's granted On Attack).
  **`push_bottom_from_discard(exclude_ids=)`** — an EVENT is already in its owner's discard when its
  own ability resolves, so "put **another** card in a discard pile…" must exclude itself while still
  offering a second copy of the same card (Commence Patrol JTL_205, whose `then_create_token` payoff
  already delivered "If you do").  **`push_name_and_discard(card_type=)`** — narrows what may be NAMED
  while the whole hand stays revealed ("Look at an opponent's hand and discard an **event** from it",
  Jam Communications JTL_207); no card of that type ⇒ fizzles with no prompt, like an empty hand.
  **`push_play_from_hand(then_select_token=<dict>)`** — an "…If you do, <give a token / buff a unit>"
  SETTLE payoff pushing a `select_token` once the play has really happened, with two settle-only keys
  `require_both_arenas` and `exclude_played`.  ⚠️ It cannot be a second EFFECT of the ability: the
  resolve_effects walker runs an earlier no-target effect only when the LATER targeted one is chosen,
  so the payoff would land *before* the play (Lando Calrissian JTL_3's Shield, Major Vonreg JTL_11's
  +1/+0 to "another" unit).  `push_select_token` also gained `arena=` and `exclude_ids=`.
  **`StandingPlayDiscount` `applies_to="trait:<Trait>"`** + `once_per_round=False` — "Each Capital Ship
  unit you play costs 2 resources less" (Admiral Piett JTL_5); the discount scan walks ARENA units, so
  an undeployed leader in the base zone grants nothing and the deployed-only reading is free.
  **`NextPlayDiscount.applies_to_piloting`** — "(This includes Piloting costs.)" (Wedge JTL_8): the
  entry is also read by `_piloting_cost` and consumed by `PilotPlay` / `PlayViaPiloting`, a path the
  ordinary hand-play discount never reaches.  **`Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND` param may
  be `(trait, reduction)`** so the gate is measured at the discounted price the decision will offer.
  ⚠️⚠️ **TOKEN COLLISION, now hit on JTL_3 (Experience) and JTL_4 (Shield):** unlike JTL_1, whose twin is
  a token UNIT, a **`GrantedAbility` is NOT safe for a token-UPGRADE number** — the granted-trigger scan
  reads a host's `attached_upgrades`, which is exactly where an Experience/Shield token lives.  Only
  `ActivatedAbility(undeployed_only=)`, `TriggerAbility(deployed_only=)` and
  `TriggerAbility(WhenDeployed(via_pilot_leader=True))` are safe there; Lando's "Attached unit gains
  Sentinel" is therefore a PERMANENT `keyword_grant` modifier from his deploy-as-an-upgrade trigger (the
  Asajj JTL_1 recipe).  PURE REUSE: JTL_197 = `GrantedAbility(WhenAttackEnds)` + a CustomEffect returning
  the pilot upgrade (a non-leader unit riding as a Pilot never has its OWN triggers collected); JTL_220 =
  optional `WhenDefeated` `ReturnToHand` over `power_max`; JTL_223's trigger = `WhenYouPlayCard(on_self=True,
  trait="Pilot")` (both play paths attach before CardPlayed fires; a LEADER deploying as a Pilot fires
  LeaderDeployed instead and is a documented non-trigger).  **ESCALATION FLAGGED (jtl-set:11, NOT built):
  JTL_2 Grand Admiral Thrawn** "When you use a 'When Defeated' ability: use that ability again" — needs an
  observer on the *use* of an entire trigger CLASS plus re-resolution of an arbitrary ability; Bossk
  SHD_10's `push_bounty_recollect` only re-runs an explicitly `is_bounty`-tagged ability and does not
  generalise ⇒ trigger-system + core-resolution surface, a dedicated framework session.
- **jtl-set:12–14 pilots, shields & tempo batch** — one new condition atom plus three context
  filters on an existing decision kind; no new decision kind, no core-machinery touch.
  **`Condition.CONTROLLER_HAS_TOKEN_UNIT`** — the condition sibling of the long-standing
  `token_unit` target predicate ("While you control a token unit, this unit gains Raid 1",
  First Order TIE Fighter JTL_81; the conditional self-grant makes the sanitiser strip the
  printed Raid, so a lone TIE really lacks it).  **`push_move_upgrade(from_host_id=,
  dest_traits=, include_tokens=)`** — three narrowings of the board-wide Survivors' Gauntlet
  SHD_64 decision, stored in the decision CONTEXT so the enumeration and both apply-guards
  re-derive the same set ("attach an upgrade on **this** unit to another eligible friendly
  **Vehicle** unit", U-Wing Lander JTL_70).  `include_tokens` is the notable one: the
  engine-wide `kind="upgrade"` convention excludes Shield/Experience tokens, and without it
  JTL_70's own two halves (3 Experience on entry, then ferry one onward) would not talk to
  each other.  ⚠️ **The "attached unit gains …" ConstantAbility(SELF) convention only works
  when the card PRINTS what it grants** — the ARENA constant scans walk units by (set, number)
  with no upgrade gate, so a spec whose unit-side reading differs leaks.  IG-88 JTL_141 is
  safe (same buff either way) and JTL_34/45/58 are safe (they print Grit / Restore 1 /
  Sentinel), but Phantom II JTL_50 is a plain 3/3 that gives its host **+3/+3** — so its buff
  is a pair of PERMANENT modifiers applied at attach time (the Lando JTL_3 recipe), whose
  lifetime `_modifier_source_in_play` / `keywords._permanent_kw_source_in_play` already tie to
  the upgrade staying in play.  PURE REUSE worth knowing: JTL_50's attach = `_attach_unit_as_pilot`
  (Poe JTLP_6), which already does everything the printed insert asks (shed upgrades, clear
  damage, drop unit-targeted modifiers), and "If this card is a unit" is free because a bare
  `ActivatedAbility` is only enumerated from arena units — an attached upgrade needs a
  `GrantedAbility` wrapper; JTL_32 Director Krennic = `StandingPlayDiscount()` at its DEFAULT
  `applies_to="has_when_defeated_ability"`, which was built for his own prerelease twin JTLP_1;
  JTL_66 = `push_distribute_heal(include_bases=False, then_damage_self=False)` (Redemption
  SOR_52's heal flavour of the `distribute_damage` pool); JTL_77 = two `fixed=EACH_IN_PLAY`
  effects, the second an existing `RevokeKeyword` whose `keyword_revoke` modifier `has_keyword`
  checks BEFORE every grant source, so "can't gain Saboteur this phase" falls out free;
  JTL_16 Ackbar = ONE targeted `CustomEffect` exhausting the victim and creating an X-Wing for
  **its** controller (`find_instance` returns the holding player), because `CreateTokenUnit
  (player=)` only knows controller/opponent/each; JTL_15 Rio = `push_granted_attack
  (attacker_arena="space", grant_keywords=["Saboteur"])` plus `ConstantAbility(SELF, StatBonus)`
  gated by `SOURCE_HAS_TRAIT("Transport")` — the first use of that atom at the
  `_upgrade_self_stat_bonus` seam, which evaluates a condition against the HOST;
  JTL_76/86 = "create/attach, THEN token another unit" as a single no-target `CustomEffect`
  pushing `select_token(exclude_ids=…)`, again because the resolve_effects walker would
  otherwise run the targeted half first (the JTL_3 lesson); JTL_73 Grim Valor =
  `GrantedAbility(WhenDefeated)` read out of `event_ctx["defeated_upgrades"]` (Public Enemy
  SHD_68).
- **jtl-set:15–16 combat-tricks batch** — seven small additive seams, no new decision kind, no
  core-machinery touch.  **`ConstantAbility.upgrade_only`** — the general CLOSER for the
  "attached unit gains …" leak flagged in the bullet above: an `upgrade_only=True` spec is
  skipped by the four ARENA scans (`keywords.has_keyword` / `keyword_value`,
  `_constant_ability_power_bonus` / `_hp_bonus`) and read ONLY by the attached-upgrade scans, so
  a Piloting card whose grant differs from its unit side is finally expressible (Jarek Yeager
  JTL_109 "attached unit gains Sentinel" — without it his 2/3 UNIT side hands itself Sentinel).
  Sanitiser rule 2 still strips the mis-tagged printed keyword, since it keys on the conditional
  SELF grant regardless of the flag.  ⚠️ **`Condition.SOURCE_POWER_MIN` now carries a REENTRANCY
  GUARD** (`registry._POWER_MIN_EVALUATING`) — it was safe only on TriggerAbilities; on a
  ConstantAbility (Vonreg's TIE Interceptor JTL_137 "While this unit has 4 or more power, it
  gains Overwhelm") its `compute_power` call re-enters the very arena/keyword scans that
  evaluate it, recursing without bound.  Re-entry reports False, which is also the right
  answer: the gated grants (Overwhelm; Raid, a while-ATTACKING bonus) never contribute to the
  non-attacking power being measured, so a 5-power Interceptor cannot bootstrap itself to 6.
  Three new condition atoms — **`CONTROLLER_HAS_GROUND_AND_SPACE_UNIT`** (JTL_109),
  **`OPPONENT_MORE_SPACE_UNITS_THAN_CONTROLLER`** (the arena-scoped sibling of
  OPPONENT_MORE_UNITS_THAN_CONTROLLER, Special Forces TIE Fighter JTL_135), and
  **`CONTROLLER_DEALT_INDIRECT_DAMAGE_THIS_PHASE`** over the new phase-scoped ledger
  `game_memory.indirect_dealers_this_phase`, fed at the single indirect-damage settle point and
  read from HAND at the play-cost site (Decimator of Dissidents JTL_138).  Plus
  **`game_memory.cannot_attack_bases_this_phase`** — the phase-scoped PER-INSTANCE sibling of the
  `CannotAttackBases` card marker, read at the same `_cannot_attack_bases` seam, for a bar an
  effect grants rather than a card prints (Scramble Fighters JTL_92);
  **`CostReduction.per_friendly_pilots`** (Red Leader JTL_101, the `other_friendly_pilots`
  StatBonus basis WITHOUT its self-exclusion — the card is in hand, so it cannot count itself);
  **`StatBonus count="other_friendly_space_units"`** (Clone Combat Squadron JTL_115); and
  **`push_exhaust_combined_cost(then_create_token_per_unit=)`**, a resolve-time rider creating one
  token per unit actually exhausted (All Wings Report In JTL_122).  GOTCHA: do NOT narrow a
  `WhenYouPlayCard` Pilot-attach observer with `card_type="upgrade"` — a *Pilot upgrade* is
  usually a Piloting UNIT card riding a Vehicle, whose printed type is "Unit"; `on_self=True`
  already implies "attached to the source", which is the whole filter JTL_101 needs.
- **The ability-redo chokepoint** (`resolver._schedule_ability_redo`) — "use that ability again",
  generalised from the Aethersprite LOF_197 When Played version to cover **When Defeated** too
  (Grand Admiral Thrawn JTL_2).  One function, dispatching on trigger type; the three call sites
  (inline resolve, mandatory-with-decision, `actions.AcceptTrigger`) call it unconditionally
  instead of guarding on `WhenPlayed`.  The re-use is inserted as an ordinary `trigger_option`
  just BELOW the original's resolution, so it runs after the original and everything it spawned —
  **no new decision kind, so no web/bot registration.**  WhenPlayed keeps its phase charge
  (`game_memory.when_played_redo_charges`, spent on OFFER); **When Defeated instead reads a
  `WhenDefeatedRedo` passive marker its controller has in play, whose price is charged on ACCEPT
  ONLY** (`redo_source_id` / `redo_cost_exhaust` / `redo_once_per_round` on the redo decision's
  context) — declining a "you may" is not a use.  A redo is only OFFERED while its price is
  payable, and `event_ctx["ability_redo"]` stops a re-use arming another.  Thrawn = two markers,
  one per leader side (undeployed exhausts himself; deployed is free but `once_per_round` over
  `game_memory.when_defeated_redo_used_this_round`).  **Bounty (`is_bounty=True`) and
  `WhenDefeatedAsUpgrade` are deliberately NOT "When Defeated abilities"** — the first is its own
  keyword collected by the dying unit's OPPONENT (so `owner_id` would credit the wrong player),
  the second is a defeat *replacement*.
  ESCALATION FLAGGED (jtl-set:15, NOT built): JTL_94 Luke Skywalker "You Still With Me?" — "If
  this upgrade would be defeated, you may instead move him to the ground arena as a unit and
  exhaust him" is a REPLACEMENT effect on upgrade defeat with a player choice inside it, needing
  both a divertable interception point in the defeat pipeline (upgrades die from ≥2 sites) and a
  decision pushed MID-defeat ⇒ core resolution + decision machinery, same class as SHD_170.
- **jtl-set:17–19 combat-tricks batch** — one new observer trigger plus nine small additive
  widenings, no new decision kind, no core-machinery touch.
  **`WhenUnitReadies`** observer trigger — "When attached unit readies" (In Debt to Crimson
  Dawn JTL_192, wrapped in a `GrantedAbility` so the HOST is the source).  The
  `WhenUnitHealed` settle-drain shape verbatim: a ledger `game_memory.ready_events` is fed by
  `actions.note_unit_readied` at the two ready chokepoints (the regroup mass-ready
  `_ready_all_cards` and the `ReadyCard` effect arm — call it BEFORE clearing `exhausted`, so
  an already-ready card records nothing) and drained by `actions._fire_ready_observers` at the
  action settle-point, which is what lets the payoff (`push_pay_or_exhaust(pay_amount=2)`)
  push a decision arising from inside the REGROUP phase.
  **`game_memory.unit_play_tax_this_phase`** (dict player → extra, serialized, phase-cleared) —
  the effect-GRANTED, phase-scoped sibling of the always-on `OpponentPlayTax` card marker (Del
  Meeko SOR_34), folded into the same single surcharge site `_opponent_play_tax`: recorded
  against a PLAYER, so it survives its source leaving play and two hits in one phase stack
  ("Each unit that opponent plays this phase costs 1 resource more" — Moff Gideon JTL_188, on
  the existing `WhenDealsCombatDamageToBase`).
  **`ReadyRestriction.regroup_only`** — the marker narrowed to the REGROUP phase, so a card
  effect may still ready the unit mid-action ("doesn't ready DURING THE REGROUP PHASE unless its
  power is 4 or more" — Rampart JTL_182), paired with **`Condition.SOURCE_POWER_MAX`**, the
  ceiling mirror of `SOURCE_POWER_MIN` **sharing its reentrancy guard** (`_POWER_MIN_EVALUATING`).
  **`push_granted_attack(attacker_damage_prevention=True)`** — a decision-scoped `all`
  `damage_prevention` modifier (NOT `combat_only`) landed on the CHOSEN attacker at the attack
  site, the attacker-side sibling of `defender_power_bonus` ("Prevent all damage that would be
  dealt to it during this attack" — I Have You Now JTL_193).
  **`CostReduction.per_damaged_ground_unit`** — the ground-arena narrowing of the
  `damaged_units_in_play` count; unqualified, so BOTH players' ground arenas count (AT-DP
  Occupier JTL_163).  Four condition atoms —
  **`OPPONENT_MORE_RESOURCES_THAN_CONTROLLER`** (a MIRROR, not a negation: level satisfies
  neither — Cham Syndulla JTL_164), **`ANOTHER_PLAYER_N_PLUS_EXHAUSTED_UNITS`** (Blade Squadron
  B-Wing JTL_199), **`NO_INITIATIVE_CLAIMED_THIS_PHASE`** over `state.initiative_claimed_this_round`
  (claimable only in ACTION and reset at the rollover, so this-round ≡ this-phase), and its
  candidate-predicate twin **`no_initiative_claimed`** — a BOARD gate expressed as a predicate,
  because an `EventAbility` has no `condition` field and a `ConditionalEffect` cannot carry a
  targeted sub-effect, so failing it yields no candidates and the event fizzles unprompted (Face
  Off JTL_178, the `fewer_units_than_prior_target_controller` TWI_55 shape).  Plus the predicate
  **`fighter_or_transport`** (the `droid_or_vehicle` disjunction for the other JTL trait pair —
  Koiogran Turn JTL_179).
  ⭐ **"After completing this attack, …" = TWO abilities + LIFO, never two effects** (Barrel Roll
  JTL_228): the `resolve_effects` walker consumes a later targeted effect's choice at the current
  `effect_idx` (the Mandalorian SHD_18 wart), so a `[push_granted_attack CustomEffect, ExhaustCard]`
  pair prompts for the exhaust before the attack is even declared.  Registered as two
  `EventAbility`s, `_resolve_event_ability` walks them in order: the TARGETED one (ability 0)
  pushes its decision, then the lone no-target CustomEffect (ability 1) inlines and pushes the
  `granted_attack` ON TOP — attack first, exhaust after.
  PURE REUSE worth knowing: JTL_150 Biggs = three `ConstantAbility(SELF, upgrade_only=True,
  condition=SOURCE_HAS_TRAIT)` specs (Jarek Yeager JTL_109), and note his rules box lives in
  `epic_action`, not `text`, so the sanitiser's text-driven rule 1 cannot see it — rule 2 strips
  the mis-tagged Overwhelm/Grit off the conditional SELF grants regardless of `upgrade_only`;
  JTL_161 Tarkin = one aura `ConstantAbility` carrying BOTH a `StatBonus` and a `KeywordGrant`,
  his printed Overwhelm stripped by sanitiser rule 1 (Admiral Piett SOR_079); JTL_157 = the Toro
  Calican SHD_239 `SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE` + `{iid}:trig` limiter on an OnAttack
  self-ready; JTL_178/JTL_195 = the Fight Fire With Fire JTL_173 shared-`event_ctx` chain
  (`prior_target_id` + `same_arena` stamp, JTL_195 also stamping `power_le_threshold` for the
  LAW_41 `power_le_event_threshold` predicate — read BEFORE the exhaust); JTL_202 = a
  `WhenYouPlayCard(on_self=True)` observer **without** `card_type="upgrade"` (a Piloting card
  played as an upgrade prints type "Unit" — the Red Leader JTL_101 gotcha) onto
  `push_granted_attack(attacker_id=SELF)`; JTL_206 = ONE targeted CustomEffect doing both clauses
  (Kylo SHD_141) over `game_memory.cannot_attack_bases_this_phase` (JTL_92); JTL_211 = the Hera
  JTL_45 numeric "attached unit gains Raid 1"; JTL_238 = a Zeb LAW_45 conditional-magnitude
  `this_attack` modifier counting the opponent's damaged units.  ⚠️ TEST TRAP: JTL_240 Fett's
  Firespray has an On Attack that pushes `assign_indirect_damage`, so it is a poor stand-in
  attacker/defender in a combat test — use a vanilla JTL_212.
- **jtl-set:20–21 combat-tricks & misc batch** — six small additive seams, no new decision
  kind, no core-machinery touch.
  **`ActivatedAbility.extra_action`** — "Take an extra action after this one" (Kazuda
  Xiono JTL_18).  Using an ability normally hands the turn over; the flag keeps the
  seat, in BOTH `UseAbility.apply` paths — the inline one skips
  `_switch_active_player`, the deferred one sets the pushed decision's
  `after_resolve_player_index` to the user.  Purely a who-is-active choice; the
  ability itself resolves unchanged, so nothing in resolution or the decision
  machinery moves.
  **`push_select_token(suppress_abilities=True)`** — one more rider on the
  long-standing select-up-to-N loop (beside token / stat buff / ready /
  grant_keywords): each chosen unit gets the unified ability-suppression flag
  (`abilities_suppressed`, Mind Trick LOF_202), which is lifted at the ROUND
  rollover — so "loses all abilities **for this round**" needs no new ledger.  "Any
  number of friendly units" is just `max_targets` = the count of eligible units, so
  no new kind and no web/bot registration.
  **`DeckSizeModifier(amount)`** + **`deckrules.deck_size_for(base)`** — a
  DECKBUILDING marker on a base, the `StartingHandModifier` (Colossus JTL_21)
  pattern one seam over: "Your minimum deck size is increased by 10 cards" (Data
  Vault JTL_24) / "decreased by 5" (Thermal Oscillator JTL_25).  `deck_size_for` is
  the single place that knows the 50, read by both validators (`deckrules.deck_errors`
  and `decklist.validate_decklist`).  ⚠️ It shifts the engine's EXACT-50 convention
  rather than opening the CR's minimum-50 range, so a Data Vault deck is exactly 60.
  **`Condition.CONTROLLER_ATTACKED_NON_TOKEN_TRAIT_UNIT_THIS_PHASE`** — the
  `CONTROLLER_ATTACKED_THIS_PHASE` find_instance resolution (a dead attacker still
  counts) plus a trait filter and a non-token exclusion; the exclusion IS the clause
  for Darth Vader JTL_6, whose payoff is a TIE Fighter *token* that would otherwise
  re-arm him forever.
  **`TargetSpec.kind="unit_or_unit_upgrade"`** — one choice over the union of `unit`
  (standing in an arena) and `unit_upgrade` (a Piloting unit card riding another unit),
  which no single kind expressed: "attach a friendly Pilot unit **or upgrade** to this
  unit" (Corvus JTL_38, dispatching to `_attach_unit_as_pilot` or `_relocate_upgrade`
  on where the pilot actually sits — the former already performs the printed reminder
  verbatim).
  **`actions.attach_leader_as_pilot_upgrade`** — the leader→Pilot relocation body
  extracted out of `DeployLeaderAsUpgrade.apply` (base zone → host, `LeaderDeployed`
  with `via_pilot_leader`), now shared with a printed Action that flips a leader onto a
  Vehicle for a smaller price than his Epic Action (Poe Dameron JTL_13, whose upgrade
  side then moves himself on with `GrantedAbility(ActivatedAbility(once_per_round))`).
  ⚠️ **GOTCHA: a GrantedAbility's "in this arena" is `same_arena_as_source`, NOT
  `same_arena_as_host`** — the latter reads `event_ctx["attached_to_id"]`, which only
  the upgrade-PLAY path threads, while a granted trigger already resolves FROM the host
  (Tam Ryvora JTL_35, the Major Vonreg JTL_11 shape).  PURE REUSE: JTL_247 =
  `SOURCE_ATTACHED_TRAIT_UPGRADES_MIN` at `("Pilot", 1)` = "has a Pilot on it" (General
  Grievous TWI_34's Lightsaber counter); JTL_261 = `push_granted_attack(repeat=True,
  repeat_max=2)` (Headhunting SHD_145); JTL_253 = two separate single-effect
  `EventAbility`s, one per arena (JTL_250); JTL_257 = conditional SELF `KeywordGrant`
  over `CONTROLLER_HAS_OTHER_TRAIT_UNIT` (Hunting Nexu SHD_168) — its printed keyword
  bar is empty in the data, so sanitiser rule 2 has nothing to strip.
- **lof-set:01–02 direct-damage/removal batches (the first LOF-set groups)** — five small
  additive seams, no new decision kind, no core-machinery touch.
  **`push_select_token(restrict_ids=, defeat=)`** — the select-up-to-N loop gains a
  caller-computed whitelist (intersected AFTER the spec filter; the complement of
  `exclude_ids`) and a DEFEAT payoff, which together give "You may defeat **any number of
  upgrades on a unit**" (Kit Fisto's Aethersprite LOF_147): the host unit is chosen first
  by an ordinary targeted `CustomEffect`, its non-token upgrades become the whitelist with
  `kind="upgrade"`, and "any number" is the Kazuda Xiono JTL_18 idiom (`max_targets` = the
  pool size, `FinishSelectToken` ends it early — including at zero).  ⚠️ Unlike every other
  select_token payoff, the defeats run in **`_resolve_select_token`, i.e. AFTER the pop** —
  a defeat pushes its own triggers synchronously and must never run under this decision
  (the distribute_damage SOR_135 rule, restated).  Paired predicate
  **`has_non_token_upgrade`** gates the unit choice, so a bare unit — or one carrying only
  a Shield — is never offered and the optional trigger auto-declines.
  **`Condition.CONTROLLER_PLAYED_NON_UNIT_TRAIT_CARD_THIS_PHASE`** + the
  `game_memory.non_unit_traits_played_this_phase` ledger — "If you played a **non-unit**
  Force card this phase" (Rey LOF_12).  The card-type-narrowed sibling of Captain Phasma
  JTL_10's trait atom, split at the SAME CardPlayed chokepoint rather than at read time,
  because an event is already in the discard when the condition is read.
  **`StatBonus(count="other_controller_trait_units_<Trait>")`** — the self-excluding
  sibling of `controller_trait_units_<Trait>` (Squad Support TWI_122), over the same
  effective-trait / both-arenas basis: "+1/+0 for each **other** friendly Jedi unit" (Kit
  Fisto LOF_11 deployed).  A ConstantAbility on a LEADER needs no `deployed_only` — only
  the arena scans read it, so it is inert while he sits in the base zone.
  **`DealDamageEqualTo(count="attached_host_power")`** — "damage equal to **attached
  unit's** power" (Craving Power LOF_91), read off the standard
  `event_ctx["attached_to_id"]` the upgrade-play site threads; effective power, so the
  upgrade's own +2/+2 is already counted when its When Played resolves.
  ⭐ PURE REUSE worth knowing: "If you attacked with a **Jedi** unit this phase" (Kit Fisto
  LOF_11) is `CONTROLLER_ATTACKED_NON_TOKEN_TRAIT_UNIT_THIS_PHASE("Jedi")` — the
  source-INCLUSIVE atom (Darth Vader JTL_6), whose non-token narrowing is a no-op for a
  trait no token unit carries.  Its `..._OTHER_TRAIT_...` sibling would have been wrong:
  it discounts Kit Fisto's own attack.
- **lof-set:03–08 batch (direct damage, card advantage, and the LOF leaders)** — many small
  additive widenings, **no new decision kind** and no core-machinery touch.
  ⭐ **Two BOARD-GATE predicates make "pay a cost, if you do <targeted effect>" expressible
  on an EVENT**: `controller_has_force_token` (Sorcerous Blast LOF_172) and
  `controller_has_trait_card_in_hand:<Trait>` (Lightsaber Throw LOF_176, the trait riding
  in the predicate string).  An `EventAbility` has no `condition` field and a
  `ConditionalEffect` cannot carry a targeted sub-effect, so failing the gate must yield NO
  candidates — the Face Off JTL_178 shape.  The cost and its payoff then live in ONE
  `CustomEffect`.
  **`push_each_player_defeats(disposition="spare_then_damage", damage_amount=)`** — the
  INVERSE of the TWI_238 walk: the chosen units are the SURVIVORS and everything else takes
  the damage ("Each player chooses a unit they control.  Deal 3 damage to each unit not
  chosen this way" — Time of Crisis LOF_177).  The choice widens to any unit they control (a
  deployed leader included) and the web prompt is disposition-aware.
  **`push_modal(decider_id=)`** — the MODE stage is decided by another player while every
  mode still resolves for, and targets for, the source's controller; `ChooseModalOption`
  shifts both `deciding_player_id` and the seat back before the target stage ("An opponent
  chooses one: [you give an Experience token to a friendly unit] / [you draw a card]" —
  Watto LOF_65, with the new modes `give_experience_friendly_unit` and the fungible
  `draw_card`).  Both modes benefit the controller, so the opponent picking the lesser evil
  is a REAL choice — it does not collapse to an optimal default.
  **`push_play_upgrade_from_hand(from_discard_only=, host_id=, repeat=)`** — "Play any
  number of upgrades from your discard pile **on this unit** (one at a time, paying their
  costs)" (Kylo Ren LOF_1).  ⚠️ `repeat` re-pushes the loop **BEFORE** `_attach_upgrade`, so
  the just-played upgrade's own When Played lands on top and resolves first (the Endless
  Legions SHD_109 ordering); the always-offered decline is the "any number", including zero.
  ⚠️⚠️ **LOF_1 IS ALSO THE EXPERIENCE TOKEN's (set, number)** (LOF_2 = Shield, LOF_3 = The
  Force) — Kylo is registered only from `ActivatedAbility(undeployed_only=True)` and
  `TriggerAbility(WhenDeployed())`, the two kinds a token can never reach; a regression test
  pins it.
  **`push_deck_search(budget=N)`** — the combined-COST cap over the picks ("any number of
  Clone units with combined cost 4 or less" — Sifo-Dyas LOF_117).  The ctx key and both its
  guards already existed for Darth Vader SOR_87's search-and-play; a plain search simply had
  no way to set it.  Combined with `up_to=True` + `count=window` ("any number", the Kazuda
  JTL_18 idiom) and `disposition="discard_free_replay"` (Cobb Vanth SHD_115).
  **`push_bottom_from_discard(then_play_from_hand=<kwargs dict>)`** and
  **`disposition="choose_only"` + `then_deck_search_shared_trait=N`** — the first is a third
  settle-at-the-finish payoff beside `then_create_token`/`then_draw` (The Burden of Masters
  LOF_125); the second makes the decision a pure SELECTOR (nothing moves) whose payoff reads
  the chosen card's traits ("Choose another card in your discard pile.  Search the top 5 …
  for a card that shares a trait with it" — Psychometry LOF_219).
  **`push_select_token(token_count=N)`** + the `then_select_token` key `restrict_played`
  — more than one token per chosen unit, landing only on the just-played unit ("play a unit
  from your hand and give 2 Experience tokens to **it**", LOF_125); `restrict_played` is the
  complement of `exclude_played`.
  **`push_say_no(effect="return_to_hand", refuse_play_named=)`** — the SOR_233 decider-shift
  with a bounce instead of damage and a REFUSAL payoff ("Return an enemy non-leader unit
  unless its controller says 'It could be worse.'  If they do, you may play a card named
  It's Worse from your hand or resources for free" — A Precarious Predicament LOF_222).  The
  payoff routes through the shared `_play_named_free_from_hand_or_resources`, which pulls a
  copy out of the RESOURCE row first (the fungible-resource SOR_145 convention).  ⚠️ It's
  Worse LOF_264 is an EVENT, so **`push_play_event_from_hand` gained `free=` /
  `eligible_ids=`** — `push_play_from_hand` only ever plays units.
  **`push_use_force(payoff="draw:N")` + `decline_penalty="draw:N"`** — the "if you don't"
  clause is not always a downside ("If you do, draw 2 cards.  If you do not, draw a card" —
  Do or Do Not LOF_175); with no Force token no decision is pushed and it lands inline,
  which is exactly the printed reading.
  **`push_peek_top(force_cost=True)`** — the Force token is the price of the PLAY option
  only, spent by `PlayTopCard` and by nothing else, so keeping the card on top costs nothing
  (As I Have Foreseen LOF_188; with no token the card collapses to its unobservable "look").
  **`push_name_a_card(names=, then_payoff=)` + `_apply_name_a_card_payoff`** — a "then …"
  rider on a naming, string-encoded like the use_force/disclose dispatch:
  `"mill_defender_match_buff:4"` mills the defending player's top card and buffs the source
  for this attack on a match (Zuckuss LOF_204).  The nameable set stays the opponent's
  PUBLIC names — offering their hidden deck would leak information.
  **`push_name_and_discard(card_type="non_unit")`** — the complement filter (Tip the Scale
  LOF_226).  **`push_play_from_hand(shares_keyword_with_id=)`** and
  **`NextPlayDiscount.shares_keyword_with_friendly`** — printed keywords both sides, measured
  while the cost is paid, which is Morgan Elsbeth LOF_5's own printed rules note (`_shares_
  keyword_with_a_unit`; `_play_discount_entry_matches` now takes the state).
  **`StatBonus(count="controller_discard_trait_units_<Trait>")`** — the DISCARD-pile sibling
  of Squad Support TWI_122's in-play count (Captain Enoch LOF_83); printed traits, since a
  card in the discard is out of the trait-grant layer's reach.
  Three predicates: **`no_experience_token`** (the negation of `has_experience_token` —
  Obi-Wan Kenobi LOF_8), **`most_power_among_friendly_villainy`** (a per-candidate board read
  admitting only the units at the maximum, so a clear winner auto-resolves and "if multiple
  units are tied, choose one" is a real prompt — Supreme Leader Snoke LOF_6), and the
  already-present `creature_or_spectre` (Kanan Jarrus LOF_4).
  ⭐ PURE REUSE worth knowing: **three separate 1-damage instances onto one chosen unit** is
  the whole point of Heavy Blaster Cannon LOF_171 (a Shield eats only the first), so the
  damage must NOT be collapsed into a single 3; Bendu LOF_170's "each other unit" is
  `fixed=EACH_IN_PLAY` + `not_self`, whose inline expansion IS the printed "all damage is
  dealt simultaneously"; Old Daka LOF_36's "not named Old Daka" is just `not_self` (she is
  unique); "While you control another Creature **or** Spectre unit" is `ANY_OF` over two
  `CONTROLLER_HAS_OTHER_TRAIT_UNIT` atoms; Avar Kriss LOF_7's "+4/+0 and gains Overwhelm" is
  ONE ConstantAbility carrying both a StatBonus and a KeywordGrant (Tarkin JTL_161).
  🧪 TEST NOTES: `_get_card` returns the LEADER for LOF_1 — a token-collision test needs a
  by-type fetch (`repo._hydrate(con, row)` takes the CONNECTION first);
  `state.initiative_holder` is an INDEX, not a player id; `NameAndDiscard`'s field is
  `card_name`, not `name`; `_make_state`'s deck is EMPTY, so any card that draws needs
  `_push_deck_top` or the draw silently becomes base damage.
- **sec-set:01–04 batch (4 groups, 28 cards — SEC's first sweep)** — all additive, no new
  decision kind.  **`DamagePrevention` widened from an upgrade-only marker into the whole
  damage-modifier family**, still read at the single `_deal_damage_with_shield` chokepoint:
  `on_self` (the marker printed on a UNIT protects that unit — Cassian Andor SEC_42),
  `aura_target` (a TargetSpec: it protects every matching OTHER unit — Vigil SEC_50), and the
  narrowings `ability_only` (non-combat only; Cassian's rules insert says combat damage is not a
  card ability) + `enemy_only` (the dealer must be an opponent's card — needs the new
  `dealer_id` kwarg now threaded from `_apply_deal_damage`).  Its dual **`DamageAmplification`**
  (+N to each instance dealt to this unit by another card, applied BEFORE prevention/shields)
  is the other half of Vigil.  **`CannotPlayFromHand`** is a passive marker read only at the
  hand-play enumeration (+ a `PlayCard.apply` guard), so the Plot / Smuggle / discard routes
  stay open — which is the whole point of One in a Million SEC_53.  **`WhenYouTakeInitiative`**
  is a new trigger matched against the `InitiativeTaken` event; `ClaimInitiative` now runs the
  trigger pipeline right after the pre-armed `_consume_pending_initiative_effects` charges
  (Ziton Moj SEC_168).  **`KeywordGrant.value_count`** makes a numeric keyword's value DYNAMIC
  (the keyword-layer sibling of `StatBonus.count`; `"damaged_enemy_units"` — Punishing One
  SEC_171), resolved in `keywords._keyword_grant_value`; it needed **keyword-sanitizer rule 8**,
  since upstream tags such a card with a bare printed "Raid" that would otherwise stack +1 on
  top of the computed value.  **`defeated_while_attacking`** is a predicate on a
  `WhenUnitDefeated` filter, backed by a `while_attacking=True` kwarg the two attacker-death
  sites pass to `_defeat_unit` (it stamps the defeat's own event_ctx — no new state; Luthen
  Rael SEC_13, whose two sides are the same trigger).  Smaller widenings:
  `push_play_upgrade_from_hand(then_damage_host=N)` (the host-side "if you do", Lama Su SEC_3);
  `push_disclose(decline_payoff=, decline_payoff_args=, always_offer=True)` — the INVERSE
  disclose, where the payoff is a penalty on the DECLINE, so the decision must be pushed even
  when the hand cannot cover the aspects (Warrior of Clan Ordo SEC_164), plus the payoff arms
  `self_base_damage` / `damage_unit`; `push_select_damage(exclude_source=,
  then_self_base_damage_if_no_friendly_hit=)` (AAT Incinerator SEC_169, the rider evaluated at
  resolve against the chosen list); two conditions `N_PLUS_EXHAUSTED_UNITS_IN_PLAY` (BOTH
  arenas) and `CONTROLLER_MORE_CARDS_IN_HAND_THAN_OPPONENT`; and the predicate
  `power_and_hp_equal_source_ready_resources`.  **TRAPS worth carrying:** a leader's DB `text`
  is the UNDEPLOYED side and `deploy_box` the DEPLOYED side — gate them with
  `undeployed_only` / `deployed_only`; there is no way to express "exhaust this leader" as an
  `ExhaustCard(fixed=SELF)` effect (an undeployed leader in the base zone is no arena unit, and
  the spec silently falls back to a full prompt) — bundle the exhaust into the payoff
  `CustomEffect`, the Boba Fett JTL_9 convention; and **`ConditionalEffect` still cannot hold a
  TARGETED sub-effect**, so a "then, if <cond>, you may hit another unit" clause puts the
  condition inside the chain fn and simply doesn't stamp `prior_target_id` (Let's Call It War
  SEC_180).  Documented deviations: Jabba SEC_2 and The Elite Squad SEC_143 observe COMBAT
  damage only (the observer family's standing limit) though both cards say "damage"; Miraj
  Scintel SEC_139's conditional Overwhelm is reported unconditionally (the Moff Gideon SHD_7 /
  Jango Fett SHD_138 convention — the keyword layer sees no combat context); Satine SEC_5's
  "heal up to 2" heals as much as possible (no choose-a-magnitude decision exists).
- **sec-set:12–18 batch (7 groups, 48 of 49 cards)** — all additive; **no new decision kind**,
  no escape hatch.  ONE ESCALATION: Implicate SEC_231 ("Choose a unit.  For this phase, it
  gains Sentinel and: 'When this unit is attacked: Create a Spy token'") is NOT encoded — a
  phase-scoped triggered ability granted to ONE chosen unit has no home: `GrantedAbility` needs
  an attached upgrade, and `AuraGrantedAbility` is collected only for a `WhenDefeated` inner
  trigger at the defeat path.  The designed fix (for a framework session) is to scan
  `AuraGrantedAbility` in the MAIN `_collect_triggers` loop over in-play sources plus
  `game_memory.phase_aura_sources`, with a per-candidate predicate matching "carries a
  `keyword_grant` modifier sourced by this aura" to pin the aura to the chosen unit.
  ⭐ **Upgrade-borne AURAS over third cards** — `ConstantAbility(via_host=True)` makes the two
  keyword scans (`has_keyword` / `keyword_value`) also walk each arena unit's attached upgrades,
  evaluating the spec's condition and target with the HOST as `source_ci`: "Attached unit gains:
  'While this unit is ready, each other friendly unit gains Overwhelm, Raid 1, Restore 1'"
  (Figure of Unity SEC_104).  The mirror of `upgrade_only` — that flag HIDES a spec from the
  arena scans, this one ADDS an upgrade to them.  Keyword layers only (all this card needs).
  ⭐ **UNITS AS RESOURCES** — the `UnitsPayCosts(traits=)` passive marker (Vuutun Palaa SEC_122,
  "Each friendly Droid unit may be exhausted to pay costs as if it were a resource") adds a
  THIRD payment tier at `_affordable_with_credits` / `_pay_play_cost` via `_unit_resource_pool`.
  Need-based and LAST (resources → credits → units), so every existing payment is byte-identical
  and a Droid is never tapped for a play the row could afford.  SCOPE deliberately matches the
  Credit economy's documented narrowing (not Smuggle/Plot, not `PayResources` ability costs).
  ⭐ **MODIFIER-backed ability suppression** — `state.ability_suppressed` gains a
  `kind="abilities_suppressed"` modifier arm, so suppression can carry a DURATION the
  per-instance flag cannot: `push_granted_attack(defender_suppress_abilities=True)` applies it
  `this_attack` to the chosen unit defender ("the defender loses all abilities for this attack"
  — One Way Out SEC_157).  ⚠️ Also needed the `UnitDefeated` branch of `_collect_triggers` to
  apply the same suppression guard the in-play scan already applies: a dying unit has left its
  arena, so it never reached that guard and its When Defeated fired through the blackout.
  Smaller, all additive: `StandingPlayDiscount(applies_to="upgrade")` (the host-free sibling of
  `upgrade_on_source` — Congress of Malastare SEC_64); `CostReduction.per_friendly_trait`
  (SEC_122); `CannotBeAttackedWhileExhausted(while_ready=True)` (the Sabine TWI_195 test
  INVERTED — Muckraker Crab Droid SEC_135); `push_distribute_heal(target_controller=,
  exclude_ids=)` ("heal up to 4 from among OTHER units", either player's — Nala Se SEC_65);
  `push_select_token(exhaust=True)` (the `ready` mirror, honouring Protection — No One Ever Knew
  SEC_196); `StatBonus` count `captives_guarded` (Libertine SEC_212); the predicate
  `not_attacked_this_phase` (It's Not Over Yet SEC_177); and five disclose payoff arms
  (`heal_unit`, `distribute_heal`, `resource_top_of_deck`, `pending_keyword_grant`,
  `ready_resources`) plus `buff_unit(duration="this_attack")` (Ebon Hawk SEC_219, whose "and/or"
  is TWO independent one-icon discloses, each self-gating).
  ⭐ PURE REUSE worth knowing: `push_choose_modal(pick=1)` is how "Choose an arena" works
  (Lightmaker SEC_207 — indices 1/2 are `EventAbility` options, never trigger-collected);
  "attack with ANOTHER unit" needs no exclusion parameter when the card exhausts the first one
  (Accelerate Our Plans SEC_228); `same_arena_as_host` already covers "attached unit's arena"
  (Nimble Prowess SEC_69).  DOCUMENTED DEVIATIONS: Theed Security SEC_95 reads "an opponent
  controls an upgrade" as `ENEMY_UNIT_UPGRADED` (misses an opponent's upgrade on YOUR unit);
  Hired Slicer SEC_220 always reveals the OPPONENT's deck and bottoms the pair before the
  choice; SEC_215/216/225/235 auto-pick resources (the SOR_145 fungible convention); Dryden Vos
  SEC_137's "next regroup" is the round-scoped `cannot_ready_this_round` flag.
- **sec-set:05–11 batch (7 groups, 40 cards)** — many small additive widenings, no new
  decision kind and no escape hatch.
  ⭐ **FOREIGN `deck_search`** — `push_deck_search(deck_owner_id=)` separates WHOSE DECK is
  searched from WHO decides ("look at the top 2 cards of the DEFENDING player's deck.
  Discard 1 of those cards" — Sabé SEC_17), with the new `disposition="discard"` (the plain
  discard of the picks into the DECK OWNER's pile) and `rest_disposition="top"` (the
  un-taken cards keep their order on top; the shuffled copy is discarded, so the RNG stream
  is unchanged).  ⚠️ Needed a narrow `invariants._check_hidden_info` EXEMPTION: a foreign
  search legitimately shows the decider another player's deck instance_ids, so a deck_search
  whose `controller_id` ≠ `deciding_player_id` has its `candidate_ids` exempted (the
  `reveal_play_credit` `revealed_id` precedent).
  ⭐ **`game_memory.foreign_discard_play_this_phase`** — the PAID sibling of JTL_221's
  cross-pile free replay: ids in ANOTHER player's discard the keyed player may play this
  phase by paying, aspect penalties waived (Obi-Wan Kenobi SEC_205).  Branch (b3) of
  `_enumerate_discard_play_actions` expresses the waiver as a `discount` equal to the payer's
  own aspect penalty, so the cost path is the shared one; consumed at the play.
  ⭐ **PRICED `say_no`** — `push_say_no(pay_to_refuse=N, effect="draw_top_card",
  revealed_card=…)`: refusing now costs the decider resources and is only offered while they
  can pay, and the effect arm needs no unit target (the decider is simply the opponent).
  `revealed_card` carries card_id + name ONLY (the look_hand hidden-info shape), so the
  decider sees what they are denying without leaking a deck instance_id — Cikatro Vizago
  SEC_218.
  ⭐ **`has_keyword` `despite_suppression` carve-out** — a `keyword_grant` modifier flagged
  `despite_suppression` survives the ability blackout, which is the ONLY way to express
  "attached unit loses … all abilities EXCEPT FOR Grit.  Attached unit gains Grit" (Exiled
  from the Force SEC_54, where the same upgrade both suppresses via `SuppressHostAbilities`
  and grants).  Default-off; a ConstantAbility cannot work there because `has_keyword`
  returns False outright for a suppressed unit.  SEC_54's Force removal is a PERMANENT
  `trait_revoke` modifier sourced on the upgrade (the Lando JTL_3 lifetime recipe).
  Smaller, all additive: `TargetSpec.cost_max_count` (the `power_max_count` sibling;
  `"controller_villainy_aspect_icons"` — Evil is Everywhere SEC_247); the per-candidate
  predicate **`has_keyword_<name>`** (reads through the keyword layer, so a GRANTED keyword
  counts — Kylo Ren's Command Shuttle SEC_32); `push_disclose(any_of=True)` (the DISJUNCTIVE
  "disclose Vigilance, Command, Aggression, Cunning, **or** Heroism" — Leia Organa SEC_4)
  plus three disclose payoff arms (`create_token`, `name_and_discard`,
  `experience_off_aspect_unit`); `push_bottom_from_hand(top_only=)` (so "one on top and
  another on the bottom" is two pushes of one decision — Kreia's Whispers SEC_232);
  `push_granted_attack(then_attack_cheaper=)` (a ONE-SHOT follow-up whose cap is read off the
  unit that just attacked — Colonel Yularen SEC_6); `push_play_from_hand(then_capture_by=)`
  (a settle payoff — DJ SEC_18); `push_pay_resources_for_tokens(token_target_id=)` (tokens on
  a CHOSEN unit — Emergency Powers SEC_40); `DiscardCardCost(cost_min=, count=)` (both gates
  the offer and picks the card — Dryden Vos SEC_7); `IgnoreAspectPenaltyForPlays.exclude_aspects`
  ("non-Villainy Official units" — Mon Mothma SEC_9); `StatBonus` counts
  `controller_discard_trait_cards_<Trait>` (card-type-blind sibling of LOF_83 — Orn Free Taa
  SEC_112) and `controller_ready_token_units` (Governor Pryce SEC_11); and the condition
  atoms `CONTROLLER_HAS_EXHAUSTED_UNIT` / `CONTROLLER_HAS_OTHER_EXHAUSTED_UNIT` (C-3PO
  SEC_15, whose deployed On Attack needs the self-exclusion — attacking exhausts him).
  ⭐ PURE REUSE worth knowing: Beguile SEC_233 is TWO `EventAbility`s, not two effects (the
  Barrel Roll JTL_228 lesson) — the targeted bounce pushes its ChooseTarget first, then the
  lone no-target look inlines and pushes `look_hand` ON TOP, so the look really happens
  first with one prompt each.  DJ SEC_18's "friendly units that are rescued enter play ready"
  needs no registration: `_release_captured_cards` already returns captives READY.
  DOCUMENTED DEVIATIONS: Bail Organa SEC_8's "when you play a card from your resources"
  observes the Smuggle path only; Renewed Friendship SEC_105's mandatory return collapses to
  the `return_from_discard` "up to"; Leia SEC_4's Experience gift rides a `select_token`, so
  it may be declined; Elia Kane SEC_242 auto-picks the enemy resource (the SOR_145 fungible
  convention).
- **The PINNED PHASE AURA (sec-set:18 framework session — Implicate SEC_231; SEC COMPLETE at
  264/264)** — "Choose a unit. For this phase, it gains Sentinel **and**: 'When this unit is
  attacked: Create a Spy token.'"  The way to give ONE CHOSEN unit an ONGOING triggered ability
  for a phase.  Neither grant shape fitted: `GrantedAbility` needs an attached upgrade to carry
  it, and `AuraGrantedAbility` was board-wide AND collected only at the defeat path.  Two
  additive seams: (1) `resolver._collect_triggers` now scans aura grants whose inner trigger is
  **not** `WhenDefeated` over the units in play — a `WhenDefeated` one stays at the UnitDefeated
  path, which exists precisely because the dying unit has already left the arena — plus
  `game_memory.phase_aura_sources`, so a spent EVENT keeps granting from the discard (Pyrrhic
  Assault TWI_103); (2) the predicate **`granted_keyword_by_source`** matches a candidate
  carrying a `keyword_grant` modifier from that same source, which narrows the board-wide aura
  to the one chosen unit.  ⭐ The trick worth reusing: **no new state** — the keyword half of the
  very same effect already stamps exactly one modifier onto exactly the chosen unit, so the aura
  reads the choice back off it, and both halves being `this_phase` makes them lapse together.
  The targeted `GrantKeyword` is ordered ahead of the CustomEffect that arms the aura, so the
  player is prompted once (the C-3PO SEC_93 rule) and with no unit to choose nothing is armed.
- **law-set:01–02 batch (2 groups, 14 cards — LAW opens at 120/264)** — all additive, no escape
  hatch.  ONE new decision kind, **`cull_for_damage`** (`actions.push_cull_for_damage`): "give up
  any number of your OWN cards, then deal that many damage" over a `pool` of `"hand"` (discard —
  Darth Vader LAW_11) or `"tokens"` (defeat friendly token units AND token upgrades — Han Solo
  LAW_17), with `min_count`/`max_count` turning the same kind into a COST (`min=max=1` = Han's
  "Action [Exhaust, defeat a friendly token]").  Nothing is culled while the decision is open —
  the picks are recorded and applied after the pop, with the damage (the `push_distribute_damage`
  rule).  Six smaller seams: **`OnAttack(vs_unit=True)`** ("If this unit is attacking a unit" — a
  base attack carries a `None` defender, so it is a plain read at the existing firing point);
  the one-shot `CardInstance.defeat_after_attack` flag settled by
  `actions._settle_defeat_after_attack` at all three combat-pipeline ends ("defeat this unit
  after completing this attack", Defiant Hammerhead LAW_62 — the non-granted-attack twin of
  `push_granted_attack(then_defeat_attacker=…)`); `heal_events` entries widened to
  `[id, amount]` + the **`event_healed_amount`** scaling count ("heal … deal THAT MUCH damage",
  Baze Malbus LAW_47); `push_sacrifice_resource_for_damage(mandatory=, create_credit=)` (a
  printed sacrifice COST has no decline, Chewbacca LAW_13); and two condition atoms —
  **`ANY_PLAYER_HAS_CREDIT`** (credits live in `PlayerState.credits`, which no target predicate
  can see) and **`CONTROLLER_DISCARDED_THIS_PHASE`** (the per-player reading of the same ledger
  `SELF_DISCARDED_THIS_PHASE` uses — ownership is read back off the discarded instance, no new
  state).  `remaining_hp_le_2` generalised to **`remaining_hp_le_<N>`**.  ⭐ The reusable shape:
  a leader is an `undeployed_only` Action + a `deployed_only` combat trigger over the SAME
  adapter, differing only by `optional`/`mandatory` — five of the seven LAW_01 cards are that.
- **jtlp-set:02 + j24-set:01 + c24-set:02 + c25-set:01 — THE LAST FOUR CARDS (🏁🏁 **THE GAP-FILLING CAMPAIGN IS COMPLETE: 24/24 sets, 231/231 groups, 0 cards remaining**; the DB audits at 2635/2636 playable)** — no new primitive, no new decision kind, no escape hatch, no escalation.  THREE of the four needed no card logic at all.
  ⚠⚠ **`reprints._norm` NOW CASE-FOLDS — the last blind spot in the printed-face identity, and the same bug as `_norm_rules`.**  `_norm` folded `\xa0` and the curly apostrophe but not letter CASE, so a printing that SHOUTS a trait or lower-cases a cost keyword keyed to its own SINGLETON group — and `find_reprints.build_worklist` skips singletons, so `--check` stayed GREEN while the faces sat unplayable beside an implemented twin.  Three of this batch's four "encoding groups" were exactly that: **C24_5 Asajj Ventress** ("another SEPARATIST unit" vs TWI_134's "Separatist"), **C25_5 C-3PO** ("Action [exhaust," vs SEC_93's "[Exhaust,") and **J24_5 Wrecker** (vs SHD_154) — each now an ALIAS, not a second implementation.  MEASURE BEFORE WIDENING AN IDENTITY: case-folding merges exactly FOUR groups DB-wide (those three plus General Tagge SOR_80/SHD_81, already covered) and every merged group is a single card NAME, so it can join no two different cards.  The guard only ever gets looser, so all ~250 existing aliases still pass it.
  ⭐ **JTLP_16 Anakin Skywalker is the OTHER kind of twin — a DB DEFECT, not a cased difference** — so it is registered rather than aliased (JTLP_18 Fett's Firespray, last batch, verbatim).  Its `epic_action` has lost the whole trigger clause ("When attached unit completes an attack (and survives):"), leaving a Piloting bar glued to a bare effect; the row's own rules note still glosses the trigger it no longer prints, which is how you tell a defect from a different card.  It IMPORTS JTL_197's finder, which now matches EITHER printing's coordinates (`ANAKIN_PILOT_KEYS`) — a `GrantedAbility` resolves from the HOST, so "this upgrade" is located among the host's `attached_upgrades` by registry key, and a hardcoded one would have found nothing for the reprint.  **When a promo twin's DB text is truncated, generalise the canonical's finder; never copy it.**
  ⚠ **THE ONE REMAINING "GAP" IS A FALSE POSITIVE**: GG_6 **Shield** (a Token Upgrade) whose printed text IS the Shield rule, which the engine implements natively at `_deal_damage_with_shield` and never through the registry.  Every OTHER Shield token audits as `implemented` only by TOKEN COLLISION — SOR_2/SHD_2/JTL_4/LOF_2/LAW_3/TS26_4/ASH_3 each share a number with a registered LEADER — so GG_6, whose number carries no such leader, is the honest reading of all 8.  It needs no encoding, and registering an ability on it would be actively wrong (a token-collision leak).
  ⚡ `scripts/next_group.py` now reconfigures stdout to UTF-8 — its `QUEUE EMPTY … 🎉` banner printed for the first time ever and then died in cp1252, exiting non-zero on a purely cosmetic failure.
  🧪 TEST NOTE: the walker's focused `-k` gate is built from bare card NUMBERS, so a one-card group numbered `5` selects ~1300 tests across the suite — the gate is real but very loose at low numbers; the per-card assertion is what actually pins these cards.  A stand-in that skips itself is now the norm: FIVE self-finding tests (`test_plan_encoding` ×3, `test_swudb_import`, `test_reprints`) report "the campaign has encoded them all", which is why the fast tier's skip count went 5 → 10 with nothing broken.
- **ts26-set:09–13 + p25-set:03 + jtlp-set:01 batch (7 groups, 31 cards — 🏁 COMPLETES TS26 (84/84) *and* P25; the DB is now 2631/2636 playable, **5 text-bearing gaps left in the whole database**)** — all additive; **no new decision kind**, no escape hatch, no escalation.
  ⭐ **`push_say_no(effect="opponent_heal_base")`** — the OPT-IN flavour of the SOR_233 seat shift: the decider's OWN base is the beneficiary, so AllowEffect is the "may" and SayNo the decline (Lom Pyke TS26_51, "each opponent may heal 5 damage from their base.  For each player that does, give 2 Experience tokens to a unit").  Targetless like the `draw_top_card` arm, and its `then_experience` payoff is a `push_select_token` addressed to the CONTROLLER, pushed AFTER the pop.  Both branches are real — a damaged base is worth more than the tokens it concedes, an undamaged one is not — so it does NOT collapse to an optimal default.
  ⚠⚠ **THE READY LEDGER NOW CARRIES ITS PHASE** — `game_memory.ready_events` entries widened from a bare instance_id to `[instance_id, phase]` (the `heal_events` widening; a bare string still reads as ACTION).  **The drain cannot re-derive it**: the regroup mass-ready is drained AFTER the rollover into ACTION, so a drain-time phase read lets every regroup ready through.  That plus **`WhenUnitReadies(controller="enemy", action_phase=True)`** — the observer was strictly self-referential for In Debt to Crimson Dawn JTL_192 — is Rex's DC-17s TS26_63 ("When an enemy unit readies during the action phase: Ready this unit.  Use this ability only once each round", the Toro SHD_239 `{iid}:trig` limiter charged inside the effect).  Without the phase half the card would burn its once-per-round use at every regroup.
  ⭐ **`IgnoreAspectPenaltyForPlays` gained `self_only` + `only_aspects`** (Kylo Ren P25_46, "While playing this unit, ignore his Villainy aspect penalty if you control Rey").  `self_only` is the marker on the card BEING PLAYED — it sits in HAND, which no in-play scan can reach, so `_controller_waives_aspect_penalty` now leads its scan with `ci` itself and the flag keeps the two readings DISJOINT (no existing marker newly self-applies).  `only_aspects` waives ONE aspect's pips rather than the whole penalty, computed as their MARGINAL cost (`_aspect_penalty(all) - _aspect_penalty(rest)`), so Kylo's Aggression pip is still paid and a pip the base already matches waives 0.
  ⭐ **`push_name_and_discard(namer_id=)`** — shifts WHO names (and therefore whose hand is stripped) off the source's controller.  "Each player reveals their hand.  In player order, each player discards a card from the hand of the player to their right.  Then, each player draws a card" (Reveal Intentions TS26_80) is TWO pushes of that one decision, one per seat, pushed in REVERSE seat order so the controller's pick resolves first on the LIFO stack — and `discarder_draws` is exactly the trailing "each player draws a card", since the discarder is the one who lost a card.
  ⭐ **Fives TS26_34 points the Chimaera JTL_39 seam the other way.**  JTL_39 uses ANOTHER unit's ability FROM that unit; "You may have this unit enter play with the 'When Played' abilities of another unit in play" re-pushes the chosen unit's `_when_played_ability_indices` as `resolve_effects` decisions with **`source_id` = FIVES** — the GrantedAbility source/spec split (the spec is read by (set, number, ability_idx), the source instance by `source_id`), so every "this unit" inside the borrowed clause means Fives.  ⚠ It needs a TERMINATION GUARD: without the `fives_borrow` event_ctx flag one copy of Fives could borrow a second copy's clause, which would choose the first again, forever.
  ⭐ Four scaling/count widenings, each one arm at an existing site: **`CostReduction.per_friendly_units`** (trait-blind, Encircle TS26_61 — whose tension is that the board paying for it is the board supplying the captor), **`CostReduction.per_controller_card_played_this_phase`** (Tribunal TS26_36; the counter is incremented AFTER the cost is computed, so "each OTHER card" is free), **`push_granted_attack(bonus_per_defending_player_unit=)`** (the arena-blind sibling of Masterstroke ASH_234's, and it scales on a BASE attack too since that still has a defending player — Fearless Attack TS26_84) and **`push_granted_attack(attacker_prevention_combat_only=)`** (Brothers TS26_59's "prevent all COMBAT damage", the narrowing of I Have You Now JTL_193's blanket `all`).
  ⚠⚠ **`_attacker_matches_predicates` bit AGAIN** — `unique`/`non_unique` had to be added there beside the resolver's for Brothers TS26_59's "up to 2 <uq> units".  That is THREE batches running.  **Whenever a card restricts a granted attack by a predicate, add the arm in BOTH places** — an unknown predicate there is IGNORED, not failed, so the filter silently offers every attacker.
  ⭐ PURE REUSE worth carrying: a bounty whose effect needs a TARGET must AUTO-PICK — a bounty's targeted effect is otherwise chosen by the DYING unit's controller, who has every reason to choose badly (Fortune and Glory TS26_27's "a friendly unit captures a non-leader unit" picks the collector's highest-power captor and the priciest foreign prey; the Fugitive Wookiee SHD_211 / Xanadu Blood SHD_191 convention).  "An opponent deals 1 damage to a unit" is `push_select_damage(decider_id=)` (Wartime Pirate TS26_66, Val SHD_58's override); "each opponent may ready a resource" collapses to taking it (fungible + pure upside — Wartime Profiteer TS26_76); "Give an Experience token to each of up to 3 units" / "Exhaust any number of non-<uq> units" are the plain select-token loop, the second at the Kazuda JTL_18 "any number" idiom (`max_targets` = the pool size) with `exhaust=True`; Encircle TS26_61's capture is Take Captive SHD_131 verbatim; Take Cover TS26_47 and Mislead TS26_81 are the two OPPOSITE readings of a two-clause event — TS26_47's "a unit … and give a Shield token to IT" is ONE targeted CustomEffect (SHD_141), TS26_81 names "a unit" TWICE so it is two independent targeted effects; Barriss Offee TS26_78's "When an ENEMY unit attacks" is `WhenUnitAttacks` (the Jedi Temple LOF_23 OBSERVER form — `OnAttack` fires only for the attacker itself) with `fixed=ATTACKER`, which resolves off the `attacker_id` all three attack-declare sites thread.
  ⚠ **JTLP_18 could NOT be aliased**: it is Fett's Firespray JTL_240, but its DB `text` is TRUNCATED mid-sentence, and `apply_reprint_aliases` asserts the two printed faces are byte-identical — the `_norm_rules` blind spot from the other side.  It is registered in the promo module and IMPORTS JTL_240's own magnitude function, so the twins cannot drift.
  🧪 TEST NOTES: the `assign_indirect_damage` context key for the size is **`amount`** (not `pool`, which is `distribute_damage`'s, nor `remaining`, which is `select_token`'s); an Experience token is **+1/+1**, so a "+2/+0 and a token" assertion reads +3; a `select_token` whose pool runs out AUTO-RESOLVES, so a trailing `FinishSelectToken` is then ILLEGAL; and `_play_event_from_hand` hands the controller resources, so assert a ramp by INSTANCE IDENTITY, never by resource-row size.
- **ts26-set:06–08 batch (3 groups, 21 cards — the TS26 LEADER block plus two combat-trick groups; TS26 now 55/84)** — all additive; **no new decision kind**, no escape hatch, no escalation.
  ⚠⚠ **THREE of group 06's seven numbers are TOKEN COLLISIONS** — TS26_1 (Battle Droid token UNIT), TS26_2 (Clone Trooper token UNIT) and TS26_4 (the SHIELD token UPGRADE, the worse half: a token upgrade lives in a host's `attached_upgrades`, exactly where a `GrantedAbility` is looked for).  Count Dooku, Anakin and Padmé are therefore registered ONLY from `ActivatedAbility(undeployed_only=)` + `TriggerAbility(deployed_only=)`.
  ⭐⭐ **A DEPLOYED LEADER NOW COUNTS AS ENTERING PLAY** — `_deploy_leader_into_arena` writes the leader into `game_memory.units_played_this_phase` (recorded BEFORE the deploy bus, so a WhenDeployed already sees it).  That set is the single reading of "entered play this phase", and three TS26 cards say so explicitly: Anakin TS26_2 and Padmé TS26_4 ("friendly units [that] entered play this phase (**including tokens and leaders**)") and — for free — Asajj Ventress TS26_7's printed Hidden reminder ("can't be attacked if she was **deployed** this phase"), which reads the same set through `_hidden_protected` and had silently never fired for a leader.
  ⭐ **`ConstantAbility.undeployed_only`** + the base-zone pass `keywords._undeployed_aura_grants` (gated on the cached `_undeployed_keyword_aura_keys` index, the `_keyword_revoke_aura_keys` trick) — the INVERSE of the standing convention.  Every other leader ConstantAbility is deployed-only for free *because* the scans walk the ARENAS and an undeployed leader sits in `base_zone`; Savage Opress TS26_5 prints an aura on his UNDEPLOYED side ("Each friendly unit with the most power among friendly units gains Overwhelm"), so the flag makes the arena scans SKIP the spec and the base-zone pass read it.  KEYWORD layers only (`has_keyword` / `keyword_value`) — no card yet needs an undeployed StatBonus aura.  Paired with the **`most_power_among_friendly`** predicate (the aspect-blind sibling of Snoke LOF_6's, and an EACH so a tie grants to every tied unit), which carries its own `_MOST_POWER_EVALUATING` reentrancy guard — it calls `compute_power` from inside an aura target (the `SOURCE_POWER_MIN` lesson).
  ⚡⚡ **KEYWORD-SANITISER RULE 1 NOW READS A LEADER'S DEPLOY BOX** — the same gap rule 9 closed in ash-set:12.  `text` is only the UNDEPLOYED side, so a leader whose undeployed box says "… gains K" while his deployed box prints a bare `K` line lost a keyword he really has.  MEASURED DB-wide: exactly **7 leaders change**, all genuine — Moff Gideon SHD_7, Maul TWI_9, Grand Admiral Sloane ASH_7 and Savage Opress TS26_5 get Overwhelm back, Rio Durant JTL_15 Saboteur, Sebulba LAW_12 Raid, and Jabba the Hutt LAW_15 correctly LOSES the Ambush his deploy box only grants.  ⚠ Rule 5 (`_is_reference_only`) is deliberately NOT widened: its signal is "EVERY occurrence is a '…with K' reference", so a larger corpus can only weaken it (Chancellor Palpatine SEC_1 would keep a Plot keyword he does not have).
  ⚠⚠ **`_attacker_matches_predicates` IGNORES an unknown predicate rather than failing it** — so a `push_granted_attack(attacker_predicates=[…])` filter the function does not implement silently offers EVERY attacker.  It bit both new users this batch (Asajj TS26_7's `token_unit`, Padmé TS26_4's `played_this_phase`), so both arms landed there beside the resolver's, and it now takes an optional `state` for the ledger-backed ones.  **Add the arm in BOTH places whenever a card restricts a granted attack by a new predicate.**
  ⭐ **`game_memory.token_unit_attackers_this_round`** (player_ids, written at the three attack-DECLARE steps by `actions.note_token_unit_attacked`) behind **`Condition.CONTROLLER_ATTACKED_TOKEN_UNIT_THIS_PHASE`** (Asajj TS26_7 deployed).  It records the CONTROLLER, not the unit, and has to be its own ledger: every other "attacked this phase" atom re-reads `units_attacked_this_round` through `find_instance`, and a defeated TOKEN ceases to exist (it is never discarded), so that re-read loses precisely the case this card is built around.
  ⭐ **`game_memory.bases_healed_this_phase`** + `actions.note_base_healed` behind **`Condition.ANY_BASE_HEALED_THIS_PHASE`** (Dooku's Solar Sailer TS26_38).  The base flavour of `units_healed_this_phase`, and its own function because a base has no single heal chokepoint — like `_bases_cannot_heal` (the read it mirrors) it is called at every base-heal site: `resolver._apply_heal` (via `note_unit_healed`'s Base branch), Restore's `_apply_restore`, the distribute-heal finish, Reinforcement Walker SOR_119's discard-heal and a bounty's `heal_base` payoff.  Restore is how the card is meant to be switched on, so missing that site would have made it near-dead text.
  ⭐ **`NextPlayDiscount.card_type="event"`** — "The next EVENT you play this phase costs N resources less" (Rex TS26_6, Ahsoka's Lightsabers TS26_35), the card-TYPE sibling of `units_only` (which is the Unit case), matched at the one `_play_discount_entry_matches` seam.  Ahsoka's discount is a pending `game_memory` entry rather than anything read off the source, which IS the card's rules note that it "remains active even if Ahsoka's Lightsabers or the attached unit is defeated".
  ⭐ **`push_deck_search(disposition="resource")`** — the selected card goes straight into the searcher's resource row FACE DOWN + EXHAUSTED (the `resource_from_discard` placement; the CR default for a resource an effect puts into play, and Jendirian Valley TS26_18's own rules note).  Plus **`Condition.CONTROLLER_DISCARD_SIZE_MIN`** (Twilight TS26_41, the plain-count sibling of `CONTROLLER_DISCARD_DISTINCT_COSTS_MIN`) and a DYNAMIC reduction on **`CONTROLLER_CAN_PLAY_UNIT_FROM_HAND`** — `param=(trait, "per_friendly_leader_unit")` reads the board at gate time (Dooku's Palace TS26_10), because a fixed 0 would hide a once-per-GAME Epic Action in exactly the case where the discount is what makes the play affordable; it shares `_is_leader_unit` with `CostReduction.per_friendly_leader_unit`, so gate and price cannot drift.  And **`keywords.distinct_keyword_names`** — `distinct_keyword_count`'s set, exposed so a card can UNION across units ("4 or more different keywords **among friendly units**", The Darksaber TS26_22); still the LIGHTWEIGHT count, so a keyword granted only by another card's aura is not in the union.
  ⭐ PURE REUSE worth carrying: **"Choose 2 players" collapses to `player="each"` in two-player** (Count Dooku TS26_1, the Chio Fain LAW_48 reading).  **"It can't attack your base or units you control for this phase" collapses to the BLANKET `cannot_attack` modifier** (Chaotic Diversion TS26_31) — in two-player that list is everything the readied unit could legally attack, which is what makes the card a trick rather than a gift.  A clause gated on a board count that the card's rules note says does NOT gate the Action ("still can be used … but no Shield token is created" — Anakin TS26_2, Padmé TS26_4) puts the gate INSIDE the effect fn, not in `ActivatedAbility.condition`.  Prime Minister Almec TS26_28 is the Kylo SHD_141 one-CustomEffect rule with the sweep measured AFTER the buff (his rules note: "Abilities that refer to a card's power include temporary modifiers").  Maul TS26_30's "you may attack with another unit" leaves the TRIGGER mandatory — the granted attack's own `DeclineGrantedAttack` is the "may", and an optional trigger on top would ask twice.  Obi-Wan TS26_40 needs no work to NOT have Restore: rule 1 already strips a bar whose only textual mention is the grant.
  🧪 TEST NOTES: `SelectTokenTarget`'s field is **`target_id`**, not `instance_id`; `UpgradePlayed`'s host field is **`attached_to_instance_id`**; and `_make_state`'s base has NO aspects, so a 2-aspect card costs +4 there — assert a cost DISCOUNT as a delta against `_play_cost` measured before the ability, never against `card_def.cost`.
- **ibh-set:03–04 + ts26-set:01–05 batch (7 groups, 32 cards — 🏁 COMPLETES IBH, 104/104, and OPENS TS26, the 2026 two-player starter, at 34/84)** — all additive; ONE new decision kind (`resource_from_hand`), no escape hatch, no escalation.  The first `src/swu/cards/ts26/` module.
  ⚠⚠ **TS26 PRINTS FOUR TOKENS AT NUMBERS 1–4** — TS26_1 Battle Droid and TS26_2 Clone Trooper (token UNITS), TS26_3 Experience and TS26_4 Shield (token UPGRADES) — each colliding with a LEADER of the same number.  Maul TS26_3 is therefore registered ONLY from `ActivatedAbility(undeployed_only=)`, `TriggerAbility(WhenDeployed())` and `TriggerAbility(deployed_only=)`; a regression test pins the spec KINDS.  A `ConstantAbility`, a `GrantedAbility` or a passive marker would leak onto the token (the JTL_1/3/4, LAW_2/3, ASH_1/2/3 hazard, now with FOUR live numbers in one set).
  ⭐ **`resource_from_hand` decision kind** (`push_resource_from_hand` / `SelectHandCardToResource` / `FinishResourceFromHand`) — "You may resource a card from your hand and ready it" (Sundari Palace TS26_12).  An "up to N" loop over the hand whose picks land in the resource row READY and, unlike Smuggle, are NOT replaced from the deck — so the row really grows, which is the whole cost structure of the card.  Registered in all four places (`_KNOWN_DECISION_KINDS`, `_decision_legal_actions`, the web prompt, a HeuristicBot handler + `_SAFE_DEFAULT_ORDER`).  Its `then_defeat_resources_at_regroup` rider feeds the new **`game_memory.defeat_resources_at_regroup`** (player → count, serialized), swept in `_enter_regroup` through the shared fungible auto-pick `_fire_defeat_own_resource` — the numeric sibling of `rescue_at_regroup`.  Resourcing nothing schedules nothing, which IS the printed "If you do".
  ⭐ **`push_deck_search(then_top_from_hand=)`** (Captain Vaughn TS26_39, "search the top 3 and draw it.  **Then**, put a card from your hand on top of your deck") — settled at the search's own resolve point.  ⚠ It could NOT be pushed first and left to LIFO: `push_bottom_from_hand` reads the hand at PUSH time and fizzles on an empty one, and the whole point is that the card the search just drew is among what may go back.  **When a "then" clause depends on what the first decision PRODUCED, it must be a settle-at-resolve rider, not a pre-push.**
  ⭐ **`not_attached_host` predicate** — "deal 1 damage to **another** friendly unit" said by an UPGRADE's When Played (Fiery Alliance TS26_25).  `not_self` is WRONG there: the source is the upgrade, so it excludes the upgrade (no candidate anyway) and happily offers the very unit it is riding.  Reads the standard `event_ctx["attached_to_id"]`, so a non-upgrade source is simply unfiltered.
  ⭐ **`CostReduction.per_friendly_leader_unit`** (Take Action TS26_71) — shares `resolver._is_leader_unit` with the `leader_unit` predicate, so the two readings of "leader unit" cannot drift and an UNDEPLOYED leader (base zone, no unit) correctly discounts nothing.  ⚠ `_is_leader_unit(ci)` takes ONE argument, not `(state, ci)`.  Paired with **`Condition.CONTROLLER_BASE_MORE_DAMAGED_THAN_ENEMY`** (Millennium Falcon IBH_31) — a COMPARISON, not the `CONTROLLER_BASE_DAMAGE_MIN` threshold, and STRICT, so a level count satisfies neither it nor its mirror.
  ⭐ Two `DealDamageEqualTo` counts, both read at RESOLUTION so the card's own leading effect already counts: **`source_controller_experience_tokens`** (Backed by the Pykes TS26_58 — the Experience it just handed out is part of the magnitude) and **`enemy_damaged_units`** (Backed by Black Sun TS26_70 — the unit its leading 1 damage just damaged counts; friendly damaged units do not).
  ⭐ Two settle-at-resolve riders on existing decisions: **`push_name_and_discard(then_foreign_discard_play=)`** (Mother Talzin TS26_26 — Bazine Netal SHD_184's look-and-strip plus "if the discarded card is a UNIT, for this phase you may play it from their discard pile ignoring aspect penalties", recording that one instance in `game_memory.foreign_discard_play_this_phase`, the PAID cross-pile permission built for Obi-Wan Kenobi SEC_205 whose enumeration branch already expresses the waiver as a discount) and **`push_select_token(then_draw_if_enemy_chosen=)`** (Secret Marriage TS26_46 — one draw when any pick landed on an ENEMY unit, none when every pick was friendly).
  ⭐ **The `may_discard` ACCEPT arm** (`push_may_discard_for_debuff`, `ctx["then_debuff"]`) — Kouhun Assassination TS26_33 is the ONE card in the DB whose payoff sits on the discard rather than the refusal.  ⚠ **DOCUMENTED ODDITY, implemented as printed**: because the payoff harms the deciding player, a rational opponent always declines and the card does nothing.  Every sibling template (Look the Other Way SHD_227, Political Pressure TWI_222, Syril Karn SEC_133) puts the penalty on the DECLINE arm, so the DB text reads like an upstream "If they do"/"If they don't" slip — flipping it is a rules judgement, not an encoding one, so it is flagged rather than "fixed".
  ⭐ PURE REUSE worth carrying: **"Only opponents may use this ability" needs NO new gate** (C-3P0 TS26_15) — the ability enumeration already offers a unit's Actions to whoever CONTROLS it, and the card's own When Played `change_control`s him to the opponent, so the ordinary controller scoping IS the printed restriction.  **"On Defense" IS `WhenAttacked`** (Sundari Gauntlet TS26_24, the Canto Bight Security LAW_121 note).  "When YOUR base is dealt COMBAT damage" is `WhenDealsCombatDamageToBase(filter=TargetSpec(controller="enemy", kind="unit"))` — the LOF_25 observer form; an enemy unit attacking a base always hits yours in two-player, and combat-only is intrinsic (unlike `WhenDamageDealtToYourBase`, which any damage source feeds) (Moralo Eval TS26_73).  "Attached unit LOSES the Jedi trait" is a PERMANENT `trait_revoke` modifier armed on play (Exiled from the Force SEC_54 + the Lando JTL_3 lifetime recipe), while the same card's Restore rides the upgrade-SELF `ConstantAbility(KeywordGrant)` and its optional bounce is a SEPARATE When Played ability — only separate abilities carry different `optional` flags (Bossk LAW_31) (TS26_37).  Maul TS26_3's "more different keywords than Experience tokens on it" is `keywords.distinct_keyword_count` (Gallius Rax ASH_100) in ONE targeted `CustomEffect`, with the CHOICE ungated and only the payoff conditional ("Choose a unit.  If it …").  Ahsoka TS26_8 is `push_peek_top("may_play_discard")` twice — undeployed off a `WhenYouPlayCard(card_type="event")` observer gated `SOURCE_READY` with the exhaust bundled into the payoff `CustomEffect` (an undeployed leader is no arena unit, so `ExhaustCard(fixed=SELF)` cannot say it — the Boba Fett JTL_9 convention), deployed off `WhenAttackEnds` at `cost_reduction=1` (Improvise LAW_242).  IBH_1 Leia's "heal a friendly unit and ANOTHER" is IBH_5's record-then-exclude pair (the effect FN stamps `excluded_target_id`; a plain pair of declarative `Heal`s would heal the SAME unit twice — the ASH_233 lesson), with `damaged` on both so nothing is ever offered as a no-op.  **IBH_10 and IBH_42 are the same printed Han Solo** whose DB rows differ only in the DASH CHARACTER of "-2/-0", so the reprint identity keys them into separate singleton groups and BOTH must be registered — the `_norm_rules` blind-spot, live again.
  ⚠ **WORKFLOW: the walker can SWALLOW a `MILESTONE:` line.**  IBH completed this batch (sets 17→18), but `next_group.py` only prints MILESTONE when the newly active set has ZERO completed groups — and TS26 had five by then.  **Trust the `sets complete N/24` counter, not the banner**: if it moved, run the medium tier + `audit_coverage.py`.
  🧪 TEST NOTES: `_place_leader` puts the leader in `base_zone` AFTER the base, so `base_zone[0]` is the BASE — read a leader back with `state.find_instance(id)[1]`, since `_find_instance` searches arenas only; the regroup `PhaseStartTrigger` fire site is a plain `fire_triggered_abilities(state, PhaseChanged(new_phase="REGROUP", …))`; `compute_power` FLOORS AT 0, so a -8/-8 debuff on a 3-power unit must be asserted through the modifier, not the number; and Redemption SOR_52 is a **Vehicle**, so it is no stand-in for a "non-Vehicle unit" target test.
- **ash-set:25–29 + ibh-set:01–02 batch (7 groups, 42 cards — 🏁 COMPLETES ASH,
  264/264, and takes IBH to 99/104)** — all additive; **no new decision kind**, no
  escape hatch, no escalation.  ASH's tail is the Mandalorian token and the
  Advantage token in one more window each, so most of it is reuse; the IBH pair is
  pure composition with no engine change at all.
  ⭐ **`_defeat_unit(by_combat_damage=True)` → `event_ctx["defeated_by_combat_damage"]`**
  — the exact sibling of `while_attacking` (Luthen Rael SEC_13), passed by the FOUR
  combatant-death sites of the two unit-combat pipelines (which are reached only
  after the damage step).  "When Defeated: **If this unit wasn't defeated by combat
  damage**, …" (Paz Vizsla ASH_28, Shin Hati's Fiend Fighter ASH_191) is then a plain
  read — and, being a bool rather than a CardInstance, it SURVIVES an optional
  trigger's decision round-trip, unlike `defeated_ci`.  Every other defeat route (an
  ability, the state-based HP sweep, an exploit sacrifice) reads False, which is
  exactly what those cards mean.
  ⭐ **`BaseDamageCap(amount)`** marker — "If your base would be dealt more than 4
  damage, prevent all but 4 of that damage" (At Attin Safety Droid ASH_70).  Bases
  have no single damage chokepoint, so it rides the ONE shared helper
  `actions.base_damage_after_prevention` (Close the Shield Gate JTL_74's), which every
  base-damage site already calls — ability damage, indirect damage, a base attack,
  both Overwhelm spill sites, a leader's base hit and the empty-deck penalty, capped
  by one read.  Per INSTANCE, not per phase; applied BEFORE the one-shot prevention,
  so a pending JTL_74 charge eats the capped hit rather than being spent by the cap.
  ⭐ **`SearchWindowDoubler`** marker — "If you would search a number of cards from
  your deck, search twice that number instead" (Arcana Star Map ASH_84).  Read at the
  single `push_deck_search` ENTRY point, where the window is still just a number, so
  every search route (plain, search-and-play, search-and-play-an-upgrade, a foreign
  search) doubles at once; only the WINDOW doubles, never `count`.  The scan walks the
  searching player's arena units AND their attached upgrades, which is what lets the
  marker be registered BARE on an upgrade for "attached unit gains …" with no
  ConstantAbility wrapper — and keyed on the HOST's controller, so it follows the unit.
  ⭐ **The Darksaber ASH_135 = two one-line markers, no decision**:
  **`LeaderUnitGrant`** ("Attached unit is a leader unit") joins
  `resolver._is_leader_unit`, which already answered that for a leader-piloted Vehicle
  (Boba Fett JTL_9) — so the host dodges "defeat a NON-LEADER unit" removal and joins
  "each leader unit you control" auras for free; and **`ProvidesAspectIcons`** ("this
  unit provides its aspect icons while you are paying costs") joins
  `actions._available_aspects`, the ONE place that decides which icons offset an
  aspect penalty, so every play route and the web penalty pill follow.  Its third
  clause is the ordinary upgrade-SELF `ConstantAbility(TraitGrant)`.
  ⭐ **`AdvantageTokensLoseAbilities`** marker — "(They aren't defeated after combat.)"
  (Eviscerator ASH_149).  The Advantage token's ONLY ability is its end-of-combat
  expiry, and that lives in the combat pipelines rather than the registry, so "lose all
  abilities" collapses to `tokens.defeat_advantage_tokens` declining to run for that
  player's units — the `EnemyCreditsLoseAbilities` LAW_117 shape.  The +1/+0 stays
  (printed stats are not an ability), which is the point of the card.
  ⭐ **Deadly Vulnerability ASH_150 = two markers**: `DamageAmplification` gained a
  **`multiplier`** field AND its read now walks a unit's ATTACHED UPGRADES, so "If
  attached unit would take damage, it takes TWICE as much instead" rides Vigil SEC_50's
  existing chokepoint (before prevention and the Shield, so a Shield still eats the
  whole doubled instance); and **`AttackerLosesOverwhelm`** is read at the two
  Overwhelm excess-SPILL steps (`actions._overwhelm_denied_by`) rather than as a
  `KeywordRevoke` aura — the keyword layer carries no combat context and could not tell
  "while attached unit is DEFENDING" from any other moment, and Overwhelm does nothing
  anywhere else, so disabling it there IS losing it.
  ⭐ **"The FIRST non-unit card you play each phase" needs no spend ledger** (Peli Motto
  ASH_212): `IgnoreAspectPenaltyForPlays` gained `card_type="non_unit"` (the complement
  filter) and is gated by the new **`CONTROLLER_NO_NON_UNIT_PLAYED_THIS_PHASE`** atom
  over a new phase-scoped COUNT `game_memory.non_units_played_this_phase` — the waiver
  is simply live until that player has played one.  ⚠️ A COUNT, not the existing
  `non_unit_traits_played_this_phase` trait set, which a TRAITLESS non-unit card leaves
  empty.  The count is written at the CardPlayed chokepoint, i.e. AFTER the cost is
  paid, so the first play still sees zero and really is waived.
  Smaller, all additive: the **`non_token`** predicate (the exact negation of
  `token_unit`, and what stops Bo-Katan's Gauntlet ASH_63's
  `AuraGrantedAbility(WhenDefeated)` from making its own Mandalorian tokens
  self-replicating); **`Condition.CONTROLLER_BASE_ATTACKED_THIS_PHASE`** over the
  `base_attackers_this_round` ledger (Ephant Mon SHD_88's, keyed by base OWNER and
  written at the DECLARE step, so it really means "attacked" — Greef Karga ASH_119,
  used as the ability's `condition` so the resource + exhaust are never spent on a
  no-op); **`CONTROLLER_HAS_UNIQUE_UNIT`** (the mirror of Rose Tico LAW_223's
  non-unique atom — Protectorate Fighter ASH_124); and
  **`CONTROLLER_LEADER_UNIT_DEFEATED_THIS_PHASE`** over the new controller-keyed
  `leader_unit_defeat_controllers_this_phase`, because Captain Pellaeon ASH_93's
  id-keyed set deliberately carries no side (Fateful Goodbye ASH_211).
  ⭐ PURE REUSE worth knowing: Pointless to Resist ASH_54's "-3/-0 while attacking a
  base" is NOT a ConstantAbility — the attached-upgrade stat scan has no combat context
  — but a PERMANENT `while_attacking_base` stats modifier landed from the upgrade's own
  When Played, reusing Sly Moore SEC_33's flag with the Lando JTL_3 lifetime recipe
  (`_modifier_source_in_play` counts an attached upgrade as in play).  Buy Time ASH_91
  works because `_create_token_units` RETURNS the instances it made, so "give **it**
  Sentinel" is a keyword_grant modifier on that exact token with no target choice.
  Rehabilitation ASH_200 is the Change of Heart SOR_224 pair (`change_control` +
  `return_control_to_owner_at_regroup`) with the −3/−0 folded into the SAME targeted
  CustomEffect (the SHD_18 single-prompt rule).  There Is No Conflict ASH_199 is Kit
  Fisto LOF_147's `push_select_token(restrict_ids=, return_to_hand=True)` with token
  upgrades excluded (they have no owner's hand).  Helgait ASH_195 reads
  `event_ctx["defeated_power"]` — the effective power `_defeat_unit` snapshots BEFORE
  stripping his upgrades.  IBH_95 is the In Pursuit TWI_221 `prior_target_id` chain with
  a DEFEAT as the cost; IBH_104's "up to 2" needs no `excludes_event_targets` at all —
  the first defeat already removed its target from the arena (General Grievous TWI_34's
  four-effect shape).
  ⚡ **PERF DISCIPLINE**: `_available_aspects` runs for EVERY cost computation and
  `_is_leader_unit` runs inside target matching, so both new reads — and the
  per-attack Advantage-token one — sit behind CACHED REGISTRY KEY INDEXES
  (`_aspect_icon_provider_keys`, `resolver._leader_unit_grant_keys`,
  `tokens._ADVANTAGE_INERT_KEYS`), the `_suppress_leader_keys` trick.  Each of the six
  new markers is registered on exactly ONE card, so those sets are tiny and the board
  walks never run.  Measured: a cProfile of the vanilla soak puts this batch's whole
  new surface at **~1.2% of runtime** (`deepcopy`, sqlite and `has_keyword` dominate) —
  so do NOT read a slow suite tier as a regression without profiling first; the old
  "~4 min fast / ~6 min medium" figures simply no longer hold at 2088 registered cards.
  🧪 TEST NOTES: TWO long-rotting stand-ins were made SELF-FINDING this batch rather
  than re-pointed — `test_reprints.py`'s keyword_deferred stand-in (which had died on
  SEC_73 → ASH_103 → ASH_52 → ASH_133 → ASH_111 and had nothing left to name once ASH
  completed) now derives an unregistered keyword-free text-bearing card at run time, and
  `test_plan_encoding.test_set_code_input` no longer asserts ASH yields groups.  Also:
  `game_memory.defeated_controllers_this_round` is a **list**, not a set; playing a card
  hands the turn over, so a test that plays twice must reset `active_player_index`; and
  the `distribute_damage` context key for the pool is **`pool`**, not `remaining`
  (that one is `select_token`'s).
- **ash-set:18–24 batch (7 groups, 44 cards — ASH now 229/264)** — all additive;
  **no new decision kind**, no escape hatch, no escalation.  Almost all of it is the
  ASH Advantage token being handed out in every conceivable window.
  ⚡ **THE ADVANTAGE SWEEP NOW TAKES A SNAPSHOT** (`actions._snapshot_advantage_tokens`
  → `defeat_advantage_tokens(only_ids=)`).  All three pipelines fire their
  attack-end triggers and only THEN sweep, so a card that hands out an Advantage
  token AT that moment — Bokken Saber ASH_180 ("Attached unit gains: 'When Attack
  Ends: Give an Advantage token to this unit'"), Vane's Snub Fighter ASH_144 — had it
  taken straight back by the attack that granted it.  The snapshot is taken right
  after defeat processing, so ONLY what the attack really rode with expires and every
  existing ordering (ledgers, observers) is byte-identical.
  ⭐ **`WhenUpgradeAttached`** observer trigger — "When 1 or more upgrades attach to
  this unit (**including from Shielded**)" (Sabine Wren ASH_208).  The
  `WhenFriendlyUpgradeDefeated` settle-drain shape mirrored: a
  `game_memory.upgrade_attachments` queue of HOST ids fed by
  `actions.note_upgrade_attached` at every attachment chokepoint — `tokens.attach_token`
  (which IS the parenthetical), `_attach_upgrade`, `_relocate_upgrade`, both pilot
  attaches — and drained COALESCED PER HOST, so "1 or more" is exactly one firing.
  ⚡ The FEED (not just the drain) is gated on the cached
  `_upgrade_attach_observer_keys()` index: every Shield / Experience / Advantage token
  attaches, so a board with no such card must record nothing at all.
  ⭐ **`AmbushAttackerBonus`** marker — "While attacking using Ambush, this unit gets
  +2/+0" (Heroic Purrgil ASH_207), the attacker-side mirror of `AmbushDefenderDebuff`
  read at the same single seam `UseAmbush.apply` as a `this_attack` modifier.  A
  `ConstantAbility(while_attacking=)` cannot say it — that flag knows only THAT the
  source is attacking, never whether AMBUSH declared the attack.
  Two new PHASE-scoped/pending ledgers, both the shape their neighbours already use:
  **`units_damaged_this_phase`** (← the single unit-damage chokepoint, only for damage
  really dealt) behind the **`damaged_this_phase`** predicate — the exact mirror of
  Barriss Offee TWI_42's heal ledger, and deliberately NOT the `damaged` predicate: "a
  unit that was damaged this phase" (Galvanized Leap ASH_188) still means one healed
  since; and **`pending_enters_ready`** (`{player_id, power_max}`, the
  `pending_keyword_grants` LOF_180 charge shape) consumed in `_put_unit_in_play` right
  where the placement reads `enters_ready` — "the next unit you play this phase with 1
  or less power enters play ready" (Neel ASH_248).
  Smaller, all additive: **`push_select_token(allow_repeats=True)`** turns the
  select-up-to-N loop into a POOL DISTRIBUTION — a chosen unit stays pickable, so
  "Distribute up to 5 Advantage tokens among other friendly units" (Elzar Mann
  ASH_224) can stack them all on one unit — with its `then_opponent_event_search`
  rider (a FOREIGN `deck_search` at 2× the tokens actually given, the Sabé SEC_17
  shape); **`push_granted_attack(opponent_discard_if_base_damaged=)`** (Rash Action
  ASH_162, the opponent-facing sibling of Stay on Target JTL_177's
  `draw_if_base_damaged`, sharing its snapshot and settle point but re-read PER PLAYER
  so only a damaged OPPONENT's base counts) and
  **`(bonus_per_defending_arena_unit=)`** (Masterstroke ASH_234 — the POPULATION
  sibling of Corner the Prey TWI_139's defender-damage count);
  **`push_bottom_from_discard(then_heal_base=)`** (Trask Walker ASH_133, the heal
  flavour of the settle-at-the-finish payoff family); **`CostReduction.host_trait`**
  (Faith in the Empire ASH_262 / The Way of the Mand'alor ASH_263 — the `host_named` /
  `host_unique` sibling); **`Condition.CONTROLLER_HAS_TRAIT_LEADER`** (Elzar Mann
  ASH_224 — trait-narrowed AND base-zone-inclusive, so an UNDEPLOYED Force leader
  counts, unlike `CONTROLLER_HAS_LEADER_UNIT`); and two StatBonus counts —
  **`upgrades_on_other_friendly_units`** (Executor ASH_197) and
  **`other_zero_power_units`** (Kelleran Beq ASH_206), the latter carrying its own
  reentrancy guard `_ZERO_POWER_COUNT_EVALUATING` because it reads EFFECTIVE power and
  `compute_power` re-enters the very constant scan evaluating it (the
  `SOURCE_POWER_MIN` lesson; a re-entrant 0 is also the right answer, since the bonus
  lands on Kelleran alone).
  ⭐ PURE REUSE worth knowing: Trask Walker ASH_133's "either … or" is
  `push_choose_modal(pick=1)` over two `EventAbility` options, each pushing the
  decision that already models its disposition (`bottom_from_discard` /
  `return_from_discard`); Follow Me ASH_184 is the Barrel Roll JTL_228 rule — TWO
  `EventAbility`s so the TARGETED token effect pushes its ChooseTarget first and the
  attack lands ON TOP and resolves first; Choose Your Path ASH_257 is a `choose_modal`
  on an EVENT card, so its option specs must be **TriggerAbility** (the Confidence in
  Victory SEC_145 rule, the exact mirror of ASH_133's), with the dead modes filtered
  out at push time; Diplomatic Pageantry ASH_231 is the LAW_41 shared-`event_ctx`
  chain, the second (enemy) pick carrying the payoff so an unpaid half hands out
  nothing.
  ⚠⚠ **A two-step "up to 2 DIFFERENT units" must be two `CustomEffect`s, not two
  declarative effects** — it is the effect FN that stamps
  `event_ctx["excluded_target_ids"]`, so a plain `ExhaustCard` pair over
  `excludes_event_targets` offers (and takes) the SAME unit twice (Keep Them Talking
  ASH_233).
  🧪 TEST NOTES: an `EntersPlayReady` marker needs the real
  `_put_unit_in_play`, not `_place`; the `deck_search` context key for the window SIZE
  is `window` (there is no `window_ids`); `_play_cost(state, ci, ps, target_host_id=)`
  takes a CardInstance, not a card_def; `_fire_when_defeated(state, ci)` takes no
  owner; and an Ambush attack is easiest driven by injecting the `ambush` decision by
  hand (the `test_keywords` shape).
- **ash-set:13–17 batch (5 groups, 35 cards — ASH now 185/264)** — all additive;
  **no new decision kind**, no escape hatch, no escalation.  Four ASH LEADERS whose
  clauses all key off the END of an attack, plus a long tail of conditional SELF
  grants.
  ⭐ **THE ATTACK-END FIRES NOW CARRY *HOW MUCH* BASE DAMAGE** —
  `attack_ended_base_damage_amount` beside the long-standing
  `attack_ended_base_damage` marker, on ALL THREE pipelines.  One key serves three
  readings: a THRESHOLD (`WhenFriendlyUnitAttackEnds(require_base_damage_min=3)` —
  Ezra Bridger ASH_13, so the trigger is not even collected below it and there is no
  prompt), a CEILING (Shin Hati ASH_16, "a unit that costs less than the amount")
  and a MAGNITUDE (Hera Syndulla ASH_31, "heal that much from your base").
  ⚡ **AND OVERWHELM SPILL NOW COUNTS**: the two unit-combat pipelines set
  `attack_ended_base_damage` + the amount for their spill AND call
  `record_base_damage` for it — excess dealt to a base IS combat damage dealt to a
  base, so `WhenAttackEnds(require_base_damage=True)` (Maul LAW_54) and the
  `WhenDamageDealtToYourBase` observer (The Daughter LOF_252) both got more faithful
  for free.
  ⭐ **`WhenYouPlayOrCreateUnit`** observer trigger — "When you play **or create** a
  unit" (Greef Karga ASH_17) / "When a friendly unit enters play (including this
  one)" (Outcast ASH_41).  The `WhenUnitHealed` settle-drain shape over a new
  `game_memory.unit_entries` queue fed at **`_put_unit_in_play`** — the ONE
  chokepoint a hand/discard/smuggle/plot play, an ability play and a created token
  unit all pass through, which is exactly the union those two cards name.  "That
  unit" is `event_ctx["entered_unit_id"]`; `include_self` (default True) is ASH_41's
  parenthetical, free because the drain runs with the unit already in its arena.
  ⚡ Both the append and the drain are gated on the cached
  `_unit_entry_observer_keys()` index — a unit entering play is one of the commonest
  things that happens.
  ⚠️⚠️ **`ATTACHED_HOST_NAMED` / `ATTACHED_HOST_HAS_TRAIT` DO NOT WORK ON AN
  UPGRADE'S SELF `ConstantAbility`.**  The keyword layer's attached-upgrade scan
  evaluates that spec's condition against the **HOST**, but those two atoms expect
  the UPGRADE as their source and look the host up from it — handed the host they
  silently read False.  Use the HOST-side atoms: `SOURCE_HAS_TRAIT` /
  `SOURCE_HAS_ASPECT` (Constructed Lightsaber LOF_261) and the NEW **`SOURCE_NAMED`**
  (substring on the source card's name — Luke's Jedi Lightsaber ASH_66, Sabine's
  Lightsaber ASH_114, whose "Sabine Wren **or** a Force unit" is ONE `ANY_OF`
  composite so a Force Sabine gains Restore 2 only once).
  Two new PHASE-scoped ledgers, each fed at the chokepoint that already drove its
  drained-queue observer, so nothing new had to be threaded:
  **`bases_damaged_this_phase`** (← `record_base_damage`) behind
  `Condition.ENEMY_BASE_DAMAGED_THIS_PHASE` and **`upgrades_defeated_this_phase`**
  (← `note_upgrade_defeated`) behind `CONTROLLER_UPGRADE_DEFEATED_THIS_PHASE` —
  together the two clauses of Baylan Skoll ASH_39, registered as **FOUR**
  single-effect abilities (When Played × When Attack Ends × two clauses) because only
  separate abilities can carry different `optional` flags and per-clause conditions
  (the Bossk LAW_31 rule).  Plus **`leader_units_defeated_this_phase`** (← the
  `_defeat_unit` ledger block) behind `ANY_LEADER_UNIT_DEFEATED_THIS_PHASE`, which is
  deliberately NOT keyed by controller — Captain Pellaeon ASH_93 counts either
  player's leader.
  Smaller, all additive: **`Condition.CONTROLLER_HAS_OTHER_NON_UNIQUE_UNIT`** (the
  self-excluding sibling of Rose Tico LAW_223's — AT-ST Raider ASH_98 is itself
  non-unique and would satisfy its own clause);
  **`SOURCE_SOLE_FRIENDLY_NON_LEADER_UNIT_IN_ARENA`** (the CONDITION sibling of the
  `sole_friendly_non_leader_unit_in_arena` predicate — Shin Hati ASH_49, where a
  friendly deployed leader does not break the clause); the predicate
  **`n_plus_keywords_<N>`** over the new **`keywords.distinct_keyword_count`**
  (Gallius Rax ASH_100 — LIGHTWEIGHT for the Boba Fett SHD_8 reason: a full
  `has_keyword` sweep would recurse back into the constant scans evaluating this very
  aura); and **`StandingPlayDiscount(applies_to="upgrade_not_on_source")`** (Pit Droid
  Team ASH_75, the complement of Guardian of the Whills SOR_61's `upgrade_on_source`
  — the chosen host must be a unit the controller controls and NOT the source).
  ⭐ PURE REUSE worth knowing: Marrok ASH_30's "he loses Sentinel and gains Saboteur"
  is TWO SELF constants over one `SOURCE_ATTACHED_UPGRADES_MIN(1)` — a `KeywordRevoke`
  (read ahead of every grant source, so the printed Sentinel really goes) and a
  `KeywordGrant`; a Shield / Experience / Advantage token IS an upgrade, so any of
  them flips him, and he is the card CLAUDE.md already cited for sanitiser rule 10's
  leading-bar-line guard (Sentinel kept, the mistagged Saboteur stripped by rule 2).
  The Conflict Within ASH_88 is In Debt to Crimson Dawn JTL_192 verbatim at
  `pay_amount=3` (`GrantedAbility` + `WhenUnitReadies`, so the decision can be pushed
  from inside the REGROUP mass-ready).  T-6 Shuttle ASH_109's "give another unit +2/+2
  … You may attack with **that** unit" is ONE targeted CustomEffect that pins
  `push_granted_attack(attacker_id=…, optional=True)` to the chosen target — a second
  free choice would let the buff and the attack name different units.  Home One
  ASH_65's "heal ALL damage" has no magnitude: read each unit's own `damage` and heal
  exactly that through `_apply_heal`, so the heal observers still see every one.
  🧪 TEST NOTES: a leader's own keyword bar lives in `deploy_box`, so a "vanilla"
  low-power attacker for a base-damage threshold test must really be vanilla
  (Underworld Thug SOR_247, 2/3) — a card with printed Raid quietly clears the bar;
  `_make_kw_modifier`'s `duration` is a `Duration` enum, not a string; and
  `_fire_when_played` cannot thread `attached_to_id` — an upgrade's When Played needs
  `_fire_upgrade_played(state, upgrade, host)`.
- **ash-set:12 — the ASH LEADER block (7 cards — ASH now 150/264)** — all additive;
  **no new decision kind**, no escape hatch, no escalation.  ⚠️⚠️ THREE of its seven
  numbers are TOKEN COLLISIONS (ASH_1 = the Mandalorian token UNIT, ASH_2 = the
  Advantage token UPGRADE, ASH_3 = the Shield token UPGRADE), so only side-gated
  `ActivatedAbility(undeployed_only=)` / `(deployed_only=)` and
  `TriggerAbility(deployed_only=)` are registered there — a regression test pins the
  spec KINDS for ASH_3.
  ⭐ **PLAYING A CARD OUT OF THE RESOURCE ROW** — `push_play_upgrade_from_hand
  (from_resources=, host_controller=, host_predicates=, then_resource_top_of_deck=)`
  (The Armorer ASH_1, "Play an upgrade from your resources on a unit that entered
  play this phase (paying its cost).  If you do, resource the top card of your
  deck").  The row becomes a fourth source zone beside hand / own discard / every
  discard; unlike Smuggle the card is NOT replaced from the deck — which is exactly
  why the card hands the row a card back.  ⚠️ It cannot pay for itself: the new
  `_play_upgrade_affordable` requires one MORE resource than the cost whenever the
  candidate is itself ready (the Smuggle "other ready resources" rule), so the offer
  and `_pay_play_cost` — which runs after the card leaves the row — cannot disagree.
  `host_controller`/`host_predicates` narrow the hosts through the ordinary
  TargetSpec matcher, and the gate atom
  **`CONTROLLER_CAN_PLAY_UPGRADE_FROM_RESOURCES`** reuses the decision's own
  candidate filter so the Exhaust is never spent on an impossible play.
  ⭐ **`DeployCondition` marker + `actions._leader_deploy_allowed`** — the escape for
  a leader whose Epic Action clause the `_deploy_threshold` regex cannot read.  Such
  a leader has ALWAYS been undeployable (the documented "Bo-Katan's Mandalorian
  count" limitation); ASH_10 Bo-Katan Kryze ("If the number of resources you control
  plus the number of friendly Mandalorian units is 10 or more") now registers a
  marker read at ONE new helper that the three deploy seams (the `legal_actions`
  offer, `DeployLeader.apply`, `DeployLeaderAsUpgrade.apply`) all funnel through, so
  offer and guards agree.  Paired with the atom
  **`CONTROLLER_RESOURCES_PLUS_TRAIT_UNITS_MIN`**; every other leader is byte-identical
  (no marker ⇒ the threshold path, unparsable ⇒ still "cannot deploy").
  ⚡⚡ **KEYWORD-SANITISER RULE 9 NOW COVERS LEADERS** — its line test reads
  `text` + **`deploy_box`** (a new `sanitize_keywords(deploy_box=)` argument threaded
  from `repository._hydrate`), because a leader's own keyword bar is the LEADING LINE
  of its deployed side.  Rule 9 was Units-only precisely because the module never saw
  that box.  MEASURED DB-wide: exactly **5 leaders** change, all genuine mistags —
  IG-88 SOR_12 (Raid), General Grievous TWI_15, Ahsoka Tano LOF_3, Baylan Skoll ASH_3
  (Sentinel) and Grand Admiral Sloane ASH_7 (loses the granted Sentinel, KEEPS her
  printed Overwhelm, which leads her deploy box).  Companion: the inert
  **`CustomEffect.grants_keywords`** field DECLARES a grant buried inside `fn` to that
  rule — Baylan gives ONE unit +2/+2 *and* Sentinel from a single effect (two targeted
  effects would prompt twice and could split them, the TWI_249 rule), which would
  otherwise hide the grant from the sanitiser.
  Smaller, all additive: **`push_select_token(mandatory=, then_pending_keyword=)`** —
  the first withholds the early `FinishSelectToken` while a pick remains (a clause with
  no "up to": "An opponent GIVES 2 Advantage tokens to a unit they control", Sabine
  Wren ASH_6; still offered when nothing is eligible, so legal_actions is never empty),
  the second is that card's "If they do" — a `pending_keyword_grants` entry (Deceptive
  Shade LOF_180) armed for the SOURCE's controller, never the decider, and only when a
  unit was really chosen.  ⚠️ `controller=` on that decision is read from the SOURCE's
  perspective, so "a unit THEY control" is `"enemy"` even though the opponent decides.
  Three predicates: **`sole_friendly_unit_in_arena`** /
  **`sole_friendly_non_leader_unit_in_arena`** (Baylan ASH_3 — the "if it's the only …"
  clause is a CANDIDATE filter, not a condition, and the non-leader reading exists
  because Baylan himself is standing in the arena when his On Attack resolves) and
  **`attack_ended_attacker_or_own_base`** (Luke Skywalker ASH_5, "Heal 2 damage from
  that unit or from your base", over the `attack_ended_attacker` key the
  `WhenFriendlyUnitAttackEnds` fire always carries).
  ⭐ PURE REUSE worth knowing: "Action [1 resource, Exhaust, **exhaust a friendly
  unit**]" is a LEADING TARGETED `ExhaustCard` effect with the play behind it (the Tomb
  of Eilram LOF_28 / Krennic LAW_8 no-cost-spec shape) — Fennec Shand ASH_2, gated on
  `ALL_OF(CONTROLLER_CAN_PLAY_UNIT_FROM_HAND, CONTROLLER_HAS_READY_UNIT_COST_MAX)` so
  neither cost is spent on a no-op; Luke ASH_5's undeployed "you may exhaust this
  leader.  If you do, heal 1" is ONE CustomEffect with an `available_fn` (Shadow Caster
  JTL_169) so a ready-leader-plus-damaged-attacker check gates the OFFER; Sloane ASH_7's
  "Choose one: each ground / each space unit" is `push_choose_modal(pick=1)` whose option
  specs must be **EventAbility** — she is a LEADER, and a TriggerAbility option would be
  collected for real from the base zone (the Lightmaker SEC_207 rule, mirrored).
  🧪 TEST NOTES: the DB `type` of a token unit is `"Token Unit"` (with a space); a
  leader's `leader_power` may be 0 while its deployed `power` carries the real number.
- **ash-set:08–11 batch (4 groups, 26 cards — ASH now 143/264)** — all additive;
  **no new decision kind**, no escape hatch, no escalation.
  ⭐ **`UnpreventableDamage`** marker — the complement of the whole
  `DamagePrevention` family, read at the same single unit-damage chokepoint but
  keyed on the DEALER: "Damage dealt by friendly Underworld cards is
  unpreventable" (Gorian Shard's Corsair ASH_196) skips every prevention AND the
  Shield.  The dealing CARD is resolved from the new **`dealer_source_id`** kwarg
  that `_deal_damage_with_shield` now carries — threaded from the resolver's
  ability-damage arms (which already had `source_id`) and from the combat
  pipelines (attacker/defender) — through `find_instance`, which REACHES THE
  DISCARD, so a spent Underworld EVENT counts as a "card" exactly as printed.
  ⚡ Gated on the cached `_unpreventable_damage_keys()` index.  DOCUMENTED
  NARROWING: a bespoke card-module damage call with no dealer id, and base damage,
  are not covered.
  ⭐ **`play_from_hand` grew its "up to N" LOOP** — `push_play_from_hand(repeat_max=,
  up_to=)` plus the new `DeclinePlayFromHand` action: each play re-pushes the
  decision with one fewer remaining **BEFORE** the unit enters play, so the played
  unit's own When Played resolves before the next pick (the Endless Legions SHD_109
  ordering), and `up_to` finally gives that long-standing mandatory-if-able decision
  a decline.  "Play up to 3 non-Vehicle units that each cost 2 or less from your
  discard pile for free" (Dathomiri Magicks ASH_104; `from_discard` alone would also
  offer the HAND, so the whitelist is `eligible_ids` — the JTL_121 convention), and
  it is also what makes One Must Destroy to Create ASH_247's "then, you may play
  that unit" a real "may".  Both the enumeration and the re-push read
  `_play_from_hand_candidates(state, ps, ctx)`, so they cannot disagree.
  ⭐ **The BORROW gained an explicit lender** — `push_granted_attack(borrow_lender_id=)`
  (default: the source, i.e. Support).  With `push_deck_search`'s new
  `then_borrowed_attack_by` rider that is the whole of "Search the top 3 for a ground
  unit and discard it.  Then, you may attack with this unit.  For this attack, this
  unit gains the discarded unit's abilities" (Improvised Identity ASH_230, a
  `GrantedAbility(ActivatedAbility(once_per_round))`): the lender sits in the DISCARD,
  which `borrowed_ability_sources` already reaches.  No ability-copying machinery.
  ⭐ **THE PINNED PHASE AURA, arena flavour** — "Choose an arena.  For this phase,
  each unit in that arena gains: 'On Attack: Deal 2 damage to this unit'"
  (Treacherous Minefield ASH_186) is ONE `AuraGrantedAbility` over
  `game_memory.phase_aura_sources`, pinned by the new **`in_source_chosen_arena`**
  predicate reading a new `game_memory.chosen_arenas` ledger (the
  `chosen_keywords` / SOURCE_CHOSEN_KEYWORD shape, JTL_47) — so one spec serves both
  branches instead of one per arena.  The arena itself is `push_choose_modal(pick=1)`
  whose option specs are **TriggerAbility** (an EVENT card — the SEC_145 mirror).
  ⭐ **`WhenYouDraw(any_phase=True)`** — the draw ledger now records REGROUP draws
  too, each entry tagged with its `phase`, but the MATCHER admits only ACTION ones
  unless the trigger opts in, so "during the action phase" stays intrinsic for every
  card that prints it and Axe Woves ASH_169's "(including during the regroup phase)"
  is the single opt-in.
  Smaller, all additive: `DealDamageEqualTo count="source_controller_units_damage"`
  (the damage-summing sibling of `source_controller_units` — Reckoning ASH_187);
  the `peek_top` mode **`may_discard`** (Keep vs Discard, the `may_bottom` sibling —
  Reanimated Night Trooper ASH_45, whose "a deck" is the CONTROLLER's own, the LAW_18
  reading); `push_choose_number(then=…)`, a continuation replacing the hard-wired
  C-3PO tail, paired with `push_deck_search(then_tokens_if_cost=…)` settled at the
  DRAW branch (the only place the drawn card's cost is known) — "Choose a number,
  then search the top 5 … If its cost is the chosen number, you may give 3 Advantage
  tokens to a Force unit" (Sense Through the Force ASH_235).
  ⭐ PURE REUSE worth knowing: ASH_55 Blade of Talzin's "When Defeated" on an UPGRADE
  is `WhenDefeatedAsUpgrade` (Roger Roger TWI_69) — the one seam that collects an
  upgrade's own trigger when its host dies (DOCUMENTED NARROWING: an upgrade picked
  off alone does not recur itself); ASH_128 Bothan-5 captures a corpse OUT OF THE
  DISCARD, which `_apply_capture` (arena units only) cannot do, so the relocation is
  spelled out in the card module — and it must read **`event_ctx["defeated_id"]`, NOT
  `defeated_ci`**, whose instance does not survive the optional trigger's decision
  round-trip; ASH_210's "On Defense" IS `WhenAttacked` (LAW_121) and its "a unit in
  this unit's arena" is `same_arena_as_source`, since a GrantedAbility already
  resolves FROM the host (JTL_35); ASH_220 = Bazine Netal SHD_184's
  `push_name_and_discard(optional=True, discarder_draws=True)` verbatim; ASH_232 is
  TWO single-effect `EventAbility`s (JTL_250) — 🧪 which resolve **LIFO**, so a test
  must route each ChooseTarget by the id it offers (the Barrel Roll JTL_228
  ordering).
- **ash-set:04 framework session — the token-doubling REPLACEMENT effect (Moff
  Jerjerrod ASH_94; ASH_94 was the last card of `ash-set:04`, now 7/7)** — additive;
  **no new decision kind**, no escape hatch, no core-machinery change.  "If you would
  create a number of tokens, you may defeat this unit.  If you do, create twice that
  number of tokens instead."
  ⭐ **The trick: a replacement effect re-read as an after-the-fact TOP-UP.**  The
  creation is left alone and the controller is instead offered *another N* tokens at
  the price of Jerjerrod — 2N either way, with no decision pushed from inside a
  creation (which is what made this an escalation).  So it needs only the ordinary
  settle-drain observer vocabulary: **`WhenYouWouldCreateTokens`**, the
  `WhenFriendlyUpgradeDefeated` shape, over a new `game_memory.token_creations` ledger
  of records `{creator, kind, name, count, host, ready}` fed at the THREE creation
  chokepoints (`tokens.attach_token`, `tokens.create_credit_token`,
  `actions._create_token_units`) and drained by `_fire_token_creation_observers`.
  `optional=True` carries the printed "you may" — no new decision kind, so no
  web/bot/invariants registration.
  ⭐ **COALESCING is what makes the doubling exact**: `GiveToken(count=2)` is TWO
  `attach_token` calls, so the drain merges equal-keyed records (same creator, kind,
  token name, host, ready-ness) into ONE event before firing — "give 2 Experience"
  doubles to 4, not 3.  ⚡ The drain is gated on the cached registry index
  `_token_doubler_keys()` (the `_shield_aura_prevention_keys` trick, **mandatory**
  here: every Shield, Experience and Advantage token feeds this ledger).
  ⚠️ The re-entrancy guard is a plain kwarg, not state: all three chokepoints take
  `note_token_creation=True`, and the shared top-up helper
  **`actions.apply_token_creation(kind, name, count, host_id, ready, creator_id)`** —
  the one place that knows how to re-run each creation shape — always passes False, so
  a doubling can never re-arm the doubler.  `CustomEffect.available_fn` (Shadow Caster
  JTL_169) suppresses the prompt when a token-UPGRADE's host has left play.
  DOCUMENTED DEVIATION: the tokens arrive in two batches and the defeat happens
  between them, rather than 2N created at once with Jerjerrod already dead.
- **ash-set:03–07 (5 groups, 34 of 35 cards — ASH now 116/264)** — all additive;
  **no new decision kind**, no escape hatch.  Its one ESCALATION — **Moff Jerjerrod
  ASH_94**, a REPLACEMENT effect on token creation with a player choice inside it (the
  IG-11 SHD_170 / Luke JTL_94 class) — was **CLEARED** in the dedicated framework
  session catalogued in the bullet above.
  ⭐ **`WhenFriendlyUpgradeDefeated`** observer trigger — "When a friendly upgrade is
  defeated" (Zeb Orrelios ASH_161).  The `WhenUnitReadies` settle-drain shape verbatim:
  a `game_memory.upgrade_defeats` queue of CONTROLLER ids fed by
  `actions.note_upgrade_defeated` at every upgrade-defeat site (`_defeat_attached_upgrade`,
  `resolver._apply_defeat_unit`'s attached branch, the host's own `_defeat_unit` — its
  upgrades die with it — and `tokens.defeat_shield` / `defeat_advantage_tokens`, which
  append inline since `actions` imports `tokens`), drained by
  `_fire_upgrade_defeat_observers` at the action settle-point.  ⚠️ A Shield / Experience
  / **Advantage** token IS an upgrade in SWU, so this fires constantly on an ASH board —
  which is exactly why ASH prints the trigger.  "Friendly" = the HOST's controller.
  ⭐ **`push_capture_combined_hp(disposition="defeat", target_controller="any",
  then_create_token_per_unit=)`** — the SEC_106 select-under-a-remaining-HP-budget walk
  turned into "Defeat any number of non-leader units with a total of 6 or less remaining
  HP.  Create a Mandalorian token for each unit defeated this way" (Pre Vizsla ASH_53):
  no captor, both players' units, and the picks killed AFTER the pop (a capture is inert
  inline, a defeat is not — the `push_distribute_damage` rule), the token count read off
  the units that really left play.
  ⭐ **`push_search_and_play_upgrade`** + the `deck_search` disposition **`play_upgrade`**
  — "search the top 8 for an upgrade that can attach to that unit … it costs 4 less"
  (Reforge ASH_90): candidates are the window's Upgrades whose `_upgrade_target_spec`
  admits the PRE-CHOSEN host and which are affordable at the reduced price; the finish
  pays, emits CardPlayed and `_attach_upgrade`s, so the upgrade's own When Played fires
  like a hand play's.  Host gone mid-decision ⇒ the revealed upgrade is discarded.
  ⭐ **`DamagePrevention.consume_shield_on_source`** — a WHOLE-instance prevention (the
  `first_each_phase` shape, not an `amount` reduction) whose price is a Shield token on
  the AURA's source: "If damage would be dealt to another friendly unit, you may defeat
  a Shield token on this unit.  If you do, prevent that damage" (The Mandalorian ASH_62).
  Consumed at the single unit-damage chokepoint by `_consume_shield_aura_prevention`,
  gated on a cached registry key set.  DOCUMENTED DEVIATION: the "you may" is automatic —
  the engine's own Shield prevents without asking, and a decision pushed mid-damage is
  replacement-effect machinery.
  ⭐ **`push_granted_attack(excess_damage_to_unit=True)`** — Overwhelm's own excess
  computation aimed at a UNIT: a `this_attack` marker on the chosen attacker, read at the
  tail of the single-defender pipeline (`_push_excess_damage_to_unit`, before the
  this-attack sweep drops it) and delivered by `push_select_damage(max_targets=1)` — the
  whole amount on one unit IS "another unit", and the always-offered finish carries the
  "you may" (Wipe Them Out ASH_137).  ⚠️ The attack's ARENA must be snapshotted BEFORE
  combat: excess only exists when the damage was lethal, so by then the defender's `zone`
  is DISCARD.
  Smaller, all additive: **`DealDamageEqualTo count="source_controller_units"`** (the
  arena-blind sibling of `source_controller_units_in_target_arena` — Turning the Tide
  ASH_138); and four predicates — **`same_arena_as_played_card`** (reads the
  `played_card_id` the CardPlayed fire already threads, so "a unit in the same arena" as
  the just-played unit needs no leading stamp and prompts ONCE — Ravager ASH_102),
  **`on_friendly_host`** ("an upgrade on a FRIENDLY unit"; the plain
  `controller="friendly"` filter reads the UPGRADE's owner, a different question —
  Reforge ASH_90, Pegasus Tri-Wing ASH_171), **`cost_eq_a_hand_unit`** ("deal 3 to a unit
  with the same cost as a unit you reveal from hand" collapses to ONE prompt: pick the
  victim, the reveal follows — Queen Soruna ASH_132) and **`cost_gt_event_threshold`**
  (the `cost_le_event_threshold` mirror, over the Force Throw SOR_167 record-then-gate
  discard — Reckless Sacrifice ASH_163).
  ⭐ PURE REUSE worth knowing: "Either deal 2 to an undamaged ground unit or 5 to a
  damaged one" is `push_choose_modal(pick=1)` over two `EventAbility` options with the
  dead mode filtered out at push time (The Cyborg Mech ASH_147); ASH_85 Grav Charge's
  "defeat this upgrade" re-finds itself on the host by REGISTRY KEY (the trigger decision
  addresses a spec by (set, number), not by instance — two copies fire twice and each
  kills an identical one); "Deal 5 to your base.  Then 5 and 5 to the same unit" is ONE
  targeted CustomEffect with TWO separate damage instances, so a Shield eats only the
  first (Boba Fett's Rancor ASH_179, the Heavy Blaster Cannon LOF_171 lesson).
  ⚠️⚠️ **`state.find_instance` REACHES THE DISCARD**, so "if that unit is defeated this
  way" must be an ARENA test (`zone not in (GROUND_ARENA, SPACE_ARENA)`) — a plain
  `find_instance(...) is None` silently never sees the kill (Justifier ASH_146, Imposing
  Scout Walker ASH_176).  🧪 The `_find_instance` TEST helper is the opposite (arenas
  only), and a 6-damage hit on a 3/7 stand-in does NOT kill it.
- **ash-set:01 residuals + ash-set:02 (29 cards — ASH opens at 82/264)** — all additive;
  **no new decision kind**, no escape hatch, no escalation.  The first `src/swu/cards/ash/`
  module.
  ⭐ **The ADVANTAGE token (ASH_2) — the ASH set mechanic, and the cheapest new token
  yet.**  It is an ordinary +1/+0 `TokenUpgrade` row in the DB, so `attach_token` /
  `GiveToken` (both token-name agnostic), the upgrade stat path, conservation exclusion
  and the leave-play strip all work UNCHANGED.  Its one bespoke rule — "When attached
  unit's attack **or defense** ends: Defeat this upgrade" — is enforced in the combat
  pipelines (`tokens.defeat_advantage_tokens` via `actions._defeat_advantage_tokens_
  after_combat`, called for the attacker and every unit defender at the tail of all
  three), NOT as a registered ability: the same place Shield's damage-prevention rule
  already lives.  Called after damage and defeat processing, so the +1 still counts for
  the attack it was spent on.  ~38 ASH cards create these, so this unblocks the set.
  ⭐ **`WhenAttackEnds(require_defender_defeated=True)`** (Thrawn ASH_33, Halo ASH_223) —
  both unit-combat pipelines now carry `attack_ended_defender_defeated` on the
  `attack_ended_survivor` fire.  ⚠️ That key is ALSO the `WhenFriendlyUnitAttackEnds`
  observer's, but that family additionally requires `attack_ended_attacker`, which this
  fire never sets — so one key serves two trigger families with no double fire.  The same
  fire gained **`attack_ended_combat_damaged`** (the list of units this attacker actually
  dealt combat damage to), which is how "defeat those units" finds them (The Great
  Mothers ASH_101).
  ⭐ **`KeywordRevoke`** — the standing AURA form of the duration-scoped `RevokeKeyword`
  effect: every unit matching a `ConstantAbility`'s target LOSES the keyword while the
  source is in play ("Enemy units lose Ambush and Support" — Domesticated Loth-Cat
  ASH_68).  Read in `keywords.has_keyword` / `keyword_value` immediately after the
  `keyword_revoke` MODIFIER check, i.e. ahead of every grant source, so "can't gain it"
  and "covers units played later" both fall out free, and it lifts on leave-play.  ⚡ The
  board scan is gated on a cached registry index (`keywords._keyword_revoke_aura_keys`) —
  the `_suppress_leader_keys` trick, mandatory on this path.
  ⭐ **`CannotBeAttacked(condition)`** — the BOARD-gated sibling of
  `CannotBeAttackedWhileExhausted` (whose gate is a property of the unit itself), read at
  the same `_cannot_be_attacked` seam and likewise yielding to Sentinel: "can't be
  attacked while you control 2 or more exhausted units" (Tatooine Repulsor Train ASH_35).
  Smaller, all additive: **`ConstantAbility.while_attacking_damaged_unit`** (the exact
  `while_attacking_bounty_unit` sibling — Marrok's Fiend Fighter ASH_241); the conditions
  **`SOURCE_REMAINING_HP_MIN`** (Doctor Pershing ASH_72), **`CONTROLLER_N_PLUS_EXHAUSTED_
  UNITS`** (the controller-scoped `N_PLUS_EXHAUSTED_UNITS_IN_PLAY`), **`CONTROLLER_HAS_
  UPGRADE`** (the payability gate for a "defeat a friendly upgrade" cost — Vane ASH_12)
  and **`CONTROLLER_DISCARD_TRAIT_UNIT_HAS_KEYWORD(param=(trait, keyword))`** (Moff Gideon
  ASH_8's eight parallel conditional SELF `KeywordGrant`s, which are also what makes
  sanitiser rule 2 strip his entirely-mistagged eight-keyword printed bar); and the
  predicates **`power_lt_source`** / **`power_lt_a_friendly_unit`** (Ahsoka ASH_9's two
  readings of "less power") and **`remaining_hp_ge_<N>`** (the ceiling mirror of
  `remaining_hp_le_<N>` — Cad Bane ASH_11).
  ⭐ PURE REUSE worth knowing: **"deal UP TO 6 damage to your base" is a
  `push_choose_modal(pick=1)` over 2/4/6** (Enoch ASH_27) — the discount steps every
  SECOND point, so an odd amount is strictly dominated (same discount, one more damage on
  your own base) and the trigger's own "you may" already covers 0; a genuine optimal-play
  collapse, and the option specs are `EventAbility` because Enoch is a UNIT card (the
  Lightmaker SEC_207 rule).  ⚠️ `push_distribute_damage` could NOT do it — its pool covers
  units only (`_distribution_units`); only the HEAL flavour knows about bases.
  ASH_46 Scion Shuttle's "while this unit is attacking, the defending unit gets **−1/−1**"
  is an OnAttack `this_attack` `ModifyStats` on `fixed=DEFENDER`, not a `while_attacking`
  ConstantAbility: that flag is read only by `compute_power`, so `compute_hp` (no combat
  context) would silently drop the −1 HP half.  ASH_202 Carson Teva's plain "while
  attacking, deals damage first" is `ConditionalFirstStrike` over *any* enemy unit — a
  `KeywordGrant("First Strike")` would also fire while he DEFENDS.  ASH_32 Rancor Keeper's
  "any number of bases" is two optional targeted steps over the accumulating
  `excludes_event_targets` set (SOR_106), with the Toro SHD_239 `{iid}:trig` once-per-round
  marker charged inside the FIRST step so declining is not a use.  ASH_12/ASH_38 are the
  LAW_41 shared-`event_ctx` chain (`prior_target_id` + `requires_prior_target`), ASH_12's
  payoff narrowed by the existing `defender_or_base` predicate (Sabine SOR_142).
  🧪 TEST NOTES: `_place`d instances are STALE after `apply` (deepcopy) — re-find by
  instance_id; a unit that attacked is exhausted, so a second `AttackWithUnit` in one test
  needs it readied first; and ASH tokens occupy ASH_1/2/3 only, so ASH_4/8/9/11/12/14 are
  collision-free leader numbers.
- **ash-set:01 — the SUPPORT keyword (the last unimplemented engine keyword)** — no new
  decision kind, no escape hatch, no escalation.  "When you play this unit / deploy this
  leader, you may attack with **another** unit.  It gains this unit's **other abilities**
  for this attack."
  ⭐ The attack half is pure reuse: two bus listeners in `keyword_triggers.py`
  (`UnitEntersPlay`, the Ambush convention — that keyword's reminder also says "when you
  PLAY this unit" and the engine has always read it as entering play — plus
  `LeaderDeployed` for the three ASH leaders) push the existing `granted_attack`
  decision at `optional=True` + `exclude_source=True`.  It is pushed ONLY when some other
  unit could really attack, probed with `_filter_granted_attacks` — the very function
  `legal_actions` uses to enumerate the options, so the gate and the offer can never
  disagree.  Support is registered BEFORE Ambush on the bus so a unit with both resolves
  its own Ambush attack first (LIFO).
  ⭐ **The BORROW = one modifier + one read layer.**  `push_granted_attack
  (borrow_abilities=True)` makes `AttackWithUnit` land a single `borrowed_abilities`
  this-attack modifier on the CHOSEN attacker naming the Support card as lender, and
  **`state.borrowed_ability_sources(state, ci)`** is the single place that reads it —
  beside `ability_suppressed`, because both the keyword layer and the trigger resolver
  consult it and neither module may import the other.  Two consumers:
  (1) `keywords.has_keyword` / `keyword_value` fold the lender in at the END of the
  guarded **keyword-copy** block (The Ghost JTL_53) — a borrowed keyword reads exactly
  like a copied one, numeric values included, and `_KEYWORD_COPY_RESOLVING` already
  guards the recursion; **Support itself is excluded** ("this unit's OTHER abilities"),
  which also stops a borrowed attack chaining into another Support prompt.
  (2) `resolver._collect_triggers` collects the lender's `TriggerAbility` specs with
  ``source_ci`` = the BORROWER and ``spec_ci`` = the LENDER — exactly the
  GrantedAbility source/spec split, one card further away, so the lender's "On Attack" /
  "When Attack Ends" resolves FROM the attacker with no change to the trigger machinery.
  A leader lender lends whichever side it is currently showing (`deployed_only` /
  `undeployed_only` read off the LENDER), and a lender whose abilities are suppressed
  lends nothing.  Everything lapses with the ordinary `this_attack` sweep — no stored
  flag, no new decision kind, so no web/bot registration.
  ⚠️ **DOCUMENTED NARROWING: constant and activated abilities are NOT borrowed.**  Both
  are read by scans keyed on the card sitting in an arena (`compute_power`'s constant
  passes, the `legal_actions` ability enumeration); only the keyword and trigger layers
  have a per-instance seam a duration can ride.  So Scion Shuttle ASH_46's "while this
  unit is attacking, the defending unit gets −1/−1" travels with the printed card, not
  with a borrower.
  ⚡ **KEYWORD-SANITISER RULE 10 (`_is_lose_only`, Units)** — a keyword every occurrence
  of which is governed by a "**lose(s)** K" clause aimed at OTHER units is stripped: the
  revoke-side mirror of rule 1, which knows only the verb "gain(s)" and therefore read a
  revoked keyword as a bare mention.  Without it Domesticated Loth-Cat ASH_68 ("Enemy
  units lose Ambush and Support") would have BOTH keywords and fire both on entry.  Two
  guards keep it exact — a keyword a card really has is printed as its own leading bar
  line (no governing verb ⇒ kept, Marrok ASH_30 "Sentinel … he loses Sentinel and gains
  Saboteur"), and within a clause the NEAREST verb wins, so "loses X and **gains** Y"
  leaves Y to rules 1–9.  Three real mistags fixed DB-wide: ASH_68 (Ambush + Support),
  Poe Dameron ASH_40 (Sentinel), Tusken Tracker LOF_209 (Hidden).
  📋 Bookkeeping: `"Support"` moved PHASE3→PHASE2 in `audit_coverage.py` (**`PHASE3_KEYWORDS`
  is now EMPTY** — every printed keyword is modelled) and in `web/swudb_import.py`; the
  ASH planner therefore emits no keyword group at all, and `ash-set:01` becomes a
  KEYWORD-RESIDUAL group of the 22 Support cards that also carry ability text.
  🧪 TEST NOTES (`tests/test_support.py`, the `test_hidden.py` synthetic-card shape):
  drive the keyword by granting it with a `keyword_grant` modifier and firing the bus
  event by hand (`get_bus().fire`) — that is exactly what `_put_unit_in_play` does; a
  clean lender for the borrowed-trigger test is Swoop Bike Marauder LAW_107 ("On Attack:
  Draw a card"), whose EXACTLY-ONE draw proves both that the borrow works and that the
  lender does not double-fire.
- **law-set:19–24 batch (6 groups, 38 cards — 🏁 COMPLETES LAW, 264/264)** — all
  additive; **no new decision kind**, no escape hatch, no escalation.  LAW's Credit
  block, so most of it is reuse of the jabba-the-hutt:07 Credit economy.
  ⭐ **`PrintedStatsOverride` grew an AURA form** (`aura_controller="friendly"` +
  `condition`) — "While you control 7 or more units, **their** printed power is
  considered to be 7 and printed HP is considered to be 7" (Obi-Wan Kenobi LAW_36),
  the board-wide sibling of Size Matters Not LOF_56's upgrade marker.  Deliberately
  NOT a TargetSpec: this is read at the SEED of `compute_power`/`compute_hp`, and the
  target matcher re-enters those very functions — a plain `CONTROLLER_N_PLUS_UNITS`
  count cannot recurse.  Same seam gained a **`printed_stats` MODIFIER** arm, the
  duration-carrying flavour ("Its printed HP is considered to be 1 **for this
  phase**", Adventurer Sniper Rifle LAW_126, from a `GrantedAbility(ActivatedAbility)`).
  `_printed_stats_override(state, ci)` now returns a `{"power"?, "hp"?}` dict and folds
  all three sources in the order they become active — aura, then upgrade, then modifier
  — which IS the card's printed "the most recent … determines the printed values" rule.
  ⭐ **`_usable_credits(s, ps)` — the one place that knows whether a Credit can pay.**
  "Enemy Credit tokens lose all abilities" (Conveyex Security Captain LAW_117) works
  because a Credit's ONLY printed ability is its spend clause; the new
  `EnemyCreditsLoseAbilities` marker is read through this helper, consulted by BOTH
  `_affordable_with_credits` (which gained an optional trailing `s`, threaded at all
  19 call sites) and `_pay_play_cost`, so the offer and the payment can never disagree
  — an over-generous gate would raise `IllegalActionError` mid-`apply`.
  ⭐ **`DefeatCreditCost`** — the sixth activated-ability cost spec ("Action [defeat a
  friendly Credit token]", Hunter For Hire LAW_156), wired at the payment site plus all
  six `legal_actions` affordability checks; credits are fungible so no choice is made,
  and the payer is the ACTIVE player, which for an `any_player` ability (Mercenary
  Gunship SHD_256) is whoever is buying the unit.
  ⭐ **`push_play_from_hand(resources_of=<player>, then_owner_resources_deck_top=)`** —
  the decision's source zone swaps from the controller's hand to ANOTHER player's
  RESOURCE row ("Look at all of an opponent's resources.  You may play 1 of those cards
  for free.  If you do, that opponent resources the top card of their deck" — Tear This
  Ship Apart LAW_66).  ⚠️ Needs NO hidden-info exemption: `_check_hidden_info` guards
  only `opp.hand + opp.deck`, and a face-down resource is not in either.
  ⭐ **`push_select_token(then_use_when_played=True)`** + `resolver._when_played_ability_indices`
  + the `has_when_played_ability` predicate — "Use any number of 'When Played' abilities
  on friendly Spectre units" (Fire Across the Galaxy LAW_256).  The WhenPlayed sibling of
  Chimaera JTL_39's `_when_defeated_ability_indices`, driven by the select-up-to-N loop in
  its "any number" form (Kazuda JTL_18); the re-uses are pushed as fresh `resolve_effects`
  decisions AFTER the pop (the `defeat`/`return_to_hand` rule), so nothing stacks under the
  open decision.  DOCUMENTED SIMPLIFICATION: "any number" is counted in UNITS — a chosen
  unit contributes all of its When Played abilities (the Shadow Caster JTL_169 reading).
  ⭐ **`ConditionalFirstStrike.condition`** — a BOARD gate beside the defender filter,
  "While attacking, **if no other units have attacked this phase**, this unit deals combat
  damage before the defending unit" (Anakin's Podracer LAW_219).  Reading it at the
  attacker's combat step rather than as a conditional `KeywordGrant` is what keeps "while
  ATTACKING" exact — the keyword layer carries no combat context, so a grant would also
  fire while the unit is DEFENDING.
  Smaller, all additive: **`IgnoreAspectPenaltyForPlays.aspects` + `.condition`** (the
  include-filter and a board gate — "**While you control 2 or more units**, ignore the
  aspect penalties on **Heroism** units you play", Hera Syndulla LAW_9, whose two sides
  need no side gate since the waiver scan walks base_zone AND both arenas);
  **`Protection.from_control_change`** read at the single `change_control` seam
  ("Opponents can't take control of this unit" — Rey LAW_149, whose second clause is the
  long-standing `from_defeat`); **`CreateCreditToken(player="each")`** (Rodian Bondsman
  LAW_116, the DrawCards convention's last arm); **`game_memory.forbidden_card_names_this_phase`**
  — the effect-granted, phase-scoped, ANY-player sibling of the `ForbidNamedCardPlay`
  marker, read at the same `_named_card_play_forbidden` seam, behind the new
  `push_name_a_card(then_payoff="forbid_play_this_phase")` arm (Transmission Jamming
  LAW_243); the **`highest_cost_among_enemy_units`** predicate (Dengar LAW_53 — printed
  cost, ties qualify, and because a `WhenUnitDefeated` filter is read AFTER the dying unit
  left its arena, "≥ the highest still standing" is the exact test); and
  **`Condition.CONTROLLER_HAS_UNIT_IN_ARENA(param="ground"|"space")`** (Getaway Freighter
  LAW_155, the single-arena sibling of `CONTROLLER_HAS_GROUND_AND_SPACE_UNIT`).
  ⚡ **FIX: `NameCard.apply` looked its source up with `_find_in_arenas_any`**, so a
  `then_payoff` on an EVENT never ran — an event is already in its owner's discard when
  its own ability resolves.  It now falls back to `find_instance` for the payoff.
  ⭐ PURE REUSE worth knowing: "Action [Exhaust, **defeat a friendly unit**]" has no cost
  spec — model it as a leading TARGETED `DefeatUnit` effect with the payoff behind it plus
  a `CONTROLLER_N_PLUS_UNITS(1)` payability gate (Director Krennic LAW_8, the Tomb of
  Eilram LOF_28 shape), targeted effect FIRST so the player is prompted once (SHD_18);
  **"On Defense" IS `WhenAttacked`** — the card's own rules note says those abilities
  "trigger at the same time as 'On Attack' abilities" (Canto Bight Security LAW_121);
  seven LAW bases (LAW_21/22/24/25/27/28/30) print Daimyo's Palace LAW_20 verbatim, and
  LAW_264 is Agent Kallus LAW_3's adapter verbatim — both keep that decision's standing
  units-only narrowing; LAW_63 L3-37 = `push_search_and_play_multiple` (Darth Vader
  SOR_87) at window 10 / budget 5 with a Droid filter; LAW_169 Payroll Heist = the
  phase-scoped `AuraGrantedAbility` over `game_memory.phase_aura_sources` (Pyrrhic Assault
  TWI_103 / Implicate SEC_231) with an **OnAttack** inner, so the spent event keeps
  granting from the discard; LAW_221 Lieutenant Gorn moves a Credit between the two
  `credits` piles directly (fungible, auto-picked — the SOR_145 convention).
  🧪 TEST NOTES: an upgrade-granted Action is addressed by the **UPGRADE's** instance_id
  (`UseAbility(upgrade.instance_id, idx)`), not the host's; `_target_protected` takes
  `(state, target_ID, source_ci, kind)` — an id, not an instance; `_fire_when_deployed`
  wants a leader already IN AN ARENA with `deployed=True` (`_place_leader` leaves it in
  base_zone); and `_find_instance` searches arenas only, so an undeployed leader needs
  `state.find_instance(...)[1]`.
- **law-set:14–18 batch (5 groups, 33 cards — LAW now 226/264)** — all additive;
  **no new decision kind**, no escape hatch, no escalation.
  ⭐ **The attack-end observer fire is now ONE fire per attack.**  The
  ``WhenFriendlyUnitAttackEnds`` fire added for Boba Fett LAW_7 was guarded on the
  defender dying (and repeated per defeated co-defender).  Anakin Skywalker LAW_88
  ("When a friendly unit's attack ends: …") is the same trigger WITHOUT that
  narrowing, so the two readings would have collided — the plain one matching both
  that fire and, on a multi-defender attack, matching it twice.  All three combat
  pipelines (base, single-defender, multi-defender) now fire it **exactly once**,
  carrying ``attack_ended_attacker`` always and ``attack_ended_defender_defeated``
  only when a defender died; ``require_defender_defeated`` reads the second key.  An
  attack ends once however many co-defenders it killed, so this is also the more
  faithful reading, and the base-attack site joins in because "a friendly unit's
  attack ends" draws no unit/base distinction.  The fire's ``after_all_player_idx``
  moved to the OPPONENT, matching the neighbouring WhenAttackEnds fire (with the
  attacker there, a decision would have handed the attacker a second action).
  ⭐ **`ConstantAbility(via_host=True)` reaches the STAT layer** — Figure of Unity
  SEC_104 built the flag for keywords only; Fulcrum LAW_150 is the first
  upgrade-borne aura carrying a `StatBonus` ("Attached unit gains … 'Each other
  friendly Rebel unit gets +2/+2'").  New **`actions._via_host_stat_bonus`**, a
  SEPARATE pass (the shape of the `while_defending`-upgrade pass beside it, rather
  than re-indenting the two hot main loops), with both main scans now skipping a
  `via_host` spec.  The HOST is the source throughout, so "friendly" / `not_self` /
  the condition read off the unit in the arena; a suppressed host confers nothing.
  ⚠️ TEST TRAP: Fulcrum ALSO prints a +2/+2 upgrade box, so its host gains +2/+2
  from the printed stats — assert the aura's absence on the host as "+2, not +4".
  ⭐ **`enemy_of_source_controller` predicate** — "Enemy units gain Raid 1 and
  Saboteur" measured against whoever CONTROLS the source right now (Galen Erso
  LAW_233).  The ordinary ``controller="enemy"`` filter compares ``owner_id``,
  which never moves, so an aura on a card whose control can change reads the wrong
  side — and Galen's own When Played ("You may have an opponent take control of
  this unit") is exactly that case: handing him over is *meant* to flip which units
  get the gift.  The predicate resolves both cards through ``find_instance`` and
  compares HOLDERS.  Reach for it on any aura printed on a card that can change
  hands.
  ⭐ **`Condition.NO_OTHER_UNIT_ATTACKED_THIS_PHASE`** — "If no other units have
  attacked this phase (including enemy units)", whose printed rules note glosses it
  "no player has made an attack with a unit this phase" (Anakin LAW_88, Boonta Eve
  Flagbearer LAW_112).  Both combat pipelines stamp the attacker into
  ``units_attacked_this_round`` at the DECLARE step — before the OnAttack fire and
  long before the attack-ends one — so the test is simply "the ledger holds ≤1".
  Round-scoped ledger ≡ this-phase (one ACTION phase per round).
  Smaller additive seams: **`CardInstance.bottom_at_regroup`** + a sweep in
  `_enter_regroup` + `push_search_and_play(bottom_at_regroup=)` — the DECK-bound
  sibling of Triple Dark Raid SHD_194's `return_at_regroup`, and a RELOCATION not a
  defeat, which is what Maz Kanata LAW_74's rules note demands ("does not trigger
  any 'When Defeated' abilities");
  **`push_pay_resources_for_tokens(cost_source="return_resource", payoff="credit")`**
  — the pay-any-number loop where each step RETURNS a resource to its owner's hand
  and mints a Credit (Intimidator LAW_140); readiness is not required and the
  fungible auto-pick (`actions._return_one_resource_to_owner`) prefers the exhausted
  ones, since a returned resource is a card in hand either way while a ready one
  left behind still pays this phase.  A real choice, so no optimal-play collapse.
  **`CostReduction.per_friendly_damaged_unit`** (Phoenix Squadron Fighters LAW_110 —
  the AT-DP Occupier JTL_163 basis with the arena filter swapped for a controller
  one) and **`CostReduction.host_unique`** (Mastery LAW_129 — `host_named`'s sibling
  keyed on a PROPERTY of the chosen host; no host chosen yet ⇒ no reduction, so a
  pre-pick affordability check is never over-generous).
  **`Condition.CONTROLLER_HAS_NON_UNIQUE_UNIT`** (Rose Tico LAW_223, the `non_unique`
  predicate as a board gate on the LAW_210 `EntersPlayReady` marker).
  ⭐ PURE REUSE worth knowing: **"You may pay 1 resource.  If you do, <payoff>" is
  now a four-card idiom** — an `optional` trigger gated by
  `CONTROLLER_N_PLUS_READY_RESOURCES(1)` over ONE CustomEffect that pays and pays
  off together (Boba Fett LAW_214), used by LAW_113 / LAW_148 / LAW_193 / LAW_227 /
  LAW_257 with a Shield, a self-buff, an opponent discard and an Experience token.
  Patient Hunter LAW_73's "can't ready during this regroup phase" is the standing
  `cannot_ready_this_round` flag (No Good to Me Dead SOR_186) — its trigger fires at
  the START of regroup, i.e. before that phase's ready step, so the two scopes name
  the same skipped ready (DOCUMENTED DEVIATION only under Max Rebo LAW_72's extra
  regroup).  Stockpile LAW_171 ("Resource this event and the top card of your deck")
  needs no new zone plumbing: an EVENT is placed in its owner's DISCARD *before* its
  ability resolves, so it resources itself straight out of that pile — and both
  cards enter EXHAUSTED (its rules note; that is why it does NOT reuse
  `_resource_top_of_deck`, which enters a READY one).  Ben Solo LAW_185 = ready +
  the `cannot_be_attacked` modifier (On Top of Things TWI_219) in ONE targeted
  effect, under BOTH printed triggers (Captain Rex SEC_48); Phantom LAW_144 =
  `push_play_from_hand(aspect=, then_select_token={"restrict_played": True})` with
  the "you may" carried by the optional trigger, since that decision has no decline,
  and an `available_fn` (Shadow Caster JTL_169) so it is never a dead prompt;
  LAW_157 = `push_granted_attack(bonus_trait="Bounty Hunter")`; LAW_186 =
  `GrantedAbility(OnAttack)`; LAW_202 decides its ±2 AT RESOLUTION (an EventAbility
  has no `condition` — the Adelphi SHD_101 convention) over the MIRROR atom
  `OPPONENT_MORE_RESOURCES_THAN_CONTROLLER`, so a level count grants nothing, which
  is exactly "fewer".
  ⚠️ Implementing LAW_74 and LAW_87 freed the **LAWP_6** and **LAWP_9** mirrors —
  re-run `scripts/find_reprints.py --check` after every batch; three
  `tests/test_reprints.py` slots fail until the aliases land.
  🧪 TEST NOTES: `_play_event_from_hand` GIVES the controller resources to pay the
  cost, so never assert on the whole resource row after using it; a resolution-time
  magnitude must have its board set up BEFORE the event is played; and
  `CardResourced` requires `card_name`.
- **law-set:12–13 batch (2 groups, 14 cards — LAW now 193/264)** — all additive;
  **no new decision kind**, no escape hatch, no escalation.  Group 12 was the set's
  LEADER block and had been scouted for sessions as the heaviest group left.
  ⭐ **The ability-redo chokepoint gains its THIRD arm: `OnAttackRedo`** — "When you
  use an 'On Attack' ability: You may [pay 2 resources and exhaust this leader.  If
  you do,] use that ability again" (Enfys Nest LAW_14).  The exact sibling of
  `WhenDefeatedRedo` (Thrawn JTL_2) at the same `resolver._schedule_ability_redo`
  seam, so the whole card is TWO PASSIVE MARKERS and no trigger of its own — the
  chokepoint offers the re-use as an ordinary `trigger_option` inserted just below
  the original's resolution, which is why "use that ability again" still needs no
  new decision kind.  `_find_when_defeated_redo` generalised into
  **`_find_ability_redo(state, controller_id, marker_cls)`**, which also gained the
  one field the When Defeated marker never needed: **`cost_resources`**, checked
  against ready resources when deciding whether to OFFER and charged beside the
  exhaust in `actions.AcceptTrigger` (`redo_cost_resources`).  Both markers share
  `game_memory.when_defeated_redo_used_this_round`, which is keyed by the marker's
  own instance id so they cannot collide.  ⚠️ Unlike the When Defeated arm there is
  no Bounty carve-out to make — a Bounty is a When Defeated ability by construction.
  ⭐ **`WhenFriendlyUnitAttackEnds(traits=, require_defender_defeated=)`** observer —
  "When a friendly Bounty Hunter unit's attack ends: If the defending unit was
  defeated, …" (Boba Fett LAW_7).  It needs its OWN fire in the combat pipelines
  (new keys `attack_ended_attacker` / `attack_ended_defender_defeated`) because the
  card's printed rules note says the attacker "doesn't need to survive the attack",
  and both neighbours disagree: `WhenAttackEnds` keys on `attack_ended_survivor`,
  which is set only for an attacker still in play, and `OnAttackDefeatsUnit` /
  `WhenFriendlyUnitAttacksAndDefeatsUnit` fire from a site guarded on
  `not attacker_dead`.  The attacker is resolved with `find_instance` (which reaches
  the discard) so a DEAD attacker's controller and traits are still readable.
  ⭐ **`game_memory.tokens_created_this_phase`** (player ids, phase-cleared) behind
  BOTH `Condition.CONTROLLER_CREATED_TOKEN_THIS_PHASE` and the same-named target
  PREDICATE — "If you created a token this phase, exhaust an enemy unit" (The Client
  LAW_16).  Fed at the THREE creation chokepoints (`tokens.attach_token`,
  `tokens.create_credit_token`, `actions._create_token_units`), so every kind of
  token records one entry.  ⚠️ LAW_16 uses the PREDICATE, not the condition: his
  printed rules note says the Action may still be used when the clause is unmet ("but
  you don't exhaust a unit"), which is exactly what an empty candidate set gives —
  a `ConditionalEffect` could not express it, since it cannot carry a targeted
  sub-effect.  (DOCUMENTED SIMPLIFICATION: `attach_token` records the HOST's
  controller, which differs from the creator only for a token given to an enemy.)
  Four smaller additive seams: **`CreateCreditToken(player="opponent")`** (the
  DrawCards / CreateTokenUnit convention — "An opponent creates a Credit token", Vel
  Sartha LAW_6); **`push_cull_for_damage(then_modal=[…])`**, which REPLACES that
  decision's damage so the cull is a pure COST and the payoff is a `push_modal`
  pushed after the pop ("Epic Action [defeat a friendly token]: …", Alliance Outpost
  LAW_19) — with two new modes, `give_shield_unit` (the Shield sibling of
  `give_experience_unit`) and the fungible `create_credit_token`;
  **`Condition.CONTROLLER_HAS_TOKEN`**, the card-type-blind widening of
  `CONTROLLER_HAS_TOKEN_UNIT` matching exactly `_cull_pool(pool="tokens")`, so a
  once-per-GAME Epic Action is never burnt on an unpayable cost; and
  **`push_select_token(extra_token_type=)`** — a SECOND token of a DIFFERENT kind on
  each chosen unit, which `token_count` (which repeats one kind) cannot say ("give an
  Experience token AND a Shield token to a unit", The Ghost LAW_69).
  ⚠️⚠️ **LAW_3 IS ALSO A SHIELD TOKEN UPGRADE's (set, number)** — the token-collision
  hazard again (LAW_2 was the Experience token).  Agent Kallus is registered only
  from `ActivatedAbility` (enumerated from ARENA UNITS; an attached upgrade needs a
  `GrantedAbility` wrapper) and a plain side-gated `TriggerAbility` (collected only
  from cards in play, never from a host's `attached_upgrades`); a `ConstantAbility`,
  a `GrantedAbility` or a passive marker would NOT be safe.  A regression test pins
  the spec KINDS rather than instantiating the twin, because `attach_token` builds
  every Shield from one canonical def.
  ⚠️ **The Mandalorian SHD_18 wart, restated with teeth**: a leading effect —
  even a no-target `CustomEffect` or a `fixed=SELF` `GiveToken` — still consumes a
  ChooseTarget of its own at the current `effect_idx`, so "[token this unit], then
  she deals damage equal to her power to an enemy unit" (Latts Razzi LAW_39) prompts
  TWICE and the halves can name different units.  Both halves therefore live in ONE
  targeted `CustomEffect`; DOCUMENTED DEVIATION — with no enemy ground unit the
  branch fizzles and the token is not given.  Its "a Shield token or an Experience
  token" is `push_choose_modal(pick=1)` over two `EventAbility` options (the
  Lightmaker SEC_207 shape — this is a UNIT card, so the options must be
  EventAbility, never trigger-collected).
  PURE REUSE worth knowing: LAW_46 Chirrut Îmwe = Maul LAW_54's
  `WhenAttackEnds(require_base_damage=True)` verbatim (his own "does not need to
  survive" note is moot — a base attack never damages the attacker), with `damaged`
  on the heal target so the "you may" is never a dead prompt; LAW_3's undeployed and
  deployed Actions are the SAME `push_play_from_hand(ignore_aspect_penalty=True)`
  adapter differing only by the exhaust cost, with the standing units-only narrowing
  (Daimyo's Palace LAW_20); LAW_6 deployed and LAW_55 Chopper are the "If you do"
  binding and the Zeb LAW_45 conditional-magnitude read respectively; LAW_31 Bossk is
  TWO single-effect `OnAttack` abilities because only separate abilities can carry
  different `optional` flags (the mandatory +1/+1 and the "you may" −1/−1);
  LAW_59 Highsinger's When Defeated needs no LAW_159 corpse-timing care — its effect
  is TARGETED, so it already resolves on a later `apply`; LAW_43 Shadow Cloaking is
  the Kylo SHD_141 one-`CustomEffect` rule (ready AND shield the SAME unit).
  🧪 TEST NOTES: the `choose_two_modal` action is `SelectModalOption(option_idx=…)`;
  `select_token`'s remaining-picks context key is **`remaining`**, not `max_targets`;
  an OPTIONAL trigger's prompt is pushed ON TOP of a mandatory sibling's, so a card
  with one of each is resolved in the reverse of the printed order — route each
  `ChooseTarget` by the top decision's `ability_idx` rather than assuming an order;
  and `_get_card` returns whatever row matches, so a low number that a TOKEN shares
  needs a by-type fetch (there are helpers for both Leader and Unit now).
  ⚠️ Implementing LAW_55 freed the **LAWP_4** mirror — re-run
  `scripts/find_reprints.py --check` after every batch; three `tests/test_reprints.py`
  slots fail until the alias lands.
- **law-set:09–11 batch (3 groups, 17 cards — LAW now 179/264)** — all additive; **no
  new decision kind**, no escape hatch, no escalation.  The set's self-mill / Credit
  block, so most of it is reuse of the `actions.discard_from_deck` primitive that
  landed in law-set:07.
  ⭐ **`WhenYouDiscardFromDeck` observer** — "When you discard a card from your deck"
  (Sebulba's Podracer LAW_176), the DECK-only narrowing of `WhenThisIsDiscarded` and
  the easier half of that pair: the observer is an ordinary card IN PLAY, so the
  standard `_collect_triggers` scan finds it and no discard-pile scan is needed.  Its
  ledger `game_memory.deck_discards` is keyed by the **milling PLAYER**, not by the
  milled card (the card milled has nothing to do with the observer), fed by a new
  `note_hand_or_deck_discard(..., from_deck=True)` kwarg passed at the six DECK sites
  only (`discard_from_deck`, both deck_search discard dispositions, the
  reveal-cull discard, Zuckuss LOF_204's mill) and drained by
  `actions._fire_deck_discard_observers` at the action settle-point.  "When YOU" is
  enforced in the matcher, so an opponent's self-mill does not fire it, and the
  shared `SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE` limiter (Toro SHD_239) is the
  "only once each round", charged on ACCEPT.  ⚠️ A hand discard still feeds only the
  hand ledgers — the two are deliberately separate.
  ⚡ **BUG FIXED in the regroup sweep**: `_enter_regroup`'s attached-upgrade
  `defeat_at_regroup` block was written for Jetpack SHD_225's Shield TOKEN, so it
  simply DROPPED the flagged upgrade from `attached_upgrades` — correct for a token
  (which ceases to exist) but it would have deleted a real card from the game.  It
  now routes a non-token upgrade to its OWNER's discard pile.  Nothing had exercised
  it until **`push_play_upgrade_from_hand(then_defeat_at_regroup=)`**, the new rider
  that stamps the flag on a played upgrade (Salvaged Materials LAW_245).
  Three smaller additive seams: **`push_name_and_discard(aspects_any=)`** — only a
  hand card sharing at least one of the listed aspects may be NAMED, the aspect
  sibling of `card_type`, with an empty eligible set fizzling unprompted ("discard a
  card from it that shares an aspect with that unit" — Hold For Questioning LAW_217,
  which passes the exhausted unit's own aspects);
  **`push_bottom_from_discard(then_create_credit=)`** — the Credit sibling of that
  decision's `then_draw` / `then_create_token` payoffs, likewise settled at the
  finish so bottoming nothing creates nothing (Scavenging Sandcrawler LAW_238); and
  **`StandingPlayDiscount(applies_to="card_trait:<Trait>")`** — the CARD-TYPE-BLIND
  sibling of the `trait:` arm, which gates on Unit: Gambit is printed on Events and
  Upgrades and on no Unit at all, so the existing arm would have made "The first
  Gambit card you play each round costs 1 less" dead text (The Master Codebreaker
  LAW_229; `once_per_round=True` is the default and IS "the first … each round").
  ⚠️⚠️ **A "When Defeated" payoff that needs the corpse IN THE DISCARD must be an
  `optional` trigger** — `_defeat_unit` fires its triggers with the unit pulled from
  its arena and NOT YET placed in the discard, so a mandatory no-target effect
  inlines into that gap and sees the card nowhere.  An `optional` trigger resolves
  from its own `trigger_option` decision, i.e. on a later `apply`, by which time the
  card has landed (Expendable Mercenary LAW_159, "You may resource this unit from its
  owner's discard pile" = an optional trigger over `push_resource_from_discard(
  up_to=False)` narrowed to the source's own instance id).  L3-37 JTL_49 gets the
  same delay for free because its effect is TARGETED.
  PURE REUSE worth knowing: LAW_237 Qui-Gon Jinn is the EXACT INVERSE of Shipbreaking
  Yard LAW_26's `push_deck_search` combination (`disposition="discard"` +
  `rest_disposition="top"` for "look at 3, you may discard 1", vs LAW_26's
  `"top"`/`"discard"`) — DOCUMENTED DEVIATION: the un-taken cards keep their order,
  since "in any order" is a freedom the decision does not model; LAW_242 Improvise =
  Ezra Bridger SOR_192's `push_peek_top(mode="may_play_discard", cost_reduction=1)`
  verbatim, that mode's three branches being exactly "play it / discard it / leave
  it"; LAW_245 = `push_play_upgrade_from_hand` at Kylo Ren LOF_1's
  `from_discard_only=True` plus Cin Drallig LOF_150's `trait` filter, paid; LAW_200
  Salvaged Blaster = Kylo's TIE Silencer SHD_135's `PlayFromDiscardAction` +
  `SELF_DISCARDED_THIS_PHASE`, and the enumerator's Upgrade branch (once per legal
  "Attach to …" host) plus `_upgrade_target_spec` cover both its clauses for free;
  LAW_224 Liberty and LAW_236 Bix Caleen are one `CustomEffect` under BOTH
  `WhenPlayed` and `OnAttack` (the Captain Rex SEC_48 shape), each binding a cost or
  a read to its payoff in ONE effect; LAW_194 Doctor Aphra's "discarded this way"
  pins the return by INSTANCE id (`push_return_from_discard(eligible_instance=)`), so
  a matching card already in the pile is not offered.
  🧪 TEST NOTES: an accepted OPTIONAL trigger resolves through a further
  `resolve_effects` decision — drive to quiescence after `AcceptTrigger` or the
  effect has not run yet; `_defeat_unit(state, owner_ps, ci)` returns **None** (it
  mutates in place); `_place_leader(state, owner, def)` takes no `deployed` kwarg
  (place into an arena and set `.deployed`); `PlayFromDiscard`'s host field is
  `upgrade_target_id`; a `deck_search` with NO eligible card still PUSHES (with an
  empty `candidate_ids` and a `FinishSearch`) rather than fizzling.
- **law-set:07–08 batch (2 groups, 14 cards — LAW now 162/264)** — all additive; **no
  new decision kind**, no escape hatch, no escalation.  Group 07 was the set's four
  LEADERS plus two BASES and had been scouted as the heaviest group left; every one
  of its feared primitives dissolved into an existing seam.
  ⭐ **`actions.discard_from_deck(s, ps, count)`** — the shared self-mill primitive
  the set kept asking for, routing each card through `note_hand_or_deck_discard` so
  the `cards_discarded_this_phase` ledger AND the `WhenThisIsDiscarded` drain (That's
  a Rock LAW_206) fire for free, and RETURNING the milled cards so a caller can
  inspect them.  ⚠️ **"discard a card from your deck" as an ability COST needs no cost
  spec** — a mill is always payable, so it rides inside the payoff's own
  `CustomEffect` (the Anakin TWI_12 "deal 2 to your base" half-cost convention;
  Sebulba LAW_12).  The `rest_disposition="discard"` branch of `_finish_deck_search`
  now notes its discards too — it had been the one deck-discard site that did not.
  ⭐ **`Condition.CONTROLLER_TRAIT_UNIT_DEFEATED_THIS_PHASE`** + the
  `game_memory.defeated_traits_this_round` ledger — the TRAIT sibling of Chancellor
  Palpatine TWI_17's aspect one, recorded at the same defeat site over EFFECTIVE
  traits ("If a friendly Rebel unit was defeated this phase", Jyn Erso LAW_5, gating
  BOTH sides so neither the exhaust nor the resource is ever spent on a no-op).
  ⭐ **`push_select_token(then_credit_and_draw=True)`** — a PER-DEFEAT payoff on
  DEFEAT mode, counted from the defeats that actually happened after the pop ("For
  each unit defeated this way, create a Credit token and draw a card", Tobias Beckett
  LAW_2).  ⭐ **`push_each_player_defeats(disposition="return_then_defeat_all")`** —
  each player's pick is RESCUED to its owner's hand, then every non-leader unit still
  standing is defeated (Rhydonium Detonation LAW_96).  The printed "may" is an
  optimal-play collapse: with the wipe landing immediately after, hand always beats
  discard.  With neither player holding an eligible unit nothing is pushed, which is
  also correct — the only units the wipe could reach are exactly the eligible ones.
  Two condition atoms: **`CONTROLLER_HAS_CREDIT`** (the controller-narrowed sibling of
  ANY_PLAYER_HAS_CREDIT / OPPONENT_HAS_CREDIT — Lando LAW_18) and
  **`OPPONENT_MORE_CARDS_IN_HAND_THAN_CONTROLLER`** (the exact MIRROR of SEC_10's
  atom, so a level count satisfies neither — Broken Horn LAW_83).
  ⭐ TWO OPTIMAL-PLAY COLLAPSES worth reusing, both the Foresight TWI_68 shape (a
  choice made before anything is revealed is information-free, so only hit probability
  moves): Lando LAW_18's "choose an aspect, then discard a card from a deck" picks the
  MODAL aspect of the remaining deck (ties broken on the aspect NAME, so it stays
  deterministic), and **"a deck" is read as the CONTROLLER's own deck** — the only one
  whose composition the controller knows, and the reading Watchful LAW_125 takes too.
  PURE REUSE worth knowing: LAW_26 Shipbreaking Yard = `push_deck_search` at a
  combination no card had used — `window=3` + `disposition="top"` (LOF_103) +
  `rest_disposition="discard"` (IBH_9) — so "discard 3, you may return one to the top"
  is ONE decision, and because nothing moves while a deck_search is open the rescued
  card is never discarded at all (so a LAW_206 in that window correctly does not
  fire); LAW_29 = Frontier Trader SHD_214 verbatim (auto-picked resource to its
  OWNER's hand + `_resource_top_of_deck`); LAW_103 Display Piece = the Arquitens
  SHD_122 relocation with the controller-at-death captured BEFORE the defeat (the
  JTL_175 ordering rule); LAW_94 Hondo = `push_peek_top(mode="may_play")` with
  `once_per_round=True`, his "look at the top card at any time" needing no
  registration (pure information, and the decision reveals it anyway); LAW_84
  Krrsantan = `DiscardCardCost(count=2)` + a `fixed=SELF` ReturnToHand, with NO
  exhaust in the printed cost so he can bounce out of a bad attack; LAW_125 Watchful =
  `GrantedAbility(OnAttack)` onto `push_peek_top(mode="may_bottom")`; LAW_48 Chio Fain
  = "choose 2 players" collapses to `DrawCards(player="each")` in a two-player game.
  ⚠️⚠️ **LAW_2 IS ALSO THE EXPERIENCE TOKEN's (set, number)** — Tobias Beckett is
  registered only as `ActivatedAbility(undeployed_only=True)` (the arena scans demand
  a Leader card_def) and `TriggerAbility(WhenDeployed())` (matched by instance id
  against a LeaderDeployed event, which a token never generates); a regression test
  pins it, as for Kylo LOF_1.  🧪 TEST NOTES: `_defeat_unit` takes
  `(state, owner_ps, ci)`; `_play_event_from_hand` is
  `(state, repo, set_code, num, …)` and RETURNS `(state, ci)`; a `deck_search` with
  `count=1` AUTO-FINISHES on the first `SelectSearchCard`.
- **law-set:06 batch (1 group, 7 cards — LAW now 148/264)** — additive; one new
  observer trigger, one new granted-attack rider, one new predicate, no escape hatch.
  ⭐ **`WhenThisIsDiscarded` observer** — "When this event is discarded from your hand
  or deck" (That's a Rock LAW_206), the first trigger whose SOURCE is a card that was
  never in play: it lives in its owner's DISCARD pile, so no in-play scan can see it.
  Built as the `WhenUnitHealed` settle-drain family verbatim — a `GameMemory.self_discards`
  queue fed by the EXISTING `note_hand_or_deck_discard` chokepoint (so a hand discard,
  a self-mill and a deck-search discard all fire it for free), drained by
  `actions._fire_self_discard_observers` at the settle point — plus a dedicated
  collection scan in `_collect_triggers` that finds the one card by id via
  `find_instance` (which reaches the discard) and collects ONLY that trigger kind.
  That scan is the Rey LOF_148 "when you draw this card" hand scan mirrored onto the
  discard pile: **the shape to copy whenever a trigger's source is out of play.**
  ⭐ **`push_granted_attack(defeat_attacker_if_base_damaged=True)`** — "After completing
  this attack, if that unit damaged a base, defeat that unit" (Flash the Vents LAW_205):
  the CONDITIONAL twin of Heroic Sacrifice SOR_150's `then_defeat_attacker`, reading
  Stay on Target JTL_177's before/after base-damage snapshot (so an Overwhelm spill
  counts exactly like a direct base attack) at `then_defeat_attacker`'s own settle
  point.  Either rider now arms that snapshot.  ⭐ **`same_arena_as_event_or_base`
  predicate** — "a base or another unit in the same arena" (Collateral Damage LAW_208):
  the `ground_or_base` SOR_158 widening (a base ALWAYS qualifies, since base_zone fails
  every arena test) applied to `same_arena_as_event`.  PURE REUSE worth knowing:
  LAW_198 = Boba Fett LAW_214's pay-then-damage binding verbatim (payment + damage in
  ONE CustomEffect so "if you do" cannot be split, gated by
  `CONTROLLER_N_PLUS_READY_RESOURCES` so it is never offered unaffordable); LAW_201 =
  `GrantedAbility(WhenDefeated)` + a plain `SOURCE_READY` condition — **"if this unit
  was ready" needs no new machinery, because `_defeat_unit` fires the WhenDefeated
  triggers BEFORE it resets the dying card's `exhausted` flag**, and the
  `event_ctx["defeated_upgrades"]` scan evaluates that condition against the HOST;
  LAW_207 = the Zeb LAW_45 conditional-MAGNITUDE CustomEffect (the aspect count is
  computed inline — no Condition atom, since nothing else asks for it), with the
  printed "you may … instead" auto-taken as a documented formality (5 is never worse
  than 3 on a unit the controller already chose); LAW_213 = the existing `exhausted`
  TargetSpec predicate beside `arena="ground"`.
- **law-set:03–05 batch (3 groups, 21 cards — LAW now 141/264)** — all additive; **no new
  decision kind**, no escape hatch.  ⭐ **`cannot_deal_combat_damage` Modifier** — the
  DEALER-side mirror of `damage_prevention` (which protects a RECEIVER), read by
  `actions._combat_power_after_block` at the five points a combat pipeline turns a unit's
  power into an amount to deal (attacking a unit, attacking a base, striking back as the
  defender, and both halves of the multi-defender split), so "For this phase, that unit
  can't deal combat damage" (Betrayed Trust LAW_130) leaves the unit's POWER honest —
  Overwhelm's excess and every "damage equal to its power" ability still read the real
  number.  ⭐ **"Deal UP TO N damage to <one chosen unit>" without a choose-a-number
  decision** — `push_distribute_damage(restrict_ids=[…])` (the whitelist complement of
  `exclude_ids`, the `push_select_token` LOF_147 field) pins the pool to the unit an
  ordinary targeted `CustomEffect` already chose, which IS a 0-to-N dial; its
  `then_heal_base_if_survives` rider heals the controller's base for the damage dealt,
  settled after the pop and forfeited when the damage defeated the target (Choke on
  Aspirations LAW_102).  ⚠️ Survival there is an ARENA test — `find_instance` reaches the
  discard.  Smaller, all additive: `push_each_player_defeats(include_leaders=True)` for a
  card printed as plain "a unit they control" with no non-leader clause (Governor's Shuttle
  LAW_99); `push_bottom_from_discard(then_damage_enemy_base=N)`, a fifth settle-at-the-finish
  payoff so bottoming nothing deals nothing (0-0-0 LAW_174);
  `CostReduction.per_controller_discard_this_phase` (Fear and Dead Men LAW_179 — counted off
  `cards_discarded_this_phase` with the owner read back off each instance, the LAW_76 trick;
  DOCUMENTED WIDENING: that ledger is fed by hand AND deck discards, so a self-mill also
  discounts); and three condition atoms — **`NOT_OF`** (the negation sibling of ALL_OF /
  ANY_OF, evaluated in the same recursive branch), **`CONTROLLER_HAS_ASPECT_UNIT`** (the
  source-INCLUSIVE sibling of CONTROLLER_HAS_OTHER_ASPECT_UNIT) and **`OPPONENT_HAS_CREDIT`**
  (the enemy-narrowed ANY_PLAYER_HAS_CREDIT, for "defeat an ENEMY Credit token" — Defiant
  Scrapper LAW_106).  ⭐ The reusable shape worth carrying: when a card's clause changes the
  CANDIDATE SET rather than a magnitude it cannot ride inside one CustomEffect (the Zeb
  LAW_45 conditional-magnitude trick) — register TWO optional triggers over COMPLEMENTARY
  conditions (`X` and `NOT_OF(X)`), so exactly one is ever collected and the printed
  "instead" is exact (Sabine Wren LAW_78).  PURE REUSE worth knowing: LAW_77 = the Frozen in
  Carbonite SHD_193 pair (`ReadyRestriction(condition=None)`) with the "gains" half as a
  `GrantedAbility(PhaseStartTrigger("regroup"))` — the Foresight TWI_68 timing, and the
  wrapper is what makes "your base" follow the HOST rather than whoever played the Condition;
  LAW_85 = the Haymaker LAW_168 shared-`event_ctx` chain (`change_control` + `prior_target_id`
  / `excluded_target_id` / `same_arena` → `requires_prior_target` + `same_arena_as_event` +
  `excludes_event_target`); LAW_132 = the One Way Out SEC_157 `abilities_suppressed` MODIFIER
  arm (a duration the per-instance LOF_202 flag cannot carry) plus a cost-gated defeat in the
  SAME CustomEffect, so a unit too expensive to kill still loses its abilities from one
  prompt; LAW_173 = the Yoda TWI_4 "record then gate" mill (stamp `prior_target_id` only on
  an Aggression discard → `requires_prior_target`); LAW_178 = `push_modal(["bomb_ground",
  "bomb_space"])` verbatim (Bombing Run SOR_173 already deals exactly 3 to each unit in the
  chosen arena); LAW_183/187 = `push_select_damage(arena=…)`, whose distinct-picks rule IS
  "different units"; LAW_195 = `DefeatUnit(kind="upgrade", arena="space")` — an attached
  upgrade carries its HOST's zone tag, so the arena filter IS "attached to a space unit".
  🧪 TEST NOTES: a `select_damage` capped at its Nth pick auto-finishes, as does a
  `bottom_from_discard` with `count=1` — a trailing Finish action is then ILLEGAL; playing an
  event flips the active seat, so a test that attacks afterwards must reset
  `active_player_index`; and `_make_state`'s base has NO aspects, so any 2-aspect card costs
  +4 there — assert a cost REDUCTION as a delta, never an absolute.
- **sec-set:19–24 batch (6 groups, 34 cards — SEC now 263/264)** — all additive; **no new
  decision kind**, no escape hatch.  ⚡⚡ **KEYWORD-SANITISER RULE 9 (`_granted_only_keywords`)**
  — a keyword the card REGISTERS a grant of and which never appears at the START OF A LINE in
  its text is stripped (Units only; a Leader's bar lives in `deploy_box`, which the sanitiser
  never sees).  Rule 1 only knows the verb "gain(s)", so every "**give** a unit Sentinel"
  card evaded it AND read as a bare mention — nine cards across the DB carried a printed
  keyword they do not have (Gladiator Star Destroyer SOR_86, Captain Typho TWI_46, Bodhi Rook
  LAW_104, Nute Gunray SEC_31, Remote Escort Tank SEC_255, Captain Rex SEC_48 → Sentinel;
  Kaadu LOF_114, Naboo Royal Starship SEC_99 (+2 promos), Jango Fett SHD_138 → Overwhelm).
  Line position is the exact signal the source data gives: a possessed keyword is always its
  own leading paragraph.  ⭐ **Keyword-only blackout** — a new `keywords_suppressed` Modifier
  read at BOTH keyword-layer entry points (`has_keyword` / `keyword_value`), the keyword-scoped
  mirror of Mind Trick LOF_202's ability blackout: "it loses its keywords (**and can't gain
  keywords**) for this phase" (Screeching TIE Fighter SEC_185) — the "can't gain" half falls out
  of reading it before every grant source, and the unit keeps its non-keyword abilities.
  ⭐ **`Protection.hp_defeat_any_phase`** — `from_hp_defeat` past the ACTION phase; Chirrut Îmwe
  SOR_4 PRINTS "During the action phase", so that stays the default and a clause with no phase
  limit opts in (Cassian Andor SEC_12 deployed, whose "isn't defeated by having no remaining HP
  **and** can't be defeated by enemy card abilities while you have the initiative" is ONE
  self-Protection ConstantAbility gated on `CONTROLLER_HAS_INITIATIVE`).
  ⭐ **`CannotBeAttackedAfterDamagingBase`** marker — the aura sibling of
  `CannotBeAttackedWhileExhausted` at the same `_cannot_be_attacked` seam, over the existing
  `game_memory.units_dealt_base_damage_this_round` ledger (checked FIRST, so the scan never runs
  for a unit that has not hit a base); the scan walks only `base_zone`, which makes it
  undeployed-only for free — the mirror of the arena-scan convention (Cassian SEC_12 undeployed).
  ⭐ **`game_memory.actions_taken_this_phase`** (dict, counted in `apply` on a CLEAR STACK, so
  resolving a sub-decision is not an action) behind the **`PlayOnlyAsFirstAction`** marker, read
  at the two hand-play seams `CannotPlayFromHand` already uses — and because an ability that
  plays a card never routes through `PlayCard`, the card's printed "can't be played as the result
  of another action" note is free (Confidence in Victory SEC_145).  Its payoff is
  **`game_memory.win_at_regroup_sole_arena`**, the `lose_at_regroup` (SHD_208) mirror checked in
  `_enter_regroup` and delivered by marking every OTHER player's base defeated; and
  **`game_memory.rescue_at_regroup`**, a one-shot list swept there through the shared
  `_rescue_captured_card` seam (Arrest SEC_195 — where `_apply_capture` needed nothing new to let
  a BASE be the captor: it resolves the captor with `find_instance`, which reaches the base zone).
  Smaller, all additive: **`DamagePrevention.first_each_phase`** — a WHOLE-instance once-per-phase
  prevention consumed at `_deal_damage_with_shield` over the phase-cleared
  `first_damage_prevented_this_phase` (Umbaran Mobile Cannon SEC_67); ⚠️ it is deliberately SKIPPED
  by the per-instance `_damage_prevention_on` sum, or its default `amount` would also shave every
  later instance.  **`game_memory.cannot_play_events_this_phase`** + `_events_locked`, the
  `CannotPlayFromHand` shape for "they can't play events for this phase" (Trade Route Taxation
  SEC_126; documented narrowing — the Plot route out of the resource zone stays open).
  **`push_multi_capture(mandatory=True)`** — the Finalizer SHD_92 pairing walk with the "any
  number" stop withheld while a legal pair remains, i.e. "**EACH** friendly unit captures an enemy
  non-leader unit in the same arena" (Let's Talk SEC_131).  **`WhenYouDraw.any_player`** — the
  any-seat sibling of its controller / opponent readings (Chairman Papanoida SEC_159); "during the
  action phase" stays intrinsic (the draw ledger records only ACTION draws).
  **`Condition.ATTACHED_HOST_HAS_TRAIT`** — the trait sibling of `ATTACHED_HOST_NAMED`, over
  EFFECTIVE traits, gating an upgrade's optional WhenPlayed so a non-matching host never prompts
  (Special Modifications SEC_227).  Predicate **`sole_friendly_upgrade_on_source`** — evaluated
  against the SOURCE, so "while this unit has exactly 1 friendly upgrade on it, THAT upgrade …"
  is one test; it drives an AURA `Protection` (Mythosaur LOF_73) whose target is an upgrade
  (Willrow Hood SEC_61).  Two `name_a_card` `then_payoff` arms — **`experience_per_hand_copy`** /
  **`token_per_hand_copy:<Name>`** (Inspector's Shuttle SEC_260, Stolen Starpath Unit SEC_210) —
  and two disclose payoff arms, **`opponent_discard`** (count; Luthen's Haulcraft SEC_153) and
  **`opponents_discard_random`** (seeded `make_rng` + write-back; Duchess's Investigators SEC_223).
  ⭐ PURE REUSE worth knowing: **"choose a player" / "choose an arena" is `push_choose_modal(pick=1)`**
  (SEC_145, SEC_178) — but ⚠️ on an **EVENT** card the option specs must be `TriggerAbility`, the
  exact mirror of Lightmaker SEC_207's UNIT card needing `EventAbility`, because
  `_resolve_event_ability` walks EVERY EventAbility spec and would run all the options; SEC_192
  Grand Moff Tarkin is the Traitorous SOR_122 `change_control` + `control_linked_to` pair verbatim
  (the second sentence needs no ability — `_revert_linked_control` already fires on leave-play);
  SEC_38 Condemn's "loses all other abilities **while attacking**" is a `this_attack`
  `abilities_suppressed` modifier (the One Way Out SEC_157 arm) landed from its own
  `GrantedAbility(OnAttack)`, with `push_disclose(discloser_id=<defending player>)` for the
  opponent-decided disclose — DOCUMENTED DEVIATION: the host's own On Attack abilities were
  collected in the same window and still resolve.  SEC_48 Captain Rex = ONE effect pair
  (targeted enemy grant FIRST, `fixed=SELF` second — the Mandalorian SHD_18 single-prompt rule)
  registered under BOTH `WhenPlayed` and `WhenAttackEnds`.
- **lof-set:19–22 batch (4 groups, 23 cards — LOF COMPLETE at 264/264)** — all additive; **no
  new decision kind**, no escape hatch.
  ⭐ **Aura `Protection`** (`resolver._aura_protection`, the third source in `_target_protected`
  beside a card's own self-targeted Protection and one on an attached upgrade): a NON-SELF
  `ConstantAbility` carrying a `Protection` protects every unit its target matches — Mythosaur
  LOF_73, "Friendly upgraded units can't be exhausted or returned to hand by enemy card
  abilities".  Gated by a cached `_is_aura_protector(sc, cn)` so the board walk never runs for
  the ~all cards that grant no such aura; "by enemy card abilities" is intrinsic to
  `_target_protected`, which already ignores friendly sources.
  ⭐ **`DoubleKeywordValue(keyword, target)`** passive marker (Marchion Ro LOF_186, "Each
  friendly unit's Raid is doubled") — read at the very END of `keywords.keyword_value`, after
  every additive source, so it doubles the EFFECTIVE value.  `has_keyword` is untouched
  (doubling 0 is 0).  Two doublers multiply twice, per the CR's independent-application reading.
  ⭐ **`WhenDealsCombatDamageToBase` grew an OBSERVER form** — `filter` (a different card, e.g. a
  Base, fires for the unit that dealt the damage — the `WhenFriendlyUnitDealtCombatDamage`
  shape) + `min_amount`, reading the new `base_combat_damage_amount` in the same event_ctx
  (Temple of Destruction LOF_25, "a friendly unit deals 3 or more combat damage to an enemy
  base").  A friendly unit attacking a base always hits the ENEMY base, so `controller="friendly"`
  is the whole filter.
  Smaller: `deck_search` `disposition="top"` (put the picks back on top in SELECTION order — the
  reveal_top SOR_152 click-order convention — instead of drawing them, Following the Path
  LOF_103); `push_move_upgrade(host_controller_id=…)` pinning the upgrade's CURRENT host to one
  player ("a friendly upgrade on a friendly unit", Jocasta Nu LOF_248 — the board-wide default
  admits enemy hosts); `push_use_force(payoff="opponents_discard")`; `TargetSpec(kind="leader")`
  = a leader card IN PLAY, arena OR undeployed in base_zone (Mythosaur's Mandalorian grant).
  Reuse worth knowing: "Action [exhaust a friendly unit]" has no cost spec — model the cost as a
  leading targeted `ExhaustCard` effect plus a `CONTROLLER_HAS_READY_UNIT_COST_MAX` (param
  `None` = any ready unit) payability gate (Tomb of Eilram LOF_28); "unit X deals damage equal to
  its remaining HP to unit Y" is the two-stage `prior_target_id` / `requires_prior_target` chain
  (Protect the Pod LOF_128); "can't be attacked this phase" is the existing `cannot_be_attacked`
  modifier (TWI_219), which carries a Sentinel escape — faithful for LOF_262, a documented
  deviation for LOF_211.
- **lof-set:12–18 batch (7 groups, 49 cards)** — a dozen small additive seams; **no new
  decision kind** and no core-machinery touch.
  ⚡⚡ **`has_keyword` / `keyword_value` now filter on the KEYWORD BEFORE evaluating a
  `ConstantAbility`'s condition.**  A condition may itself read the keyword layer (the new
  `CONTROLLER_HAS_OTHER_UNIT_WITH_KEYWORD`, Oppo Rancisis LOF_105 "gains Ambush while another
  friendly unit has Ambush", ×9 keywords), and the old order evaluated the conditions of grants
  for *every other* keyword too — two Oppos fanned that out across 18 (source, keyword) pairs
  and the suite HUNG.  Conditions are pure predicates, so the reorder is free; the atom still
  carries its own `_KEYWORD_SCAN_EVALUATING` guard for the same-keyword cycle.
  ⭐ **`WhenDamageDealtToYourBase`** observer — "When damage is dealt to your base" (The
  Daughter LOF_252), from ANY source: `actions.record_base_damage` appends the base owner to a
  `base_damage_events` ledger at both base-damage sinks (the base-attack pipeline and
  `resolver._apply_deal_damage`'s Base branch), which `_fire_base_damage_observers` drains at
  the action settle-point — the `_fire_heal_observers` shape, so no new event class and it can
  never fire mid-pipeline.
  ⭐ **Two `game_memory` pending-charge lists**, both the `pending_exploit_grants` shape:
  `pending_keyword_grants` ("the next [trait] unit you play this phase gains K" — Deceptive
  Shade LOF_180, Third Sister LOF_10 — consumed in `_put_unit_in_play` BEFORE the enter-play
  keyword bus, so a granted Ambush triggers on entry) and `pending_initiative_effects` ("the
  next time you take the initiative this phase, exhaust all units" — Premonition of Doom
  LOF_203, consumed in `ClaimInitiative`).  Plus a game-scoped `activated_ability_use_counts`
  (instance_id → count, never cleared) behind the **`SOURCE_ABILITY_USES_MAX`** condition —
  "use this ability no more than 3 times each game" (Mystic Monastery LOF_22) expressed as a
  CONDITION so the limit needs no new gate at each of the six ability-enumeration sites.
  Riders on existing decision kinds: `push_play_upgrade_from_hand(trait=, then_ready_source=)`
  (Cin Drallig LOF_150); `push_play_from_hand(then_tokens=[…], then_prevent_next_damage=N)`
  (Three Lessons LOF_225 / Shien Flurry LOF_220 — the latter a **one-shot** `damage_prevention`
  modifier, `value={"amount": N, "once": True}`, dropped as soon as it applies, unlike Finn
  TWI_53's standing one); `push_select_token(return_to_hand=True)` (the `defeat` sibling, also
  applied AFTER the pop); `push_play_event_from_hand(ignore_aspect_penalty=)`; and two
  granted-attack riders — `power_equals_remaining_hp` (Babu Frik LOF_206, a this_attack stats
  SHIFT so every damage site reads one number) and `return_defender_upgrades` (Force Speed
  LOF_205).  ⭐ The latter is how to grant an **arbitrary "On Attack" ability for one attack**:
  mark the attacker with a this_attack modifier, then act on it in `_resolve_unit_combat`'s
  OnAttack window (`_push_granted_attack_on_attack`) — the decision then rides the existing
  `pre_attack` continuation and lands BEFORE combat damage.  New matcher bits:
  `TargetSpec.traits_any` (ANY-of, vs `traits`' ALL-of — Peli Motto LOF_258) and the
  `has_hidden` predicate.  Condition atoms: `ENEMY_HAS_TRAIT_UNIT`,
  `CONTROLLER_HAS_UNIT_REMAINING_HP_MIN` (effective HP less damage).  PURE REUSE worth knowing:
  LOF_153 "+2/+0 for each damage on him" is `StatBonus(count="target_damage")` on `fixed=SELF`
  (Radiant VII JTL_226); LOF_97 is Superlaser Technician SOR_83 minus "and ready it" (so the
  resource enters EXHAUSTED, the CR default); LOF_20 is Jedi Temple LOF_23 verbatim.  ⚠️ An
  `EventAbility` has NO `condition` field and `ConditionalEffect` cannot hold a *targeted*
  sub-effect — for "If <gate>, <targeted effect>" (LOF_216 / LOF_263) put the gate inside one
  `CustomEffect` that pushes a `select_token`, so nothing is offered when the gate fails.
  ⚠️ Implementing LOF_102 freed the P25_107 mirror (same three `tests/test_reprints.py` slots
  as LOF_53 last batch) — re-run `scripts/find_reprints.py --check` after every batch.
- **lof-set:09–11 combat-tricks batch** — six small additive seams, no new decision kind and
  no core-machinery touch.
  ⭐ **`RevokeTrait(trait, target, duration)` + the `trait_revoke` Modifier** — the
  TRAIT-layer sibling of `RevokeKeyword`, for "Each enemy unit loses the Force trait for
  this phase" (Nameless Terror LOF_33).  `traits.get_traits` / `has_trait` consult
  `_revoked_traits` FIRST — ahead of the printed traits and every `TraitGrant` source — so
  "can't regain it while revoked" falls out for free, exactly as `keyword_revoke` gives it
  for keywords; it expires with the ordinary duration sweep.  ⚠️ A new targeted effect must
  also be added to `resolver._get_effect_target_spec`'s isinstance tuple, or its
  `TargetSpec` is invisible and the effect silently resolves onto nothing.
  **`WhenFriendlyUnitAttacksAndDefeatsUnit`** observer trigger — the GROUP analogue of
  `OnAttackDefeatsUnit` (the `WhenFriendlyUnitDealsCombatDamageToEnemyUnit` TWI_16 shape):
  same firing site, same `attack_defeated_unit` event_ctx key, plus a test that the attacker
  is controlled by the observer's controller — so "the attacker survived and the defender
  died" stays intrinsic and that key is also how "that friendly unit" is located (Darth Revan
  LOF_17; the source is NOT excluded — a leader that kills is "a friendly unit").  ⚠️ Note
  `fixed=ATTACKER` does NOT resolve at that site (it reads `event_ctx["attacker_id"]`, which
  the combat step does not thread there) — use a `CustomEffect`.
  **`PrintedStatsOverride(power, hp)`** marker on an UPGRADE — "Attached unit's printed power
  is considered to be 5 and its printed HP is considered to be 5" (Size Matters Not LOF_56),
  read where `compute_power`/`compute_hp` SEED the total from the printed value, so every
  bonus (upgrades, tokens, Grit, modifiers, constants) still layers on top — the printed
  reading.  ⚡ Those two functions are the hottest path in the engine, so the per-upgrade spec
  walk is gated on a lazily-built registry key set (`_printed_stats_override_keys`, the
  `_suppress_leader_keys` trick) and skipped entirely for a host with no upgrades.
  **`push_opponent_chooses_target(disposition="exhaust", ready_only=)`** — the SHD_246
  decision's third disposition: the single mandatory stage of `"defeat"` (LOF_43) with an
  exhaust instead, and a `ready_only` candidate filter so an already-exhausted unit — which
  would make the whole clause a no-op — is never a legal pick, and with none nothing is
  pushed (Cal Kestis LOF_15).  Two condition atoms: **`SOURCE_ATTACHED_UPGRADES_MIN`** (the
  trait-blind sibling of `SOURCE_ATTACHED_TRAIT_UPGRADES_MIN`; Shield/Experience tokens count,
  and on an upgrade's `ConstantAbility(SELF, TraitGrant)` the trait layer evaluates it against
  the HOST — Jedi Trials LOF_52) and **`CONTROLLER_HAS_UNIT_POWER_MIN`** (≥1 friendly arena
  unit at that *effective* power — Praetorian Guard LOF_85), which **shares SOURCE_POWER_MIN's
  `_POWER_MIN_EVALUATING` reentrancy guard**: it is read from the keyword layer and
  `compute_power` re-enters that layer for every candidate.  PURE REUSE worth knowing: LOF_49
  "while this unit is defending, it gets +2/+0" is `while_target_defending` with `fixed=SELF`
  (Concord Dawn SHD_42); LOF_58/LOF_60 are their SOR_61 / TWI_58 namesakes verbatim
  (`StandingPlayDiscount(applies_to="upgrade_on_source")` / `CONTROLLER_HAS_TRAIT_CARD_IN_PLAY`);
  LOF_76 "play a Force unit and give a Shield token to IT" = `push_play_from_hand(trait=,
  then_select_token={…, "restrict_played": True})` — a SETTLE payoff is the only ordering that
  runs after the play (LOF_125); LOF_75's "Use the Force.  If you do, <targeted effect>" is the
  `controller_has_force_token` BOARD-GATE predicate (Sorcerous Blast LOF_172), while LOF_48/72's
  "You MAY use the Force" is instead the optional trigger gated on `CONTROLLER_HAS_FORCE_TOKEN`
  (Luke LOF_249).  ⚠️ Implementing LOF_53 freed the P25_105 mirror — re-run
  `scripts/find_reprints.py --check` after a batch; three `tests/test_reprints.py` slots fail
  until the alias lands.  🧪 TEST NOTE: the `_find_instance` helper searches ARENAS only — a
  base or an undeployed leader needs `state.find_instance(...)[1]`.
- **jtl-set:26 misc-abilities batch (the last JTL group)** — four small additive seams, no
  new decision kind, no core-machinery touch.
  **`push_move_upgrade(tokens_only=, only_upgrade_id=, decider_id=, mandatory=)`** — four
  knobs that finish the `move_upgrade` decision's filter set.  `tokens_only` is the
  complement of `include_tokens`: ONLY Shield/Experience token upgrades, which is "take
  control of a **token** upgrade on a unit and attach it to a different eligible unit"
  (Shuttle ST-149 JTL_242, the Hondo Ohnaka JTL_56 shape — its own entry Shield is
  immediately a legal source, as the card's printed rules note says).  The other three all
  serve Death Star Plans JTL_260's "**The attacking player** takes control of **this
  upgrade** and attaches it to a unit they control": `only_upgrade_id` pins the relocation
  to one upgrade (`from_host_id` can't, when the host carries several), `decider_id` hands
  the choice to someone other than the source's controller, and `mandatory` drops the
  decline (`_move_upgrade_actions` omits `DeclineMoveUpgrade`, whose apply-guard now
  refuses).  All ride in the decision context, so enumeration and both apply-guards agree.
  **`StandingPlayDiscount` read off ATTACHED UPGRADES + `applies_to="unit"` +
  `actions._standing_discount_key`** — "Attached unit gains: 'The first unit you play each
  round costs 2 resources less'" (JTL_260).  `_standing_play_discount_sources` now walks
  `(host, *host.attached_upgrades)`, and because it scans one player's arena the
  beneficiary is automatically the HOST's controller — the printed "attached unit gains"
  reading, and what makes the plans worth stealing.  ⚠️ The once-per-round spend key is
  per-(source, beneficiary) for an upgrade-borne discount and per-source for a unit-borne
  one, because the upgrade changes hands mid-round: the card's rules note is explicit that
  "Multiple players can benefit from the discount ability in the same round".
  **`ConstantAbility.while_attacking_unit_arena`** — narrows `while_attacking_unit` to a
  defender in one arena, "While attacking a **space** unit, this unit gets −1/−0"
  (Retrofitted Airspeeder JTL_259), checked against the threaded `defender_id` at the same
  `compute_power` site; pairs with the existing `CrossArenaAttack` marker (SOR_212
  mirrored: a GROUND unit reaching space), so the debuff applies exactly to the attacks the
  marker unlocked.
  ⭐ PURE REUSE worth knowing: **"Choose up to 3 units.  Those units lose all abilities and
  can't gain abilities for this round"** (There Is No Escape JTL_244) needs NOTHING new —
  three `optional` targeted `CustomEffect` steps over the Attack Pattern Delta SOR_106 /
  Unlimited Power TWI_156 `excludes_event_targets` accumulating set (that IS "up to 3
  distinct units"), each stamping Mind Trick LOF_202's `abilities_suppressed` read-layer
  flag, whose "cleared at the round rollover" scope IS this card's "for this round" and
  whose read-guards give "can't gain abilities" for free.
- **jtl-set:22–25 misc-abilities batch** — ten small additive seams, no new decision kind,
  no core-machinery touch.
  ⭐ **"Use a 'When Defeated' ability" without a defeat** — `resolver._when_defeated_ability_indices`
  (the registry indices of a card's `WhenDefeated` abilities, with the ability-redo chokepoint's
  two carve-outs: a Bounty is the OPPONENT's ability and `WhenDefeatedAsUpgrade` is a defeat
  *replacement*) plus the `has_when_defeated_ability` target predicate.  A card then simply
  PUSHES a `resolve_effects` decision for that ability with the OTHER unit as source — exactly
  what `AcceptTrigger` pushes — so no trigger/decision machinery moves: Chimaera JTL_39 ("use a
  'When Defeated' ability on another friendly unit", one target) and Shadow Caster JTL_169
  ("when a friendly unit is defeated, use ALL of its 'When Defeated' abilities again", pushed in
  reverse so the first-registered resolves first, from the unit now sitting in its discard).
  **`CustomEffect.available_fn(state, source_ci, event_ctx)`** — an optional availability
  predicate read ONLY by `_optional_trigger_has_legal_effect`, extending the "don't offer a
  no-op" rule to a non-targeted `CustomEffect` (which the walker otherwise assumes always does
  something); it never gates execution, only the offer.  Shadow Caster needs it — most units
  have no When Defeated ability at all.
  **`game_memory.prevent_next_base_damage` + `actions.base_damage_after_prevention`** — a
  one-shot, per-base "the next time damage would be dealt to it this phase, prevent that damage"
  (Close the Shield Gate JTL_74).  Bases have no single damage chokepoint, so the helper is read
  at EVERY base-damage site (ability damage, indirect damage, a base attack, both Overwhelm
  spill sites, a leader's base hit, the empty-deck penalty) — the `_bases_cannot_heal` shape;
  keyed by base OWNER, spent by the first instance whatever its size, phase-cleared.
  **`HalvePaidCosts` marker + `actions.resource_cost_for`** — "While paying costs, you pay half
  as many resources, rounded up" (The Starhawk JTL_105), applied LAST to the *determined* cost
  (after every reduction, discount and tax) at the play-cost seam AND at every activated-ability
  `PayResources` affordability check plus its payment site, so it covers card and ability costs
  as printed; non-resource costs are untouched.
  **`Condition.SOURCE_CHOSEN_KEYWORD` + `game_memory.chosen_keywords` + four fungible
  `choose_keyword_*` modal modes + keyword-sanitiser rule 7** — "When Played: Choose Grit,
  Restore 1, Sentinel, or Shielded.  While this unit is in play, each friendly Vehicle unit
  gains the chosen keyword" (Admiral Yularen JTL_47).  The modal only RECORDS the pick against
  the source instance; the card registers FOUR parallel `ConstantAbility` auras, one per
  choosable keyword, each gated on the atom — which gets the printed duration free in both
  directions (later Vehicles gain it; it lapses when the source leaves play, since a constant
  scans only cards in play).  Sanitiser rule 7 keys on that same condition atom to strip the
  four choosable keywords the API mistags onto the card (rule 1's text heuristic keeps them —
  each name appears bare, in the "Choose …" list, not after "gains").
  **`AttackRestriction(condition=None)`** — the unconditional bar, "This unit can't attack"
  (Corporate Defense Shuttle JTL_59), matching the `ReadyRestriction` None-means-always
  convention.
  **`push_move_upgrade(dest_controller_id=, exclude_upgrade_traits=)`** — destinations are
  fixed to one player rather than to the current host's controller, which IS "take control of a
  non-Pilot upgrade on a unit and attach it to a different eligible unit" (Hondo Ohnaka JTL_56):
  control follows the host, so the source upgrade may sit on an ENEMY unit.
  **`NextPlayDiscount` entry keys `card_name` + `free`** (`_play_discount_entry_amount`) — a
  pending discount narrowed to one card NAME and worth the card's whole aspect-adjusted cost:
  "The next time you play a copy of that unit this phase, you may play it for free" (Jump to
  Lightspeed JTL_232).
  **`push_attach_unit_as_pilot(hosts="enemy")`** — the Poe JTLP_6 self-attach decision pointed
  at the OPPONENT's pilotless Vehicles (Sidon Ithano JTL_213); the choice rides in the decision
  context so the enumeration and the apply-guard agree.
  **`IndirectDamageSelfAssign` read off attached upgrades** — Targeting Computer JTL_171
  ("Attached unit gains: 'You assign all indirect damage dealt by this unit'") reuses
  Devastator JTL_143's marker; DOCUMENTED SIMPLIFICATION: that read is controller-scoped (as
  Devastator's own "all indirect damage YOU deal" already made it), so the Computer flips the
  decider for its controller generally, not only for its host's damage.
  ⭐ PURE REUSE worth knowing: **L3-37 JTL_49's defeat REPLACEMENT needs no new machinery** —
  "If this unit would be defeated, you may instead attach her as an upgrade to a friendly
  Vehicle without a Pilot" is an optional `WhenDefeated` whose targeted `CustomEffect` finds her
  already in the discard and relocates her (the Luke J25_4 `WhenDefeatedAsUpgrade` /
  Superlaser Technician SHD_85 stand-in; the momentary discard touch is unobservable).  ⚠️ This
  implementation also freed the C25_1 mirror — re-run `scripts/find_reprints.py --check` after a
  batch, three `tests/test_reprints.py` slots fail until the alias lands.  Sweep the Area JTL_233
  = the LAW_41 shared-`event_ctx` chain with a LEFTOVER budget ("combined cost 3 or less" =
  stamp `cost_le_threshold = 3 - cost1` and `same_arena`, then two optional targets), so "up to
  2 units in the same arena with a combined cost" needs no select-N decision; Turbolaser Salvo
  JTL_131 = the same chain where "choose an arena" collapses to choosing one enemy unit in it;
  JTL_83 Pantoran Starship Thief = `_attach_unit_as_pilot` + the Traitorous SOR_122
  control-LINKING pair (`change_control` + `control_linked_to`), which IS its printed "when this
  upgrade detaches, that unit's owner takes control of it"; JTL_52 = `StatBonus(count=
  "target_damage")` with `fixed=SELF` (Radiant VII JTL_226's aura count read off itself);
  JTL_54 = Lando LAW_108's `while_defending` constant verbatim.  ⚠️ TEST TRAP re-confirmed: a
  `WhenUnitDefeated` observer must be driven with `actions._defeat_unit`, never the
  `_defeat_and_fire` helper (which homes the corpse in the discard first).
- **`multi_capture_pairing` decision kind** (`push_multi_capture` / `CaptureWithUnit(captor_id, prey_id)`
  / `FinishMultiCapture`) — single-phase (captor, same-arena enemy non-leader prey) PAIR selection,
  "any number"; each pick captures inline via `_apply_capture` and marks the captor used, auto-resolves
  when no legal pair remains (Finalizer SHD_92 "choose any number of friendly units, each captures an
  enemy non-leader unit in the same arena"). Wired in legal_actions + web label/prompt + heuristic bot
  (greedy, highest-cost prey).
- **shd-set:21 misc-abilities batch** — small additive seams, no core-machinery touch (7/7 done; the two
  new decision kinds `play_captured_card` (Dryden Vos SHD_192) and `play_resource_units` (Endless Legions
  SHD_109 — reveal any number of your resources, play each revealed unit free, one at a time) have their own
  catalog rows above):
  **`Protection.from_capture` / `from_damage`** extend the Chewbacca JTL_103 Protection marker to two
  more enemy-ability effects — read at `_apply_capture` (skip an enemy capture) and the resolver
  DealDamage/DealDamageEqualTo arms (skip enemy ability damage; combat damage never routes through those
  effects, so it is unaffected) — Lurking TIE Phantom SHD_187 "can't be captured, damaged, or defeated
  by enemy card abilities" (+ Raid, keyword engine).  **`NamedCardPlayTax(amount)`** marker — the per-NAME
  analogue of Del Meeko SOR_34's `OpponentPlayTax` (which keys off card TYPE) and the tax-mirror of
  Regional Governor SOR_62's `ForbidNamedCardPlay`: read in `_opponent_play_tax`, it surcharges an
  opponent's play of the card the source has named (`named_card`); `push_name_a_card(from_hand=True)` names
  from the opponent's HAND (Qi'ra SHD_202 "look at an opponent's hand, then name a card … costs 3 more").
  **`push_search_and_play(free=, decider_id=)`** — the search-and-play push gained the two knobs
  push_deck_search already had: `decider_id` runs the search+play over another player's deck (a bounty
  resolving for the OPPONENT of the dying host) and `free` plays the found unit at cost 0 (Bounty Hunter's
  Quarry SHD_123, window 10 if the guarded host is unique else 5, units ≤3).  PURE REUSE: SHD_106 Rule with
  Respect = one friendly captor + `_apply_capture` over the `base_attackers_this_round` ledger (Ephant Mon
  SHD_88); SHD_132 Choose Sides = two shared-event_ctx targets + `change_control` ×2 (exchange control,
  owners unchanged).
- **shd-set:22 misc-abilities batch (🏁 COMPLETES SHD, 262/262)** — four small additive seams, no
  core-machinery touch: **`AmbushDefenderDebuff(power, hp)`** marker — read at `UseAmbush.apply`, the
  sole seam an Ambush attack is declared, applying every such marker the attacking player has in play
  as a `this_attack` stats modifier on the chosen defender; an ordinary attack by the same unit is
  untouched, which is the distinction the card draws, and "including this one" falls out for free
  (Enfys Nest SHD_219).  **`DamagePrevention(amount, host_named)`** marker on an UPGRADE — read at the
  single unit-damage chokepoint `_deal_damage_with_shield` (both combat and ability damage flow through
  it) via `_damage_prevention_on`; a *reduction*, applied BEFORE the Shield check, so an instance fully
  prevented leaves nothing for the Shield to eat and the Shield survives; `host_named` gates it on the
  host's name (Boba Fett's Armor SHD_224).  **`WhenFriendlyUnitDealtCombatDamage(traits)`** observer
  trigger — the group analogue of `WhenDealtCombatDamage`, matching when `event_ctx["dealt_combat_damage_to"]`
  names a *friendly* trait-carrying unit rather than the source itself; reuses that trigger's firing site
  verbatim (so "and isn't defeated" is equally intrinsic) and the site now also records
  `combat_damage_amount`, read by the new `DealDamageEqualTo` count **`"event_combat_damage"`** for "that
  much damage" (Tarfful SHD_250 — who is a Wookiee, so it covers damage to him too).
  **`ActivatedAbility.any_player`** — "Any player may use this ability" (Mercenary Gunship SHD_256):
  `legal_actions` additionally scans the OPPONENT's arenas for such a spec and `UseAbility` lifts its
  ownership guard; costs already come from the active player, so either side pays from their own
  resources, and it stays an action (usable only on your own turn).  `UseAbility` now threads
  `event_ctx["ability_user_id"]` so the effect knows who used it — here a `change_control` to that player.
  PURE REUSE: SHD_215 Smuggler's Starfighter = `CONTROLLER_HAS_OTHER_TRAIT_UNIT` gating collection +
  a targeted this-phase `ModifyStats`.
- **twi-set:01–02 direct-damage batch** — eight small additive seams, no core-machinery touch.
  **`Condition.ALL_OF(param=(ConditionCheck, …))`** — a CONJUNCTION composite evaluated
  recursively inside `ConditionCheck.evaluate`, so every existing single-`condition` field
  (trigger collection, activated-ability availability, constant gating) gets multi-clause gates
  for free (Chancellor Palpatine TWI_17, whose each side needs "right side showing AND the
  card's own If …").  **`game_memory.flipped_leaders`** + `SOURCE_LEADER_FLIPPED` /
  `SOURCE_LEADER_NOT_FLIPPED` — a double-sided LEADER that FLIPS instead of deploying: it has
  no Epic Action and no unit stats, so both sides are `undeployed_only` Actions and the side in
  play is this marker, not `deployed` (TWI_17; toggled by the card's own CustomEffect, never
  phase/round cleared).  **`game_memory.cards_drawn_this_phase`** + `DealDamageEqualTo`
  count **`"controller_cards_drawn_this_phase"`** — fed at the single draw chokepoint
  `_draw_cards`, ACTION-phase draws only, which is exactly the card's "(doesn't include cards
  drawn in the regroup phase)" (Pre Vizsla TWI_10).  **`Condition.CONTROLLER_HAND_SIZE_MIN`**
  — "While you have N or more cards in your hand, …" (TWI_10's two deployed clauses).
  **`game_memory.defeated_aspects_this_round`** + `CONTROLLER_ASPECT_UNIT_DEFEATED_THIS_PHASE`
  — the aspects of every defeated unit recorded beside `defeated_controllers_this_round` (a
  token ceases to exist and is in no discard pile, so the card can't re-find it), gating "If a
  friendly Heroism unit was defeated this phase" (TWI_17).  **`cost_eq_event_threshold`
  predicate** — the EQUALITY sibling of `cost_le_event_threshold` over the same
  `event_ctx["cost_le_threshold"]` ("an enemy unit that costs the same as the played unit",
  Quinlan Vos TWI_18 undeployed; his deployed side is the ≤ version).
  **`IgnoreAspectPenaltyForUpgrades(traits)`** marker on a UNIT — read at the play-cost seam
  `_host_waives_aspect_penalty` with the upgrade's chosen `target_host_id`, waiving the played
  card's WHOLE aspect penalty (unlike Daimyo's Palace LAW_20's single pip), plus
  **`Condition.SOURCE_ATTACHED_TRAIT_UPGRADES_MIN(param=(trait, N))`** for "if this unit has 4
  or more Lightsaber upgrades attached" (General Grievous TWI_34; "defeat 4 enemy units" is
  simply four sequential `DefeatUnit` effects — a defeated unit has already left the arena).
  **`combined_power_play` decision kind** (`push_combined_power_play` /
  `SelectCombinedPowerUnit` / `FinishCombinedPowerPlay`) — select any number of friendly units,
  whose combined *effective* power becomes the `cost_max` of a FREE `push_play_from_hand`
  carrying the new **`then_defeat_ids`**, so the chosen units die only after that play resolves
  (Consolidation of Power TWI_89; nothing playable ⇒ the defeat settles in the resolve helper,
  since "Then, defeat the chosen units" is not conditional on the play).  PURE REUSE this
  batch: TWI_3/13 = the In Pursuit TWI_221 `prior_target_id`/`excluded_target_id` "If you do"
  shape and `EACH_ENEMY` + a `damaged` predicate; TWI_36/76 = `hp_remaining_max` / `cost_max`
  on a `DefeatUnit`; TWI_78 = `DefeatAllUnits(controller="enemy")` under the Exploit keyword;
  TWI_41/44/48 = one CustomEffect binding a cost to its payoff.  GOTCHA re-confirmed: a
  multi-effect ability must list its TARGETED effect FIRST — a fixed effect placed earlier
  still consumes one ChooseTarget prompt (the Mandalorian SHD_18 wart; it bit TWI_17 twice).
- **twi-set:03–04 direct-damage batch** — four small additive seams, no core-machinery touch.
  **`game_memory.phase_aura_sources`** — a PHASE-SCOPED `AuraGrantedAbility` whose source is NOT
  in play: the existing aura-collection block in `resolver._collect_triggers` now also scans the
  ids listed here, recovering each through `find_instance` (which reaches the DISCARD), so a
  spent EVENT keeps granting from there with its real `owner_id` — which is what makes
  "each FRIENDLY unit" still resolvable (Pyrrhic Assault TWI_103; cleared at the phase
  rollover, so "for this phase" needs no expiry bookkeeping; empty list ⇒ the site is
  unchanged).  **`CostReduction.per_controller_base_damage`** — a SCALING reduction (`amount`
  once per N damage on the controller's base, integer division) read at the same single
  `_play_cost_reduction` site, so it moves both affordability and the resources exhausted
  (Resolute TWI_151, "1 less for every 5 damage on your base").  **`DealDamageEqualTo` count
  `"source_controller_units_with_trait:<Trait>"`** — the trait rides in the count string after
  the colon, so one arm serves every trait (Low Altitude Gunship TWI_149).
  **`Condition.CONTROLLER_HAND_SIZE_MAX`** — the ceiling mirror of the MIN atom; `param=0` is
  "If you have no cards in your hand" (Mister Bones TWI_154).  PURE REUSE: TWI_140 = the
  `prior_target_id`/`requires_prior_target` "If you do" shape with a defeat as the cost;
  TWI_146 = `push_deck_search(window=8, up_to=False)` with a trait `eligible` closure;
  TWI_150 = `CONTROLLER_BASE_DAMAGE_MIN` gating collection + `EACH_ENEMY` narrowed by `arena`;
  TWI_155 = `event_ctx["attached_to_id"]` (LOF_140); TWI_160 = `CONTROLLER_HAS_OTHER_TRAIT_UNIT`;
  TWI_162 = the Haymaker LAW_168 `same_arena` stamp + `same_arena_as_event`.  PATTERN worth
  reusing: "(All damage is dealt simultaneously.)" (Unlimited Power TWI_156) = N targeted
  CustomEffects that only RECORD `(target, amount)` into `event_ctx` (plus
  `excluded_target_ids`), then ONE trailing NON-targeted effect that applies them all — nothing
  is defeated while choices are still being made, and the applier still runs when the later
  steps fizzle for want of candidates.
- **twi-set:05 direct-damage batch** — two small additive seams, no core-machinery touch.
  **`CannotBeAttackedWhileExhausted`** marker — the DEFENDER-side mirror of `CannotAttackBases`,
  read at the attack-enumeration seam by `actions._cannot_be_attacked` alongside the Hidden
  filter (all three `attackable = [...]` sites): while exhausted the unit drops out of the
  eligible defenders entirely, so — exactly like Hidden — it neither blocks nor forces as a
  Sentinel.  Sentinel is the printed escape and a necessary one (an unattackable Sentinel would
  lock its whole arena).  Sabine Wren TWI_195; SOR_142's long-deferred residual is the same
  mechanic plus an aspect-count condition, so this seam unblocks it.
  **`push_discard_excess_from_hand(count=N)`** — the sibling shape "each player discards N cards
  of their choice" (Guerilla Insurgency TWI_177): each player's target hand size is pre-computed
  into a `keeps` map at push time (hand sizes only change through the decision itself, so pinning
  them up front is exact) and read through the new `_discard_excess_keep(ctx, pid)` helper at
  all four `keep` sites; `keep=` alone still means "down to N" (Smoke and Cinders SOR_174).
  PURE REUSE: TWI_173 = `fixed=EACH_IN_PLAY` + `arena` (HK-87 LOF_235); TWI_177's resources =
  `_fire_defeat_own_resource` per player (the K-2SO SOR_145 fungible auto-select); TWI_195's mill
  = the Kuiil SHD_41 top-of-deck + base-aspect compare; TWI_202 = `make_rng()`/write-back
  `rng_state` for "a random unit or base"; TWI_212 = the Boba Fett LAW_214 pay-then-payoff
  CustomEffect gated by `CONTROLLER_N_PLUS_READY_RESOURCES`; TWI_239 "for each unit defeated this
  way" = snapshot the matching units with their controllers, deal the damage, then read off which
  snapshot ids are no longer in an arena (nothing else could have removed them) and pay each
  controller a `_create_token_units` token.
- **twi-set:07 card-advantage batch** — four small additive seams, no core-machinery touch.
  **`WhenYouDeployLeader`** observer trigger — the sibling of `WhenDeployed` for a DIFFERENT
  permanent watching its own controller's deploy (matches `LeaderDeployed` by deploying
  player, not by instance id); collected at the existing deploy fire sites, and a Base
  source is reached by the base_zone branch of `_collect_triggers` (Shadow Collective Camp
  TWI_25).  **`Condition.ANY_UNIT_DEFEATED_THIS_PHASE`** — the controller-blind sibling of
  `ENEMY_UNIT_DEFEATED_THIS_PHASE` (`defeated_controllers_this_round` non-empty), gating "If a
  unit left play this phase" (Yoda TWI_4; being defeated is the ledgered way to leave play —
  a bounce/capture is not recorded, a documented simplification).
  **`push_bottom_from_hand(allow_top=True)` + `SelectHandCardToTop`** — the same
  `bottom_from_hand` decision offers each hand card in BOTH placements, for "put a card from
  your hand on the top **or bottom** of your deck" (Yoda TWI_4).
  **`push_play_upgrade_from_hand(include_discards=, ignore_aspect_penalty=)`** — the source
  zones widen from the controller's hand to EVERY player's discard pile, and the played
  upgrade's WHOLE aspect penalty is waived (the General Grievous TWI_34 reading, not the
  single-pip LAW_20 one) — A Fine Addition TWI_40.  An upgrade taken from a FOREIGN discard
  keeps its owner, so its "Attach to a friendly/enemy unit" restriction would evaluate from
  the wrong perspective; such cards are simply not offered from a foreign discard (documented
  narrowing — controller-agnostic restrictions, the vast majority, are unaffected).
  PURE REUSE: TWI_4's When Deployed = the Force Throw SOR_167 leading-CustomEffect "record then
  gate" shape (mill → `cost_le_event_threshold` + `requires_prior_target` → `DefeatUnit`);
  TWI_8 = `push_deck_search(window=3, up_to=False)` gated by Coordinate on both sides; TWI_35 =
  one CustomEffect binding defeat-a-friendly to the draw; TWI_68 Foresight = `GrantedAbility`
  wrapping a `PhaseStartTrigger("regroup")` whose name-a-card is collapsed to the modal
  remaining deck name (the naming is information-free, so only hit probability moves).
- **twi-set:08 card-advantage batch** — four small additive seams, no core-machinery touch (the
  new `rescue_guarded` decision kind has its own table row above).
  **`push_bottom_from_discard(own_only=, eligible=, then_create_token=)`** — the Restock SOR_252
  decision narrows to the CONTROLLER's own discard and to a card_def predicate ("choose up to 4
  UNITS in YOUR discard pile"), and gains a payoff that scales with how many cards were actually
  bottomed: one token unit of that name each, settled at the finish, so choosing none creates none
  (Reprocess TWI_88).  **`push_capture_combined_hp(max_captures=N)`** — a COUNT cap alongside the
  existing remaining-HP budget ("captures up to 3 enemy non-leader units with a total of 8 or less
  remaining HP", Cad Bane TWI_187); enforced in `_capture_combined_targets`, the one place that
  also drives the auto-finish, so the cap resolves the decision by itself.
  **`Condition.CONTROLLER_N_PLUS_TRAIT_UNITS(param=(trait, N))`** — the trait-narrowed sibling of
  the Coordinate atom `CONTROLLER_N_PLUS_UNITS`, over effective traits (Petition the Senate
  TWI_100, whose "If …, draw 3" is a plain `ConditionalEffect` — an `EventAbility` has no
  `condition` field).  **`Condition.OPPONENT_MORE_UNITS_THAN_CONTROLLER`** — the MIRROR of
  `CONTROLLER_MORE_UNITS_THAN_OPPONENT`, not its negation (equal counts satisfy neither) — Old
  Access Codes TWI_168.  PURE REUSE: TWI_101 Mas Amedda = the Grogu ASH_18 shape (an optional
  `WhenYouPlayCard(card_type="unit")` observer gated `SOURCE_READY`, one CustomEffect binding the
  exhaust to `push_deck_search(window=4, up_to=False)` so cost and payoff stay atomic); TWI_152 =
  `ATTACHED_HOST_NAMED` gating collection (Ahsoka's Padawan Lightsaber TWI_248); TWI_175 = a bare
  `DrawCards(3)`.
- **twi-set:09–10 card-advantage batch** — three small additive seams, no core-machinery touch.
  **`discard_play_discount` deck_search disposition + `game_memory.discard_play_discount_this_phase`
  + `PlayFromDiscard.discount`** — the DISCOUNTED sibling of Cobb Vanth SHD_115's free-replay flag
  (Aid from the Innocent TWI_201: "search the top 10 … for 2 Heroism non-unit cards and discard
  them.  For this phase, you may play the discarded cards, and they each cost 2 resources less"):
  each selected card is discarded and recorded `{instance_id: reduction}`, which becomes branch (c)
  of `_enumerate_discard_play_actions` (ANY card type, unlike the Unit-only free permission — an
  Upgrade is offered once per legal host) and is consumed at the play.  `PlayFromDiscard` also
  gained the EVENT branch it never needed before: the card returns to the discard and resolves
  through `_resolve_event_ability`, the same chokepoint a hand play uses.
  **`push_bottom_from_discard(then_draw=N)`** — the draw-payoff twin of `then_create_token`,
  likewise settled at the finish so bottoming nothing draws nothing ("put a Clone unit from your
  discard pile on the bottom of your deck.  If you do, draw a card" — Fives TWI_216).
  PURE REUSE: TWI_188 = `push_deck_search` whose WINDOW is the scaling part (`len(
  defeated_controllers_this_round)`, one entry per defeat); TWI_223 = a first-card self-discard
  bound in ONE CustomEffect to `push_name_and_discard` (the Chimaera SOR_185 decision already
  carries the opponent's hand to the controller and offers only names present, which IS "look at
  their hand and discard a card from it"); TWI_220 = the Chewbacca JTL_103 `Protection` marker
  (capture/defeat/return) on an UPGRADE — `_target_protected` scans a target's attached upgrades,
  so a self-protection marker on an upgrade is exactly "attached unit gains"; TWI_252 = a seeded
  `make_rng` shuffle of the opponent's discard onto their deck bottom.
- **twi-set:11 leaders batch** — four small additive seams, no core-machinery touch.
  **`IgnoreAspectPenaltyForPlays(card_type, traits)`** — the CONTROLLER-scoped sibling of
  `IgnoreAspectPenaltyForUpgrades` (which keys off a played upgrade's HOST): read at the same
  play-cost seam by `_controller_waives_aspect_penalty`, which scans the controller's base_zone (so
  an UNDEPLOYED leader's copy of the clause counts) and both arenas, waiving the played card's WHOLE
  aspect penalty — "Ignore the aspect penalty on Clone units you play" (Nala Se TWI_1).  The two
  waivers are combined with `max(...)`, never summed.
  **`StatBonus.count="controller_base_damage_per_N"`** — a scaling self-buff read off the
  controller's base damage by integer division, the stat sibling of
  `CostReduction.per_controller_base_damage` (Anakin Skywalker TWI_12, "+1/+0 for every 5 damage on
  your base"); the divisor rides in the count string, so one arm serves any step.
  **`WhenFriendlyUnitDealsCombatDamageToEnemyUnit`** — the GROUP analogue of Rukh SOR_85's
  `WhenDealsCombatDamageToUnit`, matching the same `attacker_dealt_combat_damage_to_unit` /
  `defender_id` keys at the same firing site for an OBSERVER whose controller owns the dealer
  (source excluded), so "that enemy unit" is the `DEFENDER` sentinel and the survivor clause stays
  intrinsic.  Covers the ATTACKING side only (a friendly defender striking back is not ledgered
  there) and combat damage only — documented (Jango Fett TWI_16, both sides).
  **Three condition atoms**: `CONTROLLER_UNIT_DEFEATED_THIS_PHASE` (the friendly mirror of the
  ENEMY_ atom over `defeated_controllers_this_round` — Wat Tambor TWI_6);
  `CONTROLLER_ATTACKED_THIS_PHASE` (the trait-blind, source-inclusive sibling of
  `CONTROLLER_ATTACKED_OTHER_TRAIT_UNIT_THIS_PHASE`, resolving each recorded attacker id through
  `find_instance` so an attacker that has since DIED still counts — Captain Rex TWI_7); and
  `CONTROLLER_PLAYED_EVENT_THIS_PHASE` (the event-typed sibling of `VILLAINY_PLAYED_THIS_PHASE` over
  `events_played_this_round` — Asajj Ventress TWI_14).  ⭐ "Deals combat damage before the defender"
  IS First Strike: a `GrantKeyword("First Strike", duration=THIS_ATTACK)` on SELF from an On Attack
  trigger, which the combat step reads through `has_keyword` (On Attack resolves before the damage
  step).  PURE REUSE: TWI_1's aura = the Gar Saxon SHD_1 `AuraGrantedAbility(WhenDefeated)`; TWI_9 /
  TWI_12 / TWI_14's actions = `push_granted_attack` (`grant_keywords`, `bonus_if_defender_unit`,
  and a magnitude decided at resolution); TWI_12's "deal 2 damage to your base" half-cost lives
  inside its one CustomEffect (base damage is always payable — the Galactic Ambition SOR_235
  convention), so no new cost spec.  A ConstantAbility / AuraGrantedAbility on a LEADER is
  deployed-only for free (both are collected by scans over cards in play).
- **twi-set:12–13 combat-tricks batch** — four small additive seams, no core-machinery touch.
  **`actions._constant_stat_sources(ps)`** — the two constant-stat scans
  (`_constant_ability_power_bonus` / `_hp_bonus`) walked only the arenas; they now walk this
  helper, which appends the player's **BASE**, so a base can carry a ConstantAbility ("Each
  leader unit you control gets +0/+1" — Pau City TWI_19 / Petranaki Arena TWI_28; the
  `leader_unit` predicate is a Leader card in an arena).  The undeployed LEADER beside it in
  `base_zone` is deliberately NOT added — a leader's constant stays deployed-only, which the
  arenas-only scan had been giving it for free.  (The keyword-layer scans are untouched: no
  base grants a keyword yet.)
  **`game_memory.units_healed_this_phase` + `actions.note_unit_healed(s, ci, healed)` + the
  `healed_this_phase` target predicate** — a phase-scoped set of unit instance_ids that
  actually had damage removed, fed at the two heal chokepoints (`resolver._apply_heal` and the
  heal flavour of the damage-distribution finish) and only for a real reduction, so "healing"
  an undamaged unit does not count; drives the group aura "Each friendly unit that was healed
  this phase gets +1/+0" (Barriss Offee TWI_42).  A bespoke card-module heal that pokes
  `ci.damage` directly is unmarked (the `note_hand_or_deck_discard` simplification).
  **`Condition.OPPONENT_N_PLUS_UNITS`** — the enemy-side mirror of the Coordinate atom, same
  both-arenas basis (Duchess's Champion TWI_54's conditional Sentinel).
  **`Condition.CONTROLLER_HAS_TRAIT_CARD_IN_PLAY`** — `CONTROLLER_HAS_TRAIT_UNIT` widened to
  each arena unit's attached upgrades, i.e. "a Force unit **or a Force upgrade**" (Padawan
  Starfighter TWI_58).  PURE REUSE: TWI_33 = ONE self-targeted this-phase `GrantKeyword`
  registered under TWO triggers (`WhenPlayed` + `WhenUnitDefeated(friendly)`), the printed
  Sentinel stripped by sanitiser rule 3; TWI_43/45/50/62 = conditional SELF
  KeywordGrant/StatBonus (rule 2) on `CONTROLLER_HAS_OTHER_TRAIT_UNIT` / Coordinate /
  `SOURCE_UNDAMAGED`, plus a `CreateTokenUnit` When Defeated; TWI_50's "heal 1 for each unit
  you control" = a conditional-magnitude `CustomEffect.target` (Zeb LAW_45) routed through
  `_apply_heal` so the Wolffe SOR_160 lock still applies; TWI_51 = `CostReduction` +
  the Constructed Lightsaber LOF_261 upgrade-SELF `KeywordGrant` (the keyword layer's
  attached-upgrade scan confers it on the host and evaluates the condition against that host);
  TWI_56 = an `ActivatedAbility` whose target is narrowed to `damaged` so the cost is never
  spent on a no-op; TWI_67 = `EACH_ENEMY` + `arena="ground"` this-phase `ModifyStats` and a
  `PhaseStartTrigger("regroup")` SELF `Heal`; TWI_70 = the Frozen in Carbonite SHD_193
  `event_ctx["attached_to_id"]` host exhaust.  ⚠️ TEST TRAP: the `_defeat_and_fire` helper homes
  the dying unit in the DISCARD *before* firing, so a `WhenUnitDefeated` whose filter is
  `kind="unit"` cannot match it — drive such a trigger with `actions._defeat_unit` (the same
  gotcha as auras).
- **twi-set:14 combat-tricks batch** — two small additive seams, no core-machinery touch.
  **`push_select_token(token_type=None, power_bonus=, hp_bonus=, duration=)` BUFF mode** — the
  `select_token` decision's payoff is no longer only a token: each chosen unit may instead (or
  as well) take a stat modifier, so the same select-up-to-N flow models "You may choose another
  unit — up to 2 if you have the initiative — give each +2/+2 for this phase" (Kalani TWI_85).
  The trigger stays MANDATORY: the "you may" is the always-legal `FinishSelectToken`, and an
  optional trigger on top of it would prompt twice.  The heuristic bot needs no change (it
  already picks only its own units — beneficial either way).
  **`CostReduction.per_max_opponent_units`** — the opponent-side sibling of Resolute TWI_151's
  `per_controller_base_damage`: reduce by `amount` once for every unit controlled by the
  opponent who controls the most units (two players ⇒ the one opponent's both-arena count),
  read at the same single `_play_cost_reduction` site and floored at 0 by the play path
  (Republic Defense Carrier TWI_98).  PURE REUSE: TWI_71 = the upgrade-SELF `KeywordGrant`
  (Grievous's Wheel Bike TWI_236 — the only path an upgrade's keyword reaches its host, since
  the printed bar on the upgrade never transfers); TWI_73 = targeted `Heal` FIRST then
  `CreateTokenUnit`; TWI_74 = one `CustomEffect.target` applying Sentinel plus an
  initiative-gated `ModifyStats` to the SAME chosen unit (two targeted effects would prompt
  twice and could split); TWI_81 = conditional SELF `KeywordGrant("Ambush")` on
  `CONTROLLER_HAS_OTHER_TRAIT_UNIT` (the Ambush listener reads `has_keyword` once the unit is
  in its arena, so a granted Ambush still fires on entry); TWI_105 = `ActivatedAbility` with
  `[PayResources(2), ExhaustSelf()]` onto `push_granted_attack(power_bonus=2)`.  ⚠️ GOTCHA:
  inside a `CustomEffect`, a sub-effect handed to `execute_effect` must carry a BARE
  `TargetSpec()` — `fixed=SELF` makes it resolve onto the source and silently ignore the
  chosen `target_id`.
- **twi-set:15 combat-tricks batch** — two small additive widenings of existing machinery, no
  core-machinery touch.  **`StatBonus.count="controller_trait_units_<Trait>"`** — a scaling
  constant buff read off the controller's count of units with that trait, the trait riding in
  the count string after the prefix so one arm of `actions._stat_bonus_count` serves any trait
  (Squad Support TWI_122, "+1/+1 for each Trooper unit you control"; effective traits, both
  arenas, the `CONTROLLER_N_PLUS_TRAIT_UNITS` basis, and "each" not "each other" so a matching
  host counts itself).  ⚠️ "You" is the CONTROLLER: for an upgrade-granted buff the source is
  the UPGRADE, whose `owner_id` is whoever PLAYED it, so the arm resolves the seat through
  `find_instance` (which returns the HOST's controller) and falls back to the owner.
  **`_upgrade_target_spec` now parses "Attach to a token unit"** onto the existing `token_unit`
  predicate (Nameless Valor TWI_119) — the same conservative parser widening as `non-leader`,
  so the restriction holds at every attachment site at once.  PURE REUSE: TWI_119/TWI_122 = the
  upgrade-SELF `ConstantAbility` scans (`keywords.has_keyword` for a KeywordGrant,
  `_upgrade_self_stat_bonus` for a StatBonus); TWI_120 = `GrantedAbility(ActivatedAbility)`
  (Heroic Resolve SHD_155) onto `push_play_from_hand(cost_reduction=1)`, gated
  `CONTROLLER_CAN_PLAY_DISCOUNTED_UNIT` so the host's exhaust is never wasted; TWI_129 = a
  fixed `EACH_FRIENDLY` `GrantKeyword("Restore", 2)` PLUS the Pyrrhic Assault TWI_103
  phase-scoped `AuraGrantedAbility` (`phase_aura_sources`) for the granted When Defeated —
  two clauses, two mechanisms, in one two-spec registration; TWI_130 = two conditional SELF
  `ConstantAbility` specs on one `CONTROLLER_HAS_OTHER_TRAIT_UNIT` atom with different params;
  TWI_134 = `OnAttack` `ModifyStats` gated `CONTROLLER_ATTACKED_OTHER_TRAIT_UNIT_THIS_PHASE`;
  TWI_137 = `WhenPlayed` `ReadyCard(SELF)` gated `OPPONENT_MORE_UNITS_THAN_CONTROLLER` (the
  mirror, not the negation — equal counts are not "fewer", which is exactly right).
- **twi-set:16–18 combat-tricks batch** — eight small additive widenings, no core-machinery
  touch, six of them on decisions/triggers that already existed.
  **`push_granted_attack(bonus_per_defender_damage=N)`** — the attacker's bonus scaled by the
  DEFENDER's damage, snapshotted in AttackWithUnit before the combat pipeline runs (so "at the
  start of this attack" is free) and counting a base defender's own damage (Corner the Prey
  TWI_139).  Every prior field scaled on the attacker or gated on the defender's kind/arena;
  this is the first to read a defender QUANTITY.
  **`push_select_token(shared_trait=, ready=, grant_keywords=)`** — three payoffs/filters on the
  select-up-to-N flow: `shared_trait` keeps a running INTERSECTION of the chosen units' effective
  traits so each later pick must still share one ("Choose up to 3 units that share the same
  Trait", Bold Resistance TWI_153 — the first pick is unconstrained, which is what "up to"
  means), while `ready` + `grant_keywords` stack a ready and a duration-scoped keyword on top of
  the Kalani TWI_85 buff mode (Planetary Invasion TWI_178 readies, buffs and grants Overwhelm
  per pick).
  **`WhenEnemyAttacksYourBase(arena=)`** — the SHD_241 observer narrowed to the attacker's arena
  ("When an enemy GROUND unit attacks your base", Aurra Sing TWI_166); None = either arena.
  **`WhenOpponentPlaysCard(paid_less_than_cost=True)`** — fires only on a DISCOUNTED play, read
  straight off the `CardPlayed` event's `cost_paid` vs the printed cost, so it catches any
  discount source (CostReduction, Exploit, smuggle/plot pricing) with no per-source plumbing
  (Lux Bonteri TWI_210).
  **`Condition.OPPONENT_NO_READY_RESOURCES`** — the opponent has no unexhausted resource; in
  two-player the "defending player" IS that opponent, so no attack context is needed (Rush
  Clovis TWI_183).
  **`TokensEnterPlayReady` marker** — a controller-scoped board effect read at the single
  `_create_token_units` seam, so EVERY token that player creates enters ready whatever made it
  (Chancellor Palpatine TWI_203); the standing version of `CreateTokenUnit(enters_ready=True)`,
  mirroring the `CannotAttackBases` marker+scan shape.
  **modal mode `ready_unit`** — the ready sibling of `exhaust_unit`, non-fungible and offered
  only for EXHAUSTED units, so "ready or exhaust a unit" is one `push_modal` (TWI_210).
  ⚠️ NOTE: an "up to N" whose payoff must land on ONE chosen unit needs a single `CustomEffect`
  per pick (Heroes on Both Sides TWI_249 applies +2/+2 AND Saboteur in one fn) — a
  `ModifyStats` + `GrantKeyword` pair would prompt twice and could split them across units.
  PURE REUSE worth knowing: TWI_204 Impropriety Among Thieves and TWI_211 Sly Moore are both
  pure composition of the Change of Heart SOR_224 pair (`actions.change_control` + the one-shot
  `return_control_to_owner_at_regroup` flag swept in `_enter_regroup`) — TWI_204 as a two-unit
  SWAP driven by two shared-`event_ctx` targeted CustomEffects (the LAW_41 pattern, with "if you
  do" as the second fn's guard), TWI_211 narrowed by the `token_unit` predicate; TWI_169 Clone
  Cohort = the two (and only two) upgrade→host paths in one registration, a SELF `KeywordGrant`
  (`has_keyword`'s attached-upgrade walk) plus `GrantedAbility(WhenDefeated)` still collected
  from the DETACHED upgrade at defeat; TWI_185/TWI_186 = resource ready/exhaust as auto-picked
  `CustomEffect`s (resources are fungible and not targetable cards — the SOR_145 convention).
- **twi-set:19–21 misc-abilities batch** — nine small additive widenings plus one correctness
  guard, no core-machinery touch.
  ⚠️ **`undeployed_only` now requires a Leader card_def** (the arena scans in `legal_actions`
  and `resolver._collect_triggers`) — a TOKEN UNIT SHARES ITS (set, number) WITH A REAL CARD:
  the Clone Trooper token IS `TWI_2`, the same registry key as the leader Nute Gunray, and the
  Battle Droid token is `TWI_1` (Nala Se).  `deployed_only` was already safe (a token is no
  deployed leader); `undeployed_only` was not, so a token would have offered the leader's
  undeployed Action from the arena.  Registering ANY ability on a number a token shares still
  leaks non-side-gated specs (constants/markers/plain triggers) onto that token — check
  `_token_unit_def` before registering a low number in a set that prints tokens.
  **`Condition.CONTROLLER_N_UNITS_DEFEATED_THIS_PHASE(param=N)`** — the COUNTING sibling of
  `CONTROLLER_UNIT_DEFEATED_THIS_PHASE` over the same one-entry-per-defeat ledger ("If 2 or more
  friendly units were defeated this phase", Nute Gunray TWI_2); **`CONTROLLER_HAS_DAMAGED_UNIT`**
  — the friendly mirror of `ENEMY_HAS_DAMAGED_UNIT` (TWI_60).
  **`game_memory.pending_exploit_grants` + `_consume_exploit_grant`** — "the next <trait> card
  you play this phase gains Exploit N", the `pending_play_discounts` shape, consumed at the ONE
  Exploit seam in `PlayCard.apply`; the granted value ADDS to the printed one (numeric keywords
  stack) and a card with no printed Exploit gains one (Count Dooku TWI_5 deployed).
  **`push_combined_power_play(trait=, max_units=, cost_reduction_per_unit=)`** — the TWI_89
  select-units-then-play decision gains EXPLOIT PRICING: instead of a free play capped by
  combined power, the chosen units buy 2 resources off a paid play of a matching card, and they
  die only if the play happens (exploiting is part of playing the card, the opposite of TWI_89's
  unconditional "Then, defeat the chosen units") — Dooku TWI_5 undeployed.  DEVIATION:
  `push_play_from_hand` plays units, so a Separatist event/upgrade is not offered.
  **`cannot_attack` Modifier** — an APPLIED attack ban read at `_attack_forbidden` beside the
  printed `AttackRestriction` marker, so it expires with the ordinary duration sweep ("It can't
  attack for this phase", Malevolence TWI_39).
  **`damage_prevention` Modifier** (`amount` / `all` + `combat_only`) — the applied sibling of
  the `DamagePrevention` upgrade marker, read at the same single chokepoint
  `_deal_damage_with_shield` and likewise BEFORE the Shield check (an instance reduced to nothing
  leaves the Shield intact): "prevent 1 of that damage" for this phase (Finn TWI_53) and "prevent
  ALL combat damage for this attack" (Aayla Secura TWI_96).  `_deal_damage_with_shield` gained
  **`is_combat`**, passed by the combat pipelines only, so `combat_only` can tell an ability hit
  from a combat hit.
  **stats-modifier flag `while_attacking_unit_id`** — the applied sibling of the "while
  defending, the attacker gets −N/−0" constant (Lando LAW_108): `compute_power` honours the
  modifier only when that unit is the current combat `defender_id` ("Each enemy unit gets −4/−0
  while attacking that unit this phase", I Have the High Ground TWI_72).
  **modal modes `create_clone_troopers_2` / `create_battle_droids_3`** — a "choose one" with no
  target at all, so both are fungible and resolve on a throwaway proxy (the controller's base, a
  pool that can never be empty) — the Bombing Run SOR_173 arena-mode shape (TWI_102).
  **predicate `fewer_units_than_prior_target_controller`** — a BOARD gate on the follow-up half
  of a two-target effect, reading `event_ctx["prior_target_controller"]` recorded by the first
  fn: failing it yields no candidates so the second half fizzles without prompting, the
  `requires_prior_target` shape ("Then, if you control fewer units than that unit's controller,
  give another unit −2/−2", Equalize TWI_55).
  PURE REUSE worth knowing: TWI_69 Roger Roger ("When Defeated: Attach this upgrade to a
  friendly Battle Droid token") is `WhenDefeatedAsUpgrade` + a relocate-from-discard
  `CustomEffect` — the Luke J25_4 pilot shape, and the ONLY seam that collects an upgrade's own
  trigger when its host dies (a plain `WhenDefeated` on an upgrade is never collected there) —
  with `TargetSpec.names` + the `token_unit` predicate spelling "a friendly Battle Droid token";
  TWI_52's "a unit that entered play this phase" is the existing `played_this_phase` predicate,
  whose ledger `_create_token_units` also feeds, so created tokens qualify as printed.
- **twi-set:22–24 misc-abilities batch (🏁 COMPLETES TWI, 257/257)** — five small additive
  seams plus one correctness fix, no core-machinery touch.
  **`SuppressLeaderAbilities`** marker on a UNIT — the FOURTH source of the unified
  `state.ability_suppressed` read-layer (beside Mind Trick LOF_202's per-instance flag, Galen
  Erso P25_31's name scan and Imprisoned SHD_72's upgrade marker), so "Each leader loses all
  abilities … and can't gain abilities" (Brain Invaders TWI_255) turns off keywords, trigger
  collection, the constant-stat scans, the arena action enumeration and the TraitGrant scan for
  BOTH players' leaders at once, deployed or not, and lifts when the unit leaves play.  The
  "except for EPIC ACTIONS" carve-out lives at the ONE seam offering an undeployed leader's own
  actions (the `legal_actions` leader loop skips a suppressed leader's non-`epic`
  ActivatedAbility only); deploying IS the Epic Action and never routes through the registry,
  so a leader can still deploy.  ⚡ The scan is gated on a lazily-built registry index of the
  (set, number) keys carrying the marker (`state._suppress_leader_keys`) — `ability_suppressed`
  sits on hot stat/keyword paths, so an ungated per-unit ability walk there costs real time.
  **`BasesCannotHeal`** marker on a UNIT — the STANDING, in-play-scan version of Wolffe
  SOR_160's phase-scoped `bases_cannot_heal_this_phase` lock, folded into the same single
  `actions._bases_cannot_heal` predicate every base-heal chokepoint already consults, so it is
  symmetric as printed (it stops the controller's own Restore too) and lifts on leave-play
  (Confederate Tri-Fighter TWI_132).
  **`cannot_be_attacked` Modifier** — an APPLIED "can't be attacked" read at the single
  attack-enumeration seam `_cannot_be_attacked`, beside Sabine Wren TWI_195's printed
  `CannotBeAttackedWhileExhausted` marker and sharing its Sentinel escape; it expires with the
  ordinary duration sweep ("Attached unit can't be attacked this phase (unless it has
  Sentinel)", On Top of Things TWI_219, the host located via `event_ctx["attached_to_id"]`).
  **`CreateTokenUnit(player=)`** — "controller" (default) / "opponent" / "each", the DrawCards
  convention, so a drawback clause can make the OPPONENT create tokens under their own control
  ("An opponent creates 2 Battle Droid tokens", Jesse TWI_145).
  **`push_pay_resources_for_tokens(payoff="token_units", token_unit_name=,
  opponent_token_unit_name=)`** — a third payoff on the existing pay-any-number decision: TOKEN
  UNITS for the controller and (optionally) for each opponent, one each per resource paid,
  tallied through `paid` and created at RESOLVE like the damage payoff, so each token's
  enter-play bus lands on a clean stack (The Clone Wars TWI_125).
  ⚠️ **FIX: `_resolve_exploit_commit` now threads `cost_paid`** into `_put_unit_in_play` — it
  was the ONE play path that didn't, so a When Played reading `event_ctx["cost_paid"]` saw None
  on any Exploit card.  The value is the POST-Exploit amount actually exhausted, which is
  exactly "the number of resources paid to play this unit" (Osi Sobeck TWI_115, whose capture
  ceiling is the Yoda TWI_4 "record then gate" shape: a leading CustomEffect stashes
  `cost_le_threshold`, then a `CaptureUnit` narrowed by `cost_le_event_threshold`).
  PURE REUSE worth knowing: TWI_135 Darth Maul = a bare `MultiDefenderAttack(count=2)` (the
  primitive built for C24_6); TWI_116 Clone ("enter play as a copy of a non-leader, non-Vehicle
  unit … it gains the Clone trait and is not unique") is a card-module `dataclasses.replace` of
  the chosen unit's own frozen `card_def` — printed stats/traits/aspects/keywords AND (since
  `get_abilities` is keyed on set+number) its printed abilities all come along, the instance_id
  is untouched so conservation holds, and the instance is relocated if the copy belongs to the
  other arena; TWO DOCUMENTED NARROWINGS — the copy resolves just after entry so the copied
  card's own When Played does not fire, and a serialisation round-trip rebuilds from `card_id`,
  losing the added Clone trait and the non-unique flag.  TWI_176 = the LAW_41 shared-`event_ctx`
  chain (`same_arena_as_event` + `excludes_event_target` + `requires_prior_target`) with the
  TWI_156 record-then-apply trailing effect for "all damage is dealt simultaneously"; TWI_205 =
  SOR_212's `while_attacking` ConstantAbility under a Coordinate gate; TWI_225 = a CustomEffect
  computing a whitelist and handing it to `push_play_from_hand(eligible_ids=, cost_reduction=5)`
  — `eligible_ids` is a general hand filter, not discard-only, so "a non-Vehicle unit that shares
  a Trait with the unit you control" needs no new field; TWI_227 = the Take Captive SHD_131
  captor/prey pair with a conditional token rider; TWI_250 = two fixed `EACH_FRIENDLY`
  `GrantKeyword`s narrowed by their own trait (a Trooper-Jedi picks up both, as printed).
- **jtl-set:01–03 direct-damage batch** — one new observer trigger plus seven small additive
  widenings, no core-machinery touch.
  **`WhenUnitHealed`** observer trigger — "When 1 or more damage is healed from this unit"
  (Silver Angel JTL_62).  The settle-drain shape (`WhenPlayerDiscardsFromHand` SHD_163
  verbatim): a queue `game_memory.heal_events` is fed from the ONE heal chokepoint
  `actions.note_unit_healed` — which already ignores bases and no-op heals, so an entry IS
  "1 or more damage healed" — and drained by `actions._fire_heal_observers` at the action
  settle-point, so the observer resolves on a clean stack.  Strictly self-referential
  (`event_ctx["healed_unit_id"]` vs the source's own id), unlike the any-player discard
  observer.  A bespoke card-module heal that pokes `ci.damage` directly still does not fire it.
  **`game_memory.traits_played_this_phase` + `Condition.CONTROLLER_PLAYED_TRAIT_CARD_THIS_PHASE`**
  — the TRAIT-typed sibling of `CONTROLLER_PLAYED_OTHER_CARD_THIS_PHASE`, recorded beside the
  play COUNTER at the same `CardPlayed` chokepoint (at play time, because an event is already
  in the discard by the time the condition is read); any card type counts, which is what "a
  First Order CARD" means (Captain Phasma JTL_10).
  **`Protection.upgrade_only`** — "THIS UPGRADE can't be defeated by enemy card abilities"
  (Luke Skywalker JTL_12), as against Chewbacca JTL_103's default both-ways reading: it covers
  the card ONLY while the card itself is attached, so it protects neither Luke-as-a-deployed-unit
  nor the Vehicle he is riding.  ⚡ `_card_grants_self_protection` takes the
  is-the-target-attached test as a LAZY CALLABLE — `_target_protected` sits on the hot
  damage/defeat path, so the board walk must only run for the handful of cards carrying such a
  Protection.
  **`resolver._is_leader_unit`** — the shared basis of the mutually exclusive `leader_unit` /
  `non_leader` predicates now also counts an ordinary unit carrying a LEADER attached as a Pilot
  upgrade.  Every deploy-as-an-upgrade leader prints "Attached unit is a leader unit" (Boba Fett
  JTL_9, Asajj JTL_1, Luke JTL_12), so a leader-piloted Vehicle is now correctly out of reach of
  "Defeat a non-leader unit" removal and inside a "each leader unit you control" aura.
  **`Condition.CONTROLLER_HAS_OTHER_TRAIT_CARD_IN_PLAY`** — the self-excluding sibling of
  `CONTROLLER_HAS_TRAIT_CARD_IN_PLAY`, widened to base_zone so an UNDEPLOYED leader satisfies
  "another Resistance card (unit, upgrade, or **leader**)" (Raddus JTL_104).
  Three predicates + one count: **`not_upgraded`** (the complement of `upgraded`; a Shield or
  Experience TOKEN counts as an upgrade, so a shielded unit survives Nebula Ignition JTL_80),
  **`opponent_no_space_units`** and **`controller_more_space_units_than_target_controller`** (both
  BOARD gates in the `fewer_units_than_prior_target_controller` TWI_55 shape — failing yields no
  candidates so the effect fizzles with no prompt; the latter read PER CANDIDATE is what ties
  "that opponent" to the same player in both halves of Air Superiority JTL_125's sentence), and
  **`DealDamageEqualTo count="source_controller_space_units"`** (Resistance Blue Squadron JTL_102).
  ⚠️⚠️ **JTL_1 SHARES ITS (set, number) WITH THE TIE FIGHTER TOKEN** — the live case of the known
  collision.  Asajj Ventress is registered ONLY from specs a token can never reach:
  `ActivatedAbility(undeployed_only=True)` (the leader-card_def guard), `GrantedAbility` (the
  arena trigger scan skips it — it is no `TriggerAbility`) and `WhenDeployed(via_pilot_leader=True)`
  (matched by instance id against a `LeaderDeployed` event).  A `ConstantAbility` or a passive
  marker would NOT be safe: the constant-stat and keyword scans walk arena units by (set, number)
  with NO leader gate.  So her "It gains Grit" is a PERMANENT `keyword_grant` modifier applied
  from the deploy-as-an-upgrade trigger — not the usual `ConstantAbility(SELF, KeywordGrant)` —
  which also gets the right lifetime for free (`_permanent_kw_source_in_play` counts an attached
  upgrade as in play, so the grant lapses the moment she detaches).  Note `cards/reprints.py`
  (`REPRINT_ALIASES`) does NOT help here: it solves the mirror problem (copying a registration
  ONTO a duplicate face) and explicitly excludes token types.
  PURE REUSE worth knowing: JTL_121 Salvage = `push_play_from_hand(from_discard=True,
  eligible_ids=…, then_damage=1)` — `from_discard` alone offers hand AND discard, so
  "from your discard pile" is spelled with a computed `eligible_ids` whitelist (the TWI_225
  pattern); JTL_120 Dorsal Turret = `GrantedAbility(WhenDealsCombatDamageToUnit)` + a `DEFENDER`
  DefeatUnit, i.e. Rukh SOR_85 verbatim (that trigger already means "while attacking", and fires
  only when BOTH combatants survive); JTL_147 Black One's "control Poe Dameron as a unit, upgrade,
  or leader" is `CONTROLLER_CONTROLS_NAMED` unchanged (it already scans base_zone, both arenas and
  every attached upgrade); JTL_1/JTL_10/JTL_55/JTL_127 are all the shared-`event_ctx` "If you do"
  chain (a targeted CustomEffect stamps `prior_target_id` — and for Asajj `same_arena` — and the
  follow-up is gated by `requires_prior_target`/`same_arena_as_event`).
- **jtl-set:04–06 direct-damage batch** — seven small additive widenings, no core-machinery
  touch, six of them on machinery that already existed.
  **`push_assign_indirect_damage(then_draw_if_base=, then_ready_source_if_base=,
  then_exhaust_damaged=)`** — three "then_*" riders settled at the decision's single resolve
  point, where it is known what the receiving player actually hit: "If a base is damaged this
  way, draw a card" (Tactical Heavy Bomber JTL_152) / "…ready this unit" (Guerilla Soldier
  JTL_218) / "Exhaust each unit damaged this way" (Kimogila Heavy Fighter JTL_222).  The
  decision assigns the whole amount to ONE target, so "each unit" is at most one — and a unit
  the damage defeated is no longer in an arena to exhaust.  All three inert by default.
  **`push_select_damage(arena=, enemy_only=, then_attack_with=)`** — the select-up-to-N damage
  decision gains two candidate narrowings ("each of up to 2 units **in this arena**", Twin Laser
  Turret JTL_172, where resolving from a `GrantedAbility` makes the host's own arena the answer;
  "a different **enemy** unit", Hotshot Maneuver JTL_174) and an attack rider: the named unit's
  `push_granted_attack` fires at RESOLVE, so "Then, attack with the chosen unit" happens AFTER
  the damage — pushing both up front would resolve them LIFO, i.e. backwards.
  **`_stat_bonus_amount(…, target_ci)` + `StatBonus.count="target_damage"`** — the first count
  read off the BUFFED unit rather than the buff's source, so an aura can scale per recipient
  ("Each enemy non-leader unit gets −1/−0 **for each damage on it**", Radiant VII JTL_226); the
  optional param is threaded at all four constant-stat call sites and every other count ignores
  it.  Plus **`StatBonus.count="damaged_units_in_play"`** (War Juggernaut JTL_170 — "each
  damaged unit" is unqualified, so BOTH players' damaged units count, the source included),
  **`DealDamageEqualTo count="source_controller_hand"`** (the source-side mirror of the
  long-standing `target_controller_hand` — Rebellious Hammerhead JTL_153), and
  **`Condition.CONTROLLER_NO_OTHER_TRAIT_UNIT`** (the exact negation of
  `CONTROLLER_HAS_OTHER_TRAIT_UNIT`, sharing its source-excluding scan: "If you control no other
  Fighter units", Crackshot V-Wing JTL_158 — failing it means the trigger is never collected, so
  there is no prompt and no no-op).  PURE REUSE worth knowing: JTL_148 Frisk / JTL_168 Insurgent
  Saboteurs = `DefeatUnit(kind="upgrade")` (+ `cost_max`, + the Boba Fett JTL_189
  `WhenPlayed(as_upgrade=True)` Piloting flag); JTL_173 Fight Fire With Fire = the Haymaker
  LAW_168 shared-`event_ctx` chain (`same_arena` stamp → `requires_prior_target` +
  `same_arena_as_event`) with the TWI_156 record-then-apply trailing hit, so "If you do" costs
  nothing when the pair can't be made; JTL_175 System Shock = resolve the host through
  `_find_upgrade_host` BEFORE `_defeat_attached_upgrade` detaches it; JTL_180 Piercing Shot =
  `tokens.defeat_shield` in a loop then ordinary damage (shields first is the whole card);
  JTL_219 Rafa Martez = ONE targeted `CustomEffect` doing both clauses (the Kylo SHD_141 shape)
  with the resource ready auto-picked (SOR_145 fungible convention).  ⚠️ DEVIATION: Trench Run
  JTL_156 grants its attacker a one-shot "On Attack" ability; the mill + unpreventable recoil
  (via `_apply_indirect_damage`, the shield-bypassing path) are resolved BEFORE
  `push_granted_attack` instead — outcome-equivalent, except a Fighter killed by its own recoil
  never declares the attack rather than fizzling mid-combat.  ⚠️ `_upgrade_target_spec` still
  declines trait DISJUNCTIONS ("Attach to a Capital Ship **or** Transport unit", JTL_227) — its
  traits are ANDed, so it leaves the restriction open rather than forbid a legal host.
- **jtl-set:07–09 direct-damage & card-advantage batch** — six small additive widenings plus one
  new decision kind (`reveal_cull_draw`, its own catalog row above), no core-machinery touch.
  **`StartingHandModifier(amount, no_mulligan)`** marker on a BASE — the first spec that touches
  GAME SETUP.  The standard 6-card opening hand is shifted by the marker on that player's base
  ("Draw 1 less" Colossus JTL_21 / "Draw 3 more … You can't take a mulligan" Nabat Village
  JTL_28), read through the one helper `actions._starting_hand_size` at the three seams that
  already knew the number 6 — `create_game`'s opening draw, `TakeMultiligan.apply`'s redraw, and
  the SETUP_MULLIGAN branch of `legal_actions` (which drops `TakeMultiligan` for a `no_mulligan`
  player; KeepHand is always offered, so nobody is ever stuck).  Passive, per-player, and a no-op
  for every base without it (the `ExtraRegroupPhase` shape).
  **`PhaseStartTrigger(first_only=)` + `actions._fire_action_phase_start_triggers`** — the
  ACTION-phase mirror of the long-standing `_enter_regroup` fire site (Contracted Hunter JTL_216),
  called from BOTH action-phase entries (`_start_action_phase` and the round rollover) with the
  `PhaseChanged` event the log already carries, so `first_only` picks round 1 out of the event
  itself ("When the first action phase starts: put 3 cards from your hand on the bottom of your
  deck" — JTL_28, onto the existing `bottom_from_hand` decision).  Purely additive: no card
  registered `PhaseStartTrigger("action")` before this batch.
  **`push_deck_search(then_play_free_cost_max=N)`** — settled at the DRAW branch of
  `_finish_deck_search` (after the decision is popped, so the play lands on a clean stack): a
  drawn card costing ≤N is whitelisted into a free `push_play_from_hand` ("…and draw it.  If it
  costs 2 or less, you may play it for free" — The Invisible Hand JTL_89).  DEVIATION:
  play_from_hand has no decline, so the inner "you may" collapses to mandatory; the outer one is
  the search's own `up_to=True`.
  **`push_granted_attack(draw_if_base_damaged=)`** — instead of granting a temporary trigger, the
  attack site snapshots every base's damage before combat and draws for the attacker's controller
  if the attack put anything on one, settled at the `then_defeat_attacker` rider point ("For this
  attack it gets +2/+0 and gains: 'When this unit deals damage to a base: Draw a card'" — Stay on
  Target JTL_177).  Because it compares damage rather than the chosen defender, an Overwhelm
  spill onto the base counts exactly as printed.
  **`TargetSpec.kind="unit_upgrade"`** — a UNIT card currently riding as a Pilot upgrade, i.e. the
  only attached card with stats to stand up with ("Detach a Pilot upgrade, move it to the ground
  arena as a unit" — Eject JTL_126, whose fn is a deliberate MOVE not a play: no cost, no
  `CardPlayed`, no When Played).  Enumerated from the same `attached_upgrades` scan as
  `kind="upgrade"` (whose card-def isinstance check excludes a Piloting unit); a printed Upgrade,
  a token, and a LEADER deployed as a Pilot are all out (the last a documented narrowing).
  **Three condition atoms**: `ANY_OF(param=(ConditionCheck, …))` — the DISJUNCTION sibling of
  `ALL_OF`, evaluated in the same recursive branch, for a clause that is an OR ("If you played a
  Bounty Hunter **or** Pilot card this phase" — Mist Hunter JTL_186; one ability per disjunct
  would draw twice when both hold); `CONTROLLER_HAS_HAND_CARD_COST_MIN(param=N)` (Admiral Trench
  JTL_14's Action, so its Exhaust is never spent on a guaranteed no-op); and
  `CONTROLLER_HAS_UNIQUE_TRAIT_CARD_IN_PLAY(param=trait)` — `CONTROLLER_HAS_TRAIT_CARD_IN_PLAY`'s
  basis (both arenas, every attached upgrade, plus base_zone so an undeployed leader counts)
  narrowed to the <uq> symbol (Invincible JTL_191).
  PURE REUSE worth knowing: JTL_41 Annihilator = ONE targeted `CustomEffect` under both
  `WhenPlayed` and `WhenDefeated` that reads the victim's NAME *before* `_apply_defeat_unit`
  (the JTL_175 ordering rule), sweeps that name out of the controller's hand AND deck, and
  reshuffles with `make_rng` so the purge leaks no ordering; JTL_48 Cassian = `GrantedAbility(
  OnAttack)` (never collected while he is a unit, which IS the "attached unit gains" reading);
  JTL_98 Snap Wexley = the `WhenPlayed(as_unit=)` / `WhenPlayed(as_upgrade=)` split onto
  `NextPlayDiscount(units_only=False)` and `push_deck_search(window=5, up_to=False)`; JTL_134
  Hux = a `KeywordGrant("Raid", 1)` anthem plus an Action gated
  `CONTROLLER_PLAYED_TRAIT_CARD_THIS_PHASE`; JTL_194 Heartless Tactics = the Kylo SHD_141
  one-`CustomEffect` shape (exhaust + `_make_modifier(-2/0, THIS_PHASE)` + a `compute_power`
  re-read gating `_apply_return_to_hand`); JTL_239/248 = plain `DealDamage` (`damaged` predicate /
  `fixed=SELF`).  ⚠️ Admiral Trench's third line is an Epic Action DEPLOY ("3 resources, Exhaust:
  if you control 6+ resources, deploy this leader") — deploying never routes through the ability
  registry, so he deploys at his printed cost like every other leader.
- **`AuraGrantedAbility` wrapping an `ActivatedAbility` + `UseAbility.actor_id`** — an aura that
  grants an **Action** to every unit matching its target, the many-actors analogue of the
  upgrade-granted Action (Heroic Resolve SHD_155, where the single host is derivable from the
  source).  One source arms MANY units, so the actor cannot be derived: `UseAbility` gains an
  optional **`actor_id`** — `source_id` addresses the spec, `actor_id` the unit using it — and a
  new aura scan in `legal_actions` offers it once per matching unit the ACTIVE player controls
  (sources gathered once, actor loop skipped entirely when no aura is in play).  The grant is to
  "each unit", so the source may be an ENEMY card: the ownership guard checks the ACTOR's
  controller, `ExhaustSelf`/`DefeatSelf` fall on the actor, effects resolve from the actor, the
  once-per-round key is actor-scoped, and the aura's `target` is re-checked at apply time.
  `describe()` must name the actor (the web/replay layers disambiguate same-kind actions by it).
  Satine Kryze TWI_47 — "Each unit (including enemy units) gains: 'Action [Exhaust]: …'".
  (twi-set:07)
- **`CreateTokenUnit(name, count, enters_ready)`** — Battle Droid TWI_1 / Clone Trooper
  TWI_2; tokens excluded from conservation, cease to exist on leave-play. (ahsoka:05)
- **`CreateCreditToken`** — Credit economy: `PlayerState.credits` pile + `Zone.CREDITS`;
  spend is **need-based/automatic** via `_pay_play_cost` (covers a shortfall only). (jabba:07)
- **`return_control_to_owner_at_regroup`** — one-shot CardInstance flag swept in
  `_enter_regroup` (twin of Commandeer JTL_235's `return_to_owner_hand_at_regroup`, but
  reverts CONTROL via `change_control` back to the owner rather than bouncing to hand):
  "Take control of a unit; at the start of the regroup phase its owner takes control of
  it." No new decision kind, no core-resolution change. (Change of Heart SOR_224, sor-set:20)
- **shd-set:09 card-advantage batch** — two small additive seams, no core-machinery touch:
  **`game_memory.cards_discarded_this_phase` ledger + `note_hand_or_deck_discard(s, ci)` helper
  + `Condition.SELF_DISCARDED_THIS_PHASE`** — a phase-scoped set of instance_ids discarded from a
  hand or deck this phase, fed at the self-discard / mill sites (the `DiscardFromHand` effect arm,
  the discard decisions — repeated_modal / discard_excess / discard-a-hand-card / Echo's
  discard-for-experience — and the deck-search `discard` disposition); read by the condition
  (evaluated against the discard-pile instance itself) to gate Kylo's TIE Silencer SHD_135's
  `PlayFromDiscardAction` ("If this unit was discarded from your hand or deck this phase, play it
  from your discard pile"). Bespoke one-off discards not routed through those sites are unmarked (a
  documented simplification). **`ConstantAbility.while_attacking_bounty_unit`** — like
  `while_attacking_unit` but the StatBonus applies only while the target attacks a unit that HAS A
  BOUNTY (compute_power checks the threaded `defender_id` via `resolver._unit_has_bounty`); any
  KeywordGrant it also carries is reported always by the keyword layer (the Moff Gideon SHD_7
  simplification — Jango Fett SHD_138 "+3/+0 and gains Overwhelm while attacking a Bounty unit").
  Same batch (pure reuse): Jango's "attacks and defeats a unit: draw" = `OnAttackDefeatsUnit`
  (First Light SEC_88); Death Mark SHD_176 = the Price on Your Head SHD_125 GrantedAbility bounty
  drawing 2; Pillage SHD_181 = `DiscardFromHand(chooser="opponent", count=2)`; Cripple Authority
  SHD_156 / Bo-Katan SHD_157 = CustomEffect scaling reads (resource comparison / bases at ≥15).
- **shd-set:10 card-advantage batch** — one small additive seam + one search-and-play extension:
  **`discard_from_hand_at_regroup`** — a per-instance INT counter swept in `_enter_regroup` (the
  `defeat_at_regroup` / `return_to_owner_hand_at_regroup` delayed-flag family): the unit's controller
  discards that many hand cards at regroup start (first-card simplification, then the counter clears);
  skipped if the unit has left play (documented deviation). Scheduled per-attack by Zorii Bliss
  SHD_203 ("On Attack: Draw a card. At the start of the regroup phase, discard a card from your
  hand"). **`push_search_and_play`** gained `eligible` (narrow the searched-for units, e.g. "a
  Vehicle"), `enters_ready`, and `return_at_regroup` (reuse the Commandeer delayed-return flag for
  "enters play ready. Return it to hand at the end of the phase") — Triple Dark Raid SHD_194; threaded
  through the existing `deck_search`→`disposition="play"` branch, no new decision kind. Same batch
  (pure reuse): Omega SHD_198 = `push_deck_search` eligible=Clone (Greef Karga SHD_245); A New
  Adventure SHD_207 = return-then-`owner_may_replay`-free (Rio Durant LAW_93); Criminal Muscle SHD_209
  = `ReturnToHand` non_unique upgrade; Frontier Trader SHD_214 = return a resource + `_resource_top_of_deck`
  ramp; Xanadu Blood SHD_191 = optional return + auto-exhaust best enemy unit ("or resource" narrowed;
  exhaust target auto-picked — documented). Omega's per-round "ignore aspect penalty on your first
  Clone" is a deferred cost-waiver residual (the Darksaber SHD_126 kind).
- **`CreateForceToken` / `UseForce` cost / `CONTROLLER_HAS_FORCE_TOKEN`** — the Force
  token is a per-player boolean (max 1), not a card. (qui-gon:06)
- **`DealDamageEqualTo(target, count)`** — scaling magnitude read per target. Counts:
  `target_controller_hand`, `source_controller_discard_distinct_costs`,
  `source_controller_units_in_target_arena`, `target_remaining_hp_minus_1`,
  `source_controller_resources` (Devastator SOR_90). (shd:08)
- **`WhenDealsCombatDamageToUnit(non_leader_only)`** — attacker-side mirror of
  `WhenDealtCombatDamage`: fires for the ATTACKER after it deals combat damage to a
  still-in-play defender unit (`attacker_dealt_combat_damage_to_unit` key + `defender_id`
  for a `DEFENDER` target). Rukh SOR_85 "defeat that unit".
- **`push_distribute_heal` (heal flavour of `distribute_damage`)** — "Heal up to N total
  from any number of units and/or bases, then deal that much to this unit" (Redemption
  SOR_52). Reuses the pool machinery (`heal`/`include_bases`/`self_damage_source_id` ctx
  keys, `_heal_distribution_targets`, a `heal` branch in `_finish_distribution`) so the
  existing AssignDamage/FinishDamageDistribution actions + web prompt + bot handler cover
  it — no new decision-kind registration.
- **`WhenOpponentPlaysCard(card_type)`** — observer trigger firing for an in-play card when
  an OPPONENT plays a card of `card_type` (matched at the `CardPlayed` chokepoint, like
  `WhenOpponentPlaysNthCard`). Models an "additional cost for an opponent to play an event"
  as an after-the-fact effect (Saw Gerrera SOR_153 "deal 2 to their base" — base damage is
  always payable, so the observer yields the same board state; documented simplification).
- **`WhenBountyCollected`** — settle-drain observer ("when YOU collect a bounty"), built on the
  exact `WhenYouUseForce`/`WhenYouRevealOrDiscard` pattern. Tag every bounty WhenDefeated with
  `TriggerAbility.is_bounty=True`; `resolver.fire_triggered_abilities` records one
  `GameMemory.bounties_collected` entry (collector_id + bounty registry coords +
  defeated_controller_id) per collected bounty, drained at the settle-point by
  `actions._fire_bounty_observers`. The re-collection payoff re-runs that exact bounty via a
  fresh `resolve_effects` decision (`actions.push_bounty_recollect`) — NO new decision kind;
  once-per-round via `Condition.SOURCE_BOUNTY_RECOLLECT_AVAILABLE` +
  `GameMemory.bounty_recollect_used_this_round`. Plus a `has_bounty` target predicate
  (`resolver._unit_has_bounty`). Bossk SHD_10.
- **`pay_resources_for_tokens` damage payoff** — `push_pay_resources_for_tokens(payoff=
  "damage", damage_per, damage_target_id)`: pay any number of resources, tally, and deal
  `damage_per`×paid to a target at resolve (pop-then-deal). Force Lightning SOR_138 (paired
  with the `abilities_suppressed` read-layer for "loses all abilities this phase"). Same
  decision kind — no new registration.
- **`_ability_can_inline` refinement** — a no-target `CustomEffect` that precedes a
  currently-targetless targeted effect now forces the decision path (it may arm that target
  via `event_ctx`, e.g. Force Throw SOR_167 discards→arms `requires_prior_target`). The
  inline fast-path only ever *defers* to the always-correct resolve_effects path, so a
  mandatory "leading side-effect then gated target" event now resolves in order.
- **`CONTROLLER_HAS_LEADER_UNIT` condition** (a deployed leader in an arena, any trait) +
  **`ground_or_base` predicate** (kind="unit_or_base": a base, or a ground-arena unit).
  Jedha Agitator SOR_158.
- **`TraitGrant`** + `traits.get_traits/has_trait` — effective traits (printed +
  granted); scans attached upgrades AND arena-wide granters. (Foundling SHD_69, Malakili LAW_212)
- **`CaptureUnit`** + `_apply_capture`/`_release_captured_cards` — capture pile reuse.
  (The Mandalorian's Rifle SHD_251)
- **`AttackRestriction(condition)`** / **`EntersPlayReady(condition)`** / **`Protection`** /
  **`IndirectDamageBonus`** / **`ConditionalFirstStrike(defender_spec)`** — passive markers
  read at an existing seam (add to `soak.py`'s passive-marker tuple so they aren't false
  zero-fires). (Oggdo Bogdo LOF_63, Salacious Crumb LAW_210, Chewbacca JTL_103, Hunting
  Aggressor JTL_165, Hound's Tooth JTL_185)
- **`ReadyRestriction` on an attached upgrade** — `_ready_forbidden` now also scans a unit's
  `attached_upgrades` for a `ReadyRestriction` (condition `None` = always), evaluated against
  the host, so an upgrade can forbid its host from readying (holds through every regroup).
  (Frozen in Carbonite SHD_193; the upgrade also exhausts its host via a WhenPlayed CustomEffect
  reading `event_ctx["attached_to_id"]`)
- **`TargetSpec.names=(…)`** — "a unit named X" filter in `_spec_matches_ci` (matches `card_def.name`,
  no subtitle); drives name-anthem StatBonus/KeywordGrant auras. **`TargetSpec.power_max_count`** —
  DYNAMIC power cap: effective power ≤ a count computed from board state
  (`"enemy_units_upgrade_count"`). (4-LOM SHD_188 / Zuckuss SHD_190 name-anthems; Slaver's
  Freighter SHD_189 ready-power-cap)
- **`NextPlayDiscount` / `CostReduction.host_named`** — deferred / host-conditional cost
  reduction (PlayCard path only). (Khetanna LAW_158, Grievous's Wheel Bike TWI_236)
- **`StatBonus.count`** — scaling constant buff (`other_friendly_pilots`,
  `pilots_on_self`). (Nien Nunb JTL_93, Millennium Falcon JTL_249)
- **`AdditionalPilotSlots`** — relaxes the leader-deploy-as-upgrade Pilot cap. (JTL_249/JTL_245)
- **`ConstantAbility.while_target_defending`** — mirror of `while_defending`: the StatBonus
  applies to its TARGET only while that target is itself the current combat defender
  (compute_power threads `is_defending` for the defender). "While a friendly unit is
  attacking, the defender gets −1/−0" (Jyn Erso SOR_18 deployed, target = enemy unit).
- **`ConstantAbility.while_attacking`** — attacker-SCOPED variant of `while_target_defending`:
  the StatBonus applies to its target only while the *source* is the current combat attacker
  (`compute_power`/`_constant_ability_power_bonus` thread a new `attacker_id`, passed only when
  computing the defender's combat power). "While THIS unit is attacking a ground unit, the
  defender gets −2/−0" (Strafing Gunship SOR_212, target = enemy ground unit).
- **`CrossArenaAttack`** marker — the carrier may attack enemy units in the OTHER arena. Read at
  `actions._can_attack_other_arena` (widens `_enumerate_attacks`' eligible-defender set + relaxes
  the `AttackWithUnit` cross-arena apply-guard); base/same-arena attacks unaffected. (Strafing
  Gunship SOR_212, a space→ground attacker.)
- **control-linking upgrade** — an upgrade takes control of its host on play and the owner reclaims
  it when the upgrade leaves play. REUSES `control_linked_to` + `_revert_linked_control` (Maul
  LAW_54's leave-play control-revert), now also fired from the two upgrade-removal chokepoints
  (`_apply_defeat_unit` / `_apply_return_to_hand` attached-upgrade branches). WhenPlayed sets
  `change_control` + `control_linked_to`; no new trigger kind. (Traitorous SOR_122.)

### Keyword mechanics (full notes in `docs/history/encoding_history.md` Part 2)

Coordinate (`CONTROLLER_N_PLUS_UNITS`, ahsoka:01) · Plot (deploy-triggered deck-replace,
jabba:01) · Hidden (attack-target filter, jabba:02) · Bounty (WhenDefeated "opponent
collects" template, shd:02) · Smuggle (resource-zone play + deck-replace, shd:01) ·
Piloting (unit-as-Pilot-upgrade, boba:01) · **Support** (enter-play/deploy granted attack
by another unit + a borrowed-abilities read layer, ash-set:01 — the LAST engine keyword).
The durable keyword-query/token/effective-stats reference is under **Phase 2 additions**
below.

### The escalation rule (protects the frozen engine)

A small self-contained primitive (a new effect dataclass + resolver arm, or a new decision
kind) may land inline with synthetic-card tests. Anything touching **core resolution**, the
**trigger/decision machinery**, or needing a **replacement-effect system** must STOP and be
flagged for a dedicated framework session — never jammed into a card batch. The planner
pre-flags suspected new primitives as their own one-card groups. Current outstanding
escalations: **LOF_197 Aethersprite** (duplicate-the-next-WhenPlayed). (The three SOR
escalations — SOR_122 Traitorous, SOR_177 Bib Fortuna, SOR_212 Strafing Gunship — were
cleared in a dedicated framework session 2026-07-25; their seams are catalogued above:
control-linking upgrade, `play_event_from_hand`, `CrossArenaAttack` + `ConstantAbility.while_attacking`.
The two shd-set:01 escalations — SHD_10 Bossk (bounty re-collection) + SHD_17 Lando
(Smuggle-as-effect) — were cleared in a framework session 2026-07-25; seams catalogued above:
`WhenBountyCollected` settle-drain observer + `is_bounty` tag + `push_bounty_recollect`, and the
`play_via_smuggle` decision kind.)

## Bug reporting & two-way messaging (completed — 2026-07-01)

An in-app way for players (any whitelisted user) to file bugs from
any screen on the iPad, and for the maintainer — via Claude, **out of band** — to answer, ask
for more detail, or mark them resolved. Two-way threaded messaging with an admin
triage surface inside the existing AdminPanel. Full design/plan:
`docs/bug_reporting_plan.md` (staged 1–5, all landed); the reusable triage prompt
the maintainer pastes to process a report: `docs/bug_triage_prompt.md`.

**Where reports live (the on-disk contract for out-of-band Claude processing).**
One folder per report under `data/bug_reports/`, resolved via
`swu.web.paths.data_dir` so it lands in the right instance and survives deploys
(`deploy.ps1` mirrors code only, never `data/`). Players use the **deployed** copy,
so real reports land in `swu-game-deployed/data/bug_reports/`; DEV testing writes to
`swu-game/data/bug_reports/`.
```
data/bug_reports/
  <id>/                 # id = "<YYYY-MM-DD>-<hhmm>-<slug>"
    thread.json         # conversation + form fields + context + status
    screenshot.png      # best-effort; may be absent
    game.json           # replay bundle; only for reports filed from a game screen
  archive/<id>/         # same shape; the maintainer moves finished threads here
```
The initial report is the first message (carries `title`/`expected`/`actual`);
replies carry `text`. The dev/automated side signs messages `from: "claude"`; a
reporter's inbox renders anything not their own as **"Dev Team"** (hides the
helper). "Unread for X" = any message where X ∉ `read_by`.

**The TWO independent "done" concepts (never conflate them).**
- **Reporter housekeeping** — a cosmetic `reporter_archived` flag on the thread; lets a
  reporter tidy their *own* inbox. **Never moves folders.**
- **Admin decluttering** — the maintainer moving a finished thread's folder from
  `bug_reports/` into `bug_reports/archive/` (disk-level triage). Independent of
  the reporter's view.
- **Critical rule:** status changes NEVER move folders. The reporter inbox reads
  from **both** directories, so the maintainer can archive a folder to drop it from
  the triage list without hiding anything from the reporter.

**Status lifecycle** `new → needs_info ↔ (reporter replies) → investigating →
resolved`. AdminPanel triage derives three buckets from status + last-sender (see
`BugStore._bucket`): **NEEDS YOU** (`new`, or reporter replied last) is the maintainer's
worklist — the ones to prompt Claude with; **WAITING ON REPORTER**; **RESOLVED**.

**Code.** Backend `src/swu/web/bugs.py` (`BugStore` + Pydantic models) + routes in
`app.py` (`/api/bugs*` for reporters, `/api/admin/bugs*` admin-gated; token→user via
the `/api/auth/me` machinery). Adding a reporter = adding a username to `ALLOWED` in
`auth.py`. Frontend `web/` — `ReportBug`/HUD (capture-then-open, `html-to-image`),
`BugInbox` (reporter), `BugTriage` inside `AdminPanel` (opens `game.json` in the
existing `ReplayViewer` via `/api/replay`). Tests: `tests/` (BugStore + routes,
multi-user rule, inbox spanning both dirs) and `web/tests/` (bugs.test.tsx).

## Phase 6B status (completed — 2026-06-15): LLM opponent

The **Normal** and **Hard** opponents now play via a small Claude model behind
the bot factory; **Easy stays a pure heuristic and never calls the API**. The
engine, HTTP routes, and `advance_bot`'s shape are unchanged — only the `Player`
instance behind `session.bot` differs, plus a tiny web seam for the fallback
notice (below).

**The player (`src/swu/players/llm_player.py`):**
- `LLMPlayer(player_id, *, fallback, style, model=None, client=None, timeout=None,
  max_tokens=256)` satisfies the `Player` protocol (`choose_action(view, legal)
  -> Action`). `style` is a `Style` enum (`CASUAL` for Normal, `COMPETITIVE` for
  Hard; coerces from strings). `client` is injectable for tests (a fake
  Anthropic client) — production lazily constructs `anthropic.Anthropic()`.
- **Decision flow:** (1) skip the API for forced/trivial choices —
  `len(legal) == 1` returns immediately, logged "auto" at debug. (2) Build a
  compact request and force a single `choose_action` **tool call**
  (`tool_choice={"type":"tool","name":"choose_action"}`) with params
  `action_id` + short `reasoning`. (3) Validate: require `stop_reason ==
  "tool_use"` and an `action_id` that maps to a legal action. (4) **One retry**
  with a corrective note if the id was illegal/missing. (5) **Fallback** to
  `self.fallback.choose_action(view, legal)` on any error/timeout/truncation/
  parse-failure/illegal-twice — logged in detail **and** surfaced in the in-game
  log (see seam). `stop_reason != "tool_use"` (incl. `max_tokens` truncation) is
  treated as a failure — we never parse a partial tool call.
- **Model & cost levers:** default `claude-haiku-4-5` (smallest fast tier, $1/$5
  per 1M tok — confirmed against the official reference, not memory). Override
  via the `model=` arg or **`SWU_LLM_MODEL`** env var (so Hard can point at a
  stronger model with no code change); per-call timeout via `timeout=` or
  **`SWU_LLM_TIMEOUT`** (default 20s). The **static rules brief is the `system`
  block, marked `cache_control: ephemeral`** for prompt caching (note: Haiku's
  minimum cacheable prefix is 4096 tokens, so the brief may sit just under the
  threshold — `usage.cache_read_input_tokens` is logged so you can confirm).
  Per-game token/cost counters via `usage_summary()`.
- **Hidden info:** the prompt is built **only** from this player's redacted
  `PlayerView` (`_serialise_view`), never the raw `GameState`. Opponent hand is
  already `[]`, resources are `[hidden]` stubs; the opponent block carries no
  `hand` key. Card rules text is looked up from `data/swu.db` by `card_id`
  (best-effort; redacted `card_id == -1` skipped). Asserted by
  `test_prompt_has_no_hidden_opponent_cards`.

**The fallback-notice seam (web layer, not the engine):** `LLMPlayer` buffers a
`FallbackNotice` dataclass whenever it drops to the heuristic; `GameSession.
advance_bot` drains them (`bot.drain_notices()`) and interleaves them into the
returned event batch just before each action's events. They serialise through
the existing `event_to_model` (`type="FallbackNotice"`) and the frontend log
(`web/src/game/format.ts`) renders `data.message` — so a heuristic takeover is a
**visible** "Opponent fell back …" line, not debug-only. A no-key/no-SDK
*configuration* condition is announced once (not per decision) to avoid spam.

**Logging:** rotating `data/llm.log` (logger `swu.llm`) records every call's
outcome (auto / success / retry / fallback), latency, token counts,
`stop_reason`, and the full reason + truncated raw response on failure.

**Factory (`src/swu/players/difficulty.py`):** the single wiring point — only
the NORMAL/HARD branches changed (Normal → `LLMPlayer(fallback=HeuristicBot,
style=CASUAL)`, Hard → `LLMPlayer(fallback=HeuristicBot(sharp_targeting=True),
style=COMPETITIVE)`); EASY is untouched. The 6B LLM is **not deterministic** —
keep it out of the soak/determinism oracle (soak the heuristic fallback).

**Tests (`tests/test_llm_player.py`):** all use a **mocked** client (no network).
Cover valid-choice, illegal-then-valid-retry, illegal-twice → fallback+notice,
`max_tokens` truncation → fallback, API exception → fallback, timeout → fallback,
malformed/no-tool-call → fallback, forced choice → **no API call**, hidden-info
absence, full mocked games for both styles with engine invariants intact, and
**Easy makes zero API calls**. A `conftest.py` autouse fixture strips
`ANTHROPIC_API_KEY` for every non-`live` test so the **default suite is fully
offline even on a dev machine with a key set**. One opt-in `@pytest.mark.live`
smoke test hits the real API — run with `pytest --live` (skipped otherwise).
`anthropic>=0.40` is now a project dependency.

## Phase 5 status (completed — 2026-06-13): Local Web UI

A polished local web client for playing Luke vs Vader against the WeightedBot.
**Thin client over the frozen engine** — the frontend computes no rules; it
renders `view_for`, shows the legal actions the backend labelled, and animates
the event stream. Engine untouched (no `src/swu/engine/` changes this phase).

**Backend — `src/swu/web/` (FastAPI):**
- `app.py` routes: `POST /api/games`, `GET …/state`, `GET …/actions`,
  `POST …/actions/{action_id}`, `POST …/advance`, `DELETE …/{id}`,
  `GET /api/decks`, `GET /api/cards/{card_id}/image?face=front|back`.
- `session.py` — `GameSession` owns one `GameState`, assigns opaque action ids
  (`a0`, `a1`, …) for the human's current decision point, validates a human
  action against freshly-computed `legal_actions`, and drives the bot seat.
  `SessionStore` holds games in memory (no persistence this phase).
- `models.py`/`serializers.py` — Pydantic payloads mirroring `PlayerView`, with
  `image_url` and action `label`/`params` added. OpenAPI at `docs/openapi.json`
  (regenerate: `python -m swu.web --export-openapi docs/openapi.json`).
- `cards.py` — images served by the **unique DB `card_id`** (not set/number,
  which collides between a Leader and its Token).
- Run: `python -m swu.web` (binds `127.0.0.1`; `--host 0.0.0.0` for LAN).
- Tests: `tests/test_web_api.py` — redaction-on-the-wire invariant, image
  serving, invalid action_id rejection, and a **full game played to a winner
  entirely over HTTP**. Web deps: `pip install -e ".[web]"`.

**Key seams / contracts:**
- **Action-id seam.** The frontend references actions *only* by the backend's
  `action_id`; it never constructs an `Action`. Illegal/invented actions can't
  cross the wire.
- **Event→animation contract.** Each `apply`/`advance` returns the `event_log`
  delta it produced. The UI plays these through a skippable queue (decorative
  effects) while Motion handles card travel/entrance/defeat. The UI **animates
  the event stream; it does not diff state.**
- **apply vs advance.** Separate endpoints on purpose: the frontend animates the
  human action's events, then calls `advance` to fetch the bot's events as a
  second batch (the backend's `advance` loops bot turns until human/terminal).
- **LLM-player seam (Phase 6).** Opponent selection now goes through the bot
  factory `make_opponent` (see Phase 6A below); `SessionStore.create` calls it
  with the requested `Difficulty`. The bot only needs
  `choose_action(view, legal) -> Action`.

**Frontend — `web/` (React + Vite + TS):** see `web/README.md`. `src/game/`
holds `useGame` (state + interruptible queue) and `interaction.ts` (maps the
engine's fully-enumerated actions to clicks). Tests: `npm test` (vitest) +
`npx playwright test` (e2e smoke). Manual QA: `docs/ui_qa.md`.

## Heuristic bot — play-quality overhaul (2026-08-31)

A measurement-first pass over the heuristic opponent, prompted by "it often plays
stupid moves that even improve the opposition". Two new harnesses, four real
defects fixed, and the combat weights re-tuned against evidence rather than taste.
**Every claim below is a measurement, and both harnesses are kept so the next
change can be judged the same way.**

### The two harnesses (use these before touching a weight)

- **`scripts/bot_arena.py`** — head-to-head strength. Round-robin over the 16 real
  precon deck fixtures; every (deck pair, seed) job plays **four** games — A on
  each seat *and* piloting each deck — so seat advantage and deck strength cancel
  exactly and the residual is bot skill. Prints a 95% interval. Two identical bots
  score 49–50%, which is the calibrated null.
  Bots: `heuristic`/`hard`/`easy`, `easy:<rate>`, `w:<WEIGHT=v,...>` (a
  per-instance weight variant — the form for comparing two candidate tunings
  *against each other*), and `baseline`/`baseline_easy`, the frozen pre-overhaul
  bot in **`benchmarks/heuristic_baseline.py`** (outside `src/` on purpose: a
  measurement artefact, loaded by path, never imported by application code).
  `SWU_BOT_TUNE="W_ATTACK_BASE=6"` patches the live module in each worker for a
  quick sweep against the fixed baseline.
- **`scripts/bot_blunders.py`** — a census of *named* misplays, which is what tells
  you WHY a change helped. At every decision it recomputes ground truth from the
  registry + the live state and counts: `buff_enemy`, `harm_self`,
  `upgrade_enemy`, `suicide_attack`, `whiff_attack`, `fizzled_event`. Each counter
  only fires when the better alternative was demonstrably legal, so a non-zero
  count is a real misplay, not a difference of taste.
  ⚠ Two traps this harness itself hit, worth remembering for any board analysis:
  a card's side is **control** (whose row it sits in), not `owner_id` — comparing
  owners reported control-change cards as blunders; and combat maths must use
  `compute_power`/`compute_hp`, never `ci.effective_power()`, or real attacks are
  mis-scored.

Blunders per game over 200 games, before → after:

| | old Normal | new Normal | old Easy | new Easy |
|---|---|---|---|---|
| buff_enemy | 0.30 | **0** | 0.31 | **0** |
| upgrade_enemy | 0.05 | **0** | 0.07 | **0** |
| suicide_attack | 0 | **0** | 0.59 | **0** |
| whiff_attack | 0.02 | **0** | 0.07 | 0.04 |

Strength, all over paired games against the frozen pre-overhaul bot:
**Normal 66.6% ± 2.7** (1200 games), **Easy 51.6% ± 3.5** (800 games — deliberately
unchanged, see below), and the Normal-over-Easy difficulty gap is **84.5%**.
Validated with the fast tier (5634 passed), the medium soak tier, and a 400-game
`scripts/soak.py` campaign driven by the changed bots (`--bots heuristic,easy,hard
--decks starter,vanilla,keyword`): **400 ok / 0 failed**, invariants clean, seat
win rate 52.8/47.2, report in `docs/history/soak_bot_overhaul.md`.  Games are shorter
(mean 9.5 → 6.5 rounds) — the base-race weighting doing its job.  ⚠ That report's
"zero-fire active ability" banner is PRE-EXISTING, not a regression: a control
campaign with the untouched `random,weighted` bots flags the same category.

### The four defects

1. **⭐ The bot could not see effective stats or keywords.** `CardView` reported
   `ci.effective_power()` — printed power plus attached upgrades *only* — and
   `card_def.keywords`, the printed bar. Anthems, duration modifiers, Grit and
   every granted keyword were invisible. Measured over real games: **4.5% of arena
   cards showed the wrong power, 2.2% the wrong HP, 6.6% were missing a keyword
   they had** (Raid, Sentinel, Saboteur, Grit, Ambush, Overwhelm). This was wrong
   for *every* consumer of the view — the web UI's stat line and the LLM prompt as
   much as the bot. Fixed in `views._effective_stats_and_keywords`, applied to
   cards **in an arena** only (out of play there are no modifiers, and the
   constant scans walk the arenas, so printed values are already the truth
   elsewhere). ⚡ Asking `has_keyword` all 16 keywords per card made a view ~4x
   dearer, so `views._grantable_keywords` collects once per view which keywords
   anything on this board could grant and each card checks only
   `printed ∪ grantable` (`None` = "cannot narrow", for a keyword-copy aura or a
   Support borrow). Net cost ~18%. **`test_view_effective_stats.py` pins the
   narrowing by agreement**: over a real game the view's keyword list must equal
   the engine's own per-keyword answer, card for card. `CardView.keyword_values`
   carries the numeric keywords (Raid/Restore/Exploit) because Raid is a
   while-ATTACKING bonus `effective_power` does not include.
2. **⭐ Targeting guessed polarity from which targets were offered.** The old rule
   was "enemy targets exist ⇒ it must be removal", so a heal / token / buff /
   ready landed on the OPPONENT's best unit. **155 registered abilities carry a
   beneficial targeted effect with `controller="any"`**, so the engine really does
   offer both sides. The decision context names the ability and effect index, so
   the bot now reads the effect out of the registry and classifies it
   (`_effect_polarity`): helpful → a friendly (most damaged for a heal, best
   exhausted for a ready, best unit otherwise), harmful → an enemy, and with only
   the wrong side available it **declines** rather than gifting or self-harming.
   Unknown polarity (an opaque `CustomEffect`, a net-neutral stat change) keeps
   the old guess. ⚠ `_ability_effects` FLATTENS ConditionalEffect branches, which
   shifts every index — use `_ability_raw_effects` when lining up with the
   decision's `effect_idx`.
3. **Upgrade "is this a gift?" read stats only.** 16 unrestricted upgrades in the
   DB grant a keyword, a trait or a whole ability with **no** stat change
   (Foundling, Squad Support, Nowhere to Hide), and every one of them classified
   as safe to hand to the opponent. `_upgrade_helps_host` now consults the
   registry: positive stats or any gift/granted spec ⇒ friendly; a Bounty (whose
   payoff the host's opponent collects) or a card built only from drawback markers
   ⇒ enemy; unclassifiable ⇒ assume it helps the host, so we hold it rather than
   gift it. Measured DB-wide the split is 124 positive-stats / 16 statless-helpful
   / 13 bounty / 4 drawback / 4 negative-stat, and the classifier gets all of them
   right. ⚠ `_is_enemy_buff` keyed on the action CLASS (`PlayCard`), but **six**
   actions play an upgrade onto a chosen host (PlayCard, PlayFromDiscard,
   SmugglePlay, PlotPlay, PlayTopCard, PlayViaSmuggle) — five slipped through, so
   it now keys on the `upgrade_target_id` field. The same four extra play routes
   were scoring a flat 0.0 and now route through `_score_play_card`.
4. **Easy's blunder branch picked uniformly at random.** ~0.6 suicidal attacks per
   game — a unit thrown into a defender that killed it for nothing with the enemy
   base sitting there attackable. That reads as broken, not as an easy opponent.
   It now plays "the best coherent move, minus the best": actions the bot refuses
   outright (below Pass) and self-destructive attacks are excluded, the top choice
   is dropped, one of the rest is taken at random. `_EASY_MISTAKE_RATE` 0.25 →
   **0.35** so the difficulty is unchanged (51.6% vs the old Easy over 800 paired
   games) — same beatability, sane moves.

### Combat weights — base damage was badly undervalued

Damaging the base is the win condition and, unlike attacking a unit, costs
nothing: no damage comes back. `W_ATTACK_BASE` 4.0 → **8.0**, plus
`BASE_RACE_URGENCY` 2.0 — a base attack scores
`W_ATTACK_BASE * power * (1 + URGENCY * pressure)` where pressure runs 0 → 1 as
the enemy base falls from 30 HP, because the points that finish a game are worth
more than the first chip. Also new: **Overwhelm spill** (excess past the
defender's remaining HP is credited at exactly what those points are worth on the
base, and counts toward lethal — the bot can now see a lethal line *through* a
blocker) and **Raid** in attack power.

The evidence, all with everything else held identical:
- swept 3 → 24 against the frozen baseline; a broad plateau 7–16 (63–67%), so
  8.0 was taken from the middle rather than the noisy argmax;
- **head-to-head, the tuned weights beat the old ones 61.5% ± 3.4** over 800
  paired games, and beat a deliberately control-tuned variant (cheap base damage,
  expensive trades) **60.2%**;
- four neighbouring configs all tie with the chosen one, i.e. it sits on a
  plateau and further weight fiddling has no measurable return.

⚠ `HeuristicBot(weights={...})` is what makes those head-to-heads possible —
per-INSTANCE weights (`TUNABLE_WEIGHTS`), so two differently-tuned bots play in
one process. Patching module constants can only ever measure "beats the previous
bot", which is not the same question.

### Checked and found clean (do not re-investigate)

- `fizzled_event` — events played with no legal target: **0 per 200 games**. The
  detector is verified to fire (Vanquish SOR_78 on an empty board), so this is a
  real zero, not a broken counter.
- `harm_self` — 0 before and after; the existing self-harm guards were already
  doing their job.

### Latent issue, deliberately not touched

`AttackWithLeader` scores off the view's `effective_power` (the *deployed* power)
while the engine deals `card_def.leader_power`. Every leader in the DB has
`leader_power == 0` and `legal_actions` only offers the action when it is `> 0`,
so it is unreachable dead code today. If a leader ever ships with a real
undeployed attack, the bot will over-estimate it and can claim a false lethal —
the fix is to surface `leader_power` on the base-zone `CardView`.

## Phase 6A status (completed — 2026-06-15): Heuristic opponent + difficulty system

A strong, transparent heuristic opponent, a three-level difficulty system, and a
start-screen selector — built so Phase 6B can drop in an LLM opponent by editing
**one function**. Full 6B handoff: `docs/phase6b_llm_handoff.md`.

**The bot factory — the extension point (`src/swu/players/difficulty.py`):**
- `Difficulty` enum (`EASY`/`NORMAL`/`HARD`; `str`-mixin so it serialises as its
  value; `Difficulty.coerce(x)` → unknown/empty defaults to `NORMAL`).
- `make_opponent(difficulty, *, player_id, seed=None, rng=None) -> Player` returns
  a `Player`-protocol bot. **6A: every level maps to `HeuristicBot`** — Easy with
  `mistake_rate=0.25`, Normal vanilla, Hard with `sharp_targeting=True`. **6B
  edits only the NORMAL/HARD branches** to return `LLMPlayer(fallback=heuristic,
  style=…)`; **EASY must stay a pure heuristic forever (never hits the API).**
  Nothing else in the backend/UI knows which bot kind it got.

**The heuristic (`src/swu/players/heuristic_bot.py`):**
- `HeuristicBot(player_id, *, rng=None, seed=None, mistake_rate=0.0,
  sharp_targeting=False)`. Implements `choose_action(view, legal) -> Action` as a
  pure function of the **`PlayerView`** + legal actions + its own RNG — no engine
  internals, no hidden state.
- Transparent **weighted rules** (named constants at the top of the file), not
  search: score every legal main-phase action and play the best (RNG tiebreak).
  Resourcing/curve, on-curve unit development valued by stat-efficiency+keywords,
  favourable-trade combat, base-chip/racing, **lethal recognition**, sensible
  leader deploy (discounted round one), mulligan keep/redraw, and a handler for
  **every** pending-decision kind. Anything unhandled → safe default.
- `choose_action` is wrapped to **never raise** (`_safe_default`), so it is a
  bulletproof 6B fallback.
- **Easy variant**: `mistake_rate` → that fraction of the time it plays a random
  legal action (beatable by a child, still coherent). **Hard**: `sharp_targeting`
  → removal/effects aim at the biggest threat / the unit it can finish.
- **Never buff the opponent (all levels).** `_score_play_card` scores a
  *beneficial* upgrade (net-positive `upgrade_power`/`upgrade_hp`) attached to an
  enemy unit below Pass, so the bot holds it rather than handing the opponent a
  free buff. Net-neutral/downside upgrades on enemies stay playable (the only time
  hosting an enemy unit is correct). Needed two public stat fields on
  `CardView`/`_card_view` (`upgrade_power`/`upgrade_hp`) since an upgrade-in-hand
  reports `effective_power == 0`; the web serializer ignores the extra dict keys.
- **Easy mistakes never self-harm.** `mistake_rate`'s random branch
  (`_random_mistake`) only fires at the *main-phase* layer (legal contains
  `Pass`); forced sub-decisions (target selection, damage distribution, modal)
  always resolve via `_preferred`, so Easy can never e.g. randomly aim its own
  Darth Vader ability damage at its own base. Enemy-buff plays are also filtered
  out of the random pool (`_is_enemy_buff`).
- **Won't use abilities that can only self-harm.** `_ability_forces_self_harm`
  looks up the ability spec (`get_abilities`) and refuses an ability/optional
  trigger when a harmful mandatory targeted effect (`DealDamage`/`DefeatUnit`/
  `ExhaustCard`/`ReturnToHand`/`RevokeKeyword`) with `controller="any"` has no
  enemy target on the board but does have a friendly one (so the choice would be
  forced onto a friendly — e.g. Darth Vader's "deal to a unit" with no enemy
  units). Conservative: only judges "plain" specs (unit/base kind, optional
  arena, predicates limited to `not_self`/`non_leader`, no trait/cost/HP/aspect
  filter); anything it can't evaluate from the view → no opinion (ability stays
  usable). Wired into `UseAbility` scoring (→ below Pass) and the `AcceptTrigger`
  branch (→ `DeclineTrigger`). Needed public `set_code`/`card_number` on
  `CardView` so the `UseAbility` path can find the source's ability spec (the
  `trigger_option` decision context already carries them).
- **Ability damage is attributed in the log.** `DamageDealt` gained an optional
  `source_name`; the resolver's `DealDamage` and `_deal_damage_with_shield` thread
  the source card's name through, so the web log reads "… takes N damage from
  Darth Vader." (combat damage leaves it None — the attacker is already clear from
  `AttackDeclared`). Rendered in `web/src/game/format.ts`. Note `AbilityTriggered`
  /`AbilityEffectApplied` events exist but are still never emitted.
- Public `cost` was added to `CardView`/`CardModel` (views.py + serializer + TS)
  so the bot can reason about curve/resourcing; it's public info.

**Backend wiring:** `NewGameRequest.difficulty: str = "normal"` →
`SessionStore.create(..., difficulty=...)` → `make_opponent`. `GameSession.bot`
is now typed `Player` (any bot). Seed plumbing preserved: `(seed, difficulty,
decks)` replays deterministically for the heuristic (the 6B LLM will not be
deterministic — see handoff §8).

**Start screen (`web/src/components/NewGameScreen.tsx`):** Easy/Normal/Hard
radio selector with one-line blurbs, default **Normal**, persisted to
`localStorage` (`swu.difficulty`) and restored on load (garbage → Normal). Passed
as `difficulty` in the create-game request.

**Engine robustness fixes (surfaced by the new bot / made the fallback
bulletproof):**
- `legal_actions` exploit branch now offers `ExploitCommit` **only when committing
  is affordable now** (else committing would raise; the player must sacrifice
  more — auto-commit at max sacrifices is always affordable by the PlayCard gate).
- `ContinueAttack` now calls `_expire_modifiers(s, "this_attack")` on its
  fizzle paths (attacker/defender left play during pre-attack triggers) — fixes a
  stale `this_attack` modifier leaking into a settled state (1 soak invariant
  failure at seed 447; regression covered by the heuristic soak).

**Tests:**
- `tests/test_heuristic_bot.py` — winning trade, lethal on base, avoid losing
  trade, Sentinel-only targeting, leader deploy when sensible, resource the least
  useful card, mulligan keep/redraw, highest-value target, Hard threat targeting,
  full-game-every-choice-legal robustness, Easy never-raises, factory mapping,
  determinism.
- `tests/test_web_api.py` — a playable game to completion over HTTP for **each**
  difficulty, default-when-omitted, and garbage-difficulty fallback.
- `web/tests/newgame.test.tsx` — selector renders, defaults Normal, posts the
  value, persists to / restores from `localStorage`, garbage → Normal.
- Robustness soak: `python scripts/soak.py --games 500 --bots heuristic
  --decks starter,vanilla,keyword` — 0 exceptions, all invariants hold.
- Win-rate sanity (`python scripts/bot_winrate.py`, 200 games/matchup, seats &
  decks alternated): **Heuristic 100% vs WeightedBot**, **Hard 88% / Normal 87%
  vs Easy**, **Hard 52% vs Normal** (sharp-targeting edge only, as designed).
  Soak bot pool gained `heuristic`/`easy`/`hard`.

## Phase 1 status (completed)

Vanilla rules engine: full game loop from shuffle to win, headless, fully tested.

## Phase 4 status (in progress — 2026-06-12)

Industrialised soak testing: invariant module, bot zoo, parallel campaign runner,
replay and shrink tools, regressions directory.

**Triage session (2026-06-13) — engine bugs found by the 10k campaign and fixed:**
- **State-based defeat sweep.** `apply()` now calls `_sweep_defeated_units()`
  after every action settles (no pending decisions): any arena unit with
  `damage >= compute_hp` is defeated, to a fixed point. Combat/direct-damage
  already defeated units at the point of dealing damage; the sweep is the
  catch-all for the OTHER way a unit becomes lethal — its effective HP *drops*
  (a buff source leaves play, a duration modifier expires, an upgrade is
  removed). All 148 soak invariant failures were this. Regression:
  `tests/regressions/test_defeat_sweep_on_buff_removal.py`.
- **`WhenDefeated` self-triggers.** `_defeat_unit()` removes the unit from its
  arena before firing `UnitDefeated`, so `_collect_triggers()` (which scans
  cards in play) never saw the unit as a source for its own WhenDefeated. Now
  `_defeat_unit()` passes the defeated instance via `event_ctx["defeated_ci"]`
  and `_collect_triggers()` includes it as a WhenDefeated source. Fixed
  Admiral Motti (226), Yoda (45) showing zero firings. Regression:
  `tests/regressions/test_when_defeated_self_trigger.py`.
- **Ability-coverage tracking.** Opt-in observer hook in
  `swu.abilities.resolver.set_ability_observer(fn)` fires from `execute_effect`
  (the universal chokepoint for Trigger/Activated/Event abilities). Default
  None → resolver stays pure/deterministic. `soak.py` installs it per game and
  `_analyse_ability_coverage()` classifies registered abilities into fired /
  zero-fire-active / passive-constant. Constant abilities are passive (read via
  `compute_power`/`has_keyword`, never routed through the resolver) so a 0
  count is expected; escape-hatch `[]` stubs cannot fire by design.

**Verification pass (2026-06-13) — third 10k campaign clean; one new bug found:**
- Campaign: 10,000 games, **0 failures / 0 cap-hits / 0 invariant violations**,
  no failure bundles. Distributions sane (seat win 51/49, rounds mean 10.9, no
  action kind at zero). See `docs/soak_report.md`.
- **Upgrade `WhenPlayed` self-triggers never fired.** An upgrade lives in its
  host unit's `attached_upgrades`, so `_collect_triggers` (which scans only
  `_cards_in_play` = the arenas) never saw a played upgrade as a trigger source.
  Surfaced by ability coverage: Luke's Lightsaber (SOR_53) and Vader's Lightsaber
  (SOR_136) — both implemented and in starter decks — sat at zero firings across
  10k games. Fix: `_collect_triggers` special-cases the `UpgradePlayed` event
  (mirrors the `UnitDefeated`/`defeated_ci` case), locating the upgrade by
  `event.instance_id` and collecting its `WhenPlayed` triggers. Regression:
  `tests/regressions/test_upgrade_when_played_trigger.py`. The other 8 zero-fire
  actives are all confirmed `escape_hatch=True` deferred stubs.

**Determinism triage (2026-06-13) — 30 `nondeterministic` failures, first 10k
campaign with the determinism oracle active; both root causes were randomness
drawn OUTSIDE the seeded RNG:**
- **Global `random.shuffle`.** SOR_84 (Grand Moff Tarkin) and SOR_123 (Recruit)
  reorder the deck bottom "in a random order"; they built `state.make_rng()` but
  called the *global* `random.shuffle` and saved an unadvanced `rng_state`, so the
  reorder forked between same-seed runs and downstream draws diverged the whole
  game. Fixed to `rng.shuffle(...)`. These were the only two `random.` call sites
  in `src/`.
- **`uuid.uuid4()` modifier ids.** Modifiers were stamped with `uuid4()` ids
  (os.urandom), so a game ending with a surviving modifier serialised differently
  each run. Replaced with a deterministic, serialised counter
  `GameState.alloc_modifier_id()` (`_next_modifier_id`); all modifier-construction
  sites use it. Regression: `tests/regressions/test_determinism_seeded_replay.py`.

**New files:**
- `src/swu/engine/invariants.py` — unified per-action invariant checker
- `src/swu/players/weighted_bot.py` — biased toward playing/attacking
- `src/swu/players/aggro_bot.py` — always attacks base when possible
- `src/swu/players/chaos_bot.py` — prefers rarest action kinds seen this game
- `scripts/soak.py` — parallel campaign runner (CLI, spawn-safe on Windows)
- `scripts/replay.py` — deterministic failure replayer
- `scripts/shrink.py` — delta-debugging action-history minimiser
- `tests/regressions/` — permanent regression tests (one file per soak-found bug)

**Test suite tiers:**
- **fast** — unit + per-card tests, every commit:
  `pytest tests/ --ignore=tests/test_engine_soak.py --ignore=tests/test_hypothesis_engine.py -q`
- **medium** — soaks + the Hypothesis stateful machine (both use the invariants
  module); run before/after PRs:
  `pytest tests/test_engine_soak.py tests/test_hypothesis_engine.py -q`
- **campaign** — manual/overnight, 10k+ games across bot × deck matrix:
  `python scripts/soak.py --games 10000 --jobs 8`

  NOTE: `tests/test_hypothesis_engine.py` (Hypothesis `RuleBasedStateMachine`)
  must be excluded from the fast tier — it drives full games and runs ~30–45s.
  It is the *search/shrink* counterpart to the random-bot campaign: it runs the
  full invariant checker after every legal action and auto-shrinks any
  counterexample to a minimal action sequence.

**Campaign runner CLI:**
```bash
# Quick smoke (1000 games, 4 cores)
python scripts/soak.py --games 1000 --jobs 4

# Full overnight campaign (starter + vanilla decks, all bots)
python scripts/soak.py --games 10000 --jobs 8 --decks starter,vanilla,keyword

# Replay a failure bundle
python scripts/replay.py failures/<bundle>.json --verbose

# Minimise a failure bundle
python scripts/shrink.py failures/<bundle>.json --timeout 120 --verbose
```

**Campaign statistics (added 2026-06-13) — catching the bugs invariants can't:**
- **Effect efficacy.** A per-effect observer (`resolver.set_effect_observer`,
  fired from `execute_effect`) records, per ability, how many targets each
  *targeted* effect actually resolved and its nominal magnitude — so an ability
  that "fires" but never hits a target (a targeting/wiring bug) is visible, not
  hidden behind the fire count. Report flags **fired-but-whiffed** abilities
  (a targeted effect with 0 total targets) once they have fired ≥
  `_WHIFF_MIN_FIRED` (20) times — below that a 0 is small-sample noise (e.g.
  Snowspeeder SOR_244 "exhaust an enemy Vehicle ground unit" legitimately whiffs
  when the board has no target).
- **Determinism oracle.** `--determinism-sample N` (default 50) re-plays every
  Nth game from scratch with the same seed/bots/decks and asserts an identical
  fingerprint (winner + canonical state JSON, event_log excluded). Directly
  targets the non-determinism class already hit once (sorted-set serialisation).
  A mismatch is written as a `nondeterministic` failure bundle.
- **Near-cap warning.** Games running ≥90% of the action cap are flagged even if
  none hit it — a latent slow loop.
- **Anomaly banner** at the top of `docs/soak_report.md`: seat win rate outside
  35–65%, mean rounds outside 5–40, any fired-but-whiffed ability, near-cap
  games, non-determinism, and the zero-fire-active list. Empty banner = clean.

**Invariant module (`src/swu/engine/invariants.py`):**
```python
from swu.engine.invariants import CheckContext, check
ctx = CheckContext.from_state(initial_state)   # once per game
check(state, ctx)                               # after every apply()
```
Checks: card conservation by instance_id, damage ≥ 0, no defeated units in
arenas (after settled), zone-tag consistency (each ci.zone matches its list;
covers resource placement) + exhaust sanity (no exhausted cards in DECK/HAND),
token attachment, decision stack validity, modifier durations, initiative/phase
fields, legal_actions non-empty, hidden-info in view_for(), JSON round-trip
every 50 actions. Unit-tested in `tests/test_invariants.py`.

**Semantic + gap-fill invariants added 2026-06-13** (catch *rules* bugs, not just
bookkeeping corruption — the structural checks above would never have caught the
upgrade-trigger bug):
- **Modifier expiry** — no `this_attack` modifier in a settled state (no pending
  decisions); no `this_round` modifier surviving a round rollover (ctx tracks
  `prev_round`/`prev_this_round_mod_ids`). `this_phase` is deliberately NOT
  checked: the engine has no `_expire_modifiers("this_phase")` step.
- **Phase-scoped GameMemory** — `units_played_this_phase` /
  `villainy_played_this_phase` must be empty immediately after a round rollover.
  Checked at the round boundary, NOT "outside ACTION": `clear_phase()` runs at
  the REGROUP→ACTION rollover (`actions/turn.py`, `_regroup_rollover`), so the fields legitimately
  persist through REGROUP and are only read during ACTION.
- **Upgrade zone == host zone** — every attached upgrade carries its host's zone tag.
- **Pass consistency** — `passed_players` holds valid indices; no settled ACTION
  state with both players passed. (We do NOT assert "active player not passed" —
  the engine may transiently hold `active_player_index` on a passed player.)
- **Terminal quiescence** — a terminal state offers zero legal actions (the loop
  must stop on a win).

These were validated false-positive-free across a 200-game all-deck soak before
landing; getting them right took two iterations (the first naive "memory empty
outside ACTION" and "active not passed" forms were false positives — see the
clear-at-rollover and transient-active-player notes above).

**Bot zoo:**
| Class | Description |
|---|---|
| `RandomBot` | Uniform random (existing) |
| `WeightedBot` | Biased toward PlayCard/Attack/Deploy |
| `AggroBot` | Always attacks base when possible |
| `ChaosBot` | Prefers rarest action kinds seen this game |

All bots: `choose_action(view: PlayerView, legal: list[Action]) -> Action`

---

## Phase 2 status (completed — 2026-06-11)

All Tier 1 and Tier 2 keywords implemented and tested.

**Implemented:** Sentinel, Overwhelm, Raid, Ambush, Restore, Saboteur, Shielded,
Grit (Tier 1) + Exploit (Tier 2) + Smuggle + Plot + Hidden + Coordinate + Bounty +
Piloting + **Support** (Phase 7, see below).
Shield and Experience token system. Pending decision stack. Effective-stats layer
(`compute_power`). Full CR attack pipeline.

**Deferred:** nothing — every printed SWU keyword is modelled engine-side as of
ash-set:01 (Support), so `audit_coverage.PHASE3_KEYWORDS` is empty. Card text
abilities and triggered effects are the ordinary campaign work.

The detailed implementation notes for each Phase-2 keyword (Coordinate, Plot, Hidden,
Bounty, Smuggle, Piloting) were moved to **`docs/history/encoding_history.md` (Part 2)** to keep
this file lean. One-line summaries are in the "Keyword mechanics" row of the Engine
seams & patterns catalog above; the durable keyword-query / token / effective-stats
reference is under **Phase 2 additions** below.

---

## CR reference

The Comprehensive Rules are the rules authority for this engine. They are the
publisher's copyrighted document and are NOT redistributed here — download the
current version from https://starwarsunlimited.com/rules and keep it locally
(`docs/` is a good spot; the PDF is gitignored).

**CR deviations / confirmed rules vs. prompt:**
- Non-leader units enter play **exhausted** (CR 2.3.4.b / "A unit enters play
  exhausted"; the Ambush keyword exempts specific units). **A deployed leader is
  the exception — it enters the ground arena READY** (CR: "Flip him, ready him,
  and move him to the ground arena"), so it can attack the round it deploys.
  `DeployLeader.apply()` sets `exhausted = False`; a `True` here is the bug fixed
  2026-06-16. Regression: `test_deploy_leader_places_in_arena`.
- Empty-deck draw penalty: **3 damage per undrawn card** to that player's own base
  (implemented in `_draw_cards`; verify exact amount against latest CR).
- Defeated deployed leader returns to base zone, resets damage to 0, `epic_action_spent`
  stays True (cannot redeploy). Verify with CR.
- Aspect penalty: +2 per unmatched aspect pip, counting duplicates (double-Villainy
  card needs 2 Villainy icons to avoid full penalty). Non-breaking spaces (`\xa0`)
  in DB text are normalised before parsing.

---

## Architecture

### Two-function contract

```python
legal_actions(state: GameState) -> list[Action]   # never empty while live
apply(state: GameState, action: Action) -> GameState  # raises IllegalActionError if not legal
```

Everything — from mulligan keep/redraw to regroup resource choices — is an `Action`.

### Mutation contract

`apply()` calls `copy.deepcopy(state)` before any mutation. The input state is
**never modified**. Enforced by `test_immutability_of_apply`.

`CardDef` objects (frozen dataclasses from `models.py`) implement `__deepcopy__`
to return `self` — they are shared across state copies. Only mutable wrappers
(`CardInstance`, `PlayerState`, `GameState`) are deep-copied.

### Determinism

All randomness comes from `state.make_rng()` which creates a `random.Random`
instance from `state.rng_state`. After use, `s.rng_state = rng.getstate()` is
stored in the new state. Same seed + same action sequence → identical game.
Enforced by `test_determinism`.

---

## State model

### CardDef vs CardInstance

- **CardDef** (`Unit`, `Leader`, `Base`, `Event`, `Upgrade` in `models.py`) —
  immutable, loaded from DB, shared via `__deepcopy__ = return self`.
- **CardInstance** (`state.py`) — mutable wrapper with `instance_id`, `owner_id`,
  `zone`, `exhausted`, `damage`, `face_down`, `deployed`, `epic_action_spent`,
  `attached_upgrades`.

### Phase flow

```
SETUP_MULLIGAN → SETUP_RESOURCES → ACTION → REGROUP → ACTION → REGROUP → …
```

Setup phases are sequential (player 0 first, then player 1). This is a
simplification of the real simultaneous decision; it doesn't affect game outcome.

### Action phase passing

Once a player passes (or claims initiative), they are added to `passed_players`
and take no more actions this phase. The phase ends when `len(passed_players) == 2`.
If one player passes, the other keeps acting until they also pass.

### Regroup phase

Draw 2 for both players auto-executes during the ACTION→REGROUP transition (inside
the last passing player's `apply()` call). Both players then independently choose
to resource one card or skip (initiative holder decides first). After both decide,
all cards ready and a new round begins.

### Card conservation

All cards for a player are found via `GameState.all_instances_for_player(player_id)`,
which searches all zones including upgrades attached to opponent units. Do NOT use
`PlayerState.all_instances()` for conservation checks — it misses cross-player
attachments. Enforced by `test_card_conservation_across_game` and the soak test.

### Leaders

- `deploy_threshold` is extracted from `epic_action` text via regex.
  Pattern: `"you control N or more resources"` (including non-breaking spaces).
  Alternative: `"[N resources]"` (Chewbacca style).
- Leaders with complex or unsupported deploy conditions (Grogu's trigger) return
  `threshold = None` and cannot be deployed — unless the card registers a
  `DeployCondition` marker, which the single gate `_leader_deploy_allowed` reads
  instead (Bo-Katan Kryze ASH_10's resources-plus-Mandalorians count).
- Leaders that offer "deploy as pilot/upgrade" option (Darth Vader, Luke Skywalker,
  etc.) are supported for the standard unit deploy; the pilot-upgrade option is
  Phase 2/3 scope.
- Defeated deployed leaders return to base_zone (`deployed=False`, `exhausted=True`,
  `damage=0`), `epic_action_spent` remains True (no redeploy).

---

## Serialisation

- Full `GameState` → `state.to_json()` / `GameState.from_json(data)`.
  The event log is NOT restored (not needed for replay; re-run actions instead).
  Requires `SWU_DB` env var or `data/swu.db` at default path.
- `PlayerView` → `view.to_json()` — compact, hidden-info redacted version for
  LLM player consumption.

---

## Phase 2 additions

### Pending decision stack

`GameState.pending_decisions: list[PendingDecision]` is a LIFO stack. When it
is non-empty, `legal_actions()` returns ONLY the options for the top decision —
normal turn actions are suspended. On resolution the stack pops and
`active_player_index` is set to `after_resolve_player_index`.

Decision kinds: `"ambush"` (UseAmbush / DeclineAmbush), `"exploit"` (ExploitSacrifice
/ ExploitCommit), `"test"` (AnswerTestDecision — for unit tests only). Phase 3+
adds `"trigger_option"`, `"resolve_effects"`, `"pre_attack"`, `"granted_attack"`
(effect-granted attacks; see `push_granted_attack`), and the play-from-hand pair
below. New decision kinds must be added to `_KNOWN_DECISION_KINDS` in
`invariants.py` and given a prompt in `web/session.py`.

### Play-a-unit-from-hand-as-an-ability (Admiral Ozzel, SOR_129)

`push_play_from_hand(s, source_ci, *, trait, enters_ready, then_opponents_ready)`
(`actions/hand.py`) is the seam for "Play a unit from your hand as part of an ability".
A card's `CustomEffect` calls it; it pushes a `"play_from_hand"` decision listing
a `PlayFromHand` per affordable matching hand unit (mandatory-if-able — no
decline; the decision is only pushed when ≥1 such unit exists). `PlayFromHand`
pays the unit's effective cost and routes through `_put_unit_in_play(...,
enters_ready=True)` so the unit's own keyword/`WhenPlayed` triggers still fire.
When `then_opponents_ready` is set, an `"opponent_ready"` decision (ReadyUnit /
DeclineReadyUnit — "may ready a unit") is pushed *before* the unit enters play so
the played unit's triggers resolve first (they land on top of the stack).
Exploit cost reduction is **not** applied to an ability-played unit (it must be
affordable at full cost). The played unit's `WhenPlayed`/Ambush triggers fire
normally. Note: `UseAbility`'s inline path only hands the turn over when no
decision was pushed (`not s.pending_decisions`) — an activated ability may itself
push a decision.

### Keyword query layer

Never string-match keywords at point of use. Always:
```python
from swu.engine.keywords import has_keyword, keyword_value, Keyword
has_keyword(state, unit_ci, Keyword.SENTINEL)   # bool
keyword_value(state, unit_ci, Keyword.RAID)     # int (0 if absent)
```
Numeric keyword values (Raid, Restore, Exploit) are extracted via regex from
`card_def.text` (units) or `card_def.deploy_box` (leaders). Two edge cases in
the DB have conditional values (Marchion Ro, Oppo Rancisis) — these return 0
and are treated as text-bearing cards for Phase 3.

### Token system

Shield and Experience are real `TokenUpgrade` card defs loaded from DB.
Create tokens with `tokens.attach_token(state, owner_ps, host_ci, "Shield")`.
Tokens are stripped silently (not discarded) when their host leaves play.
`all_instances_for_player()` excludes `TokenUpgrade` instances so card
conservation is not broken by token creation.

### Effective-stats layer

```python
from swu.engine.actions import compute_power
compute_power(state, unit_ci, is_attacking=False) -> int
```
Returns base + upgrade_power + Grit bonus (damage dealt as extra power) +
Raid bonus (only when `is_attacking=True`). All combat damage calls this;
never read `card_def.power` directly in combat.

### Attack pipeline (CR steps)

`_resolve_unit_combat` in `actions/combat.py` follows these CR steps:
1. Declare + exhaust attacker
2. On-attack triggers: Restore healing; Saboteur strips defender's shields
3. Compute powers: `compute_power(is_attacking=True)` vs `compute_power(is_attacking=False)`
4. Simultaneous damage via `_deal_damage_with_shield()` (shield intercepts 1 hit)
5. Overwhelm: spillover = max(0, damage_to_defender - defender_hp_before)
6. Defeat processing: tokens stripped silently, regular upgrades → discard

### Simultaneous triggers — registration order matters

`keyword_triggers.py` registers Shielded BEFORE Ambush. Both fire on
`UnitEntersPlay`. This guarantees the Shield is attached before the Ambush
decision is presented, so the shield is up during the Ambush trade.

### PLAY_BUFFER zone

`Zone.PLAY_BUFFER` / `PlayerState.play_buffer` holds a card between `PlayCard`
and `ExploitCommit`. The buffer is included in `all_instances()` so conservation
holds during the decision. `all_instances_for_player()` also counts it.

## How to add a mechanic (Phase 3 guide)

### Adding a keyword (e.g. Hidden)

1. Add `HIDDEN = "Hidden"` to `Keyword` enum in `keywords.py`.
2. Add tests in `tests/test_keywords.py`.
3. For enter-play triggers: add a listener in `keyword_triggers.py`, register via
   `get_bus().register("UnitEntersPlay", _listener)`.
4. For attack-time effects: add to the appropriate CR step in `_resolve_unit_combat`.

### Adding a new action type (e.g. UseLeaderAbility)

1. Define the `Action` subclass in the `engine/actions/` module for its mechanic —
   **beside the handler that emits it.** Do NOT place it by what the code is
   "about": the old section banners named the motivating card, and following them
   scatters a family across modules. If nothing emits it yet, it belongs with the
   `legal_actions` arm that will.
2. Add it to `legal_actions()` (in `api.py`) under the appropriate phase guard.
3. Implement `apply()` — always `deepcopy(state)` first, then mutate.
4. Emit a typed `GameEvent` and call `get_bus().fire(state, event)`.
5. Add the name to `actions/__init__.py`'s `__all__` — the facade is explicit, and
   `tests/test_actions_contract.py` pins the surface.
6. If it introduces a decision kind, add the row to the `register_decisions({...})`
   call **in the same module as its handler**. It must be a module-scope call, not
   a decorator, and a row separated from its handler fails SILENTLY because
   `_registrations()` reads the whole package.
7. Respect the layering (`tests/test_actions_layering.py`): import only from
   modules lower in the stack. If you need something from a module above, the
   helper belongs lower down, not in a function-local import.
8. Write tests.

### Adding a Phase 2 zone (e.g. capture pile, bounty)

1. Add the zone to `Zone` enum in `state.py`.
2. Add a list field on `PlayerState`.
3. Update `all_instances()` and `all_instances_for_player()` to include it.
4. Update JSON serialisation helpers in `state.py`.

---

## Running tests

### Test suite tiers

| Tier | Command | When to run | Time |
|---|---|---|---|
| **fast** | `pytest tests/ --ignore=tests/test_engine_soak.py --ignore=tests/test_hypothesis_engine.py -q` | Every commit | ~4 min |
| **medium** | `pytest tests/test_engine_soak.py -q` | Before/after PRs | ~6 min |
| **campaign** | `python scripts/soak.py --games 10000 --jobs 8` | Manual/overnight | minutes |

```bash
# Fast tier (unit + per-card, no soak)
pytest tests/ --ignore=tests/test_engine_soak.py -q

# Medium tier (includes 500-game soaks with invariants)
pytest tests/test_engine_soak.py -q

# Full test suite
pytest tests/ -q

# Campaign runner (see also scripts/soak.py --help)
python scripts/soak.py --games 1000 --jobs 4
python scripts/soak.py --games 10000 --jobs 8 --decks starter,vanilla,keyword

# Replay / shrink a failure bundle
python scripts/replay.py failures/<bundle>.json --verbose
python scripts/shrink.py failures/<bundle>.json --timeout 120
```

Set `SWU_DB=path/to/swu.db` if the database is not at `data/swu.db`.

---

## Running the CLI

```bash
# Human vs random bot (with generated vanilla decks)
python -m swu.cli

# Specify decks and types
python -m swu.cli --deck0 tests/fixtures/vanilla_deck_a.json \
                  --deck1 tests/fixtures/vanilla_deck_b.json \
                  --p0 human --p1 random --seed 42

# Random vs random (no stdin needed)
python -m swu.cli --p0 random --p1 random --seed 7
```

---

## How to implement a new card (Phase 3 recipe)

This is the authoritative guide for adding a card ability registration. Follow
it precisely — it describes the only correct path. Do not invent new patterns
or use string-matching at point of use.

### Step 0 — Find the gap

```bash
# See which cards in a specific deck need work
python scripts/audit_coverage.py --deck tests/fixtures/starter_luke.json

# Full DB audit (writes docs/coverage_report.md)
python scripts/audit_coverage.py
```

Cards labelled `text-bearing` are implementation gaps. Cards labelled
`escape-hatch` are stubs that may warrant a proper implementation.
Cards labelled `keyword-deferred` need a Phase 3+ keyword (Hidden, Piloting,
Bounty, etc.) and should be left alone until that phase.

### Step 1 — Read the card text from the DB

```python
import sqlite3
con = sqlite3.connect("data/swu.db")
con.row_factory = sqlite3.Row
row = con.execute(
    "SELECT name, text, deploy_box FROM cards WHERE set_code=? AND card_number=?",
    ("SOR", "59")
).fetchone()
print(row["name"], "|", row["text"])
```

The relevant fields are `text` (unit/event body) and `deploy_box` (leader
undeployed + deployed sides). Non-breaking spaces (`\xa0`) appear in some DB
rows — treat them as regular spaces.

### Step 2 — Choose the right ability spec

| Card text says | Spec to use |
|---|---|
| "When Played:" / "When this unit enters play:" | `TriggerAbility(trigger=WhenPlayed(), ...)` |
| "On Attack:" | `TriggerAbility(trigger=OnAttack(), ...)` |
| "When Defeated:" | `TriggerAbility(trigger=WhenDefeated(), ...)` |
| "When Attacked:" | `TriggerAbility(trigger=WhenAttacked(), ...)` |
| "When this unit defeats a unit" | `TriggerAbility(trigger=OnAttackDefeatsUnit(), ...)` |
| "Constant:" | `ConstantAbility(target=..., effects=[StatBonus(...) or KeywordGrant(...)])` |
| "Action [cost]:" | `ActivatedAbility(costs=[...], effects=[...])` |
| "Epic Action:" (one-per-game, non-deploy) | `ActivatedAbility(..., epic=True)` |
| Event card body text | `EventAbility(effects=[...])` |
| Irreducible / multi-step text | `CustomEffect(fn=...)` inside any spec's `effects` |

### Step 3 — Register the card

All registrations live in `src/swu/cards/sor/abilities.py`. Add a new
decorated function:

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

Rules:
- The decorator key is `("SET_CODE", "CARD_NUMBER")` where `CARD_NUMBER` is
  the string from the DB (e.g. `"5"`, `"130"`) — NOT zero-padded unless the
  DB stores it that way.
- The decorated function name is `_<snake_case_card_name>` and is never called
  directly.
- Return a single `AbilitySpec` or a `list[AbilitySpec]`.
- Cards with no ability complexity (pure keywords like Grit, Raid, Sentinel)
  are **not registered** — the keyword layer handles them automatically.

### Step 4 — TargetSpec reference

```python
TargetSpec(
    controller="friendly",     # "friendly" | "enemy" | "any"
    kind="unit",               # "unit" | "base" | "unit_or_base" | "upgrade"
    arena="ground",            # "ground" | "space" | None (either/both)
    traits=("Force",),         # card must have ALL listed traits
    predicates=("damaged",),   # see below
    cost_max=3,                # card cost <= N
    cost_min=1,                # card cost >= N
    hp_remaining_max=5,        # remaining HP <= N
    aspects=("Heroism",),      # card must have ALL listed aspects
    count=1,                   # how many targets to pick
    optional=False,            # True = "may" (player may decline with ChooseTarget(None))
    chooser="controller",      # "controller" | "opponent"
    fixed=SELF,                # skip player choice — use a sentinel (see below)
)
```

**Predicates:**
`"damaged"`, `"undamaged"`, `"exhausted"`, `"non_leader"`, `"not_self"`,
`"leader_unit"` (deployed leader in arena).

**Fixed-target sentinels** (skip the player-choice step entirely):
- `SELF` — the source card itself
- `ATTACKER` — the unit currently attacking (from event context)
- `DEFENDER` — the unit currently defending (from event context)
- `EACH_FRIENDLY` — auto-targets every matching friendly card
- `EACH_ENEMY` — auto-targets every matching enemy card
- `EACH_IN_PLAY` — auto-targets every matching card in play

### Step 5 — Effect primitives reference

```python
DealDamage(amount=2, target=TargetSpec(...))
Heal(amount=2, target=TargetSpec(...))
DefeatUnit(target=TargetSpec(...))
DefeatAllUnits(filter=TargetSpec(...))           # wipes all matching units
GiveToken("Shield", target=TargetSpec(...), count=1)  # "Shield" | "Experience"
DrawCards(count=1, player="controller")          # "controller" | "opponent" | "each"
DiscardFromHand(count=1, chooser="controller")
ReturnToHand(target=TargetSpec(...))
ExhaustCard(target=TargetSpec(...))
ReadyCard(target=TargetSpec(...))
ModifyStats(power=2, hp=0, target=TargetSpec(...), duration=Duration.THIS_ATTACK)
GrantKeyword("Overwhelm", value=0, target=TargetSpec(...), duration=Duration.THIS_ATTACK)
RevokeKeyword("Sentinel", target=TargetSpec(...), duration=Duration.THIS_PHASE)
ResourceCardEffect(target=TargetSpec(...))       # resource a card from play
ConditionalEffect(
    condition=ConditionCheck(Condition.SOURCE_DAMAGED),
    if_true=[DealDamage(...)],
    if_false=[],
)
```

**Duration values:** `Duration.PERMANENT`, `Duration.THIS_PHASE`,
`Duration.THIS_ATTACK`, `Duration.THIS_ROUND`.

**ConditionCheck atoms:** `SOURCE_UNDAMAGED`, `SOURCE_DAMAGED`,
`CONTROLLER_HAS_INITIATIVE`, `CONTROLLER_N_PLUS_RESOURCES` (param=N),
`CONTROLLER_HAS_TRAIT_UNIT` (param="TraitName").

### Step 6 — ConstantAbility pattern

```python
@card_ability("SOR", "042")
def _example_constant():
    """Constant: Each friendly Trooper unit gets +1/+0."""
    return ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit", traits=("Trooper",)),
        effects=[StatBonus(power=1, hp=0)],
        condition=None,  # or ConditionCheck(Condition.CONTROLLER_HAS_INITIATIVE)
    )
```

`StatBonus` and `KeywordGrant` are the only valid `effects` entries for
`ConstantAbility`. The engine re-evaluates these every time `compute_power` or
`has_keyword` is called — no action needed to "start" or "stop" them.

### Step 7 — ActivatedAbility pattern

```python
@card_ability("SOR", "042")
def _example_activated():
    """Action [exhaust, 2 resources]: Draw 2 cards."""
    return ActivatedAbility(
        costs=[ExhaustSelf(), PayResources(2)],
        effects=[DrawCards(count=2)],
        title="Draw 2 cards",
        once_per_round=False,
        epic=False,
    )
```

**Cost specs:** `ExhaustSelf()`, `PayResources(n)`, `DefeatSelf()`.

### Step 8 — Leader card pattern

Leaders have two sides. Both sides live in the same spec list; the engine
gates them by deployment state using `deployed_only` / `undeployed_only`:

```python
@card_ability("SOR", "10", escape_hatch=True)
def _darth_vader():
    return [
        # Undeployed side: presented as UseAbility before deployment
        ActivatedAbility(
            costs=[PayResources(1), ExhaustSelf()],
            effects=[CustomEffect(fn=_vader_activate)],
            title="Deal damage (if Villainy played this phase)",
            undeployed_only=True,
        ),
        # Deployed side: trigger fires only while ci.deployed == True
        TriggerAbility(
            trigger=OnAttack(),
            effects=[DealDamage(2, TargetSpec(controller="any", kind="unit"))],
            optional=True,
            deployed_only=True,
        ),
    ]
```

An ability with neither flag fires regardless of deployment state (uncommon
for leaders; valid for a card-wide constant effect).

### Step 9 — CustomEffect escape hatch

Use `CustomEffect` only when the effect cannot be expressed with the primitives
above. The function signature is:

```python
def my_effect(state: GameState, source_ci: CardInstance,
              target_id: str | None, event_ctx: dict) -> GameState:
    # state is already a deep-copied mutable instance — mutate and return it
    ...
    return state
```

Key invariants:
- Never `deepcopy` inside the function — the resolver already did it.
- **Never use the global `random` module or `uuid` for game state.** All
  randomness must come from `rng = state.make_rng()` followed by
  `state.rng_state = rng.getstate()`; all modifier ids must come from
  `state.alloc_modifier_id(prefix)`. Both are seeded/deterministic and survive
  serialisation, so two same-seed runs reproduce identically. Global `random`
  (os state) and `uuid4` (os.urandom) silently break the determinism oracle — a
  whole class of 10k-campaign failures (SOR_84/123 deck reorder, modifier ids).
- If `target_id` is `None` (no player-chosen target), the function must be
  safe to call (auto-select or no-op).
- `CustomEffect` has no `target: TargetSpec` field — the resolver will not
  prompt the player for a target automatically. If you need a player choice,
  pair it with a `TargetSpec` using a different effect, or do the selection
  inside the function.

If the entire ability is irreducible, mark the registration `escape_hatch=True`
so the audit script classifies it correctly:

```python
@card_ability("SOR", "092", escape_hatch=True)
def _overwhelming_barrage():
    return EventAbility(effects=[CustomEffect(fn=_barrage_fn)])
```

### Step 10 — EventAbility (event cards)

```python
@card_ability("SOR", "068")
def _force_push():
    """Force Push — Return a non-leader unit to its owner's hand."""
    return EventAbility(effects=[
        ReturnToHand(TargetSpec(controller="any", kind="unit",
                                predicates=("non_leader",)))
    ])
```

The `PlayCard` action calls the resolver to execute `EventAbility` effects.
The card moves to discard automatically after resolution.

### Step 11 — Write the test

Add a test class in `tests/test_sor_cards.py`. Minimal pattern:

```python
class TestMyCard:
    def test_set_num_effect_fires(self):   # method name includes the card number
        from tests.helpers import make_state_with_units, find_instance
        from swu.engine.actions import legal_actions, apply
        # set up a minimal game state and verify the effect
        ...
```

**Put the card number in each test method name** (e.g. `test_shd_64_…`). The
encoding verifier's focused-test gate (`verify_encoding.py --group NN`) builds its
`pytest -k` expression from the group's **card numbers**, not the `Test<CardName>`
class names — so methods that omit the number select **zero** tests and report a
spurious `FAIL` even though they pass. Embedding the set+number makes the gate
find them.

Use helpers from `tests/helpers.py`: `make_state_with_units`, `find_instance`,
`_place`, `AcceptTrigger`, `DeclineTrigger`, `ChooseTarget`, `ContinueAttack`.

For escape-hatch stubs with no meaningful test yet, use:

```python
@pytest.mark.xfail(reason="escape_hatch stub — full logic deferred")
def test_placeholder(self): ...
```

Do **not** remove a card from the xfail list until its registration no longer
carries `escape_hatch=True`.

### Step 12 — Confirm with audit and tests

```bash
# Card should no longer appear as a gap
python scripts/audit_coverage.py --deck tests/fixtures/starter_luke.json

# Run the focused test
pytest tests/test_sor_cards.py -q -k "MyCard"

# Full fast suite to catch regressions
pytest tests/ --ignore=tests/test_engine_soak.py -q
```
