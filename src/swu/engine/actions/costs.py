"""What a card costs to play, and how that cost gets paid.

Printed cost is rarely the price.  ``_effective_cost`` layers on the aspect penalty
(+2 per missing aspect icon, CR "Aspect Penalty"), then ``_play_cost`` applies
discounts from three independent sources — a pending one-shot discount pushed by an
ability, a standing discount from a constant ability, and an opponent-imposed tax —
and ``_pay_play_cost`` finally exhausts resources, spending Credit tokens before
cards when both are available.

Splitting "what does it cost" from "can I afford it" from "take the payment" is
what lets the same three functions serve legality checks, the bots' evaluation and
the actual play action without any of them re-deriving the arithmetic.  Every
"you may play this for free" and "costs 1 less" ability in the game routes through
here rather than constructing its own price.

Notes worth keeping in view:

* **Aspect penalties can be waived from two directions** — by the controller
  (``_controller_waives_aspect_penalty``) or by the upgrade's host
  (``_host_waives_aspect_penalty``).  Both are checked; neither implies the other.
* **The available aspects are the base's *and* the deployed leader's.**
  ``_available_aspects`` is the single place that knows this, and getting it wrong
  silently overcharges for half the card pool.
* **Smuggle is a separate price, not a discount.** ``_smuggle_cost_parts`` returns
  the Smuggle cost and its own aspect penalty, because a card played via Smuggle is
  paying a different printed number with the same penalty rules.
"""
from __future__ import annotations

from collections import Counter
from typing import Optional

from swu.cards.models import AnyCard, Event, Upgrade, Unit
from swu.engine.events import (
    CreditDefeated,
)
from swu.engine.state import (
    CardInstance, GameState, PlayerState, ability_suppressed,
)

from swu.engine.actions.base import (
    IllegalActionError,
)

# ── Effective-stats layer ─────────────────────────────────────────────────────

_ASPECT_ICON_KEYS: set | None = None
_FLIP_LEADER_ASPECT_KEYS: set | None = None


def _aspect_icon_provider_keys() -> set:
    """(set_code, card_number) keys of every card carrying a ``ProvidesAspectIcons``
    marker (The Darksaber ASH_135 — one card today).

    ``_available_aspects`` is called from ``_effective_cost`` for EVERY cost
    computation, i.e. once per playable card at every legal-action enumeration, so
    its upgrade walk must be skipped outright while no such card is registered —
    the ``_printed_stats_override_keys`` / ``_suppress_leader_keys`` trick."""
    global _ASPECT_ICON_KEYS
    if _ASPECT_ICON_KEYS is None:
        from swu.abilities.registry import get_all_registered, ProvidesAspectIcons
        _ASPECT_ICON_KEYS = {
            key for key, specs in get_all_registered().items()
            if any(isinstance(sp, ProvidesAspectIcons) for sp in specs)
        }
    return _ASPECT_ICON_KEYS


def _flip_leader_aspect_keys() -> dict:
    """(set_code, card_number) -> the ``FlipLeaderAspects`` marker, for every flip
    leader whose two sides print different aspect icons (Chancellor Palpatine TWI_17 —
    one card today).

    ``_available_aspects`` runs for EVERY cost computation, so the lookup must be a
    prebuilt dict rather than a per-call spec walk — the ``_aspect_icon_provider_keys``
    / ``_suppress_leader_keys`` trick."""
    global _FLIP_LEADER_ASPECT_KEYS
    if _FLIP_LEADER_ASPECT_KEYS is None:
        from swu.abilities.registry import get_all_registered, FlipLeaderAspects
        _FLIP_LEADER_ASPECT_KEYS = {
            key: next(sp for sp in specs if isinstance(sp, FlipLeaderAspects))
            for key, specs in get_all_registered().items()
            if any(isinstance(sp, FlipLeaderAspects) for sp in specs)
        }
    return _FLIP_LEADER_ASPECT_KEYS


# ── distribute_damage decision helpers ───────────────────────────────────────

def _card_aspect_names(ci: CardInstance, state: "GameState | None") -> tuple:
    """The aspect icons ``ci`` actually provides right now.

    Normally the card's printed aspects.  A FLIP LEADER whose two sides print
    different icons (Chancellor Palpatine TWI_17) instead reports only the side
    currently face up, read off ``game_memory.flipped_leaders`` — the DB carries one
    aspect list per row, so such a card arrives with the UNION of both sides and would
    otherwise waive a penalty for a side that is not showing.  ``state`` is optional
    (a few call sites compute a cost with no state to hand); without it the printed
    union is the only thing readable, i.e. the pre-marker behaviour."""
    printed = tuple(a.name for a in (getattr(ci.card_def, "aspects", None) or ()))
    keys = _flip_leader_aspect_keys()
    if not keys or state is None:
        return printed
    sc = getattr(ci.card_def, "set_code", None) or ""
    cn = getattr(ci.card_def, "card_number", None) or ""
    marker = keys.get((sc, cn))
    if marker is None:
        return printed
    flipped = getattr(getattr(state, "game_memory", None), "flipped_leaders", None) or ()
    return tuple(marker.back if ci.instance_id in flipped else marker.front)


def _available_aspects(ps: PlayerState,
                       state: "GameState | None" = None) -> "Counter[str]":
    """The aspect icons that count against play costs for ``ps``: the union of the
    player's **base and leader** aspects, counting duplicates.

    The leader always provides its aspects for cost purposes, whether it is
    undeployed (sitting in ``base_zone``, already counted by the loop) or
    **deployed** as a unit in an arena (no longer in ``base_zone``).  Reading only
    ``base_zone`` dropped a deployed leader's aspects, inflating every play cost
    with spurious aspect penalties once the leader hit the table (Daimyo's Palace
    LAW_20 / Leia Organa: a fully-matched Lando Calrissian wrongly showed "5 +2").

    Each card's icons go through ``_card_aspect_names``, so a flip leader contributes
    only the side currently face up (Chancellor Palpatine TWI_17) — which is why
    ``state`` is threaded here at all."""
    available: Counter[str] = Counter()
    seen: set[str] = set()
    for ci in ps.base_zone:
        seen.add(ci.instance_id)
        for name in _card_aspect_names(ci, state):
            available[name] += 1
    leader = ps.leader_instance
    if leader is not None and leader.instance_id not in seen:
        for name in _card_aspect_names(leader, state):
            available[name] += 1
    # "Attached unit gains: 'While you are paying costs, this unit provides its
    # aspect icons.'" (The Darksaber ASH_135) — a third icon source beside the base
    # and the leader.  The icons are the HOST's.  ⚡ This function runs for EVERY cost
    # computation, so the walk is gated on the cached registry index first and then
    # skipped for any unit carrying no upgrades: an ordinary board pays one set
    # membership test for it.
    keys = _aspect_icon_provider_keys()
    if keys:
        for host in ps.ground_arena + ps.space_arena:
            for up in host.attached_upgrades:
                sc = getattr(up.card_def, "set_code", None) or ""
                cn = getattr(up.card_def, "card_number", None) or ""
                if (sc, cn) in keys:
                    for a in host.card_def.aspects:
                        available[a.name] += 1
                    break
    return available


