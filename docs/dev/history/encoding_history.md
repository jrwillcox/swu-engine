# SWU Encoding History (archived from CLAUDE.md, 2026-07-16)

This file is the verbatim archive of the per-group deck-encoding session log and the
detailed Phase-2 keyword implementation notes that used to live in `CLAUDE.md`. They
were moved here to keep `CLAUDE.md` lean (it is loaded into every session). Nothing
was changed — this is the full prose record. The distilled, reusable summary lives in
`CLAUDE.md` under "Engine seams & patterns catalog". Per-deck detail is also in the
`memory/` topic files (project_han_solo.md, project_boba_fett.md, etc.).

---

## Part 1 — Phase 7 per-group encoding log (all 12 decks)

**Engine primitives added during the Phase 7 dry run (group `shd-han-solo:03`):**
- `kind="upgrade"` target enumeration in `abilities/resolver.py` (`_gather_legal_targets`
  scans hosts' `attached_upgrades`; `_spec_matches_ci` gained an upgrade branch;
  `_apply_defeat_unit` detaches+discards an upgrade). Enables "defeat an upgrade"
  (Disabling Fang Fighter SHD_166). `kind="upgrade"` was documented in the
  TargetSpec reference but previously unimplemented.
- `Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT` (registry.py) — "another X unit"
  (excludes the source), for Bounty Guild Initiate SHD_254.
- New card sets register via `src/swu/cards/__init__.py` (imports every set
  module); `src/swu/cards/shd/abilities.py` holds SHD registrations.

