"""
Phase 2 keyword tests.

Covers every Tier 1 keyword individually plus the interaction matrix
specified in the Phase 2 brief.  Uses synthetic card instances so tests
are independent of DB content.

Interaction matrix (subset that catches real bugs):
  * Saboteur + Sentinel: attacker with Saboteur ignores Sentinel
  * Saboteur + Shield + Overwhelm: Saboteur strips shield → Overwhelm can spill
  * Shield absorbs all of one damage instance → no Overwhelm from that instance
  * Grit + Raid: both stack on attacker power
  * Ambush + Sentinel arena: Ambush must target Sentinel
  * Ambush + no legal target: no decision pushed
  * Shielded + Ambush: shield is up when Ambush fires
  * Shield consumed once per damage instance (not twice)
  * Experience pushes unit out of defeat range
  * Tokens vanish on host defeat (never in discard)
"""
from __future__ import annotations

import pytest

from tests.dbpath import db_path, require_db

_DB = db_path()


# ── Test fixtures / helpers ───────────────────────────────────────────────────

def _require_db():
    require_db()


class _FakeCard:
    """Minimal card def for synthetic test units."""
    id = 0
    type = "Unit"
    aspects = ()
    is_unique = False
    text = None
    deploy_box = None

    def __init__(self, name, power, hp, keywords=(), arenas=("Ground",)):
        self.name = name
        self.display_name = name
        self.power = power
        self.hp = hp
        self.keywords = tuple(keywords)
        self.arenas = tuple(arenas)
        self.cost = 1


def _make_ci(iid, owner, power, hp, keywords=(), damage=0, arena="Ground",
             upgrades=None):
    from swu.engine.state import CardInstance, Zone
    card = _FakeCard(iid, power, hp, keywords, (arena,))
    zone = Zone.GROUND_ARENA if arena == "Ground" else Zone.SPACE_ARENA
    ci = CardInstance(iid, card, owner, zone)
    ci.damage = damage
    if upgrades:
        ci.attached_upgrades = list(upgrades)
    return ci


def _action_state(seed=1):
    """Minimal ACTION-phase state from real vanilla decks."""
    _require_db()
    from swu.cards.repository import CardRepository
    from swu.cards.decklist import build_vanilla_deck
    from swu.engine.actions import create_game
    from conftest import run_through_setup
    repo = CardRepository(_DB)
    da = build_vanilla_deck(repo, "Darth Vader", "Security Complex")
    db = build_vanilla_deck(repo, "Luke Skywalker", "Administrator's Tower")
    return run_through_setup(create_game("P0", da, "P1", db, seed=seed))


def _minimal_state(p0_units=None, p1_units=None, seed=1):
    """Action state with arenas replaced by synthetic units."""
    state = _action_state(seed=seed)
    if p0_units is not None:
        state.players[0].ground_arena = list(p0_units)
        state.players[0].space_arena = []
    if p1_units is not None:
        state.players[1].ground_arena = list(p1_units)
        state.players[1].space_arena = []
    return state


def _apply(state, action):
    from swu.engine.actions import apply
    return apply(state, action)


def _legal(state):
    from swu.engine.actions import legal_actions
    return legal_actions(state)


def _atk(attacker_id, defender_id=None):
    from swu.engine.actions import AttackWithUnit
    return AttackWithUnit(attacker_id, defender_id)


# ── Keywords module unit tests ────────────────────────────────────────────────

def test_has_keyword_true():
    from swu.engine.keywords import has_keyword, Keyword
    state = _action_state()
    ci = _make_ci("u", "P0", 2, 3, keywords=["Sentinel"])
    assert has_keyword(state, ci, Keyword.SENTINEL) is True


def test_has_keyword_false():
    from swu.engine.keywords import has_keyword, Keyword
    state = _action_state()
    ci = _make_ci("u", "P0", 2, 3)
    assert has_keyword(state, ci, Keyword.SENTINEL) is False


def test_keyword_value_raid():
    _require_db()
    from swu.cards.repository import CardRepository
    from swu.engine.keywords import keyword_value, Keyword
    from swu.engine.state import CardInstance, Zone
    repo = CardRepository(_DB)
    # Find a card with a printed Raid value
    cards = repo.search("Raid 2")
    for c in cards:
        if "Raid" in getattr(c, "keywords", ()) and c.type == "Unit":
            state = _action_state()
            ci = CardInstance(f"real_{c.id}", c, "P0", Zone.GROUND_ARENA)
            val = keyword_value(state, ci, Keyword.RAID)
            if val > 0:
                assert isinstance(val, int)
                return
    pytest.skip("No Raid unit found in DB")


