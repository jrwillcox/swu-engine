# Reprint-Duplicate Sweep — Full History (archived 2026-07-16)

Verbatim archive of the 50-batch reprint-duplicate encoding sweep log that used to
live in the `reprint-duplicates` memory topic file. Moved here to keep that memory a
concise single fact. The sweep is COMPLETE. The distilled summary + reusable-primitive
index lives in `memory/project_reprint_duplicates.md`; this file is the full per-batch
record (B1-B50) with every gotcha and re-derivation. Nothing changed below.

---

---
name: project-reprint-duplicates
description: Plan to make reprint-duplicate cards playable by aliasing the registry key to an implemented twin
metadata: 
  node_type: memory
  type: project
  originSessionId: daecf3ce-4f9f-437a-8587-4efbde47c73e
---

**🏁 STAGE 4 BATCH 50 DONE 2026-07-16 — THE SWEEP IS COMPLETE. `needs_encoding
0 groups / 0 members`, `already_covered 191→192 groups / 466 members`, `--check
OK`.** The LAST group — **The Eye of Aldhani SEC_73/SECP_5** (1-cost Vigilance Event:
"At the start of the next action phase, for each enemy unit, its controller must pay
1 resource or exhaust that unit") — was a genuine **2-PRIMITIVE BALLOON** (confirmed
re-derived vs the current engine: neither half clears the group alone, like Amidala
needed combat+ability). **User chose (AskUserQuestion, terminal-tail precedent)
"Build both — finish the sweep"** so BOTH primitives landed this session (a deliberate
one-time exception to the one-primitive rule, to clear the final group).

