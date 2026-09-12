"""
Card ability framework — declarative spec types and registry.

Every card ability is expressed as an AbilitySpec and registered via
@card_ability(set_code, card_number).  The engine reads these specs at
runtime to collect triggers, evaluate constant buffs, and present
activated ability options in legal_actions().

Naming convention for effect primitives:
  ResourceCard (effect) vs. ResourceCard (action in actions.py) — the
  effect lives here; the action is an unrelated class in actions.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from swu.engine.state import GameState, CardInstance

# ── Fixed-target sentinel strings ─────────────────────────────────────────────
SELF = "self"                  # the source card itself
ATTACKER = "attacker"          # the current attacker (from event context)
DEFENDER = "defender"          # the current defender (from event context)
EACH_FRIENDLY = "each_friendly"  # every card that matches rest of spec, friendly
EACH_ENEMY = "each_enemy"        # every card that matches rest of spec, enemy
EACH_IN_PLAY = "each_in_play"    # every card that matches rest of spec, any controller

# ── Duration ──────────────────────────────────────────────────────────────────
class Duration(Enum):
    PERMANENT = "permanent"
    THIS_PHASE = "this_phase"
    THIS_ATTACK = "this_attack"
    THIS_ROUND = "this_round"

# ── Condition atoms ───────────────────────────────────────────────────────────
class Condition(Enum):
    SOURCE_UNDAMAGED = "source_undamaged"
    SOURCE_DAMAGED = "source_damaged"
    SOURCE_EXHAUSTED = "source_exhausted"  # source unit is exhausted — gates a
                                           # "while this unit is exhausted, it
                                           # gains …" ability (Bounty: Unlicensed
                                           # Headhunter SHD_165)
    SOURCE_READY = "source_ready"          # source is NOT exhausted — gates a
                                           # triggered ability whose only effect is
                                           # to pay an exhaust-self cost, so it is
                                           # not offered once the source is already
                                           # exhausted (The Mandalorian SHD_18
                                           # undeployed: "you may exhaust this
                                           # leader" can only be paid once)
    SOURCE_IN_SPACE_ARENA = "source_in_space_arena"  # source unit currently sits in
                                           # its controller's space arena — gates both
                                           # a "while in the space arena, she gains
                                           # [Action]" ability AND the paired
                                           # ReadyRestriction ("can't ready while in
                                           # space"), so ONE atom drives both halves
                                           # (Leia Organa LOF_98)
    CONTROLLER_HAS_INITIATIVE = "controller_has_initiative"
    CONTROLLER_N_PLUS_UNITS = "controller_n_plus_units"  # the controller has ≥N
                                      # units in play (ground + space arenas,
                                      # deployed leaders included) — the keystone
                                      # of the Coordinate keyword: "Gain this
                                      # ability while you control 3 or more units"
                                      # (TWI Republic/Clone units, ahsoka-tano:01).
                                      # The source unit counts itself ("including
                                      # this one"), since it is already in its
                                      # arena whenever the ability is evaluated.
    CONTROLLER_MORE_UNITS_THAN_OPPONENT = "controller_more_units_than_opponent"
                                      # the controller has strictly MORE units in
                                      # play (ground + space arenas) than the
                                      # opponent — "While you control more units
                                      # than an opponent, …" (Corrupt Politician
                                      # SEC_79 conditional Sentinel self-grant)
    OPPONENT_MORE_UNITS_THAN_CONTROLLER = "opponent_more_units_than_controller"
                                      # the mirror: an OPPONENT has strictly more
                                      # units in play than the controller — "If an
                                      # opponent controls more units than you, draw
                                      # a card" (Old Access Codes TWI_168)
    CONTROLLER_N_PLUS_TRAIT_UNITS = "controller_n_plus_trait_units"  # param=(trait,
                                      # N): the controller has ≥N units in play with
                                      # that trait — the trait-narrowed sibling of
                                      # CONTROLLER_N_PLUS_UNITS ("If you control 3 or
                                      # more Official units", Petition the Senate
                                      # TWI_100).  Effective traits (granted included),
                                      # so a TraitGrant counts.
    CONTROLLER_RESOURCES_PLUS_TRAIT_UNITS_MIN = (
        "controller_resources_plus_trait_units_min")  # param=(trait, N): the
                                      # controller's RESOURCE count plus their count
                                      # of units with that trait is ≥N — the one
                                      # printed leader-deploy condition the
                                      # ``_deploy_threshold`` regex cannot express
                                      # ("If the number of resources you control plus
                                      # the number of friendly Mandalorian units is 10
                                      # or more, deploy this leader", Bo-Katan Kryze
                                      # ASH_10).  Effective traits, both arenas.
    OPPONENT_N_PLUS_UNITS = "opponent_n_plus_units"  # an OPPONENT has ≥`param`
                                      # units in play — the enemy-side mirror of
                                      # CONTROLLER_N_PLUS_UNITS, over the same
                                      # both-arenas count basis ("While an opponent
                                      # controls 3 or more units, this unit gains
                                      # Sentinel" — Duchess's Champion TWI_54)
    CONTROLLER_HAS_TRAIT_CARD_IN_PLAY = "controller_has_trait_card_in_play"
                                      # the controller has a card with trait `param`
                                      # in play as an arena UNIT *or* as an attached
                                      # UPGRADE — the upgrade-inclusive sibling of
                                      # CONTROLLER_HAS_TRAIT_UNIT ("While you control
                                      # a Force unit or a Force upgrade, …" — Padawan
                                      # Starfighter TWI_58).  Effective traits on the
                                      # unit side, so a TraitGrant counts.
    CONTROLLER_N_PLUS_RESOURCES = "controller_n_plus_resources"
    CONTROLLER_N_PLUS_READY_RESOURCES = "controller_n_plus_ready_resources"  # ≥N
                                      # *ready* (unexhausted) resources — gates a
                                      # "you may pay N resource(s)" trigger so it is
                                      # not offered when the payment is unaffordable
    OPPONENT_NO_READY_RESOURCES = "opponent_no_ready_resources"  # the opponent of
                                      # the source's controller has NO unexhausted
                                      # resource — "if the defending player controls
                                      # no ready resources" (Rush Clovis TWI_183).
                                      # In two-player the defending player IS that
                                      # opponent, so no attack context is needed.
    OPPONENT_MORE_RESOURCES_THAN_CONTROLLER = "opponent_more_resources_than_controller"
                                      # an opponent controls strictly MORE resources
                                      # (ready + exhausted) than the source's
                                      # controller — "If an opponent controls more
                                      # resources than you" (Cham Syndulla JTL_164).
                                      # The resource-count sibling of
                                      # OPPONENT_MORE_UNITS_THAN_CONTROLLER: a MIRROR,
                                      # not a negation — equal counts satisfy neither.
    CONTROLLER_HAS_TRAIT_UNIT = "controller_has_trait_unit"
    CONTROLLER_HAS_OTHER_TRAIT_UNIT = "controller_has_other_trait_unit"  # excludes
                                      # the source itself ("another X unit")
    CONTROLLER_NO_OTHER_TRAIT_UNIT = "controller_no_other_trait_unit"  # the exact
                                      # negation of the atom above — "If you control
                                      # no other <trait> units" (Crackshot V-Wing
                                      # JTL_158, whose When Played self-damage fires
                                      # only when it is the lone Fighter)
    CONTROLLER_ATTACKED_OTHER_TRAIT_UNIT_THIS_PHASE = \
        "controller_attacked_other_trait_unit_this_phase"  # a friendly unit with
                                      # trait=param (≠ the source) attacked this
                                      # phase (Bo-Katan Kryze SHD_12)
    CONTROLLER_HAS_UNIT_WITH_EXPERIENCE_TOKEN = "controller_has_unit_with_experience_token"
                                      # a friendly arena unit carries ≥1 Experience
                                      # token — gates "you may defeat an Experience
                                      # token on a friendly unit" (Vaneé LOF_82)
    CONTROLLER_HAS_OTHER_ASPECT_UNIT = "controller_has_other_aspect_unit"  # another
                                      # unit with aspect param ("another <Aspect>
                                      # unit"); excludes the source itself
    CONTROLLER_HAS_OTHER_SPACE_UNIT = "controller_has_other_space_unit"  # another
                                      # unit in the controller's space arena
                                      # ("another space unit"); excludes the source
                                      # itself (Death Space Skirmisher JTL_217)
    SOURCE_UPGRADED = "source_upgraded"  # source unit has ≥1 upgrade attached
                                         # ("while this unit is upgraded")
    SOURCE_REMAINING_HP_MIN = "source_remaining_hp_min"  # param=N — the source's
                                         # *remaining* HP (effective HP − damage) is
                                         # ≥ N ("If this unit has 3 or more remaining
                                         # HP" — Doctor Pershing ASH_72).  The
                                         # source-side sibling of the per-candidate
                                         # ``remaining_hp_le_<N>`` predicate.
    CONTROLLER_N_PLUS_EXHAUSTED_UNITS = "controller_n_plus_exhausted_units"  # param=N
                                         # — the source's controller has ≥ N exhausted
                                         # units across BOTH arenas (Tatooine Repulsor
                                         # Train ASH_35).  The controller-scoped
                                         # sibling of N_PLUS_EXHAUSTED_UNITS_IN_PLAY,
                                         # which counts every player's.
    CONTROLLER_HAS_UPGRADE = "controller_has_upgrade"  # the source's controller has
                                         # ≥1 non-token upgrade attached to some unit
                                         # in play, whoever controls the HOST ("Action
                                         # [… defeat a friendly upgrade]" — Vane
                                         # ASH_12; the payability gate for a cost
                                         # expressed as a leading targeted DefeatUnit).
    CONTROLLER_DISCARD_TRAIT_UNIT_HAS_KEYWORD = "controller_discard_trait_unit_has_keyword"
                                         # param=(trait, keyword) — some UNIT card in
                                         # the controller's discard pile carries
                                         # ``trait`` and prints ``keyword`` ("This unit
                                         # gains <K> if it is on an Imperial unit in
                                         # your discard pile" — Moff Gideon ASH_8).
                                         # PRINTED keywords/traits: a card in a discard
                                         # pile is out of reach of the grant layers.
    ENEMY_UNIT_UPGRADED = "enemy_unit_upgraded"  # an enemy arena unit has ≥1
                                         # attached upgrade ("while an enemy unit is
                                         # upgraded" — Sugi SHD_52)
    ENEMY_CONTROLS_BOUNTY_UNIT = "enemy_controls_bounty_unit"  # an enemy unit
                                         # currently carries a Bounty ("if an enemy
                                         # unit has a Bounty" — Krrsantan SHD_139)
    VILLAINY_PLAYED_THIS_PHASE = "villainy_played_this_phase"
    CONTROLLER_PLAYED_OTHER_CARD_THIS_PHASE = "controller_played_other_card_this_phase"
    # "If you played ANOTHER card this phase" — the controller's per-phase play
    # counter (game_memory.cards_played_this_phase) is ≥2, i.e. at least one card
    # besides the source itself (the counter is incremented before WhenPlayed
    # trigger collection, so the source's own play is already counted).  Lothal
    # Insurgent SOR_190.
    CONTROLLER_HAS_OTHER_TRAIT_CARD_IN_PLAY = "controller_has_other_trait_card_in_play"
    # "While you control ANOTHER <param> card (unit, upgrade, or leader), …" — the
    # self-excluding sibling of CONTROLLER_HAS_TRAIT_CARD_IN_PLAY, widened to the
    # controller's base_zone so an UNDEPLOYED leader counts as a card in play (which
    # is what "or leader" means on Raddus JTL_104).  Excluding the source is the
    # whole point: Raddus is himself Resistance.
    CONTROLLER_PLAYED_TRAIT_CARD_THIS_PHASE = "controller_played_trait_card_this_phase"
    # "If you played a <param> card this phase" — the TRAIT-typed sibling of
    # CONTROLLER_PLAYED_OTHER_CARD_THIS_PHASE, over the per-phase trait ledger
    # game_memory.traits_played_this_phase (fed at the same CardPlayed chokepoint).
    # Any card type counts (unit, event or upgrade), which is what "card" means.
    # Captain Phasma JTL_10.
    CONTROLLER_PLAYED_NON_UNIT_TRAIT_CARD_THIS_PHASE = \
        "controller_played_non_unit_trait_card_this_phase"
    # "If you played a NON-UNIT <param> card this phase" (Rey LOF_12) — the
    # card-type-narrowed sibling of CONTROLLER_PLAYED_TRAIT_CARD_THIS_PHASE, over
    # game_memory.non_unit_traits_played_this_phase (the same CardPlayed chokepoint
    # records into both, the non-unit dict only when the played card is not a Unit).
    CONTROLLER_DEALT_N_BASE_DAMAGE_THIS_PHASE = "controller_dealt_n_base_damage_this_phase"
    # the controller has dealt ≥ param combat damage to an enemy base this phase
    # (Cassian Andor SOR_13); backed by game_memory.base_damage_dealt_this_phase.
    ATTACHED_HOST_HAS_TRAIT = "attached_host_has_trait"  # source is an upgrade
                                                 # whose HOST carries param among
                                                 # its effective traits ("If attached
                                                 # unit is a Transport" — Special
                                                 # Modifications SEC_227); the trait
                                                 # sibling of ATTACHED_HOST_NAMED
    ATTACHED_HOST_NAMED = "attached_host_named"  # source is an upgrade whose
                                                 # host unit's name contains param
    CONTROLLER_CONTROLS_NAMED = "controller_controls_named"  # the controller has
                                      # a card whose name contains param in play —
                                      # the leader (deployed or undeployed in
                                      # base_zone), a unit in an arena, OR an
                                      # attached upgrade (a pilot / leader-as-
                                      # upgrade).  "If you control Moff Gideon as a
                                      # leader or unit" (Gideon's Light Cruiser
                                      # SHD_242); "if you control Boba Fett (as a
                                      # unit, upgrade, or leader)" (Fett's Firespray
                                      # JTL_240)
    CONTROLLER_CAN_PLAY_DISCOUNTED_UNIT = "controller_can_play_discounted_unit"
                                      # the controller holds ≥1 hand unit that is
                                      # affordable after a discount of `param`
                                      # resources — gates a "play a unit from your
                                      # hand, it costs N less" action so it is not
                                      # offered when it would change nothing
                                      # (Han Solo SHD_13)
    CONTROLLER_CAN_PLAY_UNIT_FROM_HAND = "controller_can_play_unit_from_hand"
                                      # the controller holds ≥1 affordable unit in
                                      # hand matching trait `param` (None = any
                                      # trait) — gates a "play a unit from your
                                      # hand as an ability" action whose only other
                                      # effect is a downside, so it is never
                                      # offered when no unit could be played
                                      # (Admiral Ozzel SOR_129: activating with no
                                      # playable Imperial unit only readies the
                                      # opponent's units — pure self-harm)
    CONTROLLER_CAN_PLAY_UPGRADE_FROM_RESOURCES = (
        "controller_can_play_upgrade_from_resources")  # param=(host_controller,
                                      # host_predicates): the controller's RESOURCE
                                      # row holds ≥1 affordable Upgrade with a legal
                                      # host matching that filter, so the Exhaust of
                                      # "Play an upgrade from your resources on a unit
                                      # that entered play this phase" is never spent
                                      # on a play that cannot happen (The Armorer
                                      # ASH_1)
    CONTROLLER_CAN_PLAY_EVENT_FROM_HAND = "controller_can_play_event_from_hand"
                                      # the controller holds ≥1 event in hand
                                      # affordable at `param` resources off (the
                                      # event sibling of the unit gate; Bib Fortuna
                                      # SOR_177's exhaust action is never offered
                                      # with no playable event)
    CONTROLLER_CAN_PLAY_UNIT_FROM_HAND_COST_MAX = "controller_can_play_unit_from_hand_cost_max"
                                      # the controller holds ≥1 affordable unit in
                                      # hand whose printed cost is ≤ `param` — gates
                                      # a once-per-game Epic Action that plays such
                                      # a unit (Energy Conversion Lab SOR_22) so the
                                      # epic is not wasted when nothing is playable
    CONTROLLER_HAS_UNIT_IN_HAND = "controller_has_unit_in_hand"
                                      # the controller holds ≥1 Unit card in hand —
                                      # gates an ability whose cost is "discard a unit
                                      # from your hand" so it is not offered (and a
                                      # once-per-game Epic Action not wasted) when the
                                      # cost cannot be paid (Great Pit of Carkoon
                                      # LAW_23)
    CONTROLLER_CAN_PLAY_UNIT_FROM_HAND_IGNORE_ASPECT_PENALTY = \
        "controller_can_play_unit_from_hand_ignore_aspect_penalty"
                                      # the controller holds ≥1 hand unit affordable
                                      # when one Vigilance/Command/Aggression/Cunning
                                      # aspect penalty is ignored — gates a
                                      # once-per-game Epic Action that plays such a
                                      # unit (Daimyo's Palace LAW_20) so the epic is
                                      # not wasted when nothing is playable
    CONTROLLER_HAS_READY_UNIT_COST_MAX = "controller_has_ready_unit_cost_max"
                                      # the controller has ≥1 ready (unexhausted)
                                      # unit in an arena whose printed cost is ≤
                                      # `param` — gates a "you may attack with a unit
                                      # that costs N or less" activated ability (Moff
                                      # Gideon SHD_7 undeployed) so it is not offered
                                      # (and its Exhaust cost not wasted) when no such
                                      # unit can attack.  A ready unit always has ≥1
                                      # legal attack (the enemy base at minimum), so
                                      # this is both necessary and sufficient for the
                                      # granted attack to actually do something
    CONTROLLER_BASE_DAMAGE_MIN = "controller_base_damage_min"  # the controller's
                                      # base has ≥`param` damage on it — gates a
                                      # "while your base has N or more damage, …"
                                      # constant (Anakin's Interceptor TWI_142)
    ANY_BASE_DAMAGE_MIN = "any_base_damage_min"  # SOME base in play (either
                                      # player's) has ≥`param` damage on it — "If a
                                      # base has 15 or more damage on it, …"
                                      # (Guerilla Attack Pod SOR_148)
    CONTROLLER_BASE_MORE_DAMAGED_THAN_ENEMY = "controller_base_more_damaged"
                                      # the controller's base carries STRICTLY more
                                      # damage than SOME enemy base — "If your base
                                      # has more damage on it than an enemy base, …"
                                      # (Millennium Falcon IBH_31).  A comparison,
                                      # not a threshold, so it is the COMPARATIVE
                                      # sibling of CONTROLLER_BASE_DAMAGE_MIN; strict,
                                      # so an equal count does NOT satisfy it (the
                                      # OPPONENT_MORE_RESOURCES_THAN_CONTROLLER
                                      # mirror-not-negation convention)
    CONTROLLER_HAS_FORCE_TOKEN = "controller_has_force_token"  # the controller has
                                      # a Force token ("While the Force is with
                                      # you, …" — Jedi Sentinel LOF_196; also gates
                                      # the "you may use the Force" riders so they
                                      # are not offered with no token to spend)
    CONTROLLER_HAS_NON_LEADER_UNIT = "controller_has_non_leader_unit"  # the
                                      # controller has ≥1 non-leader unit in an
                                      # arena — gates Qui-Gon Jinn LOF_16's
                                      # "Return a friendly non-leader unit …"
                                      # Action so its Force-token cost is not
                                      # wasted when there is nothing to return
    ANY_PLAYER_HAS_CREDIT = "any_player_has_credit"  # SOME player holds ≥1 Credit
                                      # token — "You may defeat a Credit token
                                      # (belonging to any player)" (Taramyn Barcona
                                      # LAW_40).  Credits live in PlayerState.credits,
                                      # not an arena, so no target predicate can see
                                      # them; this gates the optional trigger so it is
                                      # never offered with no credit to defeat.
    OPPONENT_HAS_CREDIT = "opponent_has_credit"  # an OPPONENT of the source's
                                      # controller holds ≥1 Credit token — "You may
                                      # defeat an ENEMY Credit token" (Defiant
                                      # Scrapper LAW_106), the narrowed sibling of
                                      # ANY_PLAYER_HAS_CREDIT.
    CONTROLLER_HAS_TOKEN_UNIT = "controller_has_token_unit"  # the controller has ≥1
                                      # TOKEN unit (X-Wing / TIE Fighter / Battle
                                      # Droid …) in an arena — "While you control a
                                      # token unit, this unit gains Raid 1" (First
                                      # Order TIE Fighter JTL_81); the condition
                                      # sibling of the ``token_unit`` target predicate
    CONTROLLER_HAS_GROUND_AND_SPACE_UNIT = "controller_has_ground_and_space_unit"
                                      # the controller has ≥1 unit in EACH arena —
                                      # "While you control a ground unit and a space
                                      # unit, attached unit gains Sentinel" (Jarek
                                      # Yeager JTL_109).  One atom for the whole
                                      # clause rather than an ALL_OF of two
                                      # arena atoms that nothing else would use
    CONTROLLER_HAS_UNIT_IN_ARENA = "controller_has_unit_in_arena"
                                      # param="ground"|"space" — the controller has
                                      # ≥1 unit in that arena ("If you control a
                                      # ground unit", Getaway Freighter LAW_155); the
                                      # single-arena sibling of
                                      # CONTROLLER_HAS_GROUND_AND_SPACE_UNIT
    OPPONENT_MORE_SPACE_UNITS_THAN_CONTROLLER = "opponent_more_space_units_than_controller"
                                      # an opponent has strictly MORE space-arena
                                      # units than the source's controller ("If an
                                      # opponent controls more space units than you,
                                      # ready this unit" — Special Forces TIE Fighter
                                      # JTL_135); the arena-scoped sibling of
                                      # OPPONENT_MORE_UNITS_THAN_CONTROLLER
    CONTROLLER_DEALT_INDIRECT_DAMAGE_THIS_PHASE = "controller_dealt_indirect_damage_this_phase"
                                      # the source's controller is in
                                      # ``game_memory.indirect_dealers_this_phase``
                                      # ("If you dealt indirect damage this phase,
                                      # this unit costs 1 resource less to play" —
                                      # Decimator of Dissidents JTL_138).  Evaluated
                                      # from HAND at the play-cost site, so it reads
                                      # only the memory ledger, never the board
    CONTROLLER_HAS_CARD_IN_HAND = "controller_has_card_in_hand"  # the controller
                                      # holds ≥1 card in hand — gates a trigger whose
                                      # "you may discard a card from your hand. If
                                      # you do, …" cost cannot be paid with an empty
                                      # hand (Merrin LOF_160) so it is not offered
    SOURCE_HAS_TRAIT = "source_has_trait"  # the source unit has the trait `param`
                                      # (effective traits, via the trait query
                                      # layer) — gates a granted ability that only
                                      # applies "if attached unit is a <Trait> unit"
                                      # (Fallen Lightsaber SOR_137: the granted On
                                      # Attack applies only while the host is a Force
                                      # unit; the granted ability resolves from the
                                      # host, so the source IS the host here)
    SOURCE_NAMED = "source_named"     # the source card's name CONTAINS `param` — the
                                      # name sibling of SOURCE_HAS_TRAIT /
                                      # SOURCE_HAS_ASPECT, and the one that works for
                                      # an UPGRADE's SELF ConstantAbility, whose
                                      # condition the keyword layer evaluates against
                                      # the HOST: "If attached unit is Luke Skywalker,
                                      # he gains Sentinel" (Luke's Jedi Lightsaber
                                      # ASH_66).  ``ATTACHED_HOST_NAMED`` is NOT usable
                                      # there — it expects the UPGRADE as its source
                                      # and looks the host up from it.
    SOURCE_HAS_ASPECT = "source_has_aspect"  # the source unit carries the printed
                                      # aspect `param` — gates a granted ability
                                      # that applies "if attached unit is a
                                      # <Aspect> unit" (Constructed Lightsaber
                                      # LOF_261: Heroism→Restore 2, Villainy→Raid 2;
                                      # the granted ability resolves from the host,
                                      # so the source IS the host here)
    SOURCE_LACKS_ASPECTS = "source_lacks_aspects"  # the source unit carries NONE of
                                      # the printed aspects in `param` (a
                                      # comma-separated string) — "if attached unit
                                      # is a non-Heroism, non-Villainy unit …"
                                      # (Constructed Lightsaber LOF_261 → Sentinel)
    ENEMY_HAS_DAMAGED_UNIT = "enemy_has_damaged_unit"  # the source's opponent has
                                      # ≥1 damaged unit in an arena — gates a
                                      # conditional self-buff ("While an enemy unit
                                      # is damaged, this unit gets +3/+0" — IG-88
                                      # JTL_141)
    SOURCE_POWER_MIN = "source_power_min"  # the source unit's *effective* power is
                                      # ≥ `param` — gates an "If this unit has N or
                                      # more power, …" optional trigger so it is not
                                      # offered below the threshold (Quinlan Vos
                                      # LOF_163: "If this unit has 6 or more power,
                                      # you may deal 2 to an enemy base")
    ANOTHER_PLAYER_N_PLUS_EXHAUSTED_UNITS = "another_player_n_plus_exhausted_units"
                                      # some player OTHER than the source's
                                      # controller has ≥ `param` exhausted units
                                      # across both arenas — "If another player
                                      # controls 3 or more exhausted units, …"
                                      # (Blade Squadron B-Wing JTL_199); with two
                                      # players that is the single opponent
    SOURCE_POWER_MAX = "source_power_max"  # the source unit's *effective* power is
                                      # ≤ `param` — the CEILING mirror of
                                      # SOURCE_POWER_MIN, sharing its reentrancy
                                      # guard ("This unit doesn't ready during the
                                      # regroup phase unless its power is 4 or more"
                                      # = ReadyRestriction(SOURCE_POWER_MAX, 3),
                                      # Rampart JTL_182)
    SOURCE_CHOSEN_KEYWORD = "source_chosen_keyword"  # the source instance's
                                      # recorded "Choose a keyword" pick
                                      # (``game_memory.chosen_keywords``) equals
                                      # `param` — gates one of the parallel
                                      # ConstantAbility grants a "When Played:
                                      # Choose Grit, Restore 1, Sentinel, or
                                      # Shielded. While this unit is in play, each
                                      # friendly Vehicle unit gains the chosen
                                      # keyword" card registers (Admiral Yularen
                                      # JTL_47).  False until a choice is recorded,
                                      # so the card grants nothing before then.
    NO_INITIATIVE_CLAIMED_THIS_PHASE = "no_initiative_claimed_this_phase"
                                      # no player has taken the initiative this
                                      # round/phase (``state.initiative_claimed_this_
                                      # round``, reset at the round rollover) — "If no
                                      # player has taken the initiative this phase, …"
                                      # (Face Off JTL_178).  Initiative can be claimed
                                      # only during ACTION and the flag resets at the
                                      # rollover, so this-round ≡ this-phase.
    ENEMY_CONTROLS_NO_GROUND_UNITS = "enemy_controls_no_ground_units"  # the
                                      # source's opponent has zero units in the
                                      # ground arena — gates an EntersPlayReady
                                      # ("If an opponent controls no ground units,
                                      # this unit enters play ready" — Corellian
                                      # Hounds SEC_170)
    CONTROLLER_HAS_EVENT_IN_HAND = "controller_has_event_in_hand"  # the source's
                                      # controller holds ≥1 Event card in hand —
                                      # gates a trigger whose text says "reveal an
                                      # event from your hand" (ISB Agent SOR_176)
    CONTROLLER_HAS_ASPECT_CARD_IN_DISCARD = "controller_has_aspect_card_in_discard"
                                      # the source controller's discard pile holds
                                      # ≥1 card carrying the aspect `param` — gates
                                      # "If there is a <Aspect> card in your discard
                                      # pile, …" (Anakin Skywalker LOF_70)
    CONTROLLER_HAS_TRAIT_LEADER_UNIT = "controller_has_trait_leader_unit"  # the
                                      # controller has a deployed leader *unit* (a
                                      # Leader in an arena) carrying the trait
                                      # `param` — gates "If you control a <Trait>
                                      # leader unit, …" (Darth Malak LOF_234)
    CONTROLLER_DISCARD_DISTINCT_COSTS_MIN = "controller_discard_distinct_costs_min"
                                      # the source controller's discard pile holds
                                      # cards spanning ≥ `param` *distinct* printed
                                      # costs — gates the conditional buff "While
                                      # there are N or more different costs among
                                      # cards in your discard pile, …" (Doctor Aphra
                                      # SHD_15).  Reuses the same distinct-cost count
                                      # as Fennec Shand SHD_220's DealDamageEqualTo.
    ENEMY_N_PLUS_SPACE_UNITS = "enemy_n_plus_space_units"  # the source's opponent
                                      # controls ≥ `param` units in the space arena
                                      # — gates a conditional own-cost reduction
                                      # ("If an opponent controls 3 or more space
                                      # units, this unit costs 3 less" — Home One
                                      # JTL_204)
    CONTROLLER_HAS_EXHAUSTED_UNDEPLOYED_LEADER = \
        "controller_has_exhausted_undeployed_leader"  # the controller's leader is
                                      # in base_zone (undeployed — a "non-unit
                                      # leader") AND exhausted — gates a "you may
                                      # ready a non-unit leader" trigger so it is
                                      # offered only when there is one to ready
                                      # (Darth Traya SEC_188)
    CONTROLLER_FRIENDLY_ATTACKER_DEFEATED_THIS_PHASE = \
        "controller_friendly_attacker_defeated_this_phase"  # a unit the controller
                                      # controlled was defeated *while attacking*
                                      # this phase (game_memory.attackers_defeated_
                                      # this_round holds the controllers) — gates
                                      # "If a friendly unit was defeated while
                                      # attacking this phase, …" (Oppression Breeds
                                      # Rebellion SEC_158)
    CONTROLLER_HAS_ASPECT_LEADER_OR_BASE = \
        "controller_has_aspect_leader_or_base"  # the controller's leader (deployed
                                      # or undeployed) OR base carries the aspect
                                      # `param` — gates "If you control a <Aspect>
                                      # leader or base, …" (Rey LOF_148)
    # param=<Trait>: the controller has a LEADER card with that trait, deployed or
    # still in the base zone ("While you control a Force leader" — Elzar Mann ASH_224).
    CONTROLLER_HAS_TRAIT_LEADER = "controller_has_trait_leader"
    CONTROLLER_HAS_LEADER_UNIT = "controller_has_leader_unit"  # the controller has a
                                      # deployed leader *unit* (a Leader in an arena),
                                      # any trait — gates "If you control a leader
                                      # unit, …" (Jedha Agitator SOR_158)
    ENEMY_UNIT_DEFEATED_THIS_PHASE = "enemy_unit_defeated_this_phase"  # an enemy of
                                      # the source's controller lost a unit this phase
                                      # (game_memory.defeated_controllers_this_round
                                      # holds the controller-at-death of every defeat
                                      # this round == phase) — gates Iden Versio
                                      # SOR_2's undeployed "If an enemy unit was
                                      # defeated this phase, heal 1 from your base"
    SELF_DISCARDED_THIS_PHASE = "self_discarded_this_phase"  # this very card
                                      # instance was discarded from a hand or deck this
                                      # phase (game_memory.cards_discarded_this_phase) —
                                      # gates Kylo's TIE Silencer SHD_135's play-from-
                                      # discard Action.  Evaluated against the discard-
                                      # pile instance itself, not a board unit.
    CONTROLLER_DISCARDED_THIS_PHASE = "controller_discarded_this_phase"
                                      # the SOURCE's controller discarded ≥1 card from
                                      # their hand or deck this phase — "If you
                                      # discarded a card from your hand or deck this
                                      # phase" (Vult Skerris's Defender LAW_76).  The
                                      # per-player reading of the same
                                      # ``game_memory.cards_discarded_this_phase``
                                      # ledger SELF_DISCARDED_THIS_PHASE uses: the
                                      # discarded cards sit in their owner's discard
                                      # pile, so ownership is read back off the
                                      # instance — no new state.
    SOURCE_BOUNTY_RECOLLECT_AVAILABLE = "source_bounty_recollect_available"
                                      # the source has NOT yet used its once-per-round
                                      # "when you collect a bounty, collect it again"
                                      # this round — gates Bossk SHD_10's deployed
                                      # WhenBountyCollected trigger so the "you may"
                                      # is offered at most once per round
    N_PLUS_EXHAUSTED_UNITS_IN_PLAY = "n_plus_exhausted_units_in_play"
                                      # ≥`param` EXHAUSTED units across BOTH players'
                                      # arenas — "If there are 4 or more exhausted
                                      # units in play" (Sly Moore SEC_14).  The
                                      # both-sides sibling of
                                      # ANOTHER_PLAYER_N_PLUS_EXHAUSTED_UNITS (which
                                      # counts one opponent's only).
    CONTROLLER_MORE_CARDS_IN_HAND_THAN_OPPONENT = \
        "controller_more_cards_in_hand_than_opponent"
                                      # the controller holds strictly MORE cards than
                                      # an opponent — "While you have more cards in
                                      # hand than an opponent, this unit gains Raid 2"
                                      # (Dedra Meero SEC_10 deployed).  The hand-size
                                      # sibling of CONTROLLER_MORE_UNITS_THAN_OPPONENT;
                                      # a MIRROR, not a negation (equal counts fail).
    OPPONENT_MORE_CARDS_IN_HAND_THAN_CONTROLLER = \
        "opponent_more_cards_in_hand_than_controller"
                                      # the exact MIRROR of the atom above — "If you
                                      # have FEWER cards in hand than an opponent, draw
                                      # a card" (Broken Horn LAW_83).  Equal hand sizes
                                      # satisfy neither, which is right: level is not
                                      # fewer.  The hand-size twin of
                                      # OPPONENT_MORE_RESOURCES_THAN_CONTROLLER.
    SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE = "source_once_per_round_trigger_available"
                                      # the source has NOT yet used its once-per-round
                                      # TRIGGERED ability this round — gates a "Use this
                                      # ability only once each round" trigger (Toro
                                      # Calican SHD_239).  The used-marker
                                      # (f"{instance_id}:trig" in
                                      # activated_abilities_used_this_round) is set by
                                      # the ability's CustomEffect when it resolves,
                                      # mirroring the Bossk recollect pattern.
    CONTROLLER_CAN_SMUGGLE = "controller_can_smuggle"
    CONTROLLER_CAN_PILOT = "controller_can_pilot"
                                      # the controller has ≥1 resource-zone card
                                      # playable via Smuggle, affordable at `param`
                                      # resources off — gates Lando SHD_17's "Play a
                                      # card using Smuggle" action so the ability is
                                      # not offered (its Exhaust / once-per-round not
                                      # wasted) when nothing can be smuggled
    CONTROLLER_HAS_REVEAL_RAMP_RESOURCE = "controller_has_reveal_ramp_resource"
                                      # the controller controls ≥1 resource whose name
                                      # matches a friendly unique unit — gates Hunter
                                      # SHD_9's undeployed "reveal a resource … return
                                      # it and ramp" Action so its 1-resource+Exhaust
                                      # cost is never spent when no reveal could match
    ALL_OF = "all_of"                 # composite: every ConditionCheck in ``param``
                                      # (a tuple) holds.  The engine's condition
                                      # fields take exactly ONE ConditionCheck, so a
                                      # card whose clause is a conjunction ("If you
                                      # played a Villainy card this phase" AND "this
                                      # leader is on its front side" — Chancellor
                                      # Palpatine TWI_17) wraps its parts here.
                                      # Evaluated recursively inside ConditionCheck,
                                      # so every existing condition site gets it free.
    ANY_OF = "any_of"                 # composite: at least ONE ConditionCheck in
                                      # ``param`` (a tuple) holds — the DISJUNCTION
                                      # sibling of ALL_OF, for a clause that is an
                                      # OR ("If you played a Bounty Hunter **or**
                                      # Pilot card this phase" — Mist Hunter
                                      # JTL_186).  Registering one ability per
                                      # disjunct would fire twice when both hold.
    NOT_OF = "not_of"                 # composite: the single ConditionCheck in
                                      # ``param`` does NOT hold — the NEGATION
                                      # sibling of ALL_OF / ANY_OF, evaluated in the
                                      # same recursive branch.  Needed whenever a
                                      # card's two clauses are complementary and must
                                      # not both be offered ("You may defeat a
                                      # non-unique upgrade.  If you control a
                                      # Vigilance or Command unit, you may defeat an
                                      # upgrade INSTEAD" — Sabine Wren LAW_78).
                                      # Empty param ⇒ vacuously true.
    CONTROLLER_HAS_ASPECT_UNIT = "controller_has_aspect_unit"
                                      # the controller has ≥1 arena unit carrying the
                                      # ``param`` aspect — the SOURCE-INCLUSIVE
                                      # sibling of CONTROLLER_HAS_OTHER_ASPECT_UNIT
                                      # ("If you control a Vigilance or Command unit"
                                      # — Sabine Wren LAW_78, who counts herself).
    CONTROLLER_HAS_HAND_CARD_COST_MIN = "controller_has_hand_card_cost_min"
                                      # the controller holds ≥1 hand card whose
                                      # PRINTED cost is ≥ ``param`` — gates Admiral
                                      # Trench JTL_14's "Discard a card that costs 3
                                      # or more from your hand.  If you do, draw a
                                      # card" so its Exhaust is never spent on a
                                      # guaranteed no-op
    CONTROLLER_HAS_UNIQUE_TRAIT_CARD_IN_PLAY = \
        "controller_has_unique_trait_card_in_play"
                                      # the controller controls a UNIQUE card with
                                      # ``param``'s trait — the uniqueness-narrowed
                                      # sibling of CONTROLLER_HAS_TRAIT_CARD_IN_PLAY,
                                      # over the same basis (base_zone, both arenas,
                                      # every attached upgrade): "If you control a
                                      # unique Separatist card, this unit costs 1
                                      # resource less to play" (Invincible JTL_191)
    CONTROLLER_HAND_SIZE_MIN = "controller_hand_size_min"  # the controller holds
                                      # ``param`` or more cards in hand — "While you
                                      # have 3 or more cards in your hand, this unit
                                      # gains Saboteur" (Pre Vizsla TWI_10, whose two
                                      # deployed clauses differ only in the threshold)
    CONTROLLER_HAND_SIZE_MAX = "controller_hand_size_max"  # the controller holds
                                      # ``param`` or fewer cards in hand — the mirror
                                      # of the MIN atom.  param=0 is "If you have no
                                      # cards in your hand" (Mister Bones TWI_154)
    ANY_UNIT_DEFEATED_THIS_PHASE = "any_unit_defeated_this_phase"  # ANY unit, either
                                      # controller's, was defeated this phase
                                      # (game_memory.defeated_controllers_this_round is
                                      # non-empty) — the controller-blind sibling of
                                      # ENEMY_UNIT_DEFEATED_THIS_PHASE.  Gates "If a unit
                                      # left play this phase, …" (Yoda TWI_4); being
                                      # defeated is the ledgered way a unit leaves play
                                      # (a bounce/capture is not recorded), a documented
                                      # simplification
    CONTROLLER_UNIT_DEFEATED_THIS_PHASE = "controller_unit_defeated_this_phase"
                                      # a unit the SOURCE'S CONTROLLER controlled was
                                      # defeated this phase — the friendly mirror of
                                      # ENEMY_UNIT_DEFEATED_THIS_PHASE over the same
                                      # defeated_controllers_this_round ledger ("If a
                                      # friendly unit was defeated this phase" — Wat
                                      # Tambor TWI_6, both sides)
    CONTROLLER_N_UNITS_DEFEATED_THIS_PHASE = "controller_n_units_defeated_this_phase"
                                      # param=N: at least N units the source's
                                      # controller controlled were defeated this phase.
                                      # The COUNTING sibling of
                                      # CONTROLLER_UNIT_DEFEATED_THIS_PHASE (which is
                                      # this atom at N=1) — the ledger holds one entry
                                      # per defeat, so the count is just how many of
                                      # them name the controller ("If 2 or more friendly
                                      # units were defeated this phase" — Nute Gunray
                                      # TWI_2)
    CONTROLLER_HAS_DAMAGED_UNIT = "controller_has_damaged_unit"  # the source's
                                      # controller has ≥1 damaged unit in an arena —
                                      # the friendly mirror of ENEMY_HAS_DAMAGED_UNIT
                                      # ("If you control a damaged unit" — Trade
                                      # Federation Shuttle TWI_60)
    CONTROLLER_HAS_EXHAUSTED_UNIT = "controller_has_exhausted_unit"  # the source's
                                      # controller has >=1 EXHAUSTED unit in an arena
                                      # ("If you control an exhausted unit" — C-3PO
                                      # SEC_15); the exhausted sibling of
                                      # CONTROLLER_HAS_DAMAGED_UNIT.  The source
                                      # counts itself.
    CONTROLLER_HAS_OTHER_EXHAUSTED_UNIT = "controller_has_other_exhausted_unit"
                                      # ...and its self-EXCLUDING sibling ("If you
                                      # control ANOTHER exhausted unit" — C-3PO
                                      # SEC_15 deployed, who is exhausted by his own
                                      # attack when the trigger reads).
    CONTROLLER_ATTACKED_THIS_PHASE = "controller_attacked_this_phase"  # SOME unit the
                                      # controller owns attacked this phase — the
                                      # trait-blind, source-inclusive sibling of
                                      # CONTROLLER_ATTACKED_OTHER_TRAIT_UNIT_THIS_PHASE.
                                      # Resolves each id in units_attacked_this_round
                                      # through find_instance (which reaches the
                                      # discard), so an attacker that has since died
                                      # still counts ("If a friendly unit attacked this
                                      # phase" — Captain Rex TWI_7)
    CONTROLLER_ATTACKED_NON_TOKEN_TRAIT_UNIT_THIS_PHASE = \
        "controller_attacked_non_token_trait_unit_this_phase"  # a NON-TOKEN friendly
                                      # unit with the trait ``param`` attacked this
                                      # phase ("If you attacked with a non-token
                                      # Vehicle unit this phase" — Darth Vader JTL_6,
                                      # whose payoff is a TIE Fighter *token*, so the
                                      # non-token filter is what stops the loop).
                                      # Like CONTROLLER_ATTACKED_THIS_PHASE it resolves
                                      # each id in units_attacked_this_round through
                                      # find_instance (an attacker that has since died
                                      # still counts), unlike the in-play scan the
                                      # OTHER_TRAIT sibling uses.
    CONTROLLER_ATTACKED_TOKEN_UNIT_THIS_PHASE = \
        "controller_attacked_token_unit_this_phase"  # the controller declared an attack
                                      # with a TOKEN unit this phase ("While you've
                                      # attacked with a token unit this phase, this unit
                                      # gets +2/+0" — Asajj Ventress TS26_7 deployed).
                                      # Reads its OWN ledger
                                      # game_memory.token_unit_attackers_this_round
                                      # rather than filtering units_attacked_this_round:
                                      # a defeated token ceases to exist (it is never
                                      # discarded), so the find_instance re-read its
                                      # siblings rely on would lose exactly the tokens
                                      # this card is about.
    ANY_BASE_HEALED_THIS_PHASE = "any_base_healed_this_phase"  # ≥1 base actually had
                                      # damage removed this phase, EITHER player's
                                      # (game_memory.bases_healed_this_phase, fed by
                                      # actions.note_base_healed at every base-heal
                                      # site) — "If a base was healed this phase"
                                      # (Dooku's Solar Sailer TS26_38), which draws no
                                      # side distinction.
    CONTROLLER_DISCARD_SIZE_MIN = "controller_discard_size_min"  # the controller's
                                      # discard pile holds ≥ ``param`` cards — "If there
                                      # are 5 or more cards in your discard pile, heal 3
                                      # damage from your base" (Twilight TS26_41).  The
                                      # plain-count sibling of
                                      # CONTROLLER_DISCARD_DISTINCT_COSTS_MIN.
    CONTROLLER_PLAYED_EVENT_THIS_PHASE = "controller_played_event_this_phase"
                                      # the controller has played ≥1 EVENT this phase
                                      # (game_memory.events_played_this_round, fed at
                                      # the single _resolve_event_ability chokepoint) —
                                      # the event-typed sibling of
                                      # VILLAINY_PLAYED_THIS_PHASE (Asajj Ventress
                                      # TWI_14, both sides)
    CONTROLLER_ASPECT_UNIT_DEFEATED_THIS_PHASE = \
        "controller_aspect_unit_defeated_this_phase"  # a unit carrying the ``param``
                                      # aspect was defeated this phase while under the
                                      # source controller's control
                                      # (game_memory.defeated_aspects_this_round) — "If
                                      # a friendly Heroism unit was defeated this
                                      # phase" (Chancellor Palpatine TWI_17)
    CONTROLLER_TRAIT_UNIT_DEFEATED_THIS_PHASE = \
        "controller_trait_unit_defeated_this_phase"  # the TRAIT sibling of the atom
                                      # above, over game_memory.defeated_traits_this_
                                      # round — "If a friendly Rebel unit was defeated
                                      # this phase" (Jyn Erso LAW_5, both sides)
    CONTROLLER_HAS_CREDIT = "controller_has_credit"  # the SOURCE CONTROLLER holds ≥1
                                      # Credit token — the controller-narrowed sibling
                                      # of ANY_PLAYER_HAS_CREDIT / OPPONENT_HAS_CREDIT,
                                      # for "You may defeat a FRIENDLY Credit token"
                                      # (Lando Calrissian LAW_18)
    CONTROLLER_HAS_TOKEN = "controller_has_token"  # the SOURCE CONTROLLER controls ≥1
                                      # TOKEN of any kind — a token UNIT in either
                                      # arena or a token UPGRADE (Shield/Experience)
                                      # attached to one of their units.  The
                                      # card-type-blind widening of
                                      # CONTROLLER_HAS_TOKEN_UNIT, and exactly the
                                      # pool ``actions._cull_pool(pool="tokens")``
                                      # offers — so it gates an ability whose COST is
                                      # "defeat a friendly token" (Alliance Outpost
                                      # LAW_19, whose Epic Action must not be spent
                                      # on an unpayable cost)
    CONTROLLER_CREATED_TOKEN_THIS_PHASE = "controller_created_token_this_phase"
                                      # the SOURCE CONTROLLER created ≥1 token this
                                      # phase (game_memory.tokens_created_this_phase,
                                      # fed at the three creation chokepoints) — "If
                                      # you created a token this phase" (The Client
                                      # LAW_16).  Also available as the same-named
                                      # target PREDICATE, which is what LAW_16 uses:
                                      # his Action is offered even when it was not
                                      # met (his printed rules note), so the gate must
                                      # live on the EFFECT's candidate set, not on
                                      # the ability's availability
    SOURCE_LEADER_FLIPPED = "source_leader_flipped"        # the source leader is
                                      # showing its SECOND side
                                      # (game_memory.flipped_leaders)
    SOURCE_LEADER_NOT_FLIPPED = "source_leader_not_flipped"  # …its FIRST side.  The
                                      # pair gates the two sides of a double-sided
                                      # LEADER that flips instead of deploying
                                      # (Chancellor Palpatine TWI_17); both sides are
                                      # undeployed_only Actions, so `deployed` can't
                                      # distinguish them.
    SOURCE_ATTACHED_TRAIT_UPGRADES_MIN = "source_attached_trait_upgrades_min"
                                      # the source unit has ``param`` == (trait, N)
                                      # or more attached upgrades carrying that trait
                                      # — "If this unit has 4 or more Lightsaber
                                      # upgrades attached to him" (General Grievous
                                      # TWI_34)
    SOURCE_ATTACHED_UPGRADES_MIN = "source_attached_upgrades_min"
                                      # the trait-BLIND sibling: the source unit has
                                      # ``param`` or more attached upgrades of any
                                      # kind (Shield/Experience tokens count, as they
                                      # do everywhere "upgrades on it" is counted) —
                                      # "While attached unit has 4 or more upgrades
                                      # on it, it gains the Jedi trait" (Jedi Trials
                                      # LOF_52, whose grant resolves against the HOST)
    CONTROLLER_HAS_NON_UNIQUE_UNIT = "controller_has_non_unique_unit"
                                      # the source's controller has ≥1 arena unit
                                      # WITHOUT the <uq> symbol — "If you control a
                                      # non-unique unit, this unit enters play ready"
                                      # (Rose Tico LAW_223).  The ``non_unique``
                                      # target predicate as a board gate; a token
                                      # unit is non-unique and counts, as it does
                                      # for that predicate.
    CONTROLLER_HAS_OTHER_NON_UNIQUE_UNIT = "controller_has_other_non_unique_unit"
                                      # the SELF-EXCLUDING sibling of the atom above —
                                      # "While you control ANOTHER non-<uq> unit, this
                                      # unit gains Ambush" (AT-ST Raider ASH_98), which
                                      # is itself non-unique and would otherwise always
                                      # satisfy its own clause.
    CONTROLLER_LEADER_UNIT_DEFEATED_THIS_PHASE = \
        "controller_leader_unit_defeated_this_phase"
                                      # the source's controller lost a LEADER UNIT
                                      # this phase — "If a friendly leader unit left
                                      # play this phase, distribute 5 Advantage
                                      # tokens instead" (Fateful Goodbye ASH_211).
                                      # The CONTROLLER-keyed sibling of
                                      # ANY_LEADER_UNIT_DEFEATED_THIS_PHASE, over the
                                      # ledger written at the same defeat site.
                                      # Being defeated is the ledgered way to leave
                                      # play (the Yoda TWI_4 simplification).
    CONTROLLER_NO_NON_UNIT_PLAYED_THIS_PHASE = \
        "controller_no_non_unit_played_this_phase"
                                      # the source's controller has played NO event
                                      # or upgrade this phase — how "the FIRST
                                      # non-unit card you play each phase" (Peli
                                      # Motto ASH_212) is expressed without a spend
                                      # ledger: the waiver is simply live until one
                                      # has been played.  Over the phase-scoped
                                      # ``non_units_played_this_phase`` count, which
                                      # is written AFTER the cost is paid, so the
                                      # first play still sees zero.
    CONTROLLER_HAS_UNIQUE_UNIT = "controller_has_unique_unit"
                                      # the source's controller has ≥1 arena unit
                                      # PRINTING the <uq> symbol — "If you control a
                                      # <uq> unit, create a Mandalorian token"
                                      # (Protectorate Fighter ASH_124).  The exact
                                      # mirror of CONTROLLER_HAS_NON_UNIQUE_UNIT, and
                                      # the trait-blind, units-only narrowing of
                                      # CONTROLLER_HAS_UNIQUE_TRAIT_CARD_IN_PLAY
                                      # (which also counts upgrades and an undeployed
                                      # leader).  The source itself counts, which is
                                      # what "you control" says.
    CONTROLLER_BASE_ATTACKED_THIS_PHASE = "controller_base_attacked_this_phase"
                                      # an enemy unit DECLARED an attack on the
                                      # source controller's base this phase — "If
                                      # your base was attacked this phase, create a
                                      # Mandalorian token" (Greef Karga ASH_119).
                                      # Reads the ``base_attackers_this_round`` ledger
                                      # (Ephant Mon SHD_88's), which is keyed by base
                                      # OWNER and recorded at the DECLARE step, so it
                                      # counts "attacked" and not "dealt damage" —
                                      # exactly what the card asks.  Round-scoped ≡
                                      # this-phase (attacks happen only in ACTION).
    ENEMY_BASE_DAMAGED_THIS_PHASE = "enemy_base_damaged_this_phase"
                                      # a base belonging to an OPPONENT of the source's
                                      # controller took damage this phase, from any
                                      # source — "If an enemy base was damaged this
                                      # phase" (Baylan Skoll ASH_39), over the
                                      # phase-scoped ``bases_damaged_this_phase``
                                      # ledger fed at the single ``record_base_damage``
                                      # chokepoint.
    CONTROLLER_UPGRADE_DEFEATED_THIS_PHASE = "controller_upgrade_defeated_this_phase"
                                      # the source's controller had an UPGRADE defeated
                                      # this phase — "If a friendly upgrade was defeated
                                      # this phase" (Baylan Skoll ASH_39), over the
                                      # phase-scoped ``upgrades_defeated_this_phase``
                                      # ledger fed at ``note_upgrade_defeated``.  A
                                      # Shield / Experience / Advantage token IS an
                                      # upgrade and counts.
    ANY_LEADER_UNIT_DEFEATED_THIS_PHASE = "any_leader_unit_defeated_this_phase"
                                      # a LEADER unit — either player's — was defeated
                                      # this phase (Captain Pellaeon ASH_93).
    SOURCE_SOLE_FRIENDLY_NON_LEADER_UNIT_IN_ARENA = (
        "source_sole_friendly_non_leader_unit_in_arena")
                                      # the source is the ONLY non-leader unit its
                                      # controller has in its own arena — "While this is
                                      # the only friendly non-leader ground unit, she
                                      # gains Sentinel" (Shin Hati ASH_49).  The
                                      # condition sibling of the
                                      # ``sole_friendly_non_leader_unit_in_arena``
                                      # candidate predicate (Baylan Skoll ASH_3).
    NO_OTHER_UNIT_ATTACKED_THIS_PHASE = "no_other_unit_attacked_this_phase"
                                      # at most ONE unit — the one whose attack is
                                      # being resolved — has attacked this phase, by
                                      # EITHER player: "If no other units have
                                      # attacked this phase (including enemy units)"
                                      # (Boonta Eve Flagbearer LAW_112, Anakin
                                      # Skywalker LAW_88), whose printed rules note
                                      # glosses it "no player has made an attack with
                                      # a unit this phase".  Read off
                                      # ``units_attacked_this_round``, which the two
                                      # combat pipelines stamp at the DECLARE step —
                                      # before the OnAttack fire and long before the
                                      # attack-ends one, so both readings see exactly
                                      # the current attacker in it.  The ledger is
                                      # round-scoped, but an attack can only be made
                                      # in the ACTION phase and there is one per
                                      # round, so this-round IS this-phase (the
                                      # CONTROLLER_ATTACKED_THIS_PHASE precedent).
    CONTROLLER_HAS_UNIT_POWER_MIN = "controller_has_unit_power_min"
                                      # the source's controller has ≥1 arena unit
                                      # whose *effective* power is ≥ ``param`` —
                                      # "While you control a unit with 4 or more
                                      # power, this unit gains Sentinel" (Praetorian
                                      # Guard LOF_85).  Shares SOURCE_POWER_MIN's
                                      # reentrancy guard: compute_power re-enters
                                      # every ConstantAbility condition, and the
                                      # keyword this gates never contributes power.
    CONTROLLER_HAS_UNIT_REMAINING_HP_MIN = "controller_has_unit_remaining_hp_min"
                                      # the source's controller has ≥1 arena unit
                                      # whose REMAINING HP (effective HP less damage)
                                      # is ≥ ``param`` — "If you control a unit with
                                      # 4 or more remaining HP" (Vergence Temple
                                      # LOF_19).
    SOURCE_ABILITY_USES_MAX = "source_ability_uses_max"
                                      # this source card's activated abilities have
                                      # been used FEWER than ``param`` times this
                                      # GAME — "Use this ability no more than 3 times
                                      # each game" (Mystic Monastery LOF_22).  The
                                      # ledger is keyed by the source card, not by
                                      # ability index, which is exact for every card
                                      # with a single limited ability.
    ENEMY_HAS_TRAIT_UNIT = "enemy_has_trait_unit"
                                      # an OPPONENT of the source's controller has an
                                      # arena unit with the trait ``param`` — "While
                                      # an opponent controls a Force unit, this unit
                                      # gains Ambush" (Terentatek LOF_118).  The
                                      # across-the-table mirror of
                                      # CONTROLLER_HAS_TRAIT_UNIT.
    CONTROLLER_HAS_OTHER_UNIT_WITH_KEYWORD = "controller_has_other_unit_with_keyword"
                                      # ANOTHER friendly arena unit has the keyword
                                      # ``param`` from any source (printed, modifier
                                      # or grant) — "This unit gains Ambush while
                                      # another friendly unit has Ambush" (Oppo
                                      # Rancisis LOF_105).  Read through the
                                      # effective keyword layer, so it has its own
                                      # reentrancy guard (_KEYWORD_SCAN_EVALUATING):
                                      # two such units would otherwise ask each other
                                      # forever.


# Instance ids whose SOURCE_POWER_MIN condition is mid-evaluation.  See the
# reentrancy note in ``ConditionCheck.evaluate``; empty except inside one nested
# ``compute_power`` call, and the engine is single-threaded.
_POWER_MIN_EVALUATING: set = set()

# ``(source instance_id, keyword)`` pairs whose
# CONTROLLER_HAS_OTHER_UNIT_WITH_KEYWORD condition is mid-evaluation.  The scan
# reads the *effective* keyword layer, which re-enters this very condition for
# every other conditional grant on the board — two Oppo Rancisis LOF_105 would ask
# each other about the same keyword forever.  Re-entry reports False, which is
# right: a unit can never be its own "another friendly unit".
_KEYWORD_SCAN_EVALUATING: set = set()


@dataclass(frozen=True)
class ConditionCheck:
    condition: Condition
    param: Any = None

    def evaluate(self, state: "GameState", source_ci: "CardInstance") -> bool:
        ps = state.player_by_id(source_ci.owner_id)
        c = self.condition
        if c == Condition.ALL_OF:
            # Conjunction of sub-checks, evaluated against the same source.  Empty
            # param ⇒ vacuously true (no clause can fail).
            return all(sub.evaluate(state, source_ci) for sub in (self.param or ()))
        if c == Condition.ANY_OF:
            # Disjunction of sub-checks against the same source.  Empty param ⇒
            # vacuously false (no clause can hold) — the mirror of ALL_OF.
            return any(sub.evaluate(state, source_ci) for sub in (self.param or ()))
        if c == Condition.NOT_OF:
            # Negation of a single sub-check against the same source.  Empty param ⇒
            # vacuously true (nothing to deny) — the mirror of ALL_OF's empty case.
            return not (self.param.evaluate(state, source_ci) if self.param else False)
        if c == Condition.CONTROLLER_HAS_ASPECT_UNIT:
            aspect = self.param or ""
            for arena in (ps.ground_arena, ps.space_arena):
                for ci in arena:
                    names = {a.name for a in (getattr(ci.card_def, "aspects", None) or ())}
                    if aspect in names:
                        return True
            return False
        if c == Condition.CONTROLLER_HAS_HAND_CARD_COST_MIN:
            floor = int(self.param or 0)
            return any(int(getattr(ci.card_def, "cost", None) or 0) >= floor
                       for ci in ps.hand)
        if c == Condition.CONTROLLER_HAS_UNIQUE_TRAIT_CARD_IN_PLAY:
            # "a unique <trait> card" — CONTROLLER_HAS_TRAIT_CARD_IN_PLAY's basis
            # (both arenas, every attached upgrade, plus base_zone so an undeployed
            # leader counts) narrowed to cards printing the <uq> symbol.
            from swu.engine.traits import has_trait
            trait = self.param or ""
            for zone in (ps.ground_arena, ps.space_arena, ps.base_zone):
                for ci in zone:
                    if (getattr(ci.card_def, "is_unique", False)
                            and has_trait(state, ci, trait)):
                        return True
                    for up in getattr(ci, "attached_upgrades", None) or ():
                        if (getattr(up.card_def, "is_unique", False)
                                and trait in (getattr(up.card_def, "traits", None)
                                              or ())):
                            return True
            return False
        if c == Condition.CONTROLLER_LEADER_UNIT_DEFEATED_THIS_PHASE:
            gm = getattr(state, "game_memory", None)
            return ps.player_id in (
                getattr(gm, "leader_unit_defeat_controllers_this_phase", None)
                or set())
        if c == Condition.CONTROLLER_NO_NON_UNIT_PLAYED_THIS_PHASE:
            gm = getattr(state, "game_memory", None)
            counts = getattr(gm, "non_units_played_this_phase", None) or {}
            return int(counts.get(ps.player_id, 0)) == 0
        if c == Condition.CONTROLLER_HAS_UNIQUE_UNIT:
            return any(getattr(ci.card_def, "is_unique", False)
                       for ci in ps.ground_arena + ps.space_arena)
        if c == Condition.CONTROLLER_BASE_ATTACKED_THIS_PHASE:
            gm = getattr(state, "game_memory", None)
            ledger = getattr(gm, "base_attackers_this_round", None) or {}
            return bool(ledger.get(ps.player_id))
        if c == Condition.CONTROLLER_HAND_SIZE_MIN:
            return len(ps.hand) >= (self.param or 0)
        if c == Condition.CONTROLLER_HAND_SIZE_MAX:
            return len(ps.hand) <= (self.param or 0)
        if c == Condition.CONTROLLER_ASPECT_UNIT_DEFEATED_THIS_PHASE:
            gm = getattr(state, "game_memory", None)
            by_controller = getattr(gm, "defeated_aspects_this_round", None) or {}
            return self.param in (by_controller.get(source_ci.owner_id) or ())
        if c == Condition.CONTROLLER_TRAIT_UNIT_DEFEATED_THIS_PHASE:
            gm = getattr(state, "game_memory", None)
            by_controller = getattr(gm, "defeated_traits_this_round", None) or {}
            return self.param in (by_controller.get(source_ci.owner_id) or ())
        if c in (Condition.SOURCE_LEADER_FLIPPED, Condition.SOURCE_LEADER_NOT_FLIPPED):
            gm = getattr(state, "game_memory", None)
            flipped = source_ci.instance_id in (
                getattr(gm, "flipped_leaders", None) or set())
            return flipped if c == Condition.SOURCE_LEADER_FLIPPED else not flipped
        if c == Condition.CONTROLLER_HAS_NON_UNIQUE_UNIT:
            return any(not getattr(u.card_def, "is_unique", False)
                       for arena in (ps.ground_arena, ps.space_arena) for u in arena)
        if c == Condition.CONTROLLER_HAS_OTHER_NON_UNIQUE_UNIT:
            # AT-ST Raider ASH_98 — "ANOTHER non-unique unit"; the source itself is
            # non-unique, so the self-exclusion IS the clause.
            return any(not getattr(u.card_def, "is_unique", False)
                       and u.instance_id != source_ci.instance_id
                       for arena in (ps.ground_arena, ps.space_arena) for u in arena)
        if c == Condition.ENEMY_BASE_DAMAGED_THIS_PHASE:
            gm = getattr(state, "game_memory", None)
            damaged = getattr(gm, "bases_damaged_this_phase", None) or set()
            return any(p.player_id != ps.player_id and p.player_id in damaged
                       for p in state.players)
        if c == Condition.CONTROLLER_UPGRADE_DEFEATED_THIS_PHASE:
            gm = getattr(state, "game_memory", None)
            return ps.player_id in (
                getattr(gm, "upgrades_defeated_this_phase", None) or set())
        if c == Condition.ANY_LEADER_UNIT_DEFEATED_THIS_PHASE:
            gm = getattr(state, "game_memory", None)
            return bool(getattr(gm, "leader_units_defeated_this_phase", None) or set())
        if c == Condition.SOURCE_SOLE_FRIENDLY_NON_LEADER_UNIT_IN_ARENA:
            # Shin Hati ASH_49.  The condition sibling of the
            # ``sole_friendly_non_leader_unit_in_arena`` predicate: the source is the
            # only non-leader unit its controller has in the source's own arena.  A
            # deployed leader standing beside her does not break the clause.
            from swu.abilities.resolver import _is_leader_unit
            from swu.engine.state import Zone
            if source_ci.zone == Zone.GROUND_ARENA:
                arena = ps.ground_arena
            elif source_ci.zone == Zone.SPACE_ARENA:
                arena = ps.space_arena
            else:
                return False
            return not any(u.instance_id != source_ci.instance_id
                           and not _is_leader_unit(u) for u in arena)
        if c == Condition.NO_OTHER_UNIT_ATTACKED_THIS_PHASE:
            gm = getattr(state, "game_memory", None)
            return len(getattr(gm, "units_attacked_this_round", None) or ()) <= 1
        if c == Condition.SOURCE_ATTACHED_UPGRADES_MIN:
            n = len(getattr(source_ci, "attached_upgrades", None) or ())
            return n >= (self.param or 0)
        if c == Condition.CONTROLLER_HAS_UNIT_POWER_MIN:
            # Praetorian Guard LOF_85.  Reentrancy: this is read from the keyword
            # layer, and compute_power re-enters that layer for every candidate —
            # so reuse SOURCE_POWER_MIN's guard, keyed on the SOURCE (the unit whose
            # conditional grant is being evaluated).  Re-entry reports False, which
            # is right: the keyword it gates (Sentinel) contributes no power.
            iid = getattr(source_ci, "instance_id", None)
            if iid is not None and iid in _POWER_MIN_EVALUATING:
                return False
            from swu.engine.actions import compute_power
            need = self.param or 0
            if iid is not None:
                _POWER_MIN_EVALUATING.add(iid)
            try:
                for arena in (ps.ground_arena, ps.space_arena):
                    for ci in arena:
                        if compute_power(state, ci) >= need:
                            return True
                return False
            finally:
                _POWER_MIN_EVALUATING.discard(iid)
        if c == Condition.CONTROLLER_HAS_OTHER_UNIT_WITH_KEYWORD:
            # Oppo Rancisis LOF_105.  "Another friendly unit" = any arena unit the
            # source's controller controls except the source itself; the keyword is
            # read through the effective layer (a granted Ambush counts).
            from swu.engine.keywords import Keyword, has_keyword
            try:
                kw = Keyword(self.param)
            except ValueError:
                return False
            iid = getattr(source_ci, "instance_id", None)
            guard = (iid, kw.value)
            if guard in _KEYWORD_SCAN_EVALUATING:
                return False
            _KEYWORD_SCAN_EVALUATING.add(guard)
            try:
                for arena in (ps.ground_arena, ps.space_arena):
                    for ci in arena:
                        if ci.instance_id == iid:
                            continue
                        if has_keyword(state, ci, kw):
                            return True
                return False
            finally:
                _KEYWORD_SCAN_EVALUATING.discard(guard)
        if c == Condition.SOURCE_ATTACHED_TRAIT_UPGRADES_MIN:
            trait, minimum = self.param
            from swu.engine.traits import has_trait
            n = sum(1 for up in (getattr(source_ci, "attached_upgrades", None) or ())
                    if has_trait(state, up, trait))
            return n >= minimum
        if c == Condition.SOURCE_UNDAMAGED:
            return source_ci.damage == 0
        if c == Condition.SOURCE_DAMAGED:
            return source_ci.damage > 0
        if c == Condition.SOURCE_EXHAUSTED:
            return bool(getattr(source_ci, "exhausted", False))
        if c == Condition.SOURCE_READY:
            return not bool(getattr(source_ci, "exhausted", False))
        if c == Condition.SOURCE_IN_SPACE_ARENA:
            return any(source_ci is ci for ci in ps.space_arena)
        if c == Condition.CONTROLLER_HAS_INITIATIVE:
            return state.initiative_holder == state.player_index(source_ci.owner_id)
        if c == Condition.CONTROLLER_N_PLUS_UNITS:
            # Units the controller has in play = both arenas (a deployed leader is
            # a unit in its arena and counts; an undeployed leader in base_zone
            # does not).  The source counts itself ("including this one").
            return (len(ps.ground_arena) + len(ps.space_arena)) >= (self.param or 0)
        if c == Condition.CONTROLLER_MORE_UNITS_THAN_OPPONENT:
            # Units in play = both arenas (deployed leaders included), the same
            # count basis as CONTROLLER_N_PLUS_UNITS.  "more than an opponent" is
            # strictly greater (2-player: the one opponent).
            opp_idx = 1 - state.player_index(source_ci.owner_id)
            opp = state.players[opp_idx]
            mine = len(ps.ground_arena) + len(ps.space_arena)
            theirs = len(opp.ground_arena) + len(opp.space_arena)
            return mine > theirs
        if c == Condition.OPPONENT_MORE_UNITS_THAN_CONTROLLER:
            # The mirror of the above (Old Access Codes TWI_168), same count basis.
            # Not the negation: equal counts satisfy neither.
            opp_idx = 1 - state.player_index(source_ci.owner_id)
            opp = state.players[opp_idx]
            mine = len(ps.ground_arena) + len(ps.space_arena)
            theirs = len(opp.ground_arena) + len(opp.space_arena)
            return theirs > mine
        if c == Condition.OPPONENT_MORE_SPACE_UNITS_THAN_CONTROLLER:
            # The space-arena-only sibling (Special Forces TIE Fighter JTL_135).
            # Strictly greater, so equal counts do not satisfy it.
            opp_idx = 1 - state.player_index(source_ci.owner_id)
            opp = state.players[opp_idx]
            return len(opp.space_arena) > len(ps.space_arena)
        if c == Condition.CONTROLLER_HAS_GROUND_AND_SPACE_UNIT:
            # Jarek Yeager JTL_109 — ≥1 unit in each arena (deployed leaders
            # included, the CONTROLLER_N_PLUS_UNITS count basis).
            return bool(ps.ground_arena) and bool(ps.space_arena)
        if c == Condition.CONTROLLER_HAS_UNIT_IN_ARENA:
            # "If you control a ground unit" (Getaway Freighter LAW_155) — the
            # single-arena sibling of the atom above, same count basis.
            return bool(ps.space_arena if self.param == "space"
                        else ps.ground_arena)
        if c == Condition.CONTROLLER_DEALT_INDIRECT_DAMAGE_THIS_PHASE:
            # Decimator of Dissidents JTL_138 — read off the phase-scoped ledger
            # fed at the indirect-damage settle point.  ``source_ci`` is the card in
            # HAND here (a play-cost read), so only ``owner_id`` is consulted.
            return source_ci.owner_id in getattr(
                state.game_memory, "indirect_dealers_this_phase", set())
        if c == Condition.CONTROLLER_N_PLUS_TRAIT_UNITS:
            # param=(trait, N) — "If you control N or more <trait> units"
            # (Petition the Senate TWI_100).  Effective traits, so a granted trait
            # counts; the same arena basis as CONTROLLER_N_PLUS_UNITS.
            from swu.engine.traits import has_trait
            trait, n = (self.param or ("", 0))
            count = sum(1 for arena in (ps.ground_arena, ps.space_arena)
                        for ci in arena if has_trait(state, ci, trait))
            return count >= int(n)
        if c == Condition.CONTROLLER_RESOURCES_PLUS_TRAIT_UNITS_MIN:
            # param=(trait, N) — "the number of resources you control plus the number
            # of friendly <trait> units is N or more" (Bo-Katan Kryze ASH_10's Epic
            # Action deploy condition).  Resources are counted whole (ready or not,
            # the ``total_resources`` basis every other deploy threshold uses).
            from swu.engine.traits import has_trait
            trait, n = (self.param or ("", 0))
            units = sum(1 for arena in (ps.ground_arena, ps.space_arena)
                        for ci in arena if has_trait(state, ci, trait))
            return (len(ps.resources) + units) >= int(n)
        if c == Condition.OPPONENT_N_PLUS_UNITS:
            # The enemy-side mirror of CONTROLLER_N_PLUS_UNITS (Duchess's Champion
            # TWI_54), same both-arenas basis; 2-player, so the one opponent.
            opp_idx = 1 - state.player_index(source_ci.owner_id)
            opp = state.players[opp_idx]
            return (len(opp.ground_arena) + len(opp.space_arena)) >= (self.param or 0)
        if c == Condition.CONTROLLER_HAS_TRAIT_CARD_IN_PLAY:
            # "a <trait> unit OR a <trait> upgrade" (Padawan Starfighter TWI_58) —
            # the arena scan of CONTROLLER_HAS_TRAIT_UNIT widened to each unit's
            # attached upgrades (a Pilot/leader-as-upgrade included).
            from swu.engine.traits import has_trait
            trait = self.param or ""
            for arena in (ps.ground_arena, ps.space_arena):
                for ci in arena:
                    if has_trait(state, ci, trait):
                        return True
                    for up in getattr(ci, "attached_upgrades", None) or ():
                        if trait in (getattr(up.card_def, "traits", None) or ()):
                            return True
            return False
        if c == Condition.CONTROLLER_HAS_OTHER_TRAIT_CARD_IN_PLAY:
            # "While you control ANOTHER Resistance card (unit, upgrade, or leader)"
            # (Raddus JTL_104).  The arena+upgrade scan above, minus the source, plus
            # base_zone so an undeployed leader counts.
            from swu.engine.traits import has_trait
            trait = self.param or ""
            for zone in (ps.ground_arena, ps.space_arena, ps.base_zone):
                for ci in zone:
                    if ci.instance_id == source_ci.instance_id:
                        continue
                    if has_trait(state, ci, trait):
                        return True
                    for up in getattr(ci, "attached_upgrades", None) or ():
                        if up.instance_id == source_ci.instance_id:
                            continue
                        if trait in (getattr(up.card_def, "traits", None) or ()):
                            return True
            return False
        if c == Condition.CONTROLLER_N_PLUS_RESOURCES:
            return ps.total_resources >= (self.param or 0)
        if c == Condition.CONTROLLER_N_PLUS_READY_RESOURCES:
            return ps.available_resources >= (self.param or 0)
        if c == Condition.OPPONENT_NO_READY_RESOURCES:
            opp = state.players[1 - state.player_index(source_ci.owner_id)]
            return opp.available_resources == 0
        if c == Condition.OPPONENT_MORE_RESOURCES_THAN_CONTROLLER:
            # Cham Syndulla JTL_164: "If an opponent controls more resources than
            # you".  Total resources (exhausted ones are still controlled), and ANY
            # opponent qualifies — with two players that is the single opponent.
            own_idx = state.player_index(source_ci.owner_id)
            return any(p.total_resources > ps.total_resources
                       for i, p in enumerate(state.players) if i != own_idx)
        if c == Condition.CONTROLLER_HAS_TRAIT_UNIT:
            from swu.engine.traits import has_trait
            trait = self.param or ""
            for arena in (ps.ground_arena, ps.space_arena):
                for ci in arena:
                    if has_trait(state, ci, trait):
                        return True
            return False
        if c == Condition.CONTROLLER_HAS_UNIT_REMAINING_HP_MIN:
            # Vergence Temple LOF_19.  Remaining HP = effective HP (every StatBonus
            # and Experience token counted) less damage already on the unit.
            from swu.engine.actions import compute_hp
            need = self.param or 0
            for arena in (ps.ground_arena, ps.space_arena):
                for ci in arena:
                    if compute_hp(state, ci) - int(getattr(ci, "damage", 0) or 0) >= need:
                        return True
            return False
        if c == Condition.SOURCE_ABILITY_USES_MAX:
            # Mystic Monastery LOF_22 — the per-game tally UseAbility keeps for every
            # activated ability, keyed by the source card's instance.
            gm = getattr(state, "game_memory", None)
            counts = getattr(gm, "activated_ability_use_counts", None) or {}
            return counts.get(source_ci.instance_id, 0) < (self.param or 0)
        if c == Condition.ENEMY_HAS_TRAIT_UNIT:
            # "While an opponent controls a <trait> unit" (Terentatek LOF_118) —
            # CONTROLLER_HAS_TRAIT_UNIT read across the table.
            from swu.engine.traits import has_trait
            trait = self.param or ""
            for opp in state.players:
                if opp.player_id == ps.player_id:
                    continue
                for arena in (opp.ground_arena, opp.space_arena):
                    for ci in arena:
                        if has_trait(state, ci, trait):
                            return True
            return False
        if c in (Condition.CONTROLLER_HAS_OTHER_TRAIT_UNIT,
                 Condition.CONTROLLER_NO_OTHER_TRAIT_UNIT):
            from swu.engine.traits import has_trait
            trait = self.param or ""
            found = False
            for arena in (ps.ground_arena, ps.space_arena):
                for ci in arena:
                    if ci.instance_id == source_ci.instance_id:
                        continue
                    if has_trait(state, ci, trait):
                        found = True
                        break
                if found:
                    break
            if c == Condition.CONTROLLER_NO_OTHER_TRAIT_UNIT:
                return not found
            return found
        if c == Condition.CONTROLLER_ATTACKED_OTHER_TRAIT_UNIT_THIS_PHASE:
            # "If you attacked with a(nother) <trait> unit this phase."  Backed by
            # game_memory.units_attacked_this_round (attacks only happen in ACTION
            # and the set clears at the round rollover, so this-round ≈ this-phase —
            # the attacked_this_phase predicate precedent).  Scans currently-in-play
            # friendly units (≠ source) with the trait that are in the set; the
            # source exclusion makes one atom serve both Bo-Katan clauses ("a
            # Mandalorian unit" undeployed, where the undeployed leader never
            # attacked, and "another Mandalorian unit" on her deployed On Attack).
            from swu.engine.traits import has_trait
            trait = self.param or ""
            # Annotated at this first binding: the later `attacked = ...` reads in
            # this method share the scope and so share the declared type.
            attacked: set[str] = getattr(getattr(state, "game_memory", None),
                                         "units_attacked_this_round", set())
            for arena in (ps.ground_arena, ps.space_arena):
                for ci in arena:
                    if ci.instance_id == source_ci.instance_id:
                        continue
                    if ci.instance_id in attacked and has_trait(state, ci, trait):
                        return True
            return False
        if c == Condition.CONTROLLER_HAS_UNIT_WITH_EXPERIENCE_TOKEN:
            from swu.cards.models import TokenUpgrade
            for arena in (ps.ground_arena, ps.space_arena):
                for ci in arena:
                    if any(isinstance(u.card_def, TokenUpgrade)
                           and u.card_def.name == "Experience"
                           for u in ci.attached_upgrades):
                        return True
            return False
        if c == Condition.CONTROLLER_HAS_OTHER_ASPECT_UNIT:
            aspect = self.param or ""
            for arena in (ps.ground_arena, ps.space_arena):
                for ci in arena:
                    if ci.instance_id == source_ci.instance_id:
                        continue
                    names = {a.name for a in (getattr(ci.card_def, "aspects", None) or ())}
                    if aspect in names:
                        return True
            return False
        if c == Condition.CONTROLLER_HAS_OTHER_SPACE_UNIT:
            return any(ci.instance_id != source_ci.instance_id
                       for ci in ps.space_arena)
        if c == Condition.CONTROLLER_HAS_EXHAUSTED_UNDEPLOYED_LEADER:
            ldr = ps.leader_instance
            return (ldr is not None and not getattr(ldr, "deployed", False)
                    and bool(getattr(ldr, "exhausted", False)))
        if c == Condition.CONTROLLER_HAS_LEADER_UNIT:
            # A deployed leader unit = a Leader card in an arena (base_zone leaders
            # don't count).  Any trait (Jedha Agitator SOR_158).
            from swu.cards.models import Leader
            return any(isinstance(ci.card_def, Leader)
                       for ci in ps.ground_arena + ps.space_arena)
        if c == Condition.CONTROLLER_HAS_TRAIT_LEADER:
            # "While you control a <Trait> leader" (Elzar Mann ASH_224) — a LEADER
            # card the controller has, deployed in an arena OR still undeployed in
            # the base zone (you control your leader either way), matched on its
            # EFFECTIVE traits.  The trait-narrowed, base-zone-inclusive sibling of
            # CONTROLLER_HAS_LEADER_UNIT.
            from swu.cards.models import Leader
            from swu.engine.traits import has_trait
            want = str(self.param or "")
            return any(isinstance(ci.card_def, Leader) and has_trait(state, ci, want)
                       for ci in ps.base_zone + ps.ground_arena + ps.space_arena)
        if c == Condition.CONTROLLER_FRIENDLY_ATTACKER_DEFEATED_THIS_PHASE:
            gm = getattr(state, "game_memory", None)
            defeated = getattr(gm, "attackers_defeated_this_round", None) or set()
            return source_ci.owner_id in defeated
        if c == Condition.ENEMY_UNIT_DEFEATED_THIS_PHASE:
            # Any unit whose controller-at-death was an OPPONENT of the source's
            # controller (2-player: the one opponent) was defeated this phase.
            gm = getattr(state, "game_memory", None)
            controllers = getattr(gm, "defeated_controllers_this_round", None) or []
            return any(pid != source_ci.owner_id for pid in controllers)
        if c == Condition.ANY_UNIT_DEFEATED_THIS_PHASE:
            # Any unit at all was defeated this phase, whoever controlled it —
            # "If a unit left play this phase" (Yoda TWI_4).  One entry per defeat
            # is appended to defeated_controllers_this_round (cleared at the round
            # rollover, and defeats happen only in ACTION, so round == phase here).
            gm = getattr(state, "game_memory", None)
            return bool(getattr(gm, "defeated_controllers_this_round", None) or [])
        if c == Condition.CONTROLLER_UNIT_DEFEATED_THIS_PHASE:
            # The friendly mirror of ENEMY_UNIT_DEFEATED_THIS_PHASE: some unit the
            # source's controller controlled died this phase (Wat Tambor TWI_6).
            gm = getattr(state, "game_memory", None)
            controllers = getattr(gm, "defeated_controllers_this_round", None) or []
            return any(pid == source_ci.owner_id for pid in controllers)
        if c == Condition.CONTROLLER_N_UNITS_DEFEATED_THIS_PHASE:
            # "If 2 or more friendly units were defeated this phase" (Nute Gunray
            # TWI_2).  One entry per defeat is appended to the ledger, so counting
            # the controller's entries counts the friendly units lost.
            gm = getattr(state, "game_memory", None)
            controllers = getattr(gm, "defeated_controllers_this_round", None) or []
            need = int(self.param if self.param is not None else 1)
            return sum(1 for pid in controllers if pid == source_ci.owner_id) >= need
        if c == Condition.CONTROLLER_HAS_DAMAGED_UNIT:
            # The friendly mirror of ENEMY_HAS_DAMAGED_UNIT: the source's controller
            # has ≥1 damaged unit in an arena (Trade Federation Shuttle TWI_60).  The
            # source counts itself if it is damaged — the card says "a damaged unit".
            ps = state.players[state.player_index(source_ci.owner_id)]
            for arena in (ps.ground_arena, ps.space_arena):
                for ci in arena:
                    if ci.damage > 0:
                        return True
            return False
        if c in (Condition.CONTROLLER_HAS_EXHAUSTED_UNIT,
                 Condition.CONTROLLER_HAS_OTHER_EXHAUSTED_UNIT):
            # "If you control an exhausted unit" / "…ANOTHER exhausted unit" (C-3PO
            # SEC_15).  The self-excluding form matters on his deployed On Attack:
            # attacking exhausts him, so without the exclusion the clause would
            # always be satisfied by himself.
            exclude_self = (c == Condition.CONTROLLER_HAS_OTHER_EXHAUSTED_UNIT)
            ps = state.players[state.player_index(source_ci.owner_id)]
            for arena in (ps.ground_arena, ps.space_arena):
                for ci in arena:
                    if exclude_self and ci.instance_id == source_ci.instance_id:
                        continue
                    if ci.exhausted:
                        return True
            return False
        if c == Condition.CONTROLLER_ATTACKED_THIS_PHASE:
            # "If a friendly unit attacked this phase" (Captain Rex TWI_7).  Each
            # recorded attacker id is resolved through find_instance, which reaches
            # the discard pile — so an attacker that died afterwards still counts,
            # unlike the in-play scan the trait-narrowed sibling uses.
            attacked = getattr(getattr(state, "game_memory", None),
                               "units_attacked_this_round", set()) or set()
            for iid in attacked:
                res = state.find_instance(iid)
                if res is not None and res[1].owner_id == source_ci.owner_id:
                    return True
            return False
        if c == Condition.CONTROLLER_ATTACKED_NON_TOKEN_TRAIT_UNIT_THIS_PHASE:
            # "If you attacked with a non-token <trait> unit this phase" (Darth
            # Vader JTL_6).  The CONTROLLER_ATTACKED_THIS_PHASE resolution (through
            # find_instance, so a dead attacker still counts) plus a trait filter
            # and the non-token exclusion — Vader's own TIE Fighter tokens are
            # Vehicles, and without the exclusion each one he made would re-arm the
            # ability.
            from swu.engine.traits import has_trait
            from swu.cards.models import TokenUnit
            trait = self.param or ""
            attacked = getattr(getattr(state, "game_memory", None),
                               "units_attacked_this_round", set()) or set()
            for iid in attacked:
                res = state.find_instance(iid)
                if res is None:
                    continue
                ci = res[1]
                if ci.owner_id != source_ci.owner_id:
                    continue
                if isinstance(ci.card_def, TokenUnit):
                    continue
                if has_trait(state, ci, trait):
                    return True
            return False
        if c == Condition.CONTROLLER_ATTACKED_TOKEN_UNIT_THIS_PHASE:
            # "While you've attacked with a token unit this phase" (Asajj Ventress
            # TS26_7 deployed).  Its own ledger of CONTROLLERS, written at the three
            # attack-declare steps — see the enum note: a token that attacked and
            # died is unreachable by find_instance, so the sibling atoms' re-read
            # would drop precisely the case this card is built around.
            attackers: set[str] = getattr(getattr(state, "game_memory", None),
                                          "token_unit_attackers_this_round", set()) or set()
            return ps.player_id in attackers
        if c == Condition.ANY_BASE_HEALED_THIS_PHASE:
            # "If a base was healed this phase" (Dooku's Solar Sailer TS26_38) —
            # unqualified, so either player's base counts.
            return bool(getattr(getattr(state, "game_memory", None),
                                "bases_healed_this_phase", set()))
        if c == Condition.CONTROLLER_DISCARD_SIZE_MIN:
            # "If there are N or more cards in your discard pile" (Twilight TS26_41).
            return len(ps.discard) >= int(self.param or 0)
        if c == Condition.CONTROLLER_PLAYED_EVENT_THIS_PHASE:
            # "If you played an event this phase" (Asajj Ventress TWI_14) — the
            # controller-scoped events ledger, fed at the single event-resolution
            # chokepoint.  Round-scoped, and events are played only in ACTION, so
            # this-round == this-phase (the units_attacked_this_round precedent).
            gm = getattr(state, "game_memory", None)
            players = getattr(gm, "events_played_this_round", None) or set()
            return source_ci.owner_id in players
        if c == Condition.SELF_DISCARDED_THIS_PHASE:
            gm = getattr(state, "game_memory", None)
            discarded = getattr(gm, "cards_discarded_this_phase", None) or set()
            return source_ci.instance_id in discarded
        if c == Condition.CONTROLLER_DISCARDED_THIS_PHASE:
            # The per-player reading of the same ledger: a card discarded from a hand
            # or deck sits in its OWNER's discard pile, so ownership is read back off
            # the instance rather than stored a second time.
            gm = getattr(state, "game_memory", None)
            for cid in (getattr(gm, "cards_discarded_this_phase", None) or set()):
                res = state.find_instance(cid)
                if res is not None and res[1].owner_id == ps.player_id:
                    return True
            return False
        if c == Condition.SOURCE_UPGRADED:
            return bool(getattr(source_ci, "attached_upgrades", None))
        if c == Condition.SOURCE_REMAINING_HP_MIN:
            # "If this unit has N or more remaining HP" (Doctor Pershing ASH_72).
            # Effective HP less damage marked, so an upgrade/token that raised the
            # unit's HP counts — the same basis as remaining_hp_le_<N>.
            from swu.engine.actions import compute_hp
            return (compute_hp(state, source_ci) - source_ci.damage) >= int(self.param or 0)
        if c == Condition.CONTROLLER_N_PLUS_EXHAUSTED_UNITS:
            n = sum(1 for arena in (ps.ground_arena, ps.space_arena)
                    for ci in arena if ci.exhausted)
            return n >= int(self.param or 0)
        if c == Condition.CONTROLLER_HAS_UPGRADE:
            # A non-token upgrade the controller OWNS, wherever its host stands —
            # "defeat a friendly upgrade" (Vane ASH_12).  Token upgrades are excluded
            # by the engine-wide kind="upgrade" convention, so the gate and the
            # DefeatUnit(kind="upgrade") candidate set agree.
            from swu.cards.models import TokenUpgrade
            for other in state.players:
                for arena in (other.ground_arena, other.space_arena):
                    for ci in arena:
                        for upg in getattr(ci, "attached_upgrades", None) or ():
                            if isinstance(upg.card_def, TokenUpgrade):
                                continue
                            if upg.owner_id == ps.player_id:
                                return True
            return False
        if c == Condition.CONTROLLER_DISCARD_TRAIT_UNIT_HAS_KEYWORD:
            from swu.cards.models import Unit
            trait, keyword = self.param
            for ci in ps.discard:
                cd = ci.card_def
                if not isinstance(cd, Unit):
                    continue
                if trait not in (getattr(cd, "traits", ()) or ()):
                    continue
                if keyword in (getattr(cd, "keywords", ()) or ()):
                    return True
            return False
        if c == Condition.ENEMY_UNIT_UPGRADED:
            # Any arena unit controlled by the source's opponent carries ≥1 attached
            # upgrade (Shield/Experience tokens count — they are upgrades, per the
            # Protector SHD_247 note).  Mirrors ENEMY_HAS_DAMAGED_UNIT's enemy-arena scan.
            opp = state.players[1 - state.player_index(source_ci.owner_id)]
            for arena in (opp.ground_arena, opp.space_arena):
                for ci in arena:
                    if getattr(ci, "attached_upgrades", None):
                        return True
            return False
        if c == Condition.VILLAINY_PLAYED_THIS_PHASE:
            # "If YOU played a Villainy card this phase" — controller-scoped, so
            # an opponent's Villainy play must not satisfy the source's condition.
            gm = getattr(state, "game_memory", None)
            players = getattr(gm, "villainy_players_this_phase", None) or set()
            return source_ci.owner_id in players
        if c == Condition.CONTROLLER_PLAYED_OTHER_CARD_THIS_PHASE:
            # ≥2 cards played by the controller this phase = "another card besides
            # this one" (the source's own play is already counted).  Lothal
            # Insurgent SOR_190.
            gm = getattr(state, "game_memory", None)
            played = getattr(gm, "cards_played_this_phase", None) or {}
            return played.get(source_ci.owner_id, 0) >= 2
        if c == Condition.CONTROLLER_PLAYED_TRAIT_CARD_THIS_PHASE:
            # "If you played a First Order card this phase" (Captain Phasma JTL_10),
            # over the per-phase trait ledger fed at the CardPlayed chokepoint.
            gm = getattr(state, "game_memory", None)
            seen = getattr(gm, "traits_played_this_phase", None) or {}
            return (self.param or "") in seen.get(source_ci.owner_id, ())
        if c == Condition.CONTROLLER_PLAYED_NON_UNIT_TRAIT_CARD_THIS_PHASE:
            # "If you played a non-unit Force card this phase" (Rey LOF_12) — the
            # non-unit slice of the same per-phase trait ledger.
            gm = getattr(state, "game_memory", None)
            seen = getattr(gm, "non_unit_traits_played_this_phase", None) or {}
            return (self.param or "") in seen.get(source_ci.owner_id, ())
        if c == Condition.CONTROLLER_DEALT_N_BASE_DAMAGE_THIS_PHASE:
            gm = getattr(state, "game_memory", None)
            dealt = getattr(gm, "base_damage_dealt_this_phase", None) or {}
            return dealt.get(source_ci.owner_id, 0) >= (self.param or 0)
        if c == Condition.CONTROLLER_CAN_PLAY_DISCOUNTED_UNIT:
            # Any unit in hand affordable after a `param`-resource discount.
            # Lazy import avoids an actions <-> registry import cycle.
            from swu.engine.actions import _effective_cost
            from swu.cards.models import Unit
            discount = self.param or 0
            for ci in ps.hand:
                cd = ci.card_def
                if not isinstance(cd, Unit):
                    continue
                if max(0, _effective_cost(cd, ps, state) - discount) <= ps.available_resources:
                    return True
            return False
        if c == Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND:
            # ≥1 affordable unit in hand matching `param` trait (None = any).
            # Reuses the same affordability filter the play-from-hand subsystem
            # uses, so the gate and the offered candidates never disagree.
            # ``param`` may also be a ``(trait, cost_reduction)`` pair when the
            # ability plays the unit at a discount ("Play a Capital Ship unit …
            # It costs 1 resource less" — Admiral Piett JTL_5), so the gate is
            # measured at the SAME price the decision will offer.
            from swu.engine.actions import _playable_units_from_hand
            p = self.param
            if isinstance(p, tuple):
                trait, reduction = p
                if reduction == "per_friendly_leader_unit":
                    # A DYNAMIC reduction, read off the board at gate time — "Play a
                    # unit from your hand.  It costs 1 resource less for each friendly
                    # leader unit" (Dooku's Palace TS26_10).  A fixed number could not
                    # express it, and a fixed 0 would make the once-per-GAME Epic
                    # Action unofferable exactly when the discount is what makes the
                    # play affordable.  Shares ``resolver._is_leader_unit`` with
                    # ``CostReduction.per_friendly_leader_unit``, so gate and price
                    # cannot drift.
                    from swu.abilities.resolver import _is_leader_unit
                    reduction = sum(1 for u in ps.ground_arena + ps.space_arena
                                    if _is_leader_unit(u))
                return bool(_playable_units_from_hand(
                    state, ps, trait, int(reduction or 0)))
            return bool(_playable_units_from_hand(state, ps, p))
        if c == Condition.CONTROLLER_CAN_PLAY_UPGRADE_FROM_RESOURCES:
            # ≥1 affordable Upgrade in the controller's RESOURCE row with a legal
            # host, ``param`` being the (host_controller, host_predicates) pair the
            # decision will use (The Armorer ASH_1).  Reuses the decision's own
            # candidate filter, so the gate and the offer can never disagree — and
            # the Exhaust cost is never spent on a play that could not happen.
            from swu.engine.actions import _affordable_hand_upgrades
            host_controller, host_predicates = (self.param or (None, ()))
            return bool(_affordable_hand_upgrades(state, {
                "controller_id": ps.player_id,
                "free": False,
                "cost_reduction": 0,
                "from_resources": True,
                "host_controller": host_controller,
                "host_predicates": list(host_predicates or ()),
            }))
        if c == Condition.CONTROLLER_CAN_PLAY_EVENT_FROM_HAND:
            # ≥1 event in hand affordable at `param` resources off (Bib Fortuna
            # SOR_177).  Reuses the play-event-from-hand affordability filter so the
            # gate and the offered candidates never disagree.
            from swu.engine.actions import _playable_events_from_hand
            return bool(_playable_events_from_hand(state, ps, self.param or 0))
        if c == Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND_COST_MAX:
            # ≥1 affordable unit in hand whose printed cost is ≤ `param`.
            from swu.engine.actions import _playable_units_from_hand
            return bool(_playable_units_from_hand(
                state, ps, None, 0, self.param))
        if c == Condition.CONTROLLER_HAS_UNIT_IN_HAND:
            # ≥1 Unit card in hand (the discardable "unit from your hand" cost).
            from swu.cards.models import Unit
            return any(isinstance(ci.card_def, Unit) for ci in ps.hand)
        if c == Condition.SOURCE_BOUNTY_RECOLLECT_AVAILABLE:
            # Bossk SHD_10: the "collect that bounty again" once-per-round has not
            # been spent this round by this source.
            return (source_ci.instance_id
                    not in state.game_memory.bounty_recollect_used_this_round)
        if c == Condition.SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE:
            # Toro Calican SHD_239: this source's once-per-round triggered ability has
            # not been used this round (marker set by the ability's CustomEffect).
            return (f"{source_ci.instance_id}:trig"
                    not in state.game_memory.activated_abilities_used_this_round)
        if c == Condition.CONTROLLER_CAN_SMUGGLE:
            # Lando SHD_17: ≥1 resource-zone card smuggle-playable at `param` off.
            # Reuses the play-via-smuggle candidate filter so the gate and the
            # offered candidates never disagree.
            from swu.engine.actions import _smuggle_eligible_from_resources
            return bool(_smuggle_eligible_from_resources(state, ps, self.param or 0))
        if c == Condition.CONTROLLER_CAN_PILOT:
            # Wedge Antilles JTL_8: ≥1 hand card playable via Piloting at `param`
            # off onto a friendly Vehicle.  Reuses the play-via-piloting candidate
            # filter so the gate and the offered plays never disagree.
            from swu.engine.actions import _piloting_eligible_from_hand
            return bool(_piloting_eligible_from_hand(state, ps, self.param or 0))
        if c == Condition.CONTROLLER_HAS_REVEAL_RAMP_RESOURCE:
            # Hunter SHD_9: ≥1 controlled resource whose name matches a friendly
            # unique unit.  Reuses the same candidate helper the reveal_resource_ramp
            # decision offers, so the gate and the offered reveals never disagree.
            from swu.engine.actions import _reveal_ramp_candidates
            return bool(_reveal_ramp_candidates(state, ps.player_id))
        if c == Condition.CONTROLLER_CAN_PLAY_UNIT_FROM_HAND_IGNORE_ASPECT_PENALTY:
            # ≥1 affordable hand unit once one V/C/A/Cunning aspect penalty is
            # waived (Daimyo's Palace LAW_20).  Reuses the same affordability
            # filter the play-from-hand subsystem uses so the gate and the
            # offered candidates never disagree.
            from swu.engine.actions import _playable_units_from_hand
            return bool(_playable_units_from_hand(
                state, ps, None, ignore_aspect_penalty=True))
        if c == Condition.CONTROLLER_HAS_READY_UNIT_COST_MAX:
            # ≥1 ready (unexhausted) arena unit whose printed cost is ≤ `param`.
            # A ready unit always has a legal attack (the enemy base at minimum),
            # so the presence of one is exactly the condition under which a
            # "attack with a cost-≤N unit" grant would offer a real attack rather
            # than fizzle (Moff Gideon SHD_7 undeployed).
            cost_max = self.param
            for arena in (ps.ground_arena, ps.space_arena):
                for ci in arena:
                    if getattr(ci, "exhausted", False):
                        continue
                    cost = getattr(ci.card_def, "cost", 0) or 0
                    if cost_max is None or cost <= cost_max:
                        return True
            return False
        if c == Condition.CONTROLLER_BASE_DAMAGE_MIN:
            base = ps.base_instance
            return base is not None and base.damage >= (self.param or 0)
        if c == Condition.ANY_BASE_DAMAGE_MIN:
            threshold = self.param or 0
            for p in state.players:
                b = p.base_instance
                if b is not None and b.damage >= threshold:
                    return True
            return False
        if c == Condition.CONTROLLER_BASE_MORE_DAMAGED_THAN_ENEMY:
            # "If your base has more damage on it than an enemy base" (Millennium
            # Falcon IBH_31).  STRICT: an equal count satisfies neither this nor its
            # mirror, which is exactly what "more" means.
            my_base = ps.base_instance
            if my_base is None:
                return False
            for p in state.players:
                if p.player_id == ps.player_id:
                    continue
                b = p.base_instance
                if b is not None and my_base.damage > b.damage:
                    return True
            return False
        if c == Condition.CONTROLLER_HAS_FORCE_TOKEN:
            return bool(getattr(ps, "has_force_token", False))
        if c == Condition.CONTROLLER_HAS_NON_LEADER_UNIT:
            from swu.cards.models import Leader
            for arena in (ps.ground_arena, ps.space_arena):
                for ci in arena:
                    if not isinstance(ci.card_def, Leader):
                        return True
            return False
        if c == Condition.ANY_PLAYER_HAS_CREDIT:
            return any(p.credits for p in state.players)
        if c == Condition.OPPONENT_HAS_CREDIT:
            return any(p.credits for p in state.players
                       if p.player_id != ps.player_id)
        if c == Condition.CONTROLLER_HAS_CREDIT:
            return bool(ps.credits)
        if c == Condition.CONTROLLER_HAS_TOKEN_UNIT:
            from swu.cards.models import TokenUnit
            return any(isinstance(ci.card_def, TokenUnit)
                       for arena in (ps.ground_arena, ps.space_arena)
                       for ci in arena)
        if c == Condition.CONTROLLER_HAS_TOKEN:
            # Any friendly token — a token UNIT standing in an arena or a token
            # UPGRADE (Shield / Experience) riding one of their units.  The same
            # pool ``actions._cull_pool(pool="tokens")`` builds (Alliance Outpost
            # LAW_19's "defeat a friendly token" cost).
            from swu.cards.models import TokenUnit, TokenUpgrade
            for arena in (ps.ground_arena, ps.space_arena):
                for ci in arena:
                    if isinstance(ci.card_def, TokenUnit):
                        return True
                    if any(isinstance(u.card_def, TokenUpgrade)
                           for u in (ci.attached_upgrades or ())):
                        return True
            return False
        if c == Condition.CONTROLLER_CREATED_TOKEN_THIS_PHASE:
            return ps.player_id in state.game_memory.tokens_created_this_phase
        if c == Condition.CONTROLLER_HAS_CARD_IN_HAND:
            return len(ps.hand) > 0
        if c == Condition.SOURCE_HAS_TRAIT:
            from swu.engine.traits import has_trait
            return has_trait(state, source_ci, self.param or "")
        if c == Condition.SOURCE_NAMED:
            # Substring, mirroring the card-text "is X" (a named card's subtitle is
            # not part of ``name``, so this matches every printing of that card).
            return (self.param or "") in (getattr(source_ci.card_def, "name", "") or "")
        if c == Condition.SOURCE_HAS_ASPECT:
            aspects = {a.name for a in (getattr(source_ci.card_def, "aspects", None) or ())}
            return (self.param or "") in aspects
        if c == Condition.SOURCE_LACKS_ASPECTS:
            aspects = {a.name for a in (getattr(source_ci.card_def, "aspects", None) or ())}
            wanted = {a.strip() for a in (self.param or "").split(",") if a.strip()}
            return aspects.isdisjoint(wanted)
        if c == Condition.ENEMY_HAS_DAMAGED_UNIT:
            # The source's opponent controls ≥1 damaged unit in an arena.
            opp_idx = 1 - state.player_index(source_ci.owner_id)
            opp = state.players[opp_idx]
            for arena in (opp.ground_arena, opp.space_arena):
                for ci in arena:
                    if ci.damage > 0:
                        return True
            return False
        if c == Condition.SOURCE_POWER_MIN:
            # The source unit's *effective* power (upgrades / tokens / Grit count)
            # is ≥ param.  Imported lazily to avoid a registry→actions import cycle.
            #
            # REENTRANCY GUARD.  ``compute_power`` consults the keyword layer (Grit,
            # and Raid while attacking) and the arena ConstantAbility scan — both of
            # which evaluate every in-play card's ConstantAbility conditions, so a
            # ConstantAbility gated on THIS condition (Vonreg's TIE Interceptor
            # JTL_137: "While this unit has 4 or more power, it gains Overwhelm")
            # would re-enter here from inside its own power computation and recurse
            # without bound.  The guard reports False on re-entry, which is also the
            # right answer: the grants it gates (Overwhelm; Raid, a while-ATTACKING
            # bonus) never contribute to the non-attacking power being measured, so
            # the OUTER evaluation still sees the true power.  Same hazard, same
            # remedy in spirit as the lightweight ``keywords.has_any_keyword``
            # (Boba Fett SHD_8).
            iid = getattr(source_ci, "instance_id", None)
            if iid is not None and iid in _POWER_MIN_EVALUATING:
                return False
            from swu.engine.actions import compute_power
            if iid is not None:
                _POWER_MIN_EVALUATING.add(iid)
            try:
                return compute_power(state, source_ci) >= (self.param or 0)
            finally:
                _POWER_MIN_EVALUATING.discard(iid)
        if c == Condition.ANOTHER_PLAYER_N_PLUS_EXHAUSTED_UNITS:
            # Blade Squadron B-Wing JTL_199.  "Another player" excludes the source's
            # own controller, so a wall of exhausted friendlies never satisfies it.
            own_idx = state.player_index(source_ci.owner_id)
            need = self.param or 0
            for i, p in enumerate(state.players):
                if i == own_idx:
                    continue
                if sum(1 for u in p.ground_arena + p.space_arena
                       if u.exhausted) >= need:
                    return True
            return False
        if c == Condition.N_PLUS_EXHAUSTED_UNITS_IN_PLAY:
            # Sly Moore SEC_14: "4 or more exhausted units in play" counts BOTH
            # players' arenas (the card says "in play", not "you control").
            return sum(1 for p in state.players
                       for u in p.ground_arena + p.space_arena
                       if u.exhausted) >= (self.param or 0)
        if c == Condition.CONTROLLER_MORE_CARDS_IN_HAND_THAN_OPPONENT:
            # Dedra Meero SEC_10 deployed.  Strictly more than SOME opponent (in
            # two-player, the one opponent) — the units mirror's hand-size twin.
            own_idx = state.player_index(source_ci.owner_id)
            mine = len(state.players[own_idx].hand)
            return any(mine > len(p.hand)
                       for i, p in enumerate(state.players) if i != own_idx)
        if c == Condition.OPPONENT_MORE_CARDS_IN_HAND_THAN_CONTROLLER:
            # Broken Horn LAW_83 — the exact mirror of the atom above.
            own_idx = state.player_index(source_ci.owner_id)
            mine = len(state.players[own_idx].hand)
            return any(len(p.hand) > mine
                       for i, p in enumerate(state.players) if i != own_idx)
        if c == Condition.SOURCE_POWER_MAX:
            # The CEILING mirror of SOURCE_POWER_MIN (Rampart JTL_182), sharing its
            # reentrancy guard — ``compute_power`` re-enters every ConstantAbility
            # condition, so a spec gated on this must not recurse.  Re-entry reports
            # False (the restriction lifts) rather than looping.
            iid = getattr(source_ci, "instance_id", None)
            if iid is not None and iid in _POWER_MIN_EVALUATING:
                return False
            from swu.engine.actions import compute_power
            if iid is not None:
                _POWER_MIN_EVALUATING.add(iid)
            try:
                return compute_power(state, source_ci) <= (self.param or 0)
            finally:
                _POWER_MIN_EVALUATING.discard(iid)
        if c == Condition.SOURCE_CHOSEN_KEYWORD:
            # Admiral Yularen JTL_47: the keyword this instance's controller chose
            # when it entered play.  Absent (no choice recorded yet, or the wrong
            # keyword) ⇒ this parallel grant is simply inert.
            iid = getattr(source_ci, "instance_id", None)
            return bool(iid) and state.game_memory.chosen_keywords.get(iid) == self.param
        if c == Condition.NO_INITIATIVE_CLAIMED_THIS_PHASE:
            # Face Off JTL_178.  Initiative is claimable only during ACTION and the
            # flag resets at the round rollover, so "this phase" ≡ this round.
            return not getattr(state, "initiative_claimed_this_round", False)
        if c == Condition.ENEMY_CONTROLS_NO_GROUND_UNITS:
            opp_idx = 1 - state.player_index(source_ci.owner_id)
            return len(state.players[opp_idx].ground_arena) == 0
        if c == Condition.CONTROLLER_HAS_EVENT_IN_HAND:
            from swu.cards.models import Event
            return any(isinstance(ci.card_def, Event) for ci in ps.hand)
        if c == Condition.CONTROLLER_HAS_ASPECT_CARD_IN_DISCARD:
            aspect = self.param or ""
            for ci in ps.discard:
                names = {a.name for a in (getattr(ci.card_def, "aspects", None) or ())}
                if aspect in names:
                    return True
            return False
        if c == Condition.CONTROLLER_DISCARD_DISTINCT_COSTS_MIN:
            # Read through getattr once: AnyCard is a union and Leader/Base/tokens
            # have no cost at all.
            costs = {cost for cost in (getattr(ci.card_def, "cost", None)
                                       for ci in ps.discard) if cost is not None}
            return len(costs) >= (self.param or 0)
        if c == Condition.CONTROLLER_HAS_TRAIT_LEADER_UNIT:
            from swu.engine.traits import has_trait
            from swu.cards.models import Leader
            trait = self.param or ""
            for arena in (ps.ground_arena, ps.space_arena):
                for ci in arena:
                    if isinstance(ci.card_def, Leader) and has_trait(state, ci, trait):
                        return True
            return False
        if c == Condition.ENEMY_N_PLUS_SPACE_UNITS:
            opp_idx = 1 - state.player_index(source_ci.owner_id)
            return len(state.players[opp_idx].space_arena) >= (self.param or 0)
        if c == Condition.CONTROLLER_HAS_ASPECT_LEADER_OR_BASE:
            aspect = self.param or ""
            for inst in (ps.base_instance, ps.leader_instance):
                if inst is None:
                    continue
                names = {a.name for a in (getattr(inst.card_def, "aspects", None) or ())}
                if aspect in names:
                    return True
            return False
        if c == Condition.ATTACHED_HOST_NAMED:
            # source_ci is an upgrade; find the unit it is attached to and match
            # its name against param (substring, mirroring the card-text "is X").
            name = self.param or ""
            for p in state.players:
                for arena in (p.ground_arena, p.space_arena):
                    for unit in arena:
                        if any(u.instance_id == source_ci.instance_id
                               for u in unit.attached_upgrades):
                            return name in (unit.card_def.name or "")
            return False
        if c == Condition.ATTACHED_HOST_HAS_TRAIT:
            # The trait sibling of ATTACHED_HOST_NAMED: source_ci is an upgrade,
            # and its host carries ``param`` among its EFFECTIVE traits ("If
            # attached unit is a Transport" — Special Modifications SEC_227).
            from swu.engine.traits import has_trait
            trait = self.param or ""
            for p in state.players:
                for arena in (p.ground_arena, p.space_arena):
                    for unit in arena:
                        if any(u.instance_id == source_ci.instance_id
                               for u in unit.attached_upgrades):
                            return has_trait(state, unit, trait)
            return False
        if c == Condition.CONTROLLER_CONTROLS_NAMED:
            # The controller has a card whose name contains param in play: the
            # leader (deployed in an arena or undeployed in base_zone), a unit in
            # an arena, or an attached upgrade (a pilot / leader-as-upgrade — so
            # "control Boba Fett as … an upgrade" counts).  Substring match
            # (mirrors ATTACHED_HOST_NAMED's "is X").
            name = self.param or ""
            for ci in (ps.base_zone + ps.ground_arena + ps.space_arena):
                if name in (ci.card_def.name or ""):
                    return True
                for up in ci.attached_upgrades:
                    if name in (up.card_def.name or ""):
                        return True
            return False
        if c == Condition.ENEMY_CONTROLS_BOUNTY_UNIT:
            # An enemy unit currently carries a Bounty (printed, granted, or a
            # while-condition bounty) — reuses the resolver's has_bounty check.
            from swu.abilities.resolver import _unit_has_bounty
            opp_idx = 1 - state.player_index(source_ci.owner_id)
            opp = state.players[opp_idx]
            return any(_unit_has_bounty(state, u)
                       for u in (opp.ground_arena + opp.space_arena))
        return False


# ── TargetSpec ────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class TargetSpec:
    controller: str = "any"           # "friendly" | "enemy" | "any"
    kind: str = "unit"                # "unit" | "base" | "unit_or_base" | "upgrade"
                                      # | "unit_upgrade" | "unit_or_unit_upgrade"
    arena: Optional[str] = None       # "ground" | "space" | None (either)
    traits: tuple = ()                # card must have ALL listed traits
    traits_any: tuple = ()            # card must have AT LEAST ONE listed trait —
                                      # "a friendly Vehicle or Droid unit" (Peli
                                      # Motto LOF_258).  Independent of ``traits``:
                                      # both filters apply when both are set.
    trait_or_upgrade_trait: Optional[str] = None
                                      # candidate has this trait ITSELF **or**
                                      # carries an attached upgrade with it —
                                      # "a Resistance unit or a unit with a
                                      # Resistance upgrade on it" (Admiral Holdo
                                      # JTL_7).  The disjunctive sibling of
                                      # ``traits`` (which is a conjunction on the
                                      # unit alone); a Pilot riding a Vehicle is an
                                      # attached upgrade, so this is how JTL prints
                                      # "unit or its pilot".
    names: tuple = ()                 # card's printed NAME (title, no subtitle) must
                                      # be one of these — "each friendly unit named X"
                                      # name-anthem auras (4-LOM SHD_188 buffs Zuckuss,
                                      # Zuckuss SHD_190 buffs 4-LOM).  Empty = any name.
    predicates: tuple = ()            # "damaged" | "undamaged" | "exhausted" |
                                      # "non_leader" | "not_self" | "leader_unit"
    cost_max: Optional[int] = None
    cost_min: Optional[int] = None
    cost_max_boost: Optional[tuple] = None  # conditional cost cap:
                                      # (aspects_tuple, boosted_cost_max) — when the
                                      # SOURCE controller controls a unit with ANY of
                                      # the listed aspects, cost_max is raised to
                                      # boosted_cost_max ("If you control a Command or
                                      # Aggression unit, … costs 4 or less instead" —
                                      # Kanan Jarrus LAW_89).  The source counts.
    cost_max_if_exhausted: Optional[int] = None  # PER-CANDIDATE conditional cost cap:
                                      # an EXHAUSTED candidate may cost up to this
                                      # instead of ``cost_max`` ("a non-leader unit
                                      # that costs 2 or less OR an exhausted
                                      # non-leader unit that costs 4 or less" —
                                      # Razor Crest JTL_223, expressed as cost_max=2
                                      # + cost_max_if_exhausted=4).  The candidate's
                                      # own state decides, unlike cost_max_boost
                                      # (which reads the source controller's board).
    cost_max_count: Optional[str] = None  # DYNAMIC cost cap: printed cost must be
                                      # <= a count computed from board state, named
                                      # here (the power_max_count sibling).  The only
                                      # source today is
                                      # "controller_villainy_aspect_icons" — the
                                      # number of Villainy aspect icons among friendly
                                      # units (Evil is Everywhere SEC_247: "Defeat a
                                      # unit with cost equal to or less than the
                                      # number of Villainy aspect icons among friendly
                                      # units").
    power_min: Optional[int] = None     # effective power must be >= this
    power_max: Optional[int] = None     # effective power must be <= this
                                      # ("a unit with 4 or less power" —
                                      # Independent Senator TWI_206)
    power_max_count: Optional[str] = None  # DYNAMIC power cap: effective power must be
                                      # <= a count computed from board state, named
                                      # here (like StatBonus.count).  The only source
                                      # today is "enemy_units_upgrade_count" — the
                                      # number of upgrades on enemy units (Slaver's
                                      # Freighter SHD_189: "ready another unit with
                                      # power ≤ the number of upgrades on enemy units").
    power_less_than_captor: bool = False  # effective power must be < the
                                      # capturing unit's effective power (the host
                                      # via event_ctx["attached_to_id"], else the
                                      # source) — Legal Authority SHD_124
    hp_remaining_max: Optional[int] = None
    select_extreme: Optional[str] = None  # set-relative "extreme" selector applied
                                      # AFTER all per-candidate filters: keep only
                                      # the candidates at the extreme of a stat
                                      # across the whole matched set.  The only value
                                      # today is "least_remaining_hp" — "the unit with
                                      # the least remaining HP among other units"
                                      # (Darth Nihilus P26_79).  Ties keep every
                                      # minimum, so the controller picks among them
                                      # (or it auto-resolves when one).
    aspects: tuple = ()               # card must have ALL listed aspects (empty = any)
    require_controller_aspect: Optional[str] = None  # board precondition gate: NO
                                      # candidate matches unless the source's
                                      # controller controls a unit with this aspect
                                      # ("If you control a <Aspect> unit, …" —
                                      # Sabine's Masterpiece JTL_250).  Gates the
                                      # whole effect via the empty-target fizzle, so
                                      # an inactive conditional branch is skipped
                                      # without a prompt; the source itself counts.
    count: int = 1                    # 1 = pick exactly one
    optional: bool = False            # True = "may" (decline is allowed)
    chooser: str = "controller"       # "controller" | "opponent"
    fixed: Optional[str] = None       # SELF | ATTACKER | DEFENDER |
                                      # EACH_FRIENDLY | EACH_ENEMY | EACH_IN_PLAY


# ── Effect primitives ─────────────────────────────────────────────────────────
@dataclass(frozen=True)
class DealDamage:
    amount: int
    target: TargetSpec

@dataclass(frozen=True)
class DealDamageEqualTo:
    """Scaling-magnitude damage: deal damage to each target equal to a count
    computed *per target* from game state, rather than a fixed amount.

    ``count`` names the scaling source:
      - ``"target_controller_hand"`` — the number of cards in the hand of the
        player who controls the target.  Used by The Chaos of War (SHD_159):
        each player's base takes damage equal to that player's hand size, so
        ``target=TargetSpec(kind="base", fixed=EACH_IN_PLAY)`` + this count
        deals each base its own owner's hand-size worth of damage.
      - ``"source_controller_discard_distinct_costs"`` — the number of *distinct*
        printed costs among the cards in the SOURCE controller's discard pile
        (the magnitude depends on the source, not the target).  Used by Fennec
        Shand (SHD_220): "Deal 1 damage to the defender for each different cost
        among cards in your discard pile" → ``target=TargetSpec(fixed=DEFENDER)``
        + this count.

    Reuses the normal fixed/legal-target resolution and ``_apply_deal_damage``;
    only the magnitude is computed dynamically.  A magnitude of 0 (empty hand)
    deals no damage.
    """
    target: TargetSpec
    count: str = "target_controller_hand"

@dataclass(frozen=True)
class Heal:
    amount: int
    target: TargetSpec  # kind="base" or kind="unit" etc.

@dataclass(frozen=True)
class DefeatUnit:
    target: TargetSpec

@dataclass(frozen=True)
class DefeatAllUnits:
    filter: TargetSpec = field(default_factory=lambda: TargetSpec())

@dataclass(frozen=True)
class GiveToken:
    token_type: str    # "Shield" | "Experience"
    target: TargetSpec
    count: int = 1     # number of tokens to attach

@dataclass(frozen=True)
class CreateCreditToken:
    """Create N Credit tokens in the source controller's resource area
    (jabba-the-hutt:07).  A non-targeted effect (like DrawCards): the credits go
    to the source's controller.  A credit is later *defeated* while paying a
    resource cost to pay 1 less (see actions._pay_play_cost).

    ``player`` follows the ``DrawCards`` / ``CreateTokenUnit`` convention —
    "controller" (the default) or "opponent", for a drawback clause that hands the
    OPPONENT the credits ("An opponent creates a Credit token" — Vel Sartha LAW_6).
    In a two-player game "an opponent" is the one opponent, so no choice is
    needed."""
    count: int = 1
    player: str = "controller"       # "controller" | "opponent" | "each"

@dataclass(frozen=True)
class CreateForceToken:
    """"The Force is with you (create your Force token)" (LOF, qui-gon-jinn:06).
    A non-targeted effect (like DrawCards / CreateCreditToken): the source's
    controller gains a Force token.  A player has at most one Force token, so
    creating one they already hold is a no-op.  Modelled as a per-player boolean
    (``PlayerState.has_force_token``), not a card instance — see
    actions / resolver.  Used by Jedi Temple LOF_23 and Youngling Padawan
    LOF_193."""


@dataclass(frozen=True)
class CreateTokenUnit:
    """Create N token units (e.g. "Clone Trooper") under the source's controller
    (ahsoka-tano:05).  A non-targeted effect (like DrawCards / CreateCreditToken):
    the tokens enter the controller's appropriate arena via
    ``actions._create_token_units``.  A token unit is an unlimited-supply unit card
    (TokenUnit def) — created into play, not drawn — so it is excluded from card
    conservation and ceases to exist when it leaves play.

    ``enters_ready=True`` puts the created tokens into play *ready* instead of the
    default exhausted ("Create N <token> tokens and ready them", On the Doorstep
    TWI_190).

    ``player`` selects WHO creates them, following the ``DrawCards`` convention:
    ``"controller"`` (default), ``"opponent"`` ("An opponent creates 2 Battle Droid
    tokens" — Jesse TWI_145, a drawback clause) or ``"each"``.  The tokens are
    created under that player's control, so an opponent's tokens are the
    opponent's units."""
    token_name: str
    count: int = 1
    enters_ready: bool = False
    player: str = "controller"

@dataclass(frozen=True)
class NextPlayDiscount:
    """Deferred play-cost reducer: "The next <trait> unit you play this phase
    costs N resource(s) less" (Khetanna LAW_158).

    Unlike ``CostReduction`` (a static reduction on the card's *own* cost), this
    records a *pending* discount in ``game_memory.pending_play_discounts`` for the
    source's controller.  The play-cost path (``actions._play_cost``) consults the
    first matching pending entry when computing the cost of a hand play, and the
    real play site (``PlayCard``) *consumes* one matching entry — so the discount
    applies to exactly one subsequent matching unit and lifts at the phase
    rollover (``GameMemory.clear_phase``).  A non-targeted effect (like
    DrawCards): the discount belongs to the source's controller.

    ``count`` records that many pending entries at once, so "each of the next N
    <trait> cards you play this phase costs M less" (Tranquility TWI_246, N=3) is
    one effect — each subsequent matching play consumes one entry.  ``units_only``
    (default True, Khetanna's "next <trait> *unit*") restricts the discount to Unit
    plays; set it False for "<trait> *cards*" (any card type — Tranquility).

    ``plot_only`` (default False) restricts the discount to a card played *using
    the Plot keyword* — "The next card you play using Plot this phase costs N less"
    (Chancellor Palpatine SEC_1).  Only the ``PlotPlay`` path passes ``via_plot`` to
    the play-cost seam, so a plot_only entry never discounts a normal hand play.

    ``exclude_aspects`` names printed aspects that DISQUALIFY the card — "the next
    non-[Heroism], non-[Villainy] card you play costs 2 less" (Bendu SOR_56,
    ``exclude_aspects=("Heroism","Villainy")``, ``units_only=False``): a card
    carrying any excluded aspect never matches the entry."""
    trait: str
    amount: int = 1
    count: int = 1
    units_only: bool = True
    plot_only: bool = False
    exclude_aspects: tuple = ()
    card_type: Optional[str] = None
    # Narrows the entry to one CARD TYPE — today only ``"event"``, "The next EVENT you
    # play this phase costs N resources less" (Rex TS26_6, Ahsoka's Lightsabers
    # TS26_35).  The type sibling of ``units_only`` (which is the Unit case), so such
    # an entry sets ``units_only=False`` and this instead.  None = any type.
    shares_keyword_with_friendly: bool = False
    # "… if it shares a keyword with a friendly unit" (Morgan Elsbeth LOF_5).  A
    # per-CANDIDATE board gate on the entry rather than a card-property filter: the
    # played card's printed keywords must intersect those of some unit its
    # controller already has in play.  Measured while paying, which is exactly the
    # card's printed rules note.
    applies_to_piloting: bool = False
    # "(This includes Piloting costs.)" — Wedge Antilles JTL_8.  A card played as a
    # Pilot upgrade pays ``_piloting_cost``, a path the ordinary hand-play discount
    # never reaches; with this set the entry also discounts (and is consumed by) a
    # PilotPlay.  The dual of ``plot_only``, except it WIDENS rather than narrows —
    # the entry still discounts a normal play of the same card.


@dataclass(frozen=True)
class DrawCards:
    count: int
    player: str = "controller"   # "controller" | "opponent" | "each"

@dataclass(frozen=True)
class DiscardFromHand:
    count: int
    chooser: str = "controller"  # who chooses which card to discard

@dataclass(frozen=True)
class ReturnToHand:
    target: TargetSpec

@dataclass(frozen=True)
class Protection:
    """Passive protection: the target can't be defeated and/or returned to hand by
    enemy card abilities (Chewbacca JTL_103: "This unit can't be defeated or
    returned to hand by enemy card abilities").

    Modelled as an effect on a self-targeted ``ConstantAbility`` — the same
    "attached unit gains X" convention the keyword layer uses (an upgrade's
    ``ConstantAbility(target=SELF, ...)`` confers X on its host).  So a single
    ``ConstantAbility(SELF, [Protection(...)])`` protects the card as a unit AND,
    when the card is a Pilot upgrade, protects its host (Chewbacca's "Attached
    unit gains: '...can't be defeated or returned...'").

    Read (not routed) at the defeat/return effect-resolution seams
    (``resolver`` DefeatUnit / DefeatAllUnits / ReturnToHand arms via
    ``_target_protected``): an enemy ability's DefeatUnit/ReturnToHand simply
    skips a protected target.  Only *enemy* abilities are blocked — a friendly
    ability (source controller == target controller) is unaffected — and combat/
    damage defeat is unaffected (it never routes through the DefeatUnit effect)."""
    from_defeat: bool = False
    from_return: bool = False
    from_exhaust: bool = False  # can't be exhausted by enemy card abilities
                                # (Kylo Ren's Lightsaber LOF_40, when the host is a
                                # Force unit — the ConstantAbility's condition gates it)
    from_hp_defeat: bool = False  # can't be defeated by having no remaining HP.
                                # Unlike the other three (which block *enemy card
                                # abilities*), this guards the state-based HP-defeat
                                # gate and is read by actions._hp_defeat_prevented,
                                # phase-gated to the ACTION phase (Chirrut Îmwe
                                # SOR_4: "During the action phase, this unit isn't
                                # defeated by having no remaining HP")
    from_capture: bool = False  # can't be captured by enemy card abilities — read at
                                # the capture seam (actions._apply_capture); an enemy
                                # ability's capture simply skips a protected target.
    from_damage: bool = False   # can't be damaged by enemy card abilities — read in
                                # the resolver DealDamage/DealDamageEqualTo arms, so
                                # combat damage (which never routes through those
                                # effects) is unaffected (Lurking TIE Phantom SHD_187:
                                # "can't be captured, damaged, or defeated by enemy
                                # card abilities").
    hp_defeat_any_phase: bool = False  # widen ``from_hp_defeat`` past the ACTION
                                # phase.  Chirrut Îmwe SOR_4 prints "During the
                                # action phase", which is the default reading
                                # ``actions._hp_defeat_prevented`` gates on; a card
                                # whose clause carries no phase limit (Cassian Andor
                                # SEC_12: "While you have the initiative, this unit
                                # isn't defeated by having no remaining HP") sets
                                # this so the guard also holds through REGROUP.
    from_control_change: bool = False  # "Opponents can't take control of this unit"
                                # (Rey LAW_149) — read at the single control seam
                                # ``actions.change_control``, which simply refuses to
                                # hand the card to a player who is not its owner.
                                # Unlike the other arms this is not scoped to "enemy
                                # card abilities": every control change today comes
                                # from a card, and the printed clause names the
                                # DESTINATION ("opponents"), so a friendly effect
                                # returning the unit to its owner still works.
    upgrade_only: bool = False  # the protection covers ONLY this card while it is
                                # itself attached as an upgrade — it does NOT flow to
                                # the host, and does not apply while the card is in an
                                # arena as a unit.  "THIS UPGRADE can't be defeated by
                                # enemy card abilities" (Luke Skywalker JTL_12's
                                # deploy-as-a-Pilot side), as against Chewbacca
                                # JTL_103's "this unit … / attached unit gains …",
                                # which is the default (False) both-ways reading.

@dataclass(frozen=True)
class ExhaustCard:
    target: TargetSpec

@dataclass(frozen=True)
class ReadyCard:
    target: TargetSpec

@dataclass(frozen=True)
class ModifyStats:
    power: int
    hp: int
    target: TargetSpec
    duration: Duration

@dataclass(frozen=True)
class GrantKeyword:
    keyword: str
    value: int           # 0 for boolean keywords
    target: TargetSpec
    duration: Duration

@dataclass(frozen=True)
class RevokeKeyword:
    keyword: str
    target: TargetSpec
    duration: Duration

@dataclass(frozen=True)
class RevokeTrait:
    """Duration-scoped trait REMOVAL — "Each enemy unit loses the Force trait for
    this phase" (Nameless Terror LOF_33).

    The trait-layer sibling of ``RevokeKeyword``: the resolver records a
    ``trait_revoke`` Modifier on each target, which ``swu.engine.traits.get_traits``
    / ``has_trait`` consult FIRST — ahead of the printed traits and every
    ``TraitGrant`` source — so "can't gain the trait while revoked" falls out for
    free, exactly as it does for ``keyword_revoke``.  Expires with the ordinary
    duration sweep."""
    trait: str
    target: TargetSpec
    duration: Duration = Duration.THIS_PHASE

@dataclass(frozen=True)
class ResourceCardEffect:
    """Resource a card from play — distinct from the ResourceCard action."""
    target: TargetSpec

@dataclass(frozen=True)
class CaptureUnit:
    """Capture the chosen unit — remove it from play and place it facedown under
    the capturing unit ("until he leaves play"), then return it to its owner's
    arena under their control when the captor leaves play.

    The captor is the host of the upgrade whose ability captures (read from
    ``event_ctx["attached_to_id"]``), falling back to the ability's source unit.
    ``target`` is chosen through the normal resolve_effects/ChooseTarget
    machinery (mandatory-if-able; fizzles with no eligible unit), so no new
    decision kind is needed.  See actions._apply_capture / _release_captured_cards.
    """
    target: TargetSpec

@dataclass(frozen=True)
class ConditionalEffect:
    condition: ConditionCheck
    if_true: tuple   # tuple of effects
    if_false: tuple  # tuple of effects (may be empty)

@dataclass(frozen=True)
class CustomEffect:
    """Single-step escape hatch for effects that cannot be expressed declaratively.

    fn(state, source_ci, target_id, event_ctx) -> GameState

    When ``target`` is None the effect takes no player-chosen target and fn is
    always called with ``target_id=None`` (auto/inline).  When ``target`` is a
    TargetSpec the standard resolve_effects decision machinery enumerates its
    legal targets (ChooseTarget / DeclineTarget) exactly as it does for the
    declarative targeted effects, and threads the player's chosen instance_id
    into fn as ``target_id``.  This lets a custom effect act on a real chosen
    target while still expressing logic the declarative primitives cannot (e.g.
    a conditional that keys off a property of the CHOSEN target).

    ``available_fn(state, source_ci, event_ctx) -> bool`` is an optional
    availability predicate consulted ONLY by
    ``resolver._optional_trigger_has_legal_effect``, i.e. when deciding whether an
    OPTIONAL trigger is worth prompting for.  A non-targeted CustomEffect is
    otherwise assumed always to do something, so an optional trigger built on one
    always prompts; this extends the engine-wide "don't offer a no-op" rule to
    effects whose availability only the card can compute (Shadow Caster JTL_169:
    "you may use all of a defeated friendly unit's 'When Defeated' abilities
    again" — most units have none).  It never gates execution, only the offer.

    ``grants_keywords`` is inert at runtime: it DECLARES, for the keyword
    sanitiser, which keywords this custom effect hands to OTHER cards.  A grant
    written declaratively (``GrantKeyword`` / ``KeywordGrant``) is visible to
    sanitiser rule 9, which strips the printed keyword the upstream data mistags
    onto a card that only grants it; a grant buried in ``fn`` is not — and a card
    must sometimes bury it, because two targeted effects would prompt twice and
    could split across two units (Baylan Skoll ASH_3 gives ONE unit +2/+2 *and*
    Sentinel).  Naming the keyword here restores rule 9's view of it.
    """
    fn: Callable
    target: Optional[TargetSpec] = None
    available_fn: Optional[Callable] = None
    grants_keywords: tuple = ()


# ── Static effects (for ConstantAbility) ─────────────────────────────────────
@dataclass(frozen=True)
class StatBonus:
    """Constant power/HP buff applied as long as this ability's condition holds.

    ``count`` names a scaling source (like ``DealDamageEqualTo``): when set, the
    ``power``/``hp`` values are the per-unit amount and the contribution is scaled
    by the current count from game state (Nien Nunb JTL_93:
    ``count="other_friendly_pilots"`` = "+1/+0 for each other friendly Pilot unit
    and upgrade").  When ``None`` the buff is the flat ``power``/``hp`` (the
    default, byte-identical to every existing StatBonus).

    A few count sources carry a PARAMETER in the string itself, after a fixed
    prefix — ``"controller_base_damage_per_5"`` (the divisor, Anakin TWI_12) and
    ``"controller_trait_units_Trooper"`` (the trait, Squad Support TWI_122) — so
    one arm of ``actions._stat_bonus_count`` serves every step size / trait."""
    power: int = 0
    hp: int = 0
    count: Optional[str] = None

@dataclass(frozen=True)
class KeywordGrant:
    """Constant keyword grant; value=0 for boolean keywords.

    ``value_count`` makes the numeric value DYNAMIC, naming a board count computed at
    read time instead of using ``value`` — "This unit gains Raid 1 for each damaged
    enemy unit" (Punishing One SEC_171, ``"damaged_enemy_units"``).  Resolved only in
    ``keywords.keyword_value`` (``_keyword_grant_value``); ``has_keyword`` is
    unaffected, which is right — the unit HAS the keyword either way, and a count of 0
    just means Raid 0.  The keyword-layer sibling of ``StatBonus.count``."""
    keyword: str
    value: int = 0
    value_count: Optional[str] = None

@dataclass(frozen=True)
class KeywordRevoke:
    """Constant keyword-REVOKE aura: every unit matched by this ability's ``target``
    LOSES ``keyword`` while the source is in play — "Enemy units lose Ambush and
    Support" (Domesticated Loth-Cat ASH_68).

    The aura mirror of ``KeywordGrant`` and the standing mirror of the duration-scoped
    ``RevokeKeyword`` effect (which stamps a ``keyword_revoke`` Modifier on units
    chosen *now*, and so cannot reach a unit played later).  Read by the keyword query
    layer (``keywords.has_keyword`` / ``keyword_value``) immediately after the
    ``keyword_revoke`` modifier check — i.e. BEFORE every grant source — so "and can't
    gain it" falls out for free, exactly as it does for that modifier.  The board scan
    is gated on a lazily-built registry index of the (set, number) keys carrying such a
    spec (``keywords._keyword_revoke_aura_keys``), because the keyword layer is a hot
    path and almost no card revokes."""
    keyword: str

@dataclass(frozen=True)
class TraitGrant:
    """Constant trait grant.  An upgrade carrying a ConstantAbility with a
    TraitGrant adds ``trait`` to its attached host unit (Foundling, SHD_69:
    "Attached unit gains the Mandalorian trait").  Read by the trait query layer
    (``swu.engine.traits.get_traits`` / ``has_trait``), which is consulted by the
    target matcher (``resolver._spec_matches_ci``), the trait-gated Conditions, and
    the decision trait filters — so a granted trait counts everywhere a printed one
    does for "an <X> unit" checks, without touching point-of-use string matching."""
    trait: str

@dataclass(frozen=True)
class CopyKeywords:
    """Constant keyword-copy aura: each unit matched by this ability's ``target``
    gains the SOURCE unit's keywords, for as long as the source is in play (The
    Ghost JTL_53: "Each other friendly Spectre unit gains this unit's keywords").

    Unlike ``KeywordGrant`` (a fixed named keyword) the granted set is *dynamic* —
    it is whatever ``has_keyword``/``keyword_value`` currently report for the
    source, so a keyword the source itself only conditionally gains (The Ghost's
    "while upgraded, it gains Sentinel") is copied only while the source has it.
    Read by the keyword query layer (``keywords.has_keyword`` / ``keyword_value``),
    which scans in-play units for a ConstantAbility carrying this effect whose
    ``target`` matches the queried unit; a re-entrancy guard breaks any mutual-copy
    cycle.  Carries no fields (copies the whole keyword set)."""


@dataclass(frozen=True)
class GrantSmuggleToResources:
    """Constant effect: while the source unit is in play, each of its
    controller's resources gains Smuggle (Tech, SHD_248).  The granted smuggle
    cost is that resource card's printed cost + 2, with its own aspect icons.

    Like SuppressFirstEnemyEvent this is a passive marker, not a stat/keyword
    buff read by compute_power/has_keyword: it is consulted only at the
    smuggle-enumeration seam in legal_actions (``_resources_have_granted_smuggle``
    in actions.py).  It lives on a ConstantAbility because it is purely "while in
    play" and ceases the moment the source leaves play.  Carries no fields."""


@dataclass(frozen=True)
class SuppressFirstEnemyEvent:
    """Constant *replacement* effect: while the source is in play, the first
    event each opponent plays each round loses all abilities (Relentless,
    SOR_89).

    Unlike StatBonus/KeywordGrant this is not a stat/keyword buff read by
    compute_power/has_keyword — the stat and keyword consumers ignore it.  It is
    detected at the event-resolution seam (``_resolve_event_ability`` in
    actions.py), which skips ability resolution for the affected event.  It lives
    on a ConstantAbility purely because it is passive "while in play" — there is
    no action to start or stop it, and it ceases the moment the source leaves
    play.  This marker carries no fields."""


# ── Cost specs (ActivatedAbility) ────────────────────────────────────────────
@dataclass(frozen=True)
class ExhaustSelf:
    pass

@dataclass(frozen=True)
class PayResources:
    n: int

@dataclass(frozen=True)
class DefeatSelf:
    pass

@dataclass(frozen=True)
class UseForce:
    """Cost: "use the Force (lose your Force token)" (Qui-Gon Jinn LOF_16's
    undeployed Action).  Payable only when the controller has a Force token
    (``PlayerState.has_force_token``); paying it clears the token.  Handled at the
    activated-ability cost sites in actions.py (UseAbility / legal_actions),
    parallel to ExhaustSelf / PayResources / DefeatSelf."""
    pass

@dataclass(frozen=True)
class DiscardCardCost:
    """Cost: "discard a card from your hand" (Kylo Ren SHD_11's undeployed Action).
    Payable only when the controller has ≥1 card in hand; paying it discards the
    first card (the DiscardFromHand first-card simplification).  Handled at the
    activated-ability cost sites in actions.py (UseAbility / legal_actions),
    parallel to ExhaustSelf / PayResources / DefeatSelf / UseForce.

    ``cost_min`` narrows WHICH card may be discarded — "discard a card that costs 6
    or more from your hand" (Dryden Vos SEC_7): the ability is only offered while
    the hand holds such a card, and paying discards the first one that qualifies.
    ``count`` discards that many cards ("discard 2 cards from your hand")."""
    cost_min: Optional[int] = None
    count: int = 1


@dataclass(frozen=True)
class DefeatCreditCost:
    """Cost: "defeat a friendly Credit token" (Hunter For Hire LAW_156's Action).

    Payable only while the PAYING player holds ≥``count`` Credit tokens; paying
    defeats that many (credits are unlimited-supply tokens with no discard pile —
    ``actions._defeat_credit``).  Handled at the activated-ability cost sites in
    actions.py (UseAbility / legal_actions), parallel to ExhaustSelf /
    PayResources / DefeatSelf / UseForce / DiscardCardCost.  Credits are fungible,
    so which one is defeated is not a choice (the SOR_145 convention).

    The payer is the ability's USER, not the source's owner — LAW_156 is an
    ``any_player`` ability (Mercenary Gunship SHD_256), so an opponent buying the
    unit pays from their own credit pile."""
    count: int = 1


@dataclass(frozen=True)
class EnemyCreditsLoseAbilities:
    """Constant marker on a UNIT: while it is in play, Credit tokens controlled by
    an OPPONENT of its controller lose all abilities (Conveyex Security Captain
    LAW_117: "Enemy Credit tokens lose all abilities").

    A Credit token's only printed ability IS its spend clause ("While paying
    resources, you may defeat this token.  If you do, pay 1 resource less"), so
    losing it means those credits can no longer pay for anything.  Read through the
    single helper ``actions._usable_credits`` — consulted by BOTH the affordability
    gate (``_affordable_with_credits``) and the payment site (``_pay_play_cost``),
    so the two can never disagree.  Purely a read there — no trigger, no decision
    (the ``BasesCannotHeal`` marker pattern); it lifts when the unit leaves play,
    and a suppressed unit (Mind Trick LOF_202 …) confers nothing."""
    pass


# ── Trigger conditions ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class WhenPlayed:
    """Fires when this card enters play (played from hand or via Exploit).

    ``as_upgrade=True`` narrows the trigger to the *upgrade* play path only — i.e.
    a Piloting Unit played as a Pilot upgrade (the ``UpgradePlayed``/``via_pilot``
    path), NOT when the same card is played as a normal unit (``UnitEntersPlay``).
    Used for "When played as an upgrade: …" text on a Piloting unit (Boba Fett
    JTL_189).  ``as_unit=True`` is the mirror image — fires ONLY on the normal
    unit play path (``UnitEntersPlay``), NOT when the same Piloting Unit is played
    as a Pilot upgrade — for "When played as a unit: …" text (The Mandalorian
    JTL_210).  The default (both False) fires on either play path (a unit entering
    an arena OR an upgrade being attached), which is correct for ordinary cards.
    ``as_upgrade`` and ``as_unit`` are mutually exclusive.
    """
    as_upgrade: bool = False
    as_unit: bool = False

@dataclass(frozen=True)
class WhenPlayedViaSmuggle:
    """Fires when this card is played using the Smuggle keyword (i.e. from the
    resource zone), but NOT when played normally from hand.  Gated on the
    ``via_smuggle`` flag threaded through the play event context (Cassian Andor
    SHD_148, Hotshot DL-44 Blaster SHD_174)."""

@dataclass(frozen=True)
class WhenDeployed:
    """Fires when this leader is deployed (the undeployed → deployed transition).

    Matches the ``LeaderDeployed`` event for the source leader.  At the moment of
    firing the leader is already in the arena (``deployed=True``), so this is the
    deployed side of the card (mark it ``deployed_only=True``).  Used by Leia
    Organa (LAW_10): "When Deployed: Choose a unit. Give an Experience token to
    that unit for each different aspect among units you control."

    ``via_pilot_leader=True`` narrows the trigger to the *pilot-leader-deploy*
    path (Boba Fett JTL_9 "When deployed as an upgrade: …").  The default (False)
    matches any deploy, including the normal unit-deploy path.
    """
    via_pilot_leader: bool = False

@dataclass(frozen=True)
class WhenYouDeployLeader:
    """Fires (as an observer) when the source card's controller deploys a leader.

    The observer sibling of ``WhenDeployed`` (which fires for the deploying leader
    itself): this matches the ``LeaderDeployed`` event whose deploying player is the
    SOURCE's controller, so another permanent can watch its own side's deploy —
    Shadow Collective Camp TWI_25: "When you deploy a leader: Draw a card."

    Collected at the existing deploy ``fire_triggered_abilities`` sites (the normal
    deploy and the deploy-as-a-Pilot-upgrade path both fire ``LeaderDeployed``), so
    it needs no new firing point; a Base source is reached by the ``base_zone``
    branch of ``resolver._collect_triggers``.
    """

@dataclass(frozen=True)
class WhenDefeated:
    """Fires when this card is defeated."""

@dataclass(frozen=True)
class WhenDefeatedAsUpgrade:
    """Fires when this card is defeated *while it is an attached upgrade* — the
    replacement-effect seam for a Pilot upgrade "If this upgrade would be defeated,
    you may instead …" (Luke Skywalker J25_4).

    A Pilot is a Unit card played as an upgrade (Piloting); when its host unit is
    defeated the pilot is detached and sent to its owner's discard by
    ``_defeat_unit``.  This trigger is collected ONLY from that path — the
    ``event_ctx["defeated_upgrades"]`` scan in ``resolver._collect_triggers`` — so
    it fires when the card dies as an upgrade but NOT when the same card is played
    and defeated as a normal unit (the ``defeated_ci`` scan collects only
    ``WhenDefeated``).  The replacement is modelled the Superlaser Technician SHD_85
    way: an optional trigger that, by the time it resolves, finds the card already
    in discard and relocates it (here: back to the ground arena as a unit) — a
    faithful, low-risk stand-in for a true pre-defeat interception (no shipped card
    observes an upgrade's defeat, so the momentary discard touch is unobservable).
    """

@dataclass(frozen=True)
class OnAttack:
    """Fires when this unit is declared as an attacker.

    ``vs_unit`` narrows the trigger to an attack against a UNIT — "On Attack: If
    this unit is attacking a unit, …" (Defiant Hammerhead LAW_62).  A base attack
    carries a ``None`` defender on the ``AttackDeclared`` event, so the clause is a
    plain read of the event and needs no new firing point.  Default False = fires on
    any attack (every other On Attack card)."""
    vs_unit: bool = False

@dataclass(frozen=True)
class WhenAttacked:
    """Fires when this unit is declared as a defender."""

@dataclass(frozen=True)
class WhenDamageDealtToYourBase:
    """Fires (as an observer) when damage is dealt to the source's controller's base,
    from ANY source — a base attack, an ability, or indirect damage the controller
    assigned there (The Daughter LOF_252: "When damage is dealt to your base: …").

    Matched off ``event_ctx["base_damaged_player_id"]``, a per-instance ledger the
    base-damage sinks append to (``actions.record_base_damage``) and the action
    settle-point drains (``actions._fire_base_damage_observers``) — the
    WhenUnitHealed / WhenDealNonCombatDamage shape, so it needs no new event class
    and cannot fire mid-pipeline."""


@dataclass(frozen=True)
class WhenEnemyAttacksYourBase:
    """Fires (as an observer) when an OPPONENT of the source card's controller
    declares an attack against the controller's base.

    Matches the ``AttackDeclared`` event with a ``None`` defender (a base attack)
    whose attacker belongs to an opponent of the source's controller.  Collected at
    the same base-attack ``fire_triggered_abilities`` site the attacker's OnAttack
    uses, so it needs no new firing point.  The matcher records the attacker's arena
    in ``event_ctx["same_arena"]`` so an effect can target "a friendly unit in the
    same arena as the attacker" (Kragan Gorr SHD_241).

    ``arena`` ("ground"/"space") narrows it to an attacker in that arena — "When an
    enemy GROUND unit attacks your base" (Aurra Sing TWI_166).  Default None = any
    attacker, the SHD_241 behaviour."""
    arena: Optional[str] = None

@dataclass(frozen=True)
class WhenUnitDefeated:
    """Fires when ANY unit matching filter is defeated, from the perspective of source card's controller."""
    filter: TargetSpec = field(default_factory=lambda: TargetSpec())

@dataclass(frozen=True)
class WhenUnitEntersPlay:
    """Fires when ANY unit matching filter enters play."""
    filter: TargetSpec = field(default_factory=lambda: TargetSpec())

@dataclass(frozen=True)
class WhenIndirectDamageDealtToUnit:
    """Fires (as an observer) when indirect damage is assigned to a unit.

    Unlike source-specific triggers (WhenDealtCombatDamage), this fires for
    ANY observer card in play when ``assign_indirect_damage`` resolves and the
    chosen target was a unit.  Matched via the ``indirect_damage_unit_id`` key
    in ``event_ctx`` (set by the resolution helper before firing).  Used by
    Allegiant General Pryde JTL_133: "When indirect damage is dealt to a unit:
    You may defeat a non-unique upgrade on it."
    """

@dataclass(frozen=True)
class WhenDealNonCombatDamage:
    """Fires (as an observer) when the source card's controller deals *non-combat*
    damage.

    Non-combat damage is any damage dealt outside the "deal combat damage" step of
    an attack (per the CR / Boba Fett JTL_9's rules box) — i.e. every ability /
    event / indirect damage.  It is detected by instrumenting the two non-combat
    damage sinks (``resolver._apply_deal_damage`` / ``_apply_indirect_damage``),
    which record the *dealer's* player id in ``GameMemory.noncombat_damage_dealers``;
    that queue is drained at the action settle-point (``actions.apply``), firing
    this observer with ``event_ctx["noncombat_damage_dealer_id"]`` set (matched only
    when it equals the source's controller — "when YOU deal non-combat damage").
    Combat damage flows through ``_deal_damage_with_shield`` directly and is never
    recorded, so it does not fire this trigger.  ``event`` is None (a synthesised
    observer fire, like ``WhenIndirectDamageDealtToUnit``).  Used by Boba Fett
    JTL_9: "When you deal non-combat damage: You may exhaust this leader.  If you
    do, deal 1 indirect damage to a player."

    Gate the trigger with ``condition=SOURCE_READY`` so it is not offered once the
    leader is exhausted — this bounds the natural self-chain (Boba's own indirect
    damage is itself non-combat damage, which would re-fire the observer, but by
    then the leader is exhausted so it is no longer collected).
    """

@dataclass(frozen=True)
class WhenYouDraw:
    """Fires (as an observer) when cards are drawn during the ACTION phase.

    Two flavours keyed by ``on_self``:
      * ``on_self=False`` — an **in-play** observer that fires when its controller
        draws 1+ cards during the action phase (The Mandalorian LAW_52: "When you
        draw 1 or more cards during the action phase: Give a Shield to this unit").
        Matched via ``event_ctx["drew_player_id"] == source_ci.owner_id``.
      * ``on_self=True`` — fires for the **drawn card itself** while it sits in the
        drawer's hand (Rey LOF_148: "When you draw this card during the action
        phase: …").  Matched via ``source_ci.instance_id in
        event_ctx["drawn_card_ids"]`` and collected by a dedicated hand scan in
        ``resolver._collect_triggers`` (the arena scan never yields a hand card).

    Detection mirrors ``WhenDealNonCombatDamage``: ``actions._draw_cards`` records
    one ``{"player_id", "card_ids"}`` entry per ACTION-phase draw *event* into
    ``GameMemory.action_phase_draws``; that ledger is drained at the action
    settle-point (``actions.apply`` → ``_fire_draw_observers``) — so an observer
    resolves on a clean stack rather than mid-``_draw_cards`` (which is called deep
    inside effect resolution).  ``event`` is None (a synthesised observer fire).

    ACTION and REGROUP draws are both ledgered (each entry carries its ``phase``),
    but the matcher admits only ACTION ones unless ``any_phase=True`` — so "during
    the action phase" stays intrinsic for every card that prints it, and Axe Woves
    ASH_169's "(including during the regroup phase)" is the one opt-in.  Setup
    draws are never recorded.

    ``opponent=True`` inverts the in-play match to fire when an *opponent* of the
    source's controller drew (Seasoned Fleet Admiral JTL_111: "When an opponent
    draws 1 or more cards during the action phase: …") — mutually exclusive with
    ``on_self``.

    ``any_player=True`` widens it further: the observer fires whoever drew — "When a
    player draws 1 or more cards during the action phase" (Chairman Papanoida
    SEC_159), the any-player sibling of the controller / opponent readings and the
    same shape as the any-player ``WhenPlayerDiscardsFromHand`` observer.
    """
    on_self: bool = False
    opponent: bool = False
    any_player: bool = False
    any_phase: bool = False

@dataclass(frozen=True)
class WhenYouUseForce:
    """Fires (as an observer) when the source card's controller *uses the Force*
    (spends their Force token, for any reason — an ability cost, the ``use_force``
    decision, or a card's force-spending ``CustomEffect``).

    Detection mirrors ``WhenYouDraw`` / ``WhenDealNonCombatDamage`` exactly: every
    Force-token spend routes through the single chokepoint
    ``actions.spend_force_token``, which records the spender's player id in
    ``GameMemory.force_uses``; that ledger is drained at the action settle-point
    (``actions.apply`` → ``_fire_force_observers``) — so the observer resolves on a
    clean stack rather than mid-effect-resolution (Force is usually spent deep
    inside a ``CustomEffect``).  ``event`` is None (a synthesised observer fire).
    Matched via ``event_ctx["force_used_player_id"] == source_ci.owner_id`` ("when
    YOU use the Force"), collected by the ordinary in-play arena scan (no hand
    scan — the sole user observes from play).

    Used by Yoda LOF_101: "When you use the Force: You may deal damage to a unit
    equal to twice the number of units you control."  Unlike Boba Fett JTL_9's
    ``WhenDealNonCombatDamage`` this needs no ``SOURCE_READY`` self-chain gate — the
    payoff deals damage, which does not itself use the Force, so it cannot re-fire.
    """

@dataclass(frozen=True)
class WhenYouRevealOrDiscard:
    """Fires (as an observer) when the source card's controller reveals OR discards
    1 or more cards *from their hand* — once per reveal/discard instruction (Padmé
    Amidala SEC_16: "When you reveal or discard 1 or more cards from your hand: …").

    Detection mirrors ``WhenYouUseForce`` / ``WhenYouDraw`` exactly.  The two
    hand-interaction chokepoints record the acting player's id into
    ``GameMemory.hand_reveal_discards`` — ONE entry per instruction, regardless of
    how many cards ("1 or more"):
      * a *reveal* — a successful Disclose (``actions._resolve_disclose`` when the
        discloser actually revealed ≥1 hand card; Disclose is the only
        "reveal cards from your hand" path in the shipped decks), and
      * a *discard from hand* — the declarative ``DiscardFromHand`` effect
        (``resolver`` arm) and the bespoke first-card hand-discard CustomEffects that
        move a card from hand to discard (they call ``actions.record_hand_discard``).
    That ledger is drained at the action settle-point (``actions.apply`` →
    ``_fire_reveal_discard_observers``) so the observer resolves on a clean stack
    rather than mid-effect-resolution (a reveal/discard is usually deep inside a
    CustomEffect / event resolution).  ``event`` is None (a synthesised observer
    fire).  Matched via ``event_ctx["hand_reveal_discard_player_id"] ==
    source_ci.owner_id`` ("when YOU reveal or discard").  Collected by the ordinary
    in-play arena scan AND the base_zone scan (so it fires for Padmé whether she is
    an undeployed leader in base_zone or a deployed leader in an arena).

    No self-chain gate is needed — the payoff (deal 1 damage / exhaust) neither
    reveals nor discards, so it cannot re-fire the observer (unlike Boba Fett
    JTL_9's non-combat-damage self-chain, which needs ``SOURCE_READY``)."""

@dataclass(frozen=True)
class WhenPlayerDiscardsFromHand:
    """Fires (as an observer) when ANY player discards 1+ cards *from their hand* —
    once per discard instruction (Migs Mayfeld SHD_163: "When a player discards a card
    from their hand: You may deal 2 damage to a unit or base.  Use this ability only
    once each round.").

    Detection mirrors ``WhenYouRevealOrDiscard`` but differs in two ways: it matches on
    EITHER player's discard (no ``owner_id`` guard — "a player" is anyone, like
    ``WhenIndirectDamageDealtToUnit``), and on DISCARD ONLY — a Disclose *reveal* does
    not fire it.  A dedicated discard-only ledger (``GameMemory.hand_discards``) is fed
    from the single discard chokepoint (``actions.record_hand_discard`` with the
    default ``kind="discard"``); the reveal path passes ``kind="reveal"`` and so never
    records here.  Drained at the action settle-point (``actions.apply`` →
    ``_fire_hand_discard_observers``) so the observer resolves on a clean stack.
    ``event`` is None (a synthesised observer fire).  Matched via the presence of
    ``event_ctx["hand_discard_player_id"]``.  Collected by the ordinary in-play arena
    scan (Migs is a deployed unit).

    The "once each round" limiter is the shared ``SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE``
    condition (Toro Calican SHD_239 pattern): the payoff marks ``f"{instance_id}:trig"``
    in ``activated_abilities_used_this_round`` when it resolves, so declining the "you
    may" does not spend the round's use."""

@dataclass(frozen=True)
class WhenThisIsDiscarded:
    """Fires (as an observer) when the SOURCE CARD ITSELF is discarded from its
    owner's hand or deck (That's a Rock LAW_206: "When this event is discarded from
    your hand or deck: You may deal 1 damage to a unit.").

    The ``WhenUnitHealed`` shape, but for a card that is NOT in play: a dedicated
    ledger (``GameMemory.self_discards``) is fed by ``actions.note_hand_or_deck_discard``
    — the single hand/deck-discard chokepoint that already backs
    ``cards_discarded_this_phase`` — and drained at the action settle-point
    (``actions.apply`` → ``_fire_self_discard_observers``) so the observer resolves on
    a clean stack rather than mid-mill.  ``event`` is None (a synthesised observer
    fire); matched by comparing ``event_ctx["self_discard_id"]`` to the source's own
    instance id, so it is strictly self-referential.

    Its SOURCE is the discarded card sitting in its owner's DISCARD pile, which no
    in-play scan can see — so ``_collect_triggers`` locates it by id via
    ``state.find_instance`` (which reaches the discard) and collects ONLY this trigger
    kind from it, exactly as the Rey LOF_148 "when you draw this card" scan does for a
    card sitting in hand.  A bespoke one-off discard that does not route through
    ``note_hand_or_deck_discard`` does not fire it (that helper's documented
    simplification)."""

@dataclass(frozen=True)
class WhenYouDiscardFromDeck:
    """Fires (as an observer) when the SOURCE's controller discards a card from their
    DECK — a mill, not a hand discard (Sebulba's Podracer LAW_176: "When you discard a
    card from your deck: You may ready this unit.  Use this ability only once each
    round").

    The deck-only narrowing of ``WhenThisIsDiscarded``, and the easier half of the
    pair: the source is an ordinary card IN PLAY, so the standard ``_collect_triggers``
    scan finds it and no dedicated discard-pile scan is needed.  Its ledger
    (``GameMemory.deck_discards``) is keyed by the MILLING PLAYER rather than by the
    milled card — the card that was milled has nothing to do with the observer — and
    is fed by ``actions.note_hand_or_deck_discard(..., from_deck=True)`` at the deck
    sites (``discard_from_deck``, the deck_search discard dispositions, the
    reveal-cull discard, Zuckuss LOF_204's mill), then drained at the action
    settle-point by ``actions._fire_deck_discard_observers``.  ``event`` is None (a
    synthesised observer fire); matched by comparing
    ``event_ctx["deck_discard_player_id"]`` to the source's own controller, so an
    opponent's self-mill does not fire it.

    "Only once each round" is NOT part of this trigger — use the shared
    ``Condition.SOURCE_ONCE_PER_ROUND_TRIGGER_AVAILABLE`` limiter (Toro Calican
    SHD_239), so declining the "you may" does not spend the round's use."""

@dataclass(frozen=True)
class WhenUnitHealed:
    """Fires (as an observer) when 1 or more damage is healed from the SOURCE unit
    itself (Silver Angel JTL_62: "When 1 or more damage is healed from this unit: You
    may deal 1 damage to a space unit.").

    Detection mirrors ``WhenPlayerDiscardsFromHand``: a dedicated ledger
    (``GameMemory.heal_events``) is fed from the single heal chokepoint
    (``actions.note_unit_healed``, which already ignores bases and no-op heals — so an
    entry IS "1 or more damage healed") and drained at the action settle-point
    (``actions.apply`` → ``_fire_heal_observers``) so the observer resolves on a clean
    stack.  ``event`` is None (a synthesised observer fire); matched by comparing
    ``event_ctx["healed_unit_id"]`` to the source's own instance id, so — unlike the
    any-player discard observer — this one is strictly self-referential.

    A bespoke card-module heal that pokes ``ci.damage`` directly bypasses the
    chokepoint and so does not fire it (the ``note_unit_healed`` simplification)."""

@dataclass(frozen=True)
class WhenUnitReadies:
    """Fires (as an observer) when the SOURCE unit readies (In Debt to Crimson Dawn
    JTL_192: "When attached unit readies: Exhaust it unless its controller pays 2
    resources" — wrapped in a ``GrantedAbility`` so the HOST is the source).

    The ``WhenUnitHealed`` shape verbatim: a dedicated ledger
    (``GameMemory.ready_events``) is fed by ``actions.note_unit_readied`` at the ready
    chokepoints — the regroup mass-ready ``_ready_all_cards`` and the ``ReadyCard``
    effect arm — and drained at the action settle-point (``actions.apply`` →
    ``_fire_ready_observers``) so the observer resolves on a clean stack.  ``event``
    is None (a synthesised observer fire); matched by comparing
    ``event_ctx["readied_unit_id"]`` to the source's own instance id, so it is
    strictly self-referential.  Only a card that WAS exhausted counts as readying.

    A bespoke card-module ready that pokes ``ci.exhausted`` directly bypasses the
    chokepoint and so does not fire it (the ``note_unit_healed`` simplification).

    ``controller`` widens it past the self-referential default: ``"enemy"`` fires for
    the source when an OPPONENT's unit readies ("When an enemy unit readies during
    the action phase: Ready this unit" — Rex's DC-17s TS26_63), compared through
    ``find_instance`` so the readied unit's current holder decides.  ``action_phase``
    reads the phase recorded WITH the ledger entry rather than the phase at drain
    time — the regroup mass-ready drains after the rollover into ACTION, so a
    drain-time read would let every regroup ready through."""

    controller: Optional[str] = None      # None = the source itself; "enemy"
    action_phase: bool = False            # only a ready that happened in ACTION


@dataclass(frozen=True)
class WhenUpgradeAttached:
    """Fires (as an observer) when 1 or more upgrades attach to THIS unit (Sabine
    Wren ASH_208: "When 1 or more upgrades attach to this unit (including from
    Shielded): You may exhaust a ground unit").

    The ``WhenFriendlyUpgradeDefeated`` settle-drain shape, mirrored: a dedicated
    ledger (``GameMemory.upgrade_attachments``) is fed by
    ``actions.note_upgrade_attached`` at the attachment chokepoints — the token path
    ``tokens.attach_token`` (which is how the parenthetical "including from
    Shielded" is satisfied) and the real-upgrade paths ``actions._attach_upgrade`` /
    ``_relocate_upgrade`` — and drained at the action settle-point, COALESCED per
    host so "1 or more" is exactly one firing.  ``event`` is None; matched by
    comparing ``event_ctx["upgrade_attached_host"]`` to the source's own instance.

    Self-referential, so unlike its defeat sibling there is no controller reading:
    the ledger names the HOST.  The feed is gated on a cached registry index, since
    every Shield / Experience / Advantage token attaches."""
    pass


@dataclass(frozen=True)
class WhenFriendlyUpgradeDefeated:
    """Fires (as an observer) when an upgrade the SOURCE's controller controls is
    defeated (Zeb Orrelios ASH_161: "When a friendly upgrade is defeated: Deal 1
    damage to a base").

    The ``WhenUnitReadies`` / ``WhenUnitHealed`` settle-drain shape: a dedicated
    ledger (``GameMemory.upgrade_defeats``) is fed by ``actions.note_upgrade_defeated``
    at the upgrade-defeat sites — the explicit ``_defeat_attached_upgrade`` /
    ``resolver._apply_defeat_unit`` paths, the host's own defeat (its upgrades go with
    it) and the token-defeat helpers — and drained at the action settle-point
    (``actions.apply`` → ``_fire_upgrade_defeat_observers``) so the observer resolves
    on a clean stack.  ``event`` is None; matched by comparing
    ``event_ctx["upgrade_defeat_controller"]`` to the source's controller.

    In SWU a Shield / Experience / **Advantage** token IS an upgrade, so this fires
    for a spent Shield and for the ASH Advantage tokens expiring after combat — which
    is exactly why ASH prints the trigger."""


@dataclass(frozen=True)
class WhenYouWouldCreateTokens:
    """Fires (as an observer) when the SOURCE's controller creates one or more tokens
    (Moff Jerjerrod ASH_94: "If you would create a number of tokens, you may defeat
    this unit.  If you do, create twice that number of tokens instead").

    The ``WhenFriendlyUpgradeDefeated`` settle-drain shape: a ledger
    (``GameMemory.token_creations``) is fed at the THREE creation chokepoints
    (``tokens.attach_token``, ``tokens.create_credit_token``,
    ``actions._create_token_units``) and drained at the action settle-point
    (``actions.apply`` → ``_fire_token_creation_observers``), which COALESCES
    equal-keyed records so a two-call "give 2 Experience tokens" is one creation of 2.
    ``event`` is None; matched by comparing ``event_ctx["token_creation_creator"]`` to
    the source's controller.  The event_ctx also carries ``token_creation_kind`` /
    ``_name`` / ``_count`` / ``_host`` / ``_ready``, which is everything
    ``actions.apply_token_creation`` needs to create that many more of the same.

    DOCUMENTED DEVIATION — this models a REPLACEMENT effect as an after-the-fact
    top-up: the printed card creates 2N tokens instead of N, whereas here N are
    created normally and the observer offers another N once the action settles.  The
    resulting board state is the same; what differs is that the tokens arrive in two
    batches and the defeat happens after the first batch, not before it.  A true
    replacement would need a decision pushed from inside a creation, i.e. the
    replacement-effect machinery the engine deliberately does not have."""


@dataclass(frozen=True)
class WhenBountyCollected:
    """Fires (as an observer) when the source card's controller *collects a bounty*
    (Bossk SHD_10 deployed: "When you collect a bounty: You may collect that bounty
    again.  Use this ability only once each round.").

    Detection mirrors ``WhenYouUseForce`` / ``WhenYouRevealOrDiscard`` exactly.  A
    bounty is a WhenDefeated ability flagged ``is_bounty`` (printed "Bounty — …" or
    granted by a bounty upgrade); it resolves for the COLLECTOR = the opponent of the
    dying unit's controller.  ``resolver.fire_triggered_abilities`` records ONE ledger
    entry into ``GameMemory.bounties_collected`` the moment such an ability is
    collected on a ``UnitDefeated`` — carrying the collector id and the bounty's
    registry coordinates (set/number/ability_idx/source_id) plus the dying unit's
    controller-at-death (so the re-run can recompute the same collector).  That ledger
    is drained at the action settle-point (``actions.apply`` →
    ``_fire_bounty_observers``) so the observer resolves on a clean stack rather than
    mid-``_defeat_unit``.  ``event`` is None (a synthesised observer fire).  Matched
    via ``event_ctx["bounty_collector_id"] == source_ci.owner_id`` ("when YOU collect
    a bounty").  Collected by the ordinary in-play arena scan (Bossk is a deployed
    leader in an arena).

    The re-collection ("collect that bounty again") re-runs the recorded bounty via a
    fresh ``resolve_effects`` decision (``actions.push_bounty_recollect``), so it needs
    no new decision kind.  The once-per-round limiter is the
    ``SOURCE_BOUNTY_RECOLLECT_AVAILABLE`` condition on Bossk's ability (marked spent
    when the re-run resolves); the re-run does not itself record a ledger entry (it
    bypasses the collection scan), so it cannot chain."""


@dataclass(frozen=True)
class OnAttackDefeatsUnit:
    """Fires when this unit defeats a unit via combat damage."""

@dataclass(frozen=True)
class WhenFriendlyUnitAttacksAndDefeatsUnit:
    """The GROUP analogue of ``OnAttackDefeatsUnit``: fires for an OBSERVER when a
    unit its controller controls attacked and defeated a unit (Darth Revan LOF_17:
    "When a friendly unit attacks and defeats a unit: …").

    Matched at the same firing site off the same ``attack_defeated_unit`` event_ctx
    key, so "the attacker survived and the defender died" is equally intrinsic; the
    only extra test is that the attacker is controlled by the observer's controller.
    The source itself is NOT excluded — a deployed leader that attacks and kills is
    "a friendly unit" by the printed reading.  The attacking unit's id stays in
    ``event_ctx["attack_defeated_unit"]``, which is how an effect refers to "that
    friendly unit"."""

@dataclass(frozen=True)
class WhenYouPlayCard:
    """Fires when the source card's controller plays ANOTHER card (any type —
    unit, event, or upgrade) matching the filter.

    Matches the ``CardPlayed`` event (the single event every play path emits),
    so it covers Aggression *events* and *upgrades*, not just units — unlike
    ``WhenPlayed`` which fires only for the played card itself.  ``aspect``
    (e.g. "Aggression") narrows to cards bearing that aspect; ``card_type``
    (e.g. "upgrade") narrows to a played card of that type ("When you play an
    upgrade", The Mandalorian SHD_18); ``exclude_self`` drops the source's own
    play ("another").  Used by Fighters for Freedom (SOR_143): "When you play
    another [Aggression] card: ...".
    """
    aspect: Optional[str] = None
    card_type: Optional[str] = None
    trait: Optional[str] = None
    unique: bool = False          # narrow to a played *unique* card ("another
                                  # unique unit" — Luke Skywalker LOF_249)
    on_self: bool = False         # narrow to a played upgrade attached to the
                                  # source unit ("an upgrade on this unit" —
                                  # Kylo Ren LOF_229)
    cost_min: Optional[int] = None  # narrow to a played card whose printed cost
                                    # is >= this ("a unit that costs 4 or more" —
                                    # Grogu ASH_18)
    via_smuggle: bool = False       # narrow to a card played USING the Smuggle
                                    # keyword ("When you play a card using Smuggle"
                                    # — Hondo Ohnaka SHD_5); reads the same
                                    # event_ctx["via_smuggle"] flag WhenPlayedViaSmuggle
                                    # keys on, so it fires for any smuggle play, not
                                    # only the source's own.
    has_any_keyword: bool = False   # narrow to a played card that has ≥1 keyword
                                    # from any source ("a unit that has 1 or more
                                    # keywords" — Boba Fett SHD_8); read via the
                                    # effective keyword layer (keywords.has_any_keyword).
    non_unit: bool = False          # narrow to a played card that is NOT a Unit —
                                    # "When you play a non-unit card" (Tobias Beckett
                                    # SHD_217); records event_ctx["cost_le_threshold"]
                                    # like the other filters so an effect can target
                                    # "a unit that costs the same as or less than the
                                    # card you played".
    exclude_self: bool = True

@dataclass(frozen=True)
class WhenOpponentPlaysNthCard:
    """Fires for the source card (an observer) when an OPPONENT of the source's
    controller plays their ``count``-th card of the current phase.

    Matches the ``CardPlayed`` event (the single event every play path emits) whose
    player is an opponent, gated on a per-phase per-player play counter
    (``GameMemory.cards_played_this_phase``, incremented at the ``CardPlayed`` firing
    chokepoint in ``fire_triggered_abilities`` *before* trigger collection, so the
    matcher sees the post-increment count).  Fires on exactly the ``count``-th play
    (``== count``, not ``>=``), so "their second card each phase" fires once per
    phase per opponent.  Ki-Adi-Mundi (TWI_64 / J25_2): "Coordinate — When an
    opponent plays their second card each phase: You may draw 2 cards." (The
    Coordinate prefix is the ``CONTROLLER_N_PLUS_UNITS`` condition on the ability,
    gating trigger collection.)
    """
    count: int = 2

@dataclass(frozen=True)
class WhenOpponentPlaysCard:
    """Fires for the source card (an observer, e.g. a unit in play) when an OPPONENT
    of the source's controller plays a card matching ``card_type``.

    Matches the ``CardPlayed`` event (the single event every play path emits) whose
    player is an opponent; ``card_type`` (e.g. "event") narrows to a played card of
    that type.  Used to model Saw Gerrera (SOR_158... no, SOR_153): "As an additional
    cost for each opponent to play an event, they must deal 2 damage to their base" —
    a **documented simplification** of the additional cost as an after-the-fact
    observer that deals 2 to the event player's base (base damage is always payable,
    so modelling the cost as a triggered effect yields the same board state; see the
    card docstring).  The DealDamage(controller="enemy", kind="base") auto-resolves to
    the single opponent's base (the event player's, in 2-player).

    ``paid_less_than_cost`` narrows it to a DISCOUNTED play — the ``CardPlayed``
    event's ``cost_paid`` is below the card's printed cost ("If that opponent paid
    less than the card's cost to play it", Lux Bonteri TWI_210)."""
    card_type: Optional[str] = None
    paid_less_than_cost: bool = False

@dataclass(frozen=True)
class WhenUnitAttacks:
    """Fires for the source card (an observer, e.g. a Base) when ANY unit matching
    ``filter`` is declared as an attacker.

    Matches the ``AttackDeclared`` event for an attacker satisfying ``filter`` from
    the source's perspective (so ``controller="friendly"`` means the source's own
    unit attacked).  Unlike ``OnAttack`` (which fires only for the attacking unit
    itself), this lets a *different* card observe attacks — Jedi Temple LOF_23:
    "When a friendly Force unit attacks: create your Force token".  The source is
    collected even from base_zone (a Base), see resolver._collect_triggers.
    """
    filter: TargetSpec = field(default_factory=lambda: TargetSpec())

@dataclass(frozen=True)
class WhenDealsCombatDamageToBase:
    """Fires when this unit deals combat damage to a base (a direct base attack).

    Detected via the ``dealt_combat_damage_to_base`` event-context key set at the
    base-combat damage step (mirroring the ``attack_defeated_unit`` key that backs
    OnAttackDefeatsUnit), so it needs no dedicated event class.  Used by Ketsu
    Onyo (SHD_147): "When this unit deals combat damage to a base: ...".

    ``filter`` turns it into the OBSERVER form (the ``WhenFriendlyUnitDealtCombatDamage``
    shape): a *different* card — typically a Base — fires when any unit matching the
    spec from the source's perspective dealt the damage, instead of the default
    self-match.  ``min_amount`` additionally requires the attack to have dealt at
    least that much (``base_combat_damage_amount`` in the same event_ctx).  Together
    they cover Temple of Destruction LOF_25: "When a friendly unit deals 3 or more
    combat damage to an enemy base: …" (a friendly unit attacking a base always hits
    the *enemy* base, so ``controller="friendly"`` is the whole filter).
    """
    filter: Optional["TargetSpec"] = None
    min_amount: int = 0

@dataclass(frozen=True)
class WhenDealtCombatDamage:
    """Fires when this unit is dealt combat damage and survives it.

    Covers being damaged either as the attacker (the defender deals damage back)
    or as the defender.  Detected via the ``dealt_combat_damage_to`` event-context
    key set at the unit-combat damage step (mirroring ``dealt_combat_damage_to_base``
    for OnAttack/Ketsu Onyo), so it needs no dedicated event class; the firing site
    fires it only for a unit still in play after defeat processing, so the "if it
    survives the damage" clause is intrinsic.  Used by Phase-III Dark Trooper
    (SHD_84): "When combat damage is dealt to this unit: Give an Experience token
    to this unit (if it survives the damage)".
    """

@dataclass(frozen=True)
class WhenDealsCombatDamageToUnit:
    """Fires for the ATTACKER when it deals combat damage to a defending unit.

    The mirror of ``WhenDealtCombatDamage`` (which fires for the DAMAGED unit): this
    fires for the unit that *dealt* the damage, so an attacker can react to hitting a
    unit that survived the blow.  Detected via the
    ``attacker_dealt_combat_damage_to_unit`` event-context key set at the unit-combat
    damage step (mirroring ``dealt_combat_damage_to``), so it needs no dedicated
    event class; the firing site only sets it for an attacker still in play whose
    defender unit is still in play, so "while attacking" is intrinsic and "that unit"
    (``event_ctx["defender_id"]``, a live unit) is a valid ``DEFENDER`` target.  With
    ``non_leader_only`` the trigger is suppressed when the defender is a leader unit.
    Used by Rukh (SOR_85): "When this unit deals combat damage to a non-leader unit
    while attacking: Defeat that unit."
    """
    non_leader_only: bool = False


@dataclass(frozen=True)
class WhenFriendlyUnitDealsCombatDamageToEnemyUnit:
    """Fires for an OBSERVER when any unit its controller controls deals combat damage
    to an enemy unit — the group analogue of ``WhenDealsCombatDamageToUnit`` (which
    fires only for the dealing unit itself), just as
    ``WhenFriendlyUnitDealtCombatDamage`` is the group analogue of
    ``WhenDealtCombatDamage``.

    Reuses the same ``attacker_dealt_combat_damage_to_unit`` / ``defender_id`` keys and
    the same firing site, so "that enemy unit" is a live ``DEFENDER`` target and the
    survivor clause is intrinsic.  The site is the ATTACKING side of combat, so a
    friendly *defender* striking back is not covered — a documented simplification (the
    printed cards that use this wording are all attack-facing), and neither is
    non-combat ability damage.  The source is excluded (a unit "deals damage" to an
    enemy on its own is the WhenDealsCombatDamageToUnit case).  Jango Fett TWI_16:
    "When a friendly unit deals damage to an enemy unit: You may exhaust that unit."
    """


@dataclass(frozen=True)
class WhenAttackEnds:
    """Fires for the attacking unit when its attack ends, if the unit survived.

    Detected via the ``attack_ended_survivor`` event-context key set at the very
    end of both combat pipelines (unit-vs-unit and unit-vs-base), mirroring the
    ``attack_defeated_unit`` / ``dealt_combat_damage_to`` keys: the firing site
    only sets it for an attacker that is still in play after defeat processing, so
    the "if this unit survived" clause is intrinsic (a base attack never damages
    the attacker, so it always survives there).  Used by Vermillion (LAW_215):
    "When Attack Ends: If this unit survived, reveal the top card of a deck …".

    ``require_base_damage`` narrows the trigger to the case where the attack dealt
    combat damage to a base — the base-attack pipeline additionally carries the
    ``dealt_combat_damage_to_base`` key on this fire (Maul LAW_54: "When Attack
    Ends: If this unit dealt combat damage to a player's base, …").

    ``require_defender_defeated`` narrows it to an attack whose DEFENDING UNIT died
    — "When Attack Ends: If the defending unit was defeated, ready this unit" (Grand
    Admiral Thrawn ASH_33, Halo ASH_223).  Both unit-combat pipelines now also carry
    ``attack_ended_defender_defeated`` on this fire, the same key the
    ``WhenFriendlyUnitAttackEnds`` observer already reads at its own separate fire;
    that observer keys on ``attack_ended_attacker``, which this fire never sets, so
    the shared key cannot make either family fire twice.  A base attack sets no such
    key, so the clause correctly never fires there.
    """
    require_base_damage: bool = False
    require_defender_defeated: bool = False

@dataclass(frozen=True)
class WhenFriendlyUnitDealtCombatDamage:
    """Observer trigger: fires for its source when ANY unit its controller controls
    (optionally filtered by ``traits``) is dealt combat damage and survives it.

    The group analogue of ``WhenDealtCombatDamage`` (which fires only for the
    damaged unit itself): where that trigger matches
    ``event_ctx["dealt_combat_damage_to"] == source_ci.instance_id``, this one
    matches when that id names a *friendly* unit carrying every listed trait.  The
    source is therefore an observer standing apart from the damaged unit — but it
    also fires when the source IS the damaged unit, which is what "a friendly
    Wookiee unit" means for a Wookiee (Tarfful SHD_250: "When a friendly Wookiee
    unit is dealt combat damage and isn't defeated: That unit deals that much
    damage to an enemy ground unit").

    Reuses the existing firing site verbatim, which only fires for a unit still in
    play after defeat processing — so "and isn't defeated" is intrinsic, exactly as
    for ``WhenDealtCombatDamage``.  That site also records the amount dealt in
    ``event_ctx["combat_damage_amount"]``, so "that much damage" resolves through
    ``DealDamageEqualTo(count="event_combat_damage")``.
    """
    traits: tuple = ()

@dataclass(frozen=True)
class PhaseStartTrigger:
    """"When the <phase> phase starts" — matched against the ``PhaseChanged`` event
    fired at a phase transition.  ``first_only`` narrows it to the FIRST such phase
    of the game ("When the first action phase starts" — Nabat Village JTL_28), read
    off the event's ``round_number``."""
    phase: str  # "action" | "regroup"
    first_only: bool = False

@dataclass(frozen=True)
class WhenYouTakeInitiative:
    """Fires for its source when its CONTROLLER claims the initiative ("When you take
    the initiative: Deal 2 damage to a base" — Ziton Moj SEC_168).

    Matched against the ``InitiativeTaken`` event fired by ``actions.ClaimInitiative``,
    which now also runs the trigger pipeline (right after the existing
    ``_consume_pending_initiative_effects`` — the pre-armed "next time you take the
    initiative" charges, Premonition of Doom LOF_203, which are effects rather than
    printed abilities).  Only the claiming player's own cards fire: the matcher
    compares the event's ``player_id`` against the source's controller."""


@dataclass(frozen=True)
class RoundStartTrigger:
    pass


# ── Ability specs ─────────────────────────────────────────────────────────────
@dataclass
class TriggerAbility:
    trigger: object    # one of the TriggerCondition types above
    effects: list      # list of Effect primitives
    optional: bool = False
    deployed_only: bool = False    # only fires when source leader is deployed
    undeployed_only: bool = False  # only fires when source leader is undeployed
    condition: Optional[ConditionCheck] = None  # gate: the trigger is not even
                                    # collected/offered unless this holds (e.g.
                                    # Luke's Lightsaber only on Luke Skywalker)
    is_bounty: bool = False         # this WhenDefeated trigger is a printed/granted
                                    # "Bounty — …" ability (resolves for the COLLECTOR,
                                    # the opponent of the dying unit's controller).
                                    # Marks the ability so that its collection is
                                    # recorded in the bounties-collected ledger and
                                    # fires the WhenBountyCollected observer — the sole
                                    # hook the re-collection payoff (Bossk SHD_10) reads.
                                    # Purely a tag: default-False leaves every other
                                    # WhenDefeated ability (which is NOT a bounty)
                                    # untouched.

@dataclass
class ConstantAbility:
    """A passive buff that applies continuously while the source is in play."""
    target: TargetSpec
    effects: list      # list of StatBonus or KeywordGrant
    condition: Optional[ConditionCheck] = None
    while_attacking_unit: bool = False  # when True, the StatBonus contributions of
                                    # this ability apply ONLY to a target that is
                                    # currently attacking an enemy *unit* (Moff
                                    # Gideon SHD_7: "+1/+0 … while attacking an
                                    # enemy unit").  The keyword query layer does
                                    # not see combat context, so any KeywordGrant
                                    # this ability also carries is reported always
                                    # — harmless for Overwhelm, which only matters
                                    # when attacking a unit anyway.
    while_defending: bool = False   # when True, the StatBonus contributions of this
                                    # ability apply to its target ONLY while the
                                    # *source* is the current combat defender (Lando
                                    # Calrissian LAW_108: "While this unit is
                                    # defending, the attacker gets −1/−0").  The
                                    # target spec selects the attacker (an enemy
                                    # unit); compute_power threads the defender's id
                                    # so the debuff lands only on the unit attacking
                                    # this source.  Skipped entirely by compute_hp
                                    # (no combat context there).
    while_target_defending: bool = False  # the mirror of ``while_defending``: the
                                    # StatBonus applies to its *target* ONLY while
                                    # that target is itself the current combat
                                    # defender (Jyn Erso SOR_18 deployed: "While a
                                    # friendly unit is attacking, the defender gets
                                    # −1/−0").  The target spec selects the enemy
                                    # unit being attacked; compute_power passes
                                    # ``is_defending`` when computing the defender's
                                    # power so the debuff lands only mid-combat.
    while_attacking: bool = False   # attacker-SCOPED variant of
                                    # ``while_target_defending``: the StatBonus
                                    # applies to its target ONLY while the *source*
                                    # is the current combat attacker (Strafing
                                    # Gunship SOR_212: "While THIS unit is attacking a
                                    # ground unit, the defender gets −2/−0").  The
                                    # target spec selects the defender; compute_power
                                    # threads the attacker's id so the debuff lands
                                    # only when this specific attacker is attacking
                                    # (not, like Jyn, for any friendly attacker).
    while_attacking_bounty_unit: bool = False  # like ``while_attacking_unit`` but the
                                    # StatBonus applies ONLY while the target is
                                    # attacking a unit that HAS A BOUNTY (Jango Fett
                                    # SHD_138: "While attacking a unit with a Bounty,
                                    # this unit gets +3/+0 …").  compute_power checks the
                                    # threaded ``defender_id`` via resolver._unit_has_
                                    # bounty; any KeywordGrant it also carries (Jango's
                                    # Overwhelm) is reported always by the keyword layer
                                    # (the Moff Gideon SHD_7 simplification).
    while_attacking_damaged_unit: bool = False  # like ``while_attacking_unit`` but the
                                    # StatBonus applies ONLY while the target is
                                    # attacking a DAMAGED unit ("This unit gets +2/+0
                                    # while attacking a damaged unit" — Marrok's Fiend
                                    # Fighter ASH_241).  The exact sibling of
                                    # ``while_attacking_bounty_unit``: compute_power
                                    # reads the threaded ``defender_id`` and checks
                                    # ``damage > 0``; compute_hp skips it (combat-only).
    while_attacking_unit_arena: Optional[str] = None  # narrows
                                    # ``while_attacking_unit`` to a defender in this
                                    # arena ("ground"/"space") — "While attacking a
                                    # SPACE unit, this unit gets −1/−0" (Retrofitted
                                    # Airspeeder JTL_259, a ground unit reaching space
                                    # via CrossArenaAttack).  Checked at the same
                                    # compute_power site against the threaded
                                    # ``defender_id``; None = any arena, the plain
                                    # ``while_attacking_unit`` behaviour.
    upgrade_only: bool = False      # this ability exists ONLY while the card is
                                    # attached as an UPGRADE — "Attached unit gains
                                    # <X>" on a card that can also be played as a
                                    # UNIT (a Pilot: Jarek Yeager JTL_109).  A
                                    # ``ConstantAbility(target=SELF)`` is read by two
                                    # different scans: the attached-upgrade scans
                                    # (``keywords.has_keyword`` / ``keyword_value`` /
                                    # ``actions._upgrade_self_stat_bonus``), which
                                    # confer it on the HOST — what the card means —
                                    # and the ARENA scans (``keywords`` /
                                    # ``_constant_ability_power_bonus`` /
                                    # ``_constant_ability_hp_bonus``), which walk
                                    # in-play units by (set, number) with no upgrade
                                    # gate and would ALSO confer it on the card's own
                                    # unit side.  That leak is harmless only when the
                                    # card prints what it grants; this flag closes it
                                    # by making the ARENA scans skip the spec, leaving
                                    # the attached scans unchanged.  Default False, so
                                    # every existing ConstantAbility is untouched.
    via_host: bool = False          # this ability is an AURA that an UPGRADE confers
                                    # on OTHER cards, resolved as if the attached HOST
                                    # were its source — "Attached unit gains: 'While
                                    # this unit is ready, each other friendly unit
                                    # gains …'" (Figure of Unity SEC_104).  The
                                    # ordinary arena scans only ever see units, and the
                                    # attached-upgrade scans only handle
                                    # ``target=SELF`` (the host itself), so neither can
                                    # express an upgrade-borne aura over a THIRD card.
                                    # With this flag the keyword scans (and, since
                                    # Fulcrum LAW_150, the constant-STAT scans, through
                                    # ``actions._via_host_stat_bonus``) also walk each
                                    # arena unit's attached upgrades and evaluate the
                                    # spec's condition and target with the HOST as
                                    # ``source_ci`` — so "this unit" is the host and
                                    # "friendly"/"not_self" are relative to it.  The
                                    # mirror of ``upgrade_only``: that flag hides a
                                    # spec from the arena scans, this one adds an
                                    # upgrade to them.  Default False.
    undeployed_only: bool = False   # this aura belongs to a LEADER's UNDEPLOYED side
                                    # ("Each friendly unit with the most power among
                                    # friendly units gains Overwhelm" — Savage Opress
                                    # TS26_5's text box, whose deployed box says
                                    # something else).  Every other leader
                                    # ConstantAbility is deployed-only for free
                                    # because the scans walk the ARENAS and an
                                    # undeployed leader sits in ``base_zone``; this
                                    # flag inverts that — the spec is SKIPPED by the
                                    # arena scans and read instead by the base-zone
                                    # pass in ``keywords.has_keyword`` /
                                    # ``keyword_value`` (gated on a cached registry
                                    # index, so that pass never runs for a board with
                                    # no such card).  KEYWORD layers only — no card
                                    # yet needs an undeployed StatBonus aura.

@dataclass
class ActivatedAbility:
    """An ability the controller can use by paying costs during their action."""
    costs: list        # list of CostSpec (ExhaustSelf, PayResources, DefeatSelf)
    effects: list      # list of Effect primitives
    title: str = "Action"
    once_per_round: bool = False
    epic: bool = False              # once per game (non-deploy epic actions)
    deployed_only: bool = False     # only available when source leader is deployed
    undeployed_only: bool = False   # only available when source leader is undeployed
    condition: Optional[ConditionCheck] = None  # gate availability (e.g. Vader's
                                    # "If you played a Villainy card this phase")
    any_player: bool = False        # "Any player may use this ability" (Mercenary
                                    # Gunship SHD_256).  Normally an activated
                                    # ability is enumerated only for the card's
                                    # controller and ``UseAbility`` rejects a
                                    # non-owner; with this flag ``legal_actions``
                                    # also offers it to the opponent and the
                                    # ownership guard is lifted.  Costs are always
                                    # paid by the player USING it (the active
                                    # player), so an opponent pays from their own
                                    # resources — which is what makes "any player"
                                    # meaningful.  Still an action, so it can only
                                    # be used on that player's own turn.
    extra_action: bool = False      # "Take an extra action after this one"
                                    # (Kazuda Xiono JTL_18).  Using an ability
                                    # normally hands the turn over; with this flag
                                    # ``UseAbility.apply`` keeps the seat — the
                                    # inline path skips ``_switch_active_player``
                                    # and the deferred path sets the decision's
                                    # ``after_resolve_player_index`` to the user, so
                                    # the same player acts again either way.  Purely
                                    # a who-is-active choice: no change to how the
                                    # ability itself resolves.

@dataclass
class PlayFromDiscardAction:
    """An ``Action:`` printed on a card that plays it FROM ITS OWNER'S DISCARD
    PILE, paying its printed cost, gated on ``condition`` (Brutal Traditions
    SHD_38: "Action: If an enemy unit was defeated this phase, play this upgrade
    from your discard pile (paying its cost)").

    Unlike ``ActivatedAbility`` — collected only from cards *in play* — this spec
    is scanned by ``actions.legal_actions`` over the active player's *discard
    pile*, making the discard pile a new legal-action SOURCE.  For an Upgrade it
    is enumerated per legal host (each affordable "Attach to …" target = one
    ``PlayFromDiscard`` action); the play pays the card's normal cost via
    ``_play_cost``/``_pay_play_cost`` and fires ``CardPlayed`` + the card's own
    WhenPlayed triggers exactly like a hand play, so it is indistinguishable
    downstream from an ordinary play.  ``condition`` is evaluated against the
    card's owner (None = always available while in discard)."""
    condition: Optional[ConditionCheck] = None


@dataclass
class EventAbility:
    """The effect of an Event card when played."""
    effects: list      # list of Effect primitives

@dataclass
class CostReduction:
    """Card-level play-cost reducer (e.g. Force Choke SOR_139: "If you control a
    Force unit, this event costs 1 resource less to play").

    Unlike an effect, this is read by the play-cost path *before* the card is
    played, so it affects both affordability in ``legal_actions`` and the
    resources actually exhausted in ``PlayCard``.  ``amount`` is the reduction
    (positive number); ``condition`` gates it (None = always).  The play path
    floors the final cost at 0.  Multiple CostReductions on one card stack.
    """
    amount: int
    condition: Optional[ConditionCheck] = None
    host_named: Optional[str] = None  # upgrade-only: the reduction applies only
                                      # when the upgrade is being attached to a host
                                      # unit whose name contains this string
                                      # ("While playing this upgrade on General
                                      # Grievous, it costs 2 resources less" —
                                      # Grievous's Wheel Bike TWI_236).  Read by the
                                      # play-cost path, which knows the chosen host.
    per_controller_base_damage: Optional[int] = None
                                      # SCALING reduction: instead of a flat
                                      # ``amount``, reduce by ``amount`` once for
                                      # every this-many damage on the controller's
                                      # base ("costs 1 resource less to play for
                                      # every 5 damage on your base" — Resolute
                                      # TWI_151 → amount=1, this=5).  Integer
                                      # division, so 12 damage ⇒ 2.  Read at the same
                                      # single play-cost site; None = flat ``amount``.
    per_max_opponent_units: bool = False
                                      # SCALING reduction: ``amount`` once for every
                                      # unit controlled by the opponent who controls
                                      # the MOST units ("costs 1 resource less to play
                                      # for each unit controlled by the opponent who
                                      # controls the most units" — Republic Defense
                                      # Carrier TWI_98 → amount=1, this=True).  With
                                      # two players that is simply the single
                                      # opponent's unit count (both arenas, deployed
                                      # leaders included — the CONTROLLER_N_PLUS_UNITS
                                      # basis).  Read at the same single play-cost
                                      # site; False = flat ``amount``.
    per_friendly_pilots: bool = False
                                      # SCALING reduction: ``amount`` once for every
                                      # friendly Pilot UNIT and every friendly Pilot
                                      # UPGRADE ("costs 1 resource less to play for
                                      # each friendly Pilot unit and upgrade" — Red
                                      # Leader JTL_101 → amount=1, this=True).  The
                                      # ``other_friendly_pilots`` StatBonus count
                                      # basis (Nien Nunb JTL_93) without its
                                      # self-exclusion: the card is still in hand
                                      # when the play-cost path reads this, so it
                                      # cannot count itself.  Read at the same single
                                      # play-cost site; False = flat ``amount``.
    per_controller_card_played_this_phase: bool = False
                                      # SCALING reduction: ``amount`` once for every
                                      # OTHER card the controller played this phase
                                      # ("costs 2 resources less to play for each
                                      # other card you played this phase" — Tribunal
                                      # TS26_36).  Read off the
                                      # ``cards_played_this_phase`` counter, which is
                                      # incremented AFTER the cost is paid, so the
                                      # card never counts itself.
    per_friendly_units: bool = False  # SCALING reduction: ``amount`` once for every
                                      # friendly UNIT, trait-blind, either arena
                                      # ("costs 1 resource less to play for each
                                      # friendly unit" — Encircle TS26_61).  The
                                      # ``per_friendly_trait`` basis with the filter
                                      # dropped; the card being played is in hand, so
                                      # it never counts itself.
    per_friendly_trait: Optional[str] = None
                                      # SCALING reduction: ``amount`` once for every
                                      # friendly UNIT with this trait ("costs 1
                                      # resource less to play for each friendly Droid
                                      # unit" — Vuutun Palaa SEC_122 →
                                      # amount=1, this="Droid").  The
                                      # ``per_friendly_pilots`` basis narrowed to
                                      # units alone (no upgrade leg) and
                                      # parameterised by trait; trait GRANTS count,
                                      # since the board is read through
                                      # ``traits.has_trait``.  The card being played
                                      # is still in hand, so it never counts itself.
                                      # Read at the same single play-cost site;
                                      # None = flat ``amount``.
    host_trait: Optional[str] = None  # upgrade-only: the reduction applies only when
                                      # the chosen host unit has this EFFECTIVE trait
                                      # ("This upgrade costs 1 resource less to play
                                      # on an Imperial unit" — Faith in the Empire
                                      # ASH_262).  The ``host_named`` sibling keyed on
                                      # a trait; no host chosen yet ⇒ no reduction.
    host_unique: bool = False         # upgrade-only: the reduction applies only when
                                      # the chosen host unit carries the <uq> symbol
                                      # ("This upgrade costs 1 resource less to play
                                      # on a unique unit" — Mastery LAW_129).  The
                                      # ``host_named`` sibling one step more general:
                                      # a property of the host rather than its name.
                                      # Read at the same play-cost site, which knows
                                      # the chosen host; with no host chosen yet
                                      # (affordability before the pick) it does not
                                      # apply, so the offer is never over-generous.
    per_friendly_damaged_unit: bool = False
                                      # SCALING reduction: ``amount`` once for every
                                      # DAMAGED unit the CONTROLLER controls, either
                                      # arena ("costs 1 resource less to play for each
                                      # friendly damaged unit" — Phoenix Squadron
                                      # Fighters LAW_110 → amount=1, this=True).  The
                                      # ``per_damaged_ground_unit`` basis with the
                                      # arena filter swapped for a controller one.
                                      # Read at the same single play-cost site;
                                      # False = flat ``amount``.
    per_damaged_ground_unit: bool = False
                                      # SCALING reduction: ``amount`` once for every
                                      # DAMAGED unit in a ground arena ("costs 1
                                      # resource less to play for each damaged ground
                                      # unit" — AT-DP Occupier JTL_163 → amount=1,
                                      # this=True).  "Each damaged ground unit" is
                                      # unqualified, so BOTH players' ground arenas
                                      # count (the ``damaged_units_in_play`` StatBonus
                                      # basis, War Juggernaut JTL_170, narrowed to the
                                      # ground arena).  Read at the same single
                                      # play-cost site; False = flat ``amount``.
    per_friendly_leader_unit: bool = False
                                      # SCALING reduction: ``amount`` once for every
                                      # LEADER UNIT the controller controls — a
                                      # DEPLOYED leader standing in an arena, or an
                                      # ordinary unit carrying a leader as a Pilot
                                      # upgrade ("This event costs 1 resource less to
                                      # play for each friendly leader unit" — Take
                                      # Action TS26_71 → amount=1, this=True).  Shares
                                      # ``resolver._is_leader_unit`` with the
                                      # ``leader_unit`` predicate, so the two readings
                                      # of "leader unit" can never drift apart; an
                                      # UNDEPLOYED leader sits in the base zone and is
                                      # no unit, so it does not count.  Read at the
                                      # same single play-cost site; False = flat
                                      # ``amount``.
    per_controller_discard_this_phase: bool = False
                                      # SCALING reduction: ``amount`` once for every
                                      # card the CONTROLLER discarded this phase
                                      # ("costs 1 resource less to play for each card
                                      # discarded from your hand this phase" — Fear
                                      # and Dead Men LAW_179 — amount=1, this=True),
                                      # counted off the game_memory
                                      # ``cards_discarded_this_phase`` ledger with the
                                      # owner read back from each instance (the LAW_76
                                      # trick).  DOCUMENTED WIDENING: that ledger is
                                      # fed by hand AND deck discards alike, so a
                                      # self-mill also counts.  Read at the same single
                                      # play-cost site; False = flat ``amount``.

@dataclass
class EntersPlayReady:
    """Conditional enter-play-ready spec: "this unit enters play ready" (Salacious
    Crumb LAW_210: "If you control Jabba the Hutt, this unit enters play ready").

    Read by ``actions._put_unit_in_play`` when the source itself enters play: if a
    registered ``EntersPlayReady`` spec's ``condition`` holds (or is None), the
    unit enters ready instead of the default exhausted.  ``condition`` is evaluated
    against the source's controller at the moment it enters play.  Purely a read at
    the enter-play placement — no trigger, no decision; with no such spec the
    enter-play behaviour is unchanged."""
    condition: Optional[ConditionCheck] = None


@dataclass(frozen=True)
class KeywordIfPlayedFromHand:
    """Constant marker: the source unit gains ``keyword`` when — and only when — it
    is played from its owner's hand (Millennium Falcon SHD_204: "If you play this
    unit from your hand, it gains Ambush").

    Read by ``actions._put_unit_in_play`` at the enter-play placement: if the unit
    entered via a hand play (``play_source == "hand"``) and a ``KeywordIfPlayedFromHand``
    spec is registered, the keyword is granted (a this-phase modifier applied BEFORE
    the enter-play keyword bus, exactly like the ``grant_keyword`` ability path) so a
    granted Ambush triggers on entry.  A Smuggle / discard / plot / token entry does
    NOT grant it.  The printed keyword the API mistags on such a card is stripped by
    the keyword sanitiser (rule 6) so the marker — not an always-on printed bar —
    owns it.  Purely a read at placement — no trigger, no decision; with no such spec
    the enter-play behaviour is unchanged.  Mirrors the ``EntersPlayReady`` passive
    marker."""
    keyword: str


@dataclass(frozen=True)
class AttackRestriction:
    """Constant marker: the source unit may declare an attack only while
    ``condition`` holds (Oggdo Bogdo LOF_63: "This unit can't attack unless it's
    damaged" = ``AttackRestriction(ConditionCheck(Condition.SOURCE_DAMAGED))``).

    Read only at the attack-enumeration seam (``actions._enumerate_attacks``, the
    chokepoint for both normal ACTION attacks and effect-granted attacks): a unit
    whose registered ``AttackRestriction`` condition is False is dropped from the
    legal attackers.  Purely a read at attack enumeration — no trigger, no
    decision; with no such spec attack enumeration is unchanged.  Mirrors the
    ``EntersPlayReady`` passive-marker pattern.

    ``condition=None`` is the unconditional bar — "This unit can't attack"
    (Corporate Defense Shuttle JTL_59) — matching the ``ReadyRestriction``
    convention where a ``None`` condition means "always"."""
    condition: Optional[ConditionCheck] = None


@dataclass(frozen=True)
class DoubleKeywordValue:
    """Constant marker: every unit matching ``target`` has its value for the numeric
    keyword ``keyword`` DOUBLED (Marchion Ro LOF_186: "Each friendly unit's Raid is
    doubled").

    Read only at the end of ``keywords.keyword_value`` — after every additive source
    (printed value, keyword_grant modifiers, ConstantAbility grants, attached
    upgrades, the copy aura) has been summed — so it multiplies the *effective*
    value, which is what "is doubled" means.  Purely a read there: no trigger, no
    decision, and ``has_keyword`` is untouched (doubling 0 is still 0, and a unit
    without the keyword never gains it).  Two doublers in play multiply twice, per
    the CR's independent-application reading.  Mirrors the ``AttackRestriction`` /
    ``CannotAttackBases`` passive-marker pattern."""
    keyword: str
    target: TargetSpec


@dataclass(frozen=True)
class CannotPlayFromHand:
    """Constant marker: "This card can't be played from your hand" (One in a Million
    SEC_53, a Plot event meant to be played only out of the resource zone).

    Read at the hand-play enumeration in ``actions.legal_actions`` (the card is simply
    not offered) with a defensive guard in ``PlayCard.apply``.  Deliberately NOT read
    by the Smuggle / Plot / play-from-discard paths, which are not "from your hand" —
    that is exactly the restriction's purpose.  A passive marker like
    ``CannotAttackBases``; no trigger, no decision."""


@dataclass(frozen=True)
class CannotAttackBases:
    """Constant marker: the unit carrying it (or its host, when the marker sits on
    an attached UPGRADE) can't declare an attack against a base (Entrenched SOR_72:
    "Attached unit can't attack bases").

    Read only at the attack-enumeration seam (``actions._cannot_attack_bases``,
    scanning both the attacker's own specs and its attached upgrades' specs): the
    base-attack option is dropped for that attacker, while its unit attacks are
    unaffected.  Purely a read there — no trigger, no decision.  Mirrors the
    ``AttackRestriction`` passive-marker pattern (but restricts only base targets)."""
    pass


@dataclass(frozen=True)
class TokensEnterPlayReady:
    """Constant marker: every token unit created under this card's controller enters
    play READY instead of exhausted (Chancellor Palpatine TWI_203: "Each token unit
    you create enters play ready").

    Read at the single token-creation seam (``actions._create_token_units``, which
    scans the creating player's in-play cards for this spec), so it applies to
    tokens made by ANY source — a When Played trigger, an event, another unit — not
    just the card carrying it.  ``CreateTokenUnit(enters_ready=True)`` is the
    per-effect version of the same thing; this is the board-wide one.  Purely a read
    there: no trigger, no decision.  Mirrors ``CannotAttackBases``."""
    pass


@dataclass(frozen=True)
class IgnoreAspectPenaltyForUpgrades:
    """Constant marker on a UNIT: aspect penalties are waived on upgrades played
    onto it ("Ignore the aspect penalty on each Lightsaber upgrade you play on this
    unit" — General Grievous TWI_34).

    Read only at the play-cost seam (``actions._host_waives_aspect_penalty``, called
    from ``_play_cost`` with the upgrade's chosen ``target_host_id``): the *whole*
    aspect penalty of the played card is subtracted, which is what "ignore the aspect
    penalty" says — unlike the one-pip Daimyo's Palace LAW_20 waiver.  Empty
    ``traits`` waives it for any upgrade; otherwise the upgrade must carry them all.
    A pure read there — no trigger, no decision (the CannotAttackBases marker
    pattern)."""
    traits: tuple = ()


@dataclass(frozen=True)
class IgnoreAspectPenaltyForPlays:
    """Constant marker on a card its CONTROLLER has in play (a leader on either side,
    or a unit): aspect penalties are waived on the cards that controller plays which
    match ``card_type``/``traits`` — "Ignore the aspect penalty on Clone units you
    play" (Nala Se TWI_1).

    The controller-scoped sibling of ``IgnoreAspectPenaltyForUpgrades`` (which keys off
    the played upgrade's chosen HOST): read at the same play-cost seam, by
    ``actions._controller_waives_aspect_penalty``, which scans the controller's
    base_zone (so an UNDEPLOYED leader's copy of the clause counts) and both arenas.
    Waives the played card's WHOLE aspect penalty, the TWI_34 reading.  ``card_type``
    is a lowercase "unit"/"event"/"upgrade", ``"non_unit"`` (the complement filter — an
    event or an upgrade, Peli Motto ASH_212), or None for any.  ``exclude_aspects``
    disqualifies a played card bearing any listed aspect — "non-Villainy Official
    units you play" (Mon Mothma SEC_9).  A pure read — no trigger, no decision (the
    CannotAttackBases marker pattern).

    ``aspects`` is the INCLUDE filter ``exclude_aspects`` is the complement of — the
    played card must carry every listed aspect ("Heroism units you play", Hera
    Syndulla LAW_9).  ``condition`` gates the whole waiver on board state, evaluated
    against the marker's own source card ("**While you control 2 or more units**,
    ignore the aspect penalties on Heroism units you play" — LAW_9 again); None (the
    default) is the unconditional Nala Se TWI_1 reading."""
    card_type: Optional[str] = None
    traits: tuple = ()
    exclude_aspects: tuple = ()
    aspects: tuple = ()
    condition: Optional["ConditionCheck"] = None
    self_only: bool = False           # the marker is on the card BEING PLAYED rather
                                      # than on one already in play ("While playing
                                      # THIS unit, ignore his Villainy aspect penalty
                                      # if you control Rey" — Kylo Ren P25_46).  The
                                      # scan then also reads the played card's own
                                      # specs; without the flag a marker still only
                                      # ever applies to OTHER plays, so no existing
                                      # card moves.
    only_aspects: tuple = ()          # waive only the pips of these aspects instead
                                      # of the whole penalty ("his VILLAINY aspect
                                      # penalty" — P25_46), computed as the MARGINAL
                                      # cost of those pips: the full penalty less the
                                      # penalty of the card without them.


@dataclass(frozen=True)
class HalvePaidCosts:
    """Constant marker on a UNIT: while its controller has it in play, they pay
    half as many resources — rounded UP — for any resource cost (The Starhawk
    JTL_105: "While paying costs, you pay half as many resources, rounded up").

    Read through the single helper ``actions.resource_cost_for``, applied LAST, to
    the *determined* cost: after every reduction, discount and tax, exactly as the
    printed rules note describes ("you only need to pay resources up to half of the
    determined cost").  Consulted at the play-cost seam ``_play_cost`` and at every
    activated-ability ``PayResources`` affordability check plus its payment site,
    so it covers both card costs and ability costs as printed.  Non-resource costs
    (exhaust / defeat / discard a card) are untouched.  Controller-scoped (the scan
    walks that player's own arenas) and a no-op for boards with no such marker;
    mirrors the ``BasesCannotHeal`` marker+scan shape."""


@dataclass(frozen=True)
class BasesCannotHeal:
    """Constant marker on a UNIT: while it is in play, no base can be healed
    (Confederate Tri-Fighter TWI_132: "Bases can't be healed").

    The standing, in-play-scan version of Wolffe SOR_160's phase-scoped
    ``game_memory.bases_cannot_heal_this_phase`` lock — both are read through the
    single predicate ``actions._bases_cannot_heal``, which every base-heal
    chokepoint already consults (Restore, the Heal effect on a Base target, the
    heal-distribution finish, the discard-heal, the collector heal_base).  So the
    lock is symmetric ("Bases", not "your base" — it stops the controller's own
    Restore too, as printed) and lifts the instant the unit leaves play.  Purely a
    read there — no trigger, no decision; a no-op scan for boards with no such
    marker.  Mirrors the ``TokensEnterPlayReady`` marker+scan shape."""
    pass


@dataclass(frozen=True)
class SuppressLeaderAbilities:
    """Constant marker on a UNIT: while it is in play, EVERY leader (both players',
    deployed or not) loses its abilities and can't gain abilities — except epic
    actions (Brain Invaders TWI_255).

    The fourth source of the ability-suppression read-layer, folded into
    ``state.ability_suppressed`` beside Mind Trick LOF_202's per-instance flag,
    Galen Erso P25_31's name scan and Imprisoned SHD_72's upgrade marker — so the
    ~10 ability-read guards (keywords, trigger collection, the constant-stat scans,
    the arena UseAbility enumeration, the TraitGrant scan) all honour it for free,
    and "can't gain abilities" falls out of those reads short-circuiting.

    The "except for epic actions" carve-out lives at the one seam that offers a
    leader's own actions: the undeployed-leader ``UseAbility`` enumeration skips a
    suppressed leader's non-epic ``ActivatedAbility`` only.  Deploying is itself the
    Epic Action and never routes through ``get_abilities``, so it is unaffected."""
    pass


@dataclass(frozen=True)
class PlayOnlyAsFirstAction:
    """Constant marker: this card may be played only as its controller's FIRST
    action of the action phase (Confidence in Victory SEC_145).

    Read at the two hand-play seams the ``CannotPlayFromHand`` marker already uses
    (``actions._play_only_as_first_action_blocked``: the enumeration skip and
    ``PlayCard``'s defensive guard), over the per-player counter
    ``game_memory.actions_taken_this_phase`` — which counts real TURN actions only
    (resolving a sub-decision is not one) and is phase-cleared.  This IS the card's
    printed "can't be played as the result of another action" note: an ability that
    plays a card never routes through ``PlayCard``."""
    pass


@dataclass(frozen=True)
class CannotBeAttackedAfterDamagingBase:
    """Constant marker on an UNDEPLOYED LEADER: each unit its controller controls
    that has damaged an opponent's base this phase can't be attacked, unless it has
    Sentinel (Cassian Andor SEC_12's undeployed side).

    The aura sibling of ``CannotBeAttackedWhileExhausted``, read at the same single
    attack-enumeration seam (``actions._cannot_be_attacked``) and yielding to
    Sentinel for the same reason.  Membership is the long-standing
    ``game_memory.units_dealt_base_damage_this_round`` ledger (Retaliation SEC_77) —
    combat damage dealt by attacking a base, "this round" == "this phase" — and that
    cheap set test is checked FIRST, so the marker scan never runs for a unit that
    has not hit a base.  The scan walks the controller's ``base_zone`` only, which
    makes the aura undeployed-only for free (the mirror of the arena-scan convention
    that makes ``StandingPlayDiscount`` deployed-only): once the leader deploys, its
    printed deployed side no longer carries this clause."""
    pass


@dataclass(frozen=True)
class CannotBeAttacked:
    """Constant marker on a UNIT: while ``condition`` holds (always, when None) it
    can't be attacked, unless it has Sentinel — "This unit can't be attacked while
    you control 2 or more exhausted units (unless it gains Sentinel)" (Tatooine
    Repulsor Train ASH_35).

    The BOARD-gated sibling of ``CannotBeAttackedWhileExhausted``, whose gate is a
    property of the unit itself; both are read at the same attack-enumeration seam
    (``actions._cannot_be_attacked``) and both yield to Sentinel.  The condition is
    evaluated with the unit as its source, so "you" is the unit's controller."""
    condition: Optional["ConditionCheck"] = None


@dataclass(frozen=True)
class CannotBeAttackedWhileExhausted:
    """Constant marker on a UNIT: while it is exhausted it can't be attacked, unless
    it has Sentinel (Sabine Wren TWI_195: "While this unit is exhausted, she can't be
    attacked (unless she gains Sentinel)").

    The DEFENDER-side mirror of ``CannotAttackBases``: read only at the
    attack-enumeration seam (``actions._cannot_be_attacked``, alongside the Hidden
    filter that already removes un-attackable defenders), so the unit simply drops
    out of the eligible-defender set — and, exactly like Hidden, it therefore neither
    blocks nor forces anything as a Sentinel.  The Sentinel escape is the printed
    parenthetical: a granted Sentinel says "attack me", which beats "you can't", so
    the marker yields to it.  Purely a read there — no trigger, no decision."""
    while_ready: bool = False       # INVERT the readiness test: the unit can't be
                                    # attacked while it is READY instead ("While this
                                    # unit is ready, it can't be attacked" — Muckraker
                                    # Crab Droid SEC_135).  Same single read site
                                    # (``actions._cannot_be_attacked``) and the same
                                    # Sentinel escape; only the exhausted/ready test
                                    # flips.  Default False = the printed
                                    # while-exhausted reading (Sabine Wren TWI_195).


@dataclass(frozen=True)
class PrintedStatsOverride:
    """Constant marker on an UPGRADE: while it is attached, its host's *printed*
    power and HP are considered to be ``power``/``hp`` (Size Matters Not LOF_56:
    "Attached unit's printed power is considered to be 5 and its printed HP is
    considered to be 5").

    Read at the two effective-stats seams (``actions.compute_power`` /
    ``compute_hp``) where the printed value seeds the total, so everything layered
    on top — upgrade/token bonuses, Grit, Raid, Modifier records, ConstantAbility
    buffs — still applies on top of the override, which is exactly the printed
    reading.  Several overrides on one host would be ambiguous; the LAST one found
    wins (there is only one such card today).  Purely a read there — no trigger, no
    decision.

    ``aura_controller`` turns the marker into an AURA carried by a UNIT rather than
    an upgrade — "While you control 7 or more units, **their** printed power is
    considered to be 7 and printed HP is considered to be 7" (Obi-Wan Kenobi
    LAW_36).  "friendly" (the only reading printed today) applies the override to
    every unit the marker's controller owns, the source included; ``condition``
    gates it, evaluated against the marker's own source card.  Deliberately NOT a
    TargetSpec: this is read from the seed of ``compute_power``/``compute_hp``, and
    the target matcher re-enters those very functions.

    The ordering rule the card prints ("If multiple abilities or effects change the
    printed power or printed HP of a card, the most recent … determines the card's
    printed values") is honoured in ``actions._printed_stats_override``: an aura
    first, then an attached-upgrade marker, then a ``printed_stats`` MODIFIER —
    which is also the order in which those sources are put in place."""
    power: Optional[int] = None
    hp: Optional[int] = None
    aura_controller: Optional[str] = None      # None | "friendly"
    condition: Optional["ConditionCheck"] = None


@dataclass(frozen=True)
class CrossArenaAttack:
    """Constant marker: the unit carrying it may attack enemy units in the OTHER
    arena, not only its own (Strafing Gunship SOR_212: "This unit can attack units in
    the ground arena" — a space unit reaching ground defenders).

    Read only at the attack-enumeration seam (``actions._can_attack_other_arena``):
    the eligible-defender set is widened to include the opposite enemy arena, and the
    ``AttackWithUnit`` cross-arena apply-guard is relaxed for such an attacker.  Base
    attacks and same-arena attacks are unaffected.  Purely a read there — no trigger,
    no decision."""
    pass


@dataclass(frozen=True)
class AmbushDefenderDebuff:
    """Constant marker: while a unit its controller controls is attacking *using
    Ambush*, the defender of that attack gets ``power``/``hp`` (Enfys Nest SHD_219:
    "While a friendly unit (including this one) is attacking using Ambush, the
    defender gets -3/-0").

    Read only at the Ambush-attack seam (``actions.UseAmbush.apply``, which is the
    sole path an Ambush attack is declared): before combat resolves, every such
    marker the attacking player has in play contributes a ``this_attack`` stats
    modifier on the chosen defender, so it expires with the attack like any other
    combat-scoped debuff.  An ordinary (non-Ambush) attack by the same unit is
    unaffected — that is exactly the distinction the card draws.  "Including this
    one" falls out for free: the Ambush attacker is already in play when it
    attacks, so it is found by the same scan.  Purely a read there — no trigger,
    no decision.  Mirrors the ``IndirectDamageBonus`` passive-marker pattern
    (multiple copies stack) and the ``push_granted_attack(defender_power_bonus=)``
    defender-debuff mechanic (Jyn Erso SOR_18)."""
    power: int = 0
    hp: int = 0


@dataclass(frozen=True)
class AmbushAttackerBonus:
    """Constant marker: while THIS unit is attacking *using Ambush*, it gets
    ``power``/``hp`` (Heroic Purrgil ASH_207: "While attacking using Ambush, this
    unit gets +2/+0").

    The attacker-side mirror of ``AmbushDefenderDebuff``, read at the very same
    seam (``actions.UseAmbush.apply``) and likewise landed as a ``this_attack``
    stats modifier, so it expires with the attack.  It cannot be a plain
    ``ConstantAbility(while_attacking=…)``: that flag knows only *that* the source
    is attacking, not whether the attack was declared through Ambush, which is the
    whole clause.  Unlike the debuff this one is read off the ATTACKER alone — a
    second copy on another unit grants nothing."""
    power: int = 0
    hp: int = 0


@dataclass(frozen=True)
class DamagePrevention:
    """Constant marker on an UPGRADE: prevent ``amount`` of each instance of damage
    that would be dealt to its host (Boba Fett's Armor SHD_224: "If attached unit is
    Boba Fett and damage would be dealt to him, prevent 2 of that damage").

    ``host_named`` gates the marker on the host's card name ("If attached unit is
    Boba Fett"); ``None`` means it applies to whatever the upgrade is attached to.

    Read only at the unit-damage chokepoint (``actions._deal_damage_with_shield``,
    through which BOTH combat damage and ability damage flow), so it applies to
    every source of damage as printed.  It is a *reduction*, not a replacement:
    the amount is lowered before the Shield check, so an instance fully prevented
    deals nothing and does NOT consume the host's Shield (there is no damage left
    for the Shield to prevent).  Multiple copies stack.  Purely a read there — no
    trigger, no decision.

    Three optional fields let the SAME marker be printed on a UNIT rather than an
    upgrade, at the same single chokepoint:

    * ``on_self`` — the marker sits on a unit's own card and protects that unit
      ("If an enemy card ability would deal damage to this unit, prevent 2 of that
      damage" — Cassian Andor SEC_42).
    * ``aura_target`` — the marker sits on a unit and protects every OTHER in-play
      unit matching the spec ("If damage would be dealt to another friendly unit,
      prevent 1 of that damage" — Vigil SEC_50).  ``not_self`` in the spec's
      predicates is what makes it "another".
    * ``ability_only`` / ``enemy_only`` — narrow which instances count: card-ability
      (non-combat) damage only, and only damage dealt by a card an OPPONENT of the
      marker's controller controls.  Cassian needs both ("enemy card ability";
      his rules insert is explicit that combat damage is not a card ability)."""
    amount: int = 2
    host_named: Optional[str] = None
    on_self: bool = False
    aura_target: Optional[TargetSpec] = None
    ability_only: bool = False
    enemy_only: bool = False
    first_each_phase: bool = False   # "The FIRST time this unit would take damage
                                     # each phase, prevent that damage" (Umbaran
                                     # Mobile Cannon SEC_67).  A whole-instance
                                     # replacement rather than an ``amount``
                                     # reduction, and a one-shot: the first instance
                                     # to reach the unit-damage chokepoint records
                                     # the unit in
                                     # ``game_memory.first_damage_prevented_this_phase``
                                     # (phase-cleared) and is dropped; every later
                                     # instance that phase lands in full.  Combines
                                     # with ``on_self`` (the marker sits on the
                                     # unit's own card).
    consume_shield_on_source: bool = False
                                     # "If damage would be dealt to another friendly
                                     # unit, you may defeat a Shield token on THIS
                                     # unit.  If you do, prevent that damage" (The
                                     # Mandalorian ASH_62).  Combines with
                                     # ``aura_target``: a whole-instance prevention
                                     # (like ``first_each_phase``, not an ``amount``
                                     # reduction) whose price is a Shield token on
                                     # the AURA SOURCE, consumed at the same
                                     # unit-damage chokepoint and only while the
                                     # source really holds one.
                                     # DOCUMENTED DEVIATION: the printed "you may"
                                     # is taken automatically — the engine's own
                                     # Shield token prevents without asking, and a
                                     # decision pushed mid-damage would be
                                     # replacement-effect machinery.


@dataclass(frozen=True)
class DamageAmplification:
    """Constant marker on a UNIT: while it is in play, each instance of damage dealt
    to it BY ANOTHER CARD is increased by ``amount`` ("If damage would be dealt to
    this unit by another card, deal that much damage plus 1 instead" — Vigil SEC_50).

    The exact dual of ``DamagePrevention(on_self=True)`` and read at the same single
    chokepoint (``actions._deal_damage_with_shield``), just BEFORE prevention and the
    Shield check — so "that much damage plus 1" is the instance the rest of the
    pipeline sees.  ``by_another_card`` (the only shape today) excludes damage this
    unit deals to itself.  Purely a read; with no such marker the damage pipeline is
    byte-identical.

    Also read off a unit's ATTACHED UPGRADES, which is how an upgrade says "If
    attached unit would take damage, …" (Deadly Vulnerability ASH_150).
    ``multiplier`` scales the instance instead of adding to it ("it takes TWICE as
    much damage instead"); the two compose, the multiplication applying to the
    incoming amount before any additive term."""
    amount: int = 1
    by_another_card: bool = True
    multiplier: int = 1


@dataclass(frozen=True)
class UnpreventableDamage:
    """Constant marker on a UNIT: while it is in play, damage dealt by the cards
    it names can't be prevented — "Damage dealt by friendly Underworld cards is
    unpreventable" (Gorian Shard's Corsair ASH_196).

    The complement of the whole ``DamagePrevention`` family, read at the same
    single unit-damage chokepoint (``actions._deal_damage_with_shield``) but
    keyed on the DEALER rather than the receiver: a matching dealer skips
    prevention, amplification and the Shield check outright.  The dealing card is
    resolved from the ``dealer_source_id`` the chokepoint already carries, which
    ``find_instance`` recovers even from the discard — so a spent Underworld
    EVENT is a "card" here exactly as printed.

    ``controller`` is measured against the MARKER's controller ("friendly" =
    this unit's own side) and ``traits`` against the dealer's effective traits.
    Gated by a cached registry index, so a board with no such marker pays one set
    lookup per damage instance.  DOCUMENTED NARROWING: a bespoke card-module
    damage that calls the chokepoint with no dealer id is not covered, nor is
    damage to a BASE (bases have their own prevention seam)."""
    traits: tuple = ()
    controller: str = "friendly"


@dataclass(frozen=True)
class OpponentPlayTax:
    """Constant marker: while its controller has this unit in play, each of the
    OPPONENT's plays of a matching card type costs ``amount`` more (Del Meeko
    SOR_34: "Each event an opponent plays costs 1 resource more").

    Read only at the play-cost seam (``actions._opponent_play_tax``, alongside the
    reductions): when the player about to play a card faces an enemy in-play unit
    carrying this marker and the card matches ``card_type`` (``"event"`` today), the
    tax is ADDED to the cost (raising it; the affordability check and payment both
    see it).  Purely a read there — no trigger, no decision.  The dual of the
    ``StandingPlayDiscount`` / ``NextPlayDiscount`` cost-reduction patterns."""
    amount: int = 1
    card_type: str = "event"


@dataclass(frozen=True)
class NamedCardPlayTax:
    """Constant marker: while its source unit is in play, each copy of the card the
    source has named costs ``amount`` more for the source's OPPONENTS to play (Qi'ra
    SHD_202: "name a card.  While this unit is in play, each card with that name costs
    3 resources more for your opponents to play").

    The named card is recorded on the source instance's ``named_card`` field (set by
    the ``name_a_card`` decision, shared with Galen Erso / Regional Governor).  Read
    only at the play-cost seam (``actions._opponent_play_tax``): the surcharge is the
    per-name analogue of ``OpponentPlayTax`` (which keys off card TYPE), so it is
    ADDED to the cost of a matching-named card an opponent tries to play.  Purely a
    read there — no trigger, no decision."""
    amount: int = 3


@dataclass(frozen=True)
class AdvantageTokensLoseAbilities:
    """Constant marker on a UNIT: while its controller has it in play, the Advantage
    tokens on that player's units lose all abilities — "(They aren't defeated after
    combat.)" (Eviscerator ASH_149).

    An Advantage token's ONLY printed ability is its expiry ("When attached unit's
    attack or defense ends: Defeat this upgrade"), which lives in the combat pipelines
    rather than in the registry (see ``tokens.defeat_advantage_tokens``).  So the
    marker is read at exactly that sweep, which then skips a host whose controller has
    it — the ``EnemyCreditsLoseAbilities`` LAW_117 shape, where losing "all abilities"
    likewise collapses to disabling the one clause the token really has.  The +1/+0
    stays (printed stats are not an ability), which is the point of the card."""
    pass


@dataclass(frozen=True)
class AttackerLosesOverwhelm:
    """Constant marker on an UPGRADE: "While attached unit is defending, the attacker
    loses Overwhelm" (Deadly Vulnerability ASH_150).

    Not a ``KeywordRevoke`` aura: that is read by the keyword layer, which carries no
    combat context and so cannot tell "while THIS unit is defending" from any other
    moment.  Instead the marker is read at the two places Overwhelm actually does
    something — the excess-spill steps of the two unit-combat pipelines
    (``actions._overwhelm_denied_by``) — where the defender(s) of this very attack are
    in hand.  Overwhelm has no other effect, so disabling it there IS losing it.
    Purely a read — no trigger, no decision."""
    pass


@dataclass(frozen=True)
class LeaderUnitGrant:
    """Constant marker on an UPGRADE: "Attached unit is a leader unit" (The Darksaber
    ASH_135).

    Read at the single shared predicate ``resolver._is_leader_unit``, which already
    answers this question for a Vehicle piloted by a deployed LEADER (Boba Fett
    JTL_9's "Attached unit is a leader unit").  ASH_135 prints the same clause on an
    ordinary upgrade, so the predicate simply gains a second reason to say yes — and
    with it the host is shielded from "Defeat a NON-LEADER unit" removal and picked up
    by a "each leader unit you control" aura, both for free.  Purely a read — no
    trigger, no decision."""
    pass


@dataclass(frozen=True)
class ProvidesAspectIcons:
    """Constant marker on an UPGRADE: "Attached unit gains: 'While you are paying
    costs, this unit provides its aspect icons.'" (The Darksaber ASH_135).

    Read at ``actions._available_aspects`` — the ONE place that knows which icons
    count against a play cost (today: the controller's base and leader) — so it feeds
    the aspect-penalty maths for every play route at once, and the web layer's
    penalty pill follows for free.  The icons provided are the HOST's, not the
    upgrade's, which is what "this unit provides ITS aspect icons" says.  Purely a
    read — no trigger, no decision."""
    pass


@dataclass(frozen=True)
class FlipLeaderAspects:
    """Constant marker on a FLIP LEADER whose two sides print DIFFERENT aspect icons
    (Chancellor Palpatine // Darth Sidious TWI_17 — the only such card in the DB).

    The upstream card data carries ONE aspect list per row, so a double-sided leader
    arrives with the UNION of both sides' icons (Cunning, Villainy, Heroism).  That
    union is wrong for cost purposes at every moment of the game: only the side
    currently face up provides icons, and Palpatine's sides differ precisely on the
    Heroism/Villainy pip his whole archetype is built around.  Without this marker an
    unflipped Chancellor Palpatine silently pays no penalty on Villainy cards.

    ``front`` is the side the leader starts on and ``back`` the flipped side, matched
    against ``game_memory.flipped_leaders`` (the SOURCE_LEADER_FLIPPED seam) — the same
    ledger the card's own two Actions are gated on, so the icons and the abilities can
    never disagree about which side is showing.

    Read at ``actions._available_aspects``, the ONE place that decides which icons
    offset an aspect penalty, so every play route and the web layer's "+N" penalty pill
    follow for free.  Purely a read — no trigger, no decision."""
    front: tuple = ()
    back: tuple = ()


@dataclass(frozen=True)
class BaseDamageCap:
    """Constant marker on a UNIT: while its controller has it in play, no single
    instance of damage dealt to that player's base may exceed ``amount`` — "If your
    base would be dealt more than 4 damage, prevent all but 4 of that damage" (At
    Attin Safety Droid ASH_70).

    Bases have no single damage chokepoint, so — like Close the Shield Gate JTL_74's
    one-shot charge — this is read through the ONE shared helper
    ``actions.base_damage_after_prevention``, which every base-damage site (ability
    damage, indirect damage, a base attack, both Overwhelm spill sites, a leader's
    base hit, the empty-deck penalty) already calls.  Per INSTANCE, not per phase:
    two 5-damage hits land 4 each, which is what the card says.  Purely a read — no
    trigger, no decision (the ``CannotAttackBases`` marker pattern)."""
    amount: int = 4


@dataclass(frozen=True)
class SearchWindowDoubler:
    """Constant marker: while its source is in play, a deck search its controller
    makes looks at TWICE as many cards — "If you would search a number of cards from
    your deck, search twice that number of cards instead" (Arcana Star Map ASH_84,
    which grants it to its host via ``ConstantAbility``-free registration on the
    UPGRADE and is therefore read off attached upgrades too).

    Read at the single ``actions.push_deck_search`` entry point, where the window is
    still just a number, so every search route (a plain search, search-and-play,
    search-and-play-an-upgrade, a foreign search) is covered at once.  Only the
    WINDOW doubles — how many cards may be TAKEN is untouched, which is what
    "search a number of cards" means.  The board scan walks each of the searching
    player's arena units AND their attached upgrades, so the marker works printed on
    a unit or (as here) on an upgrade conferring it on its host.  Purely a read — no
    trigger, no decision."""
    pass


@dataclass(frozen=True)
class ForbidNamedCardPlay:
    """Constant marker: while its source unit is in play, opponents can't play the
    card it has named (Regional Governor SOR_62: "Name a card.  While this unit is
    in play, opponents can't play the named card").

    The named card is recorded on the source instance's ``named_card`` field (set by
    the ``name_a_card`` decision, shared with Galen Erso's ability-suppression).  This
    marker DISTINGUISHES the play-restriction namer from the ability-suppression namer
    — read only at the play-legality seam (``actions._named_card_play_forbidden``,
    which scans enemy units carrying THIS marker), so Galen's naming still only
    suppresses abilities.  Purely a read there — no trigger, no decision.  Mirrors the
    ``CannotAttackBases`` passive-marker pattern."""
    pass


@dataclass(frozen=True)
class StartingHandModifier:
    """Constant marker on a BASE: the controller's OPENING hand is ``amount`` cards
    bigger (or smaller, when negative) than the standard 6, and — with
    ``no_mulligan`` — that player may not take a mulligan.

    "Draw 1 less card in your starting hand" (Colossus JTL_21) =
    ``StartingHandModifier(amount=-1)``; "Draw 3 more cards in your starting hand.
    You can't take a mulligan." (Nabat Village JTL_28) =
    ``StartingHandModifier(amount=3, no_mulligan=True)``.

    Read at the three setup seams that already know the number 6 —
    ``actions.new_game``'s opening draw, ``TakeMultiligan.apply``'s redraw (a
    mulligan redraws the same modified hand size), and the SETUP_MULLIGAN branch of
    ``legal_actions`` (which drops ``TakeMultiligan`` for a ``no_mulligan``
    player) — through the one helper ``actions._starting_hand_size``.  Purely a
    read: no trigger, no decision, and a no-op for every base without the marker
    (the ``ExtraRegroupPhase`` passive-marker pattern)."""
    amount: int = 0
    no_mulligan: bool = False


@dataclass(frozen=True)
class DeckSizeModifier:
    """Constant marker on a BASE: the deck it is built into needs ``amount`` more
    (or, when negative, fewer) cards than the standard 50.

    "Your minimum deck size is increased by 10 cards" (Data Vault JTL_24) =
    ``DeckSizeModifier(amount=10)``; "…decreased by 5 cards" (Thermal Oscillator
    JTL_25) = ``DeckSizeModifier(amount=-5)``.

    A DECKBUILDING rule, not an in-game ability — the ``StartingHandModifier``
    (Colossus JTL_21) pattern one seam over: read by
    ``cards.deckrules.deck_size_for``, the single place that knows the number 50,
    so it lands in the validator, the deck builder and the precon check at once.
    Purely a read: no trigger, no decision, and a no-op for every base without it.

    NOTE the engine's long-standing convention that the 50 is EXACT, not the CR's
    minimum; this marker shifts that exact number rather than introducing a range,
    so a Data Vault deck is exactly 60 and a Thermal Oscillator deck exactly 45."""
    amount: int = 0


@dataclass(frozen=True)
class DeployCondition:
    """Passive marker on a LEADER: its Epic Action deploy is gated by ``condition``
    instead of by the printed "you control N or more resources" threshold.

    ``actions._deploy_threshold`` parses that threshold out of the epic-action text
    with a regex, and a leader whose deploy clause is phrased any other way has
    always returned ``None`` — i.e. could never deploy at all.  Bo-Katan Kryze ASH_10
    is exactly that card: "If the number of resources you control plus the number of
    friendly Mandalorian units is 10 or more, deploy this leader."

    Read at the single helper ``actions._leader_deploy_allowed``, which the three
    deploy seams (the ``legal_actions`` offer, ``DeployLeader.apply``,
    ``DeployLeaderAsUpgrade.apply``) all now go through, so the offer and the two
    guards can never disagree.  Purely a read — no trigger, no decision — and a
    no-op for every leader without one (the threshold path is unchanged)."""
    condition: Optional["ConditionCheck"] = None


@dataclass(frozen=True)
class ExtraRegroupPhase:
    """Constant marker: while this unit is in play, the round runs an ADDITIONAL
    regroup phase after the first (Max Rebo LAW_72: "There is an additional regroup
    phase after the first regroup phase each round" = ``ExtraRegroupPhase()``).

    Read only at the regroup-rollover site (``actions._end_regroup`` via
    ``_extra_regroup_active``): after the first regroup's ready step, instead of
    rolling over to the next round's ACTION phase, the engine re-enters a second
    regroup (a fresh draw-2 + resource + ready), then rolls over.  It is a static
    board condition, not additive — any number of copies still yields exactly ONE
    extra regroup (the ``regroup_count_this_round < 2`` cap).  Purely a read at the
    rollover — no trigger, no decision; with no such marker the turn structure is
    unchanged.  Mirrors the ``AttackRestriction`` / ``EntersPlayReady`` passive-marker
    pattern."""


@dataclass(frozen=True)
class ReadyRestriction:
    """Constant marker: the source unit **can't ready while** ``condition`` holds
    (Leia Organa LOF_98: "While this unit is in the space arena, she can't ready" =
    ``ReadyRestriction(ConditionCheck(Condition.SOURCE_IN_SPACE_ARENA))``).

    The ready-site MIRROR of ``AttackRestriction``, with the OPPOSITE polarity
    (deliberate): ``AttackRestriction`` forbids while its condition is FALSE ("can't
    attack UNLESS …"); ``ReadyRestriction`` forbids while its condition is TRUE
    ("can't ready WHILE …").  The inverted polarity lets a single
    ``SOURCE_IN_SPACE_ARENA`` atom drive BOTH this restriction and the paired
    "gains [Action] while in space" ability — no second in-ground atom needed.

    Read via ``actions._ready_forbidden`` at the two ready sites that already
    honour ``cannot_ready_this_round`` (``_end_regroup`` and the ``ReadyCard``
    effect arm) — a persistent, board-re-evaluated block, so leaving the space
    arena lifts it automatically.  No trigger, no decision; with no such spec
    readying is unchanged.

    ``regroup_only`` narrows the block to the REGROUP phase, so an *effect* may
    still ready the unit mid-action ("This unit doesn't ready during the regroup
    phase unless its power is 4 or more" — Rampart JTL_182, which says nothing
    about being readied by a card).  Default False = the block holds at every ready
    site, the Frozen in Carbonite SHD_193 reading."""
    condition: ConditionCheck
    regroup_only: bool = False


@dataclass(frozen=True)
class ConditionalFirstStrike:
    """Constant marker: the source unit deals combat damage before the defender
    (First Strike) only while the *defender* it is attacking matches
    ``defender_spec`` (Hound's Tooth JTL_185: "While attacking an exhausted unit
    that didn't enter play this phase, this unit deals combat damage before the
    defender" = ``ConditionalFirstStrike(TargetSpec(controller="enemy",
    kind="unit", predicates=("exhausted", "not_played_this_phase")))``).

    Read only at the unit-combat step (``actions._resolve_unit_combat_step2``): the
    attacker gets First Strike for this attack iff the current defender satisfies
    ``defender_spec`` (evaluated from the attacker's perspective).  Purely a read
    at combat resolution — no trigger, no decision; unconditional First Strike is
    still the keyword layer (Incinerator Trooper SHD_234).  Mirrors the
    ``AttackRestriction`` passive-marker pattern.

    ``condition`` adds a BOARD gate on top of the defender filter, evaluated
    against the attacker — "While attacking, **if no other units have attacked this
    phase**, this unit deals combat damage before the defending unit" (Anakin's
    Podracer LAW_219, whose defender filter is simply "any unit").  Reading it here
    rather than as a conditional ``KeywordGrant`` is what keeps "while ATTACKING"
    exact: the keyword layer carries no combat context, so a granted First Strike
    would also apply while the unit is defending."""
    defender_spec: "TargetSpec"
    condition: Optional["ConditionCheck"] = None


@dataclass(frozen=True)
class IndirectDamageBonus:
    """Constant marker: while this unit is in play, indirect damage its controller
    deals to opponents is increased by ``amount`` (Hunting Aggressor JTL_165:
    "Indirect damage you deal to opponents is increased by 1").

    Read only at the indirect-damage chokepoint
    (``actions.push_assign_indirect_damage``): the pushed ``amount`` is raised by
    the sum of every ``IndirectDamageBonus`` the source's controller has in play
    (multiple copies stack).  Purely a read there — no trigger, no decision; with
    no such marker the indirect-damage amount is unchanged.  Mirrors the
    ``AttackRestriction`` / ``EntersPlayReady`` passive-marker pattern."""
    amount: int = 1


@dataclass(frozen=True)
class WhenDefeatedRedo:
    """Constant marker: while this card is in play, its controller may use a "When
    Defeated" ability a second time (Grand Admiral Thrawn JTL_2, both sides).

    Read only at the ability-redo chokepoint (``resolver._schedule_ability_redo``),
    the same seam Qui-Gon Jinn's Aethersprite LOF_197 uses for its charge-based
    "use that When Played ability again".  Where the Aethersprite arms a one-shot
    phase charge, this marker is a *standing* observer: every time its controller
    uses a qualifying When Defeated ability, the engine offers an optional re-use
    of that same ability as an ordinary ``trigger_option`` (no new decision kind).

    ``cost_exhaust_source`` — accepting exhausts the marker's own card ("You may
    exhaust this leader.  If you do, use that ability again"); offered only while
    it is ready, so the cost is always payable.  ``once_per_round`` — accepting
    burns the round's single use (``game_memory.when_defeated_redo_used_this_round``).
    Both are charged on ACCEPT only: declining a "you may" is not a use, so it
    neither exhausts the leader nor spends the round's charge (this is the one
    place the Aethersprite differs — its delayed trigger latches on offer).

    ``undeployed_only`` / ``deployed_only`` gate the marker to one side of a
    leader, mirroring the TriggerAbility flags of the same name — Thrawn's
    undeployed side pays by exhausting himself, his deployed side is free but
    once per round."""
    cost_exhaust_source: bool = False
    once_per_round: bool = False
    undeployed_only: bool = False
    deployed_only: bool = False


@dataclass(frozen=True)
class OnAttackRedo:
    """Constant marker: while this card is in play, its controller may use an "On
    Attack" ability a second time (Enfys Nest LAW_14, both sides).

    The exact sibling of ``WhenDefeatedRedo`` above — same marker shape, same
    ``resolver._schedule_ability_redo`` chokepoint, same charge-on-ACCEPT rule —
    with the trigger class being ``OnAttack`` instead of ``WhenDefeated``.  Read
    nowhere else, so it is inert for every card that does not carry it.

    ``cost_resources`` is the one field ``WhenDefeatedRedo`` had no use for:
    Enfys's undeployed side reads "You may pay 2 resources **and** exhaust this
    leader.  If you do, use that ability again", so the redo is offered only while
    the controller has that many READY resources *and* the leader is ready, and
    both halves are charged together on accept.  Her deployed side is free but
    ``once_per_round`` ("Use this ability only once each round"), sharing
    ``game_memory.when_defeated_redo_used_this_round`` — that ledger is keyed by the
    marker's own instance id, so the two marker kinds cannot collide.

    ``undeployed_only`` / ``deployed_only`` gate the marker to one side of a
    leader, exactly as on ``WhenDefeatedRedo``."""
    cost_resources: int = 0
    cost_exhaust_source: bool = False
    once_per_round: bool = False
    undeployed_only: bool = False
    deployed_only: bool = False


@dataclass(frozen=True)
class WhenFriendlyUnitAttackEnds:
    """Observer: fires when a FRIENDLY unit's attack ends — the group analogue of
    the self-referential ``WhenAttackEnds`` (Boba Fett LAW_7, "When a friendly
    Bounty Hunter unit's attack ends: If the defending unit was defeated, …").

    It needs its own firing than either neighbour because of the card's own printed
    rules note — "The attacking Bounty Hunter unit doesn't need to survive the
    attack in order to create a Credit token":

      * ``WhenAttackEnds`` keys on ``attack_ended_survivor``, which the combat
        pipelines set only for an attacker still in play, and
      * ``OnAttackDefeatsUnit`` / ``WhenFriendlyUnitAttacksAndDefeatsUnit`` fire
        from a site guarded on ``not attacker_dead``.

    So the combat pipelines carry a distinct pair of keys —
    ``attack_ended_attacker`` (always the attacker, alive or dead) and
    ``attack_ended_defender_defeated`` (the defeated defender's id, absent when the
    defender lived) — set at a dedicated fire that runs whether or not the attacker
    survived.  That fire happens EXACTLY ONCE per attack: an attack ends once,
    however many co-defenders it killed, and both readings of the trigger share the
    one firing, so neither can fire twice for a single attack.

    ``traits`` narrows the attacker by its EFFECTIVE traits (all listed must be
    present); ``require_defender_defeated`` is the "If the defending unit was
    defeated" clause.  A base attack has no defending unit, so a
    ``require_defender_defeated`` observer never fires on one — while a plain
    observer does (Anakin Skywalker LAW_88, "When a friendly unit's attack ends",
    which draws no unit/base distinction).

    ``require_base_damage_min`` is the "If it dealt N or more combat damage to a
    base" clause (Ezra Bridger ASH_13), read off ``attack_ended_base_damage_amount``
    — carried by the direct base-attack fire AND by an Overwhelm spill on a unit
    attack, both of which are combat damage dealt to a base."""
    traits: tuple = ()
    require_defender_defeated: bool = False
    require_base_damage_min: int = 0


@dataclass(frozen=True)
class WhenYouPlayOrCreateUnit:
    """Observer: fires for a card in play when a unit ENTERS PLAY under the
    observer's controller — "When you play or create a unit" (Greef Karga ASH_17)
    and "When a friendly unit enters play (including this one)" (Outcast ASH_41).

    The settle-drain family (``WhenUnitHealed`` / ``WhenFriendlyUpgradeDefeated``):
    ``actions._put_unit_in_play`` — the ONE chokepoint every entry route passes
    through, so a hand/discard/smuggle/plot play, an ability play and a created token
    unit all count, which is exactly the union the two cards name — appends to the
    ``game_memory.unit_entries`` queue, drained at the action settle-point by
    ``actions._fire_unit_entry_observers``.  "That unit" is
    ``event_ctx["entered_unit_id"]``.

    ``include_self`` (the default) lets the observer fire for its OWN entry — ASH_41
    prints "(including this one)", and the drain runs after the unit is already in
    its arena, so the ordinary in-play trigger scan finds it.  Set it False for an
    observer that must not see itself arrive."""
    include_self: bool = True


@dataclass(frozen=True)
class PreventDamage:
    """Constant marker: while this unit is in play, ABILITY damage that a unit its
    controller controls (matching ``source_traits``) would deal to ANOTHER unit that
    SAME player controls is prevented (Malakili LOF_108: "If a friendly Creature unit
    would deal damage to a friendly unit, prevent that damage").

    Read only at the ability-damage chokepoint (``resolver._apply_deal_damage`` via
    ``_damage_prevented``): the damage is dropped (no ``DamageDealt`` event, no
    non-combat-damage record, no defeat).  Combat damage is always attacker-vs-enemy,
    so a friendly Creature can only deal to a *friendly* unit via an ability — the
    single ``_apply_deal_damage`` sink — which is why this needs no combat-pipeline
    hook.  Only UNIT targets are guarded (Malakili says "a friendly unit", not a
    base).  ``source_traits`` are matched against the source's *effective* traits
    (``traits.get_traits``).  Purely a read there — no trigger, no decision; with no
    such marker damage is unchanged.  Mirrors the ``AttackRestriction`` /
    ``IndirectDamageBonus`` passive-marker family."""
    source_traits: tuple = ()


@dataclass(frozen=True)
class InteractiveDamagePrevention:
    """Constant marker: while this unit is in play, "If damage would be dealt to this
    unit, you may defeat another friendly unit that shares a trait with this unit.  If
    you do, prevent that damage." (Queen Amidala SEC_101).

    Unlike ``PreventDamage`` (a *non-interactive* drop of a friendly Creature's
    friendly-fire ability damage), this is a *player choice* with a cost (defeat one
    of your own trait-sharing units), so it is a decision, not a passive read.

    THIS SESSION implements the COMBAT-damage half only: a pre-step2 checkpoint in
    ``actions._resolve_unit_combat`` reads this marker on either combatant and, when
    that unit would take >0 unshielded combat damage and its controller has an
    eligible trait-sharing friendly to sacrifice, pushes a ``combat_damage_prevention``
    decision (under the existing ``pre_attack`` continuation).  Accepting defeats the
    chosen friendly unit and arms ``CardInstance.prevent_next_combat_damage`` on the
    protected unit, which the single combat sink ``_deal_damage_with_shield`` reads to
    drop that one combat-damage instance.  No combat-pipeline rewrite — it reuses the
    existing ``pre_attack`` / ``ContinueAttack`` resume.

    DEFERRED (the DAMAGE half's second primitive): interactive prevention of ABILITY
    damage (``resolver._apply_deal_damage``) and INDIRECT damage
    (``_apply_indirect_damage``) — those are synchronous sinks and need mid-resolution
    decision injection, a separate dedicated-session primitive.  ``share_trait`` is
    True for Amidala's "shares a trait with this unit" sacrifice restriction (the only
    shape today).  A passive marker (like ``PreventDamage`` / ``AttackRestriction``);
    with no such marker in play the combat pipeline is byte-identical."""
    share_trait: bool = True


@dataclass(frozen=True)
class IndirectDamageSelfAssign:
    """Constant marker: while this unit is in play, *its controller* assigns the
    indirect damage they deal to opponents, instead of the receiving player
    (Devastator JTL_143: "You assign all indirect damage you deal to opponents").

    Read only at the indirect-damage chokepoint
    (``actions.push_assign_indirect_damage``): when the source's controller has any
    such marker in play, the ``assign_indirect_damage`` decision is handed to the
    controller (who picks which of the receiving player's base/units absorbs the
    damage) rather than to the receiving player.  Purely a read there — no trigger,
    no new decision kind; with no such marker the receiving player assigns as
    before.  Mirrors the ``IndirectDamageBonus`` passive-marker pattern."""
    pass


@dataclass(frozen=True)
class StandingPlayDiscount:
    """Constant marker: while this unit is in play, its controller pays ``amount``
    less to play a card matched by ``applies_to`` (Director Krennic JTLP_1: "The
    first unit you play each round that has a 'When Defeated' ability costs 1
    resource less").

    Read only at the play-cost seam (``actions._play_cost`` via
    ``_standing_play_discount``), alongside the card-level ``CostReduction`` and the
    pending ``NextPlayDiscount`` — so both the affordability check and the actual
    payment see it.  ``applies_to`` names a predicate on the card being played
    (``"has_when_defeated_ability"``, ``"unit"``, ``"creature_unit"``,
    ``"trick_event"``, ``"upgrade_on_source"``, ``"trait:<T>"``).  When
    ``once_per_round`` the discount applies to only the FIRST matching play each
    round (tracked in ``game_memory.standing_play_discounts_used_this_round`` by
    ``actions._standing_discount_key``, the ``activated_abilities_used_this_round``
    once-per-round pattern), consumed at the real play site
    (``actions._consume_standing_discount``).

    The marker may also ride on an UPGRADE, in which case the discount belongs to
    the ATTACHED unit's controller — "Attached unit gains: 'The first unit you play
    each round costs 2 resources less'" (Death Star Plans JTL_260).  Purely a read /
    consume at the play path — no trigger, no decision; with no such marker the
    play cost is unchanged.  Mirrors the ``IndirectDamageBonus`` passive-marker +
    the ``NextPlayDiscount`` cost-reduction patterns."""
    amount: int = 1
    applies_to: str = "has_when_defeated_ability"
    once_per_round: bool = True


@dataclass(frozen=True)
class UnitsPayCosts:
    """Constant marker: while this unit is in play, its controller may exhaust each
    friendly unit matching ``traits`` to pay costs as if it were a resource ("Each
    friendly Droid unit may be exhausted to pay costs as if it were a resource" —
    Vuutun Palaa SEC_122).

    Read at the play-payment seam (``actions._affordable_with_credits`` /
    ``_pay_play_cost`` via ``_unit_resource_pool``), so both the affordability check
    and the actual payment see the extra capacity.  Spending is NEED-BASED and
    automatic, exactly like the Credit-token economy this mirrors: ready resources
    are exhausted first, then credits are defeated, and only then are units
    exhausted to cover a remaining shortfall — so with no marker in play the payment
    is byte-identical to before, and a unit is never tapped for a play the resource
    row could already afford.

    SCOPE (the credit economy's documented narrowing, deliberately matched): this
    covers the card-play paths that go through ``_pay_play_cost``/
    ``_affordable_with_credits`` — PlayCard, play-from-hand, play-from-discard,
    PlayTopCard, piloting.  It is NOT wired into Smuggle/Plot (which pay from the
    other resources) or activated-ability ``PayResources`` costs.  Purely a read at
    that seam — no trigger, no decision.  ``traits=()`` would match every friendly
    unit; the one shipped card names a trait."""
    traits: tuple = ()


@dataclass(frozen=True)
class AdditionalPilotSlots:
    """Constant marker: this unit may host ``count`` extra Pilot(s) beyond the
    standard one (Millennium Falcon JTL_249: "You may play or deploy 1 additional
    Pilot on this unit").

    Read at the pilot-attach seam (``actions._eligible_leader_upgrade_targets`` via
    ``_pilot_limit``): the host's Pilot limit becomes ``1 + count``.  Purely a read
    there — no trigger, no decision.  NOTE: the engine does not enforce the standard
    one-Pilot-per-Vehicle limit on the normal ``PilotPlay`` path (any Vehicle may
    already receive multiple Pilot upgrades), so this marker's functional effect is
    to relax the *leader-deploy-as-upgrade* limit (the one place a Pilot cap is
    checked); the "play an additional Pilot" case is already free.  Mirrors the
    ``IndirectDamageBonus`` passive-marker pattern."""
    count: int = 1


@dataclass(frozen=True)
class MultiDefenderAttack:
    """Constant marker: this unit may attack ``count`` enemy units at once, as a
    single attack (Darth Maul C24_6: "This unit can attack 2 units instead of 1").

    Read at the attack-enumeration seam (``actions._enumerate_two_unit_attacks``)
    and by the ``AttackTwoUnits`` action / ``_resolve_two_unit_combat`` pipeline:
    both chosen units are co-defenders of ONE attack — the attacker deals its
    power to each, each deals its power back to the attacker, all simultaneously;
    Overwhelm spills the COMBINED excess to the base; Sentinel/Saboteur/Shield
    behave as normal across both defenders; the attacker may not mix a base with a
    unit.  Purely a read — no trigger, no decision (the AttackTwoUnits action drives
    it); with no such marker attack enumeration is unchanged.  Mirrors the
    ``AttackRestriction`` passive-marker pattern (a read at the same seam)."""
    count: int = 2


@dataclass
class CustomAbility:
    """Escape-hatch: complex logic that can't be expressed declaratively.

    resolve_fn(state, source_ci, event_ctx: dict) -> GameState
    The function performs all mutations and returns the new state.
    """
    resolve_fn: Callable


@dataclass
class GrantedAbility:
    """An ability an upgrade confers on its attached host unit.

    The card text reads "Attached unit gains: '<ability>'" (e.g. Armed to the
    Teeth SHD_175: "Attached unit gains: 'On Attack: Give another friendly unit
    +2/+0 for this phase.'").  The wrapped ``ability`` behaves exactly as if it
    were registered on the HOST unit rather than on the upgrade:

    - trigger matching uses the host as the source (so an OnAttack granted
      ability fires when the *host* attacks), and
    - effect resolution uses the host as the source (so "another friendly unit"
      / the ``not_self`` predicate excludes the host).

    These granted abilities are collected by ``resolver._collect_triggers``,
    which scans every in-play unit's ``attached_upgrades`` for GrantedAbility
    specs.  The pushed decision stores the UPGRADE's ``(set_code, card_number,
    ability_idx)`` so the spec can be re-located on resolution, but its
    ``source_id`` is the host unit — so ``unwrap_granted`` must be applied when a
    looked-up spec turns out to be a GrantedAbility.

    The wrapped kind is usually a ``TriggerAbility`` (the common "Attached unit
    gains: 'On Attack: …'" pattern).  A granted ``ActivatedAbility`` is also
    supported (Heroic Resolve SHD_155: "Attached unit gains: 'Action [2 resources,
    defeat a Heroic Resolve on this unit]: Attack with this unit …'"): the trigger
    collector skips it (its ``ability`` is not a TriggerAbility), and instead the
    activated-ability enumeration in ``actions.legal_actions`` surfaces it — the
    Action is addressed by the UPGRADE's instance_id and resolves from the host,
    with a ``DefeatSelf`` cost that defeats THIS upgrade (see ``UseAbility.apply``
    and ``_defeat_attached_upgrade``).
    """
    ability: "TriggerAbility | ActivatedAbility"


@dataclass(frozen=True)
class AuraGrantedAbility:
    """A triggered ability a SOURCE confers on every in-play unit matching
    ``target`` — an *aura* grant, the group analogue of GrantedAbility (which grants
    via a single attachment).  Gar Saxon SHD_1 deployed: "Each friendly upgraded
    unit ... gains: 'When Defeated: You may return an upgrade that was attached to
    this unit to its owner's hand.'"

    Collected by ``resolver._collect_triggers``: each unit matching ``target`` (from
    the source's perspective) contributes the inner ``ability`` with THAT unit as the
    trigger source, so the wrapped trigger fires for the matched unit and its effects
    resolve from it.  The pushed decision is addressed to the SOURCE's registry entry
    at this spec's index; ``unwrap_granted`` unwraps it to the inner TriggerAbility on
    resolution (exactly like GrantedAbility, so no resolution-side changes are needed).

    Only a ``WhenDefeated`` inner trigger is collected today — the sole printed
    "each friendly … unit gains: 'When Defeated …'" pattern — and it is gathered at
    the UnitDefeated defeat path (where the dying unit is matched against ``target``),
    mirroring the bounty ``defeated_upgrades`` handling.  Because that path scans
    only cards currently in play, a leader-side aura is naturally deployed-only (an
    undeployed leader sits in base_zone, out of the in-play scan).

    A wrapped ``ActivatedAbility`` is also supported (Satine Kryze TWI_47: "Each unit
    (including enemy units) gains: 'Action [Exhaust]: …'").  The trigger collector
    skips it (its ``ability`` is not a TriggerAbility); instead the aura-grant scan in
    ``actions.legal_actions`` offers it once per matching unit the ACTIVE player
    controls, and the resulting ``UseAbility`` carries both ids — ``source_id`` for
    this spec's address and ``actor_id`` for the unit using it.  This is the
    many-actors analogue of the upgrade-granted Action (Heroic Resolve SHD_155),
    where the single host is derivable from the source and no actor field is needed.
    Because the grant is to "each unit", the source may be an ENEMY card: the
    ownership guard, the ``ExhaustSelf``/``DefeatSelf`` costs and the effect source
    all key on the ACTOR (see ``UseAbility.apply``), and the aura's ``target`` is
    re-checked at apply time in case the board moved.
    """
    ability: "TriggerAbility | ActivatedAbility"
    target: TargetSpec


@dataclass(frozen=True)
class SuppressHostAbilities:
    """A constant marker registered on an UPGRADE: while it is attached, the host
    unit loses its current abilities and can't gain abilities (Imprisoned SHD_72:
    "Attached unit loses its current abilities and can't gain abilities").

    This is the third, upgrade-borne source of the ability-suppression read-layer —
    a persistent-while-attached mirror of Mind Trick LOF_202's phase-scoped
    per-instance ``abilities_suppressed`` flag and Galen Erso P25_31's name-scoped
    ``is_name_suppressed`` scan.  ``state.ability_suppressed`` folds all three into
    one predicate that the ~10 ability-read guards consult (has_keyword/keyword_value,
    _collect_triggers, the constant-stat-bonus scans, the arena UseAbility enumeration
    and the TraitGrant scan).  Because those guards are reads and this source is
    derived from the upgrade's mere presence, both "can't gain abilities" (a read
    short-circuits before any grant is consulted) and persistence (the suppression
    lifts the instant the upgrade leaves play) fall out for free — no stored flag to
    clear.  A pure marker: it carries no fields and is never resolved as an effect."""
    pass


def unwrap_granted(spec):
    """Return the inner TriggerAbility of a Granted/AuraGranted wrapper, else ``spec``.

    Decision contexts address a granted ability by the spec card's
    ``(set_code, card_number, ability_idx)``; on resolution ``specs[ability_idx]``
    is the wrapper, so this unwraps it to the TriggerAbility whose
    ``effects``/``optional`` the resolution machinery expects.
    """
    if isinstance(spec, (GrantedAbility, AuraGrantedAbility)):
        return spec.ability
    return spec


# ── Registry ─────────────────────────────────────────────────────────────────
_REGISTRY: dict[tuple[str, str], list] = {}   # (set_code, card_number) -> list[AbilitySpec]
_ESCAPE_HATCH: set[tuple[str, str]] = set()


def card_ability(set_code: str, card_number: str, escape_hatch: bool = False):
    """Decorator — register a card's abilities.

    The decorated function must return either a single AbilitySpec or a list
    of AbilitySpec objects.  It is called immediately at decoration time.

    Example::

        @card_ability("SOR", "033")
        def _():
            return [
                TriggerAbility(
                    trigger=WhenPlayed(),
                    effects=[GiveToken("Shield", TargetSpec(fixed=SELF))],
                ),
            ]
    """
    def decorator(fn: Callable) -> Callable:
        specs = fn()
        if not isinstance(specs, list):
            specs = [specs]
        _REGISTRY[(set_code, card_number)] = specs
        if escape_hatch:
            _ESCAPE_HATCH.add((set_code, card_number))
        return fn
    return decorator


def get_abilities(set_code: str, card_number: str) -> list:
    """Return the list of AbilitySpec for this card, or [] if not registered."""
    return _REGISTRY.get((set_code, card_number), [])


def get_all_registered() -> dict:
    """Return a snapshot of the full registry."""
    return dict(_REGISTRY)


def is_escape_hatch(set_code: str, card_number: str) -> bool:
    return (set_code, card_number) in _ESCAPE_HATCH
