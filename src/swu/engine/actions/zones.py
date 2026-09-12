"""Moving cards between zones: draw, enter play, attach, capture, defeat.

A SWU card is always somewhere — deck, hand, resources, an arena, discard, or
captured under another unit — and almost every ability in the game is ultimately a
request to move one from one of those to another.  This module owns those moves, so
that the rules attached to them are written once: entering play checks for
enters-ready grants and damaging auras, defeat strips upgrades and tokens and
returns captured cards, attaching an upgrade validates the host against the
upgrade's own "Attach to ..." restriction.

Keeping the moves here rather than in the ~500 decision-family definitions above is
what stops each new card re-implementing them slightly differently.  When a card
says "defeat a unit", it calls ``_defeat_unit`` and inherits every consequence.

Things that reliably surprise people:

* **``_defeat_unit`` does not decide lethality.** ``damage._hp_lethal`` does that.
  This function executes a defeat that has already been decided, which is why
  effects that defeat a unit outright don't need to fake enough damage.
* **``_sweep_defeated_units`` is the cleanup pass, and it must run after anything
  that could have made a unit lethal.** ``apply`` calls it at a fixed point in the
  observer sequence; calling it early changes which triggers see which units.
* **A defeated card reaches the discard, and ``state.find_instance`` reaches into
  the discard.** A test asserting "the unit defeated this way is gone" has to look
  in the arena, not ask whether the instance exists. (A defeated *token* really is
  gone — tokens cease to exist rather than being discarded.)
* **Control changes are reversible and linked.** ``change_control`` records enough
  to let ``_revert_linked_control`` put a unit back when the effect that took it
  ends, and ``_control_change_protected`` is what stops a unit being stolen twice.
"""
from __future__ import annotations

import re
from typing import Optional

from swu.cards.models import Leader
from swu.engine.events import (
    ControlChanged, DamageDealt, EmptyDeckDamage,
    LeaderReturnedToBase, UnitCaptured, UnitDefeated,
    UnitEntersPlay, UnitReturnedFromCapture, UpgradeDetached,
    UpgradePlayed,
)
from swu.engine.state import (
    CardInstance, GameState, Phase, PlayerState, Zone, ability_suppressed,
)
from swu.engine.triggers import get_bus

from swu.engine.actions.base import (
    IllegalActionError,
)
from swu.engine.actions.stats import (
    compute_power,
)
from swu.engine.actions.damage import (
    _bases_cannot_heal, _deal_damage_with_shield, _hp_lethal, base_damage_after_prevention, note_base_healed,
)

# ── apply convenience wrapper ─────────────────────────────────────────────────

def note_upgrade_defeated(s: GameState, upgrade_ci: "CardInstance",
                          controller_id: Optional[str] = None) -> None:
    """Record that an UPGRADE was defeated, feeding the queue drained by
    ``_fire_upgrade_defeat_observers`` ("When a friendly upgrade is defeated" — Zeb
    Orrelios ASH_161).

    ``controller_id`` is who controlled the upgrade — i.e. the HOST's controller, the
    reading "friendly" takes (control follows the host).  Token upgrades count: in SWU
    a Shield / Experience / Advantage token IS an upgrade, so an ASH board feeds this
    ledger often.  Purely additive: with no such observer in play the drain fires
    nothing."""
    if controller_id is None:
        host = _find_upgrade_host(s, upgrade_ci.instance_id)
        if host is not None:
            res = s.find_instance(host.instance_id)
            controller_id = res[0].player_id if res is not None else host.owner_id
        else:
            controller_id = upgrade_ci.owner_id
    s.game_memory.upgrade_defeats.append(controller_id)
    # The standing, board-readable sibling of that drained queue: "If a friendly
    # upgrade was defeated this phase" (Baylan Skoll ASH_39).
    s.game_memory.upgrades_defeated_this_phase.add(controller_id)


_UPGRADE_ATTACH_OBSERVER_KEYS: list = []


def _upgrade_attach_observer_keys() -> frozenset:
    """Cached (set_code, card_number) index of the cards carrying a
    ``WhenUpgradeAttached`` trigger — the ``_token_doubler_keys`` trick.  An upgrade
    attaching is as common as token creation on an ASH board (every Shield,
    Experience and Advantage token attaches), so nothing must be recorded or walked
    for a board with no such card in it."""
    if not _UPGRADE_ATTACH_OBSERVER_KEYS:
        from swu.abilities.registry import (
            _REGISTRY, TriggerAbility, WhenUpgradeAttached,
        )
        keys = {key for key, specs in _REGISTRY.items()
                if any(isinstance(sp, TriggerAbility)
                       and isinstance(sp.trigger, WhenUpgradeAttached)
                       for sp in specs)}
        _UPGRADE_ATTACH_OBSERVER_KEYS.append(frozenset(keys))
    return _UPGRADE_ATTACH_OBSERVER_KEYS[0]


def note_upgrade_attached(s: GameState, host_ci: "CardInstance") -> None:
    """Record that an upgrade attached to ``host_ci``, feeding the queue drained by
    ``_fire_upgrade_attach_observers`` ("When 1 or more upgrades attach to this unit
    (including from Shielded)" — Sabine Wren ASH_208).

    Called from the two attachment chokepoints — ``tokens.attach_token`` (so a Shield
    from the Shielded keyword counts, as the card explicitly says) and
    ``actions._attach_upgrade`` / ``_relocate_upgrade`` for a real upgrade card.
    Gated on the cached observer index, so a board with no such card records
    nothing."""
    key = (getattr(host_ci.card_def, "set_code", None) or "",
           getattr(host_ci.card_def, "card_number", None) or "")
    if key not in _upgrade_attach_observer_keys():
        return
    s.game_memory.upgrade_attachments.append(host_ci.instance_id)


def _sweep_defeated_units(s: GameState) -> None:
    """State-based defeat check (SWU CR: a unit with damage >= HP is defeated).

    Combat and direct-damage effects already defeat units at the point they
    deal lethal damage.  This sweep is the catch-all for the *other* way a unit
    becomes lethal: its effective HP drops to or below its current damage when
    a buff source leaves play (e.g. a Constant +1/+1 leader bounced by Waylay),
    a duration modifier expires, or an upgrade is removed.

    Runs to a fixed point because defeating one unit can remove a buff it was
    providing, pushing another unit to lethal.  If a When-Defeated trigger
    suspends on a pending decision, we stop and let the next ``apply()`` (which
    resolves that decision) re-sweep — matching how state-based actions are
    re-checked each time a player would receive priority.
    """
    changed = True
    while changed:
        changed = False
        if s.pending_decisions:
            return
        for ps in s.players:
            for ci in list(ps.ground_arena + ps.space_arena):
                if _hp_lethal(s, ci):
                    _defeat_unit(s, ps, ci)
                    changed = True
                    break
            if changed:
                break