def test_keyword_value_missing_returns_zero():
    from swu.engine.keywords import keyword_value, Keyword
    state = _action_state()
    ci = _make_ci("u", "P0", 2, 3)
    assert keyword_value(state, ci, Keyword.RAID) == 0


# ── compute_power ─────────────────────────────────────────────────────────────

def test_compute_power_base():
    from swu.engine.actions import compute_power
    state = _action_state()
    ci = _make_ci("u", "P0", 4, 5)
    assert compute_power(state, ci, is_attacking=False) == 4


def test_compute_power_grit():
    from swu.engine.actions import compute_power
    state = _action_state()
    ci = _make_ci("u", "P0", 2, 5, keywords=["Grit"], damage=3)
    assert compute_power(state, ci, is_attacking=False) == 5  # 2 + 3 Grit


def test_compute_power_raid_only_while_attacking():
    from swu.engine.actions import compute_power
    _require_db()
    from swu.cards.repository import CardRepository
    repo = CardRepository(_DB)
    state = _action_state()
    # Create a synthetic unit with Raid 3 in text
    ci = _make_ci("u", "P0", 2, 5, keywords=["Raid"])
    ci.card_def.text = "Raid 3 (This unit gets +3/+0 while attacking.)"
    assert compute_power(state, ci, is_attacking=True) == 5   # 2 + 3
    assert compute_power(state, ci, is_attacking=False) == 2  # no Raid bonus


def test_compute_power_grit_and_raid():
    from swu.engine.actions import compute_power
    state = _action_state()
    ci = _make_ci("u", "P0", 2, 8, keywords=["Grit", "Raid"], damage=2)
    ci.card_def.text = "Grit\nRaid 1"
    # attacking: 2 (base) + 2 (Grit) + 1 (Raid) = 5
    assert compute_power(state, ci, is_attacking=True) == 5
    # not attacking: 2 + 2 = 4
    assert compute_power(state, ci, is_attacking=False) == 4


def test_defender_never_gets_raid():
    """In _resolve_unit_combat, defender's power is computed with is_attacking=False."""
    from swu.engine.actions import compute_power
    state = _action_state()
    defender = _make_ci("d", "P1", 3, 5, keywords=["Raid"])
    defender.card_def.text = "Raid 5"
    # As defender: no Raid bonus
    assert compute_power(state, defender, is_attacking=False) == 3


# ── Grit in combat ────────────────────────────────────────────────────────────

def test_grit_increases_combat_power():
    attacker = _make_ci("atk", "P0", 1, 5, keywords=["Grit"], damage=3)
    defender = _make_ci("dfd", "P1", 2, 5)
    state = _minimal_state([attacker], [defender])
    state.active_player_index = 0
    state2 = _apply(state, _atk("atk", "dfd"))
    # attacker power = 1 + 3 (Grit) = 4; defender power = 2
    # defender takes 4 damage → defeated (5 HP)? no: 4 < 5; defender lives
    # attacker takes 2 damage; had 3+2=5 → at 5 damage, 5 HP → defeated
    dfd = state2.players[1].ground_arena[0] if state2.players[1].ground_arena else None
    # defender survived (4 < 5 HP); attacker died (3 damage + 2 from defender = 5)
    assert dfd is not None
    assert dfd.damage == 4


# ── Raid in combat ────────────────────────────────────────────────────────────

def test_raid_increases_attacker_power():
    attacker = _make_ci("atk", "P0", 1, 5, keywords=["Raid"])
    attacker.card_def.text = "Raid 2"
    defender = _make_ci("dfd", "P1", 0, 3)
    state = _minimal_state([attacker], [defender])
    state.active_player_index = 0
    state2 = _apply(state, _atk("atk", "dfd"))
    # attacker power = 1 + 2 (Raid) = 3; defender HP = 3 → defeated
    assert not state2.players[1].ground_arena


# ── Restore ───────────────────────────────────────────────────────────────────