**Engine primitive added (group `shd-han-solo:05`) — play-from-hand-act-on-result
(Han Solo SHD_13):** the existing play-from-hand subsystem (`push_play_from_hand`
→ `play_from_hand` decision → `PlayFromHand`) gained two optional, serialisable
context fields — **`cost_reduction`** (subtracted, floored at 0, from the played
unit's effective cost in BOTH the affordability filter `_playable_units_from_hand`
and the actual payment) and **`then_damage`** (damage dealt to the *just-played
unit* — the "act on the result" handle the primitive name refers to). The damage
is dealt inside `_put_unit_in_play` **after** the Phase-2 enter-play keyword bus
(so a Shielded unit's shield intercepts it) but **before** the unit's own
`WhenPlayed` abilities fire — matching Han's errata ("2 damage is dealt to the
played unit before resolving any When Played abilities"); if it is lethal the
unit is defeated immediately and its WhenPlayed never fires. No new decision
kind, no change to the trigger/decision machinery — the existing `play_from_hand`
decision just carries more context. Both of Han's leader sides
(undeployed `Action [Exhaust]`, deployed costless `Action`) reuse one
`CustomEffect` adapter calling `push_play_from_hand(cost_reduction=1,
then_damage=2)` (the Ozzel SOR_129 pattern — a thin adapter, not irreducible
logic). Availability is gated by the new
`Condition.CONTROLLER_CAN_PLAY_DISCOUNTED_UNIT(param=discount)` atom (controller
holds ≥1 hand unit affordable at the discount), so the action is not offered when
it would change nothing (errata) and the costless deployed side is never a legal
no-op. Tests: `tests/test_shd_cards.py::TestHanSolo`.

**Part D (quality-of-life) — backend done, frontend pending:**
- **Save/restore** — `SessionStore.save/load` (file store under `data/saves/`),
  full `GameState` round-trips (mid-decision/mid-animation). Routes
  `POST /api/games/{id}/save`, `GET /api/saves`, `POST /api/saves/{slot}/load`.
- **Replay** — every `GameSession` records its seed + ordered action history
  (repro-bundle shape); `GET /api/games/{id}/replay` exports a bundle;
  `session.replay_to_state(bundle)` re-drives it deterministically.
- **SWUDB import** — `swu/web/swudb_import.py` + `POST /api/import/swudb`: accepts
  a pasted deck or url/id (injectable fetch), validates, classifies gaps, writes a
  fixture, and emits the planner command so an unshipped import immediately
  produces encoding groups.
- **Mulligan/regroup** — engine `KeepHand`/`TakeMultiligan` surfaced over HTTP.
- Backend tests: `tests/test_web_save_replay.py`, `tests/test_swudb_import.py`.

**Part D (frontend) — DONE:** in `web/` — a 💾 save button + toast in the HUD
(`Hud`/`Toast`), a dedicated **mulligan moment** overlay (`MulliganViewer`), the
start-screen **tools** (resume-saved list, SWUDB import box with a gap report +
planner hint, and a watch-replay file picker — all in `NewGameScreen`), a
**replay viewer** (`ReplayViewer.tsx`) that scrubs forward/back over per-step
board snapshots from `POST /api/replay` and replays each step's events through the
existing `EffectsLayer`, plus replay **export** from the end screen. App-level
mode switch (game vs replay) in `App.tsx`; client methods in `api/client.ts`.
Tests: `web/tests/part_d.test.tsx` (vitest), `web/tests/e2e/save_replay.spec.ts`
(Playwright); the existing e2e smoke now dismisses the mulligan overlay.

**Phase 7 remaining:** encoding the rest of `shd-han-solo`. The **Smuggle**
keyword group (`shd-han-solo:01`) is fully done (the two residual-text cards
SHD_174 Hotshot DL-44 Blaster and SHD_175 Armed to the Teeth are both
implemented — see the Phase 2 Smuggle note and the granted-ability primitive
note). The **Card advantage & disruption** ability group
(`shd-han-solo:03`) is done (Wookiee Warrior SHD_249 — "When Played: if you
control another Wookiee unit, draw a card" = a `WhenPlayed` `DrawCards` gated by
the existing `CONTROLLER_HAS_OTHER_TRAIT_UNIT` condition, no new primitive). The
**Combat tricks, buffs & tempo** ability group (`shd-han-solo:04`) is done
(Hunting Nexu SHD_168 "While you control another Aggression unit, this unit gains
Raid 2" and Protector of the Throne SHD_247 "While this unit is upgraded, it gains
Sentinel"). Both are a self-targeted conditional `ConstantAbility`
(`target=TargetSpec(fixed=SELF)`, `effects=[KeywordGrant(...)]`, `condition=…`),
which the keyword query layer (`has_keyword`/`keyword_value`) already honours, so
the keyword winks on/off with the board — no trigger/decision machinery. Two new
condition atoms: `CONTROLLER_HAS_OTHER_ASPECT_UNIT(param=aspect)` ("another
<Aspect> unit", excludes the source) and `SOURCE_UPGRADED` (source has ≥1 attached
upgrade; per CR, Shield/Experience tokens count). **Sanitiser change:** the
official data tags both cards with the keyword on their *printed* bar (always-on),
which would mis-implement the conditional grant; `keyword_sanitizer` now also
strips a printed keyword that the card grants to *itself conditionally* **iff** a
ConstantAbility (self target, `KeywordGrant`, with a `condition`) is registered to
model it — so the ability owns the keyword. An *unimplemented* conditional
self-grant (e.g. First Legion Snowtrooper's Overwhelm) is left as the existing
printed-keyword simplification. `sanitize_keywords` gained optional
`set_code`/`card_number` params, threaded from `repository._hydrate`. The
**play-from-hand-act-on-result** escalation group (`shd-han-solo:05`, Han Solo
SHD_13) is done (see the engine-primitive note above). The **repeated-modal-per-X**
escalation group (`shd-han-solo:06`, Poe Dameron SHD_153) is done (see the
engine-primitive note below). The **sacrifice-resource-cost** escalation group
(`shd-han-solo:07`, Wrecker SHD_154) is done (see the engine-primitive note
below). The **scaling-magnitude** escalation group (`shd-han-solo:08`, The Chaos
of War SHD_159) and the **granted-attack-restricted-attacker** escalation group
(`shd-han-solo:09`, Desperate Attack SHD_179) are done (see the engine-primitive
notes below). The **opponent-chooses-target** escalation group
(`shd-han-solo:10`, Grey Squadron Y-Wing SHD_246) is done (see the engine-primitive
note below). The **control-change** escalation group (`shd-han-solo:02`, Stolen
Landspeeder SHD_161 — the last gap in the Bounty keyword group) is done (see the
engine-primitive note below). The **upgrade-grants-host-a-triggered-ability**
framework group (`shd-han-solo:01` residual, Armed to the Teeth SHD_175) is done
(see the engine-primitive note below) — **`shd-han-solo` is now fully encoded;
every card in the deck is playable.** The whole machinery and QoL layer are
complete.

**Engine primitive added (group `shd-han-solo:06`) — repeated-modal-per-X (Poe
Dameron SHD_153):** a new self-contained `"repeated_modal"` decision kind
(`actions.push_repeated_modal`) for "Discard up to N cards from your hand; for
each card discarded this way, choose a *different* option." One decision drives
three stages in its context (`stage` ∈ `discard`/`choose_mode`/`choose_target`):
`DiscardForModal(card_id)` discards a hand card up to the cap `min(max_discards,
#modes)` and `FinishModalDiscard` stops early (the "up to" lets the controller
take fewer; discarding 0 fizzles the whole ability); then per discarded card
`ChooseRepeatedMode(mode)` picks one not-yet-used option (a targeted option —
`deal_2_damage`/`defeat_upgrade` — advances to `ChooseRepeatedTarget(target_id)`;
the untargeted `opponent_discards` resolves with no target, mirroring
`DiscardFromHand(chooser="opponent")` = discard the opponent's first card). Each
chosen option is **recorded** into `ctx["plan"]`, not applied, until one option
per discard is chosen; then the decision is **popped first** and the planned
effects are applied in order — so a defeat/damage trigger lands on a clean stack
(the same "pop, then deal" gotcha as `push_distribute_damage`; effects reuse the
resolver's `_apply_deal_damage`/`_apply_defeat_unit`, `kind="upgrade"` targeting
excludes tokens like Disabling Fang Fighter SHD_166). No change to the
trigger/decision machinery — the OnAttack trigger's one `CustomEffect` is a thin
adapter onto the push helper (the Palpatine SOR_135 pattern). New kind registered
in `invariants._KNOWN_DECISION_KINDS` and `web/session.py` (`_PROMPTS` +
stage-specific prompt). Tests: `tests/test_shd_cards.py::TestPoeDameron`.

**Engine primitive added (group `shd-han-solo:07`) — sacrifice-resource-cost
(Wrecker SHD_154):** a new self-contained `"sacrifice_resource"` decision kind
(`actions.push_sacrifice_resource_for_damage`) for "You may defeat a friendly
resource. If you do, deal N damage to a <arena> unit." One decision drives two
stages (`stage` ∈ `decide`/`target`): `SacrificeResource(resource_id)` defeats one
of the controller's resources (it leaves the resource zone for discard) and
advances to the damage target, `DeclineSacrifice` pops and does nothing (the "you
may"); then `ChooseSacrificeTarget(target_id)` deals the stored damage and pops.
The damage is dealt **after** the decision pops (the same "pop, then deal" gotcha
as `push_distribute_damage`/`push_repeated_modal`, reusing the resolver's
`_apply_deal_damage`) so a defeat trigger lands on a clean stack. The decision is
pushed **only** when the controller has ≥1 resource AND ≥1 legal damage target, so
"you may" with no upside is never offered (a Wrecker in play is itself a ground
unit, so the target set is never empty unless the arenas are wiped — the realistic
fizzle is having no resource to spend). No change to the trigger/decision
machinery — the WhenPlayed trigger's one `CustomEffect` is a thin adapter onto the
push helper (the Palpatine SOR_135 / Poe SHD_153 pattern); Overwhelm is the
keyword layer. New kind registered in `invariants._KNOWN_DECISION_KINDS` and
`web/session.py` (`_PROMPTS` + stage-specific prompt); `HeuristicBot` gained a
`_choose_sacrifice_resource` handler (sacrifice only to hit an enemy ground unit,
hit the one the damage best removes, else decline) and `DeclineSacrifice` in its
safe-default order. Tests: `tests/test_shd_cards.py::TestWrecker` +
`tests/test_sacrifice_resource.py` (synthetic).

**Engine primitive added (group `shd-han-solo:08`) — scaling-magnitude (The Chaos
of War SHD_159):** a new self-contained **effect** dataclass `DealDamageEqualTo`
(`registry.py`) for "deal damage equal to <a count>" where the magnitude is
computed **per target** from game state instead of a fixed constant — the bit a
plain `DealDamage(amount=...)` cannot express. It carries a `target: TargetSpec`
and a `count` string naming the scaling source; the only count today is
`"target_controller_hand"` (cards in the hand of the player who controls the
target). The resolver gained one arm in `execute_effect` and a `_scaling_magnitude`
helper; the effect is registered in `_get_effect_target_spec` so its fixed/legal
targets resolve and it inlines (no player choice). The arm reads every target's
magnitude up front (a snapshot, so damaging one base cannot change another's
amount), then reuses `_apply_deal_damage` (a 0 magnitude is a no-op). The Chaos of
War is a plain `EventAbility([DealDamageEqualTo(target=TargetSpec(kind="base",
fixed=EACH_IN_PLAY), count="target_controller_hand")])` — `EACH_IN_PLAY`
auto-targets both bases, so each takes its own owner's hand size. Note the event
is moved to **discard before its ability resolves** (`actions.py` PlayCard), so it
does not count toward the controller's own hand. **No** new decision kind and **no**
change to the trigger/decision machinery — purely a new effect dataclass + resolver
arm (the allowed small-primitive path). Tests:
`tests/test_shd_cards.py::TestTheChaosOfWar` (asymmetric per-base damage + empty-hand
zero).

**Engine primitive added (group `shd-han-solo:09`) — granted-attack-restricted-
attacker (Desperate Attack SHD_179):** the existing `granted_attack` decision
(`actions.push_granted_attack`, the Surprise Strike SOR_220 seam) gained one
optional, serialisable context field — **`attacker_predicates`** — a list of the
same TargetSpec predicate names (`"damaged"`/`"undamaged"`/`"exhausted"`/
`"non_leader"`) used to **narrow which of the controller's units may be the
attacker**. The `legal_actions` `granted_attack` branch filters its
`_enumerate_attacks` output through a new `_attacker_matches_predicates` helper
(mirrors `resolver._spec_matches_ci`'s predicate checks for the attacker-relevant
subset); a unit must satisfy ALL predicates to be offered. When the restriction
leaves no eligible attacker the (mandatory) attack fizzles via the existing
`DeclineGrantedAttack`, exactly like having no ready unit. Desperate Attack is a
plain `EventAbility` whose one `CustomEffect` is a thin adapter calling
`push_granted_attack(power_bonus=2, attacker_predicates=["damaged"])` (the
Surprise Strike pattern). **No** new decision kind and **no** change to the
trigger/decision machinery — purely a filter on the offered options of an
existing decision (the allowed small-primitive path). Tests:
`tests/test_shd_cards.py::TestDesperateAttack`. **Follow-up (same day):** the
same seam gained a sibling **`attacker_id`** pin (offer only attacks by one
specific unit) to unblock the Smuggle-group residual **Hotshot DL-44 Blaster
SHD_174** ("When played using Smuggle: Attack with attached unit"): a
`WhenPlayedViaSmuggle` `CustomEffect` reads the host from
`event_ctx["attached_to_id"]` and calls `push_granted_attack(attacker_id=host)`.
This also required widening `resolver._collect_triggers`' upgrade-play branch to
collect `WhenPlayedViaSmuggle` (not just `WhenPlayed`) for a freshly-played
upgrade — a one-line, anticipated completion (the `WhenPlayedViaSmuggle`
docstring already named SHD_174). Tests:
`tests/test_shd_cards.py::TestHotshotDL44Blaster`. SHD_175 (Armed to the Teeth)
is now done too — see the **upgrade-grants-host-a-triggered-ability** primitive
note below.

**Engine primitive added (group `shd-han-solo:01` residual) — upgrade-grants-
host-a-triggered-ability (Armed to the Teeth SHD_175):** a new ability spec
`GrantedAbility(ability=TriggerAbility(...))` (`registry.py`) for the printed
pattern "Attached unit gains: '<ability>'".  An upgrade registers a
`GrantedAbility` wrapping a normal `TriggerAbility`; the wrapped ability behaves
**as if registered on the host unit** — both trigger matching and effect
resolution use the HOST as the source.  Collection: `resolver._collect_triggers`
now also scans each in-play unit's `attached_upgrades` for `GrantedAbility`
specs, and (the structural change) its result tuple widened from `(source_ci,
ability_idx, ability)` to `(source_ci, spec_ci, ability_idx, ability)` —
`source_ci` is the unit the ability resolves *from* (the host), `spec_ci` is the
card whose registry holds the spec (the upgrade); they coincide for every
ordinary trigger.  The pushed decision is addressed to `spec_ci`'s `(set_code,
card_number, ability_idx)` but its `source_id` is the host, so the
trigger_option/resolve_effects resolution applies `registry.unwrap_granted` to
turn the looked-up `GrantedAbility` back into its inner `TriggerAbility`.  This is
purely additive (a new spec type + a collection scan + a wider internal tuple) —
**no** new decision kind and **no** change to the decision/resolution machinery
itself, so it follows the small-primitive path.  SHD_175 is a `GrantedAbility`
wrapping `OnAttack → ModifyStats(power=2, hp=0, target friendly not_self,
THIS_PHASE)`; "another friendly unit" falls out of resolving from the host
(`not_self` excludes the attacker).  Note the upgrade ALSO carries a printed
+2/+0 to its host (its `upgrade_power`/`upgrade_hp`), which is independent of the
granted ability.  Soak coverage: a `GrantedAbility`'s firing is attributed to the
host (the source), so `soak.py::_analyse_ability_coverage` treats a
`GrantedAbility`-only card as *passive* (like a constant) rather than zero-fire-
active.  Tests: `tests/test_shd_cards.py::TestArmedToTheTeeth`.  Drive-by: the web
SWUDB-import classifier (`swu/web/swudb_import.py`) was stale — it didn't strip
keyword cost brackets and still listed Smuggle as deferred, so it mis-flagged
pure-Smuggle cards (e.g. Nite Owl Skirmisher SHD_149) as gaps; aligned to the
canonical `audit_coverage` rule, so the now-complete `shd-han-solo` imports as
fully playable (`tests/test_swudb_import.py`).

**Engine primitive added (group `shd-han-solo:10`) — opponent-chooses-target
(Grey Squadron Y-Wing SHD_246):** a new self-contained `"opponent_chooses_target"`
decision kind (`actions.push_opponent_chooses_target`) for "An opponent chooses a
unit or base they control. You may deal N damage to it." Its novelty is that the
two stages have **different deciding players** — the same shift-of-decider seam
`push_say_no` (SOR_233) already uses, so no change to core resolution or the
trigger/decision machinery. Stage `"choose"` hands the decision to the OPPONENT
of the source's controller, who picks one of their own units or base via
`ChooseOwnTarget(target_id)` (mandatory — a base is always present, so the choose
list is never empty); resolving it flips `deciding_player_id`/`active_player_index`
to the controller and advances to stage `"confirm"`, where the controller may
`ConfirmOpponentDamage()` or `DeclineOpponentDamage()` (the "you may"). The damage
is dealt **after** the decision pops (the `push_distribute_damage` /
`push_sacrifice_resource_for_damage` "pop, then deal" gotcha, reusing the
resolver's `_apply_deal_damage`) so a defeat trigger lands on a clean stack. The
OnAttack trigger's one `CustomEffect` is a thin adapter onto the push helper (the
Palpatine SOR_135 pattern). New kind registered in
`invariants._KNOWN_DECISION_KINDS` and `web/session.py` (`_PROMPTS` +
stage-specific prompts); `HeuristicBot` gained a `_choose_opponent_chooses_target`
handler (as controller: always confirm — the chosen card is always an enemy; as
the targeted opponent: dump on the highest-remaining-HP card, i.e. the base,
never letting a unit die when a safer option exists). Tests:
`tests/test_shd_cards.py::TestGreySquadronYWing`.

**Engine primitive added (group `shd-han-solo:02`) — control-change (Stolen
Landspeeder SHD_161):** the dedicated framework session the planner flagged.
**Key realisation:** control in this engine is already *implicit* — a unit is
controlled by whichever player's arena list holds the `CardInstance`
(`find_instance` returns that PlayerState), while `ci.owner_id` is the
(unchanging) owner; they only ever coincided before. Combat, attacks, ability
enumeration, and `legal_actions` all key off the holding player, so the seam is
just **relocating the instance to the other player's arena**:
`actions.change_control(s, ci, new_controller_id)` removes `ci` (with its
`attached_upgrades`, which travel inside it) from its current controller's arena
and appends it to the new controller's matching arena, owner unchanged, arena
kind (ground/space) and `ci.zone` unchanged (so upgrade zone tags stay valid),
emitting a new `ControlChanged` event (generic `event_to_model`; `format.ts`
renders it). Two supporting fixes to `_defeat_unit` (both correct for *all*
cards, exercised only by control-changed units):
- a defeated card now goes to its **owner's** discard/base zone
  (`s.player_by_id(ci.owner_id)`), not its *controller's* (`owner_ps` there is
  the holding/controller PS) — so a stolen unit returns to its real owner;
- `event_ctx` now carries `defeated_controller_id` (the controller at death), and
  after the WhenDefeated triggers fire `_defeat_unit` checks an
  `event_ctx["relocated_by_trigger"]` flag and **skips the discard placement +
  leaving-play modifier expiry** when a trigger put the card back into play
  (avoids double-homing the same instance into both an arena and discard).
`_put_unit_in_play` gained a `play_source` field ("hand"/"smuggle"/"discard")
threaded into the enter-play `event_ctx` (SmugglePlay passes `"smuggle"`; the
default `"hand"` covers PlayCard + PlayFromHand). SHD_161 is two non-optional
`CustomEffect`s (no player choice → resolve **inline**, no new decision kind):
its **WhenPlayed** calls `change_control` to the owner's opponent but only when
`event_ctx["play_source"] == "hand"` (so a Smuggle play / the Bounty replay does
not re-hand it over); its **WhenDefeated Bounty** ("if you own this unit, play it
from your discard for free + Experience token") computes the collector =
opponent of `defeated_controller_id`, no-ops unless the collector *owns* it (i.e.
it died under enemy control — the steal loop), then replays the in-limbo instance
via `_put_unit_in_play(..., play_source="discard")` under the owner's control with
a fresh Experience token (damage/exhaust/old-modifiers cleared) and sets
`relocated_by_trigger`. Dying under the owner's own control (after a replay) →
collector ≠ owner → no-op, so no infinite self-replay. **Scope/limitation
(documented in `change_control`):** the abilities resolver still treats
`source_ci.owner_id` as the controller when resolving a unit's *own*
abilities, so a foreign-controlled unit with friendly-perspective
activated/triggered/constant abilities would resolve from the owner's
perspective — Stolen Landspeeder has none such (its only post-steal ability is
the collector-perspective Bounty), so it is not exercised; a future
control-changing card with such abilities would need that resolver path
generalised. No new decision kind, no `invariants`/`web/session` change. Tests:
`tests/test_shd_cards.py::TestControlChangeSeam` (synthetic seam: relocate keeps
owner, defeated foreign unit → owner's discard) and `::TestStolenLandspeeder`
(hand-play steal via `apply`, no-steal from discard, full defeat→replay loop with
Experience, no self-replay under owner control).

**Engine seams added (group `sabine-mean-green:01` — Direct damage & removal,
2026-06-17):** five small additive seams unblocked the 6-card group; none touch
core resolution or the decision/trigger machinery destructively. Cards:
`tests/test_sabine_cards.py`.
- **`WhenYouPlayCard(aspect, exclude_self)` trigger** (registry + one
  `_trigger_matches` arm) for "When you play another [Aggression] card" (Fighters
  for Freedom SOR_143). It matches the **`CardPlayed`** event — the one event
  every play path emits — so it fires on an Aggression *unit / event / upgrade*
  alike (unlike `WhenPlayed`, which only matches `UnitEntersPlay`/`UpgradePlayed`
  for the played card itself, so there is no double-fire). Both `PlayCard` and
  `SmugglePlay` now route their `CardPlayed` event through
  `fire_triggered_abilities` (a new firing site; a no-op unless a `WhenYouPlayCard`
  observer is in play, since no other trigger matches `CardPlayed`).
- **`WhenDealsCombatDamageToBase` trigger** (registry + arm) for "When this unit
  deals combat damage to a base" (Ketsu Onyo SHD_147). Fired from
  `_resolve_base_attack_step2` via a `dealt_combat_damage_to_base` event-context
  flag (the `OnAttackDefeatsUnit`/`attack_defeated_unit` pattern, `event=None`),
  with `after_all_player_idx` = the opponent so the turn passes once the optional
  trigger resolves (the attacking action's switch is suspended while a decision is
  pending). Effect: optional `DefeatUnit(kind="upgrade", cost_max=2)`.
- **`defender_or_base` predicate** (`resolver._spec_matches_ci`) for "deal 1 to
  the defender or a base" (Sabine Wren unit SOR_142 On Attack): with
  `kind="unit_or_base"`, a base always qualifies while a unit qualifies only if it
  is the current `event_ctx["defender_id"]` (attacking a base → only bases).
- **`push_modal` extension — K-2SO modes** (`kaytoo_damage_base` /
  `kaytoo_discard`, both fungible) for "When Defeated: for each opponent, choose
  one: deal 3 to that player's base, or that player discards a card" (K-2SO
  SOR_145). `_modal_mode_targets`/`_resolve_modal_mode` gained the two modes
  (they act on the OPPONENT of the modal's controller; discard uses the
  `DiscardFromHand(chooser="opponent")` first-card simplification).
- **`reveal_top` decision kind** (`push_reveal_top_discard_reorder` +
  `DiscardRevealed`/`KeepRevealed` + `_maybe_finish_reveal_top`) for "Reveal the
  top 4, deal 1 to an enemy base per [Heroism] revealed, then discard any and put
  the rest back on top in any order" (For a Cause I Believe In SOR_152). The
  Heroism damage is dealt up front (deterministic); the controller then resolves
  each revealed card (discard → discard pile; keep → next on top, the keep order
  = new top order). Registered in `invariants._KNOWN_DECISION_KINDS`,
  `web/session._PROMPTS`, and a `HeuristicBot` handler (keep all, never discard).
- **RESIDUAL DEFERRED:** Sabine Wren unit SOR_142's printed static "While there
  are ≥3 aspects among other friendly units, this unit can't be attacked (unless
  she gains Sentinel)" is NOT implemented — "can't be attacked" would touch
  attack-target enumeration (core `legal_actions`) plus a new aspect-counting
  condition; flagged for a dedicated framework session. The card is still
  `implemented` (its On Attack ability is live); it just lacks the defensive
  shield. Group readiness: **6/6 cards playable**; deck `sabine-mean-green`
  now **36/52** (next group `sabine-mean-green:02`).

**Group `sabine-mean-green:02` — Card advantage & disruption (2026-06-18).**
One card, **no new primitive**. **Bright Hope SOR_99** ("Sentinel. When Played:
You may return a friendly non-leader ground unit to its owner's hand. If you do,
draw a card.") — an optional `WhenPlayed` `TriggerAbility` (the "you may") whose
single `CustomEffect` carries `target=TargetSpec(controller="friendly",
kind="unit", arena="ground", predicates=("non_leader",))`, threading the
controller-chosen ground unit into the fn (the Vader's-Lightsaber SOR_136
CustomEffect.target pattern). The fn binds the return and the draw together so
"If you do" is honoured: a `None` target is a no-op, otherwise it calls
`_apply_return_to_hand` then `_draw_cards(owner_ps, 1)`. Crucially the conditional
draw could NOT be modelled as `[ReturnToHand, DrawCards]` — `DrawCards` is
non-targeted, so `_optional_trigger_has_legal_effect` would always offer the
trigger and draw even with no ground unit to return; folding both into one
targeted CustomEffect means no ground unit ⇒ the optional trigger auto-declines
(no prompt, no draw). Bright Hope is itself a **Space** unit, so it can never
bounce itself (the ground restriction). Group readiness: **1/1**; deck
`sabine-mean-green` now **38/52** (next group `sabine-mean-green:03`).
Tests: `tests/test_sabine_cards.py::TestBrightHope`.

**Group `sabine-mean-green:03` — Combat tricks, buffs & tempo (2026-06-18).**
Four cards; three small additive seams, none touching core resolution or the
trigger/decision machinery destructively. Tests: `tests/test_sabine_cards.py`.
- **Rebel Assault SOR_103** ("Attack with a REBEL unit. +1/+0.  Then attack with
  another REBEL unit. +1/+0") — an `EventAbility` whose one `CustomEffect` calls
  `push_granted_attack` **twice** (the Desperate Attack SHD_179 / Surprise Strike
  SOR_220 adapter pattern). The two grants sit on the LIFO stack so the second
  resolves after the first; "another" Rebel unit falls out of exhaustion (the
  first attacker is exhausted and so never re-offered). Needed a new **optional
  `attacker_trait`** field on `push_granted_attack` — a serialisable trait filter
  on the offered `AttackWithUnit` options (parallel to the existing
  `attacker_predicates`/`attacker_id`; the legal_actions `granted_attack` branch
  filters by trait). No eligible Rebel attacker → the mandatory attack fizzles via
  `DeclineGrantedAttack`. Pure filter on an existing decision (the allowed
  small-primitive path).
- **The Darksaber SHD_126** ("Attached unit gains 'On Attack: Give an Experience
  token to each other friendly Mandalorian unit'") — a `GrantedAbility` wrapping an
  `OnAttack` `TriggerAbility` (the Armed to the Teeth SHD_175 pattern); resolves
  from the HOST, so `GiveToken("Experience", TargetSpec(controller="friendly",
  traits=("Mandalorian",), predicates=("not_self",), fixed=EACH_FRIENDLY))` auto-
  tokens every other friendly Mandalorian unit inline. The "attach to a non-Vehicle
  unit" restriction is the engine's upgrade-target parser (`non_vehicle`).
  **RESIDUAL (deferred):** the cost clause "While playing this upgrade on a
  Mandalorian unit, ignore its aspect penalty" is NOT implemented — a play-cost
  waiver at the upgrade play site (a new seam), not part of the granted ability;
  the card is fully playable without it (same class of deferred cost residual as
  the Smuggle-cost upgrades).
- **Red Three SOR_144** ("Each other friendly [Heroism] unit gains Raid 1") — a
  `ConstantAbility` whose target is every other friendly Heroism unit
  (`controller="friendly"`, `aspects=("Heroism",)`, `not_self`),
  `effects=[KeywordGrant("Raid", 1)]`, read passively by `keyword_value` (winks
  on/off with the board). Red Three keeps its own printed Raid 1 — the keyword
  sanitiser's bare-mention rule already protects it (and this grant is a non-self,
  no-condition Constant, so the conditional-self-grant stripper does not touch it).
- **Medal Ceremony SOR_245** ("Give an Experience token to each of up to 3 REBEL
  units that attacked this phase") — needed a new self-contained **`"select_token"`
  decision kind** (`actions.push_select_token`, `SelectTokenTarget` /
  `FinishSelectToken`): the controller picks *distinct* matching units one at a
  time up to a cap, each receiving a token, or stops early (the "up to"). The
  `resolve_effects` machinery only takes one target per effect (its `count` is the
  token *quantity*, not a target count), so a multi-pick "up to N" cannot be a
  plain `GiveToken` — this is the deck_search "select up to N" pattern but over
  in-play units. Eligibility is recomputed each step from the stored spec via the
  resolver's matcher, governed by a new **`attacked_this_phase` predicate**
  (`resolver._spec_matches_ci`, backed by `game_memory.units_attacked_this_round` —
  attacks happen only in ACTION and the set clears at the round rollover, so "this
  round" and "this phase" coincide; mirrors `played_this_phase`). The card omits
  "friendly", so any Rebel unit that attacked is eligible (`controller="any"`);
  because Experience helps the recipient, the controller's choice simply never
  picks an enemy. The one `CustomEffect` is a thin adapter onto the push helper
  (the Palpatine SOR_135 pattern). Registered in
  `invariants._KNOWN_DECISION_KINDS` and `web/session.py` (`_PROMPTS`);
  `HeuristicBot` gained a `_choose_select_token` handler (token its own eligible
  units, then finish — never an enemy's). No change to the trigger/decision
  machinery (a new self-contained decision kind, the allowed small-primitive path).
- Group readiness: **4/4**; deck `sabine-mean-green` now **49/52** (next group
  `sabine-mean-green:04`). Tests: `tests/test_sabine_cards.py::TestRebelAssault`,
  `::TestTheDarksaber`, `::TestRedThree`, `::TestMedalCeremony`.

**Group `sabine-mean-green:04` — Miscellaneous abilities (2026-06-18).** Two
cards, both "play a unit from hand and give it Ambush for this phase"; three
small additive seams, none touching core resolution or the trigger/decision
machinery. Tests: `tests/test_sabine_cards.py::TestEnergyConversionLab`,
`::TestTimelyIntervention`.
- **Two new optional fields on the play-from-hand subsystem**
  (`push_play_from_hand` / `PlayFromHand` / `_playable_units_from_hand`, both
  serialised in the `play_from_hand` decision context):
  - **`cost_max`** — only hand units whose **printed** cost is ≤ this are
    offered/playable ("a unit that costs 6 resources or less"). Per SWU's
    reading of "costs N or less", this caps the *printed* cost; affordability is
    still checked against the aspect-adjusted effective cost.
  - **`grant_keyword`** — the played unit gains this keyword **for this phase**,
    applied as a `keyword_grant` Modifier (`duration="this_phase"`) in
    `_put_unit_in_play` **before** the enter-play keyword bus fires, so a granted
    **Ambush** triggers immediately on entry exactly as if printed (the Ambush
    listener reads `has_keyword` at bus time). A stray printed Ambush keyword on
    these non-unit cards (the data tags both) is inert — an event/base never
    enters an arena, so the enter-play listener never fires for them.
- **Base activated-ability enumeration** — `legal_actions` previously scanned
  only the arenas for `ActivatedAbility`, never `base_zone`, so a Base's
  activated/Epic ability was never offered. Added a small dedicated `base_zone`
  scan (Base cards only; the undeployed leader in base_zone keeps its own loop)
  mirroring the arena loop (epic-spent / condition / cost-affordability checks).
  `UseAbility.apply` already located the source via `find_instance` (which scans
  base_zone), so no change there.
- **`Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND_COST_MAX(param=cost_max)`** —
  ≥1 affordable hand unit with printed cost ≤ param; reuses
  `_playable_units_from_hand` so the gate and the offered candidates never
  disagree. Gates Energy Conversion Lab's Epic Action so the **once-per-game**
  epic is never wasted when nothing ≤6 is playable (the Ozzel SOR_129 /
  Han SHD_13 "don't offer a no-op" pattern). Timely Intervention is an ordinary
  Event (no gate — you may always choose to play it).
- **Energy Conversion Lab SOR_22** (Base) — `ActivatedAbility(costs=[],
  epic=True)` whose one `CustomEffect` is a thin adapter calling
  `push_play_from_hand(cost_max=6, grant_keyword="Ambush")` (the Ozzel adapter
  pattern). **Timely Intervention SHD_129** (Event, +Smuggle) — `EventAbility`
  whose `CustomEffect` calls `push_play_from_hand(grant_keyword="Ambush")` (no
  cost cap); Smuggle [2, command] is the keyword layer.
- Group readiness: **2/2**; deck `sabine-mean-green` now **52/52** — fully
  encoded. Note on `this_phase` modifiers: there is no
  `_expire_modifiers("this_phase")` step (only `this_attack`/`this_round` expire;
  phase-scoped GameMemory clears at round rollover), but a lingering granted
  Ambush is harmless — Ambush is consumed only at the enter-play instant and
  nothing reads it afterward (the same accepted simplification as Overwhelming
  Barrage SOR_92's `this_phase` stat buff).

**Group `the-mandalorian:01` — Bounty keyword (2026-06-18).** Four cards: three
bounty-granting **upgrades** (Public Enemy SHD_68, Wanted SHD_221, Rich Reward
SHD_261) and a combat-trick unit (Chain Code Collector SHD_216). Two small
additive engine seams, neither touching core resolution destructively. Tests:
`tests/test_shd_cards.py::TestPublicEnemy`, `::TestWanted`, `::TestRichReward`,
`::TestChainCodeCollector`.
- **Granted `WhenDefeated` collection from a defeated unit's upgrades.** The
  Bounty convention (shd-han-solo:02) models "Bounty — …" as a `WhenDefeated`
  trigger resolving for the **collector** (the OPPONENT of the dying unit's
  controller). For an upgrade that "Attached unit gains: 'Bounty — …'" the bounty
  is wrapped in a `GrantedAbility` so it resolves from the HOST (the Armed to the
  Teeth SHD_175 pattern) — but `GrantedAbility(WhenDefeated)` could **never fire**
  before: `_defeat_unit` removes the host from its arena AND detaches/clears its
  upgrades *before* `UnitDefeated` fires, so neither the in-play granted-ability
  scan nor `ci.attached_upgrades` sees them. Fix: `_defeat_unit` now stashes the
  detached upgrades in `event_ctx["defeated_upgrades"]` (snapshotted before
  detaching), and `resolver._collect_triggers`' UnitDefeated branch scans that
  list for `GrantedAbility(TriggerAbility(WhenDefeated))`, collecting it from the
  host (dci) as source / the upgrade as spec card. Purely additive — completes
  the `GrantedAbility` primitive for the defeated-host case; no new decision kind.
- **Collector-as-decider for bounty token choices.** Because the collector (not
  the source's controller) makes any target choice, `push_select_token` gained
  optional `decider_id` (who chooses) and `after_resolve_idx` (who is active after
  — the attacker, for a mid-combat bounty) overrides; `_select_token_targets` was
  made resilient to a source that has left play (the host is in limbo mid-defeat,
  then in discard — both fine for `controller="any"`). Public Enemy = collector
  gives 1 Shield (select_token max 1; the "Give … to a unit" mandatory-if-able is
  the negligible "up to 1" deviation — declining a free shield is never better);
  Rich Reward = collector gives Experience to up to 2 units (the Medal Ceremony
  SOR_245 select-up-to-N pattern). Wanted = collector readies up to 2 of *their
  own* exhausted resources (deterministic, resolves **inline**, no decision). Each
  bounty is a `GrantedAbility` wrapping `WhenDefeated → CustomEffect` (thin adapter
  computing the collector via `event_ctx["defeated_controller_id"]`).
- **Chain Code Collector SHD_216** (NOT a bounty-granter; miscategorised by the
  planner) — Ambush (keyword layer) + "On Attack: If the defender has a Bounty, it
  gets −4/−0 for this attack." A plain `OnAttack` `TriggerAbility` whose one
  `CustomEffect` (runs inline at CR step 2, before power is computed) checks the
  current defender (`event_ctx["defender_id"]`) for a Bounty and, if present,
  appends a `this_attack` `−4/−0` `ModifyStats` modifier to it. "Has a Bounty" is
  the structural helper `_unit_has_bounty` (printed/granted Bounty keyword on the
  unit, OR a non-token attached upgrade carrying the Bounty keyword) — bounties
  are abilities/granted upgrades, not a queryable keyword state, so this is the
  closest faithful query; no new resolver predicate was needed (the defender is
  fixed by the attack, so the check lives in the CustomEffect rather than a
  fixed-target predicate, which would have produced a spurious 1-option decision).
- Group readiness: **4/4**; deck `the-mandalorian` now **15/48** (next group
  `the-mandalorian:02`).

**Group `the-mandalorian:02` — Direct damage & removal (2026-06-18).** Two cards,
two small additive seams, neither touching core resolution or the trigger/decision
machinery. Tests: `tests/test_shd_cards.py::TestFellTheDragon`, `::TestFennecShand`.
- **`TargetSpec.power_min` filter** (registry + one `_spec_matches_ci` arm) for
  "a unit with N or more power". Reads **effective** power via `compute_power`
  (so buffs / upgrades / Experience tokens count) and only matches arena units
  (non-units fail the guard). **Fell the Dragon SHD_78** (Event) is a plain
  `EventAbility([DefeatUnit(TargetSpec(controller="any", kind="unit",
  predicates=("non_leader",), power_min=5))])` — mandatory-if-able: the controller
  picks among non-leader units of power ≥ 5, and the event fizzles with no eligible
  target. (`non_leader` already excludes a deployed leader-unit even at power 5.)
- **New `DealDamageEqualTo` count `source_controller_discard_distinct_costs`**
  (registry doc + `_scaling_magnitude` arm; the helper gained an optional
  `source_ci` param, since this magnitude depends on the SOURCE's controller, not
  the target). It counts the **distinct** printed costs among cards in the source
  controller's discard pile. **Fennec Shand SHD_220** (Unit, Ambush — keyword
  layer) is `OnAttack → DealDamageEqualTo(target=TargetSpec(kind="unit",
  fixed=DEFENDER), count="source_controller_discard_distinct_costs")`. `fixed=DEFENDER`
  resolves to the current defender from `event_ctx` and to **nothing** when
  attacking a base, so "Deal 1 damage to the defender (if it's a unit) for each
  different cost …" falls out for free (no defender unit ⇒ no damage; empty discard
  ⇒ magnitude 0 ⇒ no-op). Resolves inline (fixed target, no player choice).
- Group readiness: **2/2**; deck `the-mandalorian` now **17/48** (next group
  `the-mandalorian:03`).

**Group `the-mandalorian:03` — Card advantage & disruption (2026-06-18).** Five
cards; one small additive engine seam (a new self-contained decision kind), the
rest compose from existing primitives. None touch core resolution or the
trigger/decision machinery destructively. Tests:
`tests/test_shd_cards.py::TestGreefKarga`, `::TestThisIsTheWay`, `::TestKuiil`,
`::TestRazorCrest`, `::TestSpareTheTarget`.
- **New `return_from_discard` decision kind** (`actions.push_return_from_discard`
  + `SelectDiscardCard` / `FinishReturnFromDiscard` + `_finish_return_from_discard`
  / `_return_from_discard_actions`) — "Return up to N <eligible> cards from your
  discard pile to your hand." The discard-pile counterpart of the deck_search /
  select_token "select up to N" pattern: candidate ids (matching a card_def
  predicate) are snapshotted at push time, the controller picks distinct cards
  (auto-finishing at the cap), and a `FinishReturnFromDiscard` is always offered
  (these are "you may" / "up to", so taking 0 is legal). Pushed only when an
  eligible card is present, else fizzles cleanly. A self-contained new decision
  kind — **no** change to core resolution or the trigger/decision machinery (the
  allowed small-primitive path). Registered in `invariants._KNOWN_DECISION_KINDS`
  and `web/session.py` (`_PROMPTS`); `HeuristicBot` gained a
  `_choose_return_from_discard` handler (return a card whenever offered — pure
  card advantage — else finish) plus `FinishReturnFromDiscard` in its safe-default
  order. **Razor Crest SHD_44** (Unit, Restore 2 — keyword layer) is a `WhenPlayed`
  whose one `CustomEffect` is a thin adapter calling
  `push_return_from_discard(count=1, eligible=is-upgrade)` (the Ozzel/Tarkin
  adapter pattern) — "you may return an upgrade from your discard pile to your
  hand".
- **Greef Karga SHD_245** (Unit) and **This Is The Way SHD_253** (Event) both reuse
  the existing **deck_search** seam (`push_deck_search`, the Tarkin SOR_84 / Recruit
  SOR_123 pattern) via a thin `CustomEffect` adapter. Greef = `count=1, window=5,
  up_to=False, eligible=is-upgrade` (mandatory if able — "search for an upgrade").
  This Is The Way = `count=2, window=8, up_to=True,
  eligible=Mandalorian-trait-or-upgrade` ("up to 2 Mandalorian and/or upgrade
  cards"). The deck_search seam already handles "reveal, draw the chosen, bottom
  the rest in seeded-random order".
- **Kuiil SHD_41** (Unit, Restore 1 — keyword layer) — "On Attack: Discard a card
  from your deck. If it shares an aspect with your base, return it to your hand."
  A plain `OnAttack` whose one `CustomEffect` resolves **inline** (no player choice
  → "discard a card from your deck" mills the *top* card, the deck is ordered):
  pop deck top → discard, then if its aspects intersect the controller's base's
  aspects, move it discard → hand. Empty deck is a clean no-op.
- **Spare the Target SHD_206** (Event, Tactic) — a plain `EventAbility` with a
  single `ReturnToHand(TargetSpec(controller="enemy", kind="unit",
  predicates=("non_leader",)))`: bounce an enemy non-leader unit to its owner's
  hand (mandatory-if-able; fizzles with no eligible target). **RESIDUAL
  (deferred):** "Collect that unit's Bounties" is NOT implemented — bounties are
  `WhenDefeated` triggers that fire only on *defeat* and resolve for the collector,
  and there is no marker distinguishing a *bounty* WhenDefeated from an ordinary
  one (e.g. Rhokai Gunship's "When Defeated: deal 1"), so collecting bounties on a
  bounce would touch the trigger-firing machinery AND need a bounty tag — flagged
  for a dedicated framework session. The card is fully playable (the bounce works);
  the rider matters only when the bounced unit actually carries a bounty.
- Group readiness: **5/5**; deck `the-mandalorian` now **26/48** (next group
  `the-mandalorian:04`).

**Group `the-mandalorian:04` — Combat tricks, buffs & tempo (2026-06-18).** Seven
cards; six compose from existing primitives, only The Mandalorian SHD_18 needed
engine support (three small additive seams, none touching the decision/resolution
machinery; no escape-hatch on any card). Tests:
`tests/test_shd_cards.py::TestTheMandalorian`, `::TestClanWrenRescuer`,
`::TestTheArmorer`, `::TestFollowerOfTheWay`, `::TestCargoJuggernaut`,
`::TestMandalorianArmor`, `::TestVambraceGrappleshot`.
- **`WhenYouPlayCard.card_type` filter** (registry + one `_trigger_matches` arm)
  for "When you play an upgrade" (parallel to the existing `aspect` filter).
- **Undeployed-leader trigger collection** (`resolver._collect_triggers`) — an
  undeployed leader lives in `base_zone`, which `_cards_in_play` never yields, so
  an undeployed leader's trigger could never fire before. Added a `base_zone`
  scan (Leader, not deployed, skips `deployed_only` specs) mirroring the existing
  defeated-unit / upgrade-play collection scans. Purely additive — no card relied
  on undeployed-leader triggers staying silent (Luke/Vader's undeployed sides are
  `ActivatedAbility`, not `TriggerAbility`, so they are unaffected).
- **`Condition.SOURCE_READY`** (= source not exhausted) gates the undeployed
  self-exhaust so it is offered only while the leader is ready (the "you may
  exhaust this leader" cost is payable once before regroup re-readies it).
- **The Mandalorian SHD_18** (Leader) — two optional
  `WhenYouPlayCard(card_type="upgrade")` triggers. Deployed side: one
  `ExhaustCard` on an enemy unit with ≤6 remaining HP (`hp_remaining_max=6`); with
  no eligible enemy the optional trigger auto-declines. Undeployed side
  (`undeployed_only`, gated `SOURCE_READY`): `[ExhaustCard(enemy ≤4 HP),
  ExhaustCard(fixed=SELF)]` — the targeted enemy-exhaust is ordered FIRST so the
  player is prompted exactly once (a fixed SELF effect ahead of a targeted effect
  double-prompts in the resolver, since `resolve_effects_actions` skips the fixed
  effect when enumerating but `apply_resolve_effects` consumes the choice at the
  current idx); the outcome is identical to the printed order because exhausting
  the leader never changes the legal enemy targets. The self-exhaust models the
  cost; the `SOURCE_READY` gate prevents exhausting a second enemy off a second
  upgrade in the same round. The Epic Action deploy (6+ resources) is the standard
  leader-deploy machinery (`deploy_threshold`) — no ability registration.
  Faithful wart: with the leader ready but no enemy ≤4 HP present, the
  "you may exhaust this leader" prompt still shows (SELF is always a legal fixed
  effect) — declinable, exactly as printed.
- **Clan Wren Rescuer SHD_40** — `WhenPlayed GiveToken("Experience", any unit)`.
- **The Armorer SHD_47** — "Give a Shield to each of up to 3 Mandalorian units" =
  a thin `WhenPlayed` CustomEffect onto `push_select_token(token_type="Shield",
  max_targets=3, traits=["Mandalorian"])` (the Medal Ceremony SOR_245 select-up-
  to-N pattern; `controller="any"` mirrors the printed text, but Shield benefits
  the recipient so the controller never picks an enemy).
- **Follower of The Way SHD_56** — "While this unit is upgraded, +1/+1" =
  `ConstantAbility(target=SELF, StatBonus(1,1), condition=SOURCE_UPGRADED)` (the
  Protector of the Throne SHD_247 pattern, StatBonus instead of KeywordGrant;
  tokens count as upgrades per CR).
- **Cargo Juggernaut SHD_66** — Shielded (keyword) + `WhenPlayed Heal(4, own
  base)` gated `CONTROLLER_HAS_OTHER_ASPECT_UNIT("Vigilance")` ("another Vigilance
  unit" excludes the source).
- **Mandalorian Armor SHD_73** — "When Played: if attached unit is a Mandalorian,
  give it a Shield" = an inline `WhenPlayed` CustomEffect reading the host from
  `event_ctx["attached_to_id"]` (no player choice). The non-Vehicle attach
  restriction is the upgrade-target parser.
- **Vambrace Grappleshot SHD_74** — "Attached unit gains 'On Attack: Exhaust the
  defender'" = `GrantedAbility(OnAttack → ExhaustCard(fixed=DEFENDER))` resolving
  from the host (the Armed to the Teeth SHD_175 pattern); `fixed=DEFENDER` resolves
  to nothing on a base attack, so it fizzles harmlessly there.
- **Regression fixed (pre-existing, surfaced by the soak):** `_defeat_unit`
  stashes `defeated_upgrades` (raw CardInstances) in `event_ctx` for the granted-
  bounty-from-a-defeated-upgrade scan (group :01), but `_build_ability_decision`
  stripped only `defeated_ci` before persisting a decision's `event_ctx` — so a
  WhenDefeated trigger pushed by an *upgraded* unit leaked non-JSON-serialisable
  CardInstances into the decision context, breaking the soak's mid-game
  serialisation (`test_soak_200_starter_games`). Fixed by stripping
  `defeated_upgrades` too (read only during synchronous collection). Regression:
  `tests/regressions/test_when_defeated_self_trigger.py::
  test_pending_decision_serialisable_with_attached_upgrade`.
- Group readiness: **7/7**; deck `the-mandalorian` now **36/48** (next group
  `the-mandalorian:05`).

**Group `the-mandalorian:06` — Miscellaneous abilities (2026-06-19).** Two cards,
two small additive engine seams; neither touches core resolution or the
trigger/decision machinery destructively (the planner mis-bucketed these as
composing from existing primitives — each needed a new primitive, both within the
allowed small-primitive path). No escape-hatch on either card. Tests:
`tests/test_shd_cards.py::TestFoundling`, `::TestSurvivorsGauntlet`.
- **New `TraitGrant` constant effect + a trait query layer
  (`src/swu/engine/traits.py`, `get_traits` / `has_trait`).** The keyword-query
  analogue for traits: a unit's *effective* traits are its printed traits plus any
  granted while in play. The only granting source today is an attached **upgrade**
  carrying a `ConstantAbility` whose effects include a `TraitGrant`
  (`get_traits` scans `ci.attached_upgrades` for it, resolving the grant onto the
  host; a present condition is evaluated against the host). Three read sites now
  consult the layer instead of reading `card_def.traits` directly, so a granted
  trait counts everywhere a printed one does for "an <X> unit" checks:
  `resolver._spec_matches_ci` (the universal target matcher → covers The Darksaber
  SHD_126 "each friendly Mandalorian unit", etc.), the `CONTROLLER_HAS_TRAIT_UNIT`
  / `CONTROLLER_HAS_OTHER_TRAIT_UNIT` Conditions (`registry.py`), and
  `actions._units_matching` (the select_token / distribute trait filter → covers
  The Armorer SHD_47's Mandalorian-only Shields). **Scope/limitation:** the
  hand-card trait gates (`PlayFromHand`'s `trait` filter, the granted-attack
  `attacker_trait`/Raid `bonus_trait` checks) still read printed traits — a card
  in hand cannot carry Foundling, and no shipped card grants a trait to an
  attacker, so these are not exercised; a future trait-granter touching those
  paths would route them through `has_trait` the same way. **Foundling SHD_69**
  (Upgrade, "Attached unit gains the Mandalorian trait") is a
  `ConstantAbility(target=SELF, effects=[TraitGrant("Mandalorian")])` — purely
  additive (a new effect dataclass + a query helper + three routed reads), no new
  decision kind, no trigger/decision-machinery change.
- **New self-contained `"move_upgrade"` decision kind
  (`actions.push_move_upgrade`)** for "You may attach an upgrade on a unit to
  another eligible unit controlled by the same player." A *relocation* of an
  existing in-play upgrade (not a replay — no `WhenPlayed` re-fire): two stages
  driven by one decision — `MoveUpgradeSelect(upgrade_id)` (a movable non-token
  upgrade) / `DeclineMoveUpgrade` (the "you may"), then `MoveUpgradeTo(dest_id)`.
  An upgrade is *movable* when its current host has ≥1 other legal host controlled
  by the same player; eligibility reuses the existing attach machinery
  (`_eligible_upgrade_targets` / `_upgrade_target_spec`); token upgrades
  (Shield/Experience) are excluded, matching the engine-wide `kind="upgrade"`
  convention (Disabling Fang Fighter SHD_166). `_relocate_upgrade` detaches from
  the old host and attaches to the new one, updating the upgrade's zone tag. The
  decision is only pushed when something can actually be moved (a clean no-op
  otherwise). Registered in `invariants._KNOWN_DECISION_KINDS` and
  `web/session.py` (`_PROMPTS`); `HeuristicBot` gained a `_choose_move_upgrade`
  handler (declines — rearranging its own upgrades has no reliable heuristic
  value) and `DeclineMoveUpgrade` in its safe-default order. **Survivors' Gauntlet
  SHD_64** (Unit) is two thin `CustomEffect` adapters (`WhenPlayed` + `OnAttack`)
  onto `push_move_upgrade` (the Palpatine SOR_135 pattern). No change to core
  resolution or the trigger/decision machinery (a new self-contained decision
  kind, the allowed small-primitive path).
- Group readiness: **2/2**; deck `the-mandalorian` now **42/52** (3 groups left;
  next group `the-mandalorian:05`, then the capture escalation `the-mandalorian:07`
  and `the-mandalorian:08`).

**Engine primitive added (group `the-mandalorian:07`) — capture (The Mandalorian's
Rifle SHD_251, 2026-06-19):** the dedicated framework session the planner flagged.
**Key realisation:** the `CAPTURE_PILE` zone and `PlayerState.capture_pile` already
existed and were already wired into card conservation
(`all_instances`/`all_instances_for_player`), `find_instance`, serialisation, and
the invariants' zone scans — so capture is *not* a new zone; it is a new **effect**
plus two leave-play helpers, reusing all that scaffolding. A captured unit is
modelled as a card sitting in the **capturing player's** `capture_pile` with
`owner_id` unchanged and a new `CardInstance.captured_by` field = the captor's
instance_id (the "facedown under him" association); `_cards_in_play` only yields
arenas, so a captured card is automatically not targetable / not a trigger source /
not in `view_for` (it is hidden, as a facedown card should be). New pieces:
- **`registry.CaptureUnit(target=TargetSpec)`** effect — registered in
  `resolver._get_effect_target_spec` so the normal `resolve_effects`/`ChooseTarget`
  machinery enumerates and prompts for the target (**no new decision kind**), with
  one arm in `execute_effect`. The captor is read from `event_ctx["attached_to_id"]`
  (an upgrade's WhenPlayed threads it; survives the `_TRANSIENT` decision filter),
  defaulting to the source unit.
- **`actions._apply_capture(s, captor_id, target_id)`** — removes the target from
  its arena, defeats its upgrades (tokens vanish, real upgrades → owner's discard,
  mirroring `_defeat_unit`), expires modifiers on it, resets it (damage 0,
  `face_down=True`, `captured_by=captor`), and appends it to the captor's
  `capture_pile`. Emits a `UnitCaptured` event.
- **`actions._release_captured_cards(s, captor_ci)`** — called from `_defeat_unit`
  (the captor leaving play): returns every card it captured to its **owner's**
  matching arena under the owner's control, ready, damage cleared. Emits
  `UnitReturnedFromCapture`. Both new events serialise via the generic
  `event_to_model`; `web/src/game/format.ts` renders them.
- **SHD_251** is a `WhenPlayed` `TriggerAbility` gated by
  `ATTACHED_HOST_NAMED("The Mandalorian")` (so the whole trigger is collected only
  when the host is the Mandalorian, evaluated against the upgrade at collection
  time) whose one effect is `CaptureUnit(target=enemy non-leader exhausted unit)` —
  mandatory-if-able (fizzles with no eligible target). The non-Vehicle attach
  restriction is the upgrade-target parser.
- **Documented ASSUMPTION (pre-Capture CR v1.1 doesn't cover it):** a returned
  captured unit re-enters its owner's arena **ready** and does **not** re-fire
  enter-play triggers (capture-return treated as a relocation, not a fresh play) —
  flip the one `exhausted` line in `_release_captured_cards` if a newer CR says
  otherwise. **LIMITATIONS (no shipped card exercises these):** capture does not
  collect a captured unit's Bounty (the Bounty convention fires only on
  *WhenDefeated*), and release is wired into `_defeat_unit` only (the sole shipped
  captor is The Mandalorian, a Leader that leaves play only by defeat; a future
  captor bounced/control-changed while holding captives would need a release call on
  those paths). **No** new decision kind and **no** change to the trigger/decision
  machinery — a new effect dataclass + resolver arm + two leave-play helpers (the
  allowed small-primitive path). Tests: `tests/test_capture.py` (synthetic seam +
  invariants across capture/release) and
  `tests/test_shd_cards.py::TestTheMandaloriansRifle`.
- Group readiness: **1/1**; deck `the-mandalorian` now **45/52** (2 groups left;
  next group `the-mandalorian:05`, then `the-mandalorian:08`).

**Group `the-mandalorian:05` — Combat tricks, buffs & tempo (2026-06-19).** Three
cards, all composing from existing primitives — **no engine change, no
escape-hatch**. Tests: `tests/test_shd_cards.py::TestGrogu`,
`::TestSnapshotReflexes`, `::TestMandalorianWarrior`.
- **Grogu SHD_196** ("Action [Exhaust]: Exhaust an enemy unit") — a plain
  `ActivatedAbility(costs=[ExhaustSelf()], effects=[ExhaustCard(enemy unit)])`.
  Offered whenever Grogu is ready (the engine does not gate an activated ability on
  target existence); with no enemy unit the mandatory targeted effect fizzles
  silently (resolver skips an effect with no legal target), so the player simply
  never uses it then — an acceptable simplification, no condition needed.
- **Snapshot Reflexes SHD_223** (Upgrade, +1/+1; "When Played: You may attack with
  attached unit") — a `WhenPlayed` `TriggerAbility` whose one `CustomEffect` is a
  thin adapter calling `push_granted_attack(attacker_id=host, optional=True)` (the
  Hotshot DL-44 Blaster SHD_174 pin, but optional and on a normal play). The "may"
  is `optional=True` (a single decision offering the host's attack(s) +
  `DeclineGrantedAttack`); the "ready" restriction falls out of the attack
  enumeration (an exhausted host offers no attack, only the decline). The printed
  +1/+1 is the upgrade's own stat bonus, independent of the granted attack.
- **Mandalorian Warrior SHD_258** ("When Played: You may give an Experience token
  to another Mandalorian unit") — an optional `WhenPlayed`
  `GiveToken("Experience", target=another Mandalorian unit)` (`traits=
  ("Mandalorian",), predicates=("not_self",)`; `controller="any"` mirrors the
  printed text omitting "friendly", and an Experience token benefits the recipient
  so the controller never picks an enemy). With no other Mandalorian unit the
  optional trigger auto-declines (no prompt).
- Group readiness: **3/3**; deck `the-mandalorian` now **51/52** (1 group left;
  next group `the-mandalorian:08`).

**Group `the-mandalorian:08` — Combat tricks, buffs & tempo (2026-06-19).** One
card, composing from an existing primitive — **no engine change, no escape-hatch.**
Tests: `tests/test_shd_cards.py::TestSurpriseStrike`.
- **Surprise Strike SHD_231** (Event, Tactic; "Attack with a unit. It gets +3/+0
  for this attack.") is **identical to Surprise Strike SOR_220** — a plain
  `EventAbility` whose one `CustomEffect` is a thin adapter calling
  `push_granted_attack(power_bonus=3, hp_bonus=0)` (the granted_attack seam). The
  controller picks a unit to attack with; that unit gets +3/+0 via a `this_attack`
  stats modifier applied in `AttackWithUnit`. With no ready unit able to attack the
  (mandatory) grant fizzles cleanly via `DeclineGrantedAttack`.
- Group readiness: **1/1**; deck `the-mandalorian` now **52/52 — fully encoded**
  (all 8 groups complete; eligible for `verify_encoding.py the-mandalorian
  --graduate`).

**Group `moff-gideon:01` — Bounty keyword (2026-06-19).** Three cards. NOTE: the
planner labels this a "keyword" group, but Bounty is NOT a real keyword — it is
the WhenDefeated "opponent collects" ability template (see the Phase-2 Bounty
note). Two bounty-granting **upgrades** reuse the established
GrantedAbility(WhenDefeated)-from-a-defeated-host machinery (the-mandalorian:01);
The Client needed one small additive engine seam. No escape-hatch on any card.
Tests: `tests/test_shd_cards.py::TestTopTarget`, `::TestPriceOnYourHead`,
`::TestTheClient`.
- **Top Target SHD_71** (Upgrade) — `GrantedAbility(WhenDefeated → CustomEffect)`
  resolving from the host (the dying unit). The collector (opponent of the host's
  controller, via `_bounty_collector_id`) heals their base by **6 if the dying
  unit is unique else 4** (`source_ci.card_def.is_unique`). **Deviation
  (documented):** "Heal … from a unit **or base**" heals the collector's base only
  — the established bounty-heal convention (`Heal(controller="enemy", kind="base",
  fixed=EACH_ENEMY)` auto-heals the collector's base); the "or a unit" option is
  dropped to avoid a new collector-decided heal-target decision kind. The collector
  benefits from base healing (the safe default), so the loss is small.
- **Price on Your Head SHD_125** (Upgrade) — `GrantedAbility(WhenDefeated →
  CustomEffect)`; "your deck" is the collector's, so the collector puts the top
  card of **their own** deck into play as a ready resource (`Zone.RESOURCES`,
  `face_down`, not exhausted; emits `CardResourced`). Deterministic (deck order
  fixed) → resolves inline, no decision. Empty deck = clean no-op.
- **The Client SHD_31** (Unit, Shielded + the new seam) — "Action [Exhaust]:
  Choose a unit. For this phase it gains: 'Bounty — Heal 5 damage from a base.'"
  Shielded is the keyword layer. **New small additive seam:
  `CardInstance.granted_bounties: list[str]`** — phase-scoped bounties granted to a
  unit by another card's effect, each a tiny encoded key (only `"heal_base:N"`
  today) understood by `actions._resolve_granted_bounty`. The activated ability is
  an `ActivatedAbility(costs=[ExhaustSelf()], effects=[CustomEffect(fn, target=
  TargetSpec(controller="any", kind="unit"))])` — the CustomEffect.target seam
  prompts the controller to choose any unit (you point it at an enemy unit so YOU
  collect); the fn appends `"heal_base:5"` to that unit's `granted_bounties`. When
  the bountied unit is **defeated**, `_defeat_unit` resolves each granted bounty
  **inline** for the collector (opponent of the controller-at-death) — deterministic
  heal, so NO decision and NO change to the trigger/decision machinery (the bounty
  is NOT routed through `_collect_triggers`; addressing a non-registered granted
  ability through the trigger stack would have needed the spec-lookup tuple
  widened, which is the path the inline resolution avoids). The "for this phase"
  duration is enforced by clearing all arena units' `granted_bounties` at the round
  rollover (`_end_regroup`), bounding any lingering grant to its round (no combat
  in REGROUP). Serialised in `_instance_to_dict`/`_instance_from_dict`
  (back-compat default `[]`). This is the allowed small-primitive path: a new
  serialisable instance field + a deterministic inline resolver + a rollover clear;
  no new decision kind, no trigger-machinery change.
- Group readiness: **3/3**; deck `moff-gideon` now **15/52** (next group
  `moff-gideon:02`).

**Group `moff-gideon:02` — Direct damage & removal (2026-06-19).** Three cards;
all compose from existing primitives — **no engine change, no escape-hatch.**
Tests: `tests/test_shd_cards.py::TestDeathTrooper`, `::TestConfiscate`,
`::TestCalculatedLethality`.
- **Death Trooper SHD_30** (Unit, "When Played: Deal 2 damage to a friendly ground
  unit and 2 damage to an enemy ground unit") — a `WhenPlayed` with two mandatory
  `DealDamage(2, …)` effects, one targeting a friendly ground unit, one an enemy
  ground unit; the resolver prompts for each in turn. Death Trooper itself is a
  legal friendly ground-unit target (it's in play when its WhenPlayed resolves),
  faithful to the mandatory text.
- **Confiscate SHD_262** (Event, "Defeat an upgrade") — a plain `EventAbility` with
  one mandatory `DefeatUnit(kind="upgrade")` (the Disabling Fang Fighter SHD_166
  pattern, but mandatory); `kind="upgrade"` enumerates real (non-token) upgrades,
  fizzles cleanly with none in play.
- **Calculated Lethality SHD_39** (Event, Tactic, "Defeat a non-leader unit that
  costs 3 or less. For each upgrade that was on that unit, give an Experience token
  to a friendly unit") — a single `CustomEffect` carrying a TargetSpec (non-leader
  unit, `cost_max=3`): the resolver prompts for the unit, then the fn counts its
  attached upgrades, defeats it (`_apply_defeat_unit`), and — if it had any — calls
  `push_select_token(token_type="Experience", max_targets=<count>, controller=
  "friendly")` to give that many tokens. The dynamic per-upgrade count is why this
  is one CustomEffect rather than `[DefeatUnit, GiveToken]` — the count is only
  known after the unit is chosen and is gone once defeated, and `GiveToken` cannot
  place a state-derived number of distinct-target tokens. The pushed select_token
  lands as a **nested decision beneath the event's buried `resolve_effects`
  decision** (the SOR_233 nested-decision pattern, which `apply_resolve_effects`
  already handles — it leaves the buried decision in place and resumes it via
  AutoResolveEffects once select_token finishes); the event card sits in discard
  during resolution, where `find_instance` still locates it so `controller=
  "friendly"` resolves correctly. The friendly resolution is from `source.owner_id`,
  so the event owner's units are eligible recipients. **DEVIATION (minor):** counts
  all attached upgrades incl. Shield/Experience tokens (faithful — tokens are
  upgrade cards per CR); and select_token gives each token to a *distinct* friendly
  unit, whereas the literal text would let two tokens stack on one unit (negligible
  with a ≤3-cost unit's small upgrade count). No new decision kind, no
  trigger/decision-machinery change.
- Group readiness: **3/3**; deck `moff-gideon` now **22/52** (next group
  `moff-gideon:03`).

**Group `moff-gideon:03` — Card advantage & disruption (2026-06-19).** Three
cards; two compose from existing primitives, one extended the play-from-hand
subsystem with three small additive fields (no new decision kind, no
trigger/decision-machinery change) plus one new condition atom. No escape-hatch.
Tests: `tests/test_shd_cards.py::TestDoctorPershing`, `::TestRemnantReserves`,
`::TestGideonsLightCruiser`.
- **Doctor Pershing SHD_28** ("Action [Exhaust, deal 1 damage to a friendly
  unit]: Draw a card") — `ActivatedAbility(costs=[ExhaustSelf()],
  effects=[DealDamage(1, friendly unit), DrawCards(1)])`. There is no
  cost-shaped "deal damage" primitive, so the "deal 1 to a friendly unit" half
  of the printed cost is modelled as a **mandatory effect ahead of the draw** —
  behaviour-identical: a friendly unit always exists (Pershing itself, a 0/5, is
  a legal target; `not_self` deliberately omitted), so the damage is always
  payable and resolves before the draw exactly as a cost would.
- **Remnant Reserves SHD_93** ("Search the top 5 for up to 3 units, reveal and
  draw them; bottom the rest in a random order") — a thin `EventAbility`
  CustomEffect adapter onto the existing **deck_search** seam (`push_deck_search`,
  the Grand Moff Tarkin SOR_84 / This Is The Way SHD_253 pattern): `count=3,
  window=5, up_to=True, eligible=isinstance(Unit)`.
- **Gideon's Light Cruiser SHD_242** (Overwhelm — keyword layer; "When Played:
  If you control Moff Gideon (as a leader or unit), play a [villainy] unit that
  costs 3 or less from your hand or discard pile for free") — a `WhenPlayed`
  `CustomEffect` adapter gated by a new condition atom
  **`Condition.CONTROLLER_CONTROLS_NAMED(param="Moff Gideon")`** (true when the
  controller has a card whose name contains the param in play — the leader
  deployed or undeployed in `base_zone`, or a unit in an arena; substring match
  like `ATTACHED_HOST_NAMED`; "Gideon's Light Cruiser" does NOT contain "Moff
  Gideon", so no self-trigger). The trigger condition gates COLLECTION, so the
  play is offered only when the condition holds. The adapter calls
  `push_play_from_hand` with **three new optional, serialisable fields** added to
  the play-from-hand subsystem (`_playable_units_from_hand` /
  `push_play_from_hand` / `PlayFromHand` / the `play_from_hand` legal_actions
  branch): **`aspect`** (only units carrying that aspect — "[villainy]"),
  **`free`** (cost forced to 0 — "for free", skips the affordability check), and
  **`from_discard`** (candidates enumerated from the controller's discard pile in
  addition to hand — "from your hand or discard pile"; a new
  `_take_from_hand_or_discard` helper removes from whichever zone holds the chosen
  card, and a discard-played unit enters with `play_source="discard"`). These
  parallel the prior additive extensions of this same subsystem (`cost_reduction`/
  `then_damage` for Han SHD_13; `cost_max`/`grant_keyword` for the Sabine :04
  cards) — **no** new decision kind and **no** change to the trigger/decision
  machinery (the allowed small-primitive path).
- Group readiness: **3/3**; deck `moff-gideon` now **27/52** (next group
  `moff-gideon:04`).

**Group `moff-gideon:04` — Combat tricks, buffs & tempo (2026-06-20).** Seven
cards; three small additive engine seams (all on existing layers — the
granted_attack decision, the trigger registry+combat firing, and the
effective-stats read layer — none touching the decision/resolution machinery
destructively).  No escape-hatch on any card.  Tests:
`tests/test_shd_cards.py::TestMoffGideon`, `::TestGeneralTagge`,
`::TestOutlandTieVanguard`, `::TestSeasonedShoretrooper`,
`::TestPhaseIIIDarkTrooper`, `::TestSuperlaserTechnician`, `::TestPrivateerCrew`.
- **Two new optional `push_granted_attack` fields** (parallel to
  `attacker_trait`/`attacker_id`, both serialised in the `granted_attack`
  context): **`attacker_cost_max`** filters the offered AttackWithUnit options to
  attackers whose *printed* cost ≤ N (the legal_actions branch), and
  **`bonus_if_defender_unit`** gates the this-attack stat bonus on a unit defender
  (applied in `AttackWithUnit.apply`, like the existing `bonus_trait` gate, but on
  `self.defender_id is not None`).  **Moff Gideon SHD_7** undeployed Action
  ("Attack with a unit that costs 3 or less.  If it's attacking a unit, +1/+0") is
  a thin `CustomEffect` adapter (undeployed_only `ActivatedAbility`) onto
  `push_granted_attack(power_bonus=1, attacker_cost_max=3,
  bonus_if_defender_unit=True)` (the Surprise Strike SOR_220 pattern).
- **`while_attacking_unit` flag on `ConstantAbility`** threaded through
  `compute_power`/`_constant_ability_power_bonus` via a new `attacking_unit` bool
  (set True only at the _resolve_unit_combat attacker call — a unit attack;
  base attacks and defence leave it False).  A `while_attacking_unit` constant's
  `StatBonus` is contributed only when the buffed unit is attacking an enemy unit
  (the Raid-keyword pattern, but as a constant over *other* units); its hp side is
  skipped entirely in `_constant_ability_hp_bonus` (no combat context there).
  Moff Gideon's deployed constant ("Each friendly unit that costs 3 or less gets
  +1/+0 and gains Overwhelm while attacking an enemy unit") is a
  `ConstantAbility(target=friendly cost≤3 units, effects=[StatBonus(1,0),
  KeywordGrant("Overwhelm")], while_attacking_unit=True)` — the StatBonus is gated
  precisely; the Overwhelm KeywordGrant is reported always by the keyword layer
  (which has no combat context) but is harmless, since Overwhelm only matters when
  attacking a unit anyway.  The constant is active only while Gideon is in the
  arena (deployed), as the constant scan sees only arena sources — no explicit
  deployed-only flag needed.  Overwhelm (Gideon's own printed bar) is the keyword
  layer; the Epic Action deploy is the standard `deploy_threshold` machinery.
- **New `WhenDealtCombatDamage` trigger** (registry + a `_trigger_matches` arm +
  one combat firing site) for "When combat damage is dealt to this unit" — fired
  from `_resolve_unit_combat` after defeat processing for each unit (defender,
  then attacker) that took >0 combat damage AND is still in play, so the printed
  "(if it survives the damage)" clause is intrinsic (mirrors the
  `dealt_combat_damage_to_base`/Ketsu Onyo SHD_147 event-context-flag pattern, no
  dedicated event class).  **Phase-III Dark Trooper SHD_84** (Sentinel — keyword
  layer) is a `WhenDealtCombatDamage` whose mandatory self-targeted
  `GiveToken("Experience", fixed=SELF)` resolves inline.
- **General Tagge SHD_81** ("Give an Experience token to each of up to 3 Trooper
  units") — a thin `WhenPlayed` CustomEffect onto `push_select_token(token_type=
  "Experience", max_targets=3, traits=["Trooper"])` (the Armorer SHD_47 /
  Medal Ceremony SOR_245 select-up-to-N pattern; `controller="any"` mirrors the
  printed text, the recipient benefits so the controller never picks an enemy).
- **Outland TIE Vanguard SHD_82** ("You may give an Experience token to another
  unit that costs 3 or less") — an optional `WhenPlayed` `GiveToken("Experience",
  another `not_self` unit, cost_max=3)`; with no eligible target the optional
  trigger auto-declines.
- **Seasoned Shoretrooper SHD_83** ("While you control 6 or more resources, +2/+0")
  — a self-targeted `ConstantAbility(StatBonus(2,0),
  condition=CONTROLLER_N_PLUS_RESOURCES(6))`, read passively by compute_power.
- **Superlaser Technician SHD_85** ("When Defeated: You may put this unit into
  play as a resource and ready it") — an optional `WhenDefeated` whose one
  no-target `CustomEffect` relocates the just-defeated card.  Because the trigger
  is optional it defers (AcceptTrigger/DeclineTrigger) — by the time it resolves
  `_defeat_unit` has already placed the card in its owner's discard (the
  relocate-on-defeat fast path applies only to *inline* relocations), so the fn
  simply moves it discard → resource zone (face-down, ready, damage cleared) and
  emits CardResourced; no `relocated_by_trigger` flag needed.  The "you may" is
  always offered (a non-targeted effect can always do something).
- **Privateer Crew SHD_113** (Smuggle [6, Command] — keyword layer) — a
  `WhenPlayedViaSmuggle` whose mandatory `GiveToken("Experience", fixed=SELF,
  count=3)` gives itself 3 Experience tokens inline (fires only on a Smuggle play).
- Group readiness: **7/7**; deck `moff-gideon` now **42/52** (3 groups left;
  next group `moff-gideon:05`).

**Group `moff-gideon:05` — Combat tricks, buffs & tempo (2026-06-20).** Four
cards, all composing from existing primitives — one tiny additive seam (a new
target predicate), no new decision kind, no trigger/decision-machinery change, no
escape-hatch. Tests: `tests/test_shd_cards.py::TestKihraxzHeavyFighter`,
`::TestOutflank`, `::TestMomentOfGlory`, `::TestSnowtrooperLieutenant`.
- **New `ready` target predicate** (`resolver._spec_matches_ci`, the inverse of
  the existing `exhausted`) so a TargetSpec can restrict to a ready (non-exhausted)
  unit. **Kihraxz Heavy Fighter SHD_118** (Overwhelm — keyword layer; "On Attack:
  You may exhaust another friendly unit. If you do, this unit gets +3/+0 for this
  attack") is an **optional** `OnAttack` trigger (the "you may") whose one
  `CustomEffect` carries `target=TargetSpec(controller="friendly", kind="unit",
  predicates=("not_self","ready"))`: choosing a unit exhausts it and applies a
  +3/+0 `this_attack` modifier to Kihraxz. Cost and buff are **bound in one
  CustomEffect** so "If you do" holds (the Bright Hope SOR_99 pattern — could not
  be `[ExhaustCard, ModifyStats(fixed=SELF)]`, since a fixed-SELF buff would apply
  regardless of whether a unit was exhausted, and a fixed effect would make
  `_optional_trigger_has_legal_effect` always offer the trigger). The optional
  trigger auto-declines when no other ready friendly unit exists (the gate consults
  the CustomEffect's target).
- **Outflank SHD_128** ("Attack with 2 units (one at a time)") — an `EventAbility`
  whose one `CustomEffect` calls `push_granted_attack` **twice** (the Rebel Assault
  SOR_103 pattern): the two granted attacks sit on the LIFO stack and resolve one
  at a time; "2 different units" falls out of exhaustion (the first attacker is
  exhausted by its attack). Each is mandatory-if-able; spare grants fizzle via
  `DeclineGrantedAttack`.
- **Moment of Glory SHD_130** ("Give a unit +4/+4 for this phase") — a plain
  `EventAbility([ModifyStats(power=4, hp=4, target=any unit, THIS_PHASE)])`.
- **Snowtrooper Lieutenant SHD_236** ("When Played: You may attack with a unit. If
  it's an Imperial unit, it gets +2/+0 for this attack") — a `WhenPlayed` whose one
  `CustomEffect` is a thin adapter calling `push_granted_attack(power_bonus=2,
  optional=True, bonus_trait="Imperial")` (the existing `bonus_trait` gate, the
  Fleet Lieutenant conditional-bonus pattern): `optional=True` for the "you may"
  (a `DeclineGrantedAttack` is always offered) and the +2/+0 applies only when the
  chosen attacker is Imperial. The "ready friendly unit" restriction is intrinsic
  to the attack enumeration.
- Group readiness: **4/4**; deck `moff-gideon` now **47/52** (2 groups left;
  next group `moff-gideon:06`).

**Group `moff-gideon:06` — Miscellaneous abilities (2026-06-20).** One card,
composing from an existing keyword — **no engine change, no escape-hatch.** Tests:
`tests/test_shd_cards.py::TestIncineratorTrooper`.
- **Incinerator Trooper SHD_234** ("While attacking, this unit deals combat damage
  before the defender. (If the defender is defeated, it deals no combat damage.)")
  is exactly **First Strike** — already fully implemented in the combat pipeline
  (`_resolve_unit_combat_step2`: the attacker deals its damage first and the
  defender deals none back if defeated). Modelled as a constant self-grant of the
  First Strike keyword, identical to Han Solo SOR_198's innate First Strike:
  `ConstantAbility(target=TargetSpec(fixed=SELF),
  effects=[KeywordGrant("First Strike", value=0)])`. The combat pipeline consults
  `has_keyword(attacker, FIRST_STRIKE)` only when this unit is the attacker, so the
  "while attacking" restriction falls out for free.
- Group readiness: **1/1**; deck `moff-gideon` now **50/52** (1 group left; next
  group `moff-gideon:07` — the capture escalation).

**Group `moff-gideon:07` — New primitive: capture (2026-06-20).** Two more
capturers, both reusing the **capture** primitive added for the-mandalorian:07
(the `registry.CaptureUnit` effect + `actions._apply_capture` /
`_release_captured_cards`). Only one additive engine seam was needed; no change to
core resolution or the trigger/decision machinery, no escape-hatch on either card.
Tests: `tests/test_shd_cards.py::TestDiscerningVeteran`, `::TestLegalAuthority`.
- **Discerning Veteran SHD_120** (Unit) — "When Played: This unit captures an enemy
  non-leader ground unit." A plain `WhenPlayed` `CaptureUnit(target=enemy
  non-leader ground unit)`. Unlike The Mandalorian's Rifle, the captor is the
  source UNIT itself (it captures via its own ability, not an upgrade), so there is
  no `event_ctx["attached_to_id"]` and the resolver's `CaptureUnit` arm falls back
  to `source_ci` as captor (the card sits facedown under the Veteran). Mandatory-if-
  able (fizzles with no eligible enemy ground unit).
- **Legal Authority SHD_124** (Upgrade, attach to a friendly unit) — "When Played:
  Attached unit captures an enemy non-leader unit with less power than it." A
  `WhenPlayed` `CaptureUnit` like the Rifle (captor = the attached host via
  `event_ctx["attached_to_id"]`), but with **no** name gate. The "with less power
  than it" restriction is the **one new seam: a `TargetSpec.power_less_than_captor`
  bool** (registry) + one arm in `resolver._spec_matches_ci` — the candidate's
  **effective** `compute_power` must be strictly less than the *capturing* unit's
  effective power, where the captor is resolved the same way the effect resolves it
  (`event_ctx["attached_to_id"]` else `source_ci`). The captor id is available
  during target *enumeration* because the decision persists the trigger's
  `event_ctx` (only `defeated_ci`/`defeated_upgrades` are stripped), so the
  weaker-than-host filter and the actual capture agree. Purely additive (a new
  TargetSpec field + a resolver predicate arm; the allowed small-primitive path).
- Group readiness: **2/2**; deck `moff-gideon` now **52/52 — fully encoded** (all
  7 groups complete; eligible for `verify_encoding.py moff-gideon --graduate`).

**Group `leia-organa:01` — Direct damage & removal (2026-06-20).** Three cards
(the deck's first encoded group — **new card sets LAW + JTL**, registered via
`src/swu/cards/law/` and `src/swu/cards/jtl/`, both imported from
`src/swu/cards/__init__.py`). Three small additive engine seams, none touching
core resolution or the trigger/decision machinery. No escape-hatch on any card.
Tests: `tests/test_law_cards.py`.
- **New `power_le_event_threshold` target predicate** (`resolver._spec_matches_ci`)
  — effective power must be ≤ a numeric threshold an earlier effect stashed in
  `event_ctx["power_le_threshold"]`. **Nothing Left to Fear LAW_41** (Event,
  "Choose a friendly unit, give it +2/+2 for this phase; then you may defeat a
  non-leader unit with power ≤ the chosen unit") is an `EventAbility` whose two
  effects share the resolve_effects decision's `event_ctx` dict: a mandatory
  `CustomEffect(target=friendly unit)` applies the +2/+2 (a `this_phase` stats
  modifier) and records the *buffed* unit's `compute_power` as the threshold;
  then an optional `DefeatUnit(target=non-leader, power_le_event_threshold)` reads
  it. The two-target dependency (second target's eligibility keys off the first
  chosen target) is threaded by the shared mutable `event_ctx` — no new decision
  kind.
- **Conditional-magnitude via CustomEffect.target.** **Zeb Orellios LAW_45** (Unit,
  Sentinel — keyword layer; "When Played: you may deal 3 to a ground unit; if you
  control a Command or Cunning unit, deal 5 instead") is an optional `WhenPlayed`
  whose one `CustomEffect(target=ground unit)` decides the magnitude (3 vs 5)
  inside the fn from the board — controlling a Command **or** Cunning unit, an OR
  of two aspects a single Condition atom cannot express. Auto-declines with no
  ground unit.
- **New `TargetSpec.require_controller_aspect` field** (registry + one
  `_spec_matches_ci` board-precondition gate: NO candidate matches unless the
  source controller controls a unit with the named aspect; the source counts) and
  a **new `exhaust_resource` modal mode** (`actions._MODAL_MODE_LABELS` /
  `_MODAL_FUNGIBLE_MODES` / `_resolve_modal_mode` / `_modal_mode_targets`,
  exhaust a ready resource — the inverse of `ready_resource`; web prompt added).
  **Sabine's Masterpiece JTL_250** (Unit; "On Attack: If you control a Vigilance
  unit heal 2 from a base; Command unit give Experience to a unit; Aggression unit
  deal 1 to a unit/base; Cunning unit exhaust or ready a resource") is registered
  as **four separate single-effect OnAttack abilities** (not one 4-effect ability)
  — each clause's one target choice then sits at effect index 0, sidestepping the
  resolve_effects "skip-earlier-no-target-effect" wart (`apply_resolve_effects`
  consumes a choice against the current `effect_idx` without skipping an earlier
  *gated-off* effect, cf. The Mandalorian SHD_18's fixed-before-targeted note).
  The first three clauses are plain targeted effects gated by
  `require_controller_aspect` (an inactive clause has no legal target → that
  ability resolves inline as a silent no-op); the Cunning clause is a CustomEffect
  pushing a fungible exhaust/ready `push_modal` (Leia SOR_189 seam). Clause
  independence makes the resolution order among them immaterial.
- Group readiness: **3/3**; deck `leia-organa` now **14/52** (next group
  `leia-organa:02`).

**Group `leia-organa:02` — Card advantage & disruption (2026-06-20).** Three
cards; two compose from the existing `deck_search` seam, one needed two small
additive seams (a `reveal_top` disposition extension + a `WhenUnitDefeated`
filter fix). No new decision kind, no trigger/decision-machinery change, no
escape-hatch. Tests: `tests/test_law_cards.py::TestRogueOne`, `::TestR2D2`,
`::TestPuttingATeamTogether`.
- **`reveal_top` `disposition` extension + `WhenUnitDefeated` filter fix.**
  **Rogue One LAW_119** ("When a friendly unit is defeated: Look at the top 2
  cards of your deck. Put any number on the bottom and the rest on top in any
  order") reuses the `reveal_top` seam (`push_reveal_top_discard_reorder`, the For
  a Cause I Believe In SOR_152 pattern) with two new optional params:
  **`deal_aspect_damage=False`** (skip the SOR_152 Heroism-base-damage — Rogue One
  is a plain "look", no damage) and **`disposition="bottom"`** (a not-kept
  revealed card goes to the **bottom of the deck** instead of the discard pile;
  `DiscardRevealed.apply` reads `ctx["disposition"]` and appends to `ps.deck`,
  while `KeepRevealed` still tops it — `_maybe_finish_reveal_top` is unchanged and
  reorders the kept cards to the top, leaving the appended/bottomed ones below).
  The trigger is `WhenUnitDefeated(filter=friendly unit)`, but the existing filter
  match was **bypassed** when the defeated unit had already left play (the always
  case — `_defeat_unit` removes the unit before `UnitDefeated` fires, so
  `find_instance` returns None and the old code returned True on a bare
  `defeated_id` match, ignoring the filter). Fixed `_trigger_matches`'
  `WhenUnitDefeated` branch to apply the filter against `event_ctx["defeated_ci"]`
  (its `owner_id`/arena zone are intact at firing time) when the unit is out of
  play, so a friendly-only observer is not fired for an enemy's defeat. Rogue One
  does **not** self-trigger (its own defeat removes it from `_cards_in_play`
  before the event, so it is not collected as a source — a defensible reading of
  "a friendly unit"). Both changes are purely additive (a param + a routing arm +
  a stricter filter), no new decision kind.
- **R2-D2 LAW_145** ("When Played: Search the top 5 for a unit that shares an
  aspect with a friendly unit, reveal and draw it") — a thin `WhenPlayed`
  CustomEffect adapter onto `push_deck_search(count=1, window=5, up_to=False)`
  whose `eligible` closure captures the aspects of the controller's units (R2-D2
  itself is in play when its When Played resolves, so its own Command/Heroism
  count). **Putting a Team Together LAW_166** (Event) — `push_deck_search(count=1,
  window=8, up_to=False)`, eligible = a unit carrying Vigilance, Aggression, or
  Cunning. Both mandatory-if-able (no "up to" → a unit is taken while one remains).
- Group readiness: **3/3**; deck `leia-organa` now **20/52** (next group
  `leia-organa:03`).

**Group `leia-organa:03` — Combat tricks, buffs & tempo (2026-06-20).** Seven
cards (the deck's **first SEC-set** cards — new module `src/swu/cards/sec/`,
imported from `src/swu/cards/__init__.py`); four small additive engine seams,
none touching core resolution or the trigger/decision machinery destructively; no
escape-hatch on any card. Tests: `tests/test_law_cards.py` (LAW + SEC, deck
`leia-organa`).
- **New `WhenDeployed` trigger** (registry + a `_trigger_matches` arm matching the
  `LeaderDeployed` event for the source leader + a new firing site: `DeployLeader`
  now calls `fire_triggered_abilities` for its deploy event, additive — a no-op
  unless a `WhenDeployed` observer is present, since no other trigger matches
  `LeaderDeployed`). The deployed leader is already in the arena when it fires, so
  `_collect_triggers`' arena scan sees it (mark `deployed_only=True`). **Leia
  Organa LAW_10** (Leader, Overwhelm — keyword layer): the undeployed Action [2
  resources, Exhaust] "give a unit +1/+1 for each different aspect it has" is an
  `undeployed_only` ActivatedAbility whose one CustomEffect.target applies a
  *scaling* this-phase `_make_modifier` (+N/+N, N = the chosen unit's distinct
  aspect count — a fixed ModifyStats cannot express it); the deployed "When
  Deployed: give a chosen unit an Experience token for each different aspect among
  units you control" is a `WhenDeployed` whose CustomEffect.target gives a
  state-derived number of tokens. The Epic Action deploy is standard
  `deploy_threshold` machinery.
- **New `give_experience_unit` modal mode** (`_MODAL_MODE_LABELS` /
  `_resolve_modal_mode` / `_modal_mode_targets`, non-fungible — the target choice
  matters). **Jyn Erso LAW_67** ("When Played: Either give an Experience token to a
  unit or exhaust a unit") is a mandatory WhenPlayed whose one CustomEffect is a
  thin adapter onto `push_modal(["give_experience_unit", "exhaust_unit"])` (the
  Leia SOR_189 seam); Jyn is in play when it resolves so the give-token mode always
  has a target (never a full fizzle).
- **Four new `push_granted_attack` fields for "attack with any number of units"**
  (all serialised in the existing `granted_attack` context — **no** new decision
  kind): **`repeat`** (after each granted attack resolves, AttackWithUnit re-pushes
  the decision with the just-attacked unit added to a context `already_attacked`
  list, so each of the "any number" units attacks at most once and the loop
  terminates; combine with `optional` so a decline ends it), **`allow_exhausted`**
  (offer EXHAUSTED units too — a new `include_exhausted` param on
  `_enumerate_attacks`, plus the AttackWithUnit "attacker is exhausted" guard is
  bypassed for a granted attack carrying the flag), **`no_base`** (drop the
  attack-a-base option), and **`exclude_source`** ("*other* units"). The existing
  per-filter logic in the `granted_attack` legal_actions branch was factored into a
  shared `_filter_granted_attacks` helper used by both the branch and the re-push,
  so they agree on eligibility. **Mon Mothma SEC_103** (Restore 3 — keyword layer;
  "When Played: You may attack with any number of other units (one at a time), even
  if exhausted; they can't attack bases") is a mandatory WhenPlayed whose one
  CustomEffect adapter calls `push_granted_attack(optional=True, repeat=True,
  allow_exhausted=True, no_base=True, exclude_source=True)`. **LIMITATION
  (documented in `push_granted_attack`):** the re-push happens at the end of
  AttackWithUnit, so if a single attack itself requires a mid-attack decision (a
  `pre_attack` continuation from a choice-requiring OnAttack trigger), control
  returns through ContinueAttack and the loop ends early — no shipped repeat-grant
  card has such a trigger on its other units, so it is not exercised.
- **C-3PO SEC_93** ("Action [Exhaust, return this unit to its owner's hand]: Give a
  unit +2/+2 for this phase") — an ActivatedAbility whose Exhaust cost is a real
  `ExhaustSelf`; the "return this unit to hand" cost is modelled as a trailing
  `ReturnToHand(fixed=SELF)` effect (there is no return-self cost spec). The +2/+2
  ModifyStats is ordered FIRST (a targeted effect ahead of the fixed-SELF return,
  so the player is prompted exactly once — the Mandalorian SHD_18 fixed-before-
  targeted lesson) and excludes C-3PO itself (`not_self`, since the cost returns it
  to hand before the buff would land).
- **Han Solo LAW_37** ("On Attack: Give an Experience token to this unit") — a plain
  OnAttack `GiveToken("Experience", fixed=SELF)` (inline). **Ezra Bridger LAW_35**
  (Raid 1 — keyword layer; "When Played: You may heal 2, or 4 if you control an
  Aggression or Cunning unit") — the Zeb Orellios LAW_45 conditional-magnitude
  pattern (an optional WhenPlayed CustomEffect.target whose heal magnitude is
  decided from the board; `predicates=("damaged",)` so it auto-declines with
  nothing to heal). **Cinta Kaz LAW_105** ("While this unit is upgraded, she gains
  Sentinel") — a self-targeted constant `KeywordGrant("Sentinel")` gated by
  SOURCE_UPGRADED (the Protector of the Throne SHD_247 pattern; the keyword
  sanitiser strips Cinta's printed Sentinel because this conditional self-grant is
  registered).
- Group readiness: **7/7**; deck `leia-organa` now **32/52** (next group
  `leia-organa:04`).

**Group `leia-organa:04` — Combat tricks, buffs & tempo (2026-06-20).** Six
cards, all composing from existing primitives — **one tiny additive seam** (a new
target predicate), no new decision kind, no trigger/decision-machinery change, no
escape-hatch. Tests: `tests/test_law_cards.py::TestLeiasDisguise`,
`::TestScarifLieutenant`, `::TestJauntyLightFreighter`, `::TestC3POLAW`,
`::TestCommonCause`, `::TestMaarvaAndor`.
- **Leia's Disguise LAW_111** (Upgrade) — two specs: a `ConstantAbility(target=
  SELF, effects=[TraitGrant("Underworld")])` (the Foundling SHD_69 pattern — the
  trait query layer reads the host's effective traits) for "Attached unit gains the
  Underworld trait", plus a `WhenPlayed GiveToken("Shield", friendly unit)` gated
  by `ATTACHED_HOST_NAMED("Leia Organa")` (the Mandalorian's Rifle SHD_251 pattern,
  collected only when the host is named Leia Organa). The non-Vehicle attach
  restriction is the upgrade-target parser.
- **New `shares_trait_with_friendly_leader` target predicate**
  (`resolver._spec_matches_ci`) for **C-3PO LAW_152** ("On Attack: You may give an
  Experience token to another non-leader unit that shares a Trait with a friendly
  leader"). The candidate's *effective* traits (printed + granted) must intersect
  the controller's leader's effective traits; the friendly leader is
  `PlayerState.leader_instance` (deployed in an arena OR undeployed in base_zone),
  so the check works pre- and post-deploy. C-3PO is an optional `OnAttack`
  `GiveToken("Experience", another non_leader unit, shares_trait_with_friendly_
  leader)`; `controller="any"` mirrors the printed text but the recipient benefits
  so the controller never picks an enemy; with no friendly leader / no trait-share
  the optional trigger auto-declines.
- **Scarif Lieutenant LAW_142** — `WhenDefeated GiveToken("Experience", friendly
  Rebel unit)` (mandatory-if-able; the dying unit has left play so is never its own
  recipient). **Maarva Andor SEC_252** — `WhenDefeated GiveToken("Experience",
  fixed=EACH_FRIENDLY Rebel unit)` (auto-targets each friendly Rebel inline, no
  prompt). **Jaunty Light Freighter LAW_147** — `WhenPlayed` CustomEffect giving
  SELF a state-derived number of Experience tokens (= distinct aspects among the
  controller's units; the Leia LAW_10 `_leia_deploy_tokens` scaling pattern, fixed
  on SELF). **Common Cause LAW_167** (Event) — `EventAbility` CustomEffect.target
  buffing the chosen unit +N/+N this phase (N = the same distinct-aspect count;
  scaling `_make_modifier`, the Leia LAW_10 `_leia_buff` pattern).
- **Test-helper fidelity fix** (`tests/test_law_cards.py::_fire_unit_defeated`):
  the real `_defeat_unit` fires WhenDefeated while the card is out of every zone,
  then homes it in the owner's **discard** before the pushed decision is resolved —
  so a self-WhenDefeated whose effect *targets* (Scarif's "give to a friendly Rebel
  unit") finds its source in discard during `resolve_effects_actions`. The helper
  previously left the defeated unit in no zone, so `find_instance(source)` returned
  None and the resolver offered a fizzling `AutoResolveEffects` instead of the
  `ChooseTarget`s. The helper now appends the defeated card to its owner's discard
  after firing, mirroring the engine (Maarva's `EACH_FRIENDLY`, which resolves
  inline regardless of source location, was unaffected and already passed).
- Group readiness: **6/6**; deck `leia-organa` now **47/52** (1 group left;
  next group `leia-organa:05`).

**Group `leia-organa:05` — Miscellaneous abilities (2026-06-20).** Three cards;
two small additive engine seams (one on the play-from-hand subsystem, one on the
effective-stats read layer), no new decision kind, no trigger/decision-machinery
change, no escape-hatch. Tests: `tests/test_law_cards.py::TestDaimyosPalace`,
`::TestBodhiRook`, `::TestLandoCalrissian`. **`leia-organa` is now fully encoded
(52/52); eligible for `verify_encoding.py leia-organa --graduate`.**
- **New `ignore_aspect_penalty` field on the play-from-hand subsystem**
  (`push_play_from_hand` / `_playable_units_from_hand` / `PlayFromHand.apply` /
  the `play_from_hand` legal_actions branch, all serialised in the decision
  context — the same additive-field pattern as `cost_reduction`/`cost_max`/`free`/
  `aspect`/`from_discard`). When set, one Vigilance/Command/Aggression/Cunning
  aspect-penalty pip is waived (2 resources, via the new `_ignorable_aspect_penalty`
  helper) — **only when the card actually carries such a penalty** (a fully-matched
  card is never discounted) and **never** a Heroism/Villainy penalty (the card
  excludes those). Combines additively with `cost_reduction`, floored at 0. A new
  gating condition `CONTROLLER_CAN_PLAY_UNIT_FROM_HAND_IGNORE_ASPECT_PENALTY`
  (reusing `_playable_units_from_hand` so gate and offered candidates never
  disagree). **Daimyo's Palace LAW_20** (Base) is an `ActivatedAbility(epic=True,
  costs=[])` whose one CustomEffect is a thin adapter onto
  `push_play_from_hand(ignore_aspect_penalty=True)` (the Energy Conversion Lab
  SOR_22 base-Epic-Action pattern; base activated abilities are enumerated via the
  existing base_zone scan). **DEVIATION (documented):** "Play a **card**" is
  restricted to **units** — the play-from-hand subsystem plays only units;
  events/upgrades would need the PlayCard resolution path threaded through it (a
  larger change to core play resolution). The aspect-penalty waiver itself is
  faithful.
- **New `while_defending` flag on `ConstantAbility`** threaded through
  `compute_power`/`_constant_ability_power_bonus` via a new `defender_id` param
  (set only at the `_resolve_unit_combat_step2` attacker-power call). A
  `while_defending` constant contributes its StatBonus to its target **only while
  the source is the current combat defender** (`source_ci.instance_id ==
  defender_id`); its hp side is skipped entirely in `_constant_ability_hp_bonus`
  (no combat context, the only such card debuffs −0 hp anyway). **Lando Calrissian
  LAW_108** (Sentinel — keyword layer; "While this unit is defending, the attacker
  gets −1/−0") is a `ConstantAbility(target=TargetSpec(controller="enemy",
  kind="unit"), effects=[StatBonus(power=-1)], while_defending=True)` — the
  defender-id gate means the debuff lands solely on the unit attacking Lando, not
  on enemy units generally and not when Lando attacks (the Moff Gideon SHD_7
  `while_attacking_unit` combat-context pattern, mirrored for the defender side).
- **Bodhi Rook LAW_104** (Sentinel — keyword layer; "On Attack: You may give a
  friendly Rebel unit Sentinel for this phase") — an optional `OnAttack`
  `GrantKeyword("Sentinel", target=friendly Rebel unit, THIS_PHASE)` (a
  keyword_grant modifier honoured by `has_keyword`). Bodhi is himself a friendly
  Rebel unit so the optional trigger always has a legal target (the controller
  simply chooses which Rebel — typically a blocker, not the attacking Bodhi).
- Group readiness: **3/3**; deck `leia-organa` now **52/52 — fully encoded** (all
  5 groups complete).

**Group `ahsoka-tano:02` — Direct damage & removal (2026-06-27).** Two TWI event
cards; one tiny additive seam (a new target predicate), no new decision kind, no
trigger/decision-machinery change, no escape-hatch. Tests:
`tests/test_twi_cards.py::TestGrenadeStrike`, `::TestOpenFire`.
- **Open Fire TWI_174** ("Deal 4 damage to a unit") — a plain
  `EventAbility([DealDamage(4, any unit)])`; mandatory-if-able.
- **Grenade Strike TWI_171** ("Deal 2 damage to a unit. You may deal 1 damage to
  another unit in the same arena") — two sequential effects sharing the
  resolve_effects `event_ctx` (the Haymaker LAW_168 / Nothing Left to Fear LAW_41
  pattern): a mandatory `CustomEffect.target` (any unit) deals 2 and records the
  hit unit's id + arena (`event_ctx["excluded_target_id"]`/`["same_arena"]`); an
  optional `CustomEffect.target` deals 1 to "another unit in the same arena",
  filtered by the existing `same_arena_as_event` predicate **plus a new
  `excludes_event_target` predicate** (`resolver._spec_matches_ci` — candidate must
  not be the id recorded in `event_ctx["excluded_target_id"]`, i.e. "another"). The
  second is a "you may" (`optional=True` → a `DeclineTarget` is offered), and only
  appears when an eligible other same-arena unit exists. Purely a new predicate arm
  (the allowed small-primitive path).
- Group readiness: **2/2**; deck `ahsoka-tano` now **30/52** (next group
  `ahsoka-tano:03`).

**Group `ahsoka-tano:03` — Card advantage & disruption (2026-06-27).** Two TWI
units; both compose from existing seams, one of which gained two additive fields.
No new decision kind, no trigger/decision-machinery change, no escape-hatch.
Tests: `tests/test_twi_cards.py::TestPatrollingVWing`, `::TestTranquility`.
- **Patrolling V-Wing TWI_107** ("When Played: Draw a card") — a plain
  `TriggerAbility(WhenPlayed, [DrawCards(1)])`.
- **Tranquility TWI_246** — two triggers. **When Played** ("You may return a
  Republic unit from your discard pile to your hand") is a thin `CustomEffect`
  adapter onto the existing **return_from_discard** decision kind
  (`push_return_from_discard(count=1, eligible=Republic-unit)`, the Razor Crest
  SHD_44 pattern); the controller may take up to one or finish (the "you may"),
  pushed only when a Republic unit is in the discard pile. **On Attack** ("Each of
  the next 3 Republic cards you play this phase costs 1 resource less") reuses the
  Khetanna LAW_158 deferred-discount seam (`NextPlayDiscount`), extended with two
  small additive fields: **`count`** (record N pending entries at once → `count=3`,
  each consumed by one subsequent matching play) and **`units_only`** (default True
  keeps Khetanna's "next <trait> *unit*"; `units_only=False` here for "Republic
  *cards*", so events/upgrades qualify too — `_pending_play_discount`/
  `_consume_play_discount` now check a per-entry `units_only` instead of a blanket
  unit-only guard, old entries default True for back-compat). Tranquility is
  `OnAttack → [NextPlayDiscount("Republic", amount=1, count=3, units_only=False)]`.
  LIMITATION (inherited from Khetanna): the discount applies only on the normal
  `PlayCard` path and its affordability gates, not the ability-driven
  play-from-hand subsystem (which pays the raw effective cost) — the common case.
  Purely additive fields on an existing effect + helper (the small-primitive path).
- Group readiness: **2/2**; deck `ahsoka-tano` now **33/52** (next group
  `ahsoka-tano:04`).

**Group `ahsoka-tano:04` — Combat tricks, buffs & tempo (2026-06-27).** Seven TWI
cards; six compose from existing primitives, one needed a tiny additive seam (a
new condition atom). No new decision kind, no trigger/decision-machinery change,
no escape-hatch. Tests: `tests/test_twi_cards.py::TestRepublicTacticalOfficer`,
`::TestAdmiralYularen`, `::Test501stLiberator`, `::TestOutflankTWI`,
`::TestEncouragingLeadership`, `::TestAnakinsInterceptor`,
`::TestAhsokasPadawanLightsaber`.
- **Republic Tactical Officer TWI_91** ("When Played: You may attack with a
  Republic unit. It gets +2/+0 for this attack") — a `WhenPlayed` whose one
  `CustomEffect` is a thin adapter onto `push_granted_attack(power_bonus=2,
  optional=True, attacker_trait="Republic")` (the Snowtrooper Lieutenant SHD_236 /
  Rebel Assault SOR_103 pattern, both fields pre-existing). The officer enters
  exhausted so it is not offered as the attacker the turn it is played; other ready
  Republic units are. No engine change.
- **Admiral Yularen TWI_92** (Restore 1 — keyword layer; "Each other friendly
  Heroism unit gets +0/+1") — a `ConstantAbility(target=friendly Heroism unit,
  not_self, StatBonus(0,1))`, read passively by `compute_hp` (the Red Three SOR_144
  pattern). No engine change.
- **501st Liberator TWI_109** ("When Played: If you control another Republic unit,
  you may heal 3 damage from a base") — an **optional** `WhenPlayed` `Heal(3,
  friendly base fixed=EACH_FRIENDLY)` gated by `CONTROLLER_HAS_OTHER_TRAIT_UNIT(
  "Republic")` (the Cargo Juggernaut SHD_66 heal-own-base pattern, but optional —
  the "you may" defers via AcceptTrigger/DeclineTrigger). "A base" is read as the
  controller's own base (healing the enemy is never the choice). No engine change.
- **Outflank TWI_123** ("Attack with 2 units (one at a time)") — **identical to
  Outflank SHD_128** — an `EventAbility` whose one `CustomEffect` calls
  `push_granted_attack` twice (the Rebel Assault SOR_103 pattern); the two grants
  resolve one at a time off the LIFO stack and "2 different units" falls out of
  exhaustion. No engine change.
- **Encouraging Leadership TWI_126** ("Give each friendly unit +1/+1 for this
  phase") — a plain `EventAbility([ModifyStats(+1/+1, target=friendly
  fixed=EACH_FRIENDLY, THIS_PHASE)])` (the Moment of Glory SHD_130 pattern but
  auto-targeting every friendly unit). No engine change.
- **New `Condition.CONTROLLER_BASE_DAMAGE_MIN(param=N)` atom** (≥N damage on the
  controller's base, via `ps.base_instance.damage`) for **Anakin's Interceptor
  TWI_142** ("While your base has 15 or more damage on it, this unit gets +2/+0")
  — a self-targeted `ConstantAbility(StatBonus(2,0),
  condition=CONTROLLER_BASE_DAMAGE_MIN(15))`, read passively by `compute_power`
  (the Seasoned Shoretrooper SHD_83 self-conditional-stat pattern). Purely a new
  condition atom (the allowed small-primitive path).
- **Ahsoka's Padawan Lightsaber TWI_248** (Upgrade; "When Played: If attached unit
  is Ahsoka Tano, you may attack with a unit") — a `WhenPlayed` gated by
  `ATTACHED_HOST_NAMED("Ahsoka Tano")` (collected only when the host is Ahsoka, the
  Leia's Disguise LAW_111 / Mandalorian's Rifle SHD_251 pattern) whose one
  `CustomEffect` is a thin adapter onto `push_granted_attack(optional=True)` — any
  of the controller's ready units may attack (not pinned to the host). The
  non-Vehicle attach restriction is the upgrade-target parser. No engine change.
- Group readiness: **7/7**; deck `ahsoka-tano` now **44/52** (2 escalation groups
  left; next group `ahsoka-tano:05` — the create-token-unit primitive).

**Engine primitive added (group `ahsoka-tano:05`) — create-token-unit (2026-06-27).**
The dedicated primitive session the planner flagged. All four cards "Create N
Clone Trooper tokens" — a Clone Trooper is the Token Unit def **TWI_2** (0-cost
2/2 ground unit, traits Republic/Clone/Trooper, Heroism). **Key realisation:** a
token *unit* is the unit analogue of the Shield/Experience/Credit tokens — an
unlimited-supply card *created* into play (not drawn), excluded from card
conservation, that ceases to exist when it leaves play. So it reuses all the
existing unit-in-play scaffolding and is purely additive; **no** new decision
kind, **no** trigger/decision-machinery change (the allowed small-primitive path).
No escape-hatch on any card. Tests: `tests/test_twi_cards.py::
TestCreateTokenUnitPrimitive`, `::TestShaakTi`, `::TestCaptainRex`,
`::TestBatchBrothers`, `::TestDropIn`.
- **New `registry.CreateTokenUnit(token_name, count=1)` effect** — non-targeted
  (like `DrawCards`/`CreateCreditToken`; in the `_get_effect_target_spec` no-target
  list, one `execute_effect` arm). The tokens go to the **source's controller**
  (`owner_ps`, the established control-change-limited convention).
- **`actions._create_token_units(s, ps, token_name, count)`** loads the TokenUnit
  def via the new cached **`tokens._token_unit_def(name)`** (mirrors `_credit_def` /
  `_token_def`), allocs an instance per token, and routes each through the shared
  **`_put_unit_in_play`** path (`play_source="token"`). So a created token enters
  the controller's appropriate arena **exhausted by default**, fires
  `UnitEntersPlay` + its own enter-play keyword/trigger bus (a no-op for the plain
  Clone Trooper, but correct if a future token had keywords), is added to
  `units_played_this_phase`, and is buffable like any unit. No separate event class
  — `UnitEntersPlay` already renders everywhere (web `format.ts`).
- **Conservation / leave-play.** `state.all_instances_for_player` now excludes
  `TokenUnit` as well as `TokenUpgrade` (created on demand, not from deck), so the
  conservation invariant ignores tokens. `_defeat_unit` gained a `TokenUnit` branch
  that lets a defeated token **cease to exist** (never placed in any discard pile),
  mirroring the token-upgrade rule.
- **New `token_unit` target predicate** (`resolver._spec_matches_ci`,
  `isinstance(card_def, TokenUnit)`) for **Shaak Ti TWI_94** "Each friendly token
  unit gets +1/+0" — a `ConstantAbility(target=friendly unit, predicates=
  ("token_unit",), StatBonus(1,0))`, read passively by `compute_power` (the Red
  Three SOR_144 pattern); a Clone Trooper is a 3/2 while Shaak Ti is in play. Her
  second ability is `OnAttack → CreateTokenUnit("Clone Trooper")`.
- **Captain Rex TWI_97** = `WhenPlayed CreateTokenUnit("Clone Trooper", 2)`;
  **Batch Brothers TWI_144** = `WhenPlayed CreateTokenUnit(..., 1)`; **Drop In
  TWI_251** (Event) = `EventAbility([CreateTokenUnit(..., 2)])`. All non-targeted →
  resolve inline.
- **LIMITATIONS (no shipped card exercises these):** `ReturnToHand` / capture of a
  token unit is not special-cased (tokens should cease to exist there too — none of
  these cards bounce/capture a token); and the token is created for the source's
  `owner_id`, so a control-changed creator would create under its owner (the same
  documented control-change convention).
- Group readiness: **4/4**; deck `ahsoka-tano` now **51/52** (1 escalation group
  left; next group `ahsoka-tano:06` — the scaling-magnitude primitive, which
  already exists as `DealDamageEqualTo` from shd-han-solo:08 / the-mandalorian:02).

**Group `ahsoka-tano:06` — scaling-magnitude (Synchronized Strike TWI_99,
2026-06-27).** One card; the planner pre-flagged "scaling-magnitude" as an
escalation, but the primitive already exists (`DealDamageEqualTo` from
shd-han-solo:08 / the-mandalorian:02), so this is just a new **`count` scaling
source** on it — purely additive (a new arm in `resolver._scaling_magnitude`), no
new decision kind, no trigger/decision-machinery change, no escape-hatch. Test:
`tests/test_twi_cards.py::TestSynchronizedStrike`.
- **New `DealDamageEqualTo` count `source_controller_units_in_target_arena`**
  (registry doc not needed — the count is a string read only by the magnitude
  helper) — the number of units the SOURCE controller has in the same arena
  (ground/space) as the target, read from the controller's matching arena list
  (`src_ps.ground_arena`/`space_arena` keyed off the chosen unit's `ci.zone`).
  Depends on both source (whose controller is counted) and target (whose arena
  selects the list). **Synchronized Strike TWI_99** (Event, Tactic; "Deal damage
  to an enemy unit equal to the number of units you control in its arena") is a
  plain `EventAbility([DealDamageEqualTo(target=TargetSpec(controller="enemy",
  kind="unit"), count="source_controller_units_in_target_arena")])` — the target
  is **non-fixed** (the controller picks which enemy unit; `DealDamageEqualTo` is
  in `_get_effect_target_spec`, so it enumerates as a normal `ChooseTarget`), and
  the per-target magnitude is read at resolution. Mandatory-if-able (fizzles with
  no enemy unit); a magnitude of 0 (you control no units in that arena) is a
  no-op. The event sits in discard while the magnitude is read, but it never
  counted (it is not a unit in an arena).
- Group readiness: **1/1**; deck `ahsoka-tano` now **52/52 — fully encoded** (all
  6 groups complete; eligible for `verify_encoding.py ahsoka-tano --graduate`).

**Graduation soak fixes (`ahsoka-tano`, 2026-06-27).** The deck-specific 200-game
mirror soak (run only at graduation) surfaced two latent bugs — both pre-existing,
exposed once the whole TWI deck (Hevy's WhenDefeated AoE + Tranquility's
return-from-discard) was playable, not introduced by Synchronized Strike. Now
200/200 clean. Regressions:
`tests/regressions/test_combat_double_defeat_and_discard_return.py`.
- **Combat double-defeat → duplicate instance_id.** `_resolve_unit_combat_step2`
  computes `attacker_dead`/`defender_dead` up front, then defeats the attacker
  first. When the attacker (or a board observer) has a `WhenDefeated` AoE — Hevy
  TWI_164 "deal 1 to each enemy ground unit" — that damage can ALREADY defeat the
  still-in-arena defender *inline* (`_apply_deal_damage` → `_defeat_unit`), homing
  it to base_zone (a leader) / discard. The combat step then defeated the
  already-removed defender a **second** time, appending the same instance twice
  (a leader appeared twice in base_zone). Fix: re-check each combatant is still in
  its arena (`_find_in_arenas`) before its combat-defeat call. The `defender_dead`
  flag still drives OnAttackDefeatsUnit correctly (the defender *did* take lethal
  combat damage — the trigger just pre-empted the bookkeeping).
- **return_from_discard → exhausted card in HAND.** A unit defeated while
  exhausted lands in discard still exhausted (discard carries no exhaust meaning);
  `_finish_return_from_discard` (Tranquility TWI_246 / Razor Crest SHD_44) moved it
  to HAND without clearing the flag, tripping the zone/exhaust-sanity invariant.
  Fix: clear `exhausted` **and** `damage` when returning a card to hand — a card
  out of play must be a clean card (the Sarlacc LAW_163 discard→deck graduation
  fix, mirrored for the discard→hand path; the arena→hand `_apply_return_to_hand`
  already cleared both).

**Group `general-grievous:01` — Direct damage & removal (2026-06-27).** One TWI
event card; one small additive engine seam (a new self-contained decision kind),
no change to core resolution or the trigger/decision machinery, no escape-hatch.
Tests: `tests/test_twi_cards.py::TestMercilessContest`.
- **New `each_player_defeats` decision kind** (`actions.push_each_player_defeats`
  + `ChooseUnitToDefeat` + `_each_player_defeat_targets` /
  `_resolve_each_player_defeats`) for **Merciless Contest TWI_238** ("Each player
  chooses a non-leader unit they control. Defeat those units."). The novelty is
  that the OPPONENT must choose *their own* unit, which the `resolve_effects` flow
  cannot express (a `ChooseTarget` is always decided by the source's controller —
  the `TargetSpec.chooser` field is honoured only by `DiscardFromHand`, not by
  target enumeration), so it needs a per-stage deciding-player shift — the
  established say_no SOR_233 / opponent_chooses_target SHD_246 precedent. One
  decision walks an `order` list `[controller, opponent]`: each player picks one of
  their own non-leader arena units (a deployed leader is a Leader card_def, so
  excluded, mirroring the `non_leader` predicate); a player with no eligible unit
  is skipped, and if neither has one the decision is never pushed (the event
  fizzles). After everyone has chosen, the decision pops and the chosen units are
  defeated together (the "pop, then defeat" gotcha shared with
  push_distribute_damage — `_apply_defeat_unit` after the pop so a WhenDefeated
  trigger lands on a clean stack). Registered in `invariants._KNOWN_DECISION_KINDS`
  and `web/session.py` (`_PROMPTS`); `HeuristicBot` gained a
  `_choose_unit_to_defeat` handler (give up its least-valuable unit by
  `_card_value`). Merciless Contest is a plain `EventAbility` whose one
  non-targeted `CustomEffect` is a thin adapter onto the push helper (the Palpatine
  SOR_135 pattern). A self-contained new decision kind — the allowed small-
  primitive path.
- Group readiness: **1/1**; deck `general-grievous` now **12/52** (next group
  `general-grievous:02`).

**Group `general-grievous:02` — Card advantage & disruption (2026-06-27).** Three
TWI cards; two small additive seams (one extra optional filter on an existing
decision, one new self-contained decision kind), neither touching core resolution
or the trigger/decision machinery. No escape-hatch. Tests:
`tests/test_twi_cards.py::TestAdmiralTrench`, `::TestWaylay`,
`::TestPrivateManufacturing`.
- **`push_return_from_discard` gained an optional `eligible_instance` predicate**
  (a filter on the *CardInstance*, applied alongside the existing card_def
  `eligible`, both evaluated once at push time). **Admiral Trench TWI_86** (Exploit
  1 = keyword layer; "When Played: Return up to 3 units that were defeated this
  phase from your discard pile to your hand") is a `WhenPlayed` whose one
  `CustomEffect` is a thin adapter onto the existing `return_from_discard` seam
  (the Razor Crest SHD_44 / Tranquility TWI_246 pattern), with `eligible`=is a Unit
  and `eligible_instance`=instance id in `game_memory.units_defeated_this_round`
  ("defeated this phase" — defeats happen in ACTION and the set clears at the round
  rollover, so "this round"=="this phase", the Medal Ceremony SOR_245
  `attacked_this_phase` precedent). "From your discard pile" falls out of the seam
  scanning only the controller's own discard. Purely an additional filter on an
  existing decision (the allowed small-primitive path).
- **Waylay TWI_226** (Event) — a plain `EventAbility([ReturnToHand(TargetSpec(
  controller="any", kind="unit", predicates=("non_leader",)))])`; mandatory-if-able,
  fizzles cleanly with no eligible unit. No engine change.
- **New `bottom_from_hand` decision kind** (`actions.push_bottom_from_hand` +
  `SelectHandCardToBottom` + `_bottom_from_hand_actions`) for "Put N cards from
  your hand on the bottom of your deck in any order" — a stage-less mandatory
  self-pick: one `SelectHandCardToBottom` per hand card, picked one at a time (the
  pick order == bottom-placement order, so "in any order" falls out); each pick
  appends the card (face-down) to the deck bottom and the decision auto-pops once
  `min(count, hand size)` have been placed (no decline — the bottoming is a forced
  downside). Pushed only with ≥1 hand card. Registered in
  `invariants._KNOWN_DECISION_KINDS` and `web/session.py` (`_PROMPTS` + a "Bottom"
  label verb); `HeuristicBot` gained `_choose_bottom_from_hand` (bottom the
  highest-cost / least immediately castable cards). **Private Manufacturing
  TWI_257** (Event; "Draw 2 cards. If you control no token units, put 2 cards from
  your hand on the bottom of your deck in any order") is `[DrawCards(2),
  CustomEffect]`: the no-target CustomEffect runs **inline after the draw** (the
  resolve_effects auto-resolve loop), checks the controller's arenas for any
  `TokenUnit`, and — only if none — pushes the `bottom_from_hand` decision (the
  token-unit synergy: a Clone Trooper etc. in play skips the downside, the deck's
  reward for the create-token-unit cards in group :05). The pushed decision lands
  as a nested decision beneath the event's buried resolve_effects decision (the
  Calculated Lethality SHD_39 nested-decision pattern, which `apply_resolve_effects`
  already resumes). A self-contained new decision kind (the allowed small-primitive
  path).
- Group readiness: **3/3**; deck `general-grievous` now **16/52** (next group
  `general-grievous:03`).

**Group `general-grievous:03` — Combat tricks, buffs & tempo (2026-06-28).** Seven
TWI cards; four small additive engine seams (a `once_per_round` activated-ability
enforcement, a `WhenYouPlayCard.trait` filter + played-cost recording, and two new
target predicates), none touching core resolution or the trigger/decision
machinery destructively; no escape-hatch on any card. Tests:
`tests/test_twi_cards.py::TestGeneralGrievous`, `::TestMagnaGuardWingLeader`,
`::TestObedientVanguard`, `::TestTacticalAdvantage`, `::TestSoullessOne`,
`::TestSeparatistCommando`, `::TestTacticalDroidCommander`.
- **New `once_per_round` enforcement** (the `ActivatedAbility.once_per_round` field
  existed but was never enforced) — a new `GameMemory.activated_abilities_used_this_round`
  set (entries `f"{instance_id}:{ability_idx}"`, cleared at `clear_round`,
  serialised in `to_dict`/`from_dict`), checked in all three `legal_actions`
  `UseAbility` loops (arena/base/undeployed-leader) and recorded + guarded in
  `UseAbility.apply`.  **MagnaGuard Wing Leader TWI_82** ("Action: Attack with a
  Droid unit. Then, attack with another Droid unit. Use this ability only once each
  round.") is a no-cost `ActivatedAbility(once_per_round=True)` whose one
  `CustomEffect` calls `push_granted_attack(attacker_trait="Droid")` twice (the
  Outflank TWI_123 double-grant pattern); "another" Droid falls out of the first
  attacker's exhaustion.
- **New `WhenYouPlayCard.trait` filter + `card_type="unit"`** (registry + the
  resolver matcher arm) — narrows to "another <trait> unit" plays; the matcher also
  records the played card's **printed cost** under `event_ctx["cost_le_threshold"]`.
  Paired with the **new `cost_le_event_threshold` target predicate**
  (`resolver._spec_matches_ci`).  **Tactical Droid Commander TWI_184** (Exploit 2 —
  keyword layer; "When you play another Separatist unit: You may exhaust a unit that
  costs the same as or less than the played unit") is an optional
  `WhenYouPlayCard(trait="Separatist", card_type="unit")` whose one `ExhaustCard`
  targets any unit (`controller="any"` — you exhaust an enemy) filtered by
  `cost_le_event_threshold` (≤ the played unit); auto-declines with no eligible unit.
- **New `droid_or_general_grievous` target predicate** (`resolver._spec_matches_ci`)
  — a unit carrying the Droid trait OR named "General Grievous" (his deployed
  leader-unit form, who is not a Droid).  **Soulless One TWI_179** ("On Attack: You
  may exhaust a friendly Droid unit or General Grievous (leader or unit). If you do,
  this unit gets +2/+0 for this attack") is an optional `OnAttack` whose one
  `CustomEffect` carries `target=friendly unit, predicates=("droid_or_general_grievous",
  "ready")`: choosing one exhausts it and applies +2/+0 this-attack to Soulless One,
  bound in one CustomEffect so "If you do" holds (the Kihraxz SHD_118 pattern).
  LIMITATION: the undeployed leader form (in base_zone) is not an arena unit and so
  is not offered — the unexercised "(leader or unit)" edge.
- **General Grievous TWI_15** (Leader, Sentinel) — undeployed front "Action
  [Exhaust]: Give a Droid unit Sentinel for this phase" = an `undeployed_only`
  `ActivatedAbility(costs=[ExhaustSelf()], effects=[GrantKeyword("Sentinel",
  friendly Droid unit, THIS_PHASE)])`; deployed back "On Attack: You may give a
  Droid unit +1/+0 and Sentinel for this phase" = a `deployed_only` optional
  `OnAttack` whose one `CustomEffect` applies BOTH the +1/+0 and Sentinel to one
  chosen friendly Droid unit (bound together — the text grants both to one unit, so
  a single CustomEffect.target rather than two splittable effects).  The Epic Action
  deploy (6+ resources) is the standard `deploy_threshold` machinery.
- **Obedient Vanguard TWI_104** (Raid 1 — keyword layer) — optional `WhenDefeated`
  `ModifyStats(+2/+2, friendly Trooper unit, THIS_PHASE)` (the dying unit has left
  play so is never its own recipient).  **Tactical Advantage TWI_124** (Event) —
  plain `EventAbility([ModifyStats(+2/+2, any unit, THIS_PHASE)])` (the Moment of
  Glory SHD_130 pattern).  **Separatist Commando TWI_180** ("While you control
  another Separatist unit, this unit gains Raid 2") — a self-targeted
  `ConstantAbility(KeywordGrant("Raid", 2), condition=CONTROLLER_HAS_OTHER_TRAIT_UNIT
  ("Separatist"))` read passively by `keyword_value` (the Hunting Nexu SHD_168
  conditional self-grant pattern; the keyword sanitiser strips the printed Raid
  because this conditional self-grant is registered).
- Group readiness: **7/7**; deck `general-grievous` now **28/52** (next group
  `general-grievous:04`).

**Group `general-grievous:04` — Combat tricks, buffs & tempo (2026-06-28).** Four
TWI cards; four small additive engine seams, none touching core resolution or the
trigger/decision machinery destructively; no escape-hatch on any card. Tests:
`tests/test_twi_cards.py::TestIndependentSenator`, `::TestTriDroidSuppressor`,
`::TestInPursuit`, `::TestGrievoussWheelBike`.
- **New `TargetSpec.power_max` filter** (registry + one `_spec_matches_ci` arm, the
  inverse of `power_min`) — effective `compute_power` ≤ N, arena units only.
  **Independent Senator TWI_206** is an `ActivatedAbility(costs=[PayResources(2),
  ExhaustSelf()], effects=[ExhaustCard(any unit, power_max=4)])` — "Action [2
  resources, Exhaust]: Exhaust a unit with 4 or less power" (`controller="any"`, you
  point it at an enemy; mandatory-if-able, fizzles with no eligible unit).
- **Tri-Droid Suppressor TWI_217** (Exploit 2 — keyword layer) — a plain
  `WhenPlayed [ExhaustCard(enemy ground unit)]` (mandatory-if-able).
- **New `requires_prior_target` predicate** (`_spec_matches_ci`) — matches only when
  an earlier effect recorded `event_ctx["prior_target_id"]`, the "If you do" gate for
  a follow-up that must fire only when the prior one did. **In Pursuit TWI_221**
  ("Exhaust a friendly unit. If you do, exhaust an enemy unit") is two effects sharing
  the resolve_effects `event_ctx` (the Grenade Strike TWI_171 pattern): a mandatory
  `CustomEffect.target` (friendly unit) exhausts it and records the flag; a mandatory
  `ExhaustCard(enemy unit, predicates=("requires_prior_target",))` — with no friendly
  unit the first fizzles, the flag is never set, and the enemy exhaust has no
  candidates (no prompt), honouring "If you do".
- **Host-conditional upgrade cost reduction + upgrade-keyword conferral (Grievous's
  Wheel Bike TWI_236).** "While playing this upgrade on General Grievous, it costs 2
  less.  Attached unit gains Overwhelm."  Two new seams:
  (1) a **`CostReduction.host_named`** field, read by a host-aware play-cost path —
  `_play_cost`/`_play_cost_reduction` gained an optional `target_host_id` (threaded
  from `PlayCard.apply` via `self.upgrade_target_id` and, in `legal_actions`, by
  computing the upgrade's cost **per eligible host** so affordability is host-specific);
  the reduction applies only when the chosen host's name contains the string.  (2)
  **`has_keyword`/`keyword_value` now scan a unit's `attached_upgrades` for a
  `ConstantAbility KeywordGrant(target=SELF)`**, conferring the keyword to the host —
  the keyword analogue of the trait layer's upgrade `TraitGrant` scan (`traits.
  _granted_traits`); the existing arena ConstantAbility scan never sees an upgrade
  (it lives in `attached_upgrades`, not an arena), so this is the only path that
  confers an upgrade's static keyword.  Wheel Bike is
  `[ConstantAbility(target=SELF, KeywordGrant("Overwhelm")), CostReduction(amount=2,
  host_named="General Grievous")]`; the non-Vehicle attach is the upgrade-target
  parser.  With zero credits / no `host_named` reduction the play-cost path is
  byte-identical to before.
- Group readiness: **4/4**; deck `general-grievous` now **35/52** (2 escalation
  groups left; next group `general-grievous:05` — the create-token-unit primitive,
  which **already exists** as `CreateTokenUnit` from ahsoka-tano:05, so :05/:06 reuse
  the seam, not real escalations).

**Group `general-grievous:05` — create-token-unit (Battle Droid, 2026-06-28).**
Seven Separatist cards "Create N Battle Droid tokens"; the planner pre-flagged
"create-token-unit" as an escalation, but the primitive already exists
(`CreateTokenUnit` from ahsoka-tano:05), so this is a **reuse**, not a real
escalation — the only engine change is one tiny additive field. The Battle Droid is
the TokenUnit def **TWI_1** (a 1/1 ground unit, traits Separatist/Droid/Trooper,
Villainy) — loaded by name like Clone Trooper, so `CreateTokenUnit("Battle Droid",
…)` "just works". No new decision kind, no trigger/decision-machinery change, no
escape-hatch on any card. Tests: `tests/test_twi_cards.py::TestConfederateCourier`,
`::TestPoggleTheLesser`, `::TestGeneralsGuardian`, `::TestKraken`,
`::TestSubjugatingStarfighter`, `::TestOnTheDoorstep`, `::TestDroidCohort`.
- **New `enters_ready` field on `CreateTokenUnit`** (registry → resolver arm →
  `actions._create_token_units` → the existing `_put_unit_in_play(enters_ready=…)`
  param) — created tokens enter play *ready* instead of the default exhausted, for
  **On the Doorstep TWI_190** (Event) `EventAbility([CreateTokenUnit("Battle Droid",
  count=3, enters_ready=True)])` ("Create 3 … and ready them"). Purely additive (a
  field defaulting False → byte-identical to before for every other caller).
- **TWI_79 Confederate Courier** = `WhenDefeated [CreateTokenUnit("Battle Droid")]`
  (the token goes to the dying unit's controller — the source resolves from its
  owner on defeat). **TWI_83 General's Guardian** = `WhenAttacked [CreateTokenUnit]`.
  **TWI_84 Kraken** = `WhenPlayed [CreateTokenUnit(count=2)]` + `OnAttack
  [ModifyStats(+1/+1, this phase, target friendly `token_unit` `EACH_FRIENDLY`)]`
  (the ahsoka-tano:05 `token_unit` predicate; Kraken is a real unit so never buffs
  itself). **TWI_112 Subjugating Starfighter** (Ambush — keyword layer) = `WhenPlayed
  [CreateTokenUnit]` gated by `CONTROLLER_HAS_INITIATIVE` (the condition gates trigger
  collection, so nothing is created without initiative).
- **TWI_80 Poggle the Lesser** ("When you play another unit: You may exhaust this
  unit. If you do, create a Battle Droid token") = an **optional**
  `WhenYouPlayCard(card_type="unit")` (`exclude_self` → "another unit") gated by
  `SOURCE_READY`, with `effects=[ExhaustCard(fixed=SELF), CreateTokenUnit]` — the
  exhaust-self cost and the create both have fixed/no targets, so on Accept they
  auto-resolve inline (no CustomEffect needed); the SOURCE_READY gate guarantees the
  exhaust always succeeds when offered, so the "If you do" binding holds and the
  trigger is not offered while Poggle is already exhausted.
- **TWI_218 Droid Cohort** (Upgrade, "Attached unit gains 'When Defeated: Create a
  Battle Droid token'") = `GrantedAbility(WhenDefeated → CreateTokenUnit)` resolving
  from the HOST (the Armed to the Teeth SHD_175 / the-mandalorian:01
  granted-WhenDefeated-from-a-defeated-host pattern) — an ordinary own-perspective
  granted ability (NOT a Bounty), so the token goes to the host's controller.
- Group readiness: **7/7**; deck `general-grievous` now **45/52** (1 escalation group
  left; next group `general-grievous:06` — also create-token-unit, reusing this same
  seam).

**Group `general-grievous:06` — create-token-unit (Battle Droid), part 2
(2026-06-28).** Four more Separatist "Create N Battle Droid tokens" cards. Two are
trivial reuses of the existing `CreateTokenUnit` effect (ahsoka-tano:05 /
general-grievous:05); two needed one small self-contained decision kind each (the
allowed small-primitive path — neither touches core resolution or the
trigger/decision machinery). No escape-hatch on any card. Tests:
`tests/test_twi_cards.py::TestPoliticalPressure`, `::TestBattleDroidEscort`,
`::TestTheInvisibleHand`, `::TestDroidDeployment`. **This completes the deck —
`general-grievous` is now 52/52 (all 6 groups), eligible for
`verify_encoding.py general-grievous --graduate`.**
- **New `may_discard` decision kind** (`actions.push_may_discard_else_tokens` +
  `DiscardRandomCard` / `DeclineDiscard`) for **Political Pressure TWI_222**
  ("Choose an opponent. They may discard a random card from their hand. If they
  don't, create 2 Battle Droid tokens"). The opponent decides, which the
  `resolve_effects` flow cannot express, so it uses the deciding-player shift (the
  say_no SOR_233 / each_player_defeats TWI_238 precedent): the decision is handed
  to the OPPONENT, who either discards a *random* card (RNG-chosen via
  `state.make_rng()` — the text says "random") to prevent the tokens, or declines,
  in which case the source's controller creates `token_count` token units
  (`_create_token_units`, the create-token-unit primitive). When the opponent's
  hand is empty they cannot discard ("if they don't"), so the tokens are created
  inline with **no** decision pushed. A plain `EventAbility` whose one non-targeted
  `CustomEffect` is a thin adapter onto the push helper (the Palpatine SOR_135
  pattern). Registered in `invariants._KNOWN_DECISION_KINDS` and `web/session.py`
  (`_PROMPTS`); `HeuristicBot` gained `_choose_may_discard` (as the targeted
  opponent: pay a card to deny the 2 tokens only when flush — hand ≥ 4 — else keep
  the card).
- **New `exhaust_for_base_damage` decision kind**
  (`actions.push_exhaust_for_base_damage` + `SelectUnitToExhaust` /
  `FinishExhaustForBaseDamage`, `_exhaust_for_base_damage_targets` /
  `_resolve_exhaust_for_base_damage`) for **The Invisible Hand TWI_234** On Attack
  ("Exhaust any number of friendly Separatist units. Deal 1 damage to the defending
  player's base for each unit exhausted this way"). A multi-select decision in the
  Medal Ceremony SOR_245 select_token "any number" shape, but exhausting instead of
  token-giving and with a scaling base-damage payoff: the controller picks ready
  friendly units matching the trait filter (the `ready` predicate, moff-gideon:05)
  one at a time, each exhausted as it is chosen (so it falls out of the eligible
  set), or finishes early ("any number" includes 0 — `FinishExhaustForBaseDamage`
  is always offered). On finish the decision **pops first**, then `damage_per` ×
  (units exhausted) is dealt to the recorded defending (enemy) base (the "pop, then
  deal" gotcha so a base-defeat trigger lands on a clean stack, reusing
  `_apply_deal_damage`). The defending player is the opponent of the source's
  controller; its base id is recorded at push time. The Invisible Hand is itself a
  Separatist unit but is exhausted from attacking (CR step 1), so the `ready` filter
  never offers it; pushed only when ≥1 eligible ready unit exists. Its `WhenPlayed`
  is a plain `CreateTokenUnit(count=4)`. The OnAttack `CustomEffect` is a thin
  adapter onto the push helper. Registered in `invariants._KNOWN_DECISION_KINDS`
  and `web/session.py` (`_PROMPTS` + a `SelectUnitToExhaust` "Exhaust <name>"
  label); `HeuristicBot` gained `_choose_exhaust_for_base_damage` (exhaust only
  expendable token units — its own churned-out Battle Droids — for free base chip,
  then finish; never spends a real combat unit).
- **Battle Droid Escort TWI_229** ("When Played/When Defeated: Create a Battle Droid
  token") = the combined trigger registered as two `TriggerAbility`s (a `WhenPlayed`
  + a `WhenDefeated`), each a `CreateTokenUnit(count=1)`. **Droid Deployment
  TWI_237** (Event) = `EventAbility([CreateTokenUnit("Battle Droid", count=2)])`.
- Group readiness: **4/4**; deck `general-grievous` now **52/52 — fully encoded**
  (all 6 groups complete; eligible for `verify_encoding.py general-grievous
  --graduate`).

**Graduation soak fixes (`general-grievous`, 2026-06-28).** The deck-specific
200-game mirror soak (run only at graduation) surfaced two latent **Exploit**
bugs — both pre-existing, exposed once the whole deck was playable (Exploit units
alongside decision-pushing When Played / When Defeated abilities), not introduced
by group :06. Now 200/200 clean. Regression:
`tests/regressions/test_exploit_commit_decision_ordering.py`.
- **`_resolve_exploit_commit` popped the wrong decision → "no card in play
  buffer".** It put the committed card into play (firing its WhenPlayed, which can
  push its own decision) and only THEN did `pending_decisions.pop()` — removing the
  freshly-pushed trigger decision and leaving the already-resolved exploit decision
  on top with an empty play buffer; a second ExploitCommit then raised. Fix: pop
  the exploit decision (and set `active_player_index`) **before** the card enters
  play, so the play's WhenPlayed/Ambush triggers land on a clean stack (the
  push_distribute_damage "pop, then act" gotcha). Surfaced by Tri-Droid Suppressor
  TWI_217 (Exploit 2, "When Played: Exhaust an enemy ground unit").
- **Auto-commit at max sacrifices → `KeyError: 'sacrificed_ids'`.**
  `ExploitSacrifice` reaching `max_remaining == 0` called `_resolve_exploit_commit`
  synchronously, but the just-sacrificed unit's WhenDefeated trigger may have
  pushed its own decision on top of the exploit decision — so the commit read the
  wrong top decision's context. Fix: auto-commit **only while the exploit decision
  is still on top** (`s.pending_decisions[-1] is top_d`); otherwise leave it — the
  WhenDefeated decision resolves first (it is on top), the exploit decision
  re-surfaces, and legal_actions offers a forced ExploitCommit. Surfaced by
  sacrificing Obedient Vanguard TWI_104 (optional WhenDefeated +2/+2 to a Trooper)
  to an Exploit 1 unit (Admiral Trench TWI_86).

**Group `qui-gon-jinn:01` — Direct damage & removal (2026-06-29).** The **first
LOF deck** — new card set module `src/swu/cards/lof/` (imported from
`src/swu/cards/__init__.py`). Two cards; one composes from existing primitives,
one needed a tiny additive seam (a new serialisable instance flag + a regroup
sweep), neither touching core resolution or the trigger/decision machinery; no
escape-hatch on either card. Tests: `tests/test_lof_cards.py`.
- **Stinger Mantis LOF_198** ("When Played: You may deal 2 damage to an exhausted
  unit") — a plain optional `WhenPlayed` `DealDamage(2, TargetSpec(controller=
  "any", kind="unit", predicates=("exhausted",)))` using the existing `exhausted`
  predicate; `controller="any"` mirrors the printed text and the controller points
  it at an enemy. Auto-declines with no exhausted unit on the board. No engine
  change.
- **New `CardInstance.defeat_at_regroup` flag + a `_enter_regroup` sweep (Sneak
  Attack SOR_219).** "Play a unit from your hand. It costs 3 less and enters play
  ready. At the start of the regroup phase, defeat it." is a thin `EventAbility`
  `CustomEffect` adapter onto the play-from-hand subsystem (the Admiral Ozzel
  SOR_129 / Timely Intervention SHD_129 pattern): `push_play_from_hand(
  cost_reduction=3, enters_ready=True, defeat_at_regroup=True)`. The new
  optional `defeat_at_regroup` field on `push_play_from_hand` is threaded through
  the `play_from_hand` decision context → `PlayFromHand.apply` → `_put_unit_in_play`
  onto a new serialisable `CardInstance.defeat_at_regroup` flag (default False →
  byte-identical to before for every other caller; serialised in
  `_instance_to_dict`/`_instance_from_dict` with a back-compat default). At the
  **start of REGROUP** (`actions._enter_regroup`, after the regroup draws and after
  the active player is set to the initiative holder, before the
  `PhaseStartTrigger` fire — the Contracted Hunter JTL_216 site) a sweep defeats
  every arena unit carrying the flag (any WhenDefeated trigger's `after_all` lands
  on the initiative holder, the same handling as JTL_216). Mandatory-if-able with
  no decline (the event is "Play a unit", not "you may"); fizzles if no hand unit
  is affordable at the discount. This is the allowed small-primitive path: a new
  serialisable instance field + a play-path field + a rollover-time sweep (the
  `granted_bounties` / `_end_regroup`-clear shape), no new decision kind, no
  trigger/decision-machinery change.
- Group readiness: **2/2**; deck `qui-gon-jinn` now **10/52** (next group
  `qui-gon-jinn:02`; the keystone escalation `qui-gon-jinn:06` (force-token) is
  still pending — no other group depends on it, so :02–:05 may follow in any
  order).

**Group `qui-gon-jinn:02` — Card advantage & disruption (2026-06-29).** Three
cards (LOF_104, LOF_194 + the TWI card R2-D2 TWI_193, registered in the TWI
module since it belongs to that set); one tiny generalisation of an existing
decision kind, one new self-contained decision kind, neither touching core
resolution or the trigger/decision machinery; no escape-hatch on any card. Tests:
`tests/test_lof_cards.py::TestLuminousBeings`, `::TestJTypeNubianStarship`,
`tests/test_twi_cards.py::TestR2D2`.
- **`discard_for_search` generalised (R2-D2 TWI_193).** "When Played: You may
  discard a card from your hand. If you do, search the top 3 cards of your deck for
  a card and draw it." reuses the Great Pit of Carkoon LAW_23 seam
  (`push_discard_unit_for_search`), now generalised into `push_discard_for_search`
  with additive params: `discard_units_only` (False → any card may be discarded,
  not just a Unit), `search_name=None` (any card eligible, vs Great Pit's name
  match), `search_window`/`search_count`/`search_up_to` (forwarded to the follow-up
  `push_deck_search`), and `optional` (True → a new `FinishDiscardForSearch` decline
  is offered, carrying the "you may"). The discard candidates / search params live
  in the decision context (JSON-serialisable); `DiscardForSearch.apply` reads them
  to build the eligible closure. R2-D2 is a **mandatory** `WhenPlayed` whose one
  `CustomEffect` is a thin adapter (the optionality lives in the decision, so no
  double-decline prompt); with an empty hand the push no-ops (no candidates), so the
  mandatory trigger fizzles cleanly with no hand-size condition. `push_discard_unit_for_search`
  is kept as a thin wrapper so Great Pit is byte-identical; `HeuristicBot._choose_discard_for_search`
  now filters to `DiscardForSearch` (ignoring the new decline) and always discards
  to dig (card-neutral-or-better), `FinishDiscardForSearch` added to the safe-default
  order. Purely additive params on an existing decision kind (the allowed
  small-primitive path).
- **New `recur_and_buff` decision kind (Luminous Beings LOF_104).** "Put up to 3
  Force units from your discard pile on the bottom of your deck in a random order.
  Give that many units +4/+4 for this phase." is a self-contained two-stage
  decision (`actions.push_recur_and_buff`, the push_sacrifice_resource_for_damage
  "choose, then act" shape extended to two select-up-to lists): stage `"recur"`
  (`SelectRecurUnit`/`FinishRecur`) picks up to N matching discard units one at a
  time — on finish they go to the deck bottom in a seeded-`rng.shuffle` order
  (cleared exhaust/damage, the discard→deck cleanliness rule) and K = the number
  recurred; stage `"buff"` (`SelectBuffTarget`/`FinishRecurBuff`) gives up to K
  distinct in-play units a +4/+4 `this_phase` `_make_modifier`, auto-popping at K /
  when no eligible unit remains. The buff target list (`controller="any"`, mirroring
  the literal "units") is recomputed live so the K-cap is honoured as units leave
  play; the event card sits in discard during resolution (an Event, not a Unit, so
  never a recur candidate). Pushed only when ≥1 Force unit is in the discard pile,
  so "put 0, buff 0" is a clean no-op. Registered in `invariants._KNOWN_DECISION_KINDS`
  and `web/session.py` (`_PROMPTS`); `HeuristicBot._choose_recur_and_buff` recurs all
  offered, then buffs its own highest-power units (never an enemy's), with the two
  Finish actions in the safe-default order. A thin `EventAbility` `CustomEffect`
  adapter onto the push helper. No change to core resolution or the trigger/decision
  machinery (a new self-contained decision kind, the allowed small-primitive path).
- **J-Type Nubian Starship LOF_194** ("When Played: Draw a card. When Defeated:
  Discard a card from your hand") — two plain triggers: `WhenPlayed [DrawCards(1)]`
  + `WhenDefeated [DiscardFromHand(count=1, chooser="controller")]`. DEVIATION
  (documented): the controller discard uses the established first-card simplification
  (K-2SO SOR_145 / Garindan SEC_186) — the controller doesn't choose *which* card,
  only the forced downside itself is faithful. No engine change.
- Group readiness: **3/3**; deck `qui-gon-jinn` now **15/52** (next group
  `qui-gon-jinn:03`).

**Group `qui-gon-jinn:03` — Combat tricks, buffs & tempo (2026-06-29).** Seven
cards (LOF_96/99/111/201/242 + the SHD card SHD_96 and the JTL card JTL_201,
registered in their own set modules). Three small additive seams (one new target
predicate, one new self-contained decision kind, one sanitiser rule), none
touching core resolution or the trigger/decision machinery; no escape-hatch on any
card. Tests: `tests/test_lof_cards.py` (all group :03 tests live here so the
verifier's card-number `-k` gate finds them together).
- **Obi-Wan Kenobi LOF_96** ("When you play a Force unit (including this one): This
  unit gains Sentinel for this phase") — a `WhenYouPlayCard(trait="Force",
  card_type="unit", exclude_self=False)` whose self-targeted `GrantKeyword(
  "Sentinel", THIS_PHASE)` resolves inline. `exclude_self=False` covers "(including
  this one)": `PlayCard` fires `CardPlayed` *after* the played unit is in its arena
  (the Fighters for Freedom SOR_143 firing site), so `_collect_triggers` sees
  Obi-Wan as a source for his own play. **Sanitiser change:** the official data
  mis-tags Obi-Wan with a printed Sentinel even though he only *gains* it per-phase;
  `keyword_sanitizer` gained a third rule — strip a printed keyword that a
  registered `TriggerAbility` grants to *itself* (a self-targeted `GrantKeyword`) —
  so the ability owns it (the conditional-self-grant ConstantAbility rule's
  triggered sibling). Verified Refugee LOF_242's genuinely-possessed Sentinel is
  kept (it has no self-`GrantKeyword`).
- **Maz Kanata SHD_96** ("When you play another unit: Give an Experience token to
  this unit") — a `WhenYouPlayCard(card_type="unit")` (`exclude_self=True` → "another
  unit") `GiveToken("Experience", fixed=SELF)`.
- **Paladin Training Corvette LOF_99** ("give Experience to up to 3 Force units") —
  a thin `WhenPlayed` CustomEffect onto `push_select_token(token_type="Experience",
  max_targets=3, traits=["Force"])` (the General Tagge SHD_81 / Medal Ceremony
  SOR_245 select-up-to-N pattern).
- **Maz Kanata LOF_111** ("may attack with a Force unit, +2/+0") — a thin
  `WhenPlayed` CustomEffect onto `push_granted_attack(power_bonus=2, optional=True,
  attacker_trait="Force")` (the Snowtrooper Lieutenant SHD_236 pattern; both fields
  pre-existing).
- **New `exhaust_combined_cost` decision kind** (`actions.push_exhaust_combined_cost`
  + `SelectUnitToExhaustCombined` / `FinishExhaustCombined`) — "exhaust any number
  of units" with two optional caps: a combined-PRINTED-cost `budget` that shrinks as
  units are picked, and a `max_units` count cap. Each pick exhausts the unit inline;
  "any number" includes 0 (FinishExhaustCombined always offered). No friendly/enemy
  restriction (`controller="any"` — the controller points it at enemy units). The
  Invisible Hand TWI_234 select-shape, but budget-bounded with no payoff.
  **Qui-Gon Jinn's Lightsaber LOF_201** (Upgrade) = a `WhenPlayed` gated by
  `ATTACHED_HOST_NAMED("Qui-Gon Jinn")` whose CustomEffect adapter calls it with
  `budget=6` (no count cap). The non-Vehicle attach is the upgrade-target parser.
  **Ahsoka Tano JTL_201** reuses the same decision with `budget=None, max_units=1`
  ("you may exhaust a unit").
- **Ahsoka Tano JTL_201** ("An opponent discards a card from their hand. If it's a
  unit, you may exhaust a unit") — a mandatory `WhenPlayed` whose single no-target
  CustomEffect discards the opponent's first card (the K-2SO SOR_145 first-card
  simplification) and — *only if that card was a Unit* — pushes the
  `exhaust_combined_cost` decision (`max_units=1`). Folding both into one effect is
  necessary: a two-effect `[discard, exhaust]` ability would be judged
  inline-resolvable (the exhaust has no targets *before* the discard runs), so the
  per-effect target re-evaluation the resolve_effects path provides — and thus the
  exhaust prompt — would never happen. Pushing the decision from inside the discard
  fn (the Palpatine SOR_135 inline-resolve-then-push pattern) sidesteps that.
- **New `has_sentinel` target predicate** (`resolver._spec_matches_ci`, via the
  keyword query layer so a granted Sentinel counts) for **Refugee of The Path
  LOF_242** ("may give a Shield token to a unit with Sentinel") — an optional
  `WhenPlayed GiveToken("Shield", TargetSpec(predicates=("has_sentinel",)))`.
  Refugee is itself a Sentinel unit so it is a legal recipient; with no Sentinel
  unit the optional trigger auto-declines.
- The new decision kind is registered in `invariants._KNOWN_DECISION_KINDS`,
  `web/session.py` (`_PROMPTS` + the Exhaust label), and `HeuristicBot`
  (`_choose_exhaust_combined` — exhaust the most expensive ENEMY ready unit, never
  its own, then finish; + `FinishExhaustCombined`/`FinishExhaustForBaseDamage` in
  the safe-default order).
- Group readiness: **7/7**; deck `qui-gon-jinn` now **30/52** (next group
  `qui-gon-jinn:04`; the keystone escalation `qui-gon-jinn:06` (force-token) is
  still pending — no other group depends on it).

**Group `qui-gon-jinn:04` — Combat tricks, buffs & tempo (2026-06-29).** One card;
one small additive engine seam (a new self-contained decision kind), no change to
core resolution or the trigger/decision machinery, no escape-hatch. Test:
`tests/test_lof_cards.py::TestCuriousFlock`.
- **New `pay_resources_for_tokens` decision kind** (`actions.push_pay_resources_for_tokens`
  + `PayResourceForToken` / `FinishPayResources`) for **Curious Flock LOF_255**
  ("When Played: Pay up to 6 resources.  For each resource paid this way, give an
  Experience token to this unit").  A self-contained "pay any number up to N"
  decision: resources are fungible, so each `PayResourceForToken` just exhausts the
  next ready resource (`_exhaust_resources(ps, 1)`) AND grants one Experience token
  to the source unit **inline** (an Experience token never triggers a defeat, so
  there is no "pop, then act" concern — unlike the `exhaust_for_base_damage`
  payoff).  "Up to" includes 0, so `FinishPayResources` is always offered; the
  decision auto-resolves once the cap (`max_resources=6`) is hit or no ready
  resource remains.  Pushed only when the controller has ≥1 ready resource (paying
  0 grants 0 tokens — a clean no-op).  Curious Flock is a thin `WhenPlayed`
  `CustomEffect` adapter onto the push helper (the Palpatine SOR_135 pattern).
  Registered in `invariants._KNOWN_DECISION_KINDS` and `web/session.py`
  (`_PROMPTS`); `HeuristicBot` gained `_choose_pay_resources_for_tokens`
  (conservatively finishes immediately — spending resources on a vanilla-stat buff
  has no reliable heuristic value and over-spending would cripple its own pool) +
  `FinishPayResources` in the safe-default order.  A new self-contained decision
  kind (the allowed small-primitive path).
- Group readiness: **1/1**; deck `qui-gon-jinn` now **33/52** (next group
  `qui-gon-jinn:05`; the keystone escalation `qui-gon-jinn:06` (force-token) is
  still pending — no other group depends on it).

**Group `qui-gon-jinn:05` — Miscellaneous abilities (2026-06-29).** Two cards;
**one implemented (Kelleran Beq) via a small additive seam, one ESCALATED
(Aethersprite)** — so the group is **1/2** and the deck is NOT graduatable until a
dedicated framework session implements the escalation. No escape-hatch. Test:
`tests/test_lof_cards.py::TestKelleranBeq`.
- **New `disposition="play"` extension of the deck_search seam (Kelleran Beq
  LOF_100).** "When Played: Search the top 7 cards of your deck for a unit, reveal
  it, and play it.  It costs 3 resources less.  (Put the others on the bottom in a
  random order.)" is the *play-from-deck* sibling of the existing `deck_search`
  draw-from-deck seam (Tarkin SOR_84) — same decision kind, same
  `SelectSearchCard`/`FinishSearch` actions, bot handler and web prompt, so **no
  new decision kind**. A new push helper `actions.push_search_and_play(window,
  cost_reduction)` builds a `deck_search` decision with `disposition="play"`,
  `max_select=1`, `up_to=False` (mandatory if able), and `candidate_ids` = the
  units in the top `window` the controller can **afford at effective cost −
  `cost_reduction`** (credits cover a shortfall, like every other play path — so
  an unaffordable unit is simply not offered; events/non-units never are).
  `_finish_deck_search` gained a `disposition=="play"` branch: after the decision
  is **popped** (the push_distribute_damage "pop, then act" gotcha — so the played
  unit's own keyword / When Played triggers land on a clean stack), it pays the
  reduced cost (`_pay_play_cost`), tracks Villainy, and routes the chosen card
  through the shared `_put_unit_in_play(play_source="deck", cost_paid=…)` so the
  played unit fully enters play (firing its abilities), while the un-taken searched
  cards are bottomed in the same seeded-random order the draw branch uses. Kelleran
  is a thin `WhenPlayed` CustomEffect adapter (the Ozzel SOR_129 push-helper
  pattern). Purely additive (a new push helper + a disposition branch on an
  existing decision kind, the allowed small-primitive path).
- **LOF_197 Qui-Gon Jinn's Aethersprite — ESCALATED (flagged for a dedicated
  framework session, NOT registered).** "On Attack: The next time you use a 'When
  Played' ability this phase, you may use that ability again." is a **duplicate-the-
  next-triggered-ability** meta-mechanic: it arms a one-shot, phase-scoped marker
  that, when the controller's *next* WhenPlayed ability resolves, lets them
  re-resolve that same ability. Implementing it touches the **trigger/decision
  machinery** — it needs a persistent "repeat next WhenPlayed" flag set by the
  OnAttack, plus a hook in the resolve_effects / trigger_option **completion** path
  to consume the flag and re-push the just-resolved ability — exactly the kind of
  change the new-primitive escalation rule says to STOP and defer rather than jam
  into a card batch. Left as a genuine gap (no escape-hatch stub).
- Group readiness: **1/2**; deck `qui-gon-jinn` now **35/52** (the Aethersprite
  escalation + the force-token keystone `qui-gon-jinn:06` remain; the deck cannot
  graduate until both are done).

**Engine primitive added (group `qui-gon-jinn:06`) — the Force token (2026-06-29).**
The deck's keystone.  The Force token is a single **per-player boolean**
(`PlayerState.has_force_token`, serialised; max one per player), NOT a card
instance — so unlike Credits it touches no zone/conservation machinery.  Three
additive pieces plus a small decision kind; no escape-hatch on any of the 7 cards.
Tests: `tests/test_lof_cards.py` (Test{YounglingPadawan,JediTemple,JediSentinel,
LukeSkywalker,ImpossibleEscape,TheWillOfTheForce,QuiGonJinn}).
- **Create / read.** New non-targeted effect `registry.CreateForceToken` ("create
  your Force token" → sets the source controller's boolean; in the
  `_get_effect_target_spec` no-target list + one `execute_effect` arm, the
  CreateCreditToken pattern) and condition `CONTROLLER_HAS_FORCE_TOKEN` ("While the
  Force is with you").  **LOF_193 Youngling Padawan** = `WhenPlayed
  [CreateForceToken()]`.  **LOF_196 Jedi Sentinel** = a conditional self-grant
  `ConstantAbility(KeywordGrant("Sentinel"), condition=CONTROLLER_HAS_FORCE_TOKEN)`
  (the Hunting Nexu SHD_168 pattern; the card has no printed Sentinel, so no
  sanitiser strip needed).
- **New `WhenUnitAttacks(filter)` observer trigger + Base trigger collection.**
  **LOF_23 Jedi Temple** (a Base) = "When a friendly Force unit attacks: create
  your Force token".  Unlike `OnAttack` (the attacking unit's own trigger), this
  lets a *different* card observe an `AttackDeclared` whose attacker matches a
  filter (registry + a `_trigger_matches` arm).  Bases live in `base_zone` (never
  an arena), so `resolver._collect_triggers` gained a base_zone scan for **Base**
  trigger abilities (additive — no Base had a trigger before), parallel to the
  existing undeployed-leader base_zone scan.  CreateForceToken resolves inline
  during attack declaration (no decision, no interference with the attack pipeline).
- **`UseForce` cost spec.** "use the Force (lose your Force token)" as an
  activated-ability cost (parallel to ExhaustSelf/PayResources/DefeatSelf):
  affordable only with a token, paying clears it.  Handled in `UseAbility.apply`
  and the three `legal_actions` UseAbility affordability loops.  **LOF_16 Qui-Gon
  Jinn** (Leader) undeployed `Action [Exhaust, use the Force]` =
  `ActivatedAbility(undeployed_only, costs=[ExhaustSelf(), UseForce()],
  condition=CONTROLLER_HAS_NON_LEADER_UNIT)`; deployed "When this unit completes an
  attack (and survives)" = an optional `deployed_only WhenAttackEnds` (the
  Vermillion LAW_215 trigger).  Both sides share one CustomEffect (target = a
  friendly non-leader unit) that returns the chosen unit then plays a cheaper
  non-Villainy unit free via `push_play_from_hand(cost_max=returned−1, free=True,
  exclude_aspect="Villainy")` — the new **`exclude_aspect`** field on the
  play-from-hand subsystem ("non-Villainy unit").  The undeployed Action is gated
  by `CONTROLLER_HAS_NON_LEADER_UNIT` so its Force token isn't wasted with nothing
  to return.
- **`WhenYouPlayCard.unique` filter.** **LOF_249 Luke Skywalker** = "When you play
  another unique unit: you may use the Force; if you do, give it Experience +
  Shield".  An optional `WhenYouPlayCard(card_type="unit", unique=True)` gated by
  CONTROLLER_HAS_FORCE_TOKEN — so the "you may use the Force" choice IS the optional
  trigger Accept/Decline (no extra decision); on accept one CustomEffect spends the
  token and gives Luke the two tokens (bound, so "if you do" holds).
- **New `use_force` decision kind** (`actions.push_use_force` + `UseForceOption` /
  `DeclineUseForce` / `ChooseUseForcePayoffTarget`) for the two events where "you
  may use the Force for a rider" is mid-effect.  Stages "choose" → optional
  "payoff", decided by the controller; declining is always legal ("may").  Only
  pushed when a cost is payable.  **LOF_227 The Will of the Force** = one
  CustomEffect (target = any non-leader unit) returns it, records its owner, and
  pushes `use_force(payoff="discard_random", payoff_player_id=owner)` (that player
  discards a random card — `state.make_rng`).  **LOF_218 Impossible Escape** = a
  thin CustomEffect onto `use_force(payoff="exhaust_enemy_draw",
  allow_exhaust_friendly=True)`: pay the Force token OR exhaust a friendly unit
  (the "either … or"), then draw a card and exhaust an enemy unit if able.
  Registered in `invariants._KNOWN_DECISION_KINDS` and `web/session.py`
  (`_PROMPTS`); `HeuristicBot._choose_use_force` declines by default (the token has
  no reliable heuristic value), picking a payoff target only when forced.  The
  Force token is exposed publicly on `PlayerZoneView.has_force_token` (web model +
  serializer).  **No** change to core resolution or the trigger/decision machinery
  beyond the new self-contained pieces (the allowed small-primitive path).
- Group readiness: **7/7**; deck `qui-gon-jinn` now **49/52** (only the escalated
  Aethersprite LOF_197 `qui-gon-jinn:05` remains — a duplicate-next-WhenPlayed
  meta-mechanic flagged for its own framework session; the deck cannot graduate
  until it is done).

**Group `darth-maul:01` — Direct damage & removal (2026-06-30).** The **second
LOF deck** (Qui-Gon's paired Darth Maul deck); five cards spanning LOF + the
SOR_137 / TWI_138 cards (registered in their own set modules). Four small additive
seams plus one new self-contained decision kind; none touch core resolution or the
trigger/decision machinery destructively. No escape-hatch on any card. Tests:
`tests/test_lof_cards.py::Test{PongKrell,FallenLightsaber,SithHolocron,Merrin,CountDooku}`.
- **New `hp_remaining_lt_source_power` target predicate** (`resolver._spec_matches_ci`)
  — candidate's *remaining* HP must be strictly less than the SOURCE unit's
  *effective* power (the Legal Authority SHD_124 `power_less_than_captor`
  relative-stat pattern, but remaining-HP vs source-power). **Pong Krell LOF_38**
  (Grit — keyword layer; "When this unit completes an attack (and survives): you may
  defeat a unit with less remaining HP than this unit's power") is an optional
  `WhenAttackEnds` (the Vermillion LAW_215 surviving-attacker seam) `DefeatUnit`
  with that predicate (`controller="any"` = "a unit"); Grit's damage-driven power is
  read at trigger time, and the optional trigger auto-declines when nothing
  qualifies.
- **New `Condition.SOURCE_HAS_TRAIT(param)`** (registry) — the source unit has the
  trait via the trait query layer. For a `GrantedAbility` (which resolves from the
  HOST, so the source IS the host), this gates "if attached unit is a <Trait> unit".
  **Fallen Lightsaber SOR_137** (Upgrade; "If attached unit is a Force unit, it
  gains: 'On Attack: Deal 1 damage to each ground unit the defending player
  controls'") = `GrantedAbility(OnAttack → DealDamage(1, controller="enemy",
  arena="ground", EACH_ENEMY))` gated by `SOURCE_HAS_TRAIT("Force")` (the granted
  ability is collected only while the host is Force; EACH_ENEMY ground auto-targets
  the defending player's ground units). The non-Vehicle attach is the upgrade-target
  parser.
- **Sith Holocron LOF_138** (Upgrade, attach to a Force unit; "Attached unit gains:
  'On Attack: You may deal 2 damage to a friendly unit. If you do, this unit gets
  +2/+0 for this attack'") = `GrantedAbility` wrapping an optional `OnAttack` whose
  one `CustomEffect` (target = a friendly unit — the host itself is legal) deals 2
  and applies a +2/+0 this-attack `_make_modifier` to the HOST, bound for "If you
  do" (the Kihraxz SHD_118 pattern, resolving from the host). The "Force unit" attach
  restriction is the upgrade-target parser, so the granted ability needs no condition.
  No engine change.
- **New `Condition.CONTROLLER_HAS_CARD_IN_HAND`** (registry) — ≥1 card in hand,
  gating a "you may discard a card from your hand" trigger so it is not offered with
  an empty hand. **Merrin LOF_160** ("On Attack: You may discard a card from your
  hand. If you do, deal 2 damage to a unit") = an optional `OnAttack` gated by it,
  whose one `CustomEffect` (target = any unit) discards a hand card then deals 2,
  bound for "If you do". DEVIATION (documented): the discard uses the established
  first-card simplification (K-2SO SOR_145 / J-Type Nubian Starship LOF_194).
- **New `per_exploit_damage` decision kind** (`actions.push_per_exploit_damage` +
  `DealExploitDamage` / `DeclineExploitDamage`) for **Count Dooku TWI_138** (Exploit
  2, Overwhelm — keyword layer; "When Played: For each unit you exploited while
  playing this card, you may deal damage to an enemy unit equal to the power of the
  exploited unit"). Each exploited (sacrificed) unit's effective power is
  **snapshotted at sacrifice time** (`ExploitSacrifice` records `sacrificed_powers`
  alongside `sacrificed_ids`, since the unit is gone by the When Played) and threaded
  through the play event_ctx as `exploited_powers` (new `_put_unit_in_play` param,
  set by `_resolve_exploit_commit`). The decision walks one chunk per exploited
  power: for each, the controller may deal it to one enemy unit or skip it (the "you
  may"). Target choices are **recorded into a plan** (no damage dealt during
  choosing, so the board/enemy-target set is static); once every chunk is decided the
  decision pops and all planned damage is dealt in order — the "record, then pop,
  then deal" shape (cf. each_player_defeats / repeated_modal) so any defeat trigger
  lands on a clean stack with no mid-decision re-push. Pushed only with ≥1 positive
  amount AND ≥1 enemy unit. Count Dooku's mandatory `WhenPlayed` CustomEffect is a
  thin adapter onto the push helper (the Palpatine SOR_135 pattern). Registered in
  `invariants._KNOWN_DECISION_KINDS` and `web/session.py` (`_PROMPTS`); `HeuristicBot`
  gained `_choose_per_exploit_damage` (always deal — free enemy damage — to the
  lowest-HP threat, else decline) + `DeclineExploitDamage` in its safe-default order.
- Group readiness: **5/5**; deck `darth-maul` now **16/52** (next group
  `darth-maul:02`; the two force-token escalation groups :04/:05 REUSE the Force-token
  primitive already built for `qui-gon-jinn:06`, so they are not real escalations).

**Group `darth-maul:03` — Combat tricks, buffs & tempo (2026-06-30).** Three LOF
cards; one new passive marker spec, the rest compose from existing primitives.
None touch core resolution or the trigger/decision machinery. No escape-hatch.
Tests: `tests/test_lof_cards.py::Test{OggdoBogdo,DarthMaulsLightsaber,Scimitar}`.
- **New `registry.AttackRestriction(condition)` passive marker** (the Salacious
  Crumb `EntersPlayReady` LAW_210 marker pattern, mirrored for attack
  enumeration): a source unit may declare an attack only while its registered
  `AttackRestriction`'s condition holds. Read by the new `actions._attack_forbidden`
  helper at the **single attack-enumeration chokepoint** `_enumerate_attacks` (which
  serves BOTH normal ACTION attacks and effect-granted attacks via
  `_filter_granted_attacks`), dropping a forbidden unit from the legal attackers; a
  no-op for the overwhelming majority of units (no such spec). Added to soak.py's
  passive-marker tuple so an AttackRestriction-only card is not a false zero-fire.
  **Oggdo Bogdo LOF_63** (5/5 Creature) = `[AttackRestriction(SOURCE_DAMAGED),
  OnAttackDefeatsUnit → Heal(2, SELF)]` — "This unit can't attack unless it's
  damaged" (undamaged Oggdo can't be a chosen attacker) + "When this unit attacks
  and defeats a unit: Heal 2 damage from this unit" (the self-heal re-arms the
  restriction's downside). Purely additive (a new marker spec + a read at an
  existing seam, the allowed small-primitive path).
- **Darth Maul's Lightsaber LOF_140** (Upgrade, Overwhelm; attach to a non-Vehicle
  unit) — a `WhenPlayed` gated by `ATTACHED_HOST_NAMED("Darth Maul")` (collected
  only when the host is Maul, the LOF_201 Qui-Gon Jinn's Lightsaber pattern) whose
  one `CustomEffect` is a thin adapter onto `push_granted_attack(attacker_id=host,
  optional=True, grant_keywords=["Overwhelm"], no_base=True)` (the Hotshot DL-44
  SHD_174 host-pin + all pre-existing granted-attack fields): "you may attack with
  him; for this attack he gains Overwhelm and can't attack bases". The host is read
  from `event_ctx["attached_to_id"]`. The upgrade's printed Overwhelm bar is the
  accepted inert-printed-upgrade-keyword simplification (no card relies on it; the
  modelled grant is the "for this attack" copy the text spells out). No engine
  change.
- **Scimitar LOF_233** (3/4) — "While this unit is damaged, it gets +3/+0" = a
  self-targeted `ConstantAbility(StatBonus(3,0), condition=SOURCE_DAMAGED)`, read
  passively by `compute_power` (the Seasoned Shoretrooper SHD_83 / Anakin's
  Interceptor TWI_142 self-conditional-stat pattern). No engine change.
- Group readiness: **3/3**; deck `darth-maul` now **26/52** (2 groups left, both
  force-token: :04/:05 REUSE the Force-token primitive already built for
  `qui-gon-jinn:06`, so they are not real escalations; next group `darth-maul:04`).

**Groups `darth-maul:04` + `:05` — force-token (reuses qui-gon-jinn:06,
2026-06-30).** The deck's two force-token groups (12 cards) are a pure REUSE of the
Force-token primitive built for `qui-gon-jinn:06` (`CreateForceToken` / `UseForce` /
`CONTROLLER_HAS_FORCE_TOKEN` / `push_use_force`), not real escalations. **:04** added
zero engine code (see [[project_darth_maul]]). **:05** (5 cards) needed three small
additive seams, none touching core resolution or the trigger/decision machinery; no
escape-hatch on any card. Tests: `tests/test_lof_cards.py::Test{AcolyteOfTheBeyond,
SavageOpress,InfusedBrawler,KyloRen,DarthTyranus}`.
- **Acolyte of the Beyond LOF_129** ("On Attack/When Defeated: create your Force
  token") — two mandatory triggers (`OnAttack` + `WhenDefeated`), each a non-targeted
  `CreateForceToken` (the token is a per-player boolean, so a redundant create is a
  no-op). No engine change.
- **`push_use_force` gained a `decline_penalty` field (Savage Opress LOF_137).** The
  inverse force-spend: "You may use the Force. **If you don't**, deal 9 to your base."
  The penalty is on the DECLINE side (and lands when no token is held), so a normal
  optional-trigger-gated-by-`CONTROLLER_HAS_FORCE_TOKEN` would be wrong. New optional
  `decline_penalty` param (encoded `"self_base_damage:9"`, applied by the new
  `_apply_use_force_decline_penalty`): when a Force token is held a `use_force`
  decision is pushed (use it = avoid the penalty; `DeclineUseForce` = take 9 to your
  own base, applied after the decision pops — the "pop, then deal" gotcha); when **no**
  token is held the penalty lands inline (push_use_force applies it instead of
  no-oping). `DeclineUseForce` gained a `decline_penalty` field (set from ctx in
  `_use_force_actions`) so the bot/web can see it; `HeuristicBot._choose_use_force`
  now pays the Force token instead of declining when a penalty is present (taking 9 to
  its own base is worse). Savage Opress is two mandatory `WhenPlayed`/`WhenDefeated`
  triggers, each a no-target `CustomEffect` adapter (the Palpatine SOR_135
  inline-push pattern); Overwhelm is the keyword layer. Purely a new field on an
  existing decision kind (no new kind, no machinery change).
- **`tokens.defeat_experience` helper + `ExperienceDefeated` event (Infused Brawler
  LOF_156).** "When this unit completes an attack: Defeat an Experience token on it"
  needed a token-removal helper (mirrors `defeat_shield`; `ExperienceDefeated`
  serialises via the generic `event_to_model`, rendered in web `format.ts`). Infused
  Brawler = an optional `WhenPlayed` gated by `CONTROLLER_HAS_FORCE_TOKEN` (the "you
  may use the Force" choice = Accept/Decline, the Karis LOF_31 pattern) whose
  no-target `CustomEffect` spends the token and gives this unit 2 Experience (bound
  for "If you do") + a mandatory `WhenAttackEnds` ("completes an attack"; survivor-only
  firing is faithful — a defeated attacker has no token) defeating one Experience
  token on itself.
- **`WhenYouPlayCard.on_self` filter (Kylo Ren LOF_229).** "When you play an upgrade
  on this unit: …" — a new `on_self` field narrows the `WhenYouPlayCard` observer to a
  played upgrade attached to the source unit (the matcher locates the played upgrade's
  host by scanning in-play units' `attached_upgrades`; the upgrade is attached before
  `CardPlayed` fires). Kylo = `WhenYouPlayCard(card_type="upgrade", on_self=True)`,
  optional + gated by `CONTROLLER_HAS_FORCE_TOKEN`, a no-target `CustomEffect` spends
  the token and draws a card. Overwhelm is the keyword layer.
- **Darth Tyranus LOF_231** ("While the Force is with you, this unit gains Ambush") —
  a self-targeted `ConstantAbility(KeywordGrant("Ambush"),
  condition=CONTROLLER_HAS_FORCE_TOKEN)` (the Jedi Sentinel LOF_196 / Hunting Nexu
  SHD_168 conditional self-grant pattern), read passively by `has_keyword` and
  consulted at the enter-play keyword bus (so playing him with a token grants the
  Ambush attack). The keyword sanitiser's conditional-self-grant rule strips his
  mis-tagged printed Ambush; the genuinely-possessed Shielded is kept. No engine
  change.
- Group readiness: **5/5**; deck `darth-maul` now **52/52 — fully encoded** (all 5
  groups complete; eligible for `verify_encoding.py darth-maul --graduate`).

**Engine primitive added (group `jabba-the-hutt:07`) — create-token-unit / the
Credit-token economy (2026-06-21).** The dedicated primitive session the planner
flagged. Two parts, both additive; neither touches the trigger/decision machinery.
Cards: `tests/test_law_cards.py` (LAW_15/134/244/252) + synthetic
`tests/test_credit_token.py`. No escape-hatch on any card.
- **Credit creation.** A new effect dataclass **`registry.CreateCreditToken(count=1)`**
  (non-targeted, like `DrawCards`; one `execute_effect` arm) creates Credit tokens
  for the source's controller via **`tokens.create_credit_token`**. A Credit is an
  unlimited-supply token (the real DB def LAW_1, type "Credit Token") held in a
  **dedicated pile** — new field **`PlayerState.credits`** + new zone
  **`Zone.CREDITS`** — *not* the resource list, so all the normal resource
  machinery (exhaust, regroup ready-all, Smuggle/Plot, SacrificeResource,
  conservation) ignores credits for free. Wired into `state` serialisation
  (`_player_to_dict`/`from_dict`, `zone_list`, `all_instances`), invariants
  (`Zone.CREDITS` in the zone-tag consistency loop), and the view
  (`PlayerZoneView.credits` count — public; web `format.ts` renders the
  CreditTokenCreated/CreditDefeated events). Like Shield/Experience, credits are
  **excluded from card conservation** (`all_instances_for_player` does not scan the
  credit pile).
- **Credit spend (need-based, automatic, no decision kind).** A credit is
  *defeated* while paying a resource cost to pay 1 less. Spending is **need-based**:
  ready resources are exhausted first and a credit is defeated **only** to cover a
  shortfall (`cost > ready resources`). New helpers `_affordable_with_credits`,
  `_defeat_credit`, **`_pay_play_cost(s, ps, cost) -> credits_defeated`** wired into
  the two play-from-resources-for-value paths: **PlayCard** (the non-Exploit
  branch + its legal_actions affordability gates) and the **play-from-hand
  subsystem** (`_playable_units_from_hand` affordability + `PlayFromHand` payment).
  With zero credits the behaviour is byte-identical to the old resource-only
  payment, so the normal game and the whole soak/determinism suite are unaffected.
  This is deterministic (no RNG, no decision) and strategically sound (a credit is
  never wasted on a play affordable from ready resources). **SCOPE/LIMITATION
  (documented):** credit-spend is NOT wired into Smuggle/Plot (they pay from the
  *other* resources), the Exploit cost reduction, or activated-ability
  `PayResources` costs — no shipped card combines credits with those; the lost
  agency is that a player cannot *choose* to spend a credit they do not strictly
  need (e.g. to deliberately trigger a "if you defeated a Credit" rider on an
  otherwise-affordable play).
- **LAW_244 Unmarked Credits** (Event) = `EventAbility([CreateCreditToken()])`.
  **LAW_134 Bib Fortuna** = `WhenPlayed CreateCreditToken` gated by
  `CONTROLLER_HAS_OTHER_TRAIT_UNIT("Underworld")`. **LAW_252 Fett's Firespray**
  (Ambush — keyword layer; "When Attack Ends: if the defending unit was defeated,
  create a Credit token") = `OnAttackDefeatsUnit → CreateCreditToken` — DEVIATION
  (documented): `OnAttackDefeatsUnit` fires only when the attacker survives, so a
  trade (Fett dies too) creates no credit (the same simplification the existing
  "defeats a unit" trigger makes); a base attack creates none either way.
- **LAW_15 Jabba the Hutt** (Leader, Ambush): undeployed Action [1 resource,
  Exhaust, return a friendly Underworld unit]: Create a Credit token — an
  `undeployed_only` ActivatedAbility whose "return a friendly Underworld unit" cost
  is modelled as a leading `ReturnToHand` effect (the C-3PO SEC_93 return-as-effect
  pattern), gated by `CONTROLLER_HAS_TRAIT_UNIT("Underworld")` so the return is a
  genuine cost (no Underworld unit → not offered); the targeted `ReturnToHand` is
  ordered before the non-targeted `CreateCreditToken` so the player is prompted
  once. Deployed costless Action: play an Underworld unit from hand, and **if a
  Credit was defeated paying its cost** the unit gains Ambush this phase — a thin
  `push_play_from_hand(trait="Underworld", grant_keyword_if_credit_spent="Ambush")`
  adapter (the new optional `grant_keyword_if_credit_spent` field reads
  `credits_defeated` from `_pay_play_cost`), gated by
  `CONTROLLER_CAN_PLAY_UNIT_FROM_HAND("Underworld")` (now credit-aware) so the
  costless action is never a no-op. The Epic Action deploy (6+ resources) is the
  standard `deploy_threshold` machinery. Because credit-spend is need-based, the
  deployed action grants Ambush only when the unit's cost exceeded ready resources.
- Group readiness: **4/4**; deck `jabba-the-hutt` now **20/52** (next group
  `jabba-the-hutt:03`; the remaining escalation is `jabba-the-hutt:08`
  control-change — already implemented for shd-han-solo:02, so it should reuse
  `actions.change_control`).

**Group `jabba-the-hutt:03` — Direct damage & removal (2026-06-21).** Three cards;
three small additive engine seams, none touching core resolution or the
trigger/decision machinery destructively; no escape-hatch on any card. Tests:
`tests/test_law_cards.py::TestSarlaccOfCarkoon`, `::TestBobaFett`,
`::TestContractedHunter`.
- **New `discard_unit_damage` decision kind** (`actions.push_discard_unit_then_damage`
  + `SelectDiscardUnitForDamage` / `ChooseDiscardDamageTarget` /
  `_resolve_discard_unit_damage`) for **The Sarlacc of Carkoon LAW_163** ("On
  Attack: Put a unit from your discard pile on the bottom of your deck.  Deal
  damage equal to that unit's power to an enemy ground unit").  A self-contained
  two-stage decision in the `push_sacrifice_resource_for_damage` "choose, then
  deal" shape: stage `"select"` recycles a chosen Unit from the controller's
  discard pile to the bottom of the deck (face-down) and records its **printed**
  power (a discard card carries no in-play stats) as the magnitude; stage
  `"target"` deals it to a chosen enemy ground unit.  Mandatory-if-able — pushed
  only when the discard pile holds ≥1 unit (no decline); the damage step is
  skipped when no enemy ground unit exists at recycle time (the recycle still
  happens).  Damage is dealt **after** the decision pops (the "pop, then deal"
  gotcha) so a defeat trigger lands on a clean stack; the target stage reuses
  `_sacrifice_damage_targets`.  Registered in `invariants._KNOWN_DECISION_KINDS`
  and `web/session.py` (`_PROMPTS` + stage-specific prompts); `HeuristicBot` gained
  `_choose_discard_unit_damage` (recycle the highest-power discarded unit, then hit
  the biggest enemy ground unit).  A plain `OnAttack` whose one `CustomEffect` is a
  thin adapter onto the push helper (the Palpatine SOR_135 pattern).  No new
  decision-machinery change (a new self-contained decision kind, the allowed
  small-primitive path).
- **`PhaseStartTrigger` wired** (it was already defined+exported in `registry.py`
  but never matched or fired) for **Contracted Hunter JTL_216** (Ambush — keyword
  layer; "When the regroup phase starts: Defeat this unit").  Added a
  `resolver._trigger_matches` arm (matches the `PhaseChanged` event whose
  `new_phase` equals the trigger's `phase`) and a single firing site in
  `actions._enter_regroup` (after the regroup draws + setting the active player to
  the initiative holder; guarded by `not is_terminal`, after_all_player_idx = the
  initiative holder so the resource step resumes there).  Contracted Hunter is a
  `PhaseStartTrigger(phase="regroup") → DefeatUnit(fixed=SELF)` (mandatory, resolves
  inline).  Purely additive — with no `PhaseStartTrigger` card in play the firing
  is a cheap no-op (no trigger matches `PhaseChanged`) and uses no RNG, so the
  normal game and the determinism/soak suites are unaffected.
- **New `Condition.CONTROLLER_N_PLUS_READY_RESOURCES(param=N)` atom** (≥N
  *ready*/unexhausted resources, vs the existing `CONTROLLER_N_PLUS_RESOURCES`
  which counts total) for **Boba Fett LAW_214** ("When Played/On Attack: You may
  pay 1 resource.  If you do, deal 3 damage to a ground unit").  Two otherwise-
  identical triggers (a `WhenPlayed` and an `OnAttack`), both `optional=True`
  ("you may"), each gated by `CONTROLLER_N_PLUS_READY_RESOURCES(1)` so the trigger
  is offered only when the resource can be paid (the "don't offer a no-op"
  pattern), with one `CustomEffect` (target = any ground unit) that pays the 1
  resource (`_exhaust_resources`) and deals 3 — bound together so the damage lands
  only if the payment is made (the Bright Hope SOR_99 / Kihraxz SHD_118 "if you do"
  pattern; "pay 1 resource" cannot be a real trigger *cost*, since costs are
  ActivatedAbility-only).  The optional trigger auto-declines when no ground unit
  is on the board.
- Group readiness: **3/3**; deck `jabba-the-hutt` now **26/52** (next group
  `jabba-the-hutt:04`).

**Group `jabba-the-hutt:04` — Card advantage & disruption (2026-06-21).** Three
cards; one small additive engine seam (a new self-contained decision kind) plus a
new gating condition atom, the other two compose from existing primitives. None
touch core resolution or the trigger/decision machinery destructively; no
escape-hatch on any card. Tests: `tests/test_law_cards.py::TestGreatPitOfCarkoon`,
`::TestSyndicateSpiceRunner`, `::TestTheAxeForgets`.
- **New `discard_for_search` decision kind** (`actions.push_discard_unit_for_search`
  + `DiscardForSearch` + `_discard_for_search_actions`) for **Great Pit of Carkoon
  LAW_23** ("Epic Action [discard a unit from your hand]: Search your deck for a
  card named The Sarlacc of Carkoon, reveal it, and draw it"). The "discard a unit
  from your hand" cost lets the controller *choose* which unit (the
  `DiscardFromHand` effect's first-card simplification is for *opponent* discards,
  not a self-paid cost), so it is a small stage-less decision: one
  `DiscardForSearch(instance_id)` per discardable hand Unit, no decline (the cost
  is mandatory). Choosing one discards it, **pops the decision**, then runs the
  search via the existing **deck_search** seam (`push_deck_search`, the Tarkin
  SOR_84 pattern) over the **whole deck** (`window=len(deck)`, eligible = name
  match, `up_to=False`) — the un-taken cards are bottomed in a seeded-random order,
  which doubles as the post-search shuffle. A once-per-game Epic Action on a Base
  (`epic=True`, `costs=[]`, enumerated via the existing base_zone scan, the
  Daimyo's Palace LAW_20 pattern), gated by the **new
  `Condition.CONTROLLER_HAS_UNIT_IN_HAND`** atom so the epic is not wasted when
  there is no unit to discard (the "don't offer a no-op epic" pattern). The one
  `CustomEffect` is a thin adapter onto the push helper (the Palpatine SOR_135
  pattern). Registered in `invariants._KNOWN_DECISION_KINDS` and `web/session.py`
  (`_PROMPTS`); `HeuristicBot` gained `_choose_discard_for_search` (discard the
  cheapest unit — least tempo loss). No new decision-machinery change (a new
  self-contained decision kind, the allowed small-primitive path).
- **Syndicate Spice Runner LAW_136** (Unit, Underworld) — a `WhenPlayed` whose one
  CustomEffect is a thin adapter onto the **deck_search** seam (`window=3,
  count=1, up_to=False`, eligible = a Unit carrying the Underworld trait); the
  R2-D2 LAW_145 pattern. Mandatory-if-able.
- **The Axe Forgets LAW_246** (Event, Gambit) — a plain `EventAbility` with one
  mandatory `ReturnToHand(TargetSpec(controller="any", kind="unit",
  predicates=("non_leader",), cost_max=3))`; `controller="any"` mirrors the text
  omitting friendly/enemy. Fizzles cleanly with no eligible unit.
- Group readiness: **3/3**; deck `jabba-the-hutt` now **31/52** (next group
  `jabba-the-hutt:05`; the remaining escalation is `jabba-the-hutt:08`
  control-change — already implemented for shd-han-solo:02, so it reuses
  `actions.change_control`).

**Group `jabba-the-hutt:05` — Combat tricks, buffs & tempo (2026-06-21).** Six
cards; three small additive engine seams (two new specs + one target predicate)
plus event_ctx threading, the rest compose from existing primitives. None touch
core resolution or the trigger/decision machinery destructively; no escape-hatch
on any card. Tests: `tests/test_law_cards.py::Test4LOM`, `::TestKhetanna`,
`::TestHaymaker`, `::TestSalaciousCrumb`, `::TestWeequayPirate`,
`::TestBlackSunCabalist`.
- **4-LOM LAW_65** ("When Played: You may attack with a friendly Bounty Hunter
  unit, even if it's exhausted; it can't attack bases") — a mandatory `WhenPlayed`
  whose one `CustomEffect` is a thin adapter onto `push_granted_attack(optional=True,
  attacker_trait="Bounty Hunter", allow_exhausted=True, no_base=True)` (the Mon
  Mothma SEC_103 granted-attack fields, all pre-existing). 4-LOM is itself a Bounty
  Hunter so it is a legal attacker ("a friendly", not "another"). No engine change.
- **New deferred `NextPlayDiscount(trait, amount)` effect + pending-discount
  play-cost seam (Khetanna LAW_158).** Unlike a static `CostReduction` on the
  card's own cost, this records a *pending* "next <trait> unit you play this phase
  costs N less" discount in a new **`GameMemory.pending_play_discounts`** list (one
  entry per `{player_id, trait, amount}`; cleared at `clear_phase`, serialised in
  `to_dict`/`from_dict`). New helpers `actions._pending_play_discount` (read-only,
  the first matching entry) feed `_play_cost` (so both affordability and payment
  see it), and `_consume_play_discount` removes one matching entry at the real play
  site (`PlayCard`, right after `_pay_play_cost`). The resolver got one no-target
  arm appending the entry. Khetanna is two `TriggerAbility`s (`WhenPlayed` +
  `OnAttack`) each `[NextPlayDiscount("Underworld", 1)]`. **LIMITATION (documented):
  the discount applies only on the normal `PlayCard` path** (and its affordability
  gates), not the ability-driven play-from-hand subsystem (which pays the raw
  effective cost, like Exploit), so it does not stack onto a unit played by Jabba's
  deployed action — the common, faithful case. With no pending entry the play-cost
  path is byte-identical to before. No new decision kind.
- **New `same_arena_as_event` target predicate (Haymaker LAW_168).** "Give an
  Experience token to a friendly unit. That unit deals damage equal to its power to
  an enemy unit in the same arena" is two dependent effects sharing the
  resolve_effects `event_ctx` (the Nothing Left to Fear LAW_41 pattern): a mandatory
  `CustomEffect.target` picks the friendly unit, tokens it, and records its
  *post-token* power + arena (`event_ctx["haymaker_power"]`/`["same_arena"]`); a
  second `CustomEffect.target` deals that recorded power to a chosen enemy unit
  filtered by the new predicate (reads `event_ctx["same_arena"]` "ground"/"space").
  Each is mandatory-if-able; no friendly unit ⇒ nothing, no same-arena enemy ⇒ the
  damage fizzles. Purely a new predicate arm.
- **New `EntersPlayReady(condition)` ability spec (Salacious Crumb LAW_210).** "If
  you control Jabba the Hutt, this unit enters play ready" is read by
  `_put_unit_in_play` when the source itself enters play (new `_enters_play_ready`
  helper): a registered `EntersPlayReady` whose `condition` holds flips the unit to
  ready instead of the default exhausted. Salacious Crumb = `EntersPlayReady(
  condition=CONTROLLER_CONTROLS_NAMED("Jabba the Hutt"))` (the existing condition
  atom; matches the leader deployed or undeployed in base_zone, or a Jabba unit).
  Raid 2 is the keyword layer. Purely a read at the placement step (a no-op with no
  such spec); `soak._analyse_ability_coverage` treats it as passive (like a
  constant) so it is not a false zero-fire.
- **`cost_paid` threaded into the enter-play `event_ctx` (Weequay Pirate LAW_231).**
  "When Played: If no resources were paid to play this unit, give it an Experience
  token" — `_put_unit_in_play` gained an optional `cost_paid` param (passed by
  `PlayCard` and the play-from-hand subsystem) threaded into the trigger event_ctx;
  Weequay's `WhenPlayed` `CustomEffect` gives itself a token only when
  `event_ctx["cost_paid"] == 0` (an unknown `None` cost ⇒ no token). Saboteur is the
  keyword layer.
- **Black Sun Cabalist LAW_249** ("When Played: Give an Experience token to another
  friendly Underworld unit") — a plain `WhenPlayed` `GiveToken("Experience",
  TargetSpec(controller="friendly", kind="unit", traits=("Underworld",),
  predicates=("not_self",)))`; mandatory-if-able, fizzles with no other Underworld
  unit. No engine change.
- Group readiness: **6/6**; deck `jabba-the-hutt` now **47/52** (next group
  `jabba-the-hutt:06`; the remaining escalation is `jabba-the-hutt:08`
  control-change — already implemented for shd-han-solo:02, so it reuses
  `actions.change_control`).

**Group `jabba-the-hutt:06` — Miscellaneous abilities (2026-06-21).** Two cards;
one composes via a small additive seam, the other is **escalated** (it needs a
framework-level multi-decider primitive). No escape-hatch. Tests:
`tests/test_law_cards.py::TestMalakili`.
- **Arena-wide TraitGrant seam (Malakili LAW_212).** "Each friendly Creature unit
  … gains the Underworld trait" is the first *arena-wide* (non-upgrade) TraitGrant.
  The trait query layer (`swu.engine.traits._granted_traits`) previously scanned
  only a unit's attached upgrades; it now **also** scans in-play units for a
  `ConstantAbility` whose effects include a `TraitGrant` and whose (non-SELF)
  `target` matches the queried unit (resolved from the source unit's perspective via
  `resolver._spec_matches_ci`), so a friendly Creature in play counts as Underworld
  everywhere the trait layer is consulted (`_spec_matches_ci`'s trait filter, the
  trait-gated Conditions, the select_token/distribute trait filters — e.g. Black Sun
  Cabalist LAW_249's "another friendly Underworld unit" now offers a granted
  Creature). Two safety pieces: a **re-entrancy guard** (`_resolving_grants`, keyed
  by `(id(state), instance_id)`) breaks the cycle where a grant's own `traits=`
  filter reads the candidate's effective traits via `get_traits` → `_granted_traits`
  again (the nested query sees printed traits only); and a cached
  `_is_arena_trait_granter` (by `(set, number)`, card defs immutable) so the hot
  trait-query path skips the full spec scan for the overwhelming majority of cards
  that grant no trait (one dict lookup). Malakili is a plain
  `ConstantAbility(target=friendly Creature unit, effects=[TraitGrant("Underworld")])`
  — purely additive (a new scan + guard + cache in the trait layer), no new decision
  kind, no trigger/decision-machinery change (the allowed small-primitive path).
  **DEVIATION (documented):** the "and each Creature unit you own that *isn't in
  play* gains the Underworld trait" clause is NOT implemented — the trait layer is a
  read over *in-play* `CardInstance`s, whereas out-of-play trait gates read
  `card_def.traits` directly (the play-from-hand `trait` filter, the deck_search
  eligibility closures); routing every out-of-play read through a state-aware
  `has_trait` is a broad change to card-specific paths, out of scope for a card
  batch. The in-play clause (the board-relevant case) is faithful.
- **Vermillion LAW_215 DONE 2026-06-21** (the escalation — see the dedicated
  engine-primitive note below). Deck `jabba-the-hutt` now **51/52**.
- Group readiness: **2/2**; deck `jabba-the-hutt` now **51/52** (only Double-Cross
  LAW_170 in the control-change group `jabba-the-hutt:08` left).

**Engine primitive added (group `jabba-the-hutt:06` escalation) — attack-ends
trigger + reveal-play-credit multi-decider (Vermillion LAW_215, 2026-06-21).** The
dedicated framework session the planner flagged.  Two additive pieces; neither
rewrites core resolution, but the second is a genuinely new multi-decider decision
kind that *reaches into* the play paths.  No escape-hatch.  Tests:
`tests/test_law_cards.py::TestVermillion`.
- **`WhenAttackEnds` trigger (registry + one `_trigger_matches` arm + two combat
  firing sites).** "When Attack Ends: If this unit survived" fires for the
  *attacker* at the very end of BOTH combat pipelines
  (`_resolve_unit_combat_step2` and `_resolve_base_attack_step2`), keyed via a new
  `attack_ended_survivor` event-context flag set only when the attacker is still in
  an arena after defeat processing — so the "survived" clause is intrinsic
  (mirrors the `attack_defeated_unit` / `dealt_combat_damage_to` /
  `dealt_combat_damage_to_base` event-flag pattern, `event=None`, no dedicated
  event class).  `after_all` = the opponent so the turn passes once the resulting
  decision resolves (the attack's switch is suspended while a decision is pending).
  Purely additive — a no-op unless a `WhenAttackEnds` card is in play, no RNG, so
  the soak/determinism suites are unaffected.  A base attack never damages the
  attacker, so it always survives there.  KNOWN GAP: an attack aborted *before*
  combat damage by a pre-combat removal of the defender (the step2 early-return)
  does not count as the attack "ending" — out of the firing path; no shipped card
  exercises it.
- **New `"reveal_play_credit"` decision kind (`actions.push_reveal_play_credit`).**
  "Reveal the top card of a deck, then choose a player.  They may play the revealed
  card for free.  If they do, a different player creates Credit tokens equal to that
  card's cost."  One decision drives up to four stages (`stage` ∈
  `choose_deck`/`choose_player`/`may_play`/`choose_host`) with a mid-sequence
  **decider shift** (the say_no SOR_233 / opponent_chooses_target SHD_246
  precedent): the source controller picks which non-empty deck to reveal
  (`ChooseRevealDeck`), then which player may play it (`ChooseRevealPlayer`, which
  shifts the decider to that player); the chosen player plays it for free
  (`PlayRevealedCard`, offered only when playable — an upgrade needs a legal host)
  or declines (`DeclineRevealedCard`, leaving the card on top of its deck); an
  upgrade adds a `choose_host` stage (`ChooseRevealHost`).  The played card is
  **removed from the revealed deck and played for free under the chosen player's
  control** via the normal play paths (`_put_unit_in_play` / `_attach_upgrade` /
  `_resolve_event_ability` — so any card type works, incl. events, and the played
  card's own keyword / When Played abilities fire); the decision is popped FIRST so
  those triggers land on a clean stack (the push_distribute_damage "pop, then act"
  gotcha).  Then the OTHER player (the one who did not play it — unambiguous in
  2-player) makes `create_credit_token` × the card's **printed** cost (reusing the
  jabba-the-hutt:07 Credit pile).  **DOCUMENTED LIMITATION:** the played card's
  `owner_id` is left unchanged (control is implicit — the Stolen Landspeeder
  SHD_161 convention), so when the controller hands the play to a player who does
  NOT own the revealed card (a cross-deck play), that card's *own* abilities
  resolve from its OWNER's perspective; the common cases (a player plays their own
  deck's card) are exact.  Registered in `invariants._KNOWN_DECISION_KINDS` and
  `web/session.py` (`_PROMPTS` + stage-specific prompts); `HeuristicBot` gained a
  `_choose_reveal_play_credit` handler (no reliable heuristic for this political
  card → at choose_player it picks itself, then declines = a safe no-op, never
  handing the opponent a free card or credits) + `DeclineRevealedCard` in its
  safe-default order.  Vermillion is a mandatory `WhenAttackEnds` whose one
  `CustomEffect` is a thin adapter onto the push helper (the Palpatine SOR_135
  pattern).

**Group `jabba-the-hutt:08` — New primitive: control-change (Double-Cross
LAW_170, 2026-06-21).** The planner pre-flagged this as a control-change
escalation, but the primitive already exists (`actions.change_control`, the
shd-han-solo:02 framework session) and so does the Credit-token pile
(jabba-the-hutt:07), so this is a pure **composition** — **no engine change, no
new decision kind, no escape-hatch.** Tests:
`tests/test_law_cards.py::TestDoubleCross`. **Double-Cross LAW_170** (Event,
Trick; "Choose a friendly non-leader unit and an enemy non-leader unit.  Exchange
control of those units.  The player who takes control of the lower-cost unit
creates Credit tokens equal to the difference between those units' costs") is an
`EventAbility` with two sequential, dependent `CustomEffect.target`s sharing the
resolve_effects `event_ctx` (the Nothing Left to Fear LAW_41 / Haymaker LAW_168
pattern): the first (target = friendly non-leader unit) records the chosen unit's
id; the second (target = enemy non-leader unit) performs the whole exchange —
`change_control` relocates the friendly unit to the opponent's arena and the enemy
unit to the controller's arena (owner unchanged; control is implicit = arena
membership), then `tokens.create_credit_token` × the printed-cost difference for
whichever player now controls the lower-cost unit (the opponent if the friendly
unit was cheaper, else the controller; none on a tie).  The exchange is
all-or-nothing — with no friendly OR no enemy non-leader unit the second effect
no-ops.  **SCOPE/LIMITATION (the documented control-change convention):**
"friendly"/"enemy" resolve by `owner_id` in the target matcher
(`resolver._spec_matches_ci`), which equals the controller in every normal case —
only a unit whose control was ALREADY changed by an earlier effect would diverge
(the same limitation noted on `actions.change_control`).  Group readiness:
**1/1**; deck `jabba-the-hutt` now **52/52 — fully encoded** (all 8 groups
complete; eligible for `verify_encoding.py jabba-the-hutt --graduate`).

**Graduation soak fixes (`jabba-the-hutt`, 2026-06-21).** The deck-specific
200-game soak (run only at graduation) surfaced two latent bugs — both
pre-existing, exposed once the whole deck was playable, not introduced by
Double-Cross. Now 200/200 clean.
- **The Sarlacc of Carkoon LAW_163 recycled an exhausted card into the deck.** A
  unit defeated *while exhausted* lands in discard still exhausted (discard carries
  no exhaust meaning, so this is allowed); the Sarlacc's "put a unit from your
  discard pile on the bottom of your deck" (`SelectDiscardUnitForDamage.apply`)
  moved it to the deck without resetting it, so an exhausted card sat in DECK —
  tripping the zone/exhaust-sanity invariant ("no exhausted cards in DECK/HAND").
  Fix: clear `exhausted` **and** `damage` when bottoming the recycled unit (a card
  out of play must be a clean card). The only discard→deck path; deck_search /
  reveal_top bottom cards already-unexhausted deck-top cards.
- **Vermillion LAW_215's public reveal tripped the hidden-info-leak invariant.**
  Vermillion's `reveal_play_credit` does a *genuine public* "Reveal the top card
  of a deck" — when it reveals the OPPONENT's deck top, that card legitimately
  becomes face-up/public, so its `instance_id` appearing in the revealing player's
  view is correct. The leak invariant (`invariants._check_hidden_info`) had no
  notion of a public reveal (the `reveal_top` decision is a *private* own-deck
  look, redacted from the opponent, so it never trips). Fix: exempt instance_ids
  recorded as `revealed_id` on a pending `reveal_play_credit` decision from the
  hidden-info check. Test coverage: the existing `TestVermillion` + the clean soak.

**Bug fixes (2026-06-17) — replay seed capture + Ozzel self-harm gate:**
- **Replay seed capture.** Web games were created with `seed=None`, so
  `create_game` drew fresh OS entropy that was never recorded. The exported
  replay bundle carried `"seed": null` and could not be reproduced — re-driving
  it re-shuffled the decks and diverged on the first hand-dependent action
  (`PlayFromHand`/`PlayCard`). `SessionStore.create` now pins a concrete seed
  (`secrets.randbits(63)`) when the caller passes none, and threads it to both
  `create_game` and the bot seed, so every game's `replay_bundle()` reproduces.
  NOTE: bundles exported **before** this fix (seed null) remain non-replayable,
  but their instance ids are still stable (assigned in deck order *before* the
  shuffle), so a deck-order map recovers what each id is. Test:
  `tests/test_web_save_replay.py::test_seedless_game_records_concrete_seed_and_replays`.
- **Admiral Ozzel (SOR_129) self-harm gate.** The bot would activate Ozzel even
  with no affordable Imperial unit in hand — playing nothing while still readying
  each opponent's units (the unconditional "Each opponent may ready a unit"
  clause), i.e. pure self-harm. New condition atom
  `Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND(param=trait)` (reuses
  `_playable_units_from_hand`, so the gate and the offered candidates never
  disagree) now gates Ozzel's `ActivatedAbility`, so it is offered only when an
  Imperial unit is actually playable — the Han Solo SHD_13 "don't offer a no-op /
  self-harm action" pattern. This is a deliberate (tiny) rules deviation: the
  literal card lets you activate it for nothing, but no player ever should.
  Tests: `tests/test_sor_cards.py::TestAdmiralOzzel` (not-offered when nothing
  playable / unaffordable; offered when playable).


---

## Part 2 — Phase 2 keyword implementation notes (Coordinate, Plot, Hidden, Bounty, Smuggle, Piloting)

**Coordinate (conditional-ability prefix keyword, ahsoka-tano:01).** Coordinate
("Gain this ability/keyword while you control 3 or more units") is NOT a single
self-contained keyword effect — it is a conditional *prefix* on a heterogeneous
set of abilities (a stat buff, an enter-play keyword, an on-attack draw, a
granted keyword/buff to others, a granted attack), each gated by the same board
condition. So the keystone is one new condition atom
**`Condition.CONTROLLER_N_PLUS_UNITS(param=3)`** (counts both arenas — deployed
leaders are units and count; an undeployed leader in base_zone does not; the
source counts itself since it is already in its arena whenever evaluated), and
every "Coordinate — X" clause is registered (in the new set module
`src/swu/cards/twi/abilities.py`, imported from `src/swu/cards/__init__.py`) as
the matching ability spec gated by that condition:
- a conditional stat buff → `ConstantAbility(target=SELF, StatBonus(...),
  condition=COORDINATE)` (Echo TWI_90 +2/+2, Clone Heavy Gunner TWI_158 +2/+0,
  332nd Stalwart TWI_240 +1/+1, Ahsoka's deployed +2/+0 — the constant is active
  only while she's in an arena, as the constant scan sees only arena sources);
- a conditional keyword → `ConstantAbility(target=SELF, KeywordGrant(...),
  condition=COORDINATE)`, read passively by `has_keyword`/`keyword_value` so it
  winks on/off with the board (Coruscant Guard TWI_106 Ambush — checked at the
  enter-play bus while the unit is already in its arena, so "including this one"
  works; Hevy TWI_164 Raid 2; Republic Commando TWI_243 Saboteur). The keyword
  sanitiser's conditional-self-grant stripper removes the printed always-on copy
  (the Hunting Nexu SHD_168 / Protector of the Throne SHD_247 pattern), so the
  ability owns the keyword;
- a conditional triggered ability → `TriggerAbility(OnAttack, [DrawCards(1)],
  condition=COORDINATE)` (Anakin Skywalker TWI_147 — the condition gates trigger
  *collection*, so no draw is offered below 3 units);
- a conditional activated ability → `ActivatedAbility(..., undeployed_only=True,
  condition=COORDINATE)` (Ahsoka Tano TWI_11 undeployed "Action [Exhaust]: Attack
  with a unit. +1/+0" — a thin CustomEffect adapter onto `push_granted_attack`,
  the Moff Gideon SHD_7 / Surprise Strike SOR_220 pattern; the condition gates
  availability in `legal_actions`).
Residuals encoded in-line because trivial and in scope: **Hevy TWI_164** "When
Defeated: Deal 1 damage to each enemy ground unit" = a `WhenDefeated` with one
`DealDamage(1, enemy ground EACH_ENEMY)`. Residuals left to the keyword layer:
**Cody TWI_114**'s own printed Overwhelm (kept by the sanitiser's bare-mention
rule; only the Coordinate grant of Overwhelm to *other* units is registered), and
**Ahsoka TWI_11**'s Epic Action deploy (standard `deploy_threshold` machinery,
5+ resources — no registration). Purely additive (a new condition atom + a new
set module), no new decision kind, no trigger/decision-machinery change. Tests:
`tests/test_twi_cards.py` (synthetic condition framework + one per card).

**Plot (deploy-triggered deck-replacement keyword, jabba-the-hutt:01).** Plot
("When you deploy a leader, you may play this card from your resources, paying its
cost. Replace it with the top card of your deck.") is Smuggle's triggered sibling:
a card in your resource zone, played for its **printed** effective cost (not a
bracketed special cost) when you deploy a leader, then replaced with the deck top
so your resource count is preserved. Seam:
- `DeployLeader.apply` snapshots the deploying player's Plot resources
  (`_plot_eligible_resource_ids`, via `has_keyword(…, Keyword.PLOT)`) after firing
  the deploy's WhenDeployed triggers and, if any can actually be played now
  (`_plot_play_actions`), pushes a new `"plot"` decision (`deciding_player` = the
  deploying player; `plot_ids` snapshot in context so a card drawn into the zone
  as a replacement is not retroactively plottable).
- `legal_actions` `"plot"` branch offers a `PlotPlay` per affordable snapshotted
  Plot resource (upgrades per legal host) + a `FinishPlot` ("you may" — declining
  the rest is always legal). `PlotPlay.apply` pays `_play_cost` from the OTHER
  ready resources, replaces the card with the deck top (face-down, ready —
  deterministic, no RNG, mirroring `SmugglePlay`), then plays it via
  `_put_unit_in_play(play_source="plot")` / `_attach_upgrade` / `_resolve_event_ability`
  so its keyword / WhenPlayed triggers fire. Unlike SmugglePlay it does **not**
  pop its decision or switch the active player — one leader deploy can plot every
  eligible resource, so the `"plot"` decision stays and re-offers the rest until
  `FinishPlot` (any decision a played card pushes lands on top and resolves first,
  LIFO; the `"plot"` decision is owned by `deciding_player_id` regardless of any
  intervening active-player flip). New decision kind registered in
  `invariants._KNOWN_DECISION_KINDS` and `web/session.py` (`_PROMPTS` + a
  `PlotPlay` label); `HeuristicBot` gained `_choose_plot` (play the first
  non-enemy-buff Plot card, else finish) + `FinishPlot` in its safe-default order.
  Classifier: Plot moved from `audit_coverage.PHASE3_KEYWORDS` to `PHASE2_KEYWORDS`
  (and `swudb_import`), so a pure-Plot card classifies `keyword-complete`. Tests:
  `tests/test_plot.py` (synthetic keyword framework) + `tests/test_jabba_cards.py`
  (Garindan SEC_186, Lurking Snub Fighter SEC_189). **Residuals** (in
  `src/swu/cards/sec/abilities.py`): Lurking Snub Fighter "When Played: You may
  exhaust a unit" = optional `WhenPlayed ExhaustCard`; Garindan "When Played: Name
  a card. Look at an opponent's hand and discard a card with that name" =
  `WhenPlayed DiscardFromHand(chooser="opponent")` — **DEVIATION (documented):**
  the established first-card discard simplification (K-2SO SOR_145 / Poe's
  opponent_discards) stands in for the controller-named hand-strip, which would
  need a look-at-opponent-hand-and-pick decision kind, out of scope for the
  keyword group.

**Hidden (defensive attack-targeting keyword, jabba-the-hutt:02).** Hidden ("This
unit can't be attacked if it was played this phase") is the defensive sibling of
Sentinel: it does not push a decision or touch combat resolution — it simply
removes the unit from the legal **defenders** for the action phase it entered
play. Seam:
- A unit is protected while `has_keyword(s, u, Keyword.HIDDEN)` AND its
  `instance_id` is in `game_memory.units_played_this_phase` (the set every play
  path adds to in `_put_unit_in_play`, cleared at the REGROUP→ACTION round
  rollover) — so the shield lasts exactly through the phase it was played and
  lifts next round. The single predicate is `actions._is_hidden_from_attack`.
- Applied at the **two** defender-enumeration sites: `_enumerate_attacks` (the
  chokepoint for normal ACTION attacks AND effect-granted attacks, via
  `_filter_granted_attacks`) and the Ambush branch of `legal_actions`. Both first
  filter the enemy arena to an `attackable` list (Hidden units dropped), THEN
  compute Sentinel over `attackable` — so a freshly-played **Hidden + Sentinel**
  unit neither can be attacked nor forces enemy attacks onto itself. Saboteur
  bypasses Sentinel only, **not** Hidden.
- No new decision kind, no `invariants`/`web/session` change (purely an attack-
  enumeration filter, like Sentinel). Classifier: Hidden was already in the
  `Keyword` enum and `audit.PHASE2_KEYWORDS` is not consulted for it (it now reads
  as keyword-complete once the residual is registered). Tests: `tests/test_hidden.py`
  (synthetic keyword framework) + `tests/test_law_cards.py::TestJabbasRancor`.
- **Residual ability** (LAW_216 Jabba's Rancor, in `src/swu/cards/law/abilities.py`):
  "On Attack: An opponent chooses a ground unit they control. You may deal 7
  damage to that unit" reuses the existing **opponent-chooses-target** decision
  kind (`push_opponent_chooses_target`, the Grey Squadron Y-Wing SHD_246 seam),
  extended with one additive `ground_only` flag (restricts the opponent's choice
  to their ground-arena units — no base, no space; the decision is skipped when
  the opponent has no ground unit). A plain `OnAttack` whose one CustomEffect is a
  thin adapter onto the push helper (the Palpatine SOR_135 pattern).

**Bounty (defeat-triggered "opponent collects", shd-han-solo:02).** Bounty is
not a static keyword but an ability template: "Bounty — <effect>. (When this
unit is defeated or captured, your opponent collects its bounty.)" It is modelled
as a normal `WhenDefeated` `TriggerAbility` whose effect resolves for the
**opponent of the dying unit's controller** — expressed by writing the effect
from the **enemy perspective** (e.g. `Heal(..., controller="enemy",
fixed=EACH_ENEMY)` heals the collector's base). This reuses the existing
WhenDefeated machinery with **no change to the trigger/decision system**. The
"while this unit is exhausted, it gains Bounty" clause (Unlicensed Headhunter
SHD_165) is gated by a new `Condition.SOURCE_EXHAUSTED` atom, evaluated against
the unit's state at the moment of defeat (a unit defeated while ready collects
no bounty). Capture is not modelled in the engine, so WhenDefeated is the only
realisable bounty path today. **Limitation:** this convention only covers
bounties whose effect is deterministic or single-target (no opponent *choice*);
a bounty requiring the collector to pick among targets would need the
deciding-player seam — defer it. **Stolen Landspeeder SHD_161** (When Played
hands the unit to an opponent; bounty returns it from discard) is now done — the
**control-change** primitive landed in its own framework session (see the
"Engine primitive added (group `shd-han-solo:02`) — control-change" note in the
Phase 7 section above).

**Smuggle (deck-replacement keyword, shd-han-solo:01).** A card sitting in your
resource zone may be played for its bracketed *smuggle cost* (e.g. "Smuggle [5
resources Aggression Heroism]"), then replaced with the top card of your deck so
your resource count is preserved. Seam:
- `keywords.parse_smuggle_cost(text)` parses the bracket → `(n, aspects)`.
- `actions._smuggle_cost(state, ci, ps)` returns the effective cost (n + the
  usual +2-per-unmatched-aspect penalty against base/leader aspects), or `None`
  if `ci` can't be smuggled. A resource without printed Smuggle may still gain it
  from an in-play granter (Tech SHD_248: a `GrantSmuggleToResources` marker on a
  `ConstantAbility`, consulted only here — cost = card cost + 2 with its own
  aspects), mirroring the `SuppressFirstEnemyEvent` marker pattern.
- `actions.SmugglePlay(instance_id, upgrade_target_id?)` — a new ACTION-phase
  action enumerated by `_enumerate_smuggle_plays`. It removes the card from
  resources, pays the cost from the OTHER ready resources, replaces it with the
  deck top (face-down, ready; skipped on an empty deck), then plays it exactly
  like a hand play via `_put_unit_in_play`/`_attach_upgrade`/`_resolve_event_ability`
  with `via_smuggle=True` threaded through the play event context.
- New trigger `WhenPlayedViaSmuggle` fires only when `event_ctx["via_smuggle"]`
  is set (Cassian SHD_148 "When played using Smuggle: Ready this unit"); a normal
  `WhenPlayed` still fires on either play path. An **upgrade's**
  `WhenPlayedViaSmuggle` is now collected too: `resolver._collect_triggers`'
  `UpgradePlayed` special-case (which locates a freshly-played upgrade by event
  instance id, since it lives in its host's `attached_upgrades`, not an arena)
  was widened from `WhenPlayed` to `(WhenPlayed, WhenPlayedViaSmuggle)` for
  Hotshot DL-44 SHD_174.
- SmugglePlay pushes no new decision kind and uses no RNG (deck top is ordered),
  so the determinism oracle and invariants are unaffected. The classifier moved
  Smuggle into `audit.PHASE2_KEYWORDS` and `has_functional_text` now strips
  keyword cost brackets so a pure-Smuggle card classifies `keyword-complete`.
- **Web UI affordance (2026-06-18).** SmugglePlay was unreachable in the browser:
  `SmugglePlay` is card-anchored to its **resource** instance id (not a
  CONTROL_KIND), but `ResourceRow` rendered every resource as an anonymous
  face-down `Back` with no `onClick`/highlight/`data-instance`, so the action had
  no clickable subject and never showed as a button either. Fix is web-only (the
  frozen engine already revealed own-resource identities via `view_for`): the
  player's own `ResourceRow` now takes the `SlotFns` and renders each resource as
  a face-down `<Card faceDown>` (still a back) wired to `slot.hl/onClick/onHover`,
  so a smuggleable resource lights up (`hl-legal`) and clicking it dispatches the
  SmugglePlay (single action → immediate; an upgrade with N hosts → select, then
  pick a host). Supporting fixes: `interaction.ts::targetOf` now resolves
  `SmugglePlay.upgrade_target_id` (so a smuggled upgrade picks its host like a
  hand play); `Table.tsx` includes `view.my.resources` in the `selectedCard`
  lookup (so a selected smuggle source gets a name + context buttons) and extends
  the enemy-attach confirm gate to `SmugglePlay`; `session.label_for` renders
  "Smuggle &lt;CardName&gt; [onto &lt;Host&gt;]" instead of "Smuggle human_42".
  Opponent resources stay anonymous backs. Tests:
  `web/tests/interaction.test.ts`, `web/tests/table.test.tsx` (smuggleable
  resource highlights + dispatches), `tests/test_web_api.py::
  test_smuggle_play_label_uses_card_name`.
- Residual ability text: **Hotshot DL-44 SHD_174** ("When played using Smuggle:
  Attack with attached unit") is **done** (2026-06-17) — a `WhenPlayedViaSmuggle`
  trigger whose `CustomEffect` reads the host id from
  `event_ctx["attached_to_id"]` (threaded by `_attach_upgrade`) and calls
  `push_granted_attack(attacker_id=host)`, the attacker-pinned variant of the
  group-09 granted-attack seam (see the group-09 note). **Armed to the Teeth
  SHD_175** ("attached unit gains On Attack: …") is now done too — the
  upgrade-grants-host-a-triggered-ability primitive (`GrantedAbility`); see the
  engine-primitive note in the Phase 7 section.

**Piloting (unit-plays-as-pilot keyword, boba-fett:01).** Piloting allows a Unit
card to be played as a Pilot "upgrade" onto a friendly Vehicle unit for a bracketed
cost. The cost clause lives in the card's `epic_action` field (NOT `text`). Seam:
- **`Unit.epic_action: Optional[str]`** — new optional field on the `Unit` dataclass
  holding the Piloting cost clause (e.g. `"Piloting [2 resources Aggression
  Villainy]"`). Added to `models.py`; `repository._hydrate` populates it from the DB
  row. Without this field `_piloting_cost` always returned `None` and no
  `PilotPlay` was ever enumerated.
- **`keywords.parse_piloting_cost(text)`** — parses `"Piloting [N resources
  <aspects>]"` from the `epic_action` field into `(base_cost, aspects_tuple)`.
  Reads from `epic_action`, never `text`.
- **`actions.PilotPlay(pilot_id, vehicle_id)`** — new ACTION-phase action enumerated
  by `_enumerate_pilot_plays`. Attaches the pilot Unit onto the Vehicle unit as an
  upgrade; fires `UpgradePlayed` with `via_pilot=True` in `event_ctx`. Pays cost via
  `_pay_play_cost` (credit-spend supported). Does NOT fire the pilot's WhenPlayed
  (it enters as an upgrade, not a unit in play).
- **`_piloting_cost(state, ci, ps)`** — effective cost = base + aspect penalty vs
  base/leader aspects. Returns `None` if no Piloting clause in `ci.card_def.epic_action`.
- **`_eligible_pilot_targets(state, ps)`** — friendly Vehicle units via
  `has_trait(state, ci, "Vehicle")`.
- `compute_power`/`compute_hp` already read `upgrade_power`/`upgrade_hp` from the
  Unit's card def — no change needed; pilots contribute stats automatically.
- **GOTCHA:** `_enumerate_pilot_plays` gates on `isinstance(ci.card_def, Unit)`.
  Synthetic tests must use real `Unit` dataclass instances (not mock classes) or the
  isinstance check silently excludes them and no `PilotPlay` is enumerated.
- **Tests:** `tests/test_piloting.py` — `TestParsePilotingCost` (3 parser unit
  tests), `TestPilotPlayMechanic` (7 framework tests: offered/not-offered conditions,
  attach, stat contribution, cost, alongside PlayCard), `TestDengar` / `TestIG88` /
  `TestBossk` / `TestBobaFettJTL` (2–3 per card, DB cards).
- **DEFERRED:** "Attached unit gains: …" residual text on all 4 JTL bounty-hunter
  Piloting cards (Dengar JTL_139, IG-88 JTL_141, Bossk JTL_187, Boba Fett JTL_189)
  is deferred to later ability groups. The focused tests PASS (Piloting mechanic
  works); the cards do not count as "playable" until their residual text is
  registered.

**Group `boba-fett:01` — Direct damage & removal (2026-07-02).** Seven cards; six
implemented, **JTL_9 Boba Fett ESCALATED**. One new self-contained decision kind
for indirect damage, one small select-damage decision kind, one new observer
trigger, one scaling count, and a fourth keyword-sanitiser rule — none touching
core resolution or the trigger/decision machinery destructively; no escape-hatch
on any implemented card. Tests: `tests/test_jtl_cards.py`.
- **New `assign_indirect_damage` decision kind + `_apply_indirect_damage` shield
  bypass — the indirect-damage primitive.** "Deal N indirect damage to a player.
  (That player assigns N unpreventable damage among their base and units.)" is a
  new self-contained decision (`actions.push_assign_indirect_damage` +
  `AssignIndirectDamage`): the RECEIVING player (the opponent of the source's
  controller) picks ONE of their base/units to absorb all N points, applied by the
  new `resolver._apply_indirect_damage` which adds directly to `ci.damage`
  **bypassing shields** (indirect damage is unpreventable) — unlike the normal
  `_deal_damage_with_shield`. A base is always a legal target so the mandatory
  decision never has an empty action set (no confirm step, unlike
  opponent_chooses_target SHD_246). Damage is dealt **after** the decision pops
  (the push_distribute_damage "pop, then deal" gotcha) so a WhenDefeated trigger
  lands on a clean stack. **First Order Stormtrooper JTL_132** = two mandatory
  triggers (`OnAttack` + `WhenDefeated`), each a thin no-target `CustomEffect`
  adapter onto `push_assign_indirect_damage(1)`. Registered in
  `invariants._KNOWN_DECISION_KINDS`, `web/session.py` (`_PROMPTS`), and
  `HeuristicBot` (`_choose_assign_indirect_damage`: dump on the highest-remaining-HP
  target — the base — never letting a unit die when a safer sink exists).
- **New `WhenIndirectDamageDealtToUnit` observer trigger.** **Allegiant General
  Pryde JTL_133** — "When indirect damage is dealt to a unit: You may defeat a
  non-unique upgrade on it. On Attack: If you have the initiative, deal 2 indirect
  damage to a player." The first is a board-wide **observer** trigger (registry +
  a `_trigger_matches` arm keyed off `event_ctx["indirect_damage_unit_id"]`, fired
  by `_resolve_assign_indirect_damage` after the damage lands when the target was a
  unit — mirroring the `attack_defeated_unit`/`dealt_combat_damage_to_base`
  event-flag pattern, `event=None`); optional, its `CustomEffect` reads the damaged
  unit from event_ctx and defeats the first non-unique (non-token) upgrade on it
  (a documented simplification — the player still chooses *whether* via the
  optional trigger; choosing *which* among several non-unique upgrades is a rare,
  unmodelled corner). The On Attack is gated by `CONTROLLER_HAS_INITIATIVE` (the
  condition gates trigger collection) and pushes `assign_indirect_damage(2)`.
- **Dengar JTL_139** (Piloting — the keyword layer, already implemented) — its only
  ability text is a Pilot grant, "Attached unit gains: 'On Attack: Deal 2 indirect
  damage to a player. If this unit is an Underworld unit, deal 3 instead.'" A
  `GrantedAbility` wrapping an `OnAttack` that resolves from the HOST (the Armed to
  the Teeth SHD_175 pattern); the `CustomEffect` reads the host's effective traits
  (`traits.has_trait`, so a granted Underworld counts) to pick 2 vs 3. Played as a
  normal unit he is a vanilla 5/4 (the granted ability confers nothing to itself).
- **New `select_damage` decision kind.** **IG-2000 JTL_140** (Overwhelm — keyword
  layer) — "When Played: Deal 1 damage to each of up to 3 units." A new
  self-contained decision (`actions.push_select_damage` + `SelectDamageTarget` /
  `FinishSelectDamage`, the Medal Ceremony SOR_245 select-up-to-N shape but dealing
  damage instead of tokens): the controller picks distinct units one at a time
  (`controller="any"` mirrors the text), recorded and then dealt 1 each once the
  selection finishes ("pop, then deal"). A thin `WhenPlayed` `CustomEffect` adapter.
  Registered in `invariants._KNOWN_DECISION_KINDS`, `web/session.py`, and
  `HeuristicBot` (`_choose_select_damage`: aim only at enemy units, preferring the
  ones 1 damage finishes off, then finish).
- **New `DealDamageEqualTo` count `target_remaining_hp_minus_1`.** **No
  Disintegrations JTL_144** (Event) — "Deal damage to a non-leader unit equal to 1
  less than its remaining HP." A plain `EventAbility([DealDamageEqualTo(target=
  non-leader unit, count="target_remaining_hp_minus_1")])` (`max(0, compute_hp −
  damage − 1)`), so a unit is always left at ≥1 HP (a unit already at 1 remaining
  takes 0). Purely a new arm in `resolver._scaling_magnitude`.
- **Fourth keyword-sanitiser rule — Grit/Raid equivalence.** **Fifth Brother
  SOR_131** — "This unit gains Raid 1 for each damage on him. (+1/+0 while
  attacking for each damage on him.)" is exactly the Grit keyword (damage total
  added to power). Modelled as an *unconditional* `ConstantAbility(SELF,
  KeywordGrant("Grit"))` read by `compute_power`'s existing Grit path; the new 4th
  `keyword_sanitizer` rule strips his DB-tagged printed "Raid" when a card carries
  an unconditional `ConstantAbility(SELF, KeywordGrant("Grit"))` (distinct from the
  conditional-self-grant rule 2 — here the ability is unconditional and the keyword
  *name* differs). His On Attack ("You may deal 1 to this unit and 1 to another
  ground unit") is a single **optional** `CustomEffect` whose target is another
  ground unit (any controller, `not_self`), bundling both damages so it auto-declines
  when no other ground unit exists; the self-damage feeds his own Grit.
- **JTL_9 Boba Fett — ESCALATED (flagged, NOT registered).** The leader depends on
  **two** framework-level primitives: (1) **deploy-leader-as-upgrade** ("Deploy
  this leader as an upgrade on a friendly Vehicle unit" — its Epic Action's second
  option, and its "When deployed as an upgrade: deal up to 4 divided" ability),
  which touches the Epic-Action/deploy machinery (the `WhenDeployed.via_pilot_leader`
  field is pre-added, additive, awaiting this session); and (2) a **"when you deal
  non-combat damage" observer trigger** ("When you deal non-combat damage: you may
  exhaust this leader → deal 1 indirect"), which would instrument the damage
  chokepoint to flag non-combat damage. Both are STOP-and-defer per the escalation
  rule. Left as a genuine gap (no escape-hatch stub) — the group is **6/7** and the
  deck cannot graduate until a dedicated framework session lands the leader-as-pilot
  deploy primitive.
- Group readiness: **6/7** (JTL_9 escalated); deck `boba-fett` advances by 6 cards.

**Group `boba-fett:02` — Direct damage & removal (2026-07-02).** Seven cards, all
implemented — two small additive engine seams plus a reuse of the boba-fett:01
indirect-damage primitive; none touch core resolution or the trigger/decision
machinery destructively; no escape-hatch on any card. Tests:
`tests/test_jtl_cards.py::Test{EliteP38Starfighter,ZygerrianStarhopper,Bossk,
BobaFettJTL189,ElectromagneticPulse,TIEBomber,FettsFirespray}`.
- **New `WhenPlayed.as_upgrade` flag** (registry + the `_trigger_matches`
  WhenPlayed arm) — narrows a Piloting unit's "When played as an upgrade:" trigger
  to the **Pilot-upgrade play path only** (the `UpgradePlayed`/`via_pilot` event),
  NOT when the same card is played as a normal unit (`UnitEntersPlay`). The default
  (False) fires on either play path (unchanged). **Boba Fett JTL_189** (Shielded,
  Piloting — keyword layer) is an optional `WhenPlayed(as_upgrade=True)` whose one
  `CustomEffect.target` (any unit) deals 1, or 2 if the attached host is a
  Transport (read from `event_ctx["attached_to_id"]` — the Zeb Orellios LAW_45
  conditional-magnitude pattern). Collected via the existing UpgradePlayed
  freshly-played-upgrade scan (which already allows WhenPlayed).
- **`CONTROLLER_CONTROLS_NAMED` now also scans attached upgrades** (registry) so
  "control Boba Fett as a unit, **upgrade**, or leader" counts a pilot /
  leader-as-upgrade Boba. **Fett's Firespray JTL_240** = two mandatory triggers
  (`WhenPlayed` + `OnAttack`), each a no-target `CustomEffect` that evaluates
  `CONTROLLER_CONTROLS_NAMED("Boba Fett")` for the magnitude (1 vs 2) and pushes
  `assign_indirect_damage` (the boba-fett:01 primitive). "Fett's Firespray" does
  not contain "Boba Fett", so no self-trigger.
- **New `droid_or_vehicle` target predicate** (`resolver._spec_matches_ci`) — a
  trait OR (Droid OR Vehicle) a single `traits` tuple (which requires ALL) cannot
  express; reads effective traits. **Electromagnetic Pulse JTL_230** (Event) is a
  plain `EventAbility` whose one `CustomEffect.target` (predicate `droid_or_vehicle`)
  deals 2 to the chosen unit AND exhausts the SAME unit (one CustomEffect so it is
  one target, not two prompts).
- **Bossk JTL_187** (Piloting — keyword layer) — "On Attack: Exhaust the defender
  and deal 1 damage to it (if it's a unit)" is `[ExhaustCard(fixed=DEFENDER),
  DealDamage(1, fixed=DEFENDER)]` (`fixed=DEFENDER` → nothing on a base attack, so
  "(if it's a unit)" falls out). Registered TWICE: a plain `OnAttack` (fires when
  Bossk is a unit) AND a `GrantedAbility` wrapping the same OnAttack (the Vambrace
  Grappleshot SHD_74 pattern — fires from the host when Bossk is a Pilot upgrade);
  exactly one is collected per play mode.
- **Zygerrian Starhopper JTL_183** = `WhenDefeated → push_assign_indirect_damage(2)`;
  **TIE Bomber JTL_237** = `OnAttack → push_assign_indirect_damage(3)` (the
  "defending player" is the opponent in 2-player — exactly whom the primitive
  addresses). **Elite P-38 Starfighter TWI_181** (registered in the TWI module) =
  two optional triggers (`WhenPlayed` + `WhenDefeated`), each `DealDamage(1, any
  unit)` (auto-declines with no unit).
- Group readiness: **7/7**; deck `boba-fett` now **41/52** (next unblocked ability
  group `boba-fett:03`; `boba-fett:01` remains 6/7 pending the escalated JTL_9
  deploy-leader-as-upgrade framework session — **now DONE, see the note below**).

**Engine primitives added (group `boba-fett:01` escalation) — deploy-leader-as-
upgrade + non-combat-damage observer (Boba Fett JTL_9, 2026-07-02).** The dedicated
framework session the planner flagged; `boba-fett:01` is now **7/7**, deck
**42/52**. Two additive primitives, neither rewriting core resolution or the
trigger/decision machinery destructively; no escape-hatch. Full fast suite (1275
pass) + a clean 300-game determinism soak on the non-JTL decks. Tests:
`tests/test_jtl_cards.py::TestBobaFettJTL9`.
- **deploy-leader-as-upgrade.** New `actions.DeployLeaderAsUpgrade(vehicle_target_id)`
  action — the Epic Action's second option ("Deploy this leader as an upgrade on a
  friendly Vehicle unit without a Pilot on it"). Enumerated in `legal_actions`
  alongside `DeployLeader` when `_leader_can_deploy_as_upgrade` (the leader's
  `epic_action` text mentions "as an upgrade" — GENERAL to all 10 JTL Piloting-
  leaders, so it is forward-compatible: each just deploys as a stat pilot upgrade
  until its own deck registers any "when deployed" ability) AND an eligible host
  exists (`_eligible_leader_upgrade_targets` = a friendly Vehicle with no Pilot,
  via `_vehicle_has_pilot`). It attaches the leader as a Pilot upgrade (like
  `_attach_pilot`), marks it `deployed`/`epic_action_spent`, and fires
  `LeaderDeployed` with `event_ctx={"via_pilot_leader": True}`. **The `Leader`
  model gained `upgrade_power`/`upgrade_hp`** (populated in `repository._hydrate`;
  Boba is +4/+4) so a leader-as-upgrade contributes stats to its host exactly like
  a pilot Unit (`compute_power`/`compute_hp` already read `getattr(card_def,
  "upgrade_power", 0)`), making the host a leader unit. `resolver._collect_triggers`
  gained a scan of each in-play unit's `attached_upgrades` for a **deployed Leader
  upgrade's** own plain `TriggerAbility`s (source = the leader-upgrade), so a
  leader-as-upgrade's triggers fire (a leader was never an upgrade before). The
  pre-added `WhenDeployed(via_pilot_leader=True)` field now matches only the
  pilot-leader-deploy path (a normal deploy does not set the flag → the "when
  deployed as an upgrade: deal up to 4 divided" does not fire). "Deal **up to** 4
  divided among any number of units" = a new **`up_to` flag on
  `push_distribute_damage`** + a `FinishDamageDistribution` action (pool mode may
  stop early, assigning 0..4; overkill/any-controller targets fall out of the
  existing pool machinery). `_end_regroup` now also readies attached upgrades so an
  exhausted-by-its-own-ability leader-upgrade re-readies each round.
- **"when you deal non-combat damage" observer.** A new `WhenDealNonCombatDamage`
  trigger + a `GameMemory.noncombat_damage_dealers` ledger (serialised; drained
  every settle, so empty between actions). The two non-combat damage sinks
  `resolver._apply_deal_damage` / `_apply_indirect_damage` record the **dealer's**
  player id — obtained via a resolver `_noncombat_dealer` context-manager stack
  pushed around `execute_effect`'s `CustomEffect` arm (covering CustomEffect fns
  that deal synchronously) plus an explicit `dealer_id=` from the `DealDamage` /
  `DealDamageEqualTo` arms and the indirect / distribute-finish / select_damage
  "pop-then-deal" resolvers. **Combat damage flows through `_deal_damage_with_shield`
  directly and is never recorded**, so it never fires this trigger (matching the
  card's rules box: "non-combat damage is any damage dealt outside the deal-combat-
  damage step"). The ledger is drained at the `apply()` settle-point
  (`_fire_noncombat_damage_observers`, only while the stack is clear), firing the
  observer with `event_ctx["noncombat_damage_dealer_id"]` — matched only when it
  equals the source's controller ("when YOU deal"). **Purely additive for every
  existing deck**: with no `WhenDealNonCombatDamage` card in play the drain's
  `fire_triggered_abilities` finds nothing (event=None matches only this trigger),
  so behaviour and RNG are unchanged (300-game determinism soak clean). JTL_9's
  ability is an **optional** `WhenDealNonCombatDamage` gated by `SOURCE_READY`
  (bounding the self-chain — its own 1 indirect is itself non-combat damage, but by
  then Boba is exhausted so the observer is no longer collected), neither
  deployed_only nor undeployed_only so it works in ALL of Boba's forms (undeployed
  leader / deployed unit / deployed-as-upgrade). Its one `CustomEffect` exhausts
  Boba and pushes `assign_indirect_damage(1)` (bound so "If you do" holds). Bot:
  `_choose_distribute_damage` now filters `AssignDamage` to enemy units and honours
  `FinishDamageDistribution`; `DeployLeaderAsUpgrade` is scored ~`DeployLeader`. Web:
  `session.label_for` names the host; `FinishDamageDistribution` in the bot's
  `_SAFE_DEFAULT_ORDER`. No new decision kind (reuses `distribute_damage` /
  `assign_indirect_damage` / `trigger_option`), no `invariants` change.

**Group `boba-fett:03` — Combat tricks, buffs & tempo (2026-07-03).** Three cards,
all implemented — three small additive engine seams, none touching core resolution
or the trigger/decision machinery; no escape-hatch on any card. Tests:
`tests/test_jtl_cards.py::Test{IG88,FettsFirespray,NoGoodToMeDead}`.
- **New `ENEMY_HAS_DAMAGED_UNIT` condition atom + attached-upgrade SELF-`StatBonus`
  scan.** **IG-88 JTL_141** (Piloting — keyword layer) "While an enemy unit is
  damaged, this unit gets +3/+0" + the Pilot residual "Attached unit gains: '<the
  same>'" is ONE self-targeted conditional `ConstantAbility(target=SELF,
  StatBonus(3,0), condition=ENEMY_HAS_DAMAGED_UNIT)` that models both forms: as a
  **unit** the existing arena constant scan (`_constant_ability_power_bonus`) buffs
  IG-88 itself; as a **Pilot upgrade** the same spec is read by the new
  `_upgrade_self_stat_bonus` scan (a unit's `attached_upgrades` for a
  `ConstantAbility(target=SELF)` with a `StatBonus`, condition evaluated against the
  host) and buffs the host — the keyword layer's Grievous's Wheel Bike TWI_236
  upgrade-`KeywordGrant` scan, mirrored for a stat buff (the arena scan never sees
  an upgrade). The condition winks the +3/+0 on/off passively.
- **New `non_unique` target predicate** (`resolver._spec_matches_ci`, inverse of the
  card's `is_unique`). **Fett's Firespray SOR_184** = a `WhenPlayed` no-target
  `CustomEffect` that readies the unit if the controller controls Boba Fett OR Jango
  Fett — the OR checked via two `CONTROLLER_CONTROLS_NAMED` evaluations (a single
  atom cannot express the OR; readying = clearing the default enters-exhausted flag)
  — plus an `ActivatedAbility(costs=[PayResources(2)], effects=[ExhaustCard(any
  non_unique unit)])` (no exhaust-self cost; ungated, so it fizzles silently with no
  eligible target — the Grogu SHD_196 simplification).
- **New `CardInstance.cannot_ready_this_round` flag** (serialised) for **No Good to
  Me Dead SOR_186** (Event) "Exhaust a unit. That unit can't ready this round
  (including during the regroup phase)". A plain `EventAbility` whose one
  `CustomEffect.target` (any unit) exhausts the chosen unit AND sets the flag
  (bundled so a single target is chosen). The flag is honoured at the two ready
  sites: `_end_regroup` skips the flagged unit's ready step for the current regroup
  then clears it (so the unit readies normally the *next* round — it stays tapped an
  extra full turn, the card's point), and the `ReadyCard` resolver arm is a no-op on
  it. Cleared defensively on fresh entry (`_put_unit_in_play`) and return-to-hand
  (`_apply_return_to_hand`) so a stale flag can't survive a leave-and-replay. Purely
  a new serialisable instance field + reads at existing ready sites (the allowed
  small-primitive path, the `granted_bounties`/`defeat_at_regroup` shape).
- Group readiness: **3/3**; deck `boba-fett` now **47/52** (1 group left; next group
  `boba-fett:04` — Miscellaneous abilities).

**Group `boba-fett:04` — Miscellaneous abilities (2026-07-03).** Two cards, both
implemented — two new passive-marker specs (read at existing seams), none touching
core resolution or the trigger/decision machinery; no escape-hatch on either card.
Tests: `tests/test_jtl_cards.py::Test{HuntingAggressor,HoundsTooth}`. **This completes
the deck — `boba-fett` is now 52/52 (all 4 groups), eligible for
`verify_encoding.py boba-fett --graduate`.**
- **New `registry.IndirectDamageBonus(amount)` passive marker.** **Hunting Aggressor
  JTL_165** ("Indirect damage you deal to opponents is increased by 1") is a bare
  `IndirectDamageBonus(1)` read at the single indirect-damage chokepoint
  (`actions.push_assign_indirect_damage`, the boba-fett:01 primitive): the pushed
  `amount` is raised by the sum of every `IndirectDamageBonus` the source's
  controller has in play (new `_indirect_damage_bonus` scan; multiple copies stack).
  The bonus applies only when the base amount is > 0 (a 0-point deal stays 0, so a
  marker can never conjure damage from nothing) and only for the *controller's* own
  indirect (the scan is over the source-controller's arenas, so an enemy's copy does
  not boost you). Because every indirect source routes through this one helper
  (First Order Stormtrooper JTL_132, TIE Bomber JTL_237, Dengar's pilot grant, …),
  the static "+1" covers them all with no per-card wiring. Purely a read at an
  existing seam (the AttackRestriction/EntersPlayReady passive-marker pattern).
- **New `registry.ConditionalFirstStrike(defender_spec)` passive marker + the
  `not_played_this_phase` target predicate.** **Hound's Tooth JTL_185** ("While
  attacking an exhausted unit that didn't enter play this phase, this unit deals
  combat damage before the defender") is conditional First Strike: unconditional
  First Strike stays the keyword layer (Incinerator Trooper SHD_234), but this
  depends on the *defender*, which a `ConstantAbility(KeywordGrant)` condition (about
  the source/board) cannot express. The marker carries a `defender_spec` TargetSpec
  (`controller="enemy", kind="unit", predicates=("exhausted",
  "not_played_this_phase")`); the combat step reads it via the new
  `actions._attacker_has_first_strike(s, attacker, defender)` helper (replacing the
  bare `has_keyword(FIRST_STRIKE)` at the unit-combat step — combat unchanged for
  every other attacker), which returns True when the current defender satisfies the
  spec (via `resolver._spec_matches_ci`). `not_played_this_phase` is the new inverse
  of the `played_this_phase` predicate (both backed by
  `game_memory.units_played_this_phase`). Purely a read at the combat step (the
  AttackRestriction passive-marker pattern) + one predicate arm. Both new markers
  added to `soak._analyse_ability_coverage`'s passive-marker tuple so a
  marker-only card is not a false zero-fire.
- Group readiness: **2/2**; deck `boba-fett` now **52/52 — fully encoded** (all 4
  groups complete; eligible for `verify_encoding.py boba-fett --graduate`).

**Group `han-solo:03` — Card advantage & disruption (2026-07-04).** The **first
JTL two-player-starter Han Solo deck** group after :01/:02; four cards, all
implemented — one new `peek_top` mode, the rest compose from existing seams. None
touch core resolution or the trigger/decision machinery destructively; no
escape-hatch on any card. Tests:
`tests/test_twi_cards.py::TestWolfPackEscort`,
`tests/test_sor_cards.py::TestEzraBridger`,
`tests/test_jtl_cards.py::TestShuttleTydirium`, `::TestBoShek`.
- **New `peek_top` mode `"may_play_discard"` + `PlayTopCard`/`DiscardTopCard`
  actions (Ezra Bridger SOR_192).** "When this unit completes an attack: Look at
  the top card of your deck. You may play it, discard it, or leave it on top."
  Reuses the existing `peek_top` decision kind (R2-D2/C-3PO), so **no new decision
  kind** — just a third mode and two actions. The `legal_actions` `peek_top` branch
  gained a `may_play_discard` arm offering `KeepTopCard` (leave on top, reused),
  `DiscardTopCard` (mill the top card to discard), and `PlayTopCard` (play the top
  card for its **full** cost — enumerated one per legal host for an upgrade, gated
  by `_affordable_with_credits`). `PlayTopCard.apply` pops the decision FIRST (the
  "pop, then act" gotcha), then plays the card through the canonical PlayCard logic
  (pay `_play_cost`, consume any pending discount, track Villainy, route to
  `_put_unit_in_play`/`_attach_upgrade`/`_resolve_event_ability`, fire `CardPlayed`
  + observers) so the played card's own keyword/When Played triggers fire.
  **LIMITATION (documented):** Exploit is not special-cased on this path — an
  Exploit unit played via Ezra pays full cost with no sacrifice option (strictly
  safe for the player). Ezra is a mandatory `WhenAttackEnds` (surviving attacker —
  the Pong Krell LOF_38 seam) whose one inline `CustomEffect` calls
  `push_peek_top(mode="may_play_discard")`; an empty deck is a clean no-op. Web
  prompt + `label_for` (names the peeked card); `HeuristicBot._choose_peek_top`
  already returns the always-present `KeepTopCard` (safe — never buries/burns a
  card it cannot evaluate), so no bot change.
- **Wolf Pack Escort TWI_191** — an optional `WhenPlayed` `ReturnToHand(TargetSpec(
  controller="friendly", kind="unit", predicates=("non_leader","non_vehicle")))`
  ("return a friendly non-leader, non-Vehicle unit to hand"). Escort is itself a
  Vehicle, so it never self-bounces; auto-declines with no eligible unit.
- **Shuttle Tydirium JTL_200** — a plain `OnAttack` whose one inline `CustomEffect`
  mills the top card (Kuiil SHD_41 pattern) and, only if its cost is **odd**, pushes
  the "up to 1" Experience `push_select_token(predicates=["not_self"])` ("you may
  give an Experience token to another unit"; `controller="any"`, recipient benefits
  so never an enemy). No engine change.
- **BoShek JTL_215** (Piloting — keyword layer) — the only ability is "When played
  as an upgrade: Discard 2 cards from your deck. Return each of those cards with an
  odd cost to your hand." A `WhenPlayed(as_upgrade=True)` (the Boba Fett JTL_189
  Pilot-play-path flag — fires only when played as a Pilot upgrade, never as a
  normal unit) whose one inline `CustomEffect` mills the top 2 and returns each
  odd-cost one to hand (mandatory, no choice). No engine change.
- Group readiness: **4/4**; deck `han-solo` now **27/52** (next group
  `han-solo:04`).

**Group `han-solo:04` — Combat tricks, buffs & tempo (2026-07-04).** Seven cards
(the deck leader Han Solo JTL_17 + TWI_110 Huyang, registered in the TWI module);
all implemented — four small additive engine seams, none touching core resolution
or the trigger/decision machinery destructively; no escape-hatch on any card.
Tests: `tests/test_jtl_cards.py::Test{HanSoloJTL17,NienNunb,BlueLeader,
LeiaOrganaJTL97,TandemAssault,ItsATrap}` + `tests/test_twi_cards.py::TestHuyang`.
- **Four new `push_granted_attack` fields** (all serialised in the existing
  `granted_attack` context — **no** new decision kind, just filters/gates on an
  existing decision): **`attacker_arena`** ("ground"/"space" — restricts the
  offered attacker to that arena), **`attacker_pilot_related`** ("a Pilot unit or a
  unit with a Pilot on it" — via the new `_is_pilot_related` helper: Pilot trait or
  a Pilot upgrade attached), **`bonus_if_odd_cost_diff_from`** (the revealed card's
  cost — the this-attack stat bonus applies only when BOTH it and the chosen
  attacker's printed cost are odd AND differ), and **`grant_keywords` entries may
  be `(name, value)` pairs** to grant a *numeric* keyword for the attack (Leia's
  Restore 1; a JSON round-trip turns the tuple into a list, handled on read).
- **Han Solo JTL_17** (Leader, Pilot/Rebel) — undeployed Action [Exhaust]: "Reveal
  the top card of your deck, then attack with a unit.  If the revealed card and
  that unit have different odd costs, +1/+0" is a thin `CustomEffect` adapter (the
  Moff Gideon SHD_7 undeployed-Action pattern) reading the top card's cost and
  calling `push_granted_attack(power_bonus=1, bonus_if_odd_cost_diff_from=<cost>)`,
  gated by `CONTROLLER_HAS_READY_UNIT_COST_MAX` (param None = "any ready unit") so
  the Exhaust is not a no-op.  DEVIATION: "reveal" is modelled by reading the top
  card's cost (it stays face-down) rather than a public reveal — cosmetic.  Its
  "When deployed as an upgrade: For each friendly unit or upgrade with an odd cost,
  ready a resource" is a `WhenDeployed(via_pilot_leader=True)` (the Boba Fett JTL_9
  deploy-leader-as-upgrade primitive) whose inline `CustomEffect` counts odd-cost
  friendly units + upgrades (a Leader-as-upgrade has no printed cost, so it does
  not count) and readies that many resources.  The Epic Action deploy (5+
  resources, normally or as an upgrade) is the standard
  `deploy_threshold`/`DeployLeaderAsUpgrade` machinery — no registration.
- **New scaling `StatBonus.count` field (Nien Nunb JTL_93).** "+1/+0 for each other
  friendly Pilot unit and upgrade" is a persistent buff whose magnitude scales with
  board state, which a flat `StatBonus` cannot express.  New optional
  `StatBonus.count` names a scaling source (the `DealDamageEqualTo` pattern, but for
  a constant stat buff): `power`/`hp` become the per-unit amount, scaled by
  `_stat_bonus_count`.  The only count today is `"other_friendly_pilots"` = friendly
  Pilot units + Pilot upgrades minus one for the source (Nien Nunb is always exactly
  one friendly Pilot card).  Wired into all three StatBonus read sites via one
  `_stat_bonus_amount` helper (`_constant_ability_power_bonus`,
  `_constant_ability_hp_bonus`, the attached-upgrade `_upgrade_self_stat_bonus`
  scan) — so a single self-targeted `ConstantAbility(StatBonus(1,0,
  count="other_friendly_pilots"))` models BOTH forms of the card: the arena scan
  buffs Nien Nunb as a unit, the upgrade-self scan buffs the host when Nien is a
  Pilot upgrade (the IG-88 JTL_141 dual-form pattern).  A flat StatBonus
  (`count=None`) is byte-identical to before.
- **`permanent` modifier ends when its source leaves play (Huyang TWI_110).** "When
  Played: Choose another friendly unit. While this unit is in play, the chosen unit
  gets +2/+2" attaches a buff to a *runtime-chosen* instance (so not a
  `ConstantAbility`, whose target is a static filter) that must end when Huyang
  leaves play.  Modelled as a `duration="permanent"` stats modifier sourced by
  Huyang, implementing the documented `permanent` semantic ("lasts until source
  leaves play") that was defined but unused: `compute_power`/`compute_hp` now skip a
  `permanent` stats modifier whose source is not in play (new
  `_modifier_source_in_play` guard — an arena unit or attached upgrade), and
  `_defeat_unit` / `_apply_return_to_hand` drop `permanent` modifiers the leaving
  unit sourced.  Purely additive — no code created `permanent` modifiers before, so
  every other card is unaffected.
- **Blue Leader JTL_96** (Ambush — keyword layer) — an **optional** `WhenPlayed`
  (the "you may") gated by `CONTROLLER_N_PLUS_READY_RESOURCES(2)` whose inline
  `CustomEffect` pays 2 resources, relocates the unit from the space arena to the
  ground arena, and gives it 2 Experience tokens.  **Leia Organa JTL_97** (Restore 1
  — keyword layer) — a `WhenPlayed` `CustomEffect` adapter onto
  `push_granted_attack(power_bonus=1, optional=True, attacker_pilot_related=True,
  grant_keywords=[("Restore", 1)])` ("attack with a Pilot unit / a unit with a Pilot
  on it; +1/+0 and gains Restore 1 for this attack").  **Tandem Assault JTL_124**
  (Event) — a `CustomEffect` that, only when a ready space unit exists, pushes two
  granted attacks (the Outflank TWI_123 double-grant): a ground attack (+2/+0,
  `attacker_arena="ground"`) that resolves 2nd and a space attack
  (`attacker_arena="space"`) that resolves 1st via LIFO — so the ground attack is
  contingent on the space attack ("If you do").  **It's a Trap JTL_209** (Event) —
  a plain `EventAbility` whose non-targeted inline `CustomEffect` readies each
  friendly space unit when the opponent controls more space units.
- Group readiness: **7/7**; deck `han-solo` now **37/52** (next group
  `han-solo:05`).

**Group `han-solo:05` — Combat tricks, buffs & tempo (2026-07-04).** Three JTL
cards, all implemented — four small additive engine seams, none touching core
resolution or the trigger/decision machinery destructively; no escape-hatch on any
card. Tests: `tests/test_jtl_cards.py::Test{TheMandalorian,DeathSpaceSkirmisher,
MillenniumFalcon}`.
- **New `WhenPlayed.as_unit` flag + `same_arena_as_host` target predicate (The
  Mandalorian JTL_210).** A Piloting unit (played as a 5/6 unit OR a Pilot upgrade)
  with two mode-keyed triggers. `WhenPlayed(as_unit=True)` (registry + the resolver
  matcher arm — the mirror of the Boba Fett JTL_189 `as_upgrade` flag; fires ONLY on
  the `UnitEntersPlay` path, never the pilot-upgrade path) drives "When played as a
  unit: Exhaust up to 2 ground units" via a thin `CustomEffect` adapter onto
  `push_exhaust_combined_cost` — which gained an optional **`arena`** filter (thread
  into its `_exhaust_combined_targets` spec) — with `max_units=2, budget=None,
  arena="ground"` (the Qui-Gon's Lightsaber LOF_201 "exhaust any number" seam, capped
  and arena-restricted; "up to" includes 0 via the always-offered
  `FinishExhaustCombined`). `WhenPlayed(as_upgrade=True)` drives "When played as an
  upgrade: Exhaust an enemy unit in this arena" — a mandatory `ExhaustCard` on an
  enemy unit filtered by the **new `same_arena_as_host` predicate**
  (`resolver._spec_matches_ci`: candidate's arena must equal the arena of the upgrade's
  host, read from `event_ctx["attached_to_id"]`, which survives the decision's
  `_TRANSIENT` filter — the capture SHD_251 threading). Piloting is the keyword layer.
- **New `Condition.CONTROLLER_HAS_OTHER_SPACE_UNIT` atom (Death Space Skirmisher
  JTL_217).** "When Played: If you control another space unit, you may exhaust a
  unit" is an **optional** `WhenPlayed ExhaustCard(any unit)` gated by the new
  condition (another unit in the controller's space arena, excluding the source —
  the Skirmisher is itself a space unit; the condition gates trigger collection, so
  the "you may exhaust" is offered only when a second space unit is present).
  `controller="any"` — the controller points the exhaust at an enemy.
- **New `StatBonus.count="pilots_on_self"` + `AdditionalPilotSlots` passive marker
  (Millennium Falcon JTL_249).** Two passive clauses. "+1/+0 for each Pilot on it" is
  a self-targeted scaling `ConstantAbility(StatBonus(1,0, count="pilots_on_self"))`
  (a new `_stat_bonus_count` arm counting Pilot upgrades — or a leader-as-upgrade —
  attached to the source; the Nien Nunb JTL_93 scaling-StatBonus pattern, read
  passively by `compute_power`). "You may play or deploy 1 additional Pilot on this
  unit" is a new `AdditionalPilotSlots(1)` marker read at the pilot-attach seam via
  the new `_pilot_limit`/`_pilot_count` helpers, raising the Falcon's Pilot cap to 2.
  **DEVIATION (documented on the marker):** the engine does not enforce the standard
  one-Pilot-per-Vehicle limit on the normal `PilotPlay` path (`_eligible_pilot_targets`
  returns every Vehicle — a pre-existing simplification), so the marker's functional
  effect is to relax the *leader-deploy-as-upgrade* cap (`_eligible_leader_upgrade_targets`,
  the one place a Pilot cap is checked); the "play an additional Pilot" case is
  already free. Added to `soak.py`'s passive-marker tuple so a marker-only card is
  not a false zero-fire.
- Group readiness: **3/3**; deck `han-solo` now **40/52** (next group
  `han-solo:06`).

**Group `han-solo:06` — Miscellaneous abilities (2026-07-04).** Two JTL cards,
both implemented — one small additive seam plus reuse of the han-solo:05
`AdditionalPilotSlots` marker; no escape-hatch on either card. Tests:
`tests/test_jtl_cards.py::Test{Chewbacca,R2D2}`.
- **New `Protection` effect (Chewbacca JTL_103).** "This unit can't be defeated or
  returned to hand by enemy card abilities. Attached unit gains: '…'". Both clauses
  are the SAME passive protection expressed once: a self-targeted
  `ConstantAbility(effects=[Protection(from_defeat=True, from_return=True)])`. By the
  "attached unit gains X" convention the keyword layer already uses (an upgrade's
  `ConstantAbility(target=SELF, …)` confers X on its host), the one ability protects
  Chewbacca while he is a unit AND, when he is played as a Pilot upgrade, protects the
  Vehicle he pilots. Read (never routed) at the defeat/return effect seams — the
  `resolver` `DefeatUnit` / `DefeatAllUnits` / `ReturnToHand` arms consult a new
  `_target_protected(state, tid, source_ci, kind)` helper (which scans the target's
  own card def and its attached upgrades for a SELF-targeted `Protection` covering
  `kind`) and simply **skip** a protected target. Only *enemy* abilities are blocked
  (a source controlled by the target's own controller is unaffected — "by enemy card
  abilities"), and combat/damage defeat is untouched (damage never routes through the
  `DefeatUnit` effect). Piloting is the keyword layer. A `Protection` inside a
  `ConstantAbility` is already classed passive by `soak.py` (no marker-tuple change).
- **R2-D2 JTL_245 — pure reuse of `AdditionalPilotSlots` + `_pilot_limit` extension.**
  "This upgrade can be played on a friendly Vehicle unit with a Pilot on it" needs no
  code — the normal Piloting/`PilotPlay` path never enforced the "without a Pilot"
  restriction (`_eligible_pilot_targets` returns every friendly Vehicle), so R2-D2 can
  already attach to a piloted Vehicle. "Attached unit gains: 'You may play or deploy 1
  additional Pilot on this unit'" is the han-solo:05 `AdditionalPilotSlots(1)` marker;
  `_pilot_limit` now also scans a host's **attached upgrades** for the marker (not just
  the host's own card def), so a Vehicle carrying R2-D2 hosts one Pilot beyond R2-D2
  itself. Same documented DEVIATION as the Falcon: the cap is only checked on the
  leader-deploy-as-upgrade path.
- Group readiness: **2/2**; deck `han-solo` now **42/52** (next group
  `han-solo:07`, the scaling-magnitude escalation pair).

**Group `han-solo:07` — New primitive: scaling-magnitude (2026-07-04).** Two cards,
both implemented; the flagged "scaling-magnitude" primitive **already existed** —
both reuse the `DealDamageEqualTo` / `select_damage` seams, so **no new engine
primitive**. Tests: `tests/test_jtl_cards.py::Test{AdmiralAckbar,NeverTellMeTheOdds}`.
- **Admiral Ackbar SOR_97 — pure reuse.** "When Played: You may deal damage to a unit
  equal to the number of units you control in its arena" (Restore 1 = keyword layer)
  is an **optional** `WhenPlayed` with one `DealDamageEqualTo(target=any unit,
  count="source_controller_units_in_target_arena")` — the exact count Synchronized
  Strike TWI_99 (ahsoka-tano:06) already defines. `controller="any"` mirrors the
  printed "a unit"; auto-declined with no unit on board; magnitude 0 is a no-op.
- **Never Tell Me the Odds JTL_208 — escape-hatch `CustomEffect` (inline-resolve-then-
  push).** "Discard 3 cards from an opponent's deck and 3 from your deck. Deal damage
  to a unit equal to the number of cards with an odd cost discarded this way." The
  magnitude is *transient* (odd-cost cards milled this way) — no declarative count spec
  can express it, and the mill is inherently custom (there is no declarative deck-
  discard primitive; every mill is a `CustomEffect`). One no-target `CustomEffect` mills
  3 from each deck, counts odd-cost cards, then reuses the existing `select_damage`
  decision (IG-2000 JTL_140) via `push_select_damage(amount_each=count, max_targets=1)`
  — a single clean "deal N to a chosen unit" prompt through the standard damage path.
  The mandatory mill always happens (no target needed); count 0 pushes no damage. Minor
  deviation: `select_damage` is "up to 1", so the controller may decline the (nominally
  mandatory) damage. *(An earlier two-effect design — no-target mill stashing into the
  shared `event_ctx`, then a targeted `DealDamageEqualTo` reading it — was rejected: the
  resolve_effects target generator skips the no-target mill and offers the damage target
  BEFORE the mill runs, so `apply_resolve_effects` silently eats the first selection to
  advance the mill and re-prompts. The inline-then-push avoids that double-prompt.)*
- Group readiness: **2/2**; deck `han-solo` now **51/52** (only `han-solo:08`,
  Commandeer JTL_235 / control-change, remains).

**Group `han-solo:08` — New primitive: control-change (2026-07-04).** One card,
implemented; the flagged "control-change" primitive **already existed**
(`actions.change_control`, from Stolen Landspeeder SHD_161), so this is a
**composition of existing seams + one tiny delayed-flag**, not a core change.
Deck `han-solo` now **52/52 — fully encoded, eligible for `--graduate`**. Test:
`tests/test_jtl_cards.py::TestCommandeer`.
- **Commandeer JTL_235.** "Take control of a non-leader Vehicle unit that costs 6
  or less without a Pilot on it. If you do, ready it. At the start of the next
  regroup phase, return that unit to its owner's hand." A single **targeted
  `CustomEffect`** whose `TargetSpec` restricts the choice to `controller="enemy"`,
  `traits=("Vehicle",)`, `cost_max=6`, `predicates=("non_leader", "no_pilot")`. The
  fn composes three existing seams: `change_control` (control is implicit arena
  occupancy — the unit relocates to the caster's matching arena, `owner_id`
  unchanged), a plain `exhausted = False` ready, and a new delayed flag
  `return_to_owner_hand_at_regroup`.
- **Two small additive seams (mirroring existing patterns, no core-resolution/
  trigger/decision-machinery change):** (1) a `no_pilot` **predicate** in
  `resolver._spec_matches_ci` ("without a Pilot on it" = no attached upgrade with
  the Pilot trait, mirroring `actions._pilot_count`); (2) a
  `return_to_owner_hand_at_regroup` **flag** on `CardInstance` (+ its dict
  round-trip), swept in `actions._enter_regroup` **exactly like `defeat_at_regroup`**
  (Sneak Attack SOR_219) — the return routes through the existing
  `_apply_return_to_hand`, which already sends a card to its **owner's** hand
  regardless of who controls it, so a commandeered unit goes home.
- **Faithful-intent simplification:** `controller="enemy"`. The printed text is "a
  unit" (technically including a unit you already control), but taking a unit you
  control is a no-op (`change_control` no-ops → its "If you do" clause does
  nothing), so restricting to enemy units offers only the meaningful targets and
  makes control always change (ready + delayed-return always apply).

---