# ── Player-directed damage distribution push helpers ──────────────────────────

def _draw_cards(s: GameState, ps: PlayerState, n: int) -> int:
    drawn = 0
    drawn_ids: list[str] = []
    for _ in range(n):
        if ps.deck:
            ci = ps.deck.pop(0)
            ci.zone = Zone.HAND
            ps.hand.append(ci)
            drawn += 1
            drawn_ids.append(ci.instance_id)
        else:
            base_ci = ps.base_instance
            if base_ci is not None:
                base_ci.damage += base_damage_after_prevention(s, base_ci, 3)
                s.event_log.append(EmptyDeckDamage(
                    player_id=ps.player_id, damage=3, cards_missed=1,
                ))
                s.event_log.append(DamageDealt(
                    target_instance_id=base_ci.instance_id,
                    target_name=base_ci.card_def.display_name,
                    owner_id=ps.player_id,
                    amount=3,
                    is_base=True,
                ))
    # Record the draw *event* for the WhenYouDraw observer (LAW_52 / LOF_148).  Only
    # during the ACTION phase ("when you draw … during the action phase"; regroup /
    # setup draws set Phase.REGROUP/SETUP before drawing, so they are excluded) and
    # only when a real card was drawn ("1 or more cards" — an empty-deck penalty
    # draws nothing).  Drained at the apply() settle-point by _fire_draw_observers.
    # REGROUP draws are ledgered too, tagged with their phase: the matcher admits
    # them only for a trigger that prints "(including during the regroup phase)"
    # (Axe Woves ASH_169), so every other WhenYouDraw keeps its ACTION-only reading.
    if drawn > 0 and s.phase in (Phase.ACTION, Phase.REGROUP):
        s.game_memory.action_phase_draws.append(
            {"player_id": ps.player_id, "card_ids": drawn_ids,
             "phase": s.phase.name})
    if drawn > 0 and s.phase == Phase.ACTION:
        # Running per-phase draw count for "equal to the number of cards you've drawn
        # this phase" (Pre Vizsla TWI_10).  Same ACTION-only gate as the observer
        # above, which is exactly the card's "(…doesn't include cards drawn in the
        # regroup phase)"; cleared at the phase rollover.
        gm = s.game_memory
        gm.cards_drawn_this_phase[ps.player_id] = (
            gm.cards_drawn_this_phase.get(ps.player_id, 0) + drawn)
    return drawn


def _find_in_arenas(ps: PlayerState, instance_id: str) -> Optional[CardInstance]:
    for ci in ps.ground_arena + ps.space_arena:
        if ci.instance_id == instance_id:
            return ci
    return None


# ── distribute_damage decision helpers ───────────────────────────────────────

def _all_units_in_play(state: GameState) -> list[CardInstance]:
    units = []
    for ps in state.players:
        units.extend(ps.ground_arena)
        units.extend(ps.space_arena)
    return units


# Known unit traits, longest-first so multi-word traits match before their parts.
_UNIT_TRAITS: tuple[str, ...] = tuple(sorted(
    ("Armor", "Bounty", "Bounty Hunter", "Capital Ship", "Clone", "Condition",
     "Creature", "Disaster", "Droid", "Ewok", "Fighter", "First Order", "Force",
     "Fringe", "Gambit", "Gungan", "Hutt", "Imperial", "Innate", "Inquisitor",
     "Item", "Jawa", "Jedi", "Kaminoan", "Law", "Learned", "Lightsaber",
     "Mandalorian", "Modification", "Musician", "Naboo", "New Republic", "Night",
     "Nihil", "Official", "Pilot", "Plan", "Rebel", "Republic", "Resistance",
     "Separatist", "Sith", "Spectre", "Speeder", "Supply", "Tactic", "Tank",
     "Transport", "Trick", "Trooper", "Tusken", "Twi'lek", "Undead", "Underworld",
     "Vehicle", "Walker", "Weapon", "Wookiee"),
    key=len, reverse=True,
))

_ATTACH_TARGET_RE = re.compile(r"attach to an? ([^.\n]+)", re.IGNORECASE)


def _upgrade_target_spec(card_def) -> "Optional[TargetSpec]":  # noqa: F821 (imported in body)
    """Parse an Upgrade's "Attach to …" restriction into a ``TargetSpec``.

    Returns ``None`` when the upgrade has no parseable attachment restriction,
    in which case it may legally be attached to ANY unit in play — friendly or
    enemy — per the comprehensive rules ("A player may play an upgrade onto an
    enemy unit.").

    Parsing is deliberately *conservative*: only restrictions we can express
    confidently are applied, so a legal target is never filtered out. Anything
    we don't understand (token/unique qualifiers, "X or Y" trait choices) is
    silently ignored, leaving behaviour as permissive as before for that clause.
    """
    from swu.abilities.registry import TargetSpec

    text = (getattr(card_def, "text", "") or "")
    # Normalise non-breaking space (\xa0) and non-breaking hyphen (‑).
    text = text.replace("\xa0", " ").replace("‑", "-")
    m = _ATTACH_TARGET_RE.search(text)
    if not m:
        return None
    desc = m.group(1)
    low = desc.lower()

    controller = "any"
    if "friendly" in low:
        controller = "friendly"
    elif "enemy" in low:
        controller = "enemy"

    predicates: list[str] = []
    if "non-leader" in low:
        predicates.append("non_leader")
    if "non-vehicle" in low:
        predicates.append("non_vehicle")
    if re.search(r"\bdamaged\b", low):
        predicates.append("damaged")
    if re.search(r"\btoken unit\b", low):
        # "Attach to a token unit" (Nameless Valor TWI_119) — the same
        # ``token_unit`` predicate the target layer already knows (Shaak Ti
        # TWI_94), so the restriction is enforced everywhere an attachment is
        # validated (legal_actions, the apply guard, upgrade relocation).
        predicates.append("token_unit")

    arena = None
    if re.search(r"\bground unit\b", low):
        arena = "ground"
    elif re.search(r"\bspace unit\b", low):
        arena = "space"

    cost_max = cost_min = None
    cm = re.search(r"costs? (\d+) or less", low)
    if cm:
        cost_max = int(cm.group(1))
    cm = re.search(r"costs? (\d+) or more", low)
    if cm:
        cost_min = int(cm.group(1))

    traits: tuple[str, ...] = ()
    # Positive trait requirements. Skip "X or Y" choices — TargetSpec traits are
    # ANDed, so requiring both would wrongly forbid legal targets; leave it open.
    if " or " not in low:
        for trait in _UNIT_TRAITS:
            tl = trait.lower()
            if f"non-{tl}" in low:
                continue  # negation handled above (non_vehicle) or left open
            if re.search(rf"\b{re.escape(tl)}\b", low):
                traits = traits + (trait,)

    return TargetSpec(
        controller=controller,
        kind="unit",
        arena=arena,
        traits=traits,
        predicates=tuple(predicates),
        cost_max=cost_max,
        cost_min=cost_min,
    )