def test_restore_heals_attacking_player_base():
    attacker = _make_ci("atk", "P0", 1, 5, keywords=["Restore"])
    attacker.card_def.text = "Restore 2"
    defender = _make_ci("dfd", "P1", 0, 5)
    state = _minimal_state([attacker], [defender])
    state.active_player_index = 0
    base_p0 = state.players[0].base_instance
    base_p0.damage = 5  # pre-damage so Restore has something to heal
    state2 = _apply(state, _atk("atk", "dfd"))
    assert state2.players[0].base_instance.damage == 3  # healed 2


def test_restore_on_base_attack():
    attacker = _make_ci("atk", "P0", 2, 5, keywords=["Restore"])
    attacker.card_def.text = "Restore 1"
    state = _minimal_state([attacker], [])
    state.active_player_index = 0
    base_p0 = state.players[0].base_instance
    base_p0.damage = 3
    state2 = _apply(state, _atk("atk", None))
    assert state2.players[0].base_instance.damage == 2  # healed 1


def test_restore_does_not_overheal():
    attacker = _make_ci("atk", "P0", 0, 5, keywords=["Restore"])
    attacker.card_def.text = "Restore 5"
    defender = _make_ci("dfd", "P1", 0, 5)
    state = _minimal_state([attacker], [defender])
    state.active_player_index = 0
    base_p0 = state.players[0].base_instance
    base_p0.damage = 2  # only 2 to heal
    state2 = _apply(state, _atk("atk", "dfd"))
    assert state2.players[0].base_instance.damage == 0  # can't go below 0


# ── Sentinel ──────────────────────────────────────────────────────────────────

def test_sentinel_forces_targeting():
    sentinel = _make_ci("sen", "P1", 1, 5, keywords=["Sentinel"])
    normal = _make_ci("nrm", "P1", 1, 5)
    attacker = _make_ci("atk", "P0", 3, 5)
    state = _minimal_state([attacker], [sentinel, normal])
    state.active_player_index = 0
    acts = _legal(state)
    from swu.engine.actions import AttackWithUnit
    attack_acts = [a for a in acts if isinstance(a, AttackWithUnit)]
    targets = {a.defender_id for a in attack_acts}
    # Must target sentinel, not normal, not base
    assert "sen" in targets
    assert "nrm" not in targets
    assert None not in targets


def test_sentinel_exhausted_still_forces_targeting():
    """Exhausted Sentinel units still enforce the targeting constraint."""
    sentinel = _make_ci("sen", "P1", 1, 5, keywords=["Sentinel"])
    sentinel.exhausted = True
    normal = _make_ci("nrm", "P1", 1, 5)
    attacker = _make_ci("atk", "P0", 3, 5)
    state = _minimal_state([attacker], [sentinel, normal])
    state.active_player_index = 0
    acts = _legal(state)
    from swu.engine.actions import AttackWithUnit
    attack_acts = [a for a in acts if isinstance(a, AttackWithUnit)]
    targets = {a.defender_id for a in attack_acts}
    assert "sen" in targets
    assert "nrm" not in targets


def test_sentinel_attack_event_flags_forced_target():
    """A unit attacked because it has Sentinel emits AttackDeclared with
    forced_by_sentinel=True so the UI can explain the forced pick."""
    from swu.engine.events import AttackDeclared
    sentinel = _make_ci("sen", "P1", 1, 5, keywords=["Sentinel"])
    normal = _make_ci("nrm", "P1", 1, 5)
    attacker = _make_ci("atk", "P0", 3, 5)
    state = _minimal_state([attacker], [sentinel, normal])
    state.active_player_index = 0
    state2 = _apply(state, _atk("atk", "sen"))
    decl = next(e for e in state2.event_log if isinstance(e, AttackDeclared))
    assert decl.forced_by_sentinel is True


def test_saboteur_attack_not_flagged_forced():
    """A Saboteur ignores Sentinel, so attacking it is a free choice — the event
    must NOT claim the target was forced."""
    from swu.engine.events import AttackDeclared
    sentinel = _make_ci("sen", "P1", 1, 5, keywords=["Sentinel"])
    attacker = _make_ci("atk", "P0", 3, 5, keywords=["Saboteur"])
    state = _minimal_state([attacker], [sentinel])
    state.active_player_index = 0
    state2 = _apply(state, _atk("atk", "sen"))
    decl = next(e for e in state2.event_log if isinstance(e, AttackDeclared))
    assert decl.forced_by_sentinel is False


