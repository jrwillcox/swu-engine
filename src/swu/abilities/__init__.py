"""Card ability framework — Phase 3."""
from swu.abilities.registry import (
    card_ability, get_abilities, is_escape_hatch, get_all_registered,
    TriggerAbility, ConstantAbility, ActivatedAbility, EventAbility, CustomAbility,
    GrantedAbility, unwrap_granted,
    WhenPlayed, WhenDefeated, WhenDefeatedAsUpgrade, OnAttack, WhenAttacked,
    WhenUnitDefeated, WhenUnitEntersPlay, OnAttackDefeatsUnit,
    PhaseStartTrigger, RoundStartTrigger,
    DealDamage, Heal, DefeatUnit, DefeatAllUnits, GiveToken, CreateCreditToken,
    DrawCards, DiscardFromHand, ReturnToHand, ExhaustCard, ReadyCard,
    ModifyStats, GrantKeyword, RevokeKeyword, ConditionalEffect, CustomEffect,
    StatBonus, KeywordGrant, SuppressFirstEnemyEvent,
    ExhaustSelf, PayResources, DefeatSelf,
    TargetSpec, Condition, ConditionCheck, Duration,
    SELF, ATTACKER, DEFENDER, EACH_FRIENDLY, EACH_ENEMY, EACH_IN_PLAY,
)
from swu.abilities.resolver import fire_triggered_abilities, resolve_effects_actions

__all__ = [
    "card_ability", "get_abilities", "is_escape_hatch", "get_all_registered",
    "fire_triggered_abilities", "resolve_effects_actions",
    "TriggerAbility", "ConstantAbility", "ActivatedAbility", "EventAbility", "CustomAbility",
    "GrantedAbility", "unwrap_granted",
    "WhenPlayed", "WhenDefeated", "WhenDefeatedAsUpgrade", "OnAttack", "WhenAttacked",
    "WhenUnitDefeated", "WhenUnitEntersPlay", "OnAttackDefeatsUnit",
    "PhaseStartTrigger", "RoundStartTrigger",
    "DealDamage", "Heal", "DefeatUnit", "DefeatAllUnits", "GiveToken", "CreateCreditToken",
    "DrawCards", "DiscardFromHand", "ReturnToHand", "ExhaustCard", "ReadyCard",
    "ModifyStats", "GrantKeyword", "RevokeKeyword", "ConditionalEffect", "CustomEffect",
    "StatBonus", "KeywordGrant", "SuppressFirstEnemyEvent",
    "ExhaustSelf", "PayResources", "DefeatSelf",
    "TargetSpec", "Condition", "ConditionCheck", "Duration",
    "SELF", "ATTACKER", "DEFENDER", "EACH_FRIENDLY", "EACH_ENEMY", "EACH_IN_PLAY",
]
