"""Unit tests for the HeuristicBot and the difficulty factory.

Each test builds a real GameState, derives the redacted PlayerView and the
engine's legal actions exactly as the runtime does, and asserts the *class* of
choice the bot makes — never reaching into engine internals the bot cannot see.
"""
from __future__ import annotations


import pytest

from tests.dbpath import db_path, require_db
from conftest import run_through_setup

from swu.engine.actions import (
    AttackWithUnit, DeployLeader, Pass, ResourceCard, KeepHand, TakeMultiligan,
    ChooseTarget, create_game, legal_actions, apply,
)
from swu.engine.state import CardInstance, Phase, Zone
from swu.players.heuristic_bot import HeuristicBot
from swu.players.difficulty import Difficulty, make_opponent

_DB = db_path()


# ── construction helpers ──────────────────────────────────────────────────────

def _unit(iid, owner, power, hp, *, cost=2, keywords=(), arena="Ground",
          card_id=1000):
    class FakeUnit:
        aspects = ()
        type = "Unit"
        is_unique = False
        traits = ()
        set_code = None
        card_number = None
    FakeUnit.id = card_id
    FakeUnit.display_name = iid
    FakeUnit.cost = cost
    FakeUnit.power = power
    FakeUnit.hp = hp
    FakeUnit.keywords = tuple(keywords)
    FakeUnit.arenas = (arena,)
    z = Zone.GROUND_ARENA if arena == "Ground" else Zone.SPACE_ARENA
    return CardInstance(iid, FakeUnit(), owner, z)


def _hand_card(iid, owner, *, cost=2, ctype="Unit", power=2, hp=2):
    class FakeCard:
        aspects = ()
        is_unique = False
        traits = ()
        set_code = None
        card_number = None
        keywords = ()
    FakeCard.id = 2000
    FakeCard.display_name = iid
    FakeCard.type = ctype
    FakeCard.cost = cost
    FakeCard.power = power
    FakeCard.hp = hp
    return CardInstance(iid, FakeCard(), owner, Zone.HAND)


@pytest.fixture(scope="module")
def repo():
    if not _DB.exists():
        pytest.skip("swu.db not found")
    from swu.cards.repository import CardRepository
    return CardRepository(_DB)


def _action_state(repo, seed=1):
    """A clean ACTION-phase state (P0 to act) built from real vanilla decks.

    Uses an ability-less base (Capital City) so these tests isolate the bot's
    combat/tempo choices; Security Complex now carries a live Epic Action
    (SOR_19, gap-filling campaign) that would otherwise compete with an attack
    on a board cleared down to a single attacker."""
    from swu.cards.decklist import build_vanilla_deck
    da = build_vanilla_deck(repo, "Darth Vader", "Capital City")
    db = build_vanilla_deck(repo, "Luke Skywalker", "Administrator's Tower")
    s = run_through_setup(create_game("P0", da, "P1", db, seed=seed))
    s.active_player_index = 0
    s.passed_players = set()
    # Empty both hands so tests isolate the behaviour under examination.
    for ps in s.players:
        for ci in ps.hand:
            ci.zone = Zone.DECK
            ps.deck.append(ci)
        ps.hand.clear()
    return s


def _choose(bot, state):
    pid = (state.pending_decisions[-1].deciding_player_id
           if state.pending_decisions else state.active_player.player_id)
    return bot.choose_action(state.view_for(pid), legal_actions(state))


# ── combat ────────────────────────────────────────────────────────────────────

def test_takes_winning_trade(repo):
    """A 1/5 killing a 3/1 removes a real threat and survives untouched — worth
    far more than the single point of chip its power could put on the base."""
    s = _action_state(repo)
    s.players[0].ground_arena = [_unit("atk", "P0", 1, 5)]
    s.players[1].ground_arena = [_unit("victim", "P1", 3, 1)]
    bot = HeuristicBot("P0", seed=0)
    a = _choose(bot, s)
    assert isinstance(a, AttackWithUnit)
    assert a.attacker_id == "atk" and a.defender_id == "victim"


def test_prefers_base_over_a_marginal_trade(repo):
    """Damaging the base is the win condition and costs nothing — no damage comes
    back — so a big attacker chips the base rather than spending itself trading
    down into a small unit.

    This is a deliberate, measured stance, not an accident: with everything else
    held identical, weights that value base damage this way beat the previous
    (trade-first) weights 61.5% head-to-head over 800 paired games, and beat a
    deliberately control-tuned variant 60.2%.  See ``scripts/bot_arena.py``.
    """
    s = _action_state(repo)
    s.players[0].ground_arena = [_unit("atk", "P0", 4, 4)]
    s.players[1].ground_arena = [_unit("chaff", "P1", 2, 2)]
    bot = HeuristicBot("P0", seed=0)
    a = _choose(bot, s)
    assert isinstance(a, AttackWithUnit)
    assert a.defender_id is None