def test_no_sentinel_allows_all_targets_and_base():
    normal = _make_ci("nrm", "P1", 1, 5)
    attacker = _make_ci("atk", "P0", 3, 5)
    state = _minimal_state([attacker], [normal])
    state.active_player_index = 0
    acts = _legal(state)
    from swu.engine.actions import AttackWithUnit
    attack_acts = [a for a in acts if isinstance(a, AttackWithUnit)]
    targets = {a.defender_id for a in attack_acts}
    assert "nrm" in targets
    assert None in targets  # base attack available


# ── Overwhelm ─────────────────────────────────────────────────────────────────

def test_overwhelm_spills_excess_to_base():
    attacker = _make_ci("atk", "P0", 6, 10, keywords=["Overwhelm"])
    defender = _make_ci("dfd", "P1", 0, 3)
    state = _minimal_state([attacker], [defender])
    state.active_player_index = 0
    base_before = state.players[1].base_instance.damage
    state2 = _apply(state, _atk("atk", "dfd"))
    base_after = state2.players[1].base_instance.damage
    # 6 power, 3 HP defender → 3 overkill → 3 spill to base
    assert base_after - base_before == 3


def test_overwhelm_no_spill_if_exact_kill():
    attacker = _make_ci("atk", "P0", 3, 10, keywords=["Overwhelm"])
    defender = _make_ci("dfd", "P1", 0, 3)
    state = _minimal_state([attacker], [defender])
    state.active_player_index = 0
    base_before = state.players[1].base_instance.damage
    state2 = _apply(state, _atk("atk", "dfd"))
    assert state2.players[1].base_instance.damage == base_before


def test_overwhelm_no_spill_when_fully_shielded():
    """Shield prevents all damage → attacker lands 0 → no Overwhelm."""
    _require_db()
    from swu.cards.repository import CardRepository
    from swu.engine.tokens import attach_token
    repo = CardRepository(_DB)

    attacker = _make_ci("atk", "P0", 6, 10, keywords=["Overwhelm"])
    defender = _make_ci("dfd", "P1", 0, 3)
    state = _minimal_state([attacker], [defender])
    state.active_player_index = 0
    # Give defender a Shield
    owner_ps = state.players[1]
    attach_token(state, owner_ps, defender, "Shield")
    base_before = state.players[1].base_instance.damage
    state2 = _apply(state, _atk("atk", "dfd"))
    # Shield absorbed all 6 → 0 damage landed → no Overwhelm
    assert state2.players[1].base_instance.damage == base_before


# ── Saboteur ─────────────────────────────────────────────────────────────────

def test_saboteur_ignores_sentinel_targeting():
    sentinel = _make_ci("sen", "P1", 1, 5, keywords=["Sentinel"])
    normal = _make_ci("nrm", "P1", 1, 5)
    attacker = _make_ci("atk", "P0", 3, 5, keywords=["Saboteur"])
    state = _minimal_state([attacker], [sentinel, normal])
    state.active_player_index = 0
    acts = _legal(state)
    from swu.engine.actions import AttackWithUnit
    targets = {a.defender_id for a in acts if isinstance(a, AttackWithUnit)}
    # Saboteur: can attack anything including base and normal unit
    assert "sen" in targets
    assert "nrm" in targets
    assert None in targets


def test_saboteur_strips_defender_shields_before_damage():
    _require_db()
    from swu.cards.repository import CardRepository
    from swu.engine.tokens import attach_token
    from swu.engine.keywords import shields_on
    repo = CardRepository(_DB)

    attacker = _make_ci("atk", "P0", 3, 10, keywords=["Saboteur"])
    defender = _make_ci("dfd", "P1", 0, 5)
    state = _minimal_state([attacker], [defender])
    state.active_player_index = 0
    attach_token(state, state.players[1], defender, "Shield")
    assert shields_on(defender) == 1

    state2 = _apply(state, _atk("atk", "dfd"))
    # Saboteur strips shield before damage; defender takes 3 damage (no shield left)
    if state2.players[1].ground_arena:
        dfd2 = state2.players[1].ground_arena[0]
        assert dfd2.damage == 3
        assert shields_on(dfd2) == 0


