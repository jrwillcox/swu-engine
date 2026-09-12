"""
Token management — Shield and Experience tokens.

Tokens are real TokenUpgrade card defs in the DB (unlimited supply).
They attach to units like upgrades but have special defeat rules:
  * When their host leaves play, tokens cease to exist (not discarded).
  * They are never placed in any player's discard pile.
  * Experience grants +1/+1 via the normal upgrade stat path.
  * Shield grants no stats; its damage-prevention rule is enforced
    in the attack pipeline (see actions.py).

Creating a token requires loading a card def from the DB.  Defs are
cached per process to avoid repeated DB hits.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from swu.cards.models import TokenUpgrade
    from swu.engine.state import CardInstance, GameState, PlayerState


# ── Card-def cache ────────────────────────────────────────────────────────────

_token_cache: dict[str, "TokenUpgrade"] = {}


def _token_def(name: str) -> "TokenUpgrade":
    """Return the canonical TokenUpgrade card def for *name*, cached."""
    if name not in _token_cache:
        from swu.cards.repository import CardRepository, default_db_path
        from swu.cards.models import TokenUpgrade
        repo = CardRepository(default_db_path())
        for card in repo.by_name(name):
            if isinstance(card, TokenUpgrade):
                _token_cache[name] = card
                break
        if name not in _token_cache:
            raise RuntimeError(f"Token card def {name!r} not found in DB")
    return _token_cache[name]


def _clear_token_cache() -> None:
    """For tests that need a fresh cache (e.g. with a different DB)."""
    _token_cache.clear()
    _token_unit_cache.clear()
    _credit_def_cache.clear()


# ── Token creation ────────────────────────────────────────────────────────────

def _note_token_creation(
    state: "GameState",
    creator_id: str,
    kind: str,
    name: str,
    count: int,
    host_id=None,
    ready: bool = False,
) -> None:
    """Record a token creation for the settle-point drain (Moff Jerjerrod ASH_94,
    "If you would create a number of tokens, you may defeat this unit.  If you do,
    create twice that number of tokens instead").

    One record per creation call; ``_fire_token_creation_observers`` coalesces
    equal-keyed records before firing, so a two-call "give 2 Experience tokens" reads
    as one creation of 2.  Written inline rather than imported from ``actions``
    (which imports THIS module), like ``_note_upgrade_defeated``."""
    if int(count) <= 0:
        return
    state.game_memory.token_creations.append({
        "creator": creator_id, "kind": kind, "name": name,
        "count": int(count), "host": host_id, "ready": bool(ready),
    })


def attach_token(
    state: "GameState",
    owner_ps: "PlayerState",
    host_ci: "CardInstance",
    token_name: str,
    note_token_creation: bool = True,
) -> "CardInstance":
    """Create a token and attach it to host_ci.

    Emits TokenAttached and fires the bus.  Returns the new token instance.
    The token's owner is the host unit's owner.

    ``note_token_creation=False`` suppresses only the ASH_94 doubling ledger (the
    token is still created and still counts as "created this phase") — passed by
    Jerjerrod's own top-up so the doubling cannot re-arm itself.
    """
    from swu.engine.events import TokenAttached
    from swu.engine.triggers import get_bus

    token_def = _token_def(token_name)
    iid, nxt = state.alloc_instance_id()
    state._next_id = nxt

    from swu.engine.state import CardInstance
    token_ci = CardInstance(
        instance_id=iid,
        card_def=token_def,
        owner_id=host_ci.owner_id,
        zone=host_ci.zone,
    )
    host_ci.attached_upgrades.append(token_ci)
    # "When 1 or more upgrades attach to this unit (**including from Shielded**)"
    # (Sabine Wren ASH_208) — a token IS an upgrade, which is what that
    # parenthetical says; the helper is itself gated on a cached registry index.
    from swu.engine.actions import note_upgrade_attached
    note_upgrade_attached(state, host_ci)

    # "If you created a token this phase" (The Client LAW_16) — one of the three
    # token-creation chokepoints.  ``owner_ps`` is the host's controller, which is
    # the creator for every shipped card (see the ledger's docstring in state.py).
    state.game_memory.tokens_created_this_phase.add(owner_ps.player_id)
    if note_token_creation:
        _note_token_creation(state, owner_ps.player_id, "upgrade", token_name, 1,
                             host_id=host_ci.instance_id)

    evt = TokenAttached(
        token_name=token_name,
        host_instance_id=host_ci.instance_id,
        host_name=host_ci.card_def.display_name,
        owner_id=host_ci.owner_id,
    )
    state.event_log.append(evt)
    get_bus().fire(state, evt)
    return token_ci


# ── Token units ───────────────────────────────────────────────────────────────

_token_unit_cache: dict[str, "object"] = {}


def _token_unit_def(name: str):
    """Return the canonical TokenUnit card def for *name*, cached.

    Token units (e.g. Clone Trooper TWI_2) are unlimited-supply unit tokens
    *created* by an effect (the create-token-unit primitive, ahsoka-tano:05) — not
    drawn from a deck.  Like Shield/Experience/Credit tokens they are excluded from
    card conservation and cease to exist when they leave play.
    """
    if name not in _token_unit_cache:
        from swu.cards.repository import CardRepository, default_db_path
        from swu.cards.models import TokenUnit
        repo = CardRepository(default_db_path())
        for card in repo.by_name(name):
            if isinstance(card, TokenUnit):
                _token_unit_cache[name] = card
                break
        if name not in _token_unit_cache:
            raise RuntimeError(f"Token unit card def {name!r} not found in DB")
    return _token_unit_cache[name]


# ── Credit tokens ─────────────────────────────────────────────────────────────

_credit_def_cache: list = []  # one-element cache for the Credit CreditToken def


def _credit_def():
    """Return the canonical Credit token (CreditToken) card def, cached."""
    if not _credit_def_cache:
        from swu.cards.repository import CardRepository, default_db_path
        from swu.cards.models import CreditToken
        repo = CardRepository(default_db_path())
        for card in repo.by_name("Credit"):
            if isinstance(card, CreditToken):
                _credit_def_cache.append(card)
                break
        if not _credit_def_cache:
            raise RuntimeError("Credit token card def not found in DB")
    return _credit_def_cache[0]


def create_credit_token(
    state: "GameState",
    owner_ps: "PlayerState",
    note_token_creation: bool = True,
) -> "CardInstance":
    """Create a Credit token in ``owner_ps``'s credit pile (jabba-the-hutt:07).

    A Credit token is an unlimited-supply token card (like Shield/Experience): it
    is not drawn from the deck and is excluded from card conservation.  It sits in
    its own pile (``PlayerState.credits``, zone ``CREDITS``), never counts toward
    ``available_resources``, and is *defeated* (removed) while paying a resource
    cost to pay 1 less.  Emits ``CreditTokenCreated`` and returns the instance.
    """
    from swu.engine.state import Zone, CardInstance
    from swu.engine.events import CreditTokenCreated
    from swu.engine.triggers import get_bus

    credit_def = _credit_def()
    iid, nxt = state.alloc_instance_id()
    state._next_id = nxt
    token_ci = CardInstance(
        instance_id=iid,
        card_def=credit_def,
        owner_id=owner_ps.player_id,
        zone=Zone.CREDITS,
        face_down=False,
    )
    owner_ps.credits.append(token_ci)
    # "If you created a token this phase" (The Client LAW_16) — the Credit arm of
    # the three token-creation chokepoints.
    state.game_memory.tokens_created_this_phase.add(owner_ps.player_id)
    if note_token_creation:
        _note_token_creation(state, owner_ps.player_id, "credit", "Credit", 1)

    evt = CreditTokenCreated(
        player_id=owner_ps.player_id,
        instance_id=iid,
    )
    state.event_log.append(evt)
    get_bus().fire(state, evt)
    return token_ci


def _note_upgrade_defeated(state: "GameState", host_ci: "CardInstance") -> None:
    """Queue "a friendly upgrade was defeated" for the settle-point drain (Zeb
    Orrelios ASH_161).  A token upgrade IS an upgrade in SWU, so a defeated Shield /
    Advantage counts; "friendly" is measured by the HOST's controller (control
    follows the host).  Written inline rather than imported from ``actions`` (which
    imports THIS module)."""
    res = state.find_instance(host_ci.instance_id)
    controller_id = res[0].player_id if res is not None else host_ci.owner_id
    state.game_memory.upgrade_defeats.append(controller_id)


def defeat_shield(
    state: "GameState",
    host_ci: "CardInstance",
) -> bool:
    """Defeat one Shield token on host_ci.  Returns True if one was removed."""
    from swu.cards.models import TokenUpgrade
    from swu.engine.events import ShieldDefeated
    from swu.engine.triggers import get_bus

    for i, u in enumerate(host_ci.attached_upgrades):
        if isinstance(u.card_def, TokenUpgrade) and u.card_def.name == "Shield":
            host_ci.attached_upgrades.pop(i)
            _note_upgrade_defeated(state, host_ci)
            evt = ShieldDefeated(
                host_instance_id=host_ci.instance_id,
                host_name=host_ci.card_def.display_name,
                owner_id=u.owner_id,
            )
            state.event_log.append(evt)
            get_bus().fire(state, evt)
            return True
    return False


def defeat_experience(
    state: "GameState",
    host_ci: "CardInstance",
) -> bool:
    """Defeat one Experience token on host_ci.  Returns True if one was removed.

    Mirrors ``defeat_shield`` — used by "Defeat an Experience token on it"
    (Infused Brawler LOF_156's completes-an-attack ability)."""
    from swu.cards.models import TokenUpgrade
    from swu.engine.events import ExperienceDefeated
    from swu.engine.triggers import get_bus

    for i, u in enumerate(host_ci.attached_upgrades):
        if isinstance(u.card_def, TokenUpgrade) and u.card_def.name == "Experience":
            host_ci.attached_upgrades.pop(i)
            evt = ExperienceDefeated(
                host_instance_id=host_ci.instance_id,
                host_name=host_ci.card_def.display_name,
                owner_id=u.owner_id,
            )
            state.event_log.append(evt)
            get_bus().fire(state, evt)
            return True
    return False


_ADVANTAGE_INERT_KEYS: "set | None" = None


def _advantage_tokens_inert(state: "GameState", host_ci: "CardInstance") -> bool:
    """Whether ``host_ci``'s controller has an ``AdvantageTokensLoseAbilities`` marker
    in play (Eviscerator ASH_149), which turns off the Advantage token's only
    ability — its end-of-combat expiry.  A no-op scan for every board without one."""
    from swu.abilities.registry import get_all_registered, AdvantageTokensLoseAbilities
    global _ADVANTAGE_INERT_KEYS
    if _ADVANTAGE_INERT_KEYS is None:
        # ⚡ Cached registry index (the ``_suppress_leader_keys`` trick): this runs for
        # the attacker and every defender at the end of EVERY attack, so the board
        # walk below must not happen at all while no such card is registered.
        _ADVANTAGE_INERT_KEYS = {
            key for key, specs in get_all_registered().items()
            if any(isinstance(sp, AdvantageTokensLoseAbilities) for sp in specs)
        }
    if not _ADVANTAGE_INERT_KEYS:
        return False
    holder = None
    for ps in state.players:
        for arena in (ps.ground_arena, ps.space_arena):
            if any(u.instance_id == host_ci.instance_id for u in arena):
                holder = ps
                break
        if holder is not None:
            break
    if holder is None:
        return False
    for ci in holder.ground_arena + holder.space_arena:
        sc = getattr(ci.card_def, "set_code", None) or ""
        cn = getattr(ci.card_def, "card_number", None) or ""
        if (sc, cn) in _ADVANTAGE_INERT_KEYS:
            return True
    return False


def defeat_advantage_tokens(
    state: "GameState",
    host_ci: "CardInstance",
    only_ids: "frozenset | None" = None,
) -> int:
    """Defeat every Advantage token on ``host_ci``.  Returns how many were removed.

    The **Advantage** token (ASH_2) is the ASH set mechanic: a +1/+0 token upgrade
    printing "When attached unit's attack or defense ends: Defeat this upgrade."  It
    is created with the ordinary ``attach_token`` (its stats ride the normal upgrade
    stat path, exactly like Experience), so the only bespoke rule is that expiry —
    enforced in the combat pipelines the way Shield's damage-prevention rule is
    (see this module's docstring), not as a registered ability on the token.

    Called for the attacker and for every unit defender at the end of each of the
    three combat pipelines, after all damage and defeat processing, so the +1/+0 is
    still counted for the attack it was spent on.  A combatant that died has already
    had its tokens stripped by ``_defeat_unit``, so this is then a no-op.

    ``only_ids`` restricts the sweep to a snapshot taken BEFORE the attack-end
    triggers ran (``actions._snapshot_advantage_tokens``): a token an attack-end
    ability CREATES — "Attached unit gains: 'When Attack Ends: Give an Advantage
    token to this unit'" (Bokken Saber ASH_180) — is not part of the attack that just
    finished, so this attack's expiry must not take it away again."""
    from swu.cards.models import TokenUpgrade
    from swu.engine.events import UpgradeDetached
    # "Advantage tokens on friendly units lose all abilities.  (They aren't defeated
    # after combat.)" (Eviscerator ASH_149) — the token's expiry is its ONLY ability,
    # and it lives here rather than in the registry, so losing all abilities is
    # exactly this sweep declining to run (the EnemyCreditsLoseAbilities LAW_117
    # shape).  Checked per HOST, whose controller is who "friendly" is measured from.
    if _advantage_tokens_inert(state, host_ci):
        return 0
    n = 0
    for u in list(host_ci.attached_upgrades):
        if only_ids is not None and u.instance_id not in only_ids:
            continue
        if isinstance(u.card_def, TokenUpgrade) and u.card_def.name == "Advantage":
            host_ci.attached_upgrades.remove(u)
            _note_upgrade_defeated(state, host_ci)
            state.modifiers = [m for m in state.modifiers
                               if m.source_instance_id != u.instance_id]
            state.event_log.append(UpgradeDetached(
                upgrade_instance_id=u.instance_id,
                upgrade_name="Advantage",
                former_host_name=host_ci.card_def.display_name,
                owner_id=u.owner_id,
            ))
            n += 1
    return n


def strip_tokens(host_ci: "CardInstance") -> list["CardInstance"]:
    """Remove and return all tokens from host_ci (called when host leaves play).

    Tokens are silently removed — they do NOT go to any discard pile.
    Returns the list of removed token instances (for event logging by caller).
    """
    from swu.cards.models import TokenUpgrade
    tokens = [u for u in host_ci.attached_upgrades if isinstance(u.card_def, TokenUpgrade)]
    for t in tokens:
        host_ci.attached_upgrades.remove(t)
    return tokens