def _eligible_upgrade_targets(
    state: GameState, upgrade_ci: CardInstance
) -> list[CardInstance]:
    """Units that ``upgrade_ci`` may legally be attached to.

    With no parseable restriction this is every unit in play (either player);
    otherwise it is the units matching the upgrade's "Attach to …" clause.
    """
    spec = _upgrade_target_spec(upgrade_ci.card_def)
    units = _all_units_in_play(state)
    if spec is None:
        return units
    from swu.abilities.resolver import _spec_matches_ci
    return [u for u in units if _spec_matches_ci(spec, u, upgrade_ci, state, {})]


# ── Credit-token economy (jabba-the-hutt:07) ───────────────────────────────────

def change_control(s: GameState, ci: CardInstance, new_controller_id: str) -> None:
    """Move a unit between players' arenas, preserving ownership.

    Control in this engine is implicit: a unit is controlled by whichever
    player's arena list holds it (``find_instance`` returns that player), while
    ``ci.owner_id`` is the (unchanging) owner.  These normally coincide; this is
    the one seam that splits them.  ``ci`` (with its attached upgrades, which
    travel inside ``ci.attached_upgrades``) is relocated from its current
    controller's arena to ``new_controller_id``'s matching arena.  The arena
    kind (ground/space) and therefore ``ci.zone`` are unchanged, so attached
    upgrades keep a valid zone tag.  No-op if ``new_controller_id`` already
    controls ``ci`` or ``ci`` is not in an arena.

    NOTE (scope): the abilities resolver still treats ``source_ci.owner_id`` as
    the controller when resolving a unit's OWN abilities, so a foreign-controlled
    unit's activated/triggered/constant abilities would resolve from the owner's
    perspective rather than the controller's.  Stolen Landspeeder (SHD_161), the
    only control-changing card, has no such ability that resolves while under
    enemy control (its When Played fires before the change; its Bounty is a
    WhenDefeated written from the collector's perspective), so this is not
    exercised today — but a future control-changing card with friendly-perspective
    abilities would need that resolver path generalised to control.
    """
    result = s.find_instance(ci.instance_id)
    if result is None:
        return
    cur_ps, _ = result
    if cur_ps.player_id == new_controller_id:
        return
    if ci.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
        return
    if new_controller_id != ci.owner_id and _control_change_protected(s, ci):
        return  # "Opponents can't take control of this unit" (Rey LAW_149)
    for arena in (cur_ps.ground_arena, cur_ps.space_arena):
        if ci in arena:
            arena.remove(ci)
            break
    else:
        return
    new_ps = s.player_by_id(new_controller_id)
    target = new_ps.ground_arena if ci.zone == Zone.GROUND_ARENA else new_ps.space_arena
    target.append(ci)
    s.event_log.append(ControlChanged(
        instance_id=ci.instance_id,
        card_name=ci.card_def.display_name,
        owner_id=ci.owner_id,
        from_player_id=cur_ps.player_id,
        to_player_id=new_controller_id,
    ))


def _control_change_protected(s: GameState, ci: CardInstance) -> bool:
    """True if ``ci`` carries a ``Protection(from_control_change=True)`` — "Opponents
    can't take control of this unit" (Rey LAW_149).

    The self-targeted ``ConstantAbility`` convention every other Protection arm uses
    (Chewbacca JTL_103): the marker is read off the card's own registration, and the
    scan is skipped outright for a suppressed unit.  Read only here, at the single
    ``change_control`` seam."""
    if ability_suppressed(s, ci):
        return False
    from swu.abilities.registry import (
        get_abilities, ConstantAbility, Protection, SELF)
    sc = getattr(ci.card_def, "set_code", None) or ""
    cn = getattr(ci.card_def, "card_number", None) or ""
    if not sc or not cn:
        return False
    for spec in get_abilities(sc, cn):
        if not isinstance(spec, ConstantAbility):
            continue
        if getattr(spec.target, "fixed", None) is not SELF:
            continue
        for eff in spec.effects:
            if isinstance(eff, Protection) and getattr(
                    eff, "from_control_change", False):
                if (spec.condition is None
                        or spec.condition.evaluate(s, ci)):
                    return True
    return False


def _enters_play_ready(state: GameState, ci: CardInstance) -> bool:
    """True if ``ci`` declares a satisfied ``EntersPlayReady`` spec (Salacious Crumb
    LAW_210: "If you control Jabba the Hutt, this unit enters play ready").
    Evaluated against the source's controller as it enters play."""
    from swu.abilities.registry import get_abilities, EntersPlayReady
    sc = getattr(ci.card_def, "set_code", None) or ""
    cn = getattr(ci.card_def, "card_number", None) or ""
    for spec in get_abilities(sc, cn):
        if isinstance(spec, EntersPlayReady):
            if spec.condition is None or spec.condition.evaluate(state, ci):
                return True
    return False


def _consume_pending_keyword_grants(s: GameState, ps: PlayerState,
                                    ci: CardInstance) -> list[str]:
    """Pop and return every armed "the next unit you play this phase gains K"
    keyword for ``ps``'s play of ``ci`` (Deceptive Shade LOF_180).

    The ``pending_exploit_grants`` shape: one entry is consumed per matching play,
    an optional ``trait`` narrows which play matches, and the whole list is cleared
    at the phase rollover.  Only the FIRST matching entry fires per play, so two
    armed grants feed the next two units, not one unit twice."""
    out: list[str] = []
    traits = set(getattr(ci.card_def, "traits", ()) or ())
    for i, entry in enumerate(list(s.game_memory.pending_keyword_grants)):
        if entry.get("player_id") != ps.player_id:
            continue
        trait = entry.get("trait")
        if trait and trait not in traits:
            continue
        kw = entry.get("keyword")
        del s.game_memory.pending_keyword_grants[i]
        if kw:
            out.append(str(kw))
        break
    return out