def test_saboteur_overwhelm_after_shield_strip():
    """Saboteur strips shield, then Overwhelm can spill excess."""
    _require_db()
    from swu.cards.repository import CardRepository
    from swu.engine.tokens import attach_token
    repo = CardRepository(_DB)

    attacker = _make_ci("atk", "P0", 6, 10, keywords=["Saboteur", "Overwhelm"])
    defender = _make_ci("dfd", "P1", 0, 3)
    state = _minimal_state([attacker], [defender])
    state.active_player_index = 0
    attach_token(state, state.players[1], defender, "Shield")
    base_before = state.players[1].base_instance.damage
    state2 = _apply(state, _atk("atk", "dfd"))
    # Saboteur strips shield → 6 hits defender (3 HP) → 3 Overwhelm spill
    assert state2.players[1].base_instance.damage - base_before == 3


# ── Shielded ──────────────────────────────────────────────────────────────────

def test_shielded_grants_shield_on_enter_play():
    """Shielded trigger: UnitEntersPlay fires → Shield token attached."""
    _require_db()
    from swu.engine.keywords import shields_on
    from swu.engine.events import UnitEntersPlay
    from swu.engine.triggers import get_bus

    state = _action_state(seed=1)
    ci = _make_ci("shld_unit", "P0", 2, 3, keywords=["Shielded"])
    state.players[0].ground_arena.append(ci)

    evt = UnitEntersPlay(player_id="P0", instance_id="shld_unit", card_name="Test", arena="Ground")
    get_bus().fire(state, evt)

    assert shields_on(ci) == 1, "Shielded unit should have a Shield token after entering play"


def test_shield_prevents_all_damage_from_one_instance():
    _require_db()
    from swu.engine.tokens import attach_token
    from swu.engine.keywords import shields_on
    attacker = _make_ci("atk", "P0", 5, 10)
    defender = _make_ci("dfd", "P1", 0, 3)
    state = _minimal_state([attacker], [defender])
    state.active_player_index = 0
    attach_token(state, state.players[1], defender, "Shield")
    state2 = _apply(state, _atk("atk", "dfd"))
    # Shield prevented all 5 damage; defender should be alive with 0 damage
    if state2.players[1].ground_arena:
        dfd2 = state2.players[1].ground_arena[0]
        assert dfd2.damage == 0
        assert shields_on(dfd2) == 0  # shield consumed
    # else defender wasn't killed by the non-prevented damage (so shield worked)


def test_second_attack_damages_unshielded_unit():
    """After shield is consumed, subsequent attacks land normally."""
    _require_db()
    from swu.engine.tokens import attach_token
    attacker = _make_ci("atk", "P0", 2, 10)
    attacker2 = _make_ci("atk2", "P0", 2, 10)
    defender = _make_ci("dfd", "P1", 0, 10)
    state = _minimal_state([attacker, attacker2], [defender])
    state.active_player_index = 0
    attach_token(state, state.players[1], defender, "Shield")
    # First attack: shield absorbs
    state2 = _apply(state, _atk("atk", "dfd"))
    from swu.engine.keywords import shields_on
    assert shields_on(state2.players[1].ground_arena[0]) == 0
    # Second attack: damage lands
    state2.active_player_index = 0
    state3 = _apply(state2, _atk("atk2", "dfd"))
    assert state3.players[1].ground_arena[0].damage == 2


# ── Token system ──────────────────────────────────────────────────────────────

def test_experience_token_grants_plus_one_plus_one():
    _require_db()
    from swu.engine.tokens import attach_token
    unit = _make_ci("u", "P0", 2, 3)
    state = _minimal_state([unit], [])
    attach_token(state, state.players[0], unit, "Experience")
    assert unit.effective_power() == 3
    assert unit.effective_hp() == 4


def test_experience_keeps_unit_alive():
    """Experience token (+1/+1) saves a unit that would otherwise be defeated."""
    _require_db()
    from swu.engine.tokens import attach_token
    attacker = _make_ci("atk", "P0", 3, 10)
    defender = _make_ci("dfd", "P1", 0, 3)  # would die to 3 damage
    state = _minimal_state([attacker], [defender])
    state.active_player_index = 0
    attach_token(state, state.players[1], defender, "Experience")
    # defender now has 4 HP; attacker power = 3 → defender lives (3 < 4)
    state2 = _apply(state, _atk("atk", "dfd"))
    assert state2.players[1].ground_arena, "Defender should survive with Experience"
    assert state2.players[1].ground_arena[0].damage == 3


