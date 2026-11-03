"""
Game sessions — the backend's in-memory ownership of live GameStates.

A `GameSession` holds one GameState, the human seat id, and the bot that drives
the other seat.  It is the single place that:
  * decides whose input is needed (`awaiting`),
  * assigns stable, opaque action ids for the human's current decision point,
  * applies a human action (validated against freshly-computed `legal_actions`),
  * and resolves the bot's turn(s), returning the events produced.

The frontend only ever names an action by the id assigned here, so it can never
smuggle an illegal or invented Action past the engine.
"""
from __future__ import annotations

import json
import secrets
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from swu.engine.actions import Action, apply, legal_actions
from swu.engine.state import GameState
from swu.players.base import Player
from swu.players.difficulty import Difficulty, make_opponent
from swu.web.decks import resolve_deck

HUMAN_ID = "human"
BOT_ID = "bot"

SAVE_FORMAT = 1  # bump when the save/replay schema changes

_PROMPTS: dict[str, str] = {
    "ambush": "Ambush — attack now with the unit that just entered play, or decline.",
    "exploit": "Exploit — sacrifice friendly units to reduce the cost, or commit.",
    "trigger_option": "A triggered ability is ready — use it or decline.",
    "resolve_effects": "Choose a target for the resolving ability.",
    "pre_attack": "Continue the attack.",
    "granted_attack": "Choose a unit to attack with — it gets a bonus for this attack.",
    "play_from_hand": "Play an Imperial unit from your hand — it enters play ready.",
    "play_event_from_hand": "Play an event from your hand — it costs 1 resource less.",
    "play_via_smuggle": "Play a card from your resources using Smuggle — it costs 2 less; then defeat a resource you own.",
    "play_via_piloting": "Play a card from your hand using Piloting — choose the pilot and the friendly Vehicle it rides.",
    "opponent_ready": "You may ready one of your units.",
    "distribute_damage": "Divide the damage — choose how to assign it among the legal units.",
    "deck_search": "Searching your deck — take a revealed card, or finish (the rest go to the bottom).",
    "peek_top": "Look at the top card of your deck — decide what to do with it.",
    "choose_number": "Choose a number.",
    "modal": "Choose one effect, then its target.",
    "let_wookiee_win": "Let the Wookiee Win — the opponent chooses which effect you get.",
    "say_no": "An opponent targets your unit — allow the effect, or say 'no' (they draw cards).",
    "regroup_upkeep": "Regroup upkeep — pay 1 resource to keep this unit, or return it to your hand.",
    "pay_or_exhaust": "The Eye of Aldhani — for each of your units, pay 1 resource or let it be exhausted.",
    "repeated_modal": "Discard up to 3 cards, then choose a different option for each.",
    "sacrifice_resource": "You may defeat a friendly resource to deal damage — or decline.",
    "reveal_resource_ramp": "Reveal a resource matching a friendly unique unit to return it and ramp — or decline.",
    "combat_damage_prevention": "You may defeat a friendly trait-sharing unit to prevent combat damage to this unit — or decline.",
    "ability_damage_prevention": "You may defeat a friendly trait-sharing unit to prevent this damage to your unit — or decline.",
    "discard_unit_damage": "Recycle a unit from your discard pile (to the bottom of your deck), then deal its power to an enemy ground unit.",
    "cull_for_damage": "Give up any number of your own cards — then deal that many damage.",
    "discard_for_search": "Discard a unit from your hand, then search your deck for the named card and draw it.",
    "opponent_chooses_target": "Choose one of your units or base — your opponent may deal damage to it.",
    "owner_may_replay": "A unit was returned to your hand — you may play it for free, or decline.",
    "put_on_deck": "Put the chosen unit on the top or bottom of your deck.",
    "opponent_split_bounce": "Choose up to 2 non-leader units — the opponent picks which returns to hand (the other is bottomed).",
    "reveal_top": "Revealed cards — discard any, then keep the rest on top in the order you choose.",
    "select_token": "Choose eligible units — each gets a token or a bonus — pick one at a time, or finish.",
    "return_from_discard": "Return eligible cards from your discard pile to your hand — pick one at a time, or finish.",
    "discard_for_experience": "You may discard a card from your hand with the same name as your unit to give it 2 Experience tokens — or decline.",
    "resource_from_discard": "Choose a card in your discard pile to put into play as a resource.",
    "bottom_from_discard": "Choose up to 4 cards in a discard pile to put on the bottom of their owner's deck (random order) — pick one at a time, or finish.",
    "select_distinct_return_random": "Choose cards in your discard pile with different names — one at a time; when the last is chosen, one of them returns to your hand at random.",
    "move_upgrade": "You may move an upgrade to another eligible unit controlled by the same player — or decline.",
    "pay_and_steal_upgrade": "You may pay an upgrade's cost to take control of it and attach it to this unit (or defeat it if it can't attach) — or decline.",
    "pilot_self_attach": "You may attach this unit as a Pilot onto a friendly Vehicle without a Pilot — or decline.",
    "play_upgrade_from_hand": "You may play an upgrade from your hand — choose a host, or decline.",
    "plot": "Plot — you may play a Plot card from your resources (paying its cost), or finish.",
    "reveal_play_credit": "Reveal the top of a deck, then choose who may play it for free.",
    "look_hand": "You're looking at your opponent's hand.",
    "name_a_card": "Name a card — each of the opponent's non-leader copies loses all abilities while this unit is in play.",
    "each_player_defeats": "Choose one of your non-leader units to be defeated.",
    "capture_or_ready": "Choose one of your non-leader units to be captured, or decline.",
    "choose_units_sacrifice_rest": "Choose a unit to spare — all your other units will be defeated.",
    "resolve_unique": "You control two copies of a unique card — choose which one to keep; the other is defeated.",
    "bottom_from_hand": "Put cards from your hand on the bottom (or, when offered, the top) of your deck — pick one at a time (pick order = bottom order).",
    "resource_from_hand": "You may resource cards from your hand — each enters your resource row ready. Pick one at a time, or stop.",
    "discard_excess_from_hand": "Discard cards from your hand down to the required size — choose which to discard, one at a time.",
    "name_and_discard": "Name a card in the opponent's revealed hand — one copy of it is discarded.",
    "may_discard": "An opponent's effect: discard a random card from your hand, or decline (and suffer the effect).",
    "disclose": "You may disclose — reveal cards from your hand bearing the required aspect icons for a bonus, or decline.",
    "exhaust_for_base_damage": "Exhaust any number of friendly units — each deals 1 damage to the defending base. Pick one at a time, or finish.",
    "exhaust_combined_cost": "Exhaust any number of units with combined cost 6 or less — pick one at a time, or finish.",
    "capture_combined_hp": "Capture any number of enemy non-leader units with combined remaining HP 7 or less — pick one at a time, or finish.",
    "rescue_guarded": "You may rescue one of your cards guarded by the attacking unit — but if you do, its controller draws cards.",
    "multi_capture_pairing": "Choose any number of your units — each captures an enemy non-leader unit in the same arena. Pick a captor and its prey, one pair at a time, or finish.",
    "combined_power_play": "Choose any number of your units. Their combined power is the most a unit you then play from hand for free may cost — and the chosen units are defeated afterwards.",
    "play_captured_card": "Choose a captured card guarded by one of your units — you may play it for free under your control, or decline.",
    "play_resource_units": "Reveal any number of your resources — play each revealed unit for free, one at a time, or stop.",
    "reveal_cull_draw": "Cards are revealed from the top of the deck: the opponent discards some of them, then the controller draws one of the survivors and discards the rest.",
    "pay_resources_for_tokens": "Spend cost items (resources — exhausted or returned to hand — or Credit tokens); each one buys this card's payoff. Spend one at a time, or finish.",
    "recur_and_buff": "Put up to 3 Force units from your discard on the bottom of your deck — pick one at a time, or finish; then give that many units +4/+4.",
    "use_force": "You may use the Force (lose your Force token) for a bonus — or decline.",
    "per_exploit_damage": "For each unit you exploited, you may deal its power to an enemy unit — choose a target, or decline.",
    "assign_indirect_damage": "Assign indirect damage among your base and units — choose where to place each point.",
    "select_damage": "Deal 1 damage to each of up to 3 units — pick one at a time, or finish.",
    "choose_two_modal": "Choose from the listed options, in any order — pick one at a time (pick order = resolution order).",
    "reveal_cost_damage": "Reveal cards one at a time — stop before the combined cost passes 7 to deal that much to the chosen unit; the revealed cards go to the bottom.",
    "test": "Answer the decision.",
}