def test_overwhelm_spill_counts_toward_lethal(repo):
    """Overwhelm carries damage past the defender onto the base, so a lethal line
    that runs *through* a blocker must be seen as lethal."""
    s = _action_state(repo)
    s.players[0].ground_arena = [
        _unit("big", "P0", 9, 9, keywords=("Overwhelm",))]
    s.players[1].ground_arena = [_unit("blocker", "P1", 1, 2)]
    base = s.players[1].base_instance
    base.damage = base.effective_hp() - 5   # 5 left; 9 power - 2 HP = 7 spill
    bot = HeuristicBot("P0", seed=0)
    a = _choose(bot, s)
    assert isinstance(a, AttackWithUnit)
    assert a.defender_id == "blocker"        # through the blocker, not around it


def test_raid_counts_toward_attack_power(repo):
    """Raid is a while-attacking bonus the standing stat line does not show; the
    bot must attack with the number it will actually hit for."""
    from swu.players.heuristic_bot import _attack_power
    from swu.engine.views import CardView

    def cv(power, raid):
        return CardView(
            instance_id="u", card_id=1, card_name="u", card_type="Unit",
            owner_id="P0", zone="GROUND_ARENA", exhausted=False, damage=0,
            face_down=False, deployed=False, epic_action_spent=False,
            effective_power=power, effective_hp=3, attached_upgrades=[],
            keywords=["Raid"] if raid else [],
            keyword_values={"Raid": raid} if raid else {},
        )

    assert _attack_power(cv(3, 0)) == 3
    assert _attack_power(cv(3, 2)) == 5


def test_avoids_losing_trade_prefers_base(repo):
    """A 2/2 into a 5/6 is a clear loss; chip the base instead."""
    s = _action_state(repo)
    s.players[0].ground_arena = [_unit("atk", "P0", 2, 2)]
    s.players[1].ground_arena = [_unit("big", "P1", 5, 6)]
    bot = HeuristicBot("P0", seed=0)
    a = _choose(bot, s)
    assert isinstance(a, AttackWithUnit)
    assert a.defender_id is None  # attacked the base, not the losing trade


def test_takes_lethal_on_base(repo):
    """When a single attacker's power meets the base's remaining HP, take it."""
    s = _action_state(repo)
    atk = _unit("atk", "P0", 5, 5)
    s.players[0].ground_arena = [atk]
    # Also offer a juicy trade to prove lethal outranks everything.
    s.players[1].ground_arena = [_unit("victim", "P1", 1, 1)]
    base = s.players[1].base_instance
    base.damage = base.effective_hp() - 5
    bot = HeuristicBot("P0", seed=0)
    a = _choose(bot, s)
    assert isinstance(a, AttackWithUnit) and a.defender_id is None


def test_respects_sentinel_only_targets_sentinel(repo):
    """With an enemy Sentinel up, the bot may only attack the Sentinel — and it
    does (engine enforces legality; the bot makes a legal, sensible choice)."""
    s = _action_state(repo)
    s.players[0].ground_arena = [_unit("atk", "P0", 3, 3)]
    s.players[1].ground_arena = [
        _unit("sentinel", "P1", 2, 5, keywords=("Sentinel",)),
        _unit("squishy", "P1", 1, 1),
    ]
    bot = HeuristicBot("P0", seed=0)
    a = _choose(bot, s)
    if isinstance(a, AttackWithUnit):
        assert a.defender_id == "sentinel"  # cannot hit base or the squishy


# ── leader deploy ──────────────────────────────────────────────────────────────

def test_deploys_leader_when_sensible(repo):
    """Threshold met on round 2+ with a clear board: deploy the leader."""
    s = _action_state(repo)
    s.round_number = 3
    # Give plenty of resources so the leader's deploy threshold is met.
    leftover = s.players[0].deck[:12]
    for ci in leftover:
        ci.zone = Zone.RESOURCES
        ci.exhausted = False
        ci.face_down = True
    s.players[0].deck = s.players[0].deck[12:]
    s.players[0].resources.extend(leftover)
    assert any(isinstance(a, DeployLeader) for a in legal_actions(s)), \
        "precondition: DeployLeader should be legal"
    bot = HeuristicBot("P0", seed=0)
    a = _choose(bot, s)
    assert isinstance(a, DeployLeader)


# ── resourcing ──────────────────────────────────────────────────────────────────

