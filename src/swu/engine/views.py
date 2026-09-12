"""
PlayerView — redacted, JSON-serialisable snapshot of a GameState for one player.

What each player can see per CR:
* Own hand: fully visible (card identities)
* Opponent hand: count only
* Both decks: count only (no order)
* Own resources: face-down but OWNER knows their identities
* Opponent resources: count only (identities hidden)
* All cards in play (arenas, base zone): fully visible
* Discard piles: fully visible
* Event log: fully visible
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from swu.engine.state import GameState, CardInstance, PlayerState


@dataclass
class CardView:
    instance_id: str
    card_id: int
    card_name: str
    card_type: str
    owner_id: str
    zone: str
    exhausted: bool
    damage: int
    face_down: bool
    deployed: bool
    epic_action_spent: bool
    effective_power: int
    effective_hp: int
    attached_upgrades: list["CardView"]
    cost: int = 0          # printed resource cost (public info; 0 for bases / hidden)
    keywords: list[str] = None  # type: ignore[assignment]
    # Stat modifiers an Upgrade grants its host (public info; 0 for non-upgrades).
    # A net-positive upgrade is a buff — the bot uses this to avoid buffing enemies.
    upgrade_power: int = 0
    upgrade_hp: int = 0
    # Printed set/number identity (public info; "" when hidden).  Lets a player
    # look up the card's ability definition — e.g. so the bot can avoid using an
    # ability that could only be aimed at its own cards.
    set_code: str = ""
    card_number: str = ""
    # Aspect-penalty surcharge (+2 per unmatched aspect pip) this card would incur
    # if played now, given the owner's base/leader aspects.  Computed only for the
    # viewer's OWN hand (the "what will it cost me" cards); 0 everywhere else and
    # for on-aspect / hidden cards.  Pure display: the UI shows it as a "+N" pill
    # beside the printed cost.  Does NOT account for cost reductions or aspect-
    # penalty waivers (e.g. Daimyo's Palace) — it is the raw printed-cost penalty.
    aspect_penalty: int = 0
    # Smuggle cost for one of the viewer's OWN resources that can be smuggled
    # (printed Smuggle, or Smuggle granted by an in-play Tech).  ``smuggle_base``
    # is the bracketed/granted base cost; ``smuggle_penalty`` is the +2-per-pip
    # aspect surcharge on it.  Both None/0 for non-resources, non-smuggleable
    # resources, and opponent (hidden) resources.  The UI renders them as a
    # "<base> +<penalty>" cost badge mirroring the hand-card pill.
    smuggle_base: Optional[int] = None
    smuggle_penalty: int = 0
    # Values of the NUMERIC keywords this card has right now (Raid / Restore /
    # Exploit), e.g. ``{"Raid": 2}``.  Only populated for cards in an arena, where
    # a granted or modified value can differ from the printed one.  Raid in
    # particular is a while-ATTACKING power bonus that ``effective_power`` does
    # not include, so a reader doing combat maths needs it separately.
    keyword_values: dict = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []
        if self.keyword_values is None:
            self.keyword_values = {}

    def to_dict(self) -> dict:
        d = {
            "instance_id": self.instance_id,
            "card_id": self.card_id,
            "card_name": self.card_name,
            "card_type": self.card_type,
            "owner_id": self.owner_id,
            "zone": self.zone,
            "exhausted": self.exhausted,
            "damage": self.damage,
            "face_down": self.face_down,
            "deployed": self.deployed,
            "epic_action_spent": self.epic_action_spent,
            "effective_power": self.effective_power,
            "effective_hp": self.effective_hp,
            "cost": self.cost,
            "attached_upgrades": [u.to_dict() for u in self.attached_upgrades],
            "keywords": self.keywords,
            "upgrade_power": self.upgrade_power,
            "upgrade_hp": self.upgrade_hp,
            "set_code": self.set_code,
            "card_number": self.card_number,
            "aspect_penalty": self.aspect_penalty,
            "smuggle_base": self.smuggle_base,
            "smuggle_penalty": self.smuggle_penalty,
            "keyword_values": self.keyword_values,
        }
        return d


@dataclass
class PlayerZoneView:
    player_id: str
    deck_count: int
    hand: list[CardView]           # visible cards; opponent hand is []
    hand_count: int                # always correct; hand len == hand_count for self
    discard: list[CardView]
    resources: list[CardView]      # own = with identities; opponent = empty-faced stubs
    resource_count: int
    available_resources: int
    credits: int                   # Credit tokens in the resource area (public; jabba:07)
    ground_arena: list[CardView]
    space_arena: list[CardView]
    base_zone: list[CardView]
    is_eliminated: bool
    has_force_token: bool = False  # the player's Force token (public; qui-gon-jinn:06)

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "deck_count": self.deck_count,
            "hand": [c.to_dict() for c in self.hand],
            "hand_count": self.hand_count,
            "discard": [c.to_dict() for c in self.discard],
            "resources": [c.to_dict() for c in self.resources],
            "resource_count": self.resource_count,
            "available_resources": self.available_resources,
            "credits": self.credits,
            "has_force_token": self.has_force_token,
            "ground_arena": [c.to_dict() for c in self.ground_arena],
            "space_arena": [c.to_dict() for c in self.space_arena],
            "base_zone": [c.to_dict() for c in self.base_zone],
            "is_eliminated": self.is_eliminated,
        }


@dataclass
class PendingDecisionView:
    deciding_player_id: str
    kind: str
    context: dict
    is_mine: bool  # True when this viewer is the deciding player

    def to_dict(self) -> dict:
        return {
            "deciding_player_id": self.deciding_player_id,
            "kind": self.kind,
            "context": self.context if self.is_mine else {},
            "is_mine": self.is_mine,
        }


@dataclass
class PlayerView:
    """The redacted game state as seen by player_id."""
    viewer_id: str
    phase: str
    round_number: int
    active_player_id: str
    initiative_holder_id: str
    my: PlayerZoneView
    opponent: PlayerZoneView
    event_log_tail: list[str]  # last 20 events as strings
    pending_decisions: list[PendingDecisionView]  # top is [-1]; [] when none

    def to_dict(self) -> dict:
        return {
            "viewer_id": self.viewer_id,
            "phase": self.phase,
            "round_number": self.round_number,
            "active_player_id": self.active_player_id,
            "initiative_holder_id": self.initiative_holder_id,
            "my": self.my.to_dict(),
            "opponent": self.opponent.to_dict(),
            "event_log_tail": self.event_log_tail,
            "pending_decisions": [d.to_dict() for d in self.pending_decisions],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


def _grantable_keywords(gs) -> Optional[set]:
    """The keyword names anything on this board could GRANT to a unit — an
    over-approximation used to skip impossible ``has_keyword`` queries.

    ``has_keyword`` answers one keyword at a time and, for a keyword the card does
    not print, walks every ConstantAbility on the whole board before returning
    False.  Asking it all 16 keywords per arena card made building a view ~4x
    dearer (measured: 1.6ms of a 2.6ms view).  Almost all of that work is
    provably wasted: a keyword no card in play grants, no modifier grants, and no
    upgrade grants simply cannot be on anyone.

    So we collect the grantable names once per view and let the caller check only
    ``printed ∪ grantable``.  Returns ``None`` for "cannot narrow — check
    everything", which is what a keyword-copy aura (The Ghost JTL_53) or a Support
    borrow means: those confer *another unit's* keywords, whatever they are.

    Being an over-approximation is the safe direction — a name in the set only
    costs one ``has_keyword`` call that may answer False.
    """
    from swu.abilities.registry import (
        get_abilities, KeywordGrant, CopyKeywords)
    names: set = set()

    def scan_card(ci) -> bool:
        """Add ci's grantable names; return False if we must give up narrowing."""
        for holder in (ci, *(getattr(ci, "attached_upgrades", None) or ())):
            cd = holder.card_def
            sc = getattr(cd, "set_code", None) or ""
            cn = getattr(cd, "card_number", None) or ""
            if not sc or not cn:
                continue
            for spec in get_abilities(sc, cn):
                for eff in (getattr(spec, "effects", None) or ()):
                    if isinstance(eff, KeywordGrant):
                        names.add(eff.keyword)
                    elif isinstance(eff, CopyKeywords):
                        return False
        return True

    for ps in gs.players:
        for ci in ps.ground_arena + ps.space_arena + ps.base_zone:
            if not scan_card(ci):
                return None
    for mod in getattr(gs, "modifiers", []):
        if mod.kind in ("keyword_grant", "borrowed_abilities"):
            kw = mod.value.get("keyword") if isinstance(mod.value, dict) else None
            if kw is None:
                return None  # a borrow lends whatever the lender has
            names.add(kw)
    return names


