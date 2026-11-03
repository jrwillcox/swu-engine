"""
SOR (Spark of Rebellion) starter deck card ability tests.

One test per card with a text ability.  Cards that are pure keywords
(Sentinel, Ambush, etc.) are covered by test_keywords.py and omitted here.

Test strategy: load real card defs from the DB, build minimal game states,
and exercise abilities either via direct event firing or via PlayCard/
apply() actions.
"""
from __future__ import annotations

import uuid

import pytest

# ── DB-backed helpers ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def repo():
    # Every per-set card test module imports this fixture, so the skip-on-missing
    # -database behaviour of require_db() is what keeps a fresh clone green.
    from tests.dbpath import require_db
    from swu.cards.repository import CardRepository
    return CardRepository(require_db())


def _get_card(repo, set_code: str, card_number: str):
    with repo._con() as con:
        num = str(int(card_number))
        # (set_code, card_number) is NOT unique: low numbers are shared by a
        # Leader and a same-numbered Token (SEC_2 = Jabba + a Shield token).  Order
        # non-tokens first so this generic helper always yields the real card —
        # it used to depend on insertion order, and the type-filtered helpers
        # further down exist for tests that do want the token.
        order = " ORDER BY (type LIKE '%Token%') ASC, id ASC"
        row = con.execute(
            "SELECT * FROM cards WHERE set_code=? AND card_number=?" + order,
            (set_code, num),
        ).fetchone()
        if row is None:
            for pad in (f"{int(num):03d}", f"{int(num):04d}"):
                row = con.execute(
                    "SELECT * FROM cards WHERE set_code=? AND card_number=?" + order,
                    (set_code, pad),
                ).fetchone()
                if row:
                    break
        from tests.dbpath import using_fixture
        # On the small fixture database most cards are simply absent, and a test
        # for a card that isn't there is a skip, not a failure.  (With the real
        # corpus a missing card IS a failure: the registry and the DB have drifted,
        # which is exactly what this used to catch.)  A token row standing alone at
        # a colliding number counts as absent: the fixture carries every token, so
        # matching one here means the real card is the one that's missing.
        if using_fixture() and row is not None and "Token" in (row["type"] or ""):
            row = None
        if row is None:
            if using_fixture():
                pytest.skip(f"{set_code}_{card_number} is not in the fixture DB")
            raise KeyError(f"Card not found: {set_code}_{card_number}")
        return repo._hydrate(con, row)


# ── Game-state helpers ────────────────────────────────────────────────────────

def _make_state(include_bases: bool = True):
    """Minimal ACTION-phase state with two empty-arena players."""
    from swu.engine.state import GameState, PlayerState, CardInstance, Zone, Phase
    import uuid as _u

    def _base_ci(name, pid):
        from swu.cards.models import Base
        bdef = Base(
            id=abs(hash(name)) % 99999, card_uid=None, set_code="TST", set_name="T",
            card_number="99", name=name, subtitle=None, type="Base", rarity="Common",
            is_unique=False, artist=None, text=None, text_styled=None, rules=None,
            rules_styled=None, aspects=(), keywords=(), traits=(), arenas=(),
            image_front_url=None, image_back_url=None,
            image_front_path=None, image_back_path=None,
            hp=30, epic_action=None,
        )
        return CardInstance(
            instance_id=f"{pid}_base_{_u.uuid4().hex[:4]}",
            card_def=bdef, owner_id=pid, zone=Zone.BASE_ZONE,
        )

    ps0 = PlayerState(player_id="P0")
    ps1 = PlayerState(player_id="P1")
    if include_bases:
        ps0.base_zone.append(_base_ci("Base A", "P0"))
        ps1.base_zone.append(_base_ci("Base B", "P1"))

    return GameState(
        players=[ps0, ps1],
        phase=Phase.ACTION,
        active_player_index=0,
        round_number=1,
        initiative_holder=0,
    )


def _place(state, owner_id: str, card_def, arena: str = "ground"):
    """Place card_def directly into arena. Returns the CardInstance."""
    from swu.engine.state import CardInstance, Zone
    zone = Zone.GROUND_ARENA if arena == "ground" else Zone.SPACE_ARENA
    ci = CardInstance(
        instance_id=f"{owner_id}_{uuid.uuid4().hex[:6]}",
        card_def=card_def, owner_id=owner_id, zone=zone,
    )
    ps = state.player_by_id(owner_id)
    if arena == "ground":
        ps.ground_arena.append(ci)
    else:
        ps.space_arena.append(ci)
    return ci


def _fire_when_played(state, ci):
    """Fire a WhenPlayed trigger for ci as if it just entered play."""
    from swu.engine.events import UnitEntersPlay
    from swu.abilities.resolver import fire_triggered_abilities
    arena = "Ground" if ci.zone.name == "GROUND_ARENA" else "Space"
    evt = UnitEntersPlay(
        player_id=ci.owner_id,
        instance_id=ci.instance_id,
        card_name=ci.card_def.display_name,
        arena=arena,
    )
    state.event_log.append(evt)
    return fire_triggered_abilities(state, evt, after_all_player_idx=0)


def _fire_when_defeated(state, ci):
    """Fire a WhenDefeated trigger for ci."""
    from swu.engine.events import UnitDefeated
    from swu.abilities.resolver import fire_triggered_abilities
    evt = UnitDefeated(
        player_id=ci.owner_id,
        instance_id=ci.instance_id,
        card_name=ci.card_def.display_name,
    )
    state.event_log.append(evt)
    return fire_triggered_abilities(state, evt, after_all_player_idx=0)


def _defeat_and_fire(state, ci, controller_id):
    """Mimic ``_defeat_unit``'s trigger firing: pull ``ci`` from its arena (so it
    has left play, as during a real defeat), home it in the owner's discard, and
    fire ``UnitDefeated`` with the engine's event_ctx (``defeated_ci`` /
    ``defeated_id`` / ``defeated_controller_id``) so a self-WhenDefeated whose
    resolve_effects flow needs ``find_instance(source)`` finds it in discard."""
    from swu.engine.events import UnitDefeated
    from swu.abilities.resolver import fire_triggered_abilities
    from swu.engine.state import Zone
    ps = state.player_by_id(controller_id)
    for arena in (ps.ground_arena, ps.space_arena):
        if ci in arena:
            arena.remove(ci)
            break
    ci.zone = Zone.DISCARD
    ci.damage = 0
    owner = state.player_by_id(ci.owner_id)
    if all(ci.instance_id != c.instance_id for c in owner.discard):
        owner.discard.append(ci)
    evt = UnitDefeated(player_id=controller_id, instance_id=ci.instance_id,
                       card_name=ci.card_def.display_name)
    state.event_log.append(evt)
    ctx = {"defeated_id": ci.instance_id, "defeated_ci": ci,
           "defeated_controller_id": controller_id}
    return fire_triggered_abilities(state, evt, after_all_player_idx=0, event_ctx=ctx)


def _push_deck_top(state, owner_id, card_def):
    """Create a CardInstance for card_def and put it on top of owner's deck."""
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(
        instance_id=f"{owner_id}_deck_{uuid.uuid4().hex[:6]}",
        card_def=card_def, owner_id=owner_id, zone=Zone.DECK,
    )
    state.player_by_id(owner_id).deck.insert(0, ci)
    return ci


def _fire_on_attack(state, attacker_ci, defender_ci=None):
    """Fire an OnAttack / WhenAttacked trigger."""
    from swu.engine.events import AttackDeclared
    from swu.abilities.resolver import fire_triggered_abilities
    defender_id = defender_ci.instance_id if defender_ci else None
    defender_name = defender_ci.card_def.display_name if defender_ci else "Base"
    evt = AttackDeclared(
        attacker_player_id=attacker_ci.owner_id,
        attacker_instance_id=attacker_ci.instance_id,
        attacker_name=attacker_ci.card_def.display_name,
        defender_instance_id=defender_id,
        defender_name=defender_name,
    )
    state.event_log.append(evt)
    event_ctx = {
        "attacker_id": attacker_ci.instance_id,
        "defender_id": defender_id,
    }
    return fire_triggered_abilities(state, evt, after_all_player_idx=0, event_ctx=event_ctx)


def _fire_upgrade_played(state, upgrade_ci, host_ci):
    """Fire an UpgradePlayed trigger for upgrade_ci as if it was just attached.

    Mirrors actions.py `_attach_upgrade`: supplies event_ctx["attached_to_id"]
    so an upgrade's WhenPlayed ability can read its host.
    """
    from swu.engine.events import UpgradePlayed
    from swu.abilities.resolver import fire_triggered_abilities
    evt = UpgradePlayed(
        player_id=upgrade_ci.owner_id,
        instance_id=upgrade_ci.instance_id,
        card_name=upgrade_ci.card_def.display_name,
        attached_to_instance_id=host_ci.instance_id,
    )
    state.event_log.append(evt)
    after_idx = 1 - state.player_index(upgrade_ci.owner_id)
    return fire_triggered_abilities(
        state, evt, after_all_player_idx=after_idx,
        event_ctx={"attached_to_id": host_ci.instance_id},
    )


def _find_instance(state, instance_id: str):
    """Return the CardInstance with instance_id if it is in a unit arena, else None.

    Only the ground/space arenas count as "in play" — a defeated unit moved to
    discard returns None (state.find_instance() would still locate it there).
    """
    for ps in state.players:
        for ci in ps.ground_arena + ps.space_arena:
            if ci.instance_id == instance_id:
                return ci
    return None


def _give_resources(state, owner_id: str, count: int, repo=None):
    """Add `count` ready resources to a player (use a cheap dummy card def)."""
    from swu.engine.state import CardInstance, Zone
    ps = state.player_by_id(owner_id)
    # Use a minimal Base def as filler so it doesn't interact with abilities
    from swu.cards.models import Base
    dummy_def = Base(
        id=99990, card_uid=None, set_code="TST", set_name="T", card_number="RES",
        name="Resource", subtitle=None, type="Base", rarity="Common", is_unique=False,
        artist=None, text=None, text_styled=None, rules=None, rules_styled=None,
        aspects=(), keywords=(), traits=(), arenas=(), image_front_url=None,
        image_back_url=None, image_front_path=None, image_back_path=None,
        hp=0, epic_action=None,
    )
    for _ in range(count):
        res = CardInstance(
            instance_id=f"{owner_id}_res_{uuid.uuid4().hex[:4]}",
            card_def=dummy_def, owner_id=owner_id, zone=Zone.RESOURCES,
        )
        res.exhausted = False
        ps.resources.append(res)


def _experience_count(ci):
    from swu.engine.keywords import experience_on
    return experience_on(ci)


def _shield_count(ci):
    from swu.engine.keywords import shields_on
    return shields_on(ci)


# ── Ability registry smoke test ────────────────────────────────────────────────

class TestRegistrationSmoke:
    """Verify all expected SOR cards are registered."""

    @pytest.mark.parametrize("set_code,num", [
        ("SOR", "5"), ("SOR", "10"),    # leaders
        ("SOR", "59"), ("SOR", "45"), ("SOR", "242"), ("SOR", "244"),
        ("SOR", "196"), ("SOR", "48"), ("SOR", "49"), ("SOR", "241"),
        ("SOR", "74"), ("SOR", "218"), ("SOR", "222"), ("SOR", "78"),
        ("SOR", "79"), ("SOR", "226"), ("SOR", "230"), ("SOR", "84"),
        ("SOR", "132"), ("SOR", "231"), ("SOR", "86"), ("SOR", "172"),
        ("SOR", "233"), ("SOR", "234"), ("SOR", "136"), ("SOR", "53"),
    ])
    def test_registered(self, set_code, num):
        from swu.abilities.registry import get_abilities
        # Import to ensure registrations loaded
        import swu.cards.sor  # noqa: F401
        specs = get_abilities(set_code, num)
        assert isinstance(specs, list), f"Expected list for {set_code}_{num}"


# ── REBEL UNITS ──────────────────────────────────────────────────────────────

class TestSurgicalDroid:
    def test_on_attack_heal_is_optional(self, repo):
        """2-1B Surgical Droid On Attack: optional heal trigger fires."""
        droid = _get_card(repo, "SOR", "59")
        friendly = _get_card(repo, "SOR", "46")  # Consular Security Force
        state = _make_state()
        droid_ci = _place(state, "P0", droid, "ground")
        friendly_ci = _place(state, "P0", friendly, "ground")
        friendly_ci.damage = 2  # so there's something to heal

        state = _fire_on_attack(state, droid_ci)
        # Optional trigger → trigger_option decision pushed
        from swu.engine.actions import legal_actions
        acts = legal_actions(state)
        from swu.engine.actions import AcceptTrigger, DeclineTrigger
        assert any(isinstance(a, AcceptTrigger) for a in acts), "Should have AcceptTrigger"
        assert any(isinstance(a, DeclineTrigger) for a in acts), "Should have DeclineTrigger"

    def test_no_damaged_unit_auto_declines(self, repo):
        """2-1B Surgical Droid: with nothing to heal, the optional trigger is
        skipped silently — no accept/decline prompt is shown."""
        droid = _get_card(repo, "SOR", "59")
        friendly = _get_card(repo, "SOR", "46")  # Consular Security Force, undamaged
        state = _make_state()
        droid_ci = _place(state, "P0", droid, "ground")
        _place(state, "P0", friendly, "ground")  # no damage anywhere

        state = _fire_on_attack(state, droid_ci)
        # No legal heal target → no decision pushed at all.
        assert not state.pending_decisions, "Trigger should auto-decline when nothing is damaged"
        from swu.engine.actions import legal_actions, AcceptTrigger, DeclineTrigger
        acts = legal_actions(state)
        assert not any(isinstance(a, (AcceptTrigger, DeclineTrigger)) for a in acts)

    def test_only_damaged_units_are_targetable(self, repo):
        """2-1B Surgical Droid: an undamaged unit is not a legal heal target."""
        droid = _get_card(repo, "SOR", "59")
        damaged = _get_card(repo, "SOR", "46")
        undamaged = _get_card(repo, "SOR", "46")
        state = _make_state()
        droid_ci = _place(state, "P0", droid, "ground")
        damaged_ci = _place(state, "P0", damaged, "ground")
        undamaged_ci = _place(state, "P0", undamaged, "ground")
        damaged_ci.damage = 2

        state = _fire_on_attack(state, droid_ci)
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        target_ids = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert damaged_ci.instance_id in target_ids
        assert undamaged_ci.instance_id not in target_ids

    def test_heal_resolves_damage(self, repo):
        """2-1B Surgical Droid: accepting the trigger heals 2 damage."""
        droid = _get_card(repo, "SOR", "59")
        target_unit = _get_card(repo, "SOR", "46")
        state = _make_state()
        droid_ci = _place(state, "P0", droid, "ground")
        target_ci = _place(state, "P0", target_unit, "ground")
        target_ci.damage = 3

        state = _fire_on_attack(state, droid_ci)
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        acts = legal_actions(state)
        accept = next(a for a in acts if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        # Now choose target
        acts = legal_actions(state)
        choose = next(a for a in acts if isinstance(a, ChooseTarget)
                      and a.target_id == target_ci.instance_id)
        state = apply(state, choose)
        # Damage should be reduced by 2
        result = state.find_instance(target_ci.instance_id)
        assert result is not None
        _, healed_ci = result
        assert healed_ci.damage == 1


class TestGeneralDodonna:
    def test_constant_power_buff_rebels(self, repo):
        """General Dodonna: other friendly Rebel units get +1 power."""
        dodonna = _get_card(repo, "SOR", "242")
        rebel = _get_card(repo, "SOR", "46")  # Consular Security Force (Rebel)
        state = _make_state()
        _place(state, "P0", dodonna, "ground")
        rebel_ci = _place(state, "P0", rebel, "ground")

        from swu.engine.actions import compute_power
        base_power = rebel.power
        effective = compute_power(state, rebel_ci)
        assert effective == base_power + 1

    def test_no_buff_to_non_rebels(self, repo):
        """General Dodonna: does not buff non-Rebel units."""
        dodonna = _get_card(repo, "SOR", "242")
        imp = _get_card(repo, "SOR", "128")  # Death Star Stormtrooper (Imperial, not Rebel)
        state = _make_state()
        _place(state, "P0", dodonna, "ground")
        imp_ci = _place(state, "P0", imp, "ground")

        from swu.engine.actions import compute_power
        assert compute_power(state, imp_ci) == imp.power

    def test_no_buff_to_self(self, repo):
        """General Dodonna: does not buff itself."""
        dodonna = _get_card(repo, "SOR", "242")
        state = _make_state()
        dodonna_ci = _place(state, "P0", dodonna, "ground")

        from swu.engine.actions import compute_power
        assert compute_power(state, dodonna_ci) == dodonna.power


class TestSnowspeeder:
    def test_on_attack_exhaust_vehicle(self, repo):
        """Snowspeeder: On Attack exhausts an enemy Vehicle ground unit."""
        snowspeeder = _get_card(repo, "SOR", "244")
        at_st = _get_card(repo, "SOR", "232")  # Vehicle trait
        state = _make_state()
        ss_ci = _place(state, "P0", snowspeeder, "ground")
        atst_ci = _place(state, "P1", at_st, "ground")
        atst_ci.exhausted = False

        state = _fire_on_attack(state, ss_ci)
        # Mandatory targeted trigger → decide+resolve
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        acts = legal_actions(state)
        choose = next((a for a in acts if isinstance(a, ChooseTarget)
                       and a.target_id == atst_ci.instance_id), None)
        assert choose is not None, "Should have ChooseTarget for AT-ST"
        state = apply(state, choose)

        result = state.find_instance(atst_ci.instance_id)
        assert result is not None
        _, ci = result
        assert ci.exhausted, "AT-ST should be exhausted"

    def test_on_attack_no_vehicle_fizzles(self, repo):
        """Snowspeeder: On Attack fizzles if no enemy Vehicle ground units."""
        snowspeeder = _get_card(repo, "SOR", "244")
        non_vehicle = _get_card(repo, "SOR", "46")  # Consular Security Force (no Vehicle trait)
        state = _make_state()
        ss_ci = _place(state, "P0", snowspeeder, "ground")
        _place(state, "P1", non_vehicle, "ground")

        prev_len = len(state.pending_decisions)
        state = _fire_on_attack(state, ss_ci)
        # Should fizzle (no Vehicle targets) — no decision pushed
        assert len(state.pending_decisions) == prev_len


class TestChewbacca:
    def test_when_attacked_readies_himself(self, repo):
        """Chewbacca: When attacked, ready him."""
        chewie = _get_card(repo, "SOR", "196")
        attacker = _get_card(repo, "SOR", "128")  # Death Star Stormtrooper
        state = _make_state()
        chewie_ci = _place(state, "P0", chewie, "ground")
        att_ci = _place(state, "P1", attacker, "ground")
        chewie_ci.exhausted = True  # exhaust him first

        state = _fire_on_attack(state, att_ci, chewie_ci)
        # WhenAttacked trigger should ready Chewbacca inline
        result = state.find_instance(chewie_ci.instance_id)
        assert result is not None
        _, ci = result
        assert not ci.exhausted, "Chewbacca should be readied"


class TestVigilantHonorGuards:
    def test_gains_sentinel_while_undamaged(self, repo):
        """Vigilant Honor Guards gains Sentinel while undamaged."""
        guards = _get_card(repo, "SOR", "48")
        state = _make_state()
        guards_ci = _place(state, "P0", guards, "ground")
        guards_ci.damage = 0

        from swu.engine.keywords import has_keyword, Keyword
        assert has_keyword(state, guards_ci, Keyword.SENTINEL)

    def test_loses_sentinel_when_damaged(self, repo):
        """Vigilant Honor Guards loses Sentinel when damaged.

        The printed Sentinel is stripped by ``keyword_sanitizer`` (it is an
        implemented conditional self-grant — a ConstantAbility gated on
        SOURCE_UNDAMAGED owns the keyword), so a damaged unit no longer has it.
        """
        guards = _get_card(repo, "SOR", "48")
        state = _make_state()
        guards_ci = _place(state, "P0", guards, "ground")
        guards_ci.damage = 1

        from swu.engine.keywords import has_keyword, Keyword
        assert not has_keyword(state, guards_ci, Keyword.SENTINEL)


class TestObiWanKenobi:
    def _deck_card(self, state, repo):
        """Put one card in P0's deck so a draw is observable (and harmless)."""
        from swu.engine.state import CardInstance, Zone
        filler = _get_card(repo, "SOR", "46")
        state.players[0].deck.append(
            CardInstance("p0_deck_top", filler, "P0", Zone.DECK))

    def test_mandatory_target_choice_no_decline(self, repo):
        """Obi-Wan's When Defeated is mandatory: a target must be chosen (no decline)."""
        obi = _get_card(repo, "SOR", "49")
        target = _get_card(repo, "SOR", "46")
        state = _make_state()
        obi_ci = _place(state, "P0", obi, "ground")
        _place(state, "P0", target, "ground")

        state = _fire_when_defeated(state, obi_ci)
        from swu.engine.actions import legal_actions, ChooseTarget, DeclineTarget
        acts = legal_actions(state)
        assert any(isinstance(a, ChooseTarget) for a in acts), "must offer a target"
        assert not any(isinstance(a, DeclineTarget) for a in acts), "mandatory — no decline"

    def test_gives_2_experience_and_no_draw_for_non_force(self, repo):
        """2 Experience to the chosen unit; a NON-Force target triggers no draw."""
        obi = _get_card(repo, "SOR", "49")
        target = _get_card(repo, "SOR", "46")  # Consular Security Force — not a Force unit
        state = _make_state()
        obi_ci = _place(state, "P0", obi, "ground")
        target_ci = _place(state, "P0", target, "ground")
        self._deck_card(state, repo)
        hand_before = len(state.players[0].hand)

        state = _fire_when_defeated(state, obi_ci)
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        choose = next(a for a in legal_actions(state) if isinstance(a, ChooseTarget)
                      and a.target_id == target_ci.instance_id)
        state = apply(state, choose)

        _, ci = state.find_instance(target_ci.instance_id)
        assert _experience_count(ci) == 2
        assert len(state.players[0].hand) == hand_before, "non-Force → no draw"

    def test_gives_2_experience_and_draws_for_force_unit(self, repo):
        """A Force target receives 2 Experience AND triggers a card draw."""
        obi = _get_card(repo, "SOR", "49")
        force_target = _get_card(repo, "SOR", "51")  # Luke Skywalker Unit — Force trait
        state = _make_state()
        obi_ci = _place(state, "P0", obi, "ground")
        target_ci = _place(state, "P0", force_target, "ground")
        self._deck_card(state, repo)
        hand_before = len(state.players[0].hand)

        state = _fire_when_defeated(state, obi_ci)
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        choose = next(a for a in legal_actions(state) if isinstance(a, ChooseTarget)
                      and a.target_id == target_ci.instance_id)
        state = apply(state, choose)

        _, ci = state.find_instance(target_ci.instance_id)
        assert _experience_count(ci) == 2
        assert len(state.players[0].hand) == hand_before + 1, "Force → draw 1"

    def test_fizzles_with_no_other_friendly_unit(self, repo):
        """No 'another friendly unit' → trigger fizzles with no decision."""
        obi = _get_card(repo, "SOR", "49")
        state = _make_state()
        obi_ci = _place(state, "P0", obi, "ground")
        # only an ENEMY unit exists — not a legal "friendly" target
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        state = _fire_when_defeated(state, obi_ci)
        assert not state.pending_decisions, "no friendly target → no decision pushed"


class TestYoda:
    def test_when_defeated_each_player_draws(self, repo):
        """Yoda: When defeated, each player draws 1 card."""
        yoda = _get_card(repo, "SOR", "45")
        state = _make_state()
        yoda_ci = _place(state, "P0", yoda, "ground")
        # Put cards in each deck
        dummy = _get_card(repo, "SOR", "46")
        from swu.engine.state import CardInstance, Zone
        for ps in state.players:
            ci = CardInstance(f"{ps.player_id}_deck_draw", dummy, ps.player_id, Zone.DECK)
            ps.deck.append(ci)

        h0_before = len(state.players[0].hand)
        h1_before = len(state.players[1].hand)
        state = _fire_when_defeated(state, yoda_ci)

        assert len(state.players[0].hand) == h0_before + 1
        assert len(state.players[1].hand) == h1_before + 1


class TestWingLeader:
    def test_when_played_gives_two_experience(self, repo):
        """Wing Leader: When played, give 2 Experience to another friendly Rebel unit."""
        wing_leader = _get_card(repo, "SOR", "241")
        rebel = _get_card(repo, "SOR", "46")  # Consular Security Force (Rebel)
        state = _make_state()
        wl_ci = _place(state, "P0", wing_leader, "ground")
        rebel_ci = _place(state, "P0", rebel, "ground")

        state = _fire_when_played(state, wl_ci)
        # Should be inline-resolved (one target → auto-choose) OR need ChooseTarget
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        acts = legal_actions(state)
        if any(isinstance(a, ChooseTarget) for a in acts):
            choose = next(a for a in acts if isinstance(a, ChooseTarget)
                          and a.target_id == rebel_ci.instance_id)
            state = apply(state, choose)

        result = state.find_instance(rebel_ci.instance_id)
        if result:
            _, ci = result
            assert _experience_count(ci) == 2


# ── REBEL EVENTS ─────────────────────────────────────────────────────────────

class TestRepair:
    def test_heal_3_from_unit(self, repo):
        """Repair: heal 3 damage from a unit."""
        repair = _get_card(repo, "SOR", "74")
        target = _get_card(repo, "SOR", "46")
        state = _make_state()
        # Put repair in hand
        from swu.engine.state import CardInstance, Zone
        ps = state.players[0]
        repair_ci = CardInstance(
            instance_id="p0_repair", card_def=repair, owner_id="P0", zone=Zone.HAND
        )
        ps.hand.append(repair_ci)
        target_ci = _place(state, "P0", target, "ground")
        target_ci.damage = 5
        _give_resources(state, "P0", 10)  # cover aspect penalty

        from swu.engine.actions import apply, PlayCard, legal_actions, ChooseTarget
        acts = legal_actions(state)
        play = next((a for a in acts if isinstance(a, PlayCard)
                     and a.instance_id == repair_ci.instance_id), None)
        assert play is not None, "PlayCard(Repair) should be legal"
        state = apply(state, play)

        # Should have a resolve_effects decision for the Heal target
        acts = legal_actions(state)
        if any(isinstance(a, ChooseTarget) for a in acts):
            choose = next(a for a in acts if isinstance(a, ChooseTarget)
                          and a.target_id == target_ci.instance_id)
            state = apply(state, choose)

        result = state.find_instance(target_ci.instance_id)
        if result:
            _, ci = result
            assert ci.damage == 2, f"Expected 2 damage remaining, got {ci.damage}"

    def test_undamaged_unit_not_targetable(self, repo):
        """Repair: an undamaged unit (or base) is not a legal heal target."""
        repair = _get_card(repo, "SOR", "74")
        target = _get_card(repo, "SOR", "46")  # undamaged
        state = _make_state()
        from swu.engine.state import CardInstance, Zone
        ps = state.players[0]
        repair_ci = CardInstance(
            instance_id="p0_repair", card_def=repair, owner_id="P0", zone=Zone.HAND
        )
        ps.hand.append(repair_ci)
        _place(state, "P0", target, "ground")  # nothing damaged anywhere
        _give_resources(state, "P0", 10)

        from swu.engine.actions import apply, PlayCard, legal_actions, ChooseTarget
        play = next(a for a in legal_actions(state) if isinstance(a, PlayCard)
                    and a.instance_id == repair_ci.instance_id)
        state = apply(state, play)
        # No damaged unit or base → no heal target offered (event fizzles).
        assert not any(isinstance(a, ChooseTarget) for a in legal_actions(state))


class TestWaylay:
    def test_returns_unit_to_hand(self, repo):
        """Waylay: return a non-leader unit to its owner's hand."""
        waylay = _get_card(repo, "SOR", "222")
        target = _get_card(repo, "SOR", "128")  # Death Star Stormtrooper (non-leader)
        state = _make_state()
        from swu.engine.state import CardInstance, Zone
        ps = state.players[0]
        waylay_ci = CardInstance("p0_waylay", waylay, "P0", Zone.HAND)
        ps.hand.append(waylay_ci)
        target_ci = _place(state, "P1", target, "ground")  # enemy unit
        _give_resources(state, "P0", 10)

        from swu.engine.actions import apply, PlayCard, legal_actions, ChooseTarget
        state = apply(state, PlayCard(waylay_ci.instance_id))

        acts = legal_actions(state)
        choose = next((a for a in acts if isinstance(a, ChooseTarget)
                       and a.target_id == target_ci.instance_id), None)
        assert choose is not None
        state = apply(state, choose)

        opp_ps = state.players[1]
        assert any(ci.instance_id == target_ci.instance_id for ci in opp_ps.hand)


class TestVanquish:
    def test_defeats_non_leader_unit(self, repo):
        """Vanquish: defeat a non-leader unit."""
        vanquish = _get_card(repo, "SOR", "78")
        target = _get_card(repo, "SOR", "128")  # Death Star Stormtrooper
        state = _make_state()
        from swu.engine.state import CardInstance, Zone
        ps = state.players[0]
        vanq_ci = CardInstance("p0_vanquish", vanquish, "P0", Zone.HAND)
        ps.hand.append(vanq_ci)
        target_ci = _place(state, "P1", target, "ground")
        _give_resources(state, "P0", 10)

        from swu.engine.actions import apply, PlayCard, ChooseTarget, legal_actions
        state = apply(state, PlayCard(vanq_ci.instance_id))

        acts = legal_actions(state)
        choose = next((a for a in acts if isinstance(a, ChooseTarget)
                       and a.target_id == target_ci.instance_id), None)
        assert choose is not None
        state = apply(state, choose)

        # Target should be in discard
        opp_ps = state.players[1]
        assert any(ci.instance_id == target_ci.instance_id for ci in opp_ps.discard)


class TestIAmYourFather:
    """SOR_233 — Deal 7 damage to an enemy unit unless its controller says 'no.'
    If they do, draw 3 cards."""

    def _setup(self, repo):
        """P0 holds I Am Your Father; P1 controls a 9-HP enemy unit (survives 7
        damage so the damage is observable). P0's deck has 3 cards to draw."""
        from swu.engine.state import CardInstance, Zone
        iayf = _get_card(repo, "SOR", "233")
        enemy = _get_card(repo, "SOR", "119")  # Reinforcement Walker, HP 9
        filler = _get_card(repo, "SOR", "46")
        state = _make_state()
        ps0 = state.players[0]
        iayf_ci = CardInstance("p0_iayf", iayf, "P0", Zone.HAND)
        ps0.hand.append(iayf_ci)
        for i in range(3):
            ps0.deck.append(CardInstance(f"p0_deck_{i}", filler, "P0", Zone.DECK))
        enemy_ci = _place(state, "P1", enemy, "ground")
        _give_resources(state, "P0", 10)
        return state, iayf_ci, enemy_ci

    def _play_and_target(self, state, iayf_ci, enemy_ci):
        """Play the event and have P0 choose the enemy unit as target.
        Leaves a 'say_no' decision on the stack for P1."""
        from swu.engine.actions import apply, PlayCard, ChooseTarget, legal_actions
        state = apply(state, PlayCard(iayf_ci.instance_id))
        acts = legal_actions(state)
        choose = next((a for a in acts if isinstance(a, ChooseTarget)
                       and a.target_id == enemy_ci.instance_id), None)
        assert choose is not None, "P0 should be able to target the enemy unit"
        state = apply(state, choose)
        assert state.pending_decisions, "a say_no decision should be pending"
        top = state.pending_decisions[-1]
        assert top.kind == "say_no"
        assert top.deciding_player_id == "P1", "the target's controller decides"
        return state

    def _drain(self, state):
        """Apply any remaining forced continuations (AutoResolveEffects)."""
        from swu.engine.actions import legal_actions, apply
        while state.pending_decisions and not state.is_terminal():
            acts = legal_actions(state)
            assert len(acts) == 1, f"expected a single forced continuation, got {acts}"
            state = apply(state, acts[0])
        return state

    def test_opponent_allows_takes_7_damage_no_draw(self, repo):
        from swu.engine.actions import legal_actions, apply, AllowEffect
        state, iayf_ci, enemy_ci = self._setup(repo)
        hand_before = len(state.players[0].hand)
        state = self._play_and_target(state, iayf_ci, enemy_ci)

        allow = next(a for a in legal_actions(state) if isinstance(a, AllowEffect))
        state = apply(state, allow)
        state = self._drain(state)

        result = state.find_instance(enemy_ci.instance_id)
        assert result is not None, "9-HP unit survives 7 damage"
        _, enemy = result
        assert enemy.damage == 7, "allowing deals the full 7 damage"
        # PlayCard removed the event from hand; no extra draw on allow.
        assert len(state.players[0].deck) == 3, "no cards drawn when allowed"
        assert len(state.players[0].hand) == hand_before - 1
        assert not state.pending_decisions
        assert state.active_player_index == 1, "control passes to the opponent"

    def test_opponent_says_no_no_damage_controller_draws_3(self, repo):
        from swu.engine.actions import legal_actions, apply, SayNo
        state, iayf_ci, enemy_ci = self._setup(repo)
        state = self._play_and_target(state, iayf_ci, enemy_ci)
        hand_after_play = len(state.players[0].hand)  # event already discarded

        say_no = next(a for a in legal_actions(state) if isinstance(a, SayNo))
        state = apply(state, say_no)
        state = self._drain(state)

        result = state.find_instance(enemy_ci.instance_id)
        assert result is not None
        _, enemy = result
        assert enemy.damage == 0, "saying no deals no damage"
        assert len(state.players[0].deck) == 0, "all 3 deck cards drawn"
        assert len(state.players[0].hand) == hand_after_play + 3, "controller draws 3"
        assert not state.pending_decisions
        assert state.active_player_index == 1, "control passes to the opponent"

    def test_fizzles_with_no_enemy_unit(self, repo):
        """No enemy unit to target -> the event resolves with no decision pushed
        and no draw."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import apply, PlayCard
        iayf = _get_card(repo, "SOR", "233")
        filler = _get_card(repo, "SOR", "46")
        state = _make_state()
        ps0 = state.players[0]
        iayf_ci = CardInstance("p0_iayf", iayf, "P0", Zone.HAND)
        ps0.hand.append(iayf_ci)
        ps0.deck.append(CardInstance("p0_deck_0", filler, "P0", Zone.DECK))
        _give_resources(state, "P0", 10)

        state = apply(state, PlayCard(iayf_ci.instance_id))
        assert not state.pending_decisions, "no say_no decision without a target"
        assert len(state.players[0].deck) == 1, "no draw when the event fizzles"
        assert state.active_player_index == 1, "turn passes to the opponent"

    def test_no_longer_escape_hatch(self):
        from swu.abilities.registry import is_escape_hatch
        import swu.cards.sor  # noqa: F401
        assert not is_escape_hatch("SOR", "233")


class TestForceChoke:
    """SOR_139 — If you control a Force unit, this event costs 1 less. Deal 5
    damage to a non-Vehicle unit; that unit's controller draws a card."""

    def _hand_event(self, state, repo, owner="P0"):
        from swu.engine.state import CardInstance, Zone
        fc = _get_card(repo, "SOR", "139")
        ci = CardInstance("p0_fc", fc, owner, Zone.HAND)
        state.player_by_id(owner).hand.append(ci)
        return ci

    def _cost_paid(self, repo, *, with_force):
        """Play Force Choke and return the resources actually exhausted to play
        it (measured before the targeting decision resolves)."""
        from swu.engine.actions import apply, PlayCard
        state = _make_state()
        fc_ci = self._hand_event(state, repo)
        if with_force:
            _place(state, "P0", _get_card(repo, "SOR", "61"), "ground")  # Force unit
        # An enemy non-Vehicle unit so the event has a legal target.
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _give_resources(state, "P0", 10)
        before = state.player_by_id("P0").available_resources
        state = apply(state, PlayCard(fc_ci.instance_id))
        return before - state.player_by_id("P0").available_resources

    def test_cost_reduced_by_one_only_with_force_unit(self, repo):
        without = self._cost_paid(repo, with_force=False)
        with_force = self._cost_paid(repo, with_force=True)
        assert with_force == without - 1, "Force unit reduces the cost by exactly 1"

    def test_reduction_floors_legality(self, repo):
        """The reduction is reflected in affordability: a controller with a Force
        unit can afford Force Choke with 1 fewer resource than one without."""
        from swu.engine.actions import legal_actions, PlayCard
        # First learn the reduced cost (with a Force unit).
        reduced = self._cost_paid(repo, with_force=True)

        def _playable(with_force, resources):
            state = _make_state()
            fc_ci = self._hand_event(state, repo)
            if with_force:
                _place(state, "P0", _get_card(repo, "SOR", "61"), "ground")
            _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
            _give_resources(state, "P0", resources)
            return any(isinstance(a, PlayCard) and a.instance_id == fc_ci.instance_id
                       for a in legal_actions(state))

        # At exactly the reduced cost: playable with a Force unit, NOT without
        # (without, it still needs reduced + 1).
        assert _playable(True, reduced), "affordable with the Force-unit discount"
        assert not _playable(False, reduced), "without a Force unit it costs 1 more"
        assert _playable(False, reduced + 1), "affordable without discount at full cost"

    def test_deals_5_to_chosen_enemy_and_that_controller_draws(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import apply, PlayCard, ChooseTarget, legal_actions
        state = _make_state()
        fc_ci = self._hand_event(state, repo)
        enemy_ci = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # hp 7
        # P1 needs a card to draw; P0 should NOT draw (caster != target controller).
        filler = _get_card(repo, "SOR", "46")
        state.player_by_id("P1").deck.append(CardInstance("p1_deck_0", filler, "P1", Zone.DECK))
        state.player_by_id("P0").deck.append(CardInstance("p0_deck_0", filler, "P0", Zone.DECK))
        _give_resources(state, "P0", 10)
        p0_hand_before = len(state.player_by_id("P0").hand)
        p1_hand_before = len(state.player_by_id("P1").hand)

        state = apply(state, PlayCard(fc_ci.instance_id))
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy_ci.instance_id)
        state = apply(state, choose)
        while state.pending_decisions and not state.is_terminal():
            acts = legal_actions(state)
            assert len(acts) == 1, f"expected a forced continuation, got {acts}"
            state = apply(state, acts[0])

        _, enemy = state.find_instance(enemy_ci.instance_id)
        assert enemy.damage == 5, "5 damage dealt to the chosen unit"
        assert len(state.player_by_id("P1").deck) == 0, "targeted unit's controller drew"
        assert len(state.player_by_id("P1").hand) == p1_hand_before + 1
        assert len(state.player_by_id("P0").deck) == 1, "caster does not draw"
        assert len(state.player_by_id("P0").hand) == p0_hand_before - 1, "event left hand"

    def test_vehicle_unit_is_not_a_legal_target(self, repo):
        from swu.engine.actions import apply, PlayCard, ChooseTarget, legal_actions
        state = _make_state()
        fc_ci = self._hand_event(state, repo)
        veh_ci = _place(state, "P1", _get_card(repo, "SOR", "44"), "space")   # Vehicle
        non_veh_ci = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # non-Vehicle
        _give_resources(state, "P0", 10)
        state = apply(state, PlayCard(fc_ci.instance_id))
        target_ids = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert non_veh_ci.instance_id in target_ids, "non-Vehicle unit is targetable"
        assert veh_ci.instance_id not in target_ids, "Vehicle unit is not targetable"

    def test_fizzles_with_only_vehicle_units(self, repo):
        """No non-Vehicle target -> no decision, no damage, no draw, turn passes."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import apply, PlayCard
        state = _make_state()
        fc_ci = self._hand_event(state, repo)
        veh_ci = _place(state, "P1", _get_card(repo, "SOR", "44"), "space")  # Vehicle only
        filler = _get_card(repo, "SOR", "46")
        state.player_by_id("P1").deck.append(CardInstance("p1_deck_0", filler, "P1", Zone.DECK))
        _give_resources(state, "P0", 10)
        state = apply(state, PlayCard(fc_ci.instance_id))
        assert not state.pending_decisions, "no targeting decision without a legal target"
        _, veh = state.find_instance(veh_ci.instance_id)
        assert veh.damage == 0, "no damage to the Vehicle"
        assert len(state.player_by_id("P1").deck) == 1, "no draw when the event fizzles"
        assert state.active_player_index == 1, "turn passes to the opponent"

    def test_no_longer_escape_hatch(self):
        from swu.abilities.registry import is_escape_hatch
        import swu.cards.sor  # noqa: F401
        assert not is_escape_hatch("SOR", "139")


class TestAsteroidSanctuary:
    def test_exhaust_enemy_and_shield_friendly(self, repo):
        """Asteroid Sanctuary: exhaust enemy + give Shield to friendly ≤3-cost unit."""
        sanctuary = _get_card(repo, "SOR", "218")
        enemy = _get_card(repo, "SOR", "128")   # Death Star Stormtrooper
        friendly = _get_card(repo, "SOR", "44")  # Restored ARC-170 (cost 2 ≤ 3)
        state = _make_state()
        from swu.engine.state import CardInstance, Zone
        ps = state.players[0]
        sanc_ci = CardInstance("p0_sanc", sanctuary, "P0", Zone.HAND)
        ps.hand.append(sanc_ci)
        enemy_ci = _place(state, "P1", enemy, "ground")
        friendly_ci = _place(state, "P0", friendly, "space")  # space OK
        _give_resources(state, "P0", 10)  # cover aspect penalty

        from swu.engine.actions import apply, PlayCard, ChooseTarget, legal_actions
        state = apply(state, PlayCard(sanc_ci.instance_id))

        # Should have a ChooseTarget for the exhaust effect
        acts = legal_actions(state)
        choose_enemy = next((a for a in acts if isinstance(a, ChooseTarget)
                              and a.target_id == enemy_ci.instance_id), None)
        if choose_enemy is not None:
            state = apply(state, choose_enemy)
            # Enemy should now be exhausted
            result = state.find_instance(enemy_ci.instance_id)
            if result:
                _, ci = result
                assert ci.exhausted

        # Next: choose Shield target (friendly ≤3 cost)
        acts = legal_actions(state)
        choose_friendly = next((a for a in acts if isinstance(a, ChooseTarget)
                                 and a.target_id == friendly_ci.instance_id), None)
        if choose_friendly is not None:
            state = apply(state, choose_friendly)
            result = state.find_instance(friendly_ci.instance_id)
            if result:
                _, ci = result
                assert _shield_count(ci) == 1


# ── IMPERIAL UNITS ────────────────────────────────────────────────────────────

class TestAdmiralPiett:
    def test_6_plus_units_gain_ambush(self, repo):
        """Admiral Piett: non-leader units costing 6+ gain Ambush."""
        piett = _get_card(repo, "SOR", "79")
        big_unit = _get_card(repo, "SOR", "232")  # AT-ST cost 6
        state = _make_state()
        _place(state, "P0", piett, "ground")
        atst_ci = _place(state, "P0", big_unit, "ground")

        from swu.engine.keywords import has_keyword, Keyword
        assert has_keyword(state, atst_ci, Keyword.AMBUSH)

    def test_cheap_units_no_ambush(self, repo):
        """Admiral Piett: does not grant Ambush to units costing < 6."""
        piett = _get_card(repo, "SOR", "79")
        cheap = _get_card(repo, "SOR", "128")  # Death Star Stormtrooper cost 1
        state = _make_state()
        _place(state, "P0", piett, "ground")
        cheap_ci = _place(state, "P0", cheap, "ground")

        from swu.engine.keywords import has_keyword, Keyword
        assert not has_keyword(state, cheap_ci, Keyword.AMBUSH)

    def test_piett_himself_has_no_ambush(self, repo):
        """Regression: Piett's keyword bar is empty — he grants Ambush to OTHER
        units, he doesn't have it himself. The source data wrongly tags him with
        Ambush; the keyword sanitiser strips it (see keyword_sanitizer.py)."""
        piett = _get_card(repo, "SOR", "79")
        assert "Ambush" not in piett.keywords
        state = _make_state()
        piett_ci = _place(state, "P0", piett, "ground")

        from swu.engine.keywords import has_keyword, Keyword
        assert not has_keyword(state, piett_ci, Keyword.AMBUSH)

    def test_piett_entering_play_pushes_no_ambush_decision(self, repo):
        """Regression: when Piett enters play he must NOT get an immediate
        ready-and-attack — that was the reported bug. A cost-6 unit entering
        play under Piett (e.g. AT-ST) DOES, proving the grant still works."""
        from swu.engine.events import UnitEntersPlay
        from swu.engine.triggers import get_bus
        import swu.engine.keyword_triggers  # noqa: F401 — registers Ambush listener

        piett = _get_card(repo, "SOR", "79")
        atst = _get_card(repo, "SOR", "232")  # cost 6 → gains Ambush from Piett
        state = _make_state()
        _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")  # enemy target
        piett_ci = _place(state, "P0", piett, "ground")

        get_bus().fire(state, UnitEntersPlay(
            player_id="P0", instance_id=piett_ci.instance_id,
            card_name=piett.display_name, arena="Ground"))
        assert not state.pending_decisions, "Piett must not trigger an Ambush attack"

        atst_ci = _place(state, "P0", atst, "ground")
        get_bus().fire(state, UnitEntersPlay(
            player_id="P0", instance_id=atst_ci.instance_id,
            card_name=atst.display_name, arena="Ground"))
        assert state.pending_decisions and state.pending_decisions[-1].kind == "ambush", \
            "A cost-6 unit should still gain Ambush from Piett"

    def test_wedge_himself_has_no_ambush(self, repo):
        """Sibling of the Piett bug: Wedge grants Ambush to friendly Vehicles
        but has no keyword bar himself."""
        wedge = _get_card(repo, "SOR", "100")
        assert "Ambush" not in wedge.keywords


class TestAdmiralMotti:
    def test_when_defeated_optional_ready_villainy(self, repo):
        """Admiral Motti: When Defeated, may ready a Villainy unit."""
        motti = _get_card(repo, "SOR", "226")
        villainy_unit = _get_card(repo, "SOR", "128")  # Death Star Stormtrooper (Villainy)
        state = _make_state()
        motti_ci = _place(state, "P0", motti, "ground")
        vil_ci = _place(state, "P0", villainy_unit, "ground")
        vil_ci.exhausted = True

        state = _fire_when_defeated(state, motti_ci)
        # Optional trigger → trigger_option decision
        from swu.engine.actions import legal_actions, AcceptTrigger, DeclineTrigger
        acts = legal_actions(state)
        assert any(isinstance(a, (AcceptTrigger, DeclineTrigger)) for a in acts), \
            "Should have trigger option for Admiral Motti"


class TestGeneralVeers:
    def test_constant_buff_imperial_units(self, repo):
        """General Veers: other friendly Imperial units get +1/+1."""
        veers = _get_card(repo, "SOR", "230")
        imp = _get_card(repo, "SOR", "128")  # Death Star Stormtrooper (Imperial)
        state = _make_state()
        _place(state, "P0", veers, "ground")
        imp_ci = _place(state, "P0", imp, "ground")

        from swu.engine.actions import compute_power, compute_hp
        assert compute_power(state, imp_ci) == imp.power + 1
        assert compute_hp(state, imp_ci) == imp.hp + 1

    def test_no_buff_to_self(self, repo):
        """General Veers: does not buff himself."""
        veers = _get_card(repo, "SOR", "230")
        state = _make_state()
        veers_ci = _place(state, "P0", veers, "ground")

        from swu.engine.actions import compute_power
        assert compute_power(state, veers_ci) == veers.power


class TestImperialInterceptor:
    def test_optional_damage_to_space_unit(self, repo):
        """Imperial Interceptor: When Played, may deal 3 to a space unit."""
        interceptor = _get_card(repo, "SOR", "132")
        target = _get_card(repo, "SOR", "237")  # Alliance X-Wing (space)
        state = _make_state()
        inter_ci = _place(state, "P0", interceptor, "space")  # also space
        target_ci = _place(state, "P1", target, "space")

        state = _fire_when_played(state, inter_ci)

        from swu.engine.actions import legal_actions, AcceptTrigger, DeclineTrigger
        acts = legal_actions(state)
        assert any(isinstance(a, (AcceptTrigger, DeclineTrigger)) for a in acts)


class TestTieAdvanced:
    def test_when_played_gives_experience(self, repo):
        """TIE Advanced: When Played, give 2 Exp to another friendly Imperial unit."""
        tie = _get_card(repo, "SOR", "231")
        imperial = _get_card(repo, "SOR", "128")  # Death Star Stormtrooper
        state = _make_state()
        tie_ci = _place(state, "P0", tie, "space")
        imp_ci = _place(state, "P0", imperial, "ground")

        state = _fire_when_played(state, tie_ci)

        from swu.engine.actions import legal_actions, apply, ChooseTarget
        acts = legal_actions(state)
        choose = next((a for a in acts if isinstance(a, ChooseTarget)
                       and a.target_id == imp_ci.instance_id), None)
        if choose is not None:
            state = apply(state, choose)
            result = state.find_instance(imp_ci.instance_id)
            if result:
                _, ci = result
                assert _experience_count(ci) == 2


class TestGladiatorStarDestroyer:
    def test_when_played_grants_sentinel_for_phase(self, repo):
        """Gladiator: When Played, give a unit Sentinel for this phase."""
        gladiator = _get_card(repo, "SOR", "86")
        target = _get_card(repo, "SOR", "225")  # TIE/ln Fighter (space, no Sentinel)
        state = _make_state()
        glad_ci = _place(state, "P0", gladiator, "space")
        target_ci = _place(state, "P0", target, "space")

        state = _fire_when_played(state, glad_ci)

        from swu.engine.actions import legal_actions, apply, ChooseTarget
        acts = legal_actions(state)
        choose = next((a for a in acts if isinstance(a, ChooseTarget)
                       and a.target_id == target_ci.instance_id), None)
        if choose is not None:
            state = apply(state, choose)
            from swu.engine.keywords import has_keyword, Keyword
            result = state.find_instance(target_ci.instance_id)
            if result:
                _, ci = result
                assert has_keyword(state, ci, Keyword.SENTINEL)


# ── IMPERIAL EVENTS ───────────────────────────────────────────────────────────

class TestOpenFire:
    def test_deal_4_damage(self, repo):
        """Open Fire: deal 4 damage to a unit."""
        open_fire = _get_card(repo, "SOR", "172")
        target = _get_card(repo, "SOR", "232")  # AT-ST has 7 HP
        state = _make_state()
        from swu.engine.state import CardInstance, Zone
        ps = state.players[0]
        of_ci = CardInstance("p0_openfire", open_fire, "P0", Zone.HAND)
        ps.hand.append(of_ci)
        target_ci = _place(state, "P1", target, "ground")
        _give_resources(state, "P0", 10)

        from swu.engine.actions import apply, PlayCard, ChooseTarget, legal_actions
        state = apply(state, PlayCard(of_ci.instance_id))

        acts = legal_actions(state)
        choose = next((a for a in acts if isinstance(a, ChooseTarget)
                       and a.target_id == target_ci.instance_id), None)
        assert choose is not None
        state = apply(state, choose)

        result = state.find_instance(target_ci.instance_id)
        assert result is not None, "AT-ST should survive 4 damage (has 7 HP)"
        _, ci = result
        assert ci.damage == 4


class TestRelentless:
    """SOR_89 — 'The first event played by each opponent each round loses all
    abilities.'  A passive replacement effect active while Relentless is in play.
    """

    @staticmethod
    def _setup(repo, *, suppressor_owner="P0", event_player="P1"):
        """A state where `suppressor_owner` controls Relentless and `event_player`
        is active with Open Fire in hand, resources, and a valid damage target."""
        from swu.engine.state import CardInstance, Zone
        relentless = _get_card(repo, "SOR", "89")
        open_fire = _get_card(repo, "SOR", "172")   # Deal 4 damage to a unit
        target = _get_card(repo, "SOR", "232")      # AT-ST, 7 HP (survives 4)
        state = _make_state()
        _place(state, suppressor_owner, relentless, "ground")
        target_ci = _place(state, suppressor_owner, target, "ground")
        ps = state.player_by_id(event_player)
        of_ci = CardInstance(f"{event_player}_openfire", open_fire, event_player, Zone.HAND)
        ps.hand.append(of_ci)
        _give_resources(state, event_player, 10)
        state.active_player_index = state.player_index(event_player)
        return state, of_ci, target_ci

    def test_first_enemy_event_is_suppressed(self, repo):
        """P1's first event each round loses all abilities while P0 has Relentless."""
        from swu.engine.actions import apply, PlayCard, ChooseTarget, legal_actions
        from swu.engine.events import EventAbilitiesSuppressed
        state, of_ci, target_ci = self._setup(repo)

        state = apply(state, PlayCard(of_ci.instance_id))

        # No target choice was offered — the ability never resolved.
        assert not any(isinstance(a, ChooseTarget) for a in legal_actions(state))
        assert not state.pending_decisions
        # Suppression was logged, naming Open Fire and Relentless.
        suppressed = [e for e in state.event_log if isinstance(e, EventAbilitiesSuppressed)]
        assert len(suppressed) == 1
        assert suppressed[0].instance_id == of_ci.instance_id
        # Target took no damage; event went to discard; turn passed to P0.
        result = state.find_instance(target_ci.instance_id)
        assert result is not None and result[1].damage == 0
        assert any(c.instance_id == of_ci.instance_id for c in state.player_by_id("P1").discard)
        assert state.active_player_index == state.player_index("P0")
        # P1 is now recorded as having played an event this round.
        assert "P1" in state.game_memory.events_played_this_round

    def test_second_enemy_event_resolves(self, repo):
        """Only the FIRST event is suppressed — a later event resolves normally."""
        from swu.engine.actions import apply, PlayCard, ChooseTarget, legal_actions
        from swu.engine.events import EventAbilitiesSuppressed
        state, of_ci, target_ci = self._setup(repo)
        # Simulate P1 already having played an event earlier this round.
        state.game_memory.events_played_this_round.add("P1")

        state = apply(state, PlayCard(of_ci.instance_id))

        # The ability resolves: a target choice is offered and deals 4 damage.
        acts = legal_actions(state)
        choose = next(a for a in acts if isinstance(a, ChooseTarget)
                      and a.target_id == target_ci.instance_id)
        state = apply(state, choose)
        result = state.find_instance(target_ci.instance_id)
        assert result is not None and result[1].damage == 4
        assert not any(isinstance(e, EventAbilitiesSuppressed) for e in state.event_log)

    def test_does_not_suppress_controllers_own_event(self, repo):
        """'Each opponent' — Relentless never blanks its own controller's events."""
        from swu.engine.actions import apply, PlayCard, ChooseTarget, legal_actions
        from swu.engine.events import EventAbilitiesSuppressed
        # P0 controls Relentless AND plays the event.
        state, of_ci, target_ci = self._setup(repo, suppressor_owner="P0", event_player="P0")

        state = apply(state, PlayCard(of_ci.instance_id))

        assert not any(isinstance(e, EventAbilitiesSuppressed) for e in state.event_log)
        choose = next(a for a in legal_actions(state) if isinstance(a, ChooseTarget)
                      and a.target_id == target_ci.instance_id)
        state = apply(state, choose)
        result = state.find_instance(target_ci.instance_id)
        assert result is not None and result[1].damage == 4

    def test_no_suppressor_resolves_normally(self, repo):
        """Without a Relentless in play, the first event resolves as usual."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import apply, PlayCard, ChooseTarget, legal_actions
        from swu.engine.events import EventAbilitiesSuppressed
        open_fire = _get_card(repo, "SOR", "172")
        target = _get_card(repo, "SOR", "232")
        state = _make_state()
        target_ci = _place(state, "P0", target, "ground")
        ps = state.player_by_id("P1")
        of_ci = CardInstance("P1_openfire", open_fire, "P1", Zone.HAND)
        ps.hand.append(of_ci)
        _give_resources(state, "P1", 10)
        state.active_player_index = 1

        state = apply(state, PlayCard(of_ci.instance_id))
        assert not any(isinstance(e, EventAbilitiesSuppressed) for e in state.event_log)
        choose = next(a for a in legal_actions(state) if isinstance(a, ChooseTarget)
                      and a.target_id == target_ci.instance_id)
        state = apply(state, choose)
        assert state.find_instance(target_ci.instance_id)[1].damage == 4

    def test_round_rollover_clears_tracking(self):
        """clear_round() resets the per-round 'played an event' tracking."""
        from swu.engine.state import GameMemory
        mem = GameMemory()
        mem.events_played_this_round.add("P1")
        mem.clear_round()
        assert mem.events_played_this_round == set()


class TestVadersLightsaber:
    def _attach(self, state, repo, host_ci):
        from swu.engine.state import CardInstance
        saber = _get_card(repo, "SOR", "136")
        saber_ci = CardInstance("p0_vsaber", saber, "P0", host_ci.zone)
        host_ci.attached_upgrades.append(saber_ci)
        return saber_ci

    def test_deals_4_to_chosen_ground_unit_on_vader(self, repo):
        """On Vader: may deal 4 damage to a chosen ground unit."""
        vader_unit = _get_card(repo, "SOR", "87")     # Darth Vader Unit (hp 7)
        victim = _get_card(repo, "SOR", "46")          # enemy ground unit (hp 7)
        state = _make_state()
        vader_ci = _place(state, "P0", vader_unit, "ground")
        victim_ci = _place(state, "P1", victim, "ground")
        saber_ci = self._attach(state, repo, vader_ci)

        state = _fire_upgrade_played(state, saber_ci, vader_ci)
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        # "you may" — accept the optional trigger first
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        choose = next(a for a in legal_actions(state) if isinstance(a, ChooseTarget)
                      and a.target_id == victim_ci.instance_id)
        state = apply(state, choose)

        _, ci = state.find_instance(victim_ci.instance_id)
        assert ci.damage == 4

    def test_only_ground_units_are_targetable(self, repo):
        """The 4 damage is restricted to the ground arena — space units excluded."""
        vader_unit = _get_card(repo, "SOR", "87")
        ground_victim = _get_card(repo, "SOR", "46")
        state = _make_state()
        vader_ci = _place(state, "P0", vader_unit, "ground")
        ground_ci = _place(state, "P1", ground_victim, "ground")
        # a space unit on the same enemy must NOT be offered
        space_ci = _place(state, "P1", ground_victim, "space")
        saber_ci = self._attach(state, repo, vader_ci)

        state = _fire_upgrade_played(state, saber_ci, vader_ci)
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        target_ids = {a.target_id for a in legal_actions(state)
                      if isinstance(a, ChooseTarget)}
        assert ground_ci.instance_id in target_ids
        assert space_ci.instance_id not in target_ids

    def test_optional_can_be_declined(self, repo):
        """The trigger is a 'may' — declining deals no damage."""
        vader_unit = _get_card(repo, "SOR", "87")
        victim = _get_card(repo, "SOR", "46")
        state = _make_state()
        vader_ci = _place(state, "P0", vader_unit, "ground")
        victim_ci = _place(state, "P1", victim, "ground")
        saber_ci = self._attach(state, repo, vader_ci)

        state = _fire_upgrade_played(state, saber_ci, vader_ci)
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        decline = next(a for a in legal_actions(state) if isinstance(a, DeclineTrigger))
        state = apply(state, decline)
        assert not state.pending_decisions
        _, ci = state.find_instance(victim_ci.instance_id)
        assert ci.damage == 0

    def test_no_damage_when_not_on_vader(self, repo):
        """Off Vader: accepting + choosing a target still deals no damage."""
        other_unit = _get_card(repo, "SOR", "46")  # not Darth Vader
        victim = _get_card(repo, "SOR", "238")
        state = _make_state()
        host_ci = _place(state, "P0", other_unit, "ground")
        victim_ci = _place(state, "P1", victim, "ground")
        saber_ci = self._attach(state, repo, host_ci)

        state = _fire_upgrade_played(state, saber_ci, host_ci)
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget,
        )
        # Even if the player opts in and targets, the host-gate makes it a no-op.
        accept = next((a for a in legal_actions(state)
                       if isinstance(a, AcceptTrigger)), None)
        if accept is not None:
            state = apply(state, accept)
            choose = next((a for a in legal_actions(state)
                           if isinstance(a, ChooseTarget)
                           and a.target_id == victim_ci.instance_id), None)
            if choose is not None:
                state = apply(state, choose)
        _, ci = state.find_instance(victim_ci.instance_id)
        assert ci.damage == 0, "no damage dealt off Vader"


# ── Luke's Lightsaber ─────────────────────────────────────────────────────────

class TestLukesLightsaber:
    def _attach(self, state, repo, host_ci):
        from swu.engine.state import CardInstance
        saber = _get_card(repo, "SOR", "53")
        saber_ci = CardInstance("p0_lsaber", saber, "P0", host_ci.zone)
        host_ci.attached_upgrades.append(saber_ci)
        return saber_ci

    def _accept_optional(self, state):
        """Accept the optional WhenPlayed trigger, then auto-resolve its effect."""
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, AutoResolveEffects,
        )
        if state.pending_decisions:
            state = apply(state, next(a for a in legal_actions(state)
                                      if isinstance(a, AcceptTrigger)))
            # CustomEffect has no chosen target → AutoResolveEffects
            state = apply(state, next(a for a in legal_actions(state)
                                      if isinstance(a, AutoResolveEffects)))
        return state

    def test_heals_and_shields_on_luke(self, repo):
        """On Luke: heal all damage from him and give him a Shield."""
        luke = _get_card(repo, "SOR", "51")  # Luke Skywalker Unit
        state = _make_state()
        luke_ci = _place(state, "P0", luke, "ground")
        luke_ci.damage = 5
        saber_ci = self._attach(state, repo, luke_ci)

        state = _fire_upgrade_played(state, saber_ci, luke_ci)
        state = self._accept_optional(state)

        _, ci = state.find_instance(luke_ci.instance_id)
        assert ci.damage == 0, "all damage healed"
        assert _shield_count(ci) == 1, "Shield token granted"

    def test_no_effect_when_not_on_luke(self, repo):
        """Off Luke: no heal and no Shield, even if the trigger is accepted."""
        other = _get_card(repo, "SOR", "46")
        state = _make_state()
        host_ci = _place(state, "P0", other, "ground")
        host_ci.damage = 5
        saber_ci = self._attach(state, repo, host_ci)

        state = _fire_upgrade_played(state, saber_ci, host_ci)
        state = self._accept_optional(state)

        _, ci = state.find_instance(host_ci.instance_id)
        assert ci.damage == 5, "damage unchanged off Luke"
        assert _shield_count(ci) == 0, "no Shield off Luke"


# ── Villainy tracking ─────────────────────────────────────────────────────────

class TestVillainyTracking:
    def test_villainy_card_played_sets_flag(self, repo):
        """Playing a Villainy card records the playing player in
        villainy_players_this_phase (controller-scoped)."""
        # Death Star Stormtrooper: Villainy aspect, cost 1, no complex abilities
        villainy_card = _get_card(repo, "SOR", "128")
        state = _make_state()
        from swu.engine.state import CardInstance, Zone
        ps = state.players[0]
        unit_ci = CardInstance("p0_unit", villainy_card, "P0", Zone.HAND)
        ps.hand.append(unit_ci)
        _give_resources(state, "P0", 10)

        assert "P0" not in state.game_memory.villainy_players_this_phase

        from swu.engine.actions import apply, PlayCard
        state = apply(state, PlayCard(unit_ci.instance_id))

        assert "P0" in state.game_memory.villainy_players_this_phase
        assert "P1" not in state.game_memory.villainy_players_this_phase

    def test_heroism_card_does_not_set_flag(self, repo):
        """Playing a Heroism card does not record the player in
        villainy_players_this_phase."""
        heroism_card = _get_card(repo, "SOR", "74")  # Repair (Heroism aspect)
        state = _make_state()
        from swu.engine.state import CardInstance, Zone
        ps = state.players[0]
        rep_ci = CardInstance("p0_repair", heroism_card, "P0", Zone.HAND)
        ps.hand.append(rep_ci)
        _give_resources(state, "P0", 10)
        # Give a target for the heal
        dummy = _get_card(repo, "SOR", "46")
        target_ci = _place(state, "P0", dummy, "ground")
        target_ci.damage = 2

        from swu.engine.actions import apply, PlayCard, ChooseTarget, legal_actions, AutoResolveEffects
        state = apply(state, PlayCard(rep_ci.instance_id))
        while state.pending_decisions:
            acts = legal_actions(state)
            if any(isinstance(a, AutoResolveEffects) for a in acts):
                state = apply(state, AutoResolveEffects())
                break
            choose = next((a for a in acts if isinstance(a, ChooseTarget)), None)
            if choose:
                state = apply(state, choose)
            else:
                break

        assert "P0" not in state.game_memory.villainy_players_this_phase


# ── Surprise Strike (effect-granted attack with a stat bonus) ─────────────────

class TestSurpriseStrike:
    def test_grants_attack_with_plus_3_to_base(self, repo):
        """Surprise Strike: chosen unit attacks and gets +3/+0 for that attack."""
        from swu.engine.actions import (
            apply, legal_actions, PlayCard, AttackWithUnit,
        )
        from swu.engine.state import CardInstance, Zone

        ss = _get_card(repo, "SOR", "220")           # Surprise Strike (event)
        attacker_def = _get_card(repo, "SOR", "46")  # Consular Security Force, power 3

        state = _make_state()
        attacker = _place(state, "P0", attacker_def, "ground")
        ss_ci = CardInstance("p0_ss", ss, "P0", Zone.HAND)
        state.players[0].hand.append(ss_ci)
        _give_resources(state, "P0", 10)

        enemy_base = state.players[1].base_instance
        base_dmg_before = enemy_base.damage

        # Play the event — should push a granted_attack decision, not pass the turn.
        state = apply(state, PlayCard(ss_ci.instance_id))
        assert state.pending_decisions, "Surprise Strike should push a granted_attack decision"
        assert state.pending_decisions[-1].kind == "granted_attack"

        # The decision offers AttackWithUnit options for the ready unit.
        acts = legal_actions(state)
        base_attack = next(
            a for a in acts
            if isinstance(a, AttackWithUnit)
            and a.attacker_id == attacker.instance_id
            and a.defender_id is None
        )
        state = apply(state, base_attack)

        # Base took base power (3) + Surprise Strike bonus (3) = 6.
        enemy_base = state.players[1].base_instance
        assert enemy_base.damage - base_dmg_before == attacker_def.power + 3
        # The this-attack modifier must not linger after combat settles.
        assert not state.pending_decisions
        assert all(m.duration != "this_attack" for m in state.modifiers)


# ── Fleet Lieutenant / Snowtrooper Lieutenant (When Played: grant attack) ─────

class TestGrantAttackOnPlay:
    def _play_unit_and_get_decision(self, repo, lt_num):
        """Place a Rebel + an Imperial ready attacker, play the lieutenant, return state."""
        from swu.engine.actions import apply, PlayCard
        from swu.engine.state import CardInstance, Zone
        lt = _get_card(repo, "SOR", lt_num)
        rebel = _get_card(repo, "SOR", "46")    # Consular Security Force (Rebel, power 3)
        imp = _get_card(repo, "SOR", "128")     # Death Star Stormtrooper (Imperial, power 3)
        state = _make_state()
        rebel_ci = _place(state, "P0", rebel, "ground")
        imp_ci = _place(state, "P0", imp, "ground")
        lt_ci = CardInstance("p0_lt", lt, "P0", Zone.HAND)
        state.players[0].hand.append(lt_ci)
        _give_resources(state, "P0", 10)
        state = apply(state, PlayCard(lt_ci.instance_id))
        return state, rebel_ci, imp_ci

    def test_fleet_lieutenant_buffs_rebel_attacker(self, repo):
        """Fleet Lieutenant: chosen Rebel unit gets +2/+0 for the granted attack."""
        from swu.engine.actions import apply, legal_actions, AttackWithUnit
        state, rebel_ci, imp_ci = self._play_unit_and_get_decision(repo, "240")
        assert state.pending_decisions[-1].kind == "granted_attack"
        base_before = state.players[1].base_instance.damage
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == rebel_ci.instance_id and a.defender_id is None)
        state = apply(state, atk)
        # Consular power 3 + Rebel bonus 2 = 5.
        assert state.players[1].base_instance.damage - base_before == 3 + 2

    def test_fleet_lieutenant_no_buff_for_non_rebel(self, repo):
        """Fleet Lieutenant: a non-Rebel attacker gets no bonus."""
        from swu.engine.actions import apply, legal_actions, AttackWithUnit
        state, rebel_ci, imp_ci = self._play_unit_and_get_decision(repo, "240")
        base_before = state.players[1].base_instance.damage
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == imp_ci.instance_id and a.defender_id is None)
        state = apply(state, atk)
        assert state.players[1].base_instance.damage - base_before == 3  # base power only

    def test_snowtrooper_lieutenant_buffs_imperial_and_is_optional(self, repo):
        """Snowtrooper Lieutenant: +2/+0 to an Imperial attacker; attack is optional."""
        from swu.engine.actions import (
            apply, legal_actions, AttackWithUnit, DeclineGrantedAttack,
        )
        state, rebel_ci, imp_ci = self._play_unit_and_get_decision(repo, "227")
        acts = legal_actions(state)
        assert any(isinstance(a, DeclineGrantedAttack) for a in acts), "may-attack must allow decline"
        base_before = state.players[1].base_instance.damage
        atk = next(a for a in acts
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == imp_ci.instance_id and a.defender_id is None)
        state = apply(state, atk)
        assert state.players[1].base_instance.damage - base_before == 3 + 2

    def test_decline_granted_attack_fizzles(self, repo):
        """Declining an optional granted attack resolves cleanly with no attack."""
        from swu.engine.actions import apply, legal_actions, DeclineGrantedAttack
        state, rebel_ci, imp_ci = self._play_unit_and_get_decision(repo, "227")
        base_before = state.players[1].base_instance.damage
        decline = next(a for a in legal_actions(state) if isinstance(a, DeclineGrantedAttack))
        state = apply(state, decline)
        assert not state.pending_decisions
        assert state.players[1].base_instance.damage == base_before


class TestViperProbeDroid:
    def test_logs_hand_inspection(self, repo):
        """Viper Probe Droid: When Played logs HandInspected AND pushes a private
        'look_hand' decision carrying the opponent's hand identities to the
        inspecting player (so the UI can actually show the hand), resolved by an
        AckLookHand.  No state change to the opponent's hand."""
        from swu.engine.actions import apply, legal_actions, PlayCard, AckLookHand
        from swu.engine.state import CardInstance, Zone
        from swu.engine.events import HandInspected
        viper = _get_card(repo, "SOR", "228")
        filler = _get_card(repo, "SOR", "46")
        state = _make_state()
        # Give the opponent a couple of cards in hand.
        for i in range(2):
            state.players[1].hand.append(CardInstance(f"p1_h{i}", filler, "P1", Zone.HAND))
        viper_ci = CardInstance("p0_viper", viper, "P0", Zone.HAND)
        state.players[0].hand.append(viper_ci)
        _give_resources(state, "P0", 10)
        opp_hand_before = len(state.players[1].hand)
        state = apply(state, PlayCard(viper_ci.instance_id))

        evt = next((e for e in state.event_log if isinstance(e, HandInspected)), None)
        assert evt is not None
        assert evt.revealed_player_id == "P1"
        assert evt.card_count == opp_hand_before

        # A private look_hand decision is now pending for the inspecting player,
        # carrying the revealed hand's card identities (card_id + name only —
        # never the opponent's hidden instance_ids).
        top = state.pending_decisions[-1]
        assert top.kind == "look_hand"
        assert top.deciding_player_id == "P0"
        revealed = top.context["revealed_hand"]
        assert len(revealed) == opp_hand_before
        assert all("card_id" in c and "card_name" in c for c in revealed)
        assert all("instance_id" not in c for c in revealed)  # no hidden-info leak

        # AckLookHand resolves it; the opponent's hand is unchanged (info only).
        ack = next(a for a in legal_actions(state) if isinstance(a, AckLookHand))
        state = apply(state, ack)
        assert not state.pending_decisions
        assert len(state.players[1].hand) == opp_hand_before

    def test_look_hand_not_leaked_to_opponent_view(self, repo):
        """The revealed hand lives only in the inspector's redacted view — the
        opponent's own view must not carry the look_hand context."""
        from swu.engine.actions import apply, PlayCard
        from swu.engine.state import CardInstance, Zone
        viper = _get_card(repo, "SOR", "228")
        filler = _get_card(repo, "SOR", "46")
        state = _make_state()
        state.players[1].hand.append(CardInstance("p1_h0", filler, "P1", Zone.HAND))
        viper_ci = CardInstance("p0_viper", viper, "P0", Zone.HAND)
        state.players[0].hand.append(viper_ci)
        _give_resources(state, "P0", 10)
        state = apply(state, PlayCard(viper_ci.instance_id))

        p0_view = state.view_for("P0")
        p1_view = state.view_for("P1")
        # Inspector (P0) sees the revealed hand; opponent (P1) sees an empty ctx.
        assert p0_view.pending_decisions[-1].context.get("revealed_hand")
        assert p1_view.pending_decisions[-1].context == {}


# ── First Strike (Shoot First event, Han Solo innate) ─────────────────────────

class TestFirstStrike:
    def test_shoot_first_grants_plus1_and_first_strike(self, repo):
        """Shoot First: +1/+0 and first strike — a lethal hit means no return damage."""
        from swu.engine.actions import apply, legal_actions, PlayCard, AttackWithUnit
        from swu.engine.state import CardInstance, Zone
        ss = _get_card(repo, "SOR", "217")        # Shoot First (event)
        attacker = _get_card(repo, "SOR", "46")   # Consular Security Force (power 3, hp 7)
        defender = _get_card(repo, "SOR", "128")  # Death Star Stormtrooper (power 3, hp 1)
        state = _make_state()
        atk_ci = _place(state, "P0", attacker, "ground")
        def_ci = _place(state, "P1", defender, "ground")
        ss_ci = CardInstance("p0_ss", ss, "P0", Zone.HAND)
        state.players[0].hand.append(ss_ci)
        _give_resources(state, "P0", 10)

        state = apply(state, PlayCard(ss_ci.instance_id))
        assert state.pending_decisions[-1].kind == "granted_attack"
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == atk_ci.instance_id
                   and a.defender_id == def_ci.instance_id)
        state = apply(state, atk)

        # Defender (1 HP) is defeated by 3+1=4 first-strike damage and deals none back.
        assert _find_instance(state, def_ci.instance_id) is None, "defender should be defeated"
        atk_now = _find_instance(state, atk_ci.instance_id)
        assert atk_now is not None and atk_now.damage == 0, "first striker takes no return damage"

    def test_han_solo_has_first_strike_and_takes_no_return_damage(self, repo):
        """Han Solo: innate First Strike — kills a small defender, takes no damage back."""
        from swu.engine.actions import apply, AttackWithUnit
        from swu.engine.keywords import has_keyword, Keyword
        han = _get_card(repo, "SOR", "198")       # Han Solo (power 6, hp 6)
        defender = _get_card(repo, "SOR", "128")  # Death Star Stormtrooper (power 3, hp 1)
        state = _make_state()
        han_ci = _place(state, "P0", han, "ground")
        def_ci = _place(state, "P1", defender, "ground")

        assert has_keyword(state, han_ci, Keyword.FIRST_STRIKE)
        state = apply(state, AttackWithUnit(han_ci.instance_id, def_ci.instance_id))
        assert _find_instance(state, def_ci.instance_id) is None, "defender defeated"
        han_now = _find_instance(state, han_ci.instance_id)
        assert han_now is not None and han_now.damage == 0, "Han takes no return damage"


# ── Admiral Ozzel (play an Imperial unit from hand; enters ready) ─────────────

class TestAdmiralOzzel:
    """SOR_129 — Action [exhaust]: Play an Imperial unit from your hand (paying
    its cost). It enters play ready. Each opponent may ready a unit.

    Exercises the play-from-hand subsystem end-to-end via apply()."""

    def _setup(self, repo, *, hand_imperial=True, hand_other=True,
               opp_exhausted_unit=True, resources=10):
        """Ozzel ready in P0's arena; an Imperial (and/or non-Imperial) unit in
        P0's hand; optionally an exhausted P1 unit to ready.  Returns
        (state, ozzel_ci, imperial_ci, other_ci, opp_unit_ci)."""
        from swu.engine.state import CardInstance, Zone
        ozzel = _get_card(repo, "SOR", "129")
        state = _make_state()
        ozzel_ci = _place(state, "P0", ozzel, "ground")
        ozzel_ci.exhausted = False  # ready, so the exhaust cost is payable

        imperial_ci = other_ci = opp_unit_ci = None
        if hand_imperial:
            imp = _get_card(repo, "SOR", "128")  # Death Star Stormtrooper (Imperial, cost 1)
            imperial_ci = CardInstance("p0_imp", imp, "P0", Zone.HAND)
            state.players[0].hand.append(imperial_ci)
        if hand_other:
            reb = _get_card(repo, "SOR", "46")    # Consular Security Force (Rebel, cost 3)
            other_ci = CardInstance("p0_reb", reb, "P0", Zone.HAND)
            state.players[0].hand.append(other_ci)
        if opp_exhausted_unit:
            opp = _get_card(repo, "SOR", "46")
            opp_unit_ci = _place(state, "P1", opp, "ground")
            opp_unit_ci.exhausted = True
        _give_resources(state, "P0", resources)
        return state, ozzel_ci, imperial_ci, other_ci, opp_unit_ci

    def _use_ozzel(self, state, ozzel_ci):
        from swu.engine.actions import legal_actions, apply, UseAbility
        use = next(
            a for a in legal_actions(state)
            if isinstance(a, UseAbility) and a.source_id == ozzel_ci.instance_id
        )
        return apply(state, use)

    def test_ability_offered_and_exhausts_ozzel(self, repo):
        """Using the ability exhausts Ozzel and pushes a play_from_hand decision."""
        state, ozzel_ci, imp_ci, *_ = self._setup(repo)
        state = self._use_ozzel(state, ozzel_ci)
        assert state.pending_decisions, "expected a pending decision after using Ozzel"
        assert state.pending_decisions[-1].kind == "play_from_hand"
        ozzel_now = _find_instance(state, ozzel_ci.instance_id)
        assert ozzel_now is not None and ozzel_now.exhausted, "Ozzel pays its exhaust cost"

    def test_only_affordable_imperial_units_offered(self, repo):
        """play_from_hand lists only Imperial units; the Rebel card is excluded."""
        from swu.engine.actions import legal_actions, PlayFromHand
        state, ozzel_ci, imp_ci, other_ci, _ = self._setup(repo)
        state = self._use_ozzel(state, ozzel_ci)
        offered = {a.instance_id for a in legal_actions(state) if isinstance(a, PlayFromHand)}
        assert offered == {imp_ci.instance_id}, "only the Imperial unit is playable"

    def test_unit_enters_ready_then_opponent_ready_pushed(self, repo):
        """The played unit enters play ready; an opponent_ready decision follows."""
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        state, ozzel_ci, imp_ci, _, opp_unit_ci = self._setup(repo)
        state = self._use_ozzel(state, ozzel_ci)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand) and a.instance_id == imp_ci.instance_id)
        state = apply(state, play)

        played = _find_instance(state, imp_ci.instance_id)
        assert played is not None, "Imperial unit is now in play"
        assert not played.exhausted, "it entered play ready"
        assert state.pending_decisions[-1].kind == "opponent_ready"
        # Cost was paid (effective cost includes any unmatched-aspect penalty).
        from swu.engine.actions import _effective_cost
        cost = _effective_cost(imp_ci.card_def, state.players[0])
        assert state.players[0].available_resources == 10 - cost

    def test_opponent_readies_a_unit_then_turn_passes(self, repo):
        """The opponent readies an exhausted unit; control passes to the opponent."""
        from swu.engine.actions import legal_actions, apply, PlayFromHand, ReadyUnit
        state, ozzel_ci, imp_ci, _, opp_unit_ci = self._setup(repo)
        state = self._use_ozzel(state, ozzel_ci)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand) and a.instance_id == imp_ci.instance_id)
        state = apply(state, play)

        ready = next(a for a in legal_actions(state)
                     if isinstance(a, ReadyUnit) and a.instance_id == opp_unit_ci.instance_id)
        state = apply(state, ready)
        assert not state.pending_decisions, "all decisions resolved"
        opp_now = _find_instance(state, opp_unit_ci.instance_id)
        assert opp_now is not None and not opp_now.exhausted, "opponent's unit is readied"
        assert state.active_player_index == 1, "turn passes to the opponent (P1)"

    def test_opponent_may_decline_to_ready(self, repo):
        """'May ready' — the opponent can decline, leaving the unit exhausted."""
        from swu.engine.actions import legal_actions, apply, PlayFromHand, DeclineReadyUnit
        state, ozzel_ci, imp_ci, _, opp_unit_ci = self._setup(repo)
        state = self._use_ozzel(state, ozzel_ci)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand) and a.instance_id == imp_ci.instance_id)
        state = apply(state, play)

        decline = next(a for a in legal_actions(state) if isinstance(a, DeclineReadyUnit))
        state = apply(state, decline)
        assert not state.pending_decisions
        opp_now = _find_instance(state, opp_unit_ci.instance_id)
        assert opp_now is not None and opp_now.exhausted, "declined — unit stays exhausted"
        assert state.active_player_index == 1

    def test_no_opponent_units_skips_ready_step(self, repo):
        """With no exhausted opponent unit, no opponent_ready decision is pushed."""
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        state, ozzel_ci, imp_ci, _, _ = self._setup(repo, opp_exhausted_unit=False)
        state = self._use_ozzel(state, ozzel_ci)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand) and a.instance_id == imp_ci.instance_id)
        state = apply(state, play)
        assert not state.pending_decisions, "nothing to ready — ability fully resolves"
        assert state.active_player_index == 1, "turn passes to the opponent"

    def test_no_affordable_imperial_unit_is_not_offered(self, repo):
        """With no affordable Imperial unit in hand, the ability is NOT offered.

        Activating Ozzel plays no unit but still readies each opponent's units —
        pure self-harm — so the CONTROLLER_CAN_PLAY_UNIT_FROM_HAND gate withholds
        the action entirely (it would never be a correct play).  This protects
        the bot (and a misclicking human) from gifting the opponent free tempo.
        """
        from swu.engine.actions import legal_actions, UseAbility
        # Only a Rebel unit in hand; no Imperial to play.
        state, ozzel_ci, _, other_ci, opp_unit_ci = self._setup(
            repo, hand_imperial=False)
        assert not any(
            isinstance(a, UseAbility) and a.source_id == ozzel_ci.instance_id
            for a in legal_actions(state)
        ), "Ozzel must not be offered when no Imperial unit is playable"

    def test_not_offered_when_imperial_unit_unaffordable(self, repo):
        """An Imperial unit in hand the controller cannot pay for does not unlock
        the ability — the gate checks affordability, not mere presence."""
        from swu.engine.actions import legal_actions, UseAbility
        state, ozzel_ci, imp_ci, *_ = self._setup(repo, resources=0)
        assert not any(
            isinstance(a, UseAbility) and a.source_id == ozzel_ci.instance_id
            for a in legal_actions(state)
        ), "unaffordable Imperial unit must not unlock Ozzel"

    def test_offered_when_imperial_unit_playable(self, repo):
        """The ability IS offered when an affordable Imperial unit is in hand."""
        from swu.engine.actions import legal_actions, UseAbility
        state, ozzel_ci, imp_ci, *_ = self._setup(repo)
        assert any(
            isinstance(a, UseAbility) and a.source_id == ozzel_ci.instance_id
            for a in legal_actions(state)
        )


# ── First Legion Snowtrooper ──────────────────────────────────────────────────

class TestFirstLegionSnowTrooper:
    def test_buffs_vs_damaged_defender(self, repo):
        """First Legion Snowtrooper: +2/+0 and Overwhelm when attacking a damaged unit."""
        snowtrooper = _get_card(repo, "SOR", "130")
        defender = _get_card(repo, "SOR", "46")   # Consular Security Force
        state = _make_state()
        st_ci = _place(state, "P0", snowtrooper, "ground")
        def_ci = _place(state, "P1", defender, "ground")
        def_ci.damage = 1  # damaged

        base_power = snowtrooper.power
        state = _fire_on_attack(state, st_ci, def_ci)

        from swu.engine.actions import compute_power
        from swu.engine.keywords import has_keyword, Keyword
        assert compute_power(state, st_ci) == base_power + 2
        assert has_keyword(state, st_ci, Keyword.OVERWHELM)

    def test_no_buff_vs_undamaged_defender(self, repo):
        """First Legion Snowtrooper: no buff when attacking an undamaged unit."""
        snowtrooper = _get_card(repo, "SOR", "130")
        defender = _get_card(repo, "SOR", "46")
        state = _make_state()
        st_ci = _place(state, "P0", snowtrooper, "ground")
        def_ci = _place(state, "P1", defender, "ground")
        def_ci.damage = 0  # undamaged

        base_power = snowtrooper.power
        state = _fire_on_attack(state, st_ci, def_ci)

        from swu.engine.actions import compute_power
        assert compute_power(state, st_ci) == base_power


class TestBlizzardAssaultATAT:
    def test_on_attack_defeats_unit_optional_trigger(self, repo):
        """Blizzard Assault AT-AT: after defeating a unit, may deal 3 to another ground unit."""
        at_at = _get_card(repo, "SOR", "88")
        weak_enemy = _get_card(repo, "SOR", "128")   # 1-HP Death Star Stormtrooper
        other_enemy = _get_card(repo, "SOR", "232")  # AT-ST (7 HP)
        state = _make_state()
        at_ci = _place(state, "P0", at_at, "ground")
        weak_ci = _place(state, "P1", weak_enemy, "ground")
        _place(state, "P1", other_enemy, "ground")

        from swu.engine.actions import AttackWithUnit, apply
        state = apply(state, AttackWithUnit(at_ci.instance_id, weak_ci.instance_id))

        # Stormtrooper should be in discard (defeated), not in an arena
        opp_ps = state.players[1]
        in_arena = any(ci.instance_id == weak_ci.instance_id
                       for ci in opp_ps.ground_arena + opp_ps.space_arena)
        assert not in_arena, "Stormtrooper should be removed from arena (defeated)"
        in_discard = any(ci.instance_id == weak_ci.instance_id for ci in opp_ps.discard)
        assert in_discard, "Stormtrooper should be in discard"

    def test_registration(self):
        """Blizzard Assault AT-AT: properly registered with OnAttackDefeatsUnit trigger."""
        from swu.abilities.registry import get_abilities, TriggerAbility, OnAttackDefeatsUnit
        import swu.cards.sor  # noqa: F401
        specs = get_abilities("SOR", "88")
        assert len(specs) == 1
        assert isinstance(specs[0], TriggerAbility)
        assert isinstance(specs[0].trigger, OnAttackDefeatsUnit)


def _play_event_from_hand(state, repo, set_code, num, owner="P0", resources=10):
    """Put an event card in `owner`'s hand and play it; returns (state, event_ci)."""
    from swu.engine.state import CardInstance, Zone
    from swu.engine.actions import apply, PlayCard
    card = _get_card(repo, set_code, num)
    ci = CardInstance(f"{owner}_{num}_evt", card, owner, Zone.HAND)
    state.player_by_id(owner).hand.append(ci)
    _give_resources(state, owner, resources)
    return apply(state, PlayCard(ci.instance_id)), ci


# ── Emperor Palpatine (divided damage pool) ──────────────────────────────────

class TestEmperorPalpatine:
    def test_when_played_pushes_distribution(self, repo):
        """Palpatine When Played pushes a 6-point distribute_damage pool over enemies."""
        palp = _get_card(repo, "SOR", "135")
        palp_ci = _place(state := _make_state(), "P0", palp, "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 7 hp
        state = _fire_when_played(state, palp_ci)
        top = state.pending_decisions[-1]
        assert top.kind == "distribute_damage"
        assert top.context["mode"] == "pool"
        assert top.context["pool"] == 6
        assert top.deciding_player_id == "P0"

    def test_divides_six_damage_as_chosen(self, repo):
        """Controller splits the 6-point pool 4/2 across two enemy units."""
        from swu.engine.actions import legal_actions, apply, AssignDamage
        palp = _get_card(repo, "SOR", "135")
        palp_ci = _place(state := _make_state(), "P0", palp, "ground")
        big = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")    # 7 hp
        small = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")  # 1 hp
        state = _fire_when_played(state, palp_ci)

        for i in range(6):
            tid = big.instance_id if i < 4 else small.instance_id
            acts = legal_actions(state)
            assert acts, "legal_actions must never be empty mid-distribution"
            act = next(a for a in acts if isinstance(a, AssignDamage) and a.target_id == tid)
            state = apply(state, act)

        assert not state.pending_decisions, "pool fully spent -> decision resolved"
        big_left = _find_instance(state, big.instance_id)
        assert big_left is not None and big_left.damage == 4
        assert _find_instance(state, small.instance_id) is None, "1-hp unit defeated by 2"
        assert state.active_player_index == 1, "turn handed to opponent"

    def test_only_enemy_units_are_targetable(self, repo):
        """The pool may only be assigned to ENEMY units (friendly units excluded)."""
        from swu.engine.actions import legal_actions, AssignDamage
        palp = _get_card(repo, "SOR", "135")
        palp_ci = _place(state := _make_state(), "P0", palp, "ground")
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, palp_ci)
        targets = {a.target_id for a in legal_actions(state) if isinstance(a, AssignDamage)}
        assert enemy.instance_id in targets
        assert friendly.instance_id not in targets
        assert palp_ci.instance_id not in targets

    def test_fizzles_with_no_enemy_units(self, repo):
        """No enemy units -> no decision pushed, effect fizzles cleanly."""
        palp = _get_card(repo, "SOR", "135")
        palp_ci = _place(state := _make_state(), "P0", palp, "ground")
        state = _fire_when_played(state, palp_ci)
        assert not state.pending_decisions

    def test_no_longer_escape_hatch(self):
        from swu.abilities.registry import is_escape_hatch
        import swu.cards.sor  # noqa: F401
        assert not is_escape_hatch("SOR", "135")


# ── Overwhelming Barrage (source picks, distributes its power) ────────────────

class TestOverwhelmingBarrage:
    def test_buffs_chosen_source_and_divides_its_power(self, repo):
        """Player picks the AT-ST, it gets +2/+2, then divides its 8 power."""
        from swu.engine.actions import (legal_actions, apply, compute_power,
                                         ChooseDamageSource, AssignDamage)
        atst = _place(state := _make_state(), "P0", _get_card(repo, "SOR", "232"), "ground")
        e1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")    # 7 hp
        e2 = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")   # 1 hp
        power_before = compute_power(state, atst)
        state, _ = _play_event_from_hand(state, repo, "SOR", "92")

        top = state.pending_decisions[-1]
        assert top.kind == "distribute_damage" and top.context["stage"] == "pick_source"
        src = next(a for a in legal_actions(state)
                   if isinstance(a, ChooseDamageSource) and a.unit_id == atst.instance_id)
        state = apply(state, src)

        # Buff applied: AT-ST is now power_before + 2; that is the pool size.
        atst_now = _find_instance(state, atst.instance_id)
        assert compute_power(state, atst_now) == power_before + 2
        assert state.pending_decisions[-1].context["pool"] == power_before + 2

        # The source itself is NOT a legal target ("other units").
        targets = {a.target_id for a in legal_actions(state) if isinstance(a, AssignDamage)}
        assert atst.instance_id not in targets
        assert {e1.instance_id, e2.instance_id} <= targets

        # Divide 7 onto e1, rest onto e2.
        pool = state.pending_decisions[-1].context["pool"]
        for i in range(pool):
            tid = e1.instance_id if i < 7 else e2.instance_id
            acts = legal_actions(state)
            assert acts
            state = apply(state, next(a for a in acts
                                      if isinstance(a, AssignDamage) and a.target_id == tid))
        assert not state.pending_decisions
        assert _find_instance(state, e1.instance_id) is None, "7 damage defeats the 7-hp unit"

    def test_buff_persists_this_phase(self, repo):
        """The +2/+2 buff is a this_phase modifier left on the chosen source."""
        from swu.engine.actions import legal_actions, apply, ChooseDamageSource
        atst = _place(state := _make_state(), "P0", _get_card(repo, "SOR", "232"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "SOR", "92")
        src = next(a for a in legal_actions(state) if isinstance(a, ChooseDamageSource))
        state = apply(state, src)
        mods = [m for m in state.modifiers
                if m.target_instance_id == atst.instance_id and m.kind == "stats"]
        assert mods and mods[0].duration == "this_phase"
        assert mods[0].value == {"power": 2, "hp": 2}

    def test_fizzles_with_no_friendly_unit(self, repo):
        """No friendly source -> no decision pushed."""
        _place(state := _make_state(), "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "SOR", "92")
        assert not state.pending_decisions

    def test_no_longer_escape_hatch(self):
        from swu.abilities.registry import is_escape_hatch
        import swu.cards.sor  # noqa: F401
        assert not is_escape_hatch("SOR", "92")


# ── Maximum Firepower (two Imperial sources hit one target) ──────────────────

class TestMaximumFirepower:
    def test_two_sources_hit_same_target(self, repo):
        """Pick target, then two distinct Imperial sources each deal their power."""
        from swu.engine.actions import (legal_actions, apply,
                                         ChooseDamageTarget, ChooseDamageSource)
        s1 = _place(state := _make_state(), "P0", _get_card(repo, "SOR", "232"), "ground")  # power 6
        s2 = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")                    # power 3
        tgt = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")                    # 7 hp
        state, _ = _play_event_from_hand(state, repo, "SOR", "234")

        assert state.pending_decisions[-1].context["stage"] == "pick_target"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseDamageTarget) and a.target_id == tgt.instance_id))
        # First source: 6 damage, target (7 hp) survives.
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseDamageSource) and a.unit_id == s1.instance_id))
        survivor = _find_instance(state, tgt.instance_id)
        assert survivor is not None and survivor.damage == 6
        # s1 is no longer offered (distinct sources).
        remaining = {a.unit_id for a in legal_actions(state) if isinstance(a, ChooseDamageSource)}
        assert remaining == {s2.instance_id}
        # Second source: +3 -> 9 total -> defeated.
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseDamageSource) and a.unit_id == s2.instance_id))
        assert not state.pending_decisions
        assert _find_instance(state, tgt.instance_id) is None

    def test_stops_when_target_defeated_by_first_source(self, repo):
        """If the first source kills the target, no second source is requested."""
        from swu.engine.actions import (legal_actions, apply,
                                         ChooseDamageTarget, ChooseDamageSource)
        _place(state := _make_state(), "P0", _get_card(repo, "SOR", "232"), "ground")  # power 6
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        tgt = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")  # 1 hp
        state, _ = _play_event_from_hand(state, repo, "SOR", "234")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseDamageTarget) and a.target_id == tgt.instance_id))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseDamageSource)))
        assert not state.pending_decisions, "target dead -> sequence finished, no 2nd source"
        assert _find_instance(state, tgt.instance_id) is None

    def test_only_imperial_units_are_sources(self, repo):
        """Only friendly Imperial units may be chosen as sources."""
        from swu.engine.actions import legal_actions, apply, ChooseDamageTarget, ChooseDamageSource
        imp = _place(state := _make_state(), "P0", _get_card(repo, "SOR", "232"), "ground")  # Imperial
        reb = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # Rebel (not Imperial)
        tgt = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "SOR", "234")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseDamageTarget) and a.target_id == tgt.instance_id))
        sources = {a.unit_id for a in legal_actions(state) if isinstance(a, ChooseDamageSource)}
        assert imp.instance_id in sources
        assert reb.instance_id not in sources

    def test_fizzles_with_no_imperial_units(self, repo):
        """No friendly Imperial unit -> no decision pushed."""
        _place(state := _make_state(), "P0", _get_card(repo, "SOR", "46"), "ground")  # Rebel
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "SOR", "234")
        assert not state.pending_decisions

    def test_no_longer_escape_hatch(self):
        from swu.abilities.registry import is_escape_hatch
        import swu.cards.sor  # noqa: F401
        assert not is_escape_hatch("SOR", "234")


# ── Deck search-and-select helpers (Tarkin / Recruit) ─────────────────────────

_DECK_SEARCH_SEED = 1234


def _seed_rng(state, seed=_DECK_SEARCH_SEED):
    """Pin the game RNG so the random bottoming order is reproducible in a test."""
    import random as _r
    state.rng_state = _r.Random(seed).getstate()
    return state


def _expected_bottom_order(skipped_ids, seed=_DECK_SEARCH_SEED):
    """Replicate _finish_deck_search's seeded shuffle of the un-taken cards so a
    test can assert the exact deterministic bottom-of-deck order."""
    import random as _r
    ids = list(skipped_ids)
    _r.Random(seed).shuffle(ids)
    return ids


def _build_search_deck(state, owner_id, top_cards, below_cards=()):
    """Lay out a player's deck as `top_cards` (the searched window) on top of
    `below_cards` (the un-searched remainder).  Returns the CardInstances created,
    in deck (top-to-bottom) order."""
    from swu.engine.state import CardInstance, Zone
    ps = state.player_by_id(owner_id)
    out = []
    for i, card in enumerate(list(top_cards) + list(below_cards)):
        ci = CardInstance(f"{owner_id}_deck_{i}", card, owner_id, Zone.DECK)
        ps.deck.append(ci)
        out.append(ci)
    return out


def _search_actions(state):
    from swu.engine.actions import legal_actions
    return legal_actions(state)


def _take_from_search(state, instance_id):
    from swu.engine.actions import apply, SelectSearchCard
    return apply(state, SelectSearchCard(instance_id))


def _finish_search(state):
    from swu.engine.actions import apply, FinishSearch
    return apply(state, FinishSearch())


# ── Grand Moff Tarkin (search top 5 for up to 2 Imperial cards) ───────────────

class TestGrandMoffTarkin:
    def _setup(self, repo):
        """Tarkin in play; top 5 = imp,imp,other,other,other; 2 cards below."""
        tarkin = _get_card(repo, "SOR", "84")
        imperial = _get_card(repo, "SOR", "128")  # Death Star Stormtrooper (Imperial)
        other = _get_card(repo, "SOR", "46")      # Consular Security Force (Rebel)
        below = _get_card(repo, "SOR", "74")      # Repair (event, stays on top)
        state = _seed_rng(_make_state())
        tarkin_ci = _place(state, "P0", tarkin, "ground")
        deck = _build_search_deck(
            state, "P0",
            top_cards=[imperial, imperial, other, other, other],
            below_cards=[below, below],
        )
        state = _fire_when_played(state, tarkin_ci)
        return state, deck

    def test_pushes_deck_search_decision(self, repo):
        from swu.engine.actions import SelectSearchCard, FinishSearch
        state, deck = self._setup(repo)
        assert state.pending_decisions, "Tarkin should push a deck_search decision"
        assert state.pending_decisions[-1].kind == "deck_search"
        acts = _search_actions(state)
        # Two Imperial candidates offered, plus FinishSearch ("up to" → 0 is legal).
        selects = [a for a in acts if isinstance(a, SelectSearchCard)]
        assert {a.instance_id for a in selects} == {deck[0].instance_id, deck[1].instance_id}
        assert any(isinstance(a, FinishSearch) for a in acts)

    def test_take_two_imperial_bottoms_rest_deterministically(self, repo):
        state, deck = self._setup(repo)
        ps = state.players[0]
        hand_before = len(ps.hand)
        # Take both Imperial cards (second take auto-finishes at the cap of 2).
        state = _take_from_search(state, deck[0].instance_id)
        state = _take_from_search(state, deck[1].instance_id)
        assert not state.pending_decisions, "Reaching the cap auto-finishes the search"
        ps = state.players[0]
        hand_ids = {ci.instance_id for ci in ps.hand}
        assert len(ps.hand) == hand_before + 2
        assert {deck[0].instance_id, deck[1].instance_id} <= hand_ids
        # Un-searched remainder (the two 'below' cards) stays on top, in order.
        assert [ci.instance_id for ci in ps.deck[:2]] == [deck[5].instance_id, deck[6].instance_id]
        # The three un-taken top-5 cards are bottomed in the seeded-random order.
        expected = _expected_bottom_order(
            [deck[2].instance_id, deck[3].instance_id, deck[4].instance_id])
        assert [ci.instance_id for ci in ps.deck[2:]] == expected

    def test_take_one_imperial(self, repo):
        state, deck = self._setup(repo)
        ps = state.players[0]
        hand_before = len(ps.hand)
        state = _take_from_search(state, deck[0].instance_id)
        # One taken, cap is 2 → still pending; finish early ("up to" 1).
        assert state.pending_decisions
        state = _finish_search(state)
        ps = state.players[0]
        assert len(ps.hand) == hand_before + 1
        assert any(ci.instance_id == deck[0].instance_id for ci in ps.hand)
        # Bottom = seeded shuffle of the four un-taken top-5 cards.
        expected = _expected_bottom_order([deck[i].instance_id for i in (1, 2, 3, 4)])
        assert [ci.instance_id for ci in ps.deck[2:]] == expected

    def test_take_zero_imperial(self, repo):
        state, deck = self._setup(repo)
        ps = state.players[0]
        hand_before = len(ps.hand)
        state = _finish_search(state)  # decline all ("up to" 0)
        ps = state.players[0]
        assert len(ps.hand) == hand_before, "Taking 0 draws nothing"
        # All five top cards are bottomed (seeded order); the 'below' cards stay on top.
        assert [ci.instance_id for ci in ps.deck[:2]] == [deck[5].instance_id, deck[6].instance_id]
        expected = _expected_bottom_order([deck[i].instance_id for i in range(5)])
        assert [ci.instance_id for ci in ps.deck[2:]] == expected

    def test_imperial_means_trait_not_aspect(self, repo):
        """A Villainy/Command card without the Imperial trait is NOT a candidate."""
        from swu.cards.sor.abilities import _is_imperial_card
        # Death Star Stormtrooper: Imperial trait → eligible.
        assert _is_imperial_card(_get_card(repo, "SOR", "128"))
        # Consular Security Force: Rebel, no Imperial trait → not eligible.
        assert not _is_imperial_card(_get_card(repo, "SOR", "46"))


# ── Recruit (search top 5 for a unit, mandatory if able) ──────────────────────

class TestRecruit:
    def _play_recruit(self, repo, top_cards, below_cards=()):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import apply, PlayCard
        recruit = _get_card(repo, "SOR", "123")
        state = _seed_rng(_make_state())
        ps = state.players[0]
        rec_ci = CardInstance("p0_recruit", recruit, "P0", Zone.HAND)
        ps.hand.append(rec_ci)
        _build_search_deck(state, "P0", top_cards, below_cards)
        _give_resources(state, "P0", 10)
        state = apply(state, PlayCard(rec_ci.instance_id))
        return state

    def test_draws_chosen_unit_bottoms_rest(self, repo):
        unit = _get_card(repo, "SOR", "128")   # Death Star Stormtrooper (unit)
        event = _get_card(repo, "SOR", "74")   # Repair (event, not a unit)
        below = _get_card(repo, "SOR", "74")
        state = self._play_recruit(
            repo,
            top_cards=[event, event, unit, event, event],
            below_cards=[below],
        )
        # Recruit pushes a mandatory deck_search: exactly one unit candidate, no
        # FinishSearch offered while a unit remains to take.
        from swu.engine.actions import SelectSearchCard, FinishSearch
        assert state.pending_decisions[-1].kind == "deck_search"
        acts = _search_actions(state)
        selects = [a for a in acts if isinstance(a, SelectSearchCard)]
        assert len(selects) == 1, "Only the single unit is a candidate"
        assert not any(isinstance(a, FinishSearch) for a in acts), \
            "Mandatory search forces the take while a unit remains"
        unit_id = selects[0].instance_id
        ps = state.players[0]
        hand_before = len(ps.hand)
        deck_top5_ids = [ci.instance_id for ci in ps.deck[:5]]
        state = _take_from_search(state, unit_id)  # taking the only unit auto-finishes
        assert not state.pending_decisions
        ps = state.players[0]
        assert len(ps.hand) == hand_before + 1
        assert any(ci.instance_id == unit_id for ci in ps.hand)
        # The four un-taken top-5 cards are bottomed in seeded-random order.
        skipped = [cid for cid in deck_top5_ids if cid != unit_id]
        expected = _expected_bottom_order(skipped)
        # rest (the 'below' card) stays on top; bottom = shuffled skipped.
        assert [ci.instance_id for ci in ps.deck[-4:]] == expected

    def test_no_unit_present_takes_nothing(self, repo):
        event = _get_card(repo, "SOR", "74")   # Repair (event only — no units)
        state = self._play_recruit(repo, top_cards=[event, event, event, event, event])
        # No unit candidate → only a forced FinishSearch, which bottoms all 5.
        from swu.engine.actions import SelectSearchCard, FinishSearch
        acts = _search_actions(state)
        assert not any(isinstance(a, SelectSearchCard) for a in acts)
        assert any(isinstance(a, FinishSearch) for a in acts)
        ps = state.players[0]
        hand_before = len(ps.hand)
        deck_ids = [ci.instance_id for ci in ps.deck[:5]]
        state = _finish_search(state)
        ps = state.players[0]
        assert len(ps.hand) == hand_before, "No unit → nothing drawn"
        assert [ci.instance_id for ci in ps.deck] == _expected_bottom_order(deck_ids)


# ── Resupply ──────────────────────────────────────────────────────────────────

class TestResupply:
    def test_event_put_as_resource_exhausted_facedown(self, repo):
        """Resupply: the event enters the resource zone facedown and EXHAUSTED.

        Per CR §"PUT INTO PLAY AS A RESOURCE", a card put into play as a resource
        with no "unless otherwise specified" override is placed facedown and
        exhausted. So it raises ``total_resources`` (deploy thresholds) but is not
        available to pay costs this turn.
        """
        resupply = _get_card(repo, "SOR", "126")
        state = _make_state()
        from swu.engine.state import CardInstance, Zone
        ps = state.players[0]
        res_ci = CardInstance("p0_resupply", resupply, "P0", Zone.HAND)
        ps.hand.append(res_ci)
        _give_resources(state, "P0", 10)

        total_before = len(ps.resources)
        from swu.engine.actions import apply, PlayCard
        state = apply(state, PlayCard(res_ci.instance_id))
        ps = state.players[0]

        # Resupply card ends up in the resource zone, not the discard.
        found = next((ci for ci in ps.resources
                      if ci.instance_id == res_ci.instance_id), None)
        assert found is not None, "Resupply should add itself to resources"
        assert not any(ci.instance_id == res_ci.instance_id for ci in ps.discard), \
            "Resupply should not remain in discard"

        # Final zone tag, exhausted state, facedown.
        assert found.zone == Zone.RESOURCES
        assert found.exhausted is True, "put into play as a resource → exhausted"
        assert found.face_down is True, "resources are placed facedown"

        # It counts toward the total resource pool.
        assert len(ps.resources) == total_before + 1
        # …but not as an available (ready) resource this turn.
        assert all(r.exhausted or r.instance_id != res_ci.instance_id
                   for r in ps.resources)

    def test_no_longer_escape_hatch(self):
        from swu.abilities.registry import is_escape_hatch
        import swu.cards.sor.abilities  # noqa: F401  (ensure registered)
        assert not is_escape_hatch("SOR", "126")


# ── Superlaser Technician ───────────────────────────────────────────────────

class TestSuperlaserTechnician:
    """SOR_83 — When Defeated: You may put this unit into play as a resource and
    ready it. The "and ready it" overrides the facedown-and-exhausted default, so
    the resource enters READY."""

    def _setup_and_defeat(self, repo):
        from swu.engine.actions import _defeat_unit
        tech = _get_card(repo, "SOR", "83")
        state = _make_state()
        tech_ci = _place(state, "P0", tech, "ground")
        tech_ci.damage = 5  # carried combat damage — must be cleared on resourcing
        _defeat_unit(state, state.player_by_id("P0"), tech_ci)
        return state, tech_ci.instance_id

    def test_accept_puts_into_play_as_ready_resource(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, AutoResolveEffects,
        )
        from swu.engine.state import Zone

        state, tech_id = self._setup_and_defeat(repo)
        assert state.pending_decisions, "optional When Defeated should be pending"
        ps = state.player_by_id("P0")
        total_before = len(ps.resources)
        avail_before = ps.available_resources

        accept = next((a for a in legal_actions(state)
                       if isinstance(a, AcceptTrigger)), None)
        assert accept is not None, "Should offer AcceptTrigger"
        state = apply(state, accept)
        # The CustomEffect (no player target) resolves via AutoResolveEffects.
        auto = next((a for a in legal_actions(state)
                     if isinstance(a, AutoResolveEffects)), None)
        assert auto is not None, "Should offer AutoResolveEffects to run the effect"
        state = apply(state, auto)

        ps = state.player_by_id("P0")
        res = next((ci for ci in ps.resources if ci.instance_id == tech_id), None)
        assert res is not None, "Tech should be put into play as a resource"
        assert not any(ci.instance_id == tech_id for ci in ps.discard), \
            "Tech should leave the discard"
        assert res.zone == Zone.RESOURCES
        assert res.exhausted is False, "'and ready it' → resource enters READY"
        assert res.face_down is True, "resources are placed facedown"
        assert res.damage == 0, "a resource is a blank card — damage cleared"
        # Ready resource counts toward both total and available.
        assert len(ps.resources) == total_before + 1
        assert ps.available_resources == avail_before + 1

    def test_decline_leaves_in_discard(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        from swu.engine.state import Zone

        state, tech_id = self._setup_and_defeat(repo)
        decline = next((a for a in legal_actions(state)
                        if isinstance(a, DeclineTrigger)), None)
        assert decline is not None, "'You may' should be decline-able"
        state = apply(state, decline)

        ps = state.player_by_id("P0")
        assert any(ci.instance_id == tech_id for ci in ps.discard), \
            "Declining leaves the unit in the discard"
        assert not any(ci.instance_id == tech_id for ci in ps.resources)
        disc = next(ci for ci in ps.discard if ci.instance_id == tech_id)
        assert disc.zone == Zone.DISCARD

    def test_no_longer_escape_hatch(self):
        from swu.abilities.registry import is_escape_hatch
        import swu.cards.sor.abilities  # noqa: F401  (ensure registered)
        assert not is_escape_hatch("SOR", "83")


# ── Leader undeployed activated abilities ─────────────────────────────────────

def _place_leader(state, owner_id, leader_def):
    """Put an undeployed leader (ready) into the owner's base_zone."""
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(
        instance_id=f"{owner_id}_leader_{uuid.uuid4().hex[:6]}",
        card_def=leader_def, owner_id=owner_id, zone=Zone.BASE_ZONE,
    )
    ci.deployed = False
    ci.exhausted = False
    state.player_by_id(owner_id).base_zone.append(ci)
    return ci


def _mark_played(state, ci):
    """Record `ci` as a unit the controller played this phase."""
    state.game_memory.units_played_this_phase.add(ci.instance_id)


class TestLukeLeaderUndeployed:
    """SOR_5 (undeployed) — Action [1 resource, exhaust]: Give a Shield token to
    a [Heroism] unit you played this phase."""

    def _use_luke(self, state, luke_ci):
        from swu.engine.actions import legal_actions, apply, UseAbility
        use = next(
            a for a in legal_actions(state)
            if isinstance(a, UseAbility) and a.source_id == luke_ci.instance_id
        )
        return apply(state, use)

    def test_only_heroism_units_played_this_phase_are_targetable(self, repo):
        luke = _get_card(repo, "SOR", "5")
        heroism = _get_card(repo, "SOR", "51")   # Heroism unit
        nonheroism = _get_card(repo, "SOR", "59")  # Vigilance only

        state = _make_state()
        luke_ci = _place_leader(state, "P0", luke)
        _give_resources(state, "P0", 3)

        eligible = _place(state, "P0", heroism, "ground")        # Heroism + played
        _mark_played(state, eligible)
        heroism_unplayed = _place(state, "P0", heroism, "ground")  # Heroism, NOT played
        nonheroism_played = _place(state, "P0", nonheroism, "ground")  # played, not Heroism
        _mark_played(state, nonheroism_played)
        enemy_played = _place(state, "P1", heroism, "ground")    # enemy Heroism + played
        _mark_played(state, enemy_played)

        state = self._use_luke(state, luke_ci)

        from swu.engine.actions import legal_actions, ChooseTarget
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert offered == {eligible.instance_id}, (
            "only the friendly Heroism unit played this phase may be Shielded"
        )

    def test_shield_attaches_to_chosen_unit_and_costs_paid(self, repo):
        luke = _get_card(repo, "SOR", "5")
        heroism = _get_card(repo, "SOR", "51")

        state = _make_state()
        luke_ci = _place_leader(state, "P0", luke)
        _give_resources(state, "P0", 3)
        target_ci = _place(state, "P0", heroism, "ground")
        _mark_played(state, target_ci)

        state = self._use_luke(state, luke_ci)
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == target_ci.instance_id)
        state = apply(state, choose)

        assert _shield_count(_find_instance(state, target_ci.instance_id)) == 1
        luke_now = state.players[0].leader_instance
        assert luke_now.exhausted, "Luke pays its exhaust cost"
        assert state.players[0].available_resources == 2, "1 resource spent"

    def test_no_eligible_unit_fizzles_without_decision(self, repo):
        """The action is still usable but has no legal target → resolves with
        nothing pushed (no Shield given)."""
        luke = _get_card(repo, "SOR", "5")
        heroism = _get_card(repo, "SOR", "51")

        state = _make_state()
        luke_ci = _place_leader(state, "P0", luke)
        _give_resources(state, "P0", 3)
        # A Heroism unit exists but was NOT played this phase → ineligible.
        not_played = _place(state, "P0", heroism, "ground")

        state = self._use_luke(state, luke_ci)
        assert not state.pending_decisions, "no eligible target → no decision pushed"
        assert _shield_count(_find_instance(state, not_played.instance_id)) == 0


class TestVaderLeaderUndeployed:
    """SOR_10 (undeployed) — Action [1 resource, exhaust]: If you played a
    [Villainy] card this phase, deal 1 damage to a unit and 1 damage to a base."""

    def _vader_uses(self, state, vader_ci):
        from swu.engine.actions import legal_actions, UseAbility
        return [a for a in legal_actions(state)
                if isinstance(a, UseAbility) and a.source_id == vader_ci.instance_id]

    def test_not_available_without_villainy_played(self, repo):
        vader = _get_card(repo, "SOR", "10")
        state = _make_state()
        vader_ci = _place_leader(state, "P0", vader)
        _give_resources(state, "P0", 3)
        _place(state, "P1", _get_card(repo, "SOR", "59"), "ground")
        # villainy_players_this_phase is empty by default
        assert self._vader_uses(state, vader_ci) == [], (
            "ability is gated out until a Villainy card is played this phase"
        )

    def test_deals_1_to_chosen_unit_and_1_to_chosen_base(self, repo):
        vader = _get_card(repo, "SOR", "10")
        state = _make_state()
        vader_ci = _place_leader(state, "P0", vader)
        _give_resources(state, "P0", 3)
        enemy_unit = _place(state, "P1", _get_card(repo, "SOR", "59"), "ground")
        state.game_memory.villainy_players_this_phase.add("P0")

        from swu.engine.actions import legal_actions, apply, ChooseTarget
        use = next(a for a in self._vader_uses(state, vader_ci))
        state = apply(state, use)

        # First choice: the unit.
        unit_choice = next(a for a in legal_actions(state)
                           if isinstance(a, ChooseTarget) and a.target_id == enemy_unit.instance_id)
        state = apply(state, unit_choice)

        # Second choice: a base.  Choose the opponent's base.
        opp_base_id = state.players[1].base_instance.instance_id
        base_choice = next(a for a in legal_actions(state)
                           if isinstance(a, ChooseTarget) and a.target_id == opp_base_id)
        state = apply(state, base_choice)

        assert not state.pending_decisions, "both damage choices resolved"
        assert _find_instance(state, enemy_unit.instance_id).damage == 1, "1 damage to unit"
        assert state.players[1].base_instance.damage == 1, "1 damage to base"
        vader_now = state.players[0].leader_instance
        assert vader_now.exhausted and state.players[0].available_resources == 2

    def test_bot_refuses_ability_when_only_self_harm(self, repo):
        """End-to-end: with a friendly unit but no enemy units, the HeuristicBot
        must not use Vader's undeployed ability (its unit damage would be forced
        onto a friendly).  Exercises the real engine view + bot wiring."""
        from swu.engine.actions import legal_actions, UseAbility
        from swu.players.heuristic_bot import HeuristicBot
        vader = _get_card(repo, "SOR", "10")
        state = _make_state()
        vader_ci = _place_leader(state, "P0", vader)
        _give_resources(state, "P0", 3)
        _place(state, "P0", _get_card(repo, "SOR", "59"), "ground")  # friendly only
        state.game_memory.villainy_players_this_phase.add("P0")

        legal = legal_actions(state)
        assert any(isinstance(a, UseAbility) and a.source_id == vader_ci.instance_id
                   for a in legal), "the ability is legally available to refuse"
        chosen = HeuristicBot("P0", seed=1).choose_action(state.view_for("P0"), legal)
        assert not (isinstance(chosen, UseAbility)
                    and chosen.source_id == vader_ci.instance_id), (
            "bot must not use an ability that could only damage its own unit"
        )

    def test_damage_events_attribute_source_to_vader(self, repo):
        """Ability damage names its source card in the log (DamageDealt.source_name)
        so the battle log reads "… takes 1 damage from Darth Vader." rather than an
        unattributed hit."""
        vader = _get_card(repo, "SOR", "10")
        state = _make_state()
        vader_ci = _place_leader(state, "P0", vader)
        _give_resources(state, "P0", 3)
        enemy_unit = _place(state, "P1", _get_card(repo, "SOR", "59"), "ground")
        state.game_memory.villainy_players_this_phase.add("P0")

        from swu.engine.actions import apply, ChooseTarget
        from swu.engine.events import DamageDealt
        use = next(a for a in self._vader_uses(state, vader_ci))
        state = apply(state, use)
        state = apply(state, ChooseTarget(enemy_unit.instance_id))
        opp_base_id = state.players[1].base_instance.instance_id
        state = apply(state, ChooseTarget(opp_base_id))

        dmg = [e for e in state.event_log if isinstance(e, DamageDealt)]
        assert dmg, "damage events were emitted"
        assert all(e.source_name == vader_ci.card_def.display_name for e in dmg), (
            "both the unit and base damage are attributed to the Darth Vader ability"
        )

    def test_unit_then_base_choices_are_offered_in_order(self, repo):
        """The two targeted effects present a unit choice first, then a base."""
        vader = _get_card(repo, "SOR", "10")
        state = _make_state()
        vader_ci = _place_leader(state, "P0", vader)
        _give_resources(state, "P0", 3)
        enemy_unit = _place(state, "P1", _get_card(repo, "SOR", "59"), "ground")
        state.game_memory.villainy_players_this_phase.add("P0")

        from swu.engine.actions import legal_actions, apply, ChooseTarget
        use = next(a for a in self._vader_uses(state, vader_ci))
        state = apply(state, use)

        first = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert first == {enemy_unit.instance_id}, "first choice is the only unit"

        state = apply(state, ChooseTarget(enemy_unit.instance_id))
        second = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        base_ids = {state.players[0].base_instance.instance_id,
                    state.players[1].base_instance.instance_id}
        assert second == base_ids, "second choice enumerates the bases"

    def test_sor_10_opponent_villainy_play_does_not_enable_ability(self, repo):
        """Regression (bug report 2026-07-21): the condition is "If YOU played a
        Villainy card this phase".  An OPPONENT playing a Villainy card must NOT
        make your undeployed Vader ability available.  Previously the tracking
        was a single global flag, so the enemy's Villainy play switched it on and
        Vader dealt 1 damage to a unit and a base with no Villainy card of your
        own played."""
        vader = _get_card(repo, "SOR", "10")
        state = _make_state()
        vader_ci = _place_leader(state, "P0", vader)  # Vader owned by P0
        _give_resources(state, "P0", 3)
        _place(state, "P1", _get_card(repo, "SOR", "59"), "ground")
        # The OPPONENT (P1) played a Villainy card this phase — not P0.
        state.game_memory.villainy_players_this_phase.add("P1")

        assert self._vader_uses(state, vader_ci) == [], (
            "opponent's Villainy play must not enable your Vader ability"
        )

        # And once P0 plays a Villainy card too, the ability becomes available.
        state.game_memory.villainy_players_this_phase.add("P0")
        assert self._vader_uses(state, vader_ci), (
            "your own Villainy play enables the ability"
        )


# ── Top-of-deck peek decisions (R2-D2 SOR_236, C-3PO SOR_238) ─────────────────

def _stack_deck(state, repo, owner_id, *card_numbers):
    """Put the given SOR cards on top of `owner_id`'s deck, first arg = top card.

    Returns the list of created CardInstances (top-first), so a test can assert
    on their ids."""
    from swu.engine.state import CardInstance, Zone
    ps = state.player_by_id(owner_id)
    made = []
    for i, num in enumerate(card_numbers):
        ci = CardInstance(f"{owner_id}_deck_{i}_{num}",
                          _get_card(repo, "SOR", num), owner_id, Zone.DECK)
        made.append(ci)
    # First arg is the top card: deck index 0.
    ps.deck[:0] = made
    return made


class TestR2D2:
    """SOR_236 — When Played/On Attack: look at the top card; may bottom it."""

    def test_two_trigger_sides_registered(self):
        from swu.abilities.registry import get_abilities
        import swu.cards.sor  # noqa: F401
        specs = get_abilities("SOR", "236")
        triggers = {type(s.trigger).__name__ for s in specs}
        assert triggers == {"WhenPlayed", "OnAttack"}

    def test_when_played_pushes_peek_decision(self, repo):
        r2 = _place(state := _make_state(), "P0", _get_card(repo, "SOR", "236"), "ground")
        _stack_deck(state, repo, "P0", "46", "128")
        state = _fire_when_played(state, r2)
        top = state.pending_decisions[-1]
        assert top.kind == "peek_top" and top.context["mode"] == "may_bottom"
        assert top.deciding_player_id == "P0"

    def test_peek_context_reveals_card_identity(self, repo):
        # The deciding player must be able to study the card before choosing, so
        # its true identity (DB id + name) rides in the decision context — the
        # raw deck is redacted in the view, so this is the only channel for it.
        r2 = _place(state := _make_state(), "P0", _get_card(repo, "SOR", "236"), "ground")
        top_ci, _ = _stack_deck(state, repo, "P0", "46", "128")
        state = _fire_when_played(state, r2)
        ctx = state.pending_decisions[-1].context
        assert ctx["peeked_card_id"] == top_ci.card_def.id
        assert ctx["peeked_card_name"] == top_ci.card_def.display_name

    def test_keep_leaves_card_on_top(self, repo):
        from swu.engine.actions import legal_actions, apply, KeepTopCard
        r2 = _place(state := _make_state(), "P0", _get_card(repo, "SOR", "236"), "ground")
        top_ci, next_ci = _stack_deck(state, repo, "P0", "46", "128")
        state = _fire_when_played(state, r2)
        keep = next(a for a in legal_actions(state) if isinstance(a, KeepTopCard))
        state = apply(state, keep)
        assert not state.pending_decisions
        deck = state.player_by_id("P0").deck
        assert deck[0].instance_id == top_ci.instance_id, "top card unchanged"
        assert deck[1].instance_id == next_ci.instance_id

    def test_bottom_moves_top_card_under(self, repo):
        from swu.engine.actions import legal_actions, apply, BottomTopCard
        r2 = _place(state := _make_state(), "P0", _get_card(repo, "SOR", "236"), "ground")
        top_ci, next_ci = _stack_deck(state, repo, "P0", "46", "128")
        deck_len = len(state.player_by_id("P0").deck)
        state = _fire_when_played(state, r2)
        bottom = next(a for a in legal_actions(state) if isinstance(a, BottomTopCard))
        state = apply(state, bottom)
        assert not state.pending_decisions
        deck = state.player_by_id("P0").deck
        assert len(deck) == deck_len, "card moved, not lost"
        assert deck[0].instance_id == next_ci.instance_id, "new top is the second card"
        assert deck[-1].instance_id == top_ci.instance_id, "old top is now on the bottom"

    def test_on_attack_also_peeks(self, repo):
        r2 = _place(state := _make_state(), "P0", _get_card(repo, "SOR", "236"), "ground")
        _stack_deck(state, repo, "P0", "46")
        state = _fire_on_attack(state, r2)
        assert state.pending_decisions[-1].kind == "peek_top"

    def test_empty_deck_is_clean_noop(self, repo):
        r2 = _place(state := _make_state(), "P0", _get_card(repo, "SOR", "236"), "ground")
        assert not state.player_by_id("P0").deck
        state = _fire_when_played(state, r2)
        assert not state.pending_decisions, "no decision when the deck is empty"

    def test_no_longer_escape_hatch(self):
        from swu.abilities.registry import is_escape_hatch
        import swu.cards.sor  # noqa: F401
        assert not is_escape_hatch("SOR", "236")


class TestC3PO:
    """SOR_238 — When Played/On Attack: choose a number; if the top card's cost
    matches, may reveal and draw it.  The number is genuinely the player's
    choice (the old stub hard-coded it to 2)."""

    def test_when_played_pushes_number_choice(self, repo):
        from swu.engine.actions import legal_actions, ChooseNumber
        c3 = _place(state := _make_state(), "P0", _get_card(repo, "SOR", "238"), "ground")
        _stack_deck(state, repo, "P0", "46")  # cost 4 on top
        state = _fire_when_played(state, c3)
        top = state.pending_decisions[-1]
        assert top.kind == "choose_number" and top.deciding_player_id == "P0"
        numbers = {a.number for a in legal_actions(state) if isinstance(a, ChooseNumber)}
        assert {0, 2, 4, 10} <= numbers, "a real range of numbers is offered"

    def test_matching_number_offers_draw_and_draws(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseNumber, DrawTopCard
        c3 = _place(state := _make_state(), "P0", _get_card(repo, "SOR", "238"), "ground")
        (top_ci,) = _stack_deck(state, repo, "P0", "46")  # Consular Security Force, cost 4
        hand_before = len(state.player_by_id("P0").hand)
        state = _fire_when_played(state, c3)
        # Choose the top card's actual cost (4), NOT the old hard-coded 2.
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseNumber) and a.number == 4)
        state = apply(state, pick)
        peek = state.pending_decisions[-1]
        assert peek.kind == "peek_top" and peek.context["mode"] == "may_draw"
        draw = next(a for a in legal_actions(state) if isinstance(a, DrawTopCard))
        state = apply(state, draw)
        assert not state.pending_decisions
        hand = state.player_by_id("P0").hand
        assert len(hand) == hand_before + 1
        assert any(ci.instance_id == top_ci.instance_id for ci in hand), "the matched card was drawn"
        assert not state.player_by_id("P0").deck, "drawn off the top of the deck"

    def test_matching_number_may_decline_the_draw(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseNumber, KeepTopCard
        c3 = _place(state := _make_state(), "P0", _get_card(repo, "SOR", "238"), "ground")
        (top_ci,) = _stack_deck(state, repo, "P0", "46")
        state = _fire_when_played(state, c3)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseNumber) and a.number == 4))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, KeepTopCard)))
        assert not state.pending_decisions
        deck = state.player_by_id("P0").deck
        assert deck and deck[0].instance_id == top_ci.instance_id, "left on top"

    def test_wrong_number_reveals_but_does_not_draw(self, repo):
        """Choosing a number != the top card's cost still REVEALS the card (a
        'reveal_only' peek so the player can see it), but draws nothing and only
        offers leaving it on top — no DrawTopCard."""
        from swu.engine.actions import (
            legal_actions, apply, ChooseNumber, KeepTopCard, DrawTopCard,
        )
        c3 = _place(state := _make_state(), "P0", _get_card(repo, "SOR", "238"), "ground")
        (top_ci,) = _stack_deck(state, repo, "P0", "46")  # cost 4
        hand_before = len(state.player_by_id("P0").hand)
        state = _fire_when_played(state, c3)
        # 2 is the OLD hard-coded guess — and it does NOT match cost 4.
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseNumber) and a.number == 2))
        # The card is revealed even on a miss, so the player gets to see it.
        peek = state.pending_decisions[-1]
        assert peek.kind == "peek_top" and peek.context["mode"] == "reveal_only"
        assert peek.context["peeked_card_id"] == top_ci.card_def.id
        acts = legal_actions(state)
        assert not any(isinstance(a, DrawTopCard) for a in acts), "no draw on a miss"
        state = apply(state, next(a for a in acts if isinstance(a, KeepTopCard)))
        assert not state.pending_decisions
        assert len(state.player_by_id("P0").hand) == hand_before, "nothing drawn"
        deck = state.player_by_id("P0").deck
        assert deck[0].instance_id == top_ci.instance_id, "left on top"

    def test_empty_deck_is_clean_noop(self, repo):
        c3 = _place(state := _make_state(), "P0", _get_card(repo, "SOR", "238"), "ground")
        assert not state.player_by_id("P0").deck
        state = _fire_when_played(state, c3)
        assert not state.pending_decisions

    def test_no_longer_escape_hatch(self):
        from swu.abilities.registry import is_escape_hatch
        import swu.cards.sor  # noqa: F401
        assert not is_escape_hatch("SOR", "238")


# ── Modal "choose one" decision (Leia Organa SOR_189) ─────────────────────────

def _add_resource(state, repo, owner_id, *, exhausted: bool):
    """Append one (face-down) resource to owner's resource zone."""
    from swu.engine.state import CardInstance, Zone
    ps = state.player_by_id(owner_id)
    ci = CardInstance(
        instance_id=f"{owner_id}_res_{len(ps.resources)}",
        card_def=_get_card(repo, "SOR", "46"), owner_id=owner_id, zone=Zone.RESOURCES,
    )
    ci.face_down = True
    ci.exhausted = exhausted
    ps.resources.append(ci)
    return ci


class TestLeiaOrgana:
    """SOR_189 — When Played: Either ready a resource or exhaust a unit.

    A genuine modal "choose one" (replacing the old auto-exhaust-a-random-enemy
    stub): the controller picks a mode, then a target within that mode.
    """

    def test_when_played_pushes_modal_with_both_modes(self, repo):
        from swu.engine.actions import legal_actions, ChooseModalOption
        leia = _place(state := _make_state(), "P0", _get_card(repo, "SOR", "189"), "ground")
        _add_resource(state, repo, "P0", exhausted=True)          # ready_resource target
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # exhaust_unit target
        state = _fire_when_played(state, leia)
        top = state.pending_decisions[-1]
        assert top.kind == "modal" and top.deciding_player_id == "P0"
        assert top.context["stage"] == "mode"
        modes = {a.mode for a in legal_actions(state) if isinstance(a, ChooseModalOption)}
        assert modes == {"ready_resource", "exhaust_unit"}

    def test_ready_resource_mode_resolves_without_target_step(self, repo):
        """Resources are fungible, so choosing 'ready a resource' readies an
        arbitrary exhausted resource immediately — no second prompt."""
        from swu.engine.actions import apply, ChooseModalOption
        leia = _place(state := _make_state(), "P0", _get_card(repo, "SOR", "189"), "ground")
        r_exhausted = _add_resource(state, repo, "P0", exhausted=True)
        r_ready = _add_resource(state, repo, "P0", exhausted=False)
        state = _fire_when_played(state, leia)

        # No ChooseModalTarget step — the decision pops on the mode choice itself.
        state = apply(state, ChooseModalOption("ready_resource"))
        assert not state.pending_decisions
        res = {r.instance_id: r for r in state.player_by_id("P0").resources}
        assert res[r_exhausted.instance_id].exhausted is False, "the exhausted resource was readied"
        assert res[r_ready.instance_id].exhausted is False

    def test_exhaust_unit_mode_targets_any_ready_unit(self, repo):
        """"a unit" is not enemy-only: a friendly ready unit is a legal target."""
        from swu.engine.actions import (
            legal_actions, apply, ChooseModalOption, ChooseModalTarget,
        )
        leia = _place(state := _make_state(), "P0", _get_card(repo, "SOR", "189"), "ground")
        leia.exhausted = False
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        friendly.exhausted = False
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        enemy.exhausted = False
        already_exhausted = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        already_exhausted.exhausted = True
        state = _fire_when_played(state, leia)

        state = apply(state, ChooseModalOption("exhaust_unit"))
        targets = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseModalTarget)}
        # All three ready units (incl. friendly Leia and friendly unit), NOT the
        # already-exhausted enemy.
        assert targets == {leia.instance_id, friendly.instance_id, enemy.instance_id}

        state = apply(state, ChooseModalTarget(enemy.instance_id))
        assert not state.pending_decisions
        assert state.player_by_id("P1").ground_arena[0].exhausted is True

    def test_only_available_mode_offered_when_no_resource(self, repo):
        """No exhausted resource -> the resource mode is dropped; only exhaust_unit."""
        from swu.engine.actions import legal_actions, ChooseModalOption
        leia = _place(state := _make_state(), "P0", _get_card(repo, "SOR", "189"), "ground")
        leia.exhausted = False
        _add_resource(state, repo, "P0", exhausted=False)  # ready resource = no-op target
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, leia)
        modes = {a.mode for a in legal_actions(state) if isinstance(a, ChooseModalOption)}
        assert modes == {"exhaust_unit"}, "ready_resource has no legal target, so omitted"

    def test_fizzles_when_neither_mode_has_a_target(self, repo):
        """No exhausted resource and no ready unit -> no decision is pushed."""
        leia = _place(state := _make_state(), "P0", _get_card(repo, "SOR", "189"), "ground")
        leia.exhausted = True  # the only unit in play is already exhausted
        _add_resource(state, repo, "P0", exhausted=False)
        state = _fire_when_played(state, leia)
        assert not state.pending_decisions, "modal fizzles cleanly with no legal mode"

    def test_no_longer_escape_hatch(self):
        from swu.abilities.registry import is_escape_hatch
        import swu.cards.sor  # noqa: F401
        assert not is_escape_hatch("SOR", "189")


class TestGreedo:
    """SOR_204 — Greedo: "When Defeated: You may discard a card from your deck.
    If it's not a unit, deal 2 damage to a ground unit." """

    def test_sor_204_offered_as_optional_when_defeated(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger, DeclineTrigger
        greedo = _get_card(repo, "SOR", "204")
        state = _make_state()
        greedo_ci = _place(state, "P0", greedo, "ground")
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "186"))  # an Event
        state = _defeat_and_fire(state, greedo_ci, "P0")
        acts = legal_actions(state)
        assert any(isinstance(a, (AcceptTrigger, DeclineTrigger)) for a in acts), \
            "the 'you may' WhenDefeated must offer Accept/Decline"

    def test_sor_204_non_unit_milled_deals_2_to_ground_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget, AutoResolveEffects,
        )
        greedo = _get_card(repo, "SOR", "204")
        state = _make_state()
        greedo_ci = _place(state, "P0", greedo, "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        top = _push_deck_top(state, "P0", _get_card(repo, "SOR", "186"))  # Event = non-unit

        state = _defeat_and_fire(state, greedo_ci, "P0")
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        # Drain the inline mill effect (no player choice) so the deck top is milled.
        auto = next(a for a in legal_actions(state) if isinstance(a, AutoResolveEffects))
        state = apply(state, auto)
        # The milled Event is now in P0's discard.
        assert any(c.instance_id == top.instance_id for c in state.player_by_id("P0").discard)
        # A ground unit target is now offered; choose the enemy.
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id)
        state = apply(state, choose)
        hit = _find_instance(state, enemy.instance_id)
        assert hit is not None and hit.damage == 2

    def test_sor_204_unit_milled_deals_no_damage(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget, AutoResolveEffects,
        )
        greedo = _get_card(repo, "SOR", "204")
        state = _make_state()
        greedo_ci = _place(state, "P0", greedo, "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        top = _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))  # a Unit

        state = _defeat_and_fire(state, greedo_ci, "P0")
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        # Drain the inline mill (milling a Unit), then the damage must fizzle: no
        # ChooseTarget offered and the decision settles with the unit undamaged.
        auto = next(a for a in legal_actions(state) if isinstance(a, AutoResolveEffects))
        state = apply(state, auto)
        assert any(c.instance_id == top.instance_id for c in state.player_by_id("P0").discard)
        assert not any(isinstance(a, ChooseTarget) for a in legal_actions(state)), \
            "a milled unit arms no damage → no target prompt"
        assert not state.pending_decisions, "the ability settles with nothing to target"
        hit = _find_instance(state, enemy.instance_id)
        assert hit is not None and hit.damage == 0

    def test_sor_204_no_longer_escape_hatch(self):
        from swu.abilities.registry import is_escape_hatch
        import swu.cards.sor  # noqa: F401
        assert not is_escape_hatch("SOR", "204")


# ══════════════════════════════════════════════════════════════════════════════
# han-solo:03 — SOR_192 Ezra Bridger (peek_top may_play_discard)
# ══════════════════════════════════════════════════════════════════════════════

def _fire_attack_ends(state, attacker_ci):
    """Fire a WhenAttackEnds trigger for a surviving attacker."""
    from swu.engine.events import AttackDeclared
    from swu.abilities.resolver import fire_triggered_abilities
    evt = AttackDeclared(
        attacker_player_id=attacker_ci.owner_id,
        attacker_instance_id=attacker_ci.instance_id,
        attacker_name=attacker_ci.card_def.display_name,
        defender_instance_id=None, defender_name="Base",
    )
    state.event_log.append(evt)
    return fire_triggered_abilities(
        state, evt, after_all_player_idx=0,
        event_ctx={"attack_ended_survivor": attacker_ci.instance_id})


class TestEzraBridger:
    """SOR_192 — When this unit completes an attack: Look at the top card of your
    deck. You may play it, discard it, or leave it on top."""

    def _setup(self, repo, resources=10):
        state = _make_state()
        ezra = _place(state, "P0", _get_card(repo, "SOR", "192"), "ground")
        _give_resources(state, "P0", resources)
        return state, ezra

    def test_sor_192_offers_play_discard_leave(self, repo):
        from swu.engine.actions import legal_actions
        state, ezra = self._setup(repo)
        top = _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))  # a Unit
        state = _fire_attack_ends(state, ezra)
        kinds = {type(a).__name__ for a in legal_actions(state)}
        assert {"PlayTopCard", "DiscardTopCard", "KeepTopCard"} <= kinds

    def test_sor_192_play_top_card_enters_play(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayTopCard
        state, ezra = self._setup(repo)
        top = _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        state = _fire_attack_ends(state, ezra)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, PlayTopCard)))
        assert _find_instance(state, top.instance_id) is not None
        assert all(c.instance_id != top.instance_id
                   for c in state.player_by_id("P0").deck)
        assert not state.pending_decisions

    def test_sor_192_discard_top_card(self, repo):
        from swu.engine.actions import legal_actions, apply, DiscardTopCard
        state, ezra = self._setup(repo)
        top = _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        state = _fire_attack_ends(state, ezra)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DiscardTopCard)))
        ps = state.player_by_id("P0")
        assert any(c.instance_id == top.instance_id for c in ps.discard)
        assert all(c.instance_id != top.instance_id for c in ps.deck)

    def test_sor_192_leave_on_top(self, repo):
        from swu.engine.actions import legal_actions, apply, KeepTopCard
        state, ezra = self._setup(repo)
        top = _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        state = _fire_attack_ends(state, ezra)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, KeepTopCard)))
        assert state.player_by_id("P0").deck[0].instance_id == top.instance_id

    def test_sor_192_empty_deck_is_noop(self, repo):
        state, ezra = self._setup(repo)
        state.player_by_id("P0").deck.clear()
        state = _fire_attack_ends(state, ezra)
        assert not state.pending_decisions


# ── Reprint-duplicate encodes (Stage 4 of docs/dev/plans/reprint_duplicates_plan.md) ────

class TestSuperlaserBlast:
    """SOR_43 — "Defeat all units." (reprint canonical; sib P25_66)."""

    def test_sor_43_defeats_all_units_both_players(self, repo):
        state = _make_state()
        a = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        b = _place(state, "P0", _get_card(repo, "SOR", "128"), "space")
        c = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "SOR", "43", resources=20)
        assert not state.pending_decisions  # no target choice
        for ci in (a, b, c):
            assert _find_instance(state, ci.instance_id) is None
        assert not state.player_by_id("P0").ground_arena
        assert not state.player_by_id("P0").space_arena
        assert not state.player_by_id("P1").ground_arena

    def test_sor_43_bases_untouched(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "SOR", "43", resources=20)
        # Bases (kind="unit" filter excludes them) survive.
        assert state.player_by_id("P0").base_zone
        assert state.player_by_id("P1").base_zone


# ── Reprint sweep Stage 4 Batch 2 canonical encodes ──────────────────────────

class TestConsortiumStarViper:
    """SOR_112 — "While you have the initiative, this unit gains Restore 2."
    (reprint canonical; sib ASH_122)."""

    def test_sor_112_restore_2_while_initiative(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        state.initiative_holder = 0  # P0 has the initiative
        ci = _place(state, "P0", _get_card(repo, "SOR", "112"), "space")
        assert keyword_value(state, ci, Keyword.RESTORE) == 2

    def test_sor_112_no_restore_without_initiative(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        state.initiative_holder = 1  # opponent holds the initiative
        ci = _place(state, "P0", _get_card(repo, "SOR", "112"), "space")
        # Printed Restore is sanitiser-stripped; the conditional grant is off.
        assert keyword_value(state, ci, Keyword.RESTORE) == 0


class TestHomesteadMilitia:
    """SOR_113 — "While you control 6 or more resources, this unit gains Sentinel."
    (reprint canonical; sib JTL_113)."""

    def test_sor_113_sentinel_at_6_resources(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        ci = _place(state, "P0", _get_card(repo, "SOR", "113"), "ground")
        _give_resources(state, "P0", 5)
        assert not has_keyword(state, ci, Keyword.SENTINEL)  # below threshold
        _give_resources(state, "P0", 1)                      # now 6
        assert has_keyword(state, ci, Keyword.SENTINEL)


class TestPrepareForTakeoff:
    """SOR_125 — "Search the top 8 for up to 2 Vehicle units, reveal and draw
    them." (reprint canonical; sib JTL_128)."""

    def test_sor_125_offers_only_vehicle_units(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, PlayCard, SelectSearchCard, FinishSearch
        import uuid
        state = _make_state()
        v1 = _get_card(repo, "SOR", "112")   # Consortium StarViper (Vehicle)
        v2 = _get_card(repo, "SHD", "57")    # Rickety Quadjumper (Vehicle)
        nonv = _get_card(repo, "SOR", "128")  # Death Star Stormtrooper (not Vehicle)
        ps = state.player_by_id("P0")
        for cd in (v1, v2, nonv):
            ps.deck.append(CardInstance(f"deck_{uuid.uuid4().hex[:6]}", cd, "P0", Zone.DECK))
        evt_ci = CardInstance("P0_125_evt", _get_card(repo, "SOR", "125"), "P0", Zone.HAND)
        ps.hand.append(evt_ci)
        _give_resources(state, "P0", 10)

        state = apply(state, PlayCard(evt_ci.instance_id))
        assert state.pending_decisions[-1].kind == "deck_search"
        acts = legal_actions(state)
        assert any(isinstance(a, FinishSearch) for a in acts)   # "up to" 2
        sels = [a for a in acts if isinstance(a, SelectSearchCard)]
        assert len(sels) == 2   # only the two Vehicle units are eligible

    def test_sor_125_draws_taken_vehicles(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, PlayCard, SelectSearchCard
        import uuid
        state = _make_state()
        v1 = _get_card(repo, "SOR", "112")
        v2 = _get_card(repo, "SHD", "57")
        ps = state.player_by_id("P0")
        for cd in (v1, v2):
            ps.deck.append(CardInstance(f"deck_{uuid.uuid4().hex[:6]}", cd, "P0", Zone.DECK))
        evt_ci = CardInstance("P0_125b_evt", _get_card(repo, "SOR", "125"), "P0", Zone.HAND)
        ps.hand.append(evt_ci)
        _give_resources(state, "P0", 10)
        state = apply(state, PlayCard(evt_ci.instance_id))
        for _ in range(2):
            sel = [a for a in legal_actions(state) if isinstance(a, SelectSearchCard)][0]
            state = apply(state, sel)
        assert not state.pending_decisions   # cap of 2 → auto-finished
        names = {ci.card_def.name for ci in state.player_by_id("P0").hand}
        assert {v1.name, v2.name} <= names


# ── Reprint-duplicate encode (Stage 4 batch 5) ────────────────────────────────

class TestLukeSkywalkerSOR51:
    """SOR_51 — Restore 3.  When Played: give an enemy unit -3/-3 for this phase;
    if a friendly unit was defeated this phase, give it -6/-6 instead."""

    def test_sor_51_gives_minus_3_3(self, repo):
        from swu.engine.actions import apply, ChooseTarget, compute_power, compute_hp
        state = _make_state()
        luke = _place(state, "P0", _get_card(repo, "SOR", "51"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SEC", "51"), "ground")  # 8/8
        state = _fire_when_played(state, luke)
        state = apply(state, ChooseTarget(enemy.instance_id))
        e = _find_instance(state, enemy.instance_id)
        assert compute_power(state, e) == 5 and compute_hp(state, e) == 5

    def test_sor_51_gives_minus_6_6_after_friendly_defeat(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import apply, ChooseTarget, compute_power, compute_hp
        state = _make_state()
        luke = _place(state, "P0", _get_card(repo, "SOR", "51"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SEC", "51"), "ground")  # 8/8
        # A friendly unit was defeated this phase: a card in P0's discard whose id
        # is recorded in units_defeated_this_round.
        dead = CardInstance("P0_dead", _get_card(repo, "SOR", "46"), "P0", Zone.DISCARD)
        state.player_by_id("P0").discard.append(dead)
        state.game_memory.units_defeated_this_round.add("P0_dead")
        state = _fire_when_played(state, luke)
        state = apply(state, ChooseTarget(enemy.instance_id))
        e = _find_instance(state, enemy.instance_id)
        assert compute_power(state, e) == 2 and compute_hp(state, e) == 2


# ── SOR_176 ISB Agent (Stage-4 reprint sweep, Batch 7) ────────────────────────

def _put_event_in_hand(state, repo, owner, set_code, num):
    """Put an Event card into ``owner``'s hand (for the 'reveal an event' gate)."""
    from swu.engine.state import CardInstance, Zone
    card = _get_card(repo, set_code, num)
    ci = CardInstance(f"{owner}_ev_{num}", card, owner, Zone.HAND)
    state.player_by_id(owner).hand.append(ci)
    return ci


class TestISBAgentSOR176:
    """SOR_176 — When Played: You may reveal an event from your hand. If you do,
    deal 1 damage to a unit (optional WhenPlayed gated by an Event-in-hand)."""

    def test_sor_176_deals_1_with_event_in_hand(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        agent = _place(state, "P0", _get_card(repo, "SOR", "176"), "ground")
        _put_event_in_hand(state, repo, "P0", "SOR", "155")  # an Event (Aggression)
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _fire_when_played(state, agent)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 1

    def test_sor_176_not_offered_without_event_in_hand(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        agent = _place(state, "P0", _get_card(repo, "SOR", "176"), "ground")
        # A non-event card in hand must NOT satisfy the gate.
        from swu.engine.state import CardInstance, Zone
        unit = CardInstance("P0_u", _get_card(repo, "SOR", "46"), "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(unit)
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, agent)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert not state.pending_decisions


class TestAvenger:
    """SOR_40 — Avenger (8/8 Capital Ship): "When Played/On Attack: An opponent
    chooses a non-leader unit they control.  Defeat that unit."  Reuses the
    each_player_defeats seam restricted to the opponent."""

    def _arena_ids(self, state, pid):
        ps = state.player_by_id(pid)
        return {u.instance_id for u in ps.ground_arena + ps.space_arena}

    def test_sor_40_when_played_opponent_defeats_own_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseUnitToDefeat
        state = _make_state()
        avenger = _place(state, "P0", _get_card(repo, "SOR", "40"), "space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        state = _fire_when_played(state, avenger)
        top = state.pending_decisions[-1]
        assert top.kind == "each_player_defeats"
        assert top.deciding_player_id == "P1"  # only the opponent chooses
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseUnitToDefeat)}
        assert offered == {enemy.instance_id}
        state = apply(state, ChooseUnitToDefeat(enemy.instance_id))
        assert not state.pending_decisions
        assert enemy.instance_id not in self._arena_ids(state, "P1")

    def test_sor_40_on_attack_also_triggers(self, repo):
        from swu.engine.actions import apply, ChooseUnitToDefeat
        state = _make_state()
        avenger = _place(state, "P0", _get_card(repo, "SOR", "40"), "space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        state = _fire_on_attack(state, avenger)
        top = state.pending_decisions[-1]
        assert top.kind == "each_player_defeats" and top.deciding_player_id == "P1"
        state = apply(state, ChooseUnitToDefeat(enemy.instance_id))
        assert enemy.instance_id not in self._arena_ids(state, "P1")

    def test_sor_40_fizzles_with_no_opponent_unit(self, repo):
        state = _make_state()
        avenger = _place(state, "P0", _get_card(repo, "SOR", "40"), "space")
        # P0 has its own unit; the controller must NOT be asked to defeat it.
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        state = _fire_when_played(state, avenger)
        assert not state.pending_decisions


# ── "Choose two, in any order" aspect modals (SOR_155/107/203/58) ──────────────
# The choose_two_modal primitive: the four SOR aspect events read
# "Choose two, in any order:" over four options.  These tests play the event
# (via _resolve_event_ability, as PlayCard does) and drive the resulting
# choose_two_modal decision + the per-option resolve_effects decisions.

def _play_aspect_event(state, repo, set_code, number, controller_id="P0"):
    """Place the aspect event in the controller discard (where it sits at
    resolution time) and run its EventAbility, pushing choose_two_modal."""
    from swu.engine.state import CardInstance, Zone
    from swu.engine.actions import _resolve_event_ability
    cdef = _get_card(repo, set_code, number)
    ci = CardInstance(instance_id=f"{controller_id}_evt_{uuid.uuid4().hex[:6]}",
                      card_def=cdef, owner_id=controller_id, zone=Zone.DISCARD)
    ps = state.player_by_id(controller_id)
    ps.discard.append(ci)
    _resolve_event_ability(state, ps, ci, 1 - state.player_index(controller_id))
    return ci


def _pick_option(state, option_idx):
    from swu.engine.actions import legal_actions, apply, SelectModalOption
    act = next(a for a in legal_actions(state)
               if isinstance(a, SelectModalOption) and a.option_idx == option_idx)
    return apply(state, act)


def _choose(state, target_id):
    from swu.engine.actions import legal_actions, apply, ChooseTarget
    act = next(a for a in legal_actions(state)
               if isinstance(a, ChooseTarget) and a.target_id == target_id)
    return apply(state, act)


def _decline_target(state):
    from swu.engine.actions import legal_actions, apply, DeclineTarget
    act = next(a for a in legal_actions(state) if isinstance(a, DeclineTarget))
    return apply(state, act)


def _auto_resolve(state):
    from swu.engine.actions import legal_actions, apply, AutoResolveEffects
    act = next(a for a in legal_actions(state) if isinstance(a, AutoResolveEffects))
    return apply(state, act)


def _exp_tokens_on(ci):
    return sum(1 for u in ci.attached_upgrades
               if (u.card_def.name or "").lower().startswith("experience"))


def _shield_tokens_on(ci):
    return sum(1 for u in ci.attached_upgrades
               if (u.card_def.name or "").lower().startswith("shield"))


def _deck_card(state, owner_id, card_def):
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(instance_id=f"{owner_id}_dk_{uuid.uuid4().hex[:6]}",
                      card_def=card_def, owner_id=owner_id, zone=Zone.DECK)
    state.player_by_id(owner_id).deck.append(ci)
    return ci


def _hand_card(state, owner_id, card_def):
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(instance_id=f"{owner_id}_hd_{uuid.uuid4().hex[:6]}",
                      card_def=card_def, owner_id=owner_id, zone=Zone.HAND)
    state.player_by_id(owner_id).hand.append(ci)
    return ci


def _discard_card(state, owner_id, card_def):
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(instance_id=f"{owner_id}_dc_{uuid.uuid4().hex[:6]}",
                      card_def=card_def, owner_id=owner_id, zone=Zone.DISCARD)
    state.player_by_id(owner_id).discard.append(ci)
    return ci


class TestChooseTwoModalPrimitiveSOR155:
    def test_sor_155_selection_mechanics(self, repo):
        from swu.engine.actions import legal_actions, SelectModalOption
        state = _make_state()
        _play_aspect_event(state, repo, "SOR", "155")
        assert state.pending_decisions[-1].kind == "choose_two_modal"
        opts = {a.option_idx for a in legal_actions(state)
                if isinstance(a, SelectModalOption)}
        assert opts == {1, 2, 3, 4}
        state = _pick_option(state, 2)
        # Same decision still on top; the chosen option is no longer offered.
        assert state.pending_decisions[-1].kind == "choose_two_modal"
        opts2 = {a.option_idx for a in legal_actions(state)
                 if isinstance(a, SelectModalOption)}
        assert opts2 == {1, 3, 4}
        state = _pick_option(state, 1)
        # Exactly two options resolve — two resolve_effects decisions on the stack.
        re = [d for d in state.pending_decisions if d.kind == "resolve_effects"]
        assert len(re) == 2

    def test_sor_155_draw_then_deal4_in_pick_order(self, repo):
        state = _make_state()
        _deck_card(state, "P0", _get_card(repo, "SOR", "128"))
        _deck_card(state, "P0", _get_card(repo, "SOR", "128"))
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"))  # 3/7 non-unique
        _play_aspect_event(state, repo, "SOR", "155")
        state = _pick_option(state, 1)   # draw a card (resolves first)
        state = _pick_option(state, 4)   # deal 4 to a unit
        state = _auto_resolve(state)     # opt 1 — draw
        assert len(state.player_by_id("P0").hand) == 1
        state = _choose(state, enemy.instance_id)  # opt 4 — deal 4
        assert _find_instance(state, enemy.instance_id).damage == 4
        assert not state.pending_decisions

    def test_sor_155_ready_low_power_unit(self, repo):
        state = _make_state()
        _deck_card(state, "P0", _get_card(repo, "SOR", "128"))
        u = _place(state, "P0", _get_card(repo, "SOR", "128"))  # power 3
        u.exhausted = True
        _play_aspect_event(state, repo, "SOR", "155")
        state = _pick_option(state, 3)   # ready a unit with 3 or less power (first)
        state = _pick_option(state, 1)   # draw
        state = _choose(state, u.instance_id)
        assert _find_instance(state, u.instance_id).exhausted is False
        state = _auto_resolve(state)     # draw
        assert len(state.player_by_id("P0").hand) == 1
        assert not state.pending_decisions


class TestCommandSOR107:
    def test_sor_107_experience_then_return_from_discard(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectDiscardCard
        state = _make_state()
        friendly = _place(state, "P0", _get_card(repo, "SOR", "128"))
        disc_unit = _discard_card(state, "P0", _get_card(repo, "SOR", "128"))
        _play_aspect_event(state, repo, "SOR", "107")
        state = _pick_option(state, 1)   # give 2 Experience to a unit (first)
        state = _pick_option(state, 4)   # return a unit from discard
        state = _choose(state, friendly.instance_id)      # opt 1 target
        assert _exp_tokens_on(_find_instance(state, friendly.instance_id)) == 2
        state = _auto_resolve(state)     # opt 4 — CustomEffect pushes return_from_discard
        act = next(a for a in legal_actions(state)
                   if isinstance(a, SelectDiscardCard)
                   and a.instance_id == disc_unit.instance_id)
        state = apply(state, act)        # return the discarded unit
        while state.pending_decisions:   # drive any trailing AutoResolveEffects
            state = _auto_resolve(state)
        hand_ids = {c.instance_id for c in state.player_by_id("P0").hand}
        assert disc_unit.instance_id in hand_ids

    def test_sor_107_friendly_deals_power_to_enemy(self, repo):
        state = _make_state()
        friendly = _place(state, "P0", _get_card(repo, "SOR", "128"))  # power 3
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"))       # 3/7 non-unique
        _play_aspect_event(state, repo, "SOR", "107")
        state = _pick_option(state, 2)   # friendly deals its power to a non-unique enemy
        state = _pick_option(state, 1)   # give 2 Experience
        state = _choose(state, friendly.instance_id)  # opt 2 — friendly source
        state = _choose(state, enemy.instance_id)     # opt 2 — enemy target
        assert _find_instance(state, enemy.instance_id).damage == 3
        state = _choose(state, friendly.instance_id)  # opt 1 — Experience recipient
        assert _exp_tokens_on(_find_instance(state, friendly.instance_id)) == 2
        assert not state.pending_decisions

    def test_sor_107_put_self_into_play_as_resource(self, repo):
        state = _make_state()
        friendly = _place(state, "P0", _get_card(repo, "SOR", "128"))
        evt = _play_aspect_event(state, repo, "SOR", "107")
        state = _pick_option(state, 3)   # put this event into play as a resource (first)
        state = _pick_option(state, 1)   # give 2 Experience
        state = _auto_resolve(state)     # opt 3 — no-target CustomEffect
        ps = state.player_by_id("P0")
        assert evt.instance_id in {c.instance_id for c in ps.resources}
        assert evt.instance_id not in {c.instance_id for c in ps.discard}
        state = _choose(state, friendly.instance_id)  # opt 1
        assert not state.pending_decisions


class TestCunningSOR203:
    def test_sor_203_return_unit_and_buff(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "128"))     # 3 power, non-leader
        friendly = _place(state, "P0", _get_card(repo, "SOR", "128"))  # power 3
        _play_aspect_event(state, repo, "SOR", "203")
        state = _pick_option(state, 1)   # return a non-leader unit (power <= 4) (first)
        state = _pick_option(state, 2)   # give +4/+0 this phase
        state = _choose(state, enemy.instance_id)     # opt 1 — bounce the enemy
        assert _find_instance(state, enemy.instance_id) is None
        assert enemy.instance_id in {c.instance_id
                                     for c in state.player_by_id("P1").hand}
        state = _choose(state, friendly.instance_id)  # opt 2 — buff target
        assert compute_power(state, _find_instance(state, friendly.instance_id)) == 7
        assert not state.pending_decisions

    def test_sor_203_exhaust_units_and_opponent_random_discard(self, repo):
        state = _make_state()
        u1 = _place(state, "P1", _get_card(repo, "SOR", "128"))
        u2 = _place(state, "P1", _get_card(repo, "SOR", "128"))
        _hand_card(state, "P1", _get_card(repo, "SOR", "128"))
        _hand_card(state, "P1", _get_card(repo, "SOR", "46"))
        _play_aspect_event(state, repo, "SOR", "203")
        state = _pick_option(state, 3)   # exhaust up to 2 units (first)
        state = _pick_option(state, 4)   # an opponent discards a random card
        state = _choose(state, u1.instance_id)   # exhaust u1
        state = _decline_target(state)           # decline the 2nd exhaust ("up to 2")
        assert _find_instance(state, u1.instance_id).exhausted is True
        assert _find_instance(state, u2.instance_id).exhausted is False
        state = _auto_resolve(state)     # opt 4 — opponent random discard
        assert len(state.player_by_id("P1").hand) == 1
        assert not state.pending_decisions


class TestVigilanceSOR58:
    def test_sor_58_mill_opponent_and_heal_base(self, repo):
        state = _make_state()
        for _ in range(8):
            _deck_card(state, "P1", _get_card(repo, "SOR", "128"))
        state.player_by_id("P0").base_instance.damage = 10
        _play_aspect_event(state, repo, "SOR", "58")
        state = _pick_option(state, 1)   # discard 6 from an opponent's deck (first)
        state = _pick_option(state, 2)   # heal 5 from a base
        state = _auto_resolve(state)     # opt 1 — mill 6
        assert len(state.player_by_id("P1").deck) == 2
        assert len(state.player_by_id("P1").discard) == 6
        state = _auto_resolve(state)     # opt 2 — heal 5 (fixed friendly base)
        assert state.player_by_id("P0").base_instance.damage == 5
        assert not state.pending_decisions

    def test_sor_58_defeat_low_hp_and_give_shield(self, repo):
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "128"))    # 1 remaining HP
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"))
        _play_aspect_event(state, repo, "SOR", "58")
        state = _pick_option(state, 3)   # defeat a unit with 3 or less remaining HP (first)
        state = _pick_option(state, 4)   # give a Shield token to a unit
        state = _choose(state, enemy.instance_id)     # opt 3 — defeat
        assert _find_instance(state, enemy.instance_id) is None
        state = _choose(state, friendly.instance_id)  # opt 4 — shield
        assert _shield_tokens_on(_find_instance(state, friendly.instance_id)) == 1
        assert not state.pending_decisions


class TestMillenniumFalcon:
    """SOR_193 Millennium Falcon — "This unit enters play ready. When you ready
    cards during the regroup phase: Either pay [1 resource] or return this unit to
    her owner's hand."  EntersPlayReady (existing marker) + the new regroup_upkeep
    decision kind, fired at _enter_regroup via a PhaseStartTrigger."""

    def test_sor_193_enters_play_ready(self, repo):
        from swu.engine.actions import _enters_play_ready
        state = _make_state()
        falcon = _place(state, "P0", _get_card(repo, "SOR", "193"), "space")
        assert _enters_play_ready(state, falcon) is True

    def test_sor_193_regroup_upkeep_pushed_and_offers_pay_or_return(self, repo):
        from swu.engine.actions import _enter_regroup, legal_actions
        state = _make_state()
        _give_resources(state, "P0", 3)
        _place(state, "P0", _get_card(repo, "SOR", "193"), "space")
        _enter_regroup(state)
        assert state.pending_decisions
        top = state.pending_decisions[-1]
        assert top.kind == "regroup_upkeep"
        assert top.deciding_player_id == "P0"
        kinds = {type(a).__name__ for a in legal_actions(state)}
        assert kinds == {"PayRegroupUpkeep", "ReturnRegroupUpkeepUnit"}

    def test_sor_193_pay_keeps_falcon_and_leaves_one_resource_down_next_round(self, repo):
        from swu.engine.actions import _enter_regroup, apply, _end_regroup, PayRegroupUpkeep
        state = _make_state()
        _give_resources(state, "P0", 3)
        falcon = _place(state, "P0", _get_card(repo, "SOR", "193"), "space")
        _enter_regroup(state)
        state = apply(state, PayRegroupUpkeep(falcon.instance_id))
        assert not state.pending_decisions
        ps = state.player_by_id("P0")
        # Exactly one resource is now marked to stay exhausted next round.
        paid = [r for r in ps.resources if r.cannot_ready_this_round]
        assert len(paid) == 1 and paid[0].exhausted is True
        # Falcon is still in play.
        assert falcon.instance_id in {c.instance_id for c in ps.space_arena}
        # After the round rollover the paid resource stays exhausted (its ready is
        # skipped and the flag is cleared); the other resources ready.
        _end_regroup(state)
        ps = state.player_by_id("P0")
        exhausted = [r for r in ps.resources if r.exhausted]
        assert len(exhausted) == 1
        assert all(not r.cannot_ready_this_round for r in ps.resources)

    def test_sor_193_return_sends_falcon_to_owner_hand(self, repo):
        from swu.engine.actions import _enter_regroup, apply, ReturnRegroupUpkeepUnit
        state = _make_state()
        _give_resources(state, "P0", 3)
        falcon = _place(state, "P0", _get_card(repo, "SOR", "193"), "space")
        _enter_regroup(state)
        state = apply(state, ReturnRegroupUpkeepUnit(falcon.instance_id))
        assert not state.pending_decisions
        ps = state.player_by_id("P0")
        assert falcon.instance_id not in {c.instance_id for c in ps.space_arena}
        assert falcon.instance_id in {c.instance_id for c in ps.hand}

    def test_sor_193_forced_return_with_no_resources(self, repo):
        from swu.engine.actions import _enter_regroup, legal_actions
        state = _make_state()
        # P0 has zero resources — cannot pay, so only Return is offered.
        _place(state, "P0", _get_card(repo, "SOR", "193"), "space")
        _enter_regroup(state)
        assert state.pending_decisions[-1].kind == "regroup_upkeep"
        kinds = {type(a).__name__ for a in legal_actions(state)}
        assert kinds == {"ReturnRegroupUpkeepUnit"}

    def test_sor_193_reprint_p25_92_aliases_to_canonical(self):
        import swu.cards  # noqa: F401 — ensure registration + aliasing ran
        from swu.abilities.registry import get_abilities
        canon = get_abilities("SOR", "193")
        alias = get_abilities("P25", "92")
        assert canon and alias
        assert [type(s).__name__ for s in alias] == [type(s).__name__ for s in canon]


# ── Darth Vader — Commanding the First Legion (SOR_87) ────────────────────────
# "When Played: Search the top 10 cards of your deck for any number of [Villainy]
#  units with combined cost 3 or less and play each of them for free."
#  The combined-cost budget multi-select search-and-play primitive (batch 36).

class TestDarthVaderSOR87:
    def _setup(self, repo, top_cards):
        state = _seed_rng(_make_state())
        vader = _place(state, "P0", _get_card(repo, "SOR", "87"), "ground")
        _give_resources(state, "P0", 10)
        deck = _build_search_deck(state, "P0", top_cards, [])
        return state, vader, deck

    def test_sor_87_pushes_deck_search_offering_only_villainy_within_budget(self, repo):
        from swu.engine.actions import legal_actions, SelectSearchCard
        tie = _get_card(repo, "SOR", "225")      # Villainy unit, cost 1
        snow = _get_card(repo, "SOR", "130")     # Villainy unit, cost 2
        rukh = _get_card(repo, "SOR", "85")      # Villainy unit, cost 5 (over budget)
        consular = _get_card(repo, "SOR", "46")  # non-Villainy unit, cost 4
        state, vader, deck = self._setup(repo, [tie, snow, rukh, consular])
        tie_ci, snow_ci, rukh_ci, cons_ci = deck

        state = _fire_when_played(state, vader)
        assert state.pending_decisions[-1].kind == "deck_search"
        cands = {a.instance_id for a in legal_actions(state)
                 if isinstance(a, SelectSearchCard)}
        assert tie_ci.instance_id in cands      # Villainy, cost 1 ≤ 3
        assert snow_ci.instance_id in cands     # Villainy, cost 2 ≤ 3
        assert rukh_ci.instance_id not in cands  # Villainy but cost 5 > 3
        assert cons_ci.instance_id not in cands  # not a Villainy unit

    def test_sor_87_budget_shrinks_as_units_are_taken(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectSearchCard
        tie = _get_card(repo, "SOR", "225")   # cost 1
        snow = _get_card(repo, "SOR", "130")  # cost 2
        scout = _get_card(repo, "SOR", "32")  # cost 2
        state, vader, deck = self._setup(repo, [tie, snow, scout])
        tie_ci, snow_ci, scout_ci = deck

        state = _fire_when_played(state, vader)
        # Take the first 2-cost unit; budget 3 → 1 remaining.
        state = apply(state, SelectSearchCard(snow_ci.instance_id))
        assert state.pending_decisions[-1].kind == "deck_search"
        cands = {a.instance_id for a in legal_actions(state)
                 if isinstance(a, SelectSearchCard)}
        assert tie_ci.instance_id in cands       # a 1-cost still fits (1 ≤ 1)
        assert scout_ci.instance_id not in cands  # another 2-cost no longer fits

    def test_sor_87_plays_taken_units_for_free_and_bottoms_the_rest(self, repo):
        from swu.engine.actions import apply, SelectSearchCard
        tie = _get_card(repo, "SOR", "225")      # cost 1
        scout = _get_card(repo, "SOR", "32")     # cost 2
        consular = _get_card(repo, "SOR", "46")  # non-Villainy, bottomed
        state, vader, deck = self._setup(repo, [tie, scout, consular])
        tie_ci, scout_ci, cons_ci = deck
        avail_before = state.player_by_id("P0").available_resources

        state = _fire_when_played(state, vader)
        state = apply(state, SelectSearchCard(tie_ci.instance_id))
        # Taking both Villainy candidates hits the candidate cap → auto-finish
        # plays them and bottoms the rest (no explicit FinishSearch needed).
        state = apply(state, SelectSearchCard(scout_ci.instance_id))  # combined 3

        # Both chosen Villainy units entered play, paid nothing.
        assert _find_instance(state, tie_ci.instance_id) is not None
        assert _find_instance(state, scout_ci.instance_id) is not None
        assert state.player_by_id("P0").available_resources == avail_before
        # The un-taken searched card (the non-Villainy Consular) is bottomed.
        deck_ids = [c.instance_id for c in state.player_by_id("P0").deck]
        assert tie_ci.instance_id not in deck_ids
        assert scout_ci.instance_id not in deck_ids
        assert cons_ci.instance_id in deck_ids
        assert not state.pending_decisions

    def test_sor_87_finish_with_nothing_taken_is_a_clean_noop(self, repo):
        from swu.engine.actions import apply, FinishSearch
        tie = _get_card(repo, "SOR", "225")
        scout = _get_card(repo, "SOR", "32")
        state, vader, deck = self._setup(repo, [tie, scout])
        tie_ci, scout_ci = deck

        state = _fire_when_played(state, vader)
        state = apply(state, FinishSearch())
        # Nothing played; both stay in the deck (bottomed among themselves).
        assert _find_instance(state, tie_ci.instance_id) is None
        assert _find_instance(state, scout_ci.instance_id) is None
        deck_ids = {c.instance_id for c in state.player_by_id("P0").deck}
        assert {tie_ci.instance_id, scout_ci.instance_id} <= deck_ids
        assert not state.pending_decisions

    def test_sor_87_reprints_c24_2_and_p25_103_alias_to_sor_87(self):
        from swu.cards.reprints import REPRINT_ALIASES
        from swu.abilities.registry import get_abilities
        assert REPRINT_ALIASES[("C24", "2")] == ("SOR", "87")
        assert REPRINT_ALIASES[("P25", "103")] == ("SOR", "87")
        canonical = get_abilities("SOR", "87")
        assert canonical, "SOR_87 should be registered"
        assert get_abilities("C24", "2") == canonical
        assert get_abilities("P25", "103") == canonical


# ── group_01 — Direct damage & removal ───────────────────────────────────────

def _use_leader_ability(state, leader_ci):
    from swu.engine.actions import legal_actions, apply, UseAbility
    use = next(a for a in legal_actions(state)
               if isinstance(a, UseAbility) and a.source_id == leader_ci.instance_id)
    return apply(state, use)


def _choose(state, target_id):
    from swu.engine.actions import legal_actions, apply, ChooseTarget
    ch = next(a for a in legal_actions(state)
              if isinstance(a, ChooseTarget) and a.target_id == target_id)
    return apply(state, ch)


class TestEmperorPalpatineSOR6:
    def test_SOR_6_undeployed_defeats_friendly_deals_damage_and_draws(self, repo):
        friendly = _get_card(repo, "SOR", "61")   # 2/2 friendly to sacrifice
        enemy = _get_card(repo, "SOR", "46")       # 3/7 enemy to damage
        state = _make_state()
        palp_ci = _place_leader(state, "P0", _get_card(repo, "SOR", "6"))
        _give_resources(state, "P0", 3)
        fr = _place(state, "P0", friendly, "ground")
        en = _place(state, "P1", enemy, "ground")
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "59"))
        hand_before = len(state.players[0].hand)

        state = _use_leader_ability(state, palp_ci)
        state = _choose(state, fr.instance_id)       # defeat the friendly unit
        state = _choose(state, en.instance_id)       # deal 1 to the enemy unit

        assert _find_instance(state, fr.instance_id) is None, "friendly unit defeated (cost)"
        en_now = _find_instance(state, en.instance_id)
        assert en_now is not None and en_now.damage == 1, "enemy unit took 1 damage"
        assert len(state.players[0].hand) == hand_before + 1, "drew a card"
        assert state.players[0].leader_instance.exhausted, "leader exhausted"
        assert state.players[0].available_resources == 2, "1 resource spent"

    def test_SOR_6_undeployed_gated_out_without_a_friendly_unit(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        palp_ci = _place_leader(state, "P0", _get_card(repo, "SOR", "6"))
        _give_resources(state, "P0", 3)
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # only an enemy unit
        assert not any(isinstance(a, UseAbility) and a.source_id == palp_ci.instance_id
                       for a in legal_actions(state)), (
            "no friendly unit to defeat -> the Action is not offered")


class TestGrandInquisitorSOR11:
    def test_SOR_11_undeployed_damages_and_readies_low_power_friendly(self, repo):
        state = _make_state()
        gi_ci = _place_leader(state, "P0", _get_card(repo, "SOR", "11"))
        low = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # 3/7 (power 3)
        high = _place(state, "P0", _get_card(repo, "SOR", "51"), "ground")  # 6/7 (power 6)
        low.exhausted = True
        high.exhausted = True

        state = _use_leader_ability(state, gi_ci)
        from swu.engine.actions import legal_actions, ChooseTarget
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert offered == {low.instance_id}, "only the power-3-or-less friendly is targetable"

        state = _choose(state, low.instance_id)
        low_now = _find_instance(state, low.instance_id)
        assert low_now.damage == 2, "dealt 2 damage"
        assert not low_now.exhausted, "readied the target"


class TestCassianAndorSOR13:
    def test_SOR_13_undeployed_draws_only_after_3_base_damage_this_phase(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility
        state = _make_state()
        cass_ci = _place_leader(state, "P0", _get_card(repo, "SOR", "13"))
        _give_resources(state, "P0", 3)
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "59"))

        def _offered():
            return [a for a in legal_actions(state)
                    if isinstance(a, UseAbility) and a.source_id == cass_ci.instance_id]

        assert _offered() == [], "no base damage yet -> the Action is gated out"
        state.game_memory.base_damage_dealt_this_phase["P0"] = 2
        assert _offered() == [], "2 (< 3) base damage -> still gated out"
        state.game_memory.base_damage_dealt_this_phase["P0"] = 3
        hand_before = len(state.players[0].hand)
        state = apply(state, _offered()[0])
        assert len(state.players[0].hand) == hand_before + 1, "drew a card at 3+ base damage"


class TestHanSoloSOR17:
    def test_SOR_17_undeployed_resources_hand_card_then_defeats_a_resource(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import _fire_scheduled_action_phase_effects
        state = _make_state()
        han_ci = _place_leader(state, "P0", _get_card(repo, "SOR", "17"))
        ps = state.players[0]
        for i in range(2):
            ps.hand.append(CardInstance(
                instance_id=f"P0_hand_{i}", card_def=_get_card(repo, "SOR", "46"),
                owner_id="P0", zone=Zone.HAND))
        res_before = len(ps.resources)

        state = _use_leader_ability(state, han_ci)
        ps = state.players[0]
        assert len(ps.resources) == res_before + 1, "a hand card became a resource"
        assert len(ps.hand) == 1, "one card left the hand"
        assert ps.resources[-1].face_down and not ps.resources[-1].exhausted, "ready face-down resource"
        assert any(e.get("kind") == "defeat_own_resource"
                   for e in state.scheduled_action_phase_effects), "delayed defeat scheduled"

        _fire_scheduled_action_phase_effects(state)
        assert len(state.players[0].resources) == res_before, "one resource defeated next phase"
        assert not state.scheduled_action_phase_effects, "scheduled effect consumed"


class TestTarkintownSOR25:
    def test_SOR_25_epic_deals_3_to_a_damaged_non_leader_unit(self, repo):
        from swu.engine.state import CardInstance, Zone
        state = _make_state(include_bases=False)
        tark_ci = CardInstance(
            instance_id="P0_tarkintown", card_def=_get_card(repo, "SOR", "25"),
            owner_id="P0", zone=Zone.BASE_ZONE)
        state.players[0].base_zone.append(tark_ci)
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        victim.damage = 1  # damaged

        from swu.engine.actions import legal_actions, apply, UseAbility
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == tark_ci.instance_id)
        state = apply(state, use)
        state = _choose(state, victim.instance_id)
        victim_now = _find_instance(state, victim.instance_id)
        assert victim_now.damage == 4, "1 + 3 epic damage"


class TestCountDookuSOR38:
    def test_SOR_38_when_played_may_defeat_low_hp_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        dooku = _place(state, "P0", _get_card(repo, "SOR", "38"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        victim.damage = 4  # remaining HP = 3 (<= 4) -> eligible
        safe = _place(state, "P1", _get_card(repo, "SOR", "51"), "ground")    # 6/7 remaining 7

        _fire_when_played(state, dooku)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert victim.instance_id in offered and safe.instance_id not in offered, (
            "only a unit with 4 or less remaining HP is a legal target")
        state = _choose(state, victim.instance_id)
        assert _find_instance(state, victim.instance_id) is None, "the low-HP unit is defeated"


class TestPowerOfTheDarkSideSOR41:
    def test_SOR_41_opponent_defeats_their_own_chosen_unit(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, PlayCard, ChooseOwnTarget
        state = _make_state()
        pods = CardInstance(instance_id="P0_pods", card_def=_get_card(repo, "SOR", "41"),
                            owner_id="P0", zone=Zone.HAND)
        state.players[0].hand.append(pods)
        _give_resources(state, "P0", 10)  # cover cost + any aspect penalty
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == pods.instance_id)
        state = apply(state, play)
        top = state.pending_decisions[-1]
        assert top.kind == "opponent_chooses_target" and top.deciding_player_id == "P1"
        chosen = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseOwnTarget) and a.target_id == victim.instance_id)
        state = apply(state, chosen)
        assert _find_instance(state, victim.instance_id) is None, "opponent's chosen unit is defeated"


# ── sor-set:02 — Direct damage & removal ─────────────────────────────────────

def _accept_trigger(state):
    from swu.engine.actions import legal_actions, apply, AcceptTrigger
    act = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
    return apply(state, act)


class TestRedemptionSOR52:
    def test_SOR_52_heals_own_units_and_base_then_self_damages(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AssignDamage, FinishDamageDistribution)
        state = _make_state()
        redemption = _place(state, "P0", _get_card(repo, "SOR", "52"), "space")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        ally.damage = 3
        base = state.players[0].base_instance
        base.damage = 2

        state = _fire_when_played(state, redemption)
        top = state.pending_decisions[-1]
        assert top.kind == "distribute_damage" and top.context.get("heal")
        # Own damaged ally AND own damaged base are heal targets; the enemy is not.
        targets = {a.target_id for a in legal_actions(state)
                   if isinstance(a, AssignDamage)}
        assert ally.instance_id in targets and base.instance_id in targets

        # Heal all 3 off the ally, then stop (the pool is "up to 8").
        for _ in range(3):
            act = next(a for a in legal_actions(state)
                       if isinstance(a, AssignDamage) and a.target_id == ally.instance_id)
            state = apply(state, act)
        # Ally is now fully healed, so it drops out of the target list.
        assert ally.instance_id not in {
            a.target_id for a in legal_actions(state) if isinstance(a, AssignDamage)}
        fin = next(a for a in legal_actions(state)
                   if isinstance(a, FinishDamageDistribution))
        state = apply(state, fin)

        assert not state.pending_decisions
        assert _find_instance(state, ally.instance_id).damage == 0, "ally healed"
        red_now = _find_instance(state, redemption.instance_id)
        assert red_now is not None and red_now.damage == 3, "3 healed -> 3 self damage"

    def test_SOR_52_fizzles_with_nothing_damaged(self, repo):
        state = _make_state()
        redemption = _place(state, "P0", _get_card(repo, "SOR", "52"), "space")
        state = _fire_when_played(state, redemption)
        assert not state.pending_decisions, "nothing to heal -> no decision, no self damage"
        assert _find_instance(state, redemption.instance_id).damage == 0


class TestItBindsAllThingsSOR75:
    def test_SOR_75_heals_then_damages_another_with_a_force_unit(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        # A friendly Force unit enables the payoff (Luke Skywalker SOR_51 is a Force unit).
        force_unit = _place(state, "P0", _get_card(repo, "SOR", "51"), "ground")
        healme = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        healme.damage = 3
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7

        state, _ = _play_event_from_hand(state, repo, "SOR", "75")
        # First effect: heal a damaged unit.
        state = _choose(state, healme.instance_id)
        assert _find_instance(state, healme.instance_id).damage == 0, "healed 3"
        # Second effect: deal that 3 to ANOTHER unit; the healed unit is excluded.
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert victim.instance_id in offered and healme.instance_id not in offered
        state = _choose(state, victim.instance_id)
        assert _find_instance(state, victim.instance_id).damage == 3, "dealt the healed 3"

    def test_SOR_75_no_payoff_prompt_without_a_force_unit(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        healme = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        healme.damage = 2
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        state, _ = _play_event_from_hand(state, repo, "SOR", "75")
        state = _choose(state, healme.instance_id)
        assert _find_instance(state, healme.instance_id).damage == 0, "still heals"
        # No Force unit controlled -> the optional "deal that much" step is not offered.
        assert not state.pending_decisions
        assert not any(isinstance(a, ChooseTarget) for a in legal_actions(state))


class TestTakedownSOR77:
    def test_SOR_77_defeats_only_a_unit_with_5_or_less_remaining_hp(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        weak = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        weak.damage = 2   # remaining 5 -> eligible
        tough = _place(state, "P1", _get_card(repo, "SOR", "51"), "ground")  # 6/7 remaining 7

        state, _ = _play_event_from_hand(state, repo, "SOR", "77")
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert weak.instance_id in offered and tough.instance_id not in offered
        state = _choose(state, weak.instance_id)
        assert _find_instance(state, weak.instance_id) is None, "the <=5 HP unit is defeated"


class TestRukhSOR85:
    def test_SOR_85_defeats_a_non_leader_unit_it_damaged_in_combat(self, repo):
        from swu.engine.actions import apply, AttackWithUnit
        state = _make_state()
        rukh = _place(state, "P0", _get_card(repo, "SOR", "85"), "ground")  # 3/6
        # A 3/7 defender survives Rukh's 3 combat damage and deals only 3 back
        # (Rukh, 6 HP, survives) — so the trigger, not combat, defeats it.
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        state = apply(state, AttackWithUnit(rukh.instance_id, defender.instance_id))
        assert _find_instance(state, rukh.instance_id) is not None, "Rukh survives combat"
        assert _find_instance(state, defender.instance_id) is None, (
            "the damaged non-leader defender is defeated by the trigger")


class TestDevastatorSOR90:
    def test_SOR_90_when_played_deals_damage_equal_to_resources(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 4)
        devastator = _place(state, "P0", _get_card(repo, "SOR", "90"), "space")
        victim = _place(state, "P1", _get_card(repo, "SOR", "51"), "ground")  # 6/7

        state = _fire_when_played(state, devastator)
        state = _accept_trigger(state)   # "you may"
        state = _choose(state, victim.instance_id)
        assert _find_instance(state, victim.instance_id).damage == 4, "4 resources -> 4 damage"


class TestHardpointHeavyBlasterSOR121:
    def _attach(self, state, host_ci, repo):
        from swu.engine.state import CardInstance
        up = _get_card(repo, "SOR", "121")
        up_ci = CardInstance(
            instance_id=f"up_{uuid.uuid4().hex[:6]}", card_def=up,
            owner_id=host_ci.owner_id, zone=host_ci.zone)
        host_ci.attached_upgrades.append(up_ci)
        return up_ci

    def test_SOR_121_deals_2_to_a_unit_in_the_defenders_arena(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        defender = _place(state, "P1", _get_card(repo, "SOR", "51"), "ground")  # 6/7
        elsewhere = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")  # other arena
        self._attach(state, host, repo)

        state = _fire_on_attack(state, host, defender)
        assert state.pending_decisions[-1].kind == "resolve_effects"
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        # Ground units (defender + attacker) are in the defender's arena; the space
        # unit is not.
        assert defender.instance_id in offered
        assert elsewhere.instance_id not in offered
        state = _choose(state, defender.instance_id)
        assert _find_instance(state, defender.instance_id).damage == 2

    def test_SOR_121_no_effect_when_attacking_a_base(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "51"), "ground")
        self._attach(state, host, repo)

        state = _fire_on_attack(state, host, None)  # attacking a base
        assert not state.pending_decisions, "no prompt / fizzle when attacking a base"
        assert not any(isinstance(a, ChooseTarget) for a in legal_actions(state))


class TestSeventhSisterSOR133:
    def test_SOR_133_deals_3_to_an_enemy_ground_unit_on_base_damage(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        sister = _place(state, "P0", _get_card(repo, "SOR", "133"), "ground")  # 3/6, Saboteur
        target = _place(state, "P1", _get_card(repo, "SOR", "51"), "ground")   # 6/7

        # The base-attack action (its defender id is the base sentinel, not a unit id).
        base_attack = next(
            a for a in legal_actions(state)
            if isinstance(a, AttackWithUnit) and a.attacker_id == sister.instance_id
            and a.defender_id != target.instance_id)
        state = apply(state, base_attack)
        assert state.players[1].base_instance.damage == 3, "base took 3 combat damage"
        # Optional "you may deal 3" trigger for P0.
        state = _accept_trigger(state)
        state = _choose(state, target.instance_id)
        assert _find_instance(state, target.instance_id).damage == 3


# ── sor-set:03 — Direct damage & removal ─────────────────────────────────────


def _fire_card_played(state, player_id, played_ci):
    """Fire a CardPlayed observer as if ``player_id`` just played ``played_ci``
    (which must already be homed somewhere find_instance reaches — e.g. discard)."""
    from swu.engine.events import CardPlayed
    from swu.abilities.resolver import fire_triggered_abilities
    evt = CardPlayed(player_id=player_id, instance_id=played_ci.instance_id,
                     card_name=played_ci.card_def.display_name, cost_paid=0)
    state.event_log.append(evt)
    after = 1 - state.player_index(player_id)
    return fire_triggered_abilities(state, evt, after_all_player_idx=after)


class TestRuthlessRaiderSOR134:
    def test_SOR_134_when_played_and_when_defeated_hit_enemy_base_and_unit(self, repo):
        state = _make_state()
        raider = _place(state, "P0", _get_card(repo, "SOR", "134"), "space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "51"), "ground")  # 6/7
        enemy_base = state.players[1].base_instance

        # When Played: 2 to the enemy base, then 2 to an enemy unit (each a choice).
        state = _fire_when_played(state, raider)
        state = _choose(state, enemy_base.instance_id)
        assert state.players[1].base_instance.damage == 2, "base took 2"
        state = _choose(state, enemy.instance_id)
        assert _find_instance(state, enemy.instance_id).damage == 2, "unit took 2"

        # When Defeated fires the same two effects again.
        state = _fire_when_defeated(state, raider)
        state = _choose(state, enemy_base.instance_id)
        assert state.players[1].base_instance.damage == 4, "base took 2 more"
        state = _choose(state, enemy.instance_id)
        assert _find_instance(state, enemy.instance_id).damage == 4, "unit took 2 more"


class TestForceLightningSOR138:
    def test_SOR_138_suppresses_then_pays_resources_for_scaling_damage(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, PayResourceForToken, FinishPayResources)
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "51"), "ground")  # friendly Force unit
        victim = _place(state, "P1", _get_card(repo, "SOR", "51"), "ground")  # 6/7

        state, _ = _play_event_from_hand(state, repo, "SOR", "138")
        # First: choose the unit that loses all abilities.
        state = _choose(state, victim.instance_id)
        assert _find_instance(state, victim.instance_id).abilities_suppressed is True

        # A Force unit is controlled -> pay-any-number-of-resources damage is offered.
        top = state.pending_decisions[-1]
        assert top.kind == "pay_resources_for_tokens" and top.context["payoff"] == "damage"
        before = state.players[0].available_resources
        # Pay 2 resources (2 damage each), then stop.
        for _ in range(2):
            act = next(a for a in legal_actions(state) if isinstance(a, PayResourceForToken))
            state = apply(state, act)
        fin = next(a for a in legal_actions(state) if isinstance(a, FinishPayResources))
        state = apply(state, fin)
        # The event's own resolve_effects sits under the pay decision; pop it.
        if state.pending_decisions:
            state = _auto_resolve(state)

        assert not state.pending_decisions
        assert state.players[0].available_resources == before - 2, "2 resources spent"
        assert _find_instance(state, victim.instance_id).damage == 4, "2 resources -> 4 damage"

    def test_SOR_138_suppresses_without_a_force_unit_but_deals_no_damage(self, repo):
        state = _make_state()
        victim = _place(state, "P1", _get_card(repo, "SOR", "51"), "ground")
        state, _ = _play_event_from_hand(state, repo, "SOR", "138")
        state = _choose(state, victim.instance_id)
        assert _find_instance(state, victim.instance_id).abilities_suppressed is True
        assert not state.pending_decisions, "no Force unit -> no pay decision"
        assert _find_instance(state, victim.instance_id).damage == 0


class TestZebOrreliosSOR146:
    def test_SOR_146_deals_4_to_a_ground_unit_when_it_defeats_the_defender(self, repo):
        from swu.engine.actions import apply, AttackWithUnit
        state = _make_state()
        zeb = _place(state, "P0", _get_card(repo, "SOR", "146"), "ground")  # 5/5
        defender = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")  # 3/1
        bystander = _place(state, "P1", _get_card(repo, "SOR", "51"), "ground")  # 6/7

        state = apply(state, AttackWithUnit(zeb.instance_id, defender.instance_id))
        assert _find_instance(state, defender.instance_id) is None, "defender defeated"
        # Optional "you may deal 4 damage to a ground unit".
        state = _accept_trigger(state)
        state = _choose(state, bystander.instance_id)
        assert _find_instance(state, bystander.instance_id).damage == 4


class TestSawGerreraSOR153:
    def test_SOR_153_deals_2_to_the_event_players_base_when_they_play_an_event(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "153"), "ground")  # Saw, P0's unit
        p1_base = state.players[1].base_instance
        # Home a played event in P1's discard, then fire the CardPlayed observer.
        from swu.engine.state import CardInstance, Zone
        evt_card = CardInstance("p1_evt", _get_card(repo, "SOR", "167"), "P1", Zone.DISCARD)
        state.players[1].discard.append(evt_card)

        state = _fire_card_played(state, "P1", evt_card)
        state = _choose(state, p1_base.instance_id)  # the single enemy base is the target
        assert state.players[1].base_instance.damage == 2, "their base took 2"

    def test_SOR_153_does_not_fire_on_a_friendly_event(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "153"), "ground")
        p0_base = state.players[0].base_instance
        from swu.engine.state import CardInstance, Zone
        evt_card = CardInstance("p0_evt", _get_card(repo, "SOR", "167"), "P0", Zone.DISCARD)
        state.players[0].discard.append(evt_card)
        state = _fire_card_played(state, "P0", evt_card)
        assert not state.pending_decisions, "own event -> Saw's trigger not collected"
        assert state.players[0].base_instance.damage == 0, "own event costs nothing"


class TestJedhaAgitatorSOR158:
    def test_SOR_158_deals_2_with_a_leader_unit_but_not_without_one(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        # With a deployed leader unit: the On Attack trigger fires.
        state = _make_state()
        agitator = _place(state, "P0", _get_card(repo, "SOR", "158"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "5"), "ground")  # Luke leader unit
        target = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _fire_on_attack(state, agitator, target)
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert target.instance_id in offered, "a ground unit is a valid target"
        state = _choose(state, target.instance_id)
        assert _find_instance(state, target.instance_id).damage == 2

        # Without a leader unit: the trigger is never collected (no prompt, no damage).
        state2 = _make_state()
        agi2 = _place(state2, "P0", _get_card(repo, "SOR", "158"), "ground")
        t2 = _place(state2, "P1", _get_card(repo, "SOR", "46"), "ground")
        state2 = _fire_on_attack(state2, agi2, t2)
        assert not state2.pending_decisions, "no leader unit -> no trigger"
        assert _find_instance(state2, t2.instance_id).damage == 0


class TestForceThrowSOR167:
    def test_SOR_167_discards_and_deals_damage_equal_to_cost_with_a_force_unit(self, repo):
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "51"), "ground")  # friendly Force unit
        target = _place(state, "P1", _get_card(repo, "SOR", "51"), "ground")  # 6/7
        discard_def = _get_card(repo, "SOR", "134")  # Ruthless Raider, cost 6
        cost = discard_def.cost
        state.players[1].hand.append(CardInstance("p1_disc", discard_def, "P1", Zone.HAND))

        state, _ = _play_event_from_hand(state, repo, "SOR", "167")
        # Auto-resolve runs the mandatory discard and arms the payoff.
        state = _auto_resolve(state)
        assert not state.players[1].hand, "opponent discarded their card"
        # Payoff armed (Force unit + positive cost) -> deal that cost to a chosen unit.
        state = _choose(state, target.instance_id)
        assert _find_instance(state, target.instance_id).damage == cost, "cost-many damage"

    def test_SOR_167_no_payoff_without_a_force_unit(self, repo):
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        target = _place(state, "P1", _get_card(repo, "SOR", "51"), "ground")
        state.players[1].hand.append(
            CardInstance("p1_disc2", _get_card(repo, "SOR", "134"), "P1", Zone.HAND))
        state, _ = _play_event_from_hand(state, repo, "SOR", "167")
        state = _auto_resolve(state)  # mandatory discard runs; payoff not armed
        assert not state.players[1].hand, "still discards (mandatory)"
        assert not state.pending_decisions, "no Force unit -> no damage prompt"
        assert _find_instance(state, target.instance_id).damage == 0


class TestPowerFailureSOR170:
    def _attach(self, state, host_ci, repo, num):
        from swu.engine.state import CardInstance
        up = CardInstance(
            instance_id=f"up_{uuid.uuid4().hex[:6]}", card_def=_get_card(repo, "SOR", num),
            owner_id=host_ci.owner_id, zone=host_ci.zone)
        host_ci.attached_upgrades.append(up)
        return up

    def test_SOR_170_defeats_all_upgrades_on_the_chosen_unit(self, repo):
        state = _make_state()
        host = _place(state, "P1", _get_card(repo, "SOR", "51"), "ground")
        up1 = self._attach(state, host, repo, "121")
        up2 = self._attach(state, host, repo, "121")

        state, _ = _play_event_from_hand(state, repo, "SOR", "170")
        state = _choose(state, host.instance_id)
        remaining = {u.instance_id for u in _find_instance(state, host.instance_id).attached_upgrades}
        assert up1.instance_id not in remaining and up2.instance_id not in remaining, (
            "all real upgrades defeated")


# ── sor-set:04 & :05 — direct damage / removal + card advantage ──────────────

def _modal_option(state, mode):
    from swu.engine.actions import legal_actions, apply
    act = next(a for a in legal_actions(state)
               if type(a).__name__ == "ChooseModalOption" and a.mode == mode)
    return apply(state, act)


def _discard_unit(state, owner_id, card_def):
    """Create a CardInstance for card_def in owner's discard pile. Returns it."""
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(
        instance_id=f"{owner_id}_disc_{uuid.uuid4().hex[:6]}",
        card_def=card_def, owner_id=owner_id, zone=Zone.DISCARD,
    )
    state.player_by_id(owner_id).discard.append(ci)
    return ci


class TestBombingRunSOR173:
    def test_SOR_173_bombs_the_chosen_arena_only(self, repo):
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        their_ground = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")  # 3/1
        their_space = _place(state, "P1", _get_card(repo, "SOR", "51"), "space")     # 6/7

        state, _ = _play_event_from_hand(state, repo, "SOR", "173")
        assert state.pending_decisions[-1].kind == "modal"
        # Choosing the ground arena hits every ground unit (both players).
        state = _modal_option(state, "bomb_ground")

        assert _find_instance(state, mine.instance_id).damage == 3, "friendly ground unit hit"
        assert _find_instance(state, their_ground.instance_id) is None, "1-hp ground unit defeated"
        assert _find_instance(state, their_space.instance_id).damage == 0, "space arena untouched"

    def test_SOR_173_only_non_empty_arenas_are_offered(self, repo):
        state = _make_state()
        _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")  # only a ground unit
        state, _ = _play_event_from_hand(state, repo, "SOR", "173")
        from swu.engine.actions import legal_actions
        modes = {a.mode for a in legal_actions(state)
                 if type(a).__name__ == "ChooseModalOption"}
        assert modes == {"bomb_ground"}, "empty space arena is not offered"


class TestBobaFettSOR179:
    def test_SOR_179_deals_3_to_an_exhausted_defender_that_didnt_enter_this_round(self, repo):
        state = _make_state()
        boba = _place(state, "P0", _get_card(repo, "SOR", "179"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        enemy.exhausted = True
        state = _fire_on_attack(state, boba, enemy)
        if state.pending_decisions:
            state = _auto_resolve(state)
        assert _find_instance(state, enemy.instance_id).damage == 3

    def test_SOR_179_no_damage_to_a_ready_defender(self, repo):
        state = _make_state()
        boba = _place(state, "P0", _get_card(repo, "SOR", "179"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        enemy.exhausted = False
        state = _fire_on_attack(state, boba, enemy)
        if state.pending_decisions:
            state = _auto_resolve(state)
        assert _find_instance(state, enemy.instance_id).damage == 0

    def test_SOR_179_no_damage_if_defender_entered_this_round(self, repo):
        state = _make_state()
        boba = _place(state, "P0", _get_card(repo, "SOR", "179"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        enemy.exhausted = True
        state.game_memory.units_played_this_phase.add(enemy.instance_id)
        state = _fire_on_attack(state, boba, enemy)
        if state.pending_decisions:
            state = _auto_resolve(state)
        assert _find_instance(state, enemy.instance_id).damage == 0


class TestBosskSOR182:
    def test_SOR_182_when_you_play_an_event_may_deal_2_to_a_unit(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "182"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "51"), "ground")  # 6/7
        evt_ci = _discard_unit(state, "P0", _get_card(repo, "SOR", "58"))  # an Event
        state = _fire_card_played(state, "P0", evt_ci)
        assert state.pending_decisions, "optional trigger offered"
        state = _accept_trigger(state)
        state = _choose(state, enemy.instance_id)
        assert _find_instance(state, enemy.instance_id).damage == 2


class TestDontGetCockySOR223:
    def test_SOR_223_reveal_and_stop_deals_combined_cost(self, repo):
        from swu.engine.actions import legal_actions, apply, RevealNextCard, StopRevealing
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "51"), "ground")  # 6/7
        # Deck top → [SOR_96 (cost 2), SOR_45 (cost 3), SOR_173 (cost 5)].
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "173"))
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "45"))
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "96"))

        state, _ = _play_event_from_hand(state, repo, "SOR", "223")
        state = _choose(state, enemy.instance_id)   # choose the unit
        assert state.pending_decisions[-1].kind == "reveal_cost_damage"

        # Reveal the top two (2 + 3 = 5), then stop before the 5-cost card.
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, RevealNextCard)))
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, RevealNextCard)))
        assert state.pending_decisions[-1].context["tally"] == 5
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, StopRevealing)))

        # The event's own resolve_effects sits under the reveal decision; pop it.
        if state.pending_decisions:
            state = _auto_resolve(state)
        assert not state.pending_decisions
        assert _find_instance(state, enemy.instance_id).damage == 5
        assert len(state.players[0].deck) == 3, "revealed cards returned to the deck"

    def test_SOR_223_over_the_threshold_deals_no_damage(self, repo):
        from swu.engine.actions import legal_actions, apply, RevealNextCard
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "51"), "ground")
        # Deck = two cards costing 4 + 5 = 9 (> 7); revealing both auto-finishes.
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "173"))  # 5
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))   # 4
        state, _ = _play_event_from_hand(state, repo, "SOR", "223")
        state = _choose(state, enemy.instance_id)
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, RevealNextCard)))
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, RevealNextCard)))
        # Deck end auto-finishes the reveal; the event's resolve_effects remains — pop it.
        if state.pending_decisions:
            state = _auto_resolve(state)
        assert not state.pending_decisions
        assert _find_instance(state, enemy.instance_id).damage == 0


class TestGalacticAmbitionSOR235:
    def test_SOR_235_plays_a_non_heroism_unit_free_and_damages_own_base(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        state = _make_state()
        trooper = CardInstance("P0_128_h", _get_card(repo, "SOR", "128"), "P0", Zone.HAND)  # cost 1
        state.player_by_id("P0").hand.append(trooper)

        state, _ = _play_event_from_hand(state, repo, "SOR", "235")
        assert state.pending_decisions[-1].kind == "play_from_hand"
        act = next(a for a in legal_actions(state)
                   if isinstance(a, PlayFromHand) and a.instance_id == trooper.instance_id)
        state = apply(state, act)

        assert _find_instance(state, trooper.instance_id) is not None, "unit entered play"
        assert state.players[0].base_instance.damage == 1, "own base took the unit's cost (1)"

    def test_SOR_235_excludes_heroism_units(self, repo):
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        # Only a Heroism unit in hand → nothing eligible, nothing plays.
        luke = CardInstance("P0_51_h", _get_card(repo, "SOR", "51"), "P0", Zone.HAND)  # Heroism
        state.player_by_id("P0").hand.append(luke)
        state, _ = _play_event_from_hand(state, repo, "SOR", "235")
        assert not state.pending_decisions, "no non-Heroism unit → fizzles"
        assert state.players[0].base_instance.damage == 0


class TestInfernoFourSOR31:
    def test_SOR_31_when_played_reveals_top_2_and_bottoms_the_chosen(self, repo):
        from swu.engine.actions import apply, KeepRevealed, DiscardRevealed
        state = _make_state()
        inferno = _place(state, "P0", _get_card(repo, "SOR", "31"), "space")
        b = _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        a = _push_deck_top(state, "P0", _get_card(repo, "SOR", "45"))  # a on top, then b

        state = _fire_when_played(state, inferno)
        top = state.pending_decisions[-1]
        assert top.kind == "reveal_top" and top.context["disposition"] == "bottom"
        # Bottom 'a', keep 'b' on top.
        state = apply(state, DiscardRevealed(a.instance_id))
        state = apply(state, KeepRevealed(b.instance_id))
        deck_ids = [c.instance_id for c in state.players[0].deck]
        assert deck_ids[0] == b.instance_id, "kept card on top"
        assert deck_ids[-1] == a.instance_id, "bottomed card on the bottom"

    def test_SOR_31_also_fires_when_defeated(self, repo):
        state = _make_state()
        inferno = _place(state, "P0", _get_card(repo, "SOR", "31"), "space")
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state = _fire_when_defeated(state, inferno)
        assert state.pending_decisions[-1].kind == "reveal_top"


class TestSearchYourFeelingsSOR42:
    def test_SOR_42_searches_the_whole_deck_and_draws_the_chosen(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectSearchCard, FinishSearch
        state = _make_state()
        c1 = _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        c2 = _push_deck_top(state, "P0", _get_card(repo, "SOR", "45"))
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        state, _ = _play_event_from_hand(state, repo, "SOR", "42")
        top = state.pending_decisions[-1]
        assert top.kind == "deck_search" and top.context["window"] == 3
        assert c1.instance_id in top.context["candidate_ids"]
        state = apply(state, SelectSearchCard(c2.instance_id))
        if any(isinstance(a, FinishSearch) for a in legal_actions(state)):
            state = apply(state, FinishSearch())
        hand_ids = {c.instance_id for c in state.players[0].hand}
        assert c2.instance_id in hand_ids, "chosen card drawn to hand"


class TestRuggedSurvivorsSOR67:
    def test_SOR_67_draws_when_you_control_a_leader_unit(self, repo):
        state = _make_state()
        rugged = _place(state, "P0", _get_card(repo, "SOR", "67"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "5"), "ground")  # a leader unit
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        before = len(state.players[0].hand)
        state = _fire_on_attack(state, rugged)
        assert state.pending_decisions, "optional draw offered"
        state = _accept_trigger(state)
        if state.pending_decisions:
            state = _auto_resolve(state)
        assert len(state.players[0].hand) == before + 1

    def test_SOR_67_no_trigger_without_a_leader_unit(self, repo):
        state = _make_state()
        rugged = _place(state, "P0", _get_card(repo, "SOR", "67"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state = _fire_on_attack(state, rugged)
        assert not state.pending_decisions, "condition gates collection — no prompt"


class TestEmperorsLegionSOR91:
    def test_SOR_91_returns_units_defeated_this_phase(self, repo):
        state = _make_state()
        killed = _discard_unit(state, "P0", _get_card(repo, "SOR", "46"))
        survived = _discard_unit(state, "P0", _get_card(repo, "SOR", "45"))
        state.game_memory.units_defeated_this_round.add(killed.instance_id)
        state, _ = _play_event_from_hand(state, repo, "SOR", "91")
        hand_ids = {c.instance_id for c in state.players[0].hand}
        assert killed.instance_id in hand_ids, "unit defeated this phase returned"
        assert survived.instance_id not in hand_ids, "other discard unit stays"
        assert killed.instance_id not in {c.instance_id for c in state.players[0].discard}


class TestMonMothmaSOR96:
    def test_SOR_96_searches_top_5_for_a_rebel_and_draws_it(self, repo):
        from swu.engine.actions import apply, SelectSearchCard, FinishSearch
        state = _make_state()
        mothma = _place(state, "P0", _get_card(repo, "SOR", "96"), "ground")
        rebel = _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))  # Rebel
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))         # non-Rebel on top
        state = _fire_when_played(state, mothma)
        top = state.pending_decisions[-1]
        assert top.kind == "deck_search"
        assert top.context["candidate_ids"] == [rebel.instance_id], "only the Rebel is a candidate"
        state = apply(state, SelectSearchCard(rebel.instance_id))
        if state.pending_decisions:
            state = apply(state, FinishSearch())
        assert rebel.instance_id in {c.instance_id for c in state.players[0].hand}


class TestRogueSquadronSkirmisherSOR101:
    def test_SOR_101_returns_a_cheap_unit_from_discard(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectDiscardCard, FinishReturnFromDiscard
        state = _make_state()
        rogue = _place(state, "P0", _get_card(repo, "SOR", "101"), "space")
        cheap = _discard_unit(state, "P0", _get_card(repo, "SOR", "128"))  # cost 1
        _discard_unit(state, "P0", _get_card(repo, "SOR", "102"))          # cost 8, ineligible
        state = _fire_when_played(state, rogue)
        top = state.pending_decisions[-1]
        assert top.kind == "return_from_discard"
        assert top.context["candidate_ids"] == [cheap.instance_id]
        state = apply(state, SelectDiscardCard(cheap.instance_id))
        if any(isinstance(a, FinishReturnFromDiscard) for a in legal_actions(state)):
            state = apply(state, FinishReturnFromDiscard())
        assert cheap.instance_id in {c.instance_id for c in state.players[0].hand}


class TestHomeOneSOR102:
    def test_SOR_102_grants_restore_1_to_other_friendly_units(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "102"), "space")
        ally = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert has_keyword(state, ally, Keyword.RESTORE), "other friendly unit gains Restore"
        assert keyword_value(state, ally, Keyword.RESTORE) == 1
        assert not has_keyword(state, enemy, Keyword.RESTORE), "enemy unit unaffected"

    def test_SOR_102_when_played_plays_a_heroism_unit_from_discard(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        state = _make_state()
        home = _place(state, "P0", _get_card(repo, "SOR", "102"), "space")
        heroism = _discard_unit(state, "P0", _get_card(repo, "SOR", "46"))  # Heroism, cost 4
        _give_resources(state, "P0", 10)  # cover cost 4 (−3) plus any aspect penalty
        state = _fire_when_played(state, home)
        assert state.pending_decisions[-1].kind == "play_from_hand"
        act = next(a for a in legal_actions(state)
                   if isinstance(a, PlayFromHand) and a.instance_id == heroism.instance_id)
        state = apply(state, act)
        assert _find_instance(state, heroism.instance_id) is not None, "Heroism unit played from discard"


# ── Gap-fill: card advantage & disruption (sor-set:06) ────────────────────────

def _fire_other_unit_defeated(state, victim, controller_id):
    """Mimic the real defeat path for an OBSERVER (WhenUnitDefeated) trigger: the
    engine fires UnitDefeated after removing the victim from its arena but BEFORE
    homing it in discard (its ``zone`` still reads as the arena), so the observer's
    ``kind="unit"`` filter matches the still-arena-zoned ``defeated_ci``.  (Unlike
    ``_defeat_and_fire``, which homes the card in discard for a self-WhenDefeated.)"""
    from swu.engine.events import UnitDefeated
    from swu.abilities.resolver import fire_triggered_abilities
    ps = state.player_by_id(controller_id)
    for arena in (ps.ground_arena, ps.space_arena):
        if victim in arena:
            arena.remove(victim)
            break
    evt = UnitDefeated(player_id=controller_id, instance_id=victim.instance_id,
                       card_name=victim.card_def.display_name)
    state.event_log.append(evt)
    ctx = {"defeated_id": victim.instance_id, "defeated_ci": victim,
           "defeated_controller_id": controller_id}
    return fire_triggered_abilities(state, evt, after_all_player_idx=0, event_ctx=ctx)


def _accept_optional_and_run(state):
    """Accept a pending optional trigger, then run its effect via AutoResolveEffects
    if one is offered.  Returns the resolved state."""
    from swu.engine.actions import (
        legal_actions, apply, AcceptTrigger, AutoResolveEffects,
    )
    accept = next((a for a in legal_actions(state) if isinstance(a, AcceptTrigger)), None)
    assert accept is not None, "expected an optional trigger AcceptTrigger"
    state = apply(state, accept)
    auto = next((a for a in legal_actions(state) if isinstance(a, AutoResolveEffects)), None)
    if auto is not None:
        state = apply(state, auto)
    return state


class TestGeneralKrell_SOR_105:
    def test_SOR_105_draws_when_other_friendly_unit_defeated(self, repo):
        state = _make_state()
        krell = _place(state, "P0", _get_card(repo, "SOR", "105"), "ground")
        victim = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        hand_before = len(state.player_by_id("P0").hand)
        state = _fire_other_unit_defeated(state, victim, "P0")
        state = _accept_optional_and_run(state)
        assert len(state.player_by_id("P0").hand) == hand_before + 1

    def test_SOR_105_not_self_no_trigger_on_own_defeat(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        krell = _place(state, "P0", _get_card(repo, "SOR", "105"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        state = _fire_other_unit_defeated(state, krell, "P0")
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state)), \
            "Krell's own defeat must not trigger 'each OTHER friendly unit'"

    def test_SOR_105_enemy_unit_defeat_no_trigger(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "105"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        state = _fire_other_unit_defeated(state, enemy, "P1")
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state)), \
            "an enemy unit's defeat must not trigger (friendly filter)"


class TestAgentKallus_SOR_115:
    def test_SOR_115_draws_when_unique_unit_defeated(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "115"), "ground")
        unique_enemy = _place(state, "P1", _get_card(repo, "SOR", "135"), "ground")  # unique
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        hand_before = len(state.player_by_id("P0").hand)
        state = _fire_other_unit_defeated(state, unique_enemy, "P1")
        state = _accept_optional_and_run(state)
        assert len(state.player_by_id("P0").hand) == hand_before + 1

    def test_SOR_115_non_unique_defeat_no_trigger(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "115"), "ground")
        plain = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # not unique
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        state = _fire_other_unit_defeated(state, plain, "P1")
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state)), \
            "a non-unique unit's defeat must not trigger"


class TestBlackOne_SOR_147:
    def _hand_of(self, state, repo, owner, n):
        from swu.engine.state import CardInstance, Zone
        ps = state.player_by_id(owner)
        for i in range(n):
            ps.hand.append(CardInstance(
                f"{owner}_h{i}_{uuid.uuid4().hex[:4]}",
                _get_card(repo, "SOR", "128"), owner, Zone.HAND))

    def test_SOR_147_when_played_discards_hand_draws_three(self, repo):
        state = _make_state()
        black_one = _place(state, "P0", _get_card(repo, "SOR", "147"), "space")
        self._hand_of(state, repo, "P0", 2)          # 2 cards to discard
        for _ in range(3):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        disc_before = len(state.player_by_id("P0").discard)
        state = _fire_when_played(state, black_one)
        state = _accept_optional_and_run(state)
        ps = state.player_by_id("P0")
        assert len(ps.hand) == 3, "drew 3 after discarding the whole hand"
        assert len(ps.discard) == disc_before + 2, "the 2 held cards were discarded"

    def test_SOR_147_when_defeated_also_offers(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        black_one = _place(state, "P0", _get_card(repo, "SOR", "147"), "space")
        for _ in range(3):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state = _defeat_and_fire(state, black_one, "P0")
        assert any(isinstance(a, AcceptTrigger) for a in legal_actions(state)), \
            "When Defeated should offer the discard-and-draw"


class TestHeroicSacrifice_SOR_150:
    def test_SOR_150_draws_buffs_attack_and_self_defeats(self, repo):
        from swu.engine.actions import apply, legal_actions, AttackWithUnit
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # power 3
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))  # for "draw a card"
        hand_before = len(state.player_by_id("P0").hand)
        base_before = state.players[1].base_instance.damage
        state, _evt = _play_event_from_hand(state, repo, "SOR", "150")
        # Drew a card, then a granted_attack is pending.
        assert len(state.player_by_id("P0").hand) == hand_before + 1
        assert state.pending_decisions[-1].kind == "granted_attack"
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id and a.defender_id is None)
        state = apply(state, atk)
        # Base took power 3 + 2 = 5, and the attacker defeated itself.
        assert state.players[1].base_instance.damage - base_before == 3 + 2
        assert _find_instance(state, attacker.instance_id) is None, \
            "attacker self-defeats after dealing combat damage"


class TestStarWingScout_SOR_163:
    def test_SOR_163_draws_two_with_initiative(self, repo):
        from swu.engine.actions import legal_actions, apply, AutoResolveEffects
        state = _make_state()
        state.initiative_holder = 0  # P0 has initiative
        scout = _place(state, "P0", _get_card(repo, "SOR", "163"), "space")
        for _ in range(2):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        hand_before = len(state.player_by_id("P0").hand)
        state = _defeat_and_fire(state, scout, "P0")
        auto = next((a for a in legal_actions(state)
                     if isinstance(a, AutoResolveEffects)), None)
        if auto is not None:
            state = apply(state, auto)
        assert len(state.player_by_id("P0").hand) == hand_before + 2

    def test_SOR_163_no_draw_without_initiative(self, repo):
        state = _make_state()
        state.initiative_holder = 1  # P1 has initiative
        scout = _place(state, "P0", _get_card(repo, "SOR", "163"), "space")
        for _ in range(2):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        hand_before = len(state.player_by_id("P0").hand)
        state = _defeat_and_fire(state, scout, "P0")
        assert not state.pending_decisions
        assert len(state.player_by_id("P0").hand) == hand_before


class TestMissionBriefing_SOR_171:
    def test_SOR_171_controller_draws_two(self, repo):
        state = _make_state()
        for _ in range(2):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        # hand delta = +2 drawn - 1 event played
        hand_before = len(state.player_by_id("P0").hand)
        state, _evt = _play_event_from_hand(state, repo, "SOR", "171")
        assert not state.pending_decisions
        assert len(state.player_by_id("P0").hand) == hand_before + 2


class TestForcedSurrender_SOR_175:
    def _fill_opp_hand(self, state, repo, n):
        from swu.engine.state import CardInstance, Zone
        ps = state.player_by_id("P1")
        for i in range(n):
            ps.hand.append(CardInstance(
                f"P1_h{i}_{uuid.uuid4().hex[:4]}",
                _get_card(repo, "SOR", "128"), "P1", Zone.HAND))

    def test_SOR_175_opponent_discards_two_when_base_damaged(self, repo):
        state = _make_state()
        state.game_memory.base_damage_dealt_this_phase["P0"] = 5
        self._fill_opp_hand(state, repo, 3)
        for _ in range(2):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        opp_before = len(state.player_by_id("P1").hand)
        opp_disc_before = len(state.player_by_id("P1").discard)
        state, _evt = _play_event_from_hand(state, repo, "SOR", "175")
        assert len(state.player_by_id("P1").hand) == opp_before - 2
        assert len(state.player_by_id("P1").discard) == opp_disc_before + 2

    def test_SOR_175_no_discard_without_base_damage(self, repo):
        state = _make_state()
        self._fill_opp_hand(state, repo, 3)
        for _ in range(2):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        opp_before = len(state.player_by_id("P1").hand)
        state, _evt = _play_event_from_hand(state, repo, "SOR", "175")
        assert len(state.player_by_id("P1").hand) == opp_before, \
            "no base damaged this phase -> opponent keeps their hand"


# ── Gap-fill: card advantage & disruption (sor-set:07) ────────────────────────

def _resolve_sor_event(state, repo, num, owner="P0"):
    """Resolve an SOR event's ability from the owner's discard (where it sits at
    resolution), returning the event CardInstance.  Mirrors ``_play_aspect_event``
    but generic to any event."""
    from swu.engine.state import CardInstance, Zone
    from swu.engine.actions import _resolve_event_ability
    cdef = _get_card(repo, "SOR", num)
    ci = CardInstance(instance_id=f"{owner}_evt_{uuid.uuid4().hex[:6]}",
                      card_def=cdef, owner_id=owner, zone=Zone.DISCARD)
    ps = state.player_by_id(owner)
    ps.discard.append(ci)
    _resolve_event_ability(state, ps, ci, 1 - state.player_index(owner))
    return ci


class TestJabbaTheHutt_SOR_181:
    def test_SOR_181_trick_event_costs_one_less(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import _play_cost
        state = _make_state()
        ps = state.player_by_id("P0")
        bamboozle = _get_card(repo, "SOR", "199")  # cost-2 Trick event
        evt = CardInstance("P0_b", bamboozle, "P0", Zone.HAND)
        ps.hand.append(evt)
        base_cost = _play_cost(state, evt, ps)
        _place(state, "P0", _get_card(repo, "SOR", "181"), "ground")  # Jabba
        assert _play_cost(state, evt, ps) == base_cost - 1

    def test_SOR_181_non_trick_event_not_discounted(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import _play_cost
        state = _make_state()
        ps = state.player_by_id("P0")
        repair = _get_card(repo, "SOR", "74")  # Supply event (not Trick)
        evt = CardInstance("P0_r", repair, "P0", Zone.HAND)
        ps.hand.append(evt)
        base_cost = _play_cost(state, evt, ps)
        _place(state, "P0", _get_card(repo, "SOR", "181"), "ground")
        assert _play_cost(state, evt, ps) == base_cost

    def test_SOR_181_when_played_searches_and_draws_trick_event(self, repo):
        state = _seed_rng(_make_state())
        jabba = _place(state, "P0", _get_card(repo, "SOR", "181"), "ground")
        # Top 8: a Trick event buried among non-tricks.
        top = [_get_card(repo, "SOR", "46"),   # unit
               _get_card(repo, "SOR", "199"),  # Bamboozle (Trick event)
               _get_card(repo, "SOR", "128"),  # unit
               _get_card(repo, "SOR", "46"),
               _get_card(repo, "SOR", "128")]
        made = _build_search_deck(state, "P0", top)
        trick_ci = made[1]
        state = _fire_when_played(state, jabba)
        assert state.pending_decisions[-1].kind == "deck_search"
        state = _take_from_search(state, trick_ci.instance_id)
        assert any(c.instance_id == trick_ci.instance_id
                   for c in state.player_by_id("P0").hand), "drew the Trick event"


class TestBountyHunterCrew_SOR_183:
    def test_SOR_183_returns_event_from_discard(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, SelectDiscardCard
        state = _make_state()
        crew = _place(state, "P0", _get_card(repo, "SOR", "183"), "ground")
        ps = state.player_by_id("P0")
        event_ci = CardInstance("P0_disc_evt", _get_card(repo, "SOR", "74"),
                                "P0", Zone.DISCARD)
        ps.discard.append(event_ci)
        state = _fire_when_played(state, crew)
        assert state.pending_decisions[-1].kind == "return_from_discard"
        sel = next(a for a in legal_actions(state)
                   if isinstance(a, SelectDiscardCard)
                   and a.instance_id == event_ci.instance_id)
        state = apply(state, sel)
        assert any(c.instance_id == event_ci.instance_id
                   for c in state.player_by_id("P0").hand)

    def test_SOR_183_no_event_in_discard_fizzles(self, repo):
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        crew = _place(state, "P0", _get_card(repo, "SOR", "183"), "ground")
        ps = state.player_by_id("P0")
        # a UNIT in discard is not an event -> no candidate
        ps.discard.append(CardInstance("P0_disc_u", _get_card(repo, "SOR", "46"),
                                       "P0", Zone.DISCARD))
        state = _fire_when_played(state, crew)
        assert not state.pending_decisions, "no event to return -> clean fizzle"


class TestChopper_SOR_188:
    def test_SOR_188_gains_raid_with_another_spectre(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        chopper = _place(state, "P0", _get_card(repo, "SOR", "188"), "ground")
        assert keyword_value(state, chopper, Keyword.RAID) == 0, "no Raid alone"
        _place(state, "P0", _get_card(repo, "SOR", "192"), "ground")  # Ezra (Spectre)
        assert keyword_value(state, chopper, Keyword.RAID) == 1, "Raid 1 with another Spectre"

    def test_SOR_188_on_attack_mills_and_exhausts_on_event(self, repo):
        state = _make_state()
        chopper = _place(state, "P0", _get_card(repo, "SOR", "188"), "ground")
        _give_resources(state, "P1", 2)  # two ready resources
        event_top = _push_deck_top(state, "P1", _get_card(repo, "SOR", "74"))  # event
        disc_before = len(state.player_by_id("P1").discard)
        state = _fire_on_attack(state, chopper)
        p1 = state.player_by_id("P1")
        assert len(p1.discard) == disc_before + 1, "milled the defender's top card"
        assert any(c.instance_id == event_top.instance_id for c in p1.discard)
        assert sum(1 for r in p1.resources if r.exhausted) == 1, \
            "milled an event -> exhaust one of that player's resources"

    def test_SOR_188_on_attack_non_event_no_exhaust(self, repo):
        state = _make_state()
        chopper = _place(state, "P0", _get_card(repo, "SOR", "188"), "ground")
        _give_resources(state, "P1", 2)
        _push_deck_top(state, "P1", _get_card(repo, "SOR", "46"))  # a unit, not an event
        state = _fire_on_attack(state, chopper)
        p1 = state.player_by_id("P1")
        assert sum(1 for r in p1.resources if r.exhausted) == 0, \
            "milled a non-event -> no resource exhausted"


class TestBamboozle_SOR_199:
    def test_SOR_199_exhausts_unit_and_returns_its_upgrades(self, repo):
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        target = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        upgrade = CardInstance("P1_up", _get_card(repo, "SOR", "120"),  # Academy Training
                               "P1", Zone.GROUND_ARENA)
        target.attached_upgrades.append(upgrade)
        _resolve_sor_event(state, repo, "199")
        state = _choose(state, target.instance_id)
        tgt = _find_instance(state, target.instance_id)
        assert tgt is not None and tgt.exhausted, "the chosen unit is exhausted"
        assert not tgt.attached_upgrades, "its upgrade was removed"
        assert any(c.instance_id == upgrade.instance_id
                   for c in state.player_by_id("P1").hand), "upgrade returned to owner's hand"


class TestSparkOfRebellion_SOR_200:
    def test_SOR_200_looks_and_discards_a_card(self, repo):
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        p1 = state.player_by_id("P1")
        for i in range(3):
            p1.hand.append(CardInstance(f"P1_h{i}", _get_card(repo, "SOR", "128"),
                                        "P1", Zone.HAND))
        state, _evt = _play_event_from_hand(state, repo, "SOR", "200")
        assert state.pending_decisions[-1].kind == "look_hand"
        assert len(state.player_by_id("P1").hand) == 2, "one card discarded from opponent's hand"
        assert len(state.player_by_id("P1").discard) == 1


class TestBodhiRook_SOR_201:
    def test_SOR_201_discards_a_non_unit_card(self, repo):
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        bodhi = _place(state, "P0", _get_card(repo, "SOR", "201"), "ground")
        p1 = state.player_by_id("P1")
        unit_card = CardInstance("P1_unit", _get_card(repo, "SOR", "46"), "P1", Zone.HAND)
        event_card = CardInstance("P1_evt", _get_card(repo, "SOR", "74"), "P1", Zone.HAND)
        p1.hand.extend([unit_card, event_card])  # unit first, so a naive first-card would miss
        state = _fire_when_played(state, bodhi)
        remaining = {c.instance_id for c in state.player_by_id("P1").hand}
        assert unit_card.instance_id in remaining, "the unit is NOT discarded"
        assert event_card.instance_id not in remaining, "the non-unit event is discarded"
        assert any(c.instance_id == event_card.instance_id
                   for c in state.player_by_id("P1").discard)

    def test_SOR_201_all_units_nothing_discarded(self, repo):
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        bodhi = _place(state, "P0", _get_card(repo, "SOR", "201"), "ground")
        p1 = state.player_by_id("P1")
        p1.hand.append(CardInstance("P1_u", _get_card(repo, "SOR", "46"), "P1", Zone.HAND))
        state = _fire_when_played(state, bodhi)
        assert len(state.player_by_id("P1").hand) == 1, "no non-unit to discard"


class TestIHadNoChoice_SOR_187:
    def _select(self, state, cls_name, instance_id=None):
        from swu.engine.actions import legal_actions, apply
        act = next(a for a in legal_actions(state)
                   if type(a).__name__ == cls_name
                   and (instance_id is None or getattr(a, "instance_id", None) == instance_id))
        return apply(state, act)

    def test_SOR_187_opponent_splits_two_chosen_units(self, repo):
        state = _make_state()
        u1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        u2 = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        _resolve_sor_event(state, repo, "187")
        top = state.pending_decisions[-1]
        assert top.kind == "opponent_split_bounce" and top.deciding_player_id == "P0"
        state = self._select(state, "SelectSplitBounceUnit", u1.instance_id)
        state = self._select(state, "SelectSplitBounceUnit", u2.instance_id)
        # Picking the 2nd auto-advances to the opponent's split stage.
        top = state.pending_decisions[-1]
        assert top.context["stage"] == "split" and top.deciding_player_id == "P1"
        state = self._select(state, "ChooseSplitReturn", u1.instance_id)
        assert not state.pending_decisions
        p1 = state.player_by_id("P1")
        assert any(c.instance_id == u1.instance_id for c in p1.hand), "u1 returned to hand"
        assert p1.deck and p1.deck[-1].instance_id == u2.instance_id, "u2 bottomed"
        assert _find_instance(state, u1.instance_id) is None
        assert _find_instance(state, u2.instance_id) is None

    def test_SOR_187_choosing_one_just_returns_it(self, repo):
        state = _make_state()
        u1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _resolve_sor_event(state, repo, "187")
        state = self._select(state, "SelectSplitBounceUnit", u1.instance_id)
        state = self._select(state, "FinishSplitBounce")
        assert not state.pending_decisions, "no opponent split when only 1 chosen"
        assert any(c.instance_id == u1.instance_id
                   for c in state.player_by_id("P1").hand), "the single unit returns to hand"

    def test_SOR_187_no_units_fizzles(self, repo):
        state = _make_state()  # bases only, no arena units
        _resolve_sor_event(state, repo, "187")
        assert not state.pending_decisions, "no non-leader units -> clean fizzle"


# ── Gap-fill: card advantage & disruption (sor-set:08) ────────────────────────

class TestCantinaBouncer_SOR_202:
    def test_SOR_202_returns_a_non_leader_unit_to_hand(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        state = _make_state()
        bouncer = _place(state, "P0", _get_card(repo, "SOR", "202"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, bouncer)
        accept = next((a for a in legal_actions(state) if isinstance(a, AcceptTrigger)), None)
        if accept is not None:
            state = apply(state, accept)
        state = _choose(state, enemy.instance_id)
        assert _find_instance(state, enemy.instance_id) is None
        assert any(c.instance_id == enemy.instance_id
                   for c in state.player_by_id("P1").hand), "returned to owner's hand"

    def test_SOR_202_optional_declines_cleanly(self, repo):
        state = _make_state()  # no other units in play besides the bouncer
        bouncer = _place(state, "P0", _get_card(repo, "SOR", "202"), "ground")
        # Only the bouncer itself is a non-leader unit; it can target itself, but the
        # trigger is optional, so a decline is always available.
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _fire_when_played(state, bouncer)
        decline = next((a for a in legal_actions(state) if isinstance(a, DeclineTrigger)), None)
        if decline is not None:
            state = apply(state, decline)
        assert not state.pending_decisions


class TestMiningGuildTIEFighter_SOR_206:
    def test_SOR_206_pay_two_draw_one(self, repo):
        state = _make_state()
        tie = _place(state, "P0", _get_card(repo, "SOR", "206"), "space")
        _give_resources(state, "P0", 3)
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        hand_before = len(state.player_by_id("P0").hand)
        state = _fire_on_attack(state, tie)
        state = _accept_optional_and_run(state)
        ps = state.player_by_id("P0")
        assert len(ps.hand) == hand_before + 1, "drew a card"
        assert sum(1 for r in ps.resources if r.exhausted) == 2, "paid 2 resources"

    def test_SOR_206_not_offered_without_two_resources(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        tie = _place(state, "P0", _get_card(repo, "SOR", "206"), "space")
        _give_resources(state, "P0", 1)  # only one ready resource
        state = _fire_on_attack(state, tie)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state)), \
            "the pay-2 trigger is gated off when fewer than 2 resources are ready"


class TestPiratedStarfighter_SOR_209:
    def test_SOR_209_returns_a_friendly_non_leader_unit(self, repo):
        state = _make_state()
        star = _place(state, "P0", _get_card(repo, "SOR", "209"), "space")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, star)
        state = _choose(state, friend.instance_id)
        assert _find_instance(state, friend.instance_id) is None
        assert any(c.instance_id == friend.instance_id
                   for c in state.player_by_id("P0").hand), "friendly unit returned"


class TestYoureMyOnlyHope_SOR_246:
    def test_SOR_246_may_play_top_card_with_discount(self, repo):
        state = _make_state()
        top = _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))  # a unit
        _give_resources(state, "P0", 10)
        _resolve_sor_event(state, repo, "246")
        dec = state.pending_decisions[-1]
        assert dec.kind == "peek_top" and dec.context["mode"] == "may_play"
        assert dec.context["cost_reduction"] == 5 and dec.context["free"] is False
        from swu.engine.actions import legal_actions, apply, PlayTopCard
        play = next(a for a in legal_actions(state) if isinstance(a, PlayTopCard))
        state = apply(state, play)
        assert _find_instance(state, top.instance_id) is not None, "top card entered play"

    def test_SOR_246_free_when_base_low(self, repo):
        state = _make_state()
        base = state.player_by_id("P0").base_instance
        base.damage = base.card_def.hp - 5  # exactly 5 remaining HP
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        _resolve_sor_event(state, repo, "246")
        dec = state.pending_decisions[-1]
        assert dec.context["free"] is True, "free play when base has <=5 remaining HP"

    def test_SOR_246_may_leave_on_top(self, repo):
        state = _make_state()
        top = _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        _give_resources(state, "P0", 10)
        _resolve_sor_event(state, repo, "246")
        from swu.engine.actions import legal_actions, apply, KeepTopCard
        keep = next(a for a in legal_actions(state) if isinstance(a, KeepTopCard))
        state = apply(state, keep)
        assert not state.pending_decisions
        assert state.player_by_id("P0").deck[0].instance_id == top.instance_id, \
            "declined -> card stays on top"


class TestRestock_SOR_252:
    def test_SOR_252_bottoms_chosen_discard_cards(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import (
            legal_actions, apply, SelectBottomDiscardCard, FinishBottomFromDiscard)
        state = _make_state()
        p1 = state.player_by_id("P1")
        c1 = CardInstance("P1_d1", _get_card(repo, "SOR", "128"), "P1", Zone.DISCARD)
        c2 = CardInstance("P1_d2", _get_card(repo, "SOR", "46"), "P1", Zone.DISCARD)
        p1.discard.extend([c1, c2])
        _resolve_sor_event(state, repo, "252")
        assert state.pending_decisions[-1].kind == "bottom_from_discard"
        sel = next(a for a in legal_actions(state)
                   if isinstance(a, SelectBottomDiscardCard)
                   and a.instance_id == c1.instance_id)
        state = apply(state, sel)
        fin = next(a for a in legal_actions(state)
                   if isinstance(a, FinishBottomFromDiscard))
        state = apply(state, fin)
        p1 = state.player_by_id("P1")
        assert not any(c.instance_id == c1.instance_id for c in p1.discard)
        assert p1.deck and p1.deck[-1].instance_id == c1.instance_id, "bottomed into owner's deck"
        assert any(c.instance_id == c2.instance_id for c in p1.discard), "unchosen card stays"

    def test_SOR_252_no_discard_fizzles(self, repo):
        from swu.engine.actions import push_bottom_from_discard
        state = _make_state()
        src = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        push_bottom_from_discard(state, src, count=4)  # both discards empty
        assert not state.pending_decisions, "no discard cards -> clean fizzle"


# ── Gap campaign sor-set:09 — leaders SOR_1..SOR_9 ────────────────────────────

def _get_leader(repo, set_code, num):
    """Hydrate the LEADER-typed row for (set, num).  Low leader numbers collide with
    a same-numbered Token (e.g. SOR_2 = Shield token + Iden Versio); the plain
    ``_get_card`` fetchone can return the token, so leader tests fetch by type."""
    with repo._con() as con:
        row = con.execute(
            "SELECT * FROM cards WHERE set_code=? AND card_number=? AND type='Leader'",
            (set_code, str(int(num))),
        ).fetchone()
        from tests.dbpath import require_row
        return repo._hydrate(con, require_row(row, f"leader {set_code}_{num}"))


def _place_deployed_leader(state, owner_id, leader_def, arena="ground"):
    """Place a leader as a DEPLOYED unit (ready) in an arena."""
    ci = _place(state, owner_id, leader_def, arena)
    ci.deployed = True
    ci.exhausted = False
    return ci


def _place_hand(state, owner_id, card_def):
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(
        instance_id=f"{owner_id}_hand_{uuid.uuid4().hex[:6]}",
        card_def=card_def, owner_id=owner_id, zone=Zone.HAND,
    )
    state.player_by_id(owner_id).hand.append(ci)
    return ci


class TestDirectorKrennicLeaderSOR1:
    """SOR_1 - Constant: Each friendly damaged unit gets +1/+0."""

    def test_SOR_1_damaged_friendly_unit_gets_plus_1_power(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        _place_deployed_leader(state, "P0", _get_leader(repo, "SOR", "1"))
        unit = _place(state, "P0", _get_card(repo, "SOR", "108"), "ground")
        base = compute_power(state, unit)
        unit.damage = 1
        assert compute_power(state, unit) == base + 1, "damaged friendly unit +1/+0"

    def test_SOR_1_undamaged_and_enemy_units_unaffected(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        _place_deployed_leader(state, "P0", _get_leader(repo, "SOR", "1"))
        friendly = _place(state, "P0", _get_card(repo, "SOR", "108"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "108"), "ground")
        enemy.damage = 2
        assert compute_power(state, friendly) == friendly.card_def.power, "undamaged: no buff"
        assert compute_power(state, enemy) == enemy.card_def.power, "enemy damaged unit: no buff"


class TestIdenVersioLeaderSOR2:
    """SOR_2 - undeployed heal gated on an enemy defeat this phase; deployed
    When-an-enemy-unit-is-defeated heal."""

    def _iden_uses(self, state, iden_ci):
        from swu.engine.actions import legal_actions, UseAbility
        return [a for a in legal_actions(state)
                if isinstance(a, UseAbility) and a.source_id == iden_ci.instance_id]

    def test_SOR_2_undeployed_heal_gated_on_enemy_defeat(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        state.players[0].base_zone[0].damage = 3
        iden_ci = _place_leader(state, "P0", _get_leader(repo, "SOR", "2"))
        _give_resources(state, "P0", 3)
        # No enemy unit defeated this phase -> the action is not offered.
        assert self._iden_uses(state, iden_ci) == [], "gated out until an enemy is defeated"
        # Record an enemy unit's defeat this phase -> now offered, and it heals 1.
        state.game_memory.defeated_controllers_this_round.append("P1")
        use = self._iden_uses(state, iden_ci)[0]
        state = apply(state, use)
        assert not state.pending_decisions
        assert state.players[0].base_zone[0].damage == 2, "healed 1 from own base"

    def test_SOR_2_deployed_heals_when_enemy_unit_defeated(self, repo):
        from swu.engine.actions import _sweep_defeated_units
        state = _make_state()
        state.players[0].base_zone[0].damage = 3
        _place_deployed_leader(state, "P0", _get_leader(repo, "SOR", "2"))
        enemy = _place(state, "P1", _get_card(repo, "SOR", "108"), "ground")
        enemy.damage = 99  # lethal → the real defeat path fires WhenUnitDefeated
        _sweep_defeated_units(state)
        assert _find_instance(state, enemy.instance_id) is None, "enemy was defeated"
        assert state.players[0].base_zone[0].damage == 2, "deployed Iden heals 1 on enemy defeat"


class TestChewbaccaLeaderSOR3:
    """SOR_3 - undeployed Action [exhaust]: Play a unit costing 3 or less from hand;
    it gains Sentinel for this phase."""

    def test_SOR_3_plays_cheap_unit_that_gains_sentinel(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, PlayFromHand
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        chewie_ci = _place_leader(state, "P0", _get_leader(repo, "SOR", "3"))
        _give_resources(state, "P0", 5)
        hand_unit = _place_hand(state, "P0", _get_card(repo, "SOR", "108"))  # cost 1, no Sentinel
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == chewie_ci.instance_id)
        state = apply(state, use)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand) and a.instance_id == hand_unit.instance_id)
        state = apply(state, play)
        in_play = _find_instance(state, hand_unit.instance_id)
        assert in_play is not None, "the hand unit entered play"
        assert has_keyword(state, in_play, Keyword.SENTINEL), "played unit gains Sentinel this phase"


class TestChirrutImweLeaderSOR4:
    """SOR_4 - undeployed +0/+2 buff; deployed 'isn't defeated by no remaining HP'
    during the action phase (defeated in regroup)."""

    def test_SOR_4_undeployed_gives_plus_0_2_this_phase(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget, compute_hp
        state = _make_state()
        chirrut_ci = _place_leader(state, "P0", _get_leader(repo, "SOR", "4"))
        unit = _place(state, "P0", _get_card(repo, "SOR", "108"), "ground")
        base_hp = compute_hp(state, unit)
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == chirrut_ci.instance_id)
        state = apply(state, use)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == unit.instance_id)
        state = apply(state, choose)
        assert compute_hp(state, _find_instance(state, unit.instance_id)) == base_hp + 2

    def test_SOR_4_survives_zero_hp_in_action_defeated_in_regroup(self, repo):
        from swu.engine.actions import _sweep_defeated_units, _hp_defeat_prevented
        from swu.engine.state import Phase
        state = _make_state()
        chirrut_ci = _place_deployed_leader(state, "P0", _get_leader(repo, "SOR", "4"))
        chirrut_ci.damage = 99  # well past its HP
        # ACTION phase: protected - the sweep does not defeat him.
        assert _hp_defeat_prevented(state, chirrut_ci)
        _sweep_defeated_units(state)
        assert _find_instance(state, chirrut_ci.instance_id) is not None, "survives in action phase"
        # REGROUP: the protection drops and the sweep defeats him.
        state.phase = Phase.REGROUP
        assert not _hp_defeat_prevented(state, chirrut_ci)
        _sweep_defeated_units(state)
        assert _find_instance(state, chirrut_ci.instance_id) is None, "defeated in regroup"


class TestGrandMoffTarkinLeaderSOR7:
    """SOR_7 - undeployed Action [1 resource, exhaust]: give an Experience token to
    an Imperial unit."""

    def test_SOR_7_gives_experience_to_imperial_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget
        state = _make_state()
        tarkin_ci = _place_leader(state, "P0", _get_leader(repo, "SOR", "7"))
        _give_resources(state, "P0", 3)
        imperial = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # Imperial
        non_imp = _place(state, "P0", _get_card(repo, "SOR", "140"), "ground")   # Rebel
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == tarkin_ci.instance_id)
        state = apply(state, use)
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert imperial.instance_id in offered and non_imp.instance_id not in offered, (
            "only Imperial units may receive the token")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget) and a.target_id == imperial.instance_id))
        assert _experience_count(_find_instance(state, imperial.instance_id)) == 1


class TestHeraSyndullaLeaderSOR8:
    """SOR_8 - deployed On Attack: you may give an Experience token to another unique
    unit.  (The Spectre aspect-penalty waiver is a documented residual.)"""

    def test_SOR_8_on_attack_targets_only_unique_units(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        hera_ci = _place_deployed_leader(state, "P0", _get_leader(repo, "SOR", "8"))
        unique_unit = _place(state, "P0", _get_card(repo, "SOR", "109"), "ground")  # unique
        non_unique = _place(state, "P0", _get_card(repo, "SOR", "108"), "ground")   # non-unique
        state = _fire_on_attack(state, hera_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert unique_unit.instance_id in offered, "a unique unit is targetable"
        assert non_unique.instance_id not in offered, "a non-unique unit is not"
        assert hera_ci.instance_id not in offered, "not another == excludes Hera herself"


class TestLeiaOrganaLeaderSOR9:
    """SOR_9 - undeployed Action [exhaust]: attack with a Rebel unit (then may attack
    with another)."""

    def test_SOR_9_undeployed_offers_only_rebel_attackers(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, AttackWithUnit
        state = _make_state()
        leia_ci = _place_leader(state, "P0", _get_leader(repo, "SOR", "9"))
        rebel1 = _place(state, "P0", _get_card(repo, "SOR", "140"), "ground")  # Rebel
        rebel2 = _place(state, "P0", _get_card(repo, "SOR", "143"), "ground")  # Rebel
        non_rebel = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # Imperial
        for u in (rebel1, rebel2, non_rebel):
            u.exhausted = False
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == leia_ci.instance_id)
        state = apply(state, use)
        attackers = {a.attacker_id for a in legal_actions(state) if isinstance(a, AttackWithUnit)}
        assert attackers == {rebel1.instance_id, rebel2.instance_id}, (
            "only friendly Rebel units may be the granted attacker")


# ── Gap-filling campaign: sor-set groups 10–12 (combat tricks, buffs & tempo) ──

def _place_deployed_leader(state, owner_id, leader_def, arena="ground"):
    """Place a leader directly into an arena as a deployed (ready) leader."""
    ci = _place(state, owner_id, leader_def, arena)
    ci.deployed = True
    ci.exhausted = False
    return ci


def _hand(state, owner_id, card_def, iid=None):
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(
        instance_id=iid or f"{owner_id}_h_{uuid.uuid4().hex[:6]}",
        card_def=card_def, owner_id=owner_id, zone=Zone.HAND,
    )
    state.player_by_id(owner_id).hand.append(ci)
    return ci


def _set_base(state, owner_id, base_def):
    """Replace the player's placeholder base with a real Base card def (so its
    Epic Action is registered)."""
    from swu.engine.state import CardInstance, Zone
    ps = state.player_by_id(owner_id)
    ps.base_zone = [c for c in ps.base_zone
                    if getattr(c.card_def, "type", None) != "Base"]
    ci = CardInstance(instance_id=f"{owner_id}_base_real", card_def=base_def,
                      owner_id=owner_id, zone=Zone.BASE_ZONE)
    ps.base_zone.insert(0, ci)
    return ci


class TestIG88SOR12:
    def test_SOR_12_deployed_grants_raid_1_to_others(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        _place_deployed_leader(state, "P0", _get_card(repo, "SOR", "12"))
        ally = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")
        assert has_keyword(state, ally, Keyword.RAID)
        assert keyword_value(state, ally, Keyword.RAID) == 1

    def test_SOR_12_undeployed_bonus_when_more_units(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility
        state = _make_state()
        ig = _place_leader(state, "P0", _get_card(repo, "SOR", "12"))
        _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == ig.instance_id)
        state = apply(state, use)
        top = state.pending_decisions[-1]
        assert top.kind == "granted_attack"
        assert top.context["power_bonus"] == 1


class TestBobaFettSOR15:
    def test_SOR_15_undeployed_ready_resource_on_enemy_defeat(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, AutoResolveEffects
        state = _make_state()
        _place_leader(state, "P0", _get_card(repo, "SOR", "15"))
        _give_resources(state, "P0", 2)
        for r in state.player_by_id("P0").resources:
            r.exhausted = True
        enemy = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")
        state = _fire_when_defeated(state, enemy)   # observer: enemy stays in arena
        acc = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, acc)
        auto = next((a for a in legal_actions(state) if isinstance(a, AutoResolveEffects)), None)
        if auto:
            state = apply(state, auto)
        assert state.player_by_id("P0").available_resources == 1
        assert state.player_by_id("P0").leader_instance.exhausted

    def test_SOR_15_deployed_ready_two_after_attack_defeats_enemy(self, repo):
        from swu.engine.actions import apply, AttackWithUnit
        state = _make_state()
        boba = _place_deployed_leader(state, "P0", _get_card(repo, "SOR", "15"))
        _give_resources(state, "P0", 3)
        for r in state.player_by_id("P0").resources:
            r.exhausted = True
        enemy = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")  # 3/3, dies to Boba 4
        state = apply(state, AttackWithUnit(boba.instance_id, enemy.instance_id))
        assert state.player_by_id("P0").available_resources == 2


class TestGrandAdmiralThrawnSOR16:
    def test_SOR_16_reveal_and_exhaust_enemy_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility
        state = _make_state()
        thrawn = _place_leader(state, "P0", _get_card(repo, "SOR", "16"))
        _give_resources(state, "P0", 3)
        _push_deck_top(state, "P1", _get_card(repo, "SOR", "51"))   # Luke, cost 7
        enemy = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")  # cost 2 ≤ 7
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == thrawn.instance_id)
        state = apply(state, use)
        assert _find_instance(state, enemy.instance_id).exhausted


class TestJynErsoSOR18:
    def test_SOR_18_undeployed_defender_debuff(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, AttackWithUnit
        state = _make_state()
        jyn = _place_leader(state, "P0", _get_card(repo, "SOR", "18"))
        attacker = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")  # 3/3
        defender = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")  # 3/3
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == jyn.instance_id)
        state = apply(state, use)
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id
                   and a.defender_id == defender.instance_id)
        state = apply(state, atk)
        surviving = _find_instance(state, attacker.instance_id)
        # defender was debuffed to power 2, so the attacker took 2 (not 3)
        assert surviving is not None and surviving.damage == 2

    def test_SOR_18_deployed_defender_debuff(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        _place_deployed_leader(state, "P0", _get_card(repo, "SOR", "18"))
        enemy = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")
        base = compute_power(state, enemy)
        assert compute_power(state, enemy, is_defending=True) == base - 1
        assert compute_power(state, enemy) == base   # only while defending
        friendly = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")
        assert compute_power(state, friendly, is_defending=True) == compute_power(state, friendly)


class TestSecurityComplexSOR19:
    def test_SOR_19_epic_shield_nonleader(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget
        state = _make_state()
        base = _set_base(state, "P0", _get_card(repo, "SOR", "19"))
        unit = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == base.instance_id)
        state = apply(state, use)
        ch = [a for a in legal_actions(state) if isinstance(a, ChooseTarget)]
        if ch:
            state = apply(state, next(a for a in ch if a.target_id == unit.instance_id))
        assert _shield_count(_find_instance(state, unit.instance_id)) == 1


class TestJedhaCitySOR28:
    def test_SOR_28_epic_debuff_nonleader(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget, compute_power
        state = _make_state()
        base = _set_base(state, "P0", _get_card(repo, "SOR", "28"))
        unit = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")  # 3 power
        p = compute_power(state, unit)
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == base.instance_id)
        state = apply(state, use)
        ch = [a for a in legal_actions(state) if isinstance(a, ChooseTarget)]
        if ch:
            state = apply(state, next(a for a in ch if a.target_id == unit.instance_id))
        assert compute_power(state, _find_instance(state, unit.instance_id)) == max(0, p - 4)


class TestLieutenantChildsenSOR35:
    def test_SOR_35_experience_per_vigilance_in_hand(self, repo):
        state = _make_state()
        childsen = _place(state, "P0", _get_card(repo, "SOR", "35"), "ground")
        _hand(state, "P0", _get_card(repo, "SOR", "59"))   # Vigilance
        _hand(state, "P0", _get_card(repo, "SOR", "59"))   # Vigilance
        _hand(state, "P0", _get_card(repo, "SOR", "95"))   # not Vigilance
        state = _fire_when_played(state, childsen)
        assert _experience_count(_find_instance(state, childsen.instance_id)) == 2


class TestGideonHaskSOR36:
    def test_SOR_36_experience_on_enemy_defeat(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "36"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")
        state = _fire_when_defeated(state, enemy)   # observer: enemy stays in arena
        ch = [a for a in legal_actions(state) if isinstance(a, ChooseTarget)]
        assert ch, "should offer a friendly unit to receive Experience"
        state = apply(state, next((a for a in ch if a.target_id == ally.instance_id), ch[0]))
        assert _experience_count(_find_instance(state, ally.instance_id)) == 1


class TestAcademyDefenseWalkerSOR37:
    def test_SOR_37_experience_each_damaged_friendly(self, repo):
        state = _make_state()
        dmg = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")
        dmg.damage = 1
        undmg = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")
        walker = _place(state, "P0", _get_card(repo, "SOR", "37"), "ground")
        state = _fire_when_played(state, walker)
        assert _experience_count(_find_instance(state, dmg.instance_id)) == 1
        assert _experience_count(_find_instance(state, undmg.instance_id)) == 0


class TestATATSuppressorSOR39:
    def test_SOR_39_exhausts_all_ground_units(self, repo):
        state = _make_state()
        a = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")
        a.exhausted = False
        b = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")
        b.exhausted = False
        sp = _place(state, "P0", _get_card(repo, "SOR", "51"), "space")
        sp.exhausted = False
        atat = _place(state, "P0", _get_card(repo, "SOR", "39"), "ground")
        state = _fire_when_played(state, atat)
        assert _find_instance(state, a.instance_id).exhausted
        assert _find_instance(state, b.instance_id).exhausted
        assert not _find_instance(state, sp.instance_id).exhausted


class TestKananJarrusSOR47:
    def test_SOR_47_mill_and_heal_base(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, AutoResolveEffects
        state = _make_state()
        kanan = _place(state, "P0", _get_card(repo, "SOR", "47"), "ground")   # 1 Spectre
        state.player_by_id("P0").base_zone[0].damage = 5
        _push_deck_top(state, "P1", _get_card(repo, "SOR", "95"))   # under
        _push_deck_top(state, "P1", _get_card(repo, "SOR", "59"))   # top (Vigilance)
        state = _fire_on_attack(state, kanan)
        acc = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, acc)
        auto = next((a for a in legal_actions(state) if isinstance(a, AutoResolveEffects)), None)
        if auto:
            state = apply(state, auto)
        assert state.player_by_id("P0").base_zone[0].damage == 4   # 1 distinct aspect healed
        assert len(state.player_by_id("P1").discard) == 1


class TestTheGhostSOR50:
    def test_SOR_50_shield_another_spectre_on_play(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        other = _place(state, "P0", _get_card(repo, "SOR", "47"), "ground")   # Kanan, Spectre
        ghost = _place(state, "P0", _get_card(repo, "SOR", "50"), "ground")
        state = _fire_when_played(state, ghost)
        acc = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, acc)
        ch = [a for a in legal_actions(state) if isinstance(a, ChooseTarget)]
        if ch:
            state = apply(state, next(a for a in ch if a.target_id == other.instance_id))
        assert _shield_count(_find_instance(state, other.instance_id)) == 1


class TestTheForceIsWithMeSOR55:
    def test_SOR_55_experience_shield_and_attack(self, repo):
        from swu.engine.actions import (legal_actions, apply, PlayCard, ChooseTarget,
                                         DeclineGrantedAttack)
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "51"), "ground")   # Luke, Force unit
        chosen = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")
        ev = _hand(state, "P0", _get_card(repo, "SOR", "55"), iid="p0_fiwm")
        _give_resources(state, "P0", 10)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == "p0_fiwm")
        state = apply(state, play)
        ch = [a for a in legal_actions(state) if isinstance(a, ChooseTarget)]
        state = apply(state, next(a for a in ch if a.target_id == chosen.instance_id))
        # A granted_attack (may attack the chosen unit) is now pending — decline it.
        dec = [a for a in legal_actions(state) if isinstance(a, DeclineGrantedAttack)]
        if dec:
            state = apply(state, dec[0])
        now = state.find_instance(chosen.instance_id)[1]
        assert _experience_count(now) == 2
        assert _shield_count(now) == 1   # controls a Force unit


class TestProtectorSOR57:
    def test_SOR_57_grants_sentinel_to_host(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")
        up = CardInstance(instance_id="p0_prot", card_def=_get_card(repo, "SOR", "57"),
                          owner_id="P0", zone=Zone.GROUND_ARENA)
        host.attached_upgrades.append(up)
        assert has_keyword(state, host, Keyword.SENTINEL)


class TestDistantPatrollerSOR60:
    def test_SOR_60_shield_vigilance_on_defeat(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        vig = _place(state, "P0", _get_card(repo, "SOR", "59"), "ground")   # Vigilance
        patroller = _place(state, "P0", _get_card(repo, "SOR", "60"), "ground")
        state = _defeat_and_fire(state, patroller, "P0")
        acc = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, acc)
        ch = [a for a in legal_actions(state) if isinstance(a, ChooseTarget)]
        if ch:
            state = apply(state, next(a for a in ch if a.target_id == vig.instance_id))
        assert _shield_count(_find_instance(state, vig.instance_id)) == 1


class TestBazeMalbusSOR65:
    def test_SOR_65_conditional_sentinel_with_initiative(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        baze = _place(state, "P0", _get_card(repo, "SOR", "65"), "ground")
        assert has_keyword(state, baze, Keyword.SENTINEL)      # P0 holds initiative
        state.initiative_holder = 1
        assert not has_keyword(state, baze, Keyword.SENTINEL)  # no initiative → no Sentinel
        assert "Sentinel" not in baze.card_def.keywords         # printed bar stripped


class TestCargoJuggernautSOR68:
    def test_SOR_68_heal_base_if_another_vigilance(self, repo):
        state = _make_state()
        state.player_by_id("P0").base_zone[0].damage = 5
        _place(state, "P0", _get_card(repo, "SOR", "59"), "ground")   # another Vigilance
        cargo = _place(state, "P0", _get_card(repo, "SOR", "68"), "ground")
        state = _fire_when_played(state, cargo)
        assert state.player_by_id("P0").base_zone[0].damage == 1

    def test_SOR_68_no_heal_without_another_vigilance(self, repo):
        state = _make_state()
        state.player_by_id("P0").base_zone[0].damage = 5
        cargo = _place(state, "P0", _get_card(repo, "SOR", "68"), "ground")
        state = _fire_when_played(state, cargo)
        assert state.player_by_id("P0").base_zone[0].damage == 5


class TestDevotionSOR70:
    def test_SOR_70_grants_restore_2_to_host(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")
        up = CardInstance(instance_id="p0_dev", card_def=_get_card(repo, "SOR", "70"),
                          owner_id="P0", zone=Zone.GROUND_ARENA)
        host.attached_upgrades.append(up)
        assert has_keyword(state, host, Keyword.RESTORE)
        assert keyword_value(state, host, Keyword.RESTORE) == 2


class TestMomentOfPeaceSOR73:
    def test_SOR_73_shield_a_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayCard, ChooseTarget
        state = _make_state()
        unit = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")
        _hand(state, "P0", _get_card(repo, "SOR", "73"), iid="p0_peace")
        _give_resources(state, "P0", 10)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == "p0_peace")
        state = apply(state, play)
        ch = [a for a in legal_actions(state) if isinstance(a, ChooseTarget)]
        if ch:
            state = apply(state, next(a for a in ch if a.target_id == unit.instance_id))
        assert _shield_count(_find_instance(state, unit.instance_id)) == 1


class TestMakeAnOpeningSOR76:
    def test_SOR_76_debuff_and_heal(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayCard, ChooseTarget, compute_power
        state = _make_state()
        state.player_by_id("P0").base_zone[0].damage = 5
        enemy = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")   # 3 power
        _hand(state, "P0", _get_card(repo, "SOR", "76"), iid="p0_open")
        _give_resources(state, "P0", 10)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayCard) and a.instance_id == "p0_open")
        state = apply(state, play)
        ch = [a for a in legal_actions(state) if isinstance(a, ChooseTarget)]
        if ch:
            state = apply(state, next(a for a in ch if a.target_id == enemy.instance_id))
        assert compute_power(state, _find_instance(state, enemy.instance_id)) == 1   # 3-2
        assert state.player_by_id("P0").base_zone[0].damage == 3   # healed 2


class TestGeneralTaggeSOR80:
    def test_SOR_80_experience_up_to_3_troopers(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectTokenTarget
        state = _make_state()
        tagge = _place(state, "P0", _get_card(repo, "SOR", "80"), "ground")   # Official
        t1 = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")      # Trooper
        t2 = _place(state, "P0", _get_card(repo, "SOR", "36"), "ground")      # Trooper
        state = _fire_when_played(state, tagge)
        assert state.pending_decisions[-1].kind == "select_token"
        for tid in (t1.instance_id, t2.instance_id):
            act = next(a for a in legal_actions(state)
                       if isinstance(a, SelectTokenTarget) and a.target_id == tid)
            state = apply(state, act)
        assert _experience_count(_find_instance(state, t1.instance_id)) == 1
        assert _experience_count(_find_instance(state, t2.instance_id)) == 1


# ══════════════════════════════════════════════════════════════════════════════
# Gap-filling campaign — sor-set groups 13, 14, 15 (combat tricks, buffs & tempo)
# ══════════════════════════════════════════════════════════════════════════════

def _mk_unit(name, power=1, hp=1, traits=(), aspects=(), cost=1, keywords=()):
    """Fabricate a minimal Unit card_def with the given traits/aspects."""
    from swu.cards.models import Unit, AspectPip
    asp = tuple(AspectPip(position=i, name=a, color="", is_duplicate=False)
                for i, a in enumerate(aspects))
    return Unit(
        id=abs(hash(name)) % 99999, card_uid=None, set_code="TST", set_name="T",
        card_number="U", name=name, subtitle=None, type="Unit", rarity="Common",
        is_unique=False, artist=None, text=None, text_styled=None, rules=None,
        rules_styled=None, aspects=asp, keywords=tuple(keywords),
        traits=tuple(traits), arenas=("Ground",), image_front_url=None,
        image_back_url=None, image_front_path=None, image_back_path=None,
        cost=cost, power=power, hp=hp,
    )


class TestEmperorsRoyalGuard:
    def test_SOR_82_sentinel_only_while_controlling_official(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        guard_ci = _place(state, "P0", _get_card(repo, "SOR", "82"), "ground")
        assert not has_keyword(state, guard_ci, Keyword.SENTINEL)
        _place(state, "P0", _mk_unit("Officer", traits=("Official",)), "ground")
        assert has_keyword(state, guard_ci, Keyword.SENTINEL)

    def test_SOR_82_hp_buff_only_while_controlling_palpatine(self, repo):
        from swu.engine.actions import compute_hp
        state = _make_state()
        guard_ci = _place(state, "P0", _get_card(repo, "SOR", "82"), "ground")
        assert compute_hp(state, guard_ci) == 4
        _place(state, "P0", _mk_unit("Emperor Palpatine"), "ground")
        assert compute_hp(state, guard_ci) == 5


class TestBailOrgana:
    def test_SOR_94_gives_experience_to_another_friendly(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget
        state = _make_state()
        bail_ci = _place(state, "P0", _get_card(repo, "SOR", "94"), "ground")
        friend_ci = _place(state, "P0", _mk_unit("Friend"), "ground")
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == bail_ci.instance_id)
        state = apply(state, use)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == friend_ci.instance_id)
        state = apply(state, choose)
        assert _experience_count(_find_instance(state, friend_ci.instance_id)) == 1
        assert _find_instance(state, bail_ci.instance_id).exhausted


class TestWedgeAntilles:
    def test_SOR_100_buffs_and_grants_ambush_to_vehicles(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "100"), "ground")
        veh_ci = _place(state, "P0", _mk_unit("Speeder", power=2, hp=2,
                                              traits=("Vehicle",)), "ground")
        non_ci = _place(state, "P0", _mk_unit("Trooper", power=2, hp=2,
                                              traits=("Trooper",)), "ground")
        assert compute_power(state, veh_ci) == 3 and compute_hp(state, veh_ci) == 3
        assert has_keyword(state, veh_ci, Keyword.AMBUSH)
        assert compute_power(state, non_ci) == 2
        assert not has_keyword(state, non_ci, Keyword.AMBUSH)


class TestAttackPatternDelta:
    def test_SOR_106_buffs_three_distinct_units(self, repo):
        from swu.engine.actions import (apply, PlayCard, legal_actions,
                                        ChooseTarget, compute_power)
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        card = _get_card(repo, "SOR", "106")
        ci = CardInstance("p0_apd", card, "P0", Zone.HAND)
        state.players[0].hand.append(ci)
        _give_resources(state, "P0", 12)
        a = _place(state, "P0", _mk_unit("A", power=1), "ground")
        b = _place(state, "P0", _mk_unit("B", power=1), "ground")
        c = _place(state, "P0", _mk_unit("C", power=1), "ground")
        state = apply(state, PlayCard(ci.instance_id))
        # First buff: choose A.
        state = apply(state, next(x for x in legal_actions(state)
                                  if isinstance(x, ChooseTarget) and x.target_id == a.instance_id))
        # Second buff must exclude A ("another").
        second = {x.target_id for x in legal_actions(state) if isinstance(x, ChooseTarget)}
        assert a.instance_id not in second
        state = apply(state, next(x for x in legal_actions(state)
                                  if isinstance(x, ChooseTarget) and x.target_id == b.instance_id))
        # Third buff must exclude A and B ("a third").
        third = {x.target_id for x in legal_actions(state) if isinstance(x, ChooseTarget)}
        assert third == {c.instance_id}
        state = apply(state, next(x for x in legal_actions(state)
                                  if isinstance(x, ChooseTarget) and x.target_id == c.instance_id))
        assert compute_power(state, _find_instance(state, a.instance_id)) == 4
        assert compute_power(state, _find_instance(state, b.instance_id)) == 3
        assert compute_power(state, _find_instance(state, c.instance_id)) == 2


class TestVanguardInfantry:
    def test_SOR_108_when_defeated_may_give_experience(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        vg_ci = _place(state, "P0", _get_card(repo, "SOR", "108"), "ground")
        friend_ci = _place(state, "P0", _mk_unit("Friend"), "ground")
        state = _defeat_and_fire(state, vg_ci, "P0")
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == friend_ci.instance_id)
        state = apply(state, choose)
        assert _experience_count(_find_instance(state, friend_ci.instance_id)) == 1


class TestColonelYularen:
    def test_SOR_109_heals_base_when_command_unit_played(self, repo):
        from swu.engine.actions import apply, PlayCard
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "109"), "ground")
        state.players[0].base_instance.damage = 5
        cmd = _mk_unit("Command Trooper", aspects=("Command",))
        cmd_ci = CardInstance("p0_cmd", cmd, "P0", Zone.HAND)
        state.players[0].hand.append(cmd_ci)
        _give_resources(state, "P0", 12)
        state = apply(state, PlayCard(cmd_ci.instance_id))
        assert state.players[0].base_instance.damage == 4


class TestFrontlineShuttle:
    def test_SOR_110_defeats_self_and_grants_exhausted_no_base_attack(self, repo):
        from swu.engine.actions import (legal_actions, apply, UseAbility,
                                        AttackWithUnit)
        state = _make_state()
        shuttle_ci = _place(state, "P0", _get_card(repo, "SOR", "110"), "ground")
        friend_ci = _place(state, "P0", _mk_unit("Tired", power=3, hp=3), "ground")
        friend_ci.exhausted = True
        enemy_ci = _place(state, "P1", _mk_unit("Foe", power=1, hp=5), "ground")
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == shuttle_ci.instance_id)
        state = apply(state, use)
        # Shuttle defeated as the cost.
        assert any(c.instance_id == shuttle_ci.instance_id
                   for c in state.players[0].discard)
        assert state.pending_decisions[-1].kind == "granted_attack"
        atks = [a for a in legal_actions(state) if isinstance(a, AttackWithUnit)]
        # The exhausted friendly can attack (allow_exhausted) but not a base (no_base).
        assert any(a.attacker_id == friend_ci.instance_id
                   and a.defender_id == enemy_ci.instance_id for a in atks)
        assert all(a.defender_id is not None for a in atks), "no base attacks allowed"


class TestEscortSkiff:
    def test_SOR_114_ambush_only_while_other_command_unit(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        skiff_ci = _place(state, "P0", _get_card(repo, "SOR", "114"), "ground")
        assert not has_keyword(state, skiff_ci, Keyword.AMBUSH)
        _place(state, "P0", _mk_unit("Cmd", aspects=("Command",)), "ground")
        assert has_keyword(state, skiff_ci, Keyword.AMBUSH)


class TestSteadfastBattalion:
    def test_SOR_116_buffs_friendly_only_with_leader_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, compute_power
        state = _make_state()
        bat_ci = _place(state, "P0", _get_card(repo, "SOR", "116"), "ground")
        friend_ci = _place(state, "P0", _mk_unit("Ally", power=2, hp=2), "ground")
        # No leader unit → trigger not collected.
        s0 = _fire_on_attack(state, bat_ci)
        assert not any(isinstance(a, ChooseTarget) for a in legal_actions(s0))
        # With a friendly leader unit in the arena the buff applies.
        leader = _get_card(repo, "SOR", "5")  # Luke Skywalker leader
        from swu.engine.state import CardInstance, Zone
        ldr_ci = CardInstance("p0_ldr", leader, "P0", Zone.GROUND_ARENA)
        ldr_ci.deployed = True
        state.players[0].ground_arena.append(ldr_ci)
        state = _fire_on_attack(state, bat_ci)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == friend_ci.instance_id)
        state = apply(state, choose)
        assert compute_power(state, _find_instance(state, friend_ci.instance_id)) == 4


class Test97thLegion:
    def test_SOR_118_scales_with_resources(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        leg_ci = _place(state, "P0", _get_card(repo, "SOR", "118"), "ground")
        # Printed 0/0; with no resources the +N/+N buff is zero (HP floors at 1).
        assert compute_power(state, leg_ci) == 0
        _give_resources(state, "P0", 3)
        assert compute_power(state, leg_ci) == 3 and compute_hp(state, leg_ci) == 3


class TestReinforcementWalker:
    def test_SOR_119_discard_top_heals_base(self, repo):
        from swu.engine.actions import legal_actions, apply, DiscardTopCard
        state = _make_state()
        walker_ci = _place(state, "P0", _get_card(repo, "SOR", "119"), "ground")
        state.players[0].base_instance.damage = 5
        _push_deck_top(state, "P0", _mk_unit("TopCard"))
        state = _fire_when_played(state, walker_ci)
        acts = legal_actions(state)
        # Mandatory binary: draw or discard-and-heal, no "keep on top".
        assert {type(a).__name__ for a in acts} == {"DrawTopCard", "DiscardTopCard"}
        state = apply(state, next(a for a in acts if isinstance(a, DiscardTopCard)))
        assert state.players[0].base_instance.damage == 2  # healed 3

    def test_SOR_119_draw_top_adds_to_hand(self, repo):
        from swu.engine.actions import legal_actions, apply, DrawTopCard
        state = _make_state()
        walker_ci = _place(state, "P0", _get_card(repo, "SOR", "119"), "ground")
        _push_deck_top(state, "P0", _mk_unit("TopCard"))
        hand_before = len(state.players[0].hand)
        state = _fire_when_played(state, walker_ci)
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, DrawTopCard)))
        assert len(state.players[0].hand) == hand_before + 1


class TestGuerillaAttackPod:
    def test_SOR_148_readies_when_a_base_has_15_damage(self, repo):
        state = _make_state()
        pod_ci = _place(state, "P0", _get_card(repo, "SOR", "148"), "ground")
        pod_ci.exhausted = True
        state.players[1].base_instance.damage = 15
        state = _fire_when_played(state, pod_ci)
        assert not _find_instance(state, pod_ci.instance_id).exhausted

    def test_SOR_148_no_ready_below_15_damage(self, repo):
        state = _make_state()
        pod_ci = _place(state, "P0", _get_card(repo, "SOR", "148"), "ground")
        pod_ci.exhausted = True
        state.players[1].base_instance.damage = 10
        state = _fire_when_played(state, pod_ci)
        assert _find_instance(state, pod_ci.instance_id).exhausted


class TestMaceWindu:
    def test_SOR_149_readies_on_attack_defeating_a_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        mace_ci = _place(state, "P0", _get_card(repo, "SOR", "149"), "ground")
        enemy_ci = _place(state, "P1", _mk_unit("Weakling", power=0, hp=1), "ground")
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == mace_ci.instance_id
                   and a.defender_id == enemy_ci.instance_id)
        state = apply(state, atk)
        # The 0/1 defender is defeated; Mace readies himself after attacking.
        assert not any(c.instance_id == enemy_ci.instance_id
                       for c in state.players[1].ground_arena)
        assert not _find_instance(state, mace_ci.instance_id).exhausted


class TestRallyingCry:
    def test_SOR_154_grants_raid_2_to_each_friendly_unit(self, repo):
        from swu.engine.actions import apply, PlayCard
        from swu.engine.keywords import keyword_value, Keyword
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        card = _get_card(repo, "SOR", "154")
        ci = CardInstance("p0_rc", card, "P0", Zone.HAND)
        state.players[0].hand.append(ci)
        _give_resources(state, "P0", 10)
        f1 = _place(state, "P0", _mk_unit("F1"), "ground")
        f2 = _place(state, "P0", _mk_unit("F2"), "space")
        e1 = _place(state, "P1", _mk_unit("E1"), "ground")
        state = apply(state, PlayCard(ci.instance_id))
        assert keyword_value(state, _find_instance(state, f1.instance_id), Keyword.RAID) == 2
        assert keyword_value(state, _find_instance(state, f2.instance_id), Keyword.RAID) == 2
        assert keyword_value(state, _find_instance(state, e1.instance_id), Keyword.RAID) == 0


class TestBenthicTwoTubes:
    def test_SOR_156_grants_raid_to_another_aggression_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        benthic_ci = _place(state, "P0", _get_card(repo, "SOR", "156"), "ground")
        aggr_ci = _place(state, "P0", _mk_unit("Rebel", aspects=("Aggression",)), "ground")
        state = _fire_on_attack(state, benthic_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == aggr_ci.instance_id)
        state = apply(state, choose)
        assert keyword_value(state, _find_instance(state, aggr_ci.instance_id), Keyword.RAID) == 2


class TestPartisanInsurgent:
    def test_SOR_159_raid_only_while_other_aggression_unit(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        part_ci = _place(state, "P0", _get_card(repo, "SOR", "159"), "ground")
        assert keyword_value(state, part_ci, Keyword.RAID) == 0
        _place(state, "P0", _mk_unit("Rebel", aspects=("Aggression",)), "ground")
        assert keyword_value(state, part_ci, Keyword.RAID) == 2


class TestArdentSympathizer:
    def test_SOR_161_power_buff_with_initiative(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        ard_ci = _place(state, "P0", _get_card(repo, "SOR", "161"), "ground")
        state.initiative_holder = 0
        assert compute_power(state, ard_ci) == 5  # 3 + 2
        state.initiative_holder = 1
        assert compute_power(state, ard_ci) == 3


class TestInfiltratorsSkill:
    def test_SOR_166_grants_saboteur_to_host(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        host_ci = _place(state, "P0", _mk_unit("Host", power=2, hp=2), "ground")
        assert not has_keyword(state, host_ci, Keyword.SABOTEUR)
        upg = _get_card(repo, "SOR", "166")
        upg_ci = CardInstance("p0_inf", upg, "P0", Zone.GROUND_ARENA)
        host_ci.attached_upgrades.append(upg_ci)
        assert has_keyword(state, host_ci, Keyword.SABOTEUR)


class TestPrecisionFire:
    def test_SOR_168_grants_saboteur_and_trooper_bonus(self, repo):
        from swu.engine.actions import (apply, PlayCard, legal_actions,
                                        AttackWithUnit)
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        card = _get_card(repo, "SOR", "168")
        ci = CardInstance("p0_pf", card, "P0", Zone.HAND)
        state.players[0].hand.append(ci)
        _give_resources(state, "P0", 10)
        trooper_ci = _place(state, "P0", _mk_unit("Grunt", power=2, hp=3,
                                                  traits=("Trooper",)), "ground")
        enemy_ci = _place(state, "P1", _mk_unit("Foe", power=1, hp=10), "ground")
        state = apply(state, PlayCard(ci.instance_id))
        assert state.pending_decisions[-1].kind == "granted_attack"
        atks = [a for a in legal_actions(state) if isinstance(a, AttackWithUnit)]
        atk = next(a for a in atks if a.attacker_id == trooper_ci.instance_id
                   and a.defender_id == enemy_ci.instance_id)
        state = apply(state, atk)
        # Trooper power 2 + Precision Fire's +2 (trooper bonus) = 4 damage dealt.
        assert _find_instance(state, enemy_ci.instance_id).damage == 4

    def test_SOR_168_no_base_attack_restriction_absent(self, repo):
        """Precision Fire has no no-base clause — attacking a base is allowed."""
        from swu.engine.actions import apply, PlayCard, legal_actions, AttackWithUnit
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        card = _get_card(repo, "SOR", "168")
        ci = CardInstance("p0_pf2", card, "P0", Zone.HAND)
        state.players[0].hand.append(ci)
        _give_resources(state, "P0", 10)
        _place(state, "P0", _mk_unit("Grunt", power=2, hp=3, traits=("Trooper",)), "ground")
        state = apply(state, PlayCard(ci.instance_id))
        atks = [a for a in legal_actions(state) if isinstance(a, AttackWithUnit)]
        assert any(a.defender_id is None for a in atks)  # base attack offered


class TestKeepFighting:
    def test_SOR_169_readies_low_power_unit_only(self, repo):
        from swu.engine.actions import apply, PlayCard, legal_actions, ChooseTarget
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        card = _get_card(repo, "SOR", "169")
        ci = CardInstance("p0_kf", card, "P0", Zone.HAND)
        state.players[0].hand.append(ci)
        _give_resources(state, "P0", 8)
        weak_ci = _place(state, "P0", _mk_unit("Weak", power=3, hp=3), "ground")
        weak_ci.exhausted = True
        strong_ci = _place(state, "P0", _mk_unit("Strong", power=5, hp=5), "ground")
        strong_ci.exhausted = True
        state = apply(state, PlayCard(ci.instance_id))
        targets = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert weak_ci.instance_id in targets
        assert strong_ci.instance_id not in targets
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget) and a.target_id == weak_ci.instance_id))
        assert not _find_instance(state, weak_ci.instance_id).exhausted


class TestCartelSpacer:
    def test_SOR_178_exhausts_cheap_enemy_with_another_cunning(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        spacer_ci = _place(state, "P0", _get_card(repo, "SOR", "178"), "space")
        # No other Cunning unit → no trigger.
        s0 = _fire_when_played(state, spacer_ci)
        assert not any(isinstance(a, ChooseTarget) for a in legal_actions(s0))
        # With another Cunning unit, exhaust a cost<=4 enemy unit.
        _place(state, "P0", _mk_unit("Cunning Ally", aspects=("Cunning",)), "ground")
        enemy_ci = _place(state, "P1", _mk_unit("Cheap", power=2, hp=2, cost=3), "ground")
        expensive_ci = _place(state, "P1", _mk_unit("Pricey", power=6, hp=6, cost=7), "ground")
        state = _fire_when_played(state, spacer_ci)
        targets = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert enemy_ci.instance_id in targets
        assert expensive_ci.instance_id not in targets
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget) and a.target_id == enemy_ci.instance_id))
        assert _find_instance(state, enemy_ci.instance_id).exhausted


# ══════════════════════════════════════════════════════════════════════════════
# Gap-filling campaign — sor-set group 16 (combat tricks, buffs & tempo)
# ══════════════════════════════════════════════════════════════════════════════

class TestVanguardAce:
    def test_SOR_191_experience_per_other_card_played(self, repo):
        state = _make_state()
        ace_ci = _place(state, "P0", _get_card(repo, "SOR", "191"), "space")
        # Simulate 3 cards played this phase by P0 (incl. the Ace itself).
        state.game_memory.cards_played_this_phase["P0"] = 3
        state = _fire_when_played(state, ace_ci)
        # "other cards" = 3 − 1 = 2 Experience tokens.
        assert _experience_count(_find_instance(state, ace_ci.instance_id)) == 2

    def test_SOR_191_no_tokens_when_only_card(self, repo):
        state = _make_state()
        ace_ci = _place(state, "P0", _get_card(repo, "SOR", "191"), "space")
        state.game_memory.cards_played_this_phase["P0"] = 1
        state = _fire_when_played(state, ace_ci)
        assert _experience_count(_find_instance(state, ace_ci.instance_id)) == 0


class TestOuterRimHeadhunter:
    def test_SOR_208_exhaust_non_leader_only_with_leader_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        hunter_ci = _place(state, "P0", _get_card(repo, "SOR", "208"), "space")
        enemy_ci = _place(state, "P1", _mk_unit("Foe", power=2, hp=2), "ground")
        # No leader unit → trigger not collected.
        s0 = _fire_on_attack(state, hunter_ci)
        assert not any(isinstance(a, (AcceptTrigger, ChooseTarget))
                       for a in legal_actions(s0))
        # With a friendly deployed leader unit, the optional exhaust is offered.
        leader = _get_card(repo, "SOR", "5")
        ldr_ci = CardInstance("p0_ldr", leader, "P0", Zone.GROUND_ARENA)
        ldr_ci.deployed = True
        state.players[0].ground_arena.append(ldr_ci)
        state = _fire_on_attack(state, hunter_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        # The deployed leader is NOT an eligible (non-leader) target.
        targets = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert enemy_ci.instance_id in targets
        assert ldr_ci.instance_id not in targets
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy_ci.instance_id))
        assert _find_instance(state, enemy_ci.instance_id).exhausted


class TestGamorreanGuards:
    def test_SOR_211_sentinel_only_while_other_cunning_unit(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        guards_ci = _place(state, "P0", _get_card(repo, "SOR", "211"), "ground")
        assert not has_keyword(state, guards_ci, Keyword.SENTINEL)
        _place(state, "P0", _mk_unit("Cunning Ally", aspects=("Cunning",)), "ground")
        assert has_keyword(state, guards_ci, Keyword.SENTINEL)


class TestSmugglingCompartment:
    def test_SOR_214_host_on_attack_readies_a_resource(self, repo):
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        host_ci = _place(state, "P0", _mk_unit("Speeder", power=2, hp=2,
                                               traits=("Vehicle",)), "ground")
        upg = _get_card(repo, "SOR", "214")
        upg_ci = CardInstance("p0_sc", upg, "P0", Zone.GROUND_ARENA)
        host_ci.attached_upgrades.append(upg_ci)
        _give_resources(state, "P0", 2)
        for r in state.players[0].resources:
            r.exhausted = True
        state = _fire_on_attack(state, host_ci)
        assert sum(1 for r in state.players[0].resources if not r.exhausted) == 1


class TestSnapshotReflexesSOR:
    def test_SOR_215_when_played_offers_attack_with_host(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit, DeclineGrantedAttack
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        host_ci = _place(state, "P0", _mk_unit("Trooper", power=3, hp=3), "ground")
        _place(state, "P1", _mk_unit("Foe", power=1, hp=5), "ground")
        upg = _get_card(repo, "SOR", "215")
        upg_ci = CardInstance("p0_sr", upg, "P0", Zone.GROUND_ARENA)
        host_ci.attached_upgrades.append(upg_ci)
        state = _fire_upgrade_played(state, upg_ci, host_ci)
        assert state.pending_decisions[-1].kind == "granted_attack"
        acts = legal_actions(state)
        assert any(isinstance(a, AttackWithUnit)
                   and a.attacker_id == host_ci.instance_id for a in acts)
        assert any(isinstance(a, DeclineGrantedAttack) for a in acts)


class TestOutmaneuver:
    def test_SOR_221_exhausts_each_unit_in_chosen_arena(self, repo):
        from swu.engine.actions import (apply, PlayCard, legal_actions,
                                        ChooseModalOption)
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        card = _get_card(repo, "SOR", "221")
        ci = CardInstance("p0_om", card, "P0", Zone.HAND)
        state.players[0].hand.append(ci)
        _give_resources(state, "P0", 8)
        g_friend = _place(state, "P0", _mk_unit("GF", power=1, hp=2), "ground")
        g_enemy = _place(state, "P1", _mk_unit("GE", power=1, hp=2), "ground")
        s_friend = _place(state, "P0", _mk_unit("SF", power=1, hp=2), "space")
        state = apply(state, PlayCard(ci.instance_id))
        assert state.pending_decisions[-1].kind == "modal"
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseModalOption) and a.mode == "exhaust_ground")
        state = apply(state, choose)
        assert _find_instance(state, g_friend.instance_id).exhausted
        assert _find_instance(state, g_enemy.instance_id).exhausted
        assert not _find_instance(state, s_friend.instance_id).exhausted


class TestFrontierATRT:
    def test_SOR_249_ambush_only_while_other_vehicle_unit(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        atrt_ci = _place(state, "P0", _get_card(repo, "SOR", "249"), "ground")
        assert not has_keyword(state, atrt_ci, Keyword.AMBUSH)
        _place(state, "P0", _mk_unit("Speeder", traits=("Vehicle",)), "ground")
        assert has_keyword(state, atrt_ci, Keyword.AMBUSH)


# ══════════════════════════════════════════════════════════════════════════════
# Gap-filling campaign — sor-set group 17 (miscellaneous abilities)
# ══════════════════════════════════════════════════════════════════════════════

class TestDelMeeko:
    def test_SOR_34_taxes_opponent_events_only(self, repo):
        from swu.engine.actions import _play_cost
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        event = _get_card(repo, "SOR", "73")  # Moment of Peace (Event)
        ev_ci = CardInstance("p0_ev", event, "P0", Zone.HAND)
        state.players[0].hand.append(ev_ci)
        unit = _mk_unit("Grunt", cost=3)
        u_ci = CardInstance("p0_u", unit, "P0", Zone.HAND)
        state.players[0].hand.append(u_ci)
        ev_base = _play_cost(state, ev_ci, state.players[0])
        u_base = _play_cost(state, u_ci, state.players[0])
        _place(state, "P1", _get_card(repo, "SOR", "34"), "ground")  # Del Meeko (enemy)
        assert _play_cost(state, ev_ci, state.players[0]) == ev_base + 1  # event taxed
        assert _play_cost(state, u_ci, state.players[0]) == u_base        # unit untaxed


class TestJediLightsaber:
    def test_SOR_54_force_host_debuffs_defender_on_attack(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        host = _place(state, "P0", _mk_unit("Jedi", power=3, hp=3,
                                            traits=("Force",)), "ground")
        upg_ci = CardInstance("p0_jl", _get_card(repo, "SOR", "54"), "P0",
                              Zone.GROUND_ARENA)
        host.attached_upgrades.append(upg_ci)
        defender = _place(state, "P1", _mk_unit("Foe", power=5, hp=5), "ground")
        state = _fire_on_attack(state, host, defender)
        d = _find_instance(state, defender.instance_id)
        assert compute_power(state, d) == 3  # 5 − 2
        assert compute_hp(state, d) == 3      # 5 − 2

    def test_SOR_54_non_force_host_no_debuff(self, repo):
        from swu.engine.actions import compute_power
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        host = _place(state, "P0", _mk_unit("Grunt", power=3, hp=3), "ground")
        upg_ci = CardInstance("p0_jl2", _get_card(repo, "SOR", "54"), "P0",
                              Zone.GROUND_ARENA)
        host.attached_upgrades.append(upg_ci)
        defender = _place(state, "P1", _mk_unit("Foe", power=5, hp=5), "ground")
        state = _fire_on_attack(state, host, defender)
        assert compute_power(state, _find_instance(state, defender.instance_id)) == 5


class TestBendu:
    def test_SOR_56_discounts_next_non_heroism_villainy_card(self, repo):
        from swu.engine.actions import _play_cost
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        bendu = _place(state, "P0", _get_card(repo, "SOR", "56"), "ground")
        plain = _mk_unit("Plain", cost=5)
        plain_ci = CardInstance("p0_pl", plain, "P0", Zone.HAND)
        state.players[0].hand.append(plain_ci)
        villain = _mk_unit("Villain", cost=5, aspects=("Villainy",))
        vil_ci = CardInstance("p0_vl", villain, "P0", Zone.HAND)
        state.players[0].hand.append(vil_ci)
        vil_base = _play_cost(state, vil_ci, state.players[0])
        state = _fire_on_attack(state, bendu)
        assert _play_cost(state, plain_ci, state.players[0]) == 3   # 5 − 2
        assert _play_cost(state, vil_ci, state.players[0]) == vil_base  # Villainy excluded


class TestGuardianOfTheWhills:
    def test_SOR_61_first_upgrade_on_self_costs_less(self, repo):
        from swu.engine.actions import _play_cost
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        guardian = _place(state, "P0", _get_card(repo, "SOR", "61"), "ground")
        other = _place(state, "P0", _mk_unit("Other", power=2, hp=2), "ground")
        upg_ci = CardInstance("p0_up", _get_card(repo, "SOR", "71"), "P0", Zone.HAND)
        state.players[0].hand.append(upg_ci)
        on_guardian = _play_cost(state, upg_ci, state.players[0],
                                 target_host_id=guardian.instance_id)
        on_other = _play_cost(state, upg_ci, state.players[0],
                              target_host_id=other.instance_id)
        assert on_other - on_guardian == 1  # host-scoped 1-less on the Guardian
        # Once spent this round, no further discount.
        state.game_memory.standing_play_discounts_used_this_round.add(guardian.instance_id)
        assert _play_cost(state, upg_ci, state.players[0],
                          target_host_id=guardian.instance_id) == on_other


class TestRegionalGovernor:
    def test_SOR_62_opponent_cant_play_named_card(self, repo):
        from swu.engine.actions import legal_actions, PlayCard, apply
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        gov = _place(state, "P1", _get_card(repo, "SOR", "62"), "ground")  # enemy
        gov.named_card = "Banned Card"
        banned_ci = CardInstance("p0_b", _mk_unit("Banned Card", cost=1), "P0", Zone.HAND)
        allowed_ci = CardInstance("p0_a", _mk_unit("Allowed Card", cost=1), "P0", Zone.HAND)
        state.players[0].hand.extend([banned_ci, allowed_ci])
        _give_resources(state, "P0", 5)
        playable = {a.instance_id for a in legal_actions(state) if isinstance(a, PlayCard)}
        assert banned_ci.instance_id not in playable
        assert allowed_ci.instance_id in playable
        # Direct apply of the forbidden play is rejected.
        import pytest as _pytest
        from swu.engine.actions import IllegalActionError
        with _pytest.raises(IllegalActionError):
            apply(state, PlayCard(banned_ci.instance_id))

    def test_SOR_62_names_a_card_on_play(self, repo):
        from swu.engine.actions import apply, PlayCard, legal_actions, NameCard
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        gov_ci = CardInstance("p0_gov", _get_card(repo, "SOR", "62"), "P0", Zone.HAND)
        state.players[0].hand.append(gov_ci)
        # Give a couple of deck cards so there are names to choose.
        _push_deck_top(state, "P0", _mk_unit("Some Card"))
        _give_resources(state, "P0", 6)
        state = apply(state, PlayCard(gov_ci.instance_id))
        assert state.pending_decisions[-1].kind == "name_a_card"
        assert any(isinstance(a, NameCard) for a in legal_actions(state))


class TestElectrostaff:
    def test_SOR_71_debuffs_attacker_while_host_defends(self, repo):
        from swu.engine.actions import compute_power
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        host = _place(state, "P0", _mk_unit("Defender", power=2, hp=5), "ground")
        upg_ci = CardInstance("p0_es", _get_card(repo, "SOR", "71"), "P0",
                              Zone.GROUND_ARENA)
        host.attached_upgrades.append(upg_ci)
        attacker = _place(state, "P1", _mk_unit("Attacker", power=4, hp=4), "ground")
        # No combat context (host not the defender) → attacker unchanged.
        assert compute_power(state, attacker) == 4
        # While the host is the current defender, the attacker gets −1/−0.
        assert compute_power(state, attacker, defender_id=host.instance_id) == 3


class TestEntrenched:
    def test_SOR_72_host_cannot_attack_bases(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        host = _place(state, "P0", _mk_unit("Trooper", power=3, hp=3), "ground")
        _place(state, "P1", _mk_unit("Foe", power=1, hp=5), "ground")
        atks_before = [a for a in legal_actions(state)
                       if isinstance(a, AttackWithUnit) and a.attacker_id == host.instance_id]
        assert any(a.defender_id is None for a in atks_before)  # base attack offered
        upg_ci = CardInstance("p0_en", _get_card(repo, "SOR", "72"), "P0",
                              Zone.GROUND_ARENA)
        host.attached_upgrades.append(upg_ci)
        atks_after = [a for a in legal_actions(state)
                      if isinstance(a, AttackWithUnit) and a.attacker_id == host.instance_id]
        assert atks_after, "unit attacks still offered"
        assert all(a.defender_id is not None for a in atks_after)  # no base attack


# ── sor-set:18 — Miscellaneous abilities ──────────────────────────────────────

class TestAllianceDispatcherSOR93:
    def test_SOR_93_activated_play_costs_one_less(self, repo):
        """Action [exhaust]: pushes a play_from_hand decision with cost_reduction=1
        and (paying the discount) puts a hand unit into play; the dispatcher exhausts."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import legal_actions, apply, UseAbility, PlayFromHand
        dispatcher = _get_card(repo, "SOR", "93")
        state = _make_state()
        disp_ci = _place(state, "P0", dispatcher, "ground")
        disp_ci.exhausted = False
        unit = _get_card(repo, "SOR", "128")  # cost-1 unit
        unit_ci = CardInstance("p0_u", unit, "P0", Zone.HAND)
        state.players[0].hand.append(unit_ci)
        _give_resources(state, "P0", 10)

        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == disp_ci.instance_id)
        state = apply(state, use)
        top = state.pending_decisions[-1]
        assert top.kind == "play_from_hand"
        assert top.context["cost_reduction"] == 1
        assert _find_instance(state, disp_ci.instance_id).exhausted

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand) and a.instance_id == unit_ci.instance_id)
        state = apply(state, play)
        placed = _find_instance(state, unit_ci.instance_id)
        assert placed is not None and placed.zone in (Zone.GROUND_ARENA, Zone.SPACE_ARENA)


class TestUWingReinforcementSOR104:
    def test_SOR_104_caps_at_three_units_and_plays_free(self, repo):
        """Search top 10 for up to 3 units (combined cost ≤7), play each free: the
        deck_search decision caps max_select at 3 even with 4 affordable candidates."""
        from swu.engine.actions import (legal_actions, apply, SelectSearchCard)
        state = _make_state()
        # Four cost-1 units on top of P0's deck (combined cost 4 ≤ 7, but capped at 3).
        unit_def = _get_card(repo, "SOR", "128")
        deck_units = [_deck_card(state, "P0", unit_def) for _ in range(4)]
        state, _evt = _play_event_from_hand(state, repo, "SOR", "104", resources=20)

        top = state.pending_decisions[-1]
        assert top.kind == "deck_search"
        assert top.context["disposition"] == "play"
        assert top.context["max_select"] == 3, "up-to-3 cap"

        # Take three; the third pick auto-finishes (can't exceed the cap).
        for _ in range(3):
            sel = next(a for a in legal_actions(state) if isinstance(a, SelectSearchCard))
            state = apply(state, sel)
        assert not any(d.kind == "deck_search" for d in state.pending_decisions)
        in_play = len(state.players[0].ground_arena) + len(state.players[0].space_arena)
        assert in_play == 3, f"exactly 3 units played for free, got {in_play}"


class TestStrikeTrueSOR127:
    def test_SOR_127_friendly_deals_its_power_to_enemy(self, repo):
        """A friendly unit deals damage equal to its power to a chosen enemy unit."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget, compute_power
        state = _make_state()
        friendly = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "37"), "ground")  # high-hp
        power = compute_power(state, friendly)
        assert power > 0
        state, _evt = _play_event_from_hand(state, repo, "SOR", "127")

        # Step 1: choose the friendly source.
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == friendly.instance_id)
        state = apply(state, choose)
        # Step 2: choose the enemy target.
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id)
        state = apply(state, choose)

        assert _find_instance(state, enemy.instance_id).damage == power


class TestSpecForceSoldierSOR140:
    def test_SOR_140_target_unit_loses_sentinel(self, repo):
        """When Played: a chosen unit loses Sentinel for this phase."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        soldier = _place(state, "P0", _get_card(repo, "SOR", "140"), "ground")
        sentinel = _place(state, "P1", _get_card(repo, "SOR", "35"), "ground")  # Sentinel
        assert has_keyword(state, sentinel, Keyword.SENTINEL)

        state = _fire_when_played(state, soldier)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == sentinel.instance_id)
        state = apply(state, choose)
        assert not has_keyword(state, _find_instance(state, sentinel.instance_id), Keyword.SENTINEL)


class TestKarabastSOR151:
    def test_SOR_151_deals_friendly_damage_plus_one(self, repo):
        """A friendly unit deals damage to an enemy equal to its own damage + 1."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        friendly = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        friendly.damage = 3
        enemy = _place(state, "P1", _get_card(repo, "SOR", "37"), "ground")  # high-hp
        state, _evt = _play_event_from_hand(state, repo, "SOR", "151")

        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == friendly.instance_id)
        state = apply(state, choose)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id)
        state = apply(state, choose)

        assert _find_instance(state, enemy.instance_id).damage == 4  # 3 + 1


class TestWolffeSOR160:
    def test_SOR_160_when_played_blocks_base_heals(self, repo):
        """When Played sets the phase-scoped 'bases can't be healed' lock: a Restore
        and a Heal effect both leave a damaged base untouched, and clear_phase lifts it."""
        from swu.engine.actions import _apply_restore, _bases_cannot_heal
        from swu.abilities.resolver import _apply_heal
        state = _make_state()
        wolffe = _place(state, "P0", _get_card(repo, "SOR", "160"), "ground")
        ps0 = state.players[0]
        base = ps0.base_instance
        base.damage = 8

        state = _fire_when_played(state, wolffe)
        assert _bases_cannot_heal(state)

        _apply_restore(state, ps0, 5)
        assert base.damage == 8, "Restore heals nothing while the lock is up"
        _apply_heal(state, wolffe, base.instance_id, 5)
        assert base.damage == 8, "Heal effect heals no base while the lock is up"

        state.game_memory.clear_phase()
        assert not _bases_cannot_heal(state)
        _apply_restore(state, ps0, 5)
        assert base.damage == 3, "healing resumes after the phase rolls over"


# ── sor-set:19 — Miscellaneous abilities ──────────────────────────────────────

class TestDisarmSOR216:
    def test_SOR_216_gives_enemy_minus_four_power(self, repo):
        """The event debuffs a chosen enemy unit -4/-0 for this phase."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget, compute_power
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "185"), "space")  # 8 power
        base_power = compute_power(state, enemy)
        assert base_power >= 4
        state, _evt = _play_event_from_hand(state, repo, "SOR", "216")
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id)
        state = apply(state, choose)
        assert compute_power(state, _find_instance(state, enemy.instance_id)) == base_power - 4


class TestLothalInsurgentSOR190:
    def _opp_hand_and_deck(self, state, repo):
        """Give P1 a single known hand card and a single known deck-top card."""
        hand = _hand_card(state, "P1", _get_card(repo, "SOR", "128"))
        deck = _push_deck_top(state, "P1", _get_card(repo, "SOR", "128"))
        return hand, deck

    def _drain(self, state):
        from swu.engine.actions import legal_actions, apply, AutoResolveEffects
        while True:
            act = next((a for a in legal_actions(state)
                        if isinstance(a, AutoResolveEffects)), None)
            if act is None:
                return state
            state = apply(state, act)

    def test_SOR_190_opponent_draws_then_discards_when_another_played(self, repo):
        """With another card played this phase, the opponent draws 1 then discards a
        random (first) hand card."""
        state = _make_state()
        insurgent = _place(state, "P0", _get_card(repo, "SOR", "190"), "ground")
        hand, deck = self._opp_hand_and_deck(state, repo)
        state.game_memory.cards_played_this_phase["P0"] = 2  # "played another card"
        state = self._drain(_fire_when_played(state, insurgent))
        p1 = state.players[1]
        assert deck.instance_id in {c.instance_id for c in p1.hand}, "opponent drew the deck card"
        assert hand.instance_id in {c.instance_id for c in p1.discard}, "opponent discarded its old card"

    def test_SOR_190_no_effect_without_another_card(self, repo):
        """The clause is gated: if no other card was played this phase, nothing fires."""
        state = _make_state()
        insurgent = _place(state, "P0", _get_card(repo, "SOR", "190"), "ground")
        hand, deck = self._opp_hand_and_deck(state, repo)
        state.game_memory.cards_played_this_phase["P0"] = 1  # only this card
        state = self._drain(_fire_when_played(state, insurgent))
        p1 = state.players[1]
        assert deck.instance_id in {c.instance_id for c in p1.deck}, "no draw"
        assert not p1.discard, "no discard"


class TestLandoCalrissianSOR197:
    def test_SOR_197_returns_two_resources_to_hand(self, repo):
        """When Played auto-returns up to 2 friendly resources to the controller's hand."""
        state = _make_state()
        lando = _place(state, "P0", _get_card(repo, "SOR", "197"), "ground")
        _give_resources(state, "P0", 5)
        p0 = state.players[0]
        res_before, hand_before = len(p0.resources), len(p0.hand)
        state = _fire_when_played(state, lando)
        p0 = state.players[0]
        assert len(p0.resources) == res_before - 2
        assert len(p0.hand) == hand_before + 2

    def test_SOR_197_returns_only_what_is_available(self, repo):
        """"Up to 2": with a single resource, exactly one is returned."""
        state = _make_state()
        lando = _place(state, "P0", _get_card(repo, "SOR", "197"), "ground")
        _give_resources(state, "P0", 1)
        p0 = state.players[0]
        hand_before = len(p0.hand)
        state = _fire_when_played(state, lando)
        p0 = state.players[0]
        assert len(p0.resources) == 0
        assert len(p0.hand) == hand_before + 1


def _advance_to_kind(state, kind, limit=20):
    """Apply AutoResolveEffects until a decision of `kind` is on top (or the effect
    stack drains) — used to surface a decision a mandatory trigger pushes."""
    from swu.engine.actions import legal_actions, apply, AutoResolveEffects
    for _ in range(limit):
        if state.pending_decisions and state.pending_decisions[-1].kind == kind:
            return state
        act = next((a for a in legal_actions(state)
                    if isinstance(a, AutoResolveEffects)), None)
        if act is None:
            return state
        state = apply(state, act)
    return state


class TestSmokeAndCindersSOR174:
    def _drive_discards(self, state):
        """Resolve the pending discard_excess_from_hand decision — each deciding
        player discards their first legal card until the decision pops."""
        from swu.engine.actions import (
            legal_actions, apply, SelectExcessHandCardToDiscard)
        while (state.pending_decisions
               and state.pending_decisions[-1].kind == "discard_excess_from_hand"):
            act = next(a for a in legal_actions(state)
                       if isinstance(a, SelectExcessHandCardToDiscard))
            state = apply(state, act)
        return state

    def test_SOR_174_each_player_discards_down_to_two(self, repo):
        """Both players discard (of their choice) down to a 2-card hand, the event's
        controller first."""
        from swu.engine.actions import legal_actions, SelectExcessHandCardToDiscard
        state = _make_state()
        for _ in range(4):
            _hand_card(state, "P0", _get_card(repo, "SOR", "128"))
            _hand_card(state, "P1", _get_card(repo, "SOR", "128"))
        state, _evt = _play_event_from_hand(state, repo, "SOR", "174")
        state = _advance_to_kind(state, "discard_excess_from_hand")
        top = state.pending_decisions[-1]
        assert top.kind == "discard_excess_from_hand"
        assert top.deciding_player_id == "P0"  # controller trims first
        # All four of P0's hand cards are offered ("of their choice").
        assert len([a for a in legal_actions(state)
                    if isinstance(a, SelectExcessHandCardToDiscard)]) == 4
        state = self._drive_discards(state)
        assert len(state.players[0].hand) == 2
        assert len(state.players[1].hand) == 2
        assert len(state.players[1].discard) == 2  # opponent discarded exactly 2

    def test_SOR_174_player_at_two_is_skipped(self, repo):
        """A player already holding ≤2 cards discards nothing; only the excess side
        acts."""
        state = _make_state()
        _hand_card(state, "P1", _get_card(repo, "SOR", "128"))  # P1 holds only 1
        for _ in range(4):
            _hand_card(state, "P0", _get_card(repo, "SOR", "128"))
        state, _evt = _play_event_from_hand(state, repo, "SOR", "174")
        state = _advance_to_kind(state, "discard_excess_from_hand")
        state = self._drive_discards(state)
        assert len(state.players[0].hand) == 2  # P0 trimmed
        assert len(state.players[1].hand) == 1  # P1 untouched (already ≤2)
        assert not state.players[1].discard


class TestChimaeraSOR185:
    def test_SOR_185_names_and_discards_a_hand_card(self, repo):
        """On Attack the controller names a card in the opponent's revealed hand and
        one copy of that name is discarded."""
        from swu.engine.actions import legal_actions, apply, NameAndDiscard
        state = _make_state()
        chimaera = _place(state, "P0", _get_card(repo, "SOR", "185"), "space")
        card128 = _get_card(repo, "SOR", "128")
        card46 = _get_card(repo, "SOR", "46")
        victim = _hand_card(state, "P1", card128)
        keeper = _hand_card(state, "P1", card46)
        state = _advance_to_kind(_fire_on_attack(state, chimaera), "name_and_discard")
        top = state.pending_decisions[-1]
        assert top.kind == "name_and_discard"
        assert top.deciding_player_id == "P0"
        # The controller may name either revealed card's name; no opponent
        # instance_id is exposed in the private context (hidden-info safe).
        names = {a.card_name for a in legal_actions(state)
                 if isinstance(a, NameAndDiscard)}
        assert names == {card128.display_name, card46.display_name}
        blob = repr(top.context["revealed_hand"])
        assert victim.instance_id not in blob and keeper.instance_id not in blob
        act = next(a for a in legal_actions(state)
                   if isinstance(a, NameAndDiscard)
                   and a.card_name == card128.display_name)
        state = apply(state, act)
        p1 = state.players[1]
        assert victim.instance_id in {c.instance_id for c in p1.discard}
        assert keeper.instance_id in {c.instance_id for c in p1.hand}

    def test_SOR_185_fizzles_on_empty_opponent_hand(self, repo):
        """With no cards in the opponent's hand there is nothing to reveal or
        discard — no decision is pushed."""
        state = _make_state()
        chimaera = _place(state, "P0", _get_card(repo, "SOR", "185"), "space")
        state = _fire_on_attack(state, chimaera)
        assert not any(d.kind == "name_and_discard" for d in state.pending_decisions)


class TestChangeOfHeart:
    """SOR_224 — Change of Heart (Event, Gambit, cost 6): "Take control of a
    non-leader unit. At the start of the regroup phase, its owner takes control of
    it."  Control-change seam + the return_control_to_owner_at_regroup revert flag."""

    def _hand_event(self, state, repo, owner="P0"):
        from swu.engine.state import CardInstance, Zone
        coh = _get_card(repo, "SOR", "224")
        ci = CardInstance("p0_coh", coh, owner, Zone.HAND)
        state.player_by_id(owner).hand.append(ci)
        return ci

    def _seed_decks(self, state, repo):
        # Give both players a couple of deck cards so the regroup draw does not
        # trigger the empty-deck base-damage penalty.
        from swu.engine.state import CardInstance, Zone
        filler = _get_card(repo, "SOR", "46")
        for pid in ("P0", "P1"):
            for i in range(3):
                state.player_by_id(pid).deck.append(
                    CardInstance(f"{pid}_dk_{i}", filler, pid, Zone.DECK))

    def test_SOR_224_takes_control_then_reverts_at_regroup(self, repo):
        from swu.engine.actions import (
            apply, PlayCard, ChooseTarget, legal_actions, _enter_regroup)
        state = _make_state()
        coh_ci = self._hand_event(state, repo)
        self._seed_decks(state, repo)
        enemy_ci = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # non-leader
        _give_resources(state, "P0", 10)

        state = apply(state, PlayCard(coh_ci.instance_id))
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy_ci.instance_id)
        state = apply(state, choose)
        while state.pending_decisions and not state.is_terminal():
            acts = legal_actions(state)
            state = apply(state, acts[0])

        # Now controlled by P0 (relocated into P0's arena); owner unchanged.
        holder, ci = state.find_instance(enemy_ci.instance_id)
        assert holder.player_id == "P0", "P0 took control of the enemy unit"
        assert ci.owner_id == "P1", "ownership is unchanged"
        assert ci.return_control_to_owner_at_regroup, "revert flag armed"

        _enter_regroup(state)

        holder, ci = state.find_instance(enemy_ci.instance_id)
        assert holder.player_id == "P1", "owner regained control at regroup"
        assert not ci.return_control_to_owner_at_regroup, "revert flag consumed"

    def test_SOR_224_only_enemy_units_are_targetable(self, repo):
        from swu.engine.actions import apply, PlayCard, ChooseTarget, legal_actions
        state = _make_state()
        coh_ci = self._hand_event(state, repo)
        enemy_ci = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        friendly_ci = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _give_resources(state, "P0", 10)
        state = apply(state, PlayCard(coh_ci.instance_id))
        target_ids = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert enemy_ci.instance_id in target_ids, "enemy unit targetable"
        assert friendly_ci.instance_id not in target_ids, "own unit not offered (no-op)"

    def test_SOR_224_no_longer_escape_hatch(self):
        from swu.abilities.registry import is_escape_hatch
        import swu.cards.sor  # noqa: F401
        assert not is_escape_hatch("SOR", "224")


class TestVolunteerSoldier:
    """SOR_248 — Volunteer Soldier (Unit, Trooper, 2/3, Raid 1): "If you control a
    TROOPER unit, this unit costs 1 resource less to play."  Force Choke SOR_139
    CostReduction template gated by CONTROLLER_HAS_TRAIT_UNIT("Trooper")."""

    def _hand_unit(self, state, repo, owner="P0"):
        from swu.engine.state import CardInstance, Zone
        vs = _get_card(repo, "SOR", "248")
        ci = CardInstance("p0_vs", vs, owner, Zone.HAND)
        state.player_by_id(owner).hand.append(ci)
        return ci

    def _cost_paid(self, repo, *, with_trooper):
        from swu.engine.actions import apply, PlayCard
        state = _make_state()
        vs_ci = self._hand_unit(state, repo)
        if with_trooper:
            _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")  # a Trooper unit
        _give_resources(state, "P0", 10)
        before = state.player_by_id("P0").available_resources
        state = apply(state, PlayCard(vs_ci.instance_id))
        return before - state.player_by_id("P0").available_resources

    def test_SOR_248_cost_reduced_by_one_only_with_trooper(self, repo):
        without = self._cost_paid(repo, with_trooper=False)
        with_trooper = self._cost_paid(repo, with_trooper=True)
        assert with_trooper == without - 1, "a controlled Trooper reduces the cost by 1"

    def test_SOR_248_reduction_reflected_in_affordability(self, repo):
        from swu.engine.actions import legal_actions, PlayCard
        reduced = self._cost_paid(repo, with_trooper=True)

        def _playable(with_trooper, resources):
            state = _make_state()
            vs_ci = self._hand_unit(state, repo)
            if with_trooper:
                _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")
            _give_resources(state, "P0", resources)
            return any(isinstance(a, PlayCard) and a.instance_id == vs_ci.instance_id
                       for a in legal_actions(state))

        assert _playable(True, reduced), "affordable with the Trooper discount"
        assert not _playable(False, reduced), "without a Trooper it costs 1 more"
        assert _playable(False, reduced + 1), "affordable without discount at full cost"

    def test_SOR_248_no_longer_escape_hatch(self):
        from swu.abilities.registry import is_escape_hatch
        import swu.cards.sor  # noqa: F401
        assert not is_escape_hatch("SOR", "248")


def _drain_forced(state):
    """Apply any pending forced continuations (AutoResolveEffects / single-action)."""
    from swu.engine.actions import legal_actions, apply
    guard = 0
    while state.pending_decisions and not state.is_terminal():
        acts = legal_actions(state)
        if len(acts) != 1:
            break
        state = apply(state, acts[0])
        guard += 1
        if guard > 20:
            break
    return state


class TestTraitorousSOR122:
    """SOR_122 — Traitorous: take control on attach (≤3-cost non-leader), revert on unattach.

    The former escalation of sor-set:18. Trigger 1 is an ordinary upgrade WhenPlayed
    that composes actions.change_control with the control_linked_to seam; trigger 2
    reuses _revert_linked_control (Maul LAW_54), now fired from the upgrade-removal
    chokepoints (_apply_defeat_unit / _apply_return_to_hand).
    """

    def _attach_traitorous(self, state, repo, host_ci, upgrade_owner="P0"):
        from swu.engine.state import CardInstance
        traitorous = _get_card(repo, "SOR", "122")
        upg = CardInstance(
            instance_id=f"{upgrade_owner}_trait_{uuid.uuid4().hex[:6]}",
            card_def=traitorous, owner_id=upgrade_owner, zone=host_ci.zone,
        )
        host_ci.attached_upgrades.append(upg)
        state = _fire_upgrade_played(state, upg, host_ci)
        state = _drain_forced(state)
        return state, upg

    def _in_arena(self, state, pid, instance_id):
        ps = state.player_by_id(pid)
        return any(c.instance_id == instance_id
                   for c in ps.ground_arena + ps.space_arena)

    def test_SOR_122_takes_control_of_cheap_enemy_unit(self, repo):
        state = _make_state()
        host = _place(state, "P1", _get_card(repo, "SOR", "140"), "ground")  # cost 1
        state, upg = self._attach_traitorous(state, repo, host)
        assert self._in_arena(state, "P0", host.instance_id), "P0 now controls the host"
        assert not self._in_arena(state, "P1", host.instance_id)
        moved = _find_instance(state, host.instance_id)
        assert moved.owner_id == "P1", "ownership is unchanged (only control moved)"
        assert moved.control_linked_to == upg.instance_id, "control is linked to Traitorous"

    def test_SOR_122_no_control_of_expensive_unit(self, repo):
        state = _make_state()
        host = _place(state, "P1", _get_card(repo, "SOR", "232"), "ground")  # AT-ST cost 6
        state, upg = self._attach_traitorous(state, repo, host)
        assert self._in_arena(state, "P1", host.instance_id), "a >3-cost unit is not stolen"
        assert not self._in_arena(state, "P0", host.instance_id)
        moved = _find_instance(state, host.instance_id)
        assert moved.control_linked_to is None

    def test_SOR_122_reverts_control_when_upgrade_defeated(self, repo):
        from swu.abilities.resolver import _apply_defeat_unit
        state = _make_state()
        host = _place(state, "P1", _get_card(repo, "SOR", "140"), "ground")
        state, upg = self._attach_traitorous(state, repo, host)
        assert self._in_arena(state, "P0", host.instance_id)  # sanity: stolen
        state = _apply_defeat_unit(state, upg.instance_id)     # remove Traitorous
        assert self._in_arena(state, "P1", host.instance_id), "owner reclaims on unattach"
        moved = _find_instance(state, host.instance_id)
        assert moved.control_linked_to is None, "the link is cleared on revert"
        assert any(c.instance_id == upg.instance_id
                   for c in state.player_by_id("P0").discard), "upgrade to its owner's discard"

    def test_SOR_122_reverts_control_when_upgrade_returned_to_hand(self, repo):
        from swu.abilities.resolver import _apply_return_to_hand
        state = _make_state()
        host = _place(state, "P1", _get_card(repo, "SOR", "140"), "ground")
        state, upg = self._attach_traitorous(state, repo, host)
        assert self._in_arena(state, "P0", host.instance_id)
        state = _apply_return_to_hand(state, upg.instance_id)  # bounce Traitorous
        assert self._in_arena(state, "P1", host.instance_id), "owner reclaims when upgrade bounced"
        moved = _find_instance(state, host.instance_id)
        assert moved.control_linked_to is None

    def test_SOR_122_no_longer_escape_hatch(self):
        from swu.abilities.registry import is_escape_hatch
        import swu.cards.sor  # noqa: F401
        assert not is_escape_hatch("SOR", "122")


class TestBibFortunaSOR177:
    """SOR_177 — Bib Fortuna: "Action [Exhaust]: Play an event from your hand. It
    costs 1 resource less."  The former escalation of sor-set:19 (play-EVENT-from-hand).
    """

    def _setup(self, repo, *, event=True, unit_in_hand=False, resources=10):
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        bib = _get_card(repo, "SOR", "177")
        bib_ci = _place(state, "P0", bib, "ground")
        bib_ci.exhausted = False
        ev_ci = None
        if event:
            ev = _get_card(repo, "SOR", "171")  # Mission Briefing (Event, cost 3, Draw 2)
            ev_ci = CardInstance("p0_ev", ev, "P0", Zone.HAND)
            state.players[0].hand.append(ev_ci)
        if unit_in_hand:
            u = _get_card(repo, "SOR", "128")   # Death Star Stormtrooper (Unit)
            state.players[0].hand.append(CardInstance("p0_u", u, "P0", Zone.HAND))
        # Give the deck some cards so Mission Briefing's draw has material.
        for _ in range(3):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        _give_resources(state, "P0", resources)
        return state, bib_ci, ev_ci

    def _use_bib(self, state, bib_ci):
        from swu.engine.actions import legal_actions, apply, UseAbility
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == bib_ci.instance_id)
        return apply(state, use)

    def test_SOR_177_ability_exhausts_and_pushes_play_event(self, repo):
        state, bib_ci, ev_ci = self._setup(repo)
        state = self._use_bib(state, bib_ci)
        assert state.pending_decisions[-1].kind == "play_event_from_hand"
        bib_now = _find_instance(state, bib_ci.instance_id)
        assert bib_now is not None and bib_now.exhausted, "Bib pays its exhaust cost"

    def test_SOR_177_only_events_offered(self, repo):
        from swu.engine.actions import legal_actions, PlayEventFromHand
        state, bib_ci, ev_ci = self._setup(repo, unit_in_hand=True)
        state = self._use_bib(state, bib_ci)
        offered = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, PlayEventFromHand)}
        assert offered == {ev_ci.instance_id}, "only the event is playable, not the unit"

    def test_SOR_177_plays_event_at_one_less_and_resolves(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayEventFromHand, _play_cost
        state, bib_ci, ev_ci = self._setup(repo, resources=10)
        before = state.players[0].available_resources
        # Expected discount: full effective cost (incl. any aspect penalty) less 1.
        expected = max(0, _play_cost(state, ev_ci, state.players[0]) - 1)
        state = self._use_bib(state, bib_ci)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayEventFromHand) and a.instance_id == ev_ci.instance_id)
        state = apply(state, play)
        state = _drain_forced(state)
        assert state.players[0].available_resources == before - expected, "event costs 1 less"
        # event is in the discard, no longer in hand
        assert any(c.instance_id == ev_ci.instance_id for c in state.players[0].discard)
        assert not any(c.instance_id == ev_ci.instance_id for c in state.players[0].hand)
        # Mission Briefing drew 2 (deck had 3, hand net: −event +2)
        assert len(state.players[0].deck) == 1, "drew 2 of the 3 deck cards"

    def test_SOR_177_not_offered_without_affordable_event(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        # No event in hand at all → the gate withholds the action.
        state, bib_ci, _ = self._setup(repo, event=False, unit_in_hand=True)
        assert not any(
            isinstance(a, UseAbility) and a.source_id == bib_ci.instance_id
            for a in legal_actions(state)), "no event → Bib's action is not offered"
        # An event in hand but too expensive even at −1 → still not offered.
        state, bib_ci, _ = self._setup(repo, event=True, resources=1)
        assert not any(
            isinstance(a, UseAbility) and a.source_id == bib_ci.instance_id
            for a in legal_actions(state)), "unaffordable event → not offered"

    def test_SOR_177_no_longer_escape_hatch(self):
        from swu.abilities.registry import is_escape_hatch
        import swu.cards.sor  # noqa: F401
        assert not is_escape_hatch("SOR", "177")


class TestStrafingGunshipSOR212:
    """SOR_212 — Strafing Gunship: cross-arena attack (space → ground) + an
    attacker-scoped "defender gets −2/−0" debuff.  The former escalation of sor-set:19.
    """

    def _setup(self, repo):
        state = _make_state()  # ACTION phase, P0 active
        gun = _place(state, "P0", _get_card(repo, "SOR", "212"), "space")
        gun.exhausted = False
        wampa = _place(state, "P1", _get_card(repo, "SOR", "164"), "ground")  # vanilla 4/5
        return state, gun, wampa

    def test_SOR_212_can_attack_ground_from_space(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state, gun, wampa = self._setup(repo)
        assert any(
            isinstance(a, AttackWithUnit) and a.attacker_id == gun.instance_id
            and a.defender_id == wampa.instance_id
            for a in legal_actions(state)), "space gunship can attack a ground unit"

    def test_SOR_212_defender_minus_2_only_from_this_attacker(self, repo):
        from swu.engine.actions import compute_power
        state, gun, wampa = self._setup(repo)
        base = compute_power(state, wampa)
        assert compute_power(state, wampa, is_defending=True,
                             attacker_id=gun.instance_id) == base - 2, \
            "the gunship's attack debuffs its ground defender by 2 power"
        # A DIFFERENT friendly attacker does not carry the debuff (attacker-scoped).
        other = _place(state, "P0", _get_card(repo, "SOR", "164"), "ground")
        assert compute_power(state, wampa, is_defending=True,
                             attacker_id=other.instance_id) == base, \
            "another attacker gets no debuff"
        # No combat context at all → no debuff.
        assert compute_power(state, wampa) == base

    def test_SOR_212_debuff_applies_in_combat(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state, gun, wampa = self._setup(repo)
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == gun.instance_id
                   and a.defender_id == wampa.instance_id)
        state = apply(state, atk)
        state = _drain_forced(state)
        g = _find_instance(state, gun.instance_id)
        # Wampa's 4 power → 2 after the debuff; the 4-HP gunship survives with 2 damage.
        assert g is not None, "gunship survives (Wampa's debuffed 2 < 4 HP)"
        assert g.damage == 2, "gunship took Wampa's debuffed 2 combat damage"
        w = _find_instance(state, wampa.instance_id)
        assert w is not None and w.damage == 3, "Wampa took the gunship's 3 power"

    def test_SOR_212_no_longer_escape_hatch(self):
        from swu.abilities.registry import is_escape_hatch
        import swu.cards.sor  # noqa: F401
        assert not is_escape_hatch("SOR", "212")
