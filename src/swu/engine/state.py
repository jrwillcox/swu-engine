"""
Game state for a 2-player SWU match.

Design contract
---------------
* apply() deep-copies state before mutating — never mutates its input.
  CardDef objects (frozen dataclasses from models.py) are shared across
  copies via __deepcopy__ returning self; all mutable wrappers are copied.
* All randomness flows through the Random instance reconstructed from
  rng_state.  Same seed + same action sequence => identical game.
* GameState is JSON-serialisable via to_json() / GameState.from_json().
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional, TYPE_CHECKING, cast

from swu.cards.models import AnyCard, Base, Leader
from swu.engine.decisions import PendingDecision

if TYPE_CHECKING:
    # Imported inside view_for() at runtime to break the state<->views cycle;
    # declared here so the return annotation resolves for type checkers.
    from swu.engine.views import PlayerView


# ── Modifier record ───────────────────────────────────────────────────────────

@dataclass
class Modifier:
    """A transient stat/keyword modifier created by an ability effect.

    kind:
      "stats"          — value is {"power": int, "hp": int}
      "keyword_grant"  — value is {"keyword": str, "value": int}
      "keyword_revoke" — value is {"keyword": str, "value": 0}

    duration:
      "permanent"    — lasts until source leaves play (or explicitly removed)
      "this_phase"   — cleared at end of current ACTION phase
      "this_attack"  — cleared at end of current attack
      "this_round"   — cleared at end of regroup (start of next round)
    """
    modifier_id: str
    source_instance_id: str
    target_instance_id: Optional[str]  # None if category-wide
    kind: str
    value: Any                         # dict (see above)
    duration: str                      # "permanent" | "this_phase" | "this_attack" | "this_round"

    def to_dict(self) -> dict:
        return {
            "modifier_id": self.modifier_id,
            "source_instance_id": self.source_instance_id,
            "target_instance_id": self.target_instance_id,
            "kind": self.kind,
            "value": self.value,
            "duration": self.duration,
        }

    @staticmethod
    def from_dict(d: dict) -> "Modifier":
        return Modifier(
            modifier_id=d["modifier_id"],
            source_instance_id=d["source_instance_id"],
            target_instance_id=d.get("target_instance_id"),
            kind=d["kind"],
            value=d["value"],
            duration=d["duration"],
        )


# ── GameMemory ────────────────────────────────────────────────────────────────

@dataclass
class GameMemory:
    """Phase/round-scoped transient facts needed by abilities.

    Cleared at appropriate phase transitions by the action engine.
    """
    units_played_this_phase: set = field(default_factory=set)    # instance_ids
    # Instance_ids of units whose owner may replay them from their discard pile
    # FOR FREE for the rest of this phase (Second Chance SHD_53: "When Defeated:
    # For this phase, this unit's owner may play it from their discard pile for
    # free.").  Added by the granted When-Defeated effect keyed to the dying unit;
    # read by ``actions._enumerate_discard_play_actions`` (a free ``PlayFromDiscard``
    # for each such unit sitting in the active player's discard) and consumed when
    # the unit is replayed.  Phase-scoped — cleared at the phase rollover, the same
    # duration basis as ``units_played_this_phase``.
    free_discard_play_this_phase: set = field(default_factory=set)  # instance_ids
    # The CROSS-PILE sibling of the field above: a permission granted to a player to
    # play, for free, a card sitting in ANOTHER player's discard pile ("Choose an
    # opponent.  For this phase, they may play this unit from its owner's discard
    # pile for free." — Stolen AT-Hauler JTL_221).  Keyed by the PERMITTED player's
    # id → the instance_ids they may play; the card stays in its owner's discard
    # (and returns there when it later leaves play), it simply enters under the
    # player who paid nothing for it, since control follows the holder.  Read by
    # ``actions._enumerate_discard_play_actions`` and consumed on replay.
    # Phase-scoped, cleared at the phase rollover.
    foreign_free_discard_play_this_phase: dict = field(
        default_factory=dict)  # permitted player_id -> [instance_ids]
    # The PAID sibling of the field above: instance_ids in ANOTHER player's discard
    # pile that the keyed player may play this phase by PAYING the card's cost, with
    # its aspect penalties waived ("Discard a card from the defending player's deck.
    # For this phase, you may play that card from their discard pile, ignoring its
    # aspect penalties." — Obi-Wan Kenobi SEC_205).  Read by
    # ``actions._enumerate_discard_play_actions`` and consumed on replay.
    # Phase-scoped, cleared at the phase rollover.
    foreign_discard_play_this_phase: dict = field(
        default_factory=dict)  # permitted player_id -> [instance_ids]
    # The DISCOUNTED sibling of the field above: instance_ids in a discard pile that
    # their owner may play for the rest of this phase, each at the recorded number of
    # resources less ("For this phase, you may play the discarded cards, and they each
    # cost 2 resources less" — Aid from the Innocent TWI_201).  Unlike the free
    # permission (a Second Chance replay, hence Unit-only) the discounted one covers
    # any card type, because the cards it grants are non-units.  Read by
    # ``actions._enumerate_discard_play_actions`` and consumed when the card is
    # played.  Phase-scoped, cleared at the phase rollover.
    discard_play_discount_this_phase: dict = field(default_factory=dict)  # iid -> int
    # Instance_ids of UNITS that actually had damage removed this phase ("each
    # friendly unit that was healed this phase gets +1/+0" — Barriss Offee TWI_42).
    # Fed by ``actions.note_unit_healed`` from the heal chokepoints, and only when
    # damage was really removed (healing an undamaged unit heals nothing, so it is
    # not "healed").  Read by the ``healed_this_phase`` target predicate.
    # Phase-scoped, cleared at the phase rollover.
    units_healed_this_phase: set = field(default_factory=set)    # instance_ids
    # Instance_ids of UNITS that actually took damage this phase — the exact MIRROR
    # of the ledger above, for "Ready a unit that was damaged this phase"
    # (Galvanized Leap ASH_188).  Distinct from the ``damaged`` predicate, which
    # reads a unit's CURRENT damage: a unit healed since still counts here, and one
    # that entered play already damaged does not.  Fed at the single unit-damage
    # chokepoint ``actions._deal_damage_with_shield``, and only for damage that was
    # really dealt (a fully prevented hit is not damage).  Read by the
    # ``damaged_this_phase`` target predicate.  Phase-scoped.
    units_damaged_this_phase: set = field(default_factory=set)   # instance_ids
    # PLAYER IDs who created at least one token this phase — "If you created a token
    # this phase, …" (The Client LAW_16).  Fed at the THREE token-creation
    # chokepoints (``tokens.attach_token`` for a Shield/Experience upgrade,
    # ``tokens.create_credit_token`` for a Credit, ``actions._create_token_units``
    # for a token unit), so every way a token comes into existence records one
    # entry.  DOCUMENTED SIMPLIFICATION: ``attach_token`` records the HOST's
    # controller rather than whoever caused the attachment — the two differ only
    # when a card gives a token to an ENEMY unit, which no shipped card does.
    # Phase-scoped, cleared at the phase rollover (the card says "this phase").
    tokens_created_this_phase: set = field(default_factory=set)   # player_ids
    # Per-player count of cards played this phase, keyed player_id -> int, for the
    # "an opponent plays their Nth card each phase" observer (Ki-Adi-Mundi TWI_64).
    # Incremented at the CardPlayed firing chokepoint (resolver.fire_triggered_
    # abilities) so the count stays aligned with the firing opportunities — the Nth
    # *fired* play is exactly when the count reaches N (effect-driven plays that
    # append CardPlayed without firing it do not count, matching every other
    # WhenYouPlayCard observer's coverage).  Cleared at the phase rollover.
    cards_played_this_phase: dict = field(default_factory=dict)  # player_id -> int
    # The effective TRAITS of every card each player has played this phase, fed at
    # the same CardPlayed chokepoint as the counter above — "If you played a First
    # Order card this phase" (Captain Phasma JTL_10).  The counter alone cannot
    # answer a trait question, and the played card may already have left play (an
    # event goes straight to the discard), so the traits are recorded at play time
    # rather than re-derived.  Cleared at the phase rollover.
    traits_played_this_phase: dict = field(default_factory=dict)  # player_id -> set[str]
    # The NON-UNIT slice of the ledger above, fed at the same chokepoint from the
    # same traits but only when the played card is not a Unit — "If you played a
    # non-unit Force card this phase" (Rey LOF_12).  A separate dict rather than a
    # filter because the card type is known only at play time (an event is already
    # in the discard when the condition is read).  Cleared at the phase rollover.
    non_unit_traits_played_this_phase: dict = field(default_factory=dict)  # pid -> set[str]
    units_defeated_this_round: set = field(default_factory=set)  # instance_ids
    # instance_ids of cards discarded from a hand or deck this PHASE (fed by
    # actions.note_hand_or_deck_discard at the self-discard / mill sites).  Cleared
    # at the phase rollover.  Gates "If this unit was discarded from your hand or
    # deck this phase, play it from your discard pile" (Kylo's TIE Silencer SHD_135).
    cards_discarded_this_phase: set = field(default_factory=set)  # instance_ids
    units_attacked_this_round: set = field(default_factory=set)  # instance_ids
    # instance_ids of units that dealt combat damage to a base this round ("this
    # round" == "this phase" — base attacks happen only in ACTION, cleared at the
    # round rollover; the units_attacked_this_round precedent).  Recorded at the
    # base-combat damage step.  Gates "Defeat a unit that dealt damage to a base
    # this phase" (Retaliation SEC_77).
    units_dealt_base_damage_this_round: set = field(default_factory=set)
    # base-owner player_id -> list of enemy unit instance_ids that DECLARED an
    # attack against that player's base this round ("this round" == "this phase" —
    # base attacks happen only in ACTION, cleared at the round rollover; the
    # units_attacked_this_round precedent).  Recorded at the base-attack DECLARE
    # step (so it counts "attacked", not "dealt damage").  Gates "an enemy unit
    # that attacked your base this phase" (Ephant Mon SHD_88).
    base_attackers_this_round: dict = field(default_factory=dict)  # base_owner -> [ids]
    # player_ids who DECLARED an attack with a TOKEN unit this round ("this round" ==
    # "this phase" — attacks happen only in ACTION, cleared at the round rollover; the
    # units_attacked_this_round precedent).  Written at the same three DECLARE steps as
    # that set, and it has to be its own ledger rather than a scan of it: a token that
    # attacked and then died ceases to exist entirely (tokens are not discarded), so
    # ``find_instance`` — the way every other "attacked this phase" atom re-reads its
    # attackers — can never see it again.  Gates "While you've attacked with a token
    # unit this phase, this unit gets +2/+0" (Asajj Ventress TS26_7 deployed).
    token_unit_attackers_this_round: set = field(default_factory=set)  # player_ids
    # player_ids who lost a unit that was *defeated while attacking* this round
    # ("this round" == "this phase" — attacks happen only in ACTION, cleared at the
    # round rollover; the units_defeated_this_round precedent).  Recorded by the
    # unit-combat step when the attacker is defeated.  Gates "If a friendly unit was
    # defeated while attacking this phase, …" (Oppression Breeds Rebellion SEC_158).
    attackers_defeated_this_round: set = field(default_factory=set)  # player_ids
    # Controller-at-death of every unit defeated this round, one entry per defeat
    # (a list so counts survive — "each enemy unit that was defeated this phase",
    # Darth Sion SEC_35).  "this round" == "this phase" (defeats happen only in
    # ACTION, cleared at the round rollover; the units_defeated_this_round precedent).
    defeated_controllers_this_round: list = field(default_factory=list)  # player_ids
    epic_actions_spent: set = field(default_factory=set)         # instance_ids (non-deploy epics)
    # Per-GAME activated-ability use counter, keyed by the source card's
    # instance_id → count (Mystic Monastery LOF_22: "Use this ability no more than 3
    # times each game").  Incremented by every ``UseAbility`` and read by the
    # ``SOURCE_ABILITY_USES_MAX`` condition; never cleared, like epic_actions_spent.
    activated_ability_use_counts: dict = field(default_factory=dict)
    # Activated abilities flagged ``once_per_round`` that have been used this round
    # (MagnaGuard Wing Leader TWI_82).  Each entry: ``f"{instance_id}:{ability_idx}"``;
    # cleared at the round rollover.
    activated_abilities_used_this_round: set = field(default_factory=set)
    # Source instance_ids of ``once_per_round`` StandingPlayDiscount markers whose
    # discount has been used this round (Director Krennic JTLP_1: "the first unit
    # you play each round that has a When Defeated ability costs 1 less").  Consumed
    # at the real play site (actions._consume_standing_discount); cleared at the
    # round rollover.  The activated_abilities_used_this_round once-per-round pattern.
    standing_play_discounts_used_this_round: set = field(default_factory=set)
    # Source instance_ids of ``once_per_round`` WhenDefeatedRedo markers whose
    # "use that When Defeated ability again" has been used this round (Grand
    # Admiral Thrawn JTL_2's DEPLOYED side).  Charged on ACCEPT only — declining
    # the optional re-use is not a use — and cleared at the round rollover.  The
    # activated_abilities_used_this_round once-per-round pattern.
    when_defeated_redo_used_this_round: set = field(default_factory=set)
    # instance_id → keyword name chosen by a "When Played: Choose <keyword>…"
    # ability whose grant then lasts "while this unit is in play" (Admiral Yularen
    # JTL_47).  NOT phase/round scoped: the choice is a property of that instance
    # for as long as it stays in play, read by
    # Condition.SOURCE_CHOSEN_KEYWORD, which gates the card's four
    # ConstantAbility grants (one per offerable keyword).  A fresh copy of the
    # card gets a fresh instance_id, so a stale entry is unreachable.
    chosen_keywords: dict = field(default_factory=dict)  # instance_id -> keyword
    # instance_id → the arena ("ground"/"space") its controller chose for a
    # "Choose an arena.  For this phase, each unit in that arena gains: …" effect
    # (Treacherous Minefield ASH_186) — the ``chosen_keywords`` shape one layer
    # over, read by the ``in_source_chosen_arena`` target predicate so ONE aura
    # spec can be pinned to whichever arena was picked.  Not cleared: the aura it
    # gates is itself phase-scoped (``phase_aura_sources``), and a fresh copy of
    # the card gets a fresh instance_id, so a stale entry is unreachable.
    chosen_arenas: dict = field(default_factory=dict)  # instance_id -> arena
    # Owner ids of bases with a one-shot "the next time damage would be dealt to
    # it this phase, prevent that damage" armed (Close the Shield Gate JTL_74).
    # Consumed by the first damage instance reaching that base
    # (actions.base_damage_after_prevention, read at every base-damage site) and
    # cleared at the phase rollover, so "this phase" needs no expiry bookkeeping.
    prevent_next_base_damage: set = field(default_factory=set)  # player_ids
    # Player_ids who have played a Villainy card this phase.  Controller-scoped
    # because the cards that read this ("If YOU played a Villainy card this
    # phase", e.g. Darth Vader SOR_10) key off the source's own controller — an
    # OPPONENT playing a Villainy card must NOT satisfy the condition for you.
    villainy_players_this_phase: set = field(default_factory=set)  # player_ids
    # Per-player total combat damage dealt to an ENEMY base this phase, keyed
    # player_id -> int (Cassian Andor SOR_13's undeployed "If you've dealt 3 or
    # more damage to an enemy base this phase").  Accumulated at the direct
    # base-combat damage step (the common case, alongside
    # units_dealt_base_damage_this_round); non-combat / Overwhelm-spillover base
    # damage is a documented uncovered edge.  Cleared at the phase rollover.
    base_damage_dealt_this_phase: dict = field(default_factory=dict)  # player_id -> int
    # instance_ids that have already spent their once-per-phase whole-instance
    # damage prevention ("The first time this unit would take damage each phase,
    # prevent that damage" — Umbaran Mobile Cannon SEC_67, via
    # DamagePrevention(first_each_phase=True)).  Cleared at the phase rollover.
    first_damage_prevented_this_phase: set = field(default_factory=set)
    # player_id -> number of real TURN ACTIONS taken this action phase (counted in
    # ``actions.apply`` on a clear stack).  Answers "Play only as your first action
    # in the action phase" (Confidence in Victory SEC_145).  Phase-cleared.
    actions_taken_this_phase: dict = field(default_factory=dict)
    # Scheduled "if you are the only player who controls units in <arena> at the
    # start of the regroup phase, you win the game" entries (Confidence in Victory
    # SEC_145), each {"player_id", "arena"}.  Checked and cleared in
    # ``actions._enter_regroup``; the win is delivered the ``lose_at_regroup`` way,
    # by marking every OTHER player's base defeated.
    win_at_regroup_sole_arena: list = field(default_factory=list)
    # instance_ids of captured cards whose owner rescues them at the start of the
    # next regroup phase (Arrest SEC_195).  Swept and cleared in
    # ``actions._enter_regroup`` through the shared ``_rescue_captured_card`` seam;
    # a one-shot, and a no-op for a card that has already left the capture pile.
    rescue_at_regroup: list = field(default_factory=list)
    # Per-player count of OWN resources to defeat at the start of the next regroup
    # phase, keyed player_id -> int ("If you do, defeat that many friendly resources
    # at the start of the regroup phase" — Sundari Palace TS26_12).  The numeric
    # sibling of ``rescue_at_regroup``: swept and cleared in ``actions._enter_regroup``
    # through the shared fungible auto-pick ``_fire_defeat_own_resource`` (resources
    # are face-down and not targetable, the K-2SO SOR_145 convention), and a clean
    # no-op for a player whose row has since emptied.
    defeat_resources_at_regroup: dict = field(default_factory=dict)
    # player_ids who can't play EVENTS this phase (Trade Route Taxation SEC_126).
    # Read at the two hand-play seams (the enumeration skip and PlayCard's guard),
    # the CannotPlayFromHand shape; cleared at the phase rollover.
    cannot_play_events_this_phase: set = field(default_factory=set)
    events_played_this_round: set = field(default_factory=set)   # player_ids who've played >=1 event
    # Pending "next <trait> unit you play this phase costs N less" discounts
    # (Khetanna LAW_158).  Each entry: {"player_id", "trait", "amount"}.  Consumed
    # one-per-matching-play by the play-cost path; cleared at the phase rollover.
    pending_play_discounts: list = field(default_factory=list)
    # Pending "the next <trait> card you play this phase gains Exploit N" grants
    # (Count Dooku TWI_5).  Each entry: {"player_id", "trait", "amount"}.  Read and
    # consumed at the single Exploit seam in ``PlayCard.apply`` — the played card's
    # Exploit value becomes printed + granted, so a card with no printed Exploit
    # gains one.  The pending_play_discounts shape, one grant per matching play;
    # cleared at the phase rollover.
    pending_exploit_grants: list = field(default_factory=list)
    # Pending "the next [<trait>] unit you play this phase gains K for this phase"
    # keyword grants (Deceptive Shade LOF_180).  Each entry:
    # {"player_id", "trait", "keyword"}.  Consumed one-per-matching-play in
    # ``actions._put_unit_in_play`` (before the enter-play keyword bus, so a granted
    # Ambush triggers on entry); the pending_exploit_grants shape, cleared at the
    # phase rollover.
    pending_keyword_grants: list = field(default_factory=list)
    # The same pending-charge shape for "the next unit you play this phase with 1 or
    # less power ENTERS PLAY READY" (Neel ASH_248).  Entries are
    # ``{"player_id", "power_max"}``; ``_put_unit_in_play`` consumes the FIRST
    # matching one per play (so two charges ready the next two units, not one twice)
    # and the whole list is cleared at the phase rollover.
    pending_enters_ready: list = field(default_factory=list)
    # Queue of player_ids whose BASE was dealt damage since the last settle point,
    # populated by the base-damage sinks (the base-attack pipeline and the ability
    # damage sink) and drained at the action settle-point
    # (actions.apply → _fire_base_damage_observers) to fire the
    # WhenDamageDealtToYourBase observer (The Daughter LOF_252).  The
    # noncombat_damage_dealers shape: always empty between actions, so no phase or
    # round clear is needed.
    base_damage_events: list = field(default_factory=list)
    # Armed "the next time you take the initiative this phase, <effect>" charges
    # (Premonition of Doom LOF_203).  Each entry: {"player_id", "effect"}, the only
    # effect today being "exhaust_all_units"; consumed by the matching player's
    # ``ClaimInitiative``.  Phase-scoped like every other pending_* list.
    pending_initiative_effects: list = field(default_factory=list)
    # Armed "the next time you use a When Played ability this phase, you may use it
    # again" charges, keyed by controller player_id → count (Qui-Gon Jinn's
    # Aethersprite LOF_197).  An OnAttack arms one charge for its controller; the
    # next qualifying WhenPlayed ability that controller uses consumes one charge
    # and offers an optional re-use of that same ability (resolver._schedule_when_
    # played_redo).  Phase-scoped — attacks happen only in ACTION, so clearing at
    # the round rollover matches "this phase" (the units_played_this_phase note).
    when_played_redo_charges: dict = field(default_factory=dict)
    # Queue of player_ids who dealt *non-combat* damage since the last settle
    # point, populated by the non-combat damage sinks (resolver._apply_deal_damage
    # / _apply_indirect_damage) and drained at the action settle-point
    # (actions.apply → _fire_noncombat_damage_observers) to fire the
    # WhenDealNonCombatDamage observer (Boba Fett JTL_9).  Deduped, and always
    # empty between actions (drained every settle) — so serialising it matters only
    # for a state persisted mid-decision.  No phase/round clear needed.
    noncombat_damage_dealers: list = field(default_factory=list)
    # Queue of ACTION-phase draw *events* since the last settle point, populated by
    # ``actions._draw_cards`` (only during ACTION, only when ≥1 card was drawn) and
    # drained at the action settle-point (``actions.apply`` → ``_fire_draw_observers``)
    # to fire the WhenYouDraw observer (The Mandalorian LAW_52 in-play "when you draw
    # 1+ cards"; Rey LOF_148 "when you draw this card").  Each entry:
    # {"player_id", "card_ids": [...]}.  Always empty between actions (drained every
    # settle) — so serialising it matters only for a state persisted mid-decision.
    # No phase/round clear needed.
    action_phase_draws: list = field(default_factory=list)
    # Queue of player_ids who used the Force (spent their Force token) since the
    # last settle point, populated by ``actions.spend_force_token`` (the single
    # Force-spend chokepoint) and drained at the action settle-point
    # (``actions.apply`` → ``_fire_force_observers``) to fire the WhenYouUseForce
    # observer (Yoda LOF_101).  Always empty between actions (drained every settle)
    # — so serialising it matters only for a state persisted mid-decision.  No
    # phase/round clear needed.
    force_uses: list = field(default_factory=list)
    # Queue of player_ids who revealed OR discarded 1+ cards from their hand since
    # the last settle point - ONE entry per reveal/discard instruction, populated by
    # ``actions._resolve_disclose`` (a successful Disclose reveal) and
    # ``actions.record_hand_discard`` (the DiscardFromHand effect arm + the bespoke
    # first-card hand-discard CustomEffects), drained at the action settle-point
    # (``actions.apply`` -> ``_fire_reveal_discard_observers``) to fire the
    # WhenYouRevealOrDiscard observer (Padme Amidala SEC_16).  Always empty between
    # actions (drained every settle) - so serialising it matters only for a state
    # persisted mid-decision.  No phase/round clear needed.
    hand_reveal_discards: list = field(default_factory=list)
    # Queue of player_ids who DISCARDED 1+ cards from their hand since the last
    # settle point — the discard-ONLY subset of ``hand_reveal_discards`` (a Disclose
    # reveal never records here).  Populated by ``actions.record_hand_discard`` with
    # its default ``kind="discard"`` (the disclose path passes ``kind="reveal"`` and
    # so skips this ledger), and drained at the action settle-point
    # (``actions.apply`` -> ``_fire_hand_discard_observers``) to fire the
    # WhenPlayerDiscardsFromHand observer (Migs Mayfeld SHD_163 — "when a player
    # discards a card from their hand", ANY player).  Always empty between actions
    # (drained every settle).  No phase/round clear needed.
    hand_discards: list = field(default_factory=list)
    # Queue of UNIT instance_ids that had 1+ damage actually removed since the last
    # settle point — populated by ``actions.note_unit_healed`` (which already skips
    # bases and no-op heals, so an entry IS "1 or more damage healed") and drained at
    # the action settle-point (``actions.apply`` -> ``_fire_heal_observers``) to fire
    # the WhenUnitHealed observer (Silver Angel JTL_62).  One entry per heal
    # instruction, so two heals fire the observer twice.  Always empty between
    # actions (drained every settle).  No phase/round clear needed.
    heal_events: list = field(default_factory=list)
    # Queue of ``[unit_instance_id, phase_name]`` pairs — one per UNIT that readied
    # since the last settle point.  The PHASE half is recorded because the regroup
    # mass-ready is drained after the rollover into ACTION, so the phase at drain
    # time is not the phase the card readied in ("When an enemy unit readies DURING
    # THE ACTION PHASE" — Rex's DC-17s TS26_63); a bare-string legacy entry reads as
    # an ACTION ready.  Otherwise —
    # populated by ``actions.note_unit_readied`` at the ready chokepoints (the
    # regroup mass-ready ``_ready_all_cards`` and the ``ReadyCard`` effect arm) and
    # drained at the action settle-point (``actions.apply`` ->
    # ``_fire_ready_observers``) to fire the WhenUnitReadies observer (In Debt to
    # Crimson Dawn JTL_192).  The ``heal_events`` shape exactly; a bespoke
    # card-module ready that pokes ``ci.exhausted`` directly is unmarked (the
    # documented ``note_hand_or_deck_discard`` simplification).  Always empty
    # between actions (drained every settle).  No phase/round clear needed.
    ready_events: list = field(default_factory=list)
    # Queue of CONTROLLER player_ids, one entry per UPGRADE (token upgrades
    # included — in SWU a Shield / Experience / Advantage token IS an upgrade) that
    # was defeated since the last settle point.  Populated by
    # ``actions.note_upgrade_defeated`` at the upgrade-defeat sites and drained at
    # the action settle-point (``actions.apply`` -> ``_fire_upgrade_defeat_observers``)
    # to fire the WhenFriendlyUpgradeDefeated observer (Zeb Orrelios ASH_161).  The
    # ``heal_events`` shape; always empty between actions, so no phase/round clear.
    upgrade_defeats: list = field(default_factory=list)
    # Queue of HOST instance_ids, one entry per upgrade that ATTACHED to a unit since
    # the last settle point — the mirror of the queue above, for "When 1 or more
    # upgrades attach to this unit (including from Shielded)" (Sabine Wren ASH_208).
    # Fed by ``actions.note_upgrade_attached`` at the attachment chokepoints, ONLY for
    # hosts whose card actually carries such a trigger (the drain is otherwise far too
    # hot — every Shield / Experience / Advantage token attaches), and drained at the
    # action settle-point, COALESCED per host so "1 or more" is one event.  Always
    # empty between actions, so no phase/round clear.
    upgrade_attachments: list = field(default_factory=list)
    # Queue of TOKEN-CREATION records, one dict per creation call, since the last
    # settle point:
    #   {"creator": player_id, "kind": "upgrade"|"unit"|"credit",
    #    "name": token name, "count": int, "host": host instance_id or None,
    #    "ready": bool}
    # Populated at the THREE token-creation chokepoints (``tokens.attach_token``,
    # ``tokens.create_credit_token``, ``actions._create_token_units``) and drained at
    # the action settle-point (``actions.apply`` -> ``_fire_token_creation_observers``,
    # which COALESCES equal-keyed records so "give 2 Experience tokens" — two
    # ``attach_token`` calls — reads as one creation of 2) to fire the
    # WhenYouWouldCreateTokens observer (Moff Jerjerrod ASH_94).  A creation made BY
    # that observer's own top-up passes ``note_token_creation=False`` and is not
    # recorded, so the doubling cannot re-arm itself.  The ``heal_events`` shape;
    # always empty between actions, so no phase/round clear.
    token_creations: list = field(default_factory=list)
    # Queue of instance_ids of CARDS discarded from a hand or deck since the last
    # settle point — populated by ``actions.note_hand_or_deck_discard`` (the same
    # chokepoint that feeds ``cards_discarded_this_phase``) and drained at the action
    # settle-point (``actions.apply`` -> ``_fire_self_discard_observers``) to fire the
    # WhenThisIsDiscarded observer on the discarded card ITSELF (That's a Rock
    # LAW_206).  The ``ready_events`` shape; the source is found in its owner's
    # discard pile by id.  Always empty between actions (drained every settle).  No
    # phase/round clear needed.
    self_discards: list = field(default_factory=list)
    # Queue of PLAYER IDs — one entry per card discarded FROM A DECK since the last
    # settle point, the deck-only narrowing of ``self_discards`` above (both are fed
    # by ``actions.note_hand_or_deck_discard``, which takes ``from_deck``).  Drained
    # at the action settle-point (``actions.apply`` -> ``_fire_deck_discard_observers``)
    # to fire the WhenYouDiscardFromDeck observer on an IN-PLAY card whose controller
    # did the discarding (Sebulba's Podracer LAW_176).  Keyed by player rather than by
    # card because the observer asks WHO milled, not WHAT was milled — and the milled
    # card is nothing to do with the observer.  Always empty between actions (drained
    # every settle).  No phase/round clear needed.
    deck_discards: list = field(default_factory=list)
    # Per-player EXTRA resources that player must pay for each UNIT they play this
    # phase ("Each unit that opponent plays this phase costs 1 resource more" — Moff
    # Gideon JTL_188).  {player_id: extra}, summed at the single play-cost surcharge
    # site ``actions._opponent_play_tax``; the effect-granted, phase-scoped sibling
    # of the always-on ``OpponentPlayTax`` card marker (Del Meeko SOR_34).  Cleared
    # at the phase rollover; empty = inert.
    unit_play_tax_this_phase: dict = field(default_factory=dict)
    # Queue of bounty *collections* since the last settle point — ONE entry per
    # bounty resolved for its collector, populated by
    # ``resolver.fire_triggered_abilities`` when it collects an ``is_bounty``
    # WhenDefeated ability, and drained at the action settle-point
    # (``actions.apply`` -> ``_fire_bounty_observers``) to fire the
    # WhenBountyCollected observer (Bossk SHD_10).  Each entry:
    # {"collector_id", "set_code", "card_number", "ability_idx", "source_id",
    #  "defeated_controller_id"}.  Always empty between actions (drained every
    # settle) — so serialising it matters only for a state persisted mid-decision.
    # No phase/round clear needed.
    bounties_collected: list = field(default_factory=list)
    # Instance ids of sources that have spent their once-per-round "when you collect
    # a bounty, collect it again" this round (Bossk SHD_10).  Marked when the
    # re-collection resolves; gates further offers via
    # SOURCE_BOUNTY_RECOLLECT_AVAILABLE; cleared at the round rollover (the
    # activated_abilities_used_this_round once-per-round pattern).
    bounty_recollect_used_this_round: set = field(default_factory=set)
    # Global "Bases can't be healed for this phase" lock (Wolffe SOR_160).  A plain
    # phase-scoped boolean read at every base-heal chokepoint (_apply_restore,
    # _apply_heal on a base target, the Redemption heal-distribution, Reinforcement
    # Walker's discard-heal, the collector heal_base) — the heal-side mirror of the
    # CannotAttackBases marker.  Affects both players' bases; default inert.
    bases_cannot_heal_this_phase: bool = False
    # Card NAMES nobody may play for the rest of this phase ("Name a card.  Cards
    # with that name can't be played this phase" — Transmission Jamming LAW_243).
    # The effect-granted, phase-scoped, ANY-player sibling of the standing
    # ``ForbidNamedCardPlay`` marker (Regional Governor SOR_62, which bars only the
    # namer's opponents); read at the same play-legality seam
    # (actions._named_card_play_forbidden) and cleared at the phase rollover.
    forbidden_card_names_this_phase: set = field(default_factory=set)
    # Forced-attack COMPULSION (Give In to Your Anger SHD_144): "Its controller's
    # next action this phase must be an attack action with that unit, if able. It
    # must attack a unit, if able."  ``None`` (inert) or a dict
    # {"player_id", "unit_id"}.  Read at the ACTION-phase legal-action seam
    # (actions._forced_attack_actions): while set and the flagged player is active,
    # legal_actions returns ONLY that unit's attacks (a unit target if any, else
    # base) — unless the unit is unable to attack, in which case the compulsion is
    # vacuous.  Consumed by the flagged player's very next action (actions.apply)
    # and cleared at the phase rollover (the "this phase" duration).  Default inert,
    # so every existing deck is unaffected.
    forced_attack: dict | None = None
    # Delayed self-loss (Final Showdown SHD_208: "At the start of the regroup phase,
    # you lose the game").  A set of player_ids that lose at the next regroup start.
    # Read in actions._enter_regroup: each listed player is forced to lose (its base
    # is marked defeated → is_eliminated → _check_game_over).  Set when the card
    # resolves (during ACTION); it survives into REGROUP because clear_phase runs
    # only at the REGROUP→ACTION rollover.  Default empty, so every deck is
    # unaffected.
    lose_at_regroup: set = field(default_factory=set)
    # Per-player count of cards DRAWN this phase, keyed player_id -> int (Pre Vizsla
    # TWI_10: "Deal damage to a unit equal to the number of cards you've drawn this
    # phase").  Accumulated at the single draw chokepoint ``actions._draw_cards`` and
    # only while the phase is ACTION — which is exactly the card's parenthetical
    # "(This doesn't include cards drawn in the regroup phase.)".  Cleared at the
    # phase rollover.
    cards_drawn_this_phase: dict = field(default_factory=dict)  # player_id -> int
    # Aspect names carried by every unit defeated this round, keyed by its
    # controller-at-death (player_id -> list of aspect names, one list entry per
    # defeat's worth of aspects, flattened).  Recorded alongside
    # ``defeated_controllers_this_round`` at the defeat site; gates "If a friendly
    # <Aspect> unit was defeated this phase" (Chancellor Palpatine TWI_17).  "this
    # round" == "this phase" (defeats happen only in ACTION), the
    # defeated_controllers_this_round precedent.
    defeated_aspects_this_round: dict = field(default_factory=dict)  # player_id -> [str]
    # The TRAIT sibling of the ledger above, recorded at the same defeat site and
    # keyed the same way (player_id -> flattened list of trait names).  EFFECTIVE
    # traits (a TraitGrant counts), read while the unit is still whole.  Gates "If a
    # friendly Rebel unit was defeated this phase" (Jyn Erso LAW_5).  Its own ledger
    # rather than a re-find of the corpse, for the same reason the aspect one is: a
    # token unit ceases to exist and sits in no discard pile.
    defeated_traits_this_round: dict = field(default_factory=dict)  # player_id -> [str]
    # Instance ids of double-sided LEADERS currently showing their *second* side
    # (Chancellor Palpatine TWI_17: "…, then flip this leader").  A flip leader never
    # deploys — both of its sides are undeployed Actions — so the side in play is not
    # the ``deployed`` flag but this marker, read by the SOURCE_LEADER_FLIPPED /
    # SOURCE_LEADER_NOT_FLIPPED conditions that gate each side's ability.  Toggled by
    # the card's own effect; never phase/round cleared (a flip is permanent until
    # flipped back), so it is serialised like ``epic_actions_spent``.
    flipped_leaders: set = field(default_factory=set)  # instance_ids
    # Instance ids of cards whose registered ``AuraGrantedAbility`` specs apply for
    # THIS PHASE even though the card is no longer in play (Pyrrhic Assault TWI_103:
    # "For this phase, each friendly unit gains: 'When Defeated: …'").  The aura
    # collection site scans in-play sources plus every id listed here, resolving each
    # through ``find_instance`` — which reaches the discard pile, so a spent EVENT
    # keeps granting from there, with its real ``owner_id`` so "friendly" still means
    # its controller.  Appended by the granting card's own effect and cleared at the
    # phase rollover; empty ⇒ the collection site behaves exactly as before.
    phase_aura_sources: list = field(default_factory=list)  # instance_ids
    # player_ids who have DEALT indirect damage this phase (Decimator of Dissidents
    # JTL_138: "If you dealt indirect damage this phase, this unit costs 1 resource
    # less to play").  Recorded at the single indirect-damage settle point
    # (actions._resolve_assign_indirect_damage) and only when damage was really
    # dealt (a 0-point assignment is not "dealt indirect damage"); read by
    # Condition.CONTROLLER_DEALT_INDIRECT_DAMAGE_THIS_PHASE.  Phase-scoped.
    indirect_dealers_this_phase: set = field(default_factory=set)  # player_ids
    # instance_ids of units that can't attack BASES for the rest of this phase
    # (Scramble Fighters JTL_92: "Create 8 TIE Fighter tokens and ready them.  They
    # can't attack bases for this phase").  The phase-scoped, per-instance sibling
    # of the CannotAttackBases card marker (Entrenched SOR_72), read at the same
    # single seam (actions._cannot_attack_bases) so the base-attack option is
    # dropped at enumeration while unit attacks stay intact.  Default empty.
    cannot_attack_bases_this_phase: set = field(default_factory=set)  # instance_ids
    # player_ids whose BASE took damage this phase, from any source (fed at the
    # single ``actions.record_base_damage`` chokepoint the WhenDamageDealtToYourBase
    # observer already uses).  Answers "If an enemy base was damaged this phase"
    # (Baylan Skoll ASH_39) — the standing, board-readable sibling of that drained
    # queue.  Cleared at the phase rollover.
    bases_damaged_this_phase: set = field(default_factory=set)  # player_ids
    # controller_ids who had an UPGRADE defeated this phase, fed at the single
    # ``actions.note_upgrade_defeated`` chokepoint that already drives the
    # WhenFriendlyUpgradeDefeated observer (Zeb Orrelios ASH_161).  Answers "If a
    # friendly upgrade was defeated this phase" (Baylan Skoll ASH_39).  A Shield /
    # Experience / Advantage token IS an upgrade, so this fills up fast on an ASH
    # board — which is exactly what the card is counting on.  Phase-cleared.
    upgrades_defeated_this_phase: set = field(default_factory=set)  # controller_ids
    # instance_ids of LEADER units defeated this phase, recorded at the same defeat
    # site as ``defeated_traits_this_round``.  Answers "While a leader unit has been
    # defeated this phase" (Captain Pellaeon ASH_93) — either player's leader, which
    # is why this is not keyed by controller.  Phase-cleared.
    leader_units_defeated_this_phase: set = field(default_factory=set)  # instance_ids
    # CONTROLLER-keyed companion of the set above, recorded at the same defeat site:
    # the players who lost a LEADER unit this phase.  "If a friendly leader unit left
    # play this phase, distribute 5 Advantage tokens instead" (Fateful Goodbye
    # ASH_211) needs the side, which the id-keyed set deliberately does not carry.
    # Phase-cleared.
    leader_unit_defeat_controllers_this_phase: set = field(default_factory=set)
    # player_id -> how many NON-UNIT cards (events + upgrades) that player has played
    # this phase, fed at the same CardPlayed chokepoint as the trait ledgers.  A COUNT
    # rather than a trait set, because "the FIRST non-unit card you play each phase"
    # (Peli Motto ASH_212) must also see a traitless one.  Read before the play it
    # would waive is recorded, so the first play sees 0.  Phase-cleared.
    non_units_played_this_phase: dict = field(default_factory=dict)
    # Queue of units that ENTERED PLAY (played, created as a token, or put into play
    # by an ability), each {"player_id", "instance_id"}, fed at the single
    # ``actions._put_unit_in_play`` chokepoint and drained at the action
    # settle-point by ``actions._fire_unit_entry_observers`` — the
    # WhenYouPlayOrCreateUnit observer ("When you play or create a unit" Greef Karga
    # ASH_17 / "When a friendly unit enters play (including this one)" Outcast
    # ASH_41).  The ``WhenUnitHealed`` settle-drain shape.
    unit_entries: list = field(default_factory=list)
    # instance_ids of BASES that actually had damage removed this phase — the base
    # flavour of ``units_healed_this_phase``, and deliberately its own ledger because
    # ``note_unit_healed`` ignores bases (the predicate it feeds asks about units).
    # Written by ``actions.note_base_healed`` at every base-heal site (the shape
    # ``_bases_cannot_heal`` is read at); a heal that removes nothing records nothing.
    # Gates "If a base was healed this phase" (Dooku's Solar Sailer TS26_38).
    bases_healed_this_phase: set = field(default_factory=set)

    def clear_phase(self) -> None:
        self.units_played_this_phase.clear()
        self.free_discard_play_this_phase.clear()
        self.foreign_free_discard_play_this_phase.clear()
        self.foreign_discard_play_this_phase.clear()
        self.discard_play_discount_this_phase.clear()
        self.units_healed_this_phase.clear()
        self.units_damaged_this_phase.clear()
        self.tokens_created_this_phase.clear()
        self.cards_played_this_phase.clear()
        self.traits_played_this_phase.clear()
        self.non_unit_traits_played_this_phase.clear()
        self.villainy_players_this_phase.clear()
        self.base_damage_dealt_this_phase.clear()
        self.first_damage_prevented_this_phase.clear()
        self.cannot_play_events_this_phase.clear()
        self.actions_taken_this_phase.clear()
        self.pending_play_discounts.clear()
        self.pending_exploit_grants.clear()
        self.pending_keyword_grants.clear()
        self.pending_enters_ready.clear()
        self.pending_initiative_effects.clear()
        self.when_played_redo_charges.clear()
        self.bases_cannot_heal_this_phase = False
        self.forbidden_card_names_this_phase.clear()
        self.prevent_next_base_damage.clear()
        self.forced_attack = None
        self.cards_discarded_this_phase.clear()
        self.cards_drawn_this_phase.clear()
        self.phase_aura_sources.clear()
        self.indirect_dealers_this_phase.clear()
        self.cannot_attack_bases_this_phase.clear()
        self.unit_play_tax_this_phase.clear()
        self.bases_damaged_this_phase.clear()
        self.upgrades_defeated_this_phase.clear()
        self.leader_units_defeated_this_phase.clear()
        self.leader_unit_defeat_controllers_this_phase.clear()
        self.non_units_played_this_phase.clear()
        self.bases_healed_this_phase.clear()

    def clear_round(self) -> None:
        self.defeated_aspects_this_round.clear()
        self.defeated_traits_this_round.clear()
        self.units_defeated_this_round.clear()
        self.units_attacked_this_round.clear()
        self.token_unit_attackers_this_round.clear()
        self.units_dealt_base_damage_this_round.clear()
        self.base_attackers_this_round.clear()
        self.attackers_defeated_this_round.clear()
        self.defeated_controllers_this_round.clear()
        self.events_played_this_round.clear()
        self.activated_abilities_used_this_round.clear()
        self.standing_play_discounts_used_this_round.clear()
        self.bounty_recollect_used_this_round.clear()
        self.when_defeated_redo_used_this_round.clear()

    def to_dict(self) -> dict:
        return {
            "units_played_this_phase": sorted(self.units_played_this_phase),
            "free_discard_play_this_phase": sorted(self.free_discard_play_this_phase),
            "foreign_free_discard_play_this_phase": {
                k: sorted(v)
                for k, v in self.foreign_free_discard_play_this_phase.items()},
            "foreign_discard_play_this_phase": {
                k: sorted(v)
                for k, v in self.foreign_discard_play_this_phase.items()},
            "discard_play_discount_this_phase": {
                k: int(v) for k, v in self.discard_play_discount_this_phase.items()},
            "units_healed_this_phase": sorted(self.units_healed_this_phase),
            "units_damaged_this_phase": sorted(self.units_damaged_this_phase),
            "tokens_created_this_phase": sorted(self.tokens_created_this_phase),
            "cards_played_this_phase": {k: int(v) for k, v in self.cards_played_this_phase.items()},
            "traits_played_this_phase": {
                k: sorted(v) for k, v in self.traits_played_this_phase.items()},
            "non_unit_traits_played_this_phase": {
                k: sorted(v) for k, v in self.non_unit_traits_played_this_phase.items()},
            "units_defeated_this_round": sorted(self.units_defeated_this_round),
            "cards_discarded_this_phase": sorted(self.cards_discarded_this_phase),
            "units_attacked_this_round": sorted(self.units_attacked_this_round),
            "units_dealt_base_damage_this_round": sorted(self.units_dealt_base_damage_this_round),
            "token_unit_attackers_this_round": sorted(self.token_unit_attackers_this_round),
            "base_attackers_this_round": {k: list(v) for k, v in self.base_attackers_this_round.items()},
            "attackers_defeated_this_round": sorted(self.attackers_defeated_this_round),
            "defeated_controllers_this_round": list(self.defeated_controllers_this_round),
            "epic_actions_spent": sorted(self.epic_actions_spent),
            "activated_ability_use_counts": {
                k: int(v) for k, v in self.activated_ability_use_counts.items()},
            "activated_abilities_used_this_round": sorted(self.activated_abilities_used_this_round),
            "standing_play_discounts_used_this_round": sorted(self.standing_play_discounts_used_this_round),
            "when_defeated_redo_used_this_round": sorted(self.when_defeated_redo_used_this_round),
            "chosen_keywords": dict(self.chosen_keywords),
            "chosen_arenas": dict(self.chosen_arenas),
            "villainy_players_this_phase": sorted(self.villainy_players_this_phase),
            "base_damage_dealt_this_phase": {k: int(v) for k, v in self.base_damage_dealt_this_phase.items()},
            "first_damage_prevented_this_phase": sorted(self.first_damage_prevented_this_phase),
            "cannot_play_events_this_phase": sorted(self.cannot_play_events_this_phase),
            "actions_taken_this_phase": {k: int(v) for k, v in self.actions_taken_this_phase.items()},
            "win_at_regroup_sole_arena": [dict(e) for e in self.win_at_regroup_sole_arena],
            "rescue_at_regroup": list(self.rescue_at_regroup),
            "defeat_resources_at_regroup": {
                k: int(v) for k, v in self.defeat_resources_at_regroup.items()},
            "events_played_this_round": sorted(self.events_played_this_round),
            "pending_play_discounts": [dict(e) for e in self.pending_play_discounts],
            "pending_exploit_grants": [dict(e) for e in self.pending_exploit_grants],
            "pending_keyword_grants": [dict(e) for e in self.pending_keyword_grants],
            "pending_enters_ready": [dict(e) for e in self.pending_enters_ready],
            "base_damage_events": list(self.base_damage_events),
            "pending_initiative_effects": [
                dict(e) for e in self.pending_initiative_effects],
            "when_played_redo_charges": {k: int(v) for k, v in self.when_played_redo_charges.items()},
            "noncombat_damage_dealers": list(self.noncombat_damage_dealers),
            "action_phase_draws": [dict(e) for e in self.action_phase_draws],
            "force_uses": list(self.force_uses),
            "hand_reveal_discards": list(self.hand_reveal_discards),
            "hand_discards": list(self.hand_discards),
            "heal_events": list(self.heal_events),
            "ready_events": list(self.ready_events),
            "upgrade_defeats": list(self.upgrade_defeats),
            "upgrade_attachments": list(self.upgrade_attachments),
            "token_creations": [dict(e) for e in self.token_creations],
            "unit_play_tax_this_phase": {
                k: int(v) for k, v in self.unit_play_tax_this_phase.items()},
            "bounties_collected": [dict(e) for e in self.bounties_collected],
            "bounty_recollect_used_this_round": sorted(self.bounty_recollect_used_this_round),
            "bases_cannot_heal_this_phase": bool(self.bases_cannot_heal_this_phase),
            "forbidden_card_names_this_phase": sorted(self.forbidden_card_names_this_phase),
            "prevent_next_base_damage": sorted(self.prevent_next_base_damage),
            "forced_attack": (dict(self.forced_attack)
                              if self.forced_attack is not None else None),
            "lose_at_regroup": sorted(self.lose_at_regroup),
            "cards_drawn_this_phase": {k: int(v) for k, v in self.cards_drawn_this_phase.items()},
            "defeated_aspects_this_round": {k: list(v) for k, v in self.defeated_aspects_this_round.items()},
            "defeated_traits_this_round": {k: list(v) for k, v in self.defeated_traits_this_round.items()},
            "flipped_leaders": sorted(self.flipped_leaders),
            "phase_aura_sources": list(self.phase_aura_sources),
            "indirect_dealers_this_phase": sorted(self.indirect_dealers_this_phase),
            "cannot_attack_bases_this_phase": sorted(self.cannot_attack_bases_this_phase),
            "bases_damaged_this_phase": sorted(self.bases_damaged_this_phase),
            "upgrades_defeated_this_phase": sorted(self.upgrades_defeated_this_phase),
            "leader_units_defeated_this_phase": sorted(
                self.leader_units_defeated_this_phase),
            "leader_unit_defeat_controllers_this_phase": sorted(
                self.leader_unit_defeat_controllers_this_phase),
            "non_units_played_this_phase": dict(self.non_units_played_this_phase),
            "unit_entries": list(self.unit_entries),
            "bases_healed_this_phase": sorted(self.bases_healed_this_phase),
        }

    @staticmethod
    def from_dict(d: dict) -> "GameMemory":
        return GameMemory(
            units_played_this_phase=set(d.get("units_played_this_phase", [])),
            free_discard_play_this_phase=set(d.get("free_discard_play_this_phase", [])),
            foreign_free_discard_play_this_phase={
                k: list(v) for k, v in
                d.get("foreign_free_discard_play_this_phase", {}).items()},
            foreign_discard_play_this_phase={
                k: list(v) for k, v in
                d.get("foreign_discard_play_this_phase", {}).items()},
            discard_play_discount_this_phase={
                k: int(v) for k, v in
                d.get("discard_play_discount_this_phase", {}).items()},
            units_healed_this_phase=set(d.get("units_healed_this_phase", [])),
            units_damaged_this_phase=set(d.get("units_damaged_this_phase", [])),
            tokens_created_this_phase=set(d.get("tokens_created_this_phase", [])),
            cards_played_this_phase={k: int(v) for k, v in d.get("cards_played_this_phase", {}).items()},
            traits_played_this_phase={
                k: set(v) for k, v in d.get("traits_played_this_phase", {}).items()},
            non_unit_traits_played_this_phase={
                k: set(v) for k, v in
                d.get("non_unit_traits_played_this_phase", {}).items()},
            units_defeated_this_round=set(d.get("units_defeated_this_round", [])),
            cards_discarded_this_phase=set(d.get("cards_discarded_this_phase", [])),
            units_attacked_this_round=set(d.get("units_attacked_this_round", [])),
            units_dealt_base_damage_this_round=set(d.get("units_dealt_base_damage_this_round", [])),
            token_unit_attackers_this_round=set(
                d.get("token_unit_attackers_this_round", [])),
            base_attackers_this_round={k: list(v) for k, v in d.get("base_attackers_this_round", {}).items()},
            attackers_defeated_this_round=set(d.get("attackers_defeated_this_round", [])),
            defeated_controllers_this_round=list(d.get("defeated_controllers_this_round", [])),
            epic_actions_spent=set(d.get("epic_actions_spent", [])),
            activated_ability_use_counts={
                k: int(v) for k, v in
                (d.get("activated_ability_use_counts") or {}).items()},
            activated_abilities_used_this_round=set(d.get("activated_abilities_used_this_round", [])),
            standing_play_discounts_used_this_round=set(d.get("standing_play_discounts_used_this_round", [])),
            when_defeated_redo_used_this_round=set(d.get("when_defeated_redo_used_this_round", [])),
            chosen_keywords=dict(d.get("chosen_keywords", {})),
            chosen_arenas=dict(d.get("chosen_arenas", {})),
            villainy_players_this_phase=set(d.get("villainy_players_this_phase", [])),
            base_damage_dealt_this_phase={k: int(v) for k, v in d.get("base_damage_dealt_this_phase", {}).items()},
            first_damage_prevented_this_phase=set(d.get("first_damage_prevented_this_phase", [])),
            cannot_play_events_this_phase=set(d.get("cannot_play_events_this_phase", [])),
            actions_taken_this_phase={k: int(v) for k, v in d.get("actions_taken_this_phase", {}).items()},
            win_at_regroup_sole_arena=[dict(e) for e in d.get("win_at_regroup_sole_arena", [])],
            rescue_at_regroup=list(d.get("rescue_at_regroup", [])),
            defeat_resources_at_regroup={
                k: int(v) for k, v in
                d.get("defeat_resources_at_regroup", {}).items()},
            events_played_this_round=set(d.get("events_played_this_round", [])),
            pending_play_discounts=[dict(e) for e in d.get("pending_play_discounts", [])],
            pending_exploit_grants=[dict(e) for e in d.get("pending_exploit_grants", [])],
            pending_keyword_grants=[dict(e) for e in d.get("pending_keyword_grants", [])],
            pending_enters_ready=[dict(e) for e in d.get("pending_enters_ready", [])],
            base_damage_events=list(d.get("base_damage_events", [])),
            pending_initiative_effects=[
                dict(e) for e in d.get("pending_initiative_effects", [])],
            when_played_redo_charges={k: int(v) for k, v in d.get("when_played_redo_charges", {}).items()},
            noncombat_damage_dealers=list(d.get("noncombat_damage_dealers", [])),
            action_phase_draws=[dict(e) for e in d.get("action_phase_draws", [])],
            force_uses=list(d.get("force_uses", [])),
            hand_reveal_discards=list(d.get("hand_reveal_discards", [])),
            hand_discards=list(d.get("hand_discards", [])),
            heal_events=list(d.get("heal_events", [])),
            ready_events=list(d.get("ready_events", [])),
            upgrade_defeats=list(d.get("upgrade_defeats", [])),
            upgrade_attachments=list(d.get("upgrade_attachments", [])),
            token_creations=[dict(e) for e in d.get("token_creations", [])],
            unit_play_tax_this_phase={
                k: int(v) for k, v in (d.get("unit_play_tax_this_phase") or {}).items()},
            bounties_collected=[dict(e) for e in d.get("bounties_collected", [])],
            bounty_recollect_used_this_round=set(d.get("bounty_recollect_used_this_round", [])),
            bases_cannot_heal_this_phase=bool(d.get("bases_cannot_heal_this_phase", False)),
            forbidden_card_names_this_phase=set(d.get("forbidden_card_names_this_phase", [])),
            prevent_next_base_damage=set(d.get("prevent_next_base_damage", [])),
            forced_attack=(dict(d["forced_attack"])
                           if d.get("forced_attack") is not None else None),
            lose_at_regroup=set(d.get("lose_at_regroup", [])),
            cards_drawn_this_phase={k: int(v) for k, v in d.get("cards_drawn_this_phase", {}).items()},
            defeated_aspects_this_round={k: list(v) for k, v in d.get("defeated_aspects_this_round", {}).items()},
            defeated_traits_this_round={k: list(v) for k, v in d.get("defeated_traits_this_round", {}).items()},
            flipped_leaders=set(d.get("flipped_leaders", [])),
            phase_aura_sources=list(d.get("phase_aura_sources", [])),
            indirect_dealers_this_phase=set(d.get("indirect_dealers_this_phase", [])),
            cannot_attack_bases_this_phase=set(
                d.get("cannot_attack_bases_this_phase", [])),
            bases_damaged_this_phase=set(d.get("bases_damaged_this_phase", [])),
            upgrades_defeated_this_phase=set(
                d.get("upgrades_defeated_this_phase", [])),
            leader_units_defeated_this_phase=set(
                d.get("leader_units_defeated_this_phase", [])),
            leader_unit_defeat_controllers_this_phase=set(
                d.get("leader_unit_defeat_controllers_this_phase", [])),
            non_units_played_this_phase={
                k: int(v) for k, v in
                d.get("non_units_played_this_phase", {}).items()},
            unit_entries=list(d.get("unit_entries", [])),
            bases_healed_this_phase=set(d.get("bases_healed_this_phase", [])),
        )


# ── Patch CardBase so deepcopy shares immutable defs ──────────────────────────
# Frozen dataclasses are immutable; copying them wastes memory.
from swu.cards.models import CardBase as _CardBase  # noqa: E402

def _cardbase_deepcopy(self: _CardBase, memo: dict) -> _CardBase:
    return self

_CardBase.__deepcopy__ = _cardbase_deepcopy  # type: ignore[attr-defined]
# ─────────────────────────────────────────────────────────────────────────────


class Phase(Enum):
    SETUP_MULLIGAN = auto()   # both players decide keep/redraw
    SETUP_RESOURCES = auto()  # both players choose 2 starting resources
    ACTION = auto()           # main action phase
    REGROUP = auto()          # regroup: optional resource + ready


class Zone(Enum):
    DECK = auto()
    HAND = auto()
    DISCARD = auto()
    RESOURCES = auto()
    GROUND_ARENA = auto()
    SPACE_ARENA = auto()
    BASE_ZONE = auto()      # undeployed leader + base
    CAPTURE_PILE = auto()
    PLAY_BUFFER = auto()    # card mid-resolution (e.g. Exploit sacrifices in progress)
    CREDITS = auto()        # Credit tokens in the resource area (jabba-the-hutt:07)


@dataclass
class CardInstance:
    """
    A card in play — wrapper around an immutable CardDef with runtime state.

    instance_id is unique within a game session (format: "p{n}_{seq}").
    """
    instance_id: str
    card_def: AnyCard
    owner_id: str
    zone: Zone
    exhausted: bool = False
    damage: int = 0
    face_down: bool = False        # True when in RESOURCES zone
    deployed: bool = False         # leaders only: True when deployed as unit
    epic_action_spent: bool = False  # leaders only: True after deploy action
    attached_upgrades: list["CardInstance"] = field(default_factory=list)
    # Capture: when this card has been captured, the instance_id of the unit that
    # captured it ("placed facedown under him").  The card lives in the capturing
    # player's capture_pile (zone CAPTURE_PILE) with owner_id unchanged, and is
    # returned to its owner's arena when the captor leaves play.  None when not
    # captured.  See actions._apply_capture / _release_captured_cards.
    captured_by: Optional[str] = None
    # Bounties granted to this unit for the current phase by another card's effect
    # (The Client SHD_31: "Choose a unit. For this phase, it gains: 'Bounty — …'").
    # Each entry is a small encoded key understood by
    # ``actions._resolve_granted_bounty`` (e.g. "heal_base:5"); a unit's own
    # printed/upgrade bounty is NOT stored here (those are TriggerAbility/
    # GrantedAbility specs).  Resolved for the collector when this unit is defeated
    # and cleared at the round rollover (the "for this phase" duration).
    granted_bounties: list[str] = field(default_factory=list)
    # Set when a unit is played by an effect that defeats it at the start of the
    # next regroup phase (Sneak Attack SOR_219: "Play a unit … At the start of the
    # regroup phase, defeat it.").  Swept and defeated in actions._enter_regroup.
    defeat_at_regroup: bool = False
    # Set when an effect exhausts a unit and forbids it readying for the rest of the
    # round, including the upcoming regroup phase (No Good to Me Dead SOR_186).  The
    # flag makes _end_regroup skip this unit's ready step (and any ReadyCard effect
    # is a no-op) for the one regroup during which it is set; _end_regroup then
    # clears it, so the unit readies normally at the *next* round's regroup.
    cannot_ready_this_round: bool = False
    # Set when an effect takes temporary control of a unit that must go back to its
    # owner's hand at the start of the next regroup phase (Commandeer JTL_235:
    # "Take control of a … unit. … At the start of the next regroup phase, return
    # that unit to its owner's hand.").  Swept in actions._enter_regroup, mirroring
    # ``defeat_at_regroup``; the return routes through _apply_return_to_hand, which
    # already sends the card to its owner's hand regardless of who controls it.
    return_to_owner_hand_at_regroup: bool = False
    # Set when an effect takes temporary control of a unit whose CONTROL must revert to
    # its owner at the start of the next regroup phase (Change of Heart SOR_224: "Take
    # control of a non-leader unit.  At the start of the regroup phase, its owner takes
    # control of it.").  Swept in actions._enter_regroup alongside
    # ``return_to_owner_hand_at_regroup``; the revert routes through ``change_control``
    # (control is implicit arena occupancy), so the unit simply moves back to its owner's
    # arena rather than to hand.  Cleared by the relocation.
    return_control_to_owner_at_regroup: bool = False
    # Set when an effect puts a unit into play only until the next regroup phase, at
    # whose start it goes on the BOTTOM of its owner's deck (Maz Kanata LAW_74: "…
    # play it.  It costs 4 resources less and enters play ready.  At the start of the
    # regroup phase, put that unit on the bottom of your deck (if it is still in
    # play)").  The deck-bound sibling of ``return_to_owner_hand_at_regroup``: swept
    # in actions._enter_regroup through ``_apply_put_on_deck``, which — as the card's
    # printed rules note requires — is a relocation, NOT a defeat, so no "When
    # Defeated" ability of that unit fires.  "(if it is still in play)" is the
    # per-instance delayed-flag convention: a unit already gone is skipped.
    bottom_at_regroup: bool = False
    # Count of delayed "at the start of the regroup phase, discard a card from your
    # hand" obligations scheduled by this unit's On Attack (Zorii Bliss SHD_203:
    # "On Attack: Draw a card.  At the start of the regroup phase, discard a card
    # from your hand.").  Incremented each attack; swept in actions._enter_regroup
    # (the unit's controller discards this many hand cards, first-card simplification)
    # and reset to 0.  Skipped if the unit has left play by regroup — a per-instance
    # delayed flag, mirroring ``defeat_at_regroup`` / ``return_to_owner_hand_at_regroup``.
    discard_from_hand_at_regroup: int = 0
    # Set on a unit whose control was changed by an effect that must REVERT when its
    # source unit leaves play (Maul LAW_54: "take control of a … unit. When this unit
    # leaves play, that unit's owner takes control of that unit.").  Holds the
    # instance_id of the SOURCE unit (Maul); when that source is defeated,
    # actions._revert_linked_control returns this unit to its owner's control.  Mirrors
    # the ``captured_by`` leave-play linkage.  None when control is not linked.
    control_linked_to: Optional[str] = None
    # Set on an ATTACKER during its own attack when an On Attack effect redirects the
    # combat damage that would be dealt to it onto a chosen unit (Maul SHD_90: "all
    # combat damage that would be dealt to this unit during this attack is dealt to
    # the chosen unit instead").  Holds the chosen unit's instance_id.  Read at the
    # combat-damage step (_apply_attacker_combat_damage) and cleared at the end of the
    # attack — a this_attack scope, mirroring the other transient instance flags.
    combat_damage_redirect_to: Optional[str] = None
    # Set on an ATTACKER during its own attack when it chooses to let the defending
    # unit deal combat damage FIRST (The Stranger LAW_86: "While attacking, you may
    # have the defending unit deal combat damage before this unit").  Read at the
    # unit-combat damage step (_defender_deals_first) and cleared at the end of the
    # attack — a this_attack scope, the mirror of the attacker-first-strike ordering.
    defender_deals_first: bool = False
    # Set on an ATTACKER by its own On Attack ability to mean "defeat this unit after
    # completing this attack" (Defiant Hammerhead LAW_62: "you may give this unit
    # +4/+0 for this attack.  If you do, defeat this unit after completing this
    # attack").  Read once at the end of each combat pipeline
    # (``actions._settle_defeat_after_attack``, called just before the this-attack
    # cleanup) and cleared there — a this_attack scope.  If combat already defeated
    # the attacker the flag dies with the instance, so the rider is a clean no-op.
    defeat_after_attack: bool = False
    # Set on a unit whose next combat-damage instance this attack is to be PREVENTED
    # (Queen Amidala SEC_101: "If damage would be dealt to this unit, you may defeat
    # another friendly unit that shares a trait with this unit.  If you do, prevent
    # that damage.").  Armed by the ``combat_damage_prevention`` decision (which
    # already defeated the sacrificed friendly unit) and read at the single combat
    # sink ``actions._deal_damage_with_shield``: a one-shot early-return that drops
    # the incoming combat damage, then clears itself.  A this_attack scope — also
    # cleared in ``_clear_this_attack_combat_flags`` so an armed-but-unused flag (the
    # damage never landed) does not leak.  Default False → byte-identical for every
    # unit that does not carry the InteractiveDamagePrevention marker.
    prevent_next_combat_damage: bool = False
    # Set on a unit whose abilities are suppressed for this phase (Mind Trick LOF_202:
    # "those units lose all abilities and can't gain abilities for this phase").  Read
    # as a skip/early-return at every ability-read site (actions._abilities_suppressed):
    # has_keyword/keyword_value, _collect_triggers, the constant-stat-bonus scans, the
    # arena UseAbility enumeration, and the arena-wide TraitGrant scan — the read-layer
    # mirror of the trait/keyword query layers.  Because the guards are reads, "can't
    # gain abilities" falls out for free (a read short-circuits before any grant is
    # consulted).  Phase-scoped: cleared at the round rollover (_regroup_rollover),
    # alongside granted_bounties.
    abilities_suppressed: bool = False
    # A card an enemy Galen Erso (P25_31) has NAMED — "Name a card.  While this unit
    # is in play, each non-leader card an opponent owns with that name, including
    # those not in play, loses all abilities."  This field lives on the NAMER (Galen):
    # it holds the named card's NAME.  Its effect is read via ``is_name_suppressed``
    # at the same ability-read guards as ``abilities_suppressed`` — a name-based,
    # PERSISTENT mirror of the phase-scoped per-instance flag.  Because the effect is
    # a scan over in-play namers (not a flag stamped on each victim), persistence
    # falls out for free (the suppression lifts when Galen leaves play) and it matches
    # by NAME, so an opponent-owned copy is suppressed wherever its abilities are read,
    # including one just played from hand ("including those not in play").
    named_card: Optional[str] = None

    def effective_power(self) -> int:
        """Power after applying attached upgrades."""
        base = getattr(self.card_def, "power", 0) or 0
        for u in self.attached_upgrades:
            base += getattr(u.card_def, "upgrade_power", 0) or 0
        return max(0, base)

    def effective_hp(self) -> int:
        """Max HP after applying attached upgrades."""
        base = getattr(self.card_def, "hp", 0) or 0
        for u in self.attached_upgrades:
            base += getattr(u.card_def, "upgrade_hp", 0) or 0
        return max(1, base)

    def is_defeated(self) -> bool:
        return self.damage >= self.effective_hp()

    def arena(self) -> Optional[str]:
        """Return 'Ground' or 'Space' based on card def arenas; None for non-units."""
        arenas = getattr(self.card_def, "arenas", ())
        if arenas:
            return arenas[0]
        return None

    def zone_for_arena(self) -> Zone:
        a = self.arena()
        if a == "Space":
            return Zone.SPACE_ARENA
        return Zone.GROUND_ARENA


@dataclass
class PlayerState:
    player_id: str
    deck: list[CardInstance] = field(default_factory=list)
    hand: list[CardInstance] = field(default_factory=list)
    discard: list[CardInstance] = field(default_factory=list)
    resources: list[CardInstance] = field(default_factory=list)
    ground_arena: list[CardInstance] = field(default_factory=list)
    space_arena: list[CardInstance] = field(default_factory=list)
    base_zone: list[CardInstance] = field(default_factory=list)   # leader (undeployed) + base
    capture_pile: list[CardInstance] = field(default_factory=list)
    # Credit tokens (CreditToken card defs) sitting in this player's resource area.
    # NOT normal resources: they never count toward ``available_resources`` and are
    # never exhausted/readied — a credit is *defeated* (removed) while paying a
    # resource cost to pay 1 less (jabba-the-hutt:07).  Held in their own pile so
    # all the normal resource machinery (exhaust, regroup ready-all, Smuggle, Plot,
    # SacrificeResource, conservation) ignores them; like Shield/Experience tokens
    # they are an unlimited supply not drawn from the deck, so they are excluded
    # from card-conservation counts (``all_instances_for_player``).
    credits: list[CardInstance] = field(default_factory=list)
    # Temporary buffer while a card is mid-play (e.g. Exploit decision in progress)
    play_buffer: list[CardInstance] = field(default_factory=list)
    # Regroup phase: True once this player has made their resource decision
    regroup_done: bool = False
    # The Force token (LOF, qui-gon-jinn:06).  A single per-player boolean — a
    # player has at most one Force token ("The Force is with you").  Set by
    # CreateForceToken ("create your Force token"); cleared by the UseForce cost /
    # the use_force decision ("use the Force (lose your Force token)").  Read by the
    # CONTROLLER_HAS_FORCE_TOKEN condition ("While the Force is with you").  Unlike
    # Credit tokens this is not a card instance — it is a status, so it touches no
    # zone/conservation machinery.
    has_force_token: bool = False

    # ── Derived properties ─────────────────────────────────────────────────

    @property
    def base_instance(self) -> Optional[CardInstance]:
        for ci in self.base_zone:
            if isinstance(ci.card_def, Base):
                return ci
        return None

    @property
    def leader_instance(self) -> Optional[CardInstance]:
        """The leader, whether deployed (in an arena) or not (in base_zone)."""
        for ci in self.base_zone:
            if isinstance(ci.card_def, Leader):
                return ci
        for ci in self.ground_arena + self.space_arena:
            if isinstance(ci.card_def, Leader):
                return ci
        return None

    @property
    def available_resources(self) -> int:
        return sum(1 for r in self.resources if not r.exhausted)

    @property
    def total_resources(self) -> int:
        return len(self.resources)

    @property
    def is_eliminated(self) -> bool:
        b = self.base_instance
        if b is None:
            return False
        # base_instance always holds a Base, but AnyCard is a union and only
        # Base/Unit carry hp — cast rather than isinstance so this stays free.
        return b.damage >= cast(Base, b.card_def).hp

    def all_instances(self) -> list[CardInstance]:
        """All CardInstances owned by this player across all zones."""
        result: list[CardInstance] = []
        for zone_list in (
            self.deck, self.hand, self.discard, self.resources,
            self.ground_arena, self.space_arena, self.base_zone,
            self.capture_pile, self.play_buffer, self.credits,
        ):
            for ci in zone_list:
                result.append(ci)
                result.extend(ci.attached_upgrades)
        return result

    def zone_list(self, zone: Zone) -> list[CardInstance]:
        mapping = {
            Zone.DECK: self.deck,
            Zone.HAND: self.hand,
            Zone.DISCARD: self.discard,
            Zone.RESOURCES: self.resources,
            Zone.GROUND_ARENA: self.ground_arena,
            Zone.SPACE_ARENA: self.space_arena,
            Zone.BASE_ZONE: self.base_zone,
            Zone.CAPTURE_PILE: self.capture_pile,
            Zone.PLAY_BUFFER: self.play_buffer,
            Zone.CREDITS: self.credits,
        }
        return mapping[zone]


@dataclass
class GameState:
    """
    Complete 2-player match state.

    Mutation contract: apply() calls copy.deepcopy(state) before any change.
    The original state passed to apply() is never modified.
    """
    players: list[PlayerState]
    phase: Phase = Phase.SETUP_MULLIGAN
    active_player_index: int = 0
    round_number: int = 1
    # Index into self.players; set by coin flip at game creation.
    initiative_holder: int = 0
    # ACTION phase tracking
    # passed_players: set of player indices who have passed (or claimed initiative)
    # this action phase. Once in this set, that player takes no more actions.
    passed_players: set[int] = field(default_factory=set)
    # Whether initiative was claimed this round (prevents double-claiming)
    initiative_claimed_this_round: bool = False
    # How many regroup phases have STARTED this round.  Normally exactly 1, but a
    # unit carrying the ExtraRegroupPhase marker (Max Rebo LAW_72: "There is an
    # additional regroup phase after the first regroup phase each round") makes the
    # round run 2.  Incremented at the top of _enter_regroup; reset to 0 at the true
    # round rollover (_regroup_rollover).  Serialised, back-compat default 0.
    regroup_count_this_round: int = 0
    # Effects scheduled to fire once at the START of the next action phase, for a
    # card that has already left play (an Event → discard) so there is no in-play
    # host to hang a PhaseStartTrigger on.  Each entry is a small JSON-serialisable
    # dict {"kind": <str>, "controller_id": <str>, ...}; drained by
    # actions._fire_scheduled_action_phase_effects at _regroup_rollover /
    # _start_action_phase.  The Eye of Aldhani SEC_73 seam ("At the start of the
    # next action phase, …").  Serialised, back-compat default [].
    scheduled_action_phase_effects: list[dict] = field(default_factory=list)
    # SETUP tracking
    mulligan_done: list[bool] = field(default_factory=lambda: [False, False])
    resources_chosen: list[int] = field(default_factory=lambda: [0, 0])
    # Serialisable RNG state (tuple from random.Random.getstate())
    rng_state: tuple = field(default_factory=lambda: random.Random().getstate())
    # Sequential counter for generating unique instance IDs
    _next_id: int = field(default=0, repr=False)
    # Sequential counter for generating unique, *deterministic* modifier IDs.
    # Must never use uuid4/os.urandom: a non-seeded id makes to_json() differ
    # between two same-seed runs and breaks the determinism oracle.
    _next_modifier_id: int = field(default=0, repr=False)
    # Append-only event log
    event_log: list = field(default_factory=list)  # list[GameEvent] — typed in events.py
    # Pending decisions — non-empty suspends normal turn alternation.
    # Top of stack is [-1].  legal_actions() serves the top decision's
    # options; apply() pops it when resolved.
    pending_decisions: list[PendingDecision] = field(default_factory=list)
    # Active transient modifiers created by ability effects.
    modifiers: list[Modifier] = field(default_factory=list)
    # Phase/round-scoped memory of events for ability conditions.
    game_memory: GameMemory = field(default_factory=GameMemory)

    # ── Convenience properties ─────────────────────────────────────────────

    @property
    def active_player(self) -> PlayerState:
        return self.players[self.active_player_index]

    @property
    def inactive_player(self) -> PlayerState:
        return self.players[1 - self.active_player_index]

    @property
    def winner(self) -> Optional[str]:
        for p in self.players:
            if p.is_eliminated:
                other = self.players[1 - self.players.index(p)]
                return other.player_id
        return None

    def is_terminal(self) -> bool:
        return self.winner is not None

    # ── RNG helpers ────────────────────────────────────────────────────────

    def make_rng(self) -> random.Random:
        r = random.Random()
        r.setstate(self.rng_state)
        return r

    def alloc_instance_id(self) -> tuple[str, int]:
        """Return (new_id, next_counter). Caller must update _next_id."""
        return f"ci_{self._next_id}", self._next_id + 1

    def alloc_modifier_id(self, prefix: str = "mod") -> str:
        """Return a unique, deterministic modifier id and advance the counter.

        Deterministic by construction (a per-state counter), so two runs of the
        same seed produce identical ids — unlike uuid4, which draws from
        os.urandom and would make the serialised state diverge between runs.
        """
        mid = f"{prefix}_{self._next_modifier_id}"
        self._next_modifier_id += 1
        return mid

    # ── Lookup helpers ─────────────────────────────────────────────────────

    def all_instances_for_player(self, player_id: str) -> list[CardInstance]:
        """All CardInstances owned by player_id, across ALL zones including opponent attachments.

        NOTE: Token instances (Shield, Experience, Clone Trooper, etc.) are excluded
        from this count because they are created on demand (not from the player's
        deck) and cease to exist when they leave play.  This covers both token
        upgrades (TokenUpgrade) and token units (TokenUnit, e.g. Clone Trooper —
        the create-token-unit primitive, ahsoka-tano:05).  Card-conservation checks
        should use this method.
        """
        from swu.cards.models import TokenUpgrade, TokenUnit
        _TOKENS = (TokenUpgrade, TokenUnit)
        result: list[CardInstance] = []
        for ps in self.players:
            for zone_list in (
                ps.deck, ps.hand, ps.discard, ps.resources,
                ps.ground_arena, ps.space_arena, ps.base_zone,
                ps.capture_pile, ps.play_buffer,
            ):
                for ci in zone_list:
                    if ci.owner_id == player_id and not isinstance(ci.card_def, _TOKENS):
                        result.append(ci)
                    for upg in ci.attached_upgrades:
                        if upg.owner_id == player_id and not isinstance(upg.card_def, _TOKENS):
                            result.append(upg)
        return result

    def find_instance(self, instance_id: str) -> Optional[tuple[PlayerState, CardInstance]]:
        """Find a CardInstance by ID across all players and zones."""
        for p in self.players:
            for ci in p.all_instances():
                if ci.instance_id == instance_id:
                    return p, ci
        return None

    def player_by_id(self, player_id: str) -> PlayerState:
        for p in self.players:
            if p.player_id == player_id:
                return p
        raise KeyError(player_id)

    def player_index(self, player_id: str) -> int:
        for i, p in enumerate(self.players):
            if p.player_id == player_id:
                return i
        raise KeyError(player_id)

    # ── Serialisation ──────────────────────────────────────────────────────

    def to_json(self) -> str:
        return json.dumps(_state_to_dict(self), default=str)

    @staticmethod
    def from_json(data: str) -> "GameState":
        return _state_from_dict(json.loads(data))

    def view_for(self, player_id: str) -> "PlayerView":
        from swu.engine.views import build_view
        return build_view(self, player_id)


# ── Name-based ability suppression (Galen Erso P25_31) ────────────────────────

def is_name_suppressed(state: "GameState", ci: "CardInstance") -> bool:
    """True when ``ci`` is a non-leader card whose NAME has been named by an
    in-play enemy Galen Erso (P25_31: "each non-leader card an opponent owns with
    that name … loses all abilities").  Read at the same ability-read guards as the
    per-instance ``abilities_suppressed`` flag, so "loses all abilities" covers
    keywords, triggers, activated, constant and trait-granting abilities alike.

    The check scans in-play namer units (those carrying ``named_card``): a namer U
    controlled by player P suppresses ``ci`` iff ``ci`` is a NON-leader card owned by
    P's opponent whose card name equals U's ``named_card``.  Because it is a scan
    over in-play namers, the effect is PERSISTENT-while-in-play (it lifts when Galen
    leaves) and it matches by NAME, so a copy in any zone — including one just played
    from hand — is suppressed as soon as its abilities are read ("including those not
    in play").  A Leader card is never suppressed ("non-leader card")."""
    cd = getattr(ci, "card_def", None)
    if cd is None or isinstance(cd, Leader):
        return False
    name = getattr(cd, "name", None)
    if not name:
        return False
    owner = ci.owner_id
    for ps in state.players:
        if ps.player_id == owner:
            continue  # a namer controlled by ci's OWNER can't be its opponent's Galen
        for u in (*ps.ground_arena, *ps.space_arena):
            if getattr(u, "named_card", None) == name:
                return True
    return False


def _has_suppressing_upgrade(ci: "CardInstance") -> bool:
    """True when ``ci`` carries an attached upgrade that suppresses its abilities
    (Imprisoned SHD_72 — a ``SuppressHostAbilities`` marker).  Derived purely from
    the upgrade's presence, so the suppression is persistent while attached and lifts
    the instant the upgrade leaves play (no stored flag to clear)."""
    ups = getattr(ci, "attached_upgrades", None)
    if not ups:
        return False
    from swu.abilities.registry import get_abilities, SuppressHostAbilities
    for u in ups:
        cd = getattr(u, "card_def", None)
        if cd is None:
            continue
        sc = getattr(cd, "set_code", "") or ""
        cn = getattr(cd, "card_number", "") or ""
        for spec in get_abilities(sc, cn):
            if isinstance(spec, SuppressHostAbilities):
                return True
    return False


_SUPPRESS_LEADER_KEYS: "frozenset | None" = None


def _suppress_leader_keys() -> frozenset:
    """The (set_code, card_number) keys registering a ``SuppressLeaderAbilities``
    marker.  Built once from the (immutable, import-time) ability registry — the
    hot-path guard for the board scan below."""
    global _SUPPRESS_LEADER_KEYS
    if _SUPPRESS_LEADER_KEYS is None:
        import swu.cards  # noqa: F401 — ensure every registration has landed
        from swu.abilities.registry import _REGISTRY, SuppressLeaderAbilities
        _SUPPRESS_LEADER_KEYS = frozenset(
            key for key, specs in _REGISTRY.items()
            if any(isinstance(spec, SuppressLeaderAbilities) for spec in specs))
    return _SUPPRESS_LEADER_KEYS


def _leader_abilities_suppressed(state: "GameState", ci: "CardInstance") -> bool:
    """True when ``ci`` is a LEADER card and some in-play unit carries a
    ``SuppressLeaderAbilities`` marker (Brain Invaders TWI_255: "Each leader loses
    all abilities except for epic actions and can't gain abilities").

    Board-wide and side-blind — it covers the leader deployed as a unit and the one
    still sitting in ``base_zone`` alike, and both players' (as printed: "Each
    leader", including the marker's own controller's).  Being a scan over in-play
    markers makes it persistent-while-in-play and self-lifting, like the Galen Erso
    name scan.  Not recursive: the marker sources are non-leader units, for which
    this returns False at the first line before their own suppression is read."""
    cd = getattr(ci, "card_def", None)
    if cd is None or not isinstance(cd, Leader):
        return False
    # ``ability_suppressed`` sits on the hot stat/keyword read paths, so the board
    # scan is gated on a one-off registry index of the (set, number) keys that
    # actually carry the marker — a set lookup per in-play unit, no per-unit
    # ability-list walk.
    keys = _suppress_leader_keys()
    if not keys:
        return False
    for ps in state.players:
        for src in (*ps.ground_arena, *ps.space_arena):
            scd = getattr(src, "card_def", None)
            if scd is None or isinstance(scd, Leader):
                continue
            key = (getattr(scd, "set_code", "") or "",
                   getattr(scd, "card_number", "") or "")
            if key not in keys:
                continue
            if ability_suppressed(state, src):
                continue      # the marker's own abilities may themselves be off
            return True
    return False


def ability_suppressed(state: "GameState", ci: "CardInstance") -> bool:
    """Unified ability-suppression read: True when ``ci``'s abilities are suppressed
    by ANY source — Mind Trick LOF_202's phase-scoped per-instance flag
    (``abilities_suppressed``), Galen Erso P25_31's persistent name scan
    (``is_name_suppressed``), an attached ability-suppressing upgrade (Imprisoned
    SHD_72, ``_has_suppressing_upgrade``), or an in-play leader-suppressing unit
    (Brain Invaders TWI_255, ``_leader_abilities_suppressed``).  This is the single
    predicate the ~10 ability-read guards consult, so a new suppression source is
    added in one place."""
    if getattr(ci, "abilities_suppressed", False):
        return True
    # A MODIFIER-backed suppression, so it can carry a duration the per-instance
    # flag cannot — "the defender loses all abilities for this attack" (One Way Out
    # SEC_157) uses ``duration="this_attack"``, swept with every other this-attack
    # modifier.  Same unified read; a new source added in the one place.
    for mod in getattr(state, "modifiers", []):
        if (mod.kind == "abilities_suppressed"
                and mod.target_instance_id == ci.instance_id):
            return True
    if is_name_suppressed(state, ci):
        return True
    if _has_suppressing_upgrade(ci):
        return True
    return _leader_abilities_suppressed(state, ci)


def borrowed_ability_sources(state: "GameState", ci: "CardInstance") -> list:
    """The cards whose abilities ``ci`` has BORROWED right now — the read side of
    the Support keyword's "It gains this unit's other abilities for this attack."

    The borrow is carried by a ``borrowed_abilities`` Modifier landed on the chosen
    attacker at the attack site, so it expires with the ordinary ``this_attack``
    duration sweep and needs no stored flag.  Returns the LENDER instances (the
    Support unit/leader), located with ``find_instance`` so a lender that has since
    left play still lends for the rest of the attack — the grant's duration is the
    attack, not the lender's stay.

    This lives here, beside ``ability_suppressed``, because both the keyword layer
    and the trigger resolver read it and neither may import the other.  A lender
    whose own abilities are suppressed lends nothing."""
    out: list = []
    for mod in getattr(state, "modifiers", []):
        if mod.kind != "borrowed_abilities" or mod.target_instance_id != ci.instance_id:
            continue
        lender_id = (mod.value or {}).get("lender_id") or mod.source_instance_id
        if lender_id is None or lender_id == ci.instance_id:
            continue
        found = state.find_instance(lender_id)
        if found is None:
            continue
        lender = found[1]
        if ability_suppressed(state, lender):
            continue
        if not any(x.instance_id == lender.instance_id for x in out):
            out.append(lender)
    return out


# ── JSON helpers ──────────────────────────────────────────────────────────────

def _instance_to_dict(ci: CardInstance) -> dict:
    return {
        "instance_id": ci.instance_id,
        "card_id": ci.card_def.id,
        "card_name": ci.card_def.display_name,
        "card_type": ci.card_def.type,
        "owner_id": ci.owner_id,
        "zone": ci.zone.name,
        "exhausted": ci.exhausted,
        "damage": ci.damage,
        "face_down": ci.face_down,
        "deployed": ci.deployed,
        "epic_action_spent": ci.epic_action_spent,
        "captured_by": ci.captured_by,
        "granted_bounties": list(ci.granted_bounties),
        "defeat_at_regroup": ci.defeat_at_regroup,
        "cannot_ready_this_round": ci.cannot_ready_this_round,
        "return_to_owner_hand_at_regroup": ci.return_to_owner_hand_at_regroup,
        "return_control_to_owner_at_regroup": ci.return_control_to_owner_at_regroup,
        "bottom_at_regroup": ci.bottom_at_regroup,
        "discard_from_hand_at_regroup": ci.discard_from_hand_at_regroup,
        "combat_damage_redirect_to": ci.combat_damage_redirect_to,
        "defender_deals_first": ci.defender_deals_first,
        "defeat_after_attack": ci.defeat_after_attack,
        "prevent_next_combat_damage": ci.prevent_next_combat_damage,
        "abilities_suppressed": ci.abilities_suppressed,
        "named_card": ci.named_card,
        "control_linked_to": ci.control_linked_to,
        "attached_upgrades": [_instance_to_dict(u) for u in ci.attached_upgrades],
    }


def _player_to_dict(ps: PlayerState) -> dict:
    return {
        "player_id": ps.player_id,
        "deck": [_instance_to_dict(ci) for ci in ps.deck],
        "hand": [_instance_to_dict(ci) for ci in ps.hand],
        "discard": [_instance_to_dict(ci) for ci in ps.discard],
        "resources": [_instance_to_dict(ci) for ci in ps.resources],
        "ground_arena": [_instance_to_dict(ci) for ci in ps.ground_arena],
        "space_arena": [_instance_to_dict(ci) for ci in ps.space_arena],
        "base_zone": [_instance_to_dict(ci) for ci in ps.base_zone],
        "capture_pile": [_instance_to_dict(ci) for ci in ps.capture_pile],
        "play_buffer": [_instance_to_dict(ci) for ci in ps.play_buffer],
        "credits": [_instance_to_dict(ci) for ci in ps.credits],
        "regroup_done": ps.regroup_done,
        "has_force_token": ps.has_force_token,
    }


def _state_to_dict(gs: GameState) -> dict:
    return {
        "players": [_player_to_dict(p) for p in gs.players],
        "phase": gs.phase.name,
        "active_player_index": gs.active_player_index,
        "round_number": gs.round_number,
        "initiative_holder": gs.initiative_holder,
        "passed_players": sorted(gs.passed_players),
        "initiative_claimed_this_round": gs.initiative_claimed_this_round,
        "regroup_count_this_round": gs.regroup_count_this_round,
        "scheduled_action_phase_effects": [dict(e) for e in gs.scheduled_action_phase_effects],
        "mulligan_done": gs.mulligan_done,
        "resources_chosen": gs.resources_chosen,
        "rng_state": list(gs.rng_state),
        "_next_id": gs._next_id,
        "_next_modifier_id": gs._next_modifier_id,
        "event_log": [{"type": type(e).__name__} for e in gs.event_log],
        "pending_decisions": [d.to_dict() for d in gs.pending_decisions],
        "modifiers": [m.to_dict() for m in gs.modifiers],
        "game_memory": gs.game_memory.to_dict(),
    }


def _instance_from_dict(d: dict, repo: object) -> CardInstance:
    card_def = repo.by_id(d["card_id"])  # type: ignore[attr-defined]
    return CardInstance(
        instance_id=d["instance_id"],
        card_def=card_def,
        owner_id=d["owner_id"],
        zone=Zone[d["zone"]],
        exhausted=d["exhausted"],
        damage=d["damage"],
        face_down=d["face_down"],
        deployed=d["deployed"],
        epic_action_spent=d["epic_action_spent"],
        captured_by=d.get("captured_by"),
        granted_bounties=list(d.get("granted_bounties", [])),
        defeat_at_regroup=d.get("defeat_at_regroup", False),
        cannot_ready_this_round=d.get("cannot_ready_this_round", False),
        return_to_owner_hand_at_regroup=d.get("return_to_owner_hand_at_regroup", False),
        return_control_to_owner_at_regroup=d.get("return_control_to_owner_at_regroup", False),
        bottom_at_regroup=d.get("bottom_at_regroup", False),
        discard_from_hand_at_regroup=d.get("discard_from_hand_at_regroup", 0),
        control_linked_to=d.get("control_linked_to"),
        combat_damage_redirect_to=d.get("combat_damage_redirect_to"),
        defender_deals_first=d.get("defender_deals_first", False),
        defeat_after_attack=d.get("defeat_after_attack", False),
        prevent_next_combat_damage=d.get("prevent_next_combat_damage", False),
        abilities_suppressed=d.get("abilities_suppressed", False),
        named_card=d.get("named_card"),
        attached_upgrades=[_instance_from_dict(u, repo) for u in d["attached_upgrades"]],
    )


def _player_from_dict(d: dict, repo: object) -> PlayerState:
    def load(lst):
        return [_instance_from_dict(ci, repo) for ci in lst]
    ps = PlayerState(player_id=d["player_id"])
    ps.deck = load(d["deck"])
    ps.hand = load(d["hand"])
    ps.discard = load(d["discard"])
    ps.resources = load(d["resources"])
    ps.ground_arena = load(d["ground_arena"])
    ps.space_arena = load(d["space_arena"])
    ps.base_zone = load(d["base_zone"])
    ps.capture_pile = load(d["capture_pile"])
    ps.play_buffer = load(d.get("play_buffer", []))
    ps.credits = load(d.get("credits", []))
    ps.regroup_done = d.get("regroup_done", False)
    ps.has_force_token = d.get("has_force_token", False)
    return ps


def _state_from_dict(d: dict) -> "GameState":
    from swu.cards.repository import CardRepository, default_db_path
    repo = CardRepository(default_db_path())
    players = [_player_from_dict(p, repo) for p in d["players"]]
    rng_raw = d["rng_state"]
    # Stored as list; reconstruct tuple as getstate() expects
    rng_state = (rng_raw[0], tuple(rng_raw[1]), rng_raw[2])
    gs = GameState(
        players=players,
        phase=Phase[d["phase"]],
        active_player_index=d["active_player_index"],
        round_number=d["round_number"],
        initiative_holder=d["initiative_holder"],
        passed_players=set(d["passed_players"]),
        initiative_claimed_this_round=d["initiative_claimed_this_round"],
        regroup_count_this_round=d.get("regroup_count_this_round", 0),
        scheduled_action_phase_effects=[
            dict(e) for e in d.get("scheduled_action_phase_effects", [])
        ],
        mulligan_done=d["mulligan_done"],
        resources_chosen=d["resources_chosen"],
        rng_state=rng_state,
        _next_id=d["_next_id"],
        _next_modifier_id=d.get("_next_modifier_id", 0),
        event_log=[],  # log not restored (not needed for replay)
        pending_decisions=[
            PendingDecision.from_dict(dd) for dd in d.get("pending_decisions", [])
        ],
        modifiers=[Modifier.from_dict(m) for m in d.get("modifiers", [])],
        game_memory=GameMemory.from_dict(d.get("game_memory", {})),
    )
    return gs
