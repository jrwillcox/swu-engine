"""
SWU campaign runner — scalable soak testing with parallel workers.

Usage
-----
python scripts/soak.py [options]

Options
-------
--games N           Total games to play (default: 1000)
--seed-start N      First seed value (default: 0)
--bots SPEC         Comma-separated list of bot types to use as the player pool.
                    Valid: random,weighted,aggro,chaos (default: random,weighted,aggro,chaos)
--decks SPEC        Comma-separated list of deck presets to pair:
                    vanilla,keyword,starter (default: starter,vanilla)
--check-invariants  Enable per-action invariant checks (default: on)
--no-check-invariants
                    Disable per-action invariant checks for speed
--jobs N            Parallel worker count (default: cpu_count or 4)
--action-cap N      Max actions per game before declaring a cap-hit failure (default: 2000)
--failures-dir DIR  Directory to write repro bundles (default: failures/)
--report PATH       Path for the JSON statistics report (default: docs/soak_report.json)
--quiet             Suppress per-game progress output

Exit code: 0 if all games completed cleanly; 1 if any failures occurred.
"""
from __future__ import annotations

import argparse
import datetime
import json
import multiprocessing
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

# ── picklable game runner ─────────────────────────────────────────────────────

def _run_game(args: dict) -> dict:
    """Worker function — must be picklable (module-level, no closures).

    Returns a result dict with keys:
      seed, bot_p0, bot_p1, deck_p0, deck_p1, outcome ('ok'|'cap'|'error'|'invariant'),
      n_actions, winner, rounds, action_history (only on failure),
      error_msg (only on failure), state_json (only on failure).
    """
    import sys
    import os
    # Ensure src is importable when spawned as a new process
    src = args["src_path"]
    if src not in sys.path:
        sys.path.insert(0, src)

    db_path = args["db_path"]
    os.environ.setdefault("SWU_DB", db_path)

    seed = args["seed"]
    bot_p0_name = args["bot_p0"]
    bot_p1_name = args["bot_p1"]
    deck_p0_name = args["deck_p0"]
    deck_p1_name = args["deck_p1"]
    action_cap = args["action_cap"]
    check_invariants = args["check_invariants"]

    try:
        from swu.cards.repository import CardRepository
        repo = CardRepository(db_path)
        deck_p0 = _load_deck(repo, deck_p0_name)
        deck_p1 = _load_deck(repo, deck_p1_name)

        from swu.engine.actions import create_game, legal_actions, apply
        state = create_game("P0", deck_p0, "P1", deck_p1, seed=seed)

        ctx = None
        if check_invariants:
            from swu.engine.invariants import CheckContext, check as inv_check
            ctx = CheckContext.from_state(state)

        bot_p0 = _make_bot(bot_p0_name, "P0", seed)
        bot_p1 = _make_bot(bot_p1_name, "P1", seed + 1)
        bots = {"P0": bot_p0, "P1": bot_p1}

        action_history: list[dict] = []
        n_actions = 0
        stats = _GameStats()

        # Install the ability-resolution observer for this game.  Re-set every
        # game (workers are reused across games) so counts attribute correctly.
        from swu.abilities.resolver import set_ability_observer, set_effect_observer
        set_ability_observer(lambda sc, cn: stats.record_ability_fired(f"{sc}_{cn}"))
        set_effect_observer(
            lambda sc, cn, kind, amount, nt: stats.record_effect(sc, cn, kind, amount, nt)
        )

        while not state.is_terminal() and n_actions < action_cap:
            acts = legal_actions(state)
            active_id = state.active_player.player_id
            view = state.view_for(active_id)
            chosen = bots[active_id].choose_action(view, acts)

            # Record before apply
            action_history.append({
                "kind": type(chosen).__name__,
                "player": active_id,
                "desc": chosen.describe(),
            })
            stats.record_action(state, chosen)

            state = apply(state, chosen)
            n_actions += 1

            if check_invariants and ctx is not None:
                try:
                    inv_check(state, ctx)
                except AssertionError as exc:
                    return _failure_bundle(
                        seed, bot_p0_name, bot_p1_name, deck_p0_name, deck_p1_name,
                        "invariant", str(exc), action_history, state, stats,
                    )

        if not state.is_terminal():
            return _failure_bundle(
                seed, bot_p0_name, bot_p1_name, deck_p0_name, deck_p1_name,
                "cap", f"Action cap {action_cap} reached without terminal state",
                action_history, state, stats,
            )

        # Determinism oracle: on a sampled fraction of games, replay the exact
        # same seed/bots/decks a second time and assert an identical outcome.
        # Directly targets the non-determinism class already hit once (sorted-set
        # serialisation).  Disabled by sample==0.
        det_sample = args.get("determinism_sample", 0)
        if det_sample and seed % det_sample == 0:
            try:
                fp1 = _game_fingerprint(state, n_actions)
                from swu.abilities.resolver import set_ability_observer, set_effect_observer
                set_ability_observer(None)   # don't double-count on the replay
                set_effect_observer(None)
                fp2 = _replay_plain(
                    seed, bot_p0_name, bot_p1_name,
                    deck_p0_name, deck_p1_name, db_path, action_cap,
                )
                if fp1 != fp2:
                    return _failure_bundle(
                        seed, bot_p0_name, bot_p1_name, deck_p0_name, deck_p1_name,
                        "nondeterministic",
                        f"Re-run from seed {seed} diverged: {fp1[:2]} vs {fp2[:2]}",
                        action_history, state, stats,
                    )
            except Exception:
                tb = traceback.format_exc()
                return _failure_bundle(
                    seed, bot_p0_name, bot_p1_name, deck_p0_name, deck_p1_name,
                    "nondeterministic", f"Determinism re-run raised: {tb}",
                    action_history, state, stats,
                )

        return {
            "outcome": "ok",
            "seed": seed,
            "bot_p0": bot_p0_name,
            "bot_p1": bot_p1_name,
            "deck_p0": deck_p0_name,
            "deck_p1": deck_p1_name,
            "n_actions": n_actions,
            "winner": state.winner,
            "rounds": state.round_number,
            "action_cap": action_cap,
            "stats": stats.to_dict(),
        }

    except Exception:
        tb = traceback.format_exc()
        return {
            "outcome": "error",
            "seed": seed,
            "bot_p0": bot_p0_name,
            "bot_p1": bot_p1_name,
            "deck_p0": deck_p0_name,
            "deck_p1": deck_p1_name,
            "n_actions": -1,
            "winner": None,
            "rounds": -1,
            "error_msg": tb,
            "action_history": [],
            "stats": {},
        }