def test_resources_least_useful_card(repo):
    """During setup resourcing, give up the expensive non-unit over a cheap
    unit we want to keep on curve."""
    from swu.cards.decklist import build_vanilla_deck
    da = build_vanilla_deck(repo, "Darth Vader", "Security Complex")
    db = build_vanilla_deck(repo, "Luke Skywalker", "Administrator's Tower")
    s = create_game("P0", da, "P1", db, seed=5)
    # Force SETUP_RESOURCES with a controlled hand.
    s.phase = Phase.SETUP_RESOURCES
    s.active_player_index = 0
    ps = s.players[0]
    for ci in ps.hand:
        ci.zone = Zone.DECK
    ps.deck.extend(ps.hand)
    ps.hand.clear()
    cheap = _hand_card("cheap_unit", "P0", cost=1, ctype="Unit")
    pricey = _hand_card("pricey_event", "P0", cost=6, ctype="Event")
    ps.hand.extend([cheap, pricey])
    bot = HeuristicBot("P0", seed=0)
    a = _choose(bot, s)
    assert isinstance(a, ResourceCard)
    assert a.instance_id == "pricey_event"  # kept the cheap unit


# ── mulligan ────────────────────────────────────────────────────────────────────

def _mulligan_state(repo, hand_cards, seed=7):
    from swu.cards.decklist import build_vanilla_deck
    da = build_vanilla_deck(repo, "Darth Vader", "Security Complex")
    db = build_vanilla_deck(repo, "Luke Skywalker", "Administrator's Tower")
    s = create_game("P0", da, "P1", db, seed=seed)  # starts in SETUP_MULLIGAN
    ps = s.players[0]
    for ci in ps.hand:
        ci.zone = Zone.DECK
    ps.deck.extend(ps.hand)
    ps.hand.clear()
    ps.hand.extend(hand_cards)
    s.active_player_index = 0
    return s


def test_mulligan_keeps_playable_curve(repo):
    hand = [
        _hand_card("u1", "P0", cost=1, ctype="Unit"),
        _hand_card("u2", "P0", cost=2, ctype="Unit"),
        _hand_card("u3", "P0", cost=3, ctype="Unit"),
    ]
    s = _mulligan_state(repo, hand)
    bot = HeuristicBot("P0", seed=0)
    assert isinstance(_choose(bot, s), KeepHand)


def test_mulligan_redraws_clog(repo):
    hand = [
        _hand_card("e1", "P0", cost=6, ctype="Event"),
        _hand_card("e2", "P0", cost=7, ctype="Event"),
        _hand_card("u1", "P0", cost=8, ctype="Unit"),
    ]
    s = _mulligan_state(repo, hand)
    bot = HeuristicBot("P0", seed=0)
    assert isinstance(_choose(bot, s), TakeMultiligan)


# ── target selection (a pending decision) ──────────────────────────────────────

def test_targets_highest_value_enemy(repo):
    """Given a resolve_effects target choice over enemy units, the bot spends it
    on the most valuable enemy."""
    s = _action_state(repo)
    s.players[1].ground_arena = [
        _unit("weak", "P1", 1, 1),
        _unit("strong", "P1", 6, 6),
    ]
    # Hand-craft a resolve_effects decision offering both as ChooseTarget options
    # by exercising the engine's own action surface would require a real card; we
    # instead assert the bot's preference among constructed ChooseTarget actions.
    view = s.view_for("P0")
    legal = [ChooseTarget("weak"), ChooseTarget("strong")]
    # Wrap so the bot sees a pending decision context (kind set to resolve_effects
    # only matters for dispatch; the action set is what drives the choice).
    bot = HeuristicBot("P0", seed=0)
    a = bot.choose_action(view, legal)
    assert isinstance(a, ChooseTarget) and a.target_id == "strong"


def test_hard_targeting_prefers_threat(repo):
    """sharp_targeting (HARD) favours the highest-power enemy threat."""
    s = _action_state(repo)
    s.players[1].ground_arena = [
        _unit("tanky", "P1", 1, 9),   # high value by stats, low threat
        _unit("threat", "P1", 7, 2),  # biggest attacker
    ]
    view = s.view_for("P0")
    legal = [ChooseTarget("tanky"), ChooseTarget("threat")]
    hard = HeuristicBot("P0", seed=0, sharp_targeting=True)
    assert hard.choose_action(view, legal).target_id == "threat"


# ── robustness: always returns a legal action, never raises ─────────────────────

def test_full_game_every_choice_legal(repo):
    """Drive a full heuristic-vs-heuristic game; every choice must be legal and
    no decision may raise (the property the 6B fallback relies on)."""
    require_db()  # engine token lookup / from_json needs the card database
    from swu.cards.decklist import build_vanilla_deck
    da = build_vanilla_deck(repo, "Darth Vader", "Security Complex")
    db = build_vanilla_deck(repo, "Luke Skywalker", "Administrator's Tower")
    for seed in range(10):
        s = create_game("P0", da, "P1", db, seed=seed)
        bots = {"P0": HeuristicBot("P0", seed=seed),
                "P1": HeuristicBot("P1", seed=seed + 1)}
        n = 0
        while not s.is_terminal() and n < 3000:
            legal = legal_actions(s)
            pid = (s.pending_decisions[-1].deciding_player_id
                   if s.pending_decisions else s.active_player.player_id)
            chosen = bots[pid].choose_action(s.view_for(pid), legal)
            assert chosen in legal
            s = apply(s, chosen)
            n += 1
        assert s.is_terminal(), f"game seed {seed} did not finish"


