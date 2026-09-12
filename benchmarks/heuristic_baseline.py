# FROZEN BASELINE COPY of heuristic_bot.py as of the 2026-08-31 tuning session.
# Used ONLY by scripts/bot_arena.py to measure whether a change made the bot
# stronger.  Do not import from application code; do not edit.
"""
HeuristicBot — a transparent, weighted-heuristic opponent.

This is the strong, fast, debuggable bot that powers every difficulty in Phase
6A and that 6B's LLM player falls back to whenever the model fails.  It is a
pure function of the redacted ``PlayerView`` + the engine's fully-enumerated
``legal_actions`` + its own RNG.  It holds **no** hidden state and reads **no**
engine internals — everything it needs is in the view the engine already hands
it.  That is what makes it safe as both a playable opponent and an always-legal
fallback.

Design philosophy
-----------------
Not a search/minimax — a set of *named, weighted rules* (constants at the top of
this file).  Each turn the bot scores every legal action and plays the best one;
ties break on the bot's RNG.  Because the engine alternates initiative after
every action, the bot reasons one action at a time (there is no multi-attack
combo to plan within a single decision).

It must answer **every** decision the engine can present — main-phase actions,
mulligan, resourcing, target selection, triggers, trigger ordering, and every
pending-decision kind.  Anything it has no strong opinion on falls through to a
safe default (take a reasonable option / decline optional effects), and the
whole entry point is wrapped so it can **never raise** — a fallback that crashes
is worse than useless.

Rule summary (see the scoring constants and per-handler docstrings below):
* Resourcing/curve — resource the least useful card; keep an early curve.
* Playing cards — develop on-curve units valued by stat efficiency + keywords.
* Combat — take trades that come out ahead; chip / race the base otherwise;
  recognise and take lethal on the enemy base; Sentinel is enforced by the
  engine's legal-action enumeration.
* Leader — deploy once the threshold is met and it is worthwhile (not blindly
  round one).
* Mulligan — keep a playable early curve; mulligan air/clog.
* Targeting — spend effects on the highest-value legal target; decline optional
  effects that do not help.

Easy variant
------------
``mistake_rate`` > 0 makes the bot play a random legal action that fraction of
the time (and otherwise play its preferred line).  Tuned so a child can win a
fair share while the bot still does coherent things.  Selected by the factory
for the EASY difficulty; see ``swu.players.difficulty``.

``sharp_targeting`` (HARD) nudges target selection toward the biggest threat /
the unit it can actually finish, rather than merely the highest raw stat-line.
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from swu.engine.actions import Action
    from swu.engine.views import PlayerView, CardView


# ── Tuning weights (adjust here; documented intent each) ──────────────────────

# A win trumps everything else the bot could possibly do this action.
W_LETHAL = 1_000_000.0

# Developing board presence is the bot's bread and butter.
W_PLAY_UNIT = 50.0        # flat value of getting *a* unit onto the board
W_PLAY_EVENT = 40.0       # events (often removal) — played, but units edge them early
W_PLAY_UPGRADE = 18.0     # upgrades develop less board than a fresh body
W_DEPLOY_LEADER = 130.0   # a deployed leader is a premium body + ability
W_USE_ABILITY = 45.0      # activated abilities are usually worth it
W_ATTACK_BASE = 4.0       # per point of damage to the enemy base (racing/chip)
W_LEADER_BASE_ATTACK = 3.5  # per point — slightly under deploying the leader
W_TRADE_BASELINE = 8.0    # baseline appeal of a favourable unit attack
W_CLAIM_INITIATIVE = 2.0  # just above Pass — claim only when otherwise idle
W_PASS = 0.0

# Card-value model: power matters a touch more than HP; keywords add a premium.
V_POWER = 1.5
V_HP = 1.0
V_COST_CURVE = 1.2        # reward spending resources (bigger affordable = better)
KEYWORD_VALUE: dict[str, float] = {
    "Sentinel": 2.0, "Overwhelm": 2.0, "Raid": 2.0, "Shielded": 2.0,
    "Ambush": 1.5, "Grit": 1.0, "Restore": 1.0, "Saboteur": 1.0,
}
_DEFAULT_KEYWORD_VALUE = 0.5

# Combat: how strongly the stat-delta of a trade feeds the action score, and the
# minimum trade score the bot will accept (HARD accepts marginally worse trades).
TRADE_SCALE = 3.0
TRADE_THRESHOLD_NORMAL = 0.0
TRADE_THRESHOLD_HARD = -1.5
# Partial credit for chip damage that does not kill / counter damage we soak.
CHIP_GAIN = 0.30
CHIP_LOSS = 0.20

# Round before which deploying the leader is discounted (avoid blind turn-one).
LEADER_EARLY_ROUND = 2
LEADER_EARLY_FACTOR = 0.25

# Resourcing: keep cards we can deploy on an early curve.
RESOURCE_KEEP_COST = 3    # cost <= this is "on curve / keep-able" early


class HeuristicBot:
    """Weighted-heuristic ``Player``.  See module docstring for the rule set."""

    def __init__(
        self,
        player_id: str,
        seed: Optional[int] = None,
        *,
        rng: Optional[random.Random] = None,
        mistake_rate: float = 0.0,
        sharp_targeting: bool = False,
    ) -> None:
        self.player_id = player_id
        self._rng = rng if rng is not None else random.Random(seed)
        self.mistake_rate = max(0.0, min(1.0, mistake_rate))
        self.sharp_targeting = sharp_targeting

    # ── Player protocol ───────────────────────────────────────────────────

    def choose_action(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        """Return one element of ``legal``.  Never raises: any internal error
        falls back to a safe default so the bot is a bulletproof fallback."""
        if not legal:  # defensive — the engine guarantees this never happens
            raise ValueError("HeuristicBot.choose_action called with no legal actions")
        try:
            # Easy: a fraction of the time, just do something legal-but-random.
            if self.mistake_rate and self._rng.random() < self.mistake_rate:
                return self._random_mistake(view, legal)
            return self._preferred(view, legal)
        except Exception:
            return _safe_default(legal)

    def _random_mistake(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        """Easy's deliberate-blunder branch: play a *suboptimal but not
        self-destructive* legal action.

        Mistakes only happen at the strategic (main-phase) layer — picking a less
        useful card, a worse attack, deploying off-curve, etc.  Sub-decisions
        (target selection, damage distribution, modal choices) are *not*
        randomised: once committed to an action the bot still resolves it
        sensibly, so it never does something nonsensical like aiming its own
        Darth Vader damage at its own base.  Plays that would buff an opponent are
        also kept out of the random pool.
        """
        kinds = {type(a).__name__ for a in legal}
        if "Pass" not in kinds:
            # Not a free main-phase choice (it's a forced sub-decision) — resolve
            # it properly even when "making a mistake".
            return self._preferred(view, legal)
        idx = _card_index(view)
        pool = [a for a in legal if not _is_enemy_buff(a, idx)]
        return self._rng.choice(pool or legal)

    def observe(self, state: object, action: object, actor_id: str) -> None:
        pass

    # ── Top-level dispatch ────────────────────────────────────────────────

    def _preferred(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        kinds = {type(a).__name__ for a in legal}

        # Main ACTION phase is the only context that offers Pass.
        if "Pass" in kinds:
            return self._choose_main_phase(view, legal)

        # Setup / regroup resourcing.
        if "KeepHand" in kinds:
            return self._choose_mulligan(view, legal)
        if "ResourceCard" in kinds:
            return self._choose_resource(view, legal, regroup="SkipResource" in kinds)

        # Pending-decision handlers (each keyed on the action types present).
        if "UseAmbush" in kinds or kinds == {"DeclineAmbush"}:
            return self._choose_ambush(view, legal)
        if "ExploitCommit" in kinds or "ExploitSacrifice" in kinds:
            return self._choose_exploit(view, legal)
        if "AcceptTrigger" in kinds:
            # Optional triggers usually help — accept, *unless* the trigger could
            # only be aimed at our own cards (e.g. Darth Vader's "deal 2 to a unit"
            # with no enemy unit on the board), in which case decline.
            ctx = _top_context(view)
            if _ability_forces_self_harm(
                ctx.get("set_code", "") or "", ctx.get("card_number", "") or "",
                int(ctx.get("ability_idx", 0) or 0), ctx.get("source_id"), view,
            ):
                return self._first(legal, "DeclineTrigger")
            return self._first(legal, "AcceptTrigger")
        if {"ChooseTarget", "DeclineTarget", "AutoResolveEffects"} & kinds:
            return self._choose_resolve_effects(view, legal)
        if "PlayFromHand" in kinds:
            return self._choose_play_from_hand(view, legal)
        if "ReadyUnit" in kinds or kinds == {"DeclineReadyUnit"}:
            return self._choose_ready_unit(view, legal)
        if "AllowEffect" in kinds or "SayNo" in kinds:
            return self._choose_say_no(view, legal)
        if "PayRegroupUpkeep" in kinds or "ReturnRegroupUpkeepUnit" in kinds:
            return self._choose_regroup_upkeep(view, legal)
        if "PayToAvoidExhaust" in kinds or "AcceptExhaust" in kinds:
            return self._choose_pay_or_exhaust(view, legal)
        if {"AssignDamage", "ChooseDamageTarget", "ChooseDamageSource",
                "FinishDamageDistribution"} & kinds:
            return self._choose_distribute_damage(view, legal)
        if "SelectSearchCard" in kinds or "FinishSearch" in kinds:
            return self._choose_deck_search(view, legal)
        if {"KeepTopCard", "BottomTopCard", "DrawTopCard"} & kinds:
            return self._choose_peek_top(view, legal)
        if "ChooseNumber" in kinds:
            return self._choose_number(view, legal)
        if "ChooseModalOption" in kinds or "ChooseModalTarget" in kinds:
            return self._choose_modal(view, legal)
        if "ChooseWookieeMode" in kinds or "ChooseWookieeReadyUnit" in kinds:
            return self._choose_let_wookiee_win(view, legal)
        if "SelectModalOption" in kinds:
            return self._choose_two_modal(view, legal)
        if "SacrificeResource" in kinds or "ChooseSacrificeTarget" in kinds:
            return self._choose_sacrifice_resource(view, legal)
        if "RevealResourceForRamp" in kinds:
            return self._choose_reveal_resource_ramp(view, legal)
        if "ChoosePreventionSacrifice" in kinds or "DeclineCombatPrevention" in kinds:
            # Conservatively decline — never trade away a friendly unit to prevent
            # combat damage (the safe "don't self-harm" default; Amidala SEC_101).
            return self._first(legal, "DeclineCombatPrevention")
        if ("SelectDiscardUnitForDamage" in kinds
                or "ChooseDiscardDamageTarget" in kinds):
            return self._choose_discard_unit_damage(view, legal)
        if {"SelectCullCard", "FinishCull", "ChooseCullDamageTarget"} & kinds:
            return self._choose_cull_for_damage(view, legal)
        if "DiscardForSearch" in kinds:
            return self._choose_discard_for_search(view, legal)
        if {"SelectRecurUnit", "FinishRecur", "SelectBuffTarget",
                "FinishRecurBuff"} & kinds:
            return self._choose_recur_and_buff(view, legal)
        if {"ChooseOwnTarget", "ConfirmOpponentDamage", "DeclineOpponentDamage"} & kinds:
            return self._choose_opponent_chooses_target(view, legal)
        if {"SelectSplitBounceUnit", "FinishSplitBounce", "ChooseSplitReturn"} & kinds:
            return self._choose_opponent_split_bounce(view, legal)
        if "ChooseUnitToDefeat" in kinds:
            return self._choose_unit_to_defeat(view, legal)
        if "NameCard" in kinds:
            return self._choose_name_a_card(view, legal)
        if "ChooseCaptureVictim" in kinds or "DeclineCaptureVictim" in kinds:
            return self._choose_capture_or_ready(view, legal)
        if "ChooseUnitToSpare" in kinds:
            return self._choose_unit_to_spare(view, legal)
        if "KeepUniqueCopy" in kinds:
            return self._choose_keep_unique_copy(view, legal)
        if "SelectTokenTarget" in kinds or "FinishSelectToken" in kinds:
            return self._choose_select_token(view, legal)
        if "SelectDamageTarget" in kinds or "FinishSelectDamage" in kinds:
            return self._choose_select_damage(view, legal)
        if "AssignIndirectDamage" in kinds:
            return self._choose_assign_indirect_damage(view, legal)
        if "SelectDiscardCard" in kinds or "FinishReturnFromDiscard" in kinds:
            return self._choose_return_from_discard(view, legal)
        if "SelectBottomDiscardCard" in kinds or "FinishBottomFromDiscard" in kinds:
            return self._choose_bottom_from_discard(view, legal)
        if "SelectDistinctDiscardCard" in kinds:
            return self._choose_distinct_discard(view, legal)
        if "SelectHandCardToBottom" in kinds:
            return self._choose_bottom_from_hand(view, legal)
        if "SelectHandCardToResource" in kinds:
            return self._choose_resource_from_hand(view, legal)
        if "DiscloseSelectCard" in kinds or "DeclineDisclose" in kinds:
            return self._choose_disclose(view, legal)
        if "DiscardRandomCard" in kinds or "DeclineDiscard" in kinds:
            return self._choose_may_discard(view, legal)
        if ("SelectDiscardForExperience" in kinds
                or "DeclineDiscardForExperience" in kinds):
            # Echo SHD_99 "you may discard a card from your hand" — conservatively
            # decline (never spend a card from hand on the heuristic path).
            return self._first(legal, "DeclineDiscardForExperience")
        if "SelectUnitToExhaust" in kinds or "FinishExhaustForBaseDamage" in kinds:
            return self._choose_exhaust_for_base_damage(view, legal)
        if ("SelectUnitToExhaustCombined" in kinds
                or "FinishExhaustCombined" in kinds):
            return self._choose_exhaust_combined(view, legal)
        if ("SelectUnitToCaptureCombined" in kinds
                or "FinishCaptureCombined" in kinds):
            return self._choose_capture_combined(view, legal)
        if "RescueGuardedCard" in kinds or "DeclineRescue" in kinds:
            # Cad Bane TWI_187: rescuing your captured card hands its captor's
            # controller two fresh cards — a net card-economy loss.  Decline, the
            # same conservative default as the other "may help the opponent" offers.
            return self._first(legal, "DeclineRescue")
        if "CaptureWithUnit" in kinds or "FinishMultiCapture" in kinds:
            return self._choose_multi_capture(view, legal)
        if ("SelectCombinedPowerUnit" in kinds
                or "FinishCombinedPowerPlay" in kinds):
            return self._choose_combined_power_play(view, legal)
        if "SelectCapturedToPlay" in kinds or "DeclineCapturedPlay" in kinds:
            return self._choose_play_captured(view, legal)
        if "SelectResourceUnitToPlay" in kinds or "DeclineResourceUnitPlay" in kinds:
            return self._choose_play_resource_units(view, legal)
        if "CullRevealedCard" in kinds or "DrawRevealedCard" in kinds:
            return self._choose_reveal_cull_draw(view, legal)
        if "PayResourceForToken" in kinds or "FinishPayResources" in kinds:
            return self._choose_pay_resources_for_tokens(view, legal)
        if "DealExploitDamage" in kinds or "DeclineExploitDamage" in kinds:
            return self._choose_per_exploit_damage(view, legal)
        if ({"UseForceOption", "DeclineUseForce", "ChooseUseForcePayoffTarget"}
                & kinds):
            return self._choose_use_force(view, legal)
        if "ReplayReturnedUnit" in kinds or "DeclineReplay" in kinds:
            return self._choose_owner_may_replay(view, legal)
        if "PutOnDeckTop" in kinds or "PutOnDeckBottom" in kinds:
            return self._choose_put_on_deck(view, legal)
        if {"MoveUpgradeSelect", "DeclineMoveUpgrade", "MoveUpgradeTo"} & kinds:
            return self._choose_move_upgrade(view, legal)
        if {"AttachSelfAsPilot", "DeclineAttachSelfAsPilot"} & kinds:
            return self._first(legal, "DeclineAttachSelfAsPilot")
        if {"PlayUpgradeFromHand", "DeclinePlayUpgradeFromHand"} & kinds:
            # Re-playing a returned upgrade for free has no reliable heuristic
            # value (host choice / enemy-attach ambiguity) — decline, consistent
            # with the move_upgrade / pilot_self_attach conservative default.
            return self._first(legal, "DeclinePlayUpgradeFromHand")
        if "PlotPlay" in kinds or "FinishPlot" in kinds:
            return self._choose_plot(view, legal)
        if ({"ChooseRevealDeck", "ChooseRevealPlayer", "PlayRevealedCard",
             "DeclineRevealedCard", "ChooseRevealHost"} & kinds):
            return self._choose_reveal_play_credit(view, legal)
        if "RevealNextCard" in kinds or "StopRevealing" in kinds:
            return self._choose_reveal_cost_damage(view, legal)
        if "KeepRevealed" in kinds or "DiscardRevealed" in kinds:
            # For a Cause I Believe In (SOR_152): keep every revealed card on top
            # (never throw away cards) — pick the first KeepRevealed each step.
            return self._first(legal, "KeepRevealed")
        if "DeclineGrantedAttack" in kinds or "AttackWithUnit" in kinds:
            return self._choose_granted_attack(view, legal)
        if "ContinueAttack" in kinds:
            return legal[0]  # only ever one continuation

        return _safe_default(legal)

    # ── Mulligan ──────────────────────────────────────────────────────────

    def _choose_mulligan(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        """Keep a hand with a playable early curve; mulligan air/clog.

        Heuristic: a hand is keepable if it has at least two cards castable in
        the first couple of rounds (cost <= RESOURCE_KEEP_COST), at least one of
        which is a unit (we need a body to develop).
        """
        hand = view.my.hand
        cheap = [c for c in hand if c.cost <= RESOURCE_KEEP_COST]
        cheap_units = [c for c in cheap if c.card_type == "Unit"]
        keep = len(cheap) >= 2 and len(cheap_units) >= 1
        return self._first(legal, "KeepHand" if keep else "TakeMultiligan")

    # ── Resourcing ────────────────────────────────────────────────────────

    def _choose_resource(
        self, view: "PlayerView", legal: list["Action"], *, regroup: bool
    ) -> "Action":
        """Resource the *least useful* card in hand.

        Usefulness favours cheap units we can deploy on curve; the least useful
        card is typically the most expensive or a non-unit we cannot play soon.
        During regroup we keep the last card in hand (skip) rather than empty
        the hand entirely.
        """
        resource_acts = [a for a in legal if type(a).__name__ == "ResourceCard"]
        skip = next((a for a in legal if type(a).__name__ == "SkipResource"), None)

        if regroup and skip is not None and len(view.my.hand) <= 1:
            return skip

        hand_by_id = {c.instance_id: c for c in view.my.hand}

        def keep_value(act: "Action") -> float:
            cv = hand_by_id.get(getattr(act, "instance_id", None))
            if cv is None:
                return 0.0
            v = 0.0
            if cv.card_type == "Unit":
                v += 6.0                       # prefer keeping bodies
            v += max(0, RESOURCE_KEEP_COST + 1 - cv.cost) * 1.5  # cheap = keep
            v += _card_value(cv) * 0.1
            return v

        # Resource the card with the *lowest* keep value.
        return min(resource_acts, key=keep_value)

    # ── Main ACTION phase ─────────────────────────────────────────────────

    def _choose_main_phase(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        """Score every legal main-phase action and play the best one.

        Action families and intent:
          * PlayCard  — develop on-curve units; play events/upgrades at lower
            priority.
          * AttackWithUnit — take favourable trades; otherwise chip/race the
            base; take lethal immediately.
          * DeployLeader — premium body once the threshold is met (discounted
            round one).
          * AttackWithLeader — chip the base with the undeployed leader side.
          * UseAbility — usually worthwhile; the target choice resolves later.
          * ClaimInitiative — only when otherwise idle (it ends our turn).
          * Pass — the floor.
        """
        idx = _card_index(view)
        base_remaining = _enemy_base_remaining(view)

        best = legal[0]
        best_score = float("-inf")
        for a in legal:
            score = self._score_main_action(a, view, idx, base_remaining)
            # RNG tiebreak keeps play varied and avoids deterministic ruts.
            if score > best_score or (score == best_score and self._rng.random() < 0.5):
                best, best_score = a, score
        return best

    def _score_main_action(
        self, a: "Action", view: "PlayerView", idx: dict, base_remaining: int
    ) -> float:
        kind = type(a).__name__

        if kind == "Pass":
            return W_PASS
        if kind == "ClaimInitiative":
            return W_CLAIM_INITIATIVE
        if kind == "DeployLeader":
            score = W_DEPLOY_LEADER
            if view.round_number < LEADER_EARLY_ROUND:
                score *= LEADER_EARLY_FACTOR
            return score
        if kind == "DeployLeaderAsUpgrade":
            # Boba Fett JTL_9's alternate deploy: fold the leader onto a Vehicle
            # (making it a leader unit + dealing up to 4).  Value it just below the
            # normal deploy so the bot has a reason to use it when it has a Vehicle,
            # but prefers a clean deploy by default.
            return W_DEPLOY_LEADER * 0.9
        if kind == "AttackWithLeader":
            leader = _my_undeployed_leader(view)
            power = leader.effective_power if leader else 0
            if base_remaining > 0 and power >= base_remaining:
                return W_LETHAL
            return W_LEADER_BASE_ATTACK * power
        if kind == "UseAbility":
            src_id = getattr(a, "source_id", None)
            src = idx.get(src_id, (None, None))[0]
            if src is not None:
                sc = getattr(src, "set_code", "") or ""
                cn = getattr(src, "card_number", "") or ""
                aidx = int(getattr(a, "ability_idx", 0) or 0)
                # Refuse (score below Pass) an ability that, right now, would only
                # force self-harm OR pay a tangible cost for no effect at all.
                if (_ability_forces_self_harm(sc, cn, aidx, src_id, view)
                        or _ability_is_pointless(sc, cn, aidx, src_id, view)):
                    return W_PASS - 1.0
            return W_USE_ABILITY
        if kind == "PlayCard":
            return self._score_play_card(a, idx)
        if kind == "PlayFromDiscard":
            # Replay a card from the discard pile (Brutal Traditions SHD_38) —
            # value it exactly like a hand play of the same card (host/beneficial
            # logic applies identically via instance_id / upgrade_target_id).
            return self._score_play_card(a, idx)
        if kind == "AttackWithUnit":
            return self._score_attack(a, idx, base_remaining)
        if kind == "AttackTwoUnits":
            return self._score_two_unit_attack(a, idx)
        return 0.0

    def _score_play_card(self, a: "Action", idx: dict) -> float:
        cv = idx.get(getattr(a, "instance_id", None), (None, None))[0]
        if cv is None:
            return W_PLAY_EVENT
        if cv.card_type == "Unit":
            return W_PLAY_UNIT + _card_value(cv) + cv.cost * V_COST_CURVE
        if cv.card_type == "Upgrade":
            # Value the unit we are upgrading: better hosts are better targets.
            host, host_side = idx.get(getattr(a, "upgrade_target_id", None), (None, None))
            host_bonus = _card_value(host) * 0.2 if host else 0.0
            # A Bounty upgrade pays off when its host is *defeated* (the opponent
            # of the host's controller collects it), so it has the inverse value
            # of a buff: it belongs on an ENEMY unit — ideally a high-value one —
            # and is wasted (or self-harming) on a friendly.  Reward an enemy host
            # and refuse a friendly one (or a host we can't resolve as enemy).
            if _upgrade_grants_bounty(getattr(cv, "set_code", "") or "",
                                      getattr(cv, "card_number", "") or ""):
                if host is None or host_side != "opp":
                    return W_PASS - 1.0
                return W_PLAY_UPGRADE + cv.cost * 0.5 + host_bonus
            # Never buff an opponent's unit.  A net-positive upgrade attached to an
            # enemy is a blunder even the Easy bot should not make; score it below
            # Pass so the bot holds the upgrade instead.  Net-neutral/downside
            # upgrades (e.g. an ability-granting upgrade with no stat gain) stay
            # playable on a friendly — that is their intended host.
            if host is not None and host_side == "opp" and _is_beneficial_upgrade(cv):
                return W_PASS - 1.0
            return W_PLAY_UPGRADE + cv.cost * 0.5 + host_bonus
        # Events (and anything else): moderate; the target resolves later.
        return W_PLAY_EVENT + cv.cost * 0.5

    def _score_attack(self, a: "Action", idx: dict, base_remaining: int) -> float:
        attacker = idx.get(getattr(a, "attacker_id", None), (None, None))[0]
        defender_id = getattr(a, "defender_id", None)
        if attacker is None:
            return 0.0

        if defender_id is None:  # base attack
            if base_remaining > 0 and attacker.effective_power >= base_remaining:
                return W_LETHAL
            return W_ATTACK_BASE * attacker.effective_power

        defender = idx.get(defender_id, (None, None))[0]
        if defender is None:
            return 0.0
        gain, loss = _trade_outcome(attacker, defender)
        threshold = (
            TRADE_THRESHOLD_HARD if self.sharp_targeting else TRADE_THRESHOLD_NORMAL
        )
        delta = gain - loss
        if delta < threshold:
            # A clearly losing trade — worth less than chipping the base.
            return W_ATTACK_BASE * attacker.effective_power - 1.0 + delta
        return W_TRADE_BASELINE + delta * TRADE_SCALE

    def _score_two_unit_attack(self, a: "Action", idx: dict) -> float:
        """Score Darth Maul C24_6's "attack 2 units" (AttackTwoUnits): the attacker
        deals its power to BOTH defenders and takes the SUM of their power back.  The
        gain is the two per-defender trade gains; the loss is a single combined hit."""
        attacker = idx.get(getattr(a, "attacker_id", None), (None, None))[0]
        d1 = idx.get(getattr(a, "defender1_id", None), (None, None))[0]
        d2 = idx.get(getattr(a, "defender2_id", None), (None, None))[0]
        if attacker is None or d1 is None or d2 is None:
            return 0.0
        gain = 0.0
        for d in (d1, d2):
            g, _ = _trade_outcome(attacker, d)
            gain += g
        incoming = 0 if _has_shield(attacker) else (
            d1.effective_power + d2.effective_power)
        atk_rem = _remaining_hp(attacker)
        loss = (_card_value(attacker) if (incoming >= atk_rem and atk_rem > 0)
                else CHIP_LOSS * _card_value(attacker) * (incoming / max(1, atk_rem)))
        return W_TRADE_BASELINE + (gain - loss) * TRADE_SCALE

    # ── Pending-decision handlers ─────────────────────────────────────────

    def _choose_ambush(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        """Ambush: attack now only if a favourable trade exists, else decline."""
        idx = _card_index(view)
        decline = next((a for a in legal if type(a).__name__ == "DeclineAmbush"), None)
        best, best_delta = None, float("-inf")
        for a in legal:
            if type(a).__name__ != "UseAmbush":
                continue
            attacker = idx.get(a.attacker_id, (None, None))[0]
            defender = idx.get(a.target_id, (None, None))[0]
            if attacker is None or defender is None:
                continue
            gain, loss = _trade_outcome(attacker, defender)
            delta = gain - loss
            if delta > best_delta:
                best, best_delta = a, delta
        threshold = TRADE_THRESHOLD_HARD if self.sharp_targeting else TRADE_THRESHOLD_NORMAL
        if best is not None and best_delta >= threshold:
            return best
        return decline or (best or legal[0])

    def _choose_exploit(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        """Exploit: keep the board — commit without sacrificing whenever the
        engine still offers a commit (it only offers one we can afford).  If
        forced to sacrifice, give up the least valuable unit."""
        commit = next((a for a in legal if type(a).__name__ == "ExploitCommit"), None)
        if commit is not None:
            return commit
        idx = _card_index(view)
        sac = [a for a in legal if type(a).__name__ == "ExploitSacrifice"]
        if not sac:
            return legal[0]
        return min(
            sac, key=lambda a: _card_value(idx.get(a.unit_id, (None, None))[0])
        )

    def _choose_resolve_effects(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Spend an effect on the highest-value legal target.

        Without the effect's semantics in hand, the bot infers intent from the
        targets offered: when enemy targets are available the effect is almost
        always harmful, so it hits the most valuable / most threatening enemy;
        when only friendly targets exist the effect is beneficial, so it picks
        the most-damaged unit (heal) or the best unit (buff).  Optional effects
        with no useful target are declined.
        """
        auto = next((a for a in legal if type(a).__name__ == "AutoResolveEffects"), None)
        if auto is not None:
            return auto
        decline = next((a for a in legal if type(a).__name__ == "DeclineTarget"), None)
        choices = [a for a in legal if type(a).__name__ == "ChooseTarget"]
        if not choices:
            return decline or legal[0]

        idx = _card_index(view)
        resolved = [(a, idx.get(a.target_id, (None, None))) for a in choices]
        enemy_choices = [(a, cv) for a, (cv, side) in resolved
                         if side == "opp" and cv is not None]
        friendly_choices = [(a, cv) for a, (cv, side) in resolved
                            if side == "my" and cv is not None]

        if enemy_choices:
            if self.sharp_targeting:
                # Prefer the biggest threat we could remove (high power, low HP).
                key = lambda t: (t[1].effective_power, -_remaining_hp(t[1]))
            else:
                key = lambda t: _card_value(t[1])
            return max(enemy_choices, key=key)[0]
        if friendly_choices:
            damaged = [(a, cv) for a, cv in friendly_choices if cv.damage > 0]
            if damaged:
                return max(damaged, key=lambda t: t[1].damage)[0]
            return max(friendly_choices, key=lambda t: _card_value(t[1]))[0]
        # Targets we couldn't resolve in the view — just take the first.
        return choices[0]

    def _choose_play_from_hand(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Play the strongest eligible unit from hand (it enters ready)."""
        idx = _card_index(view)
        plays = [a for a in legal if type(a).__name__ == "PlayFromHand"]
        if not plays:
            return legal[0]
        return max(plays, key=lambda a: _card_value(idx.get(a.instance_id, (None, None))[0]))

    def _choose_ready_unit(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        """"May ready a unit" — ready the most valuable exhausted unit."""
        idx = _card_index(view)
        ready = [a for a in legal if type(a).__name__ == "ReadyUnit"]
        if not ready:
            return legal[0]
        return max(ready, key=lambda a: _card_value(idx.get(a.instance_id, (None, None))[0]))

    def _choose_say_no(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        """Opponent targets our unit for N damage unless we say 'no' (they then
        draw cards).  Say 'no' to save a valuable unit that would die; otherwise
        allow the hit rather than hand the opponent cards."""
        allow = next((a for a in legal if type(a).__name__ == "AllowEffect"), None)
        say_no = next((a for a in legal if type(a).__name__ == "SayNo"), None)
        ctx = _top_context(view)
        target_id = ctx.get("target_id")
        damage = int(ctx.get("damage", 0) or 0)
        idx = _card_index(view)
        cv = idx.get(target_id, (None, None))[0]
        if cv is not None and say_no is not None:
            dies = damage >= _remaining_hp(cv)
            if dies and _card_value(cv) >= 6.0:
                return say_no
        return allow or say_no or legal[0]

    def _choose_regroup_upkeep(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Millennium Falcon SOR_193: pay 1 resource to keep the unit if we can
        (a strong ready 3/4 is worth one resource), else return it to hand."""
        pay = next((a for a in legal
                    if type(a).__name__ == "PayRegroupUpkeep"), None)
        ret = next((a for a in legal
                    if type(a).__name__ == "ReturnRegroupUpkeepUnit"), None)
        return pay or ret or legal[0]

    def _choose_pay_or_exhaust(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """The Eye of Aldhani SEC_73: for each of our units, pay 1 resource or let it
        be exhausted.  Defending costs resources (tempo we usually want for plays), so
        pay to keep a unit ready only with a comfortable ready-resource surplus; else
        let it exhaust.  AcceptExhaust is always offered, so this never crashes."""
        pay = next((a for a in legal
                    if type(a).__name__ == "PayToAvoidExhaust"), None)
        accept = next((a for a in legal
                       if type(a).__name__ == "AcceptExhaust"), None)
        if pay is not None:
            ready = sum(1 for r in getattr(view.my, "resources", [])
                        if not getattr(r, "exhausted", True))
            if ready >= 4:      # only spend on defence with resources to spare
                return pay
        return accept or pay or legal[0]

    def _choose_distribute_damage(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Player-directed damage: concentrate on enemies we can finish.

        AssignDamage spends one point; ChooseDamageTarget picks the single
        victim; ChooseDamageSource picks a dealing unit.  We do not have the
        effect's full bookkeeping in the view, so we pick sensibly and lean on
        the engine for legality.
        """
        idx = _card_index(view)
        ctx = _top_context(view)
        alloc = ctx.get("alloc", {}) if isinstance(ctx, dict) else {}

        assigns = [a for a in legal if type(a).__name__ == "AssignDamage"]
        finish = next((a for a in legal
                       if type(a).__name__ == "FinishDamageDistribution"), None)
        if assigns:
            # Never dump distributed damage on our own units — when the target set
            # is "any" (Boba Fett JTL_9's "up to 4 among any number of units"),
            # restrict to enemy units; if none worth hitting and we may stop early,
            # finish rather than damage ourselves.
            enemy_assigns = [a for a in assigns
                             if idx.get(a.target_id, (None, None))[1] == "opp"]
            pool = enemy_assigns or ([] if finish is not None else assigns)
            if pool:
                # Target the enemy needing the fewest *additional* points to die.
                def need(a: "Action") -> float:
                    cv = idx.get(a.target_id, (None, None))[0]
                    if cv is None:
                        return 1e9
                    rem = _remaining_hp(cv) - int(alloc.get(a.target_id, 0))
                    return rem if rem > 0 else 1e6  # already lethal → deprioritise
                return min(pool, key=need)
        if finish is not None:
            return finish

        ctgt = [a for a in legal if type(a).__name__ == "ChooseDamageTarget"]
        if ctgt:
            return max(ctgt, key=lambda a: _card_value(idx.get(a.target_id, (None, None))[0]))

        csrc = [a for a in legal if type(a).__name__ == "ChooseDamageSource"]
        if csrc:
            return max(csrc, key=lambda a: _card_value(idx.get(a.unit_id, (None, None))[0]))

        return legal[0]

    def _choose_deck_search(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        """Searched deck cards are not in the view; taking cards is card
        advantage, so select one whenever offered (the engine auto-finishes at
        the cap), else finish."""
        select = next((a for a in legal if type(a).__name__ == "SelectSearchCard"), None)
        return select or legal[0]

    def _choose_return_from_discard(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        """Returning a card from the discard pile to hand is pure card advantage,
        so take one whenever offered (the engine auto-finishes at the cap), else
        finish (Razor Crest SHD_44)."""
        select = next((a for a in legal if type(a).__name__ == "SelectDiscardCard"), None)
        return select or legal[0]

    def _choose_distinct_discard(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        """Doctor Aphra SHD_15 deploy: keep picking differently-named discard cards
        (the engine auto-finishes at the required count and returns one at random).
        Any legal pick advances the forced selection — pure upside, so grab one."""
        return self._first(legal, "SelectDistinctDiscardCard")

    def _choose_bottom_from_discard(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        """Restock SOR_252 ("choose up to 4 cards in a discard pile, bottom them"):
        a niche deck-order tool.  The safe heuristic is to bottom nothing — finishing
        never risks recycling our own useful discard back under the deck."""
        return next((a for a in legal
                     if type(a).__name__ == "FinishBottomFromDiscard"), legal[0])

    def _choose_bottom_from_hand(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        """Forced "put N cards from hand on the bottom of your deck" (Private
        Manufacturing TWI_257): bottom the highest-cost card we're holding (the
        least immediately castable), keeping cheaper, more flexible cards in hand."""
        idx = _card_index(view)
        acts = [a for a in legal if type(a).__name__ == "SelectHandCardToBottom"]
        if not acts:
            return legal[0]

        def _cost(a: "Action") -> int:
            cv, _ = idx.get(getattr(a, "instance_id", None), (None, None))
            return int(getattr(cv, "cost", 0)) if cv is not None else 0

        return max(acts, key=_cost)

    def _choose_resource_from_hand(self, view: "PlayerView",
                                   legal: list["Action"]) -> "Action":
        """"You may resource a card from your hand and ready it" (Sundari Palace
        TS26_12).  Ramp is worth a card only while the hand is deep enough to spare
        one, and each card resourced also schedules a resource defeat at regroup —
        so resource the HIGHEST-COST card (the least immediately castable, the
        bottom_from_hand reading) while holding 4+ cards, and otherwise stop."""
        idx = _card_index(view)
        acts = [a for a in legal if type(a).__name__ == "SelectHandCardToResource"]
        finish = next((a for a in legal
                       if type(a).__name__ == "FinishResourceFromHand"), None)
        if not acts or (finish is not None and len(acts) < 4):
            return finish if finish is not None else legal[0]

        def _cost(a: "Action") -> int:
            cv, _ = idx.get(getattr(a, "instance_id", None), (None, None))
            return int(getattr(cv, "cost", 0)) if cv is not None else 0

        return max(acts, key=_cost)

    def _choose_disclose(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        """Karis Nemik SEC_148 / Syril Karn SEC_133: "You may disclose <aspects>.
        If you do, <upside>."  The payoff is always beneficial (a Spy token, enemy
        damage) and revealing hand cards is only a minor info leak, so disclose
        greedily — take the first offered reveal each step (the branch offers only
        cards contributing a still-needed aspect, so each pick makes progress and
        the payoff auto-resolves once covered)."""
        select = next((a for a in legal
                       if type(a).__name__ == "DiscloseSelectCard"), None)
        if select is not None:
            return select
        return self._first(legal, "DeclineDisclose")

    def _choose_may_discard(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        """Political Pressure TWI_222: as the targeted opponent, discard a random
        card to deny the controller 2 Battle Droid tokens, or decline and keep the
        card.  Heuristic: a card costs us a known resource; two 1/1 tokens are only
        a modest board swing, so we only pay a card when we are flush with options
        (a deep hand can spare one), otherwise we keep the card."""
        discard = next((a for a in legal
                        if type(a).__name__ == "DiscardRandomCard"), None)
        decline = next((a for a in legal
                        if type(a).__name__ == "DeclineDiscard"), None)
        if discard is not None and len(view.my.hand) >= 4:
            return discard
        return decline if decline is not None else _safe_default(legal)

    def _choose_exhaust_for_base_damage(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """The Invisible Hand TWI_234: exhaust any number of friendly units to deal
        1 base damage each.  Exhausting a unit costs it its turn (attack/block), so
        we only spend the expendable ones — token units (the Battle Droids this deck
        churns out) — for free base chip, then finish.  Never exhausts a real unit
        we might want for combat."""
        idx = _card_index(view)
        selects = [a for a in legal if type(a).__name__ == "SelectUnitToExhaust"]
        for a in selects:
            cv, _ = idx.get(a.target_id, (None, None))
            if cv is not None and getattr(cv, "card_type", "") == "Token Unit":
                return a
        return self._first(legal, "FinishExhaustForBaseDamage")

    def _choose_exhaust_combined(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Qui-Gon Jinn's Lightsaber LOF_201: exhaust any number of units (any
        controller) with combined cost ≤ 6.  Only ENEMY units are worth exhausting
        (it denies them an attack/block); exhausting our own units is self-harm, so
        we never do it.  Spend the budget on the most expensive enemy units first,
        then finish."""
        idx = _card_index(view)
        selects = [a for a in legal
                   if type(a).__name__ == "SelectUnitToExhaustCombined"]
        enemy = []
        for a in selects:
            cv, side = idx.get(a.target_id, (None, None))
            if cv is not None and side == "opp":
                enemy.append((a, getattr(cv, "cost", 0) or 0))
        if enemy:
            enemy.sort(key=lambda t: t[1], reverse=True)
            return enemy[0][0]
        return self._first(legal, "FinishExhaustCombined")

    def _choose_capture_combined(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Dismantle the Conspiracy SEC_106: capture any number of enemy non-leader
        units with combined remaining HP ≤ 7.  Capturing removes an enemy unit from
        play (pure upside), so greedily capture the most valuable enemy unit that
        still fits the budget, then finish."""
        idx = _card_index(view)
        selects = [a for a in legal
                   if type(a).__name__ == "SelectUnitToCaptureCombined"]
        enemy = []
        for a in selects:
            cv, _side = idx.get(a.target_id, (None, None))
            enemy.append((a, getattr(cv, "cost", 0) or 0 if cv is not None else 0))
        if enemy:
            enemy.sort(key=lambda t: t[1], reverse=True)
            return enemy[0][0]
        return self._first(legal, "FinishCaptureCombined")

    def _choose_multi_capture(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Finalizer SHD_92: choose any number of friendly units, each captures an
        enemy non-leader unit in the same arena.  Capturing removes an enemy unit
        from play (pure upside), so greedily capture the most valuable enemy prey
        available, then finish (each pick auto-marks its captor used)."""
        idx = _card_index(view)
        pairs = [a for a in legal if type(a).__name__ == "CaptureWithUnit"]
        if pairs:
            def prey_value(a: "Action") -> float:
                cv, _side = idx.get(a.prey_id, (None, None))
                return getattr(cv, "cost", 0) or 0 if cv is not None else 0
            pairs.sort(key=prey_value, reverse=True)
            return pairs[0]
        return self._first(legal, "FinishMultiCapture")

    def _choose_combined_power_play(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Consolidation of Power TWI_89: every unit added to the pool is a unit
        that will be DEFEATED, so the heuristic path never feeds it — finish
        immediately (the conservative "don't self-harm" stance the bot takes with
        every other sacrifice decision)."""
        return self._first(legal, "FinishCombinedPowerPlay")

    def _choose_play_captured(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Dryden Vos SHD_192: play a captured card for free under your control.
        Free board presence is pure upside, so play the highest-cost captured unit;
        decline only if nothing is offered."""
        idx = _card_index(view)
        picks = [a for a in legal if type(a).__name__ == "SelectCapturedToPlay"]
        if picks:
            def value(a: "Action") -> float:
                cv, _side = idx.get(a.instance_id, (None, None))
                return getattr(cv, "cost", 0) or 0 if cv is not None else 0
            picks.sort(key=value, reverse=True)
            return picks[0]
        return self._first(legal, "DeclineCapturedPlay")

    def _choose_reveal_cull_draw(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Admiral Trench JTL_14: an opponent discards 2 of 4 revealed cards, then the
        controller draws 1 of the survivors.  Both seats want the same ranking for
        opposite reasons — deny the most expensive card, keep the most expensive
        survivor — so both stages pick the highest cost on offer."""
        idx = _card_index(view)

        def value(a: "Action") -> float:
            cv, _side = idx.get(a.instance_id, (None, None))
            return (getattr(cv, "cost", 0) or 0) if cv is not None else 0

        picks = [a for a in legal
                 if type(a).__name__ in ("CullRevealedCard", "DrawRevealedCard")]
        if picks:
            picks.sort(key=value, reverse=True)
            return picks[0]
        return legal[0]

    def _choose_play_resource_units(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Endless Legions SHD_109: reveal resources and play each revealed unit for
        free.  Free board presence off a 14-cost finisher is the whole point, so play
        the highest-cost offered unit-resource each loop iteration (the loop re-offers
        the rest until they are all out); stop only when nothing is left."""
        idx = _card_index(view)
        picks = [a for a in legal if type(a).__name__ == "SelectResourceUnitToPlay"]
        if picks:
            def value(a: "Action") -> float:
                cv, _side = idx.get(a.instance_id, (None, None))
                return getattr(cv, "cost", 0) or 0 if cv is not None else 0
            picks.sort(key=value, reverse=True)
            return picks[0]
        return self._first(legal, "DeclineResourceUnitPlay")

    def _choose_pay_resources_for_tokens(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Curious Flock LOF_255: pay up to 6 resources, one Experience token each.
        Spending resources costs tempo (they can't be used elsewhere this phase) and
        the heuristic has no reliable way to value a vanilla-stat buff against that,
        so it conservatively pays nothing — finishing immediately is always safe and
        never cripples its own resource pool."""
        return self._first(legal, "FinishPayResources")

    def _choose_per_exploit_damage(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Count Dooku TWI_138: for each exploited unit, deal its power to an enemy
        unit.  Dealing is pure upside (free enemy damage), so always deal when a
        target exists — prefer the enemy unit the chunk can finish, else the
        biggest threat.  Decline only when no enemy unit is offered."""
        idx = _card_index(view)
        deals = [a for a in legal if type(a).__name__ == "DealExploitDamage"]
        if deals:
            def key(a):
                cv, _ = idx.get(a.target_id, (None, None))
                if cv is None:
                    return (0, 0)
                # Prefer the lowest-HP threat (most likely to die), tie-break on
                # the highest power.
                return (-_remaining_hp(cv), cv.effective_power)
            return max(deals, key=key)
        return self._first(legal, "DeclineExploitDamage")

    def _choose_use_force(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        """"You may use the Force" rider (The Will of the Force LOF_227 / Impossible
        Escape LOF_218): conservatively decline — the Force token is a resource the
        heuristic has no reliable way to value spending here.  At the payoff stage
        (the cost was already paid, no decline offered) exhaust the first eligible
        enemy unit (pure upside).  EXCEPTION: when declining carries a penalty
        (Savage Opress LOF_137 — "if you don't, deal 9 to your base"), pay the
        Force token instead when we can — taking 9 to our own base is worse."""
        decline = next((a for a in legal if type(a).__name__ == "DeclineUseForce"), None)
        if decline is not None and getattr(decline, "decline_penalty", None):
            force = next((a for a in legal
                          if type(a).__name__ == "UseForceOption"
                          and getattr(a, "option", None) == "force"), None)
            if force is not None:
                return force
        if decline is not None:
            return decline
        return legal[0]

    def _choose_peek_top(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        """Top-of-deck peek: draw it if we may (card advantage); otherwise leave
        it on top (we cannot see it, so do not bury it)."""
        draw = next((a for a in legal if type(a).__name__ == "DrawTopCard"), None)
        if draw is not None:
            return draw
        return self._first(legal, "KeepTopCard")

    def _choose_number(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        """Name a number (C-3PO): pick a commonly-printed cost to maximise the
        chance the top card matches and we draw it."""
        nums = [a for a in legal if type(a).__name__ == "ChooseNumber"]
        if not nums:
            return legal[0]
        return min(nums, key=lambda a: abs(int(getattr(a, "number", 0)) - 2))

    def _choose_reveal_cost_damage(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Don't Get Cocky (SOR_223) push-your-luck: reveal while the running
        tally is still 0 (0-cost cards add no risk and no reward), then lock in
        the first non-zero total.  A safe, non-overshooting default — never gambles
        a positive tally into the >7 zone (which would deal 0)."""
        tally = 0
        if view.pending_decisions:
            tally = int(view.pending_decisions[-1].context.get("tally", 0))
        reveal = next((a for a in legal if type(a).__name__ == "RevealNextCard"), None)
        if reveal is not None and tally == 0:
            return reveal
        return self._first(legal, "StopRevealing")

    def _choose_modal(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        """Modal 'choose one' (Leia): exhaust a threatening enemy unit if there
        is one, else ready a resource (ramp).  At the target stage, exhaust the
        biggest enemy / ready any resource."""
        idx = _card_index(view)
        options = [a for a in legal if type(a).__name__ == "ChooseModalOption"]
        if options:
            enemy_ready = [
                c for c in (view.opponent.ground_arena + view.opponent.space_arena)
                if not c.exhausted and c.effective_power > 0
            ]
            want = "exhaust_unit" if enemy_ready else "ready_resource"
            chosen = next((a for a in options if getattr(a, "mode", None) == want), None)
            return chosen or options[0]

        targets = [a for a in legal if type(a).__name__ == "ChooseModalTarget"]
        if targets:
            # If any target is an enemy unit, this is the exhaust mode → hit the
            # biggest threat; otherwise (resource ready) any target is fine.
            def threat(a: "Action") -> float:
                cv, side = idx.get(a.target_id, (None, None))
                if cv is None:
                    return -1.0
                return cv.effective_power if side == "opp" else -_card_value(cv)
            return max(targets, key=threat)
        return legal[0]

    def _choose_two_modal(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """"Choose two, in any order" aspect events (SOR_155/107/203/58): pick the
        first available option.  The options are ordered value-first on these cards
        (draw / removal / heal / mill lead), and each chosen option's own targeting
        is handled sensibly later via _choose_resolve_effects, so a simple
        first-available pick is safe and coherent."""
        return self._first(legal, "SelectModalOption")

    def _choose_sacrifice_resource(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Optional resource sacrifice (Wrecker SHD_154): worth a resource only if
        the 5 damage lands on an enemy ground unit.  At the decide stage, sacrifice
        when an enemy ground unit exists, else decline; at the target stage hit the
        enemy unit the damage best removes (biggest power / one it can finish)."""
        idx = _card_index(view)
        targets = [a for a in legal if type(a).__name__ == "ChooseSacrificeTarget"]
        if targets:
            def threat(a: "Action") -> float:
                cv, side = idx.get(a.target_id, (None, None))
                if cv is None or side != "opp":
                    return -1.0
                # Prefer a target the 5 damage outright defeats, then biggest power.
                finishes = 1.0 if (cv.effective_hp - cv.damage) <= 5 else 0.0
                return finishes * 100 + cv.effective_power
            return max(targets, key=threat)
        # decide stage
        enemy_ground = list(view.opponent.ground_arena)
        if enemy_ground:
            return self._first(legal, "SacrificeResource")
        return self._first(legal, "DeclineSacrifice")

    def _choose_reveal_resource_ramp(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Hunter SHD_9: revealing a name-matching resource is pure upside — the
        resource returns to hand (a replayable card) and its controller ramps a
        fresh resource off the deck top.  Always reveal (never decline); which
        matching resource is a minor value call, so take the first offered."""
        return self._first(legal, "RevealResourceForRamp")

    def _choose_discard_unit_damage(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """The Sarlacc of Carkoon LAW_163: recycle a unit from the discard pile
        (its power = the damage), then deal it to an enemy ground unit.

        Select stage — recycle the highest-power discarded unit to maximise the
        damage.  Target stage — hit the enemy unit the damage best removes (one it
        can finish, then biggest power), mirroring _choose_sacrifice_resource."""
        idx = _card_index(view)
        targets = [a for a in legal if type(a).__name__ == "ChooseDiscardDamageTarget"]
        if targets:
            def threat(a: "Action") -> float:
                cv, side = idx.get(a.target_id, (None, None))
                if cv is None or side != "opp":
                    return -1.0
                return cv.effective_power
            return max(targets, key=threat)
        selects = [a for a in legal
                   if type(a).__name__ == "SelectDiscardUnitForDamage"]
        if selects:
            def power(a: "Action") -> float:
                cv, _ = idx.get(a.instance_id, (None, None))
                return cv.effective_power if cv is not None else 0.0
            return max(selects, key=power)
        return _safe_default(legal)

    def _choose_cull_for_damage(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Darth Vader LAW_11 / Han Solo LAW_17: give up any number of your own
        cards, then deal that many damage.

        Cards in hand and tokens on board are real resources, so the bot is
        deliberately frugal: it culls exactly ONE (enough to make the ability do
        something and to satisfy a min-of-1 cost) and then finishes.  Target stage —
        hit the enemy unit the damage best removes, mirroring
        ``_choose_discard_unit_damage``; never a friendly one."""
        idx = _card_index(view)
        targets = [a for a in legal if type(a).__name__ == "ChooseCullDamageTarget"]
        if targets:
            def threat(a: "Action") -> float:
                cv, side = idx.get(a.target_id, (None, None))
                if cv is None or side != "opp":
                    return -1.0
                return cv.effective_power
            return max(targets, key=threat)
        top = view.pending_decisions[-1] if view.pending_decisions else None
        chosen = list((getattr(top, "context", None) or {}).get("chosen", ()))
        selects = [a for a in legal if type(a).__name__ == "SelectCullCard"]
        if selects and not chosen:
            return selects[0]
        finish = self._first(legal, "FinishCull")
        if finish is not None:
            return finish
        if selects:
            return selects[0]
        return _safe_default(legal)

    def _choose_discard_for_search(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Discard a card from hand to search the deck (Great Pit of Carkoon LAW_23
        cost; R2-D2 TWI_193 "you may discard a card, then dig").  Discarding to dig
        is card-neutral-or-better, so always discard (over the optional decline);
        pick the cheapest discardable card — the least tempo loss."""
        idx = _card_index(view)
        choices = [a for a in legal if type(a).__name__ == "DiscardForSearch"]
        if not choices:
            return _safe_default(legal)

        def cost(a: "Action") -> float:
            cv, _ = idx.get(a.instance_id, (None, None))
            return float(getattr(cv, "cost", 99)) if cv is not None else 99.0
        return min(choices, key=cost)

    def _choose_recur_and_buff(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Luminous Beings LOF_104: put up to 3 Force units from discard on the
        deck bottom, then give that many units +4/+4 this phase.  Recur as many as
        offered (more recurred → more buffs), then buff our own highest-power units
        (never an enemy's — the buff helps the recipient)."""
        idx = _card_index(view)
        recur = next((a for a in legal if type(a).__name__ == "SelectRecurUnit"), None)
        if recur is not None:
            return recur
        buffs = [a for a in legal if type(a).__name__ == "SelectBuffTarget"]
        mine = [a for a in buffs if idx.get(a.instance_id, (None, "opp"))[1] == "my"]
        if mine:
            def power(a: "Action") -> float:
                cv, _ = idx.get(a.instance_id, (None, None))
                return float(getattr(cv, "effective_power", 0)) if cv is not None else 0.0
            return max(mine, key=power)
        return self._first(legal, "FinishRecurBuff")

    def _choose_owner_may_replay(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Baylan Skoll LOF_185 / Rio Durant LAW_93 — the owner of a returned unit
        may play it back for free.  We are that owner; replaying is pure upside (a
        free unit back into play, possibly with Shielded), so take it whenever
        offered, else decline."""
        kinds = {type(a).__name__ for a in legal}
        if "ReplayReturnedUnit" in kinds:
            return self._first(legal, "ReplayReturnedUnit")
        return self._first(legal, "DeclineReplay")

    def _choose_put_on_deck(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Qui-Gon Jinn LOF_200 — the owner of a chosen unit puts it on the top or
        bottom of their own deck.  We are that owner (it is our card, our deck), so
        putting it on TOP draws it back soonest to replay it — pure tempo recovery."""
        return self._first(legal, "PutOnDeckTop")

    def _choose_let_wookiee_win(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Let the Wookiee Win (SHD_205) — two roles, told apart by the offered actions:
          * mode stage (we are the OPPONENT, choosing what the controller gets):
            pick ``ready_resources`` — it never hands the controller a free +2/+0
            Wookiee attack, and at instant speed few of their resources are exhausted,
            so it is usually the lower-value gift too.
          * ready stage (we are the CONTROLLER): ready our highest-power unit — the
            best defender to untap, and the biggest hit if it happens to be a Wookiee
            (the chained granted attack is then handled by _choose_granted_attack)."""
        modes = [a for a in legal if type(a).__name__ == "ChooseWookieeMode"]
        if modes:
            ready_res = next((a for a in modes if a.mode == "ready_resources"), None)
            return ready_res or modes[0]
        idx = _card_index(view)
        readies = [a for a in legal if type(a).__name__ == "ChooseWookieeReadyUnit"]
        if readies:
            def power(a: "Action") -> float:
                cv, _ = idx.get(a.unit_id, (None, None))
                return float(cv.effective_power) if cv is not None else -1.0
            return max(readies, key=power)
        return _safe_default(legal)

    def _choose_opponent_chooses_target(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Grey Squadron Y-Wing SHD_246 "An opponent chooses a unit or base they
        control. You may deal 2 damage to it."

        Two roles, told apart by the offered actions:
          * confirm stage (we are the source's controller) — the chosen target is
            an enemy card, so dealing the free damage is always good: confirm.
          * choose stage (we are the targeted opponent) — pick our least-valuable
            card to expose: the one with the most remaining HP (the base, almost
            always), never letting a unit die when a safer dump exists."""
        kinds = {type(a).__name__ for a in legal}
        if "ConfirmOpponentDamage" in kinds:
            return self._first(legal, "ConfirmOpponentDamage")
        idx = _card_index(view)
        choices = [a for a in legal if type(a).__name__ == "ChooseOwnTarget"]
        if choices:
            def safety(a: "Action") -> float:
                cv, _ = idx.get(a.target_id, (None, None))
                if cv is None:
                    return -1.0
                # Most remaining HP = least proportional harm; a base (huge HP)
                # wins, and a unit 2 damage would kill scores low.
                return float(_remaining_hp(cv))
            return max(choices, key=safety)
        return _safe_default(legal)

    def _choose_opponent_split_bounce(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """I Had No Choice SOR_187 — two roles, told apart by the offered actions:
          * split stage (we are the OPPONENT, our units were chosen): return our
            higher-value unit to hand (quick to redeploy), leaving the lesser one to
            be bottomed.
          * choose stage (we are the source's controller): add up to 2 ENEMY units
            to the bounce pool (never our own — no self-harm), highest value first;
            with no enemy unit to bounce, finish (a harmless no-op)."""
        idx = _card_index(view)
        splits = [a for a in legal if type(a).__name__ == "ChooseSplitReturn"]
        if splits:
            def value(a: "Action") -> float:
                cv, _ = idx.get(a.instance_id, (None, None))
                return _card_value(cv)
            return max(splits, key=value)
        selects = [a for a in legal if type(a).__name__ == "SelectSplitBounceUnit"]
        enemy = []
        for a in selects:
            cv, side = idx.get(a.instance_id, (None, None))
            if side == "opp" and cv is not None:
                enemy.append((a, _card_value(cv)))
        if enemy:
            return max(enemy, key=lambda pair: pair[1])[0]
        return self._first(legal, "FinishSplitBounce")

    def _choose_unit_to_defeat(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Merciless Contest TWI_238 "Each player chooses a non-leader unit they
        control. Defeat those units."  We must defeat one of our own units, so
        give up the least valuable one (lowest board value)."""
        idx = _card_index(view)
        choices = [a for a in legal if type(a).__name__ == "ChooseUnitToDefeat"]
        if choices:
            def value(a: "Action") -> float:
                cv, _ = idx.get(a.target_id, (None, None))
                return _card_value(cv)
            return min(choices, key=value)
        return _safe_default(legal)

    def _choose_name_a_card(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Galen Erso P25_31 "Name a card."  Name the card matching the highest-value
        enemy unit currently in play (shutting off the biggest threat's abilities),
        else the first offered name.  The option list is public, so this never leaks
        hidden info."""
        choices = [a for a in legal if type(a).__name__ == "NameCard"]
        if not choices:
            return _safe_default(legal)
        offered = {a.name for a in choices}
        best_name, best_val = None, -1.0
        for cv in (*view.opponent.ground_arena, *view.opponent.space_arena):
            nm = getattr(cv, "name", None)
            if nm in offered:
                v = _card_value(cv)
                if v > best_val:
                    best_name, best_val = nm, v
        if best_name is not None:
            return next(a for a in choices if a.name == best_name)
        return choices[0]

    def _choose_capture_or_ready(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Grand Admiral Thrawn SEC_193 WhenPlayed: as the deciding OPPONENT we may
        give up one of our own non-leader units to be captured (else the enemy
        Thrawn readies).  Declining hands the enemy only a ready Thrawn; giving up a
        unit is a real material loss — so always decline (readying an already-in-play
        enemy unit is the lesser evil)."""
        decline = next((a for a in legal
                        if type(a).__name__ == "DeclineCaptureVictim"), None)
        return decline if decline is not None else _safe_default(legal)

    def _choose_unit_to_spare(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Always Two LOF_42 "Choose 2 friendly units … Defeat all other friendly
        units."  Every other friendly unit dies, so keep the most valuable ones —
        spare the highest board value each step."""
        idx = _card_index(view)
        choices = [a for a in legal if type(a).__name__ == "ChooseUnitToSpare"]
        if choices:
            def value(a: "Action") -> float:
                cv, _ = idx.get(a.target_id, (None, None))
                return _card_value(cv)
            return max(choices, key=value)
        return _safe_default(legal)

    def _choose_keep_unique_copy(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Unique Rule: we control two copies of a unique card and must keep one
        (the rest are defeated).  Keep the most valuable copy — the more
        developed one (upgrades / tokens / less damage), by board value."""
        idx = _card_index(view)
        choices = [a for a in legal if type(a).__name__ == "KeepUniqueCopy"]
        if choices:
            def value(a: "Action") -> float:
                cv, _ = idx.get(a.instance_id, (None, None))
                return _card_value(cv)
            return max(choices, key=value)
        return _safe_default(legal)

    def _choose_move_upgrade(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Survivors' Gauntlet SHD_64 "You may attach an upgrade on a unit to
        another eligible unit controlled by the same player."  The heuristic has
        no reliable read on when rearranging its own upgrades helps, so it declines
        when it can (always safe — "you may").  Defensively, if it is somehow at the
        destination stage (no decline offered), it takes the first relocation."""
        kinds = {type(a).__name__ for a in legal}
        if "DeclineMoveUpgrade" in kinds:
            return self._first(legal, "DeclineMoveUpgrade")
        return _safe_default(legal)

    def _choose_reveal_play_credit(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Vermillion LAW_215: reveal a deck top; a chosen player may play it for
        free, and a *different* player makes Credits equal to its cost.  This
        political card has no reliable heuristic value, so the bot fizzles it
        safely — at the choose-player stage it picks itself, then declines to play,
        a clean no-op that never hands the opponent a free card or credits.
        Declining at the may-play stage is always safe, whoever did the choosing
        (the Survivors' Gauntlet SHD_64 "decline when unsure" philosophy)."""
        kinds = {type(a).__name__ for a in legal}
        if "DeclineRevealedCard" in kinds:
            return self._first(legal, "DeclineRevealedCard")
        if "ChooseRevealPlayer" in kinds:
            mine = [a for a in legal
                    if type(a).__name__ == "ChooseRevealPlayer"
                    and a.player_id == self.player_id]
            if mine:
                return mine[0]
            return self._first(legal, "ChooseRevealPlayer")
        if "ChooseRevealDeck" in kinds:
            return self._first(legal, "ChooseRevealDeck")
        return _safe_default(legal)

    def _choose_plot(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Plot (Garindan SEC_186, Lurking Snub Fighter SEC_189): on a leader
        deploy you may play Plot cards from your resources for their cost.  Playing
        a unit you already resourced is good value (a body now, a fresh card drawn
        to replace it), so take the first non-enemy-buff PlotPlay; otherwise
        finish.  Never plays an upgrade onto an enemy unit."""
        idx = _card_index(view)
        plays = [a for a in legal
                 if type(a).__name__ == "PlotPlay" and not _is_enemy_buff(a, idx)]
        if plays:
            return plays[0]
        return self._first(legal, "FinishPlot")

    def _choose_select_token(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Medal Ceremony SOR_245: give an Experience token to up to 3 eligible
        units.  Tokens are purely beneficial, so give one to each of our OWN
        eligible units (never an enemy's), then finish."""
        idx = _card_index(view)
        mine = [a for a in legal
                if type(a).__name__ == "SelectTokenTarget"
                and idx.get(a.target_id, (None, None))[1] == "my"]
        if mine:
            return mine[0]
        return self._first(legal, "FinishSelectToken")

    def _choose_select_damage(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """IG-2000 JTL_140: deal 1 damage to each of up to 3 units.  Aim only at
        ENEMY units (never our own), preferring the ones 1 damage can finish off,
        then the highest-value threats; finish once no enemy unit is left to hit."""
        idx = _card_index(view)
        enemy = [a for a in legal
                 if type(a).__name__ == "SelectDamageTarget"
                 and idx.get(a.target_id, (None, None))[1] == "opp"]
        if enemy:
            def priority(a: "Action") -> float:
                cv, _ = idx.get(a.target_id, (None, None))
                if cv is None:
                    return -1.0
                kill_bonus = 100.0 if _remaining_hp(cv) <= 1 else 0.0
                return kill_bonus + _card_value(cv)
            return max(enemy, key=priority)
        return self._first(legal, "FinishSelectDamage")

    def _choose_assign_indirect_damage(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """Indirect damage the bot must absorb (as the receiving player): dump it
        on the target with the most remaining HP — the base, essentially always —
        so a unit is never let die when a safer sink exists (mirrors the
        opponent_chooses_target safety heuristic)."""
        idx = _card_index(view)
        choices = [a for a in legal if type(a).__name__ == "AssignIndirectDamage"]
        if choices:
            def safety(a: "Action") -> float:
                cv, _ = idx.get(a.target_id, (None, None))
                return float(_remaining_hp(cv)) if cv is not None else -1.0
            return max(choices, key=safety)
        return _safe_default(legal)

    def _choose_granted_attack(
        self, view: "PlayerView", legal: list["Action"]
    ) -> "Action":
        """An effect grants an attack (e.g. Surprise Strike).  Reuse combat
        scoring; if every option is a losing trade and a decline is offered,
        decline; if the attack is mandatory, take the least-bad option (prefer
        chipping the base)."""
        idx = _card_index(view)
        base_remaining = _enemy_base_remaining(view)
        decline = next((a for a in legal if type(a).__name__ == "DeclineGrantedAttack"), None)
        attacks = [a for a in legal if type(a).__name__ == "AttackWithUnit"]
        if not attacks:
            return decline or legal[0]
        best, best_score = None, float("-inf")
        for a in attacks:
            score = self._score_attack(a, idx, base_remaining)
            if score > best_score:
                best, best_score = a, score
        # Decline only an optional grant that has nothing worthwhile.
        if decline is not None and best_score <= W_PASS:
            return decline
        return best or legal[0]

    # ── small helpers ─────────────────────────────────────────────────────

    def _first(self, legal: list["Action"], kind: str) -> "Action":
        return next((a for a in legal if type(a).__name__ == kind), legal[0])


# ── module-level pure helpers (shared, view-only) ─────────────────────────────

def _card_value(cv: Optional["CardView"]) -> float:
    """Board value of a unit: stat efficiency plus a keyword premium.  ``None``
    (an unresolved id) is worth nothing so it never wins a max()."""
    if cv is None:
        return 0.0
    v = V_POWER * cv.effective_power + V_HP * cv.effective_hp
    for kw in (cv.keywords or ()):
        v += KEYWORD_VALUE.get(kw, _DEFAULT_KEYWORD_VALUE)
    return v


# ── Self-harm avoidance ───────────────────────────────────────────────────────
# Effect kinds that hurt the *controller* of the card they target.  An ability
# built only from these, whose targets right now can only be the bot's own cards,
# is one the bot refuses to use / accept.
_HARMFUL_TARGETED_EFFECTS = frozenset({
    "DealDamage", "DefeatUnit", "ExhaustCard", "ReturnToHand", "RevokeKeyword",
})
# Predicates we can evaluate against the view when counting candidate targets.  A
# harmful spec carrying any *other* predicate (or a stat/cost/aspect filter) is
# treated as "can't tell" — we skip the rule rather than wrongly refuse a usable
# ability.
_KNOWN_PREDICATES = frozenset({"not_self", "non_leader"})


# Cost specs that make activating an ability a tangible loss (so paying them for
# no effect is pure waste).  A free ability that fizzles costs nothing to attempt.
_TANGIBLE_COSTS = frozenset({"ExhaustSelf", "PayResources", "DefeatSelf"})


def _ability_spec(set_code: str, card_number: str, ability_idx: int):
    """The registered ability spec, or None on any lookup problem (callers treat
    None as "no opinion")."""
    try:
        from swu.abilities.registry import get_abilities
        specs = get_abilities(set_code or "", card_number or "")
    except Exception:
        return None
    if not (0 <= ability_idx < len(specs)):
        return None
    return specs[ability_idx]


def _ability_has_tangible_cost(spec) -> bool:
    """True when activating ``spec`` pays an exhaust / resources / defeat-self cost."""
    return any(type(c).__name__ in _TANGIBLE_COSTS
               for c in (getattr(spec, "costs", None) or ()))


def _ability_effects(set_code: str, card_number: str, ability_idx: int) -> list:
    """Flattened effect list for one ability spec (ConditionalEffect → both
    branches).  Empty on any lookup problem — callers treat that as "no opinion"."""
    spec = _ability_spec(set_code, card_number, ability_idx)
    if spec is None:
        return []
    flat: list = []
    for e in list(getattr(spec, "effects", []) or []):
        if type(e).__name__ == "ConditionalEffect":
            flat.extend(list(getattr(e, "if_true", ()) or ()))
            flat.extend(list(getattr(e, "if_false", ()) or ()))
        else:
            flat.append(e)
    return flat


def _spec_target_count(spec, view: "PlayerView", side: str, source_id) -> int:
    """How many cards on ``side`` ("my"|"opp") this (simple) TargetSpec matches."""
    zone = view.my if side == "my" else view.opponent
    cands: list = []
    if spec.kind in ("unit", "unit_or_base"):
        cands += list(zone.ground_arena) + list(zone.space_arena)
    if spec.kind in ("base", "unit_or_base"):
        cands += [c for c in zone.base_zone if c.card_type == "Base"]

    n = 0
    for cv in cands:
        if cv.card_type == "Base":
            if spec.kind == "unit":
                continue
        else:  # a unit / deployed leader in an arena
            if spec.kind == "base":
                continue
            if spec.arena:
                want = "GROUND_ARENA" if spec.arena == "ground" else "SPACE_ARENA"
                if cv.zone != want:
                    continue
        if "not_self" in spec.predicates and cv.instance_id == source_id:
            continue
        if "non_leader" in spec.predicates and cv.card_type == "Leader":
            continue
        n += 1
    return n


def _ability_forces_self_harm(
    set_code: str, card_number: str, ability_idx: int, source_id, view: "PlayerView"
) -> bool:
    """True when a harmful, mandatory effect of this ability could right now only
    be aimed at the bot's own cards.

    Conservative by design: we only judge "plain" targets (controller="any", a
    unit/base kind, at most an arena + the handful of predicates we understand,
    no trait/cost/HP/aspect filter).  Anything we cannot evaluate from the view
    means "no opinion" — the ability stays usable.  We flag self-harm only when
    no enemy target of that kind exists *and* a friendly one does, so the choice
    would be forced onto a friendly.
    """
    for e in _ability_effects(set_code, card_number, ability_idx):
        if type(e).__name__ not in _HARMFUL_TARGETED_EFFECTS:
            continue
        spec = getattr(e, "target", None)
        if spec is None or spec.fixed is not None or spec.optional:
            continue
        if spec.controller != "any" or spec.kind not in ("unit", "base", "unit_or_base"):
            continue
        if (spec.traits or spec.aspects or spec.cost_max is not None
                or spec.cost_min is not None or spec.hp_remaining_max is not None
                or any(p not in _KNOWN_PREDICATES for p in spec.predicates)):
            continue
        if _spec_target_count(spec, view, "opp", source_id) > 0:
            continue  # an enemy target exists — fine to use
        if _spec_target_count(spec, view, "my", source_id) > 0:
            return True  # only friendly targets → forced self-harm
    return False


def _ability_is_pointless(
    set_code: str, card_number: str, ability_idx: int, source_id, view: "PlayerView"
) -> bool:
    """True when activating this *cost-bearing* ability would, right now, do
    nothing useful: every one of its effects is a harmful targeted effect we
    understand, and none of them can currently reach an enemy (so each would only
    fizzle on an empty target set, or be forced onto a friendly).  Paying an
    Exhaust / resource / defeat-self cost for that is pure waste — refuse it.

    This generalises the self-harm guard to the wider "don't pay a cost for a
    no-op" class (Grogu SHD_196's "Action [Exhaust]: Exhaust an enemy unit" with
    no enemy unit; Moff Gideon SHD_7's round-1 self-exhaust before its engine
    `condition` gate landed).

    Conservative by the same rule as ``_ability_forces_self_harm``: if the
    ability has no tangible cost, has no effects, or carries any effect we don't
    recognise as a plain harmful-targeted one — a beneficial effect, a card draw,
    or an opaque ``CustomEffect`` — we return False ("no opinion"), so a useful
    ability is never refused.  An opaque ``CustomEffect`` therefore stays the
    engine's responsibility to gate with a `condition` (the Moff Gideon pattern):
    the bot cannot see through an opaque fn from a redacted view, and an offered
    gated ability is assumed live.
    """
    spec = _ability_spec(set_code, card_number, ability_idx)
    if spec is None or not _ability_has_tangible_cost(spec):
        return False
    effects = _ability_effects(set_code, card_number, ability_idx)
    if not effects:
        return False
    for e in effects:
        if type(e).__name__ not in _HARMFUL_TARGETED_EFFECTS:
            return False  # a non-harmful (possibly useful) effect → no opinion
        tspec = getattr(e, "target", None)
        if tspec is None or tspec.fixed is not None:
            return False  # a fixed / auto target — can't judge from the view
        # Only judge plain specs we can evaluate (mirror _ability_forces_self_harm).
        if tspec.controller not in ("any", "enemy") or tspec.kind not in (
                "unit", "base", "unit_or_base"):
            return False
        if (tspec.traits or tspec.aspects or tspec.cost_max is not None
                or tspec.cost_min is not None or tspec.hp_remaining_max is not None
                or any(p not in _KNOWN_PREDICATES for p in tspec.predicates)):
            return False
        if _spec_target_count(tspec, view, "opp", source_id) > 0:
            return False  # this effect can hit an enemy → the ability does something
    return True  # every effect is harmful, yet none can currently reach an enemy


def _is_beneficial_upgrade(cv: "CardView") -> bool:
    """True when an upgrade grants a net-positive stat line (a buff).

    An upgrade-in-hand reports ``effective_power == 0`` (its modifier lives in
    ``upgrade_power``/``upgrade_hp``), so we read those public fields directly.
    Net-neutral or downside upgrades (no stat gain) return False — they are the
    only upgrades that legitimately belong on an enemy unit.
    """
    return (getattr(cv, "upgrade_power", 0) or 0) > 0 or (getattr(cv, "upgrade_hp", 0) or 0) > 0


def _upgrade_grants_bounty(set_code: str, card_number: str) -> bool:
    """True when this upgrade grants its host a Bounty.

    A Bounty is modelled as a ``GrantedAbility`` wrapping a ``WhenDefeated``
    trigger that resolves for the *opponent* of the host's controller (the
    collector).  So a Bounty upgrade has the inverse value of a normal buff: its
    payoff comes when the host is defeated, which the opponent collects — meaning
    it belongs on an *enemy* unit, not a friendly one.  Detected by inspecting the
    registered ability specs (the same `get_abilities` lookup the self-harm guard
    uses), so the bot stays a pure function of the view + the registry, with no DB
    text lookup.  This is the ONLY net-statless upgrade kind that wants an enemy
    host — ability-granting upgrades (Foundling, The Darksaber) are statless too
    but help a friendly host, so a stat-only test cannot tell them apart.
    """
    try:
        from swu.abilities.registry import (
            get_abilities, GrantedAbility, TriggerAbility, WhenDefeated,
        )
        specs = get_abilities(set_code or "", card_number or "")
    except Exception:
        return False
    for s in specs:
        if (isinstance(s, GrantedAbility)
                and isinstance(s.ability, TriggerAbility)
                and isinstance(s.ability.trigger, WhenDefeated)):
            return True
    return False


def _is_enemy_buff(a: "Action", idx: dict) -> bool:
    """True when ``a`` plays a beneficial upgrade onto an opponent's unit."""
    if type(a).__name__ != "PlayCard":
        return False
    cv = idx.get(getattr(a, "instance_id", None), (None, None))[0]
    if cv is None or cv.card_type != "Upgrade":
        return False
    host, host_side = idx.get(getattr(a, "upgrade_target_id", None), (None, None))
    return host is not None and host_side == "opp" and _is_beneficial_upgrade(cv)


def _remaining_hp(cv: "CardView") -> int:
    return max(0, cv.effective_hp - cv.damage)


def _has_shield(cv: "CardView") -> bool:
    return any((u.card_name or "").lower() == "shield" for u in (cv.attached_upgrades or ()))


def _trade_outcome(attacker: "CardView", defender: "CardView") -> tuple[float, float]:
    """Estimate (value gained, value lost) for ``attacker`` striking ``defender``.

    Simultaneous damage: the attacker deals its power to the defender and takes
    the defender's power back.  A unit dies when the incoming damage meets its
    remaining HP (a Shield token absorbs the whole strike once).  Kills score the
    full board value; non-kills get partial chip credit.
    """
    atk_dmg = 0 if _has_shield(defender) else attacker.effective_power
    def_dmg = 0 if _has_shield(attacker) else defender.effective_power

    def_rem = _remaining_hp(defender)
    atk_rem = _remaining_hp(attacker)
    def_dies = atk_dmg >= def_rem and def_rem > 0
    atk_dies = def_dmg >= atk_rem and atk_rem > 0

    def_val = _card_value(defender)
    atk_val = _card_value(attacker)
    gain = def_val if def_dies else CHIP_GAIN * def_val * (atk_dmg / max(1, def_rem))
    loss = atk_val if atk_dies else CHIP_LOSS * atk_val * (def_dmg / max(1, atk_rem))
    return gain, loss


def _card_index(view: "PlayerView") -> dict:
    """Map every visible instance_id → (CardView, "my" | "opp").

    Covers hands, resources, arenas, base zones and (recursively) attached
    upgrades, so any target_id the engine offers can be looked up.
    """
    idx: dict = {}

    def add(cv: "CardView", side: str) -> None:
        idx[cv.instance_id] = (cv, side)
        for u in (cv.attached_upgrades or ()):
            add(u, side)

    for side, zone in (("my", view.my), ("opp", view.opponent)):
        for lst in (zone.hand, zone.resources, zone.discard,
                    zone.ground_arena, zone.space_arena, zone.base_zone):
            for cv in lst:
                add(cv, side)
    return idx


def _enemy_base_remaining(view: "PlayerView") -> int:
    for cv in view.opponent.base_zone:
        if cv.card_type == "Base":
            return _remaining_hp(cv)
    return 0


def _my_undeployed_leader(view: "PlayerView") -> Optional["CardView"]:
    for cv in view.my.base_zone:
        if cv.card_type == "Leader" and not cv.deployed:
            return cv
    return None


def _top_context(view: "PlayerView") -> dict:
    if view.pending_decisions:
        ctx = view.pending_decisions[-1].context
        if isinstance(ctx, dict):
            return ctx
    return {}


# Safe, non-raising fallback options in priority order: prefer declining /
# continuing / passing over a surprising commitment.  The first one present in
# ``legal`` wins; ``legal[0]`` is the ultimate backstop (always engine-legal).
_SAFE_DEFAULT_ORDER = (
    "Pass", "ContinueAttack", "AutoResolveEffects", "DeclineTarget",
    "DeclineTrigger", "DeclineAmbush", "DeclineReadyUnit", "DeclineGrantedAttack",
    "ExploitCommit", "KeepTopCard", "FinishSearch", "AllowEffect", "KeepHand",
    "DeclineSacrifice", "DeclineRevealResource",
    "FinishReturnFromDiscard", "FinishBottomFromDiscard",
    "DeclineMoveUpgrade",
    "FinishPlot", "DeclineRevealedCard", "AckLookHand", "FinishSplitBounce",
    "FinishDiscardForSearch", "FinishRecur", "FinishRecurBuff",
    "FinishExhaustForBaseDamage", "FinishExhaustCombined", "FinishCaptureCombined",
    "FinishPayResources", "DeclineExploitDamage", "FinishSelectDamage",
    "FinishDamageDistribution", "DeclineReplay", "DeclineDisclose",
    "PayRegroupUpkeep", "DeclineAttachSelfAsPilot", "DeclineCaptureVictim",
    "DeclinePlayUpgradeFromHand", "DeclineCombatPrevention", "AcceptExhaust",
    "DeclineStealUpgrade", "DeclineNameAndDiscard", "DeclineCapturedPlay",
    "DeclineResourceUnitPlay", "FinishCombinedPowerPlay", "DeclineRescue",
    "FinishResourceFromHand",
)


def _safe_default(legal: list["Action"]) -> "Action":
    by_kind = {type(a).__name__: a for a in legal}
    for kind in _SAFE_DEFAULT_ORDER:
        if kind in by_kind:
            return by_kind[kind]
    return legal[0]