def _failure_bundle(
    seed, bot_p0, bot_p1, deck_p0, deck_p1,
    outcome, error_msg, action_history, state, stats,
) -> dict:
    try:
        state_json = state.to_json()
    except Exception:
        state_json = "{}"
    return {
        "outcome": outcome,
        "seed": seed,
        "bot_p0": bot_p0,
        "bot_p1": bot_p1,
        "deck_p0": deck_p0,
        "deck_p1": deck_p1,
        "n_actions": len(action_history),
        "winner": None,
        "rounds": getattr(state, "round_number", -1),
        "error_msg": error_msg,
        "action_history": action_history,
        "state_json": state_json,
        "stats": stats.to_dict() if stats else {},
    }


def _game_fingerprint(state: Any, n_actions: int) -> tuple:
    """A deterministic fingerprint of a finished game for the re-run oracle.

    Excludes event_log (not restored by from_json; not part of game outcome).
    """
    j = json.loads(state.to_json())
    j.pop("event_log", None)
    return (state.winner, n_actions, json.dumps(j, sort_keys=True))


def _replay_plain(
    seed, bot_p0_name, bot_p1_name, deck_p0_name, deck_p1_name, db_path, action_cap,
) -> tuple:
    """Re-play a game from scratch with the same seed/bots/decks (no invariants,
    no observers) and return its fingerprint.  Same seed + same deterministic
    bots must reproduce the same game; any divergence is a non-determinism bug.
    """
    from swu.cards.repository import CardRepository
    from swu.engine.actions import create_game, legal_actions, apply
    repo = CardRepository(db_path)
    deck_p0 = _load_deck(repo, deck_p0_name)
    deck_p1 = _load_deck(repo, deck_p1_name)
    state = create_game("P0", deck_p0, "P1", deck_p1, seed=seed)
    bots = {
        "P0": _make_bot(bot_p0_name, "P0", seed),
        "P1": _make_bot(bot_p1_name, "P1", seed + 1),
    }
    n = 0
    while not state.is_terminal() and n < action_cap:
        acts = legal_actions(state)
        aid = state.active_player.player_id
        chosen = bots[aid].choose_action(state.view_for(aid), acts)
        state = apply(state, chosen)
        n += 1
    return _game_fingerprint(state, n)


# ── per-game statistics collector ─────────────────────────────────────────────

class _GameStats:
    def __init__(self) -> None:
        self.action_kinds: dict[str, int] = {}
        self.leader_deployed: dict[str, bool] = {"P0": False, "P1": False}
        self.leader_deploy_round: dict[str, int] = {}
        self.initiative_takes: int = 0
        self.mulligan_taken: dict[str, bool] = {"P0": False, "P1": False}
        self.abilities_fired: dict[str, int] = {}  # "SOR_59" -> count
        # Per-ability effect efficacy: distinguishes "fired" from "did something".
        # key -> {"fired": int, "targets": int, "amount": int, "kinds": {name: count}}
        self.effect_efficacy: dict[str, dict] = {}
        self._last_round: int = 1

    def record_action(self, state: Any, action: Any) -> None:
        kind = type(action).__name__
        self.action_kinds[kind] = self.action_kinds.get(kind, 0) + 1
        self._last_round = getattr(state, "round_number", 1)

        if kind == "DeployLeader":
            pid = state.active_player.player_id
            self.leader_deployed[pid] = True
            self.leader_deploy_round[pid] = state.round_number

        if kind == "ClaimInitiative":
            self.initiative_takes += 1

        if kind in ("TakeMultiligan",):
            pid = state.active_player.player_id
            self.mulligan_taken[pid] = True

    def record_ability_fired(self, ability_key: str) -> None:
        self.abilities_fired[ability_key] = self.abilities_fired.get(ability_key, 0) + 1

    def record_effect(self, sc: str, cn: str, kind: str, amount: int, n_targets: int) -> None:
        key = f"{sc}_{cn}"
        e = self.effect_efficacy.get(key)
        if e is None:
            e = {"fired": 0, "targets": 0, "amount": 0, "kinds": {}}
            self.effect_efficacy[key] = e
        e["fired"] += 1
        e["targets"] += n_targets
        e["amount"] += amount
        e["kinds"][kind] = e["kinds"].get(kind, 0) + 1

    def to_dict(self) -> dict:
        return {
            "action_kinds": self.action_kinds,
            "leader_deployed": self.leader_deployed,
            "leader_deploy_round": self.leader_deploy_round,
            "initiative_takes": self.initiative_takes,
            "mulligan_taken": self.mulligan_taken,
            "abilities_fired": self.abilities_fired,
            "effect_efficacy": self.effect_efficacy,
        }