def _effective_stats_and_keywords(gs, ci, grantable=None) -> tuple:
    """(power, hp, keywords) for a card **in an arena**, as the rules see it.

    ``CardInstance.effective_power`` / ``effective_hp`` only fold in attached
    upgrades, and ``card_def.keywords`` is the printed bar — so an anthem, a
    duration modifier, Grit, or a granted Sentinel were all invisible in the view.
    Measured over real games, 4.5% of arena cards showed the wrong power, 2.2% the
    wrong HP, and 6.6% were missing a keyword they actually had (Raid, Sentinel,
    Saboteur, Grit, Ambush, Overwhelm).  Every consumer of the view — the UI's
    stat line, the heuristic bot's trade maths, the LLM prompt — was reading those
    wrong numbers.

    Only arena cards get this treatment: out of play there are no modifiers to
    apply, and the engine's constant-ability scans walk the arenas, so printed
    values are already the truth for a card in hand, deck, discard or resources.
    Falls back to the printed reading if anything raises, so a view can never
    fail to build.

    Returns ``(power, hp, keyword_names, numeric_keyword_values)``.
    """
    from swu.engine.actions import compute_power, compute_hp
    from swu.engine.keywords import Keyword, has_keyword, keyword_value
    try:
        power = compute_power(gs, ci)
        hp = compute_hp(gs, ci)
        printed = set(getattr(ci.card_def, "keywords", ()) or ())
        keywords = [
            kw.value for kw in Keyword
            if (grantable is None or kw.value in printed or kw.value in grantable)
            and has_keyword(gs, ci, kw)
        ]
        values = {}
        for kw in (Keyword.RAID, Keyword.RESTORE, Keyword.EXPLOIT):
            if kw.value in keywords:
                n = keyword_value(gs, ci, kw)
                if n:
                    values[kw.value] = n
    except Exception:
        return (ci.effective_power(), ci.effective_hp(),
                list(getattr(ci.card_def, "keywords", ()) or ()), {})
    return power, hp, keywords, values