def test_easy_never_raises_and_returns_legal(repo):
    """Easy (high mistake rate) still only ever returns legal actions."""
    require_db()  # engine token lookup / from_json needs the card database
    from swu.cards.decklist import build_vanilla_deck
    da = build_vanilla_deck(repo, "Darth Vader", "Security Complex")
    db = build_vanilla_deck(repo, "Luke Skywalker", "Administrator's Tower")
    s = create_game("P0", da, "P1", db, seed=3)
    bots = {
        "P0": make_opponent(Difficulty.EASY, player_id="P0", seed=3),
        "P1": make_opponent(Difficulty.EASY, player_id="P1", seed=4),
    }
    n = 0
    while not s.is_terminal() and n < 3000:
        legal = legal_actions(s)
        pid = (s.pending_decisions[-1].deciding_player_id
               if s.pending_decisions else s.active_player.player_id)
        chosen = bots[pid].choose_action(s.view_for(pid), legal)
        assert chosen in legal
        s = apply(s, chosen)
        n += 1
    assert s.is_terminal()


# ── factory ─────────────────────────────────────────────────────────────────────

def test_factory_maps_difficulties():
    # Phase 6B: EASY stays a pure heuristic; NORMAL/HARD are LLM players backed
    # by a heuristic fallback (casual vs competitive style, with sharp targeting
    # on the Hard fallback).
    from swu.players.llm_player import LLMPlayer, Style

    easy = make_opponent(Difficulty.EASY, player_id="bot", seed=1)
    normal = make_opponent(Difficulty.NORMAL, player_id="bot", seed=1)
    hard = make_opponent("hard", player_id="bot", seed=1)  # string coercion

    assert isinstance(easy, HeuristicBot) and easy.mistake_rate > 0

    assert isinstance(normal, LLMPlayer) and normal.style is Style.CASUAL
    assert isinstance(normal.fallback, HeuristicBot)
    assert normal.fallback.mistake_rate == 0 and normal.fallback.sharp_targeting is False

    assert isinstance(hard, LLMPlayer) and hard.style is Style.COMPETITIVE
    assert isinstance(hard.fallback, HeuristicBot) and hard.fallback.sharp_targeting is True


def test_difficulty_coerce_defaults_to_normal():
    assert Difficulty.coerce(None) is Difficulty.NORMAL
    assert Difficulty.coerce("garbage") is Difficulty.NORMAL
    assert Difficulty.coerce("EASY") is Difficulty.EASY
    assert Difficulty.coerce(Difficulty.HARD) is Difficulty.HARD
    # Saves written before the fix stored str(Difficulty.HARD).
    assert Difficulty.coerce("Difficulty.HARD") is Difficulty.HARD


def test_seeded_heuristic_is_deterministic(repo):
    """Same seed + same decks → identical game (the determinism contract)."""
    require_db()  # engine token lookup / from_json needs the card database
    from swu.cards.decklist import build_vanilla_deck

    def play():
        da = build_vanilla_deck(repo, "Darth Vader", "Security Complex")
        db = build_vanilla_deck(repo, "Luke Skywalker", "Administrator's Tower")
        s = create_game("P0", da, "P1", db, seed=99)
        bots = {"P0": HeuristicBot("P0", seed=99), "P1": HeuristicBot("P1", seed=100)}
        n = 0
        while not s.is_terminal() and n < 3000:
            pid = (s.pending_decisions[-1].deciding_player_id
                   if s.pending_decisions else s.active_player.player_id)
            s = apply(s, bots[pid].choose_action(s.view_for(pid), legal_actions(s)))
            n += 1
        return s.winner, n

    assert play() == play()


# ── Don't-buff-the-opponent + Easy-mistake safety ─────────────────────────────

from swu.engine.views import CardView, PlayerView, PlayerZoneView
from swu.engine.actions import PlayCard
from swu.players.heuristic_bot import (
    _upgrade_helps_host, _is_enemy_buff, W_PASS,
)


def _cv(iid, ctype="Unit", *, power=2, hp=2, up=0, uhp=0, owner="P0",
        sc="", cn=""):
    return CardView(
        instance_id=iid, card_id=1, card_name=iid, card_type=ctype,
        owner_id=owner, zone="GROUND_ARENA", exhausted=False, damage=0,
        face_down=False, deployed=False, epic_action_spent=False,
        effective_power=power, effective_hp=hp, attached_upgrades=[],
        cost=2, keywords=[], upgrade_power=up, upgrade_hp=uhp,
        set_code=sc, card_number=cn,
    )