def _consume_pending_enters_ready(s: GameState, ps: PlayerState,
                                  ci: CardInstance) -> bool:
    """Pop an armed "the next unit you play this phase with N or less power enters
    play ready" charge for ``ps``'s play of ``ci`` (Neel ASH_248).

    The ``_consume_pending_keyword_grants`` shape: the first matching entry is
    consumed per play, so two charges ready the next two units.  PRINTED power — the
    unit is not in an arena yet, so nothing has had a chance to buff it."""
    power = int(getattr(ci.card_def, "power", 0) or 0)
    for i, entry in enumerate(list(s.game_memory.pending_enters_ready)):
        if entry.get("player_id") != ps.player_id:
            continue
        if power > int(entry.get("power_max", 0) or 0):
            continue
        del s.game_memory.pending_enters_ready[i]
        return True
    return False


def _put_unit_in_play(
    s: GameState, ps: PlayerState, ci: CardInstance,
    enters_ready: bool = False, via_smuggle: bool = False,
    then_damage: int = 0, then_damage_source: str | None = None,
    play_source: str = "hand", grant_keyword: str | None = None,
    cost_paid: int | None = None, defeat_at_regroup: bool = False,
    exploited_powers: list[int] | None = None,
) -> None:
    """Place a unit into the appropriate arena and fire UnitEntersPlay.

    Units normally enter play exhausted; ``enters_ready=True`` puts the unit in
    ready (e.g. Admiral Ozzel, SOR_129).  The exhaust flag is independent of the
    enter-play triggers fired below, so keyword/ability triggers are unaffected.
    ``via_smuggle`` is threaded into the trigger event context so a card's
    "When played using Smuggle" trigger fires only on a smuggle play.
    ``play_source`` ("hand"/"smuggle"/"discard") is threaded likewise so a
    "When Played: ... if you played this from your hand" trigger (Stolen
    Landspeeder SHD_161) can distinguish a hand play from a replay-from-discard
    or smuggle.

    ``then_damage`` deals that much damage to the unit immediately after it
    enters play and after Phase-2 enter-play keywords resolve (so a Shielded
    unit's shield intercepts it), but BEFORE its own "When Played" abilities —
    matching Han Solo's (SHD_13) errata ("2 damage is dealt to the played unit
    before resolving any When Played abilities").  If the damage defeats the
    unit, it is defeated immediately and its "When Played" abilities never fire.
    """
    target_zone = ci.zone_for_arena()
    ci.zone = target_zone
    ci.face_down = False
    # "The next unit you play this phase with 1 or less power enters play ready"
    # (Neel ASH_248) — an armed charge on ``game_memory.pending_enters_ready``,
    # consumed here, just before the placement reads ``enters_ready``.
    if _consume_pending_enters_ready(s, ps, ci):
        enters_ready = True
    # A card may declare it enters play ready under a condition (Salacious Crumb
    # LAW_210) — checked once at placement (default behaviour unchanged otherwise).
    ci.exhausted = not (enters_ready or _enters_play_ready(s, ci))
    # A fresh entry clears any stale "can't ready this round" flag (No Good to Me
    # Dead SOR_186) that lingered on the instance from a previous stint in play.
    ci.cannot_ready_this_round = False
    ci.abilities_suppressed = False  # a fresh entry clears any stale suppression
    # Sneak Attack SOR_219: this unit is defeated at the start of the next regroup.
    ci.defeat_at_regroup = defeat_at_regroup
    arena_list = ps.ground_arena if target_zone == Zone.GROUND_ARENA else ps.space_arena
    arena_list.append(ci)
    evt = UnitEntersPlay(
        player_id=ps.player_id,
        instance_id=ci.instance_id,
        card_name=ci.card_def.display_name,
        arena=ci.arena() or "Ground",
    )
    s.event_log.append(evt)
    # Record the entry for the settle-drain WhenYouPlayOrCreateUnit observer
    # ("When you play or create a unit" Greef Karga ASH_17; "When a friendly unit
    # enters play (including this one)" Outcast ASH_41).  This is the ONE chokepoint
    # every entry route passes through — a hand/discard/smuggle/plot play, an
    # ability play, and a created token unit — which is exactly the union those two
    # cards name.  The ``heal_events`` shape: append here, drain at the settle-point.
    s.game_memory.unit_entries.append(
        {"player_id": ps.player_id, "instance_id": ci.instance_id})
    # A keyword granted "for this phase" as part of the play (e.g. Energy
    # Conversion Lab / Timely Intervention "Give it Ambush for this phase").
    # Applied BEFORE the enter-play keyword bus so a granted Ambush triggers on
    # entry, exactly as if printed on the card.
    grant_keywords_now: list[str] = [grant_keyword] if grant_keyword else []
    # "If you play this unit from your hand, it gains K" (Millennium Falcon
    # SHD_204): a registered KeywordIfPlayedFromHand marker grants its keyword only
    # on a hand play, not via Smuggle/discard/plot/token.  Read here so the grant
    # lands before the enter-play keyword bus, exactly like the ability grant above.
    # "The next unit you play this phase gains K for this phase" (Deceptive Shade
    # LOF_180) — one pending grant per matching play, the pending_play_discounts
    # shape; consumed here so it lands before the enter-play keyword bus (a granted
    # Ambush therefore triggers on entry).
    grant_keywords_now += _consume_pending_keyword_grants(s, ps, ci)
    if play_source == "hand":
        from swu.abilities.registry import get_abilities, KeywordIfPlayedFromHand
        sc = getattr(ci.card_def, "set_code", None) or ""
        cn = getattr(ci.card_def, "card_number", None) or ""
        if sc and cn:
            for spec in get_abilities(sc, cn):
                if isinstance(spec, KeywordIfPlayedFromHand):
                    grant_keywords_now.append(spec.keyword)
    for gk in grant_keywords_now:
        from swu.engine.state import Modifier
        s.modifiers.append(Modifier(
            modifier_id=s.alloc_modifier_id(),
            source_instance_id=ci.instance_id,
            target_instance_id=ci.instance_id,
            kind="keyword_grant",
            value={"keyword": gk, "value": 0},
            duration="this_phase",
        ))
    # Phase 2 keyword triggers (Shielded, Ambush)
    get_bus().fire(s, evt)
    s.game_memory.units_played_this_phase.add(ci.instance_id)
    # Effect-source damage to the just-played unit (Han Solo): resolved after the
    # enter-play keyword bus (Shielded shield is up) but before "When Played".
    if then_damage > 0:
        _deal_damage_with_shield(s, ps, ci, then_damage, source_name=then_damage_source)
        if _hp_lethal(s, ci):
            _defeat_unit(s, ps, ci)
            return  # defeated before its When Played abilities could fire
    # Phase 3: WhenPlayed / WhenUnitEntersPlay ability triggers
    # Fires AFTER Phase 2 bus (so Ambush is already pushed if present;
    # Phase 3 triggers will be on top and resolve first)
    after_idx = 1 - s.player_index(ps.player_id)
    from swu.abilities.resolver import fire_triggered_abilities
    event_ctx = {"source_id": ci.instance_id, "arena": ci.arena() or "Ground",
                 "via_smuggle": via_smuggle, "play_source": play_source,
                 "cost_paid": cost_paid,
                 "exploited_powers": list(exploited_powers or [])}
    fire_triggered_abilities(s, evt, after_all_player_idx=after_idx, event_ctx=event_ctx)


