"""
Bot blunder census — counts *named* misplays a bot commits over many real games.

Win rate tells you whether a change helped; this tells you WHY.  It replays real
games and, at every decision, works out from the engine's own ground truth (the
ability registry + the live GameState) which of a short list of unambiguous
blunders the bot just committed:

  buff_enemy        gave an enemy card a heal / token / stat buff / keyword /
                    ready, while a friendly target was legal
  harm_self         aimed damage-defeat-exhaust-bounce-capture at its OWN card
                    while an enemy target was legal
  upgrade_enemy     attached a non-Bounty, non-negative upgrade to an enemy unit
  suicide_attack    attacked into a unit that kills it without killing back,
                    while attacking the enemy base was legal
  whiff_attack      attacked a unit it cannot damage at all, while the enemy base
                    was attackable
  fizzled_event     played an Event whose every effect needs a target, with no
                    legal target on the board — the card is simply thrown away

Every counter is a *false-positive-safe* judgement: it only fires when the better
alternative was demonstrably legal at that moment, so a non-zero count is a real
misplay rather than a difference of taste.

Usage
-----
    python scripts/bot_blunders.py --bot heuristic --games 64 --jobs 8
    python scripts/bot_blunders.py --bot easy --games 64      # Easy's blunder rate
"""
from __future__ import annotations

import argparse
import collections
import itertools
import multiprocessing
import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

_DB = str(_ROOT / "data" / "swu.db")
_FX = _ROOT / "tests" / "fixtures"

DECKS = [
    "shd_han_solo", "sabine_mean_green", "the_mandalorian", "moff_gideon",
    "leia_organa", "ahsoka_tano", "general_grievous", "jabba_the_hutt",
    "boba_fett", "han_solo", "darth_maul", "qui_gon_jinn",
    "chancellor_palpatine", "padme_amidala", "emperor_palpatine",
    "luke_skywalker_ash",
]

# Effects that HELP whoever controls the target.
BENEFICIAL = {"Heal", "GiveToken", "ReadyCard", "GrantKeyword", "TraitGrant"}
# Effects that HURT whoever controls the target.
HARMFUL = {"DealDamage", "DealDamageEqualTo", "DefeatUnit", "ExhaustCard",
           "ReturnToHand", "RevokeKeyword", "RevokeTrait", "CaptureUnit",
           "ResourceCardEffect"}


