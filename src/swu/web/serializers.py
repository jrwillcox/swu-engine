"""
Pure translation between engine objects and the API's Pydantic models.

No game logic lives here — these functions only reshape data the engine already
produced (`PlayerView`, `Action`, `GameEvent`) and decorate cards with image
URLs the frontend can fetch over HTTP.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from swu.engine.actions import Action
from swu.engine.views import PlayerView
from swu.web.cards import has_back, image_version, variants_for_card
from swu.web.models import (
    ActionModel,
    CardModel,
    CardVariantImages,
    EventModel,
    PendingDecisionModel,
    PlayerViewModel,
    ZoneModel,
)


def _card_image_url(card_id: int, face: str = "front", variant: str | None = None) -> str | None:
    if card_id is None or card_id < 0:
        return None
    url = f"/api/cards/{card_id}/image?face={face}"
    if variant:
        url += f"&variant={variant}"
    # Cache-bust: the image endpoint is served `immutable`, so a corrected image
    # would otherwise stay stale in a browser cache (the iPad Safari repro). The
    # mtime token changes the URL whenever the file changes. See cards.image_version.
    version = image_version(card_id, face, variant)
    if version is not None:
        url += f"&v={version}"
    return url


def _card_variants(card_id: int) -> dict[str, CardVariantImages]:
    """Available alternate-art printings for a card (cosmetic; may be empty)."""
    if card_id is None or card_id < 0:
        return {}
    out: dict[str, CardVariantImages] = {}
    for vtype, faces in variants_for_card(card_id).items():
        out[vtype] = CardVariantImages(
            image_url=_card_image_url(card_id, "front", vtype),
            back_image_url=_card_image_url(card_id, "back", vtype) if faces.get("back") else None,
        )
    return out


def card_to_model(d: dict) -> CardModel:
    card_id = d["card_id"]
    return CardModel(
        instance_id=d["instance_id"],
        card_id=card_id,
        card_name=d["card_name"],
        card_type=d["card_type"],
        owner_id=d["owner_id"],
        zone=d["zone"],
        exhausted=d["exhausted"],
        damage=d["damage"],
        face_down=d["face_down"],
        deployed=d["deployed"],
        epic_action_spent=d["epic_action_spent"],
        effective_power=d["effective_power"],
        effective_hp=d["effective_hp"],
        upgrade_power=d.get("upgrade_power", 0),
        upgrade_hp=d.get("upgrade_hp", 0),
        cost=d.get("cost", 0),
        aspect_penalty=d.get("aspect_penalty", 0),
        smuggle_base=d.get("smuggle_base"),
        smuggle_penalty=d.get("smuggle_penalty", 0),
        attached_upgrades=[card_to_model(u) for u in d["attached_upgrades"]],
        keywords=d.get("keywords", []),
        image_url=_card_image_url(card_id, "front"),
        back_image_url=_card_image_url(card_id, "back") if (card_id >= 0 and has_back(card_id)) else None,
        variants=_card_variants(card_id),
    )


def _zone_to_model(d: dict) -> ZoneModel:
    return ZoneModel(
        player_id=d["player_id"],
        deck_count=d["deck_count"],
        hand=[card_to_model(c) for c in d["hand"]],
        hand_count=d["hand_count"],
        discard=[card_to_model(c) for c in d["discard"]],
        resources=[card_to_model(c) for c in d["resources"]],
        resource_count=d["resource_count"],
        available_resources=d["available_resources"],
        credits=d.get("credits", 0),
        has_force_token=d.get("has_force_token", False),
        ground_arena=[card_to_model(c) for c in d["ground_arena"]],
        space_arena=[card_to_model(c) for c in d["space_arena"]],
        base_zone=[card_to_model(c) for c in d["base_zone"]],
        is_eliminated=d["is_eliminated"],
    )


def view_to_model(view: PlayerView) -> PlayerViewModel:
    d = view.to_dict()
    return PlayerViewModel(
        viewer_id=d["viewer_id"],
        phase=d["phase"],
        round_number=d["round_number"],
        active_player_id=d["active_player_id"],
        initiative_holder_id=d["initiative_holder_id"],
        my=_zone_to_model(d["my"]),
        opponent=_zone_to_model(d["opponent"]),
        event_log_tail=d["event_log_tail"],
        pending_decisions=[PendingDecisionModel(**pd) for pd in d["pending_decisions"]],
    )


def action_to_model(
    action_id: str, action: Action, label: str | None = None
) -> ActionModel:
    params: dict[str, Any] = asdict(action) if is_dataclass(action) else {}
    return ActionModel(
        action_id=action_id,
        kind=type(action).__name__,
        label=label if label is not None else action.describe(),
        params=params,
    )


def event_to_model(event: Any) -> EventModel:
    data = asdict(event) if is_dataclass(event) else dict(getattr(event, "__dict__", {}))
    # Tuples (e.g. GameStarted.player_ids) → lists for clean JSON.
    data = {k: (list(v) if isinstance(v, tuple) else v) for k, v in data.items()}
    return EventModel(type=type(event).__name__, data=data)