class IllegalStep(Exception):
    """Raised when a requested step is not valid for the current state."""


@dataclass
class GameSession:
    game_id: str
    state: GameState
    bot: Player                    # any Player; the factory decides which kind
    human_id: str = HUMAN_ID
    bot_id: str = BOT_ID
    difficulty: Difficulty = Difficulty.NORMAL
    action_cap: int = 5000
    # Reproduction metadata (for save/restore + replay).  human_deck/bot_deck are
    # the catalog keys or paths originally passed to create; seed + the ordered
    # action_history let a recorded game be re-driven deterministically (the same
    # repro-bundle format soak.py/replay.py use: {kind, desc} per action).
    seed: int | None = None
    human_deck: str = ""
    bot_deck: str = ""
    action_history: list[dict] = field(default_factory=list)
    _action_cache: dict[str, Action] = field(default_factory=dict)

    def _record(self, action: Action) -> None:
        self.action_history.append(
            {"kind": type(action).__name__, "desc": action.describe()})

    # ── turn / actor introspection ─────────────────────────────────────────

    def actor_id(self) -> str | None:
        s = self.state
        if s.is_terminal():
            return None
        if s.pending_decisions:
            return s.pending_decisions[-1].deciding_player_id
        return s.active_player.player_id

    def awaiting(self) -> str:
        if self.state.is_terminal():
            return "terminal"
        return "human" if self.actor_id() == self.human_id else "bot"

    @property
    def winner(self) -> str | None:
        return self.state.winner

    def prompt(self) -> str | None:
        s = self.state
        if not s.pending_decisions:
            return None
        top = s.pending_decisions[-1]
        if top.deciding_player_id != self.human_id:
            return None
        base = _PROMPTS.get(top.kind, "Make a choice.")
        if top.kind == "each_player_defeats":
            if top.context.get("disposition") == "spare_then_damage":
                amount = top.context.get("damage_amount", 0)
                base = (f"Choose a unit you control to spare — every unit not "
                        f"chosen this way takes {amount} damage.")
            elif top.context.get("disposition") == "return_then_defeat_all":
                base = ("Choose one of your non-leader units to return to hand — "
                        "every non-leader unit left in play is then defeated.")
        elif top.kind == "capture_combined_hp":
            if top.context.get("disposition") == "defeat":
                budget = top.context.get("remaining_budget")
                base = (f"Defeat any number of non-leader units with combined "
                        f"remaining HP {budget} or less — pick one at a time, or "
                        f"finish.")
        elif top.kind == "exploit":
            n = top.context.get("max_remaining")
            if n is not None:
                base = f"Exploit — sacrifice up to {n} more friendly unit(s), or commit."
        elif top.kind == "distribute_damage":
            ctx = top.context
            stage = ctx.get("stage")
            if stage in ("pick_source",):
                base = "Choose the unit that deals the damage."
            elif stage == "pick_target":
                base = "Choose the unit to be dealt damage."
            else:
                pool = ctx.get("pool")
                if pool is not None:
                    base = f"Assign damage — {pool} point(s) left to divide among the legal units."
        elif top.kind == "peek_top":
            mode = top.context.get("mode")
            if mode == "may_bottom":
                base = "Top card of your deck — leave it on top, or put it on the bottom."
            elif mode == "may_discard":
                base = "Top card of your deck — leave it on top, or discard it."
            elif mode == "may_draw":
                base = "The top card's cost matches — reveal and draw it, or leave it on top."
            elif mode == "reveal_only":
                base = "The top card's cost doesn't match — it stays on top."
            elif mode == "may_play_discard":
                name = top.context.get("peeked_card_name") or "the top card"
                base = f"Top card of your deck ({name}) — play it, discard it, or leave it on top."
            elif mode == "may_play":
                name = top.context.get("peeked_card_name") or "the top card"
                free = bool(top.context.get("free"))
                red = int(top.context.get("cost_reduction", 0) or 0)
                disc = ("for free" if free else f"costing {red} less" if red else "")
                base = f"Top card of your deck ({name}) — play it {disc}, or leave it on top.".replace("  ", " ")
            elif mode == "may_draw_or_discard_heal":
                name = top.context.get("peeked_card_name") or "the top card"
                heal = int(top.context.get("discard_heal", 0) or 0)
                base = f"Top card of your deck ({name}) — draw it, or discard it and heal {heal} damage from your base."
        elif top.kind == "modal":
            ctx = top.context
            if ctx.get("stage") == "mode":
                from swu.engine.actions import _MODAL_MODE_LABELS
                opts = ", ".join(
                    _MODAL_MODE_LABELS.get(m, m).lower() for m in ctx.get("modes", []))
                base = f"Choose one: {opts}." if opts else "Choose one effect."
            else:
                chosen = ctx.get("chosen_mode")
                if chosen == "ready_resource":
                    base = "Choose one of your exhausted resources to ready."
                elif chosen == "exhaust_resource":
                    base = "Choose one of your ready resources to exhaust."
                elif chosen == "exhaust_unit":
                    base = "Choose a unit to exhaust."
        elif top.kind == "let_wookiee_win":
            if top.context.get("stage") == "ready":
                base = ("Ready a friendly unit — if it's a Wookiee it then attacks "
                        "with +2/+0.")
            elif top.deciding_player_id == self.human_id:
                base = ("Let the Wookiee Win — choose one for your opponent: they "
                        "ready up to 6 resources, or ready a unit (a Wookiee attacks "
                        "+2/+0).")
        elif top.kind == "repeated_modal":
            ctx = top.context
            stage = ctx.get("stage")
            if stage == "discard":
                base = "Discard up to 3 cards from your hand (one option per card), or finish."
            elif stage == "choose_target":
                base = "Choose a target for the selected option."
            else:
                base = "Choose a different option for each discarded card."
        elif top.kind == "reveal_cost_damage":
            ctx = top.context
            n = len(ctx.get("revealed_ids", []))
            tally = int(ctx.get("tally", 0))
            thr = int(ctx.get("threshold", 7))
            names = ", ".join(r["card_name"] for r in ctx.get("revealed", [])) or "none yet"
            over = " — over the limit, would deal 0" if tally > thr else ""
            base = (f"Revealed {n} ({names}); combined cost {tally}{over}. "
                    f"Reveal another, or stop (dealing {tally if tally <= thr else 0}).")
        elif top.kind == "sacrifice_resource":
            if top.context.get("stage") == "target":
                base = "Choose a unit to be dealt the damage."
            else:
                base = "Defeat one of your resources to deal damage, or decline."
        elif top.kind == "reveal_resource_ramp":
            base = ("Reveal a resource that shares a name with a friendly unique "
                    "unit — return it to hand and put your deck's top card into "
                    "play as a resource"
                    + (", or decline." if top.context.get("optional") else "."))
        elif top.kind == "cull_for_damage":
            if top.context.get("stage") == "target":
                base = "Choose what takes the damage — one for each card you gave up."
            elif top.context.get("pool") == "hand":
                base = ("Discard any number of cards from your hand, then finish — "
                        "you deal that many damage.")
            else:
                base = ("Defeat any number of your tokens, then finish — you deal "
                        "that many damage.")
        elif top.kind == "discard_unit_damage":
            if top.context.get("stage") == "target":
                base = "Choose an enemy ground unit to take the recycled unit's power as damage."
            else:
                base = "Choose a unit in your discard pile to put on the bottom of your deck (its power = the damage dealt)."
        elif top.kind == "opponent_chooses_target":
            if top.context.get("stage") == "confirm":
                base = "You may deal damage to the unit or base the opponent chose, or decline."
            elif top.context.get("disposition") == "defeat":
                base = "Choose one of your units — the opponent will defeat it."
            elif top.context.get("disposition") == "exhaust":
                base = "Choose one of your ready units — it will be exhausted."
            else:
                base = "Choose one of your units or base — the opponent may deal damage to it."
        elif top.kind == "opponent_split_bounce":
            if top.context.get("stage") == "split":
                base = ("The opponent chose 2 of your units — pick which returns to "
                        "its owner's hand (the other goes to the bottom of its deck).")
            else:
                base = ("Choose up to 2 non-leader units, then finish — the opponent "
                        "picks which returns to hand (the other is bottomed).")
        elif top.kind == "reveal_play_credit":
            ctx = top.context
            stage = ctx.get("stage")
            name = ctx.get("revealed_card_name")
            if stage == "choose_deck":
                base = "Reveal the top card of a deck — choose which deck."
            elif stage == "choose_player":
                base = f"Revealed {name} — choose who may play it for free."
            elif stage == "choose_host":
                base = f"Choose a unit to attach the revealed {name} to."
            else:  # may_play
                cost = ctx.get("revealed_cost")
                base = (f"You may play {name} for free "
                        f"(the other player then makes {cost} Credit(s)), or decline.")
        elif top.kind == "trigger_option":
            # Name the source card and quote its ability text so the player knows
            # what "use it" actually does (e.g. heal a unit), rather than a bare
            # "a triggered ability is ready".
            found = s.find_instance(top.context.get("source_id", ""))
            if found is not None:
                name = found[1].card_def.display_name
                text = (getattr(found[1].card_def, "text", "") or "").strip()
                base = (f"{name} — {text} Use it, or decline."
                        if text else f"{name}'s ability is ready — use it, or decline.")
        return base

    # ── action surfacing ───────────────────────────────────────────────────

    def _rebuild_cache(self) -> dict[str, Action]:
        self._action_cache = {
            f"a{i}": a for i, a in enumerate(legal_actions(self.state))
        }
        return self._action_cache

    def human_actions(self) -> list[tuple[str, Action]]:
        """(action_id, Action) pairs for the human, or [] if not their turn."""
        if self.awaiting() != "human":
            self._action_cache = {}
            return []
        cache = self._rebuild_cache()
        return list(cache.items())

    def label_for(self, action: Action) -> str:
        """A human-readable button label for ``action``.

        The engine's ``describe()`` only knows instance ids (it has no card
        names), so a target-picking action renders as e.g. "Choose target
        human_19".  Here — where we hold the live state — we resolve the id to
        the target card's name so the decision banner reads "Target Fleet
        Lieutenant".  Everything else falls back to ``describe()``.
        """
        from swu.engine.actions import (
            ChooseTarget, DiscardRevealed, KeepRevealed, PlotPlay, SmugglePlay,
            SelectSearchCard, SelectDiscardCard, SelectDiscardUnitForDamage,
            DiscardForSearch, PlayFromHand, PlayEventFromHand, SelectHandCardToBottom,
            SelectHandCardToTop,
            SelectUnitToExhaust, SelectUnitToExhaustCombined,
            SelectBottomDiscardCard, SelectDistinctDiscardCard,
            SelectResourceFromDiscard, SelectDiscardForExperience,
            SelectCapturedToPlay, SelectResourceUnitToPlay, RescueGuardedCard,
            CullRevealedCard, DrawRevealedCard, PlayViaPiloting,
        )
        # Card-anchored selection actions name an instance id; resolve the card's
        # name so the label (and the log) reads "Take Greef Karga", not a raw id.
        _verbs = {
            SelectSearchCard: "Take",
            SelectDiscardCard: "Return",
            PlayFromHand: "Play",
            PlayEventFromHand: "Play",
            PlayViaPiloting: "Pilot",
            DiscardForSearch: "Discard",
            SelectDiscardUnitForDamage: "Recycle",
            SelectHandCardToBottom: "Bottom",
            SelectHandCardToTop: "Top",
            SelectBottomDiscardCard: "Bottom",
            SelectDistinctDiscardCard: "Choose",
            SelectResourceFromDiscard: "Resource",
            SelectDiscardForExperience: "Discard",
            SelectCapturedToPlay: "Play captured",
            SelectResourceUnitToPlay: "Play from resources",
            RescueGuardedCard: "Rescue",
            CullRevealedCard: "Discard",
            DrawRevealedCard: "Draw",
        }
        for cls, verb in _verbs.items():
            if isinstance(action, cls):
                name = self._card_name(action.instance_id)
                if name:
                    return f"{verb} {name}"
        if isinstance(action, SmugglePlay):
            # describe() only knows instance ids ("Smuggle human_42"); here we
            # resolve the smuggled card's name, and (for an upgrade) its host.
            name = self._card_name(action.instance_id) or "card"
            host = self._card_name(action.upgrade_target_id) if action.upgrade_target_id else None
            return f"Smuggle {name}" + (f" onto {host}" if host else "")
        if isinstance(action, PlotPlay):
            name = self._card_name(action.instance_id) or "card"
            host = self._card_name(action.upgrade_target_id) if action.upgrade_target_id else None
            return f"Plot {name}" + (f" onto {host}" if host else "")
        from swu.engine.actions import DeployLeaderAsUpgrade
        if isinstance(action, DeployLeaderAsUpgrade):
            host = self._card_name(action.vehicle_target_id) or "a Vehicle"
            return f"Deploy leader as upgrade on {host}"
        from swu.engine.actions import ChoosePreventionSacrifice
        if isinstance(action, ChoosePreventionSacrifice):
            name = self._card_name(action.target_id) or "a friendly unit"
            return f"Defeat {name} to prevent the damage"
        from swu.engine.actions import RevealResourceForRamp
        if isinstance(action, RevealResourceForRamp):
            name = self._card_name(action.resource_id) or "a resource"
            return f"Reveal {name} (return it and ramp)"
        from swu.engine.actions import PayToAvoidExhaust, AcceptExhaust
        if isinstance(action, PayToAvoidExhaust):
            name = self._card_name(action.unit_id) or "this unit"
            return f"Pay 1 resource to keep {name} ready"
        if isinstance(action, AcceptExhaust):
            name = self._card_name(action.unit_id) or "this unit"
            return f"Let {name} be exhausted"
        from swu.engine.actions import AttackTwoUnits
        if isinstance(action, AttackTwoUnits):
            atk = self._card_name(action.attacker_id) or "unit"
            d1 = self._card_name(action.defender1_id) or "a unit"
            d2 = self._card_name(action.defender2_id) or "a unit"
            return f"Attack {d1} & {d2} with {atk}"
        from swu.engine.actions import CaptureWithUnit
        if isinstance(action, CaptureWithUnit):
            captor = self._card_name(action.captor_id) or "a unit"
            prey = self._card_name(action.prey_id) or "an enemy unit"
            return f"Capture {prey} with {captor}"
        from swu.engine.actions import PlayFromDiscard
        if isinstance(action, PlayFromDiscard):
            # Replay a card from the discard pile (Brutal Traditions SHD_38);
            # name the card and, for an upgrade, its chosen host.
            name = self._card_name(action.instance_id) or "card"
            host = self._card_name(action.upgrade_target_id) if action.upgrade_target_id else None
            return f"Play {name} from discard" + (f" onto {host}" if host else "")
        from swu.engine.actions import PlayUpgradeFromHand
        if isinstance(action, PlayUpgradeFromHand):
            # The upgrade is either carried on the action (choose mode, Fenn Rau
            # SHD_67) or fixed in the decision context (Jabba ASH_42).
            upg_id = action.upgrade_id
            if upg_id is None and self.state.pending_decisions:
                upg_id = self.state.pending_decisions[-1].context.get("upgrade_id")
            upg = self._card_name(upg_id) if upg_id else None
            host = self._card_name(action.host_id) or "a unit"
            return f"Play {upg or 'the upgrade'} onto {host}"
        if isinstance(action, (SelectUnitToExhaust, SelectUnitToExhaustCombined)):
            name = self._card_name(action.target_id)
            if name:
                return f"Exhaust {name}"
        from swu.engine.actions import KeepUniqueCopy
        if isinstance(action, KeepUniqueCopy):
            name = self._card_name(action.instance_id)
            if name:
                return f"Keep {name}"
        from swu.engine.actions import PlayTopCard, DiscardTopCard, KeepTopCard
        if isinstance(action, (PlayTopCard, DiscardTopCard, KeepTopCard)):
            name = None
            if self.state.pending_decisions:
                ctx = self.state.pending_decisions[-1].context
                if ctx.get("mode") in ("may_play_discard", "may_play",
                                       "may_discard",
                                       "may_draw_or_discard_heal"):
                    name = ctx.get("peeked_card_name")
            if name:
                if isinstance(action, PlayTopCard):
                    host = self._card_name(action.upgrade_target_id) if action.upgrade_target_id else None
                    return f"Play {name}" + (f" onto {host}" if host else "")
                if isinstance(action, DiscardTopCard):
                    return f"Discard {name}"
                return f"Leave {name} on top"
        from swu.engine.actions import UseAbility
        if isinstance(action, UseAbility) and action.actor_id is not None:
            # An aura-granted Action (Satine Kryze TWI_47) is offered once per unit
            # that gained it, so the button must name the ACTOR — describe() would
            # otherwise show two raw instance ids.
            actor = self._card_name(action.actor_id) or "a unit"
            src = self._card_name(action.source_id)
            return f"Use {src}'s ability with {actor}" if src else f"Use ability with {actor}"
        if isinstance(action, ChooseTarget):
            name = self._card_name(action.target_id)
            if name:
                return f"Target {name}"
        from swu.engine.actions import ChooseWookieeReadyUnit
        if isinstance(action, ChooseWookieeReadyUnit):
            name = self._card_name(action.unit_id)
            if name:
                return f"Ready {name}"
        if isinstance(action, KeepRevealed):
            name = self._card_name(action.card_id)
            if name:
                return f"Keep {name} on top"
        if isinstance(action, DiscardRevealed):
            name = self._card_name(action.card_id)
            if name:
                disposition = "discard"
                if self.state.pending_decisions:
                    disposition = self.state.pending_decisions[-1].context.get(
                        "disposition", "discard")
                if disposition == "bottom":
                    return f"Put {name} on the bottom"
                return f"Discard {name}"
        return action.describe()

    def _card_name(self, instance_id: str) -> str | None:
        found = self.state.find_instance(instance_id)
        return found[1].card_def.display_name if found is not None else None

    # ── stepping ───────────────────────────────────────────────────────────

    def apply_human(self, action_id: str) -> list:
        """Apply the human action named by ``action_id``; return events produced."""
        if self.state.is_terminal():
            raise IllegalStep("Game is over.")
        if self.actor_id() != self.human_id:
            raise IllegalStep("It is not your turn.")
        cache = self._action_cache or self._rebuild_cache()
        action = cache.get(action_id) or self._rebuild_cache().get(action_id)
        if action is None:
            raise KeyError(action_id)
        # Defence in depth: confirm the cached action is still legal right now.
        if action not in legal_actions(self.state):
            raise IllegalStep("That action is no longer legal.")
        before = len(self.state.event_log)
        self.state = apply(self.state, action)
        self._record(action)
        self._auto_resolve_forced_noops()
        self._action_cache = {}
        return self.state.event_log[before:]

    def _auto_resolve_forced_noops(self) -> None:
        """Collapse forced single-option decisions that offer the human no choice.

        Two engine bookmarks surface as a lone, meaningless click for the human:

        * ``pre_attack`` → ``ContinueAttack``.  When a unit's On Attack trigger
          needs a decision the engine splits the attack: it fires the trigger,
          then leaves this bookmark whose only action deals the combat damage.
          Once the trigger is resolved there is nothing left to decide.
        * ``granted_attack`` → ``DeclineGrantedAttack``.  An effect that lets a
          unit attack (e.g. Fleet Lieutenant) always pushes the decision, even
          when the controller has *no* unit able to attack — leaving only a
          no-op decline.

        In both cases the sole legal action is forced, so we auto-apply it in
        place.  We deliberately do **not** auto-resolve a ``granted_attack`` that
        still offers a real attack (those carry >1 action — the player keeps the
        choice) nor any other single-option decision.  Auto-applied actions are
        recorded so replay stays faithful, and their events remain in
        ``event_log`` so the frontend still animates them.  Bot seats resolve
        their own bookmarks in ``advance_bot``'s loop, so this is human-only.
        """
        from swu.engine.actions import ContinueAttack, DeclineGrantedAttack
        s = self.state
        while (
            not s.is_terminal()
            and s.pending_decisions
            and s.pending_decisions[-1].deciding_player_id == self.human_id
        ):
            legal = legal_actions(s)
            if len(legal) != 1 or not isinstance(
                legal[0], (ContinueAttack, DeclineGrantedAttack)
            ):
                break
            s = apply(s, legal[0])
            self._record(legal[0])
        self.state = s

    def advance_bot(self) -> list:
        """Resolve consecutive bot actions; return the ordered events produced.

        After each bot decision we drain any *fallback notices* the bot wants
        shown in the in-game log (an LLM bot emits one when it drops to its
        heuristic for a decision — API error, timeout, truncation, illegal
        choice).  They are interleaved just before the action's own events so
        the player can see exactly when and why the opponent fell back.  A
        heuristic bot has no ``drain_notices`` and contributes nothing here.
        """
        events: list = []
        iters = 0
        while (
            not self.state.is_terminal()
            and self.actor_id() == self.bot_id
            and iters < self.action_cap
        ):
            legal = legal_actions(self.state)
            view = self.state.view_for(self.bot_id)
            chosen = self.bot.choose_action(view, legal)
            notices = self._drain_bot_notices()
            before = len(self.state.event_log)
            self.state = apply(self.state, chosen)
            self._record(chosen)
            events.extend(notices)
            events.extend(self.state.event_log[before:])
            iters += 1
        self._action_cache = {}
        return events

    def _drain_bot_notices(self) -> list:
        """Pull any user-visible fallback notices the bot accumulated this turn."""
        drain = getattr(self.bot, "drain_notices", None)
        if callable(drain):
            try:
                return list(drain())
            except Exception:
                return []
        return []

    # ── save / restore / replay ─────────────────────────────────────────────

    def replay_bundle(self) -> dict:
        """A shareable, deterministic replay bundle (seed + decks + the ordered
        action history).  Re-driving it from scratch reproduces this game exactly
        (same repro-bundle shape soak.py/replay.py use)."""
        return {
            "format": SAVE_FORMAT,
            "kind": "replay",
            "seed": self.seed,
            "difficulty": str(self.difficulty),
            "human_deck": self.human_deck,
            "bot_deck": self.bot_deck,
            "action_history": list(self.action_history),
        }

    def save_blob(self) -> dict:
        """Full save: the live GameState (incl. mid-decision / mid-animation) plus
        the metadata needed to recreate the bot and keep replay working."""
        blob = self.replay_bundle()
        blob["kind"] = "save"
        blob["game_id"] = self.game_id
        blob["human_id"] = self.human_id
        blob["bot_id"] = self.bot_id
        blob["state"] = self.state.to_json()
        return blob