def _tokens_enter_play_ready(s: GameState, ps: PlayerState) -> bool:
    """True if ``ps`` controls an in-play card carrying the ``TokensEnterPlayReady``
    marker (Chancellor Palpatine TWI_203).  Scans that player's arenas only — the
    marker is a controller-scoped board effect, and its abilities are subject to the
    usual suppression read.  A no-op scan for the overwhelming majority of boards."""
    from swu.abilities.registry import get_abilities, TokensEnterPlayReady
    from swu.engine.state import ability_suppressed
    for ci in ps.ground_arena + ps.space_arena:
        if ability_suppressed(s, ci):
            continue
        sc = getattr(ci.card_def, "set_code", None) or ""
        cn = getattr(ci.card_def, "card_number", None) or ""
        if not sc or not cn:
            continue
        for spec in get_abilities(sc, cn):
            if isinstance(spec, TokensEnterPlayReady):
                return True
    return False


def _create_token_units(
    s: GameState, ps: PlayerState, token_name: str, count: int = 1,
    enters_ready: bool = False, note_token_creation: bool = True,
) -> list[CardInstance]:
    """Create *count* token units (e.g. "Clone Trooper") under ``ps``'s control.

    The create-token-unit primitive (ahsoka-tano:05).  A token unit is an
    unlimited-supply unit card (TokenUnit def from the DB, like Shield/Experience
    upgrades or the Credit token) that is *created* into play rather than drawn
    from a deck — so it is excluded from card conservation
    (``all_instances_for_player``) and ceases to exist when it leaves play (see
    ``_defeat_unit``).  Each token enters the appropriate arena via the shared
    ``_put_unit_in_play`` path, so it enters exhausted by default, fires
    ``UnitEntersPlay`` (and its own enter-play keyword/trigger bus — a no-op for the
    plain Clone Trooper) and is buffable like any unit (Shaak Ti TWI_94 "Each
    friendly token unit gets +1/+0").  ``enters_ready=True`` puts each token into
    play ready instead of the default exhausted ("Create N tokens and ready them",
    On the Doorstep TWI_190).  Returns the created instances.
    """
    from swu.engine.tokens import _token_unit_def
    # A board-wide "Each token unit you create enters play ready" marker on any
    # in-play card the creating player controls (Chancellor Palpatine TWI_203)
    # upgrades every token this player makes, whatever created it.
    if not enters_ready and _tokens_enter_play_ready(s, ps):
        enters_ready = True
    # "If you created a token this phase" (The Client LAW_16) — the token-UNIT arm
    # of the three token-creation chokepoints.  Recorded only for a real creation
    # (count >= 1), so a no-op call records nothing.
    if int(count) > 0:
        s.game_memory.tokens_created_this_phase.add(ps.player_id)
        if note_token_creation:
            from swu.engine.tokens import _note_token_creation
            _note_token_creation(s, ps.player_id, "unit", token_name, int(count),
                                 ready=enters_ready)
    created: list[CardInstance] = []
    for _ in range(max(0, count)):
        token_def = _token_unit_def(token_name)
        iid, nxt = s.alloc_instance_id()
        s._next_id = nxt
        ci = CardInstance(
            instance_id=iid,
            card_def=token_def,
            owner_id=ps.player_id,
            zone=Zone.GROUND_ARENA,  # overwritten by _put_unit_in_play via arena()
        )
        _put_unit_in_play(s, ps, ci, enters_ready=enters_ready, play_source="token")
        created.append(ci)
    return created


def _attach_upgrade(
    s: GameState, ps: PlayerState, upgrade_ci: CardInstance, target_id: Optional[str],
    via_smuggle: bool = False,
) -> None:
    if target_id is None:
        raise IllegalActionError("Upgrade requires a target")
    upgrade_ci.face_down = False
    spec = _upgrade_target_spec(upgrade_ci.card_def)
    for owner_ps in s.players:
        for unit_ci in owner_ps.ground_arena + owner_ps.space_arena:
            if unit_ci.instance_id == target_id:
                if spec is not None:
                    from swu.abilities.resolver import _spec_matches_ci
                    if not _spec_matches_ci(spec, unit_ci, upgrade_ci, s, {}):
                        raise IllegalActionError(
                            f"{upgrade_ci.card_def.display_name} cannot attach to "
                            f"{unit_ci.card_def.display_name} ({target_id})"
                        )
                upgrade_ci.zone = unit_ci.zone
                unit_ci.attached_upgrades.append(upgrade_ci)
                note_upgrade_attached(s, unit_ci)      # Sabine Wren ASH_208
                # Fire WhenPlayed triggers for the upgrade
                evt = UpgradePlayed(
                    player_id=ps.player_id,
                    instance_id=upgrade_ci.instance_id,
                    card_name=upgrade_ci.card_def.display_name,
                    attached_to_instance_id=target_id,
                )
                s.event_log.append(evt)
                get_bus().fire(s, evt)
                from swu.abilities.resolver import fire_triggered_abilities
                after_idx = 1 - s.player_index(ps.player_id)
                fire_triggered_abilities(s, evt, after_all_player_idx=after_idx,
                                         event_ctx={"attached_to_id": target_id,
                                                    "via_smuggle": via_smuggle})
                return
    raise IllegalActionError(f"Upgrade target {target_id} not found in any arena")


# ── Capture ───────────────────────────────────────────────────────────────────

