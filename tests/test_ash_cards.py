"""ASH card ability tests — the ``ash-set:01`` Support-residual batch.

One focused test per card, asserting behaviour through the public engine interfaces
(``legal_actions`` / ``apply`` / trigger firing).  Method names embed the card number
so the encoding verifier's ``-k`` gate selects them.

Reuses the DB-backed game-state helpers from the SOR card tests.
"""
from __future__ import annotations

import pytest

from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _get_card, _make_state, _place, _place_leader, _push_deck_top,
    _fire_on_attack, _fire_when_defeated, _fire_when_played, _find_instance,
    _fire_upgrade_played,
    _shield_count, _add_resource, _play_event_from_hand,
)

# Vanilla stand-ins (no text, no keywords), so a test asserts only the card under it.
VANILLA_GROUND = ("SOR", "46")    # Consular Security Force 3/7
VANILLA_SPACE = ("JTL", "95")     # Phoenix Squadron A-Wing 3/2
BIG_SPACE = ("JTL", "69")         # Munificent Frigate 4/7
VANILLA_WEAK = ("SOR", "247")     # Underworld Thug 2/3, cost 2


# ── Local helpers ────────────────────────────────────────────────────────────

def _get_by_type(repo, set_code, number, type_name):
    """Fetch the (set, number) row of a given card TYPE — ``_get_card`` returns
    whatever row matches first, and a low number is often shared with a token."""
    with repo._con() as con:
        row = con.execute(
            "SELECT * FROM cards WHERE set_code=? AND card_number=? AND type=?",
            (set_code, str(int(number)), type_name)).fetchone()
        from tests.dbpath import require_row
        row = require_row(row, f"{set_code}_{number} ({type_name})")
        return repo._hydrate(con, row)


def _drive(state, picker=None, limit=40):
    """Apply actions until nothing is pending.  ``picker(state, acts)`` may return
    the action to take; otherwise the first legal one is applied."""
    from swu.engine.actions import legal_actions, apply
    guard = 0
    while state.pending_decisions and guard < limit:
        guard += 1
        acts = legal_actions(state)
        choice = picker(state, acts) if picker else None
        state = apply(state, choice or acts[0])
    return state


def _drive_until(state, kind, picker=None, limit=40):
    """Apply actions until the TOP pending decision is of ``kind`` (or nothing is
    pending) — so a test can inspect that decision's options instead of ``_drive``
    running straight through it."""
    from swu.engine.actions import legal_actions, apply
    guard = 0
    while (state.pending_decisions
           and state.pending_decisions[-1].kind != kind and guard < limit):
        guard += 1
        acts = legal_actions(state)
        choice = picker(state, acts) if picker else None
        state = apply(state, choice or acts[0])
    return state


def _accept_and_target(target_ci=None):
    """Picker: accept every optional trigger, then pick ``target_ci`` (or the first
    real target) at each ChooseTarget."""
    from swu.engine.actions import AcceptTrigger, ChooseTarget

    def _pick(state, acts):
        for a in acts:
            if isinstance(a, AcceptTrigger):
                return a
        chooses = [a for a in acts if isinstance(a, ChooseTarget)
                   and getattr(a, "target_id", None)]
        if chooses:
            if target_ci is not None:
                for a in chooses:
                    if a.target_id == target_ci.instance_id:
                        return a
            return chooses[0]
        return None
    return _pick


def _target_ids(state):
    """The instance ids offered by the pending ChooseTarget decision."""
    from swu.engine.actions import legal_actions, ChooseTarget
    return {a.target_id for a in legal_actions(state)
            if isinstance(a, ChooseTarget) and getattr(a, "target_id", None)}


def _attach(state, host_ci, token_name="Experience"):
    from swu.engine import tokens
    ps = state.player_by_id(host_ci.owner_id)
    return tokens.attach_token(state, ps, host_ci, token_name)


def _advantage_count(ci):
    from swu.cards.models import TokenUpgrade
    return sum(1 for u in ci.attached_upgrades
               if isinstance(u.card_def, TokenUpgrade) and u.card_def.name == "Advantage")


def _attack(state, attacker, defender=None):
    from swu.engine.actions import apply, AttackWithUnit
    return apply(state, AttackWithUnit(attacker_id=attacker.instance_id,
                                       defender_id=(defender.instance_id
                                                    if defender else None)))


# ── ASH_8 Moff Gideon ────────────────────────────────────────────────────────