def _match_recorded(legal: list, entry: dict, step: int):
    """Pick the legal action matching a recorded {kind, desc} entry."""
    matches = [a for a in legal if type(a).__name__ == entry["kind"]]
    if not matches:
        raise IllegalStep(f"Replay diverged: no legal {entry['kind']} at step {step}")
    if len(matches) == 1:
        return matches[0]
    return next((a for a in matches if a.describe() == entry.get("desc")), matches[0])


def replay_to_state(bundle: dict) -> GameState:
    """Deterministically reconstruct the final GameState from a replay/save
    bundle by re-creating the game and re-driving its recorded action history.

    Matches each recorded {kind, desc} against the freshly-computed legal actions
    (by kind, disambiguated by describe()), exactly as scripts/replay.py does.
    """
    from swu.engine.actions import create_game
    deck_h = resolve_deck(bundle["human_deck"])
    deck_b = resolve_deck(bundle["bot_deck"])
    human_id = bundle.get("human_id", HUMAN_ID)
    bot_id = bundle.get("bot_id", BOT_ID)
    state = create_game(human_id, deck_h, bot_id, deck_b, seed=bundle.get("seed"))
    for i, entry in enumerate(bundle.get("action_history", [])):
        state = apply(state, _match_recorded(legal_actions(state), entry, i))
    return state