def _zone(pid, **over):
    base = dict(player_id=pid, deck_count=0, hand=[], hand_count=0, discard=[],
                resources=[], resource_count=0, available_resources=3, credits=0,
                ground_arena=[], space_arena=[], base_zone=[], is_eliminated=False)
    base.update(over)
    return PlayerZoneView(**base)


def _view(my, opp):
    return PlayerView(
        viewer_id="P0", phase="ACTION", round_number=2, active_player_id="P0",
        initiative_holder_id="P0", my=my, opponent=opp,
        event_log_tail=[], pending_decisions=[],
    )


def test_upgrade_helps_host_reads_stats_and_registry():
    """Who an upgrade wants underneath it, judged from stats AND the registry.

    A stat line alone is not enough: an upgrade can grant a keyword, a trait or a
    whole ability with no stat change at all, and reading only stats classified
    every one of those as safe to hand to the opponent.
    """
    import swu.cards  # noqa: F401  (force ability registrations to load)
    # Stats alone, no registered abilities.
    assert _upgrade_helps_host(_cv("u", "Upgrade", up=2, uhp=2))
    assert _upgrade_helps_host(_cv("u", "Upgrade", up=0, uhp=3))
    assert not _upgrade_helps_host(_cv("u", "Upgrade", up=-2, uhp=-2))
    # Unknown and statless: assume it helps its host, so we hold it rather than
    # gift it — the safe way to be wrong.
    assert _upgrade_helps_host(_cv("u", "Upgrade", up=0, uhp=0))
    # Statless but a real gift: Squad Support TWI_122 (+1/+1 per Trooper).
    assert _upgrade_helps_host(
        _cv("u", "Upgrade", up=0, uhp=0, sc="TWI", cn="122"))
    # Negative stats but a real gift: Nowhere to Hide ASH_198 grants Sentinel,
    # so it belongs on a friendly despite the -2 power.
    assert _upgrade_helps_host(
        _cv("u", "Upgrade", up=-2, uhp=0, sc="ASH", cn="198"))
    # A Bounty pays the host's OPPONENT — it wants an enemy host.
    assert not _upgrade_helps_host(
        _cv("u", "Upgrade", up=0, uhp=0, sc="SHD", cn="68"))  # Public Enemy
    # A pure drawback wants an enemy host too.
    assert not _upgrade_helps_host(
        _cv("u", "Upgrade", up=0, uhp=0, sc="SHD", cn="193"))  # Frozen in Carbonite


def test_enemy_buff_scored_below_pass():
    """A beneficial upgrade on an enemy unit scores below Pass (never chosen);
    the same upgrade on a friendly unit scores positively."""
    bot = HeuristicBot("P0", seed=1)
    idx = {
        "enemy": (_cv("enemy", owner="P1"), "opp"),
        "ally": (_cv("ally", owner="P0"), "my"),
        "upg": (_cv("upg", "Upgrade", up=2, uhp=2), "my"),
    }
    enemy_play = PlayCard("upg", upgrade_target_id="enemy")
    friendly_play = PlayCard("upg", upgrade_target_id="ally")
    assert bot._score_play_card(enemy_play, idx) < W_PASS
    assert bot._score_play_card(friendly_play, idx) > W_PASS


def test_downside_upgrade_on_enemy_stays_playable():
    """A net-negative ("downside") upgrade on an enemy is a legitimate play and is
    not penalised below Pass."""
    bot = HeuristicBot("P0", seed=1)
    idx = {
        "enemy": (_cv("enemy", owner="P1"), "opp"),
        "upg": (_cv("upg", "Upgrade", up=-2, uhp=-2), "my"),
    }
    play = PlayCard("upg", upgrade_target_id="enemy")
    assert bot._score_play_card(play, idx) > W_PASS


def test_is_enemy_buff_helper():
    idx = {
        "enemy": (_cv("enemy", owner="P1"), "opp"),
        "ally": (_cv("ally", owner="P0"), "my"),
        "buff": (_cv("buff", "Upgrade", up=1, uhp=1), "my"),
        "downside": (_cv("downside", "Upgrade", up=-1, uhp=0), "my"),
    }
    assert _is_enemy_buff(PlayCard("buff", upgrade_target_id="enemy"), idx)
    assert not _is_enemy_buff(PlayCard("buff", upgrade_target_id="ally"), idx)
    assert not _is_enemy_buff(PlayCard("downside", upgrade_target_id="enemy"), idx)
    assert not _is_enemy_buff(PlayCard("ally"), idx)  # not an upgrade