class TestMoffGideonASH8:
    """"This unit gains each of the following keywords if it is on an Imperial unit
    in your discard pile: Ambush, Grit, Hidden, Overwhelm, Saboteur, Sentinel,
    Shielded, Support" — eight conditional SELF KeywordGrants."""

    def test_ASH_8_gains_a_keyword_off_an_imperial_unit_in_discard(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        from swu.engine.state import Zone
        state = _make_state()
        gideon = _place(state, "P0", _get_by_type(repo, "ASH", "8", "Leader"), "ground")
        gideon.deployed = True
        # His printed eight-keyword bar is a mistag — sanitiser rule 2 strips it, so
        # with an empty discard he has none of them.
        assert gideon.card_def.keywords == ()
        assert not has_keyword(state, gideon, Keyword.SUPPORT)
        assert not has_keyword(state, gideon, Keyword.SENTINEL)

        # Rukh ASH_36 is an Imperial unit printing Support.
        rukh = _place(state, "P0", _get_card(repo, "ASH", "36"), "ground")
        state.player_by_id("P0").ground_arena.remove(rukh)
        rukh.zone = Zone.DISCARD
        state.player_by_id("P0").discard.append(rukh)

        assert has_keyword(state, gideon, Keyword.SUPPORT)
        assert not has_keyword(state, gideon, Keyword.SENTINEL)   # nothing grants it


# ── ASH_9 Ahsoka Tano ────────────────────────────────────────────────────────

class TestAhsokaTanoASH9:
    """Deployed On Attack: "You may give a unit with less power than this unit
    +2/+0 for this phase" (the ``power_lt_source`` predicate)."""

    def test_ASH_9_on_attack_offers_only_weaker_units(self, repo):
        from swu.engine.actions import compute_power, AcceptTrigger, legal_actions, apply
        state = _make_state()
        ahsoka = _place(state, "P0", _get_by_type(repo, "ASH", "9", "Leader"), "ground")
        ahsoka.deployed = True                                   # 5 power
        weak = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")   # 3
        strong = _place(state, "P1", _get_card(repo, "ASH", "101"), "ground")    # 6

        state = _fire_on_attack(state, ahsoka, weak)
        acts = legal_actions(state)
        accept = next(a for a in acts if isinstance(a, AcceptTrigger))
        state = apply(state, accept)

        offered = _target_ids(state)
        assert weak.instance_id in offered
        assert strong.instance_id not in offered
        assert ahsoka.instance_id not in offered      # 5 is not < 5

        before = compute_power(state, weak)
        state = _drive(state, _accept_and_target(weak))
        assert compute_power(state, _find_instance(state, weak.instance_id)) == before + 2


# ── ASH_14 The Mandalorian ───────────────────────────────────────────────────

class TestTheMandalorianASH14:
    """Deployed On Attack: "If you have the initiative, you may draw a card"."""

    def test_ASH_14_on_attack_draws_only_with_initiative(self, repo):
        from swu.engine.actions import AcceptTrigger, legal_actions, apply
        state = _make_state()
        mando = _place(state, "P0", _get_by_type(repo, "ASH", "14", "Leader"), "ground")
        mando.deployed = True
        _push_deck_top(state, "P0", _get_card(repo, *VANILLA_GROUND))
        state.initiative_holder = 1                    # P1 holds it → no trigger
        state = _fire_on_attack(state, mando, None)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert len(state.player_by_id("P0").hand) == 0

        state.initiative_holder = 0                    # P0 holds it → may draw
        state = _fire_on_attack(state, mando, None)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = _drive(apply(state, accept))
        assert len(state.player_by_id("P0").hand) == 1


# ── ASH_33 Grand Admiral Thrawn ──────────────────────────────────────────────

class TestGrandAdmiralThrawnASH33:
    """"When Attack Ends: If the defending unit was defeated, ready this unit" —
    the first WhenAttackEnds(require_defender_defeated=True)."""

    def test_ASH_33_readies_itself_when_the_defender_dies(self, repo):
        state = _make_state()
        thrawn = _place(state, "P0", _get_card(repo, "ASH", "33"), "ground")   # 5/7
        prey = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        prey.damage = 6                                   # 1 remaining HP → dies

        state = _drive(_attack(state, thrawn, prey))
        now = _find_instance(state, thrawn.instance_id)
        assert now is not None and not now.exhausted      # attacked, then readied

    def test_ASH_33_does_not_ready_when_the_defender_survives(self, repo):
        state = _make_state()
        thrawn = _place(state, "P0", _get_card(repo, "ASH", "33"), "ground")
        prey = _place(state, "P1", _get_card(repo, "ASH", "101"), "ground")   # 6/7
        state = _drive(_attack(state, thrawn, prey))
        assert _find_instance(state, thrawn.instance_id).exhausted


# ── ASH_36 Rukh + the Advantage token ────────────────────────────────────────

class TestRukhASH36:
    """"When Attack Ends: If the defending unit was defeated, you may give 3
    Advantage tokens to a unit" — the ASH set's Advantage token (ASH_2)."""

    def test_ASH_36_gives_three_advantage_tokens_on_a_kill(self, repo):
        state = _make_state()
        rukh = _place(state, "P0", _get_card(repo, "ASH", "36"), "ground")     # 1/5
        buddy = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        prey = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        prey.damage = 6                                   # 1 remaining HP → dies

        state = _drive(_attack(state, rukh, prey), _accept_and_target(buddy))
        assert _advantage_count(_find_instance(state, buddy.instance_id)) == 3

    def test_ASH_36_advantage_token_is_a_plus_1_that_expires_after_combat(self, repo):
        """The token grants +1/+0 through the ordinary upgrade stat path, and is
        defeated when its host's attack ends (its printed rule, enforced in the
        combat pipelines)."""
        from swu.engine.actions import compute_power
        state = _make_state()
        atk = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")  # 3/7
        _attach(state, atk, "Advantage")
        assert compute_power(state, atk) == 4
        assert _advantage_count(atk) == 1

        state = _drive(_attack(state, atk, None))          # base attack
        now = _find_instance(state, atk.instance_id)
        assert _advantage_count(now) == 0
        assert state.player_by_id("P1").base_instance.damage == 4   # +1 counted


# ── ASH_37 Red Leader ────────────────────────────────────────────────────────

class TestRedLeaderASH37:
    """"This unit may attack units in either arena" — the CrossArenaAttack marker."""

    def test_ASH_37_can_attack_a_ground_unit_from_space(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        red = _place(state, "P0", _get_card(repo, "ASH", "37"), "space")
        ground_prey = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        plain = _place(state, "P0", _get_card(repo, *BIG_SPACE), "space")

        acts = legal_actions(state)
        assert AttackWithUnit(attacker_id=red.instance_id,
                              defender_id=ground_prey.instance_id) in acts
        assert AttackWithUnit(attacker_id=plain.instance_id,
                              defender_id=ground_prey.instance_id) not in acts


# ── ASH_46 Scion Shuttle ─────────────────────────────────────────────────────

class TestScionShuttleASH46:
    """"While this unit is attacking, the defending unit gets –1/–1"."""

    def test_ASH_46_defender_is_minus_1_minus_1_for_the_attack(self, repo):
        state = _make_state()
        shuttle = _place(state, "P0", _get_card(repo, "ASH", "46"), "space")   # 1/3
        prey = _place(state, "P1", _get_card(repo, *VANILLA_SPACE), "space")   # 3/2

        state = _drive(_attack(state, shuttle, prey))
        # Defender is 2/1 for this attack: the shuttle's 1 damage kills it, and it
        # strikes back for 2 (not 3).
        assert _find_instance(state, prey.instance_id) is None
        assert _find_instance(state, shuttle.instance_id).damage == 2
        assert all(m.duration != "this_attack" for m in state.modifiers)


# ── ASH_50 Morgan Elsbeth ────────────────────────────────────────────────────

class TestMorganElsbethASH50:
    """"When Defeated: You may give a unit –2/–2 for this phase"."""

    def test_ASH_50_when_defeated_debuffs_a_chosen_unit(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        morgan = _place(state, "P0", _get_card(repo, "ASH", "50"), "ground")
        victim = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")

        state = _fire_when_defeated(state, morgan)
        state = _drive(state, _accept_and_target(victim))
        now = _find_instance(state, victim.instance_id)
        assert compute_power(state, now) == 1 and compute_hp(state, now) == 5


# ── ASH_59 Leia Organa ───────────────────────────────────────────────────────

class TestLeiaOrganaASH59:
    """"On Attack: You may deal 1 damage to this unit.  If you do, heal 2 damage
    from your base"."""

    def test_ASH_59_self_damage_heals_the_base(self, repo):
        state = _make_state()
        leia = _place(state, "P0", _get_card(repo, "ASH", "59"), "ground")
        base = state.player_by_id("P0").base_instance
        base.damage = 5

        state = _drive(_fire_on_attack(state, leia, None), _accept_and_target())
        assert _find_instance(state, leia.instance_id).damage == 1
        assert state.player_by_id("P0").base_instance.damage == 3


# ── ASH_68 Domesticated Loth-Cat ─────────────────────────────────────────────

class TestDomesticatedLothCatASH68:
    """"Enemy units lose Ambush and Support" — the KeywordRevoke aura."""

    def test_ASH_68_revokes_support_from_enemy_units_only(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        friendly_sup = _place(state, "P0", _get_card(repo, "ASH", "130"), "space")
        enemy_sup = _place(state, "P1", _get_card(repo, "ASH", "130"), "space")
        assert has_keyword(state, enemy_sup, Keyword.SUPPORT)

        cat = _place(state, "P0", _get_card(repo, "ASH", "68"), "ground")
        assert not has_keyword(state, enemy_sup, Keyword.SUPPORT)
        assert has_keyword(state, friendly_sup, Keyword.SUPPORT)

        # …and the revoke beats a later GRANT, because it is read first.
        from swu.engine.state import Modifier
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id=cat.instance_id,
            target_instance_id=enemy_sup.instance_id,
            kind="keyword_grant", value={"keyword": "Ambush", "value": 0},
            duration="this_phase"))
        assert not has_keyword(state, enemy_sup, Keyword.AMBUSH)

        # It lifts the moment the Loth-Cat leaves play.
        state.player_by_id("P0").ground_arena.remove(cat)
        assert has_keyword(state, enemy_sup, Keyword.SUPPORT)


# ── ASH_72 Doctor Pershing ───────────────────────────────────────────────────

class TestDoctorPershingASH72:
    """"On Attack: If this unit has 3 or more remaining HP, draw a card"."""

    def test_ASH_72_draws_only_above_the_hp_floor(self, repo):
        state = _make_state()
        doc = _place(state, "P0", _get_card(repo, "ASH", "72"), "ground")   # 0/4
        _push_deck_top(state, "P0", _get_card(repo, *VANILLA_GROUND))
        _push_deck_top(state, "P0", _get_card(repo, *VANILLA_GROUND))

        state = _drive(_fire_on_attack(state, doc, None))
        assert len(state.player_by_id("P0").hand) == 1

        doc = _find_instance(state, doc.instance_id)
        doc.damage = 2                                   # 2 remaining HP → no draw
        state = _drive(_fire_on_attack(state, doc, None))
        assert len(state.player_by_id("P0").hand) == 1


# ── ASH_99 Gozanti Assault Carrier ───────────────────────────────────────────

class TestGozantiAssaultCarrierASH99:
    """"On Attack: This unit gains Sentinel for this phase" — its printed Sentinel
    bar is a mistag and is stripped by keyword-sanitiser rule 3."""

    def test_ASH_99_gains_sentinel_only_after_attacking(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        goz = _place(state, "P0", _get_card(repo, "ASH", "99"), "space")
        assert "Sentinel" not in goz.card_def.keywords
        assert not has_keyword(state, goz, Keyword.SENTINEL)

        state = _drive(_fire_on_attack(state, goz, None))
        assert has_keyword(state, _find_instance(state, goz.instance_id),
                           Keyword.SENTINEL)


# ── ASH_101 The Great Mothers ────────────────────────────────────────────────

class TestTheGreatMothersASH101:
    """"When Attack Ends: If this unit dealt combat damage to 1 or more non-leader
    units, defeat those units"."""

    def test_ASH_101_defeats_the_unit_it_damaged(self, repo):
        state = _make_state()
        mothers = _place(state, "P0", _get_card(repo, "ASH", "101"), "ground")  # 6/7
        prey = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")  # 3/7

        state = _drive(_attack(state, mothers, prey))
        # 6 combat damage does not kill a 3/7 — the attack-end sweep does.
        assert _find_instance(state, prey.instance_id) is None
        assert _find_instance(state, mothers.instance_id) is not None

    def test_ASH_101_does_not_re_defeat_a_unit_the_combat_damage_killed(self, repo):
        """Regression: the sweep must SKIP a unit already in the discard.

        ``state.find_instance`` REACHES THE DISCARD, so a unit the combat damage
        itself killed still resolves in the attack-end sweep.  Defeating it a
        second time appended it to the discard twice and tripped the
        duplicate-instance_id conservation invariant (found by the
        emperor-palpatine deck soak, 29/200 games)."""
        state = _make_state()
        mothers = _place(state, "P0", _get_card(repo, "ASH", "101"), "ground")  # 6/7
        prey = _place(state, "P1", _get_card(repo, *VANILLA_WEAK), "ground")    # 2/3

        state = _drive(_attack(state, mothers, prey))

        # 6 combat damage kills a 2/3 outright — it must reach the discard once.
        assert _find_instance(state, prey.instance_id) is None
        discard = state.player_by_id("P1").discard
        assert [ci.instance_id for ci in discard].count(prey.instance_id) == 1


# ── ASH_156 R5-D4 ────────────────────────────────────────────────────────────

class TestR5D4ASH156:
    """"On Attack: Defeat all upgrades on the defending unit"."""

    def test_ASH_156_strips_every_upgrade_from_the_defender(self, repo):
        state = _make_state()
        r5 = _place(state, "P0", _get_card(repo, "ASH", "156"), "ground")
        prey = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        _attach(state, prey, "Shield")
        _attach(state, prey, "Experience")
        assert len(prey.attached_upgrades) == 2

        state = _drive(_fire_on_attack(state, r5, prey))
        assert _find_instance(state, prey.instance_id).attached_upgrades == []


# ── ASH_168 Migs Mayfeld ─────────────────────────────────────────────────────

class TestMigsMayfeldASH168:
    """"On Attack: Deal 1 damage to the defending unit.  If this unit is upgraded,
    deal 2 damage to the defending unit instead"."""

    def test_ASH_168_deals_1_or_2_by_whether_it_is_upgraded(self, repo):
        state = _make_state()
        migs = _place(state, "P0", _get_card(repo, "ASH", "168"), "ground")
        prey = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")

        state = _drive(_fire_on_attack(state, migs, prey))
        assert _find_instance(state, prey.instance_id).damage == 1

        migs = _find_instance(state, migs.instance_id)
        _attach(state, migs, "Experience")
        state = _drive(_fire_on_attack(state, migs, prey))
        assert _find_instance(state, prey.instance_id).damage == 3   # 1 + 2


# ── ASH_189 Emperor's Messenger ──────────────────────────────────────────────

class TestEmperorsMessengerASH189:
    """"On Attack: Ready a resource" (auto-picked — resources are fungible)."""

    def test_ASH_189_readies_one_exhausted_resource(self, repo):
        state = _make_state()
        msgr = _place(state, "P0", _get_card(repo, "ASH", "189"), "ground")
        _add_resource(state, repo, "P0", exhausted=True)
        _add_resource(state, repo, "P0", exhausted=True)

        state = _drive(_fire_on_attack(state, msgr, None))
        ready = sum(1 for r in state.player_by_id("P0").resources if not r.exhausted)
        assert ready == 1


# ── ASH_202 Carson Teva ──────────────────────────────────────────────────────

class TestCarsonTevaASH202:
    """"While attacking, this unit deals combat damage before the defender" —
    ConditionalFirstStrike over any enemy unit."""

    def test_ASH_202_kills_before_taking_damage_back(self, repo):
        state = _make_state()
        carson = _place(state, "P0", _get_card(repo, "ASH", "202"), "ground")  # 1/4
        prey = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        prey.damage = 6                                   # 1 remaining HP

        state = _drive(_attack(state, carson, prey))
        assert _find_instance(state, prey.instance_id) is None
        assert _find_instance(state, carson.instance_id).damage == 0

    def test_ASH_202_gets_no_first_strike_while_defending(self, repo):
        """The whole point of the marker over a KeywordGrant: it is read at the
        attacker's combat step, so Carson defending strikes simultaneously."""
        state = _make_state()
        carson = _place(state, "P0", _get_card(repo, "ASH", "202"), "ground")  # 1/4
        attacker = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        state.active_player_index = 1

        state = _drive(_attack(state, attacker, carson))
        assert _find_instance(state, carson.instance_id).damage == 3
        assert _find_instance(state, attacker.instance_id).damage == 1


# ── ASH_203 Mando's N-1 Starfighter ──────────────────────────────────────────

class TestMandosN1ASH203:
    """"On Attack: You may exhaust a friendly (non-upgrade) leader.  If you do, this
    unit gets +2/+0 for this attack"."""

    def test_ASH_203_exhausts_a_leader_for_plus_two(self, repo):
        from swu.engine.actions import AcceptTrigger, legal_actions, compute_power
        state = _make_state()
        n1 = _place(state, "P0", _get_card(repo, "ASH", "203"), "space")
        leader = _place_leader(state, "P0", _get_by_type(repo, "ASH", "9", "Leader"))

        state = _fire_on_attack(state, n1, None)
        assert any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        state = _drive(state, _accept_and_target())
        assert state.player_by_id("P0").base_zone[-1].exhausted
        assert compute_power(state, _find_instance(state, n1.instance_id)) == 3

    def test_ASH_203_is_not_offered_without_a_ready_leader(self, repo):
        from swu.engine.actions import AcceptTrigger, legal_actions
        state = _make_state()
        n1 = _place(state, "P0", _get_card(repo, "ASH", "203"), "space")
        leader = _place_leader(state, "P0", _get_by_type(repo, "ASH", "9", "Leader"))
        leader.exhausted = True

        state = _fire_on_attack(state, n1, None)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


# ── ASH_209 Ezra Bridger ─────────────────────────────────────────────────────

class TestEzraBridgerASH209:
    """"On Attack: If this unit is upgraded, you may give a unit –3/–0 for this
    phase"."""

    def test_ASH_209_only_triggers_while_upgraded(self, repo):
        from swu.engine.actions import AcceptTrigger, legal_actions, compute_power
        state = _make_state()
        ezra = _place(state, "P0", _get_card(repo, "ASH", "209"), "ground")
        victim = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")

        state = _fire_on_attack(state, ezra, victim)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

        _attach(state, ezra, "Experience")
        state = _drive(_fire_on_attack(state, ezra, victim), _accept_and_target(victim))
        assert compute_power(state, _find_instance(state, victim.instance_id)) == 0


# ── ASH_223 Halo ─────────────────────────────────────────────────────────────

class TestHaloASH223:
    """"When Attack Ends: If the defending unit was defeated, give a Shield token to
    this unit"."""

    def test_ASH_223_shields_itself_on_a_kill(self, repo):
        state = _make_state()
        halo = _place(state, "P0", _get_card(repo, "ASH", "223"), "space")    # 4/4
        prey = _place(state, "P1", _get_card(repo, *VANILLA_SPACE), "space")  # 3/2

        state = _drive(_attack(state, halo, prey))
        assert _find_instance(state, prey.instance_id) is None
        assert _shield_count(_find_instance(state, halo.instance_id)) == 1


# ── ASH_241 Marrok's Fiend Fighter ───────────────────────────────────────────

class TestMarroksFiendFighterASH241:
    """"This unit gets +2/+0 while attacking a damaged unit"."""

    def test_ASH_241_plus_two_only_against_a_damaged_defender(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        marrok = _place(state, "P0", _get_card(repo, "ASH", "241"), "space")  # 3/2
        fresh = _place(state, "P1", _get_card(repo, *BIG_SPACE), "space")
        hurt = _place(state, "P1", _get_card(repo, *BIG_SPACE), "space")
        hurt.damage = 1

        assert compute_power(state, marrok, is_attacking=True, attacking_unit=True,
                             defender_id=hurt.instance_id) == 5
        assert compute_power(state, marrok, is_attacking=True, attacking_unit=True,
                             defender_id=fresh.instance_id) == 3
        assert compute_power(state, marrok) == 3          # not attacking at all


# ── ASH_253 Yellow Aces Bomber ───────────────────────────────────────────────

class TestYellowAcesBomberASH253:
    """"On Attack: If this unit is upgraded, deal 2 damage to a base"."""

    def test_ASH_253_hits_a_base_only_while_upgraded(self, repo):
        state = _make_state()
        bomber = _place(state, "P0", _get_card(repo, "ASH", "253"), "space")
        enemy_base = state.player_by_id("P1").base_instance

        state = _drive(_fire_on_attack(state, bomber, None))
        assert enemy_base.damage == 0                     # no upgrade → no trigger

        bomber = _find_instance(state, bomber.instance_id)
        _attach(state, bomber, "Experience")
        state = _drive(_fire_on_attack(state, bomber, None),
                       _accept_and_target(enemy_base))
        assert state.player_by_id("P1").base_instance.damage == 2


# ══ ash-set:02 — Direct damage & removal ═════════════════════════════════════


class TestGrandAdmiralThrawnLeaderASH4:
    """Undeployed Action: "Attack with a unit.  It gains Restore 2 for this attack if
    you control the same number of units as the defending player."  |  Deployed On
    Attack: "If you control more units than the defending player, you may defeat a
    non-leader unit they control"."""

    def test_ASH_4_grants_restore_only_on_an_even_board(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility
        for mine, expect_restore in ((1, True), (2, False)):
            state = _make_state()
            thrawn = _place_leader(state, "P0",
                                   _get_by_type(repo, "ASH", "4", "Leader"))
            for _ in range(mine):
                _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
            _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")

            use = next(a for a in legal_actions(state) if isinstance(a, UseAbility))
            state = apply(state, use)
            top = state.pending_decisions[-1]
            assert top.kind == "granted_attack"
            granted = top.context.get("grant_keywords") or []
            assert bool(granted) is expect_restore, (mine, granted)

    def test_ASH_4_deployed_defeats_a_unit_while_ahead_on_board(self, repo):
        from swu.engine.actions import AcceptTrigger, legal_actions
        state = _make_state()
        thrawn = _place(state, "P0", _get_by_type(repo, "ASH", "4", "Leader"), "ground")
        thrawn.deployed = True
        _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        prey = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")

        state = _fire_on_attack(state, thrawn, prey)
        assert any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        state = _drive(state, _accept_and_target(prey))
        assert _find_instance(state, prey.instance_id) is None

    def test_ASH_4_deployed_is_silent_when_not_ahead(self, repo):
        from swu.engine.actions import AcceptTrigger, legal_actions
        state = _make_state()
        thrawn = _place(state, "P0", _get_by_type(repo, "ASH", "4", "Leader"), "ground")
        thrawn.deployed = True
        prey = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        state = _fire_on_attack(state, thrawn, prey)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestCadBaneLeaderASH11:
    """"Deal 1 damage to a unit with 2 or more remaining HP" — the new
    ``remaining_hp_ge_<N>`` predicate."""

    def test_ASH_11_only_offers_units_above_1_remaining_hp(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility
        state = _make_state()
        _place_leader(state, "P0", _get_by_type(repo, "ASH", "11", "Leader"))
        healthy = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        nearly_dead = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        nearly_dead.damage = 6                          # 1 remaining HP

        use = next(a for a in legal_actions(state) if isinstance(a, UseAbility))
        state = apply(state, use)
        offered = _target_ids(state)
        assert healthy.instance_id in offered
        assert nearly_dead.instance_id not in offered

        state = _drive(state, _accept_and_target(healthy))
        assert _find_instance(state, healthy.instance_id).damage == 1


class TestVaneLeaderASH12:
    """Undeployed Action [Exhaust, defeat a friendly upgrade]: Deal 2 damage to a
    base.  |  Deployed On Attack: You may defeat a friendly upgrade.  If you do, deal
    2 damage to the defending unit or a base."""

    def test_ASH_12_action_needs_a_friendly_upgrade(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility
        state = _make_state()
        _place_leader(state, "P0", _get_by_type(repo, "ASH", "12", "Leader"))
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        assert not any(isinstance(a, UseAbility) for a in legal_actions(state))

        upg = _place(state, "P0", _get_card(repo, "SOR", "53"), "ground")  # Luke's Lightsaber
        state.player_by_id("P0").ground_arena.remove(upg)
        host.attached_upgrades.append(upg)
        upg.zone = host.zone

        use = next(a for a in legal_actions(state) if isinstance(a, UseAbility))
        state = _drive(apply(state, use), _accept_and_target())
        assert _find_instance(state, host.instance_id).attached_upgrades == []
        bases = [p.base_instance.damage for p in state.players]
        assert 2 in bases

    def test_ASH_12_deployed_only_damages_when_an_upgrade_was_defeated(self, repo):
        from swu.engine.actions import AcceptTrigger, legal_actions
        state = _make_state()
        vane = _place(state, "P0", _get_by_type(repo, "ASH", "12", "Leader"), "ground")
        vane.deployed = True
        prey = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")

        # No friendly upgrade → the first (targeted) effect has no candidate, so the
        # optional trigger is not even offered.
        state = _fire_on_attack(state, vane, prey)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestEnochASH27:
    """"When Defeated: You may deal up to 6 damage to your base.  The next unit you
    play this phase costs 1 resource less for every 2 damage dealt this way"."""

    def test_ASH_27_choose_amount_damages_base_and_arms_the_discount(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, SelectModalOption)
        state = _make_state()
        enoch = _place(state, "P0", _get_card(repo, "ASH", "27"), "ground")

        state = _fire_when_defeated(state, enoch)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        while state.pending_decisions and state.pending_decisions[-1].kind != "choose_two_modal":
            state = apply(state, legal_actions(state)[0])
        opts = [a for a in legal_actions(state) if isinstance(a, SelectModalOption)]
        assert len(opts) == 3                       # 2 / 4 / 6 damage
        state = _drive(apply(state, opts[-1]))      # take the 6-damage option

        assert state.player_by_id("P0").base_instance.damage == 6
        pending = state.game_memory.pending_play_discounts
        assert len(pending) == 1 and pending[0]["amount"] == 3


class TestRancorKeeperASH32:
    """"When a friendly unit is dealt damage and survives: Deal 1 damage to any
    number of bases.  Use this ability only once each round"."""

    def test_ASH_32_hits_both_bases_then_locks_for_the_round(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        keeper = _place(state, "P0", _get_card(repo, "ASH", "32"), "ground")
        buddy = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        enemy = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        state.active_player_index = 1

        state = _drive(_attack(state, enemy, buddy), _accept_and_target())
        hits = sum(p.base_instance.damage for p in state.players)
        assert hits == 2                              # both bases, distinct picks

        # Once each round: the trigger is no longer collected.
        state.active_player_index = 1
        _find_instance(state, enemy.instance_id).exhausted = False
        state = _attack(state, _find_instance(state, enemy.instance_id),
                        _find_instance(state, buddy.instance_id))
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        state = _drive(state)
        assert sum(p.base_instance.damage for p in state.players) == 2


class TestTatooineRepulsorTrainASH35:
    """"This unit can't be attacked while you control 2 or more exhausted units
    (unless it gains Sentinel)."  |  "On Attack: Deal 2 damage to a ground unit for
    each friendly exhausted unit"."""

    def test_ASH_35_cannot_be_attacked_while_two_units_are_exhausted(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        train = _place(state, "P0", _get_card(repo, "ASH", "35"), "ground")
        mate = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        attacker = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        state.active_player_index = 1

        hit = AttackWithUnit(attacker_id=attacker.instance_id,
                             defender_id=train.instance_id)
        assert hit in legal_actions(state)            # 0 exhausted → attackable
        train.exhausted = True
        assert hit in legal_actions(state)            # 1 exhausted → still attackable
        mate.exhausted = True
        assert hit not in legal_actions(state)        # 2 exhausted → protected

    def test_ASH_35_on_attack_scales_with_friendly_exhausted_units(self, repo):
        state = _make_state()
        train = _place(state, "P0", _get_card(repo, "ASH", "35"), "ground")
        mate = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        mate.exhausted = True
        prey = _place(state, "P1", _get_card(repo, "ASH", "101"), "ground")   # 6/7
        train.exhausted = True                        # attacking exhausts it

        state = _drive(_fire_on_attack(state, train, prey), _accept_and_target(prey))
        assert _find_instance(state, prey.instance_id).damage == 4   # 2 × 2 exhausted


class TestPurrgilUltraASH38:
    """"When Played/When Defeated: You may return another friendly non-leader unit to
    its owner's hand.  If you do, deal damage to a unit equal to the returned unit's
    cost"."""

    def test_ASH_38_bounce_then_damage_equal_to_that_cost(self, repo):
        from tests.test_sor_cards import _fire_when_played
        state = _make_state()
        purrgil = _place(state, "P0", _get_card(repo, "ASH", "38"), "space")
        friend = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")  # cost 3
        victim = _place(state, "P1", _get_card(repo, "ASH", "101"), "ground")

        def _pick(state, acts):
            from swu.engine.actions import AcceptTrigger, ChooseTarget
            for a in acts:
                if isinstance(a, AcceptTrigger):
                    return a
            for a in acts:
                if isinstance(a, ChooseTarget) and a.target_id in (
                        friend.instance_id, victim.instance_id):
                    return a
            return None

        cost = int(friend.card_def.cost)
        state = _drive(_fire_when_played(state, purrgil), _pick)
        assert _find_instance(state, friend.instance_id) is None
        assert len(state.player_by_id("P0").hand) == 1
        assert _find_instance(state, victim.instance_id).damage == cost

    def test_ASH_38_declining_the_bounce_deals_no_damage(self, repo):
        from tests.test_sor_cards import _fire_when_played
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        purrgil = _place(state, "P0", _get_card(repo, "ASH", "38"), "space")
        _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        victim = _place(state, "P1", _get_card(repo, "ASH", "101"), "ground")

        state = _fire_when_played(state, purrgil)
        decline = next(a for a in legal_actions(state) if isinstance(a, DeclineTrigger))
        state = _drive(apply(state, decline))
        assert _find_instance(state, victim.instance_id).damage == 0


# ══ ash-set:03 — direct damage & removal ════════════════════════════════════

def _fire_card_played(state, ci):
    """Fire a CardPlayed observer (WhenYouPlayCard) for ``ci``, threading the
    ``played_card_id`` the observers read."""
    from swu.engine.events import CardPlayed
    from swu.abilities.resolver import fire_triggered_abilities
    evt = CardPlayed(player_id=ci.owner_id, instance_id=ci.instance_id,
                     card_name=ci.card_def.display_name, cost_paid=0)
    state.event_log.append(evt)
    return fire_triggered_abilities(
        state, evt, after_all_player_idx=0,
        event_ctx={"played_card_id": ci.instance_id})


class TestCoronaFourASH43:
    """On Attack: give a unit −2/−0 this phase.  When Defeated: defeat a
    non-leader unit with 0 power."""

    def test_ASH_43_debuff_then_defeat_a_zero_power_unit(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        corona = _place(state, "P0", _get_card(repo, "ASH", "43"), "space")
        victim = _place(state, "P1", _get_card(repo, *VANILLA_SPACE), "space")  # 3/2
        # Two attacks' worth of −2/−0 takes the A-Wing to 0 power or below.
        for _ in range(2):
            state = _drive(_fire_on_attack(state, corona, victim),
                           _accept_and_target(victim))
        assert compute_power(state, _find_instance(state, victim.instance_id)) <= 0

        state = _drive(_fire_when_defeated(state, corona),
                       _accept_and_target(victim))
        assert _find_instance(state, victim.instance_id) is None


class TestPreVizslaASH53:
    """When Played: Defeat any number of non-leader units with a total of 6 or less
    remaining HP.  Create a Mandalorian token for each unit defeated this way."""

    def test_ASH_53_defeats_within_the_hp_budget_and_mints_tokens(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectUnitToCaptureCombined
        state = _make_state()
        vizsla = _place(state, "P0", _get_card(repo, "ASH", "53"), "ground")
        small = _place(state, "P1", _get_card(repo, *VANILLA_SPACE), "space")   # 2 HP
        big = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")   # 7 HP

        state = _fire_when_played(state, vizsla)
        top = state.pending_decisions[-1]
        assert top.kind == "capture_combined_hp"
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, SelectUnitToCaptureCombined)}
        assert small.instance_id in offered          # 2 remaining HP
        assert big.instance_id not in offered        # 7 > the 6 budget

        pick = next(a for a in legal_actions(state)
                    if isinstance(a, SelectUnitToCaptureCombined)
                    and a.target_id == small.instance_id)
        state = _drive(apply(state, pick))
        assert _find_instance(state, small.instance_id) is None
        assert _find_instance(state, big.instance_id) is not None
        tokens = [ci for ci in state.player_by_id("P0").ground_arena
                  if ci.card_def.name == "Mandalorian"]
        assert len(tokens) == 1


class TestCobbVanthASH60:
    """When you play another unit: You may deal 2 damage to this unit.  If you do,
    give a Shield token to that unit."""

    def test_ASH_60_self_damage_buys_the_played_unit_a_shield(self, repo):
        state = _make_state()
        cobb = _place(state, "P0", _get_card(repo, "ASH", "60"), "ground")
        played = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")

        state = _drive(_fire_card_played(state, played), _accept_and_target())
        assert _find_instance(state, cobb.instance_id).damage == 2
        assert _shield_count(_find_instance(state, played.instance_id)) == 1


class TestTheMandalorianASH62:
    """If damage would be dealt to another friendly unit, you may defeat a Shield
    token on this unit.  If you do, prevent that damage."""

    def test_ASH_62_spends_a_shield_to_blank_damage_on_a_friend(self, repo):
        from swu.abilities.resolver import _apply_deal_damage
        state = _make_state()
        mando = _place(state, "P0", _get_card(repo, "ASH", "62"), "ground")
        friend = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        _attach(state, mando, "Shield")
        assert _shield_count(mando) == 1

        _apply_deal_damage(state, friend.instance_id, 3, "test")
        assert _find_instance(state, friend.instance_id).damage == 0   # prevented
        assert _shield_count(_find_instance(state, mando.instance_id)) == 0

        # With no Shield left to pay, the next instance lands in full.
        _apply_deal_damage(state, friend.instance_id, 3, "test")
        assert _find_instance(state, friend.instance_id).damage == 3


class TestGetLostASH67:
    """Defeat an upgraded non-leader unit."""

    def test_ASH_67_only_offers_upgraded_units(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        upgraded = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        bare = _place(state, "P1", _get_card(repo, *VANILLA_SPACE), "space")
        _attach(state, upgraded, "Experience")

        state, _evt = _play_event_from_hand(state, repo, "ASH", "67")
        assert _target_ids(state) == {upgraded.instance_id}
        pick = next(a for a in legal_actions(state) if isinstance(a, ChooseTarget)
                    and a.target_id == upgraded.instance_id)
        state = _drive(apply(state, pick))
        assert _find_instance(state, upgraded.instance_id) is None
        assert _find_instance(state, bare.instance_id) is not None


class TestBatteredHaulcraftASH71:
    """When Played: Deal 1 damage to this unit and 1 damage to an enemy space unit."""

    def test_ASH_71_hits_itself_and_an_enemy_space_unit(self, repo):
        state = _make_state()
        haul = _place(state, "P0", _get_card(repo, "ASH", "71"), "space")
        enemy = _place(state, "P1", _get_card(repo, *VANILLA_SPACE), "space")
        _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")   # not eligible

        state = _drive(_fire_when_played(state, haul), _accept_and_target(enemy))
        assert _find_instance(state, enemy.instance_id).damage == 1
        assert _find_instance(state, haul.instance_id).damage == 1


class TestSummaVerminothASH83:
    """On Attack: Defeat all other space units."""

    def test_ASH_83_wipes_every_other_space_unit(self, repo):
        state = _make_state()
        summa = _place(state, "P0", _get_card(repo, "ASH", "83"), "space")
        friend = _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")
        foe = _place(state, "P1", _get_card(repo, *VANILLA_SPACE), "space")
        ground = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")

        state = _drive(_fire_on_attack(state, summa, foe))
        assert _find_instance(state, summa.instance_id) is not None
        assert _find_instance(state, friend.instance_id) is None
        assert _find_instance(state, foe.instance_id) is None
        assert _find_instance(state, ground.instance_id) is not None


# ══ ash-set:04 — direct damage & removal ════════════════════════════════════

def _attach_upgrade_card(state, host, card_def):
    """Attach a real (non-token) upgrade card to ``host`` without playing it."""
    import uuid as _u
    from swu.engine.state import CardInstance
    ci = CardInstance(instance_id=f"{host.owner_id}_up_{_u.uuid4().hex[:6]}",
                      card_def=card_def, owner_id=host.owner_id, zone=host.zone)
    host.attached_upgrades.append(ci)
    return ci


class TestGravChargeASH85:
    """When attached unit's attack ends: Deal 4 damage to it and defeat this
    upgrade."""

    def test_ASH_85_blasts_its_host_and_dies_when_the_attack_ends(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")  # 3/7
        charge = _attach_upgrade_card(state, host, _get_card(repo, "ASH", "85"))

        state = _drive(_attack(state, host))          # attack the enemy base
        live = _find_instance(state, host.instance_id)
        assert live.damage == 4
        assert all(u.instance_id != charge.instance_id for u in live.attached_upgrades)
        assert any(c.instance_id == charge.instance_id
                   for c in state.player_by_id("P0").discard)


class TestReforgeASH90:
    """Defeat an upgrade on a friendly unit.  If you do, search the top 8 cards of
    your deck for an upgrade that can attach to that unit and play it for 4 less."""

    def test_ASH_90_swaps_an_upgrade_for_one_off_the_top_8(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectSearchCard
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        old = _attach_upgrade_card(state, host, _get_card(repo, "ASH", "85"))
        fresh = _push_deck_top(state, "P0", _get_card(repo, "ASH", "183"))

        state, _evt = _play_event_from_hand(state, repo, "ASH", "90")
        from swu.engine.actions import ChooseTarget
        pick_old = next(a for a in legal_actions(state) if isinstance(a, ChooseTarget)
                        and getattr(a, "target_id", None) == old.instance_id)
        state = apply(state, pick_old)
        # The old upgrade is gone and the search is up with the deck upgrade offered.
        assert state.pending_decisions[-1].kind == "deck_search"
        picks = [a for a in legal_actions(state) if isinstance(a, SelectSearchCard)]
        assert {a.instance_id for a in picks} == {fresh.instance_id}
        state = _drive(apply(state, picks[0]))

        live = _find_instance(state, host.instance_id)
        assert [u.instance_id for u in live.attached_upgrades] == [fresh.instance_id]
        assert any(c.instance_id == old.instance_id
                   for c in state.player_by_id("P0").discard)


class TestFoundlingRescueASH92:
    """You may defeat a unit with 2 or less remaining HP.  Create a Mandalorian
    token."""

    def test_ASH_92_defeats_a_small_unit_and_always_makes_a_token(self, repo):
        state = _make_state()
        small = _place(state, "P1", _get_card(repo, *VANILLA_SPACE), "space")   # 2 HP
        big = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")   # 7 HP

        state, _evt = _play_event_from_hand(state, repo, "ASH", "92")
        assert _target_ids(state) == {small.instance_id}
        state = _drive(state, _accept_and_target(small))

        assert _find_instance(state, small.instance_id) is None
        assert _find_instance(state, big.instance_id) is not None
        assert sum(1 for ci in state.player_by_id("P0").ground_arena
                   if ci.card_def.name == "Mandalorian") == 1


class TestRavagerASH102:
    """When you play a unit: You may have it deal damage equal to its power to a unit
    in the same arena."""

    def test_ASH_102_played_unit_shoots_in_its_own_arena(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "ASH", "102"), "space")
        played = _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")  # 3 pow
        space_foe = _place(state, "P1", _get_card(repo, *BIG_SPACE), "space")   # 4/7
        ground_foe = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")

        state = _fire_card_played(state, played)
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        offered = _target_ids(state)
        assert space_foe.instance_id in offered
        assert ground_foe.instance_id not in offered      # wrong arena
        state = _drive(state, _accept_and_target(space_foe))
        assert _find_instance(state, space_foe.instance_id).damage == 3


class TestLongLiveTheEmpireASH103:
    """Defeat a friendly Imperial unit.  If you do, resource the top card of your
    deck."""

    def test_ASH_103_defeat_an_imperial_to_ramp(self, repo):
        state = _make_state()
        rukh = _place(state, "P0", _get_card(repo, "ASH", "36"), "ground")   # Imperial
        ramped = _push_deck_top(state, "P0", _get_card(repo, *VANILLA_GROUND))

        state, _evt = _play_event_from_hand(state, repo, "ASH", "103")
        state = _drive(state, _accept_and_target(rukh))

        assert _find_instance(state, rukh.instance_id) is None
        assert any(c.instance_id == ramped.instance_id
                   for c in state.player_by_id("P0").resources)


class TestAdmiralAckbarASH110:
    """When Played: You may defeat this unit.  If you do, search the top 10 cards for
    any number of space units with combined cost 5 or less and play each for free."""

    def test_ASH_110_sacrifices_himself_for_free_space_units(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectSearchCard
        state = _make_state()
        ackbar = _place(state, "P0", _get_card(repo, "ASH", "110"), "ground")
        awing = _push_deck_top(state, "P0", _get_card(repo, *VANILLA_SPACE))
        _push_deck_top(state, "P0", _get_card(repo, *VANILLA_GROUND))   # not space

        state = _fire_when_played(state, ackbar)
        state = apply(state, next(a for a in legal_actions(state)
                                  if type(a).__name__ == "AcceptTrigger"))
        # An accepted optional trigger resolves through a further resolve_effects
        # decision, so drive until the search is up.
        while state.pending_decisions[-1].kind == "resolve_effects":
            state = apply(state, legal_actions(state)[0])
        assert _find_instance(state, ackbar.instance_id) is None
        assert state.pending_decisions[-1].kind == "deck_search"
        picks = [a for a in legal_actions(state) if isinstance(a, SelectSearchCard)]
        assert {a.instance_id for a in picks} == {awing.instance_id}
        state = _drive(apply(state, picks[0]))
        assert _find_instance(state, awing.instance_id) is not None


# ══ ash-set:05 — direct damage & removal ════════════════════════════════════

def _to_hand(state, owner_id, card_def):
    import uuid as _u
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(instance_id=f"{owner_id}_hand_{_u.uuid4().hex[:6]}",
                      card_def=card_def, owner_id=owner_id, zone=Zone.HAND)
    state.player_by_id(owner_id).hand.append(ci)
    return ci


def _use_ability(state, source_ci, idx=0):
    from swu.engine.actions import legal_actions, apply, UseAbility
    act = next(a for a in legal_actions(state) if isinstance(a, UseAbility)
               and a.source_id == source_ci.instance_id
               and getattr(a, "ability_idx", 0) == idx)
    return apply(state, act)


class TestLukeSkywalkerASH112:
    """When Played: If you control at least 4 units, deal 3 damage to each enemy
    unit."""

    def test_ASH_112_wipes_only_with_four_friendly_units(self, repo):
        state = _make_state()
        luke = _place(state, "P0", _get_card(repo, "ASH", "112"), "ground")
        foe = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        # Three units total — the clause fails, so nothing fires.
        _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")
        state = _drive(_fire_when_played(state, luke))
        assert _find_instance(state, foe.instance_id).damage == 0

        _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")   # 4th unit
        state = _drive(_fire_when_played(state, luke))
        assert _find_instance(state, foe.instance_id).damage == 3


class TestEightDEightASH118:
    """Action [Exhaust]: Deal 1 damage to another friendly unit.  If you do, search
    the top 5 cards of your deck for a unit, reveal it, and draw it."""

    def test_ASH_118_hurts_a_friend_and_digs_for_a_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectSearchCard
        state = _make_state()
        droid = _place(state, "P0", _get_card(repo, "ASH", "118"), "ground")
        friend = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        wanted = _push_deck_top(state, "P0", _get_card(repo, *VANILLA_SPACE))

        state = _use_ability(state, droid)
        while state.pending_decisions[-1].kind != "deck_search":
            state = _drive(state, _accept_and_target(friend), limit=1)
        assert _find_instance(state, friend.instance_id).damage == 1
        pick = next(a for a in legal_actions(state) if isinstance(a, SelectSearchCard)
                    and a.instance_id == wanted.instance_id)
        state = _drive(apply(state, pick))
        assert any(c.instance_id == wanted.instance_id
                   for c in state.player_by_id("P0").hand)


class TestQueenSorunaASH132:
    """You may reveal a unit from your hand.  If you do, deal 3 damage to a unit with
    the same cost as the revealed unit."""

    def test_ASH_132_only_hits_units_matching_a_hand_unit_cost(self, repo):
        state = _make_state()
        soruna = _place(state, "P0", _get_card(repo, "ASH", "132"), "ground")
        match = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        other = _place(state, "P1", _get_card(repo, *BIG_SPACE), "space")
        assert match.card_def.cost != other.card_def.cost
        _to_hand(state, "P0", _get_card(repo, *VANILLA_GROUND))

        state = _fire_when_played(state, soruna)
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        offered = _target_ids(state)
        assert match.instance_id in offered
        assert other.instance_id not in offered
        assert soruna.instance_id not in offered     # Soruna's own cost differs
        state = _drive(state, _accept_and_target(match))
        assert _find_instance(state, match.instance_id).damage == 3


class TestWipeThemOutASH137:
    """Attack with a unit.  For this attack, you may deal its excess damage to
    another unit in the same arena."""

    def test_ASH_137_excess_damage_lands_on_another_ground_unit(self, repo):
        from swu.engine.actions import (legal_actions, apply, AttackWithUnit,
                                        SelectDamageTarget)
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        defender = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        defender.damage = 6                       # 1 remaining HP → 2 excess
        bystander = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")

        state, _evt = _play_event_from_hand(state, repo, "ASH", "137")
        atk = next(a for a in legal_actions(state) if isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id
                   and a.defender_id == defender.instance_id)
        state = apply(state, atk)
        assert _find_instance(state, defender.instance_id) is None
        assert state.pending_decisions[-1].kind == "select_damage"
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, SelectDamageTarget)
                    and a.target_id == bystander.instance_id)
        state = _drive(apply(state, pick))
        assert _find_instance(state, bystander.instance_id).damage == 2


class TestTurningTheTideASH138:
    """Choose a unit.  Deal 1 damage to it for each friendly unit."""

    def test_ASH_138_scales_with_friendly_unit_count(self, repo):
        state = _make_state()
        for _ in range(3):
            _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        foe = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")

        state, _evt = _play_event_from_hand(state, repo, "ASH", "138")
        state = _drive(state, _accept_and_target(foe))
        assert _find_instance(state, foe.instance_id).damage == 3


class TestMortarTrooperASH142:
    """Action [Exhaust]: Deal 1 damage to each of up to 3 ground units."""

    def test_ASH_142_pings_up_to_three_ground_units(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectDamageTarget
        state = _make_state()
        trooper = _place(state, "P0", _get_card(repo, "ASH", "142"), "ground")
        a = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        b = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        spacer = _place(state, "P1", _get_card(repo, *VANILLA_SPACE), "space")

        state = _use_ability(state, trooper)
        assert state.pending_decisions[-1].kind == "select_damage"
        offered = {act.target_id for act in legal_actions(state)
                   if isinstance(act, SelectDamageTarget)}
        assert spacer.instance_id not in offered
        for target in (a, b):
            state = apply(state, next(act for act in legal_actions(state)
                                      if isinstance(act, SelectDamageTarget)
                                      and act.target_id == target.instance_id))
        state = _drive(state)
        assert _find_instance(state, a.instance_id).damage == 1
        assert _find_instance(state, b.instance_id).damage == 1
        assert _find_instance(state, spacer.instance_id).damage == 0


class TestJustifierASH146:
    """You may deal 1 damage to a unit.  If that unit is defeated this way, give an
    Advantage token to a unit."""

    def test_ASH_146_a_kill_pays_an_advantage_token(self, repo):
        state = _make_state()
        justifier = _place(state, "P0", _get_card(repo, "ASH", "146"), "space")
        doomed = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        doomed.damage = 6                          # 1 remaining HP

        state = _drive(_fire_when_played(state, justifier),
                       _accept_and_target(doomed))
        assert _find_instance(state, doomed.instance_id) is None
        assert _advantage_count(_find_instance(state, justifier.instance_id)) == 1


# ══ ash-set:06 — direct damage & removal ════════════════════════════════════

class TestTheCyborgMechASH147:
    """When Played: Either deal 2 damage to an undamaged ground unit or 5 damage to
    a damaged ground unit."""

    def test_ASH_147_five_damage_mode_needs_a_damaged_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectModalOption
        state = _make_state()
        mech = _place(state, "P0", _get_card(repo, "ASH", "147"), "ground")
        hurt = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        hurt.damage = 1

        state = _fire_when_played(state, mech)
        assert state.pending_decisions[-1].kind == "choose_two_modal"
        opts = [a for a in legal_actions(state) if isinstance(a, SelectModalOption)]
        # Both modes are live (the Mech itself is an undamaged ground unit).
        assert len(opts) == 2
        state = apply(state, next(a for a in opts if a.option_idx == 2))
        state = _drive(state, _accept_and_target(hurt))
        assert _find_instance(state, hurt.instance_id).damage == 6


class TestNinthSisterASH148:
    """When Played: An opponent discards a card from their hand.  You may deal damage
    equal to its cost divided as you choose among any number of units."""

    def test_ASH_148_discard_cost_becomes_a_damage_pool(self, repo):
        from swu.engine.actions import legal_actions, apply, AssignDamage
        state = _make_state()
        sister = _place(state, "P0", _get_card(repo, "ASH", "148"), "ground")
        foe = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        pitched = _to_hand(state, "P1", _get_card(repo, *VANILLA_GROUND))
        cost = pitched.card_def.cost

        state = _fire_when_played(state, sister)
        assert any(c.instance_id == pitched.instance_id
                   for c in state.player_by_id("P1").discard)
        assert state.pending_decisions[-1].kind == "distribute_damage"
        for _ in range(cost):
            state = apply(state, next(a for a in legal_actions(state)
                                      if isinstance(a, AssignDamage)
                                      and a.target_id == foe.instance_id))
        state = _drive(state)
        assert _find_instance(state, foe.instance_id).damage == cost


class TestOperationCinderASH151:
    """Deal 5 damage to your base.  Then, deal 5 damage to each unit."""

    def test_ASH_151_burns_your_base_and_every_unit(self, repo):
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        theirs = _place(state, "P1", _get_card(repo, *BIG_SPACE), "space")

        state, _evt = _play_event_from_hand(state, repo, "ASH", "151")
        state = _drive(state)
        assert state.player_by_id("P0").base_instance.damage == 5
        assert state.player_by_id("P1").base_instance.damage == 0
        assert _find_instance(state, mine.instance_id).damage == 5     # both sides
        assert _find_instance(state, theirs.instance_id).damage == 5


class TestGreenLeaderASH153:
    """When Defeated: You may deal 2 damage to a unit."""

    def test_ASH_153_when_defeated_deals_2(self, repo):
        state = _make_state()
        green = _place(state, "P0", _get_card(repo, "ASH", "153"), "space")
        foe = _place(state, "P1", _get_card(repo, *BIG_SPACE), "space")

        state = _drive(_fire_when_defeated(state, green), _accept_and_target(foe))
        assert _find_instance(state, foe.instance_id).damage == 2


class TestHanSoloASH158:
    """When Played: Deal 3 damage to this unit.  Give 3 Advantage tokens to a unit."""

    def test_ASH_158_hurts_himself_and_hands_out_three_advantage(self, repo):
        state = _make_state()
        han = _place(state, "P0", _get_card(repo, "ASH", "158"), "ground")
        friend = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")

        state = _drive(_fire_when_played(state, han), _accept_and_target(friend))
        assert _find_instance(state, han.instance_id).damage == 3
        assert _advantage_count(_find_instance(state, friend.instance_id)) == 3


class TestZebOrreliosASH161:
    """When Played: Give 3 Advantage tokens to another unit.
    When a friendly upgrade is defeated: Deal 1 damage to a base."""

    def test_ASH_161_a_defeated_friendly_upgrade_pings_a_base(self, repo):
        from swu.engine.actions import apply, legal_actions, ChooseTarget
        state = _make_state()
        zeb = _place(state, "P0", _get_card(repo, "ASH", "161"), "ground")
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        shield = _attach(state, host, "Shield")
        assert shield is not None

        # Spending the Shield defeats a friendly upgrade → the observer fires at the
        # next settle point, so drive an action through ``apply``.
        from swu.engine import tokens as _tok
        _tok.defeat_shield(state, host)
        from swu.engine.actions import Pass
        state = apply(state, Pass())
        target = next((a for a in legal_actions(state) if isinstance(a, ChooseTarget)
                       and getattr(a, "target_id", None)), None)
        assert target is not None, "the upgrade-defeat observer did not fire"
        enemy_base = state.player_by_id("P1").base_instance
        pick = next(a for a in legal_actions(state) if isinstance(a, ChooseTarget)
                    and a.target_id == enemy_base.instance_id)
        state = _drive(apply(state, pick))
        assert state.player_by_id("P1").base_instance.damage == 1


class TestRecklessSacrificeASH163:
    """Discard a unit from your hand.  Deal 5 damage to a unit that costs more than
    the discarded card."""

    def test_ASH_163_only_hits_units_costlier_than_the_discard(self, repo):
        state = _make_state()
        cheap = _to_hand(state, "P0", _get_card(repo, *VANILLA_SPACE))
        pricey = _place(state, "P1", _get_card(repo, "ASH", "148"), "ground")   # 7
        small = _place(state, "P1", _get_card(repo, *VANILLA_SPACE), "space")
        assert small.card_def.cost <= cheap.card_def.cost < pricey.card_def.cost

        state, _evt = _play_event_from_hand(state, repo, "ASH", "163")
        from swu.engine.actions import legal_actions, apply
        state = apply(state, legal_actions(state)[0])    # resolve the leading discard
        assert any(c.instance_id == cheap.instance_id
                   for c in state.player_by_id("P0").discard)
        offered = _target_ids(state)
        assert pricey.instance_id in offered
        assert small.instance_id not in offered
        state = _drive(state, _accept_and_target(pricey))
        assert _find_instance(state, pricey.instance_id).damage == 5


# ══ ash-set:07 — direct damage & removal ════════════════════════════════════

class TestClanVizslaSoldierASH165:
    """When Defeated: You may defeat an upgrade."""

    def test_ASH_165_when_defeated_kills_an_upgrade(self, repo):
        state = _make_state()
        soldier = _place(state, "P0", _get_card(repo, "ASH", "165"), "ground")
        host = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        upg = _attach_upgrade_card(state, host, _get_card(repo, "ASH", "85"))
        _attach(state, host, "Shield")            # a token is NOT an "upgrade" here

        state = _fire_when_defeated(state, soldier)
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        assert _target_ids(state) == {upg.instance_id}
        state = _drive(state, _accept_and_target())
        live = _find_instance(state, host.instance_id)
        assert all(u.instance_id != upg.instance_id for u in live.attached_upgrades)


class TestDesertSharpshooterASH170:
    """When Played: You may deal 2 damage to an upgraded ground unit."""

    def test_ASH_170_only_hits_upgraded_ground_units(self, repo):
        state = _make_state()
        shooter = _place(state, "P0", _get_card(repo, "ASH", "170"), "ground")
        upgraded = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        bare = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        _attach(state, upgraded, "Experience")

        state = _fire_when_played(state, shooter)
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        assert _target_ids(state) == {upgraded.instance_id}
        state = _drive(state, _accept_and_target(upgraded))
        assert _find_instance(state, upgraded.instance_id).damage == 2
        assert _find_instance(state, bare.instance_id).damage == 0


class TestPegasusTriWingASH171:
    """When Played: You may defeat a friendly upgrade.  If you do, ready this unit."""

    def test_ASH_171_eats_a_friendly_upgrade_to_ready_itself(self, repo):
        state = _make_state()
        pegasus = _place(state, "P0", _get_card(repo, "ASH", "171"), "space")
        pegasus.exhausted = True
        friend = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        upg = _attach_upgrade_card(state, friend, _get_card(repo, "ASH", "85"))

        state = _drive(_fire_when_played(state, pegasus), _accept_and_target(upg))
        assert _find_instance(state, pegasus.instance_id).exhausted is False
        live = _find_instance(state, friend.instance_id)
        assert all(u.instance_id != upg.instance_id for u in live.attached_upgrades)


class TestStarFortressHeavyBomberASH174:
    """When Played: You may deal 6 damage to a non-<uq> ground unit."""

    def test_ASH_174_spares_unique_ground_units(self, repo):
        state = _make_state()
        bomber = _place(state, "P0", _get_card(repo, "ASH", "174"), "space")
        plain = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        unique = _place(state, "P1", _get_card(repo, "ASH", "110"), "ground")
        assert unique.card_def.is_unique and not plain.card_def.is_unique

        state = _fire_when_played(state, bomber)
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        assert _target_ids(state) == {plain.instance_id}
        state = _drive(state, _accept_and_target(plain))
        assert _find_instance(state, plain.instance_id).damage == 6
        assert _find_instance(state, unique.instance_id).damage == 0


class TestImposingScoutWalkerASH176:
    """When Played: You may deal 3 damage to a ground unit.  If it's defeated this
    way, give 3 Advantage tokens to this unit."""

    def test_ASH_176_a_kill_pays_three_advantage_tokens(self, repo):
        state = _make_state()
        walker = _place(state, "P0", _get_card(repo, "ASH", "176"), "ground")
        doomed = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        doomed.damage = 5                             # 2 remaining HP

        state = _drive(_fire_when_played(state, walker), _accept_and_target(doomed))
        assert _find_instance(state, doomed.instance_id) is None
        assert _advantage_count(_find_instance(state, walker.instance_id)) == 3


class TestBobaFettsRancorASH179:
    """When Played: 5 to your base, then 5 and 5 to one enemy ground unit.
    On Attack: 1 damage to a base for every 5 damage on your base."""

    def test_ASH_179_when_played_burns_base_and_double_taps(self, repo):
        state = _make_state()
        rancor = _place(state, "P0", _get_card(repo, "ASH", "179"), "ground")
        foe = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        _attach(state, foe, "Shield")     # eats only the FIRST of the two 5s

        state = _drive(_fire_when_played(state, rancor), _accept_and_target(foe))
        assert state.player_by_id("P0").base_instance.damage == 5
        live = _find_instance(state, foe.instance_id)
        assert _shield_count(live) == 0        # the Shield ate the first 5 …
        assert live.damage == 5                # … and the second landed in full

    def test_ASH_179_on_attack_scales_with_own_base_damage(self, repo):
        state = _make_state()
        rancor = _place(state, "P0", _get_card(repo, "ASH", "179"), "ground")
        state.player_by_id("P0").base_instance.damage = 11      # → 2 damage
        enemy_base = state.player_by_id("P1").base_instance

        state = _drive(_fire_on_attack(state, rancor, None),
                       _accept_and_target(enemy_base))
        assert state.player_by_id("P1").base_instance.damage == 2


class TestWhistlingBirdsASH183:
    """Attached unit gains: "When Attack Ends: If this unit dealt combat damage to an
    opponent's base, deal 2 damage to each unit that opponent controls in this unit's
    arena.\""""

    def test_ASH_183_base_hit_sprays_the_enemy_arena(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        _attach_upgrade_card(state, host, _get_card(repo, "ASH", "183"))
        ground_foe = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        space_foe = _place(state, "P1", _get_card(repo, *BIG_SPACE), "space")

        state = _drive(_attack(state, host))          # attack the enemy base
        assert _find_instance(state, ground_foe.instance_id).damage == 2
        assert _find_instance(state, space_foe.instance_id).damage == 0


# ── ASH_94 Moff Jerjerrod (the token-doubling observer) ──────────────────────

def _token_units(state, owner_id, name):
    """Token units of ``name`` in ``owner_id``'s arenas."""
    ps = state.player_by_id(owner_id)
    return [ci for ci in ps.ground_arena + ps.space_arena
            if ci.card_def.name == name]


def _token_upgrades(ci, name):
    from swu.cards.models import TokenUpgrade
    return [u for u in ci.attached_upgrades
            if isinstance(u.card_def, TokenUpgrade) and u.card_def.name == name]


def _decline_triggers(state, acts):
    from swu.engine.actions import DeclineTrigger
    for a in acts:
        if isinstance(a, DeclineTrigger):
            return a
    return None


class TestMoffJerjerrodASH94:
    """"If you would create a number of tokens, you may defeat this unit.  If you do,
    create twice that number of tokens instead."

    Modelled as the WhenYouWouldCreateTokens settle-drain observer: the creation
    happens, then the controller may pay Jerjerrod for the matching top-up.  The three
    creation chokepoints (token units / Credits / token upgrades) each feed it."""

    def test_ASH_94_doubles_a_token_unit_creation(self, repo):
        # Droid Deployment TWI_237 — "Create 2 Battle Droid tokens" → 4.
        state = _make_state()
        jerj = _place(state, "P0", _get_card(repo, "ASH", "94"), "ground")
        state, _ = _play_event_from_hand(state, repo, "TWI", "237")
        state = _drive(state, _accept_and_target())
        assert _find_instance(state, jerj.instance_id) is None   # he paid for it
        assert len(_token_units(state, "P0", "Battle Droid")) == 4

    def test_ASH_94_declining_costs_nothing(self, repo):
        state = _make_state()
        jerj = _place(state, "P0", _get_card(repo, "ASH", "94"), "ground")
        state, _ = _play_event_from_hand(state, repo, "TWI", "237")
        state = _drive(state, _decline_triggers)
        assert _find_instance(state, jerj.instance_id) is not None
        assert len(_token_units(state, "P0", "Battle Droid")) == 2

    def test_ASH_94_doubles_a_credit_token(self, repo):
        # Unmarked Credits LAW_244 — "Create a Credit token" → 2 (the credit arm).
        state = _make_state()
        jerj = _place(state, "P0", _get_card(repo, "ASH", "94"), "ground")
        state, _ = _play_event_from_hand(state, repo, "LAW", "244")
        state = _drive(state, _accept_and_target())
        assert _find_instance(state, jerj.instance_id) is None
        assert len(state.player_by_id("P0").credits) == 2

    def test_ASH_94_coalesces_two_token_upgrade_calls(self, repo):
        # Consumed by the Dark Side LOF_239 — "Give 2 Experience tokens to a unit" is
        # TWO attach_token calls, which the drain coalesces into one creation of 2, so
        # the doubling lands on 4 rather than 3.
        state = _make_state()
        jerj = _place(state, "P0", _get_card(repo, "ASH", "94"), "ground")
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        state, _ = _play_event_from_hand(state, repo, "LOF", "239")
        state = _drive(state, _accept_and_target(host))
        assert _find_instance(state, jerj.instance_id) is None
        assert len(_token_upgrades(_find_instance(state, host.instance_id),
                                   "Experience")) == 4

    def test_ASH_94_ignores_an_opponents_creation(self, repo):
        # "If YOU would create" — an enemy Jerjerrod is not offered P0's tokens.
        state = _make_state()
        jerj = _place(state, "P1", _get_card(repo, "ASH", "94"), "ground")
        state, _ = _play_event_from_hand(state, repo, "TWI", "237")
        assert not state.pending_decisions
        assert _find_instance(state, jerj.instance_id) is not None
        assert len(_token_units(state, "P0", "Battle Droid")) == 2

    def test_ASH_94_top_up_does_not_re_arm_itself(self, repo):
        # The doubled tokens are created with note_token_creation=False, so the ledger
        # is empty once the dust settles and nothing is left pending.
        state = _make_state()
        _place(state, "P0", _get_card(repo, "ASH", "94"), "ground")
        state, _ = _play_event_from_hand(state, repo, "TWI", "237")
        state = _drive(state, _accept_and_target())
        assert state.game_memory.token_creations == []
        assert not state.pending_decisions


# ── ash-set:08 — Direct damage & removal ─────────────────────────────────────


class TestTreacherousMinefieldASH186:
    """Choose an arena.  For this phase, each unit in that arena gains: "On Attack:
    Deal 2 damage to this unit"."""

    def test_ASH_186_grants_the_chosen_arena_a_self_hit_on_attack(self, repo):
        from swu.engine.actions import apply, SelectModalOption
        state = _make_state()
        grounder = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        spacer = _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")
        enemy = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")

        state, _evt = _play_event_from_hand(state, repo, "ASH", "186")
        # Ability index 1 is the GROUND option, 2 the space one.
        state = _drive(apply(state, SelectModalOption(option_idx=1)))

        # A ground attacker takes 2 from its own granted ability …
        state = _drive(_fire_on_attack(state, grounder, enemy))
        assert _find_instance(state, grounder.instance_id).damage == 2
        # … a space attacker is untouched (the other arena was not chosen) …
        state = _drive(_fire_on_attack(state, spacer, enemy))
        assert _find_instance(state, spacer.instance_id).damage == 0
        # … and the grant is arena-wide, not controller-wide: the ENEMY ground unit
        # has it too ("each unit in that arena").
        state = _drive(_fire_on_attack(state, enemy, grounder))
        assert _find_instance(state, enemy.instance_id).damage == 2


class TestReckoningASH187:
    """Deal damage to a unit equal to the total amount of damage on all units you
    control."""

    def test_ASH_187_scales_with_the_damage_on_your_own_units(self, repo):
        from swu.engine.actions import apply, legal_actions, ChooseTarget
        state = _make_state()
        a = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        b = _place(state, "P0", _get_card(repo, *BIG_SPACE), "space")
        a.damage = 2
        b.damage = 3
        _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground").damage = 4
        victim = _place(state, "P1", _get_card(repo, *BIG_SPACE), "space")

        state, _evt = _play_event_from_hand(state, repo, "ASH", "187")
        pick = next(a2 for a2 in legal_actions(state) if isinstance(a2, ChooseTarget)
                    and a2.target_id == victim.instance_id)
        state = _drive(apply(state, pick))
        # 2 + 3 from the friendly units only — the enemy's 4 does not count.
        assert _find_instance(state, victim.instance_id).damage == 5


class TestSnubFighterSquadronASH194:
    """Ambush.  When Played: Deal 1 damage to a space unit."""

    def test_ASH_194_deals_1_to_a_space_unit(self, repo):
        state = _make_state()
        snub = _place(state, "P0", _get_card(repo, "ASH", "194"), "space")
        enemy_space = _place(state, "P1", _get_card(repo, *BIG_SPACE), "space")
        enemy_ground = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")

        state = _fire_when_played(state, snub)
        # Only space units are offered (either controller's).
        assert enemy_ground.instance_id not in _target_ids(state)
        assert enemy_space.instance_id in _target_ids(state)
        state = _drive(state, _accept_and_target(enemy_space))
        assert _find_instance(state, enemy_space.instance_id).damage == 1


class TestGorianShardsCorsairASH196:
    """Damage dealt by friendly Underworld cards is unpreventable.
    When Played/On Attack: You may deal 2 damage to a unit."""

    def test_ASH_196_damage_is_unpreventable_and_fires_on_both_triggers(self, repo):
        state = _make_state()
        corsair = _place(state, "P0", _get_card(repo, "ASH", "196"), "space")
        victim = _place(state, "P1", _get_card(repo, *BIG_SPACE), "space")
        _attach(state, victim, "Shield")
        assert _shield_count(_find_instance(state, victim.instance_id)) == 1

        # When Played: the Shield does NOT eat the hit — the Corsair is Underworld.
        state = _drive(_fire_when_played(state, corsair), _accept_and_target(victim))
        victim_now = _find_instance(state, victim.instance_id)
        assert victim_now.damage == 2
        assert _shield_count(victim_now) == 1

        # On Attack: the same effect under the second trigger.
        state = _drive(_fire_on_attack(state, corsair, victim),
                       _accept_and_target(victim))
        assert _find_instance(state, victim.instance_id).damage == 4

    def test_ASH_196_leaves_other_cards_damage_preventable(self, repo):
        # A NON-Underworld friendly dealer is unaffected: its damage is still eaten
        # by the Shield, so the marker really is keyed on the dealing card.
        state = _make_state()
        _place(state, "P0", _get_card(repo, "ASH", "196"), "space")
        ratcatcher = _place(state, "P0", _get_card(repo, "ASH", "259"), "ground")
        assert "Underworld" not in (ratcatcher.card_def.traits or ())
        victim = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        _attach(state, victim, "Shield")

        state = _drive(_fire_when_played(state, ratcatcher),
                       _accept_and_target(victim))
        victim_now = _find_instance(state, victim.instance_id)
        assert victim_now.damage == 0
        assert _shield_count(victim_now) == 0


class TestDDCDefenderASH210:
    """Attach to a non-Vehicle unit.  Attached unit gains: "On Defense: You may deal
    1 damage to a unit in this unit's arena and exhaust it"."""

    def test_ASH_210_on_defense_damages_and_exhausts_a_unit_in_the_arena(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        upg = _place(state, "P0", _get_card(repo, "ASH", "210"), "ground")
        state.player_by_id("P0").ground_arena.remove(upg)
        host.attached_upgrades.append(upg)
        attacker = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        elsewhere = _place(state, "P1", _get_card(repo, *VANILLA_SPACE), "space")

        state = _fire_on_attack(state, attacker, host)
        state = _drive(state, _accept_and_target(attacker))
        hit = _find_instance(state, attacker.instance_id)
        assert hit.damage == 1
        assert hit.exhausted
        # A unit in the OTHER arena was never eligible.
        assert _find_instance(state, elsewhere.instance_id).damage == 0

    def test_ASH_210_attaches_only_to_a_non_vehicle_unit(self, repo):
        from swu.engine.actions import _upgrade_target_spec
        spec = _upgrade_target_spec(_get_card(repo, "ASH", "210"))
        assert spec is not None and "non_vehicle" in spec.predicates


class TestLEPRatcatcherASH259:
    """When Played: You may deal 1 damage to a ground unit."""

    def test_ASH_259_may_deal_1_to_a_ground_unit(self, repo):
        from swu.engine.actions import apply, legal_actions, DeclineTrigger
        state = _make_state()
        rat = _place(state, "P0", _get_card(repo, "ASH", "259"), "ground")
        enemy = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        _place(state, "P1", _get_card(repo, *VANILLA_SPACE), "space")

        fired = _fire_when_played(state, rat)
        # The "you may" is a real decline.
        declined = _drive(apply(fired, next(
            a for a in legal_actions(fired) if isinstance(a, DeclineTrigger))))
        assert _find_instance(declined, enemy.instance_id).damage == 0

        state = _drive(fired, _accept_and_target(enemy))
        assert _find_instance(state, enemy.instance_id).damage == 1


# ── ash-set:09 — Card advantage & disruption ─────────────────────────────────


class TestReanimatedNightTrooperASH45:
    """When Defeated: Look at the top card of a deck.  You may discard it."""

    def test_ASH_45_may_discard_the_top_card(self, repo):
        from swu.engine.actions import apply, legal_actions, DiscardTopCard, KeepTopCard
        state = _make_state()
        trooper = _place(state, "P0", _get_card(repo, "ASH", "45"), "ground")
        top = _push_deck_top(state, "P0", _get_card(repo, *VANILLA_GROUND))

        fired = _fire_when_defeated(state, trooper)
        kinds = {type(a).__name__ for a in legal_actions(fired)}
        assert kinds == {"KeepTopCard", "DiscardTopCard"}

        kept = apply(fired, next(a for a in legal_actions(fired)
                                 if isinstance(a, KeepTopCard)))
        assert kept.player_by_id("P0").deck[0].instance_id == top.instance_id

        state = apply(fired, next(a for a in legal_actions(fired)
                                  if isinstance(a, DiscardTopCard)))
        assert top.instance_id in {c.instance_id
                                   for c in state.player_by_id("P0").discard}


class TestBladeOfTalzinASH55:
    """When Defeated: If this upgrade was on a friendly Night unit, return this
    upgrade from your discard pile to your hand."""

    def _kill_host_with_blade(self, repo, host_card):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        host = _place(state, "P0", host_card, "ground")
        blade = _place(state, "P0", _get_card(repo, "ASH", "55"), "ground")
        state.player_by_id("P0").ground_arena.remove(blade)
        host.attached_upgrades.append(blade)
        blade.zone = host.zone
        _defeat_unit(state, state.player_by_id("P0"), host)
        return _drive(state), blade

    def test_ASH_55_returns_itself_off_a_night_host(self, repo):
        state, blade = self._kill_host_with_blade(repo, _get_card(repo, "LOF", "66"))
        hand = {c.instance_id for c in state.player_by_id("P0").hand}
        assert blade.instance_id in hand

    def test_ASH_55_stays_in_the_discard_off_a_non_night_host(self, repo):
        state, blade = self._kill_host_with_blade(
            repo, _get_card(repo, *VANILLA_GROUND))
        assert blade.instance_id not in {c.instance_id
                                         for c in state.player_by_id("P0").hand}
        assert blade.instance_id in {c.instance_id
                                     for c in state.player_by_id("P0").discard}


class TestCyberneticEnhancementsASH87:
    """When Played: Draw a card."""

    def test_ASH_87_draws_when_played(self, repo):
        from tests.test_sor_cards import _fire_upgrade_played
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        upg = _place(state, "P0", _get_card(repo, "ASH", "87"), "ground")
        state.player_by_id("P0").ground_arena.remove(upg)
        host.attached_upgrades.append(upg)
        _push_deck_top(state, "P0", _get_card(repo, *VANILLA_SPACE))
        before = len(state.player_by_id("P0").hand)

        state = _drive(_fire_upgrade_played(state, upg, host))
        assert len(state.player_by_id("P0").hand) == before + 1


class TestMoffGideonASH97:
    """When Defeated: You may return a non-unique Imperial unit from your discard
    pile to your hand."""

    def test_ASH_97_returns_a_non_unique_imperial_unit(self, repo):
        from swu.engine.state import Zone
        from swu.engine.actions import legal_actions, apply, SelectDiscardCard
        state = _make_state()
        gideon = _place(state, "P0", _get_card(repo, "ASH", "97"), "ground")
        ps = state.player_by_id("P0")
        for card in (_get_card(repo, "ASH", "45"), _get_card(repo, *VANILLA_GROUND)):
            ci = _place(state, "P0", card, "ground")
            ps.ground_arena.remove(ci)
            ci.zone = Zone.DISCARD
            ps.discard.append(ci)
        imperial, other = ps.discard[0], ps.discard[1]

        state = _drive_until(
            _fire_when_defeated(state, gideon), "return_from_discard",
            lambda st, acts: next(
                (a for a in acts if type(a).__name__ == "AcceptTrigger"), None))
        picks = [a for a in legal_actions(state) if isinstance(a, SelectDiscardCard)]
        # Only the non-unique Imperial UNIT is offered.
        assert {a.instance_id for a in picks} == {imperial.instance_id}
        assert other.instance_id not in {a.instance_id for a in picks}
        state = _drive(apply(state, picks[0]))
        assert imperial.instance_id in {c.instance_id
                                        for c in state.player_by_id("P0").hand}


class TestDathomiriMagicksASH104:
    """If you control a Force unit, this event costs 1 less.  Play up to 3
    non-Vehicle units that each cost 2 or less from your discard pile for free."""

    def _seed_discard(self, state, repo):
        from swu.engine.state import Zone
        ps = state.player_by_id("P0")
        out = []
        for card in (_get_card(repo, "ASH", "116"), _get_card(repo, "ASH", "45"),
                     _get_card(repo, "ASH", "259"),
                     _get_card(repo, *VANILLA_SPACE),      # cost 2 but a VEHICLE
                     _get_card(repo, *VANILLA_GROUND)):    # non-Vehicle but cost 4
            ci = _place(state, "P0", card, "ground")
            ps.ground_arena.remove(ci)
            ci.zone = Zone.DISCARD
            ps.discard.append(ci)
            out.append(ci)
        return out

    def test_ASH_104_plays_up_to_three_free_units_from_the_discard(self, repo):
        from swu.engine.actions import (legal_actions, apply, PlayFromHand,
                                        DeclinePlayFromHand)
        state = _make_state()
        cheap = self._seed_discard(state, repo)[:3]
        vehicle, expensive = state.player_by_id("P0").discard[3:5]

        state, _evt = _play_event_from_hand(state, repo, "ASH", "104", resources=20)
        offered = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, PlayFromHand)}
        assert offered == {c.instance_id for c in cheap}
        assert vehicle.instance_id not in offered
        assert expensive.instance_id not in offered

        # Play two, then stop — "up to" really is stoppable.
        for _ in range(2):
            play = next(a for a in legal_actions(state) if isinstance(a, PlayFromHand))
            state = _drive_until(apply(state, play), "play_from_hand",
                                 lambda st, acts: next(
                                     (a for a in acts
                                      if type(a).__name__ == "DeclineTrigger"), None))
        stop = next(a for a in legal_actions(state)
                    if isinstance(a, DeclinePlayFromHand))
        state = apply(state, stop)
        assert not state.pending_decisions
        ps = state.player_by_id("P0")
        assert len(ps.ground_arena) + len(ps.space_arena) == 2
        # Free: the event's own cost was the only thing paid.
        assert len([c for c in ps.resources if c.exhausted]) <= 10

    def test_ASH_104_costs_1_less_with_a_force_unit(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import _play_cost

        def _cost(with_force: bool) -> int:
            state = _make_state()
            if with_force:
                _place(state, "P0", _get_card(repo, "LOF", "93"), "ground")
            ps = state.player_by_id("P0")
            ci = CardInstance("evt", _get_card(repo, "ASH", "104"), "P0", Zone.HAND)
            ps.hand.append(ci)
            return _play_cost(state, ci, ps)

        assert _cost(False) - _cost(True) == 1


class TestClanWrenLoyalistASH107:
    """When Played: Search the top 5 cards of your deck for a card that shares a
    Trait with a unit you control, reveal it, and draw it."""

    def test_ASH_107_only_offers_a_trait_sharing_card(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectSearchCard
        state = _make_state()
        loyalist = _place(state, "P0", _get_card(repo, "ASH", "107"), "ground")
        # Bottom-first, so the Trooper ends up inside the top-5 window with a
        # non-matching card beside it.
        _push_deck_top(state, "P0", _get_card(repo, *VANILLA_GROUND))   # Trooper ✔
        stranger = _push_deck_top(state, "P0", _get_card(repo, *VANILLA_SPACE))

        state = _drive_until(_fire_when_played(state, loyalist), "deck_search")
        picks = [a for a in legal_actions(state) if isinstance(a, SelectSearchCard)]
        assert picks and stranger.instance_id not in {a.instance_id for a in picks}
        drawn = picks[0].instance_id
        state = _drive(apply(state, picks[0]))
        assert drawn in {c.instance_id for c in state.player_by_id("P0").hand}


class TestAntDroidASH116:
    """When Defeated: Draw a card."""

    def test_ASH_116_draws_when_defeated(self, repo):
        state = _make_state()
        droid = _place(state, "P0", _get_card(repo, "ASH", "116"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, *VANILLA_GROUND))
        before = len(state.player_by_id("P0").hand)
        state = _drive(_fire_when_defeated(state, droid))
        assert len(state.player_by_id("P0").hand) == before + 1


# ── ash-set:10 — Card advantage & disruption ─────────────────────────────────


class TestBothan5ASH128:
    """When another friendly non-Vehicle unit is defeated: You may have this unit
    capture that unit from your discard pile.  Once each round."""

    def test_ASH_128_captures_the_corpse_from_the_discard(self, repo):
        from swu.engine.actions import _defeat_unit, apply, legal_actions
        state = _make_state()
        bothan = _place(state, "P0", _get_card(repo, "ASH", "128"), "ground")
        friend = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")

        _defeat_unit(state, state.player_by_id("P0"), friend)
        accept = next(a for a in legal_actions(state)
                      if type(a).__name__ == "AcceptTrigger")
        state = _drive(apply(state, accept))

        ps = state.player_by_id("P0")
        assert friend.instance_id in {c.instance_id for c in ps.capture_pile}
        assert friend.instance_id not in {c.instance_id for c in ps.discard}
        assert next(c for c in ps.capture_pile
                    if c.instance_id == friend.instance_id).captured_by == bothan.instance_id

    def test_ASH_128_ignores_a_friendly_vehicle(self, repo):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        _place(state, "P0", _get_card(repo, "ASH", "128"), "ground")
        vehicle = _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")
        _defeat_unit(state, state.player_by_id("P0"), vehicle)
        assert not state.pending_decisions
        assert vehicle.instance_id in {c.instance_id
                                       for c in state.player_by_id("P0").discard}


class TestAxeWovesASH169:
    """When you draw 1 or more cards (including during the regroup phase): Give an
    Advantage token to this unit."""

    def _draw_and_settle(self, state, repo, phase):
        from swu.engine.actions import _draw_cards, _fire_draw_observers
        state.phase = phase
        _push_deck_top(state, "P0", _get_card(repo, *VANILLA_GROUND))
        _draw_cards(state, state.player_by_id("P0"), 1)
        return _drive(_fire_draw_observers(state))

    def test_ASH_169_gets_an_advantage_token_on_an_action_phase_draw(self, repo):
        from swu.engine.state import Phase
        state = _make_state()
        axe = _place(state, "P0", _get_card(repo, "ASH", "169"), "ground")
        state = self._draw_and_settle(state, repo, Phase.ACTION)
        assert _advantage_count(_find_instance(state, axe.instance_id)) == 1

    def test_ASH_169_also_fires_in_the_regroup_phase(self, repo):
        from swu.engine.state import Phase
        state = _make_state()
        axe = _place(state, "P0", _get_card(repo, "ASH", "169"), "ground")
        state = self._draw_and_settle(state, repo, Phase.REGROUP)
        assert _advantage_count(_find_instance(state, axe.instance_id)) == 1

    def test_ASH_169_regroup_draw_does_not_fire_an_action_only_observer(self, repo):
        # The Mandalorian LAW_52 prints "during the action phase", so the widened
        # ledger must NOT reach it.
        from swu.engine.state import Phase
        state = _make_state()
        mando = _place(state, "P0", _get_card(repo, "LAW", "52"), "ground")
        state = self._draw_and_settle(state, repo, Phase.REGROUP)
        assert _shield_count(_find_instance(state, mando.instance_id)) == 0


class TestRazorCrestASH172:
    """On Attack: You may discard a card from your hand.  If you do, this unit gets
    +2/+0 for this attack."""

    def test_ASH_172_discards_for_plus_two_power(self, repo):
        from swu.engine.actions import compute_power, apply, legal_actions
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        crest = _place(state, "P0", _get_card(repo, "ASH", "172"), "space")
        enemy = _place(state, "P1", _get_card(repo, *BIG_SPACE), "space")
        ps = state.player_by_id("P0")
        ps.hand.append(CardInstance("P0_h1", _get_card(repo, *VANILLA_GROUND),
                                    "P0", Zone.HAND))
        base_power = compute_power(state, crest, is_attacking=True)

        fired = _fire_on_attack(state, crest, enemy)
        state = _drive(apply(fired, next(a for a in legal_actions(fired)
                                         if type(a).__name__ == "AcceptTrigger")))
        assert not state.player_by_id("P0").hand
        assert len(state.player_by_id("P0").discard) == 1
        assert compute_power(state, _find_instance(state, crest.instance_id),
                             is_attacking=True) == base_power + 2

    def test_ASH_172_is_not_offered_with_an_empty_hand(self, repo):
        state = _make_state()
        crest = _place(state, "P0", _get_card(repo, "ASH", "172"), "space")
        enemy = _place(state, "P1", _get_card(repo, *BIG_SPACE), "space")
        assert not _fire_on_attack(state, crest, enemy).pending_decisions


class TestIntimidationASH185:
    """If you control a unit with 4 or more power, draw 2 cards."""

    def test_ASH_185_draws_only_with_a_four_power_unit(self, repo):
        def _drawn(power_unit) -> int:
            state = _make_state()
            if power_unit is not None:
                _place(state, "P0", power_unit, "ground")
            for _ in range(3):
                _push_deck_top(state, "P0", _get_card(repo, *VANILLA_SPACE))
            before = len(state.player_by_id("P0").hand)
            state, _evt = _play_event_from_hand(state, repo, "ASH", "185")
            return len(_drive(state).player_by_id("P0").hand) - before

        # BIG_SPACE is 4/7; VANILLA_SPACE is 3/2.
        assert _drawn(_get_card(repo, *BIG_SPACE)) == 2
        assert _drawn(_get_card(repo, *VANILLA_SPACE)) == 0
        assert _drawn(None) == 0


class TestRemnantLookoutsASH220:
    """When Played: Look at an opponent's hand.  You may discard a card from it.  If
    you do, they draw a card."""

    def test_ASH_220_discards_from_the_opponent_hand_and_they_draw(self, repo):
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import apply, legal_actions
        state = _make_state()
        lookouts = _place(state, "P0", _get_card(repo, "ASH", "220"), "ground")
        opp = state.player_by_id("P1")
        opp.hand.append(CardInstance("P1_h1", _get_card(repo, *VANILLA_GROUND),
                                     "P1", Zone.HAND))
        _push_deck_top(state, "P1", _get_card(repo, *VANILLA_SPACE))

        state = _drive_until(_fire_when_played(state, lookouts), "name_and_discard")
        pick = next(a for a in legal_actions(state)
                    if type(a).__name__ == "NameAndDiscard")
        state = _drive(apply(state, pick))
        # One discarded, one drawn back — hand size unchanged, discard grew.
        assert len(state.player_by_id("P1").discard) == 1
        assert len(state.player_by_id("P1").hand) == 1


class TestCamtonoASH229:
    """Attached unit gains: "When Attack Ends: Look at the top card of your deck.  If
    it costs 2 or less, you may play it for free"."""

    def _attack_end_peek(self, repo, top_card):
        """A real BASE attack: the attacker always survives, so "When Attack Ends"
        fires with the host as source."""
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        upg = _place(state, "P0", _get_card(repo, "ASH", "229"), "ground")
        state.player_by_id("P0").ground_arena.remove(upg)
        host.attached_upgrades.append(upg)
        _push_deck_top(state, "P0", top_card)
        return _attack(state, host), host

    def test_ASH_229_offers_a_free_play_of_a_cheap_top_card(self, repo):
        from swu.engine.actions import apply, legal_actions
        state, host = self._attack_end_peek(repo, _get_card(repo, *VANILLA_SPACE))
        kinds = {type(a).__name__ for a in legal_actions(state)}
        assert "PlayTopCard" in kinds and "KeepTopCard" in kinds
        state = _drive(apply(state, next(a for a in legal_actions(state)
                                         if type(a).__name__ == "PlayTopCard")))
        ps = state.player_by_id("P0")
        assert len(ps.space_arena) == 1
        assert not [c for c in ps.resources if c.exhausted]   # free

    def test_ASH_229_only_reveals_an_expensive_top_card(self, repo):
        from swu.engine.actions import legal_actions
        state, _host = self._attack_end_peek(repo, _get_card(repo, *VANILLA_GROUND))
        kinds = {type(a).__name__ for a in legal_actions(state)}
        assert kinds == {"KeepTopCard"}


class TestImprovisedIdentityASH230:
    """Attached unit gains: "Action: Search the top 3 for a ground unit and discard
    it.  Then, you may attack with this unit, gaining the discarded unit's
    abilities"."""

    def test_ASH_230_discards_a_ground_unit_and_borrows_its_abilities(self, repo):
        from swu.engine.actions import (legal_actions, apply, UseAbility,
                                        SelectSearchCard, AttackWithUnit)
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        upg = _place(state, "P0", _get_card(repo, "ASH", "230"), "ground")
        state.player_by_id("P0").ground_arena.remove(upg)
        host.attached_upgrades.append(upg)
        # The lender: Swoop Bike Marauder LAW_107, a ground unit whose ONLY ability
        # is "On Attack: Draw a card" — so exactly one draw proves the borrow (the
        # Support test's lender).  A SPACE unit sits above it and must not be offered.
        _push_deck_top(state, "P0", _get_card(repo, *VANILLA_GROUND))
        lender = _push_deck_top(state, "P0", _get_card(repo, "LAW", "107"))
        space = _push_deck_top(state, "P0", _get_card(repo, *VANILLA_SPACE))

        use = next(a for a in legal_actions(state) if isinstance(a, UseAbility))
        assert use.source_id == upg.instance_id
        state = _drive_until(apply(state, use), "deck_search")
        picks = {a.instance_id for a in legal_actions(state)
                 if isinstance(a, SelectSearchCard)}
        assert lender.instance_id in picks and space.instance_id not in picks
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, SelectSearchCard)
                    and a.instance_id == lender.instance_id)
        state = _drive_until(apply(state, pick), "granted_attack")

        assert lender.instance_id in {c.instance_id
                                      for c in state.player_by_id("P0").discard}
        before = len(state.player_by_id("P0").hand)
        attack = next(a for a in legal_actions(state) if isinstance(a, AttackWithUnit))
        state = _drive(apply(state, attack))
        # The borrowed "On Attack: Draw a card" fired exactly once, from the host.
        assert len(state.player_by_id("P0").hand) == before + 1

    def test_ASH_230_is_once_each_round(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        upg = _place(state, "P0", _get_card(repo, "ASH", "230"), "ground")
        state.player_by_id("P0").ground_arena.remove(upg)
        host.attached_upgrades.append(upg)
        _push_deck_top(state, "P0", _get_card(repo, "LAW", "107"))

        use = next(a for a in legal_actions(state) if isinstance(a, UseAbility))
        state = _drive(apply(state, use))
        assert not [a for a in legal_actions(state) if isinstance(a, UseAbility)]


# ── ash-set:11 — Card advantage & disruption ─────────────────────────────────


class TestFullOfSurprisesASH232:
    """Return an upgrade that costs 2 or less to its owner's hand.  Give a Shield
    token to a unit."""

    def test_ASH_232_bounces_a_cheap_upgrade_and_shields_a_unit(self, repo):
        from swu.engine.actions import ChooseTarget
        state = _make_state()
        host = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        cheap = _place(state, "P1", _get_card(repo, "ASH", "210"), "ground")  # cost 1
        state.player_by_id("P1").ground_arena.remove(cheap)
        host.attached_upgrades.append(cheap)
        mine = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")

        state, _evt = _play_event_from_hand(state, repo, "ASH", "232")

        # Two single-effect EventAbilities push in order, so their decisions resolve
        # LIFO (the Barrel Roll JTL_228 ordering) — route each ChooseTarget by the
        # id it offers rather than assuming which clause is on top.
        wanted = {cheap.instance_id, mine.instance_id}

        def _pick(st, acts):
            return next((a for a in acts if isinstance(a, ChooseTarget)
                         and a.target_id in wanted), None)

        state = _drive(state, _pick)

        assert cheap.instance_id in {c.instance_id
                                     for c in state.player_by_id("P1").hand}
        assert _shield_count(_find_instance(state, mine.instance_id)) == 1


class TestSenseThroughTheForceASH235:
    """Choose a number, then search the top 5 for a card, reveal it, and draw it.  If
    its cost is the chosen number, you may give 3 Advantage tokens to a Force
    unit."""

    def _run(self, repo, number):
        from swu.engine.actions import (legal_actions, apply, ChooseNumber,
                                        SelectSearchCard)
        state = _make_state()
        force_unit = _place(state, "P0", _get_card(repo, "LOF", "93"), "ground")  # 2
        _push_deck_top(state, "P0", _get_card(repo, *VANILLA_SPACE))              # 2
        state, _evt = _play_event_from_hand(state, repo, "ASH", "235")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseNumber) and a.number == number))
        pick = next(a for a in legal_actions(state) if isinstance(a, SelectSearchCard))
        drawn = pick.instance_id
        return _drive(apply(state, pick), _accept_and_target(force_unit)), force_unit, drawn

    def test_ASH_235_gives_three_advantage_tokens_on_a_cost_match(self, repo):
        state, force_unit, drawn = self._run(repo, 2)   # VANILLA_SPACE costs 2
        assert drawn in {c.instance_id for c in state.player_by_id("P0").hand}
        assert _advantage_count(_find_instance(state, force_unit.instance_id)) == 3

    def test_ASH_235_gives_nothing_on_a_miss(self, repo):
        state, force_unit, drawn = self._run(repo, 7)
        assert drawn in {c.instance_id for c in state.player_by_id("P0").hand}
        assert _advantage_count(_find_instance(state, force_unit.instance_id)) == 0


class TestFarFarAwayASH236:
    """Return a friendly non-leader unit to its owner's hand.  If you do, return an
    enemy non-leader unit to its owner's hand."""

    def test_ASH_236_bounces_one_of_each(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        theirs = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")

        state, _evt = _play_event_from_hand(state, repo, "ASH", "236")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == mine.instance_id))
        state = _drive(apply(state, next(a for a in legal_actions(state)
                                         if isinstance(a, ChooseTarget)
                                         and a.target_id == theirs.instance_id)))
        assert mine.instance_id in {c.instance_id for c in state.player_by_id("P0").hand}
        assert theirs.instance_id in {c.instance_id for c in state.player_by_id("P1").hand}

    def test_ASH_236_does_nothing_without_a_friendly_unit(self, repo):
        state = _make_state()
        theirs = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        state, _evt = _play_event_from_hand(state, repo, "ASH", "236")
        state = _drive(state)
        assert _find_instance(state, theirs.instance_id) is not None


class TestExploitAdvantageASH246:
    """Defeat a friendly upgrade.  If you do, draw 2 cards."""

    def test_ASH_246_defeats_a_friendly_upgrade_and_draws_two(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        upg = _place(state, "P0", _get_card(repo, "ASH", "210"), "ground")
        state.player_by_id("P0").ground_arena.remove(upg)
        host.attached_upgrades.append(upg)
        # An upgrade on an ENEMY unit is not "a friendly upgrade".
        enemy_host = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        theirs = _place(state, "P1", _get_card(repo, "ASH", "210"), "ground")
        state.player_by_id("P1").ground_arena.remove(theirs)
        enemy_host.attached_upgrades.append(theirs)
        for _ in range(3):
            _push_deck_top(state, "P0", _get_card(repo, *VANILLA_SPACE))

        state, _evt = _play_event_from_hand(state, repo, "ASH", "246")
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget) and a.target_id}
        assert offered == {upg.instance_id}
        before = len(state.player_by_id("P0").hand)
        state = _drive(apply(state, next(a for a in legal_actions(state)
                                         if isinstance(a, ChooseTarget)
                                         and a.target_id == upg.instance_id)))
        assert len(state.player_by_id("P0").hand) == before + 2
        assert upg.instance_id in {c.instance_id
                                   for c in state.player_by_id("P0").discard}


class TestOneMustDestroyToCreateASH247:
    """Defeat a friendly non-leader unit.  Then, you may play that unit from your
    discard pile for free."""

    def test_ASH_247_replays_the_defeated_unit_for_free(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, PlayFromHand
        state = _make_state()
        victim = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")

        state, _evt = _play_event_from_hand(state, repo, "ASH", "247")
        state = _drive_until(apply(state, next(
            a for a in legal_actions(state) if isinstance(a, ChooseTarget)
            and a.target_id == victim.instance_id)), "play_from_hand")
        plays = [a for a in legal_actions(state) if isinstance(a, PlayFromHand)]
        assert {a.instance_id for a in plays} == {victim.instance_id}
        state = _drive(apply(state, plays[0]))
        assert _find_instance(state, victim.instance_id) is not None

    def test_ASH_247_replay_may_be_declined(self, repo):
        from swu.engine.actions import (legal_actions, apply, ChooseTarget,
                                        DeclinePlayFromHand)
        state = _make_state()
        victim = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        state, _evt = _play_event_from_hand(state, repo, "ASH", "247")
        state = _drive_until(apply(state, next(
            a for a in legal_actions(state) if isinstance(a, ChooseTarget)
            and a.target_id == victim.instance_id)), "play_from_hand")
        state = _drive(apply(state, next(a for a in legal_actions(state)
                                         if isinstance(a, DeclinePlayFromHand))))
        assert _find_instance(state, victim.instance_id) is None
        assert victim.instance_id in {c.instance_id
                                      for c in state.player_by_id("P0").discard}


class TestMosEspaWatermongerASH260:
    """When Played: You may draw a card.  If you do, discard a card."""

    def test_ASH_260_draws_then_discards(self, repo):
        from swu.engine.actions import legal_actions, apply
        state = _make_state()
        monger = _place(state, "P0", _get_card(repo, "ASH", "260"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, *VANILLA_SPACE))
        before = len(state.player_by_id("P0").hand)

        fired = _fire_when_played(state, monger)
        state = _drive(apply(fired, next(a for a in legal_actions(fired)
                                         if type(a).__name__ == "AcceptTrigger")))
        ps = state.player_by_id("P0")
        assert len(ps.hand) == before          # drew one, discarded one
        assert len(ps.discard) == 1

    def test_ASH_260_may_be_declined(self, repo):
        from swu.engine.actions import legal_actions, apply
        state = _make_state()
        monger = _place(state, "P0", _get_card(repo, "ASH", "260"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, *VANILLA_SPACE))
        fired = _fire_when_played(state, monger)
        state = _drive(apply(fired, next(a for a in legal_actions(fired)
                                         if type(a).__name__ == "DeclineTrigger")))
        assert not state.player_by_id("P0").discard
        assert len(state.player_by_id("P0").deck) == 1


# ══ ash-set:12 — the ASH LEADER block ══════════════════════════════════════

VANILLA_UPGRADE = ("SOR", "120")   # Academy Training, +2/+2, no text


def _resource_card(state, owner_id, card_def, exhausted=False):
    """Put a specific card into a player's RESOURCE row (face down)."""
    import uuid as _u
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(instance_id=f"{owner_id}_res_{_u.uuid4().hex[:6]}",
                      card_def=card_def, owner_id=owner_id, zone=Zone.RESOURCES)
    ci.face_down = True
    ci.exhausted = exhausted
    state.player_by_id(owner_id).resources.append(ci)
    return ci


def _leader_ability(state, leader_ci, idx):
    """The UseAbility for one of a leader's registered ability indices, or None."""
    from swu.engine.actions import legal_actions, UseAbility
    for a in legal_actions(state):
        if (isinstance(a, UseAbility) and a.source_id == leader_ci.instance_id
                and getattr(a, "ability_idx", 0) == idx):
            return a
    return None


class TestTheArmorerASH1:
    """Undeployed Action: "Play an upgrade from your resources on a unit that
    entered play this phase (paying its cost).  If you do, resource the top card of
    your deck." """

    def test_ASH_1_plays_a_resource_upgrade_onto_a_unit_played_this_phase(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayUpgradeFromHand
        state = _make_state()
        armorer = _place_leader(state, "P0", _get_by_type(repo, "ASH", "1", "Leader"))
        fresh = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        veteran = _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")
        upgrade = _resource_card(state, "P0", _get_card(repo, *VANILLA_UPGRADE))
        for _ in range(6):
            _add_resource(state, repo, "P0", exhausted=False)
        _push_deck_top(state, "P0", _get_card(repo, *VANILLA_GROUND))

        # No unit has entered play this phase, so the Exhaust is never offered.
        assert _leader_ability(state, armorer, 0) is None

        state.game_memory.units_played_this_phase.add(fresh.instance_id)
        act = _leader_ability(state, armorer, 0)
        assert act is not None
        state = apply(state, act)

        # Only the unit that entered play this phase is a legal host.
        hosts = {a.host_id for a in legal_actions(state)
                 if isinstance(a, PlayUpgradeFromHand)}
        assert hosts == {fresh.instance_id}
        assert veteran.instance_id not in hosts

        deck_before = len(state.player_by_id("P0").deck)
        state = _drive(apply(state, next(a for a in legal_actions(state)
                                         if isinstance(a, PlayUpgradeFromHand))))

        ps = state.player_by_id("P0")
        host = _find_instance(state, fresh.instance_id)
        assert upgrade.instance_id in {u.instance_id for u in host.attached_upgrades}
        assert upgrade.instance_id not in {r.instance_id for r in ps.resources}
        # "If you do, resource the top card of your deck."
        assert len(ps.deck) == deck_before - 1


class TestFennecShandASH2:
    """Undeployed Action [1 resource, Exhaust, exhaust a friendly unit]: "Play a
    unit from your hand (paying its cost).  It enters play ready." """

    def test_ASH_2_exhausts_a_friendly_unit_and_plays_a_unit_ready(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, PlayFromHand
        state = _make_state()
        fennec = _place_leader(state, "P0", _get_by_type(repo, "ASH", "2", "Leader"))
        helper = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        in_hand = _to_hand(state, "P0", _get_card(repo, *VANILLA_SPACE))
        for _ in range(8):
            _add_resource(state, repo, "P0", exhausted=False)

        state = apply(state, _leader_ability(state, fennec, 0))
        # The printed cost "exhaust a friendly unit" is a leading targeted effect.
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == helper.instance_id))
        state = _drive_until(state, "play_from_hand")
        state = _drive(apply(state, next(a for a in legal_actions(state)
                                         if isinstance(a, PlayFromHand)
                                         and a.instance_id == in_hand.instance_id)))

        played = _find_instance(state, in_hand.instance_id)
        assert played is not None and not played.exhausted   # "enters play ready"
        assert _find_instance(state, helper.instance_id).exhausted
        assert _find_instance(state, fennec.instance_id) is None  # still undeployed
        assert state.find_instance(fennec.instance_id)[1].exhausted  # the Exhaust cost


class TestBaylanSkollASH3:
    """Undeployed: "+2/+2 for this phase if it's the only unit you control in its
    arena".  Deployed On Attack: the same, plus Sentinel, over NON-LEADER units."""

    def test_ASH_3_undeployed_offers_only_a_lone_unit(self, repo):
        from swu.engine.actions import apply, compute_power
        state = _make_state()
        baylan = _place_leader(state, "P0", _get_by_type(repo, "ASH", "3", "Leader"))
        # Two ground units: neither is alone.  One space unit: it is.
        crowd_a = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        lone = _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")
        for _ in range(3):
            _add_resource(state, repo, "P0", exhausted=False)

        state = apply(state, _leader_ability(state, baylan, 0))
        assert _target_ids(state) == {lone.instance_id}
        assert crowd_a.instance_id not in _target_ids(state)

        before = compute_power(state, lone)
        state = _drive(state)
        assert compute_power(state, _find_instance(state, lone.instance_id)) == before + 2

    def test_ASH_3_deployed_grants_plus_two_and_sentinel_to_one_unit(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        baylan = _place(state, "P0", _get_by_type(repo, "ASH", "3", "Leader"), "ground")
        baylan.deployed = True
        # He is a LEADER, so the friendly ground unit beside him is still "the only
        # non-leader unit you control in its arena".
        buddy = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        foe = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")

        power_before = compute_power(state, buddy)
        hp_before = compute_hp(state, buddy)
        state = _drive(_fire_on_attack(state, baylan, foe),
                       _accept_and_target(buddy))
        buffed = _find_instance(state, buddy.instance_id)
        assert compute_power(state, buffed) == power_before + 2
        assert compute_hp(state, buffed) == hp_before + 2
        assert has_keyword(state, buffed, Keyword.SENTINEL)

    def test_ASH_3_printed_sentinel_is_a_mistag(self, repo):
        """He GIVES Sentinel; his own bar is empty (sanitiser rule 9, leaders)."""
        assert _get_by_type(repo, "ASH", "3", "Leader").keywords == ()

    def test_ASH_3_is_a_token_collision_number(self, repo):
        """ASH_3 is also the Shield token upgrade — only side-gated Activated /
        Trigger abilities are safe there."""
        from swu.abilities.registry import (
            get_abilities, ActivatedAbility, TriggerAbility,
        )
        for spec in get_abilities("ASH", "3"):
            assert isinstance(spec, (ActivatedAbility, TriggerAbility))
            assert spec.undeployed_only or spec.deployed_only


class TestLukeSkywalkerASH5:
    """"When a friendly unit's attack ends": exhaust to heal 1 (undeployed) /
    heal 2 from that unit or your base (deployed)."""

    def test_ASH_5_undeployed_exhausts_to_heal_the_attacker(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        state = _make_state()
        luke = _place_leader(state, "P0", _get_by_type(repo, "ASH", "5", "Leader"))
        attacker = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        attacker.damage = 3

        state = _attack(state, attacker)          # attacks the enemy base
        accept = [a for a in legal_actions(state) if isinstance(a, AcceptTrigger)]
        assert accept, "the optional heal should be offered"
        state = _drive(apply(state, accept[0]))

        assert _find_instance(state, attacker.instance_id).damage == 2
        assert state.find_instance(luke.instance_id)[1].exhausted

    def test_ASH_5_undeployed_is_not_offered_with_an_undamaged_attacker(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        _place_leader(state, "P0", _get_by_type(repo, "ASH", "5", "Leader"))
        attacker = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        state = _attack(state, attacker)
        assert not [a for a in legal_actions(state) if isinstance(a, AcceptTrigger)]

    def test_ASH_5_deployed_heals_the_attacker_or_your_base(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        luke = _place(state, "P0", _get_by_type(repo, "ASH", "5", "Leader"), "ground")
        luke.deployed = True
        attacker = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        attacker.damage = 3
        own_base = state.player_by_id("P0").base_zone[0]
        own_base.damage = 5

        state = _attack(state, attacker)
        offered = _target_ids(state)
        assert offered == {attacker.instance_id, own_base.instance_id}
        state = _drive(apply(state, next(
            a for a in legal_actions(state) if isinstance(a, ChooseTarget)
            and a.target_id == attacker.instance_id)))
        assert _find_instance(state, attacker.instance_id).damage == 1


class TestSabineWrenASH6:
    """Undeployed Action: "An opponent gives 2 Advantage tokens to a unit they
    control.  If they do, the next unit you play this phase gains Shielded." """

    def test_ASH_6_opponent_must_take_the_advantage_tokens(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectTokenTarget, FinishSelectToken,
        )
        state = _make_state()
        sabine = _place_leader(state, "P0", _get_by_type(repo, "ASH", "6", "Leader"))
        foe = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")

        state = apply(state, _leader_ability(state, sabine, 0))
        top = state.pending_decisions[-1]
        assert top.kind == "select_token"
        assert top.deciding_player_id == "P1"          # the OPPONENT chooses
        acts = legal_actions(state)
        assert not [a for a in acts if isinstance(a, FinishSelectToken)]  # mandatory

        state = _drive(apply(state, next(a for a in acts
                                         if isinstance(a, SelectTokenTarget))))
        assert _advantage_count(_find_instance(state, foe.instance_id)) == 2
        # "If they do" — the payoff is armed for SABINE's controller.
        armed = state.game_memory.pending_keyword_grants
        assert [(e["player_id"], e["keyword"]) for e in armed] == [("P0", "Shielded")]

    def test_ASH_6_arms_nothing_when_the_opponent_has_no_unit(self, repo):
        state = _make_state()
        sabine = _place_leader(state, "P0", _get_by_type(repo, "ASH", "6", "Leader"))
        from swu.engine.actions import apply
        state = _drive(apply(state, _leader_ability(state, sabine, 0)))
        assert not state.game_memory.pending_keyword_grants

    def test_ASH_6_deployed_on_attack_arms_shielded(self, repo):
        state = _make_state()
        sabine = _place(state, "P0", _get_by_type(repo, "ASH", "6", "Leader"), "ground")
        sabine.deployed = True
        foe = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        state = _drive(_fire_on_attack(state, sabine, foe))
        assert [(e["player_id"], e["keyword"])
                for e in state.game_memory.pending_keyword_grants] == [("P0", "Shielded")]


class TestGrandAdmiralSloaneASH7:
    """Undeployed: "Choose one: give each ground / each space unit Sentinel and
    Overwhelm for this phase."  Deployed: "Each other friendly unit gains Overwhelm
    and Sentinel." """

    def test_ASH_7_printed_bar_is_overwhelm_only(self, repo):
        """Her deploy box's leading line is Overwhelm; the Sentinel she only grants
        is stripped by keyword-sanitiser rule 9 (now applied to leaders)."""
        assert _get_by_type(repo, "ASH", "7", "Leader").keywords == ("Overwhelm",)

    def test_ASH_7_undeployed_arena_modal_grants_to_that_arena_only(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectModalOption
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        sloane = _place_leader(state, "P0", _get_by_type(repo, "ASH", "7", "Leader"))
        friendly_ground = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        enemy_ground = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        spacer = _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")

        state = apply(state, _leader_ability(state, sloane, 0))
        options = [a for a in legal_actions(state) if isinstance(a, SelectModalOption)]
        assert len(options) == 2                      # ground / space
        state = _drive(apply(state, options[0]))      # the ground arena

        for ci in (friendly_ground, enemy_ground):    # "each ground unit"
            live = _find_instance(state, ci.instance_id)
            assert has_keyword(state, live, Keyword.SENTINEL)
            assert has_keyword(state, live, Keyword.OVERWHELM)
        live_spacer = _find_instance(state, spacer.instance_id)
        assert not has_keyword(state, live_spacer, Keyword.SENTINEL)

    def test_ASH_7_deployed_aura_covers_other_friendly_units_only(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        sloane = _place(state, "P0", _get_by_type(repo, "ASH", "7", "Leader"), "ground")
        sloane.deployed = True
        buddy = _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")
        foe = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")

        assert has_keyword(state, buddy, Keyword.OVERWHELM)
        assert has_keyword(state, buddy, Keyword.SENTINEL)
        assert not has_keyword(state, foe, Keyword.SENTINEL)
        # "Each OTHER friendly unit" — she keeps her printed Overwhelm, not Sentinel.
        assert has_keyword(state, sloane, Keyword.OVERWHELM)
        assert not has_keyword(state, sloane, Keyword.SENTINEL)


class TestBoKatanKryzeASH10:
    """"Other friendly Mandalorian units get +1/+0"; a Mandalorian token on the
    Action / On Attack while you control a unit in each arena; and an Epic Action
    deploy condition the resource-threshold regex cannot read."""

    def _mandalorian_count(self, state, player_id="P0"):
        ps = state.player_by_id(player_id)
        return sum(1 for ci in ps.ground_arena + ps.space_arena
                   if ci.card_def.name == "Mandalorian")

    def test_ASH_10_deploys_on_resources_plus_mandalorian_units(self, repo):
        from swu.engine.actions import legal_actions, DeployLeader
        state = _make_state()
        _place_leader(state, "P0", _get_by_type(repo, "ASH", "10", "Leader"))
        for _ in range(6):
            _add_resource(state, repo, "P0", exhausted=False)
        mando = _get_by_type(repo, "ASH", "1", "Token Unit")
        for _ in range(3):
            _place(state, "P0", mando, "ground")
        # 6 resources + 3 Mandalorians = 9 — one short.
        assert not [a for a in legal_actions(state) if isinstance(a, DeployLeader)]
        _place(state, "P0", mando, "ground")
        assert [a for a in legal_actions(state) if isinstance(a, DeployLeader)]

    def test_ASH_10_buffs_other_mandalorian_units(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        bo = _place(state, "P0", _get_by_type(repo, "ASH", "10", "Leader"), "ground")
        bo.deployed = True
        mando = _place(state, "P0", _get_by_type(repo, "ASH", "1", "Token Unit"), "ground")
        plain = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        assert compute_power(state, mando) == mando.card_def.power + 1
        assert compute_power(state, plain) == plain.card_def.power
        # "OTHER friendly Mandalorian units" — she is Mandalorian but excludes herself.
        assert compute_power(state, bo) == bo.card_def.power

    def test_ASH_10_on_attack_creates_a_token_only_with_both_arenas(self, repo):
        state = _make_state()
        bo = _place(state, "P0", _get_by_type(repo, "ASH", "10", "Leader"), "ground")
        bo.deployed = True
        foe = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")

        # Ground only — the clause fails, so nothing is created.
        state = _drive(_fire_on_attack(state, bo, foe))
        assert self._mandalorian_count(state) == 0

        _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")
        state = _drive(_fire_on_attack(state, bo, foe))
        assert self._mandalorian_count(state) == 1


# ══ ash-set:13 — combat tricks, buffs & tempo ═══════════════════════════════


def _base_attack(state, attacker):
    """Attack the opponent's base and settle any resulting decision."""
    from swu.engine.actions import apply, AttackWithUnit
    return apply(state, AttackWithUnit(attacker_id=attacker.instance_id,
                                       defender_id=None))


class TestEzraBridgerASH13:
    """"When a friendly unit's attack ends: If it dealt 3 or more combat damage to
    a base, you may exhaust this leader.  If you do, give an Advantage token to a
    different unit." """

    def test_ASH_13_gives_an_advantage_token_after_a_big_base_hit(self, repo):
        from swu.engine.actions import AcceptTrigger, legal_actions
        state = _make_state()
        ezra = _place_leader(state, "P0", _get_by_type(repo, "ASH", "13", "Leader"))
        hitter = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        hitter.exhausted = False
        other = _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")

        state = _base_attack(state, hitter)            # 3 power → 3 base damage
        assert any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        state = _drive(state, _accept_and_target(other))

        assert _advantage_count(_find_instance(state, other.instance_id)) == 1
        # "a DIFFERENT unit" — never the attacker, and the leader paid with its exhaust.
        assert _advantage_count(_find_instance(state, hitter.instance_id)) == 0
        assert state.find_instance(ezra.instance_id)[1].exhausted

    def test_ASH_13_does_not_fire_below_three_base_damage(self, repo):
        from swu.engine.actions import AcceptTrigger, legal_actions
        state = _make_state()
        _place_leader(state, "P0", _get_by_type(repo, "ASH", "13", "Leader"))
        # A vanilla 2-power attacker deals only 2 to the base — under the threshold.
        weak = _place(state, "P0", _get_card(repo, *VANILLA_WEAK), "ground")
        weak.exhausted = False
        _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")

        state = _base_attack(state, weak)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestEmperorPalpatineASH15:
    """Undeployed Action [Exhaust]: "Choose an exhausted friendly unit.  Give an
    Advantage token to it for each other friendly unit." """

    def test_ASH_15_tokens_scale_with_the_other_friendly_units(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        palp = _place_leader(state, "P0", _get_by_type(repo, "ASH", "15", "Leader"))
        tired = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        tired.exhausted = True
        _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")
        _place(state, "P0", _get_card(repo, *BIG_SPACE), "space")

        act = _leader_ability(state, palp, 0)
        assert act is not None
        state = _drive(apply(state, act), _accept_and_target(tired))

        # Two other friendly units (the leader is in the base zone, not an arena).
        assert _advantage_count(_find_instance(state, tired.instance_id)) == 2

    def test_ASH_15_action_is_not_offered_without_an_exhausted_unit(self, repo):
        state = _make_state()
        palp = _place_leader(state, "P0", _get_by_type(repo, "ASH", "15", "Leader"))
        ready = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        ready.exhausted = False
        assert _leader_ability(state, palp, 0) is None


class TestShinHatiASH16:
    """"When a friendly unit's attack ends: You may exhaust this leader.  If you do,
    exhaust a unit that costs less than the amount of combat damage dealt to a base
    this attack." """

    def test_ASH_16_exhausts_a_cheaper_unit_after_a_base_hit(self, repo):
        state = _make_state()
        shin = _place_leader(state, "P0", _get_by_type(repo, "ASH", "16", "Leader"))
        hitter = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        hitter.exhausted = False
        # Cost 2 (< the 3 base damage) and ready, so it is the only legal pick.
        cheap = _place(state, "P1", _get_card(repo, *VANILLA_WEAK), "ground")
        cheap.exhausted = False

        state = _drive(_base_attack(state, hitter), _accept_and_target(cheap))

        assert _find_instance(state, cheap.instance_id).exhausted
        assert state.find_instance(shin.instance_id)[1].exhausted

    def test_ASH_16_is_not_offered_when_nothing_is_cheap_enough(self, repo):
        from swu.engine.actions import AcceptTrigger, legal_actions
        state = _make_state()
        _place_leader(state, "P0", _get_by_type(repo, "ASH", "16", "Leader"))
        hitter = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        hitter.exhausted = False
        # Cost 6, i.e. not "less than" the 3 damage dealt.
        pricey = _place(state, "P1", _get_card(repo, *BIG_SPACE), "space")
        pricey.exhausted = False

        state = _base_attack(state, hitter)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestGreefKargaASH17:
    """"When you play or create a unit: You may exhaust this leader.  If you do,
    give an Advantage token to that unit." """

    def test_ASH_17_tokens_a_created_token_unit(self, repo):
        from swu.engine.actions import _create_token_units, apply, Pass
        state = _make_state()
        greef = _place_leader(state, "P0", _get_by_type(repo, "ASH", "17", "Leader"))
        ps = state.player_by_id("P0")
        made = _create_token_units(state, ps, "Battle Droid", 1)[0]

        # The observer is a settle-drain, so it fires on the next settled action.
        state = _drive(apply(state, Pass()), _accept_and_target())

        assert _advantage_count(_find_instance(state, made.instance_id)) == 1
        assert state.find_instance(greef.instance_id)[1].exhausted

    def test_ASH_17_deployed_side_needs_no_exhaust(self, repo):
        from swu.engine.actions import _create_token_units, apply, Pass
        state = _make_state()
        greef = _place(state, "P0", _get_by_type(repo, "ASH", "17", "Leader"), "ground")
        greef.deployed = True
        greef.exhausted = False
        ps = state.player_by_id("P0")
        made = _create_token_units(state, ps, "Battle Droid", 1)[0]

        state = _drive(apply(state, Pass()), _accept_and_target())

        assert _advantage_count(_find_instance(state, made.instance_id)) == 1
        assert not _find_instance(state, greef.instance_id).exhausted


class TestMarrokASH30:
    """"Sentinel.  While this unit is upgraded, he loses Sentinel and gains
    Saboteur." """

    def test_ASH_30_swaps_sentinel_for_saboteur_when_upgraded(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        marrok = _place(state, "P0", _get_card(repo, "ASH", "30"), "ground")

        # Bare: the printed Sentinel survives the sanitiser, Saboteur does not.
        assert marrok.card_def.keywords == ("Sentinel",)
        assert has_keyword(state, marrok, Keyword.SENTINEL)
        assert not has_keyword(state, marrok, Keyword.SABOTEUR)

        _attach(state, marrok, "Shield")   # a token IS an upgrade in SWU
        assert not has_keyword(state, marrok, Keyword.SENTINEL)
        assert has_keyword(state, marrok, Keyword.SABOTEUR)


class TestHeraSyndullaASH31:
    """"When Attack Ends: If this unit dealt combat damage to a base, heal that much
    damage from your base." """

    def test_ASH_31_heals_her_base_for_the_damage_dealt(self, repo):
        state = _make_state()
        hera = _place(state, "P0", _get_card(repo, "ASH", "31"), "ground")
        hera.exhausted = False
        own_base = state.player_by_id("P0").base_instance
        own_base.damage = 7

        state = _drive(_base_attack(state, hera))

        # 3 power → 3 combat damage to the enemy base → heal 3 from her own.
        assert state.player_by_id("P0").base_instance.damage == 4
        assert state.player_by_id("P1").base_instance.damage == 3


class TestBaylanSkollASH39:
    """"When Played/When Attack Ends: If an enemy base was damaged this phase, give
    an Advantage token to a unit.  If a friendly upgrade was defeated this phase,
    you may exhaust a unit." """

    def test_ASH_39_token_clause_needs_a_damaged_enemy_base(self, repo):
        state = _make_state()
        friend = _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")

        # Nothing damaged yet — the trigger is not even collected.
        baylan = _place(state, "P0", _get_card(repo, "ASH", "39"), "ground")
        state = _drive(_fire_when_played(state, baylan))
        assert _advantage_count(_find_instance(state, friend.instance_id)) == 0

        state.player_by_id("P1").base_instance.damage = 4
        state.game_memory.bases_damaged_this_phase.add("P1")
        state = _drive(_fire_when_played(state, baylan), _accept_and_target(friend))
        assert _advantage_count(_find_instance(state, friend.instance_id)) == 1

    def test_ASH_39_exhaust_clause_needs_a_defeated_friendly_upgrade(self, repo):
        state = _make_state()
        baylan = _place(state, "P0", _get_card(repo, "ASH", "39"), "ground")
        foe = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        foe.exhausted = False

        state = _drive(_fire_when_played(state, baylan), _accept_and_target(foe))
        assert not _find_instance(state, foe.instance_id).exhausted

        state.game_memory.upgrades_defeated_this_phase.add("P0")
        state = _drive(_fire_when_played(state, baylan), _accept_and_target(foe))
        assert _find_instance(state, foe.instance_id).exhausted


# ══ ash-set:14 — combat tricks, buffs & tempo ═══════════════════════════════


class TestOutcastASH41:
    """"When a friendly unit enters play (including this one): It gets +1/+0 for
    this phase." """

    def test_ASH_41_buffs_a_unit_that_enters_play(self, repo):
        from swu.engine.actions import _create_token_units, apply, Pass, compute_power
        state = _make_state()
        _place(state, "P0", _get_card(repo, "ASH", "41"), "ground")
        ps = state.player_by_id("P0")
        made = _create_token_units(state, ps, "Battle Droid", 1)[0]

        state = _drive(apply(state, Pass()))

        arrival = _find_instance(state, made.instance_id)
        assert compute_power(state, arrival) == arrival.card_def.power + 1

    def test_ASH_41_does_not_buff_an_enemy_arrival(self, repo):
        from swu.engine.actions import _create_token_units, apply, Pass, compute_power
        state = _make_state()
        _place(state, "P0", _get_card(repo, "ASH", "41"), "ground")
        made = _create_token_units(state, state.player_by_id("P1"),
                                   "Battle Droid", 1)[0]

        state = _drive(apply(state, Pass()))

        arrival = _find_instance(state, made.instance_id)
        assert compute_power(state, arrival) == arrival.card_def.power


class TestBarrissOfeeASH44:
    """"When Played: Heal up to 2 damage from a unit.  Give an Advantage token to it
    for each damage healed this way." """

    def test_ASH_44_tokens_match_the_damage_actually_healed(self, repo):
        state = _make_state()
        barriss = _place(state, "P0", _get_card(repo, "ASH", "44"), "ground")
        hurt = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        hurt.damage = 2

        state = _drive(_fire_when_played(state, barriss), _accept_and_target(hurt))

        healed = _find_instance(state, hurt.instance_id)
        assert healed.damage == 0
        assert _advantage_count(healed) == 2

    def test_ASH_44_heals_only_what_is_there(self, repo):
        state = _make_state()
        barriss = _place(state, "P0", _get_card(repo, "ASH", "44"), "ground")
        hurt = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        hurt.damage = 1

        state = _drive(_fire_when_played(state, barriss), _accept_and_target(hurt))

        healed = _find_instance(state, hurt.instance_id)
        assert healed.damage == 0
        assert _advantage_count(healed) == 1


class TestShinHatiASH49:
    """"While this is the only friendly non-leader ground unit, she gains
    Sentinel." """

    def test_ASH_49_sentinel_only_while_she_stands_alone(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        shin = _place(state, "P0", _get_card(repo, "ASH", "49"), "ground")
        assert shin.card_def.keywords == ()      # the printed mistag is stripped
        assert has_keyword(state, shin, Keyword.SENTINEL)

        # A friendly SPACE unit is in another arena, so the clause still holds.
        _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")
        assert has_keyword(state, shin, Keyword.SENTINEL)

        _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        assert not has_keyword(state, shin, Keyword.SENTINEL)

    def test_ASH_49_a_friendly_leader_does_not_break_the_clause(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        shin = _place(state, "P0", _get_card(repo, "ASH", "49"), "ground")
        boss = _place(state, "P0", _get_by_type(repo, "ASH", "10", "Leader"), "ground")
        boss.deployed = True
        assert has_keyword(state, shin, Keyword.SENTINEL)


class TestReinforcingLightCruiserASH51:
    """"Restore 1.  When Played: You may exhaust a unit." """

    def test_ASH_51_exhausts_a_ready_unit(self, repo):
        state = _make_state()
        cruiser = _place(state, "P0", _get_card(repo, "ASH", "51"), "space")
        foe = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        foe.exhausted = False

        state = _drive(_fire_when_played(state, cruiser), _accept_and_target(foe))
        assert _find_instance(state, foe.instance_id).exhausted

    def test_ASH_51_is_not_offered_with_no_ready_unit(self, repo):
        from swu.engine.actions import AcceptTrigger, legal_actions
        state = _make_state()
        cruiser = _place(state, "P0", _get_card(repo, "ASH", "51"), "space")
        cruiser.exhausted = True
        foe = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        foe.exhausted = True

        state = _fire_when_played(state, cruiser)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestChimaeraASH52:
    """"When Played: You may choose a friendly unit and an enemy non-leader unit.
    If you do, defeat those units.  |  When an enemy unit is defeated: Heal 2
    damage from your base." """

    def test_ASH_52_defeats_both_chosen_units(self, repo):
        state = _make_state()
        chimaera = _place(state, "P0", _get_card(repo, "ASH", "52"), "space")
        mine = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        theirs = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")

        state = _drive(_fire_when_played(state, chimaera))

        assert _find_instance(state, mine.instance_id) is None
        assert _find_instance(state, theirs.instance_id) is None

    def test_ASH_52_heals_two_when_an_enemy_unit_is_defeated(self, repo):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        _place(state, "P0", _get_card(repo, "ASH", "52"), "space")
        theirs = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        state.player_by_id("P0").base_instance.damage = 5

        _defeat_unit(state, state.player_by_id("P1"), theirs)
        state = _drive(state)

        assert state.player_by_id("P0").base_instance.damage == 3


class TestLothalEWingASH57:
    """"While an enemy unit is upgraded, this unit gains Restore 2." """

    def test_ASH_57_gains_restore_two_when_an_enemy_is_upgraded(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        ewing = _place(state, "P0", _get_card(repo, "ASH", "57"), "space")
        foe = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")

        assert not has_keyword(state, ewing, Keyword.RESTORE)
        _attach(state, foe, "Shield")
        assert keyword_value(state, ewing, Keyword.RESTORE) == 2


class TestTheArmorerASH64:
    """"Shielded.  When Played: Give a Shield token to each friendly unit with
    Shielded (including this one)." """

    def test_ASH_64_shields_every_shielded_friendly_unit(self, repo):
        from swu.abilities.resolver import _make_kw_modifier
        from swu.abilities.registry import Duration
        state = _make_state()
        armorer = _place(state, "P0", _get_card(repo, "ASH", "64"), "ground")
        shielded_friend = _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")
        state.modifiers.append(_make_kw_modifier(
            state, armorer.instance_id, shielded_friend.instance_id,
            keyword="Shielded", value=0, duration=Duration.PERMANENT,
            kind="keyword_grant"))
        plain_friend = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        shielded_foe = _place(state, "P1", _get_card(repo, "ASH", "64"), "ground")

        state = _drive(_fire_when_played(state, armorer))

        assert _shield_count(_find_instance(state, armorer.instance_id)) == 1
        assert _shield_count(_find_instance(state, shielded_friend.instance_id)) == 1
        assert _shield_count(_find_instance(state, plain_friend.instance_id)) == 0
        assert _shield_count(_find_instance(state, shielded_foe.instance_id)) == 0


# ══ ash-set:15 — combat tricks, buffs & tempo ═══════════════════════════════


class TestHomeOneASH65:
    """"Sentinel.  When Played: Heal all damage from each friendly unit." """

    def test_ASH_65_heals_every_friendly_unit_completely(self, repo):
        state = _make_state()
        home_one = _place(state, "P0", _get_card(repo, "ASH", "65"), "space")
        hurt_a = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        hurt_a.damage = 5
        hurt_b = _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")
        hurt_b.damage = 1
        enemy = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        enemy.damage = 4

        state = _drive(_fire_when_played(state, home_one))

        assert _find_instance(state, hurt_a.instance_id).damage == 0
        assert _find_instance(state, hurt_b.instance_id).damage == 0
        assert _find_instance(state, enemy.instance_id).damage == 4


class TestLukesJediLightsaberASH66:
    """"If attached unit is Luke Skywalker, he gains Sentinel." """

    def test_ASH_66_grants_sentinel_only_to_luke(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        saber = _get_card(repo, "ASH", "66")
        luke = _place(state, "P0", _get_card(repo, "SOR", "51"), "ground")
        other = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        assert luke.card_def.name == "Luke Skywalker"

        for host, expected in ((other, False), (luke, True)):
            up = CardInstance(instance_id=f"up_{host.instance_id}", card_def=saber,
                              owner_id="P0", zone=Zone.GROUND_ARENA)
            host.attached_upgrades.append(up)
            assert has_keyword(state, host, Keyword.SENTINEL) is expected


class TestPalaceChefDroidASH73:
    """"Sentinel.  This unit gets +2/+0 while defending." """

    def test_ASH_73_gets_two_power_only_while_defending(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        droid = _place(state, "P0", _get_card(repo, "ASH", "73"), "ground")

        assert compute_power(state, droid) == droid.card_def.power
        assert compute_power(state, droid, is_defending=True) == (
            droid.card_def.power + 2)


class TestPitDroidTeamASH75:
    """"The first upgrade you play on another friendly unit each phase costs 1
    resource less." """

    def test_ASH_75_discounts_an_upgrade_on_another_friendly_unit(self, repo):
        from swu.engine.actions import _play_cost
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        pit = _place(state, "P0", _get_card(repo, "ASH", "75"), "ground")
        other = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        foe = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        ps = state.player_by_id("P0")
        up = CardInstance(instance_id="P0_up", card_def=_get_card(repo, *VANILLA_UPGRADE),
                          owner_id="P0", zone=Zone.HAND)
        ps.hand.append(up)

        full = _play_cost(state, up, ps, target_host_id=pit.instance_id)
        # "on ANOTHER friendly unit" — not on Pit Droid Team itself, not on an enemy.
        assert _play_cost(state, up, ps, target_host_id=other.instance_id) == full - 1
        assert _play_cost(state, up, ps, target_host_id=foe.instance_id) == full

    def test_ASH_75_discount_is_spent_after_the_first_upgrade(self, repo):
        from swu.engine.actions import (
            _play_cost, _consume_standing_discount)
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        pit = _place(state, "P0", _get_card(repo, "ASH", "75"), "ground")
        other = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        ps = state.player_by_id("P0")
        up = CardInstance(instance_id="P0_up", card_def=_get_card(repo, *VANILLA_UPGRADE),
                          owner_id="P0", zone=Zone.HAND)
        ps.hand.append(up)

        before = _play_cost(state, up, ps, target_host_id=other.instance_id)
        _consume_standing_discount(state, up, ps, target_host_id=other.instance_id)
        assert _play_cost(state, up, ps, target_host_id=other.instance_id) == before + 1


class TestBWingRearguardASH78:
    """"While you control a ground unit, this unit gains Sentinel." """

    def test_ASH_78_sentinel_follows_a_friendly_ground_unit(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        bwing = _place(state, "P0", _get_card(repo, "ASH", "78"), "space")
        assert not has_keyword(state, bwing, Keyword.SENTINEL)

        # An ENEMY ground unit is not "you control".
        _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        assert not has_keyword(state, bwing, Keyword.SENTINEL)

        _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        assert has_keyword(state, bwing, Keyword.SENTINEL)


class TestKoskaReevesASH79:
    """"While you control a token unit, this unit gains Sentinel.  |  When Played:
    If a friendly unit was defeated this phase, create a Mandalorian token." """

    def test_ASH_79_sentinel_needs_a_friendly_token_unit(self, repo):
        from swu.engine.actions import _create_token_units
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        koska = _place(state, "P0", _get_card(repo, "ASH", "79"), "ground")
        assert not has_keyword(state, koska, Keyword.SENTINEL)

        _create_token_units(state, state.player_by_id("P0"), "Battle Droid", 1)
        assert has_keyword(state, koska, Keyword.SENTINEL)

    def test_ASH_79_creates_a_mandalorian_only_after_a_friendly_defeat(self, repo):
        def _mandos(st):
            return sum(1 for u in st.player_by_id("P0").ground_arena
                       if u.card_def.name == "Mandalorian")
        state = _make_state()
        koska = _place(state, "P0", _get_card(repo, "ASH", "79"), "ground")

        state = _drive(_fire_when_played(state, koska))
        assert _mandos(state) == 0

        state.game_memory.defeated_controllers_this_round.append("P0")
        state = _drive(_fire_when_played(state, koska))
        assert _mandos(state) == 1


class TestNebulonCFrigateASH81:
    """"When Played: You may heal 3 damage from a unit or base." """

    def test_ASH_81_heals_a_damaged_base(self, repo):
        state = _make_state()
        frigate = _place(state, "P0", _get_card(repo, "ASH", "81"), "space")
        own_base = state.player_by_id("P0").base_instance
        own_base.damage = 5

        state = _drive(_fire_when_played(state, frigate),
                       _accept_and_target(own_base))
        assert state.player_by_id("P0").base_instance.damage == 2

    def test_ASH_81_is_not_offered_with_nothing_damaged(self, repo):
        from swu.engine.actions import AcceptTrigger, legal_actions
        state = _make_state()
        frigate = _place(state, "P0", _get_card(repo, "ASH", "81"), "space")
        _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")

        state = _fire_when_played(state, frigate)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


# ══ ash-set:16 — combat tricks, buffs & tempo ═══════════════════════════════


class TestTrexlerArmoredMarauderASH82:
    """"Grit.  When Played: You may give a Shield token to a unit that costs 3 or
    less." """

    def test_ASH_82_shields_only_a_cheap_unit(self, repo):
        state = _make_state()
        trexler = _place(state, "P0", _get_card(repo, "ASH", "82"), "ground")
        cheap = _place(state, "P0", _get_card(repo, *VANILLA_WEAK), "ground")
        pricey = _place(state, "P0", _get_card(repo, *BIG_SPACE), "space")

        state = _drive_until(_fire_when_played(state, trexler), "resolve_effects",
                             _accept_and_target())
        offered = _target_ids(state)
        assert cheap.instance_id in offered
        assert pricey.instance_id not in offered

        state = _drive(state, _accept_and_target(cheap))
        assert _shield_count(_find_instance(state, cheap.instance_id)) == 1


class TestDurasteelPlatingASH86:
    """"When Played: Give a Shield token to attached unit." """

    def test_ASH_86_shields_its_own_host(self, repo):
        from tests.test_sor_cards import _fire_upgrade_played
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        plating = CardInstance(instance_id="P0_plating",
                               card_def=_get_card(repo, "ASH", "86"),
                               owner_id="P0", zone=Zone.GROUND_ARENA)
        host.attached_upgrades.append(plating)

        state = _drive(_fire_upgrade_played(state, plating, host))
        assert _shield_count(_find_instance(state, host.instance_id)) == 1


class TestTheConflictWithinASH88:
    """"Attached unit gains: 'When this unit readies: You may pay 3 resources.  If
    you don't, exhaust this unit.'" """

    def test_ASH_88_offers_pay_or_exhaust_when_the_host_readies(self, repo):
        from swu.engine.actions import (
            apply, Pass, note_unit_readied, PayToAvoidExhaust, AcceptExhaust,
            legal_actions)
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        host.exhausted = True
        host.attached_upgrades.append(CardInstance(
            instance_id="P0_conflict", card_def=_get_card(repo, "ASH", "88"),
            owner_id="P0", zone=Zone.GROUND_ARENA))
        for _ in range(4):
            _add_resource(state, repo, "P0", exhausted=False)

        note_unit_readied(state, host)
        host.exhausted = False
        state = apply(state, Pass())

        acts = legal_actions(state)
        assert any(isinstance(a, PayToAvoidExhaust) for a in acts)
        accept = next(a for a in acts if isinstance(a, AcceptExhaust))
        state = _drive(apply(state, accept))
        assert _find_instance(state, host.instance_id).exhausted


class TestPerseveranceASH89:
    """"Heal 3 damage from a unit and give a Shield token to it." """

    def test_ASH_89_heals_and_shields_the_same_unit(self, repo):
        state = _make_state()
        hurt = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        hurt.damage = 5
        other = _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")

        state, _ = _play_event_from_hand(state, repo, "ASH", "89")
        state = _drive(state, _accept_and_target(hurt))

        healed = _find_instance(state, hurt.instance_id)
        assert healed.damage == 2
        assert _shield_count(healed) == 1
        assert _shield_count(_find_instance(state, other.instance_id)) == 0


class TestCaptainPellaeonASH93:
    """"While a leader unit has been defeated this phase, this unit gains Raid 3." """

    def test_ASH_93_raid_three_after_a_leader_dies(self, repo):
        from swu.engine.actions import _defeat_unit, compute_power
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        pellaeon = _place(state, "P0", _get_card(repo, "ASH", "93"), "ground")
        assert pellaeon.card_def.keywords == ()      # printed Raid is a mistag
        assert not has_keyword(state, pellaeon, Keyword.RAID)

        # EITHER player's leader counts.
        foe_leader = _place(state, "P1", _get_by_type(repo, "ASH", "10", "Leader"),
                            "ground")
        foe_leader.deployed = True
        _defeat_unit(state, state.player_by_id("P1"), foe_leader)

        pellaeon = _find_instance(state, pellaeon.instance_id)
        assert has_keyword(state, pellaeon, Keyword.RAID)
        assert compute_power(state, pellaeon, is_attacking=True) == (
            pellaeon.card_def.power + 3)


class TestATSTRaiderASH98:
    """"While you control another non-<uq> unit, this unit gains Ambush." """

    def test_ASH_98_needs_another_non_unique_friendly_unit(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        raider = _place(state, "P0", _get_card(repo, "ASH", "98"), "ground")
        # It is itself non-unique — "ANOTHER" is the whole clause.
        assert not raider.card_def.is_unique
        assert not has_keyword(state, raider, Keyword.AMBUSH)

        unique_friend = _place(state, "P0", _get_card(repo, "ASH", "49"), "ground")
        assert unique_friend.card_def.is_unique
        assert not has_keyword(state, raider, Keyword.AMBUSH)

        _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        assert has_keyword(state, raider, Keyword.AMBUSH)


class TestGalliusRaxASH100:
    """"Other friendly units with 2 or more different keywords get +2/+2." """

    def test_ASH_100_buffs_only_units_with_two_keywords(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        rax = _place(state, "P0", _get_card(repo, "ASH", "100"), "ground")
        # Marrok ASH_30 prints exactly one keyword (Sentinel) after the sanitiser.
        one_kw = _place(state, "P0", _get_card(repo, "ASH", "30"), "ground")
        # Home One ASH_65 prints Sentinel; give it a second keyword by hand.
        two_kw = _place(state, "P0", _get_card(repo, "ASH", "65"), "space")
        from swu.abilities.resolver import _make_kw_modifier
        from swu.abilities.registry import Duration
        state.modifiers.append(_make_kw_modifier(
            state, rax.instance_id, two_kw.instance_id, keyword="Grit", value=0,
            duration=Duration.PERMANENT, kind="keyword_grant"))

        assert compute_power(state, one_kw) == one_kw.card_def.power
        assert compute_power(state, two_kw) == two_kw.card_def.power + 2
        assert compute_hp(state, two_kw) == two_kw.card_def.hp + 2
        # "OTHER friendly units" — Rax never buffs himself.
        assert compute_power(state, rax) == rax.card_def.power


# ══ ash-set:17 — combat tricks, buffs & tempo ═══════════════════════════════


class TestBoKatanKryzeASH105:
    """"While you control another Mandalorian unit, this unit gains Raid 2." """

    def test_ASH_105_raid_two_beside_another_mandalorian(self, repo):
        from swu.engine.actions import _create_token_units, compute_power
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        bo = _place(state, "P0", _get_card(repo, "ASH", "105"), "ground")
        assert not has_keyword(state, bo, Keyword.RAID)

        _create_token_units(state, state.player_by_id("P0"), "Mandalorian", 1)
        assert compute_power(state, bo, is_attacking=True) == bo.card_def.power + 2


class TestT6ShuttleASH109:
    """"Sentinel.  Action [Exhaust]: Give another unit +2/+2 for this phase.  You
    may attack with that unit." """

    def test_ASH_109_buffs_and_offers_an_attack_with_that_unit(self, repo):
        from swu.engine.actions import (
            apply, legal_actions, compute_power, UseAbility, AttackWithUnit)
        state = _make_state()
        shuttle = _place(state, "P0", _get_card(repo, "ASH", "109"), "space")
        shuttle.exhausted = False
        friend = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        friend.exhausted = False
        _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")

        act = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == shuttle.instance_id)
        state = _drive_until(apply(state, act), "granted_attack",
                             _accept_and_target(friend))

        buffed = _find_instance(state, friend.instance_id)
        assert compute_power(state, buffed) == buffed.card_def.power + 2
        # "That unit" — the attack is pinned to the buffed one.
        attacks = [a for a in legal_actions(state) if isinstance(a, AttackWithUnit)]
        assert attacks and all(a.attacker_id == friend.instance_id for a in attacks)


class TestMandalorianFlagshipASH113:
    """"While you control a leader unit, this unit gains Ambush.  |  This unit gets
    +1/+0 for each other friendly Mandalorian unit." """

    def test_ASH_113_ambush_needs_a_friendly_leader_unit(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        flagship = _place(state, "P0", _get_card(repo, "ASH", "113"), "space")
        assert not has_keyword(state, flagship, Keyword.AMBUSH)

        boss = _place(state, "P0", _get_by_type(repo, "ASH", "10", "Leader"), "ground")
        boss.deployed = True
        assert has_keyword(state, flagship, Keyword.AMBUSH)

    def test_ASH_113_scales_with_other_mandalorian_units(self, repo):
        from swu.engine.actions import _create_token_units, compute_power
        state = _make_state()
        flagship = _place(state, "P0", _get_card(repo, "ASH", "113"), "space")
        assert compute_power(state, flagship) == flagship.card_def.power

        _create_token_units(state, state.player_by_id("P0"), "Mandalorian", 2)
        flagship = _find_instance(state, flagship.instance_id)
        assert compute_power(state, flagship) == flagship.card_def.power + 2


class TestSabinesLightsaberASH114:
    """"If attached unit is Sabine Wren or a Force unit, it gains Restore 2." """

    def test_ASH_114_grants_restore_to_a_force_host_but_not_a_plain_one(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        saber = _get_card(repo, "ASH", "114")
        force_host = _place(state, "P0", _get_card(repo, "ASH", "49"), "ground")
        plain_host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        assert "Force" in (force_host.card_def.traits or ())

        for host, expected in ((plain_host, 0), (force_host, 2)):
            host.attached_upgrades.append(CardInstance(
                instance_id=f"saber_{host.instance_id}", card_def=saber,
                owner_id="P0", zone=Zone.GROUND_ARENA))
            assert keyword_value(state, host, Keyword.RESTORE) == expected


class TestTheStudentGuidesTheMasterASH115:
    """"Give a friendly unit +1/+0 for this phase for each other friendly unit with
    less power than it." """

    def test_ASH_115_scales_with_weaker_friendly_units(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        big = _place(state, "P0", _get_card(repo, *BIG_SPACE), "space")   # 4 power
        _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")   # 3 power
        _place(state, "P0", _get_card(repo, *VANILLA_WEAK), "ground")     # 2 power
        _place(state, "P1", _get_card(repo, *VANILLA_WEAK), "ground")     # enemy

        state, _ = _play_event_from_hand(state, repo, "ASH", "115")
        state = _drive(state, _accept_and_target(big))

        buffed = _find_instance(state, big.instance_id)
        assert compute_power(state, buffed) == buffed.card_def.power + 2


class TestWarriorOfClanKryzeASH120:
    """"While you control another exhausted unit, this unit gains Sentinel." """

    def test_ASH_120_ignores_its_own_exhaustion(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        warrior = _place(state, "P0", _get_card(repo, "ASH", "120"), "ground")
        warrior.exhausted = True
        assert not has_keyword(state, warrior, Keyword.SENTINEL)

        friend = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        friend.exhausted = True
        assert has_keyword(state, warrior, Keyword.SENTINEL)


class TestStolenEtaShuttleASH125:
    """"Hidden.  While you have the initiative, this unit gets +2/+0." """

    def test_ASH_125_gets_two_power_with_the_initiative(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        shuttle = _place(state, "P0", _get_card(repo, "ASH", "125"), "space")

        state.initiative_holder = state.player_index("P1")
        assert compute_power(state, shuttle) == shuttle.card_def.power

        state.initiative_holder = state.player_index("P0")
        assert compute_power(state, shuttle) == shuttle.card_def.power + 2


# ── ash-set:18 — combat tricks, buffs & tempo ────────────────────────────────


class TestTheTwinsASH127:
    """When Played/On Attack: give another friendly unit Sentinel for this phase.
    When another friendly unit is defeated: heal 1 from your base."""

    def test_ASH_127_when_played_grants_another_friendly_unit_sentinel(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        twins = _place(state, "P0", _get_card(repo, "ASH", "127"), "ground")
        ally = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        assert has_keyword(state, ally, Keyword.SENTINEL) is False
        state = _fire_when_played(state, twins)
        state = _drive(state, _accept_and_target(ally))
        assert has_keyword(state, _find_instance(state, ally.instance_id),
                           Keyword.SENTINEL) is True
        # "another" — the Twins themselves are never offered a Sentinel of their own.
        assert has_keyword(state, _find_instance(state, twins.instance_id),
                           Keyword.SENTINEL) is False

    def test_ASH_127_heals_your_base_when_another_friendly_unit_is_defeated(self, repo):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        twins = _place(state, "P0", _get_card(repo, "ASH", "127"), "ground")
        ally = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        base = state.player_by_id("P0").base_instance
        base.damage = 5
        _defeat_unit(state, state.player_by_id("P0"), ally)
        state = _drive(state)
        assert base.damage == 4
        # An ENEMY unit dying does nothing (the filter is friendly-only).
        foe = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        _defeat_unit(state, state.player_by_id("P1"), foe)
        state = _drive(state)
        assert base.damage == 4
        assert twins is not None


class TestTraskWalkerASH133:
    """When Played/On Attack: choose a unit in your discard pile costing 7 or less.
    Either bottom it and heal 3 from your base, or return it to your hand."""

    def _seed(self, state, repo, key=VANILLA_GROUND):
        from swu.engine.state import CardInstance, Zone
        ci = CardInstance("P0_corpse", _get_card(repo, *key), "P0", Zone.DISCARD)
        state.player_by_id("P0").discard.append(ci)
        return ci

    def _open(self, state, repo, option_idx):
        """Fire the When Played, then take the given modal option."""
        from swu.engine.actions import legal_actions, apply, SelectModalOption
        trask = _place(state, "P0", _get_card(repo, "ASH", "133"), "ground")
        state = _fire_when_played(state, trask)
        opts = [a for a in legal_actions(state) if isinstance(a, SelectModalOption)]
        assert len(opts) == 2, "either/or"
        return apply(state, opts[option_idx])

    def test_ASH_133_bottom_mode_heals_three_from_your_base(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectBottomDiscardCard
        state = _make_state()
        corpse = self._seed(state, repo)
        state.player_by_id("P0").base_instance.damage = 9
        state = self._open(state, repo, 0)          # bottom + heal
        state = _drive_until(state, "bottom_from_discard")
        picks = [a for a in legal_actions(state)
                 if isinstance(a, SelectBottomDiscardCard)]
        assert [a.instance_id for a in picks] == [corpse.instance_id]
        state = _drive(apply(state, picks[0]))
        assert state.player_by_id("P0").base_instance.damage == 6, "healed 3"
        assert corpse.instance_id in [c.instance_id
                                      for c in state.player_by_id("P0").deck]
        assert not state.player_by_id("P0").discard

    def test_ASH_133_return_mode_puts_the_card_in_hand(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectDiscardCard
        state = _make_state()
        corpse = self._seed(state, repo)
        state.player_by_id("P0").base_instance.damage = 9
        state = self._open(state, repo, 1)          # return to hand
        state = _drive_until(state, "return_from_discard")
        picks = [a for a in legal_actions(state) if isinstance(a, SelectDiscardCard)]
        state = _drive(apply(state, picks[0]))
        assert corpse.instance_id in [c.instance_id
                                      for c in state.player_by_id("P0").hand]
        assert state.player_by_id("P0").base_instance.damage == 9, "no heal"

    def test_ASH_133_no_eligible_unit_prompts_nothing(self, repo):
        state = _make_state()
        trask = _place(state, "P0", _get_card(repo, "ASH", "133"), "ground")
        state = _fire_when_played(state, trask)   # empty discard pile
        assert not state.pending_decisions


class TestDisplayOfStrengthASH136:
    """Give a unit +3/+3 for this phase."""

    def test_ASH_136_buffs_the_chosen_unit_for_the_phase(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        target = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        p0, hp0 = compute_power(state, target), compute_hp(state, target)
        state, _ev = _play_event_from_hand(state, repo, "ASH", "136")
        state = _drive(state, _accept_and_target(target))
        live = _find_instance(state, target.instance_id)
        assert compute_power(state, live) == p0 + 3
        assert compute_hp(state, live) == hp0 + 3


class TestVanesSnubFighterASH144:
    """When a friendly unit's attack ends: if it dealt combat damage to a base,
    give an Advantage token to this unit."""

    def test_ASH_144_gains_a_token_when_a_friendly_attack_hits_a_base(self, repo):
        state = _make_state()
        vane = _place(state, "P0", _get_card(repo, "ASH", "144"), "space")
        hitter = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        state = _attack(state, hitter)          # base attack
        state = _drive(state)
        assert _advantage_count(_find_instance(state, vane.instance_id)) == 1

    def test_ASH_144_does_not_fire_on_a_unit_attack_that_spares_the_base(self, repo):
        state = _make_state()
        vane = _place(state, "P0", _get_card(repo, "ASH", "144"), "space")
        hitter = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        blocker = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        state = _attack(state, hitter, blocker)
        state = _drive(state)
        assert _advantage_count(_find_instance(state, vane.instance_id)) == 0


class TestGroguASH155:
    """When you take the initiative: you may attack with a unit."""

    def test_ASH_155_offers_an_attack_when_you_claim_initiative(self, repo):
        from swu.engine.actions import apply, ClaimInitiative
        state = _make_state()
        _place(state, "P0", _get_card(repo, "ASH", "155"), "ground")
        _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        state.active_player_index = state.player_index("P0")
        state = apply(state, ClaimInitiative())
        assert state.pending_decisions
        assert state.pending_decisions[-1].kind == "granted_attack"

    def test_ASH_155_does_not_fire_for_the_opponents_claim(self, repo):
        from swu.engine.actions import apply, ClaimInitiative
        state = _make_state()
        _place(state, "P0", _get_card(repo, "ASH", "155"), "ground")
        _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        state.active_player_index = state.player_index("P1")
        state = apply(state, ClaimInitiative())
        assert not any(d.kind == "granted_attack" for d in state.pending_decisions)


class TestDangerSquadronWingmenASH157:
    """On Attack: you may give an Advantage token to another unit."""

    def test_ASH_157_tokens_another_unit_on_attack(self, repo):
        state = _make_state()
        wing = _place(state, "P0", _get_card(repo, "ASH", "157"), "space")
        ally = _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")
        state = _fire_on_attack(state, wing)
        state = _drive(state, _accept_and_target(ally))
        assert _advantage_count(_find_instance(state, ally.instance_id)) == 1
        assert _advantage_count(_find_instance(state, wing.instance_id)) == 0


class TestAlphabetSquadronUWingASH159:
    """Overwhelm.  When the regroup phase starts: give an Advantage token to a
    unit."""

    def test_ASH_159_tokens_a_unit_at_the_start_of_regroup(self, repo):
        from swu.engine.actions import _enter_regroup
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        uwing = _place(state, "P0", _get_card(repo, "ASH", "159"), "space")
        assert has_keyword(state, uwing, Keyword.OVERWHELM) is True
        ally = _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")
        _enter_regroup(state)
        state = _drive(state, _accept_and_target(ally))
        assert _advantage_count(_find_instance(state, ally.instance_id)) == 1


# ── ash-set:19 — combat tricks, buffs & tempo ────────────────────────────────


class TestKachirhoMilitiaASH160:
    """When an enemy ground unit attacks your base: ready this unit.  Once each
    round."""

    def test_ASH_160_readies_itself_when_an_enemy_ground_unit_hits_your_base(self, repo):
        state = _make_state()
        militia = _place(state, "P0", _get_card(repo, "ASH", "160"), "ground")
        militia.exhausted = True
        raider = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        state.active_player_index = state.player_index("P1")
        state = _attack(state, raider)
        state = _drive(state)
        assert _find_instance(state, militia.instance_id).exhausted is False

    def test_ASH_160_fires_only_once_each_round(self, repo):
        state = _make_state()
        militia = _place(state, "P0", _get_card(repo, "ASH", "160"), "ground")
        militia.exhausted = True
        r1 = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        r2 = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        state.active_player_index = state.player_index("P1")
        state = _attack(state, r1)
        state = _drive(state)
        live = _find_instance(state, militia.instance_id)
        live.exhausted = True
        state.active_player_index = state.player_index("P1")
        state = _attack(state, _find_instance(state, r2.instance_id))
        state = _drive(state)
        assert _find_instance(state, militia.instance_id).exhausted is True

    def test_ASH_160_ignores_a_SPACE_attacker(self, repo):
        state = _make_state()
        militia = _place(state, "P0", _get_card(repo, "ASH", "160"), "ground")
        militia.exhausted = True
        flyer = _place(state, "P1", _get_card(repo, *VANILLA_SPACE), "space")
        state.active_player_index = state.player_index("P1")
        state = _attack(state, flyer)
        state = _drive(state)
        assert _find_instance(state, militia.instance_id).exhausted is True


class TestRashActionASH162:
    """Attack with a unit at +1/+0; it gains "When Attack Ends: if it dealt combat
    damage to an opponent's base, that opponent discards a card"."""

    def test_ASH_162_opponent_discards_when_the_attack_damages_their_base(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        hitter = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        opp = state.player_by_id("P1")
        opp.hand.append(CardInstance("P1_h1", _get_card(repo, *VANILLA_GROUND),
                                     "P1", Zone.HAND))
        state, _ev = _play_event_from_hand(state, repo, "ASH", "162")
        state.active_player_index = state.player_index("P0")
        atk = [a for a in legal_actions(state)
               if isinstance(a, AttackWithUnit)
               and a.attacker_id == hitter.instance_id and not a.defender_id]
        assert atk, "the granted attack offers a base attack"
        state = apply(state, atk[0])
        state = _drive(state)
        # 3 power +1 from the event.
        assert state.player_by_id("P1").base_instance.damage == 4
        assert not state.player_by_id("P1").hand, "the opponent discarded"

    def test_ASH_162_no_discard_when_the_attack_hits_a_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        hitter = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        blocker = _place(state, "P1", _get_card(repo, *BIG_SPACE), "ground")
        opp = state.player_by_id("P1")
        opp.hand.append(CardInstance("P1_h1", _get_card(repo, *VANILLA_GROUND),
                                     "P1", Zone.HAND))
        state, _ev = _play_event_from_hand(state, repo, "ASH", "162")
        state.active_player_index = state.player_index("P0")
        atk = [a for a in legal_actions(state)
               if isinstance(a, AttackWithUnit)
               and a.attacker_id == hitter.instance_id
               and a.defender_id == blocker.instance_id]
        state = apply(state, atk[0])
        state = _drive(state)
        assert len(state.player_by_id("P1").hand) == 1, "no base damage, no discard"


class TestFlarestarAttackShuttleASH167:
    """When Played/When Defeated: you may give an Advantage token to a unit."""

    def test_ASH_167_tokens_a_unit_when_played(self, repo):
        state = _make_state()
        shuttle = _place(state, "P0", _get_card(repo, "ASH", "167"), "space")
        state = _fire_when_played(state, shuttle)
        state = _drive(state, _accept_and_target(shuttle))
        assert _advantage_count(_find_instance(state, shuttle.instance_id)) == 1

    def test_ASH_167_tokens_a_unit_when_defeated(self, repo):
        state = _make_state()
        shuttle = _place(state, "P0", _get_card(repo, "ASH", "167"), "space")
        ally = _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")
        state = _fire_when_defeated(state, shuttle)
        state = _drive(state, _accept_and_target(ally))
        assert _advantage_count(_find_instance(state, ally.instance_id)) == 1


class TestKnobbyWhiteIceSpiderASH178:
    """Hidden.  When Played: for each enemy unit, give an Advantage token to this
    unit."""

    def test_ASH_178_gains_one_token_per_enemy_unit(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        spider = _place(state, "P0", _get_card(repo, "ASH", "178"), "ground")
        assert has_keyword(state, spider, Keyword.HIDDEN) is True
        _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        _place(state, "P1", _get_card(repo, *VANILLA_SPACE), "space")
        _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")   # friendly
        state = _fire_when_played(state, spider)
        state = _drive(state)
        assert _advantage_count(_find_instance(state, spider.instance_id)) == 2


class TestBokkenSaberASH180:
    """Attach to a non-Vehicle unit.  Attached unit gains: "When Attack Ends: give
    an Advantage token to this unit"."""

    def test_ASH_180_host_keeps_the_token_it_earns_at_the_end_of_its_attack(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        saber = _attach_upgrade_card(state, host, _get_card(repo, "ASH", "180"))
        state = _attack(state, host)            # base attack
        state = _drive(state)
        live = _find_instance(state, host.instance_id)
        assert _advantage_count(live) == 1, "the attack's own sweep must not take it"
        assert saber is not None

    def test_ASH_180_the_attacks_own_advantage_token_still_expires(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        _attach_upgrade_card(state, host, _get_card(repo, "ASH", "180"))
        _attach(state, host, "Advantage")       # rode into this attack
        assert _advantage_count(host) == 1
        state = _attack(state, host)
        state = _drive(state)
        # The pre-existing token expired; the granted one replaced it.
        assert _advantage_count(_find_instance(state, host.instance_id)) == 1


class TestMarkMyWordsASH181:
    """Attach to a damaged unit.  Attached unit gains Overwhelm."""

    def test_ASH_181_grants_its_host_overwhelm(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        host.damage = 1
        assert has_keyword(state, host, Keyword.OVERWHELM) is False
        _attach_upgrade_card(state, host, _get_card(repo, "ASH", "181"))
        assert has_keyword(state, host, Keyword.OVERWHELM) is True

    def test_ASH_181_only_attaches_to_a_damaged_unit(self, repo):
        from swu.engine.actions import _upgrade_target_spec
        spec = _upgrade_target_spec(_get_card(repo, "ASH", "181"))
        assert spec is not None and "damaged" in (spec.predicates or ())


class TestUnfetteredAmbitionASH182:
    """When Played: for each upgrade on attached unit not named Advantage (including
    this one), give an Advantage token to attached unit."""

    def test_ASH_182_tokens_the_host_once_per_non_advantage_upgrade(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        _attach(state, host, "Experience")               # counts
        _attach(state, host, "Advantage")                # does NOT count
        upg = _attach_upgrade_card(state, host, _get_card(repo, "ASH", "182"))
        from tests.test_sor_cards import _fire_upgrade_played
        state = _fire_upgrade_played(state, upg, host)
        state = _drive(state)
        live = _find_instance(state, host.instance_id)
        # Experience + Unfettered Ambition itself = 2 new tokens, plus the one
        # already there.
        assert _advantage_count(live) == 3


# ── ash-set:20 — combat tricks, buffs & tempo ────────────────────────────────


class TestFollowMeASH184:
    """Attack with a unit.  After completing the attack, give 3 Advantage tokens to
    a unit."""

    def test_ASH_184_attacks_first_then_hands_out_three_tokens(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        hitter = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        state, _ev = _play_event_from_hand(state, repo, "ASH", "184")
        state.active_player_index = state.player_index("P0")
        atk = [a for a in legal_actions(state)
               if isinstance(a, AttackWithUnit)
               and a.attacker_id == hitter.instance_id and not a.defender_id]
        assert atk, "the attack resolves BEFORE the token choice"
        state = apply(state, atk[0])
        state = _drive(state, _accept_and_target(hitter))
        assert state.player_by_id("P1").base_instance.damage == 3
        assert _advantage_count(_find_instance(state, hitter.instance_id)) == 3


class TestGalvanizedLeapASH188:
    """Ready a unit that was damaged this phase."""

    def test_ASH_188_only_offers_a_unit_damaged_this_phase(self, repo):
        from swu.abilities.resolver import _apply_deal_damage
        state = _make_state()
        hurt = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        clean = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        hurt.exhausted = clean.exhausted = True
        _apply_deal_damage(state, hurt.instance_id, 2, "test")
        state, _ev = _play_event_from_hand(state, repo, "ASH", "188")
        assert _target_ids(state) == {hurt.instance_id}
        state = _drive(state, _accept_and_target(hurt))
        assert _find_instance(state, hurt.instance_id).exhausted is False
        assert _find_instance(state, clean.instance_id).exhausted is True

    def test_ASH_188_a_unit_healed_since_still_counts(self, repo):
        from swu.abilities.resolver import _apply_deal_damage, _apply_heal
        state = _make_state()
        hurt = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        hurt.exhausted = True
        _apply_deal_damage(state, hurt.instance_id, 2, "test")
        _apply_heal(state, hurt, hurt.instance_id, 2)
        assert _find_instance(state, hurt.instance_id).damage == 0
        state, _ev = _play_event_from_hand(state, repo, "ASH", "188")
        assert _target_ids(state) == {hurt.instance_id}, "the ledger, not the damage"


class TestExecutorASH197:
    """+1/+0 for each upgrade on other friendly units.  When Played: give an
    Advantage token to each other friendly unit."""

    def test_ASH_197_scales_with_upgrades_on_OTHER_friendly_units(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        exe = _place(state, "P0", _get_card(repo, "ASH", "197"), "space")
        assert compute_power(state, exe) == 5
        _attach(state, exe, "Experience")            # on itself — does not count
        ally = _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")
        _attach(state, ally, "Experience")
        _attach(state, ally, "Shield")
        foe = _place(state, "P1", _get_card(repo, *VANILLA_SPACE), "space")
        _attach(state, foe, "Experience")            # enemy — does not count
        assert compute_power(state, exe) == 5 + 1 + 2, "own +1/+1 plus two upgrades"

    def test_ASH_197_tokens_each_other_friendly_unit_when_played(self, repo):
        state = _make_state()
        exe = _place(state, "P0", _get_card(repo, "ASH", "197"), "space")
        a1 = _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")
        a2 = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        foe = _place(state, "P1", _get_card(repo, *VANILLA_SPACE), "space")
        state = _drive(_fire_when_played(state, exe))
        assert _advantage_count(_find_instance(state, a1.instance_id)) == 1
        assert _advantage_count(_find_instance(state, a2.instance_id)) == 1
        assert _advantage_count(_find_instance(state, exe.instance_id)) == 0
        assert _advantage_count(_find_instance(state, foe.instance_id)) == 0


class TestNowhereToHideASH198:
    """Attached unit gains Sentinel."""

    def test_ASH_198_grants_its_host_sentinel(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        assert has_keyword(state, host, Keyword.SENTINEL) is False
        _attach_upgrade_card(state, host, _get_card(repo, "ASH", "198"))
        assert has_keyword(state, host, Keyword.SENTINEL) is True


class TestBladeThreeASH204:
    """When your base is dealt damage: give an Advantage token to this unit."""

    def test_ASH_204_gains_a_token_when_your_base_takes_damage(self, repo):
        state = _make_state()
        blade = _place(state, "P0", _get_card(repo, "ASH", "204"), "space")
        raider = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        state.active_player_index = state.player_index("P1")
        state = _drive(_attack(state, raider))       # hits P0's base
        assert _advantage_count(_find_instance(state, blade.instance_id)) == 1

    def test_ASH_204_ignores_damage_to_the_ENEMY_base(self, repo):
        state = _make_state()
        blade = _place(state, "P0", _get_card(repo, "ASH", "204"), "space")
        mine = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        state = _drive(_attack(state, mine))         # hits P1's base
        assert _advantage_count(_find_instance(state, blade.instance_id)) == 0


class TestInspiringVeteranASH205:
    """When Played: give an Advantage token to each of up to 3 exhausted units."""

    def test_ASH_205_tokens_only_exhausted_units(self, repo):
        from swu.engine.actions import legal_actions, SelectTokenTarget
        state = _make_state()
        vet = _place(state, "P0", _get_card(repo, "ASH", "205"), "ground")
        tired = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        tired.exhausted = True
        fresh = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        state = _fire_when_played(state, vet)
        state = _drive_until(state, "select_token")
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, SelectTokenTarget)}
        assert offered == {tired.instance_id}
        state = _drive(state)
        assert _advantage_count(_find_instance(state, tired.instance_id)) == 1
        assert _advantage_count(_find_instance(state, fresh.instance_id)) == 0


class TestKelleranBeqASH206:
    """Ambush.  +1/+0 for each other unit (friendly and enemy) with 0 power."""

    def test_ASH_206_scales_with_every_other_zero_power_unit(self, repo):
        from swu.engine.actions import compute_power
        from swu.engine.keywords import has_keyword, Keyword
        from swu.engine.state import Modifier
        state = _make_state()
        beq = _place(state, "P0", _get_card(repo, "ASH", "206"), "ground")
        assert has_keyword(state, beq, Keyword.AMBUSH) is True
        assert compute_power(state, beq) == 3
        mine = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")   # 3
        foe = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")    # 3
        assert compute_power(state, beq) == 3, "nobody is at 0 power yet"
        for ci in (mine, foe):
            state.modifiers.append(Modifier(
                modifier_id=state.alloc_modifier_id(),
                source_instance_id=beq.instance_id,
                target_instance_id=ci.instance_id,
                kind="stats", value={"power": -3, "hp": 0},
                duration="this_phase"))
        assert compute_power(state, mine) == 0 and compute_power(state, foe) == 0
        assert compute_power(state, beq) == 5, "both sides count, no recursion"


# ── ash-set:21 — combat tricks, buffs & tempo ────────────────────────────────


class TestHeroicPurrgilASH207:
    """Ambush.  While attacking using Ambush, this unit gets +2/+0."""

    def test_ASH_207_hits_for_two_more_on_its_ambush_attack(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAmbush
        from swu.engine.decisions import PendingDecision
        state = _make_state()
        prey = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        purrgil = _place(state, "P0", _get_card(repo, "ASH", "207"), "ground")
        # The Ambush decision as the enter-play bus pushes it (test_keywords shape).
        state.pending_decisions.append(PendingDecision(
            deciding_player_id="P0", kind="ambush",
            context={"unit_id": purrgil.instance_id},
            after_resolve_player_index=1))
        state.active_player_index = 0
        amb = [a for a in legal_actions(state)
               if isinstance(a, UseAmbush) and a.target_id == prey.instance_id]
        assert amb, "Ambush offers the attack"
        state = _drive(apply(state, amb[0]))
        # 3 printed +2 while attacking using Ambush = 5 on a 7-HP defender.
        assert _find_instance(state, prey.instance_id).damage == 5

    def test_ASH_207_an_ordinary_attack_gets_no_bonus(self, repo):
        state = _make_state()
        purrgil = _place(state, "P0", _get_card(repo, "ASH", "207"), "ground")
        prey = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _drive(_attack(state, purrgil, prey))
        assert _find_instance(state, prey.instance_id).damage == 3, "printed power"


class TestSabineWrenASH208:
    """Shielded.  When 1 or more upgrades attach to this unit (including from
    Shielded): You may exhaust a ground unit."""

    def test_ASH_208_fires_when_a_shield_token_attaches(self, repo):
        from swu.engine.actions import apply, Pass
        state = _make_state()
        sabine = _place(state, "P0", _get_card(repo, "ASH", "208"), "ground")
        foe = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        _attach(state, sabine, "Shield")
        assert state.game_memory.upgrade_attachments == [sabine.instance_id]
        state = apply(state, Pass())          # settle point drains the ledger
        state = _drive(state, _accept_and_target(foe))
        assert _find_instance(state, foe.instance_id).exhausted is True

    def test_ASH_208_coalesces_several_attachments_into_one_firing(self, repo):
        from swu.engine.actions import apply, Pass
        state = _make_state()
        sabine = _place(state, "P0", _get_card(repo, "ASH", "208"), "ground")
        f1 = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        f2 = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        for _ in range(3):
            _attach(state, sabine, "Experience")
        state = apply(state, Pass())
        state = _drive(state, _accept_and_target(f1))
        assert _find_instance(state, f1.instance_id).exhausted is True
        assert _find_instance(state, f2.instance_id).exhausted is False, "one firing"

    def test_ASH_208_ignores_an_upgrade_on_another_unit(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "ASH", "208"), "ground")
        other = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        _attach(state, other, "Shield")
        assert state.game_memory.upgrade_attachments == []


class TestAmnestyOfficerASH214:
    """When Played: you may exhaust a unit with one or more keywords."""

    def test_ASH_214_only_offers_a_unit_with_a_keyword(self, repo):
        state = _make_state()
        officer = _place(state, "P0", _get_card(repo, "ASH", "214"), "ground")
        keyworded = _place(state, "P1", _get_card(repo, "ASH", "206"), "ground")  # Ambush
        plain = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        state = _fire_when_played(state, officer)
        state = _drive_until(state, "resolve_effects")
        state = _drive(state, _accept_and_target(keyworded))
        assert _find_instance(state, keyworded.instance_id).exhausted is True
        assert _find_instance(state, plain.instance_id).exhausted is False


class TestMandalorianScoutASH216:
    """When Defeated: exhaust a ready friendly resource."""

    def test_ASH_216_exhausts_one_ready_friendly_resource(self, repo):
        state = _make_state()
        scout = _place(state, "P0", _get_card(repo, "ASH", "216"), "ground")
        for _ in range(3):
            _add_resource(state, repo, "P0", exhausted=False)
        ps = state.player_by_id("P0")
        assert all(not r.exhausted for r in ps.resources)
        state = _drive(_fire_when_defeated(state, scout))
        ps = state.player_by_id("P0")
        assert sum(1 for r in ps.resources if r.exhausted) == 1


class TestMayorsMajordomoASH217:
    """Action [Exhaust, discard a card from your hand]: exhaust a unit."""

    def test_ASH_217_costs_a_hand_card_and_exhausts_a_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        mayor = _place(state, "P0", _get_card(repo, "ASH", "217"), "ground")
        foe = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        ps = state.player_by_id("P0")
        # With an empty hand the cost cannot be paid, so the Action is not offered.
        assert not [a for a in legal_actions(state)
                    if isinstance(a, UseAbility)
                    and a.source_id == mayor.instance_id]
        ps.hand.append(CardInstance("P0_h1", _get_card(repo, *VANILLA_GROUND),
                                    "P0", Zone.HAND))
        act = [a for a in legal_actions(state)
               if isinstance(a, UseAbility) and a.source_id == mayor.instance_id]
        assert act
        state = _drive(apply(state, act[0]), _accept_and_target(foe))
        assert _find_instance(state, foe.instance_id).exhausted is True
        assert _find_instance(state, mayor.instance_id).exhausted is True
        assert not state.player_by_id("P0").hand


class TestJodNaNawoodASH219:
    """Sentinel.  When Played: you may pay 4 resources.  If you do, choose an arena.
    Exhaust each unit in that arena."""

    def test_ASH_219_pays_four_then_exhausts_one_whole_arena(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectModalOption
        state = _make_state()
        jod = _place(state, "P0", _get_card(repo, "ASH", "219"), "ground")
        for _ in range(5):
            _add_resource(state, repo, "P0", exhausted=False)
        ground_foe = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        space_foe = _place(state, "P1", _get_card(repo, *VANILLA_SPACE), "space")
        state = _fire_when_played(state, jod)
        state = _drive_until(state, "choose_two_modal", _accept_and_target())
        opts = [a for a in legal_actions(state) if isinstance(a, SelectModalOption)]
        assert len(opts) == 2, "ground or space"
        state = _drive(apply(state, opts[0]))            # ground
        assert _find_instance(state, ground_foe.instance_id).exhausted is True
        assert _find_instance(state, space_foe.instance_id).exhausted is False
        ps = state.player_by_id("P0")
        assert sum(1 for r in ps.resources if r.exhausted) == 4

    def test_ASH_219_is_not_offered_without_four_ready_resources(self, repo):
        state = _make_state()
        jod = _place(state, "P0", _get_card(repo, "ASH", "219"), "ground")
        for _ in range(3):
            _add_resource(state, repo, "P0", exhausted=False)
        _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        state = _fire_when_played(state, jod)
        assert not state.pending_decisions, "the trigger is never collected"


class TestHelixStarfighterASH221:
    """When Played: if an opponent controls a space unit, give a Shield token to
    this unit.  Otherwise, give 2 Advantage tokens to this unit."""

    def test_ASH_221_shields_itself_against_an_enemy_space_unit(self, repo):
        state = _make_state()
        helix = _place(state, "P0", _get_card(repo, "ASH", "221"), "space")
        _place(state, "P1", _get_card(repo, *VANILLA_SPACE), "space")
        state = _drive(_fire_when_played(state, helix))
        live = _find_instance(state, helix.instance_id)
        assert _shield_count(live) == 1
        assert _advantage_count(live) == 0

    def test_ASH_221_takes_two_advantage_tokens_otherwise(self, repo):
        state = _make_state()
        helix = _place(state, "P0", _get_card(repo, "ASH", "221"), "space")
        _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        state = _drive(_fire_when_played(state, helix))
        live = _find_instance(state, helix.instance_id)
        assert _shield_count(live) == 0
        assert _advantage_count(live) == 2


# ── ash-set:22 — combat tricks, buffs & tempo ────────────────────────────────


class TestElzarMannASH224:
    """Enters ready while you control a Force leader.  When Played: distribute up to
    5 Advantage tokens among other friendly units; then an opponent searches twice
    that many cards for an event and draws it."""

    def test_ASH_224_enters_ready_only_with_a_force_leader(self, repo):
        from swu.engine.actions import _put_unit_in_play
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        ci = CardInstance("P0_elzar1", _get_card(repo, "ASH", "224"), "P0", Zone.HAND)
        _put_unit_in_play(state, state.player_by_id("P0"), ci)
        assert ci.exhausted is True, "no Force leader yet"

        state2 = _make_state()
        _place_leader(state2, "P0", _get_by_type(repo, "ASH", "16", "Leader"))
        ci2 = CardInstance("P0_elzar2", _get_card(repo, "ASH", "224"), "P0", Zone.HAND)
        _put_unit_in_play(state2, state2.player_by_id("P0"), ci2)
        assert ci2.exhausted is False, "an undeployed Force leader still counts"

    def test_ASH_224_stacks_several_tokens_on_one_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectTokenTarget
        state = _make_state()
        elzar = _place(state, "P0", _get_card(repo, "ASH", "224"), "ground")
        ally = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        state = _fire_when_played(state, elzar)
        state = _drive_until(state, "select_token")
        for _ in range(3):
            pick = [a for a in legal_actions(state)
                    if isinstance(a, SelectTokenTarget)
                    and a.target_id == ally.instance_id]
            assert pick, "a chosen unit stays pickable (distribution mode)"
            state = apply(state, pick[0])
        assert _advantage_count(_find_instance(state, ally.instance_id)) == 3
        # Elzar himself is never a target ("other friendly units").
        assert not [a for a in legal_actions(state)
                    if isinstance(a, SelectTokenTarget)
                    and a.target_id == elzar.instance_id]

    def test_ASH_224_opponent_searches_twice_that_many(self, repo):
        from swu.engine.actions import (legal_actions, apply, SelectTokenTarget,
                                        FinishSelectToken)
        state = _make_state()
        elzar = _place(state, "P0", _get_card(repo, "ASH", "224"), "ground")
        ally = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        for _ in range(8):
            _push_deck_top(state, "P1", _get_card(repo, *VANILLA_GROUND))
        state = _fire_when_played(state, elzar)
        state = _drive_until(state, "select_token")
        pick = [a for a in legal_actions(state) if isinstance(a, SelectTokenTarget)
                and a.target_id == ally.instance_id]
        state = apply(state, pick[0])
        state = apply(state, FinishSelectToken())
        top = state.pending_decisions[-1]
        assert top.kind == "deck_search"
        assert top.deciding_player_id == "P1", "the OPPONENT searches their own deck"
        assert top.context["window"] == 2, "twice the one token given"


class TestHeightenedAwarenessASH227:
    """Attached unit gains: "When the regroup phase starts: give an Advantage token
    to this unit"."""

    def test_ASH_227_tokens_its_host_at_the_start_of_regroup(self, repo):
        from swu.engine.actions import _enter_regroup
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        other = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        _attach_upgrade_card(state, host, _get_card(repo, "ASH", "227"))
        _enter_regroup(state)
        state = _drive(state)
        assert _advantage_count(_find_instance(state, host.instance_id)) == 1
        assert _advantage_count(_find_instance(state, other.instance_id)) == 0


class TestPreparationASH228:
    """When Played: exhaust attached unit."""

    def test_ASH_228_exhausts_the_unit_it_attaches_to(self, repo):
        from tests.test_sor_cards import _fire_upgrade_played
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        assert host.exhausted is False
        upg = _attach_upgrade_card(state, host, _get_card(repo, "ASH", "228"))
        state = _drive(_fire_upgrade_played(state, upg, host))
        assert _find_instance(state, host.instance_id).exhausted is True


class TestDiplomaticPageantryASH231:
    """Exhaust a friendly unit and an enemy unit.  If you do, give 2 Advantage
    tokens to that friendly unit."""

    def test_ASH_231_exhausts_both_and_pays_the_friendly_unit(self, repo):
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        theirs = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        state, _ev = _play_event_from_hand(state, repo, "ASH", "231")
        state = _drive(state)
        assert _find_instance(state, mine.instance_id).exhausted is True
        assert _find_instance(state, theirs.instance_id).exhausted is True
        assert _advantage_count(_find_instance(state, mine.instance_id)) == 2

    def test_ASH_231_no_enemy_unit_means_no_tokens(self, repo):
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        state, _ev = _play_event_from_hand(state, repo, "ASH", "231")
        state = _drive(state)
        assert _advantage_count(_find_instance(state, mine.instance_id)) == 0


class TestKeepThemTalkingASH233:
    """Exhaust up to 2 units that each cost 3 or less."""

    def test_ASH_233_exhausts_two_cheap_units_and_spares_the_rest(self, repo):
        state = _make_state()
        cheap1 = _place(state, "P1", _get_card(repo, *VANILLA_WEAK), "ground")   # 2
        cheap2 = _place(state, "P1", _get_card(repo, *VANILLA_WEAK), "ground")
        pricey = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")  # 4
        state, _ev = _play_event_from_hand(state, repo, "ASH", "233")
        assert pricey.instance_id not in _target_ids(state), "cost 4 is out of reach"
        state = _drive(state, _accept_and_target())
        assert _find_instance(state, cheap1.instance_id).exhausted is True
        assert _find_instance(state, cheap2.instance_id).exhausted is True
        assert _find_instance(state, pricey.instance_id).exhausted is False


class TestMasterstrokeASH234:
    """Attack with a unit.  It gets +1/+0 for each unit the defending player
    controls in its arena."""

    def test_ASH_234_scales_with_the_defending_players_arena(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        hitter = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")  # 3
        d1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, *VANILLA_SPACE), "space")   # other arena
        state, _ev = _play_event_from_hand(state, repo, "ASH", "234")
        state.active_player_index = state.player_index("P0")
        atk = [a for a in legal_actions(state)
               if isinstance(a, AttackWithUnit)
               and a.attacker_id == hitter.instance_id
               and a.defender_id == d1.instance_id]
        state = _drive(apply(state, atk[0]))
        # 3 printed + 2 ground units the defender controls; the space one is out.
        assert _find_instance(state, d1.instance_id).damage == 5


class TestMouseDroidASH237:
    """Raid 1.  When Played: the next Imperial unit you play this phase costs 1
    resource less."""

    def test_ASH_237_discounts_the_next_imperial_unit(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        mouse = _place(state, "P0", _get_card(repo, "ASH", "237"), "ground")
        assert keyword_value(state, mouse, Keyword.RAID) == 1
        state = _drive(_fire_when_played(state, mouse))
        entries = state.game_memory.pending_play_discounts
        assert len(entries) == 1
        assert entries[0]["trait"] == "Imperial"
        assert entries[0]["amount"] == 1


# ── ash-set:23 / :24 — combat tricks, buffs & tempo ──────────────────────────


class TestMandalorianSuperCommandosASH240:
    """While you control a leader unit, this unit gets +2/+0."""

    def test_ASH_240_grows_while_you_control_a_leader_unit(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        cmd = _place(state, "P0", _get_card(repo, "ASH", "240"), "ground")
        assert compute_power(state, cmd) == 2
        leader = _place(state, "P0", _get_by_type(repo, "ASH", "16", "Leader"),
                        "ground")
        leader.deployed = True
        assert compute_power(state, cmd) == 4
        # An ENEMY leader unit is not "you control".
        state.player_by_id("P0").ground_arena.remove(leader)
        state.player_by_id("P1").ground_arena.append(leader)
        assert compute_power(state, cmd) == 2


class TestEyeOfSionASH245:
    """Action [Exhaust]: search the top 8 for a unit costing at most this unit's
    power; play it for free, ready."""

    def test_ASH_245_plays_a_cheap_unit_from_the_top_eight_ready(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility
        state = _make_state()
        eye = _place(state, "P0", _get_card(repo, "ASH", "245"), "space")  # 5 power
        _push_deck_top(state, "P0", _get_card(repo, *VANILLA_GROUND))     # cost 4
        act = [a for a in legal_actions(state)
               if isinstance(a, UseAbility) and a.source_id == eye.instance_id]
        assert act
        state = _drive(apply(state, act[0]))
        played = [u for u in state.player_by_id("P0").ground_arena]
        assert len(played) == 1
        assert played[0].exhausted is False, "it enters play ready"
        assert _find_instance(state, eye.instance_id).exhausted is True


class TestNeelASH248:
    """When Played/On Attack: the next unit you play this phase with 1 or less power
    enters play ready."""

    def test_ASH_248_readies_the_next_low_power_unit_you_play(self, repo):
        from swu.engine.actions import _put_unit_in_play
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        neel = _place(state, "P0", _get_card(repo, "ASH", "248"), "ground")
        state = _drive(_fire_when_played(state, neel))
        assert len(state.game_memory.pending_enters_ready) == 1
        weak = CardInstance("P0_weak", _get_card(repo, "ASH", "237"),  # 1 power
                            "P0", Zone.HAND)
        _put_unit_in_play(state, state.player_by_id("P0"), weak)
        assert weak.exhausted is False
        assert not state.game_memory.pending_enters_ready, "one charge, one unit"

    def test_ASH_248_does_not_ready_a_bigger_unit(self, repo):
        from swu.engine.actions import _put_unit_in_play
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        neel = _place(state, "P0", _get_card(repo, "ASH", "248"), "ground")
        state = _drive(_fire_when_played(state, neel))
        big = CardInstance("P0_big", _get_card(repo, *VANILLA_GROUND),  # 3 power
                           "P0", Zone.HAND)
        _put_unit_in_play(state, state.player_by_id("P0"), big)
        assert big.exhausted is True
        assert len(state.game_memory.pending_enters_ready) == 1, "still armed"


class TestZealousSoldierASH251:
    """When Played: give an Advantage token to this unit."""

    def test_ASH_251_tokens_itself_when_played(self, repo):
        state = _make_state()
        soldier = _place(state, "P0", _get_card(repo, "ASH", "251"), "ground")
        state = _drive(_fire_when_played(state, soldier))
        assert _advantage_count(_find_instance(state, soldier.instance_id)) == 1


class TestAnakinSkywalkerASH255:
    """Hidden.  Saboteur.  When Played: give a Shield token to another friendly
    unit."""

    def test_ASH_255_shields_another_friendly_unit(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        anakin = _place(state, "P0", _get_card(repo, "ASH", "255"), "ground")
        assert has_keyword(state, anakin, Keyword.HIDDEN) is True
        assert has_keyword(state, anakin, Keyword.SABOTEUR) is True
        ally = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        state = _fire_when_played(state, anakin)
        state = _drive(state, _accept_and_target(ally))
        assert _shield_count(_find_instance(state, ally.instance_id)) == 1
        assert _shield_count(_find_instance(state, anakin.instance_id)) == 0


class TestChooseYourPathASH257:
    """Choose one: heal 5 from your base (Force unit) / create a Mandalorian token
    and give it an Advantage token (Mandalorian unit)."""

    def test_ASH_257_offers_only_the_modes_you_qualify_for(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectModalOption
        state = _make_state()
        _place(state, "P0", _get_card(repo, "ASH", "255"), "ground")   # Force
        state.player_by_id("P0").base_instance.damage = 9
        state, _ev = _play_event_from_hand(state, repo, "ASH", "257")
        opts = [a for a in legal_actions(state) if isinstance(a, SelectModalOption)]
        assert len(opts) == 1, "only the Force clause holds"
        state = _drive(apply(state, opts[0]))
        assert state.player_by_id("P0").base_instance.damage == 4

    def test_ASH_257_mandalorian_mode_creates_a_token_with_an_advantage(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectModalOption
        state = _make_state()
        _place(state, "P0", _get_card(repo, "ASH", "240"), "ground")   # Mandalorian
        state, _ev = _play_event_from_hand(state, repo, "ASH", "257")
        opts = [a for a in legal_actions(state) if isinstance(a, SelectModalOption)]
        assert len(opts) == 1
        state = _drive(apply(state, opts[0]))
        ps = state.player_by_id("P0")
        token = [u for u in ps.ground_arena
                 if u.card_def.name == "Mandalorian"]
        assert len(token) == 1
        assert _advantage_count(token[0]) == 1

    def test_ASH_257_fizzles_with_neither_trait(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        state, _ev = _play_event_from_hand(state, repo, "ASH", "257")
        assert not state.pending_decisions


class TestFaithInTheEmpireASH262:
    """This upgrade costs 1 resource less to play on an Imperial unit."""

    def test_ASH_262_is_cheaper_on_an_imperial_host(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        imperial = _place(state, "P0", _get_card(repo, "ASH", "237"), "ground")
        plain = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        from swu.engine.state import CardInstance, Zone
        upg = CardInstance("P0_faith", _get_card(repo, "ASH", "262"), "P0", Zone.HAND)
        ps = state.player_by_id("P0")
        full = _play_cost(state, upg, ps, target_host_id=plain.instance_id)
        cut = _play_cost(state, upg, ps, target_host_id=imperial.instance_id)
        assert cut == full - 1


class TestTheWayOfTheMandalorASH263:
    """This upgrade costs 1 resource less to play on a Mandalorian unit."""

    def test_ASH_263_is_cheaper_on_a_mandalorian_host(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        mando = _place(state, "P0", _get_card(repo, "ASH", "240"), "ground")
        plain = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        from swu.engine.state import CardInstance, Zone
        upg = CardInstance("P0_way", _get_card(repo, "ASH", "263"), "P0", Zone.HAND)
        ps = state.player_by_id("P0")
        full = _play_cost(state, upg, ps, target_host_id=plain.instance_id)
        cut = _play_cost(state, upg, ps, target_host_id=mando.instance_id)
        assert cut == full - 1


class TestANewOrderASH264:
    """Give an Advantage token to each of up to 2 units."""

    def test_ASH_264_tokens_two_different_units(self, repo):
        state = _make_state()
        a = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        b = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        state, _ev = _play_event_from_hand(state, repo, "ASH", "264")
        state = _drive(state)
        assert _advantage_count(_find_instance(state, a.instance_id)) == 1
        assert _advantage_count(_find_instance(state, b.instance_id)) == 1


# ══════════════════════════════════════════════════════════════════════════════
# ash-set:25 — miscellaneous abilities
# ══════════════════════════════════════════════════════════════════════════════

def _token_units(state, player_id, name="Mandalorian"):
    ps = state.player_by_id(player_id)
    return [u for u in ps.ground_arena + ps.space_arena
            if u.card_def.name == name]


class TestPazVizslaASH28:
    """When Defeated: If this unit wasn't defeated by combat damage, create 2
    Mandalorian tokens."""

    def test_ASH_28_non_combat_defeat_creates_two_tokens(self, repo):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        paz = _place(state, "P0", _get_card(repo, "ASH", "28"), "ground")
        _defeat_unit(state, state.player_by_id("P0"), paz)
        state = _drive(state)
        assert len(_token_units(state, "P0")) == 2

    def test_ASH_28_combat_defeat_creates_nothing(self, repo):
        from swu.engine.actions import apply, AttackWithUnit
        state = _make_state()
        paz = _place(state, "P1", _get_card(repo, "ASH", "28"), "ground")
        paz.damage = 6                     # one more point of combat damage kills him
        atk = _place(state, "P0", _get_card(repo, *VANILLA_WEAK), "ground")
        atk.exhausted = False
        state = apply(state, AttackWithUnit(attacker_id=atk.instance_id,
                                            defender_id=paz.instance_id))
        state = _drive(state)
        assert _find_instance(state, paz.instance_id) is None   # he really died
        assert _token_units(state, "P1") == []


class TestWicketASH34:
    """Saboteur | This unit can't attack bases."""

    def test_ASH_34_cannot_attack_a_base(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        wicket = _place(state, "P0", _get_card(repo, "ASH", "34"), "ground")
        wicket.exhausted = False
        enemy = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        attacks = [a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == wicket.instance_id]
        assert attacks, "Wicket should still be able to attack a unit"
        assert all(a.defender_id is not None for a in attacks)
        assert enemy.instance_id in {a.defender_id for a in attacks}


class TestPoeDameronASH40:
    """All units lose Sentinel."""

    def test_ASH_40_strips_sentinel_from_every_unit(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        paz = _place(state, "P1", _get_card(repo, "ASH", "28"), "ground")  # Sentinel
        assert has_keyword(state, paz, Keyword.SENTINEL)
        poe = _place(state, "P0", _get_card(repo, "ASH", "40"), "ground")
        assert not has_keyword(state, paz, Keyword.SENTINEL)
        # Poe's own mistagged printed Sentinel was stripped by sanitiser rule 10.
        assert not has_keyword(state, poe, Keyword.SENTINEL)


class TestGarSaxonASH47:
    """When you play an upgrade on this unit: You may create a Mandalorian token.
    Use this ability only once each round."""

    def test_ASH_47_first_upgrade_makes_a_token_second_does_not(self, repo):
        from swu.engine.actions import apply, PlayCard
        from swu.engine.state import CardInstance, Zone
        from tests.test_sor_cards import _give_resources
        state = _make_state()
        gar = _place(state, "P0", _get_card(repo, "ASH", "47"), "ground")
        _give_resources(state, "P0", 20)
        for i in range(2):
            upg = CardInstance(f"P0_upg{i}", _get_card(repo, "ASH", "263"),
                               "P0", Zone.HAND)
            state.player_by_id("P0").hand.append(upg)
            state.active_player_index = 0   # playing a card hands the turn over
            state = apply(state, PlayCard(upg.instance_id,
                                          upgrade_target_id=gar.instance_id))
            state = _drive(state, _accept_and_target())
            assert len(_token_units(state, "P0")) == 1, f"after upgrade {i}"


class TestPointlessToResistASH54:
    """Attached unit gets -3/-0 while attacking a base."""

    def test_ASH_54_debuffs_only_a_base_attack(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")  # 3/7
        upg = CardInstance("P0_ptr", _get_card(repo, "ASH", "54"), "P0", Zone.HAND)
        host.attached_upgrades.append(upg)
        upg.zone = host.zone
        state = _fire_upgrade_played(state, upg, host)
        host = _find_instance(state, host.instance_id)
        assert compute_power(state, host, is_attacking=True) == 3      # vs a unit
        assert compute_power(state, host, is_attacking=True,
                             attacking_base=True) == 0                 # 3 - 3
        assert compute_hp(state, host) == 7                            # HP untouched


class TestHuyangASH56:
    """On Attack: You may give an upgraded unit -4/-0 for this phase."""

    def test_ASH_56_only_upgraded_units_are_offered(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        huyang = _place(state, "P0", _get_card(repo, "ASH", "56"), "ground")
        bare = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        upgraded = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        _attach(state, upgraded)                     # an Experience token IS an upgrade
        state = _fire_on_attack(state, huyang)
        state = _drive_until(state, "resolve_effects", _accept_and_target())
        offered = _target_ids(state)
        assert upgraded.instance_id in offered
        assert bare.instance_id not in offered
        state = _drive(state, _accept_and_target(upgraded))
        # 3 printed + 1 Experience, minus 4 → floored at 0
        assert compute_power(state, _find_instance(state, upgraded.instance_id)) == 0


class TestDuchesssProtectorASH58:
    """When Defeated: Create a Mandalorian token."""

    def test_ASH_58_creates_a_token_on_defeat(self, repo):
        state = _make_state()
        prot = _place(state, "P0", _get_card(repo, "ASH", "58"), "ground")
        state = _fire_when_defeated(state, prot)
        state = _drive(state)
        assert len(_token_units(state, "P0")) == 1


# ══════════════════════════════════════════════════════════════════════════════
# ash-set:26 — miscellaneous abilities
# ══════════════════════════════════════════════════════════════════════════════

class TestBoKatansGauntletASH63:
    """Each other friendly non-token unit gains: "When Defeated: Create a
    Mandalorian token." """

    def test_ASH_63_other_non_token_unit_mints_a_token(self, repo):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        _place(state, "P0", _get_card(repo, "ASH", "63"), "space")
        ally = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        _defeat_unit(state, state.player_by_id("P0"), ally)
        state = _drive(state)
        assert len(_token_units(state, "P0")) == 1

    def test_ASH_63_does_not_grant_to_a_token_unit(self, repo):
        from swu.engine.actions import _defeat_unit, _create_token_units
        state = _make_state()
        _place(state, "P0", _get_card(repo, "ASH", "63"), "space")
        tok = _create_token_units(state, state.player_by_id("P0"),
                                  "Mandalorian", 1)[0]
        _defeat_unit(state, state.player_by_id("P0"), tok)
        state = _drive(state)
        assert _token_units(state, "P0") == []   # no self-replicating tokens


class TestAtAttinSafetyDroidASH70:
    """If your base would be dealt more than 4 damage, prevent all but 4."""

    def test_ASH_70_caps_each_base_damage_instance_at_4(self, repo):
        from swu.abilities.resolver import _apply_deal_damage
        state = _make_state()
        base = state.player_by_id("P0").base_instance
        _apply_deal_damage(state, base.instance_id, 7)
        assert base.damage == 7                       # no Droid yet
        _place(state, "P0", _get_card(repo, "ASH", "70"), "ground")
        _apply_deal_damage(state, base.instance_id, 7)
        assert base.damage == 11                      # capped to 4
        _apply_deal_damage(state, base.instance_id, 3)
        assert base.damage == 14                      # under the cap, untouched

    def test_ASH_70_does_not_protect_the_enemy_base(self, repo):
        from swu.abilities.resolver import _apply_deal_damage
        state = _make_state()
        _place(state, "P0", _get_card(repo, "ASH", "70"), "ground")
        enemy_base = state.player_by_id("P1").base_instance
        _apply_deal_damage(state, enemy_base.instance_id, 7)
        assert enemy_base.damage == 7


class TestRyderAzadiASH77:
    """When Played: Name a card.  While this unit is in play, opponents can't play
    cards with that name."""

    def test_ASH_77_named_card_cannot_be_played_by_the_opponent(self, repo):
        from swu.engine.actions import legal_actions, PlayCard, NameCard, apply
        from swu.engine.state import CardInstance, Zone
        from tests.test_sor_cards import _give_resources
        state = _make_state()
        # The opponent holds (and controls a copy of) the card that gets named.
        victim_def = _get_card(repo, *VANILLA_GROUND)
        _place(state, "P1", victim_def, "ground")
        hand_copy = CardInstance("P1_v", victim_def, "P1", Zone.HAND)
        state.player_by_id("P1").hand.append(hand_copy)
        _give_resources(state, "P1", 20)

        ryder = _place(state, "P0", _get_card(repo, "ASH", "77"), "ground")
        state = _fire_when_played(state, ryder)
        names = [a for a in legal_actions(state) if isinstance(a, NameCard)]
        assert any(a.name == victim_def.name for a in names)
        state = apply(state, next(a for a in names if a.name == victim_def.name))
        state = _drive(state)

        state.active_player_index = 1
        plays = [a for a in legal_actions(state)
                 if isinstance(a, PlayCard) and a.instance_id == "P1_v"]
        assert plays == [], "the named card must be unplayable for the opponent"


class TestCovertBelieversASH80:
    """When Defeated: Create a Mandalorian token."""

    def test_ASH_80_creates_a_token_on_defeat(self, repo):
        state = _make_state()
        cb = _place(state, "P0", _get_card(repo, "ASH", "80"), "ground")
        state = _fire_when_defeated(state, cb)
        state = _drive(state)
        assert len(_token_units(state, "P0")) == 1


class TestArcanaStarMapASH84:
    """Attached unit gains: "If you would search a number of cards from your deck,
    search twice that number of cards instead." """

    def test_ASH_84_doubles_the_search_window(self, repo):
        from swu.engine.actions import push_deck_search
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        for _ in range(12):
            _push_deck_top(state, "P0", _get_card(repo, *VANILLA_WEAK))

        push_deck_search(state, host, count=1, eligible=lambda c: False, up_to=True,
                         window=3)
        assert state.pending_decisions[-1].context["window"] == 3
        state.pending_decisions.clear()

        upg = _get_card(repo, "ASH", "84")
        from swu.engine.state import CardInstance, Zone
        star_map = CardInstance("P0_map", upg, "P0", Zone.GROUND_ARENA)
        host.attached_upgrades.append(star_map)
        push_deck_search(state, host, count=1, eligible=lambda c: False, up_to=True,
                         window=3)
        assert state.pending_decisions[-1].context["window"] == 6


class TestBuyTimeASH91:
    """Create a Mandalorian token and give it Sentinel for this phase."""

    def test_ASH_91_token_enters_with_sentinel(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        state, _ev = _play_event_from_hand(state, repo, "ASH", "91")
        state = _drive(state)
        toks = _token_units(state, "P0")
        assert len(toks) == 1
        assert has_keyword(state, toks[0], Keyword.SENTINEL)


class TestCrixMadineASH108:
    """When Played: You may play a Heroism unit from your hand.  It costs 2 less for
    each arena in which you control the most units."""

    def test_ASH_108_discount_scales_with_arena_majorities(self, repo):
        state = _make_state()
        # A Heroism unit in hand (Luke Skywalker IBH_20, cost 7).
        from swu.engine.state import CardInstance, Zone
        luke = CardInstance("P0_luke", _get_card(repo, "IBH", "20"), "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(luke)
        from tests.test_sor_cards import _give_resources
        _give_resources(state, "P0", 20)
        # Crix + a space unit ⇒ the most units in BOTH arenas ⇒ 2 + 2 = 4 off.
        _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")
        crix = _place(state, "P0", _get_card(repo, "ASH", "108"), "ground")
        state = _fire_when_played(state, crix)
        state = _drive_until(state, "play_from_hand")
        assert state.pending_decisions[-1].context["cost_reduction"] == 4
        # And the "you may" is real — a decline is offered.
        from swu.engine.actions import legal_actions, DeclinePlayFromHand
        assert any(isinstance(a, DeclinePlayFromHand) for a in legal_actions(state))


# ══════════════════════════════════════════════════════════════════════════════
# ash-set:27 — miscellaneous abilities
# ══════════════════════════════════════════════════════════════════════════════

class TestChildrenOfTheWatchASH111:
    """When Played: Create 2 Mandalorian tokens."""

    def test_ASH_111_creates_two_tokens(self, repo):
        state = _make_state()
        cw = _place(state, "P0", _get_card(repo, "ASH", "111"), "ground")
        state = _fire_when_played(state, cw)
        state = _drive(state)
        assert len(_token_units(state, "P0")) == 2


class TestGreefKargaASH119:
    """Action [1 resource, Exhaust]: If your base was attacked this phase, create a
    Mandalorian token."""

    def test_ASH_119_offered_only_after_your_base_was_attacked(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility
        from tests.test_sor_cards import _give_resources
        state = _make_state()
        greef = _place(state, "P0", _get_card(repo, "ASH", "119"), "ground")
        greef.exhausted = False
        _give_resources(state, "P0", 5)
        assert not [a for a in legal_actions(state)
                    if isinstance(a, UseAbility) and a.source_id == greef.instance_id]

        state.game_memory.base_attackers_this_round["P0"] = ["enemy_unit"]
        uses = [a for a in legal_actions(state)
                if isinstance(a, UseAbility) and a.source_id == greef.instance_id]
        assert uses
        state = _drive(apply(state, uses[0]))
        assert len(_token_units(state, "P0")) == 1


class TestLangASH123:
    """Action [Exhaust]: This unit deals damage equal to his power to a ground unit."""

    def test_ASH_123_deals_his_power(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility
        state = _make_state()
        lang = _place(state, "P0", _get_card(repo, "ASH", "123"), "ground")  # 2/5
        lang.exhausted = False
        _attach(state, lang)                       # +1/+1 Experience ⇒ power 3
        victim = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == lang.instance_id)
        state = _drive(apply(state, use), _accept_and_target(victim))
        assert _find_instance(state, victim.instance_id).damage == 3


class TestProtectorateFighterASH124:
    """When Played: If you control a <uq> unit, create a Mandalorian token."""

    def test_ASH_124_needs_a_unique_unit(self, repo):
        state = _make_state()
        pf = _place(state, "P0", _get_card(repo, "ASH", "124"), "space")
        state = _drive(_fire_when_played(state, pf))
        assert _token_units(state, "P0") == []     # nothing unique on the board

        _place(state, "P0", _get_card(repo, "ASH", "123"), "ground")   # Lang, unique
        state = _drive(_fire_when_played(state, pf))
        assert len(_token_units(state, "P0")) == 1


class TestWarriorsLegacyASH134:
    """Attached unit gains: "When Defeated: Create a Mandalorian token." """

    def test_ASH_134_host_mints_a_token_when_it_dies(self, repo):
        from swu.engine.actions import _defeat_unit
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        upg = CardInstance("P0_wl", _get_card(repo, "ASH", "134"), "P0",
                           Zone.GROUND_ARENA)
        host.attached_upgrades.append(upg)
        _defeat_unit(state, state.player_by_id("P0"), host)
        state = _drive(state)
        assert len(_token_units(state, "P0")) == 1


class TestTheDarksaberASH135:
    """Attached unit is a leader unit and gains the Mandalorian trait; it provides its
    aspect icons while you are paying costs."""

    def test_ASH_135_host_becomes_a_leader_unit_with_the_mandalorian_trait(self, repo):
        from swu.abilities.resolver import _is_leader_unit
        from swu.engine.traits import has_trait
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        assert not _is_leader_unit(host)
        assert not has_trait(state, host, "Mandalorian")
        upg = CardInstance("P0_dks", _get_card(repo, "ASH", "135"), "P0",
                           Zone.GROUND_ARENA)
        host.attached_upgrades.append(upg)
        assert _is_leader_unit(host)
        assert has_trait(state, host, "Mandalorian")

    def test_ASH_135_host_provides_its_aspect_icons_for_costs(self, repo):
        from swu.engine.actions import _available_aspects
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        # Consular Security Force SOR_46 is a [Vigilance] unit.
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        host_aspects = [a.name for a in host.card_def.aspects]
        assert host_aspects, "the stand-in host must actually carry an aspect"
        ps = state.player_by_id("P0")
        before = _available_aspects(ps)[host_aspects[0]]
        upg = CardInstance("P0_dks", _get_card(repo, "ASH", "135"), "P0",
                           Zone.GROUND_ARENA)
        host.attached_upgrades.append(upg)
        assert _available_aspects(ps)[host_aspects[0]] == before + 1


class TestHoldThemOffASH139:
    """Choose a friendly unit.  That unit deals damage equal to its power divided as
    you choose among any number of units in its arena."""

    def test_ASH_139_pool_is_the_chosen_units_power_and_its_own_arena(self, repo):
        state = _make_state()
        dealer = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")  # 3
        same_arena = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        other_arena = _place(state, "P1", _get_card(repo, *VANILLA_SPACE), "space")
        state, _ev = _play_event_from_hand(state, repo, "ASH", "139")
        state = _drive_until(state, "distribute_damage", _accept_and_target(dealer))
        ctx = state.pending_decisions[-1].context
        assert ctx["pool"] == 3
        allowed = set(ctx["restrict_ids"])
        assert same_arena.instance_id in allowed
        assert dealer.instance_id in allowed        # "any number of units", not "other"
        assert other_arena.instance_id not in allowed


# ══════════════════════════════════════════════════════════════════════════════
# ash-set:28 — miscellaneous abilities
# ══════════════════════════════════════════════════════════════════════════════

class TestStrongerTogetherASH140:
    """Create 2 Mandalorian tokens."""

    def test_ASH_140_creates_two_tokens(self, repo):
        state = _make_state()
        state, _ev = _play_event_from_hand(state, repo, "ASH", "140")
        state = _drive(state)
        assert len(_token_units(state, "P0")) == 2


class TestEvisceratorASH149:
    """Advantage tokens on friendly units lose all abilities (they aren't defeated
    after combat) | When Played/On Attack: Give 2 Advantage tokens to each other
    friendly unit."""

    def test_ASH_149_tokens_each_other_friendly_unit(self, repo):
        state = _make_state()
        ev = _place(state, "P0", _get_card(repo, "ASH", "149"), "space")
        ally = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        enemy = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        state = _drive(_fire_when_played(state, ev))
        assert _advantage_count(_find_instance(state, ally.instance_id)) == 2
        assert _advantage_count(_find_instance(state, ev.instance_id)) == 0   # "other"
        assert _advantage_count(_find_instance(state, enemy.instance_id)) == 0

    def test_ASH_149_advantage_tokens_survive_combat(self, repo):
        from swu.engine.actions import apply, AttackWithUnit
        state = _make_state()
        atk = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        atk.exhausted = False
        _attach(state, atk, "Advantage")
        defender = _place(state, "P1", _get_card(repo, *VANILLA_WEAK), "ground")
        # Without Eviscerator the token expires with the attack.
        s1 = _drive(apply(state, AttackWithUnit(attacker_id=atk.instance_id,
                                                defender_id=defender.instance_id)))
        assert _advantage_count(_find_instance(s1, atk.instance_id)) == 0
        # With it on the board, it survives.
        _place(state, "P0", _get_card(repo, "ASH", "149"), "space")
        s2 = _drive(apply(state, AttackWithUnit(attacker_id=atk.instance_id,
                                                defender_id=defender.instance_id)))
        assert _advantage_count(_find_instance(s2, atk.instance_id)) == 1


class TestDeadlyVulnerabilityASH150:
    """If attached unit would take damage, it takes twice as much instead | While
    attached unit is defending, the attacker loses Overwhelm."""

    def test_ASH_150_doubles_damage_dealt_to_the_host(self, repo):
        from swu.abilities.resolver import _apply_deal_damage
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        host = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")  # 3/7
        upg = CardInstance("P1_dv", _get_card(repo, "ASH", "150"), "P1",
                           Zone.GROUND_ARENA)
        host.attached_upgrades.append(upg)
        _apply_deal_damage(state, host.instance_id, 3)
        assert _find_instance(state, host.instance_id).damage == 6

    def test_ASH_150_denies_the_attacker_overwhelm(self, repo):
        from swu.engine.actions import apply, AttackWithUnit
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        # Vader's Lightsaber grants nothing here — use a printed Overwhelm attacker.
        atk = _place(state, "P0", _get_card(repo, "ASH", "149"), "ground")  # 9 power
        atk.exhausted = False
        from swu.engine.state import Modifier
        state.modifiers.append(Modifier(
            modifier_id=state.alloc_modifier_id(),
            source_instance_id=atk.instance_id,
            target_instance_id=atk.instance_id,
            kind="keyword_grant",
            value={"keyword": "Overwhelm", "value": 0},
            duration="permanent"))
        victim = _place(state, "P1", _get_card(repo, *VANILLA_WEAK), "ground")  # 2/3
        base = state.player_by_id("P1").base_instance
        upg = CardInstance("P1_dv", _get_card(repo, "ASH", "150"), "P1",
                           Zone.GROUND_ARENA)
        victim.attached_upgrades.append(upg)
        state = _drive(apply(state, AttackWithUnit(attacker_id=atk.instance_id,
                                                   defender_id=victim.instance_id)))
        assert state.player_by_id("P1").base_instance.damage == 0


class TestOnyxCinderASH177:
    """Hidden | Other friendly units gain Hidden."""

    def test_ASH_177_grants_hidden_to_other_friendly_units(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        ally = _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")
        enemy = _place(state, "P1", _get_card(repo, *VANILLA_SPACE), "space")
        assert not has_keyword(state, ally, Keyword.HIDDEN)
        onyx = _place(state, "P0", _get_card(repo, "ASH", "177"), "space")
        assert has_keyword(state, ally, Keyword.HIDDEN)
        assert has_keyword(state, onyx, Keyword.HIDDEN)    # its own printed keyword
        assert not has_keyword(state, enemy, Keyword.HIDDEN)


class TestShinHatisFiendFighterASH191:
    """When Defeated: You may give 2 Advantage tokens to a unit — 3 instead if this
    unit wasn't defeated by combat damage."""

    def test_ASH_191_three_tokens_on_a_non_combat_defeat(self, repo):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        fighter = _place(state, "P0", _get_card(repo, "ASH", "191"), "space")
        ally = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        _defeat_unit(state, state.player_by_id("P0"), fighter)
        state = _drive(state, _accept_and_target(ally))
        assert _advantage_count(_find_instance(state, ally.instance_id)) == 3

    def test_ASH_191_two_tokens_on_a_combat_defeat(self, repo):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        fighter = _place(state, "P0", _get_card(repo, "ASH", "191"), "space")
        ally = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        _defeat_unit(state, state.player_by_id("P0"), fighter, by_combat_damage=True)
        state = _drive(state, _accept_and_target(ally))
        assert _advantage_count(_find_instance(state, ally.instance_id)) == 2


class TestHelgaitASH195:
    """When Defeated: You may distribute a number of Advantage tokens equal to this
    unit's power among friendly units."""

    def test_ASH_195_pool_equals_his_power_and_may_stack(self, repo):
        from swu.engine.actions import _defeat_unit, SelectTokenTarget
        state = _make_state()
        helgait = _place(state, "P0", _get_card(repo, "ASH", "195"), "ground")  # 6/4
        ally = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        _defeat_unit(state, state.player_by_id("P0"), helgait)
        state = _drive_until(state, "select_token", _accept_and_target())
        assert state.pending_decisions[-1].context["remaining"] == 6
        # allow_repeats ⇒ the whole pool may land on one unit.
        state = _drive(state, lambda st, acts: next(
            (a for a in acts if isinstance(a, SelectTokenTarget)
             and a.target_id == ally.instance_id), None))
        assert _advantage_count(_find_instance(state, ally.instance_id)) == 6


class TestThereIsNoConflictASH199:
    """When Played: Return any number of other upgrades on attached unit to their
    owners' hands."""

    def test_ASH_199_returns_another_upgrade_but_not_itself_or_tokens(self, repo):
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        other = CardInstance("P0_other", _get_card(repo, "ASH", "263"), "P0",
                             Zone.GROUND_ARENA)
        host.attached_upgrades.append(other)
        _attach(state, host)                       # an Experience token, not returnable
        tinc = CardInstance("P0_tinc", _get_card(repo, "ASH", "199"), "P0",
                            Zone.GROUND_ARENA)
        host.attached_upgrades.append(tinc)
        state = _fire_upgrade_played(state, tinc, host)
        state = _drive_until(state, "select_token")
        assert set(state.pending_decisions[-1].context["restrict_ids"]) == {"P0_other"}
        state = _drive(state)
        host = _find_instance(state, host.instance_id)
        assert "P0_other" not in {u.instance_id for u in host.attached_upgrades}
        assert "P0_tinc" in {u.instance_id for u in host.attached_upgrades}
        assert any(c.instance_id == "P0_other"
                   for c in state.player_by_id("P0").hand)


# ══════════════════════════════════════════════════════════════════════════════
# ash-set:29 — miscellaneous abilities  (completes ASH)
# ══════════════════════════════════════════════════════════════════════════════

class TestRehabilitationASH200:
    """Choose a non-leader unit.  Give it -3/-0 for this phase, then take control of
    it.  At the start of the regroup phase, its owner takes control of it."""

    def test_ASH_200_debuffs_and_takes_control_until_regroup(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        victim = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")  # 3/7
        state, _ev = _play_event_from_hand(state, repo, "ASH", "200")
        state = _drive(state, _accept_and_target(victim))
        moved = _find_instance(state, victim.instance_id)
        assert moved is not None
        assert any(u.instance_id == victim.instance_id
                   for u in state.player_by_id("P0").ground_arena)
        assert moved.owner_id == "P1"              # control moved, ownership did not
        assert compute_power(state, moved) == 0    # 3 - 3
        assert moved.return_control_to_owner_at_regroup


class TestFatefulGoodbyeASH211:
    """If a friendly unit left play this phase, distribute 3 Advantage tokens among
    friendly units.  If a friendly LEADER unit left play this phase, 5 instead."""

    def _setup(self, repo, *, lost_unit=False, lost_leader=False):
        state = _make_state()
        _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        if lost_unit and "P0" not in state.game_memory.defeated_controllers_this_round:
            state.game_memory.defeated_controllers_this_round.append("P0")
        if lost_leader:
            state.game_memory.leader_unit_defeat_controllers_this_phase.add("P0")
        return _play_event_from_hand(state, repo, "ASH", "211")[0]

    def test_ASH_211_fizzles_when_nothing_left_play(self, repo):
        assert not self._setup(repo).pending_decisions

    def test_ASH_211_pool_is_3_for_a_unit_and_5_for_a_leader(self, repo):
        s1 = _drive_until(self._setup(repo, lost_unit=True), "select_token")
        assert s1.pending_decisions[-1].context["remaining"] == 3
        s2 = _drive_until(self._setup(repo, lost_unit=True, lost_leader=True),
                          "select_token")
        assert s2.pending_decisions[-1].context["remaining"] == 5


class TestPeliMottoASH212:
    """Shielded | Ignore the aspect penalties of the first non-unit card you play each
    phase."""

    def test_ASH_212_waives_only_the_first_non_unit_play(self, repo):
        from swu.engine.actions import _play_cost
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        ps = state.player_by_id("P0")
        # An off-aspect EVENT: the base has no aspects, so it owes a penalty.
        evt = CardInstance("P0_ev", _get_card(repo, "ASH", "140"), "P0", Zone.HAND)
        unit = CardInstance("P0_un", _get_card(repo, *VANILLA_GROUND), "P0", Zone.HAND)
        full_evt = _play_cost(state, evt, ps)
        full_unit = _play_cost(state, unit, ps)
        assert full_evt > (evt.card_def.cost or 0), "the stand-in event must owe a penalty"

        _place(state, "P0", _get_card(repo, "ASH", "212"), "ground")
        assert _play_cost(state, evt, ps) == evt.card_def.cost      # waived
        assert _play_cost(state, unit, ps) == full_unit             # units untouched

        state.game_memory.non_units_played_this_phase["P0"] = 1
        assert _play_cost(state, evt, ps) == full_evt               # only the FIRST


class TestFerryDroidASH218:
    """When Played: Give 4 Advantage tokens to this unit."""

    def test_ASH_218_gives_itself_four_tokens(self, repo):
        state = _make_state()
        droid = _place(state, "P0", _get_card(repo, "ASH", "218"), "ground")
        state = _drive(_fire_when_played(state, droid))
        assert _advantage_count(_find_instance(state, droid.instance_id)) == 4


class TestAttendantNavigatorASH238:
    """When Played: You may give 2 Advantage tokens to a space unit."""

    def test_ASH_238_only_space_units_are_offered(self, repo):
        state = _make_state()
        nav = _place(state, "P0", _get_card(repo, "ASH", "238"), "ground")
        ground = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        space = _place(state, "P0", _get_card(repo, *VANILLA_SPACE), "space")
        state = _fire_when_played(state, nav)
        state = _drive_until(state, "resolve_effects", _accept_and_target())
        offered = _target_ids(state)
        assert space.instance_id in offered
        assert ground.instance_id not in offered
        state = _drive(state, _accept_and_target(space))
        assert _advantage_count(_find_instance(state, space.instance_id)) == 2


class TestImperialDefectorASH250:
    """When Played: Look at an opponent's hand."""

    def test_ASH_250_pushes_a_private_look_hand(self, repo):
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        card = _get_card(repo, *VANILLA_GROUND)
        state.player_by_id("P1").hand.append(
            CardInstance("P1_h", card, "P1", Zone.HAND))
        defector = _place(state, "P0", _get_card(repo, "ASH", "250"), "ground")
        state = _fire_when_played(state, defector)
        state = _drive_until(state, "look_hand")
        top = state.pending_decisions[-1]
        assert top.kind == "look_hand"
        assert top.deciding_player_id == "P0"
        shown = top.context["revealed_hand"]
        assert [c["card_name"] for c in shown] == [card.display_name]
        # Hidden-info shape: card identities only, never the opponent's instance_ids.
        assert all("instance_id" not in c for c in shown)


class TestGallofreeTransportASH254:
    """When Defeated: Give 2 Advantage tokens to a friendly unit."""

    def test_ASH_254_tokens_a_friendly_unit_on_defeat(self, repo):
        state = _make_state()
        gt = _place(state, "P0", _get_card(repo, "ASH", "254"), "space")
        ally = _place(state, "P0", _get_card(repo, *VANILLA_GROUND), "ground")
        enemy = _place(state, "P1", _get_card(repo, *VANILLA_GROUND), "ground")
        state = _fire_when_defeated(state, gt)
        assert enemy.instance_id not in _target_ids(state)
        state = _drive(state, _accept_and_target(ally))
        assert _advantage_count(_find_instance(state, ally.instance_id)) == 2


# ── Registration smoke test ──────────────────────────────────────────────────

class TestASHRegistrationSmoke:
    @pytest.mark.parametrize("num", [
        "8", "9", "14", "33", "36", "37", "46", "50", "59", "68", "72", "99",
        "101", "156", "168", "189", "202", "203", "209", "223", "241", "253",
        "4", "11", "12", "27", "32", "35", "38",
        "43", "53", "60", "62", "67", "71", "83",
        "85", "90", "92", "94", "102", "103", "110",
        "112", "118", "132", "137", "138", "142", "146",
        "147", "148", "151", "153", "158", "161", "163",
        "165", "170", "171", "174", "176", "179", "183",
        "186", "187", "194", "196", "210", "259",
        "45", "55", "87", "97", "104", "107", "116",
        "128", "169", "172", "185", "220", "229", "230",
        "232", "235", "236", "246", "247", "260",
        "1", "2", "3", "5", "6", "7", "10",
        "240", "245", "248", "251", "255", "257", "262", "263", "264",
        "224", "227", "228", "231", "233", "234", "237",
        "207", "208", "214", "216", "217", "219", "221",
        "184", "188", "197", "198", "204", "205", "206",
        "127", "133", "136", "144", "155", "157", "159", "160", "162", "167", "178", "180", "181", "182",
        "105", "109", "113", "114", "115", "120", "125",
        "82", "86", "88", "89", "93", "98", "100",
        "65", "66", "73", "75", "78", "79", "81",
        "41", "44", "49", "51", "52", "57", "64",
        "13", "15", "16", "17", "30", "31", "39",
        "28", "34", "40", "47", "54", "56", "58",
        "63", "70", "77", "80", "84", "91", "108",
        "111", "119", "123", "124", "134", "135", "139",
        "140", "149", "150", "177", "191", "195", "199",
        "200", "211", "212", "218", "238", "250", "254",
    ])
    def test_ASH_registered(self, num):
        from swu.abilities.registry import get_abilities
        assert get_abilities("ASH", num), f"ASH_{num} not registered"
