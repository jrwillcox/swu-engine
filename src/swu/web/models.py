"""
Pydantic models for every API payload.

These mirror the engine's `PlayerView.to_dict()` shape (so the OpenAPI schema
stays honest) and add a handful of UI-convenience fields the backend computes
(``image_url`` on cards; ``label``/``params`` on actions) so the frontend never
has to know engine internals.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


# ── Cards & zones ─────────────────────────────────────────────────────────────

class CardVariantImages(BaseModel):
    image_url: Optional[str] = None
    back_image_url: Optional[str] = None


class CardModel(BaseModel):
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
    # Stat bonus this card grants as an upgrade (an upgrade-in-hand reports
    # effective_power/hp of 0, so these carry its printed buff). Both 0 for a
    # net-neutral upgrade (e.g. a Bounty/control upgrade), which is the only kind
    # that legitimately belongs on an enemy unit — the UI uses that to skip the
    # "attach to an enemy?" confirm.
    upgrade_power: int = 0
    upgrade_hp: int = 0
    cost: int = 0
    # Aspect-penalty surcharge (+2 per unmatched pip) for this card in the
    # viewer's own hand; 0 for on-aspect / in-play / opponent / hidden cards.
    # The UI renders it as a "+N" pill beside the printed cost.
    aspect_penalty: int = 0
    # Smuggle cost for one of your own smuggle-able resources: base bracket/granted
    # cost + aspect-penalty surcharge. None/0 otherwise. Rendered as a "<base> +<N>"
    # badge on the (face-down) resource.
    smuggle_base: Optional[int] = None
    smuggle_penalty: int = 0
    attached_upgrades: list["CardModel"] = []
    keywords: list[str] = []
    # UI convenience — backend-computed; None for hidden/back-only cards.
    image_url: Optional[str] = None
    back_image_url: Optional[str] = None
    # Available alternate art, keyed by variant type (hyperspace / hyperspace_foil
    # / showcase) → {image_url, back_image_url}.  Empty for cards with no variants.
    # Cosmetic only; the frontend chooses which to show per the user's setting.
    variants: dict[str, CardVariantImages] = {}


class ZoneModel(BaseModel):
    player_id: str
    deck_count: int
    hand: list[CardModel]
    hand_count: int
    discard: list[CardModel]
    resources: list[CardModel]
    resource_count: int
    available_resources: int
    credits: int = 0
    has_force_token: bool = False
    ground_arena: list[CardModel]
    space_arena: list[CardModel]
    base_zone: list[CardModel]
    is_eliminated: bool


class PendingDecisionModel(BaseModel):
    deciding_player_id: str
    kind: str
    context: dict[str, Any]
    is_mine: bool


class PlayerViewModel(BaseModel):
    viewer_id: str
    phase: str
    round_number: int
    active_player_id: str
    initiative_holder_id: str
    my: ZoneModel
    opponent: ZoneModel
    event_log_tail: list[str]
    pending_decisions: list[PendingDecisionModel]


# ── Actions & events ──────────────────────────────────────────────────────────

class ActionModel(BaseModel):
    action_id: str          # backend-assigned; the ONLY handle the frontend uses
    kind: str               # engine Action class name, e.g. "PlayCard"
    label: str              # human-readable, from Action.describe()
    params: dict[str, Any]  # the action's dataclass fields (instance_id, target_id, …)


class EventModel(BaseModel):
    type: str               # engine GameEvent class name, e.g. "UnitDefeated"
    data: dict[str, Any]    # the event's dataclass fields


# ── Aggregate snapshots ───────────────────────────────────────────────────────

class Snapshot(BaseModel):
    """Everything the frontend needs to render and decide what to offer next."""
    game_id: str
    view: PlayerViewModel
    awaiting: str                 # "human" | "bot" | "terminal"
    actor_id: Optional[str]       # whose input is needed (None if terminal)
    winner: Optional[str]         # player_id of the winner, or None
    prompt: Optional[str]         # set when a decision needs the human
    actions: list[ActionModel]    # the human's legal actions (empty unless awaiting==human)


class StepResult(Snapshot):
    """A snapshot plus the ordered events produced by the step that led to it."""
    events: list[EventModel] = []


# ── Requests ──────────────────────────────────────────────────────────────────

class SeatConfig(BaseModel):
    kind: str = "human"           # "human" | "weighted_bot"
    deck: str                     # catalog key ("luke") or path to a decklist


class NewGameRequest(BaseModel):
    human: SeatConfig
    bot: SeatConfig
    seed: Optional[int] = None
    difficulty: str = "normal"     # "easy" | "normal" | "hard"; unknown → normal


class NewGameResponse(Snapshot):
    player_id: str                # the human seat's player id


class DeckChoice(BaseModel):
    key: str
    label: str
    leader_name: str
    base_name: str
    kind: str = "official"        # "official" (built-in/graduated) | "custom"


# ── Custom deck builder (Stage 3) ────────────────────────────────────────────
#
# The store's own payloads (``CustomDeck`` / ``DeckSummary``) live in
# ``swu.web.deckstore``; these are the HTTP request bodies for the routes.

class CreateCustomDeckRequest(BaseModel):
    name: str


class PatchCustomDeckRequest(BaseModel):
    """Partial edit.  A field left out is unchanged; an explicit ``null`` on
    ``leader_id``/``base_id`` clears that slot.  The route uses
    ``model_fields_set`` to tell "omitted" from "explicitly null"."""
    name: Optional[str] = None
    leader_id: Optional[int] = None
    base_id: Optional[int] = None
    cards: Optional[dict[str, int]] = None


class CardDeltaRequest(BaseModel):
    card_id: int
    delta: int


# ── Auth (user login) ─────────────────────────────────────────────────────────

class CheckRequest(BaseModel):
    username: str


class CheckResponse(BaseModel):
    exists: bool        # this username already has a password set
    allowed: bool       # this username is on the whitelist (may register)


class AuthRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    token: str          # bearer token; the client persists it in localStorage
    username: str       # display name (the casing the user typed)
    admin: bool


class MeResponse(BaseModel):
    username: str
    admin: bool


class ResetRequest(BaseModel):
    username: str
    new_password: str


class UserSummary(BaseModel):
    username: str
    admin: bool
    registered: bool


# ── Card explorer (catalog browsing / future deck-builder) ───────────────────

class ExplorerCard(BaseModel):
    id: int                       # DB primary key — also the image endpoint key
    set_code: str
    card_number: str
    name: str
    subtitle: Optional[str] = None
    type: str
    rarity: Optional[str] = None
    cost: Optional[int] = None
    power: Optional[int] = None
    hp: Optional[int] = None
    unique: bool = False
    aspects: list[str] = []
    keywords: list[str] = []
    traits: list[str] = []
    arenas: list[str] = []
    status: str                   # classifier label (implemented / text-bearing / …)
    playable: bool                # "Available to play" in the engine
    decks: list[str] = []         # catalog deck keys this card appears in
    image_url: Optional[str] = None
    # Card back (Leaders / double-sided Bases); null for single-faced cards.
    back_image_url: Optional[str] = None
    # Alternate-art printings (hyperspace / hyperspace_foil / showcase) →
    # {image_url, back_image_url}.  Empty for cards with no downloaded variants.
    variants: dict[str, CardVariantImages] = {}


class SetChoice(BaseModel):
    code: str
    name: str


class ExplorerDeck(BaseModel):
    key: str
    label: str


class ExplorerResponse(BaseModel):
    """Full card catalog plus the distinct values for each filter facet."""
    cards: list[ExplorerCard]
    sets: list[SetChoice]
    types: list[str]
    aspects: list[str]
    keywords: list[str]
    traits: list[str]
    decks: list[ExplorerDeck]


CardModel.model_rebuild()
