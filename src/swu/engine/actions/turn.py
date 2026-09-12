"""Starting a game: deck setup, opening hands, and the seeded RNG.

``create_game`` builds the initial ``GameState`` from two decklists — shuffling with
a seeded RNG, dealing opening hands, and pushing the mulligan decisions that the
first ``legal_actions`` call will offer.

The seeding is the part worth protecting.  Every shuffle and random choice in a game
must come from ``state.make_rng()`` so that a seed fully determines the game: the
soak suite plays 400 seeded games and the determinism regression replays specific
seeds expecting identical results.  Two bugs in this area were real and are worth
remembering — a global ``random.shuffle`` that made the same seed diverge, and
``uuid4`` modifier ids that made a serialised end state differ run to run.  Both are
covered by ``tests/regressions/test_determinism_seeded_replay.py``.

The starting hand size is a value, not a constant, because a base can change it —
``_starting_hand_modifier`` is why ``STARTING_HAND_SIZE`` is only the default.
"""
from __future__ import annotations

from typing import Optional

from swu.cards.models import AnyCard, Base, Leader
from swu.engine.events import (
    GameStarted, HandDrawn,
)
from swu.engine.state import (
    CardInstance, GameState, Phase, PlayerState, Zone,
)

from swu.engine.actions.zones import (
    _draw_cards,
)


# ── Setup actions ─────────────────────────────────────────────────────────────

STARTING_HAND_SIZE = 6


def _starting_hand_modifier(ps: "PlayerState"):
    """The ``StartingHandModifier`` marker on ``ps``'s base, or None.

    Scans the player's ``base_zone`` (which also holds the undeployed leader — a
    leader carrying the marker would count too, but none prints it).  A no-op read
    for every base without the marker (the ``_extra_regroup_active`` shape)."""
    from swu.abilities.registry import get_abilities, StartingHandModifier
    for ci in ps.base_zone:
        sc = getattr(ci.card_def, "set_code", None) or ""
        cn = getattr(ci.card_def, "card_number", None) or ""
        if not sc or not cn:
            continue
        for spec in get_abilities(sc, cn):
            if isinstance(spec, StartingHandModifier):
                return spec
    return None


def _starting_hand_size(ps: "PlayerState") -> int:
    """How many cards ``ps`` draws for an opening hand (and redraws on a mulligan).

    The standard 6, shifted by their base's ``StartingHandModifier`` — "Draw 1 less
    card in your starting hand" (Colossus JTL_21) / "Draw 3 more" (Nabat Village
    JTL_28).  Floored at 0."""
    spec = _starting_hand_modifier(ps)
    return max(0, STARTING_HAND_SIZE + (int(spec.amount) if spec is not None else 0))


# ── Game creation ─────────────────────────────────────────────────────────────

def create_game(
    player0_id: str,
    deck0: list[AnyCard],
    player1_id: str,
    deck1: list[AnyCard],
    seed: Optional[int] = None,
) -> GameState:
    """Build the initial GameState: shuffle decks, flip coin, draw opening hands."""
    rng = _new_rng(seed)
    counter = 0

    def make_player(pid: str, deck: list[AnyCard]) -> PlayerState:
        nonlocal counter
        ps = PlayerState(player_id=pid)
        for card in deck:
            if isinstance(card, Leader):
                ci = CardInstance(
                    instance_id=f"{pid}_{counter}", card_def=card,
                    owner_id=pid, zone=Zone.BASE_ZONE,
                )
                counter += 1
                ps.base_zone.append(ci)
            elif isinstance(card, Base):
                ci = CardInstance(
                    instance_id=f"{pid}_{counter}", card_def=card,
                    owner_id=pid, zone=Zone.BASE_ZONE,
                )
                counter += 1
                ps.base_zone.append(ci)
            else:
                ci = CardInstance(
                    instance_id=f"{pid}_{counter}", card_def=card,
                    owner_id=pid, zone=Zone.DECK,
                )
                counter += 1
                ps.deck.append(ci)
        return ps

    ps0 = make_player(player0_id, deck0)
    ps1 = make_player(player1_id, deck1)

    rng.shuffle(ps0.deck)
    rng.shuffle(ps1.deck)
    initiative_holder = rng.randint(0, 1)

    state = GameState(
        players=[ps0, ps1],
        phase=Phase.SETUP_MULLIGAN,
        active_player_index=0,
        initiative_holder=initiative_holder,
        rng_state=rng.getstate(),
        _next_id=counter,
    )
    state.event_log.append(GameStarted(
        player_ids=(player0_id, player1_id),
        initiative_holder_id=state.players[initiative_holder].player_id,
    ))

    # The opening hand is 6, shifted by each player's base (Colossus JTL_21 draws
    # 1 less, Nabat Village JTL_28 draws 3 more) — see _starting_hand_size.
    n0 = _starting_hand_size(ps0)
    _draw_cards(state, ps0, n0)
    state.event_log.append(HandDrawn(player_id=player0_id, card_count=n0))
    n1 = _starting_hand_size(ps1)
    _draw_cards(state, ps1, n1)
    state.event_log.append(HandDrawn(player_id=player1_id, card_count=n1))

    return state


# ── Internal helpers ──────────────────────────────────────────────────────────

def _new_rng(seed: Optional[int]) -> "random.Random":  # noqa: F821 (imported in body)
    import random
    return random.Random(seed)