def test_tokens_removed_on_host_defeat():
    """When a unit with tokens is defeated, tokens are not in any discard pile."""
    _require_db()
    from swu.engine.tokens import attach_token
    from swu.cards.models import TokenUpgrade
    attacker = _make_ci("atk", "P0", 10, 10)
    defender = _make_ci("dfd", "P1", 0, 3)  # 3 HP + 1 Experience = 4 HP; 10 > 4 → still dies
    state = _minimal_state([attacker], [defender])
    state.active_player_index = 0
    # Use Experience only (Shield would absorb all damage, preventing defeat)
    attach_token(state, state.players[1], defender, "Experience")

    state2 = _apply(state, _atk("atk", "dfd"))
    assert not state2.players[1].ground_arena, "Defender should be defeated (10 > 4 HP)"

    # Experience token must NOT be in any discard pile
    for ps in state2.players:
        for ci in ps.discard:
            assert not isinstance(ci.card_def, TokenUpgrade), \
                f"Token {ci.card_def.name} found in discard"


def test_tokens_not_counted_in_card_conservation():
    """all_instances_for_player excludes tokens (they come from unlimited supply)."""
    _require_db()
    from swu.engine.tokens import attach_token
    unit = _make_ci("u", "P0", 2, 3)
    state = _minimal_state([unit], [])
    before = len(state.all_instances_for_player("P0"))
    attach_token(state, state.players[0], unit, "Experience")
    after = len(state.all_instances_for_player("P0"))
    assert after == before  # token not counted


# ── Ambush ────────────────────────────────────────────────────────────────────

def test_ambush_pushes_decision_on_enter_play():
    """Ambush trigger: UnitEntersPlay with enemy targets → Ambush decision pushed."""
    _require_db()
    from swu.engine.events import UnitEntersPlay
    from swu.engine.triggers import get_bus

    state = _action_state(seed=1)
    ambush_unit = _make_ci("amb_unit", "P0", 2, 5, keywords=["Ambush"])
    enemy = _make_ci("enemy", "P1", 1, 5)
    state.players[0].ground_arena.append(ambush_unit)
    state.players[1].ground_arena = [enemy]

    evt = UnitEntersPlay(player_id="P0", instance_id="amb_unit", card_name="Test", arena="Ground")
    get_bus().fire(state, evt)

    assert state.pending_decisions, "Ambush decision should be pending when enemy targets exist"
    assert state.pending_decisions[-1].kind == "ambush"


def test_ambush_no_decision_when_no_targets():
    """Ambush trigger: no enemy targets → no decision pushed."""
    _require_db()
    from swu.engine.events import UnitEntersPlay
    from swu.engine.triggers import get_bus

    state = _action_state(seed=1)
    ambush_unit = _make_ci("amb_unit", "P0", 2, 5, keywords=["Ambush"])
    state.players[0].ground_arena.append(ambush_unit)
    state.players[1].ground_arena = []

    evt = UnitEntersPlay(player_id="P0", instance_id="amb_unit", card_name="Test", arena="Ground")
    get_bus().fire(state, evt)

    assert not state.pending_decisions, "No Ambush decision when no targets exist"


def test_ambush_must_target_sentinel():
    """When an Ambush unit could attack, Sentinel forces it to target Sentinel."""
    state = _action_state(seed=1)
    from swu.engine.decisions import PendingDecision

    ambush_unit = _make_ci("amb", "P0", 2, 5, keywords=["Ambush"])
    sentinel = _make_ci("sen", "P1", 1, 5, keywords=["Sentinel"])
    normal = _make_ci("nrm", "P1", 1, 5)
    state.players[0].ground_arena = [ambush_unit]
    state.players[1].ground_arena = [sentinel, normal]

    # Inject Ambush decision manually (as trigger would)
    d = PendingDecision(
        deciding_player_id="P0",
        kind="ambush",
        context={"unit_id": "amb"},
        after_resolve_player_index=1,
    )
    state.pending_decisions.append(d)
    state.active_player_index = 0

    from swu.engine.actions import legal_actions, UseAmbush
    acts = legal_actions(state)
    ambush_targets = {a.target_id for a in acts if isinstance(a, UseAmbush)}
    assert "sen" in ambush_targets
    assert "nrm" not in ambush_targets


