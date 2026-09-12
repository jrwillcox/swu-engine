"""
Typed game events appended to GameState.event_log by apply().

The UI and replay system render from these. Phase 2/3 triggers will
also listen to the same event types via the TriggerBus.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GameEvent:
    pass


@dataclass(frozen=True)
class GameStarted(GameEvent):
    player_ids: tuple[str, str]
    initiative_holder_id: str


@dataclass(frozen=True)
class HandDrawn(GameEvent):
    player_id: str
    card_count: int


@dataclass(frozen=True)
class MulliganTaken(GameEvent):
    player_id: str


@dataclass(frozen=True)
class HandKept(GameEvent):
    player_id: str


@dataclass(frozen=True)
class CardResourced(GameEvent):
    player_id: str
    instance_id: str
    card_name: str


@dataclass(frozen=True)
class CreditTokenCreated(GameEvent):
    """A Credit token was created in a player's resource area (jabba-the-hutt:07)."""
    player_id: str
    instance_id: str


@dataclass(frozen=True)
class CreditDefeated(GameEvent):
    """A Credit token was defeated while paying a resource cost (paid 1 less)."""
    player_id: str
    instance_id: str


@dataclass(frozen=True)
class PhaseChanged(GameEvent):
    new_phase: str
    round_number: int


@dataclass(frozen=True)
class RoundStarted(GameEvent):
    round_number: int
    initiative_holder_id: str


@dataclass(frozen=True)
class CardPlayed(GameEvent):
    player_id: str
    instance_id: str
    card_name: str
    cost_paid: int


@dataclass(frozen=True)
class UnitEntersPlay(GameEvent):
    player_id: str
    instance_id: str
    card_name: str
    arena: str  # "Ground" or "Space"


@dataclass(frozen=True)
class UpgradePlayed(GameEvent):
    player_id: str
    instance_id: str
    card_name: str
    attached_to_instance_id: str


@dataclass(frozen=True)
class AttackDeclared(GameEvent):
    attacker_player_id: str
    attacker_instance_id: str
    attacker_name: str
    defender_instance_id: str | None  # None = attacking base
    defender_name: str
    # True when the defender had to be this unit because it has Sentinel (the
    # base and any non-Sentinel units were not legal targets). Lets the UI
    # explain why the target was forced rather than freely chosen.
    forced_by_sentinel: bool = False


@dataclass(frozen=True)
class DamageDealt(GameEvent):
    target_instance_id: str | None  # None = base
    target_name: str
    owner_id: str
    amount: int
    is_base: bool
    # Name of the card whose ability dealt this damage (e.g. "Darth Vader").
    # None for ordinary combat damage, where the attacker is already clear from
    # the preceding AttackDeclared event.
    source_name: str | None = None


@dataclass(frozen=True)
class UnitDefeated(GameEvent):
    player_id: str
    instance_id: str
    card_name: str


@dataclass(frozen=True)
class UpgradeDetached(GameEvent):
    upgrade_instance_id: str
    upgrade_name: str
    former_host_name: str
    owner_id: str


@dataclass(frozen=True)
class LeaderDeployed(GameEvent):
    player_id: str
    instance_id: str
    leader_name: str
    arena: str


@dataclass(frozen=True)
class LeaderReturnedToBase(GameEvent):
    player_id: str
    instance_id: str
    leader_name: str


@dataclass(frozen=True)
class InitiativeTaken(GameEvent):
    player_id: str


@dataclass(frozen=True)
class PlayerPassed(GameEvent):
    player_id: str


@dataclass(frozen=True)
class RegroupDrawn(GameEvent):
    player_id: str
    count: int


@dataclass(frozen=True)
class EmptyDeckDamage(GameEvent):
    player_id: str
    damage: int
    cards_missed: int


@dataclass(frozen=True)
class RegroupResourced(GameEvent):
    player_id: str
    instance_id: str
    card_name: str


@dataclass(frozen=True)
class RegroupSkipped(GameEvent):
    player_id: str


@dataclass(frozen=True)
class AllCardsReadied(GameEvent):
    round_number: int


@dataclass(frozen=True)
class GameOver(GameEvent):
    winner_player_id: str
    loser_player_id: str


# ── Phase 2 events ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TokenAttached(GameEvent):
    token_name: str          # "Shield" or "Experience"
    host_instance_id: str
    host_name: str
    owner_id: str


@dataclass(frozen=True)
class ShieldDefeated(GameEvent):
    host_instance_id: str
    host_name: str
    owner_id: str


@dataclass(frozen=True)
class ExperienceDefeated(GameEvent):
    host_instance_id: str
    host_name: str
    owner_id: str