def test_upgrade_grants_bounty_helper():
    """The bounty signature is detected from the registry (a GrantedAbility
    wrapping a WhenDefeated), not from stats — Public Enemy SHD_68 is a Bounty,
    a plain stat upgrade is not."""
    import swu.cards  # noqa: F401  (force ability registrations to load)
    from swu.players.heuristic_bot import _upgrade_grants_bounty
    assert _upgrade_grants_bounty("SHD", "68")    # Public Enemy
    assert _upgrade_grants_bounty("SHD", "261")   # Rich Reward
    assert not _upgrade_grants_bounty("SHD", "175")  # Armed to the Teeth (OnAttack grant)
    assert not _upgrade_grants_bounty("", "")


def test_bounty_upgrade_prefers_enemy_host():
    """A Bounty upgrade (statless, GrantedAbility(WhenDefeated)) belongs on an
    ENEMY unit: an enemy host scores positively, a friendly host below Pass — the
    inverse of a normal buff."""
    import swu.cards  # noqa: F401
    bot = HeuristicBot("P0", seed=1)
    idx = {
        "enemy": (_cv("enemy", owner="P1"), "opp"),
        "ally": (_cv("ally", owner="P0"), "my"),
        # Public Enemy SHD_68 — statless Bounty upgrade.
        "bounty": (_cv("bounty", "Upgrade", up=0, uhp=0, sc="SHD", cn="68"), "my"),
    }
    on_enemy = PlayCard("bounty", upgrade_target_id="enemy")
    on_friendly = PlayCard("bounty", upgrade_target_id="ally")
    assert bot._score_play_card(on_enemy, idx) > W_PASS
    assert bot._score_play_card(on_friendly, idx) < W_PASS


def test_ability_grant_upgrade_stays_on_friendly():
    """A statless *ability-granting* upgrade (not a Bounty) still belongs on a
    friendly host — it must not be mistaken for a Bounty and pushed onto an enemy.
    Armed to the Teeth SHD_175 grants an OnAttack buff, so a friendly host is
    playable and an enemy host is not preferred over it."""
    import swu.cards  # noqa: F401
    bot = HeuristicBot("P0", seed=1)
    idx = {
        "ally": (_cv("ally", owner="P0"), "my"),
        # SHD_175 carries a printed +2/0, so model it as a beneficial upgrade.
        "upg": (_cv("upg", "Upgrade", up=2, uhp=0, sc="SHD", cn="175"), "my"),
    }
    on_friendly = PlayCard("upg", upgrade_target_id="ally")
    assert bot._score_play_card(on_friendly, idx) > W_PASS


def test_easy_mistake_never_self_targets_subdecision():
    """Even at mistake_rate=1.0, a forced sub-decision (no Pass) is resolved
    sensibly — the Easy bot never randomly aims damage at its own base."""
    bot = HeuristicBot("P0", seed=7, mistake_rate=1.0)
    my = _zone("P0", base_zone=[_cv("mybase", "Base", power=0, hp=30, owner="P0")])
    opp = _zone("P1", base_zone=[_cv("oppbase", "Base", power=0, hp=30, owner="P1")])
    view = _view(my, opp)
    legal = [ChooseTarget("mybase"), ChooseTarget("oppbase")]
    for _ in range(50):
        assert bot.choose_action(view, legal).target_id == "oppbase"


def test_easy_mistake_excludes_enemy_buff_from_random_pool():
    """At mistake_rate=1.0 the random main-phase pool excludes buffing an enemy,
    so the bot passes rather than handing the opponent a free upgrade."""
    bot = HeuristicBot("P0", seed=3, mistake_rate=1.0)
    my = _zone("P0", hand=[_cv("upg", "Upgrade", up=2, uhp=2, owner="P0")])
    opp = _zone("P1", ground_arena=[_cv("enemy", owner="P1")])
    view = _view(my, opp)
    legal = [Pass(), PlayCard("upg", upgrade_target_id="enemy")]
    for _ in range(50):
        assert isinstance(bot.choose_action(view, legal), Pass)


def test_easy_mistake_never_suicides_a_unit(repo):
    """Easy's blunder branch plays a *worse* line, never a self-destructive one.

    At mistake_rate=1.0 with a 2/2 facing a 5/6, throwing the 2/2 in kills it for
    nothing while the enemy base sits there attackable.  The old uniform-random
    pool did that about once every two games (``scripts/bot_blunders.py``); the
    pool now excludes it entirely.
    """
    s = _action_state(repo)
    s.players[0].ground_arena = [_unit("atk", "P0", 2, 2)]
    s.players[1].ground_arena = [_unit("big", "P1", 5, 6)]
    for seed in range(25):
        bot = HeuristicBot("P0", seed=seed, mistake_rate=1.0)
        a = _choose(bot, s)
        if isinstance(a, AttackWithUnit):
            assert a.defender_id is None, "Easy threw its unit away"