def _card_view(ci: "CardInstance", reveal_identity: bool,
               aspect_penalty: int = 0,
               smuggle_base: Optional[int] = None,
               smuggle_penalty: int = 0,
               gs: "GameState" = None,
               grantable: Optional[set] = None) -> CardView:
    if reveal_identity:
        if gs is not None:
            power, hp, keywords, kw_values = _effective_stats_and_keywords(
                gs, ci, grantable)
        else:
            power, hp = ci.effective_power(), ci.effective_hp()
            keywords = list(getattr(ci.card_def, "keywords", ()) or ())
            kw_values = {}
        return CardView(
            instance_id=ci.instance_id,
            card_id=ci.card_def.id,
            card_name=ci.card_def.display_name,
            card_type=ci.card_def.type,
            owner_id=ci.owner_id,
            zone=ci.zone.name,
            exhausted=ci.exhausted,
            damage=ci.damage,
            face_down=ci.face_down,
            deployed=ci.deployed,
            epic_action_spent=ci.epic_action_spent,
            effective_power=power,
            effective_hp=hp,
            cost=int(getattr(ci.card_def, "cost", 0) or 0),
            attached_upgrades=[_card_view(u, True) for u in ci.attached_upgrades],
            keywords=keywords,
            upgrade_power=int(getattr(ci.card_def, "upgrade_power", 0) or 0),
            upgrade_hp=int(getattr(ci.card_def, "upgrade_hp", 0) or 0),
            set_code=getattr(ci.card_def, "set_code", "") or "",
            card_number=getattr(ci.card_def, "card_number", "") or "",
            aspect_penalty=aspect_penalty,
            smuggle_base=smuggle_base,
            smuggle_penalty=smuggle_penalty,
            keyword_values=kw_values,
        )
    else:
        return CardView(
            instance_id=ci.instance_id,
            card_id=-1,
            card_name="[hidden]",
            card_type="[hidden]",
            owner_id=ci.owner_id,
            zone=ci.zone.name,
            exhausted=ci.exhausted,
            damage=0,
            face_down=True,
            deployed=False,
            epic_action_spent=False,
            effective_power=0,
            effective_hp=0,
            attached_upgrades=[],
            keywords=[],
        )