@dataclass(frozen=True)
class RestoreHealing(GameEvent):
    player_id: str
    amount: int
    source_name: str | None = None


@dataclass(frozen=True)
class OverwhelmDamage(GameEvent):
    defending_player_id: str
    amount: int


@dataclass(frozen=True)
class CombatDamagePrevented(GameEvent):
    """A unit's incoming combat damage was prevented by a replacement effect that
    defeated a friendly unit to do so (Queen Amidala SEC_101)."""
    unit_instance_id: str
    unit_name: str
    owner_id: str
    amount: int


@dataclass(frozen=True)
class DamagePrevented(GameEvent):
    """A unit's incoming non-combat (ability) damage was prevented by a replacement
    effect that defeated a friendly unit to do so (Queen Amidala SEC_101 — the
    ability-damage half; combat is CombatDamagePrevented)."""
    unit_instance_id: str
    unit_name: str
    owner_id: str
    amount: int


@dataclass(frozen=True)
class DecisionPushed(GameEvent):
    deciding_player_id: str
    kind: str


@dataclass(frozen=True)
class DecisionResolved(GameEvent):
    deciding_player_id: str
    kind: str
    choice: str  # human-readable summary of what was chosen


# ── Phase 3 events ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AbilityTriggered(GameEvent):
    """Emitted when a card ability trigger fires."""
    source_instance_id: str
    source_name: str
    trigger_kind: str          # e.g. "WhenPlayed", "OnAttack"
    optional: bool


@dataclass(frozen=True)
class AbilityEffectApplied(GameEvent):
    """Emitted when a single effect from an ability resolves."""
    source_instance_id: str
    effect_kind: str           # e.g. "DealDamage", "GiveToken"
    target_instance_id: str    # may be "" for effects without a target


@dataclass(frozen=True)
class ModifierApplied(GameEvent):
    """Emitted when a Modifier record is added to GameState.modifiers."""
    modifier_id: str
    target_instance_id: str
    kind: str
    duration: str


@dataclass(frozen=True)
class HandInspected(GameEvent):
    """Emitted when a player looks at an opponent's hand (information only).

    Carries no card identities — the engine has full information already; this
    records the act so the UI/log can surface it and coverage can see it fire.
    """
    inspecting_player_id: str
    revealed_player_id: str
    card_count: int


@dataclass(frozen=True)
class ModifierExpired(GameEvent):
    """Emitted when a Modifier is cleaned up due to duration expiry."""
    modifier_id: str
    reason: str  # "this_attack", "this_phase", "this_round"


@dataclass(frozen=True)
class EventAbilitiesSuppressed(GameEvent):
    """Emitted when a played event loses all its abilities before resolving.

    Source of the suppression is a Relentless-style replacement effect: the
    first event each opponent plays each round is blanked.  The event card was
    still played (cost paid) and still goes to discard; it simply does nothing.
    """
    player_id: str          # controller of the suppressed event
    instance_id: str        # the event card
    card_name: str
    source_instance_id: str  # the unit causing the suppression (e.g. Relentless)
    source_name: str


@dataclass(frozen=True)
class ControlChanged(GameEvent):
    """Emitted when a unit changes controller while keeping its owner.

    Control in this engine is implicit — a unit is controlled by whichever
    player's arena list holds it.  This event records a relocation between the
    two players' arenas with ``owner_id`` unchanged (Stolen Landspeeder SHD_161:
    "When Played: an opponent takes control of it").
    """
    instance_id: str
    card_name: str
    owner_id: str
    from_player_id: str
    to_player_id: str


@dataclass(frozen=True)
class UnitCaptured(GameEvent):
    """Emitted when a unit is captured (removed from play and placed facedown
    under the capturing unit).  The captured card keeps its owner; it lives in
    the capturing player's capture pile until the captor leaves play
    (The Mandalorian's Rifle SHD_251).
    """
    captor_instance_id: str
    captor_name: str
    captured_instance_id: str
    captured_name: str
    captor_player_id: str   # controller of the capturing unit
    owner_id: str           # owner of the captured card


@dataclass(frozen=True)
class UnitReturnedFromCapture(GameEvent):
    """Emitted when a captured card returns to play because the unit holding it
    left play.  It returns to its owner's arena under their control.
    """
    instance_id: str
    card_name: str
    owner_id: str
    captor_instance_id: str


@dataclass(frozen=True)
class UnitReadied(GameEvent):
    """Emitted when a unit is readied by an ability (not the regroup ready-all).

    Used by Admiral Ozzel (SOR_129): the played Imperial unit enters ready and
    each opponent may ready one of their units.
    """
    player_id: str          # controller of the readied unit
    instance_id: str
    card_name: str
