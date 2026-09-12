"""
Card dataclasses — loaded from swu.db by the repository layer.

Every field the game engine and LLM player will need is present:
- Full rules text, aspects in order (with duplicates), keywords, traits,
  arenas, stats, leader deploy/epic text, image paths.

The LLM player receives a serialised representation of a card; the
`to_text()` method on each class produces the canonical form.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AspectPip:
    """A single aspect pip, ordered by position on the card frame."""
    position: int
    name: str
    color: str
    is_duplicate: bool  # True for doubled pips (e.g. double Villainy)


@dataclass(frozen=True)
class CardBase:
    """Fields shared by every card type."""
    id: int
    card_uid: Optional[str]
    set_code: Optional[str]
    set_name: Optional[str]
    card_number: str
    name: str
    subtitle: Optional[str]
    type: str
    rarity: Optional[str]
    is_unique: bool
    artist: Optional[str]

    # Rules content
    text: Optional[str]
    text_styled: Optional[str]
    rules: Optional[str]        # errata/FAQ clarifications (separate from card text)
    rules_styled: Optional[str]

    # Relations
    aspects: tuple[AspectPip, ...]
    keywords: tuple[str, ...]
    traits: tuple[str, ...]
    arenas: tuple[str, ...]

    # Images
    image_front_url: Optional[str]
    image_back_url: Optional[str]
    image_front_path: Optional[str]
    image_back_path: Optional[str]

    @property
    def display_name(self) -> str:
        if self.subtitle:
            return f"{self.name} — {self.subtitle}"
        return self.name

    @property
    def aspect_names(self) -> list[str]:
        """All aspect names in order, duplicates included."""
        return [a.name for a in sorted(self.aspects, key=lambda a: a.position)]

    def to_text(self) -> str:
        """Produce a human/LLM-readable text block for this card."""
        parts = [
            f"[{self.type.upper()}] {self.display_name}",
            f"Set: {self.set_code} #{self.card_number}  Rarity: {self.rarity}",
        ]
        if self.aspect_names:
            parts.append(f"Aspects: {', '.join(self.aspect_names)}")
        if self.traits:
            parts.append(f"Traits: {', '.join(self.traits)}")
        if self.arenas:
            parts.append(f"Arenas: {', '.join(self.arenas)}")
        if self.keywords:
            parts.append(f"Keywords: {', '.join(self.keywords)}")
        if self.text:
            parts.append(f"Text: {self.text}")
        return "\n".join(parts)


@dataclass(frozen=True)
class Unit(CardBase):
    """A Unit card (ground or space combatant)."""
    cost: int
    power: int
    hp: int
    upgrade_power: Optional[int] = None   # stat bonus when played as a pilot (Piloting keyword)
    upgrade_hp: Optional[int] = None
    epic_action: Optional[str] = None     # Piloting cost clause, e.g. "Piloting [2 resources …]"


@dataclass(frozen=True)
class Leader(CardBase):
    """
    A Leader card — double-sided.
    Front side: leader ability (deploy_box, epic_action).
    Back side (deployed unit): power/hp stats.

    leader_power / leader_hp are the undeployed "leader unit" side stats.
    The DB does not store them; the ability registry provides per-leader
    values.  Defaults are 0 (attack not legal if 0, or override per card).
    """
    power: int               # deployed unit side stats
    hp: int                  # deployed unit side stats
    deploy_box: Optional[str]
    epic_action: Optional[str]
    leader_power: int = 0    # undeployed leader unit side power
    leader_hp: int = 0       # undeployed leader unit side hp
    # Stat bonus when this leader is deployed as an upgrade (Boba Fett JTL_9's
    # "deploy as an upgrade on a friendly Vehicle" option) — read by
    # compute_power / compute_hp via getattr(card_def, "upgrade_power", 0), exactly
    # like a pilot Unit's upgrade stats.  None for the vast majority of leaders.
    upgrade_power: Optional[int] = None
    upgrade_hp: Optional[int] = None

    def to_text(self) -> str:
        base = super().to_text()
        parts = [base]
        if self.deploy_box:
            parts.append(f"Deploy ability: {self.deploy_box}")
        if self.epic_action:
            parts.append(f"Epic action: {self.epic_action}")
        parts.append(f"Deployed stats: {self.power}/{self.hp}")
        if self.leader_power or self.leader_hp:
            parts.append(f"Leader unit stats: {self.leader_power}/{self.leader_hp}")
        return "\n".join(parts)


@dataclass(frozen=True)
class Base(CardBase):
    """A Base card."""
    hp: int
    epic_action: Optional[str]

    def to_text(self) -> str:
        base = super().to_text()
        parts = [base, f"HP: {self.hp}"]
        if self.epic_action:
            parts.append(f"Epic action: {self.epic_action}")
        return "\n".join(parts)


@dataclass(frozen=True)
class Event(CardBase):
    """An Event card."""
    cost: int


@dataclass(frozen=True)
class Upgrade(CardBase):
    """An Upgrade card (attached to a unit)."""
    cost: int
    upgrade_power: Optional[int]   # stat modifier, may be None or 0
    upgrade_hp: Optional[int]

    def to_text(self) -> str:
        base = super().to_text()
        parts = [base]
        mods = []
        if self.upgrade_power is not None:
            mods.append(f"+{self.upgrade_power} power")
        if self.upgrade_hp is not None:
            mods.append(f"+{self.upgrade_hp} HP")
        if mods:
            parts.append(f"Modifiers: {', '.join(mods)}")
        return "\n".join(parts)


@dataclass(frozen=True)
class TokenUnit(CardBase):
    """A token unit (Shield, Experience, etc.)."""
    power: Optional[int]
    hp: Optional[int]


@dataclass(frozen=True)
class TokenUpgrade(CardBase):
    """A token upgrade (e.g. Shield, Experience, Advantage)."""
    upgrade_power: Optional[int]
    upgrade_hp: Optional[int]


@dataclass(frozen=True)
class CreditToken(CardBase):
    """Credit token — can be defeated while paying resources to reduce cost by 1."""


@dataclass(frozen=True)
class ForceToken(CardBase):
    """The Force token — granted by Force-related abilities; removed on use."""


# Union of all card types for type hints
AnyCard = Unit | Leader | Base | Event | Upgrade | TokenUnit | TokenUpgrade | CreditToken | ForceToken