def _apply_capture(s: GameState, captor_id: str, target_id: str) -> GameState:
    """Capture ``target_id`` under ``captor_id``.

    The target leaves its arena (its upgrades are defeated like any leave-play),
    is reset, tagged ``captured_by``, and placed facedown in the capturing
    player's capture pile.  A no-op if either instance is gone or the target is
    not an in-play arena unit.
    """
    from swu.cards.models import TokenUpgrade

    cap_res = s.find_instance(captor_id)
    tgt_res = s.find_instance(target_id)
    if cap_res is None or tgt_res is None:
        return s
    captor_ps, captor_ci = cap_res
    holder_ps, target_ci = tgt_res

    # Protection: a unit that "can't be captured by enemy card abilities" is skipped
    # when an enemy-controlled captor tries to capture it (Lurking TIE Phantom
    # SHD_187).  The captor is the source of the capture; a friendly capture (same
    # controller) is unaffected, mirroring _target_protected's enemy-only guard.
    from swu.abilities.resolver import _target_protected
    if _target_protected(s, target_id, captor_ci, "capture"):
        return s

    # Remove the target from whichever arena holds it
    removed = False
    for arena in (holder_ps.ground_arena, holder_ps.space_arena):
        if target_ci in arena:
            arena.remove(target_ci)
            removed = True
            break
    if not removed:
        return s  # not an in-play unit (already gone / not an arena card)

    # A captured unit leaves play: its upgrades are defeated (tokens vanish,
    # real upgrades go to their owner's discard), mirroring _defeat_unit.
    for upgrade in list(target_ci.attached_upgrades):
        if isinstance(upgrade.card_def, TokenUpgrade):
            continue
        s.event_log.append(UpgradeDetached(
            upgrade_instance_id=upgrade.instance_id,
            upgrade_name=upgrade.card_def.display_name,
            former_host_name=target_ci.card_def.display_name,
            owner_id=upgrade.owner_id,
        ))
        upgrade_owner = s.player_by_id(upgrade.owner_id)
        upgrade.zone = Zone.DISCARD
        upgrade_owner.discard.append(upgrade)
    target_ci.attached_upgrades.clear()

    # The unit is no longer in play — expire modifiers that targeted it.
    s.modifiers = [m for m in s.modifiers if m.target_instance_id != target_ci.instance_id]

    # Place facedown under the captor (owner unchanged).
    target_ci.damage = 0
    target_ci.exhausted = False
    target_ci.face_down = True
    target_ci.deployed = False
    target_ci.captured_by = captor_ci.instance_id
    target_ci.zone = Zone.CAPTURE_PILE
    captor_ps.capture_pile.append(target_ci)

    s.event_log.append(UnitCaptured(
        captor_instance_id=captor_ci.instance_id,
        captor_name=captor_ci.card_def.display_name,
        captured_instance_id=target_ci.instance_id,
        captured_name=target_ci.card_def.display_name,
        captor_player_id=captor_ps.player_id,
        owner_id=target_ci.owner_id,
    ))
    return s


def _release_captured_cards(s: GameState, captor_ci: CardInstance) -> None:
    """Return every card captured by ``captor_ci`` to its owner's arena.

    Called when the captor leaves play.  Each captured card re-enters its
    owner's matching arena under their control, ready, with damage cleared (see
    the ASSUMPTION note above).
    """
    for ps in s.players:
        for captured in list(ps.capture_pile):
            if captured.captured_by != captor_ci.instance_id:
                continue
            ps.capture_pile.remove(captured)
            owner_ps = s.player_by_id(captured.owner_id)
            captured.captured_by = None
            captured.face_down = False
            captured.damage = 0
            captured.exhausted = False
            captured.zone = captured.zone_for_arena()
            owner_ps.zone_list(captured.zone).append(captured)
            s.event_log.append(UnitReturnedFromCapture(
                instance_id=captured.instance_id,
                card_name=captured.card_def.display_name,
                owner_id=captured.owner_id,
                captor_instance_id=captor_ci.instance_id,
            ))


def _revert_linked_control(s: GameState, source_ci: CardInstance) -> None:
    """Revert any control changes linked to ``source_ci`` leaving play.

    Maul LAW_54 ("When this unit leaves play, that unit's owner takes control of
    that unit"): every in-play unit whose ``control_linked_to`` is this source's
    instance_id is returned to its owner's control via ``change_control`` and the
    link is cleared.  Mirrors ``_release_captured_cards`` (the capture leave-play
    linkage); like it, this is wired into ``_defeat_unit`` only — a source
    bounced/put-on-deck/captured while holding a linked unit does not revert (no
    shipped card exercises that path)."""
    linked = [
        ci
        for ps in s.players
        for arena in (ps.ground_arena, ps.space_arena)
        for ci in arena
        if ci.control_linked_to == source_ci.instance_id
    ]
    for ci in linked:
        ci.control_linked_to = None
        change_control(s, ci, ci.owner_id)


def _resolve_granted_bounty(s: GameState, collector_id: str, key: str) -> None:
    """Resolve a phase-granted bounty (CardInstance.granted_bounties) for the
    collector.  Keys are small encoded strings so the field stays JSON-serialisable
    and this stays decoupled from the cards module.  Currently the only form is
    ``"heal_base:N"`` (The Client SHD_31): heal N damage from the collector's base
    — the deterministic "Heal N damage from a base" the collector would always
    point at their own base."""
    kind, _, arg = key.partition(":")
    if kind == "heal_base":
        amount = int(arg or 0)
        base = s.player_by_id(collector_id).base_instance
        if base is not None and amount > 0 and not _bases_cannot_heal(s):
            before_base = int(base.damage)
            base.damage = max(0, base.damage - amount)
            note_base_healed(s, base, before_base - base.damage)
    elif kind == "next_unit_discount":
        # Jabba the Hutt SHD_6: "Bounty — The next unit you play this phase costs N
        # resource(s) less."  Record a pending NextPlayDiscount for the collector
        # (units-only, any trait), consumed by their next hand unit play this phase
        # (the Khetanna LAW_158 pending-discount seam); lifts at the phase rollover.
        amount = int(arg or 0)
        if amount > 0:
            s.game_memory.pending_play_discounts.append(
                {"player_id": collector_id, "trait": "", "amount": amount,
                 "units_only": True})


def _find_upgrade_host(s: GameState, upgrade_id: str) -> Optional[CardInstance]:
    """Return the in-play unit whose ``attached_upgrades`` contains ``upgrade_id``
    (or None).  Used to resolve a granted activated ability from its host and to
    detach the upgrade when paying a "defeat this upgrade" cost (SHD_155)."""
    for p in s.players:
        for u in (*p.ground_arena, *p.space_arena):
            if any(up.instance_id == upgrade_id for up in u.attached_upgrades):
                return u
    return None