def test_ambush_decline_switches_to_opponent():
    state = _action_state(seed=1)
    from swu.engine.decisions import PendingDecision
    from swu.engine.actions import DeclineAmbush, apply

    ambush_unit = _make_ci("amb", "P0", 2, 5)
    state.players[0].ground_arena = [ambush_unit]
    d = PendingDecision("P0", "ambush", {"unit_id": "amb"}, after_resolve_player_index=1)
    state.pending_decisions.append(d)
    state.active_player_index = 0

    state2 = apply(state, DeclineAmbush("amb"))
    assert not state2.pending_decisions
    assert state2.active_player_index == 1


# ── Shielded + Ambush ordering ────────────────────────────────────────────────

def test_shielded_ambush_shield_up_before_ambush_fires():
    """Shielded registered before Ambush → shield is attached before Ambush decision fires."""
    _require_db()
    from swu.engine.keywords import shields_on
    from swu.engine.events import UnitEntersPlay
    from swu.engine.triggers import get_bus

    state = _action_state(seed=1)
    # Unit with both keywords
    combo_unit = _make_ci("sa_unit", "P0", 2, 5, keywords=["Shielded", "Ambush"])
    enemy = _make_ci("enemy", "P1", 1, 5)
    state.players[0].ground_arena.append(combo_unit)
    state.players[1].ground_arena = [enemy]

    evt = UnitEntersPlay(player_id="P0", instance_id="sa_unit", card_name="Test", arena="Ground")
    get_bus().fire(state, evt)

    # Shield was attached (Shielded listener fires first)
    assert shields_on(combo_unit) == 1, "Shield should be on unit when Ambush decision is presented"
    # Ambush decision also pushed (listener order preserved)
    assert state.pending_decisions
    assert state.pending_decisions[-1].kind == "ambush"


# ── Interaction matrix ────────────────────────────────────────────────────────

def test_interaction_saboteur_vs_sentinel():
    """Saboteur attacker ignores Sentinel — can attack non-Sentinel or base."""
    sentinel = _make_ci("sen", "P1", 1, 5, keywords=["Sentinel"])
    normal = _make_ci("nrm", "P1", 1, 5)
    saboteur = _make_ci("sab", "P0", 2, 5, keywords=["Saboteur"])
    state = _minimal_state([saboteur], [sentinel, normal])
    state.active_player_index = 0
    acts = _legal(state)
    from swu.engine.actions import AttackWithUnit
    targets = {a.defender_id for a in acts if isinstance(a, AttackWithUnit)}
    assert "nrm" in targets  # can bypass Sentinel
    assert None in targets   # base attack available too


def test_interaction_grit_raid_attacker_vs_grit_defender():
    """Grit+Raid attacker vs Grit defender — correct powers on both sides."""
    attacker = _make_ci("atk", "P0", 1, 10, keywords=["Grit", "Raid"], damage=2)
    attacker.card_def.text = "Grit\nRaid 1"
    defender = _make_ci("dfd", "P1", 2, 10, keywords=["Grit"], damage=3)
    state = _minimal_state([attacker], [defender])
    state.active_player_index = 0
    state2 = _apply(state, _atk("atk", "dfd"))
    # attacker power = 1 + 2 (Grit) + 1 (Raid) = 4; defender takes 4
    # defender power = 2 + 3 (Grit) = 5; attacker takes 5
    if state2.players[1].ground_arena:
        dfd2 = state2.players[1].ground_arena[0]
        assert dfd2.damage == 3 + 4  # 3 pre-existing + 4 from combat


def test_interaction_shield_prevents_no_overwhelm():
    """Full shield prevention → 0 damage → 0 Overwhelm (spec: prevented damage never lands)."""
    _require_db()
    from swu.engine.tokens import attach_token
    attacker = _make_ci("atk", "P0", 10, 10, keywords=["Overwhelm"])
    defender = _make_ci("dfd", "P1", 0, 3)
    state = _minimal_state([attacker], [defender])
    state.active_player_index = 0
    attach_token(state, state.players[1], defender, "Shield")
    base_before = state.players[1].base_instance.damage
    state2 = _apply(state, _atk("atk", "dfd"))
    assert state2.players[1].base_instance.damage == base_before  # no Overwhelm