# ── deck / bot construction (run inside worker) ───────────────────────────────

_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
_PHASE2_KEYWORDS = frozenset({
    "Sentinel", "Overwhelm", "Raid", "Ambush",
    "Restore", "Saboteur", "Shielded", "Grit", "Exploit",
})


def _load_deck(repo: Any, name: str) -> list:
    if name == "starter_vader":
        from swu.cards.decklist import load_decklist
        return load_decklist(_FIXTURE_DIR / "starter_vader.json", repo)
    if name == "starter_luke":
        from swu.cards.decklist import load_decklist
        return load_decklist(_FIXTURE_DIR / "starter_luke.json", repo)
    if name == "vanilla_vader":
        from swu.cards.decklist import build_vanilla_deck
        return build_vanilla_deck(repo, "Darth Vader", "Security Complex")
    if name == "vanilla_luke":
        from swu.cards.decklist import build_vanilla_deck
        return build_vanilla_deck(repo, "Luke Skywalker", "Administrator's Tower")
    if name == "keyword_vader":
        return _build_keyword_deck(repo, "Darth Vader", "Security Complex")
    if name == "keyword_luke":
        return _build_keyword_deck(repo, "Luke Skywalker", "Administrator's Tower")
    # Fallback: treat the name as a SWUDB-JSON fixture (path, or a stem under the
    # fixtures dir).  Lets the encoding verifier soak an arbitrary deck by name —
    # e.g. --decks tests/fixtures/shd_han_solo.json:tests/fixtures/shd_han_solo.json
    from pathlib import Path as _Path
    cand = _Path(name)
    if not cand.exists():
        stem = name[:-5] if name.endswith(".json") else name
        cand = _FIXTURE_DIR / f"{stem}.json"
    if cand.exists():
        from swu.cards.decklist import load_decklist
        return load_decklist(cand, repo)
    raise ValueError(f"Unknown deck preset or fixture: {name!r}")


def _build_keyword_deck(repo: Any, leader_name: str, base_name: str) -> list:
    from swu.cards.models import Leader, Base, Unit

    leaders = repo.by_name(leader_name)
    leader = next((c for c in leaders if isinstance(c, Leader)), None)
    if leader is None:
        raise ValueError(f"No Leader named {leader_name!r}")
    bases = repo.by_name(base_name)
    base = next((c for c in bases if isinstance(c, Base)), None)
    if base is None:
        raise ValueError(f"No Base named {base_name!r}")

    available_aspects = {a.name for a in leader.aspects} | {a.name for a in base.aspects}
    keyword_units: list = []
    other_units: list = []
    for card in repo.all_of_type("Unit"):
        if not isinstance(card, Unit):
            continue
        card_aspects = {a.name for a in card.aspects}
        if card_aspects and not (card_aspects & available_aspects):
            continue
        kws = set(getattr(card, "keywords", ()))
        if kws & _PHASE2_KEYWORDS:
            keyword_units.append(card)
        else:
            other_units.append(card)

    seen: set[str] = set()
    pool: list = []
    for c in keyword_units + other_units:
        if c.name not in seen:
            seen.add(c.name)
            pool.append(c)

    deck_cards: list = []
    for c in pool:
        limit = 1 if c.is_unique else 3
        for _ in range(limit):
            if len(deck_cards) >= 50:
                break
            deck_cards.append(c)
        if len(deck_cards) >= 50:
            break

    return [leader, base] + deck_cards[:50]


def _make_bot(name: str, player_id: str, seed: int) -> Any:
    if name == "random":
        from swu.players.random_bot import RandomBot
        return RandomBot(player_id, seed=seed)
    if name == "weighted":
        from swu.players.weighted_bot import WeightedBot
        return WeightedBot(player_id, seed=seed)
    if name == "aggro":
        from swu.players.aggro_bot import AggroBot
        return AggroBot(player_id, seed=seed)
    if name == "chaos":
        from swu.players.chaos_bot import ChaosBot
        return ChaosBot(player_id, seed=seed)
    if name == "heuristic":
        from swu.players.heuristic_bot import HeuristicBot
        return HeuristicBot(player_id, seed=seed)
    if name == "easy":
        from swu.players.difficulty import Difficulty, make_opponent
        return make_opponent(Difficulty.EASY, player_id=player_id, seed=seed)
    if name == "hard":
        from swu.players.difficulty import Difficulty, make_opponent
        return make_opponent(Difficulty.HARD, player_id=player_id, seed=seed)
    raise ValueError(f"Unknown bot type: {name!r}")


# ── deck preset expansion ─────────────────────────────────────────────────────

_DECK_PRESETS: dict[str, list[tuple[str, str]]] = {
    "starter": [("starter_vader", "starter_luke")],
    "vanilla": [("vanilla_vader", "vanilla_luke")],
    "keyword": [("keyword_vader", "keyword_luke")],
}