**PRIMITIVE A — delayed action-phase-start scheduler.** The event resolves in ACTION
→ discard, so there is NO in-play host for a `PhaseStartTrigger` (which fires only at
`_enter_regroup`, `phase="regroup"`, scanning in-play cards). New serialised field
**`GameState.scheduled_action_phase_effects: list[dict]`** (state.py; to_dict/from_dict,
back-compat default `[]` — the `defeat_at_regroup`/`granted_bounties` "serialised flag
swept at a phase boundary" shape). `push_eye_of_aldhani_schedule(s, source_ci)` appends
`{"kind":"eye_of_aldhani","controller_id": caster_owner_id}` (records the CASTER's id,
not the instance — it's gone by fire time). `_fire_scheduled_action_phase_effects(s)`
drains the list (clears FIRST so nothing re-fires next round) and dispatches by kind;
called at the END of BOTH action-phase-start sites — `_regroup_rollover` (the normal
round boundary → ACTION) and `_start_action_phase`. No-op for every game with nothing
scheduled → soak/determinism unaffected.

**PRIMITIVE B — per-enemy pay-or-exhaust decision (`pay_or_exhaust` kind).** A
multi-unit sibling of `regroup_upkeep` (Millennium Falcon SOR_193), but the DECIDER is
the ENEMY (each unit's controller) and the consequence is EXHAUST, not bounce.
`_fire_eye_of_aldhani(s, caster_id)`: opponent = `players[1 - player_index(caster)]`;
snapshot the opponent's **READY** ground+space units (an already-exhausted unit's "or
exhaust" is a guaranteed no-op → skipping is faithful in outcome + avoids pointless
prompts); no push if none. Push a `pay_or_exhaust` decision, `deciding_player_id` =
opponent, ctx `{controller_id: opponent, caster_id, pending_ids: [ready enemy unit
ids]}`, `after_resolve_player_index = s.active_player_index` (restore-what-was), flip
active to the opponent. legal_actions branch `_pay_or_exhaust_actions` processes the
HEAD of `pending_ids`: **`PayToAvoidExhaust(head)`** (offered only when the decider has
a ready resource AND the head unit is still present+ready — no point protecting a
gone/exhausted unit) + **`AcceptExhaust(head)`** (ALWAYS offered → action set never
empty; on a present ready unit it exhausts it, on a gone/already-exhausted unit it's a
harmless no-op advance). Each action calls `_advance_pay_or_exhaust` = pop the head id,
log DecisionResolved; when `pending_ids` empties, pop the decision + restore active to
`after_resolve_player_index`. Registered `pay_or_exhaust` in
`invariants._KNOWN_DECISION_KINDS`, `web/session._PROMPTS` + `label_for` (names the
unit: "Pay 1 resource to keep <name> ready" / "Let <name> be exhausted"),
`HeuristicBot._choose_pay_or_exhaust` (pay to keep a unit ready only with ≥4 ready
resources to spare, else let it exhaust) + `AcceptExhaust` in `_SAFE_DEFAULT_ORDER`. No
new event class (exhaust has none engine-wide; log DecisionResolved + state diff).

**ENCODING SEC_73** (sec/abilities.py) = a plain `EventAbility` whose one no-target
`CustomEffect` adapter calls `push_eye_of_aldhani_schedule` (the Palpatine SOR_135
inline-push pattern). Face SEC_73==SECP_5 byte-identical (SECP_5 is literally
`reprintOf` SEC_73 in the DB) → alias `("SECP","5") → ("SEC","73")` reprints.py "batch
50". **⚠️ FIXED all THREE stale `test_reprints.py` examples** that hardcoded
SEC_73/SECP_5 as the last unregistered/needs_encoding example (repointed there in
B45/B47): (1) `test_unregistered_canonical_raises` → repointed to a VANILLA
already_playable pair **Alliance X-Wing LAW_253/SOR_237** (neither registered, same
face — stable since vanilla cards never get a per-card encode); (2) renamed
`test_text_bearing_reprint_lands_in_needs_encoding` → **`test_reprint_sweep_complete_needs_encoding_empty`**
asserting the COMPLETION invariant (`needs_encoding` bucket EMPTY + SEC_73/SECP_5 in
`already_covered`) — there is no remaining real needs_encoding reprint to pin; (3)
`test_verify_playable_flags_an_injected_bad_keyword_deferred` → repointed the injected
card to **Long Live the Empire ASH_103** (unregistered, no keyword, text-bearing; ASH
is an un-encoded set → stable stand-in). Tests `tests/test_eye_of_aldhani.py` (15,
enemy unit = SOR_46 vanilla): registration + SECP_5 alias identity; play schedules the
effect for the caster; `_regroup_rollover` fires + clears the one-shot schedule;
decision fired to the ENEMY with its ready unit ids; PAY → 1 resource spent + unit
stays ready; DECLINE → unit exhausted; iterate all units then pop + restore active; NO
decision without a ready enemy unit; already-exhausted units skipped; pay not offered
without a ready resource; only ENEMY units targeted (not the caster's own); serialises
across the scheduled state + the pending decision; invariants hold. **NO soak change**
(SEC_73 is an active EventAbility not a marker; SEC not in soak pools). **THE
REPRINT-DUPLICATE SWEEP IS FINISHED — every text-bearing reprint group is encoded;
only vanilla `already_playable` (43) + `already_covered` (192) groups remain, all
playable.** Reusable seams left behind: the `scheduled_action_phase_effects` delayed
scheduler + the `pay_or_exhaust` multi-unit per-enemy decision. See [[reprint-duplicates]].

**STAGE 4 BATCH 49 DONE 2026-07-16 (FRAMEWORK ESCALATION — the REPLACEMENT-EFFECT
framework's DAMAGE half, ABILITY sink: interactive ability-damage prevention —
COMPLETES + REGISTERS Queen Amidala SEC_101 "If damage would be dealt to this unit,
you may defeat another friendly unit that shares a trait with this unit.  If you do,
prevent that damage").** Re-ran `find_reprints --check` FIRST (was 2 grp, `--check OK`).
Surveyed BOTH remaining canonicals' DB text + RE-DERIVED vs the CURRENT engine: still
**2-PRIMITIVE BALLOONS** (Amidala's combat half was B48; the ability/indirect half is
the deferred 2nd; Eye of Aldhani SEC_73 = scheduler + per-enemy pay-or-exhaust). No
single primitive clears a group → **surfaced via AskUserQuestion (terminal-tail
precedent B47/B48); user chose "Complete Amidala (dmg prevention)".** Cleared **1 grp**
(3 members: SEC_101, J25_16, P25_27): **needs_encoding 2→1, already_covered 190→191,
`--check OK`.** ONLY **Eye of Aldhani SEC_73/SECP_5** remains — THE LAST group.

**⚠️ DESIGN FINDING — the ability half is ONE self-contained primitive (deferred-damage
prevention), NOT a resumable-resolver rewrite.** The two synchronous non-combat sinks
are `resolver._apply_deal_damage` (ability) and `_apply_indirect_damage` (indirect),
fed by ~10 call paths (execute_effect's DealDamage/DealDamageEqualTo arms incl. EACH_*
loops, every damage CustomEffect, the top-level "pop-then-deal" resolvers). Combat is a
SEPARATE sink `_deal_damage_with_shield` (B48's flag mechanism, untouched). **Key: avoid
stack-unwinding by DEFERRING the damage, not the control flow.** In `_apply_deal_damage`,
AFTER the Malakili `_damage_prevented` check and BEFORE `_record_noncombat_damage`: if
the target carries `InteractiveDamagePrevention`, is UNSHIELDED (a shield would absorb
the hit — same simplification as combat), and has ≥1 trait-sharing friendly, PUSH an
`ability_damage_prevention` decision (carrying the deferred payload `{protect_id,
controller_id, amount, source_name, dealer_id, source_id}`) and RETURN without dealing
(`_try_defer_ability_damage_prevention` returns True). This reuses the established
NESTED-DECISION resume — `apply_resolve_effects` (resolver.py 2233-43) leaves its buried
`resolve_effects` decision in place when a new one is on top and resumes via
AutoResolveEffects; the top-level pop-then-deal resolvers likewise just see a new top
decision. On resolve (`_resolve_ability_damage_prevention`): ACCEPT → `_apply_defeat_unit`
the sacrifice (pop-then-act) + DROP the damage + emit new `DamagePrevented` event; DECLINE
→ re-apply the deferred damage via `_apply_deal_damage(..., _skip_prevention=True)` (the
new param prevents infinite re-deferral). **⚠️ KEY DE-RISKER: the engine keys the acting
player off the TOP pending decision's `deciding_player_id`, NOT `active_player_index`
(web/session.py:120-122; the invariant only asserts active-idx IN RANGE + decider is a
real player — it does NOT assert they match).** So even if a pop-then-deal resolver
overwrites `active_player_index` after our defer pushed a decision, the prevention is
still presented to the right player, and the mismatch self-corrects as decisions resolve
— no active-idx bookkeeping fight. Defer sets `after_resolve_player_index =
state.active_player_index` (restore-what-was) and flips active to the decider.

**⚠️ INDIRECT needs NO coverage — FAITHFUL BY CONSTRUCTION.** `_apply_indirect_damage`'s
SOLE functional caller is `_resolve_assign_indirect_damage`, where the RECEIVING player
(= Amidala's controller) ASSIGNS the whole indirect chunk to ONE of their base/units.
A base is always a legal sink, so they simply dump indirect on their base and never
onto their own Amidala → prevention-vs-indirect is unreachable. NOT implementing defer at
`_apply_indirect_damage` is fully faithful in OUTCOME (and avoids the observer-ordering
wart with `WhenIndirectDamageDealtToUnit`). So the whole primitive touches ONE sink.

**REUSE (B48 combat half) + ADDITIONS.** Reused B48's `InteractiveDamagePrevention`
marker, `_has_interactive_damage_prevention`, `_prevention_sacrifice_targets`,
`_combat_damage_prevention_actions`. BROADENED the two action classes
`ChoosePreventionSacrifice` / `DeclineCombatPrevention` to accept BOTH kinds (new
`_PREVENTION_KINDS = ("combat_damage_prevention","ability_damage_prevention")`),
dispatching in `.apply()` to `_resolve_ability_damage_prevention` vs
`_resolve_combat_damage_prevention` by `top.kind`; broadened the legal_actions branch to
both kinds (→ the same `_combat_damage_prevention_actions`). Bot needs NO change (it
already declines both via the class names in `_SAFE_DEFAULT_ORDER`); web `label_for` +
`_PROMPTS` gained the ability kind (label made generic "prevent the damage"). New event
`DamagePrevented` (events.py, generic `event_to_model` serialise; format.ts). Registered
`ability_damage_prevention` in `invariants._KNOWN_DECISION_KINDS`. Files: events.py,
resolver.py (`_apply_deal_damage` +`_skip_prevention` param + defer call),
actions.py (`_try_defer_ability_damage_prevention` / `_resolve_ability_damage_prevention`
/ `_PREVENTION_KINDS` / broadened actions + legal_actions), invariants.py, web/session.py,
web/format.ts. **With no marker in play the sink is byte-identical (`_skip_prevention`
False default, marker-gated) → soak/determinism unaffected.**

**ENCODING SEC_101** (sec/abilities.py; imported `InteractiveDamagePrevention`) =
`[TriggerAbility(WhenPlayed(), effects=[CreateTokenUnit("Spy", count=2)]),
InteractiveDamagePrevention()]`. Spy = TokenUnit **SEC_1** (0/2, trait Official) loaded by
name — Amidala's traits are **Naboo/Official**, so her own Spy tokens SHARE Official and
are eligible sacrifices (thematic + self-contained). FACES SEC_101==J25_16==P25_27
byte-identical (find_reprints grouped; same text/rules/cost/stats) → aliases
`("J25","16")/("P25","27") → ("SEC","101")` reprints.py "batch 49". **NO test_reprints
repoint** — its stale-example hardcodes already point at Eye of Aldhani SEC_73/SECP_5
(repointed there in B45/B47), which stays needs_encoding; registering Amidala does not
touch them (grep-confirmed no SEC_101/Amidala in test_reprints.py). Tests:
`tests/test_ability_damage_prevention.py` (13, REAL SEC_101 now registered — sacrifice =
Mon Mothma **SEC_103** [Official/Rebel, no WhenDefeated], enemy source SOR_46): marker+Spy
registration; alias identity; ability damage DEFERRED (target damage still 0) + offered to
the protected unit's CONTROLLER; ACCEPT → sacrifice→discard + 0 damage + DamagePrevented;
DECLINE → full damage lands; lethal decline DEFEATS Amidala; NOT offered without a
trait-sharing friendly / when shielded; 0-amount no-op; **END-TO-END via Open Fire TWI_174
("Deal 4 to a unit") through `apply` — P0 ChooseTarget(Amidala) → deferred prevention
decision to P1 → decline (Amidala defeated) / accept (sacrifice defeated, Amidala survives,
buried resolve_effects resumes to quiescence via a `_drain` AutoResolveEffects loop)**;
serialises across the pending decision; invariants hold. Verification: 13 new pass; B48
combat tests + test_reprints (830) pass; fast tier + `--check OK`. **REMAINING 1 grp:
Eye of Aldhani SEC_73/SECP_5** (delayed action-phase-start scheduler [an Event goes to
discard → needs a per-player scheduled-effect queue fired at ACTION-phase start; the
existing PhaseStartTrigger needs an in-play host] + a per-enemy pay-1-resource-or-exhaust
decision [the enemy is the decider per unit] = 2 independent primitives). See
[[reprint-duplicates]].

**STAGE 4 BATCH 48 DONE 2026-07-16 (FRAMEWORK ESCALATION — the REPLACEMENT-EFFECT
framework's DAMAGE half, COMBAT sub-half: interactive combat-damage prevention for
Queen Amidala SEC_101 "If damage would be dealt to this unit, you may defeat another
friendly unit that shares a trait with this unit.  If you do, prevent that damage").**
Re-ran `find_reprints --check` FIRST (2 grp, `--check OK`, NO reopen).  Surveyed BOTH
remaining canonicals' DB text + RE-DERIVED vs the CURRENT engine: **both remaining are
TWO-PRIMITIVE BALLOONS → no single primitive clears a group** (the TERMINAL hard tail).
Amidala = combat-damage-prevention decision + ability/indirect-damage prevention (two
sinks); Eye of Aldhani SEC_73 = delayed action-phase-start scheduler + per-enemy
pay-or-exhaust. **⚠️ Surfaced the path via AskUserQuestion (both are 2-session arcs; no
single primitive clears any group); user chose "Combat resumability (Amidala DAMAGE
half)".**  Cleared **0 grp** — a PURE FRAMEWORK-FOUNDATION session: **Amidala stays
ESCALATED (NOT registered), needs_encoding UNCHANGED at 2, already_covered 190, NO alias
landed** (her full replacement also needs the DEFERRED ability/indirect half).

**⚠️ KEY DESIGN FINDING — the combat step does NOT need a heavyweight rewrite.** Combat
is ALREADY resumable into `_resolve_unit_combat_step2` via the existing `pre_attack`
decision + `ContinueAttack`.  So the COMBAT-damage prevention is additive/low-risk:
**(1) `CardInstance.prevent_next_combat_damage` bool** (state.py; serialised) — a one-shot
read at the SINGLE combat sink `_deal_damage_with_shield` (early-return BEFORE the shield
check → drop the instance, emit `CombatDamagePrevented`, disarm).  Cleared in
`_clear_this_attack_combat_flags(attacker, defender=None)` — the helper GAINED an optional
`defender` param (passed at the two unit-vs-unit step2 exits) so a DEFENDER-armed-but-unused
flag can't leak if the attacker died pre-step2.  **(2) `registry.InteractiveDamagePrevention(
share_trait=True)`** passive marker (the AttackRestriction/PreventDamage family; read at the
checkpoint; exported from registry, added to `soak._analyse_ability_coverage`'s passive
tuple).  **(3) checkpoint `_armed_combat_preventions`** in `_resolve_unit_combat` AFTER the
OnAttack-trigger collection: for EACH combatant carrying the marker with >0 unshielded
incoming combat power (`compute_power`, same calls as step2) AND ≥1 eligible trait-sharing
friendly sacrifice → push the `pre_attack` continuation (as today) + a
`combat_damage_prevention` decision per armed unit, INSERTED at `decisions_before+1` (just
ABOVE pre_attack, BELOW any OnAttack-trigger decisions, so it resolves right before
ContinueAttack).  **(4) new decision kind `combat_damage_prevention`**: `ChoosePreventionSacrifice(
target_id)` / `DeclineCombatPrevention`; accept defeats the chosen friendly (`_apply_defeat_unit`,
POP-then-defeat gotcha) then arms the protected unit's flag; the existing `ContinueAttack`
resumes step2 (which now deals 0 to the armed unit).  `_prevention_sacrifice_targets` = other
friendly units sharing an effective trait (`get_traits`) with the protected unit; deciding
player = the protected unit's controller (works for Amidala-as-DEFENDER *and* -as-ATTACKER).
Registered in invariants `_KNOWN_DECISION_KINDS`, web/session `_PROMPTS` + `label_for`
(ChoosePreventionSacrifice names the sacrifice), HeuristicBot (DECLINES — the "don't
self-harm" safe default; `DeclineCombatPrevention` in `_SAFE_DEFAULT_ORDER`), format.ts
(`CombatDamagePrevented`).  **NO combat-pipeline rewrite; with no marker in play the pipeline
is byte-identical → soak/determinism unaffected** (flag defaults False).  Tests:
`tests/test_combat_damage_prevention.py` (9, SYNTHETIC — the marker registered on stand-in
**SOR_46** via a `_REGISTRY` save/restore fixture, since Amidala is unregistered; attacker =
vanilla **SOR_68** Cargo Juggernaut 4/6 no-Sentinel, sacrifice = a 2nd SOR_46 sharing
Rebel/Trooper): flag one-shot at the sink; offered to the defender's controller; accept →
sacrifice→discard + 0 combat damage (attacker still took the defender's 3); decline → full
damage lands; NOT offered without a trait-sharing friendly / when shielded; attacker-side
prevention (decider = attacker's controller); serialises across the decision; invariants hold.
**⚠️ CARD-CHOICE GOTCHA: SOR_48 Vigilant Honor Guards has SENTINEL → it forces the attack
onto itself, so it's a BAD test defender/sacrifice; SOR_46 (no Sentinel, no abilities) is the
clean stand-in.**  Verification: 9 new pass; fast tier **2481 passed / 5 skipped / 0 FAILED /
118 known WinError-5 errors**; `--check OK`, needs_encoding unchanged.  **FOLLOW-ON (the DAMAGE
half's SECOND primitive, DEFERRED): interactive prevention of ABILITY damage
(`resolver._apply_deal_damage`) + INDIRECT damage (`_apply_indirect_damage`)** — those are
SYNCHRONOUS sinks; injecting an interactive decision mid-resolution needs unwinding/resuming
the synchronous call stack = a separate dedicated-session primitive.  **Amidala registers
only once BOTH halves land** (combat = this batch; ability/indirect = next).  **REMAINING 2
grp**: Amidala SEC_101/J25_16/P25_27 (the ability/indirect-damage half above) + Eye of Aldhani
SEC_73/SECP_5 (delayed action-phase-start scheduler + per-enemy pay-or-exhaust = 2 independent
primitives).  See [[reprint-duplicates]].

**STAGE 4 BATCH 47 DONE 2026-07-16 (FRAMEWORK ESCALATION — the REPLACEMENT-EFFECT
framework, DEFEAT half: a `WhenDefeatedAsUpgrade` trigger collected from
`_defeat_unit`'s `defeated_upgrades` scan, relocating a just-defeated PILOT from
discard back to the ground arena as an exhausted unit — "If this upgrade would be
defeated, you may instead move him to the ground arena as a unit and exhaust him").**
Re-ran `find_reprints --check` FIRST (was 3, `--check OK`, NO reopen). Surveyed ALL 3
fresh canonicals' DB text (`.text` + `epic_action` + `rules`) + RE-DERIVED each vs the
CURRENT engine: NO trivial stragglers → no AskUserQuestion easy/escalation fork.
**RE-DERIVATION FINDING — the TERMINAL HARD TAIL: all 3 remaining are STOP-class** (2
replacement-effect + 1 two-primitive balloon), so the "just pick one small primitive"
path terminates in STOP for every candidate. **Luke J25_4** = REPLACEMENT effect in
`epic_action`; **Amidala SEC_101** = INTERACTIVE mid-COMBAT-damage prevention decision
(B41's `PreventDamage` read is non-interactive at `_apply_deal_damage`, but Amidala's
"if damage would be dealt to THIS unit" also covers COMBAT damage in the synchronous
`_deal_damage_with_shield`/`_resolve_unit_combat_step2` — injecting a decision there
needs the combat step made RESUMABLE = replacement-class); **Eye of Aldhani SEC_73** =
delayed action-phase-start schedule (NONE exists — `PhaseStartTrigger` fires ONLY at
`_enter_regroup` and needs a persistent in-play card; an Event goes to discard) + a
per-enemy pay-or-exhaust decision kind = TWO INDEPENDENT new primitives → balloon.
**⚠️ Surfaced this inflection point via AskUserQuestion (a genuine judgment call: the
one-primitive rule can't clear any group). User chose "Tackle replacement-effect
framework."** Cleared **1 grp** (2 members: J25_4, P25_89): needs_encoding **3→2**,
already_covered **189→190**, `--check OK`.

**THE FRAMEWORK — (1) new trigger `WhenDefeatedAsUpgrade` (registry.py; exported in
`abilities/__init__.py`).** Fires when a card is defeated WHILE IT IS AN ATTACHED
UPGRADE (a Pilot). **(2) `_trigger_matches` arm** = `isinstance(event, UnitDefeated)`
ONLY (NO instance-id compare — the UnitDefeated event is the HOST's; the "as an
upgrade" gating is STRUCTURAL, done at the collection site). **(3) `_collect_triggers`
`defeated_upgrades` scan EXTENDED** (resolver.py ~608): the loop that collected
`GrantedAbility(WhenDefeated)` (bounty) from a defeated host's detached upgrades now
ALSO collects the upgrade's OWN `TriggerAbility(WhenDefeatedAsUpgrade)`, appending
`(upg, upg, idx, spec)` — source = the DETACHED PILOT ITSELF (which is in its owner's
discard by then). **KEY: the `defeated_ci` scan (line 588) collects only `WhenDefeated`,
so Luke defeated as a NORMAL UNIT does NOT fire his replacement — only the
`defeated_upgrades` path does; that's the whole reason for a dedicated trigger type
rather than a plain `WhenDefeated`.** **(4) ENCODING J25_4** (promo/abilities.py — J25
cards register there; imported `WhenDefeatedAsUpgrade`) = an OPTIONAL
`TriggerAbility(WhenDefeatedAsUpgrade(), effects=[CustomEffect(_luke_j25_4_move_to_ground)])`.
The no-target fn `find_instance(source)` locates Luke in his owner's discard,
`discard.remove`, sets `zone=GROUND_ARENA` / `face_down=False` / `exhausted=True`
("exhaust him") / `damage=0` / `attached_upgrades=[]`, appends to owner's ground_arena,
emits `UnitEntersPlay` (event only — does NOT fire the enter-play bus / WhenPlayed;
it's a relocation, not a play; Luke has no such triggers anyway). Piloting is the
keyword layer; played as a normal unit Luke is a vanilla 3/2. **This is the FAITHFUL
LOW-RISK replacement stand-in = the Superlaser Technician SHD_85 discard-then-relocate
pattern (an optional trigger that finds the just-defeated card already in discard and
moves it) — the ONLY difference from a TRUE pre-defeat interception is a momentary
discard touch, UNOBSERVABLE (no shipped card triggers on an upgrade's defeat). It needs
ZERO combat-pipeline surgery.** No new decision kind (reuses `trigger_option` /
AcceptTrigger/DeclineTrigger), NO invariants/web/session change, NO soak change (Luke is
promo/anthology, never in the starter/vanilla/keyword soak pool → no zero-fire risk).
FACE J25_4==P25_89 (find_reprints grouped; P25_89 has a trailing space in `epic_action`
+ no `rules` field, J25_4 has `rules` — cosmetic, same face) → alias `("P25","89") →
("J25","4")` reprints.py "batch 47". **⚠️ FIXED BOTH stale `test_reprints.py::TestVerifyPlayable`
examples** — B46 repointed them to **Luke J25_4/P25_89** as the "implemented-keyword
(Piloting) masks unregistered functional text → stays needs_encoding" example;
registering J25_4 broke BOTH (test 1: `build_worklist` now buckets Luke `already_covered`,
NOT needs_encoding; test 2: `verify_playable`'s `(s,n) not in registered` guard at
line 263 now SKIPS the registered Luke → no problem recorded → the `assert problems`
fails). **⚠️ NO keyworded needs_encoding reprint remains** (Amidala + Eye of Aldhani
have NO keyword), so the "keyword-mask" example is EXHAUSTED — repointed BOTH to **The
Eye of Aldhani SEC_73/SECP_5** (unregistered + text-bearing + no keyword → verify_playable
flags it via the FUNCTIONAL-TEXT gate, the `unimpl` keyword gate passing trivially);
renamed test 1 to `test_text_bearing_reprint_lands_in_needs_encoding` (now guards plain
text-bearing routing; keyword-mask path still exercised by `_bucket`'s `has_text_keys`
branch when a real keyworded+text card appears). Tests `TestLukeSkywalkerJ254` (6, in
tests/test_promo_cards.py [J25 cards test there], methods embed j25_4: attach Luke as a
pilot upgrade on a P0 host via `_attach_upgrade`, defeat host via REAL `_defeat_unit` →
Accept the optional trigger → Luke relocates to ground arena EXHAUSTED, not in discard;
relocated Luke has UNIT stats 3/2 [compute_power/compute_hp, not upgrade stats]; Decline
→ Luke STAYS in discard; Luke defeated AS A NORMAL UNIT [`_defeat_and_fire`] → NO
AcceptTrigger offered [replacement doesn't fire]; serialises across the pending trigger;
P25_89 alias `get_abilities` identity). **⚠️ TEST GOTCHA: the test `_find_instance`
helper does NOT search the DISCARD pile → returns None for a card in discard; assert
discard membership by iterating `ps.discard` (`any(c.instance_id==… )`), NOT via
`_find_instance`.** **FOLLOW-ON — Amidala SEC_101 is the DAMAGE half of THIS framework**:
"If damage would be dealt to this unit, you may defeat a friendly trait-sharing unit →
prevent it" CANNOT be a post-hoc trigger (once lethal damage lands Amidala is already
defeated — prevention must be PRE-damage), so it needs a TRUE pre-event interception at
BOTH damage sinks incl. the SYNCHRONOUS combat step made RESUMABLE — the single
highest-regression-risk change in the engine, DEFERRED to its own dedicated session (do
NOT jam combat resumability into a card batch). Eye of Aldhani SEC_73 remains its own
two-primitive balloon. **REMAINING 2 grp**, both STOP-class: Amidala SEC_101/J25_16/P25_27
(combat-resumable damage-prevention = the framework's DAMAGE half); Eye of Aldhani
SEC_73/SECP_5 (delayed action-phase-start schedule + per-enemy pay-or-exhaust = two
independent primitives). See [[reprint-duplicates]].

**STAGE 4 BATCH 46 DONE 2026-07-15 (FRAMEWORK ESCALATION — NAME-BASED PERSISTENT
ABILITY SUPPRESSION: a `name_a_card` decision kind + a `CardInstance.named_card`
field + a `state.is_name_suppressed` scan WOVEN INTO B44's 7 ability-read guards —
"Name a card; each non-leader card an opponent owns with that name, incl. out of
play, loses all abilities while the namer is in play").** Re-ran `find_reprints
--check` FIRST (was 4, `--check OK`, NO reopen). Surveyed ALL 4 fresh canonicals'
`.text` + RE-DERIVED each vs the CURRENT engine (NO trivial stragglers → no
AskUserQuestion fork; pure escalation, the HARD TAIL). RE-DERIVATION FINDINGS —
**Amidala SEC_101** shrank a little (its "Create 2 Spy tokens" half is now a TRIVIAL
`CreateTokenUnit("Spy")` reuse — Spy is TokenUnit **SEC_1**) but its "if damage WOULD
be dealt … you may defeat a friendly unit sharing a trait to prevent it" half is an
INTERACTIVE mid-damage decision INJECTION = replacement-class → STOP; **Eye of Aldhani
SEC_73** = delayed action-phase-start schedule (none exists) + per-enemy pay-or-exhaust
= TWO pieces → balloon; **Luke J25_4** = REPLACEMENT in `epic_action` → STOP. **Galen
P25_31 REOPENED from "balloon" to a clean SINGLE primitive** — the memory-flagged
"needs a persistent global registry + out-of-play, B44's PHASE-SCOPED flag FIGHTS it"
concern DISSOLVES if suppression is modelled as a **name-based SCAN over in-play namer
units** rather than the per-instance flag: then (a) PERSISTENCE falls out for free (the
scan is over in-play namers → lifts when Galen leaves) and (b) OUT-OF-PLAY falls out for
free (the ability-read guards match by NAME, so an opponent-owned copy is suppressed
wherever its abilities are read — e.g. when played from hand). NO second primitive; NO
fight with B44's flag (the two suppression sources COEXIST through the same 7 guards).
**Picked Galen Erso P25_31** (4-cost Imperial, Vigilance/Heroism; canonical, shipped
promo/anthology; + Plot = keyword layer, free). Cleared **1 grp** (3 members: P25_31,
P26_38, P26_50): needs_encoding **4→3**, already_covered **188→189**, `--check OK`, fast
tier **2463 pass / 0 fail** (118 known WinError-5 PermissionError errors).

**THE PRIMITIVE — (1) `CardInstance.named_card: Optional[str] = None`** (state.py;
serialised to_dict/from_dict, back-compat default None — the `abilities_suppressed`/
`combat_damage_redirect_to` transient-instance-field pattern). Lives on the NAMER
(Galen), holds the named card's NAME. **(2) `state.is_name_suppressed(state, ci) ->
bool`** (module-level in state.py — state.py already imports `Leader`, no cycle): True
when `ci` is a NON-leader card whose `card_def.name` equals the `named_card` of ANY
in-play unit controlled by `ci`'s OPPONENT (scan both players' arenas; skip `ci`'s own
owner's player, so the namer must be the opponent's; a Leader card_def short-circuits
False — "non-leader card"). Compares by `owner_id` (correct even under control-change —
"an opponent OWNS"). **(3) The B44 read-layer EXTENDED at all 7 guards** — each
`if getattr(ci,"abilities_suppressed",False):` became `… or is_name_suppressed(state,
ci):` — so "loses all abilities" reuses B44's exact inventory: `keywords.has_keyword`
(early `return False`) + `keyword_value` (`return 0`) [top-level `from swu.engine.state
import is_name_suppressed` — HOT path]; `resolver._collect_triggers` (`continue` the
candidate — skips own/upgrade-granted/leader-as-upgrade triggers) [local import];
`traits._scan_arena_grants` (a named unit grants no traits) [local import];
`actions.legal_actions` ARENA UseAbility loop (skip `ci`) + `_constant_ability_power_bonus`
+ `_constant_ability_hp_bonus` (a named source buffs nothing) [top-level import added to
actions' state import]. **KEY ELEGANCE (inherited from B44): because the guards are
READS, "loses ALL abilities" incl. keywords granted by upgrades falls out for free, AND
because the scan is by NAME over in-play namers, persistence + out-of-play are automatic
— no per-victim stamping, no hand/deck touch.** **(4) A `name_a_card` decision kind**
(`actions.push_name_a_card(s, source_ci)` + `NameCard(name)` action + `_name_a_card_names`
enumerator + the `legal_actions` branch `return [NameCard(n) for n in top.context["names"]]`).
Decider = source controller; MANDATORY (no decline — "Name a card"); on `NameCard.apply`
pop the decision, set the source's `named_card` (source found via
`_find_in_arenas_any`), restore active player. **OPTION LIST = distinct NON-leader card
names among the OPPONENT's cards in PUBLIC zones ONLY** (ground+space arenas + their
attached upgrades + discard + base) — this (a) keeps the list bounded and (b) AVOIDS
LEAKING the opponent's hidden hand/deck to the naming player (a real hidden-info concern
the enumeration MUST respect); "including those not in play" is STILL honoured because a
hidden copy of a PUBLICLY-named card is suppressed by the name-based read the instant its
abilities are read. **DOCUMENTED SIMPLIFICATION: a card with NO public copy cannot be
named (the naming fizzles if the opponent has no public non-leader card — no push).**
Registered `name_a_card` in `invariants._KNOWN_DECISION_KINDS` + `web/session._PROMPTS`
(`NameCard.describe()` = "Name card <name>", already id-free → NO `label_for` change) +
`HeuristicBot._choose_name_a_card` (name the card matching the highest-`_card_value`
enemy ARENA unit, else the first offered — options are public, no leak). **NO soak change**
(Galen is an active WhenPlayed CustomEffect, not marker-only). **ENCODING P25_31**
(promo/abilities.py — P25/P26 cards register there; imported nothing new, WhenPlayed/
CustomEffect already imported) = a mandatory `TriggerAbility(WhenPlayed(),
effects=[CustomEffect(fn=_galen_name_a_card)])` whose no-target fn `push_name_a_card`
(the Palpatine SOR_135 inline-push pattern); Plot is the keyword layer. FACES
P25_31==P26_38==P26_50 byte-identical (find_reprints grouped; alias guard asserts) →
aliases `("P26","38")/("P26","50") → ("P25","31")` reprints.py "batch 46". **⚠️ FIXED
BOTH stale `test_reprints.py::TestVerifyPlayable` examples** (`test_keyword_deferred_card_with_ability_text_is_needs_encoding`
+ `test_verify_playable_flags_an_injected_bad_keyword_deferred`) that hardcoded **Galen
Erso P25_31/P26_38** as the "implemented-keyword masks unregistered functional text →
stays needs_encoding" example (B43 repointed them HERE from Jabba ASH_42) — registering
P25_31 broke both; repointed BOTH to **Luke Skywalker J25_4/P25_89** (needs a card whose
keyword IS in `IMPL_ENGINE_KEYWORDS` + unregistered functional text: Luke's keyword is
**Piloting** ∈ IMPL_ENGINE_KEYWORDS and `has_functional_text(full_text, keywords)` is
True via the REPLACEMENT text in his `epic_action` — and Luke J25_4/P25_89 stays
needs_encoding, the deferred replacement). Tests `TestGalenErsoP2531` (9, in
tests/test_promo_cards.py [P25 cards test there], methods embed p25_31: WhenPlayed →
name_a_card decision offers opponent-public names → NameCard sets `named_card`; named
enemy unit loses its keyword [Cell Block Guard SOR_229 Sentinel → has_keyword False];
named enemy loses its self-constant [Scimitar LOF_233 damaged +3/+0 → compute_power
6→3, the constant-source guard]; a copy PLAYED LATER enters suppressed [set named_card,
then `_place` a fresh copy → suppressed, the out-of-play proof]; suppression LIFTS when
Galen removed from arena [persistence]; ONLY opponent-owned copies suppressed [the
namer's OWN same-named copy keeps its keyword]; a Leader card is NEVER suppressed;
`named_card` serialises; P26_38/P26_50 alias `get_abilities` equality). **⚠️ TEST DRIVER
GOTCHA: fire Galen's mandatory WhenPlayed via `_fire_when_played(state, galen)` then
`_drain` (AutoResolveEffects) to run the no-target CustomEffect that pushes the decision;
for the suppression assertions set `galen.named_card = "<name>"` DIRECTLY (bypass the
decision) — `_place` puts Galen in the arena, no enter-play machinery needed; a small-HP
`_place`d unit stays put (no combat) so `has_keyword`/`compute_power` reads are stable.**
**FOLLOW-ON:** `is_name_suppressed` + `named_card` + the `name_a_card` decision is a
reusable "name-based persistent ability suppression" seam; it COEXISTS with B44's
phase-scoped `abilities_suppressed` through the same 7 guards (two suppression sources,
one read-layer). **REMAINING 3 grp**, all genuine escalation, the HARD TAIL: **Amidala
SEC_101/J25_16** (Spy-token reuse + INTERACTIVE mid-damage prevention decision =
replacement-class, STOP); **Eye of Aldhani SEC_73/SECP_5** (delayed action-phase-start
schedule + per-enemy pay-or-exhaust = TWO pieces); **Luke J25_4/P25_89** (REPLACEMENT
effect in `epic_action`, STOP per rule). See [[reprint-duplicates]].

**STAGE 4 BATCH 45 DONE 2026-07-15 (FRAMEWORK ESCALATION — the MULTI-DEFENDER
ATTACK primitive: a `MultiDefenderAttack` marker + an `AttackTwoUnits` action +
a `_resolve_two_unit_combat[_step2]` pipeline — a unit attacks TWO enemy units as
ONE simultaneous attack).** Re-ran `find_reprints --check` FIRST (was 5, `--check
OK`, NO reopen). Surveyed ALL 5 fresh canonicals' `.text` + RE-DERIVED each vs the
CURRENT engine: **NO zero-engine trivial stragglers → no AskUserQuestion fork**;
pure escalation, the HARD TAIL. RE-DERIVED "needs exactly ONE new primitive (not a
2-piece balloon, not a replacement)": **Galen P25_31** = name-a-card decision (ALL
card names, not a zone) + PERSISTENT global name-suppression registry (B44's per-
instance `abilities_suppressed` is PHASE-SCOPED & cleared at regroup → it FIGHTS
Galen) + OUT-OF-PLAY application = MULTIPLE pieces → balloon (B44 read-layer alone
does NOT make it one primitive); **Eye of Aldhani SEC_73** = delayed "start of next
action phase" schedule (none exists) + per-enemy pay-or-exhaust (none exists) = TWO
pieces → balloon; **Luke J25_4** = REPLACEMENT effect in `epic_action` → STOP per
rule; **Amidala SEC_101** = interactive "if damage WOULD be dealt … you may defeat
a friendly unit to prevent" = a REPLACEMENT / mid-combat-damage decision injection →
STOP-class; **Maul C24_6** = "This unit can attack 2 units instead of 1" — the ONLY
remaining group that is genuinely ONE coherent mechanic (multi-defender combat),
self-contained in the combat pipeline, needs NO second primitive, NOT a replacement.
**Picked Maul C24_6** (canonical, shipped C24 promo/anthology; 5/6 Ground, Force/
Sith). Cleared **1 grp** (3 members: C24_6, J25_5, P25_91): needs_encoding **5→4**,
already_covered **187→188**, `--check OK`, fast tier **2448 pass / 0 fail** (118
known WinError-5 web PermissionError errors).

**THE PRIMITIVE — a `MultiDefenderAttack(count=2)` bare passive marker
(registry.py, `@dataclass(frozen=True)` — the AttackRestriction/EntersPlayReady/
IndirectDamageBonus family) + a dedicated `AttackTwoUnits(attacker_id, defender1_id,
defender2_id)` action + a parallel two-defender combat resolver.** ISOLATED from the
granted-attack-tangled `AttackWithUnit` (no shipped card grants a two-unit attack).
(1) `actions._multi_defender_count(state, attacker)` = scans `get_abilities` for the
marker → count (0 if none; the `_attack_forbidden` scan shape). (2)
`_enumerate_two_unit_attacks(state, ps, inactive_ps)` (called in `legal_actions`
ACTION phase, right after `_enumerate_attacks`): for a READY attacker with the marker,
all UNORDERED distinct PAIRS of legal enemy UNIT defenders in the attacker's OWN
arena — Hidden-filtered, Sentinel-filtered ACROSS THE PAIR (both must be Sentinel if
the defending player controls one & attacker isn't Saboteur), NO base ("may not
attack a base and a unit"); needs ≥2 eligible. (3) `AttackTwoUnits.apply` guards
(marker present, distinct defenders, same arena) then `_resolve_two_unit_combat`;
switches active player iff no continuation/decision. (4) **`_resolve_two_unit_combat`**
= exhaust; log an AttackDeclared per co-defender (both attacked); fire OnAttack/
WhenAttacked triggers ONCE (attacker's OnAttack fires once per the rules; event_ctx
carries `defender_ids=[d1,d2]` + `defender_id=d1`); if a trigger pushes a decision →
insert a `pre_attack` continuation carrying `defender_ids` (NO new decision kind —
reuses `pre_attack`), else step2. (5) **`_resolve_two_unit_combat_step2(…, attacker,
defenders: LIST)`** = Restore/Saboteur (strips shields on BOTH); filter to live
defenders (+attacker-gone guard); compute atk_power ONCE; snapshot each defender's
hp_before + def_power; SIMULTANEOUS damage — each defender takes atk_power (own Shield
intercepts), attacker takes the SUM of both defenders' power (`_deal_damage_with_shield`);
Overwhelm spills the COMBINED excess `sum(max(0, dealt-hp_before))` to the base;
defeat processing for attacker + both co-defenders (each re-checked in-arena — the
single-defender double-defeat guard); OnAttackDefeatsUnit fires once per slain
co-defender (attacker survived); WhenCombatDamageDealt (SHD_84) per hit survivor;
WhenAttackEnds (Vermillion LAW_215) survivor; cleanup `_clear_this_attack_combat_flags`
+ `_expire_modifiers("this_attack")`. (6) **`ContinueAttack` extended:** if the
`pre_attack` ctx has `defender_ids` → re-find both, route to
`_resolve_two_unit_combat_step2` with the surviving list. **NO new decision kind, NO
invariants change** (`pre_attack` already known); soak passive-marker tuple gained
`MultiDefenderAttack` (Maul's ONLY spec is the marker → must not be a false zero-fire);
`web/session.label_for` names attacker+both defenders; `HeuristicBot._score_two_unit_attack`
(sum both per-defender `_trade_outcome` gains, single combined loss). **DOCUMENTED
SIMPLIFICATIONS (none exercised by a shipped card co-occurring with a two-unit
attacker):** First Strike / defender-deals-first (LAW_86) / combat-damage redirect
(SHD_90) are NOT modelled for a two-unit attack (always simultaneous); Lando
"while defending" attacker debuff (LAW_108) not applied (`defender_id`=None for
attacker power); only the FIRST co-defender's WhenAttacked is fired (no shipped
WhenAttacked-defender-under-a-two-unit-attack). **ENCODING C24_6** (promo/abilities.py
— C24 cards live there alongside C24_3; imported `MultiDefenderAttack`) = a lone
`MultiDefenderAttack(count=2)` marker (Maul is vanilla-stat otherwise). FACE
C24_6==J25_5==P25_91 → aliases `("J25","5")/("P25","91") → ("C24","6")` reprints.py
"batch 45". **⚠️ FIXED 1 stale `test_reprints.py::TestApplyGuard::test_unregistered_canonical_raises`**
that hardcoded **Darth Maul C24_6/P25_91** as its "neither-registered needs_encoding"
example (B40 repointed it HERE after Max Rebo LAW_72) — registering C24_6 broke the
`assert ("C24","6") not in _REGISTRY`; repointed to **The Eye of Aldhani SEC_73/SECP_5**
(still needs_encoding, same face, the delayed-schedule+pay-or-exhaust escalation).
Tests `TestDarthMaulC246` (8, in tests/test_promo_cards.py [C24 cards test there],
methods embed c24_6: AttackTwoUnits offered only with ≥2 defenders + not for a normal
unit; deals power to BOTH defenders & attacker takes the SUM [two 3/7 survive, Maul
takes 6→dies]; kills both 2/3 Thugs & survives with 4 dmg; Overwhelm combined excess
4 to base [granted via a permanent keyword_grant Modifier]; Sentinel forces BOTH to be
Sentinels [1 sentinel+1 thug → no pair offered; 2 sentinels → pair]; state round-trip;
J25_5/P25_91 alias `get_abilities` equality). **⚠️ TEST GOTCHA: `_make_state()` puts
P0 active in ACTION with a freshly-`_place`d unit READY, so drive the attack via
`legal_actions`→pick the `AttackTwoUnits`→`apply` (a real action, NOT `_fire_on_attack`);
SOR_247 Underworld Thug is a clean 2/3 vanilla defender (Maul kills it & survives two;
two 3-power defenders would kill Maul).** **FOLLOW-ON:** `MultiDefenderAttack` +
`AttackTwoUnits` + `_resolve_two_unit_combat` is a reusable "attack N units as one
simultaneous attack" combat seam (count is parameterised; only 2 shipped). **REMAINING
4 grp**, all genuine escalation, the HARD TAIL, each a DEDICATED framework session:
Galen P25_31 name-based/OUT-OF-PLAY/persistent "lose all abilities" (name-a-card +
persistent global registry + out-of-play — the B44 read-layer alone is NOT enough);
Amidala SEC_101 interactive mid-combat-damage prevention decision (replacement-class);
Eye of Aldhani SEC_73 delayed-action-phase-start schedule + per-enemy pay-or-exhaust
PAIR; Luke J25_4 REPLACEMENT effect (STOP per rule). See [[reprint-duplicates]].

**STAGE 4 BATCH 44 DONE 2026-07-15 (FRAMEWORK ESCALATION — the ABILITY-SUPPRESSION
READ-LAYER: a `CardInstance.abilities_suppressed` bool read as a skip/early-return
at every ability-read site — the read-layer mirror of the trait/keyword query
layers — a unit "loses all abilities and can't gain abilities for this phase").**
Re-ran `find_reprints --check` FIRST (was 6, `--check OK`, NO reopen). Surveyed ALL
6 fresh canonicals' `.text` + RE-DERIVED triviality: **NO zero-engine trivial
stragglers** → **no AskUserQuestion fork**; pure escalation, the HARD TAIL. RE-
DERIVED each for "needs exactly ONE new primitive (rest reuses)": Maul C24_6
(attack-2 = multi-defender combat balloon); Galen P25_31 (name-based + **incl. out-
of-play** "loses all abilities" = broadest read-layer); Luke J25_4 (empty `.text`,
REPLACEMENT effect in `epic_action` — STOP per rule); Amidala SEC_101 (Spy tokens
reuse + INTERACTIVE mid-COMBAT-damage decision INJECTION = balloon atop B41
`PreventDamage`); Eye of Aldhani SEC_73 (delayed-schedule + per-enemy pay-or-exhaust
= TWO pieces). **Picked Mind Trick LOF_202** (canonical, shipped Legends of the
Force; 2-cost Cunning/Heroism Event; "Exhaust any number of units with a combined
power of 4 or less. If you control a Force unit, those units lose all abilities and
can't gain abilities for this phase.") — the ONLY remaining group needing exactly
ONE new primitive: the exhaust half is a TRIVIAL variant of the existing
`exhaust_combined_cost` seam, and the "lose all abilities" half is a SINGLE coherent
read-layer BOUNDED to in-play instances + this-phase (Galen's name-based/out-of-play
version is the FUTURE EXTENSION of this same layer). Cleared **1 grp** (2 members):
needs_encoding **6→5**, already_covered **186→187**, `--check OK`, fast tier **2434
pass / 0 fail** (118 known WinError-5 web PermissionError errors).

**THE PRIMITIVE — a `CardInstance.abilities_suppressed: bool` flag (state.py;
serialised to_dict/from_dict, back-compat default False — the `cannot_ready_this_round`/
`granted_bounties` transient/phase-scoped-instance-field pattern) read as a
skip/early-return at EVERY ability-read site.** This is the read-layer MIRROR of the
trait query layer (`get_traits`) and keyword query layer (`has_keyword`) — a "are
this instance's abilities suppressed?" guard, like Hidden filters defenders and B41
`PreventDamage` filters damage. **KEY ELEGANCE: because the guards are READS,
"can't gain abilities" falls out for FREE** — e.g. `has_keyword` returns False BEFORE
consulting any grant, so even a keyword granted to a suppressed unit is inert. **The
7 guards** (all `getattr(ci,"abilities_suppressed",False)` — direct attribute check,
NO helper/import, since it's a real dataclass field, avoiding circular imports):
(1) `keywords.has_keyword` → early `return False`; (2) `keywords.keyword_value` →
early `return 0`; (3) `resolver._collect_triggers` → `continue` the arena candidate
loop for a suppressed `ci` (skips its OWN + upgrade-granted + leader-as-upgrade
triggers — placed right after the `hasattr` guard, before set_code/card_number);
(4) `actions._constant_ability_power_bonus` + (5) `_constant_ability_hp_bonus` →
skip a suppressed `source_ci` (a suppressed buffer buffs nothing); (6)
`actions.legal_actions` ARENA `UseAbility` loop → skip a suppressed `ci` (no
activated ability); (7) `traits._scan_arena_grants` → skip a suppressed `source` (a
suppressed Malakili grants no traits). **Flag lifecycle:** cleared at
`_regroup_rollover` (with `granted_bounties` — "for this phase"), reset on fresh
entry (`_put_unit_in_play`, after `cannot_ready_this_round=False`) and return-to-hand
(`resolver._apply_return_to_hand`, "a card out of play is a clean card"). **NO new
decision kind, NO invariants/web/session/bot change, NO soak change** (Mind Trick is
an active Event; the flag is ONLY set by it). **REUSE — exhaust-combined-POWER:** the
existing `push_exhaust_combined_cost` (Qui-Gon's Lightsaber LOF_201) gained TWO
additive, serialised fields: **`budget_source="power"`** (a new
`_exhaust_combined_weight(state,ci,ctx)` helper returns effective `compute_power`
instead of printed cost — "combined power of 4 or less"; used in BOTH
`_exhaust_combined_targets`' budget filter AND `SelectUnitToExhaustCombined.apply`'s
decrement, computed BEFORE setting `exhausted`) + **`then_suppress_if_trait="Force"`**
(in `_resolve_exhaust_combined`, iff the controller controls a unit with that trait
via `has_trait`, set `abilities_suppressed=True` on each still-in-play `ctx["chosen"]`
unit). NO new decision kind — the existing `exhaust_combined_cost` kind carries more
ctx. **ENCODING LOF_202** (lof/abilities.py, shipped LOF) = a plain `EventAbility`
whose one no-target `CustomEffect` adapter calls `push_exhaust_combined_cost(budget=4,
budget_source="power", then_suppress_if_trait="Force")` (the Palpatine SOR_135 inline-
push pattern). `controller="any"` (default) — the controller points the exhausts at
enemy units; "any number" includes 0 (`FinishExhaustCombined`). FACE LOF_202==LOFP_17
BYTE-IDENTICAL (verified — same text/cost/aspects) → alias `("LOFP","17") →
("LOF","202")` reprints.py "batch 44". **NO stale test_reprints hardcode this batch**
(grep confirmed no LOF_202/LOFP_17). Tests `TestMindTrick` (8, in
tests/test_lof_cards.py, methods embed lof_202: eligibility capped by COMBINED POWER
[two power-3 enemies, after picking one only 1 budget left → other power-3 excluded];
Force unit → chosen units `abilities_suppressed` + `has_keyword(SENTINEL)` False +
exhausted; NO Force unit → exhausted True but NOT suppressed + keyword intact;
suppression lifts at `_regroup_rollover`; suppressed Scimitar LOF_233 [damaged +3/+0
self-constant] power 6→3 [constant-source guard]; suppressed Grogu SHD_196 `UseAbility`
not offered [arena UseAbility guard]; LOFP_17 alias `get_abilities` equality;
serialises). **⚠️ TEST GOTCHA: `_play_event_from_hand(state, repo, "LOF", "202")`
plays via PlayCard → resolves the EventAbility → pushes the exhaust decision (the
event sits in DISCARD, where `find_instance` still locates the source — the Calculated
Lethality SHD_39 precedent); a freshly-`_place`d unit is READY so eligible to exhaust;
after picking a power-3 unit, 1 budget remains → may still be a decision, so guard
with `if state.pending_decisions: apply(FinishExhaustCombined)`.** **DOCUMENTED
SIMPLIFICATION:** `has_keyword`/`keyword_value` FULLY suppress (all sources incl.
upgrade-granted keywords — a suppressed unit truly has NO keywords), but an attached
upgrade's SELF `StatBonus` (`_upgrade_self_stat_bonus`) is LEFT applying (an upgrade
is a separate card — a niche no power-≤4 Mind-Trick target realistically hits).
**FOLLOW-ON:** the `abilities_suppressed` read-layer is the shared blocker with **Galen
Erso P25_31** — its name-based, includes-OUT-OF-PLAY, persistent "loses all abilities"
is the FUTURE EXTENSION of this same layer (add a name-based + out-of-play matcher +
a persistent [not phase-scoped] suppression source). **REMAINING 5 grp**, all genuine
escalation, the HARD TAIL: Maul C24_6 attack-2 multi-defender combat; Galen P25_31
"lose all abilities" name-based/out-of-play EXTENSION of THIS layer; Amidala SEC_101
interactive mid-combat-damage decision injection; Eye of Aldhani SEC_73 delayed-
schedule + per-enemy pay-or-exhaust pair; Luke J25_4 replacement effect. See
[[reprint-duplicates]].

**STAGE 4 BATCH 43 DONE 2026-07-15 (FRAMEWORK ESCALATION — the
`play_upgrade_from_hand` decision kind: the UPGRADE sibling of the units-only
`play_from_hand` subsystem — "play an upgrade from your hand for free, choosing a
legal host" — plus a completion of `ReturnToHand` for upgrades).** Re-ran
`find_reprints --check` FIRST (was 7, `--check OK`, NO reopen). Surveyed ALL 7
fresh canonicals' `.text` + RE-DERIVED triviality: **NO zero-engine trivial
stragglers** → **no AskUserQuestion fork**; pure escalation. **⚠️ ALL 7 remaining
are flagged balloons/defers** — the escalation phase is now in its hard tail. RE-
DERIVED each for "needs exactly ONE new primitive (rest reuses)": Mind Trick LOF_202
(exhaust-combined-POWER [trivial variant of `exhaust_combined_cost`] + a BROAD
`lose all abilities` read-layer suppression touching ~7-8 ability-read sites —
`has_keyword`/`keyword_value` self+source, `_collect_triggers`, 3× legal_actions
UseAbility, both `_constant_ability_*_bonus`, `_granted_traits` — the "broad read-
layer" every prior batch deferred; still too broad for a card-batch session);
Amidala SEC_101 (interactive damage-prevention = a mid-COMBAT-damage decision
INJECTION into synchronous combat resolution = balloon, even atop B41 `PreventDamage`);
Eye of Aldhani SEC_73 (delayed-action-phase-start schedule + per-enemy pay-or-exhaust
= TWO new pieces); Maul C24_6 (multi-defender combat = balloon); Galen P25_31
(name-based global suppression incl. OUT-OF-PLAY cards = broadest); Luke J25_4
(replacement effect, STOP per rule). **Picked Jabba the Hutt ASH_42** (canonical,
shipped ASH set; 4-cost 2/6 unique Underworld/Hutt, Cunning/Vigilance/Villainy;
"Restore 2 [keyword layer]. When Played: You may return an upgrade to its owner's
hand. If it's returned to your hand, you may play it for free.") — the ONLY remaining
group needing exactly ONE new primitive (the return-upgrade-to-hand half is a small
COMPLETION of the existing `ReturnToHand`, not a second primitive). Cleared **1 grp**
(2 members): needs_encoding **7→6**, already_covered **185→186**, `--check OK`, fast
tier **2423 pass / 0 fail** (118 known WinError-5 web PermissionError errors).

**THE PRIMITIVE — a `play_upgrade_from_hand` decision kind (the upgrade sibling of
the units-only `push_play_from_hand`).** The Daimyo's Palace LAW_20 note explicitly
flagged upgrades-from-hand as unsupported ("play-from-hand plays only units"). Single-
stage host-selection decision (the `move_upgrade`/`pilot_self_attach` shape): the
upgrade is FIXED in the ctx (the just-returned one); the player only picks a host or
declines. (1) `actions.push_play_upgrade_from_hand(s, source_ci, *, upgrade_id,
free=True)` — pushed only when `upgrade_id` is in the controller's hand AND has ≥1
legal host (`_play_upgrade_from_hand_hosts` = `_eligible_upgrade_targets`, so the
upgrade's own "Attach to …" restriction is honoured); decider = source controller.
(2) `PlayUpgradeFromHand(host_id)` — remove the upgrade from hand, **pop the decision
FIRST** (the "pop, then act" gotcha), then `_attach_upgrade(s, ps, upgrade_ci,
host_id)` (free — no cost paid; fires `UpgradePlayed` → the upgrade's OWN WhenPlayed
re-fires on a clean stack) + `DeclinePlayUpgradeFromHand` (the "you may play it for
free"). Both resolve INLINE in Action.apply (the move_upgrade shape; NO central
action registry). (3) legal_actions branch after `pilot_self_attach` = one
`PlayUpgradeFromHand` per legal host + a lone decline. **COMPLETION OF `ReturnToHand`:
`resolver._apply_return_to_hand` gained an UPGRADE-detach branch AT THE TOP** — if the
target ci sits in some host's `attached_upgrades` (an upgrade, NOT an arena unit — the
old arena-removal loop silently missed it and would DOUBLE-HOME it), detach it, clear
damage/exhaust/face_down/cannot_ready, and route to its OWNER's hand (a TokenUpgrade
ceases to exist → discard instead). This is a correctness completion, NOT a second
primitive. **WIRED: `invariants._KNOWN_DECISION_KINDS += "play_upgrade_from_hand"`;
`web/session._PROMPTS` + a `label_for(PlayUpgradeFromHand)` naming the ctx upgrade +
chosen host; `HeuristicBot` dispatch → `_first(legal, "DeclinePlayUpgradeFromHand")`
(DECLINES — re-playing a returned upgrade has no reliable heuristic value / host-
choice+enemy-attach ambiguity, consistent with move_upgrade/pilot_self_attach) +
`DeclinePlayUpgradeFromHand` in `_SAFE_DEFAULT_ORDER`. NO soak change (Jabba is an
active WhenPlayed CustomEffect, not marker-only).** **ENCODING ASH_42**
(promo/abilities.py — ASH cards live in the `promo` module alongside ASH_243/226/18)
= an **optional** `TriggerAbility(WhenPlayed(), effects=[CustomEffect(fn,
target=TargetSpec(controller="any", kind="upgrade"))])` — `kind="upgrade"` enumerates
non-token attached upgrades (excludes tokens, Disabling Fang Fighter SHD_166 conv.),
so the optional trigger auto-declines when none in play. The fn: read the chosen
upgrade's `owner_id`, `_apply_return_to_hand`, then IFF `owner_id ==
source_ci.owner_id` (returned to YOUR hand) push `play_upgrade_from_hand(upgrade_id,
free=True)`. FACE ASH_42==C26_6 byte-identical (aspect-order Cunning/Vigilance vs
Vigilance/Cunning COSMETIC — find_reprints grouped them) → alias `("C26","6") →
("ASH","42")` reprints.py "batch 43". **⚠️ FIXED 2 stale `test_reprints.py`
examples** (`TestVerifyPlayable::test_keyword_deferred_card_with_ability_text_is_
needs_encoding` + `::test_verify_playable_flags_an_injected_bad_keyword_deferred`)
that hardcoded **Jabba ASH_42/C26_6** as their "implemented-keyword-masks-unregistered-
functional-text stays needs_encoding" example (B39 repointed them HERE after The
Stranger LAW_86) — registering ASH_42 broke BOTH; repointed BOTH to **Galen Erso
P25_31/P26_38** (Plot keyword IS in `find_reprints.IMPL_ENGINE_KEYWORDS` + the
unregistered "name a card → loses all abilities" balloon → same shape, stays
needs_encoding). Tests `TestJabbaTheHuttASH42` (6, in tests/test_promo_cards.py
[ASH cards test there], methods embed ash_42: `_apply_return_to_hand` detaches an
attached upgrade → owner hand [unit test of the completion]; return own upgrade →
free-replay decision → PlayUpgradeFromHand re-attaches to a NEW host + leaves hand +
re-logs UpgradePlayed; decline → stays in hand; ENEMY-owned upgrade → goes to P1 hand,
NO free-replay [owner≠controller]; no upgrade in play → optional auto-declines; reprint
C26_6 alias). **⚠️ TEST DRIVER: an optional WhenPlayed with a kind="upgrade"
CustomEffect target = AcceptTrigger → ChooseTarget(upgrade) → AutoResolveEffects (the
fn returns+pushes); loop all three until the play_upgrade_from_hand decision surfaces.
`_attach_upgrade` test helper sets the upgrade `owner_id`; SOR_120 Academy Training =
a plain +2/+2 no-ability non-token upgrade (clean flow), SOR_46 3/7 host, SOR_88 9/9
replay host.** **FOLLOW-ON:** `play_upgrade_from_hand` + `push_play_upgrade_from_hand`
is a reusable "play a specific hand upgrade for free onto a chosen host" seam (the
`free` param is threaded for a future non-free caller); the `_apply_return_to_hand`
upgrade branch now makes `ReturnToHand(kind="upgrade")` correct everywhere. **REMAINING
6 grp**, all genuine escalation, the HARD TAIL — every one is a multi-piece/broad-read-
layer/replacement balloon needing a DEDICATED framework session (Maul C24_6 multi-
defender combat + Amidala SEC_101 interactive-damage-prevention mid-combat injection +
Galen P25_31 + Mind Trick LOF_202 broad "lose all abilities" read-layer + Eye of
Aldhani SEC_73 delayed-schedule-pair + Luke J25_4 replacement). See
[[reprint-duplicates]].

**STAGE 4 BATCH 42 DONE 2026-07-15 (FRAMEWORK ESCALATION — the `capture_or_ready`
decision kind: an OPPONENT-decided "give up a non-leader unit to be captured by
the source, OR I ready" — the deciding-player shift of each_player_defeats /
opponent_chooses_target, but with a capture-or-ready payoff the opponent MAY
decline).** Re-ran `find_reprints --check` FIRST (was 8, `--check OK`, NO reopen).
Surveyed ALL 8 fresh canonicals' `.text` + RE-DERIVED triviality: **NO zero-engine
trivial stragglers** → **no AskUserQuestion fork**; pure escalation. **⚠️ Luke J25_4
has EMPTY `.text` but is NOT trivial — its `epic_action` field carries a REAL
replacement effect** ("Piloting […] / If this upgrade would be defeated, you may
instead move him to the ground arena as a unit and exhaust him") → confirmed DEFER
per the escalation rule ("replacement-effect system must STOP"). **Picked Grand
Admiral Thrawn SEC_193** (canonical, shipped Secrets of Power; 7-cost 8/7 unique
Imperial/Official; "When Played: An opponent may choose a non-leader unit they
control. If they do, this unit captures that unit. If they don't, ready this unit. /
When Defeated: A friendly unit captures an enemy non-leader unit in the same
arena.") — **the CAPTURE PRIMITIVE ALREADY EXISTS** (`_apply_capture` /
`_release_captured_cards` / `CaptureUnit`, the-mandalorian:07 / moff-gideon:07), so
Thrawn is ONE new decision kind + a COMPOSITION. **KEY SCOPING INSIGHT that keeps it
to ONE primitive: the WhenDefeated needs NO new decision kind — it is the two-
dependent-CustomEffect `event_ctx`-threading pattern (Haymaker LAW_168 / Double-Cross
LAW_170) reusing the existing `same_arena_as_event` predicate + `_apply_capture`.**
Rejected the 7 others as genuine multi-piece/broad: Maul C24_6 attack-2 (multi-
defender combat), Galen P25_31 + Mind Trick LOF_202 ("lose all abilities" broad
read-layer), Amidala J25_16/SEC_101 (INTERACTIVE damage-prevention = a mid-combat-
damage decision INJECTION into combat resolution = balloon), Eye of Aldhani SEC_73
(delayed-schedule + per-enemy pay-or-exhaust PAIR), Jabba ASH_42 (upgrade-return +
free-play-upgrade-from-hand PAIR), Luke J25_4 (replacement). Cleared **1 grp** (2
members): needs_encoding **8→7**, already_covered **184→185**, `--check OK`, fast
tier **2414 pass / 0 fail** (118 known WinError-5 web PermissionError errors).

**THE PRIMITIVE — a `capture_or_ready` decision kind (WhenPlayed) + a WhenDefeated
COMPOSITION (no new kind).** (1) `actions.push_opponent_capture_or_ready(s,
source_ci)` — decider = the OPPONENT of source.owner (the each_player_defeats
TWI_238 / opponent_chooses_target SHD_246 deciding-player shift); eligible =
opponent's non-Leader arena units (`_capture_or_ready_targets`, isinstance(Leader)
exclusion = `non_leader`). **If the opponent has NO non-leader unit → they "can't
choose" so "they don't" → the source READIES INLINE (`source_ci.exhausted=False`),
NO decision pushed.** Else push `PendingDecision(kind="capture_or_ready",
deciding_player_id=opponent, after_resolve_player_index=controller)`. (2) Actions
`ChooseCaptureVictim(target_id)` (opponent picks own non-leader → pop, then
`_apply_capture(captor=source_id, target)` — the "pop, then act" gotcha; Thrawn
stays exhausted on the capture branch) + `DeclineCaptureVictim` (→ pop, then ready
the source). Both resolve INLINE in the Action.apply (the ChooseUnitToDefeat shape;
NO central action registry — actions self-dispatch via `.apply()`, only referenced
by class-name in the bot). (3) legal_actions `capture_or_ready` branch = one
`ChooseCaptureVictim` per eligible + a lone `DeclineCaptureVictim` ("an opponent MAY
choose"). **WhenDefeated = two dependent CustomEffects sharing the resolve_effects
`event_ctx`:** effect 1 `CustomEffect(_thrawn_record_captor, target=friendly unit)`
records `event_ctx["thrawn_captor_id"]` + `["same_arena"]` (ground/space of captor);
effect 2 `CustomEffect(_thrawn_capture_enemy, target=enemy unit,
predicates=("non_leader","same_arena_as_event"))` calls `_apply_capture(captor=
recorded, target)`. Each mandatory-if-able (no friendly unit ⇒ nothing; captor in an
arena with no enemy non-leader ⇒ effect 2 fizzles — the documented minor sequencing
deviation of the two-CustomEffect pattern). **Thrawn is out of the arena (in
discard) when WhenDefeated resolves → never the captor; friendly/enemy resolve via
`source.owner_id` (Scarif Lieutenant LAW_142 precedent, works from discard).**
**WIRED: `invariants._KNOWN_DECISION_KINDS += "capture_or_ready"`; `web/session._PROMPTS`;
`HeuristicBot._choose_capture_or_ready` (as the deciding OPPONENT: ALWAYS DECLINE —
declining only readies an already-in-play enemy unit; giving up your own unit is a
real material loss) + `DeclineCaptureVictim` in `_SAFE_DEFAULT_ORDER`. NO soak change
(Thrawn is active WhenPlayed/WhenDefeated CustomEffects, not marker-only).**
**ENCODING SEC_193** (sec/abilities.py, CaptureUnit already imported there) = two
`TriggerAbility`s: `WhenPlayed` with one no-target `CustomEffect(_thrawn_capture_or_ready)`
inline-push (Palpatine SOR_135; MANDATORY from the controller's side — the "may" is
the opponent's, inside the decision), + `WhenDefeated` with the two dependent
CustomEffects. FACE SEC_193==P25_33 byte-identical → alias `("P25","33") →
("SEC","193")` reprints.py "batch 42". **NO stale test_reprints hardcode this batch**
(grep confirmed no SEC_193/P25_33). Tests `TestGrandAdmiralThrawnSEC193` (8, in
tests/test_law_cards.py [SEC lives there], methods embed sec_193: WhenPlayed decision
decided by OPPONENT P1; opponent gives up unit → Thrawn captures it into P0's
capture_pile + Thrawn STAYS exhausted; opponent declines → Thrawn readies, no
capture; no opponent unit → readies inline, no decision; WhenDefeated friendly captor
captures same-arena enemy into captor's-controller capture_pile; only same-arena
enemy offered [ground captor → space enemy excluded]; no friendly unit → no capture;
reprint alias). **⚠️ TEST GOTCHA: a freshly-played unit is EXHAUSTED — set
`ci.exhausted=True` after `_place` (which places READY) to observe the "ready this
unit" branch (the LAW_80 pattern); drain AutoResolveEffects until the inline-push
appears; `_fire_unit_defeated` (test_law_cards helper) homes the defeated card in
owner discard so friendly/enemy targeting works.** **FOLLOW-ON:** `capture_or_ready`
+ `push_opponent_capture_or_ready` is a reusable "opponent gives up a unit to be
captured OR the source readies" seam; the WhenDefeated pattern (choose captor + same-
arena target via two CustomEffects) is a reusable "a chosen friendly unit captures a
chosen enemy" recipe needing no new kind. **REMAINING 7 grp**, all genuine escalation
(Maul C24_6 attack-2 multi-defender combat + Galen/Mind Trick "lose all abilities"
broad read-layer + Amidala interactive damage-prevention + Eye of Aldhani delayed-
pair + Jabba ASH_42 upgrade-return-pair + Luke J25_4 replacement). See
[[reprint-duplicates]].

**STAGE 4 BATCH 41 DONE 2026-07-15 (FRAMEWORK ESCALATION — the ability-damage-
prevention primitive: a `PreventDamage` passive marker read at the single
`_apply_deal_damage` chokepoint — a friendly Creature's ABILITY damage to a
friendly unit is dropped).** Re-ran `find_reprints --check` FIRST (was 9,
`--check OK`, NO reopen). Surveyed ALL 9 fresh canonicals' `.text` + RE-DERIVED
triviality: **NO zero-engine trivial stragglers** → **no AskUserQuestion fork**;
pure escalation. **⚠️ STALE-ROADMAP REOPEN (the point of re-deriving): Malakili
LOF_108 was memory-flagged a damage-prevention BALLOON "needs a 2nd primitive",
but its "first Creature unit costs 1 less" half is NOW `StandingPlayDiscount`
(B31), so its ONLY remaining piece is the passive damage-prevention → it became a
clean SINGLE-primitive build.** **Picked Malakili LOF_108** (2-cost 1/4 Underworld;
"The first Creature unit you play each phase costs 1 resource less. / If a friendly
Creature unit would deal damage to a friendly unit, prevent that damage.") — the
cleanest genuine single new primitive left. **KEY INSIGHT that shrinks it: combat
damage is ALWAYS attacker-vs-enemy, so a friendly Creature can deal to a *friendly*
unit only via an ABILITY → the single `_apply_deal_damage` sink, NO combat-pipeline
hook.** Rejected: Amidala SEC_101 damage-prevention (INTERACTIVE — "you may defeat a
friendly unit sharing a trait; if you do, prevent" = a mid-damage DECISION = a 2nd
primitive), Maul C24_6 attack-2 (multi-defender combat model), Thrawn SEC_193 (two
capture flows), Eye of Aldhani SEC_73 (delayed-schedule + pay-or-exhaust pair),
Galen P25_31 + Mind Trick LOF_202 ("lose all abilities" broad read-layer change),
Jabba ASH_42 (upgrade-return + free-replay pair), Luke J25_4 (replacement/empty
text). Cleared **1 grp** (2 members): needs_encoding **9→8**, already_covered
**183→184**, `--check OK`, fast tier **2403 pass / 0 fail** (118 known WinError-5
web PermissionError errors).

**THE PRIMITIVE — a `PreventDamage(source_traits)` bare passive marker + a
`resolver._damage_prevented` read at `_apply_deal_damage` + an optional `source_id`
param threaded from the two execute_effect damage arms.** (1) New marker
`registry.PreventDamage(source_traits: tuple = ())` (the `AttackRestriction`/
`IndirectDamageBonus`/`EntersPlayReady` family — `@dataclass(frozen=True)`). (2)
`resolver._apply_deal_damage` gained an optional `source_id: str|None = None` param;
`execute_effect`'s **DealDamage** AND **DealDamageEqualTo** arms now pass
`source_id=source_ci.instance_id` (alongside the existing `dealer_id=owner_id`).
(3) `resolver._damage_prevented(state, source_id, target_ps, target_ci)` — True when
the SOURCE (a unit its controller controls, whose `traits.get_traits` ⊇ the marker's
`source_traits`) and the TARGET are BOTH controlled by the SAME player who holds a
matching `PreventDamage` marker in their arenas. **`source_id` None (unthreaded
callers — the damage-DECISION resolvers in actions.py: distribute/select/sacrifice/
opponent_chooses/indirect — never pass it) → NOT prevented (conservative; no shipped
Creature routes friendly-fire through those).** (4) Integrated in `_apply_deal_damage`
**right after `find_instance`, BEFORE `_record_noncombat_damage`**, guarded
`not isinstance(ci.card_def, Base)` — so a prevented hit logs NO `DamageDealt`, records
NO non-combat damage (WhenDealNonCombatDamage does not fire), and triggers no defeat.
**⚠️ ONLY UNIT TARGETS guarded** (Malakili says "a friendly unit", not a base — bases
never prevented). Combat (`_deal_damage_with_shield` in `_resolve_unit_combat`) and
indirect (`_apply_indirect_damage`, enemy source + "unpreventable") are untouched.
**REUSE: `StandingPlayDiscount` extended trivially** — `_card_matches_standing_discount`
gained an `applies_to="creature_unit"` branch (printed `card_def.traits` contains
"Creature"); Malakili's discount uses `once_per_round=True` since there's ONE ACTION
phase/round (Max Rebo LAW_72 adds only an extra *regroup*), so "first Creature each
phase" == "each round" for plays (documented in the branch). **NO new decision kind,
NO invariants/web/session/bot change** (purely a read at the damage sink + a marker).
Added `PreventDamage` to soak.py's passive-marker import + tuple (Malakili's ONLY
registered specs are the two markers → must not be a false zero-fire). **ENCODING
LOF_108** (lof/abilities.py, shipped LOF) = `[StandingPlayDiscount(1, "creature_unit",
once_per_round=True), PreventDamage(("Creature",))]` (imported StandingPlayDiscount +
PreventDamage into the lof registry block). FACE LOF_108==LOFP_7 (identical text) →
alias `("LOFP","7") → ("LOF","108")` reprints.py "batch 41". **NO stale test_reprints
example hit this batch** (grep confirmed no LOF_108/LOFP_7 hardcode). Tests
`TestMalakiliLOF108` (7, methods embed lof_108: friendly-Creature→friendly-unit
PREVENTED; no-Malakili→lands; non-Creature-source→lands; Creature→ENEMY-unit lands
[friendly-fire only]; Creature→base lands [units only]; first-Creature `_standing_play_discount`
returns 1 while non-Creature 0; reprints alias). **⚠️ TEST GOTCHA: a small-HP target
gets DEFEATED by the test damage and leaves the arena → `_find_instance` returns None**;
use a sturdy target (SOR_46 3/7 survives 2–3 dmg). **FOLLOW-ON:** `PreventDamage` +
`_damage_prevented` + the `source_id` thread is a reusable "prevent ability damage from
X-trait units to friendly units" seam; a FUTURE session builds the INTERACTIVE variant
(damage-time decision) for Amidala SEC_101 (Spy tokens = CreateTokenUnit reuse + the
optional-defeat-cost prevention). **REMAINING 8 grp**, all genuine escalation (Amidala
damage-prevention-with-cost + Galen/Mind Trick "lose all abilities" + Maul C24_6
attack-2 + Thrawn SEC_193 two-capture + Eye of Aldhani SEC_73 delayed-pair + Jabba
ASH_42 upgrade-return-pair + Luke J25_4 replacement). See [[reprint-duplicates]].

**STAGE 4 BATCH 40 DONE 2026-07-15 (FRAMEWORK ESCALATION — the extra-regroup-phase
turn-structure primitive: an `ExtraRegroupPhase` passive marker + a
`GameState.regroup_count_this_round` counter, read at the regroup-rollover site — a
SECOND regroup phase runs each round while a Max Rebo is in play).** Re-ran
`find_reprints --check` FIRST (was 10, `--check OK`, NO reopen). Surveyed ALL 10
fresh canonicals' `.text` + RE-DERIVED triviality: **NO zero-engine trivial
stragglers** → **no AskUserQuestion fork**; pure escalation. Buildable single-primitive
set = C24_6 Maul "attack 2 units" (multi-defender combat composition), SEC_193 Thrawn
(2 capture decision flows), LAW_72 Max Rebo (extra regroup phase / turn loop), SEC_73
Eye of Aldhani (delayed-schedule + pay-or-exhaust PAIR). **Picked Max Rebo LAW_72**
"Encore!" (4-cost Unit; "There is an additional regroup phase after the first regroup
phase each round") — the ONLY remaining group that is genuinely ONE self-contained
primitive touching neither combat nor a new decision kind, with the strongest no-op
safety property (zero effect unless a Max Rebo is in play). Rejected: C24_6 (attack-2
= multi-defender combat, must compose Overwhelm/Sentinel/shields/FS/redirect[B38]/
defender-first[B39] across 2 defenders — balloon-risk, deferred by B38/B39), Thrawn
(TWO capture flows = 2 primitives), Eye of Aldhani (2 unbuilt pieces), the balloon
pairs (Galen P25_31 + Mind Trick LOF_202 ability-loss; Malakili LOF_108 + Amidala
J25_16/SEC_101 damage-prevention), Jabba ASH_42 return-upgrade balloon, Luke J25_4
replacement (empty `.text`). Cleared **1 grp** (3 members): needs_encoding **10→9**,
already_covered **182→183**, `--check OK`, fast tier **2393 pass / 0 fail** (118 known
WinError-5 web PermissionError errors).

**THE PRIMITIVE — a turn-structure marker + a per-round regroup counter.** (1) New
bare passive marker `registry.ExtraRegroupPhase()` (the `AttackRestriction`/
`EntersPlayReady`/`ReadyRestriction` family — `@dataclass(frozen=True)`, NO fields),
read only at the regroup-rollover site. (2) New serialised `GameState.regroup_count_this_round: int`
(state.py; to_dict/from_dict back-compat default 0) — incremented at the TOP of
`_enter_regroup`, reset to 0 at the true round rollover. (3) **Split the monolithic
`_end_regroup` into `_ready_all_cards(s)` + `_regroup_rollover(s)`:** `_end_regroup`
now = call `_ready_all_cards`, then **if `not is_terminal() and regroup_count_this_round
< 2 and _extra_regroup_active(s)`: re-enter `_enter_regroup(s)` and RETURN** (draws 2
more + re-resource + refire the regroup-start `PhaseStartTrigger`s — the Contracted
Hunter JTL_216 site); **else: `_regroup_rollover(s)`** (expire this_round mods, clear
round/phase GameMemory, `round_number += 1`, phase=ACTION, reset passed_players/
initiative_claimed, RoundStarted bus fire, `regroup_count_this_round = 0`).
`actions._extra_regroup_active(s)` = scan both players' ground+space arenas for a unit
whose `get_abilities(sc,cn)` includes an `ExtraRegroupPhase` marker (the `_attack_forbidden`
scan shape). A STATIC condition, NOT additive — the `< 2` cap yields EXACTLY one extra
regroup regardless of copies. **KEY FAITHFULNESS — the `cannot_ready_this_round` clear
MOVED from the ready loop to the rollover:** `_ready_all_cards` now SKIPS a flagged unit
(`continue`) but does NOT clear the flag (No Good to Me Dead SOR_186 must stay exhausted
through BOTH regroups); `_regroup_rollover` clears the flag on all cards. `granted_bounties`
clearing (The Client SHD_31 "for this phase") likewise moved to rollover. **⚠️ VERIFIED
byte-identical for the no-Max-Rebo case** (single ready-step → single rollover, flag
skipped-then-cleared at the same round transition as before). `_ready_forbidden` (Leia
LOF_98) stays a persistent re-evaluated skip (no clear) at each ready. **NO new decision
kind** (reuses the existing RegroupResource/SkipResource flow) → **NO invariants/web/
session/bot change** (round_number stays constant across the two regroups so the
"this_round mods survive rollover" / "phase GameMemory empty after rollover" invariants
never false-positive between them; this_round mods + memory expire only at the true
rollover). Added `ExtraRegroupPhase` to soak.py's passive-marker tuple (Max Rebo's ONLY
registered spec is this marker → must not be a false zero-fire). **ENCODING LAW_72**
(law/abilities.py, shipped LAW) = `ExtraRegroupPhase()` — a lone bare marker (Max Rebo
is vanilla-stat otherwise). FACE LAW_72==P26_82==P26_98 (find_reprints already grouped) →
aliases `("P26","82")/("P26","98") → ("LAW","72")` reprints.py "batch 40". **⚠️ FIXED 1
stale `test_reprints.py::TestApplyGuard::test_unregistered_canonical_raises`** that
hardcoded Max Rebo LAW_72/P26_82 as its "neither-registered needs_encoding" example
(repointed there in B35 after Always Two) — registering LAW_72 broke it; repointed to
**Darth Maul C24_6/P25_91** (still needs_encoding, same face, the attack-2 escalation).
Tests `TestMaxReboLAW72` (5, methods embed law_72: two-regroups-draws-double [count 1→2
mid-round, rollover to round 2 with counter reset, drew 4]; no-Max-Rebo single-regroup
byte-identical [drew 2, round 2]; cannot_ready stays exhausted through BOTH regroups +
flag cleared only at rollover; regroup_count serialises mid-second-regroup; reprints
alias). **⚠️ TEST GOTCHA: `_make_state()` decks are EMPTY** — regroup draws hit the
empty-deck 3-dmg/card base penalty; a `_stock(state, repo)` helper pushes 8 SOR_46 onto
each deck first (and `repo` is a module-scoped fixture, so it must be PASSED IN, not
called). **FOLLOW-ON:** `ExtraRegroupPhase` + the `_ready_all_cards`/`_regroup_rollover`
split is a reusable turn-structure seam (any future "additional <phase>" card); the
split cleanly separates the per-regroup ready step from the once-per-round rollover.
**REMAINING 9 grp**, all genuine escalation (the two BALLOON pairs + Luke J25_4
replacement still deferred; buildable ones left = Maul C24_6 attack-2, Thrawn SEC_193
two-capture, Eye of Aldhani SEC_73 delayed-schedule pair). See [[reprint-duplicates]].

**STAGE 4 BATCH 39 DONE 2026-07-14 (FRAMEWORK ESCALATION — defender-first-strike:
a `this_attack` `CardInstance.defender_deals_first` bool flag on the attacker, read
at the unit-combat damage step — the MIRROR of attacker First Strike).** Re-ran
`find_reprints --check` FIRST (was 11, `--check OK`, NO reopen). Surveyed ALL 11
fresh canonicals' `.text` + RE-DERIVED triviality: **NO zero-engine trivial
stragglers** → **no AskUserQuestion fork**; pure escalation. Buildable single-primitive
set = C24_6 Maul "attack 2 units" (combat target-count), SEC_193 Thrawn (2 capture
decision flows), LAW_72 Max Rebo (turn loop / extra regroup), SEC_73 Eye of Aldhani
(delayed-scheduling PAIR), LAW_86 The Stranger (defender-first-strike). **Picked The
Stranger LAW_86** (tie-break 1: closest mirror to batch-38's OnAttack `this_attack`-flag
shape — the "you may" is a no-target optional OnAttack, minus B38's target) — 5-cost
**1/7** Ground, Cunning/Vigilance/Villainy, Ambush+**Grit**=keyword layer; "While
attacking, you may have the defending unit deal combat damage before this unit."
Rejected: C24_6 (attack-2 = target-count change to the attack model), Thrawn (TWO
capture decision flows), Max Rebo (turn loop), Eye of Aldhani (delayed scheduling +
pay-or-exhaust = 2 unbuilt pieces), balloons/replacement (Galen P25_31 + Mind Trick
LOF_202 ability-loss; Malakili LOF_108 + Amidala SEC_101 damage-prevention; Jabba
ASH_42 return-upgrade; Luke J25_4 replacement). Cleared **1 grp** (2 members):
needs_encoding **11→10**, already_covered **181→182**, `--check OK`, fast tier **2382
pass / 0 fail** (118 known WinError-5 web PermissionError errors).

**THE PRIMITIVE — a `this_attack`-scoped `CardInstance.defender_deals_first: bool`**
(state.py; serialised to_dict/from_dict, back-compat default False — the
`combat_damage_redirect_to`/`cannot_ready_this_round` transient-instance-field pattern).
Set on the ATTACKER by the optional OnAttack CustomEffect (the Accept path); read via
new `actions._defender_deals_first(attacker)` at `_resolve_unit_combat_step2` step 4 as a
NEW **`elif` branch BETWEEN** `_attacker_has_first_strike` and the simultaneous `else`:
the defender's combat damage lands on the attacker FIRST (via `_apply_attacker_combat_damage`,
so the B38 redirect still composes); if that defeats the attacker, `dealt_to_defender=0`
(attacker deals nothing back) — the exact mirror of the attacker-FS branch. Attacker-FS
wins a (contradictory, no-card) tie. **KEY FAITHFULNESS — Grit recompute:** in the
survive sub-branch, `atk_power` is **RE-computed AFTER** the attacker takes the defender's
hit (not the step-3 snapshot), so a Grit attacker's power grows from that incoming damage
before it swings back — the WHOLE POINT of choosing defender-first for The Stranger (1
power + Grit: taking 2 → power 3 → kills a 3-hp defender it otherwise couldn't). **CLEAR
+ DRIVE-BY FIX:** new `actions._clear_this_attack_combat_flags(attacker)` clears BOTH
`combat_damage_redirect_to` AND `defender_deals_first`, called at all FOUR attacker-in-scope
this_attack cleanup sites (the two unit-step2 exits + the base-step2 end + the defender-gone
pre_attack fizzle) — this **ALSO closes a latent batch-38 leak**: the base-attack end and
the fizzle paths never cleared `combat_damage_redirect_to`, so a Maul SHD_90 redirect
accepted on a base attack could leak into a later attack. (The attacker-None fizzle can't
clear — moot, the attacker left play.) **NO new decision kind** (reuses trigger_option
Accept/Decline + the pre_attack continuation) → **NO invariants/web/session/bot change**
(soak untouched — The Stranger is an active OnAttack card, not marker-only). **ENCODING
LAW_86** (law/abilities.py, shipped LAW) = optional `TriggerAbility(OnAttack(),
optional=True, effects=[CustomEffect(fn=_the_stranger_law86_defender_first)])`; the
no-target fn sets `source_ci.defender_deals_first = True`. A no-target optional effect is
always offerable, so the "you may" (Accept/Decline) is presented on every attack. FACE
LAW_86==P26_110 (verified: text identical, aspect-order [Cunning,Vigilance vs
Vigilance,Cunning] COSMETIC — find_reprints already grouped them) → alias `("P26","110")
→ ("LAW","86")` reprints.py "batch 39". **⚠️ FIXED 2 stale `test_reprints.py` examples**
(`TestVerifyPlayable::test_keyword_deferred_card_with_ability_text_is_needs_encoding` +
`::test_verify_playable_flags_an_injected_bad_keyword_deferred`) that hardcoded The Stranger
LAW_86/P26_110 as the "keyword-deferred card masking unregistered functional text" example
(repointed there in B30 after Ki-Adi TWI_64) — NOW registering LAW_86 broke them; repointed
BOTH to **Jabba the Hutt ASH_42/C26_6** (Restore keyword implemented + unregistered
return-upgrade balloon = same shape, a deferred balloon that stays needs_encoding). Tests
`TestTheStrangerLAW86` (6, methods embed law_86: OnAttack offers optional trigger + sets
flag + JSON round-trips; defender-first lets Grit-grown power kill the 3-hp Thug [survive
branch, Grit recompute]; declined = simultaneous → Thug survives; defender-first defeats
the Stranger → deals nothing back [First-Strike mirror]; attacking a base clears the flag
[no leak, the drive-by]; reprint P26_110 aliases). **⚠️ TEST GOTCHA: an isolated
`_fire_on_attack`+AcceptTrigger must `_drive_to_quiescence` to run the AutoResolveEffects
that sets the flag** (Accept only pushes resolve_effects); the full-attack `_resolve_attack`
loop already drives it. **FOLLOW-ON:** `defender_deals_first` + the step-4 elif is a
reusable "grant the defender first strike this attack" combat seam; `_clear_this_attack_combat_flags`
is now the single home for all this_attack combat-flag cleanup. **REMAINING 10 grp**, all
genuine escalation (the two BALLOON pairs + Luke J25_4 replacement still deferred). See
[[reprint-duplicates]].

**STAGE 4 BATCH 38 DONE 2026-07-14 (FRAMEWORK ESCALATION — the combat-damage
redirect: a `this_attack` `combat_damage_redirect_to` flag on the attacker, read
at the combat-damage step).** Re-ran `find_reprints --check` FIRST (was 12,
`--check OK`, NO reopen). Surveyed ALL 12 fresh canonicals' `.text` + RE-DERIVED
triviality: **NO zero-engine trivial stragglers** → **no AskUserQuestion fork**;
pure escalation. Single-primitive buildable set = the three combat-pipeline cards
(C24_6 Maul "attack 2 units", SHD_90 Maul redirect, LAW_86 The Stranger
defender-first-strike), Max Rebo LAW_72 (turn loop), Thrawn SEC_193 (2 capture
decision flows). **Picked Maul SHD_90** (tie-break 1: smallest combat surface /
most reuse) — 7-cost 7/6 Ground, Force/Underworld, Ambush+Overwhelm=keyword layer;
"On Attack: You may choose another friendly Underworld unit. If you do, all combat
damage that would be dealt to this unit during this attack is dealt to the chosen
unit instead." The "you may choose" half is a STOCK optional `OnAttack`
`CustomEffect.target` (project_custom_effect_target) — the ONLY new engine piece is
the redirect. Rejected: C24_6 (attack-2 = target-count change to the combat
pipeline), LAW_86 (`_attacker_has_first_strike` exists but defender-first-strike
inverts who-deals-first AND is a mid-combat "you may" → real ordering change), Max
Rebo (turn loop), Thrawn (TWO capture decision flows — WhenPlayed opponent-choose-
own-or-decline + WhenDefeated friendly-captor pick), balloons/replacement/pair
(Galen P25_31, Jabba ASH_42, Luke J25_4, Malakili LOF_108, Mind Trick LOF_202,
Amidala SEC_101, Eye of Aldhani SEC_73). Cleared **1 grp** (4 members):
needs_encoding **12→11**, already_covered **180→181**, `--check OK`, fast tier
**2373 pass / 0 fail** (118 known WinError-5 web PermissionError errors — verified
ALL 118 originate in web/db-fixture modules: test_web_auth/bugs/deckbuilder/
save_replay, test_deckstore, test_audit_images, test_plan_encoding, test_swudb_
import, test_ui_deck_registry, test_verify_encoding, test_build_db_variants).

**THE PRIMITIVE — a `this_attack`-scoped `CardInstance.combat_damage_redirect_to:
Optional[str]` flag** (state.py; serialised to_dict/from_dict, back-compat default
None — the `cannot_ready_this_round`/`defeat_at_regroup`/`return_to_owner_hand_at_
regroup` transient-instance-field pattern). Set on the ATTACKER by the OnAttack
CustomEffect fn = the chosen unit's id; read at the SINGLE combat-damage-to-attacker
line. Two actions.py helpers next to `_deal_damage_with_shield`: (1)
`_combat_redirect_unit(s, active_ps, attacker)` → the friendly redirect CardInstance
via `_find_in_arenas(active_ps, tid)` (the chosen unit is always friendly to the
attacker — "another friendly Underworld unit"), or None if unset/left-play; (2)
`_apply_attacker_combat_damage(s, active_ps, attacker, def_power, redirect)` — if
redirect: deal `def_power` to the redirect unit (its OWN Shield may intercept),
attacker takes 0, **return 0**; else the normal `_deal_damage_with_shield(attacker)`.
Wired at `_resolve_unit_combat_step2` step 4: `redirect = _combat_redirect_unit(...)`
computed once, then BOTH the first-strike-else and the simultaneous
`dealt_to_attacker` lines route through the helper. Flag **cleared at BOTH step2
exits** (the pre-combat early-return at the top + after `_expire_modifiers(s,
"this_attack")` at the end, on the `attacker` object) — this_attack scope, never
leaks to a later attack. **KEY FAITHFULNESS:** redirect happens BEFORE Maul's own
shield (his shield untouched; chosen unit's shield intercepts); `dealt_to_attacker=0`
→ attacker's WhenDealtCombatDamage correctly does NOT fire (took no damage); Maul
still deals his own damage + Overwhelm to the DEFENDER. **DOCUMENTED SIMPLIFICATIONS:**
(a) a WhenDealtCombatDamage on the REDIRECT unit is NOT fired (only Phase-III Dark
Trooper SHD_84 has that trigger; the redirect unit is a friendly Underworld unit —
no shipped card exercises it); (b) a redirect unit defeated by the redirected damage
is homed by the post-action `_sweep_defeated_units` (the HP-drop/off-combatant
defeat path — step 6 checks only the two combatants), which still fires its
WhenDefeated. **NO new decision kind → NO invariants/web/session/bot change** (soak
untouched — Maul is an active OnAttack card, not marker-only). **ENCODING SHD_90**
(shd/abilities.py, shipped SHD) = `TriggerAbility(OnAttack(), optional=True,
effects=[CustomEffect(fn=_maul_shd90_redirect, target=TargetSpec(controller=
"friendly", kind="unit", traits=("Underworld",), predicates=("not_self",)))])`; the
fn sets `source_ci.combat_damage_redirect_to = target_id`. optional=True + a TARGETED
CustomEffect → the optional trigger auto-declines when no other friendly Underworld
unit exists (the standard gate). FACE SHD_90==J24_4==P25_155==P25_165 (all one card;
aspect-list order [Villainy,Command vs Command,Villainy] is COSMETIC — find_reprints
already grouped them) → aliases `("J24","4")/("P25","155")/("P25","165") → ("SHD",
"90")` reprints.py "batch 38". Tests `TestMaulSHD90` (6, methods embed shd_90:
OnAttack sets flag + only-other-Underworld offered + JSON round-trips; redirects
return damage to the chosen unit [survives] + Maul takes 0 + flag cleared + defender
still dies; no-other-Underworld auto-declines → Maul takes damage; declined → Maul
takes damage, chosen untouched; pre-damaged chosen unit defeated by redirected damage
[swept]; reprints alias). **⚠️ TEST GOTCHA: driving a full attack with an OnAttack
DECISION needs an explicit `ContinueAttack` after the trigger resolves** (the
pre_attack continuation — `_resolve_attack` helper loops trigger_option→AcceptTrigger/
DeclineTrigger, pre_attack→ContinueAttack, else→ChooseTarget until settled).
**FOLLOW-ON:** `combat_damage_redirect_to` + `_apply_attacker_combat_damage` is a
reusable "redirect the attacker's incoming combat damage onto a chosen unit"
this-attack seam. **REMAINING 11 grp**, all genuine escalation (the two BALLOON pairs
+ Luke J25_4 replacement still deferred). See [[reprint-duplicates]].

**STAGE 4 BATCH 37 DONE 2026-07-14 (FRAMEWORK ESCALATION — the location-gated
ready restriction: `ReadyRestriction` passive marker + `SOURCE_IN_SPACE_ARENA`
atom).** Re-ran `find_reprints --check` FIRST (was 13, `--check OK`, NO reopen).
Surveyed ALL 13 fresh canonicals' `.text` + RE-DERIVED triviality: **NO
zero-engine trivial stragglers** → **no AskUserQuestion fork**; pure escalation.
**Leverage:** all buildable groups 1-grp/primitive → tie-break 1 (smallest
surface / MOST reuse). **Picked Leia Organa LOF_98** (5/5 unique **Space** unit
[arenas=('Space',)], Command/Heroism; "While this unit is in the space arena, she
can't ready and gains: 'Action [use the Force]: Move this unit to the ground
arena and give each friendly Heroism unit +2/+2 for this phase.'"). She ENTERS in
space (Space unit), stuck there until she spends the Force to jump to ground.
Rejected: combat-pipeline (Maul C24_6 attack-2, Stranger LAW_86 defender-first-
strike, Maul J24_4/SHD_90 redirect — `_attacker_has_first_strike` exists but the
"you may" makes it a mid-combat decision), turn-loop (Max Rebo LAW_72 extra
regroup), balloons (Galen P25_31, Malakili LOF_108, Amidala J25_16, Mind Trick
LOF_202, Jabba ASH_42, Thrawn P25_33 = 2 decision flows), replacement (Luke
J25_4), delayed-scheduling PAIR (Eye of Aldhani SEC_73 = delayed-until-next-action
+ per-enemy pay-or-exhaust, TWO unbuilt pieces). Cleared **1 grp**: needs_encoding
**13→12**, already_covered **179→180**, `--check OK`, fast tier **2358 pass / 0
fail** (118 known WinError-5 web PermissionError errors — verified ALL are
PermissionError).

**THE PRIMITIVE — `ReadyRestriction(condition: ConditionCheck)` passive marker**
(registry.py; the ready-site MIRROR of `AttackRestriction` [Oggdo Bogdo LOF_63,
darth-maul:03]) + one new condition atom **`Condition.SOURCE_IN_SPACE_ARENA`**
(`any(source_ci is ci for ci in ps.space_arena)`). Semantics: the source unit
**can't ready WHILE `condition` holds**. **⚠️ POLARITY IS INVERTED vs
`AttackRestriction`** (which forbids WHILE its condition is FALSE, "can't attack
UNLESS…") — DELIBERATE, so a SINGLE `SOURCE_IN_SPACE_ARENA` atom drives BOTH the
restriction AND the "gains [Action] while in space" gate (no second in-ground
atom). Read via new `actions._ready_forbidden(state, ci)` (scans
`get_abilities(sc,cn)` for a `ReadyRestriction` whose `condition.evaluate` is
True; early-returns no set/number — the `_attack_forbidden` shape) at **the two
ready sites that already honour `cannot_ready_this_round`** (matching its EXACT
coverage): (1) `_end_regroup` (actions.py:9959) — after the cannot_ready block,
before `ci.exhausted=False`, `if _ready_forbidden(s, ci): continue` (persistent,
re-evaluated each regroup, DON'T clear); (2) the `ReadyCard` resolver arm
(resolver.py:1310) alongside the cannot_ready guard (lazy `from swu.engine.actions
import _ready_forbidden`). **SCOPE (documented):** niche ready paths NOT guarded
(the `opponent_ready` ReadyUnit decision; the modal `ready_resource` mode =
resources-only) — same coverage `cannot_ready_this_round` has; no shipped card
readies an enemy's space Leia. Added `ReadyRestriction` to soak.py's passive-marker
tuple (not strictly needed — Leia ALSO has an ActivatedAbility so isn't
marker-only — but future-proofs a marker-only card). **NO new decision kind → NO
invariants/web/session/bot change.** **ENCODING LOF_98** (lof/abilities.py, shipped
LOF) = a LIST `[ReadyRestriction(ConditionCheck(SOURCE_IN_SPACE_ARENA)),
ActivatedAbility(costs=[UseForce()], effects=[CustomEffect(_move_to_ground),
ModifyStats(2,2, TargetSpec(controller="friendly", kind="unit", aspects=
("Heroism",), fixed=EACH_FRIENDLY), THIS_PHASE)], condition=ConditionCheck(
SOURCE_IN_SPACE_ARENA))]`. The move fn mirrors Blue Leader JTL_96's inline
space→ground relocation; the buff REUSES ModifyStats EACH_FRIENDLY+aspects (works
since the Lawbringer LAW_101 bugfix; Leia is herself friendly Heroism → buffed
too, faithful). UseForce cost (qui-gon-jinn:06) makes it affordable only with a
Force token; ActivatedAbility.condition gates availability (project_activated_
ability_condition). Once she reaches ground → SOURCE_IN_SPACE_ARENA False → BOTH
the restriction AND the Action vanish. FACE LOF_98==P25_80==P26_102 byte-identical
(verified) → aliases `("P25","80")/("P26","102") → ("LOF","98")` reprints.py
"batch 37". Tests `TestLeiaOrganaLOF98` (6, methods embed lof_98: can't-ready at
regroup in space [plain space unit DOES ready]; Action offered in-space only WITH
a Force token, not without, gone on ground; use Action → leaves space_arena for
ground_arena + token spent + each friendly Heroism +2/+2 [non-Heroism/enemy
unbuffed] + Action disappears; readies normally after moving to ground;
`_ready_forbidden` True-in-space/False-on-ground + ReadyCard effect can't ready
her in space; reprints alias). **⚠️ TEST GOTCHA: `UseAbility` fields are
`source_id`/`ability_idx` (NOT `instance_id`).** **FOLLOW-ON:** `ReadyRestriction`
+ `SOURCE_IN_SPACE_ARENA` is a reusable "can't ready while <condition>" passive
block (any future such restriction). **REMAINING 12 grp**, all genuine escalation
(the two BALLOON pairs + Luke J25_4 replacement still deferred). See
[[reprint-duplicates]].

**STAGE 4 BATCH 36 DONE 2026-07-14 (FRAMEWORK ESCALATION — the combined-cost-budget
multi-select search-and-play: `push_search_and_play_multiple`).** Re-ran
`find_reprints --check` FIRST (was 14, `--check OK`, NO reopen). Surveyed ALL 14
fresh canonicals' `.text` + RE-DERIVED triviality: **NO zero-engine trivial
stragglers** → **no AskUserQuestion fork**; pure escalation. **Leverage:** all
buildable groups 1-grp/primitive → tie-break 1 (smallest surface / closest mirror,
avoiding combat-pipeline + turn-loop + balloons + replacement). **Picked Darth
Vader SOR_87** "Commanding the First Legion" (7-cost 5/7, Ambush = keyword layer;
"When Played: Search the top 10 cards of your deck for any number of [Villainy]
units with combined cost 3 or less and play each of them for free.") — the ONE new
mechanic is a combined-cost budget on a multi-select search-and-play, a clean
extension of the existing `deck_search` seam. Rejected: combat-pipeline (Maul C24_6,
Stranger LAW_86, Maul J24_4-redirect), turn-loop (Max Rebo LAW_72), balloons (Galen
P25_31, Malakili LOF_108, Amidala J25_16, Mind Trick LOF_202, Jabba ASH_42, Thrawn
P25_33 = 2 new decision flows), replacement (Luke J25_4), delayed-scheduling PAIR
(Eye of Aldhani SEC_73), and Leia LOF_98 (2 weak seams — arena-move is a REUSE of
Blue Leader JTL_96). Cleared **1 grp**: needs_encoding **14→13**, already_covered
**178→179**, `--check OK`, fast tier **2346 pass / 0 fail** (118 known WinError-5
web PermissionError errors — ALL PermissionError, verified).

**THE PRIMITIVE — `push_search_and_play_multiple(s, source_ci, *, window, budget,
eligible)`** (actions.py, next to `push_search_and_play` [Kelleran Beq LOF_100]).
**NO new decision kind — additive fields on the existing `deck_search` decision
kind.** Pushes a `deck_search` decision with `disposition="play"`, **`free=True`**
(each chosen unit played at cost 0), **`budget=int`** (the picked units' combined
*printed* cost cap), `max_select`=#candidates (so the existing auto-finish fires
only when literally everything is taken — a select-all shortcut, no explicit
FinishSearch), `up_to=True` (FinishSearch always offered — "any number" includes 0).
candidate_ids = every card in top `window` matching `eligible` regardless of
individual cost (an over-budget one just never becomes selectable). **3 small edits
to the existing seam:** (1) `_deck_search_actions` — when `ctx["budget"]` set, look
up each candidate's printed cost from `ps.deck` (deck untouched while the decision
is open), compute `spent`=Σ selected costs, drop any offered candidate whose cost >
budget−spent (SET-RELATIVE, like `exhaust_combined_cost`'s budget → belongs in
legal_actions, not a `_spec_matches_ci` predicate); (2) `SelectSearchCard.apply` —
defensive budget guard BEFORE the append (inert when no budget); (3)
`_finish_deck_search` play branch (which already LOOPS over `selected`, paying +
`_put_unit_in_play` for each — Kelleran just never exercised multi) — `cost = 0 if
ctx.get("free") else max(0, _effective_cost − cost_reduction)`. Everything else
(pay, CardPlayed, Villainy tracking, bus fire, bottom-the-rest in seeded-random
order) unchanged. Bot: `_choose_deck_search` already grabs SelectSearchCard whenever
offered (correct — free Villainy units are pure value); no bot/invariants/web change.
**ENCODING SOR_87** (sor/abilities.py, SHIPPED set — NOT the promo; SOR_87 is a
never-before-encoded base-set unit Vader, distinct from the SOR Luke/Vader
LEADERS) = MANDATORY `TriggerAbility(WhenPlayed(), [CustomEffect(fn)])`, the fn a
thin non-targeted adapter (Palpatine SOR_135 inline-push) calling the helper with
`window=10, budget=3, eligible=<Villainy Unit>` (`isinstance(cd, Unit) and Villainy
in aspects`). **DOCUMENTED SIMPLIFICATION:** several units played in one loop
resolve their WhenPlayed triggers LIFO (the engine's standard stacked-trigger
order), not each-fully-before-the-next — all fire, only relative order differs.
FACE SOR_87==C24_2==P25_103 byte-identical (verified) → aliases `("C24","2")/
("P25","103") → ("SOR","87")` reprints.py "batch 36". Tests `TestDarthVaderSOR87`
(5, methods embed sor_87: pushes decision + only Villainy-units-within-budget
offered [rukh cost5 & non-Villainy consular excluded]; budget shrinks as taken
[after a 2-cost, a remaining 2-cost drops, a 1-cost stays]; take-2-within-budget
auto-finishes → both enter play paid 0 + rest bottomed; FinishSearch-with-0 = clean
no-op; reprints alias). **FOLLOW-ON:** `push_search_and_play_multiple` is a reusable
"search top N, play any number matching a filter under a combined-cost budget, for
free" decision. **REMAINING 13 grp**, all genuine escalation (the two BALLOON pairs +
Luke J25_4 replacement still deferred). See [[reprint-duplicates]].

**STAGE 4 BATCH 35 DONE 2026-07-14 (FRAMEWORK ESCALATION — the
`choose_units_sacrifice_rest` decision kind: choose N friendly units, buff each,
defeat all OTHER friendly units).** Re-ran `find_reprints --check` FIRST (was 15,
`--check OK`, NO reopen). Surveyed ALL 15 fresh canonicals' `.text` + RE-DERIVED
triviality: **NO zero-engine trivial stragglers** (choose_two_modal pick=1 covers
none of these) → **no AskUserQuestion fork**; pure escalation. **Leverage:** all
buildable groups 1-grp/primitive → tie-break 1. Rejected: combat-pipeline (Maul
C24_6, Stranger LAW_86), turn-loop (Max Rebo LAW_72), balloons (Galen P25_31,
Malakili LOF_108, Amidala J25_16, Mind Trick LOF_202, Jabba ASH_42), replacement
(Luke J25_4), delayed-scheduling+pay-or-exhaust PAIR (Eye of Aldhani SEC_73),
2-decision-flow (Thrawn P25_33), and Leia LOF_98 (2 weak seams — its arena-move is
a reuse of Blue Leader JTL_96, per B34). **Picked Always Two LOF_42** (Event, cost
4, "Choose 2 friendly unique Sith units. If you do, give 2 Shield + 2 Experience
tokens to each chosen unit. Defeat all other friendly units.") — a single crisp new
self-contained decision kind. Cleared **1 grp**: needs_encoding **15→14**,
already_covered **177→178**, `--check OK`, fast tier **2335 pass / 0 fail** (118
known WinError-5 web errors).

**THE PRIMITIVE — `choose_units_sacrifice_rest` decision kind** (mirror of
`each_player_defeats` TWI_238 "select one at a time → POP → defeat" + `select_token`
recompute-eligible loop): (1) `actions.push_choose_units_sacrifice_rest(s,
source_ci, *, required_count, traits, predicates, tokens=[[name,count],...])` —
scans ONLY the CONTROLLER's arenas (so "friendly" is intrinsic AND the Event
sitting in discard mid-resolution is a non-issue — the select_token fallback
pattern), filtered via `_spec_matches_ci(spec, ci, ci, state, {})`; if
`< required_count` eligible → **NOT pushed** (the "If you do" fails cleanly — no
defeats). (2) `ChooseUnitToSpare(target_id)` — appends to `chosen`; auto-resolves
when `len(chosen)==required_count`. **NO decline** (mandatory "Choose 2"). (3)
`_resolve_choose_units_sacrifice_rest(s, top)` — POP first, then `tokens.attach_token`
each chosen unit its tokens, then snapshot + `_apply_defeat_unit` every unit in the
controller's arenas NOT in chosen ("all other friendly units", BOTH arenas; a
deployed friendly leader is a unit → defeated back to base, faithful). "pop, then
defeat" so WhenDefeated lands clean. (4) legal_actions arm kind ==
`choose_units_sacrifice_rest`. **SUPPORTING SEAM:** new `unique` target predicate in
`resolver._spec_matches_ci` (inverse of existing `non_unique`; the `<uq>` symbol =
"unique Sith units"). Wired: `invariants._KNOWN_DECISION_KINDS`; `web/session._PROMPTS`;
`HeuristicBot._choose_units_sacrifice_rest` (spare the highest-`_card_value` unit each
step — keep its best 2; no Finish action → no `_SAFE_DEFAULT_ORDER` entry). **ENCODING
LOF_42** (lof/abilities.py, shipped set) = `EventAbility([CustomEffect(fn)])`, the fn a
thin non-targeted adapter (Palpatine SOR_135 inline-push) calling the push helper with
`required_count=2, traits=["Sith"], predicates=["unique"],
tokens=[["Shield",2],["Experience",2]]`. FACE LOF_42==P26_73==P26_89 byte-identical
(verified) → aliases `("P26","73")/("P26","89") → ("LOF","42")` reprints.py "batch 35".
**⚠️ FIXED 1 stale `test_reprints.py::TestApplyGuard::test_unregistered_canonical_raises`**
that hardcoded Always Two LOF_42/P26_73 as its "neither-registered needs_encoding"
example (the SAME batch-30 stale-example hazard) — repointed to **Max Rebo LAW_72/P26_82**
(still needs_encoding, same face). Tests `TestAlwaysTwoLOF42` (4, methods embed lof_42:
pushes decision + only unique Sith eligible to spare; buff-2-defeat-rest [chosen get
2 shield/2 exp, other friendlies incl. 3rd Sith/non-Sith-unique/non-unique defeated,
enemy untouched]; fizzles with <2 unique Sith [no push, nothing dies]; reprints alias).
**FOLLOW-ON:** `push_choose_units_sacrifice_rest` is a reusable "choose N units, buff
them, defeat the rest" decision. **REMAINING 14 grp**, all genuine escalation (the two
BALLOON pairs + Luke J25_4 replacement still deferred). See [[reprint-duplicates]].

**STAGE 4 BATCH 34 DONE 2026-07-14 (FRAMEWORK ESCALATION — the attach-an-in-play-
unit-as-a-Pilot-upgrade primitive: a unit-becomes-upgrade relocation).** Re-ran
`find_reprints --check` FIRST (was 16, `--check OK`, NO reopen). Surveyed ALL 16
fresh canonicals' `.text` + RE-DERIVED triviality: **NO zero-engine trivial
stragglers** (Malakili LOF_108's "first Creature costs 1 less" half is NOW covered
by `StandingPlayDiscount` B31, but its damage-prevention half still BALLOONS) → **no
AskUserQuestion fork**; pure escalation. **Leverage:** all buildable groups
1-grp/primitive → tie-break 1 (smallest surface / closest mirror, avoiding
combat-pipeline + turn-loop). **⚠️ KEY SURVEY FINDING: Blue Leader JTL_96
(han-solo:04) ALREADY does inline space→ground arena relocation, so Leia LOF_98's
"move to ground arena" is a REUSE** — Leia's only NEW pieces = a diffuse
in-space-arena condition atom + a can't-ready-while-in-space constraint (2 weak
seams) → REJECTED Leia for a crisper single primitive. **Picked Poe Dameron JTLP_6**
(promo canonical) — every piece EXISTS except the self-as-pilot relocation:
`CreateTokenUnit` (X-Wing = TokenUnit JTL_2, Vehicle/Fighter 2/2),
`WhenPlayed(as_unit=True)` (Mandalorian JTL_210), `_vehicle_has_pilot`/no-pilot
(Commandeer JTL_235). Cleared **1 grp**: needs_encoding **16→15**, already_covered
**176→177**, `--check OK`, fast tier **2325 pass / 0 fail** (118 known WinError-5
web errors).

**THE PRIMITIVE — `pilot_self_attach` decision kind** (the sibling of `_attach_pilot`
[attaches a HAND unit as pilot] and `_relocate_upgrade` [move_upgrade,
the-mandalorian:06 — a relocation, NO WhenPlayed re-fire]): (1)
`actions.push_attach_unit_as_pilot(s, source_ci)` — eligible hosts = the source
controller's Vehicles with NO pilot (`not _vehicle_has_pilot`), excluding source; if
none → **NO decision** (the "you may" auto-skips cleanly). (2) `AttachSelfAsPilot(
vehicle_id)` / `DeclineAttachSelfAsPilot` (the "you may"). (3)
`_attach_unit_as_pilot(s, unit_id, vehicle_id)` — find unit in an arena, strip its
attached upgrades (tokens vanish, real → owner discard — defensive, normally empty
for a freshly-played unit), reset (damage=0/exhausted=False/face_down=False/
deployed=False), remove from arena, `zone = host.zone`, append to
`host.attached_upgrades`; **appends an `UpgradePlayed` to event_log for UI animation
but does NOT fire it** (a relocation, NO WhenPlayed re-fire — mirror
`_relocate_upgrade`). The unit's `upgrade_power`/`upgrade_hp` (Poe 2/3) buff the host
via the existing compute_power/hp `getattr(card_def,"upgrade_power")` reads; on the
host's defeat `_defeat_unit` detaches Poe (a non-token Unit) → owner's discard
(existing pilot behaviour). Restore active_player guarded `if not pending_decisions`
(inline-push, so a buried resolve_effects after_resolve isn't clobbered — mirror
MoveUpgradeTo). **NO registry/state/resolver change** (no new spec, **NO new serialised
field**, no trigger). **ENCODING JTLP_6** (promo/abilities.py, Krennic JTLP_1 precedent)
= mandatory `TriggerAbility(WhenPlayed(as_unit=True), [CustomEffect(fn=_poe_jtlp6)])`
— fires ONLY when Poe is played as a unit (not via his own Piloting); the fn creates
the X-Wing inline (`_create_token_units`) then `push_attach_unit_as_pilot` — **the
X-Wing (a Vehicle) is itself a legal host, so Poe hops onto the token he just made.**
The create is mandatory; the attach is "you may" via the decline. Wired:
`invariants._KNOWN_DECISION_KINDS += "pilot_self_attach"`; `web/session._PROMPTS`;
`HeuristicBot` DECLINES (no reliable heuristic — attaching trades a body for a buff;
the move_upgrade bot also declines) + `DeclineAttachSelfAsPilot` in
`_SAFE_DEFAULT_ORDER`. FACE JTLP_6==P25_90 byte-identical (verified) → alias
`("P25","90") → ("JTLP","6")` reprints.py "batch 34". Tests `TestPoeDameronJTLP6`
(6, methods embed jtlp_6: played-as-unit creates X-Wing + offers attach; attach onto
X-Wing → Poe leaves arena as a Pilot upgrade, host 4/5; decline keeps Poe a unit;
no-Vehicle-host push helper no-ops; host defeat → Poe to owner discard; reprint
P25_90 aliases). **FOLLOW-ON:** `push_attach_unit_as_pilot` is a reusable "convert an
in-play unit into a Pilot upgrade" relocation. **REMAINING 15 grp**, all genuine
escalation (the two BALLOON pairs + Luke J25_4 replacement still deferred). See
[[reprint-duplicates]].

**STAGE 4 BATCH 33 DONE 2026-07-14 (FRAMEWORK ESCALATION — the source-linked
control-revert primitive: a control change that AUTO-REVERTS when its source unit
leaves play).** Re-ran `find_reprints --check` FIRST (was 17, `--check OK`, NO
easy-phase reopen). Surveyed ALL 17 fresh canonicals' DB `.text` + RE-DERIVED
triviality: **NO zero-engine trivial stragglers remain** → **no AskUserQuestion
fork**; pure escalation. **Leverage:** all 17 are 1-grp/primitive → tie-break 1
(smallest surface / closest mirror, avoiding combat-pipeline + turn-loop groups).
**Picked Maul LAW_54** "Master of the Shadow Collective" (7-cost 6/8, Overwhelm =
keyword layer) — every piece EXISTS except the revert-on-leave linkage: WhenAttackEnds
(Vermillion LAW_215), the base-damage event flag (Ketsu Onyo SHD_147), `change_control`
(Stolen Landspeeder SHD_161), CustomEffect.target (Vader's Lightsaber SOR_136). Chose
it over **Jabba ASH_42** (return-upgrade + replay-if-yours = 2 unbuilt primitives — the
free-play-upgrade-from-hand path doesn't exist → BALLOON, defer). Cleared **1 grp**:
needs_encoding **17→16**, already_covered **175→176**, `--check OK`, fast tier **2316
pass / 0 fail** (118 known WinError-5 web errors).

**THE PRIMITIVE — source-linked control revert** (mirror of the `permanent`-modifier
cleanup Huyang TWI_110 / the capture `_release_captured_cards` leave-play linkage):
(1) new serialisable `CardInstance.control_linked_to: Optional[str]` (state.py; the
SOURCE unit's instance_id; to_dict/from_dict back-compat default None). (2)
`actions._revert_linked_control(s, source_ci)` — collect every in-play unit whose
`control_linked_to == source.instance_id`, clear the flag, `change_control(back to
owner_id)`; **called in `_defeat_unit` right after `_release_captured_cards`** (the
capture leave-play precedent). **SCOPE LIMITATION (documented, matches capture):**
wired into `_defeat_unit` ONLY — a source bounced/put-on-deck/captured while holding a
linked unit does NOT revert (no shipped card does that to a 6/8 attacker; defeat is the
realistic leave). Hygiene: `_apply_return_to_hand` clears `control_linked_to` on the
returned card. **THE TINY ADDITIVE FILTER (base-damage gate on WhenAttackEnds):** new
`WhenAttackEnds.require_base_damage: bool = False` field (registry, frozen); the
base-attack step2 fire adds a **DISTINCT key `attack_ended_base_damage`** (NOT
`dealt_combat_damage_to_base`) to the `attack_ended_survivor` event_ctx when `power > 0`
— **⚠️ REGRESSION CAUGHT+FIXED: first used `dealt_combat_damage_to_base` and it
DOUBLE-FIRED Ketsu Onyo SHD_147's `WhenDealsCombatDamageToBase` (which matches that
key); the distinct key avoids the collision.** resolver `_trigger_matches` WhenAttackEnds
arm: require `attack_ended_survivor==self`, and if `require_base_damage` also
`attack_ended_base_damage==self`; unit-vs-unit path never sets the key. **ENCODING LAW_54**
(law/abilities.py, shipped set) = optional `TriggerAbility(WhenAttackEnds(require_base_
damage=True), [CustomEffect(fn=_maul_law54_take_control, target=TargetSpec(controller=
"enemy", kind="unit", predicates=("non_leader",)))])` — the fn `change_control(target,
source.owner_id)` + sets `target.control_linked_to = source.instance_id`. "that player" =
base-damaged player = opponent (2-player) = enemy. **NO new decision kind** (reuses
trigger_option Accept/Decline + ChooseTarget) → NO invariants/web/bot change. FACE LAW_54
== P26_4 byte-identical (verified) → alias `("P26","4") → ("LAW","54")` reprints.py
"batch 33". Tests `TestMaulLAW54` (6, methods embed law_54: base-attack take-control links;
Maul defeat → revert + flag cleared; unit attack does NOT fire [require_base_damage gate];
no-enemy-unit auto-declines; decline leaves control unchanged; reprint P26_4 aliases).
**FOLLOW-ON:** `control_linked_to` + `_revert_linked_control` is a reusable "take control,
revert when I leave play" linkage (any future such card). **REMAINING 16 grp**, all genuine
escalation (the two BALLOON pairs + Luke J25_4 replacement still deferred). See
[[reprint-duplicates]].

**STAGE 4 BATCH 32 DONE 2026-07-14 (FRAMEWORK ESCALATION — the recurring
regroup-phase "pay 1 or return to hand" upkeep: `regroup_upkeep` decision kind).**
Re-ran `find_reprints --check` FIRST (was 18, `--check OK`, NO easy-phase reopen).
Surveyed ALL 18 fresh canonicals' DB TEXT (the actual `text` field — NOTE the
repo's `rules` field is FAQ/rulings, not gameplay text; use `.text`) + RE-DERIVED
triviality: **NO zero-engine trivial stragglers remain** → **no AskUserQuestion
fork**; pure escalation. **Leverage:** all 18 are 1-grp/primitive → tie-break 1
(smallest surface / closest mirror). **Picked Millennium Falcon SOR_193** —
`EntersPlayReady` ALREADY EXISTS (unconditional, half the card free), so the only
new piece is a self-contained regroup upkeep decision fired at the established
`_enter_regroup` `PhaseStartTrigger` site (Contracted Hunter JTL_216); NO combat,
NO turn-loop change, NO 2nd unbuilt primitive. (Runners-up: Maul LAW_54 =
change_control+WhenAttackEnds+revert-on-leave linkage; The Stranger LAW_86 =
defender-first-strike touches core combat order.) Cleared **1 grp**: needs_encoding
**18→17**, already_covered **174→175**, `--check OK`, fast tier **2307 pass / 0
fail** (118 known WinError-5 web errors).

**THE PRIMITIVE — `regroup_upkeep` decision kind** (`actions.push_regroup_upkeep(s,
source_ci, amount=1)`). Encoding SOR_193 = **`[EntersPlayReady(),
TriggerAbility(PhaseStartTrigger(phase="regroup"), [CustomEffect(fn=_falcon_regroup_
upkeep)])]`** in `sor/abilities.py`. The mandatory non-targeted CustomEffect resolves
INLINE inside `_enter_regroup`'s `fire_triggered_abilities` and pushes the decision
(addressed to the source's controller, `after_resolve_player_index=initiative_holder`
so the regroup resource step resumes). Two Action classes (actions.py, near SayNo):
`PayRegroupUpkeep` (offered only if controller has ≥1 resource; apply picks one
resource and sets `exhausted=True` AND `cannot_ready_this_round=True`) and
`ReturnRegroupUpkeepUnit` (always offered; `_apply_return_to_hand` → owner's hand).
`_regroup_upkeep_actions` builds the branch (legal_actions kind=="regroup_upkeep").
**KEY: "pay 1" is modeled via the existing `cannot_ready_this_round` flag** (state.py;
No Good to Me Dead SOR_186 / Sneak Attack SOR_219 `_enter_regroup`-flag family) —
`_end_regroup`'s ready-all loop `flag=False; continue` skips the ready but does NOT
touch `exhausted`, so setting BOTH guarantees the resource enters next ACTION
exhausted = a deterministic −1 (fungible resources, no sub-decision). **TIMING
DEVIATION (documented):** fires at regroup START, not the ready-cards instant; the
cannot_ready mechanism nets −1 regardless, so faithful. If 0 resources → only Return
(forced). Wired: `invariants._KNOWN_DECISION_KINDS += "regroup_upkeep"`;
`web/session._PROMPTS` (describe() fallbacks suffice for the two button labels);
`HeuristicBot._choose_regroup_upkeep` (pay if able else return) + `PayRegroupUpkeep`
in `_SAFE_DEFAULT_ORDER`. FACE SOR_193==P25_92 byte-identical (verified) → alias
`("P25","92") → ("SOR","193")` reprints.py "batch 32". Tests
`TestMillenniumFalcon` (6, methods embed sor_193: enters ready; upkeep pushed offers
pay+return; pay keeps Falcon + leaves 1 resource down after `_end_regroup`; return →
owner hand; forced-return with 0 resources; reprint P25_92 aliases). **FOLLOW-ON:**
`push_regroup_upkeep` is a reusable recurring-per-round upkeep decision (any future
"at regroup, pay X or lose the card" card). **REMAINING 17 grp**, all genuine
escalation (the two BALLOON pairs + Luke J25_4 replacement still deferred). See
[[reprint-duplicates]].

**STAGE 4 BATCH 31 DONE 2026-07-14 (FRAMEWORK ESCALATION — the standing per-round
conditional play-cost discount: `StandingPlayDiscount` marker).** Re-ran
`find_reprints --check` FIRST (was 19, `--check OK`, NO easy-phase reopen). Surveyed
ALL 19 fresh canonicals' DB TEXT + RE-DERIVED triviality from the current primitive
set: **NO zero-engine trivial stragglers remain** (every one needs an unbuilt
mechanic) → **no AskUserQuestion fork**; pure escalation. **Leverage:** all 19 are
1-grp/primitive (distinct mechanics, none clears two) → tie-break 1 (smallest surface
/ closest mirror) governs. Combat-pipeline (Darth Maul C24_6 attack-2, Maul SHD_90
redirect, The Stranger LAW_86 defender-first-strike) + turn-loop (Max Rebo extra
regroup) = large; Thrawn/Jabba-ASH/Falcon = medium. **Picked Director Krennic JTLP_1**
(closest mirror to the `NextPlayDiscount`/`pending_play_discounts` cost seam in
`_play_cost` + the `once_per_round` GameMemory-set pattern; NO decision kind, NO
combat, NO turn-loop, NO regroup timing, single primitive). Cleared **1 grp**:
needs_encoding **19→18**, already_covered **173→174**, `--check OK`, fast tier **2298
pass / 0 fail** (118 known WinError-5 web errors).

**THE PRIMITIVE — `StandingPlayDiscount(amount=1, applies_to="has_when_defeated_
ability", once_per_round=True)`** = a bare passive marker (the AttackRestriction/
IndirectDamageBonus family, registry.py) on an in-play SOURCE card, read ONLY at the
play-cost seam. Pieces: (1) new GameMemory set `standing_play_discounts_used_this_
round` (source instance_ids; cleared in `clear_round`; serialised to_dict/from_dict —
the `activated_abilities_used_this_round` once-per-round pattern). (2)
`actions._card_matches_standing_discount(card_def, applies_to)` — for
`"has_when_defeated_ability"`: `isinstance(card_def, Unit)` AND printed text (nbsp-
normalised, lowercased) contains "when defeated" — a DB-TEXT check (NOT registered
specs), so it holds regardless of whether the played card is itself encoded.
**DEVIATION: a Bounty is rules-wise a When-Defeated ability but printed "Bounty —", so
it does NOT match — a rare documented corner.** (3) `_standing_play_discount(state,
ci, ps)` (read-only) + `_consume_standing_discount` (spends the per-round marker), both
via a shared `_standing_play_discount_sources` scan of `ps.ground_arena+space_arena`
for the marker (so read & consume never disagree; two Krennics → -2 on the first
qualifying play). (4) `_play_cost` reduction term += `_standing_play_discount`; consume
at BOTH `_consume_play_discount` sites — `PlayCard.apply` AND `PlayTopCard.apply` (peek-
play) — the two normal unit-play paths that use `_play_cost`. **LIMITATION (the
documented Khetanna scope):** the play-from-hand subsystem pays raw `_effective_cost`
(NOT `_play_cost`), so an ability-driven play neither sees nor consumes the discount.
Added `StandingPlayDiscount` to `soak.py`'s passive-marker isinstance tuple (Krennic's
ONLY registered spec is this marker; Shielded = keyword layer) so a marker-only card
isn't a false zero-fire. **ENCODING JTLP_1** (both faces promo → `promo/abilities.py`,
the Grogu ASH_18 promo-canonical precedent) = `StandingPlayDiscount(amount=1)`
(defaults). FACE JTLP_1==P25_65 byte-identical (verified) → alias `("P25","65") →
("JTLP","1")` reprints.py "batch 31". Tests `TestDirectorKrennicJTLP1` (6, methods
embed jtlp_1: discounts a When-Defeated unit [+ `_play_cost` −1 vs no-Krennic]; NO
discount for a vanilla unit; NO discount without Krennic; FIRST-play-only-each-round
then resets via `clear_round`; end-to-end PlayCard pays 1 less + marks spent; reprint
P25_65 aliases). **FOLLOW-ON the marker ALSO unblocks:** any "the first <X> you play
each round/phase costs less" standing conditional discount (add a new `applies_to`
predicate arm). **REMAINING 18 grp**, all genuine escalation (the two BALLOON pairs +
Luke J25_4 replacement still deferred). See [[reprint-duplicates]].

**STAGE 4 BATCH 30 DONE 2026-07-13 (TWO trivial stragglers CLEARED + ONE framework
escalation — user chose "clear stragglers AND build primitive" via the
AskUserQuestion fork).** Re-ran `find_reprints --check` FIRST (was 22). **⚠️ FRESH
SURVEY OVERTURNED the roadmap: TWO trivial zero-engine stragglers, not the ONE
(Shatterpoint) my batch 27–29 notes recorded.** **Lawbringer LAW_101 is ALSO
trivial** — the roadmap's "choose-aspect mass debuff = new primitive" label WENT
STALE: batch-23's `choose_two_modal pick=1` extension covers "choose an aspect"
(6 options, pick 1) exactly as it covers Shatterpoint's modal+Force. Per the
>1-trivial-straggler rule I offered the easy-vs-escalation **AskUserQuestion fork**;
user picked **Option C** (clear both stragglers AND build the Ki-Adi primitive).
Cleared **3 grp**: needs_encoding **22→19**, already_covered **170→173**, `--check
OK`, fast tier **2289 pass / 0 fail** (118 known WinError-5 web errors). **LESSON:
NEVER trust the roadmap's "1-per-primitive" labels — always RE-DERIVE triviality
from the CURRENT primitive set (pick=1 modal makes modal+ANYTHING-declarative
trivial, not just modal+Force).**

**Shatterpoint P25_153 (ZERO new engine; promo/abilities.py):** "Choose one: Defeat
a non-leader unit with ≤3 remaining HP. / Use the Force. If you do, defeat a
non-leader unit." = `EventAbility(CustomEffect→push_choose_modal(option_indices=[1,2],
pick=1))` + TWO `TriggerAbility(WhenPlayed())` options (an EVENT is never in
`_cards_in_play` → safe, the SOR aspect-event convention): opt1 =
`DefeatUnit(non_leader, hp_remaining_max=3)`; opt2 = `[CustomEffect(spend_force_token
+ set event_ctx["prior_target_id"]=source_id IFF spent), DefeatUnit(non_leader,
requires_prior_target)]` — the In Pursuit TWI_221 "If you do" gate (no token → flag
unset → the defeat has no candidates → no-op). **Confirmed the resolve_effects flow
handles [no-target CustomEffect, gated DefeatUnit]: `AutoResolveEffects.apply`
executes the no-target force-spend inline in its while-loop THEN re-gathers the gated
defeat's candidates — NOT the Ahsoka JTL_201 optional-trigger-gate trap (this is a
modal-option resolve_effects, not an optional trigger).** Aliases P25_163/P26_74/
P26_90→P25_153. Tests `TestShatterpointP25153` (5, method names embed p25_153).

**Lawbringer LAW_101 (near-zero — ONE 1-line EACH_* filter-propagation BUGFIX;
law/abilities.py):** "When Played/On Attack: Choose an aspect. Give each enemy unit
with that aspect –2/–2 for this phase." = TWO triggers (`WhenPlayed`+`OnAttack`) each
`CustomEffect→push_choose_modal(option_indices=[2..7], pick=1)` + SIX `EventAbility`
options idx 2..7 = (Vigilance,Command,Aggression,Cunning,Heroism,Villainy), each
`ModifyStats(-2,-2, TargetSpec(controller="enemy", aspects=(X,), fixed=EACH_ENEMY),
THIS_PHASE)`. ⚠️ **Lawbringer is a UNIT in play → the option specs MUST be
`EventAbility` NOT `TriggerAbility`** (the Luke LAW_80 lesson: `_collect_triggers`
collects only TriggerAbility → would fire them on his entry). **THE BUGFIX:
`resolver._resolve_fixed_target_ids`'s `EACH_*` sub_spec DROPPED `aspects` (and
`power_min`/`power_max`/`hp_remaining_max`) → a mass EACH_ENEMY effect ignored the
aspect filter and hit EVERY enemy unit** (test caught it — Command Krell debuffed
when Aggression chosen). Added those 4 per-candidate "card must match" fields to the
sub_spec; verified NO pre-existing card combined `fixed=EACH_*` with them, so it only
tightens matching where a card asked. ⚠️ **GOTCHA: `compute_hp` floors at
`max(1, base)`, so a mass -2/-2 alone can NOT drop an undamaged unit to lethal — it
defeats only a PRE-DAMAGED unit** (defeat test pre-damages a 2/3 to remaining 1).
Aliases P26_83/P26_99→LAW_101. Tests `TestLawbringerLAW101` (5, method names embed
law_101).

**Ki-Adi-Mundi TWI_64 (FRAMEWORK ESCALATION — the `WhenOpponentPlaysNthCard`
observer trigger; canonical = SHIPPED TWI → twi/abilities.py; alias J25_2→TWI_64):**
"Coordinate — When an opponent plays their second card each phase: You may draw 2
cards." **THE PRIMITIVE:** (1) new registry trigger
`WhenOpponentPlaysNthCard(count=2)`; (2) new counter `GameMemory.cards_played_this_phase`
(dict player_id→int; cleared in `clear_phase`; serialised to_dict/from_dict);
(3) increment at the SINGLE `CardPlayed` firing chokepoint `fire_triggered_abilities`
(guarded `isinstance(event, CardPlayed)`, BEFORE `_collect_triggers` so the matcher
sees the post-increment count); (4) matcher arm in `resolver._trigger_matches` — fires
when `event.player_id != source.owner_id` AND `counter[event.player_id] == trigger.count`
(`==` not `>=` → fires exactly on the Nth play, once per phase per opponent). Coordinate
= `_COORDINATE` (`CONTROLLER_N_PLUS_UNITS`, 3) gates trigger COLLECTION (Anakin TWI_147
pattern); `optional=True` carries "you may". Reuses `trigger_option`
(AcceptTrigger/DeclineTrigger) → NO new decision kind, NO invariants/web/bot change.
**KEY DESIGN: incrementing INSIDE `fire_triggered_abilities` (not at the ~10 CardPlayed
emission sites) keeps the counter aligned with FIRING opportunities → the Nth *fired*
play is exactly `count==N`, avoiding an off-by-one where a non-firing play advances the
count past the threshold.** **DOCUMENTED LIMITATION:** the 4 EFFECT-driven plays
(PlayFromHand ability-play / ReplayReturnedUnit owner-replay / FinishSearch play-from-
deck / Exploit-commit) append `CardPlayed` WITHOUT firing it through
`fire_triggered_abilities`, so they don't count — matching every existing
`WhenYouPlayCard` observer's coverage (Fighters for Freedom etc.); the normal PlayCard
hand-play + Smuggle/Plot/Pilot keyword plays DO count/fire (tokens fire UnitEntersPlay
not CardPlayed → correctly don't count). Tests `TestKiAdiMundiTWI64` (7, method names
embed twi_64: 1st play no draw; 2nd play may-draw-2; 3rd no-retrigger; requires 3+
units [Coordinate off]; friendly plays don't count; counter resets each phase;
reprint face). **FOLLOW-ON the observer ALSO unblocks:** any "when an opponent plays
their Nth card each phase" / per-phase opponent-play-count trigger. **⚠️ FIXED 2 stale
`test_reprints.py` regression tests** that hardcoded Ki-Adi TWI_64 as the canonical
"keyword-deferred card with unregistered ability text" example — repointed both to
**The Stranger LAW_86** (still needs_encoding; Ambush+Grit implemented keywords +
unregistered defender-first-strike text, the same shape).

**REMAINING 14 grp** (the 19-group list below MINUS Director Krennic JTLP_1 [B31 done],
Millennium Falcon P25_92 [B32 done], Maul LAW_54 [B33 done], Poe Dameron JTLP_6 [B34
done], Always Two LOF_42 [B35 done]; all genuine escalation; the two BALLOON pairs still
deferred: damage-prevention Malakili LOF_108 + Amidala J25_16; "lose all abilities"
Galen P25_31 + Mind Trick LOF_202): Darth Maul C24_6 (attack 2
units — combat pipeline), Darth Vader C24_2 (search-multi-play-free), Galen Erso P25_31
(name-a-card ability-loss aura — BALLOON), Thrawn P25_33/SEC_193 (capture + 2 decision
flows), Jabba ASH_42 (return-upgrade + replay-if-yours — BALLOON: needs
free-play-upgrade-from-hand too), Leia LOF_98 (arena-move [REUSE — Blue Leader JTL_96]
+ in-space condition atom + can't-ready-while-in-space constraint), Luke J25_4
(REPLACEMENT effect — STOP/defer), Malakili LOF_108 (damage-prevention — BALLOON; the
discount half is now trivial via StandingPlayDiscount B31), Maul J24_4/SHD_90 (redirect
combat dmg — combat pipeline), Max Rebo LAW_72 (extra regroup phase — turn loop), Mind
Trick LOF_202 (exhaust + ability-loss — BALLOON), Amidala J25_16/SEC_101 (pay-to-prevent
— BALLOON), Eye of Aldhani SEC_73 (delayed start-of-next-action-phase pay-or-exhaust per
enemy unit — mirrors regroup_upkeep B32 but needs delayed scheduling too), The Stranger
LAW_86 (defender-first-strike — combat pipeline). **NO trivial stragglers remain.** See
[[reprint-duplicates]].

**STAGE 4 BATCH 29 DONE 2026-07-13 (FRAMEWORK ESCALATION — deploy-leader-as-effect:
"When you play a unique unit that costs 4 or more: you may deploy this leader for
FREE").** Re-ran `find_reprints --check` FIRST (was 23, `--check OK`, no new-set
import had reopened the easy phase). Surveyed all 23 fresh canonicals' DB TEXT.
**Straggler status UNCHANGED:** Shatterpoint P25_153 still the lone noted ZERO-
ENGINE straggler → a LONE straggler does NOT trigger the AskUserQuestion fork
(Knight's-Saber/B22 precedent), so I did the escalation + left it noted.
**Leverage:** every escalation group ties at 1 grp/primitive → tie-break 1
(smallest engine surface / closest mirror) picked **Grogu ASH_18** over Thrawn
P25_33 (capture EXISTS — `CaptureUnit`/`_apply_capture` — but Thrawn needs TWO new
decision flows: WhenPlayed opponent-choose-own-unit-or-decline capture + WhenDefeated
choose-captor-AND-target capture, so LARGER), The Stranger LAW_86 (defender-first-
strike, combat pipeline), Max Rebo LAW_72 (extra regroup phase, turn loop). EXCLUDED
Luke J25_4 = a **REPLACEMENT effect** ("If this upgrade would be defeated → INSTEAD
move him to ground as a unit") → STOP-and-defer per the escalation rule.
⚠️ **NOTE for empty-`text` canonicals:** Grogu's & Luke's functional text lives in
the **`epic_action`** DB column, NOT `text` (repo `.text==''`); ALWAYS check
`epic_action`/`deploy_box` before dismissing a "text-bearing" card as vanilla.
Also `<uq>` in DB text = the **UNIQUE symbol** (decoded via cross-ref — NOT an aspect).

**The primitive (deploy-leader-as-effect):** factored the shared body of
`DeployLeader.apply` — flip leader into arena READY + `LeaderDeployed` event +
`fire_triggered_abilities` (WhenDeployed) + the Plot check, MINUS the resource/
threshold check and the end-of-action `_switch_active_player` — into
`actions._deploy_leader_into_arena(s, ps, leader_ci)`; `DeployLeader.apply` now =
checks + helper + switch. New public `actions.deploy_leader_as_effect(s, leader_id)`
re-finds the undeployed base_zone leader (guard `leader_ci in ps.base_zone`) and
calls the helper WITHOUT the switch (it runs inside trigger resolution). New
`WhenYouPlayCard.cost_min` field (matcher gates on the played card's printed cost
≥ N; the matcher's `find_instance` block now runs when ONLY `cost_min` is set too).
NO new decision kind, NO combat pipeline, NO invariants/web/bot change.
⚠️ **GOTCHA (found+fixed at import):** `class DeployLeader(Action)` carries a
`@dataclass` decorator on the line ABOVE it; my first Edit inserted the two helper
functions BETWEEN `@dataclass` and `class DeployLeader` → `@dataclass` decorated a
function → `AttributeError: 'function' object has no attribute '__mro__'`. Fixed by
moving `@dataclass` back onto the class. LESSON: when inserting code before a class,
check the preceding line for a decorator.

**Grogu ASH_18 encoding** (canonical = shipped 267-card ASH set, no dedicated module
→ **promo/abilities.py**, following the ASH_243/ASH_226 precedent): an OPTIONAL
`TriggerAbility(WhenYouPlayCard(card_type="unit", unique=True, cost_min=4),
undeployed_only=True, condition=ConditionCheck(SOURCE_READY),
effects=[CustomEffect(_grogu_deploy)])`; the no-target CustomEffect deploys the
source leader via `deploy_leader_as_effect(state, source_ci.instance_id)`. Collected
by the base_zone undeployed-leader trigger scan (the-mandalorian:04, matches the
`CardPlayed` event); `undeployed_only` stops it re-firing once he is a unit; Grogu
has NO deploy threshold (his epic_action is a trigger, not "N resources") so this
trigger is his ONLY deploy path (free, off-threshold). alias **MV26_1→ASH_18**.
needs_encoding **23→22**, already_covered **169→170**, `--check OK`.
**Tests** (tests/test_promo_cards.py::TestGroguASH18, 6 — method names embed
`ash_18`): deploys on unique-4+ play (JTL_53; deployed+ready, out of base_zone);
NOT offered for non-unique (SOR_116 cost 5) / cheap unique (SOR_192 cost 3, cost_min
fails) / exhausted Grogu (SOURCE_READY) / already-deployed (undeployed_only); decline
leaves him undeployed. Fast tier **2254 passed, 0 failed** (118 known WinError-5).
**Follow-on the primitive ALSO unblocks:** any "you may deploy this leader" play-
trigger (distinct from the JTL Piloting-leaders' `DeployLeaderAsUpgrade` — this is
the free-deploy-off-a-play-trigger case, reusing `_deploy_leader_into_arena`).

**STAGE 4 BATCH 28 DONE 2026-07-13 (FRAMEWORK ESCALATION — the keyword-COPY
aura: "each other friendly <trait> unit gains THIS unit's keywords").** Re-ran
`find_reprints --check` FIRST (was 24, `--check OK`, no new-set import had
reopened the easy phase). Surveyed all 24 fresh canonicals' DB TEXT. **Straggler
status UNCHANGED:** Shatterpoint P25_153 is still the lone noted ZERO-ENGINE
straggler (choose_two_modal pick=1 + DefeatUnit/hp_remaining_max + spend_force
+ requires_prior_target; canonical P25_153 → promo/abilities.py, alias
P25_163/P26_74/P26_90) — a LONE straggler does NOT trigger the AskUserQuestion
fork (Knight's-Saber/B22 precedent), so I did the escalation and left it noted.
**Leverage:** every escalation group ties at 1 grp/primitive (the two 2-for-1
BALLOONS still deferred: "lose all abilities" Galen P25_31 + Mind Trick LOF_202
[name-a-card aura vs power-budget exhaust]; damage-prevention Malakili LOF_108 +
Amidala J25_16 [passive-always vs pay-to-prevent]). Picked by tie-break 1
(smallest surface / CLOSEST MIRROR to batch-27's work / no 2nd-primitive dep):
**The Ghost J25_1** "Each other friendly Spectre unit gains this unit's keywords.
While this unit is upgraded, it gains Sentinel." Cleared **1 grp**: needs_encoding
**24→23**, already_covered **168→169**; 5 tests, `--check OK`, fast tier **2245
pass / 0 fail** (118 known WinError-5 web errors).
**THE PRIMITIVE — a new `CopyKeywords` ConstantAbility effect (registry.py) read
ENTIRELY in the keyword-query layer (`keywords.has_keyword`/`keyword_value` — the
SAME functions batch-27's permanent keyword-grant touched); NO new decision kind,
NO combat pipeline, NO invariants/web/bot change.** `CopyKeywords` is a fieldless
ConstantAbility effect meaning "each unit matched by this ability's `target` gains
the SOURCE unit's keywords" — DYNAMIC (whatever the source currently reports), so a
keyword the source only conditionally has (The Ghost's while-upgraded Sentinel) is
copied only while present. New keywords.py pieces: a helper
`_copy_keyword_sources(state, unit_ci)` yields each in-play unit whose
ConstantAbility(CopyKeywords) target matches unit_ci (source≠unit via the aura's
`not_self`; matched via `resolver._spec_matches_ci`), and BOTH read functions, just
before their `return`, scan those sources — `has_keyword` returns True if any source
`has_keyword(source, kw)`; `keyword_value` ADDS each source's `keyword_value(source,
kw)` ("gains this unit's keywords" → a numeric keyword copied at its value). A
module-level re-entrancy guard `_KEYWORD_COPY_RESOLVING` (keyed `(id(state),
instance_id)`, add/remove around the recursive scan) breaks a mutual-copy cycle
(hypothetical two-Ghost board → terminates, no RecursionError). Defaults harmless —
no existing card carries a CopyKeywords effect, and the constant/upgrade KeywordGrant
scans skip a CopyKeywords effect (isinstance), so every other card is byte-identical.
**ENCODING JTL_53** (canonical = SHIPPED set → `jtl/abilities.py`): TWO passive
`ConstantAbility` specs — `[CopyKeywords()]` targeting `controller="friendly"
kind="unit" traits=("Spectre",) not_self`, AND `[KeywordGrant("Sentinel")]`
target=SELF gated `SOURCE_UPGRADED` (the Cinta Kaz LAW_105 conditional-self-grant
pattern → the keyword sanitiser's rule-2 STRIPS The Ghost's DB-mistagged PRINTED
Sentinel [verified: hydrated keywords go `('Sentinel',)`→`()`], so the copy confers
Sentinel to allies ONLY while The Ghost is upgraded — the intended combo). **FACE:
J25_1 + JTL_53 + P25_86 byte-identical** (5/6, cost 5, same text) → plain same-face
aliases `("J25","1")/("P25","86") → ("JTL","53")` reprints.py "batch 28". Tests
`tests/test_jtl_cards.py::TestTheGhostJTL53` (5: ally gains Sentinel ONLY while Ghost
upgraded; copy affects ONLY friendly Spectre [not friendly non-Spectre, not enemy
Spectre]; copy ENDS when Ghost leaves the arena [source-in-play — the scan only sees
in-play units]; NUMERIC keyword copied at value via keyword_value [Raid-2 modifier on
Ghost → ally keyword_value(Raid)==2]; two-Ghost board = no infinite recursion). Reuses
`_get_card`/`_place`/`_attach_upgrade_directly` (SHD_74 as the upgrade; Ezra SOR_192 =
clean Spectre ally, no printed kw). **REMAINING 23 grp**, all genuine 1-per-primitive
escalation EXCEPT the noted Shatterpoint zero-engine straggler. **FOLLOW-ON the
keyword-copy aura ALSO unblocks:** any future "each friendly <trait> unit gains this
unit's keywords" copy-aura (add a new ConstantAbility(CopyKeywords) with the right
target). See [[reprint-duplicates]].

**STAGE 4 BATCH 27 DONE 2026-07-13 (FRAMEWORK ESCALATION — the `permanent`
keyword-grant that ends when its source leaves play; the keyword-layer MIRROR of
Huyang TWI_110's `permanent` STAT modifier).** Re-ran `find_reprints --check` FIRST
(was 25, `--check OK`, no new-set import had reopened the easy phase — still 25).
Surveyed all 25 fresh canonicals' DB TEXT. **⚠️ FRESH SURVEY FINDING — the "no more
trivial stragglers" note WAS STALE: Shatterpoint P25_153 is now a ZERO-ENGINE
trivial straggler** (it composes entirely from EXISTING primitives, having become
easy after batches 15/17/23 built modal+force): a `choose_two_modal` with **pick=1**
(batch-23 Luke LAW_80 extension) over TWO option specs — opt1 = `DefeatUnit(
TargetSpec(non_leader, hp_remaining_max=3))`, opt2 = `EventAbility([CustomEffect
(spend_force_token + set event_ctx["prior_target_id"] iff spent), DefeatUnit(
TargetSpec(non_leader, requires_prior_target))])` (the In Pursuit TWI_221 "if you
do" gate). Options as `TriggerAbility(WhenPlayed())` like the SOR aspect events
(safe — an event is never in `_cards_in_play`). NO new engine code. Per precedent
(Knight's Saber / batch-22: a LONE straggler does NOT trigger the AskUserQuestion
fork) I did the ESCALATION and left Shatterpoint as a **noted trivial straggler to
clear in a future cleanup pass** (add to `promo/abilities.py` — P25 promo group,
members P25_153/P25_163/P26_74/P26_90, all no-shipped-twin → register canonical
P25_153, alias the other 3). **Leverage:** every escalation group ties at 1
grp/primitive (the two 2-for-1 BALLOONS still deferred: "lose all abilities" Galen
P25_31 + Mind Trick LOF_202; damage-prevention Malakili LOF_108 + Amidala SEC_101).
Picked by tie-break 1 (smallest surface / closest mirror / no 2nd-primitive dep):
**BD-1 C25_4** "Hidden. When Played: Choose another friendly unit. While this unit
is in play, the chosen unit gets +1/+0 and gains Saboteur." Cleared **1 grp**:
needs_encoding **25→24**, already_covered **167→168**; 5 tests, `--check OK`, fast
tier **2234 pass / 0 fail** (118 known WinError-5 web errors).
**THE PRIMITIVE — the `permanent`-modifier machinery ALREADY existed for STATS
(Huyang TWI_110); the ONLY new engine code is guarding the `permanent`
`keyword_grant` READ in `has_keyword`/`keyword_value` (keywords.py).** A `permanent`
modifier models "while <source> is in play, <target> gets X"; `compute_power`/
`compute_hp` already skip a `permanent` STATS modifier whose source left play (via
`actions._modifier_source_in_play`), and `_defeat_unit` / `_apply_return_to_hand` /
the relocate path already drop EVERY `permanent` modifier by source **regardless of
kind** (so a permanent keyword_grant is cleaned up for free). Batch 27 adds the
keyword mirror: both keyword_grant read loops now `continue` past a `permanent`
modifier when `not _permanent_kw_source_in_play(state, source_id)` — a new tiny
keyword.py helper that LAZILY imports `actions._modifier_source_in_play` (keywords↔
actions cycle: actions imports keywords). Defaults harmless — a non-permanent
keyword_grant (every existing `GrantKeyword`, all `this_phase`/`this_attack`) is
byte-identical. **ENCODING C25_4** (Hidden = keyword layer; canonical in
`promo/abilities.py` — both members anthology/promo, NO shipped twin): a MANDATORY
`WhenPlayed` whose one `CustomEffect.target=TargetSpec(controller="friendly",
kind="unit", predicates=("not_self",))` ("another friendly unit") appends TWO
`permanent` Modifiers sourced by BD-1 — a `stats` +1/+0 (the exact Huyang fn
pattern: construct `Modifier(... kind="stats", value={"power":1,"hp":0},
duration="permanent")` directly) AND a `keyword_grant` `{"keyword":"Saboteur",
"value":0}` permanent. None target (BD-1 only friendly unit) = clean no-op; mandatory
targeted so with an enemy-only board the effect fizzles (no legal friendly target).
**FACE: C25_4 + LOFP_15 byte-identical** (1/3, cost 1, Hidden, same text) → plain
same-face alias `("LOFP","15") → ("C25","4")` reprints.py "batch 27". Tests
`tests/test_promo_cards.py::TestBD1C254` (5: grants +1/+0 & Saboteur; buff ENDS when
BD-1 leaves play [`_defeat_and_fire` removes BD-1 from arena → source-in-play guards
make both modifiers inert — this is the NEW keyword-guard exercised]; targets ONLY
another friendly [not self, not enemy]; no-other-friendly = no-op [no ChooseTarget,
no modifiers]; survives `GameState.from_json(to_json())` round-trip). **REMAINING 24
grp**, all genuine 1-per-primitive escalation EXCEPT the noted Shatterpoint zero-
engine straggler (above). **FOLLOW-ON the permanent keyword-grant ALSO unblocks:**
any future "while this unit is in play, <chosen unit> gains <keyword>" card (the
Huyang pattern + a keyword). See [[reprint-duplicates]].

**STAGE 4 BATCH 26 DONE 2026-07-13 (FRAMEWORK ESCALATION — the `select_extreme`
set-relative target selector).** Re-ran `find_reprints --check` FIRST (was 26,
`--check OK`, no new-set import had reopened the easy phase; surveyed all 26 fresh
canonicals' DB TEXT — NO trivial stragglers, all genuine 1-per-primitive → no
AskUserQuestion fork). **Leverage:** every remaining group ties at 1 grp/primitive
(the two 2-for-1 BALLOONS still deferred: "lose all abilities" Galen P25_31 + Mind
Trick LOF_202, and damage-prevention Malakili LOF_108 + Amidala J25_16). Picked by
tie-break 1 (smallest surface / closest mirror, and the SAFEST — isolated to
target-gathering, no combat pipeline like The Stranger / no per-round ledger like
Krennic): **Darth Nihilus P26_79** — "When Played/On Attack: Deal 3 damage to the
unit with the least remaining HP among other units. If it's a non-Vehicle unit,
give an Experience token to this unit." Cleared **1 grp**: needs_encoding **26→25**,
already_covered **166→167**; 5 tests, `--check OK`, fast tier **2226 pass / 0 fail**
(118 known WinError-5 web errors).
**THE PRIMITIVE — ONE new declarative field `TargetSpec.select_extreme` (registry.py)
+ one POST-filter arm in `_gather_legal_targets` (resolver.py); NO new decision kind,
NO CustomEffect machinery change, NO combat-pipeline touch.** The only value today is
`"least_remaining_hp"`. Unlike a per-candidate predicate (e.g. `cost_max_boost`, which
is evaluated per-candidate), an "extreme" selector is SET-RELATIVE — it depends on the
whole matched set — so it CANNOT be a `_spec_matches_ci` predicate; it is applied AFTER
the per-candidate loop in `_gather_legal_targets` by a new helper `_apply_select_extreme`
(computes `compute_hp(state,ci) - ci.damage` for each surviving candidate, keeps only
those equal to the MINIMUM). **TIES keep every minimum** → the standard ChooseTarget flow
prompts the controller to pick among them, and auto-resolves when exactly one. Because it
flows through `_gather_legal_targets`, the optional-trigger auto-decline gate would honor
it too (Nihilus is MANDATORY though — no "may", so it just fizzles with no other units).
`select_extreme` defaults None → byte-identical for every existing card.
**ENCODING P26_79** (canonical — both members are P26 PROMOS with NO shipped twin, so it
lives in `promo/abilities.py`, NOT a set module; batch-19's shared promo module): TWO
mandatory `TriggerAbility`s (a `WhenPlayed` + an `OnAttack`, matching "When Played/On
Attack") each with ONE `CustomEffect(fn=_darth_nihilus_p26_79, target=TargetSpec(
controller="any", kind="unit", predicates=("not_self",), select_extreme="least_remaining_hp"))`.
`controller="any"` + `not_self` = "among OTHER units" (both friendly AND enemy, excluding
Nihilus). The fn binds BOTH clauses in one CustomEffect (the Bright Hope SOR_99 / Zeb
Orellios LAW_45 "if you do"-style bind) because the conditional Experience depends on
WHICH unit was hit: it reads `"Vehicle" not in target.card_def.traits` (printed traits,
matching the `non_vehicle` predicate) BEFORE dealing damage so a target the 3 damage
DEFEATS still qualifies ("it" = the unit that was damaged), then `_apply_deal_damage(3)`,
then if non-Vehicle `attach_token(Experience)` to Nihilus (re-find self via find_instance).
**FACE: P26_79 + P26_95 byte-identical** (6/6, cost 7, Villainy Force/Sith, same text)
→ plain same-face alias `("P26","95") → ("P26","79")` in reprints.py "batch 26". Tests
`tests/test_promo_cards.py::TestDarthNihilusP2679` (5: only-least-HP-offered + survives +
self-Experience; ties offer EVERY minimum; excludes-self-includes-friendly [Nihilus damaged
to remaining 1 but NEVER a target, friendly min-among-others chosen]; Vehicle target → NO
Experience [TIE Fighter SOR_225]; OnAttack also fires). Local `_ct_ids`/`_choose` helpers;
mandatory trigger → `_fire_when_played`/`_fire_on_attack` push ChooseTarget DIRECTLY (no
AcceptTrigger). **REMAINING 25 grp**, all genuine 1-per-primitive escalation. **FOLLOW-ON
`select_extreme` may also help:** any future "the unit with the most/least <stat>"
auto-selector (add a new selector string + arm to `_apply_select_extreme`; e.g. Darth
Nihilus P26_79 was in batch-19's DEFERRED list as "least remaining HP auto-target selector").
See [[reprint-duplicates]].

**STAGE 4 BATCH 25 DONE 2026-07-13 (FRAMEWORK ESCALATION — the `cost_max_boost`
conditional target cost cap).** Re-ran `find_reprints --check` FIRST (was 27, no
new-set import had reopened the easy phase; surveyed all 27 fresh canonicals' DB
TEXT — NO trivial stragglers, all genuine 1-per-primitive → no AskUserQuestion
fork). **Leverage:** every remaining group ties at 1 grp/primitive (the two 2-for-1
BALLOONS still deferred: "lose all abilities" Galen P25_31 + Mind Trick LOF_202,
and damage-prevention Malakili LOF_108 + Amidala SEC_101). Picked by tie-break 1
(smallest surface / closest mirror to an existing primitive): **Kanan Jarrus
LAW_89** — "Restore 1. When Played: You may return a non-leader unit that costs 2
or less to its owner's hand. If you control a Command or Aggression unit, you may
return a non-leader unit that costs 4 or less instead." Cleared **1 grp**:
needs_encoding **27→26**, already_covered **165→166**; 5 tests, `--check OK`, fast
tier **2218 pass / 0 fail** (118 known WinError-5 web errors).
**THE PRIMITIVE — ONE new declarative field `TargetSpec.cost_max_boost` (registry.py)
+ one resolver arm; NO new decision kind, NO CustomEffect, NO machinery change.**
Kanan is the closest mirror to the Baylan/Rio return-to-hand primitive MINUS the
replay — a plain OPTIONAL `WhenPlayed` whose one effect is a first-class
`ReturnToHand(TargetSpec(controller="any", kind="unit", predicates=("non_leader",),
cost_max=2, cost_max_boost=(("Command","Aggression"), 4)))`. `controller="any"` = "a
non-leader unit" (not friendly/enemy). The ONLY new engine surface: `cost_max_boost
= (aspects_tuple, boosted_cap)` — when the SOURCE controller controls a unit with
ANY listed aspect (the source counts), `_spec_matches_ci`'s cost filter raises
`cost_max` to `boosted_cap` (mirrors the existing `require_controller_aspect`
state-aware gate; effective_cost_max computed inline before the `cost > cap` check).
Being OPTIONAL + TARGETED, the trigger auto-declines with no eligible unit — the
`ReturnToHand` TargetSpec gates `_optional_trigger_has_legal_effect` (which routes
through `_gather_legal_targets` → `_spec_matches_ci`, so cost_max_boost is honored
in the auto-decline too). `cost_max_boost` defaults None → byte-identical for every
existing card; TargetSpec is a static registry object (never serialised), so the
nested-tuple field needs no JSON support. Restore 1 = keyword layer. **KEY FACT:
Kanan is Cunning/Vigilance/Heroism, so he NEVER self-satisfies the Command/Aggression
boost** — the boost activates only with ANOTHER qualifying unit (clean to test both
caps). **FACE: LAW_89 + LAWP_10 byte-identical** (3/4, cost 4, same Restore 1 +
WhenPlayed text, NO reminder split) → plain same-face alias `("LAWP","10") → ("LAW",
"89")` in reprints.py "batch 25". Encoding in `law/abilities.py` at EOF (canonical
LAW = shipped set). Tests `tests/test_law_cards.py::TestKananJarrusLAW89` (5:
cost-2 enemy → owner hand; cost-3 NOT returnable at base cap → auto-declines;
Aggression unit boosts cap → cost-3 returns; Command unit → cap exactly 4 inclusive
via SOR_46; declinable). `_in_hand(state, owner, iid)` helper (checks owner's hand;
`_find_instance` returns None once a unit leaves the arena). **REMAINING 26 grp**,
all genuine 1-per-primitive escalation. **FOLLOW-ON `cost_max_boost` may also help:**
any future "return/target a unit costing ≤N, or ≤M if you control an <aspect> unit"
card. See [[reprint-duplicates]].

**⚠️ BATCH-23 REGRESSION FOUND+FIXED 2026-07-13 (before batch 24).** Batch 23's
Luke LAW_80 was declared "done" the prior session but had silently BROKEN batch 22's
Cad Bane: the new `_luke_skywalker_law80` function had been mis-inserted INTO
`_cad_bane`, stripping `_cad_bane`'s `return` (→ returned None → Cad Bane's on-attack
ability never registered) and stranding its real return as dead code. Batch 23's
focused verify ran reprints+LAW+SOR but NOT `test_cad_bane.py` (a separate file), so
the 3 genuine failures slipped through (the other 2 Cad Bane tests passed VACUOUSLY —
no decision pushed = "no effect" trivially true). Fix = restore `_cad_bane`'s
`return TriggerAbility(OnAttack, [CustomEffect(_fn)])` + delete the orphaned dup after
Luke's return. Confirmed clean: fast tier **2199 pass / 0 fail** (only the 118 known
WinError-5 web PermissionError collection errors). **PROCESS LESSON (added to the
standing prompt's step 6): when a batch registers a card NEXT TO an existing one, run
that NEIGHBOR's test file too — insertion errors hit the neighbor, not the new card;
and any FAILED (not ERROR) in the fast tier MUST be investigated before "done".**

**STAGE 4 BATCH 24 DONE 2026-07-13 (FRAMEWORK ESCALATION — the `put_on_deck`
multi-decider decision kind).** Re-ran `find_reprints --check` FIRST (still 28, no
new-set import had reopened the easy phase; surveyed all 28 fresh canonicals' DB
TEXT — no trivial stragglers, all genuine 1-per-primitive → no AskUserQuestion fork).
**Leverage:** every remaining group ties at 1 grp/primitive; picked by tie-break 1
(smallest surface / closest mirror to an existing push_): **Qui-Gon Jinn LOF_200** —
"Ambush. When Defeated: You may choose a non-leader ground unit. Its owner puts it on
the top or bottom of their deck." Cleared **1 grp**: needs_encoding **28→27**,
already_covered **164→165**; 5 tests, `--check OK`.
**THE PRIMITIVE — new self-contained `put_on_deck` decision kind** (actions.py), a
near-exact mirror of batch-20 `owner_may_replay` (multi-decider push, the OWNER
decides — the say_no SOR_233 deciding-player shift) + `_apply_return_to_hand`
(leave-play machinery, destination = deck instead of hand). Pieces: `push_put_on_deck(
s, source_ci, target_id)` pushes a decision owned by the chosen unit's OWNER (who may
be the opponent — only they should order their own deck); two mandatory actions
`PutOnDeckTop`/`PutOnDeckBottom` (no decline — "puts it on the top OR bottom" once
chosen) → `_resolve_put_on_deck` pops FIRST (the "pop, then act" gotcha) then
`_apply_put_on_deck(s, tid, to_top)` relocates the unit: strips non-token upgrades to
owners' discards, resets (damage 0/exhausted False/face_down True + clears
cannot_ready/defeat_at_regroup/return_to_owner_hand_at_regroup flags), removes from
arena, `deck.insert(0,ci)` for TOP (deck[0] = drawn-first) or `deck.append` for BOTTOM,
drops permanent modifiers it sourced. **A RELOCATION, NOT a defeat** — no WhenDefeated
fires on the moved unit. Registered in `invariants._KNOWN_DECISION_KINDS`, web/session
`_PROMPTS`, bot `_choose_put_on_deck` (always PutOnDeckTop — owner draws their card
back soonest; both actions card-anchored so no `_SAFE_DEFAULT_ORDER` entry).
**ENCODING LOF_200** (Ambush = keyword layer; canonical LOF = shipped set): an
**OPTIONAL** `WhenDefeated` (the "you may") whose one `CustomEffect(target=TargetSpec(
controller="any", kind="unit", arena="ground", predicates=("non_leader",)))` is a thin
adapter pushing `put_on_deck` from inside resolve_effects (Palpatine SOR_135 inline-push;
`_resolve_put_on_deck` guards active_player restore with `if not pending_decisions` so
the buried resolve_effects's after_resolve isn't clobbered). CustomEffect.target gates
the optional trigger → auto-declines with no ground unit. In `lof/abilities.py`.
**FACE: LOF_200 + P25_94 + P26_64 byte-identical** (7/5, cost 7, same Ambush+WhenDefeated
text) → plain same-face aliases `("P25","94")/("P26","64") → ("LOF","200")` reprints.py
"batch 24". Tests `tests/test_lof_cards.py::TestQuiGonJinnLOF200` (5: enemy→top; enemy
→bottom; friendly→owner deck + upgrades stripped; no-ground-unit auto-declines; declinable
— GOTCHA: test harness `_defeat_and_fire` doesn't run apply()'s AutoResolveEffects, so
drain the buried empty resolve_effects with a `_drain` helper before asserting clean).
**REMAINING 27 grp**, all genuine 1-per-primitive escalation (the two 2-for-1 balloons
still STOP-and-defer: damage-prevention Malakili LOF_108 + Amidala J25_16, and "lose all
abilities" Galen P25_31 + Mind Trick LOF_202). See [[reprint-duplicates]].

**STAGE 4 BATCH 23 DONE 2026-07-13 (FRAMEWORK ESCALATION — opponent-decided modal;
NO new decision kind — EXTENDED the existing `choose_two_modal` kind with a
`decider_id` opponent shift + pick=1).** Re-ran `find_reprints` FIRST (still 29,
`--check OK` — no new-set import had reopened the easy phase; no trivial stragglers,
so no AskUserQuestion fork). **Leverage ranking:** every remaining group is
1-per-primitive; the only apparent 2-for-1 beyond the deferred damage-prevention
balloon is "lose all abilities" (Galen Erso P25_31 + Mind Trick LOF_202) but I
CONFIRMED it BALLOONS — Galen needs a *name-a-card* decision + a persistent aura
reaching cards NOT in play; Mind Trick needs a *power-budget-exhaust* selection + a
this-phase per-instance marker; different application mechanisms, each depending on a
SECOND unbuilt primitive → STOP-and-defer. So picked by tie-break 1 (smallest surface
/ closest mirror to an existing push_): **Luke Skywalker LAW_80** — "When Played: An
opponent chooses one: [they create a Credit token, ready this] / [you may deal 5 to a
unit]." Cleared **1 grp**: needs_encoding **29→28**, already_covered **163→164**; 4
tests, `--check OK`.
**THE PRIMITIVE — extended `push_choose_modal` (batch-15 choose_two_modal), NOT a new
decision kind.** Added one optional `decider_id: str | None = None` param (default =
controller → byte-identical to the 4 SOR aspect events): when set, the modal's
`deciding_player_id`/`active_player_index`/context `decider_id` become the decider's
(the say_no SOR_233 decider shift). `_resolve_choose_two_modal` needed **ZERO change**
— it already pops and pushes each chosen option's `resolve_effects` owned by the
CONTROLLER and hands active back to the controller (opponent picks the MODE; controller
resolves it — "you may deal 5" stays the controller's target choice). Reuses
SelectModalOption; `choose_two_modal` already in invariants `_KNOWN_DECISION_KINDS` +
web `_PROMPTS` (only genericised the prompt text from "two of the four" → "the listed
options") + bot `_choose_two_modal` (first-available; acceptable for the opponent seat)
→ **ZERO new registrations**.
**THE ONE SUBTLETY — option-spec type.** Batch-15 registers option specs as
`TriggerAbility(WhenPlayed())`, safe ONLY because an event is never in `_cards_in_play`.
Luke is a **UNIT in play** → `_collect_triggers` (collects only `TriggerAbility`) would
wrongly fire idx-1/idx-2 on his entry. FIX: register the option specs as **`EventAbility`**
— `resolve_effects` reads any spec's `.effects` (not just TriggerAbility), `_collect_triggers`
skips EventAbility, and an EventAbility on a Unit is NEVER run by `_resolve_event_ability`
(fires only for Event *cards*). So idx 0 = `TriggerAbility(WhenPlayed → CustomEffect
pushing the modal with decider_id=opponent, pick=1)`; idx 1 = `EventAbility([CustomEffect
_luke_law80_opt_credit_ready])` (opponent creates a Credit for THEMSELVES via
`tokens.create_credit_token(opponent_ps)` + ready Luke inline); idx 2 =
`EventAbility([DealDamage(5, any unit, optional=True)])`. In `law/abilities.py` (LAW =
shipped set → canonical there). Opponent = the player != source.owner_id (2-player).
**FACE: LAW_80 + P26_112 byte-identical** (9/7, cost 7, same text, no reminder split) →
plain same-face alias `("P26","112") → ("LAW","80")` in reprints.py "batch 23". Tests
`tests/test_law_cards.py::TestLukeSkywalkerLAW80` (4: modal owned by opponent+pick=1;
option A → opponent's credit + Luke readied; option B → controller deals 5; option B
declinable). **REMAINING 28 grp**, all genuine 1-per-primitive escalation (the one
2-for-1 = damage-prevention Malakili LOF_108 + Amidala J25_16, still a STOP-and-defer
2-primitive balloon; "lose all abilities" Galen+Mind Trick ALSO a balloon — see above).
See [[reprint-duplicates]].

**STAGE 4 STRAGGLER DONE 2026-07-13 (NOT an escalation — the "register-as-vanilla"
CLASSIFIER EXEMPTION; ZERO card registration, ZERO alias).** Cleared the last
trivial straggler **Knight's Saber LOF_151 + P25_109** (byte-identical 3/2 vanilla
upgrade "Attach to a Jedi non-Vehicle unit", NO ability). **Root cause (batch-14's
diagnosis, confirmed):** a pure attach-restriction upgrade is ALREADY fully
playable — the engine parses the clause via `actions._upgrade_target_spec`
(→ traits=("Jedi",), non_vehicle) and applies printed upgrade_power/hp — it was
only MIS-classified `needs_encoding` because `audit_coverage.has_functional_text`
counted the declarative "Attach to …" prose as an ability. **The fix = ONE line in
the CANONICAL rule** (`scripts/audit_coverage.py`): a new `_ATTACH_CLAUSE_RE =
re.compile(r"attach to an? [^.\n]+\.", IGNORECASE)` stripped alongside the reminder/
bracket strips inside `has_functional_text`, BEFORE the prose check. The terminating
period scopes the strip to the restriction sentence, so "Attach to X. Attached unit
gains …" keeps its real ability. `plan_encoding.has_functional_text` delegates to
this, so planner/verifier/audit stay consistent (CLAUDE.md's single-canonical-rule
invariant). **BLAST RADIUS = exactly 4 cards** (measured): LOF_74 Bolstered
Endurance, LOF_151 + P25_109 Knight's Saber, TS26_79 Underestimated — all genuinely
pure-attach vanilla upgrades, all now classify `vanilla`/playable (CORRECT, not
count inflation). Only Knight's Saber was a >1-member reprint group → **needs_encoding
30→29, already_playable 42→43** (`--check OK`). NO reprints.py change (both members
independently vanilla-playable → nothing to alias). Tests:
`tests/test_reprints.py::TestAttachRestrictionExemption` (4: pure-attach not
functional; attach-then-ability stays functional; Knight's Saber classifies vanilla;
group in already_playable). `test_already_playable_members_all_classify_playable` +
`test_verify_playable_finds_no_exceptions` now cover it automatically. `test_deck_
coverage.py` UNAFFECTED (its own local `_has_functional_text`; scans only shipped
decks, none of the 4). **REMAINING 29 grp**, ALL genuine escalation (no more trivial
stragglers). The one 2-for-1 left is damage-prevention (Malakili LOF_108 + Amidala
J25_16, a 2-primitive balloon — STOP-and-defer). See [[reprint-duplicates]].

**STAGE 4 BATCH 22 DONE 2026-07-13 (FRAMEWORK ESCALATION — defeat-Credits-for-a-
scaling-payoff; NO new decision kind — GENERALISED the existing
`pay_resources_for_tokens` kind).** Re-ran `find_reprints` FIRST (still 31, no
new-set import had reopened the easy phase — same as batch-21 end), surveyed the
fresh canonicals: only ONE trivial straggler (Knight's Saber LOF_151, still), NOT a
batch → no AskUserQuestion fork. **Leverage:** every remaining group is
1-per-primitive EXCEPT damage-prevention (2 grp), but I RE-CONFIRMED that one
balloons (Malakili LOF_108 = passive unconditional replacement; Queen Amidala
J25_16/SEC_101 = reactive pay-a-cost prevention needing a decision AT damage-time,
incl. **pausing the combat-damage pipeline** — checked `_resolve_unit_combat_step2`,
combat damage flows through `_deal_damage_with_shield` with no decision hook → two
distinct primitives, STOP-and-defer per contract). So picked the CLEANEST 1-group by
tie-break 1 (smallest surface / closest mirror): **Cad Bane C26_5** — "On Attack:
Defeat any number of friendly Credit tokens. Give an Experience token to this unit
for each Credit defeated this way." Cleared **1 grp**: needs_encoding **31→30**,
already_covered **162→163**; 5 tests, `--check OK`, fast tier **2188 pass / 0 fail**
(118 known WinError-5 web errors).
**THE PRIMITIVE — generalised `pay_resources_for_tokens` (Curious Flock LOF_255),
NOT a new decision kind.** Cad Bane is structurally IDENTICAL to Curious Flock (each
pick removes one cost item + grants one Experience to the source INLINE — Experience
never triggers a defeat, so no "pop, then act"; FinishPayResources stops; "any
number/up to" includes 0). Only the cost SOURCE differs. So added a **`cost_source`
ctx field** ("resource" default | "credit") + support for an **unbounded cap**
(`max_resources=None`, credit-count-bounded): `push_pay_resources_for_tokens(...,
cost_source="credit", max_resources=None)`; `_pay_resources_for_tokens_can_pay`
branches (`credit` → `len(ps.credits)>0`, cap None=unbounded);
`PayResourceForToken.apply` branches (`_defeat_credit(s, ps)` vs
`_exhaust_resources(ps,1)`); push-guard requires ≥1 credit for the credit source.
REUSES the SAME `PayResourceForToken`/`FinishPayResources` actions → **ZERO new
registrations**: no `_KNOWN_DECISION_KINDS` entry, no new web-prompt kind (genericised
the existing `pay_resources_for_tokens` prompt text to mention Credit tokens), NO new
bot handler (the existing `_choose_pay_resources_for_tokens` → Finish is safe/
conservative; keying on the unchanged action-class names). Credits pile = jabba:07
(`PlayerState.credits`, `_defeat_credit(s, ps)->bool`, `tokens.create_credit_token`).
**ENCODING Cad Bane LAW_32** (Shielded/Overwhelm = keyword layer): mandatory `OnAttack
→ CustomEffect(fn)` (no `optional` — "any number" includes 0 via the decision; push
no-ops with 0 credits → clean fizzle), fn calls the generalised push helper. In
`law/abilities.py` (LAW = shipped set → CANONICAL there).
**FACE: all four members BYTE-IDENTICAL** (C26_5 / LAW_32 / P26_80 / P26_96, same
text+stats, cost 6, 6/6) — NO reminder-parenthetical split (unlike disclose), so a
single registration + plain same-face aliases: `("C26","5")/("P26","80")/("P26","96")
→ ("LAW","32")` in reprints.py. Tests `tests/test_cad_bane.py` (5, method names embed
`law_32`; GOTCHA: `apply` deep-copies so re-find Cad Bane by `instance_id` in the
final state before `_experience_count` — `_exp(state, iid)` helper). **REMAINING 30
grp.** Next trivial straggler still Knight's Saber LOF_151. The 2-for-1
damage-prevention (Malakili + Amidala) stays deferred as a genuine 2-primitive
balloon.

**STAGE 4 BATCH 21 DONE 2026-07-12 (FRAMEWORK ESCALATION — the `disclose`
primitive, new `disclose` decision kind).** ⚠️ **The easy phase HAD re-opened
AGAIN via new-set imports** (C26/J24/J25/JTLP/LAWP/MV26/P25/P26/SECP variants) — the
33-group remainder was DIFFERENT from the batch-20 roadmap (new names: BD-1, Cad
Bane, Director Krennic, Galen Erso, Kanan, Karis Nemik, Knight's Saber, Millennium
Falcon, Poe, Syril Karn, two Maul groups, Shatterpoint…). Per the standing rule I
re-ran `find_reprints` (still 31–33, `--check OK`) and **surveyed every canonical's
DB text FIRST**. Verdict: only ONE truly-trivial straggler (**Knight's Saber
LOF_151**, a vanilla 3/2 upgrade "Attach to a Jedi non-Vehicle unit", zero ability)
— NOT a batch → no AskUserQuestion fork; proceeded with escalation. **TWO 2-for-1
primitives had re-appeared** (the roadmap's "all 1-per-primitive" note went stale):
**disclose** (Karis Nemik + Syril Karn) and **damage-prevention** (Malakili +
Amidala, but TWO distinct mechanisms — passive-always vs pay-to-prevent — risks a
balloon). **Leverage pick: disclose** — 2 reprint groups, ONE uniform mechanic
(closest mirror to select_token/reveal), and it BROADLY unblocks the ~40 OTHER SEC
"You may disclose …" singleton cards (huge non-metric value). Cleared **2 grp**:
needs_encoding **33→31**, already_covered **160→162**; 8 tests, `--check OK`, fast
tier 2174 pass / 0 fail (118 known WinError-5 web errors).
**THE PRIMITIVE — `push_disclose(s, source_ci, required_aspects, *, payoff,
payoff_args, discloser_id=None)`** in actions.py. "You may disclose <aspects>
(reveal cards from hand collectively bearing those aspect ICONS). If you do,
<payoff>." A self-contained multi-select decision (select_token 'pick a covering
set' shape): `DiscloseSelectCard(id)` reveals a hand card contributing ≥1
still-needed aspect, decrementing the required multiset; when covered → auto-resolve
+ payoff; `DeclineDisclose` = the "you may". **Revealing does NOT move cards** (public
info only; NOT modeled in view — accepted). Aspects read via `card_def.aspect_names`
(dup-included list; multiset = Counter). `push_disclose` NO-OPS (no prompt) when the
discloser can't cover the requirement (`_disclose_can_satisfy` scans hand). **Payoff
= a STRING key + JSON-serialisable args** dispatched by `_apply_disclose_payoff`
(the use_force pattern — must stay JSON, invariants check ctx). Two payoff arms:
`create_ready_token` (Karis: `_create_token_units` then set exhausted=False) and
`damage_unless_discard` (Syril: `push_may_discard_else_damage`). Registered in
invariants `_KNOWN_DECISION_KINDS`, web/session `_PROMPTS`, bot dispatch
(`_choose_disclose` = greedily reveal first offered card — payoff is upside,
info-leak minor) + `DeclineDisclose` in `_SAFE_DEFAULT_ORDER`.
**KARIS NEMIK SEC_148** (Hidden = keyword layer): MANDATORY `WhenDefeated →
CustomEffect(fn)` (no `optional` — the "you may" lives in disclose Decline)
disclosing Aggression+Heroism → payoff `create_ready_token` (Spy token, readied).
Source is defeated/in-limbo but ctx stores `discloser_id` so payoff creates for the
right player. **SYRIL KARN SEC_133**: MANDATORY `OnAttack → CustomEffect(fn,
target=TargetSpec(controller="enemy", kind="unit"))` — target chosen UP FRONT (a
cosmetic reorder of printed "disclose, then choose a unit"; documented), disclose
Agg×2+Villainy → payoff `damage_unless_discard(target, 2)`. **REUSED/EXTENDED (NOT a
2nd new primitive): `may_discard` gained an else="damage" variant** —
`push_may_discard_else_damage(s, source_ci, target_id, amount)` (decider = target's
controller, the say_no SOR_233 shift; empty hand → damage inline) + a `DeclineDiscard`
branch (`ctx["else_effect"]=="damage"` → `_apply_deal_damage`, else the old tokens).
Discard is RANDOM (reuses `DiscardRandomCard`) = the established discard
simplification (Syril text says "discards a card"; documented).
**GOTCHA — FACE-IDENTITY GUARD SPLITS THE GROUP:** `find_reprints` groups by a
reminder-STRIPPED face, but `reprints.apply_reprint_aliases` compares FULL
normalized `text` (incl. "(reveal cards…)" reminder). So each group holds **TWO
exact-faces**: the SEC printing WITH the reminder vs the J25/P26 printings WITHOUT.
Aliasing ONLY works within an identical face → **register the ability under BOTH
faces via STACKED `@card_ability` decorators** (`card_ability` returns `fn`, so
`@card_ability("SEC","148")` over `@card_ability("J25","17")` registers both) and
alias only same-face twins: P26_77/84/93/100 → **J25_17** (no-reminder), P26_54 →
**P26_42** (no-reminder); SEC_148/SEC_133 registered directly. (My first attempt
aliasing J25_17→SEC_148 RAISED "face mismatch" at import — that's the guard working.)
Cards in `sec/abilities.py`; tests `tests/test_disclose.py` (8, method names embed
sec_148/sec_133). **FOLLOW-ON the disclose primitive ALSO unblocks (future, easy):**
~40 SEC singleton disclose cards (Ahsoka SEC_96, Charged-with-X removal events,
Chancellor Valorum, Mina Bonteri, The Galleon "create 3 Spy", Vice Admiral Rampart,
etc.) — each just needs its own `push_disclose(..., payoff=…)` adapter + a payoff arm
(most reuse existing seams). **STILL-TRIVIAL STRAGGLER to clear next: Knight's Saber
LOF_151** (vanilla upgrade — register with empty/attach-only spec + alias P25_109).
**REMAINING 31 grp.** Genuine-escalation remainder (mostly 1-per-primitive; the
one 2-for-1 left is **damage-prevention** Malakili LOF_108 + Queen Amidala J25_16):
Darth Maul C24_6 (multi-defender "attack 2 units" — BIG), [✅ Cad Bane C26_5 =
DONE in BATCH 22 via generalised pay_resources_for_tokens cost_source="credit"],
Darth Nihilus P26_79 (least-HP damage), Darth Vader C24_2
(search-multi-play-free), Director Krennic JTLP_1 (per-round first-WhenDefeated
discount), Galen Erso P25_31 (name-a-card ability-loss aura), Thrawn P25_33/SEC_193
(capture), Grogu ASH_18 (leader deploy+combat-mod), Jabba ASH_42 (return upgrade
replay-free), Kanan LAW_89 (return-to-hand conditional cap), Ki-Adi J25_2/TWI_64
(per-phase opp-play counter), Lawbringer LAW_101 (choose-aspect mass debuff), Leia
LOF_98 (arena-move+granted action), Luke J25_4 (pilot-defeat-to-ground), Luke LAW_80
(opponent-chooses modal), Maul J24_4 (redirect combat dmg), Maul LAW_54 (take-control
on base dmg), Max Rebo LAW_72 (extra regroup), Millennium Falcon P25_92 (regroup
pay-or-bounce), Mind Trick LOF_202 (exhaust + ability-loss), Poe JTLP_6 (X-Wing +
self-as-upgrade), Qui-Gon LOF_200 (put-on-deck), Shatterpoint P25_153 (modal+Force),
Eye of Aldhani SEC_73 (delayed pay-or-exhaust), Ghost J25_1 (keyword-copy aura),
Stranger LAW_86 (defender-first-strike), Always Two LOF_42 (choose-2 + mass-defeat),
BD-1 C25_4 (persistent chosen-unit buff+keyword), Knight's Saber LOF_151 (TRIVIAL).

**STAGE 4 BATCH 20 DONE 2026-07-12 (FRAMEWORK ESCALATION — new multi-decider
`owner_may_replay` decision kind).** After batch 19 swept the fresh anthology/promo
easy groups in the SAME session, I re-ran `find_reprints` (still 35 needs_encoding,
`--check OK`) and confirmed NO new easy groups had appeared, so the escalation
premise genuinely held again — proceeded with the escalation contract. **Leverage
pick:** every remaining primitive clears exactly 1 group EXCEPT the "return a unit,
then its owner may play it for free" primitive, which clears **2 groups with one new
primitive** (the sole 2-for-1) — **Baylan Skoll LOF_185 + Rio Durant LAW_93** (+2
siblings LOFP_14, P26_2). needs_encoding **35→33 grp**, already_covered **158→160**;
8 new tests pass, `find_reprints.py --check` exits 0. No change to core resolution or
the trigger/decision machinery — a self-contained new decision kind (the allowed
small-primitive path).
- **The primitive (`owner_may_replay`, actions.py):** "return a non-leader unit to
  its owner's hand; then, its owner may play it for FREE." A MULTI-DECIDER decision:
  the returned unit's OWNER — who may be the source's OPPONENT — decides whether to
  replay it (the say_no SOR_233 / opponent_chooses_target SHD_246 deciding-player
  shift; an ordinary `play_from_hand` decision is ALWAYS decided by the source's
  controller, so it cannot express this). The return happens INLINE first (via
  `resolver._apply_return_to_hand`, which sends the card to its OWNER's hand
  regardless of controller), THEN `push_owner_may_replay(s, source_ci, returned_id,
  *, grant_keyword=None)` hands the owner the decision. Two Action classes:
  `ReplayReturnedUnit(instance_id)` (take the card from the owner's hand, play it for
  cost 0 via `_put_unit_in_play(grant_keyword=…, cost_paid=0)` — the PlayFromHand free
  path; **pop the decision BEFORE the unit enters play** so its own WhenPlayed/keyword
  triggers land on a clean stack, the push_distribute_damage "pop, then act" gotcha) +
  `DeclineReplay` (the "may"). `grant_keyword` (Rio's "Shielded") is applied before the
  enter-play keyword bus so a granted Shielded winks on → the replay gets a Shield
  token on entry. Registered in `invariants._KNOWN_DECISION_KINDS`, `web/session.py`
  `_PROMPTS` (default prompt, no per-stage branch needed), and `HeuristicBot`
  (`_choose_owner_may_replay` = always replay when offered — a free unit back in play
  is pure upside — else decline; `DeclineReplay` in `_SAFE_DEFAULT_ORDER`).
- **The two encodings** (both an optional `WhenPlayed` whose one `CustomEffect` has a
  `target=TargetSpec(controller="any", kind="unit", predicates=("non_leader",),
  cost_max=N)` and whose fn calls `_apply_return_to_hand` then `push_owner_may_replay`):
  - **Baylan LOF_185** (Hidden = keyword layer; in `lof/abilities.py`): gated
    `condition=CONTROLLER_HAS_FORCE_TOKEN` — the AcceptTrigger IS the "you may use the
    Force" choice; the fn `spend_force_token(state, ps)` FIRST (if False → return, "if
    you do"), cost_max=4, NO grant_keyword. With a token but no eligible ≤4 unit the
    optional trigger auto-declines (token preserved).
  - **Rio LAW_93** (in `law/abilities.py`): ungated optional WhenPlayed, cost_max=3,
    `grant_keyword="Shielded"`.
- **GOTCHA:** the CustomEffect fn pushes `owner_may_replay` from INSIDE resolve_effects
  (the Palpatine SOR_135 inline-resolve-then-push) — it lands on top of the buried
  resolve_effects decision, resolves first (LIFO), then AutoResolveEffects drains the
  (now-empty) resolve_effects. So `ReplayReturnedUnit`/`DeclineReplay` guard their
  `active_player_index` restore with `if not s.pending_decisions` (the buried
  resolve_effects is still there → don't clobber its after_resolve).
- **Siblings aliased (`REPRINT_ALIASES` "batch 20"):** LOF_185 ← LOFP_14; LAW_93 ← P26_2.
- **Tests:** `tests/test_owner_may_replay.py` (8 tests, card numbers `lof_185`/`law_93`
  in each name; force-return→owner(opponent)-replays, owner-declines, decline-Force-
  keeps-token, no-token-not-offered, cost-cap, Rio-Shield-on-replay, friendly-return→
  owner-is-controller, Rio-cost-4-excluded). Helpers reuse test_sor_cards.
- **NEXT SESSION:** 33 needs_encoding groups remain. Re-run `find_reprints.py` FIRST —
  the easy phase has reopened TWICE on new-set imports (IBH, then anthology/promo), so
  **always survey the fresh canonicals and re-offer the AskUserQuestion fork before
  assuming escalation.** The genuine-escalation remainder is now all 1-group-per-primitive
  (no more 2-for-1): TWI_64 Ki-Adi (per-phase play counter), the self-contained-decision-
  kind cards (Always Two LOF_42, Cad Bane LAW_32, Qui-Gon LOF_200, Luke LAW_80, Darth
  Vader SOR_87), damage-prevention (Malakili LOF_108, Queen Amidala SEC_101), Thrawn
  SEC_193 capture, Ghost JTL_53 keyword-copy, Stranger LAW_86 defender-first-strike, Max
  Rebo LAW_72 extra regroup, Mind Trick LOF_202, Eye of Aldhani SEC_73, Lawbringer
  LAW_101, Leia LOF_98 arena-move, plus the batch-19 borderline easy-with-a-seam (BD-1
  C25_4, Luke J25_4, Grogu ASH_18, Darth Nihilus P26_79).

---

**STAGE 4 BATCH 19 DONE 2026-07-12 (EASY-ENCODE SWEEP — NOT a framework escalation;
the SECOND consecutive time the re-pasted escalation prompt's premise was invalidated
by newly-imported sets).** Since batch 18, new **anthology/convention/promo sets**
(**ASH, C24, C25, G25, J25, P25, P26** — plus JTLP/LOFP already present) were imported
into `data/swu.db`, refilling the easy phase with fresh reprint faces (own subtitle,
NO shipped-set member) that compose from EXISTING primitives. Re-ran the AskUserQuestion
fork (per the standing instruction); user again chose the easy batch. Cleared **17
groups**: **needs_encoding 52→35 grp, already_covered 141→158**; 22 new tests pass,
`find_reprints.py --check` exits 0, `--check OK`. NEW module `src/swu/cards/promo/`
(+`promo/abilities.py`), registered in `cards/__init__.py` right after `ibh`. All
promo canonicals live here (no per-promo-set folders — one shared module).
- **ONE tiny additive seam:** new `StatBonus.count="controller_hand_size"` arm in
  `_stat_bonus_count` (engine/actions.py) = `len(controller.hand)`, for **Qi'ra
  ASH_226** "-1/-0 for each card in your hand" (the Nien Nunb JTL_93 scaling-StatBonus
  pattern; negative base × count). NO new decision kind, no machinery change.
- **The 17 groups (canonical registered = one member; sibs aliased in `reprints.py`
  "batch 19"):**
  - **Exact pattern-twins of implemented shipped cards** (mirror the twin's spec, but a
    DISTINCT face so a fresh @card_ability, NOT an alias): P26_81 Han Solo (=Han LAW_37
    `OnAttack GiveToken(Exp,SELF)`), P25_1 Bossk (=Bossk JTL_187 — Piloting, plain
    `OnAttack [ExhaustCard(DEFENDER),DealDamage(1,DEFENDER)]` + `GrantedAbility` clone),
    JTLP_7 Chewbacca (=JTL_103 `ConstantAbility(SELF,Protection(defeat,return))`),
    P25_96 Darth Tyranus (=LOF_231 `KeywordGrant(Ambush)` cond CONTROLLER_HAS_FORCE_TOKEN),
    G25_3 Obi-Wan (=LOF_96 `WhenYouPlayCard(Force,unit,exclude_self=False)`→Sentinel this
    phase), C24_3 Emperor Palpatine (=SOR_135 `push_distribute_damage(6,enemy)`),
    P25_151 Karis (=LOF_31 WhenDefeated force→ -2/-2), G25_2 Darth Sidious (=LOF_39
    WhenPlayed force→defeat each non-Sith unit ≤3 remaining HP).
  - **Trivial constants/triggers:** ASH_243 Darth Vader (`KeywordGrant(Sentinel)` cond
    SOURCE_READY; Shielded kept), P26_75 Naboo Royal Starship (`ConstantAbility(friendly
    leader-unit, [KeywordGrant(Raid,2),KeywordGrant(Overwhelm)])`; Plot kw), J25_18
    General Grievous (`WhenAttacked→ReturnToHand(SELF)`; Hidden kw), P25_7 **and** P25_157
    Black One (TWO distinct groups, identical spec: `ConstantAbility(SELF,StatBonus(1,0),
    SOURCE_UPGRADED)` + optional `OnAttack DealDamage(1,unit)` gated
    CONTROLLER_CONTROLS_NAMED("Poe Dameron")).
  - **Force-token reuse** (qui-gon:06 primitive; local `_use_force_then(fn)` wrapper =
    spend_force_token then fn, "if you do"): LOFP_10 Mace Windu (optional WhenPlayed
    gated CONTROLLER_HAS_FORCE_TOKEN → deal 4 to a unit), P25_129 Vernestra Rwoh (→ready
    self, no-target). All optional-trigger AcceptTrigger = the "use the Force" choice.
  - **Qi'ra ASH_226:** scaling self-debuff (new count) + optional WhenPlayed discard→deal
    3 (Merrin LOF_160 gated CONTROLLER_HAS_CARD_IN_HAND, first-card discard).
  - **BB-8 C25_2:** Piloting; `WhenPlayed(as_upgrade=True)` optional gated
    CONTROLLER_N_PLUS_READY_RESOURCES(2), CustomEffect(target=friendly Resistance unit)
    exhausts 2 resources + readies target. (Test: fire via `_fire_upgrade_played`.)
- **KEY GOTCHAS:** (1) `state.find_instance(id)` returns a **(ps, ci) TUPLE**, not a ci —
  unpack `result[1]` (the test-file `_find_instance` helper differs, returns ci-or-None).
  (2) Sanitiser: self-grant rules strip Vader/Tyranus/Obi-Wan mis-tagged printed
  Sentinel/Ambush correctly; BUT for Naboo's compound "gains Raid 2 **and** Overwhelm"
  the grants-to-others matcher strips only Raid (the keyword right after "gains"), leaving
  a cosmetic printed Overwhelm on Naboo — accepted (promo Vehicle, no soak/fixture deck;
  documented in its docstring; NOT worth a sanitiser change in an easy batch).
- **Tests:** `tests/test_promo_cards.py` (22 tests, card number in each method name; reuses
  SOR/SHD/LOF helpers incl. `_fire_card_played`, `_defeat_and_fire`, `_fire_upgrade_played`;
  local `_drain`=AutoResolveEffects-to-quiescence for no-target CustomEffects).
- **DEFERRED as still-needing-a-real-seam (NOT in this batch):** BD-1 C25_4 (permanent
  keyword-grant source-in-play — Huyang extends only stats), Luke J25_4 (Piloting
  pilot-death-redirect), Grogu ASH_18 (deploy-trigger "when you play a unique unit cost
  4+"), Darth Nihilus P26_79 ("least remaining HP among other units" auto-target selector).
- **NEXT SESSION:** 35 needs_encoding groups remain. Re-run `find_reprints.py` FIRST — the
  easy phase has now reopened TWICE (IBH, then anthology/promo), so **always survey the
  fresh canonicals before assuming escalation**; re-run the AskUserQuestion fork if a fresh
  batch of trivial groups appears. The genuine-escalation remainder (highest leverage first):
  return-then-owner-replays-free (Baylan LOF_185 + Rio LAW_93 = **2 grp/1 primitive**), then
  TWI_64 Ki-Adi (per-phase play counter), the self-contained-decision-kind cards (Always Two
  LOF_42, Cad Bane LAW_32, Qui-Gon LOF_200, Luke LAW_80, Darth Vader SOR_87), damage-
  prevention (Malakili LOF_108, Queen Amidala SEC_101), Thrawn SEC_193 capture, Ghost JTL_53
  keyword-copy, Stranger LAW_86 defender-first-strike, Max Rebo LAW_72 extra regroup, Mind
  Trick LOF_202, Eye of Aldhani SEC_73, Lawbringer LAW_101 choose-aspect, Leia LOF_98
  arena-move, plus the borderline easy-with-a-seam (BD-1/Nihilus/etc. above).

---

**STAGE 4 BATCH 18 DONE 2026-07-12 (EASY-ENCODE SWEEP — NOT a framework escalation).**
The escalation prompt's premise ("the iterative easy-encode phase is OVER — every
remaining group needs a new primitive") was INVALIDATED by a new set: **IBH** ("Intro
B..."/Battle-of-Hoth reprint faces) was imported into `data/swu.db` since the batch-14
survey, adding **19 new needs_encoding reprint groups** — each a fresh face (own
subtitle/text, so its own group; NOT a reprint of the implemented same-named twin) that
composes from EXISTING primitives, the batch-7–13 shape. Surfaced this to the user (via
AskUserQuestion), who chose the easy-encode batch over a single-primitive escalation.
Cleared ALL 19: **needs_encoding 71→52 grp, already_covered 122→141**; 24 new tests pass,
`find_reprints.py --check` exits 0, fast tier **2043 pass** (only the 118 pre-existing
WinError-5 web PermissionError collection errors). NEW module `src/swu/cards/ibh/` (+
`ibh/abilities.py`), registered in `cards/__init__.py` right after `lof`.
- **Two tiny additive seams (no new decision kind, no core-machinery change):**
  1. **`rest_disposition="discard"` on `push_deck_search`** (default `"bottom"`) — the
     un-taken searched cards go to discard instead of the deck bottom, for **I've Found
     Them IBH_9** ("Reveal top 3, draw a unit, discard the other revealed cards"):
     `push_deck_search(count=1, window=3, up_to=False, eligible=isinstance Unit,
     rest_disposition="discard")`. `_finish_deck_search` branches on `ctx["rest_disposition"]`.
  2. **`attacker_aspect` field on `push_granted_attack`** (mirror of `attacker_trait`) —
     filters offered attackers by ASPECT, for **General Rieekan IBH_23** ("Action
     [Exhaust]: Attack with another Heroism unit. +2/+0"). **KEY GOTCHA: "a Heroism/
     Aggression/Vigilance/etc. unit" is an ASPECT, not a trait** — `attacker_trait="Heroism"`
     matched nothing (traits are strings like Rebel/Droid; aspects are `AspectPip` objects
     with `.name`). New filter reads `{asp.name for asp in card_def.aspects}`.
- **The conditional-draw cards use `CONTROLLER_HAS_OTHER_ASPECT_UNIT(aspect)` (correct
  even though it excludes the source):** each of Piett/C-3PO/Veers/R2-D2 needs an aspect
  the SOURCE itself lacks (Piett=Vig/Vill needs Aggression; C-3PO=Cmd/Hero needs Cunning;
  Veers=Agg/Vill needs Vigilance; R2-D2=Cun/Hero needs Command), so "other" never wrongly
  excludes a qualifying self. The condition gates trigger COLLECTION → no draw/no prompt
  when absent (mandatory when present). Neat: the four IBH cards cross-enable each other
  in tests (Veers=Aggression enables Piett, R2-D2=Cunning enables C-3PO, etc.).
- **The 19 encodings (all in `ibh/abilities.py`; canonical = lowest number):**
  Events — IBH_61 We're In Trouble (`DealDamage(3,unit)`), IBH_59 Target the Main
  Generator (`DealDamage(2,base)`), IBH_66 Too Strong for Blasters (`Heal(2,unit)`),
  IBH_18 Go for the Legs (`ExhaustCard(enemy ground unit)`), IBH_5 I'll Cover For You
  (Grenade-Strike TWI_171 record-then-`excludes_event_target` two-effect "another enemy
  unit"), IBH_21 Improvised Detonation (`push_granted_attack(+2)`), IBH_74 I Want Proof
  (`[DrawCards(2), DiscardFromHand(controller)]` — first-card discard DEVIATION), IBH_9
  I've Found Them (deck_search discard-rest). Unit triggers — IBH_82 Admiral Ozzel
  (`WhenDefeated DiscardFromHand(opponent)`), IBH_60 Admiral Piett (`OnAttack DrawCards`
  gated Aggression), IBH_19 C-3PO (`WhenPlayed DrawCards` gated Cunning), IBH_68 General
  Veers (`WhenPlayed [DealDamage(2,enemy base EACH_ENEMY), Heal(2,own base EACH_FRIENDLY)]`
  gated Vigilance), IBH_11 R2-D2 (`OnAttack ExhaustCard(enemy ground cost≤4)` gated
  Command), IBH_6 Rebellion Y-Wing (`OnAttack DealDamage(1,base)`), IBH_15 Tauntaun Mount
  (`WhenDefeated Heal(2,own base EACH_FRIENDLY)`), IBH_64 Hoth Lieutenant (`WhenPlayed →
  push_granted_attack(+2,optional,exclude_source)`). Activated — IBH_16 Ion Cannon
  (`[ExhaustSelf] DealDamage(3,space unit)`), IBH_62 Imperial Deck Officer (`[ExhaustSelf]
  Heal(2,Villainy unit)`), IBH_23 General Rieekan (`[ExhaustSelf] → push_granted_attack(+2,
  attacker_aspect="Heroism",exclude_source)`).
- **Siblings aliased (`REPRINT_ALIASES` "batch 18", all IBH-internal):** each canonical ←
  its second (or third) IBH number; e.g. IBH_82←85, IBH_6←24,32, IBH_15←28,51 (full block
  in reprints.py). Tests: `tests/test_ibh_cards.py` (24 tests, card number in each name).
- **NEXT SESSION:** the IBH easy fruit is now exhausted (all 19 IBH reprint groups
  cleared; the remaining 52 needs_encoding are the OLD shipped-canonical new-primitive
  remainder). Resume framework escalation: **TWI_64 Ki-Adi-Mundi** (opponent-plays-2nd-
  card-each-phase — a per-phase-per-player play counter, NOT a ledger observer), then the
  self-contained-decision-kind cards (LOF_42 Always Two, LAW_32 Cad Bane, LOF_200 Qui-Gon,
  LAW_80 Luke, SOR_87 Darth Vader). (Watch for FUTURE new sets refilling the easy phase —
  re-run the AskUserQuestion fork if `find_reprints` shows a fresh batch of trivial groups.)

---

**STAGE 4 BATCH 17 DONE 2026-07-12 (FRAMEWORK ESCALATION — new `WhenYouUseForce`
observer trigger).** Built the highest-leverage remaining primitive: ONE new observer
trigger clears **1** needs_encoding group — **Yoda LOF_101** ("When you use the Force:
you may deal damage to a unit equal to twice the number of units you control") (+2
siblings J25_11, LOFP_6). needs_encoding 72→71 grp, already_covered 121→122; 4 new
tests pass, `find_reprints.py --check` exits 0, fast tier **1956 pass** (only the 118
pre-existing WinError-5 web PermissionError collection errors). No new decision kind —
reuses trigger_option/resolve_effects, so NO invariants/web/session/bot change. An EXACT
mirror of the batch-16 `WhenYouDraw` (and batch's-prior `WhenDealNonCombatDamage`)
ledger+settle observer, reusing the qui-gon-jinn:06 Force-token primitive.
- **The primitive (`WhenYouUseForce`, registry.py):** `@dataclass class WhenYouUseForce`
  (no fields). `event` is None (synthesised observer fire). Fires when the source's
  controller USES THE FORCE (spends their Force token, for ANY reason). Detection
  mirrors WhenYouDraw EXACTLY: every spend routes through the new single chokepoint
  `actions.spend_force_token(s, ps) -> bool` (sets `ps.has_force_token=False`, appends
  `ps.player_id` to new `GameMemory.force_uses` ledger; returns False if no token so
  callers keep their "if you do" early-return); the ledger is drained at the `apply()`
  settle-point by new `actions._fire_force_observers` (mirror of `_fire_draw_observers`,
  called right after it), firing `fire_triggered_abilities(s, None,
  event_ctx={"force_used_player_id": pid})`. **WHY a ledger not inline:** Force is
  usually spent deep inside a `CustomEffect` (mid-resolution) — firing inline would push
  a decision onto a mid-resolution stack.
- **CHOKEPOINT CONSOLIDATION (the one non-trivial part vs WhenYouDraw):** unlike draws
  (ONE site, `_draw_cards`), the Force-token spend was **dispersed across 8 sites** — 6
  card `CustomEffect` fns in `lof/abilities.py` (Luke LOF_249, `_use_force_debuff`, Darth
  Sidious, Chirrut, Infused Brawler LOF_156, Kylo Ren LOF_229) + 2 engine sites (the
  `UseForce` ability cost in `UseAbility.apply`; the `use_force` decision's
  `UseForceOption.apply`). All 8 `ps.has_force_token=False` sites now route through
  `spend_force_token` (mechanical refactor, NOT a 2nd primitive — the analogue of
  `_draw_cards` being the one draw site). The 6 card fns use an inline `from
  swu.engine.actions import spend_force_token`. Only `spend_force_token` itself still
  writes `has_force_token=False`.
- **ONE collection site (SIMPLER than WhenYouDraw):** Yoda observes from in-play, so the
  EXISTING arena scan already collects `WhenYouUseForce` — NO new collection site, no
  hand scan. `_trigger_matches` arm: `event_ctx.get("force_used_player_id") ==
  source_ci.owner_id`. **NO self-chain gate needed** (unlike Boba JTL_9 `SOURCE_READY`):
  Yoda's payoff deals damage, which does not use the Force, so it cannot re-fire.
- **New `DealDamageEqualTo` count `source_controller_units_x2`** (resolver
  `_scaling_magnitude`, before the `find_instance` line — target-independent) = 2 ×
  (len ground_arena + len space_arena) of the source controller. For Yoda's payoff.
- **Encoding LOF_101 Yoda:** `[WhenPlayed optional gated CONTROLLER_HAS_FORCE_TOKEN →
  CustomEffect(_yoda_use_force_heal: spend_force_token then heal 5 from own base),
  WhenYouUseForce() optional → DealDamageEqualTo(any unit,
  count="source_controller_units_x2")]`. The WhenPlayed Accept/Decline IS the "you may
  use the Force" choice (Infused Brawler LOF_156 pattern); its token-spend records into
  the ledger, drained at settle to fire the 2nd ability (per the card's rules box "using
  the Force for When Played triggers his second ability").
- **Siblings aliased (`REPRINT_ALIASES` "batch 17"):** LOF_101 ← J25_11, LOFP_6.
- **Tests:** `tests/test_lof_cards.py::TestYodaLOF101` (WhenPlayed use-Force heals 5 &
  triggers 2nd ability→deal 2×units; decline WhenPlayed→token kept/no force use;
  use-Force by any route→observer fires w/ x2 magnitude; decline 2nd ability→no damage).
  GOTCHA: `_fire_when_played` uses `fire_triggered_abilities` (NO settle), but `apply()`
  runs `_fire_force_observers` — so drive WhenPlayed via `apply`+AutoResolveEffects and
  the observer chains at the AutoResolveEffects settle. Design note:
  `docs/design_when_you_use_force_observer.md`. `force_uses` JSON round-trip verified.
- **NEXT SESSION:** the LAST remaining *new-observer* card is **TWI_64 Ki-Adi-Mundi**
  ("Coordinate — When an opponent plays their 2nd card each phase: draw 2") — needs a
  NEW per-phase-per-player play counter (a `GameMemory` counter reset each phase +
  fire on the exact 2nd opponent play), NOT a ledger observer. After that, the
  self-contained-decision-kind cards (LOF_42 Always Two, LAW_32 Cad Bane, LOF_200
  Qui-Gon, LAW_80 Luke, SOR_87 Darth Vader).

---

**STAGE 4 BATCH 16 DONE 2026-07-11 (FRAMEWORK ESCALATION — new `WhenYouDraw` observer
trigger).** Built the highest-leverage remaining primitive: ONE new observer trigger
clears **2** needs_encoding groups — **The Mandalorian LAW_52** ("When you draw 1+ cards
during the action phase: give this unit a Shield") + **Rey LOF_148** ("When you draw this
card during the action phase: … deal 2 to a unit and 2 to a base") (+4 promo siblings).
needs_encoding 74→72 grp, already_covered 119→121; 8 new tests pass, `find_reprints.py
--check` exits 0, fast tier **1946 pass** (only the 118 pre-existing WinError-5 web
PermissionError collection errors). No new decision kind — reuses trigger_option/
resolve_effects, so NO invariants/web/session/bot change. An EXACT mirror of the
`WhenDealNonCombatDamage` (Boba JTL_9) ledger+settle observer.
- **The primitive (`WhenYouDraw`, registry.py):** `@dataclass class WhenYouDraw:
  on_self: bool = False`. `event` is None (synthesised observer fire). Detection mirrors
  WhenDealNonCombatDamage EXACTLY: `_draw_cards` records one `{"player_id","card_ids"}`
  entry per ACTION-phase draw *event* into new `GameMemory.action_phase_draws` (guarded
  `drawn>0 and s.phase==Phase.ACTION` → regroup/setup draws excluded, so "during the
  action phase" is intrinsic; regroup draw sets Phase.REGROUP BEFORE drawing); ledger
  drained at the `apply()` settle-point by new `actions._fire_draw_observers` (mirror of
  `_fire_noncombat_damage_observers`, called right after it), firing
  `fire_triggered_abilities(s, None, event_ctx={"drew_player_id","drawn_card_ids"})`.
  **WHY a ledger not inline:** `_draw_cards` is called deep inside effect resolution
  (WhenPlayed DrawCards, activated abilities, mid-resolve_effects) — firing inline would
  push a decision onto a mid-resolution stack.
- **Two collection sites, ONE trigger kind (like WhenDefeated's 3 sites):** `_trigger_matches`
  `WhenYouDraw` arm: `on_self` → `source_ci.instance_id in event_ctx["drawn_card_ids"]`;
  else → `event_ctx["drew_player_id"] == source_ci.owner_id`. (1) LAW_52 in-play observer =
  collected by the EXISTING arena scan (matches on drew_player_id). (2) LOF_148 drawn-card =
  NEW hand scan in `_collect_triggers` (iterate `event_ctx["drawn_card_ids"]`, find each in
  the drawer's hand, collect its `WhenYouDraw(on_self=True)` triggers — the arena scan never
  yields a hand card). **Resolving from a hand source needs NO new machinery:** `find_instance`
  already scans `all_instances()` (incl. hand), and the effects target the board, not the source.
- **New condition atom `CONTROLLER_HAS_ASPECT_LEADER_OR_BASE(param)`** (registry) — reads
  `ps.base_instance`/`ps.leader_instance` `.aspects` names; gates LOF_148's "If you control an
  Aggression leader or base". Rey's "you may reveal this card from your hand" IS the optional
  trigger's Accept/Decline (reveal modelled as a documented no-op — Rey stays in hand).
- **Encodings:** LAW_52 = `[WhenPlayed [DrawCards(1)], WhenYouDraw() [GiveToken("Shield",
  fixed=SELF)]]` (mandatory; its own WhenPlayed draw feeds it a Shield since it is in play by
  the drain). LOF_148 = `WhenYouDraw(on_self=True), optional=True,
  condition=CONTROLLER_HAS_ASPECT_LEADER_OR_BASE("Aggression"), effects=[DealDamage(2,unit),
  DealDamage(2,base)]`.
- **Siblings aliased (`REPRINT_ALIASES` "batch 16"):** LAW_52 ← C26_2; LOF_148 ← J25_13,
  LOFP_9, P25_71.
- **Tests:** `tests/test_law_cards.py::TestTheMandalorianLAW52` (draw→shield, own-WhenPlayed-
  draw→shield, regroup-draw→no-shield, enemy-draw→no-shield) +
  `tests/test_lof_cards.py::TestReyLOF148` (draw→reveal→deal 2/2 & Rey stays in hand,
  no-Aggression-gate→not-offered, decline→nothing, regroup-draw→not-offered). Design note:
  `docs/design_when_you_draw_observer.md`. GOTCHA: use a ≥3-HP enemy unit (SOR_46 3/7) as the
  unit-damage target so it survives 2 to assert `.damage==2` (SOR_128 3/1 dies).
- **NEXT SESSION:** [✅ LOF_101 Yoda "when you use the Force" observer = DONE in BATCH
  17.] The LAST remaining *new-observer* card is TWI_64 Ki-Adi-Mundi ("opponent plays
  their 2nd card each phase" — needs a per-phase play counter, NOT a ledger observer),
  then the self-contained-decision-kind cards.

---

**STAGE 4 BATCH 15 DONE 2026-07-10 (FRAMEWORK ESCALATION — new `choose_two_modal`
decision kind).** Built the highest-leverage remaining primitive: ONE new decision kind
clears **4** needs_encoding groups — the "Choose two, in any order" SOR aspect events
**Aggression SOR_155 / Command SOR_107 / Cunning SOR_203 / Vigilance SOR_58** (+8 promo
siblings). needs_encoding 78→74 grp, already_covered 115→119; 10 new tests pass,
`find_reprints.py --check` exits 0, fast tier **1926 pass** (only the 118 pre-existing
WinError-5 web PermissionError collection errors). No change to core resolution or the
trigger/decision machinery — the decision kind is a pure SELECTOR that delegates to
existing resolve_effects.
- **Registration shape (the reusable pattern):** each card registers **idx 0** =
  `EventAbility([CustomEffect(fn=_choose_two_modal_controller)])` whose thin fn calls
  `actions.push_choose_modal(s, source_ci, option_indices=[1,2,3,4], pick=2)`; **idx
  1..4** = the four options, each a `TriggerAbility(trigger=WhenPlayed(), effects=[…])`.
  The option specs are **never fired as real triggers** (an Event is never in
  `_cards_in_play`, incl. when Command puts itself into the resource zone → not scanned)
  and **never resolved by `_resolve_event_ability`** (it only processes EventAbility
  specs) — only their `.effects` is read, ONLY from the modal resolution.
- **The primitive (`choose_two_modal`, actions.py):** `push_choose_modal` pushes a
  decision (ctx: source_id, controller_id, set_code, card_number, option_indices, pick,
  chosen=[]) owned by the controller. `SelectModalOption(option_idx)` picks one distinct
  option at a time (mandatory "choose two"; no decline); the pick ORDER is the resolution
  order. On the `pick`-th pick, `_resolve_choose_two_modal` **pops** the decision then
  pushes one `resolve_effects` decision per chosen option **in REVERSE pick order** (so
  the first-chosen resolves first off the LIFO stack), each addressed to
  `(set,number,ability_idx=opt)` with a **fresh `event_ctx={}`** — mirroring exactly how
  `_resolve_event_ability` pushes one resolve_effects per EventAbility. So **all option
  targeting is delegated to the existing resolve_effects machinery** — no hand-applied
  per-option dispatcher (unlike repeated_modal's `_apply_repeated_modal_option`).
- **WHY delegate (not hand-apply):** the 16 options span single-target, two-target
  (Haymaker), multi-select-up-to-2, nested-decision (return_from_discard), and no-target
  effects — re-implementing targeting per option would duplicate the resolver. The known
  **"no-target-before-targeted" resolve_effects wart** (target generator skips a leading
  no-target effect, then apply eats the first choice) is AVOIDED by keeping each option
  in its OWN resolve_effects decision (never concatenating options) — verified no single
  option internally sequences a no-target effect before a targeted one.
- **GOTCHA — action naming:** `ChooseModalOption`/`ChooseModalTarget` are ALREADY taken
  by the Leia SOR_189 `"modal"` (choose-ONE-then-target) kind, so the new action is
  **`SelectModalOption`** (distinct). Registered in `_KNOWN_DECISION_KINDS`
  (invariants), `_PROMPTS` (web/session), and HeuristicBot (`_choose_two_modal` = pick
  first-available; mandatory → no `_SAFE_DEFAULT_ORDER` entry needed).
- **Option encodings (all EXISTING primitives + tiny CustomEffect fns, in
  `src/swu/cards/sor/abilities.py`; NO second new primitive):**
  - **Aggression SOR_155:** DrawCards(1) / two optional `DefeatUnit(kind="upgrade")`
    ("up to 2") / `ReadyCard(power_max=3)` / `DealDamage(4)`.
  - **Command SOR_107:** `GiveToken("Experience", count=2)` / two dependent
    `CustomEffect.target` sharing event_ctx (Haymaker LAW_168: effect1 records the chosen
    friendly's `compute_power` → effect2 deals it to a chosen `non_unique` enemy) /
    CustomEffect put-self-as-resource (discard→resources, face_down+ready, CardResourced)
    / CustomEffect → `push_return_from_discard(count=1, eligible=isinstance Unit)`.
  - **Cunning SOR_203:** `ReturnToHand(non_leader, power_max=4)` / `ModifyStats(+4/0,
    THIS_PHASE)` / two optional `ExhaustCard(predicates=("ready",))` — the **`ready`
    predicate keeps the two picks distinct** ("up to 2") / CustomEffect opponent-random-
    discard (`state.make_rng()` → rng_state, Political-Pressure convention).
  - **Vigilance SOR_58:** CustomEffect mill-opponent-6 (deck top→discard) / `Heal(5,
    base fixed=EACH_FRIENDLY)` (own base, inline no trivial prompt) /
    `DefeatUnit(hp_remaining_max=3)` / `GiveToken("Shield")`.
- **Siblings aliased (`REPRINT_ALIASES` "batch 15"):** Aggression ← P25_126/P25_138;
  Command ← P25_122/P25_134; Cunning ← P25_130/P25_142; Vigilance ← P25_119/P25_131.
- **Tests:** `tests/test_sor_cards.py::Test{ChooseTwoModalPrimitiveSOR155, CommandSOR107,
  CunningSOR203, VigilanceSOR58}` (method names embed the number; drive the full
  play→choose_two_modal→per-option resolve_effects chain incl. AutoResolveEffects,
  ChooseTarget/DeclineTarget, and the nested return_from_discard). Test helper
  `_play_aspect_event` places the event in discard (where it sits at resolution) and runs
  `_resolve_event_ability`.
- **FOLLOW-ON UNBLOCK:** the SELECTOR + option-specs-as-TriggerAbility pattern is reusable
  for any future "choose N of M options, each with own targeting" card — e.g. Luke LAW_80
  ("opponent chooses the mode") could reuse the option-spec structure with a decider shift
  at the SelectModalOption stage.

---

**STAGE 4 BATCH 14 — ZERO ENCODABLE 2026-07-10 (survey only, no code change).** The
iterative "encode a shipped-canonical with EXISTING primitives + tiny additive seams"
phase has reached its END: I read the FULL text of every remaining shipped-canonical
needs_encoding group (25 groups spanning ~all sets) and NONE is implementable without a
new decision kind / new observer trigger / new mechanic. needs_encoding stays 78 grp /
already_covered 115 (nothing changed; no aliases added, no tests, fast tier not re-run —
survey batch). This confirms batch-13's prediction ("per-batch yield dropping to ~1")
has hit 0. The remainder MUST advance via dedicated framework sessions, one primitive at
a time. Full categorization of the 25 shipped-canonical remainders by the primitive each
needs (this IS the roadmap for the escalation sessions):
- **choose-two-of-four modal** — ✅ **DONE in BATCH 15** (`choose_two_modal` decision
  kind): SOR_155 Aggression / SOR_107 Command / SOR_203 Cunning / SOR_58 Vigilance all
  cleared. (No longer a remaining need — 21 groups left of the original 25.)
- **new observer triggers**: TWI_64 Ki-Adi-Mundi (opponent-plays-2nd-card-each-phase —
  the ONLY one left). [✅ the when-you-DRAW observer LAW_52 + LOF_148 = DONE in BATCH 16
  via `WhenYouDraw`; ✅ LOF_101 Yoda WhenYouUseForce = DONE in BATCH 17.]
- **new self-contained decision kinds**: LOF_42 Always Two (select-2-friendly-then-
  defeat-the-complement), LAW_32 Cad Bane (defeat-any-#-Credit-tokens-for-scaling-Exp —
  like exhaust_for_base_damage/pay_resources_for_tokens but over the `ps.credits` pile
  with DEFEAT semantics), LOF_200 Qui-Gon Jinn (owner-puts-unit-top/bottom-of-own-deck),
  LAW_80 Luke Skywalker (opponent-picks-the-MODE), SOR_87 Darth Vader (multi-select
  search-top-10-play-any-#-Villainy-combined-cost≤3-free = search-play-budget).
- **multi-decider return-then-OWNER-replays-free**: LOF_185 Baylan Skoll, LAW_93 Rio
  Durant ("return a cheap unit; THEN its owner may play it for free"). Two deciders.
- **capture variants**: SEC_193 Grand Admiral Thrawn (WhenPlayed = opponent-decider
  capture-or-ready fallback; WhenDefeated = pick-a-friendly-unit-to-capture-an-enemy).
- **damage-prevention**: LOF_108 Malakili (prevent Creature→friendly dmg; NOTE its OTHER
  clause "first Creature each phase costs 1 less" = existing NextPlayDiscount, but the
  prevention blocks it), SEC_101 Queen Amidala (defeat-friendly-to-prevent + new **Spy
  token** unit).
- **keyword-copy**: JTL_53 The Ghost ("each other Spectre gains THIS unit's keywords" —
  dynamic copy in the keyword-query layer; its "while upgraded gains Sentinel" half is
  the existing SOURCE_UPGRADED self-grant, but copy is the blocker).
- **combat-timing / defender-first-strike**: LAW_86 The Stranger (attacker may let the
  DEFENDER strike first — inverts First Strike, touches combat pipeline).
- **phase-structure**: LAW_72 Max Rebo (an ADDITIONAL regroup phase each round).
- **lose-abilities**: LOF_202 Mind Trick (exhaust units combined POWER≤4 — note
  exhaust_combined_cost is COST-budget not power — then they "lose all abilities").
- **arena-move + granted force action**: LOF_98 Leia Organa (move self space→ground).
- **delayed pay-or-exhaust**: SEC_73 The Eye of Aldhani (at START of next action phase,
  each enemy unit's controller pays 1 or exhausts it).
- **known-DROPPED dynamic cost-cap** (batch 11): LAW_89 Kanan Jarrus (return ≤2, or ≤4
  if control Command/Aggression — the leading-no-target-effect resolve_effects-enum wart,
  the rejected Never-Tell-Me shape).
- **classifier artifact, NOT a real encode**: LOF_151 Knight's Saber = "Attach to a Jedi
  non-Vehicle unit." with NO ability text; parser already handles the restriction. Needs
  a "register-as-vanilla" exemption convention to clear it from needs_encoding; out of
  scope for any card batch.
NEXT SESSION: pick ONE bullet above by the prompt's leverage ranking. The choose-two
modal (4 cards) is DONE; the next-highest is the **when-you-draw observer** (LAW_52 The
Mandalorian + LOF_148 Rey = 2 groups for one new observer trigger), then the remaining
1-group primitives. Run as a dedicated framework/escalation session, NOT a reprint batch.

**REUSABLE PROMPT for the escalation sessions lives in `docs/reprint_escalation_prompt.md`**
(paste-in file, alongside encode_group_prompt.md / bug_triage_prompt.md). It self-selects
the primitive by ranking THIS roadmap by leverage (most groups cleared per new primitive),
so it never goes stale — keep the roadmap above current (step 7 of that prompt trims cleared
cards) and don't duplicate the prompt text here.

**STAGE 4 BATCH 13 DONE 2026-07-10** — encoded ONLY 1 needs_encoding group. The
shipped-canonical remainder is now genuinely new-primitive-heavy; SEC_35 was the one
card cleanly implementable with EXISTING primitives + tiny batch-12-shaped additive
seams (NO new decision kind, no core-machinery change). needs_encoding 79→78 grp,
already_covered 114→115; 4 new tests pass, `--check` exits 0, fast tier 1892 pass
(only the pre-existing Windows PermissionError web 118 collection errors).

Group + siblings aliased (`REPRINT_ALIASES` "batch 13"):
- **SEC_35 Darth Sion** (Unit, Sith/Force, 5/5) ← J25_15, P26_71, P26_87. Two mandatory
  triggers, each one no-target `CustomEffect` (in `src/swu/cards/sec/abilities.py`).
  - **WhenPlayed** "Give an Experience token to this unit for each enemy unit defeated
    this phase" = scaling CustomEffect (Leia LAW_10 deploy-tokens pattern): N =
    `game_memory.defeated_controllers_this_round.count(enemy_id)`, `attach_token(...,
    source_ci, "Experience")` × N.
  - **WhenDefeated** "If this unit had 7 or more power, return him to his owner's hand."
- Two tiny additive engine seams (batch-12 shape — a tracker + an event_ctx field):
  1. **`GameMemory.defeated_controllers_this_round: list`** (state.py) — append
     `owner_ps.player_id` per `_defeat_unit` call (controller-at-death), so a later
     "each enemy unit defeated this phase" count can tell whose unit it was. Cleared in
     `clear_round`; serialised as a plain list. ("this round"=="this phase" for defeats.)
  2. **`event_ctx["defeated_power"]`** — in `_defeat_unit`, `compute_power(s, ci)` snapshotted
     BEFORE the upgrade/token strip, threaded into `event_ctx_defeated`. **WHY: `Condition.
     SOURCE_POWER_MIN` already exists but is USELESS here** — a WhenDefeated trigger fires
     AFTER `_defeat_unit` detaches upgrades/tokens, so `compute_power(defeated_ci)` would
     read the stripped base 5, never 7. The pre-strip snapshot is the only faithful read.
- **KEY GOTCHA — mandatory no-target WhenDefeated CustomEffect resolves INLINE during
  `_defeat_unit`, BEFORE the card is homed to discard.** So at fn time the card is in
  LIMBO (removed from arena, not yet in any zone list) → `find_instance` returns None.
  Handle it: operate on `source_ci` directly (move to hand, clear damage/exhaust), and
  set `event_ctx["relocated_by_trigger"]=True` so `_defeat_unit` (checks it right after
  `fire_triggered_abilities`) SKIPS the discard placement — the Stolen Landspeeder SHD_161
  relocate convention. Also handle the deferred case (card already in discard → pull it
  back out). Superlaser Technician SHD_85 gets away with discard-only handling ONLY because
  it is OPTIONAL (defers past the placement); a MANDATORY self-relocate must cover limbo.
- Test GOTCHA: test the end-to-end via the real `actions._defeat_unit` (attach 2 Experience
  → 7/7, defeat, drive pending to quiescence, assert in hand not discard) so the
  `defeated_power` seam is exercised — the `_defeat_and_fire` test helper does NOT compute
  defeated_power. Tests in `tests/test_law_cards.py::TestDarthSionSEC35` (method names embed
  `sec_35`).

**FLAGGED escalations (shipped-canonical needs_encoding, deferred to own sessions — the
dominant remainder):** choose-two-of-four modal events (Aggression SOR_155 / Command SOR_107
/ Cunning SOR_203 / Vigilance SOR_58 — one big modal primitive, 4 groups); Cad Bane LAW_32
("defeat any number of friendly Credit tokens, Experience each" = new decision kind, could
mirror `pay_resources_for_tokens` for the credit pile); Qui-Gon Jinn LOF_200 ("put a unit on
top or bottom of deck, owner chooses" = new small decision); The Ghost JTL_53 (keyword-copy
"gains this unit's keywords"); The Mandalorian LAW_52 ("when you draw during action phase"
observer); Rey LOF_148 / Yoda LOF_101 (when-you-draw / when-you-use-the-Force observers); The
Stranger LAW_86 (defender-deals-first / inverse-first-strike combat-timing); Darth Vader SOR_87
(multi-select search-and-play with combined-cost budget); Luke LAW_80 (opponent-chooses-a-mode
modal); Queen Amidala SEC_101 (Spy tokens exist via Bail Organa SEC_198, but damage-prevention
via defeat-friendly is new); Malakili LOF_108 (first-Creature-each-phase discount + friendly-
creature damage prevention); Max Rebo LAW_72 (extra regroup phase = phase-structure); Mind Trick
LOF_202 (units "lose all abilities" this phase); Baylan LOF_185 / Rio Durant LAW_93 (return-then-
owner-replays-free, already flagged batch 11); The Eye of Aldhani SEC_73 (delayed start-of-phase
pay-or-exhaust). **LOF_151 Knight's Saber** = a NON-escalation oddity: its only text is "Attach
to a Jedi non-Vehicle unit." — a pure attach restriction the engine's `_upgrade_target_spec`
parser already enforces WITHOUT registration; it's a *classifier artifact* (text-bearing +
unregistered), not a real encode. Fixing it needs a "register-as-vanilla / attach-only exemption"
convention (registering an empty ability contradicts the recipe), out of scope for a card batch.

---

**STAGE 4 BATCH 12 DONE 2026-07-10** — encoded 4 more needs_encoding groups
(shipped-set canonicals, all low-risk; NO new decision kind, no core-machinery
change; no escalations encoded). needs_encoding 83→79 grp, already_covered 110→114;
13 new tests pass, `--check` exits 0, fast tier 1879 pass (only the pre-existing
Windows PermissionError web 118 collection errors). Small additive seams only.

Groups + siblings aliased (`REPRINT_ALIASES` "batch 12"):
- **JTL_203 Han Solo** (Piloting residual) ← JTLP_17, P25_93. Only ability is the
  Pilot-play residual: `TriggerAbility(WhenPlayed(as_upgrade=True))` (the Boba Fett
  JTL_189 flag — fires only on the pilot-upgrade play path, vanilla 4/5 as a unit)
  whose one CustomEffect is a thin adapter onto `push_granted_attack(attacker_id=host,
  optional=True, grant_keywords=["First Strike"] iff host is the Millennium Falcon)`.
  Host read from `event_ctx["attached_to_id"]`. **NO engine change** — all
  granted_attack fields pre-existed. **GOTCHA: compare `host.card_def.name`, NOT
  `.display_name`** — display_name appends the subtitle ("Millennium Falcon — Get Out
  And Push"), so a display_name equality check silently never grants First Strike.
- **JTL_142 Darth Vader** (Piloting residual) ← J25_6, P25_171. `GrantedAbility(OnAttack)`
  (Dengar JTL_139 pattern — vanilla 7/7 as a unit; a bare GrantedAbility is NOT
  collected from an arena unit, only from a host's attached_upgrades) with TWO
  dependent optional `CustomEffect.target` effects sharing the resolve_effects
  event_ctx (the Grenade Strike TWI_171 / confirmed persists across a TRIGGER's
  sequential ChooseTargets via the resolve_effects push site storing event_ctx):
  effect1 deals 1 to a chosen unit and, if it left its arena, sets
  `event_ctx["prior_target_defeated"]` (detect via `state.find_instance(tid)` then
  check `zone.name not in ("GROUND_ARENA","SPACE_ARENA")` — a defeated unit still
  resolves in DISCARD, so `_find_in_arenas(ps, id)` is the WRONG helper; it takes a
  PlayerState not the state); effect2 = `DealDamage`-via-CustomEffect kind=`unit_or_base`
  gated by the EXISTING `requires_prior_defeat` predicate. **NO engine change** (the
  predicate + unit_or_base kind already existed).
- **SEC_188 Darth Traya** ← P26_104. Optional `OnAttack` (the "you may") whose one
  no-target CustomEffect readies the controller's undeployed leader
  (`ps.leader_instance` with `not deployed` = a "non-unit leader"; readies only the
  controller's — enemy-leader readying is never worth it), gated by new condition
  **`CONTROLLER_HAS_EXHAUSTED_UNDEPLOYED_LEADER`** (leader undeployed AND exhausted,
  so the trigger isn't offered as a no-op). **GOTCHA (tests): an optional-trigger
  no-target CustomEffect does NOT auto-run on `AcceptTrigger`** — it leaves a
  `resolve_effects` decision whose next action is `AutoResolveEffects`; drive to
  quiescence after accepting.
- **SEC_158 Oppression Breeds Rebellion** ← SECP_14. Event whose one no-target
  CustomEffect draws 3 iff new condition **`CONTROLLER_FRIENDLY_ATTACKER_DEFEATED_THIS_PHASE`**
  holds. That reads a **new `GameMemory.attackers_defeated_this_round` set** (player_ids;
  cleared at `clear_round`; serialised in to_dict/from_dict) recorded in
  `actions._resolve_unit_combat_step2` — `add(active_ps.player_id)` when the attacker
  is dead (whether a WhenDefeated AoE or the combat step does the actual defeat).
  "this round"=="this phase" (attacks only in ACTION; the units_defeated_this_round
  precedent). Only combat change is that one recording line (no behaviour change).

Selection note: the low-hanging shipped-canonical fruit is largely gone. Skipped
this batch as new-primitive escalations (NOT encoded): capture (Thrawn SEC_193),
choose-an-aspect (Lawbringer LAW_101), the aspect "choose two of four" modal events
(Aggression SOR_155 / Command SOR_107 / Cunning SOR_203 / Vigilance SOR_58),
new-trigger observers (Ki-Adi TWI_64 "opponent's 2nd card", Mandalorian LAW_52 "when
you draw", Yoda LOF_101 "when you use the Force", Rey LOF_148 "when you draw this"),
phase-structure (Max Rebo LAW_72 extra regroup), combat-redirect (Maul SHD_90),
top/bottom-deck-by-owner (Qui-Gon LOF_200), reverse-first-strike (The Stranger
LAW_86), keyword-copy (The Ghost JTL_53), opponent-modal (Luke LAW_80), and the
already-flagged control-with-revert (Maul LAW_54). NOTE: my prior-session memory that
JTL_142/JTL_203/LOF_151 were "classifier artifacts" was WRONG — the DB `text` field is
empty but `full_text` folds in the Piloting `epicAction` residual, so those Piloting
cards DO carry real ability text (LOF_151 Knight's Saber is a pure attach-restriction
+ stat upgrade the audit flags text-bearing — left unencoded, nothing to register).

---

**STAGE 4 BATCH 11 DONE 2026-07-09** — encoded 5 more needs_encoding groups
(shipped-set canonicals, all low-risk; NO new decision kind, no core-machinery
change; no escalations). needs_encoding 88→83 grp, already_covered 105→110; 12 new
tests pass, `--check` exits 0, fast tier 1850 pass (only the pre-existing Windows
PermissionError web 118 collection errors). Small additive seams only.
Groups:
- **LOF_90 Inquisitor's Lightsaber** (Upgrade) = `GrantedAbility(OnAttack →
  CustomEffect)` resolving from the HOST that reads `event_ctx["defender_id"]` and,
  if the defender is a Force unit, applies a this-attack +2/0 `_make_modifier` to
  the host — the Chain Code Collector SHD_216 combat-trick pattern (a static "while
  attacking a Force unit, +2/0" modelled as an OnAttack this-attack buff; bonus
  only matters during that attack, base attack has no defender → fizzles). NO
  engine change. Sib P25_106.
- **LOF_246 Grogu** (Unit, Hidden kw) = `ActivatedAbility([ExhaustSelf()],` two
  dependent `CustomEffect.target` effects sharing `event_ctx` (the Haymaker LAW_168
  pattern — BOTH effects targeted, so no resolve_effects-skip issue): effect1 heals
  min(2, damage) from chosen unit + records amount; effect2 deals that to chosen
  unit. Confirmed the ActivatedAbility resolve_effects decision carries a
  persistent `event_ctx` dict (actions.py UseAbility push site), same as
  EventAbility. DEVIATION (documented): "up to 2" = heal the max available (no
  0/1/2 amount choice). NO engine change. Sibs P26_49/P26_61.
- **LOF_261 Constructed Lightsaber** (Upgrade) = 3 mutually-exclusive
  `ConstantAbility(target=SELF, KeywordGrant, condition=<aspect>)` — Heroism→Restore
  2, Villainy→Raid 2, neither→Sentinel. Read via the keyword layer's attached-upgrade
  scan (`has_keyword`/`keyword_value` already scan a unit's `attached_upgrades` for
  SELF-targeted ConstantAbility KeywordGrant AND evaluate the spec's condition
  against the HOST — Grievous's Wheel Bike TWI_236 pattern). NEW conditions
  `SOURCE_HAS_ASPECT(param)` + `SOURCE_LACKS_ASPECTS(param="Heroism,Villainy")`
  (registry, read `source_ci.card_def.aspects` names). Upgrade's own printed
  Restore/Raid/Sentinel are inert (accepted). Sib P25_112.
- **TWI_189 Unnatural Life** (Event) = thin EventAbility `CustomEffect` adapter onto
  `push_play_from_hand(from_discard=True, cost_reduction=2, enters_ready=True,
  defeat_at_regroup=True, eligible_ids=<units in ctrl discard ∩
  units_defeated_this_round>)` — the Sneak Attack SOR_219 defeat-at-regroup pattern
  but from discard. NEW `eligible_ids` frozenset whitelist field on the
  play-from-hand subsystem (`_playable_units_from_hand` + `push_play_from_hand` +
  the `play_from_hand` legal_actions branch + `PlayFromHand.apply` validation;
  serialised as a list in ctx). "Defeated this phase"=="this round" (Medal Ceremony
  precedent). Sib P25_56.
- **LAW_226 Secret Battle of Pretend** (Event, Trick) = single `CustomEffect.target`
  (friendly unit) exhausts the chosen unit, computes its distinct-aspect count N +
  arena, then INLINE-PUSHES `push_exhaust_combined_cost(controller="enemy",
  arena=arena, max_units=N, budget=None)` (Ahsoka JTL_201 inline-then-push;
  Calculated Lethality nested-decision resume). NEW `controller` filter on
  `push_exhaust_combined_cost` (threaded into ctx + `_exhaust_combined_targets`
  spec). DEVIATION (minor): "exhaust N enemies" offered as "up to N" (Finish always
  offered; controller always maxes out — enemy exhaust is pure upside). Sib LAWP_19.

DROPPED this batch: **Kanan Jarrus LAW_89** — "return a non-leader unit cost≤2, or
cost≤4 if you control a Command OR Aggression unit". The dynamic cost-cap is NOT
cleanly expressible: a two-effect [no-target-set-threshold, ReturnToHand
cost_le_event_threshold] design is BROKEN because `resolve_effects_actions` SKIPS a
leading no-target CustomEffect during target enumeration (the effect runs only in
apply's auto-resolve loop AFTER a choice), so effect2's targets enumerate with the
threshold unset — exactly the rejected "Never Tell Me the Odds" shape. And OR-of-
aspects + negation can't be a single condition atom. Wants a dynamic-target-cap seam
→ its own session.
FLAGGED for own session (new multi-decider primitive): **Rio Durant LAW_93** +
**Baylan Skoll LOF_185** — both "return a non-leader unit to owner's hand, then its
OWNER may play it for free (Shielded this phase)". Needs a decision handed to a
specific (possibly opponent) player to play one specific card for free — a
multi-decider play-specific-card seam. Also skipped as new-primitive: Cad Bane LAW_32
(defeat-any-number-of-Credits→experience, new decision), The Mandalorian LAW_52
(when-you-draw observer trigger), Luke LAW_80 (opponent-chooses-mode modal), Maul
LAW_54 (control-change + leaves-play-return hook), SEC_193 Thrawn (opponent-choose-
capture-with-fallback), SEC_35 Darth Sion (power-at-defeat snapshot), Millennium
Falcon SOR_193 (regroup pay-or-bounce trigger), Malakili LOF_108 (damage-prevention),
Rey LOF_148 (when-you-draw-THIS-card), Qui-Gon LOF_200 (owner-picks-top/bottom).
Classifier artifacts (nothing to encode): JTL_142 Darth Vader, JTL_203 Han Solo,
LOF_151 Knight's Saber, JTL_53 The Ghost (copy-keywords primitive).

---

**STAGE 4 BATCH 10 DONE 2026-07-09** — encoded 5 more needs_encoding groups
(shipped-set canonicals; all low-risk reuse — NO new decision kind, no
core-machinery change; no escalations). needs_encoding 93→88 grp, already_covered
100→105; 15 new tests pass, `--check` exits 0, fast tier 1820 pass (only the
pre-existing Windows PermissionError web-save/deckbuilder 118 collection errors).
ONE tiny additive seam (`IndirectDamageSelfAssign` passive marker + decider flip).
Groups:
- **SEC_209 The Mandalorian** (Unit 6/8, Ambush kw) = optional `OnAttackDefeatsUnit`
  `CaptureUnit(enemy non-leader)` — REUSES capture primitive (Discerning Veteran
  SHD_120 pattern; captor=source via CaptureUnit fallback). NO engine change. sib J25_19.
  Test-fire: `fire_triggered_abilities(None, event_ctx={"attack_defeated_unit": id})`.
- **SEC_68 Lando Calrissian** (Unit 6/8, Grit kw) = optional `WhenPlayed` w/ TWO
  dependent `CustomEffect.target`s sharing event_ctx (Haymaker LAW_168): pick enemy
  unit (record `lando_enemy_id`) → pick friendly non-leader (`not_self`="another"),
  heal 6 from OWN base (`ctrl.base_instance.damage-=6`) + `_apply_capture(captor=enemy,
  target=friendly)` so friendly lands in P1's capture_pile. Guarded on both ids for
  "If you do". NO engine change. sib SECP_3.
- **SEC_82 Chancellor Palpatine** (Unit 2/2, Plot kw) = `WhenPlayed` inline no-target
  CustomEffect: gate "control a leader unit" (scan arenas for `isinstance Leader`, no
  new condition atom), then `_create_token_units(ctrl,"Spy",2)` (Spy=TokenUnit SEC_1,
  0/2 Raid2) + per-token `this_phase keyword_grant Sentinel` Modifier. REUSES
  create-token-unit primitive. NO engine change. sib P26_62.
- **JTL_154 Profundity** (Unit 8/9, Overwhelm kw) = `WhenPlayed`+`WhenDefeated`, each
  a no-target CustomEffect: opponent discards first hand card (K-2SO SOR_145 first-card
  simplification, `hand.pop(0)→discard`), then if opp hand > controller hand, discard
  again. NO engine change. sibs P25_159/169.
- **JTL_143 Devastator** (Unit 9/6) = `IndirectDamageSelfAssign` marker + `WhenPlayed`
  CustomEffect `push_assign_indirect_damage(4)`. NEW tiny seam: `IndirectDamageSelfAssign`
  passive marker (registry) + `_controller_self_assigns_indirect` scan; in
  `push_assign_indirect_damage`, when controller has the marker the DECIDER flips to the
  controller (not receiving player) — target set unchanged (still receiving player's
  base/units). Added to soak.py passive-marker tuple. sibs P25_3/4/5/6.
SKIPPED as new-primitive-smelling (flagged for own sessions): SOR aspect events
Aggression/Command/Cunning/Vigilance (choose-2-of-4 modal), Mind Trick LOF_202
(silence/"lose all abilities"), Lawbringer LAW_101 (choose-an-aspect), Max Rebo LAW_72
(extra regroup phase), Queen Amidala/SHD_90 Maul (damage-prevention replacement),
Darth Traya SEC_188 (ready a non-unit/undeployed leader — needs base_zone target
enumeration). NOTE: JTL_142 Darth Vader (vanilla Piloting) / JTL_203 Han Solo
(Ambush+Piloting) / LOF_151 Knight's Saber (attach-only) are classifier artifacts
(nothing to encode) — left. (Batch 9: SOR_40/SHD_131/LAW_115/LOF_37/SHD_141/SHD_46.)

**STAGE 4 BATCH 9 DONE 2026-07-09** — encoded 6 more needs_encoding groups
(shipped-set canonicals; all low-risk reuse — NO new decision kind, no
core-machinery change; no escalations). needs_encoding 99→93 grp, already_covered
94→100; 15 new tests pass, `--check` exits 0; fast tier 1778 pass (only the
pre-existing Windows PermissionError web-save/deckbuilder collection errors).
Groups:
- **SOR_40 Avenger** (Unit 8/8) = TWO triggers (`WhenPlayed`+`OnAttack`), each a
  no-target `CustomEffect` onto `push_each_player_defeats(only_opponent=True)` — NEW
  `only_opponent` param on the Merciless Contest TWI_238 seam (order=[opponent] so
  only the opponent picks their own non-leader unit to defeat). sib J24_1.
- **SHD_131 Take Captive** (Event) = two dependent `CustomEffect.target`s sharing
  event_ctx (Haymaker LAW_168 pattern): pick friendly captor (record its arena into
  `event_ctx["same_arena"]`), then enemy non-leader w/ `same_arena_as_event`
  predicate → REUSES capture primitive `actions._apply_capture`. NO engine change.
  sib TWI_128.
- **LAW_115 Rickety Quadjumper** (Unit 1/3) = optional `OnAttack` CustomEffect reads
  deck top in place (Han JTL_17 read-top; "leave on top" = don't pop) and, if NOT a
  Unit, `push_select_token(Experience, max 1, not_self)`. NO engine change. sib SHD_57.
  GOTCHA: optional trigger → AcceptTrigger then **AutoResolveEffects** runs the
  no-target CustomEffect that pushes select_token (test needs both steps).
- **LOF_37 Darth Vader** (Unit 5/6) = `WhenPlayed [GiveToken("Shield",friendly),
  GiveToken("Shield",enemy)]` + `OnAttack DefeatUnit(enemy w/ NEW `has_shield_token`
  predicate)` (scans attached_upgrades for a Shield TokenUpgrade). sibs
  P25_75/152/162, P26_72/88.
- **SHD_141 Kylo Ren** (Unit 6/6) = `OnAttack CustomEffect(target=any unit)` +2/+0
  this-phase + (if non-Villainy aspect) an Experience token (bound). RESIDUAL
  DEFERRED: "ignore Villainy penalty if control Rey" (play-cost waiver, Darksaber
  class). sib C24_4. GOTCHA: Experience token adds +1/+1, so a non-Villainy target's
  compute_power is base+3 (2 buff + 1 exp), not +2.
- **SHD_46 Rey** (Unit, cost5) = optional `OnAttack CustomEffect(target=any unit)`
  heal 2 + (if non-Heroism) a Shield token (bound). RESIDUAL DEFERRED: same cost-waiver
  class. sib P25_59.
Seams (all trivial-additive): `only_opponent` param on push_each_player_defeats
(actions.py) + `has_shield_token` predicate (resolver `_spec_matches_ci`). Aliases in
reprints.py "Reprint-sweep batch (2026-07-09)" block; tests: test_sor (Avenger),
test_shd (TakeCaptive/KyloRenSHD141/ReySHD46), test_law (RicketyQuadjumper), test_lof
(DarthVaderLOF37). REMAINING: encode needs_encoding (93 grp).

**STAGE 4 BATCH 8 DONE 2026-07-08** — encoded 6 more needs_encoding groups
(shipped-set canonicals; all low-risk small-additive reuse — NO new decision kind,
no core-machinery change; no escalations). needs_encoding 105→99 grp,
already_covered 88→94; 19 new tests pass, `--check` exits 0. Groups:
- **LOF_70 Anakin Skywalker** (Unit 5/7) = TWO optional `WhenPlayed` triggers, each
  gated by NEW `CONTROLLER_HAS_ASPECT_CARD_IN_DISCARD(aspect)` condition (any
  discard-pile card carrying the aspect) with `ModifyStats(-3,-3, any unit,
  THIS_PHASE)` — one per Heroism/Villainy discard clause; both fire if both present.
  sibs P25_87/P25_145.
- **LOF_234 Darth Malak** (Unit 4/7, Overwhelm=kw) = optional `WhenPlayed
  ReadyCard(fixed=SELF)` gated by NEW `CONTROLLER_HAS_TRAIT_LEADER_UNIT("Sith")`
  (a deployed Leader card_def in an arena carrying the trait). sib P25_21.
- **LOF_40 Kylo Ren's Lightsaber** (Upgrade) = self `ConstantAbility
  Protection(from_exhaust=True)` gated by `SOURCE_HAS_TRAIT("Force")` — NEW
  `Protection.from_exhaust` field read at the ExhaustCard resolver arm via
  `_target_protected(...,"exhaust")` (enemy abilities only). GOTCHA: extended
  `_card_grants_self_protection` to EVALUATE the ConstantAbility's `condition`
  against the host (Chewbacca JTL_103 was unconditional; the Force gate matters
  here since the upgrade attaches to any non-Vehicle unit). sib P25_104.
- **TWI_121 General's Blade** (Upgrade) = `GrantedAbility(OnAttack →
  NextPlayDiscount(trait="", amount=2))` gated by `SOURCE_HAS_TRAIT("Jedi")`
  (Fallen Lightsaber SOR_137 pattern). NEW: empty-trait = "any card" match in
  `_play_discount_entry_matches` (`if t and t not in traits`) for "the next unit".
  sibs P25_156/P25_166.
- **JTL_176 Shoot Down** (Event) = `[CustomEffect(target=space unit) deals 3 +
  records defeat in event_ctx["prior_target_defeated"], DealDamage(2, base,
  optional, predicate NEW `requires_prior_defeat`)]` — the "If defeated, you may
  deal 2 to a base" gate (mirrors `requires_prior_target`; reads event_ctx only so
  works for base candidates). sib JTLP_14.
- **JTL_204 Home One** (Unit 7/8, Ambush=kw) = declarative `CostReduction(amount=3,
  condition=NEW ENEMY_N_PLUS_SPACE_UNITS(3))` on its own play cost (Force Choke
  SOR_139 pattern; read by `_play_cost_reduction` for any card type). sibs
  P25_9/10/11/12.

Seams (all trivial-additive, NOT escalations): 3 condition atoms + `Protection.from_exhaust`
(+ condition-aware `_card_grants_self_protection`) + `requires_prior_defeat` predicate
+ empty-trait=any discount match. Tests: `TestAnakinSkywalkerLOF70`,
`TestDarthMalakLOF234` (needs AutoResolveEffects after AcceptTrigger for the fixed-SELF
ReadyCard), `TestKyloRensLightsaberLOF40` in test_lof_cards.py;
`TestGeneralsBladeTWI121` in test_twi_cards.py; `TestShootDownJTL176`,
`TestHomeOneJTL204` in test_jtl_cards.py.

**STAGE 4 BATCH 7 DONE 2026-07-08** — encoded 6 more needs_encoding groups
(shipped-set canonicals; all low-risk small-additive reuse — NO new decision kind,
no core-machinery change; no escalations). needs_encoding 111→105 grp,
already_covered 82→88; 14 new tests pass, `--check` exits 0. Groups:
- **LOF_62 Axe Woves** (Unit 2/2, Shielded=kw) = self `ConstantAbility StatBonus(1,1,
  count="upgrades_on_self")` — NEW _stat_bonus_count arm = len(attached_upgrades)
  (tokens counted per CR, so an Experience token nets +2/+2). Nien Nunb JTL_93 scaling
  pattern. sibs P25_120/P25_132/P26_39/P26_51.
- **SEC_170 Corellian Hounds** (Unit 5/5) = `EntersPlayReady(condition=NEW
  ENEMY_CONTROLS_NO_GROUND_UNITS)` — Salacious Crumb LAW_210 passive-marker pattern
  (opponent's ground_arena empty). sib SECP_15.
- **SEC_130 Ferrix Uprising** (Event) = `EventAbility([DealDamageEqualTo(any unit,
  count="source_controller_units_in_target_arena_x2")])` — NEW doubled count arm
  (Synchronized Strike TWI_99 count ×2; mandatory-if-able). sib SECP_10.
- **LAW_247 Backed by the Hutts** (Event) = CustomEffect adapter: `create_credit_token`
  then `push_select_damage(amount_each=len(credits), max_targets=1)` (the "you may deal"
  = select_damage "up to 1"). REUSES CreateCredit + select_damage — the Never Tell Me
  the Odds JTL_208 inline-then-push (avoids the [Create,DealDamageEqualTo] double-prompt
  wart). NO new seam. sib LAWP_20.
- **SOR_176 ISB Agent** (Unit 1/3) = optional `WhenPlayed DealDamage(1, any unit)` gated
  NEW condition `CONTROLLER_HAS_EVENT_IN_HAND` (reveal-an-event = cosmetic; gate on
  holding an Event). sib SEC_184.
- **LOF_132 Grand Inquisitor** (Unit 3/4, Hidden+Raid1=kw, kept by bare-mention) = grant
  `ConstantAbility(target=friendly Inquisitor not_self, KeywordGrant("Hidden"))` read by
  has_keyword (Red Three SOR_144 grant-to-others; NO new primitive). sibs P25_15/P25_81.
Small seams added (all trivial-additive, NOT escalations): 2 condition atoms
(`ENEMY_CONTROLS_NO_GROUND_UNITS`, `CONTROLLER_HAS_EVENT_IN_HAND` in registry), 1
`_stat_bonus_count` arm `upgrades_on_self` (actions.py), 1 `_scaling_magnitude` doubled
arm `source_controller_units_in_target_arena_x2` (resolver.py). Aliases in reprints.py
"Stage 4 batch 7" block; tests: test_lof (AxeWovesLOF62/GrandInquisitorLOF132), test_law
(CorellianHoundsSEC170/FerrixUprisingSEC130/BackedByTheHuttsLAW247), test_sor
(ISBAgentSOR176). REMAINING: encode needs_encoding (105 grp).

**STAGE 4 BATCH 6 DONE 2026-07-08** — encoded 6 more needs_encoding groups
(shipped-set canonicals; all low-risk small-additive reuse — NO new decision kind,
no core-machinery change; no escalations). needs_encoding 117→111 grp,
already_covered 76→82; 11 new tests pass, `--check` exits 0; fast tier 1631 pass
(only the pre-existing Windows PermissionError web-save/deckbuilder errors). Groups:
- **LAW_34 Chewbacca** (Unit 4/4, Overwhelm=kw) = `OnAttackDefeatsUnit → [GiveToken
  Exp SELF, Heal 3 SELF]` — "When Attack Ends: if defending unit was defeated" ≡
  OnAttackDefeatsUnit (attacker survived; base attack = no unit = no fire). ZERO new
  code (Oggdo Bogdo LOF_63 self-heal pattern). sib P26_10.
- **LAW_68 Millennium Falcon** (Unit 2/5) = TWO separate single-effect optional
  `OnAttack ModifyStats` THIS_PHASE (space unit −2/−0; ground unit +2/+0),
  controller="any" (Sabine's Masterpiece JTL_250 separate-abilities pattern). ZERO
  new code. sib LAWP_5.
- **LOF_46 Ezra Bridger** (Unit 3/5) = optional `OnAttack GiveToken(Exp, another unit,
  predicates=("not_self","creature_or_spectre"))`. NEW predicate `creature_or_spectre`
  (trait-OR, droid_or_vehicle pattern). sib P25_77.
- **LOF_163 Quinlan Vos** (Unit 4/5) = optional `OnAttack DealDamage(2, enemy base)`
  gated NEW condition `SOURCE_POWER_MIN(6)` (compute_power(source) ≥ param; gates
  trigger COLLECTION so not offered below 6). sib P25_85.
- **SEC_114 Kino Loy** (Unit 1/5) = self `ConstantAbility StatBonus(1,0,
  count="other_exhausted_friendly_units")` — NEW _stat_bonus_count arm (Nien Nunb
  JTL_93 scaling pattern). sib SECP_9.
- **JTL_256 Swarming Vulture Droid** (Unit 2/2) = self `ConstantAbility StatBonus(1,0,
  count="other_friendly_same_name")` — NEW count arm (matches source card_def.name,
  excl self); 15-copy deck limit is a deckrules concern, not in-play. sib JTLP_20.
Small seams added (all trivial-additive, NOT escalations): `SOURCE_POWER_MIN` condition
(registry), `creature_or_spectre` predicate (resolver `_spec_matches_ci`), two
`_stat_bonus_count` arms (actions.py). Aliases in reprints.py "Stage 4 batch 6" block;
tests: test_law (ChewbaccaLAW34/MillenniumFalconLAW68/KinoLoySEC114), test_lof
(EzraBridgerLOF46/QuinlanVosLOF163), test_jtl (SwarmingVultureDroidJTL256).

**STAGE 4 BATCH 5 DONE 2026-07-08** — encoded 6 more needs_encoding groups
(shipped-set canonicals, ALL pure reuse — NO new engine primitive, count, predicate,
condition, or decision kind; no escalations). needs_encoding 123→117 grp,
already_covered 70→76; 14 new tests pass, `--check` exits 0; fast tier 1602 pass
(the only errors are the pre-existing Windows tmp-dir PermissionError in
test_web_save_replay/test_web_deckbuilder — unrelated). Groups:
- **LAW_33 Hound's Tooth** (Unit 4/8) = optional `WhenAttackEnds DefeatUnit(any unit,
  power_less_than_captor=True)` — the Pong Krell LOF_38 surviving-attacker seam, but
  the SHD_124 `power_less_than_captor` FIELD (captor falls back to source_ci) for "less
  power than this unit". sib LAWP_1. GOTCHA: `power_less_than_captor` is a TargetSpec
  FIELD, not a predicate-tuple name (same for the others) — putting it in `predicates=`
  is silently ignored.
- **TWI_198 Enfys Nest** (Unit 5/7, Saboteur=kw) = two optional triggers (WhenPlayed +
  OnAttack), each `ReturnToHand(enemy non_leader, power_less_than_captor=True)`. sib J25_9.
- **SEC_51 Bo-Katan Kryze** (Unit 8/8) = `WhenPlayed ModifyStats(-3/-3, EACH_ENEMY unit,
  THIS_PHASE)` (Encouraging Leadership mass-buff, negatived) + `WhenUnitDefeated(enemy)
  GiveToken("Experience", friendly unit)` (HK-47 LOF_130 enemy-defeat observer). sib SECP_2.
- **LAW_75 Interrogation Droid** (Unit 3/1) = `WhenPlayed CustomEffect(target=enemy unit)`
  exhaust it, and if its cost≤3 opponent discards first hand card (K-2SO simplification),
  bound so "If you do and that unit costs 3 or less" keys off the chosen unit. sib LAWP_7.
- **SHD_49 The Mandalorian** (Unit 5/6, Sentinel=kw) = optional `WhenPlayed CustomEffect(
  target=unit cost_max=2)` zero its damage (heal ALL) + attach 2 Shields (bound). sib P25_101.
- **SOR_51 Luke Skywalker** (Unit 6/7, Restore 3=kw) = `WhenPlayed CustomEffect(target=enemy
  unit)` this-phase -3/-3 via `_make_modifier`, or -6/-6 if a friendly unit was defeated
  this phase (id in `units_defeated_this_round` ∩ controller's discard — Zeb LAW_45
  conditional-magnitude; minor deviation if the dead card left discard). sib P25_173.
Aliases in reprints.py "Stage 4 batch 5" block; tests in test_law_cards
(HoundsTooth/InterrogationDroid/BoKatanKryze), test_twi (EnfysNest), test_shd
(TheMandalorianSHD49), test_sor (LukeSkywalkerSOR51).

**STAGE 4 BATCH 4 DONE 2026-07-07** — encoded 8 more needs_encoding groups
(shipped-set canonicals, ALL pure reuse of existing primitives — NO new engine
primitive, NO new count/predicate/condition arm, no escalations). needs_encoding
131→123 grp, already_covered 62→70; 15 new tests pass, `--check` exits 0. Groups:
- **SEC_258 Grassroots Resistance** (Event) = `EventAbility([DealDamage(3, any unit),
  Heal(3, friendly base EACH_FRIENDLY)])`. sibs ASH_258, SECP_20.
- **LAW_79 K-2SO** (Unit, Ambush) = optional `OnAttack DealDamage(3, damaged ground
  unit)`. sib LAWP_8. (NOTE: distinct from K-2SO SOR_145 & LAW_79's own reprint set.)
- **LOF_51 Jedi Holocron** (Upgrade, attach Force) = `GrantedAbility(optional OnAttack
  Heal(3, another unit not_self))`. sib P25_13.
- **LOF_187 Corrupted Saber** (Upgrade, attach non-Vehicle) = `GrantedAbility(OnAttack
  ModifyStats(-2/0, fixed=DEFENDER, THIS_ATTACK))` gated `SOURCE_HAS_TRAIT("Force")`
  (Fallen Lightsaber SOR_137 pattern). sib P25_110.
- **LOF_238 Darth Revan's Lightsabers** (Upgrade) = `ConstantAbility(SELF,
  KeywordGrant("Grit"), condition=SOURCE_HAS_TRAIT("Sith"))` — the keyword-layer
  attached-upgrade conferral scan (keywords.py:167/238) evaluates the condition
  against the HOST, so "if attached unit is Sith, gains Grit" works; sanitiser's
  conditional-self-grant rule strips the upgrade's mistagged printed Grit. sib P25_19.
- **LAW_203 Daring Delve** (Event) = CustomEffect mills top 2, then optional
  `return_from_discard` over Aggression cards among them (`eligible`=Aggression aspect,
  `eligible_instance`=in milled set — Admiral Trench TWI_86 pattern). sib LAWP_16.
- **LOF_240 Flight of the Inquisitor** (Event) = CustomEffect pushes TWO independent
  optional `return_from_discard` (one Force unit, one Lightsaber-trait upgrade). sib
  LOFP_20.
- **SEC_147 Chopper** (Unit) = `WhenDealsCombatDamageToBase` (Ketsu Onyo SHD_147
  trigger) → two `DiscardFromHand` (chooser controller + opponent = "each player
  discards"). sibs C25_6, P26_44, P26_56.
GOTCHA: Pong Krell LOF_38 has NATIVE Grit — don't use it as the negative-control host
for a Grit-grant test (use a plain no-Grit unit e.g. SOR_46). Event cards land in
discard after resolving, so a mill-2 event leaves discard=3 (2 milled + the event).

**STAGE 4 BATCH 3 DONE 2026-07-07** — encoded 7 more needs_encoding groups
(shipped-set canonicals, ALL pure reuse of existing primitives — NO new engine
primitive, NO new count/predicate/condition arm, no escalations). Canonical
registered + siblings aliased in `REPRINT_ALIASES`; focused tests (card# in method
names). Groups:
- **LAW_57 Benthic "Two Tubes"** (Unit) = `OnAttack DealDamage(1, enemy ground unit)`
  + `WhenDefeated DealDamage(1, base controller=any)`. sib P26_8.
- **LOF_130 HK-47** (Unit) = `WhenUnitDefeated(filter=enemy unit) → DealDamage(1,
  enemy base EACH_ENEMY)` (Rogue One LAW_119 WhenUnitDefeated pattern, enemy side).
  sibs J25_12, P25_123, P25_135, P26_41, P26_53.
- **LOF_207 Loth-Cat** (Unit) = two optional triggers `WhenPlayed`+`WhenDefeated`,
  each `ExhaustCard(any ground unit)`. sib LOFP_18.
- **LOF_235 HK-87 Assassin Droid** (Unit) = `WhenDefeated DealDamage(2, ground unit
  EACH_IN_PLAY)` (both sides; simultaneous). sib LOFP_19.
- **JTL_90 Executor** (Unit, Overwhelm) = three triggers WhenPlayed/OnAttack/
  WhenDefeated each `CreateTokenUnit("TIE Fighter", 3)` (create-token-unit
  primitive; TIE Fighter = JTL_1 space TokenUnit). sib P25_88.
- **JTL_181 Planetary Bombardment** (Event) = `CustomEffect` pushing
  `push_assign_indirect_damage(8, or 12 if control a Capital Ship unit)` (indirect-
  damage primitive boba-fett:01 + Zeb LAW_45 conditional magnitude). sibs P25_127,
  P25_139, P26_45, P26_57.
- **SEC_198 Bail Organa** (Unit) = optional `OnAttack` gated CONTROLLER_HAS_CARD_IN_HAND,
  `CustomEffect` discards first hand card (K-2SO simplification) then
  `_create_token_units("Spy",1)` (Spy = SEC_1 TokenUnit); bound so "if you do" holds.
  sib SECP_17.
Only edits outside per-card blocks: imports (lof += WhenUnitDefeated/ExhaustCard/
EACH_ENEMY/EACH_IN_PLAY; jtl += CreateTokenUnit; law += DealDamage; sec +=
ConditionCheck/Condition). needs_encoding 138→131 grp (343→322 mem), already_covered
55→62 grp (125→146 mem, +7 canon +14 sibs); all 21 members now non-text-bearing.
`--check` exits 0; 20 new card tests pass; **fast tier 1523 pass** (0 fail; the 118
web errors = the known WinError-5 basetemp quirk, confirmed pass with --basetemp
override). **GOTCHA re-confirmed:** a `WhenUnitDefeated(filter=kind="unit")` observer
only matches while the defeated unit's `ci.zone` is still an ARENA zone — real
`_defeat_unit` removes it from the arena LIST but keeps `ci.zone` as the arena zone
until AFTER triggers fire, so HK-47 works; but the `_defeat_and_fire` test helper
sets `ci.zone=DISCARD` too early, so an observer test must use `_fire_when_defeated`
(keeps the unit in-arena) — the Hevy TWI_164 pattern. REMAINING: Stage 4 continues
(needs_encoding 131 groups). Good next shipped-canonical candidates (existing
primitives): SEC_130 Ferrix Uprising (DealDamageEqualTo — needs new x2 count arm),
LOF_240 Flight of the Inquisitor (two stacked return_from_discard), SHD_57 Rickety
Quadjumper (peek-top-then-conditional-select_token), LAW_247 Backed by the Hutts
(CreateCreditToken + DealDamageEqualTo credit-count).

**STAGE 4 BATCH 2 DONE 2026-07-05** — encoded 7 more needs_encoding groups
(shipped-set canonicals, ALL pure reuse of existing primitives — NO new engine
primitive, NO new count arm, no escalations). Each canonical registered + siblings
aliased in `REPRINT_ALIASES`; focused tests (card# in method names). Groups:
- **SOR_112 Consortium StarViper** (Unit) = conditional self-grant
  `ConstantAbility(SELF, KeywordGrant("Restore",2), condition=CONTROLLER_HAS_INITIATIVE)`
  (Separatist Commando pattern; sanitiser strips printed Restore). sib ASH_122.
- **SOR_113 Homestead Militia** (Unit) = `ConstantAbility(SELF, KeywordGrant("Sentinel"),
  condition=CONTROLLER_N_PLUS_RESOURCES(6))` (Sentinel sibling of Shoretrooper SHD_83
  StatBonus; sanitiser strips printed Sentinel). sib JTL_113.
- **SOR_125 Prepare for Takeoff** (Event) = deck_search adapter `push_deck_search(
  count=2, window=8, up_to=True, eligible=Vehicle unit)` (This Is The Way SHD_253
  pattern). sib JTL_128.
- **SHD_260 Street Gang Recruiter** (Unit) = `WhenPlayed` return_from_discard adapter
  `push_return_from_discard(count=1, eligible=Underworld card)` (Razor Crest SHD_44
  pattern). sib LAW_261.
- **LOF_45 Yaddle** (Unit, Restore1 kept) = `OnAttack GrantKeyword("Restore",1,
  friendly Jedi not_self EACH_FRIENDLY, THIS_PHASE)` (each-friendly grant; keeps own
  printed Restore since grant is to others). sib P25_143.
- **LOF_77 Crushing Blow** (Event) = `EventAbility([DefeatUnit(non_leader, cost_max=2)])`
  (Confiscate/Fell-the-Dragon pattern). sib LOFP_3.
- **SEC_88 First Light** (Unit, Ambush+Plot keyword layers) = optional
  `OnAttackDefeatsUnit → DrawCards(1)` (Fett's Firespray LAW_252 pattern). sib P25_25.
Only edits outside per-card blocks: added `EACH_FRIENDLY` to lof imports,
`OnAttackDefeatsUnit`+`DrawCards` to sec imports. Result: needs_encoding 145→138 grp
(357→343 mem), already_covered 48→55 grp (111→125 mem, +7 canon +7 sibs); all 14
members now non-text-bearing. `--verify-playable` exits 0; test_reprints **208 pass**;
13 new card tests pass; **fast tier 1585 pass** (basetemp override → 0 WinError-5
errors). ONE collateral test fix: `TestRefugeeOfThePath::test_lof_242` had used
SOR_113 Homestead Militia as a convenient "genuinely has Sentinel" unit — but SOR_113
is now correctly encoded with CONDITIONAL Sentinel (6+ resources) and its printed
Sentinel stripped, so that test now uses **SOR_229 Cell Block Guard** (a vanilla
unconditional-Sentinel unit). Lesson: encoding a previously-vanilla card can break
tests that leaned on its always-on printed keyword. REMAINING: Stage 4 continues
(needs_encoding 138 groups).
Good next candidates (still shipped canonical, mostly existing primitives): SEC_130
Ferrix Uprising (DealDamageEqualTo needs new x2 count arm), SEC_158 Oppression Breeds
Rebellion (draw 3 if a friendly unit was defeated attacking this phase — needs a
new condition), LOF_240 Flight of the Inquisitor (two return_from_discard: Force unit
+ Lightsaber upgrade — pure reuse, two stacked decisions), LOF_207 Loth-Cat
(WhenPlayed/WhenDefeated optional exhaust ground unit — pure reuse), SHD_57 Rickety
Quadjumper (peek-top-then-conditional-select_token — pure reuse, Shuttle Tydirium
JTL_200 shape).

**STAGE 4 BATCH 1 DONE 2026-07-05** — encoded 8 needs_encoding groups (shipped-set
canonicals, all pure reuse of existing primitives — NO new engine primitive, no
escalations). Each canonical registered + siblings aliased in `REPRINT_ALIASES`;
focused tests (card# in method names). Groups:
- **SOR_43 Superlaser Blast** (Event) = `EventAbility([DefeatAllUnits(filter=any
  unit)])` — first user of the pre-existing DefeatAllUnits primitive. sib P25_66.
- **LAW_131 Incapacitate** (Event) = `EventAbility([ModifyStats(-2,-2, any unit,
  THIS_PHASE)])` (Moment-of-Glory pattern, debuff). sib LAWP_12.
- **SHD_37 Supreme Leader Snoke** (Unit) = `ConstantAbility(target=enemy non_leader,
  StatBonus(-2,-2))`. sibs J24_3, P25_76.
- **JTL_85 Victor Leader** (Unit) = `ConstantAbility(target=friendly space not_self,
  StatBonus(1,1))`. sibs P25_154, P25_164.
- **JTL_33 Onyx Squadron Brute** (Unit) = `WhenDefeated Heal(2, friendly base
  EACH_FRIENDLY)`. sib JTLP_2.
- **JTL_151 Red Five** (Unit) = optional `OnAttack DealDamage(2, damaged unit)`. sib JTLP_12.
- **SEC_142 Fulminatrix** (Unit) = two optional triggers `WhenPlayed`+`OnAttack`,
  each `DealDamage(4, ground unit)`. sib SECP_12.
- **LOF_165 Asajj Ventress** (Unit) = two triggers `WhenPlayed`+`OnAttack`, each
  `ModifyStats(+2/0, friendly Force not_self, THIS_PHASE)`. sib P25_84.
Result: needs_encoding 153→145 grp (375→357 mem), already_covered 40→48 grp
(93→111 mem, +8 canon +10 sibs); all 18 members now non-text-bearing. New alias
entries face-guard clean. test_reprints 187 pass; fast tier **1433 passed** (118
errors = the known WinError-5 web-tmp_path teardown quirk, unrelated). REMAINING:
Stage 4 continues (needs_encoding 145 groups). Good next candidates (shipped
canonical, existing primitives): SEC_114 Kino Loy (scaling StatBonus.count — needs
new count arm), SEC_130 Ferrix Uprising (DealDamageEqualTo x2 count), LOF_45 Yaddle
(GrantKeyword Restore to EACH), SEC_88 First Light (OnAttackDefeatsUnit draw).

Reprint-duplicate sweep planned 2026-07-04. Many DB cards are exact reprints of
another (same printed face, different set_code/card_number/art — e.g. Rio Durant
*Beckett's Right Hands* LAW_93==P26_2; Maul *Shadow Collective Visionary*
J24_4==P25_155==P25_165==SHD_90). A shared **name** is NOT enough (Maul is 4
different cards); match the whole printed face.

**Key mechanism (why it's cheap):** runtime abilities AND the keyword sanitizer
both resolve via `get_abilities(set_code, card_number)` from
`registry._REGISTRY` (keyed by `@card_ability(SET,NUM)`). A reprint already has
correct stats/keywords/traits from its own DB row — it only lacks a registry
entry. So we **alias** the reprint's key to its implemented twin's specs (copy
`_REGISTRY[canonical]` onto the reprint key + escape-hatch membership), applied at
import time before `repository._hydrate`. No card logic duplicated.

**STAGE 3 DONE 2026-07-05** — verified the two "no work" buckets. **already_playable
(103 members): 0 exceptions** (all re-classify vanilla/keyword-complete).
**keyword_deferred: 1 exception found** — Ki-Adi-Mundi (J25_2 + TWI_64, Coordinate):
the Coordinate keyword IS implemented engine-side, but the card carries an
UNREGISTERED per-card ability ("When an opponent plays their second card each phase:
draw 2"), so it is NOT truly playable. Root cause = `audit.classify` masks a card's
functional text behind the `keyword-deferred` label whenever it bears a Phase-3
keyword. **Fix (durable): `find_reprints._bucket` now looks past that mask** (via a
`has_text_keys` set built from `has_functional_text`) — a keyword-deferred member
that still has functional text is routed to **needs_encoding**, matching the
docstring's "and no member carries functional ability text". Ki-Adi-Mundi (no
registered twin) auto-re-bucketed → **keyword_deferred 1grp/2→0/0, needs_encoding
152/373→153/375** (totals preserved 235/571). New **`find_reprints.py
--verify-playable`** mode (+ `verify_playable()` + `IMPL_ENGINE_KEYWORDS` =
PHASE2 | {Coordinate,Bounty}) is the Stage-3 regression check: exits 0, "all 103
already_playable + 0 keyword_deferred members are playable". `tests/test_reprints.py`
+6 (TestVerifyPlayable) → 157 pass; fast tier 1505 pass (0 fail; --basetemp override
also avoided the WinError-5 web quirk). REMAINING: **Stage 4** (encode needs_encoding
153/375, now incl. Ki-Adi-Mundi/TWI_64).

**STAGE 2 DONE 2026-07-04** — `REPRINT_ALIASES` populated with all 47 mirror-gap
members (reprint→canonical, taken verbatim from the worklist); applied at import,
all 47 wire (`get_abilities(reprint) is get_abilities(canonical)`) + face-identical
+ classify as implemented/escape-hatch. **Audit playable 744→791 (+47 exactly);
registered 307→354.** `find_reprints.py --check` now exits 0 (mirror bucket → 0
groups; the 34 mirror groups folded into `already_covered`, now 40/93). CLAUDE.md
Phase-7 "Reprint aliasing" note added. `tests/test_reprints.py` rewritten (151
tests: identity helper + parametrized per-alias wiring/face/classify + guard +
--check-passes/--check-fails-if-removed + table==worklist-mirror). Fast tier 1381
pass (118 errors = the WinError-5 tmp_path web-test quirk, confirmed unrelated via
--basetemp); medium soak 3/3 green. **REMAINING: Stage 3** (verify already_playable
42/103 + keyword_deferred 1/2 buckets), **Stage 4** (encode needs_encoding 152/373).

**STAGE 1 DONE 2026-07-04** — detection tooling + alias mechanism built & green
(fast tier 1241 pass, the 118 errors are the pre-existing WinError-5 tmp_path
teardown quirk in web tests, unrelated). Pieces:
- `scripts/find_reprints.py` — reuses `audit_coverage` (load_cards, _load_registry,
  classify, is_playable, index_by_set_number, TOKEN_TYPES) for classification, and
  the shared face-key from reprints.py for grouping; writes `docs/reprints_worklist.json`;
  `--check` exits non-zero if any mirror gap is un-aliased.
- `src/swu/cards/reprints.py` — EMPTY `REPRINT_ALIASES` dict, the canonical
  `face_key`/`load_faces` identity helper (imported BY find_reprints so they can't
  diverge), and guarded `apply_reprint_aliases()` (asserts canonical registered +
  faces byte-identical, else raises; copies `_REGISTRY[canonical]` + escape-hatch
  membership onto the reprint key). Robust DB resolver (SWU_DB / parents[3]/data).
- Wired `from swu.cards import reprints; reprints.apply_reprint_aliases()` LAST in
  `src/swu/cards/__init__.py` (attribute access `swu.cards.reprints.x` fails mid
  package-init — must use the `from … import` binding).
- NOTE: `--check` INTENTIONALLY FAILS at Stage 1 (47 mirror gaps, empty table) —
  it passes only after Stage 2 populates the table. The test asserts both directions.

**Sizing (STRICT full-face key, 2026-07-04 via find_reprints.py):** 235 reprint
groups / 571 members (strict key incl. subtitle+stats; supersedes the earlier
coarse 208/516). Buckets (each group bucketed exactly once):
- **mirror** 34 groups / 81 members — **47 gap members to alias for free** (Stage 2).
  E.g. Ahsoka Tano JTL_201→5 promos (J25_8/P25_160/P25_170/P26_78/P26_94);
  Boba Fett LAW_214←C26_1; C-3PO SEC_93←SECP_7.
- **already_covered** 6 groups / 12 — every member already registered (no-op).
- **already_playable** 42 groups / 103 — vanilla/keyword-complete, verify (Stage 3).
- **keyword_deferred** 1 group / 2 (Stage 3).
- **needs_encoding** 152 groups / 373 — genuine encodes, overlaps normal backlog (Stage 4).

**Plan = 4 stages, each with a ready-made prompt in
`docs/reprint_duplicates_plan.md`:** (1) build `scripts/find_reprints.py` (reuses
audit_coverage.classify) + `src/swu/cards/reprints.py` (REPRINT_ALIASES +
guarded `apply_reprint_aliases()`, imported LAST in cards/__init__.py) + tests;
(2) populate REPRINT_ALIASES for the 38 mirror-gaps; (3) verify the
already-playable/keyword-deferred buckets; (4) encode the needs_encoding groups in
small batches (shipped-set canonical first, escalate new primitives separately),
aliasing siblings. Identity-key + face-identity guard mandatory. See
[[project-phase7-workflow]] for the per-card encode recipe.