def _effective_cost(card: AnyCard, ps: PlayerState,
                    state: "GameState | None" = None) -> int:
    """Card cost + 2 per unmatched aspect pip (counting duplicates).

    ``state`` is threaded only so a flip leader reports the side currently face up
    (Chancellor Palpatine TWI_17); every other card reads the same either way."""
    base_cost = getattr(card, "cost", 0) or 0
    card_aspects = Counter(a.name for a in card.aspects)
    if not card_aspects:
        return base_cost
    available = _available_aspects(ps, state)
    penalty = 0
    for aspect, needed in card_aspects.items():
        have = available[aspect]
        missing = max(0, needed - have)
        penalty += missing * 2
    return base_cost + penalty


def _play_cost_reduction(state: GameState, ci: CardInstance,
                         target_host_id: Optional[str] = None) -> int:
    """Sum of any card-level CostReduction abilities whose condition currently
    holds (Force Choke SOR_139, etc.).  Read from the card's registered specs so
    each card declares its own reduction rather than the play path special-casing
    it inline.  Conditions are evaluated against the card's controller.

    ``target_host_id`` is the unit a played UPGRADE is being attached to (None for
    units/events, or when affordability is checked before a host is chosen).  A
    CostReduction carrying ``host_named`` applies only when that host's name
    contains the named string ("While playing this upgrade on General Grievous, it
    costs 2 resources less" — Grievous's Wheel Bike TWI_236)."""
    from swu.abilities.registry import get_abilities, CostReduction
    sc = getattr(ci.card_def, "set_code", None) or ""
    cn = getattr(ci.card_def, "card_number", None) or ""
    total = 0
    for spec in get_abilities(sc, cn):
        if isinstance(spec, CostReduction):
            if getattr(spec, "host_named", None) is not None:
                if target_host_id is None:
                    continue
                res = state.find_instance(target_host_id)
                if res is None:
                    continue
                _, host = res
                if spec.host_named not in (getattr(host.card_def, "name", None) or ""):
                    continue
            if getattr(spec, "host_trait", None):
                # "This upgrade costs 1 resource less to play on an Imperial unit"
                # (Faith in the Empire ASH_262, The Way of the Mand'alor ASH_263) —
                # the ``host_named`` sibling keyed on the host's EFFECTIVE traits.
                # No host chosen yet ⇒ no reduction, like host_unique.
                if target_host_id is None:
                    continue
                res = state.find_instance(target_host_id)
                if res is None:
                    continue
                from swu.engine.traits import has_trait
                if not has_trait(state, res[1], str(spec.host_trait)):
                    continue
            if getattr(spec, "host_unique", False):
                # "This upgrade costs 1 resource less to play on a unique unit"
                # (Mastery LAW_129) — the host_named sibling, keyed on a PROPERTY of
                # the chosen host.  No host chosen yet ⇒ no reduction, so a
                # pre-pick affordability check is never over-generous.
                if target_host_id is None:
                    continue
                res = state.find_instance(target_host_id)
                if res is None or not getattr(res[1].card_def, "is_unique", False):
                    continue
            if spec.condition is None or spec.condition.evaluate(state, ci):
                per = getattr(spec, "per_controller_base_damage", None)
                if per:
                    # Scaling reduction: ``amount`` once per ``per`` damage on the
                    # controller's base (Resolute TWI_151, "1 less for every 5
                    # damage on your base").
                    base = state.player_by_id(ci.owner_id).base_instance
                    marks = int(getattr(base, "damage", 0) or 0) if base is not None else 0
                    total += spec.amount * (marks // per)
                elif getattr(spec, "per_max_opponent_units", False):
                    # Scaling reduction: ``amount`` once per unit controlled by the
                    # opponent who controls the most units (Republic Defense Carrier
                    # TWI_98).  Two players ⇒ the single opponent's unit count.
                    own_idx = state.player_index(ci.owner_id)
                    most = max(
                        (len(p.ground_arena) + len(p.space_arena)
                         for i, p in enumerate(state.players) if i != own_idx),
                        default=0,
                    )
                    total += spec.amount * most
                elif getattr(spec, "per_friendly_pilots", False):
                    # Scaling reduction: ``amount`` once per friendly Pilot unit AND
                    # per friendly Pilot upgrade (Red Leader JTL_101).  The same
                    # count basis as the ``other_friendly_pilots`` StatBonus source
                    # (Nien Nunb JTL_93) but WITHOUT its self-exclusion — Red Leader
                    # is in hand while this is read, so it is never in the count.
                    from swu.engine.traits import has_trait
                    ps_own = state.player_by_id(ci.owner_id)
                    pilots = 0
                    for u in ps_own.ground_arena + ps_own.space_arena:
                        if has_trait(state, u, "Pilot"):
                            pilots += 1
                        for up in u.attached_upgrades:
                            if "Pilot" in (getattr(up.card_def, "traits", ()) or ()):
                                pilots += 1
                    total += spec.amount * pilots
                elif getattr(spec, "per_controller_card_played_this_phase", False):
                    # Scaling reduction: ``amount`` once per OTHER card the
                    # controller played this phase (Tribunal TS26_36).  The
                    # ``cards_played_this_phase`` counter is incremented at the
                    # CardPlayed chokepoint, i.e. AFTER this cost is computed, so
                    # the card being played is never in its own count — which is
                    # exactly the printed "each OTHER card".
                    played = state.game_memory.cards_played_this_phase.get(
                        ci.owner_id, 0)
                    total += spec.amount * int(played)
                elif getattr(spec, "per_friendly_units", False):
                    # Scaling reduction: ``amount`` once per friendly unit, either
                    # arena, trait-blind (Encircle TS26_61) — the ``per_friendly_trait``
                    # basis with the filter dropped.  The card being played is in
                    # hand, so it never counts itself.
                    ps_own = state.player_by_id(ci.owner_id)
                    total += spec.amount * (len(ps_own.ground_arena)
                                            + len(ps_own.space_arena))
                elif getattr(spec, "per_friendly_trait", None):
                    # Scaling reduction: ``amount`` once per friendly unit with the
                    # named trait (Vuutun Palaa SEC_122, "Droid").  Read through
                    # ``has_trait`` so granted traits count; the card being played is
                    # in hand, so it never counts itself.
                    from swu.engine.traits import has_trait
                    ps_own = state.player_by_id(ci.owner_id)
                    want = spec.per_friendly_trait
                    total += spec.amount * sum(
                        1 for u in ps_own.ground_arena + ps_own.space_arena
                        if has_trait(state, u, want))
                elif getattr(spec, "per_friendly_damaged_unit", False):
                    # Scaling reduction: ``amount`` once per DAMAGED unit the
                    # controller controls, either arena (Phoenix Squadron Fighters
                    # LAW_110).  The card being played is in hand, so it can never
                    # count itself.
                    ps_own = state.player_by_id(ci.owner_id)
                    total += spec.amount * sum(
                        1 for u in ps_own.ground_arena + ps_own.space_arena
                        if int(getattr(u, "damage", 0) or 0) > 0
                    )
                elif getattr(spec, "per_damaged_ground_unit", False):
                    # Scaling reduction: ``amount`` once per DAMAGED ground-arena unit
                    # (AT-DP Occupier JTL_163).  "Each damaged ground unit" names no
                    # controller, so both players' ground arenas count.
                    damaged = sum(
                        1 for p in state.players for u in p.ground_arena
                        if int(getattr(u, "damage", 0) or 0) > 0
                    )
                    total += spec.amount * damaged
                elif getattr(spec, "per_friendly_leader_unit", False):
                    # Scaling reduction: ``amount`` once per friendly LEADER UNIT
                    # (Take Action TS26_71).  ``_is_leader_unit`` is the same basis
                    # the ``leader_unit`` predicate uses — a deployed leader in an
                    # arena, or a unit carrying a leader as a Pilot upgrade — so an
                    # undeployed leader in the base zone correctly counts for nothing.
                    from swu.abilities.resolver import _is_leader_unit
                    ps_own = state.player_by_id(ci.owner_id)
                    total += spec.amount * sum(
                        1 for u in ps_own.ground_arena + ps_own.space_arena
                        if _is_leader_unit(u)
                    )
                elif getattr(spec, "per_controller_discard_this_phase", False):
                    # Scaling reduction: ``amount`` once per card the CONTROLLER
                    # discarded this phase (Fear and Dead Men LAW_179).  Ownership is
                    # read back off each discarded instance (the LAW_76
                    # CONTROLLER_DISCARDED_THIS_PHASE trick — no new state).
                    mine = 0
                    for cid in (state.game_memory.cards_discarded_this_phase or ()):
                        res = state.find_instance(cid)
                        if res is not None and res[1].owner_id == ci.owner_id:
                            mine += 1
                    total += spec.amount * mine
                else:
                    total += spec.amount
    return total


def _shares_keyword_with_a_unit(state: GameState, ci: CardInstance,
                                player_id: str) -> bool:
    """Does ``ci`` share a printed keyword with a unit ``player_id`` controls?

    Morgan Elsbeth LOF_5 ("… if it shares a keyword with a friendly unit" / "a unit
    … that shares a keyword with the chosen unit").  PRINTED keywords on the played
    card, because it is still in hand — which is also the card's own printed rules
    note ("the unit being played must already have a shared keyword while paying its
    cost")."""
    want = {str(k).split()[0] for k in (getattr(ci.card_def, "keywords", None) or ())}
    if not want:
        return False
    ps = state.player_by_id(player_id)
    for u in ps.ground_arena + ps.space_arena:
        if u.instance_id == ci.instance_id:
            continue
        theirs = {str(k).split()[0]
                  for k in (getattr(u.card_def, "keywords", None) or ())}
        if want & theirs:
            return True
    return False


def _play_discount_entry_matches(entry: dict, ci: CardInstance, ps: PlayerState,
                                 traits: set, via_plot: bool = False,
                                 state: Optional[GameState] = None) -> bool:
    """Whether a pending NextPlayDiscount ``entry`` applies to playing ``ci``: same
    controller, the card carries the entry's trait, and — unless the entry waives it
    (``units_only=False``, Tranquility TWI_246's "<trait> cards") — the card is a
    Unit (Khetanna LAW_158's "<trait> unit").  Old entries lack ``units_only`` and
    default to True (units-only), preserving Khetanna's behaviour.

    A ``plot_only`` entry (Chancellor Palpatine SEC_1's "next card you play using
    Plot") applies only when the card is being played via the Plot keyword
    (``via_plot`` — set only by the ``PlotPlay`` path)."""
    if entry.get("player_id") != ps.player_id:
        return False
    if entry.get("plot_only", False) and not via_plot:
        return False
    t = entry.get("trait")
    if t and t not in traits:  # empty/None trait = any card ("the next unit",
        return False           # General's Blade TWI_121); non-empty must match
    if entry.get("units_only", True) and not isinstance(ci.card_def, Unit):
        return False
    ctype = entry.get("card_type")
    if ctype == "event" and not isinstance(ci.card_def, Event):
        # "The next EVENT you play this phase costs N resource(s) less" (Rex TS26_6,
        # Ahsoka's Lightsabers TS26_35).  The card-TYPE narrowing beside
        # ``units_only``'s Unit one; an entry without the key matches any type, so
        # every existing discount is untouched.
        return False
    excl = entry.get("exclude_aspects") or ()
    if excl:  # Bendu SOR_56: "non-[Heroism], non-[Villainy] card" — any excluded
        card_aspects = {a.name for a in (getattr(ci.card_def, "aspects", ()) or ())}
        if card_aspects.intersection(excl):  # aspect on the card disqualifies it
            return False
    name = entry.get("card_name")
    if name and getattr(ci.card_def, "name", None) != name:
        return False  # "a COPY of that unit" (Jump to Lightspeed JTL_232)
    if entry.get("shares_keyword_with_friendly"):
        # "… if it shares a keyword with a friendly unit" (Morgan Elsbeth LOF_5).
        if state is None or not _shares_keyword_with_a_unit(state, ci, ps.player_id):
            return False
    return True


def _play_discount_entry_amount(entry: dict, ci: CardInstance, ps: PlayerState,
                                state: "GameState | None" = None) -> int:
    """The discount a matching pending entry is worth for ``ci``.

    A ``free`` entry ("you may play it for free" — Jump to Lightspeed JTL_232) is
    worth the card's whole aspect-adjusted cost, so the play really costs 0
    whatever the aspect penalty; every other entry is worth its fixed ``amount``."""
    if entry.get("free"):
        return _effective_cost(ci.card_def, ps, state)
    return int(entry.get("amount", 0) or 0)


def _pending_play_discount(state: GameState, ci: CardInstance, ps: PlayerState,
                           via_plot: bool = False) -> int:
    """Amount of the FIRST pending NextPlayDiscount (Khetanna LAW_158 / Tranquility
    TWI_246) that applies to playing ``ci`` from hand — read-only, does NOT consume.
    Used by ``_play_cost`` so both the affordability check and the actual payment see
    the discount; the entry is consumed separately at the real play site
    (``_consume_play_discount``).  ``via_plot`` lets a plot_only discount (SEC_1)
    apply to a Plot play."""
    traits = set(getattr(ci.card_def, "traits", ()) or ())
    for entry in state.game_memory.pending_play_discounts:
        if _play_discount_entry_matches(entry, ci, ps, traits, via_plot, state):
            return _play_discount_entry_amount(entry, ci, ps, state)
    return 0


def _card_matches_standing_discount(card_def, applies_to: str) -> bool:
    """Whether the card being played satisfies a ``StandingPlayDiscount``'s
    ``applies_to`` predicate.  Only ``"has_when_defeated_ability"`` today (Director
    Krennic JTLP_1): the card is a Unit whose printed text carries a "When Defeated"
    ability.  Read from the DB text (not the registered specs) so it holds regardless
    of whether the played card is itself encoded.  DEVIATION: a Bounty is rules-wise
    a When-Defeated ability but is printed "Bounty —", so it does not match — a rare,
    documented corner."""
    if applies_to == "has_when_defeated_ability":
        if not isinstance(card_def, Unit):
            return False
        text = (getattr(card_def, "text", None) or "").replace("\xa0", " ")
        return "when defeated" in text.lower()
    if applies_to == "unit":
        # "The first UNIT you play each round costs 2 resources less" (Death Star
        # Plans JTL_260, conferred on the attached unit's controller).  No trait or
        # text gate at all — every Unit card qualifies.
        return isinstance(card_def, Unit)
    if applies_to.startswith("trait:"):
        # "Each <Trait> unit you play costs N resources less" (Admiral Piett JTL_5
        # deployed: Capital Ship).  A card in hand carries only its PRINTED traits,
        # so a plain membership test suffices — the ``creature_unit`` reading, but
        # parameterised by trait instead of hardcoded.
        if not isinstance(card_def, Unit):
            return False
        return applies_to.split(":", 1)[1] in (getattr(card_def, "traits", ()) or ())
    if applies_to.startswith("card_trait:"):
        # The CARD-TYPE-BLIND sibling of the arm above: "The first Gambit CARD you
        # play each round costs 1 resource less" (The Master Codebreaker LAW_229).
        # Gambit is printed almost entirely on Events (and a couple of Upgrades),
        # so the Unit gate would make the whole clause dead text.
        return applies_to.split(":", 1)[1] in (getattr(card_def, "traits", ()) or ())
    if applies_to == "creature_unit":
        # Malakili LOF_108: "The first Creature unit you play each phase costs 1
        # less".  A card in hand carries only its PRINTED traits, so a plain
        # ``card_def.traits`` membership test suffices (no in-play trait grants).
        # NOTE: "each phase" is modelled with ``once_per_round`` — there is exactly
        # one ACTION phase per round (Max Rebo LAW_72 adds only an extra *regroup*
        # phase, in which no card is played), so "first Creature each phase" and
        # "first each round" coincide for plays.
        if not isinstance(card_def, Unit):
            return False
        return "Creature" in (getattr(card_def, "traits", ()) or ())
    if applies_to == "trick_event":
        # Jabba the Hutt SOR_181: "Each TRICK event you play costs 1 resource
        # less."  An unlimited (``once_per_round=False``) standing discount on
        # every Trick-trait Event the controller plays.  A card in hand carries
        # only its PRINTED traits, so a plain membership test suffices.
        if not isinstance(card_def, Event):
            return False
        return "Trick" in (getattr(card_def, "traits", ()) or ())
    if applies_to == "upgrade":
        # Congress of Malastare SEC_64: "The first UPGRADE you play each phase costs
        # 1 resource less."  The host-free sibling of ``upgrade_on_source`` — card
        # type only, any host.  "each phase" is modelled with ``once_per_round``
        # (the Malakili LOF_108 equivalence: one action phase per round).
        return isinstance(card_def, Upgrade)
    if applies_to == "upgrade_not_on_source":
        # Pit Droid Team ASH_75: "The first upgrade you play on ANOTHER friendly unit
        # each phase costs 1 resource less."  Card-type check only; the "not on this
        # unit, and on a unit you control" host match is enforced by the caller
        # (_standing_play_discount_sources), which knows both.
        return isinstance(card_def, Upgrade)
    if applies_to == "upgrade_on_source":
        # Guardian of the Whills SOR_61: "The first upgrade you play on this unit
        # each round costs 1 less."  Card-type check only; the "on this unit" host
        # match (target_host_id == the source's instance) is enforced by the caller
        # (_standing_play_discount_sources), which knows the discount source and the
        # chosen host.
        return isinstance(card_def, Upgrade)
    return False


def _standing_discount_key(src: CardInstance, ps: PlayerState) -> str:
    """The per-round spend key of a ``once_per_round`` ``StandingPlayDiscount``.

    A unit-borne discount is keyed by its source instance alone (the source sits in
    its controller's own arena, so the beneficiary never changes).  An UPGRADE-borne
    one is keyed by instance AND beneficiary, because the upgrade changes hands
    mid-round — Death Star Plans JTL_260's printed rules note is explicit: "Multiple
    players can benefit from the discount ability in the same round." """
    from swu.cards.models import Upgrade
    if isinstance(src.card_def, Upgrade):
        return f"{src.instance_id}@{ps.player_id}"
    return src.instance_id


def _standing_play_discount_sources(state: GameState, ci: CardInstance,
                                    ps: PlayerState,
                                    target_host_id: Optional[str] = None) -> list[CardInstance]:
    """In-play units controlled by ``ps`` carrying a ``StandingPlayDiscount`` marker
    that currently applies to playing ``ci`` (predicate matches AND, if
    ``once_per_round``, the source has not yet spent its discount this round).  Used
    by both the read (``_standing_play_discount``) and consume
    (``_consume_standing_discount``) so they never disagree.  ``target_host_id`` (an
    upgrade's chosen host) gates a host-scoped ``"upgrade_on_source"`` discount
    (Guardian of the Whills SOR_61) to upgrades being played onto the source unit.

    An ATTACHED UPGRADE carrying the marker counts too — "Attached unit gains: 'The
    first unit you play each round costs 2 resources less'" (Death Star Plans
    JTL_260).  The discount then belongs to the HOST's controller, which is exactly
    the arena we are scanning, so an upgrade sitting on an enemy unit benefits that
    enemy — the printed "attached unit gains" reading."""
    from swu.abilities.registry import get_abilities, StandingPlayDiscount
    used = state.game_memory.standing_play_discounts_used_this_round
    out: list[CardInstance] = []
    for host in ps.ground_arena + ps.space_arena:
        for src in (host, *host.attached_upgrades):
            sc = getattr(src.card_def, "set_code", None) or ""
            cn = getattr(src.card_def, "card_number", None) or ""
            for spec in get_abilities(sc, cn):
                if isinstance(spec, StandingPlayDiscount) and _card_matches_standing_discount(
                    ci.card_def, spec.applies_to
                ):
                    # "on this unit" host gate — the upgrade must attach to the source.
                    if spec.applies_to == "upgrade_on_source" and target_host_id != src.instance_id:
                        continue
                    # …and its complement: "on ANOTHER friendly unit" (Pit Droid Team
                    # ASH_75) needs a chosen host that is neither the source itself nor
                    # a unit the source's controller does not control.
                    if spec.applies_to == "upgrade_not_on_source":
                        if target_host_id is None or target_host_id == src.instance_id:
                            continue
                        if not any(u.instance_id == target_host_id
                                   for u in ps.ground_arena + ps.space_arena):
                            continue
                    if spec.once_per_round and _standing_discount_key(src, ps) in used:
                        continue
                    out.append(src)
                    break
    return out


def _standing_play_discount(state: GameState, ci: CardInstance, ps: PlayerState,
                            target_host_id: Optional[str] = None) -> int:
    """Sum of the amounts of every applicable, un-spent ``StandingPlayDiscount``
    sourced by an in-play unit ``ps`` controls (Director Krennic JTLP_1) — read-only,
    does NOT consume.  Read by ``_play_cost`` so affordability and payment agree; the
    per-round marker is spent separately at the real play site
    (``_consume_standing_discount``)."""
    from swu.abilities.registry import get_abilities, StandingPlayDiscount
    total = 0
    for src in _standing_play_discount_sources(state, ci, ps, target_host_id):
        sc = getattr(src.card_def, "set_code", None) or ""
        cn = getattr(src.card_def, "card_number", None) or ""
        for spec in get_abilities(sc, cn):
            if isinstance(spec, StandingPlayDiscount) and _card_matches_standing_discount(
                ci.card_def, spec.applies_to
            ):
                total += spec.amount
                break
    return total


def _opponent_play_tax(state: GameState, ci: CardInstance, ps: PlayerState) -> int:
    """Extra resources ``ps`` must pay to play ``ci`` because an ENEMY in-play unit
    carries an ``OpponentPlayTax`` marker matching the card's type (Del Meeko
    SOR_34: "Each event an opponent plays costs 1 resource more").  Read by
    ``_play_cost`` so both affordability and payment see the surcharge; a no-op
    unless an opponent controls such a unit and the card type matches.

    Also folds in the phase-scoped, effect-GRANTED unit surcharge
    ``game_memory.unit_play_tax_this_phase`` ("Each unit that opponent plays this
    phase costs 1 resource more" — Moff Gideon JTL_188), which is recorded against a
    player rather than derived from a card in play and so survives the source
    leaving play, exactly as printed."""
    from swu.abilities.registry import (
        get_abilities, OpponentPlayTax, NamedCardPlayTax)
    total = 0
    if isinstance(ci.card_def, Unit):
        total += int(
            state.game_memory.unit_play_tax_this_phase.get(ps.player_id, 0) or 0)
    name = getattr(ci.card_def, "name", None)
    opp = state.players[1 - state.player_index(ps.player_id)]
    for src in opp.ground_arena + opp.space_arena:
        sc = getattr(src.card_def, "set_code", None) or ""
        cn = getattr(src.card_def, "card_number", None) or ""
        named = getattr(src, "named_card", None)
        for spec in get_abilities(sc, cn):
            if isinstance(spec, OpponentPlayTax):
                matches = (spec.card_type == "event" and isinstance(ci.card_def, Event))
                if matches:
                    total += spec.amount
            elif isinstance(spec, NamedCardPlayTax):
                # Per-name surcharge (Qi'ra SHD_202): only a card whose name the
                # source has named is taxed.
                if name is not None and named == name:
                    total += spec.amount
    return total


def resource_cost_for(state: GameState, ps: PlayerState, n: int) -> int:
    """The resources ``ps`` actually pays for a determined cost of ``n``.

    Today the only modifier is the ``HalvePaidCosts`` marker (The Starhawk
    JTL_105, "While paying costs, you pay half as many resources, rounded up"),
    which applies to BOTH card costs and ability costs — so this helper is read at
    the play-cost seam ``_play_cost`` and at every activated-ability
    ``PayResources`` affordability check plus its payment site.  A no-op (returns
    ``n``) for a board with no such marker.

    Non-resource costs (exhaust, defeat, discard) are untouched, as printed."""
    if n <= 0:
        return n
    from swu.abilities.registry import get_abilities, HalvePaidCosts
    for ci in ps.ground_arena + ps.space_arena:
        if ability_suppressed(state, ci):
            continue
        sc = getattr(ci.card_def, "set_code", None) or ""
        cn = getattr(ci.card_def, "card_number", None) or ""
        if not sc or not cn:
            continue
        if any(isinstance(spec, HalvePaidCosts) for spec in get_abilities(sc, cn)):
            return -(-n // 2)  # halved, rounded UP
    return n


def _play_cost(state: GameState, ci: CardInstance, ps: PlayerState,
               target_host_id: Optional[str] = None, via_plot: bool = False) -> int:
    """Effective resource cost to play ``ci`` from hand: aspect-adjusted cost
    minus any active card-level cost reductions, any applicable pending
    "next <trait> unit costs N less" discount (Khetanna LAW_158), and any
    standing per-play discount from an in-play source (Director Krennic JTLP_1),
    PLUS any opponent-imposed play tax (Del Meeko SOR_34), floored at 0.  Used by
    both the legality (affordability) check and the actual resource payment so the
    two never diverge.  ``target_host_id`` (an upgrade's chosen host) lets a
    host-conditional reduction apply (Grievous's Wheel Bike TWI_236).  ``via_plot``
    (set only by the Plot play path) lets a plot_only "next card you play using
    Plot" discount apply (Chancellor Palpatine SEC_1)."""
    base = _effective_cost(ci.card_def, ps, state)
    reduction = (_play_cost_reduction(state, ci, target_host_id)
                 + _pending_play_discount(state, ci, ps, via_plot)
                 + _standing_play_discount(state, ci, ps, target_host_id)
                 # The two aspect-penalty waivers overlap only in principle (one keys
                 # off an upgrade's host, the other off the controller's board), so
                 # take the larger rather than double-subtracting the same penalty.
                 + max(_host_waives_aspect_penalty(state, ci, ps, target_host_id),
                       _controller_waives_aspect_penalty(state, ci, ps)))
    tax = _opponent_play_tax(state, ci, ps)
    return resource_cost_for(state, ps, max(0, base - reduction + tax))


def _host_waives_aspect_penalty(state: GameState, ci: CardInstance, ps: PlayerState,
                                target_host_id: Optional[str]) -> int:
    """Resources waived because the UNIT a played upgrade is being attached to carries
    an ``IgnoreAspectPenaltyForUpgrades`` marker (General Grievous TWI_34: "Ignore the
    aspect penalty on each Lightsaber upgrade you play on this unit").

    Returns the played card's FULL aspect penalty — "ignore the aspect penalty",
    unqualified, unlike the single-pip Daimyo's Palace LAW_20 waiver — or 0 when there
    is no host, no marker, or the upgrade lacks the marker's traits.  Nothing else is
    waived, so a non-upgrade play (``target_host_id`` is None) can never reach here."""
    if target_host_id is None:
        return 0
    res = state.find_instance(target_host_id)
    if res is None:
        return 0
    _, host = res
    if ability_suppressed(state, host):
        return 0
    from swu.abilities.registry import get_abilities, IgnoreAspectPenaltyForUpgrades
    from swu.engine.traits import has_trait
    sc = getattr(host.card_def, "set_code", None) or ""
    cn = getattr(host.card_def, "card_number", None) or ""
    for spec in get_abilities(sc, cn):
        if not isinstance(spec, IgnoreAspectPenaltyForUpgrades):
            continue
        if spec.traits and not all(has_trait(state, ci, t) for t in spec.traits):
            continue
        return _aspect_penalty(
            tuple(a.name for a in (getattr(ci.card_def, "aspects", None) or ())),
            ps, state)
    return 0


def _controller_waives_aspect_penalty(state: GameState, ci: CardInstance,
                                      ps: PlayerState) -> int:
    """Resources waived because the playing controller has a card in play carrying an
    ``IgnoreAspectPenaltyForPlays`` marker that matches the played card (Nala Se TWI_1:
    "Ignore the aspect penalty on Clone units you play").

    The controller-scoped sibling of ``_host_waives_aspect_penalty``.  Scans the
    controller's base_zone (so an UNDEPLOYED leader's copy of the clause counts, and
    the base itself could carry one) and both arenas; returns the played card's FULL
    aspect penalty, or 0 when no marker matches."""
    from swu.abilities.registry import get_abilities, IgnoreAspectPenaltyForPlays
    from swu.cards.models import Unit, Event, Upgrade
    from swu.engine.traits import has_trait
    _TYPES = {"unit": Unit, "event": Event, "upgrade": Upgrade}
    # ``ci`` itself leads the scan for a SELF marker ("While playing THIS unit,
    # ignore his Villainy aspect penalty if you control Rey" — Kylo Ren P25_46).
    # The played card is in HAND, so no in-play scan could ever reach it; the
    # ``self_only`` flag keeps the two readings disjoint, so no existing marker
    # newly applies to its own card's play.
    for src in [ci] + list(ps.base_zone) + list(ps.ground_arena) + list(ps.space_arena):
        sc = getattr(src.card_def, "set_code", None) or ""
        cn = getattr(src.card_def, "card_number", None) or ""
        if not sc or not cn:
            continue
        specs = [s for s in get_abilities(sc, cn)
                 if isinstance(s, IgnoreAspectPenaltyForPlays)
                 and bool(getattr(s, "self_only", False)) is (src is ci)]
        if not specs or ability_suppressed(state, src):
            continue
        for spec in specs:
            if spec.card_type == "non_unit":
                # "the first NON-UNIT card you play each phase" (Peli Motto ASH_212)
                # — the complement filter, the push_name_and_discard LOF_226 shape.
                if isinstance(ci.card_def, Unit):
                    continue
            else:
                want = _TYPES.get(spec.card_type or "")
                if want is not None and not isinstance(ci.card_def, want):
                    continue
            if spec.traits and not all(has_trait(state, ci, t) for t in spec.traits):
                continue
            played_aspects = {a.name for a in
                              (getattr(ci.card_def, "aspects", None) or ())}
            if spec.exclude_aspects and (played_aspects & set(spec.exclude_aspects)):
                continue  # "non-Villainy …" (Mon Mothma SEC_9)
            if getattr(spec, "aspects", ()) and not played_aspects.issuperset(
                    spec.aspects):
                continue  # "Heroism units you play" (Hera Syndulla LAW_9)
            cond = getattr(spec, "condition", None)
            if cond is not None and not cond.evaluate(state, src):
                continue  # "While you control 2 or more units, …" (LAW_9)
            names = tuple(a.name for a in
                          (getattr(ci.card_def, "aspects", None) or ()))
            only = tuple(getattr(spec, "only_aspects", ()) or ())
            if only:
                # "his VILLAINY aspect penalty" (Kylo Ren P25_46) — the MARGINAL cost
                # of those pips: the full penalty less the penalty the card would
                # carry without them, so a pip the base already matches waives 0.
                rest = tuple(n for n in names if n not in only)
                return (_aspect_penalty(names, ps, state)
                        - _aspect_penalty(rest, ps, state))
            return _aspect_penalty(names, ps, state)
    return 0


def _aspect_penalty(aspect_names: tuple[str, ...], ps: PlayerState,
                    state: "GameState | None" = None) -> int:
    """+2 per unmatched aspect pip (counting duplicates), matched against the
    controller's base/leader aspects — mirrors ``_effective_cost``."""
    if not aspect_names:
        return 0
    available = _available_aspects(ps, state)
    penalty = 0
    for aspect, needed in Counter(aspect_names).items():
        penalty += max(0, needed - available[aspect]) * 2
    return penalty


def _resources_have_granted_smuggle(state: GameState, ps: PlayerState) -> bool:
    """True if ``ps`` controls an in-play unit granting Smuggle to its resources
    (Tech, SHD_248 — GrantSmuggleToResources marker on a ConstantAbility)."""
    from swu.abilities.registry import (
        get_abilities, ConstantAbility, GrantSmuggleToResources,
    )
    for ci in ps.ground_arena + ps.space_arena:
        sc = getattr(ci.card_def, "set_code", None) or ""
        cn = getattr(ci.card_def, "card_number", None) or ""
        for spec in get_abilities(sc, cn):
            if isinstance(spec, ConstantAbility) and any(
                isinstance(eff, GrantSmuggleToResources) for eff in spec.effects
            ):
                return True
    return False


def _smuggle_cost_parts(
    state: GameState, ci: CardInstance, ps: PlayerState
) -> Optional[tuple[int, int]]:
    """``(base_cost, aspect_penalty)`` to play ``ci`` via Smuggle, or None if it
    cannot be smuggled.  ``base_cost`` is the bracketed Smuggle cost (printed
    Smuggle) or the card's printed cost + 2 (Smuggle granted by an in-play Tech);
    ``aspect_penalty`` is +2 per unmatched aspect pip against the player's
    base/leader aspects.  The total smuggle cost is the sum.  Splitting the two
    lets the UI mirror the hand-card "<base> +<penalty>" cost display."""
    from swu.engine.keywords import parse_smuggle_cost
    spec = parse_smuggle_cost(getattr(ci.card_def, "text", None))
    if spec is not None:
        n, aspects = spec
        return n, _aspect_penalty(aspects, ps, state)
    if _resources_have_granted_smuggle(state, ps):
        base = getattr(ci.card_def, "cost", 0) or 0
        aspects = tuple(a.name for a in (getattr(ci.card_def, "aspects", None) or ()))
        return base + 2, _aspect_penalty(aspects, ps, state)
    return None


def _exhaust_resources(ps: PlayerState, n: int) -> None:
    exhausted = 0
    for r in ps.resources:
        if not r.exhausted and exhausted < n:
            r.exhausted = True
            exhausted += 1
    if exhausted < n:
        raise IllegalActionError(f"Only {exhausted} ready resources, need {n}")


# ── Credit-token economy (jabba-the-hutt:07) ───────────────────────────────────

def _unit_resource_pool(ps: PlayerState) -> list[CardInstance]:
    """Ready friendly units that may be exhausted to pay costs as if they were
    resources (Vuutun Palaa SEC_122's ``UnitsPayCosts`` marker).

    A marker source anywhere in ``ps``'s arenas enables the pool; the pool itself is
    every READY unit of theirs matching the marker's traits (the marker source
    included — it is a Vehicle, not a Droid, so in practice it is not in its own
    pool).  Printed traits only: this is read from the payment path, where pulling in
    the trait-grant layer would recurse through cost computation.  Empty list (a
    cheap two-loop scan) when no marker is in play, so the ordinary payment path is
    unchanged."""
    from swu.abilities.registry import get_abilities, UnitsPayCosts
    specs: list = []
    units = list(ps.ground_arena) + list(ps.space_arena)
    for u in units:
        sc = getattr(u.card_def, "set_code", None) or ""
        cn = getattr(u.card_def, "card_number", None) or ""
        if not sc or not cn:
            continue
        specs.extend(s for s in get_abilities(sc, cn)
                     if isinstance(s, UnitsPayCosts))
    if not specs:
        return []
    out: list[CardInstance] = []
    for u in units:
        if u.exhausted:
            continue
        traits = set(getattr(u.card_def, "traits", ()) or ())
        if any(not spec.traits or traits.issuperset(spec.traits) for spec in specs):
            out.append(u)
    return out


def _usable_credits(s: Optional[GameState], ps: PlayerState) -> int:
    """How many of ``ps``'s Credit tokens can actually be spent.

    Normally all of them.  An OPPONENT with a ``EnemyCreditsLoseAbilities`` marker
    in play (Conveyex Security Captain LAW_117) strips the credit's only ability —
    its "defeat this token to pay 1 less" clause — so none of ``ps``'s credits can
    pay while such a unit is on the board.

    ``s`` may be None for the handful of legacy call sites with no state in scope;
    that reading is the unconditional one (every credit usable), which is also the
    answer for every board with no such marker."""
    n = len(ps.credits)
    if n == 0 or s is None:
        return 0 if n == 0 else n
    from swu.abilities.registry import get_abilities, EnemyCreditsLoseAbilities
    for opp in s.players:
        if opp.player_id == ps.player_id:
            continue
        for ci in opp.ground_arena + opp.space_arena:
            sc = getattr(ci.card_def, "set_code", None) or ""
            cn = getattr(ci.card_def, "card_number", None) or ""
            if not sc or not cn:
                continue
            if not any(isinstance(spec, EnemyCreditsLoseAbilities)
                       for spec in get_abilities(sc, cn)):
                continue
            if ability_suppressed(s, ci):
                continue
            return 0
    return n


def _affordable_with_credits(ps: PlayerState, cost: int,
                             s: Optional[GameState] = None) -> bool:
    """True if ``cost`` can be paid from ready resources, defeating credits, and —
    with a ``UnitsPayCosts`` marker in play (Vuutun Palaa SEC_122) — exhausting
    friendly units that pay "as if they were a resource".

    ``s`` (optional, for callers with the state in scope) lets the credit tier be
    switched off by an enemy ``EnemyCreditsLoseAbilities`` marker (LAW_117); the
    payment site ``_pay_play_cost`` always passes it, so gate and payment agree."""
    return (ps.available_resources + _usable_credits(s, ps)
            + len(_unit_resource_pool(ps))) >= cost


def _defeat_credit(s: GameState, ps: PlayerState) -> bool:
    """Defeat (remove) one Credit token from ``ps``.  Returns True if one was
    removed.  Credits are unlimited-supply tokens, so a defeated credit ceases to
    exist (it is not placed in any discard pile)."""
    if not ps.credits:
        return False
    credit = ps.credits.pop()
    s.event_log.append(CreditDefeated(
        player_id=ps.player_id,
        instance_id=credit.instance_id,
    ))
    return True


def _pay_play_cost(s: GameState, ps: PlayerState, cost: int) -> int:
    """Pay ``cost`` to play a card: exhaust ready resources first, then defeat
    Credit tokens to cover any shortfall.  Returns the number of credits defeated
    (so a "if you defeated a Credit while paying its cost" rider can read it).
    Raises ``IllegalActionError`` if ``cost`` cannot be covered even with credits."""
    if not _affordable_with_credits(ps, cost, s):
        raise IllegalActionError(
            f"Insufficient resources: need {cost}, have "
            f"{ps.available_resources} ready resources + {len(ps.credits)} credits")
    from_resources = min(cost, ps.available_resources)
    _exhaust_resources(ps, from_resources)
    credits_defeated = 0
    spendable = _usable_credits(s, ps)
    for _ in range(min(cost - from_resources, spendable)):
        if not _defeat_credit(s, ps):
            break
        credits_defeated += 1
    # Last tier: exhaust friendly units that pay as if they were resources (Vuutun
    # Palaa SEC_122).  Need-based and last, so an existing credit/resource payment is
    # untouched and a unit is never tapped for a play the row could already afford.
    shortfall = cost - from_resources - credits_defeated
    if shortfall > 0:
        for unit in _unit_resource_pool(ps)[:shortfall]:
            unit.exhausted = True
    return credits_defeated


# ── Play-a-card-from-hand-as-an-ability subsystem (Admiral Ozzel, SOR_129) ────

def _play_reduction_for(cd, base_reduction: int,
                        cost_reduction_if_trait) -> int:
    """The cost reduction to apply to card def ``cd`` — normally ``base_reduction``,
    but the higher value if ``cost_reduction_if_trait`` = ``(trait, reduction)`` is
    set and ``cd`` carries that trait.  "It costs 6 less; if it's a Force unit, it
    costs 8 less instead." (Palpatine's Return SHD_94) — a REPLACEMENT, not additive.
    """
    if cost_reduction_if_trait is not None:
        trait, reduction = cost_reduction_if_trait
        if trait in (getattr(cd, "traits", ()) or ()):
            return reduction
    return base_reduction


# ── Play an EVENT from hand as an ability (Bib Fortuna SOR_177) ────────────────

def _event_aspect_waiver(card_def, ps: PlayerState, ignore: bool,
                         state: "GameState | None" = None) -> int:
    """Resources waived by "ignoring its aspect penalties" (Anakin Skywalker LOF_18)
    — the card's WHOLE aspect penalty, the ``_play_upgrade_cost`` reading, not the
    single-pip Daimyo's Palace LAW_20 one.  0 when the rider is off."""
    if not ignore:
        return 0
    aspects = tuple(a.name for a in (getattr(card_def, "aspects", None) or ()))
    return _aspect_penalty(aspects, ps, state)


# ── Play an upgrade from hand for free, choosing a host (Jabba the Hutt ASH_42) ─

def _play_upgrade_cost(state: GameState, ctx: dict, upgrade_ci: CardInstance,
                       host_id: Optional[str] = None) -> int:
    """Resource cost to play ``upgrade_ci`` through this decision: its effective
    play cost less ``cost_reduction``, and — with ``ctx['ignore_aspect_penalty']``
    — less its WHOLE aspect penalty ("ignoring its aspect penalty", unqualified,
    A Fine Addition TWI_40; the General Grievous TWI_34 full-waiver reading, not
    the single-pip Daimyo's Palace LAW_20 one).  Floored at 0."""
    ps = state.player_by_id(ctx["controller_id"])
    cost = _play_cost(state, upgrade_ci, ps, target_host_id=host_id)
    if ctx.get("ignore_aspect_penalty"):
        aspects = tuple(a.name for a in (getattr(upgrade_ci.card_def, "aspects", None) or ()))
        cost -= _aspect_penalty(aspects, ps, state)
    return max(0, cost - int(ctx.get("cost_reduction", 0) or 0))


def _play_upgrade_affordable(state: GameState, ctx: dict,
                             upgrade_ci: CardInstance, cost: int) -> bool:
    """Can the controller pay ``cost`` for this play?

    ``from_resources`` (The Armorer ASH_1) needs the Smuggle "other ready resources"
    rule: the card being played leaves the resource row before the cost is paid, so
    it can never pay for itself — one more resource is required whenever the
    candidate is itself ready."""
    ps = state.player_by_id(ctx["controller_id"])
    if ctx.get("from_resources") and not upgrade_ci.exhausted:
        cost += 1
    return _affordable_with_credits(ps, cost, state)


# ── distribute_damage decision helpers ───────────────────────────────────────

def _consume_play_discount(state: GameState, ci: CardInstance, ps: PlayerState,
                           via_plot: bool = False) -> int:
    """Remove and return the amount of the first pending NextPlayDiscount that
    applies to playing ``ci`` (mirrors ``_pending_play_discount``'s match), or 0.
    Called once at the real play site so each discount applies to exactly one
    subsequent matching card.  ``via_plot`` lets a plot_only discount (SEC_1) be
    consumed by a Plot play."""
    traits = set(getattr(ci.card_def, "traits", ()) or ())
    for i, entry in enumerate(state.game_memory.pending_play_discounts):
        if _play_discount_entry_matches(entry, ci, ps, traits, via_plot, state):
            amt = _play_discount_entry_amount(entry, ci, ps, state)
            del state.game_memory.pending_play_discounts[i]
            return amt
    return 0


def _consume_standing_discount(state: GameState, ci: CardInstance, ps: PlayerState,
                               target_host_id: Optional[str] = None) -> None:
    """Mark each ``once_per_round`` ``StandingPlayDiscount`` source that discounted
    playing ``ci`` as spent for the round (Director Krennic JTLP_1: "the first unit
    you play each round …").  Called once at the real play site, mirroring
    ``_consume_play_discount``.  ``target_host_id`` gates a host-scoped upgrade
    discount (Guardian of the Whills SOR_61)."""
    from swu.abilities.registry import get_abilities, StandingPlayDiscount
    used = state.game_memory.standing_play_discounts_used_this_round
    for src in _standing_play_discount_sources(state, ci, ps, target_host_id):
        sc = getattr(src.card_def, "set_code", None) or ""
        cn = getattr(src.card_def, "card_number", None) or ""
        for spec in get_abilities(sc, cn):
            if isinstance(spec, StandingPlayDiscount) and spec.once_per_round and (
                _card_matches_standing_discount(ci.card_def, spec.applies_to)
            ):
                used.add(_standing_discount_key(src, ps))
                break


#: Aspect-penalty pips a "ignore 1 aspect penalty" waiver may waive — Daimyo's
#: Palace LAW_20 explicitly excludes Heroism/Villainy ("Vigilance, Command,
#: Aggression, or Cunning aspect penalties").
_WAIVABLE_ASPECTS = {"Vigilance", "Command", "Aggression", "Cunning"}


def _ignorable_aspect_penalty(card: AnyCard, ps: PlayerState,
                              state: "GameState | None" = None) -> int:
    """Resources waived by ignoring **one** Vigilance/Command/Aggression/Cunning
    aspect penalty when playing ``card`` (Daimyo's Palace LAW_20): 2 if the card
    has at least one unmatched pip among those four aspects against ``ps``'s base
    aspects, else 0.  Heroism/Villainy penalties are not waivable per the card,
    and a fully-matched card is never discounted.  Mirrors ``_effective_cost`` /
    ``_aspect_penalty`` (base_zone aspects, counting duplicates)."""
    card_aspects = tuple(a.name for a in (getattr(card, "aspects", None) or ()))
    if not card_aspects:
        return 0
    available = _available_aspects(ps, state)
    for aspect, needed in Counter(card_aspects).items():
        if aspect in _WAIVABLE_ASPECTS and max(0, needed - available[aspect]) > 0:
            return 2
    return 0


def _smuggle_cost(state: GameState, ci: CardInstance, ps: PlayerState) -> Optional[int]:
    """Total effective resource cost to play ``ci`` via Smuggle (base + aspect
    penalty), or None if it cannot be smuggled.  See ``_smuggle_cost_parts``."""
    parts = _smuggle_cost_parts(state, ci, ps)
    return None if parts is None else parts[0] + parts[1]


def _piloting_discount_entry(state: GameState, ci: CardInstance,
                             ps: PlayerState) -> Optional[int]:
    """Index of the first pending NextPlayDiscount that discounts playing ``ci``
    as a PILOT, or None.

    Only an entry flagged ``applies_to_piloting`` reaches this path — "The next
    Pilot card you play this phase costs 1 resource less.  (This includes Piloting
    costs.)" (Wedge Antilles JTL_8).  Otherwise the ordinary hand-play discount
    would silently apply twice, once per play mode."""
    traits = set(getattr(ci.card_def, "traits", ()) or ())
    for i, entry in enumerate(state.game_memory.pending_play_discounts):
        if not entry.get("applies_to_piloting", False):
            continue
        if _play_discount_entry_matches(entry, ci, ps, traits, False, state):
            return i
    return None


def _piloting_cost(state: GameState, ci: CardInstance, ps: PlayerState) -> Optional[int]:
    """Total effective resource cost to play ``ci`` as a Pilot (base + aspect
    penalty, less any pending Piloting-aware discount), or None if it cannot be
    piloted (no Piloting keyword in epic_action).

    Read at BOTH the enumeration and the payment site, so a pending discount can
    never make an offered PilotPlay unaffordable; ``PilotPlay`` consumes the entry."""
    from swu.engine.keywords import parse_piloting_cost
    spec = parse_piloting_cost(getattr(ci.card_def, "epic_action", None))
    if spec is None:
        return None
    n, aspects = spec
    total = n + _aspect_penalty(aspects, ps, state)
    idx = _piloting_discount_entry(state, ci, ps)
    if idx is not None:
        total -= int(
            state.game_memory.pending_play_discounts[idx].get("amount", 0) or 0)
    return max(0, total)


def _vehicle_has_pilot(host: CardInstance) -> bool:
    """True if the host unit already has a Pilot attached (a Pilot upgrade or a
    leader deployed as an upgrade — both carry the Pilot trait on their card_def)."""
    return _pilot_count(host) > 0


def _pilot_count(host: CardInstance) -> int:
    """Number of Pilot upgrades (or leaders-as-upgrade) attached to ``host``."""
    return sum(1 for upg in host.attached_upgrades
               if "Pilot" in (getattr(upg.card_def, "traits", ()) or ()))


def _pilot_limit(host: CardInstance) -> int:
    """Max Pilots ``host`` may carry: the standard 1, plus any extra granted by an
    ``AdditionalPilotSlots`` marker — either printed on the host's card def
    (Millennium Falcon JTL_249: "1 additional Pilot") or conferred by a Pilot
    upgrade attached to the host (R2-D2 JTL_245: "Attached unit gains: 'You may
    play or deploy 1 additional Pilot on this unit.'")."""
    from swu.abilities.registry import get_abilities, AdditionalPilotSlots

    def _extra(cd) -> int:
        sc = getattr(cd, "set_code", None) or ""
        cn = getattr(cd, "card_number", None) or ""
        if not sc or not cn:
            return 0
        return sum(spec.count for spec in get_abilities(sc, cn)
                   if isinstance(spec, AdditionalPilotSlots))

    extra = _extra(host.card_def)
    for upg in getattr(host, "attached_upgrades", None) or ():
        extra += _extra(upg.card_def)
    return 1 + extra


def _discard_cost_candidates(ps: PlayerState, cost) -> list:
    """Hand cards that satisfy a ``DiscardCardCost`` (all of them by default, or
    only those at/above ``cost_min`` — "discard a card that costs 6 or more from
    your hand", Dryden Vos SEC_7)."""
    lo = getattr(cost, "cost_min", None)
    if lo is None:
        return list(ps.hand)
    return [c for c in ps.hand
            if int(getattr(c.card_def, "cost", None) or 0) >= int(lo)]


def _discard_cost_payable(ps: PlayerState, cost) -> bool:
    """Whether ``ps`` can pay a ``DiscardCardCost`` right now."""
    return len(_discard_cost_candidates(ps, cost)) >= int(getattr(cost, "count", 1) or 1)