def _defeat_unit(s: GameState, owner_ps: PlayerState, ci: CardInstance,
                 *, while_attacking: bool = False,
                 by_combat_damage: bool = False) -> None:
    """Remove ci from play, detach upgrades, and send to discard (or leader base zone).

    ``while_attacking`` is passed by the two attacker-death sites in the combat
    pipeline; it stamps ``event_ctx["defeated_while_attacking"]`` so a
    ``WhenUnitDefeated`` observer can require it via the
    ``defeated_while_attacking`` predicate (Luthen Rael SEC_13).  Default False,
    so every other defeat site is unchanged.

    ``by_combat_damage`` is its exact sibling, passed by the four combatant-death
    sites of the two unit-combat pipelines (attacker and defender(s), which are
    reached only after the combat damage step): it stamps
    ``event_ctx["defeated_by_combat_damage"]`` so a "When Defeated: **if this unit
    wasn't defeated by combat damage**, …" clause can read it (Paz Vizsla ASH_28,
    Shin Hati's Fiend Fighter ASH_191).  It is a plain bool, so — unlike
    ``defeated_ci`` — it survives an optional trigger's decision round-trip.
    Default False, so every non-combat defeat route (an ability, the state-based
    sweep, an exploit sacrifice) reads as "not by combat damage", which is exactly
    what those cards mean."""
    from swu.cards.models import TokenUpgrade

    # Remove from arena
    for arena in (owner_ps.ground_arena, owner_ps.space_arena):
        if ci in arena:
            arena.remove(ci)
            break

    # The defeated unit is leaving play — any cards it has captured return to
    # their owners' arenas (The Mandalorian's Rifle SHD_251).
    _release_captured_cards(s, ci)

    # ... and any control it took via a source-linked control change reverts to
    # the affected units' owners (Maul LAW_54).
    _revert_linked_control(s, ci)

    # Snapshot the upgrades BEFORE detaching them: a bounty-granting upgrade
    # (Public Enemy SHD_68 etc.) confers a "When Defeated" ability on its host via
    # a GrantedAbility, but the detach below clears ``attached_upgrades`` before
    # the UnitDefeated event fires — so the resolver collects these granted
    # WhenDefeated abilities from this stashed list (event_ctx["defeated_upgrades"]).
    defeated_upgrades = list(ci.attached_upgrades)

    # Snapshot the unit's *effective* power BEFORE detaching its upgrades/tokens, so
    # a "When Defeated: if this unit had N or more power" clause (Darth Sion SEC_35)
    # reads the power it had at the moment of defeat, not its stripped base power.
    defeated_power = compute_power(s, ci)

    # Detach upgrades — every one of them is DEFEATED with its host (tokens
    # included), which is what feeds "When a friendly upgrade is defeated"
    # (Zeb Orrelios ASH_161).  ``owner_ps`` is the host's controller here.
    for upgrade in list(ci.attached_upgrades):
        note_upgrade_defeated(s, upgrade, owner_ps.player_id)
        if isinstance(upgrade.card_def, TokenUpgrade):
            # Tokens cease to exist — never go to any discard pile
            pass
        else:
            s.event_log.append(UpgradeDetached(
                upgrade_instance_id=upgrade.instance_id,
                upgrade_name=upgrade.card_def.display_name,
                former_host_name=ci.card_def.display_name,
                owner_id=upgrade.owner_id,
            ))
            upgrade_owner = s.player_by_id(upgrade.owner_id)
            upgrade.zone = Zone.DISCARD
            upgrade_owner.discard.append(upgrade)
    ci.attached_upgrades.clear()

    evt_defeated = UnitDefeated(
        player_id=owner_ps.player_id,
        instance_id=ci.instance_id,
        card_name=ci.card_def.display_name,
    )
    s.event_log.append(evt_defeated)
    get_bus().fire(s, evt_defeated)
    s.game_memory.units_defeated_this_round.add(ci.instance_id)
    # Record the controller-at-death so a later "each enemy unit defeated this phase"
    # count (Darth Sion SEC_35) can tell whose unit it was (owner_ps is the holding
    # controller here).
    s.game_memory.defeated_controllers_this_round.append(owner_ps.player_id)
    # …and the aspects it carried, so "If a friendly <Aspect> unit was defeated this
    # phase" (Chancellor Palpatine TWI_17) can be answered without re-finding the
    # card (a token unit ceases to exist and is in no discard pile).
    _dead_aspects = [a.name for a in (getattr(ci.card_def, "aspects", None) or ())]
    if _dead_aspects:
        s.game_memory.defeated_aspects_this_round.setdefault(
            owner_ps.player_id, []).extend(_dead_aspects)
    # …and the TRAIT sibling, for "If a friendly Rebel unit was defeated this phase"
    # (Jyn Erso LAW_5).  EFFECTIVE traits, read here while the unit is still whole —
    # a TraitGrant (Foundling SHD_69) counts, and a token unit that is about to cease
    # to exist is recorded before it does.
    from swu.engine.traits import get_traits
    _dead_traits = list(get_traits(s, ci) or ())
    if _dead_traits:
        s.game_memory.defeated_traits_this_round.setdefault(
            owner_ps.player_id, []).extend(_dead_traits)
    # …and whether it was a LEADER unit, for "While a leader unit has been defeated
    # this phase" (Captain Pellaeon ASH_93).  Either player's leader counts, so this
    # ledger is not keyed by controller; ``deployed`` is still set here (the reset
    # to the base zone happens further down).
    from swu.cards.models import Leader as _LeaderDef
    if isinstance(ci.card_def, _LeaderDef):
        s.game_memory.leader_units_defeated_this_phase.add(ci.instance_id)
        # …and the SIDE that lost it, for "If a friendly leader unit left play this
        # phase" (Fateful Goodbye ASH_211).  ``owner_ps`` is the controller-at-death.
        s.game_memory.leader_unit_defeat_controllers_this_phase.add(
            owner_ps.player_id)

    # Phase 3: WhenDefeated and WhenUnitDefeated ability triggers
    # Determine after_all_player_idx: the currently active player should
    # remain active (the attacker's action that caused this defeat will
    # handle switching via _switch_active_player after the pipeline ends).
    after_idx = s.active_player_index
    from swu.abilities.resolver import fire_triggered_abilities
    # Pass the defeated CardInstance itself so its own "When Defeated" trigger
    # can be collected — at this point it has already been removed from its
    # arena (and not yet placed in discard), so it is not in _cards_in_play.
    # ``defeated_controller_id`` records who controlled it at the moment of
    # defeat (``owner_ps`` is always the holding/controller PlayerState here):
    # a bounty resolves for that controller's OPPONENT, so a WhenDefeated bounty
    # CustomEffect can identify the collector even after the unit leaves play.
    event_ctx_defeated = {"defeated_id": ci.instance_id, "defeated_ci": ci,
                          "defeated_controller_id": owner_ps.player_id,
                          "defeated_power": defeated_power,
                          "defeated_upgrades": defeated_upgrades,
                          "defeated_while_attacking": bool(while_attacking),
                          "defeated_by_combat_damage": bool(by_combat_damage)}
    fire_triggered_abilities(s, evt_defeated, after_all_player_idx=after_idx, event_ctx=event_ctx_defeated)

    # Bounties GRANTED to this unit for the phase (The Client SHD_31: "Choose a
    # unit. For this phase, it gains: 'Bounty — Heal 5 damage from a base.'").
    # These are deterministic (no player choice), so they resolve INLINE here for
    # the collector — the OPPONENT of whoever controlled the unit at death — using
    # the same enemy-of-the-controller convention as the printed/upgrade bounties.
    if ci.granted_bounties:
        collector = s.players[1 - s.player_index(owner_ps.player_id)].player_id
        for key in list(ci.granted_bounties):
            _resolve_granted_bounty(s, collector, key)

    # A WhenDefeated trigger may have relocated this card back into play instead
    # of to discard (Stolen Landspeeder SHD_161's Bounty replays it from its
    # owner's discard "for free").  When it did, the card is a fresh in-play
    # object again — skip the discard/base placement (and the leaving-play
    # modifier expiry, which the replay already handled) to avoid double-homing.
    if event_ctx_defeated.get("relocated_by_trigger"):
        return

    # Expire modifiers that targeted this unit (it's no longer in play), and any
    # ``permanent`` "while this unit is in play" modifier this unit was the source
    # of (Huyang TWI_110's +2/+2 on another unit ends when Huyang leaves play).
    s.modifiers = [
        m for m in s.modifiers
        if m.target_instance_id != ci.instance_id
        and not (m.duration == "permanent" and m.source_instance_id == ci.instance_id)
    ]

    # A defeated card always goes to its OWNER's pile, not its controller's
    # (they differ only for a control-changed unit; ``owner_ps`` above is the
    # controller).
    from swu.cards.models import TokenUnit
    owner_of_card = s.player_by_id(ci.owner_id)
    if isinstance(ci.card_def, Leader):
        ci.zone = Zone.BASE_ZONE
        ci.deployed = False
        ci.exhausted = True
        ci.damage = 0
        owner_of_card.base_zone.append(ci)
        s.event_log.append(LeaderReturnedToBase(
            player_id=owner_of_card.player_id,
            instance_id=ci.instance_id,
            leader_name=ci.card_def.display_name,
        ))
    elif isinstance(ci.card_def, TokenUnit):
        # A token unit ceases to exist when it leaves play — it is never placed in
        # any discard pile (like Shield/Experience tokens; see _create_token_units).
        pass
    else:
        ci.zone = Zone.DISCARD
        owner_of_card.discard.append(ci)