def test_easy_mistake_is_suboptimal_not_optimal(repo):
    """…but it is still a MISTAKE: over many seeds Easy must sometimes pick
    something other than the line the Normal bot would take, or the difficulty
    levels would be identical."""
    s = _action_state(repo)
    s.players[0].ground_arena = [_unit("a1", "P0", 4, 4), _unit("a2", "P0", 1, 1)]
    s.players[1].ground_arena = [_unit("chaff", "P1", 1, 1)]
    best = _choose(HeuristicBot("P0", seed=0), s)
    chosen = {repr(_choose(HeuristicBot("P0", seed=i, mistake_rate=1.0), s))
              for i in range(30)}
    assert len(chosen) > 1, "Easy always played the same move"
    assert chosen != {repr(best)}, "Easy never deviated from the best line"


# ── Decline abilities that could only hit our own cards ───────────────────────

import swu.cards  # noqa: E402,F401  (force ability registrations to load)
from swu.players.heuristic_bot import (  # noqa: E402
    _ability_forces_self_harm, _ability_is_pointless, _card_index,
)
from swu.engine.actions import UseAbility, AcceptTrigger, DeclineTrigger  # noqa: E402
from swu.engine.views import PendingDecisionView  # noqa: E402


def _vader_cv(iid="vader"):
    cv = _cv(iid, "Leader", owner="P0")
    cv.set_code, cv.card_number = "SOR", "10"  # Darth Vader
    return cv


def test_forces_self_harm_vader_unit_damage_only_friendly():
    """Vader's "deal 1 to a unit" with a friendly unit but no enemy unit → forced
    self-harm."""
    my = _zone("P0", ground_arena=[_cv("ally", owner="P0")],
               base_zone=[_cv("mybase", "Base", hp=30, owner="P0")])
    opp = _zone("P1", base_zone=[_cv("oppbase", "Base", hp=30, owner="P1")])
    assert _ability_forces_self_harm("SOR", "10", 0, "vader", _view(my, opp))


def test_no_self_harm_when_enemy_unit_present():
    my = _zone("P0", ground_arena=[_cv("ally", owner="P0")],
               base_zone=[_cv("mybase", "Base", hp=30, owner="P0")])
    opp = _zone("P1", ground_arena=[_cv("enemy", owner="P1")],
                base_zone=[_cv("oppbase", "Base", hp=30, owner="P1")])
    assert not _ability_forces_self_harm("SOR", "10", 0, "vader", _view(my, opp))


def test_no_self_harm_when_no_unit_at_all():
    """No friendly unit either → the unit effect simply fizzles, not self-harm."""
    my = _zone("P0", base_zone=[_cv("mybase", "Base", hp=30, owner="P0")])
    opp = _zone("P1", base_zone=[_cv("oppbase", "Base", hp=30, owner="P1")])
    assert not _ability_forces_self_harm("SOR", "10", 0, "vader", _view(my, opp))


def test_use_ability_scored_below_pass_when_only_self_harm():
    bot = HeuristicBot("P0", seed=1)
    vader = _vader_cv()
    my = _zone("P0", ground_arena=[_cv("ally", owner="P0")],
               base_zone=[_cv("mybase", "Base", hp=30, owner="P0"), vader])
    opp = _zone("P1", base_zone=[_cv("oppbase", "Base", hp=30, owner="P1")])
    view = _view(my, opp)
    idx = _card_index(view)
    score = bot._score_main_action(UseAbility("vader", 0), view, idx, base_remaining=30)
    assert score < W_PASS


def test_use_ability_scored_normally_when_enemy_target_exists():
    bot = HeuristicBot("P0", seed=1)
    vader = _vader_cv()
    my = _zone("P0", base_zone=[_cv("mybase", "Base", hp=30, owner="P0"), vader])
    opp = _zone("P1", ground_arena=[_cv("enemy", owner="P1")],
                base_zone=[_cv("oppbase", "Base", hp=30, owner="P1")])
    view = _view(my, opp)
    idx = _card_index(view)
    score = bot._score_main_action(UseAbility("vader", 0), view, idx, base_remaining=30)
    assert score == pytest.approx(45.0)  # W_USE_ABILITY


# ── Don't pay a cost for a no-op (generalised self-harm guard) ────────────────

def _grogu_cv(iid="grogu"):
    cv = _cv(iid, "Unit", owner="P0")
    cv.set_code, cv.card_number = "SHD", "196"  # Action [Exhaust]: Exhaust an enemy unit
    return cv