def replay_steps(bundle: dict):
    """Re-drive a replay bundle, capturing a board snapshot per step so a UI can
    scrub forward/back.  Returns ``(human_id, steps)`` where ``steps[0]`` is the
    initial state and ``steps[i]`` is the state after the i-th recorded action,
    each as ``(PlayerView, events_delta, winner)`` from the human's perspective."""
    from swu.engine.actions import create_game
    deck_h = resolve_deck(bundle["human_deck"])
    deck_b = resolve_deck(bundle["bot_deck"])
    human_id = bundle.get("human_id", HUMAN_ID)
    bot_id = bundle.get("bot_id", BOT_ID)
    state = create_game(human_id, deck_h, bot_id, deck_b, seed=bundle.get("seed"))
    steps = [(state.view_for(human_id), [], state.winner)]
    for i, entry in enumerate(bundle.get("action_history", [])):
        before = len(state.event_log)
        state = apply(state, _match_recorded(legal_actions(state), entry, i))
        steps.append((state.view_for(human_id), list(state.event_log[before:]), state.winner))
    return human_id, steps


def _default_save_dir() -> Path:
    # .../src/swu/web/session.py -> parents[3] == .../swu-game
    return Path(__file__).resolve().parents[3] / "data" / "saves"


class SessionStore:
    """In-memory registry of live games, with file-based save/restore."""

    def __init__(self, save_dir: Path | None = None) -> None:
        self._sessions: dict[str, GameSession] = {}
        self.save_dir = save_dir or _default_save_dir()

    def create(
        self,
        human_deck: str,
        bot_deck: str,
        seed: int | None = None,
        difficulty: "Difficulty | str | None" = Difficulty.NORMAL,
    ) -> GameSession:
        from swu.engine.actions import create_game

        # Always pin a concrete seed.  A web game created with seed=None used to
        # let create_game draw fresh OS entropy that was never recorded, so the
        # exported replay bundle carried "seed": null and could not be
        # reproduced (re-driving it re-shuffled the decks and diverged on the
        # first hand-dependent action).  Generating the seed here — and storing
        # it on the session — makes every game's replay deterministic.
        if seed is None:
            seed = secrets.randbits(63)
        deck_h = resolve_deck(human_deck)
        deck_b = resolve_deck(bot_deck)
        state = create_game(HUMAN_ID, deck_h, BOT_ID, deck_b, seed=seed)
        diff = Difficulty.coerce(difficulty)
        bot_seed = seed + 9973
        # The factory is the single seam for opponent intelligence (Phase 6B
        # swaps in the LLM player here for NORMAL/HARD; EASY stays heuristic).
        bot = make_opponent(diff, player_id=BOT_ID, seed=bot_seed)
        game_id = uuid.uuid4().hex[:12]
        session = GameSession(
            game_id=game_id, state=state, bot=bot, difficulty=diff,
            seed=seed, human_deck=human_deck, bot_deck=bot_deck,
        )
        self._sessions[game_id] = session
        return session

    def get(self, game_id: str) -> GameSession:
        if game_id not in self._sessions:
            raise KeyError(game_id)
        return self._sessions[game_id]

    def delete(self, game_id: str) -> None:
        self._sessions.pop(game_id, None)

    # ── persistence ──────────────────────────────────────────────────────────

    def save(self, game_id: str, slot: str | None = None) -> Path:
        """Persist a live game to ``save_dir/<slot>.json`` (slot defaults to the
        game id).  The full GameState round-trips, so a mid-decision /
        mid-animation game restores exactly."""
        session = self.get(game_id)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        path = self.save_dir / f"{slot or game_id}.json"
        path.write_text(json.dumps(session.save_blob(), indent=2), encoding="utf-8")
        return path

    def list_saves(self) -> list[str]:
        if not self.save_dir.exists():
            return []
        return sorted(p.stem for p in self.save_dir.glob("*.json"))

    def load(self, slot: str) -> GameSession:
        """Restore a saved game into the live store and return it (new game id)."""
        path = self.save_dir / f"{slot}.json"
        if not path.exists():
            raise KeyError(slot)
        blob = json.loads(path.read_text(encoding="utf-8"))
        return self.restore(blob)

    def restore(self, blob: dict) -> GameSession:
        """Rebuild a live session from a save blob; the bot is recreated from the
        recorded difficulty/seed (its future choices need no saved RNG)."""
        state = GameState.from_json(blob["state"])
        diff = Difficulty.coerce(blob.get("difficulty"))
        seed = blob.get("seed")
        bot_seed = None if seed is None else (seed + 9973)
        bot = make_opponent(diff, player_id=blob.get("bot_id", BOT_ID), seed=bot_seed)
        game_id = uuid.uuid4().hex[:12]
        session = GameSession(
            game_id=game_id, state=state, bot=bot, difficulty=diff,
            human_id=blob.get("human_id", HUMAN_ID),
            bot_id=blob.get("bot_id", BOT_ID),
            seed=seed, human_deck=blob.get("human_deck", ""),
            bot_deck=blob.get("bot_deck", ""),
            action_history=list(blob.get("action_history", [])),
        )
        self._sessions[game_id] = session
        return session