# ── Put a chosen in-play unit on the top or bottom of its owner's deck

def _apply_put_on_deck(s: GameState, target_id: str, *, to_top: bool) -> GameState:
    """Relocate an in-play unit to the top (``to_top``) or bottom of its owner's
    deck.  Strips its non-token upgrades to their owners' discards and resets the
    card (damage/exhaust/flags cleared, face_down) — a card out of play is a clean
    card, the _apply_return_to_hand rule mirrored for the deck."""
    result = s.find_instance(target_id)
    if result is None:
        return s
    ps, ci = result
    from swu.cards.models import TokenUpgrade
    for upg in list(ci.attached_upgrades):
        if not isinstance(upg.card_def, TokenUpgrade):
            upg_owner = s.player_by_id(upg.owner_id)
            upg.zone = Zone.DISCARD
            upg_owner.discard.append(upg)
    ci.attached_upgrades.clear()
    ci.damage = 0
    ci.exhausted = False
    ci.face_down = True
    ci.cannot_ready_this_round = False
    ci.defeat_at_regroup = False
    ci.return_to_owner_hand_at_regroup = False
    ci.return_control_to_owner_at_regroup = False
    ci.bottom_at_regroup = False
    for arena in (ps.ground_arena, ps.space_arena):
        if ci in arena:
            arena.remove(ci)
            break
    ci.zone = Zone.DECK
    owner_ps = s.player_by_id(ci.owner_id)
    if to_top:
        owner_ps.deck.insert(0, ci)  # deck[0] is the top (drawn via pop(0))
    else:
        owner_ps.deck.append(ci)     # bottom
    # A relocated card no longer sources any 'while this unit is in play' permanent
    # modifier it granted (Huyang TWI_110) — drop them for hygiene (the compute-time
    # source-in-play guard already makes them inert).
    s.modifiers = [
        m for m in s.modifiers
        if not (m.duration == "permanent" and m.source_instance_id == ci.instance_id)
    ]
    return s


# ── Capture ───────────────────────────────────────────────────────────────────

def _rescue_captured_card(s: GameState, captive_ci: CardInstance) -> bool:
    """RESCUE ``captive_ci``: it leaves the capture pile for its OWNER'S HAND.

    The CR rescue destination — unlike the leave-play RELEASE
    (``_release_captured_cards``), which returns captives to their owner's arena.
    Returns False if the card is not currently in a capture pile.  (Unexpected
    Escape SHD_76, Cad Bane TWI_187.)
    """
    for ps in s.players:
        if captive_ci not in ps.capture_pile:
            continue
        captor_id = captive_ci.captured_by
        ps.capture_pile.remove(captive_ci)
        owner_ps = s.player_by_id(captive_ci.owner_id)
        captive_ci.captured_by = None
        captive_ci.face_down = False
        captive_ci.damage = 0
        captive_ci.exhausted = False
        captive_ci.zone = Zone.HAND
        owner_ps.hand.append(captive_ci)
        s.event_log.append(UnitReturnedFromCapture(
            instance_id=captive_ci.instance_id,
            card_name=captive_ci.card_def.display_name,
            owner_id=captive_ci.owner_id,
            captor_instance_id=captor_id,
        ))
        return True
    return False