def test_pointless_when_cost_bearing_ability_has_no_enemy_target():
    """Grogu's "Action [Exhaust]: Exhaust an enemy unit" with no enemy unit on the
    board would only exhaust Grogu for nothing → pointless."""
    my = _zone("P0", ground_arena=[_grogu_cv()],
               base_zone=[_cv("mybase", "Base", hp=30, owner="P0")])
    opp = _zone("P1", base_zone=[_cv("oppbase", "Base", hp=30, owner="P1")])
    assert _ability_is_pointless("SHD", "196", 0, "grogu", _view(my, opp))


def test_not_pointless_when_enemy_target_exists():
    my = _zone("P0", ground_arena=[_grogu_cv()],
               base_zone=[_cv("mybase", "Base", hp=30, owner="P0")])
    opp = _zone("P1", ground_arena=[_cv("enemy", owner="P1")],
                base_zone=[_cv("oppbase", "Base", hp=30, owner="P1")])
    assert not _ability_is_pointless("SHD", "196", 0, "grogu", _view(my, opp))


def test_grogu_use_ability_scored_below_pass_when_no_enemy_unit():
    """The bot must not pay Grogu's exhaust when there is nothing to exhaust."""
    bot = HeuristicBot("P0", seed=1)
    my = _zone("P0", ground_arena=[_grogu_cv()],
               base_zone=[_cv("mybase", "Base", hp=30, owner="P0")])
    opp = _zone("P1", base_zone=[_cv("oppbase", "Base", hp=30, owner="P1")])
    view = _view(my, opp)
    idx = _card_index(view)
    score = bot._score_main_action(UseAbility("grogu", 0), view, idx, base_remaining=30)
    assert score < W_PASS


def test_grogu_use_ability_scored_normally_when_enemy_unit_present():
    bot = HeuristicBot("P0", seed=1)
    my = _zone("P0", ground_arena=[_grogu_cv()],
               base_zone=[_cv("mybase", "Base", hp=30, owner="P0")])
    opp = _zone("P1", ground_arena=[_cv("enemy", owner="P1")],
                base_zone=[_cv("oppbase", "Base", hp=30, owner="P1")])
    view = _view(my, opp)
    idx = _card_index(view)
    score = bot._score_main_action(UseAbility("grogu", 0), view, idx, base_remaining=30)
    assert score == pytest.approx(45.0)  # W_USE_ABILITY


def test_opaque_custom_effect_ability_is_no_opinion():
    """Moff Gideon's undeployed Action is an opaque CustomEffect adapter — the bot
    cannot judge it from the view, so the pointless guard yields no opinion (the
    engine `condition` gate is what keeps it off the menu when it would fizzle)."""
    gideon = _cv("gideon", "Leader", owner="P0")
    gideon.set_code, gideon.card_number = "SHD", "7"
    my = _zone("P0", base_zone=[_cv("mybase", "Base", hp=30, owner="P0"), gideon])
    opp = _zone("P1", base_zone=[_cv("oppbase", "Base", hp=30, owner="P1")])
    assert not _ability_is_pointless("SHD", "7", 0, "gideon", _view(my, opp))


def _trigger_view(my, opp, ability_idx):
    view = _view(my, opp)
    view.pending_decisions = [PendingDecisionView(
        deciding_player_id="P0", kind="trigger_option",
        context={"set_code": "SOR", "card_number": "10",
                 "ability_idx": ability_idx, "source_id": "vader"},
        is_mine=True,
    )]
    return view


def test_declines_optional_trigger_that_only_self_harms():
    """Vader's deployed On-Attack "deal 2 to a unit" with no enemy unit → decline."""
    bot = HeuristicBot("P0", seed=1)
    my = _zone("P0", ground_arena=[_cv("ally", owner="P0")],
               base_zone=[_cv("mybase", "Base", hp=30, owner="P0")])
    opp = _zone("P1", base_zone=[_cv("oppbase", "Base", hp=30, owner="P1")])
    view = _trigger_view(my, opp, ability_idx=1)
    legal = [AcceptTrigger("vader", "Darth Vader"), DeclineTrigger("vader", "Darth Vader")]
    assert isinstance(bot.choose_action(view, legal), DeclineTrigger)


def test_accepts_optional_trigger_when_enemy_target_exists():
    bot = HeuristicBot("P0", seed=1)
    my = _zone("P0", base_zone=[_cv("mybase", "Base", hp=30, owner="P0")])
    opp = _zone("P1", ground_arena=[_cv("enemy", owner="P1")],
                base_zone=[_cv("oppbase", "Base", hp=30, owner="P1")])
    view = _trigger_view(my, opp, ability_idx=1)
    legal = [AcceptTrigger("vader", "Darth Vader"), DeclineTrigger("vader", "Darth Vader")]
    assert isinstance(bot.choose_action(view, legal), AcceptTrigger)