def _zone_view(gs: "GameState", ps: "PlayerState", viewer_id: str,
               grantable: Optional[set] = None) -> PlayerZoneView:
    is_self = ps.player_id == viewer_id
    # Aspect-penalty surcharge is only meaningful (and only shown) for the
    # viewer's own hand — the cards they're deciding whether to afford.
    if is_self:
        from swu.engine.actions import _aspect_penalty
        hand_views = [
            _card_view(
                c, True,
                _aspect_penalty(
                    tuple(a.name for a in (getattr(c.card_def, "aspects", None) or ())),
                    ps, gs,
                ),
            )
            for c in ps.hand
        ]
    else:
        hand_views = []
    # Own resources: owner can see identities (face-down means hidden from
    # opponent).  For the owner, also surface the per-resource Smuggle cost
    # (base + aspect penalty) so the UI can show a "<base> +<penalty>" badge on a
    # smuggle-able resource.  Opponent resources stay hidden stubs with no cost.
    if is_self:
        from swu.engine.actions import _smuggle_cost_parts
        resource_views = []
        for r in ps.resources:
            parts = _smuggle_cost_parts(gs, r, ps)
            if parts is None:
                resource_views.append(_card_view(r, True))
            else:
                base, pen = parts
                resource_views.append(
                    _card_view(r, True, smuggle_base=base, smuggle_penalty=pen))
    else:
        resource_views = [_card_view(r, False) for r in ps.resources]
    return PlayerZoneView(
        player_id=ps.player_id,
        deck_count=len(ps.deck),
        hand=hand_views,
        hand_count=len(ps.hand),
        discard=[_card_view(c, True) for c in ps.discard],
        resources=resource_views,
        resource_count=len(ps.resources),
        available_resources=ps.available_resources,
        credits=len(ps.credits),
        has_force_token=bool(getattr(ps, "has_force_token", False)),
        # Cards in an arena get their EFFECTIVE stats and keywords (anthems,
        # modifiers, Grit, granted keywords) — see _effective_stats_and_keywords.
        ground_arena=[_card_view(c, True, gs=gs, grantable=grantable)
                      for c in ps.ground_arena],
        space_arena=[_card_view(c, True, gs=gs, grantable=grantable)
                     for c in ps.space_arena],
        base_zone=[_card_view(c, True) for c in ps.base_zone],
        is_eliminated=ps.is_eliminated,
    )


def build_view(gs: "GameState", player_id: str) -> PlayerView:
    viewer_ps = gs.player_by_id(player_id)
    opponent_ps = gs.players[1 - gs.player_index(player_id)]
    tail = [type(e).__name__ for e in gs.event_log[-20:]]
    # Computed once for the whole view: which keywords this board could grant, so
    # each arena card only asks ``has_keyword`` about keywords that are possible.
    try:
        grantable = _grantable_keywords(gs)
    except Exception:
        grantable = None  # "cannot narrow" — ask about every keyword
    decision_views = [
        PendingDecisionView(
            deciding_player_id=d.deciding_player_id,
            kind=d.kind,
            context=d.context if d.deciding_player_id == player_id else {},
            is_mine=(d.deciding_player_id == player_id),
        )
        for d in gs.pending_decisions
    ]
    return PlayerView(
        viewer_id=player_id,
        phase=gs.phase.name,
        round_number=gs.round_number,
        active_player_id=gs.active_player.player_id,
        initiative_holder_id=gs.players[gs.initiative_holder].player_id,
        my=_zone_view(gs, viewer_ps, player_id, grantable),
        opponent=_zone_view(gs, opponent_ps, player_id, grantable),
        event_log_tail=tail,
        pending_decisions=decision_views,
    )