def _baseline_module():
    """The FROZEN pre-tuning heuristic, loaded from ``benchmarks/`` by path.

    It lives outside ``src/`` on purpose: it is a measurement artefact, not part
    of the game, and a second 1900-line near-copy of the bot sitting beside the
    real one in ``swu/players/`` is exactly the sort of thing that gets edited by
    accident.  Loading it by path also keeps it working in every multiprocessing
    worker without sys.path juggling.
    """
    import importlib.util
    global _BASELINE
    try:
        return _BASELINE
    except NameError:
        pass
    path = _ROOT / "benchmarks" / "heuristic_baseline.py"
    if not path.exists():
        raise SystemExit(
            f"no frozen baseline at {path} — 'baseline' needs it; compare two "
            f"live variants with the w:/easy: forms instead")
    spec = importlib.util.spec_from_file_location("swu_heuristic_baseline", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _BASELINE = module
    return module


def _make_bot(name: str, pid: str, seed: int):
    from swu.players.heuristic_bot import HeuristicBot
    if name in ("heuristic", "normal"):
        return HeuristicBot(pid, seed=seed)
    if name == "hard":
        return HeuristicBot(pid, seed=seed, sharp_targeting=True)
    if name == "easy":
        from swu.players.difficulty import _EASY_MISTAKE_RATE
        return HeuristicBot(pid, seed=seed, mistake_rate=_EASY_MISTAKE_RATE)
    if name == "baseline":
        return _baseline_module().HeuristicBot(pid, seed=seed)
    if name == "baseline_easy":
        return _baseline_module().HeuristicBot(pid, seed=seed, mistake_rate=0.25)
    raise SystemExit("unknown bot: " + name)


def _live_effect(state, decision):
    """The effect a ``resolve_effects`` decision is *currently* asking about.

    Mirrors ``resolver.resolve_effects_actions``' walk (skip effects with no
    target spec or no legal targets) using the real state, so this is ground
    truth rather than the bot's view-only approximation.
    Returns (effect, target_spec, legal_target_ids) or None.
    """
    from swu.abilities.registry import get_abilities
    from swu.abilities.resolver import (
        unwrap_granted, _get_effect_target_spec, _gather_legal_targets,
    )
    ctx = decision.context
    try:
        specs = get_abilities(ctx["set_code"], ctx["card_number"])
        ability = unwrap_granted(specs[ctx["ability_idx"]])
        effects = ability.effects
        res = state.find_instance(ctx["source_id"])
        if res is None:
            return None
        _, source_ci = res
        i = ctx["effect_idx"]
        while i < len(effects):
            eff = effects[i]
            spec = _get_effect_target_spec(eff)
            if spec is None or spec.fixed is not None:
                i += 1
                continue
            targets = _gather_legal_targets(state, spec, source_ci,
                                            ctx.get("event_ctx", {}))
            if not targets:
                i += 1
                continue
            return eff, spec, targets
    except Exception:
        return None
    return None


def _side_of(state, iid, me):
    res = state.find_instance(iid)
    if res is None:
        return None
    ps, _ci = res
    # Side is CONTROL, not ownership: a card sits in the row of whoever controls
    # it (the engine convention), which is exactly what the bot's view shows.
    return "my" if ps.player_id == me else "opp"


def _shielded(ci) -> bool:
    for u in (getattr(ci, "attached_upgrades", None) or ()):
        if (u.card_def.display_name or "").lower() == "shield":
            return True
    return False


def _classify(state, action, me, counts):
    """Record any blunder ``action`` represents for player ``me`` in ``state``."""
    from swu.engine.actions import legal_actions
    kind = type(action).__name__

    # ── targeted effects ──────────────────────────────────────────────────
    if kind == "ChooseTarget" and state.pending_decisions:
        top = state.pending_decisions[-1]
        if top.kind == "resolve_effects":
            live = _live_effect(state, top)
            if live is not None:
                eff, _spec, targets = live
                ename = type(eff).__name__
                if ename == "ModifyStats":
                    ename = "BUFF" if (eff.power > 0 or eff.hp > 0) else "DEBUFF"
                sides = {t: _side_of(state, t, me) for t in targets}
                chosen = sides.get(action.target_id)
                present = set(sides.values())
                if ename in BENEFICIAL or ename == "BUFF":
                    if chosen == "opp" and "my" in present:
                        counts["buff_enemy"] += 1
                        counts["buff_enemy:" + type(eff).__name__] += 1
                elif ename in HARMFUL or ename == "DEBUFF":
                    if chosen == "my" and "opp" in present:
                        counts["harm_self"] += 1
                        counts["harm_self:" + type(eff).__name__] += 1
        return

    # ── events played into an empty board ─────────────────────────────────
    if kind == "PlayCard" and not getattr(action, "upgrade_target_id", None):
        res = state.find_instance(action.instance_id)
        if res is not None and getattr(res[1].card_def, "type", "") == "Event":
            if _event_fizzles(state, res[1]):
                cd = res[1].card_def
                counts["fizzled_event"] += 1
                counts["fizzled_event:%s_%s" % (
                    getattr(cd, "set_code", ""), getattr(cd, "card_number", ""))] += 1
        return

    # ── upgrades onto enemy units ─────────────────────────────────────────
    if getattr(action, "upgrade_target_id", None):
        from swu.players.heuristic_bot import _upgrade_grants_bounty
        res = state.find_instance(action.instance_id)
        host = state.find_instance(action.upgrade_target_id)
        if res is not None and host is not None:
            _, ci = res
            host_ps, host_ci = host
            cd = ci.card_def
            sc = getattr(cd, "set_code", "") or ""
            cn = getattr(cd, "card_number", "") or ""
            if host_ps.player_id != me and not _upgrade_grants_bounty(sc, cn):
                # A genuinely negative upgrade legitimately wants an enemy host.
                if (getattr(cd, "power", 0) or 0) >= 0 and (getattr(cd, "hp", 0) or 0) >= 0:
                    counts["upgrade_enemy"] += 1
                    counts["upgrade_enemy:" + kind + ":" + sc + "_" + cn] += 1
        return

    # ── attacks ───────────────────────────────────────────────────────────
    if kind == "AttackWithUnit" and getattr(action, "defender_id", None):
        legal = legal_actions(state)
        base_ok = any(type(a).__name__ == "AttackWithUnit" and a.defender_id is None
                      and a.attacker_id == action.attacker_id for a in legal)
        if not base_ok:
            return
        ares = state.find_instance(action.attacker_id)
        dres = state.find_instance(action.defender_id)
        if ares is None or dres is None:
            return
        _, atk = ares
        _, dfd = dres
        # Effective stats, as combat will actually see them: Raid is a
        # while-attacking bonus and auras/modifiers do not show in the printed
        # reading, so the naive ci.effective_power() mis-scores real attacks.
        from swu.engine.actions import compute_power, compute_hp
        atk_power = compute_power(state, atk, is_attacking=True)
        atk_dmg = 0 if _shielded(dfd) else atk_power
        def_dmg = 0 if _shielded(atk) else compute_power(state, dfd)
        atk_rem = max(0, compute_hp(state, atk) - atk.damage)
        def_rem = max(0, compute_hp(state, dfd) - dfd.damage)
        atk_dies = atk_rem > 0 and def_dmg >= atk_rem
        def_dies = def_rem > 0 and atk_dmg >= def_rem
        if atk_dies and not def_dies:
            counts["suicide_attack"] += 1
        if atk_dmg == 0:
            counts["whiff_attack"] += 1
        return


def _event_fizzles(state, ci) -> bool:
    """True when every effect of this event needs a target and none is legal.

    Only judges an event whose abilities are entirely made of targeted effects we
    can resolve (no CustomEffect, no untargeted draw/damage rider) — anything else
    counts as "does something" and is not reported.
    """
    from swu.abilities.registry import get_abilities, EventAbility
    from swu.abilities.resolver import _get_effect_target_spec, _gather_legal_targets
    cd = ci.card_def
    try:
        specs = get_abilities(getattr(cd, "set_code", "") or "",
                              getattr(cd, "card_number", "") or "")
    except Exception:
        return False
    abilities = [s for s in specs if isinstance(s, EventAbility)]
    if not abilities:
        return False
    saw_target = False
    for ability in abilities:
        effects = list(getattr(ability, "effects", None) or ())
        if not effects:
            return False
        for eff in effects:
            if type(eff).__name__ in ("CustomEffect", "ConditionalEffect"):
                return False  # opaque — assume it does something
            spec = _get_effect_target_spec(eff)
            if spec is None:
                return False  # an untargeted effect always does something
            if getattr(spec, "fixed", None) is not None:
                return False
            saw_target = True
            try:
                if _gather_legal_targets(state, spec, ci, {}):
                    return False
            except Exception:
                return False
    return saw_target


def _run(job: dict) -> dict:
    src = str(_ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from swu.cards.repository import CardRepository
    from swu.cards.decklist import load_decklist
    from swu.engine.actions import create_game, legal_actions, apply

    repo = CardRepository(_DB)
    d0 = load_decklist(_FX / (job["deck_a"] + ".json"), repo)
    d1 = load_decklist(_FX / (job["deck_b"] + ".json"), repo)
    counts: collections.Counter = collections.Counter()

    for a_is_p0 in (True, False):
        a_id = "P0" if a_is_p0 else "P1"
        da, db = (d0, d1) if a_is_p0 else (d1, d0)
        try:
            state = create_game("P0", da, "P1", db, seed=job["seed"])
            bots = {"P0": _make_bot(job["bot"], "P0", job["seed"]),
                    "P1": _make_bot(job["bot"], "P1", job["seed"] + 7919)}
            n = 0
            while not state.is_terminal() and n < job["cap"]:
                pid = (state.pending_decisions[-1].deciding_player_id
                       if state.pending_decisions else state.active_player.player_id)
                chosen = bots[pid].choose_action(state.view_for(pid),
                                                 legal_actions(state))
                if pid == a_id:
                    counts["decisions"] += 1
                    _classify(state, chosen, a_id, counts)
                state = apply(state, chosen)
                n += 1
            counts["games"] += 1
        except Exception as exc:
            counts["errors"] += 1
            counts["err:" + type(exc).__name__] += 1
    return dict(counts)


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--bot", default="heuristic")
    p.add_argument("--games", type=int, default=64)
    p.add_argument("--jobs", type=int,
                   default=max(1, (multiprocessing.cpu_count() or 4)))
    p.add_argument("--cap", type=int, default=3000)
    p.add_argument("--seed-start", type=int, default=9000)
    args = p.parse_args(argv)

    pairs = [(x, y) for x, y in itertools.product(DECKS, DECKS) if x != y]
    random.Random(999).shuffle(pairs)
    jobs = [{"deck_a": pairs[i % len(pairs)][0], "deck_b": pairs[i % len(pairs)][1],
             "seed": args.seed_start + i, "bot": args.bot, "cap": args.cap}
            for i in range(max(1, args.games // 2))]

    if args.jobs > 1:
        with multiprocessing.Pool(args.jobs) as pool:
            results = pool.map(_run, jobs)
    else:
        results = [_run(j) for j in jobs]

    total: collections.Counter = collections.Counter()
    for r in results:
        total.update(r)

    games = total.pop("games", 0)
    decisions = total.pop("decisions", 0)
    print("bot=%s  games=%d  decisions=%d" % (args.bot, games, decisions))
    print("%-34s%8s%12s" % ("blunder", "count", "per game"))
    for key in ("buff_enemy", "harm_self", "upgrade_enemy",
                "suicide_attack", "whiff_attack", "fizzled_event"):
        n = total.pop(key, 0)
        print("%-34s%8d%12.2f" % (key, n, n / max(1, games)))
    detail = {k: v for k, v in total.items() if ":" in k}
    if detail:
        print("\nbreakdown:")
        for k, v in sorted(detail.items(), key=lambda kv: -kv[1])[:25]:
            print("  %-42s%6d" % (k, v))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