def _expand_deck_pairs(spec: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for token in spec.split(","):
        token = token.strip()
        if token in _DECK_PRESETS:
            pairs.extend(_DECK_PRESETS[token])
        elif ":" in token:
            a, b = token.split(":", 1)
            pairs.append((a.strip(), b.strip()))
        else:
            raise ValueError(f"Unknown deck spec: {token!r}")
    return pairs


def _reachable_card_keys(deck_pairs: list[tuple[str, str]], db_path: str, src_path: str) -> set[str]:
    """All "SET_NUM" card keys present in any deck used this campaign.

    Used to escalate zero-fire stubs on cards the bots could actually play.
    Best-effort: returns an empty set on any failure (never blocks reporting).
    """
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    keys: set[str] = set()
    try:
        from swu.cards.repository import CardRepository
        repo = CardRepository(db_path)
        for name in {n for pair in deck_pairs for n in pair}:
            for c in _load_deck(repo, name):
                sc = getattr(c, "set_code", None)
                cn = getattr(c, "card_number", None)
                if sc and cn:
                    keys.add(f"{sc}_{cn}")
    except Exception:
        return set()
    return keys


# ── report generation ─────────────────────────────────────────────────────────

def _analyse_ability_coverage(agg_abilities: dict[str, int], reachable_keys: set[str] | None = None) -> dict:
    """Compare fire counts against the full ability registry.

    Returns a dict with these buckets:
      fired             — {key: count} for abilities that resolved >= 1 time
      zero_fire_active  — [{key, types, reachable}] active abilities that never
                          fired (a real finding: broken wiring or unreachable card)
      reachable_zero_fire — subset of zero_fire_active whose card is in one of
                          THIS campaign's decks.  A zero-fire ability on an
                          unreachable card is benign; one on a card the bots
                          actually drew and (could have) played is a likely
                          no-op/stub bug — the exact class that hid Surprise
                          Strike (it fired its event but the registration was
                          empty, so it never routed through the resolver).
      passive_constant  — [key] cards whose ONLY ability is Constant; these are
                          passive (read by compute_power/has_keyword) and never
                          routed through the resolver, so a 0 here is expected.
    """
    reachable_keys = reachable_keys or set()
    # Ensure SOR registrations are loaded in this process.
    import swu.cards.sor  # noqa: F401
    from swu.abilities.registry import (
        get_all_registered, ConstantAbility, GrantedAbility, EntersPlayReady,
        AttackRestriction, ConditionalFirstStrike, IndirectDamageBonus,
        AdditionalPilotSlots, IndirectDamageSelfAssign, StandingPlayDiscount,
        ReadyRestriction, ExtraRegroupPhase, PreventDamage, MultiDefenderAttack,
        InteractiveDamagePrevention, AmbushDefenderDebuff, AmbushAttackerBonus,
        DamagePrevention,
        IgnoreAspectPenaltyForUpgrades, StartingHandModifier, HalvePaidCosts,
        WhenDefeatedRedo, OnAttackRedo,
        CrossArenaAttack, CannotBeAttacked, CannotBeAttackedWhileExhausted,
    )

    registry = get_all_registered()
    fired: dict[str, int] = {}
    zero_fire_active: list[dict] = []
    passive_constant: list[str] = []

    for (sc, cn), specs in sorted(registry.items()):
        key = f"{sc}_{cn}"
        count = agg_abilities.get(key, 0)
        type_names = sorted({type(s).__name__ for s in specs})
        # ConstantAbility is passive (read by compute_power/has_keyword, never
        # routed through the resolver).  GrantedAbility *is* routed through the
        # resolver, but its firing is attributed to the HOST unit (the source),
        # not to the upgrade key — so a 0 against the upgrade is likewise
        # expected, not a wiring bug.  Both are reported as passive.
        # EntersPlayReady is likewise passive: read at the enter-play placement
        # (_put_unit_in_play), never routed through the resolver, so a 0 against it
        # is expected — not a wiring bug.
        only_passive = bool(specs) and all(
            isinstance(s, (ConstantAbility, GrantedAbility, EntersPlayReady,
                           AttackRestriction, ConditionalFirstStrike,
                           IndirectDamageBonus, AdditionalPilotSlots,
                           IndirectDamageSelfAssign, StandingPlayDiscount,
                           ReadyRestriction, ExtraRegroupPhase, PreventDamage,
                           MultiDefenderAttack, InteractiveDamagePrevention,
                           AmbushDefenderDebuff, AmbushAttackerBonus,
                           DamagePrevention,
                           IgnoreAspectPenaltyForUpgrades, StartingHandModifier,
                           HalvePaidCosts,
                           # The two ability-redo markers (Thrawn JTL_2, Enfys
                           # Nest LAW_14) are read only at
                           # resolver._schedule_ability_redo, never routed through
                           # the resolver — a 0 is expected, not a wiring bug.
                           WhenDefeatedRedo, OnAttackRedo,
                           # Attack-enumeration markers (Red Leader ASH_37,
                           # Tatooine Repulsor Train ASH_35, Sabine TWI_195) —
                           # read at legal_actions, never routed through the
                           # resolver, so a 0 is expected.
                           CrossArenaAttack, CannotBeAttacked,
                           CannotBeAttackedWhileExhausted))
            for s in specs)
        if count > 0:
            fired[key] = count
        elif only_passive:
            passive_constant.append(key)
        else:
            zero_fire_active.append({
                "key": key, "types": type_names, "reachable": key in reachable_keys,
            })

    # Any fired key not in the registry (shouldn't happen) is still reported.
    for key, count in agg_abilities.items():
        if key not in fired and count > 0:
            fired[key] = count

    return {
        "fired": dict(sorted(fired.items())),
        "zero_fire_active": zero_fire_active,
        "reachable_zero_fire": [z["key"] for z in zero_fire_active if z["reachable"]],
        "passive_constant": sorted(passive_constant),
        "n_registered": len(registry),
        "n_fired": len(fired),
    }


# Effect kinds for which resolving zero targets across a whole campaign is a
# red flag (they require a chosen/auto target to do anything).  Targetless or
# opaque kinds (DrawCards, DefeatAllUnits, CustomEffect, ConditionalEffect) are
# excluded — a 0-target reading there is normal, not a bug.
_TARGETED_EFFECT_KINDS = frozenset({
    "DealDamage", "Heal", "DefeatUnit", "GiveToken", "ExhaustCard", "ReadyCard",
    "ModifyStats", "GrantKeyword", "RevokeKeyword", "ReturnToHand",
    "ResourceCardEffect",
})


# Minimum resolutions before a 0-target reading is treated as a finding rather
# than small-sample noise.  A working but low-frequency targeted ability (e.g.
# Snowspeeder's "exhaust an enemy Vehicle ground unit") can legitimately whiff a
# handful of times when the board lacks a target; at campaign scale (10k games) a
# genuinely broken targeting resolves zero across hundreds of fires.
_WHIFF_MIN_FIRED = 20


def _analyse_effect_efficacy(agg_efficacy: dict[str, dict]) -> dict:
    """Flag abilities that resolve a *targeted* effect but never hit a target.

    An ability that "fires" (routes through execute_effect) yet resolves zero
    targets for every targeted effect across the whole campaign is almost always
    a targeting/wiring bug — the symptom the per-ability fire count alone hides.
    Only flagged once it has fired at least ``_WHIFF_MIN_FIRED`` times, so rare
    targeted abilities are not reported as bugs on small samples.
    """
    suspicious: list[dict] = []
    for key, e in sorted(agg_efficacy.items()):
        kinds = e.get("kinds", {})
        targeted = {k: c for k, c in kinds.items() if k in _TARGETED_EFFECT_KINDS}
        if targeted and e.get("targets", 0) == 0 and e.get("fired", 0) >= _WHIFF_MIN_FIRED:
            suspicious.append({
                "key": key,
                "fired": e.get("fired", 0),
                "targeted_kinds": sorted(targeted),
            })
    return {
        "per_ability": dict(sorted(agg_efficacy.items())),
        "suspicious_whiff": suspicious,
    }


def _build_report(results: list[dict], elapsed: float, reachable_keys: set[str] | None = None) -> dict:
    ok = [r for r in results if r["outcome"] == "ok"]
    failures = [r for r in results if r["outcome"] != "ok"]
    total = len(results)

    # Win rates
    winner_counts: dict[str, int] = {}
    for r in ok:
        w = r.get("winner") or "none"
        winner_counts[w] = winner_counts.get(w, 0) + 1

    # Game length distributions
    action_counts = [r["n_actions"] for r in ok if r["n_actions"] > 0]
    round_counts = [r["rounds"] for r in ok if r.get("rounds", 0) > 0]

    def _stats(vals: list[int]) -> dict:
        if not vals:
            return {}
        vals_s = sorted(vals)
        n = len(vals_s)
        return {
            "min": vals_s[0],
            "max": vals_s[-1],
            "mean": round(sum(vals_s) / n, 1),
            "p25": vals_s[n // 4],
            "p50": vals_s[n // 2],
            "p75": vals_s[3 * n // 4],
        }

    # Action kind frequencies (aggregate across all games)
    agg_kinds: dict[str, int] = {}
    for r in ok:
        for k, v in r.get("stats", {}).get("action_kinds", {}).items():
            agg_kinds[k] = agg_kinds.get(k, 0) + v

    # Leader deploy rates
    deployed_p0 = sum(
        1 for r in ok if r.get("stats", {}).get("leader_deployed", {}).get("P0", False)
    )
    deployed_p1 = sum(
        1 for r in ok if r.get("stats", {}).get("leader_deployed", {}).get("P1", False)
    )
    deploy_rounds_p0 = [
        r["stats"]["leader_deploy_round"]["P0"]
        for r in ok
        if r.get("stats", {}).get("leader_deploy_round", {}).get("P0")
    ]
    deploy_rounds_p1 = [
        r["stats"]["leader_deploy_round"]["P1"]
        for r in ok
        if r.get("stats", {}).get("leader_deploy_round", {}).get("P1")
    ]

    # Ability coverage
    agg_abilities: dict[str, int] = {}
    for r in ok:
        for k, v in r.get("stats", {}).get("abilities_fired", {}).items():
            agg_abilities[k] = agg_abilities.get(k, 0) + v

    # Classify every *registered* ability against the fire counts so we can
    # surface zero-fire abilities.  Constant abilities are passive (read by
    # compute_power/has_keyword, never routed through the resolver) so they are
    # reported separately rather than flagged as broken wiring.
    coverage_analysis = _analyse_ability_coverage(agg_abilities, reachable_keys)

    # Effect efficacy: aggregate per-ability {fired, targets, amount, kinds}.
    agg_efficacy: dict[str, dict] = {}
    for r in ok:
        for key, e in r.get("stats", {}).get("effect_efficacy", {}).items():
            agg = agg_efficacy.get(key)
            if agg is None:
                agg = {"fired": 0, "targets": 0, "amount": 0, "kinds": {}}
                agg_efficacy[key] = agg
            agg["fired"] += e.get("fired", 0)
            agg["targets"] += e.get("targets", 0)
            agg["amount"] += e.get("amount", 0)
            for k, c in e.get("kinds", {}).items():
                agg["kinds"][k] = agg["kinds"].get(k, 0) + c
    efficacy_analysis = _analyse_effect_efficacy(agg_efficacy)

    # Game-length tail: flag games that ran close to the action cap (a latent
    # slow-loop that did not quite trip the cap).  cap is threaded via results.
    cap = max((r.get("action_cap", 0) for r in results), default=0)
    near_cap = sorted(
        (r["n_actions"] for r in ok if cap and r["n_actions"] >= 0.9 * cap),
        reverse=True,
    )

    # Determinism re-run mismatches (outcome=="nondeterministic" failures).
    nondeterministic = [r for r in results if r["outcome"] == "nondeterministic"]

    report = {
        "generated": datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat() + "Z",
        "total_games": total,
        "ok_games": len(ok),
        "failed_games": len(failures),
        "elapsed_seconds": round(elapsed, 1),
        "win_rates": winner_counts,
        "action_length": _stats(action_counts),
        "round_length": _stats(round_counts),
        "action_kind_frequencies": dict(sorted(agg_kinds.items(), key=lambda x: -x[1])),
        "leader_deploy_rate": {
            "P0": round(deployed_p0 / max(1, len(ok)), 3),
            "P1": round(deployed_p1 / max(1, len(ok)), 3),
            "avg_deploy_round_P0": round(sum(deploy_rounds_p0) / max(1, len(deploy_rounds_p0)), 2) if deploy_rounds_p0 else None,
            "avg_deploy_round_P1": round(sum(deploy_rounds_p1) / max(1, len(deploy_rounds_p1)), 2) if deploy_rounds_p1 else None,
        },
        "initiative_takes_per_game": round(
            sum(r.get("stats", {}).get("initiative_takes", 0) for r in ok) / max(1, len(ok)), 2
        ),
        "ability_coverage": dict(sorted(agg_abilities.items())),
        "coverage_analysis": coverage_analysis,
        "effect_efficacy": efficacy_analysis,
        "action_cap": cap,
        "near_cap_games": near_cap,
        "nondeterministic_games": [r["seed"] for r in nondeterministic],
        "failures": [
            {
                "seed": r["seed"],
                "outcome": r["outcome"],
                "error_msg": r.get("error_msg", "")[:500],
                "n_actions": r["n_actions"],
            }
            for r in failures
        ],
    }
    return report


def _collect_anomalies(report: dict) -> list[str]:
    """Surface findings worth investigating at the top of the report.

    Bands: seat win rate 35–65%, mean rounds 5–40, no fired-but-whiffed ability,
    no near-cap games, no non-determinism.  Zero-fire active abilities are noted
    (they should all be escape-hatch stubs — worth a glance, not necessarily a
    bug).
    """
    out: list[str] = []
    ok = max(1, report.get("ok_games", 0))
    for player, count in sorted(report.get("win_rates", {}).items()):
        if player == "none":
            continue
        pct = 100 * count / ok
        if pct < 35 or pct > 65:
            out.append(f"Seat win rate for {player} is {pct:.1f}% (outside 35–65%).")
    rl = report.get("round_length", {})
    if rl.get("mean") is not None:
        if rl["mean"] < 5:
            out.append(f"Mean game length {rl['mean']} rounds (< 5 — games ending too fast).")
        if rl["mean"] > 40:
            out.append(f"Mean game length {rl['mean']} rounds (> 40 — games dragging).")
    whiff = report.get("effect_efficacy", {}).get("suspicious_whiff", [])
    if whiff:
        out.append(f"{len(whiff)} fired-but-whiffed ability(ies): "
                   f"{', '.join(w['key'] for w in whiff)} (targeting/wiring bug?).")
    near = report.get("near_cap_games", [])
    if near:
        out.append(f"{len(near)} game(s) ran ≥90% of the action cap (max {near[0]}).")
    nd = report.get("nondeterministic_games", [])
    if nd:
        out.append(f"{len(nd)} game(s) were non-deterministic on re-run "
                   f"(seeds {nd[:10]}).")
    cov = report.get("coverage_analysis", {})
    zfa = cov.get("zero_fire_active", [])
    reachable_zf = cov.get("reachable_zero_fire", [])
    if reachable_zf:
        # LIKELY BUG: the card is in a deck the bots played this campaign, yet its
        # active ability never resolved.  This is the class that hid Surprise
        # Strike — a playable card whose ability does nothing.
        out.append(f"⚠ {len(reachable_zf)} zero-fire active ability(ies) on cards "
                   f"REACHABLE in this campaign's decks (likely no-op/stub bug): "
                   f"{', '.join(reachable_zf)}.")
    unreachable_zf = [i["key"] for i in zfa if not i.get("reachable")]
    if unreachable_zf:
        out.append(f"{len(unreachable_zf)} zero-fire active ability(ies) on "
                   f"unreachable cards — confirm each is a deferred stub: "
                   f"{', '.join(unreachable_zf)}.")
    return out


def _write_markdown_report(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# SWU Soak Campaign Report",
        "",
        f"Generated: {report['generated']}",
        f"Total games: {report['total_games']}  "
        f"OK: {report['ok_games']}  "
        f"Failed: {report['failed_games']}  "
        f"Elapsed: {report['elapsed_seconds']}s",
        "",
    ]

    # Anomaly banner at the very top — surfaces the things worth investigating
    # without scrolling.  Empty banner == clean run.
    anomalies = _collect_anomalies(report)
    if anomalies:
        lines += ["## ⚠ Anomalies flagged", ""]
        lines += [f"- {a}" for a in anomalies]
        lines += [""]
    else:
        lines += ["_No anomalies flagged._", ""]

    lines += ["## Win Rates", ""]
    for player, count in sorted(report["win_rates"].items()):
        pct = 100 * count / max(1, report["ok_games"])
        lines.append(f"- {player}: {count} wins ({pct:.1f}%)")
    lines += [
        "",
        "## Game Length",
        "",
        f"Actions — {report['action_length']}",
        f"Rounds  — {report['round_length']}",
        "",
        "## Leader Deploy Rates",
        "",
        f"- P0: {report['leader_deploy_rate']['P0']:.1%} "
        f"(avg round {report['leader_deploy_rate']['avg_deploy_round_P0']})",
        f"- P1: {report['leader_deploy_rate']['P1']:.1%} "
        f"(avg round {report['leader_deploy_rate']['avg_deploy_round_P1']})",
        "",
        "## Action Kind Frequencies",
        "",
    ]
    for kind, count in list(report["action_kind_frequencies"].items())[:20]:
        lines.append(f"- {kind}: {count}")
    lines += ["", "## Ability Coverage", ""]
    cov = report.get("coverage_analysis", {})
    if cov:
        lines.append(
            f"Registered abilities: {cov['n_registered']}  "
            f"Fired at least once: {cov['n_fired']}  "
            f"Passive (constant-only): {len(cov['passive_constant'])}  "
            f"Zero-fire active: {len(cov['zero_fire_active'])}"
        )
        lines.append("")
        if cov["zero_fire_active"]:
            lines.append("**ZERO-FIRE ACTIVE abilities (investigate each):**")
            for item in cov["zero_fire_active"]:
                flag = "  ⚠ REACHABLE (likely bug)" if item.get("reachable") else ""
                lines.append(f"- {item['key']} ({', '.join(item['types'])}){flag}")
        else:
            lines.append("**No zero-fire active abilities** — every registered "
                         "non-constant ability resolved at least once.")
        lines.append("")
        lines.append("Passive constant-only abilities (expected zero via the "
                     "resolver tracker; active whenever the card is in play):")
        lines.append(f"  {', '.join(cov['passive_constant']) or '(none)'}")
        lines.append("")
        lines.append("### Fire counts (effects resolved across the campaign)")
        for k, v in sorted(cov["fired"].items()):
            lines.append(f"- {k}: {v}")
    else:
        for k, v in sorted(report["ability_coverage"].items()):
            lines.append(f"- {k}: {v}")

    # Effect efficacy
    eff = report.get("effect_efficacy", {})
    if eff:
        lines += ["", "## Effect Efficacy", ""]
        whiff = eff.get("suspicious_whiff", [])
        if whiff:
            lines.append("**FIRED-BUT-WHIFFED abilities (resolved a targeted "
                         "effect but never hit a target — likely a targeting/"
                         "wiring bug):**")
            for w in whiff:
                lines.append(
                    f"- {w['key']}: fired {w['fired']}× / 0 targets "
                    f"({', '.join(w['targeted_kinds'])})"
                )
        else:
            lines.append("**No fired-but-whiffed abilities** — every ability "
                         "that resolved a targeted effect hit a target at least "
                         "once.")
        lines.append("")
        lines.append("### Per-ability efficacy (fired / targets / nominal amount)")
        for k, e in sorted(eff.get("per_ability", {}).items()):
            kinds = ",".join(f"{kk}×{vv}" for kk, vv in sorted(e.get("kinds", {}).items()))
            lines.append(
                f"- {k}: fired {e['fired']}, targets {e['targets']}, "
                f"amount {e['amount']} [{kinds}]"
            )

    # Game-length tail / near-cap
    cap = report.get("action_cap", 0)
    near = report.get("near_cap_games", [])
    lines += ["", "## Game-length tail", ""]
    lines.append(f"Action cap: {cap}")
    if near:
        lines.append(f"**{len(near)} game(s) ran ≥90% of the cap** "
                     f"(max {near[0]}): investigate for slow loops.")
    else:
        lines.append("No games ran within 90% of the action cap.")

    # Determinism
    nd = report.get("nondeterministic_games", [])
    lines += ["", "## Determinism re-run", ""]
    if nd:
        lines.append(f"**{len(nd)} game(s) produced a different result on "
                     f"re-run from the same seed** (seeds: {nd[:20]}): "
                     f"non-determinism — investigate immediately.")
    else:
        lines.append("All re-run sampled games reproduced identically.")

    if report["failures"]:
        lines += ["", "## Failures", ""]
        for f in report["failures"]:
            lines.append(
                f"- seed={f['seed']} outcome={f['outcome']} "
                f"n_actions={f['n_actions']}: {f['error_msg'][:200]}"
            )
    path.write_text("\n".join(lines), encoding="utf-8")


# ── repro bundle writer ───────────────────────────────────────────────────────

def _write_repro_bundle(result: dict, failures_dir: Path) -> Path:
    failures_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).strftime("%Y%m%d_%H%M%S")
    fname = f"{ts}_seed{result['seed']}.json"
    fpath = failures_dir / fname
    fpath.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return fpath


# ── main ──────────────────────────────────────────────────────────────────────

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="SWU parallel campaign runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--games", type=int, default=1000)
    p.add_argument("--seed-start", type=int, default=0, dest="seed_start")
    p.add_argument("--bots", default="random,weighted,aggro,chaos")
    p.add_argument("--decks", default="starter,vanilla")
    p.add_argument("--check-invariants", dest="check_invariants",
                   action="store_true", default=True)
    p.add_argument("--no-check-invariants", dest="check_invariants",
                   action="store_false")
    p.add_argument("--jobs", type=int,
                   default=min(multiprocessing.cpu_count(), 8))
    p.add_argument("--action-cap", type=int, default=2000, dest="action_cap")
    p.add_argument("--determinism-sample", type=int, default=50,
                   dest="determinism_sample",
                   help="Re-run every Nth game (by seed) from scratch and assert "
                        "an identical outcome; 0 disables (default: 50).")
    p.add_argument("--failures-dir", default="failures", dest="failures_dir")
    p.add_argument("--report", default="docs/soak_report.json")
    p.add_argument("--quiet", action="store_true", default=False)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    # Resolve paths relative to the project root (parent of scripts/)
    project_root = Path(__file__).resolve().parent.parent
    src_path = str(project_root / "src")
    db_path = str(project_root / "data" / "swu.db")
    failures_dir = project_root / args.failures_dir
    report_path = project_root / args.report

    if not Path(db_path).exists():
        print(f"ERROR: Database not found at {db_path}", file=sys.stderr)
        return 1

    # Expand deck / bot combinations
    bot_pool = [b.strip() for b in args.bots.split(",")]
    deck_pairs = _expand_deck_pairs(args.decks)

    # Build work items — cycle through bot × deck matrix
    import itertools

    combos = list(itertools.product(bot_pool, bot_pool, deck_pairs))
    work_items: list[dict] = []
    for i in range(args.games):
        seed = args.seed_start + i
        # Rotate through combos deterministically
        bot_p0, bot_p1, (deck_p0, deck_p1) = combos[i % len(combos)]
        work_items.append({
            "seed": seed,
            "bot_p0": bot_p0,
            "bot_p1": bot_p1,
            "deck_p0": deck_p0,
            "deck_p1": deck_p1,
            "action_cap": args.action_cap,
            "check_invariants": args.check_invariants,
            "determinism_sample": args.determinism_sample,
            "src_path": src_path,
            "db_path": db_path,
        })

    print(
        f"Campaign: {args.games} games, {args.jobs} workers, "
        f"bots={bot_pool}, decks={[p for pair in deck_pairs for p in pair]}, "
        f"invariants={'on' if args.check_invariants else 'off'}"
    )

    t0 = time.monotonic()
    results: list[dict] = []
    n_ok = 0
    n_fail = 0

    if args.jobs == 1:
        # Single-process path (easier to debug)
        # Add src to path in this process too
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        os.environ.setdefault("SWU_DB", db_path)
        for i, item in enumerate(work_items):
            result = _run_game(item)
            results.append(result)
            if result["outcome"] == "ok":
                n_ok += 1
            else:
                n_fail += 1
                bpath = _write_repro_bundle(result, failures_dir)
                print(
                    f"  FAIL seed={result['seed']} {result['outcome']}: "
                    f"{str(result.get('error_msg',''))[:120]} -> {bpath}"
                )
            if not args.quiet and (i + 1) % 50 == 0:
                elapsed = time.monotonic() - t0
                print(f"  {i+1}/{args.games} games | {elapsed:.1f}s | {n_fail} failures")
    else:
        # Multiprocessing — use spawn to avoid fork-related issues on Windows/Mac
        ctx = multiprocessing.get_context("spawn")
        with ctx.Pool(processes=args.jobs) as pool:
            for i, result in enumerate(pool.imap_unordered(_run_game, work_items)):
                results.append(result)
                if result["outcome"] == "ok":
                    n_ok += 1
                else:
                    n_fail += 1
                    bpath = _write_repro_bundle(result, failures_dir)
                    print(
                        f"  FAIL seed={result['seed']} {result['outcome']}: "
                        f"{str(result.get('error_msg',''))[:120]} -> {bpath}"
                    )
                if not args.quiet and (i + 1) % 50 == 0:
                    elapsed = time.monotonic() - t0
                    print(f"  {i+1}/{args.games} games | {elapsed:.1f}s | {n_fail} failures")

    elapsed = time.monotonic() - t0
    print(f"\nDone: {n_ok} ok, {n_fail} failed in {elapsed:.1f}s")

    # Cards reachable in this campaign's decks — lets the coverage analysis
    # escalate a zero-fire stub on a *playable* card from "worth a glance" to a
    # likely bug (the class that hid Surprise Strike).
    reachable_keys = _reachable_card_keys(deck_pairs, db_path, src_path)

    # Write reports
    report = _build_report(results, elapsed, reachable_keys)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path = report_path.with_suffix(".md")
    _write_markdown_report(report, md_path)
    print(f"Report: {report_path}")
    print(f"        {md_path}")

    return 1 if n_fail > 0 else 0


if __name__ == "__main__":
    # Windows spawn requires this guard
    multiprocessing.freeze_support()
    sys.exit(main())
