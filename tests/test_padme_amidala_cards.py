"""Tests for the padme-amidala deck's card encodings.

Group ``padme-amidala:01`` — Card advantage & disruption:
  * SEC_94  Mina Bonteri — "When Defeated: You may disclose Command+Command+Heroism.
    If you do, draw a card." (the new ``draw`` disclose-payoff arm.)
  * SEC_197 Furtive Handmaiden — "On Attack: You may discard a card from your hand.
    If you do, draw a card." (optional trigger + discard/draw, pure reuse.)

Group ``padme-amidala:02`` — Combat tricks, buffs & tempo:
  * SEC_96  Ahsoka Tano — WhenAttackEnds disclose Command+Heroism → attack with
    another unit (the new ``granted_attack`` disclose-payoff arm).
  * SEC_98  Captain Typho — WhenAttacked disclose Command+Heroism → heal 1 from
    your base (the new ``heal_base`` disclose-payoff arm).
  * SEC_99  Naboo Royal Starship — ConstantAbility granting Raid 2 + Overwhelm to
    friendly leader units.
  * JTL_111 Seasoned Fleet Admiral — ``WhenYouDraw(opponent=True)`` observer →
    optional GiveToken Experience (the new ``opponent`` draw-observer flag).
  * SEC_111 Jar Jar Binks — optional WhenPlayed +2/+2 to another friendly unit.
  * SEC_116 Nubian Star Skiff — conditional self-grant of Restore 2 while you
    control an Official unit.
  * JTL_123 Dogfight — event granting an attack with an exhausted unit that can't
    attack bases.

Group ``padme-amidala:03`` — Combat tricks, buffs & tempo:
  * SEC_129 With Thunderous Applause — event: buff a unit +2/+2, then disclose
    Command → buff another unit (the new ``buff_unit`` disclose-payoff arm).
  * SEC_201 Anakin Skywalker — conditional self-grant of Raid 2 while you control
    Padmé Amidala (leader or unit); Hidden is kept.
  * SEC_234 Bog Down in Procedure — event: exhaust a unit, then disclose Cunning →
    exhaust another unit (the new ``exhaust_unit`` disclose-payoff arm).

Group ``padme-amidala:04`` — Miscellaneous abilities:
  * SEC_106 Dismantle the Conspiracy — event: a friendly unit captures any number
    of enemy non-leader units with combined remaining HP ≤ 7 (the new
    ``capture_combined_hp`` decision kind).
  * SEC_115 Taylander Shuttle — OnAttack (initiative-gated) create a Spy token.
  * SEC_120 Naboo Security Force — WhenPlayed/WhenDefeated disclose Command → give
    a friendly unit Sentinel this phase (the new ``grant_keyword`` payoff arm).
  * SEC_127 Charged with Corruption — event: disclose Command+Command → a friendly
    unit captures an enemy non-leader unit (the new ``capture`` payoff arm).
  * SEC_208 Hunter — Saboteur + OnAttack: if the defender is exhausted it gets
    −4/−0 for this attack.
  * SEC_248 B2EMO — Restore + OnAttack disclose Heroism+Heroism → give a unit
    Sentinel this phase (the ``grant_keyword`` payoff arm).
  * SEC_256 Moral Authority — upgrade WhenPlayed: attached unit captures an enemy
    non-leader unit with less remaining HP than it (the new
    ``less_remaining_hp_than_host`` predicate).

Group ``padme-amidala:05`` — New primitive: reveal-or-discard-trigger:
  * SEC_16 Padmé Amidala — the new ``WhenYouRevealOrDiscard`` observer trigger
    (settle-point ledger drain, mirroring WhenYouUseForce / WhenYouDraw).  Both
    sides fire when P0 reveals (a successful Disclose) or discards 1+ cards from
    their hand: undeployed = "may exhaust this leader, then deal 1 damage" (gated
    SOURCE_READY); deployed = "may deal 1 damage to a unit".

Method names embed the card number so the encoding verifier's ``-k`` gate selects
them.
"""
from __future__ import annotations

from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _get_card, _make_state, _place, _fire_on_attack, _defeat_and_fire,
    _push_deck_top, _fire_attack_ends, _fire_when_played, _experience_count,
    _play_event_from_hand, _place_leader, _find_instance,
)
from tests.test_disclose import _add_hand, _settle, _neutral, _her


def _resolve_all(state):
    """Drive AutoResolveEffects to quiescence (no player-facing choices left)."""
    from swu.engine.actions import legal_actions, apply, AutoResolveEffects
    for _ in range(40):
        if not state.pending_decisions:
            break
        a = next((x for x in legal_actions(state)
                  if isinstance(x, AutoResolveEffects)), None)
        if a is None:
            break
        state = apply(state, a)
    return state


# ── SEC_94 Mina Bonteri (WhenDefeated, disclose Command×2+Heroism → draw) ──────

class TestMinaBonteri:
    def _setup(self, repo, *, with_aspects=True, deck=True):
        state = _make_state()
        mina = _place(state, "P0", _get_card(repo, "SEC", "94"), "ground")
        if with_aspects:
            # Two Command+Heroism cards cover the Command×2 + Heroism requirement.
            _add_hand(state, "P0", _her(repo))
            _add_hand(state, "P0", _her(repo))
        if deck:
            _push_deck_top(state, "P0", _neutral(repo))
        return state, mina

    def test_sec_94_disclose_draws_a_card(self, repo):
        state, mina = self._setup(repo)
        drawn_id = state.player_by_id("P0").deck[0].instance_id
        before = len(state.player_by_id("P0").hand)   # 2 (disclosed cards stay)
        state = _defeat_and_fire(state, mina, "P0")
        state = _settle(state)   # disclose both cards, then draw
        assert not state.pending_decisions
        hand = state.player_by_id("P0").hand
        assert len(hand) == before + 1   # revealed cards remain in hand, +1 drawn
        assert any(c.instance_id == drawn_id for c in hand)

    def test_sec_94_decline_disclose_no_draw(self, repo):
        state, mina = self._setup(repo)
        before = len(state.player_by_id("P0").hand)
        state = _defeat_and_fire(state, mina, "P0")
        state = _settle(state, decline_disclose=True)
        assert not state.pending_decisions
        assert len(state.player_by_id("P0").hand) == before   # no draw

    def test_sec_94_cannot_disclose_no_prompt_no_draw(self, repo):
        # A hand that can't cover Command×2+Heroism → no prompt, no draw.
        state = _make_state()
        mina = _place(state, "P0", _get_card(repo, "SEC", "94"), "ground")
        _add_hand(state, "P0", _neutral(repo))   # mono-Vigilance
        _push_deck_top(state, "P0", _neutral(repo))
        before = len(state.player_by_id("P0").hand)
        state = _defeat_and_fire(state, mina, "P0")
        state = _settle(state)
        assert not state.pending_decisions
        assert len(state.player_by_id("P0").hand) == before   # no disclose, no draw


# ── SEC_197 Furtive Handmaiden (On Attack, may discard → draw) ─────────────────

class TestFurtiveHandmaiden:
    def _setup(self, repo, *, hand=1):
        state = _make_state()
        hm = _place(state, "P0", _get_card(repo, "SEC", "197"), "ground")
        for _ in range(hand):
            _add_hand(state, "P0", _neutral(repo))
        _push_deck_top(state, "P0", _neutral(repo))
        return state, hm

    def test_sec_197_discard_then_draw(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        state, hm = self._setup(repo, hand=1)
        ps = state.player_by_id("P0")
        drawn_id = ps.deck[0].instance_id
        discarded_id = ps.hand[0].instance_id
        before_hand = len(ps.hand)          # 1
        before_discard = len(ps.discard)
        state = _fire_on_attack(state, hm)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = _resolve_all(state)
        assert not state.pending_decisions
        ps = state.player_by_id("P0")
        assert len(ps.hand) == before_hand           # discard 1, draw 1 → net 0
        assert len(ps.discard) == before_discard + 1
        assert any(c.instance_id == drawn_id for c in ps.hand)      # drew deck top
        assert any(c.instance_id == discarded_id for c in ps.discard)

    def test_sec_197_decline_no_discard_no_draw(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state, hm = self._setup(repo, hand=1)
        before_hand = len(state.player_by_id("P0").hand)
        before_discard = len(state.player_by_id("P0").discard)
        state = _fire_on_attack(state, hm)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        state = _resolve_all(state)
        ps = state.player_by_id("P0")
        assert len(ps.hand) == before_hand
        assert len(ps.discard) == before_discard

    def test_sec_197_not_offered_with_empty_hand(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state, hm = self._setup(repo, hand=0)
        state = _fire_on_attack(state, hm)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


# ══ Group padme-amidala:02 — Combat tricks, buffs & tempo ═════════════════════

def _has_trigger_option(state):
    from swu.engine.actions import legal_actions, AcceptTrigger, DeclineTrigger
    return any(isinstance(a, (AcceptTrigger, DeclineTrigger))
               for a in legal_actions(state))


def _accept_trigger(state):
    from swu.engine.actions import legal_actions, apply, AcceptTrigger
    return apply(state, next(a for a in legal_actions(state)
                             if isinstance(a, AcceptTrigger)))


def _choose_target(state, target_id):
    from swu.engine.actions import legal_actions, apply, ChooseTarget
    return apply(state, next(a for a in legal_actions(state)
                             if isinstance(a, ChooseTarget)
                             and a.target_id == target_id))


# ── SEC_96 Ahsoka Tano (WhenAttackEnds, disclose Command+Heroism → attack again) ─

class TestAhsokaTanoSec96:
    def _setup(self, repo, *, with_aspects=True):
        state = _make_state()
        ahsoka = _place(state, "P0", _get_card(repo, "SEC", "96"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # ready 3-power
        if with_aspects:
            _add_hand(state, "P0", _her(repo))   # one card carrying Command + Heroism
        return state, ahsoka, ally

    def test_sec_96_disclose_grants_attack_with_another_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state, ahsoka, ally = self._setup(repo)
        base_before = state.players[1].base_instance.damage
        state = _fire_attack_ends(state, ahsoka)
        state = _settle(state)   # accept disclose → granted_attack pushed
        assert state.pending_decisions[-1].kind == "granted_attack"
        # Ahsoka herself is excluded ("another unit").
        acts = legal_actions(state)
        assert not any(isinstance(a, AttackWithUnit)
                       and a.attacker_id == ahsoka.instance_id for a in acts)
        atk = next(a for a in acts if isinstance(a, AttackWithUnit)
                   and a.attacker_id == ally.instance_id and a.defender_id is None)
        state = apply(state, atk)
        assert not state.pending_decisions
        assert state.players[1].base_instance.damage > base_before

    def test_sec_96_decline_disclose_no_attack(self, repo):
        state, ahsoka, ally = self._setup(repo)
        state = _fire_attack_ends(state, ahsoka)
        state = _settle(state, decline_disclose=True)
        assert not state.pending_decisions

    def test_sec_96_cannot_disclose_no_prompt(self, repo):
        state, ahsoka, ally = self._setup(repo, with_aspects=False)
        state = _fire_attack_ends(state, ahsoka)
        state = _settle(state)
        assert not state.pending_decisions


# ── SEC_98 Captain Typho (WhenAttacked, disclose Command+Heroism → heal base) ────

class TestCaptainTypho:
    def _setup(self, repo, *, with_aspects=True, base_damage=3):
        state = _make_state()
        typho = _place(state, "P0", _get_card(repo, "SEC", "98"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state.players[0].base_instance.damage = base_damage
        if with_aspects:
            _add_hand(state, "P0", _her(repo))
        return state, typho, attacker

    def test_sec_98_disclose_heals_base(self, repo):
        state, typho, attacker = self._setup(repo, base_damage=3)
        state = _fire_on_attack(state, attacker, defender_ci=typho)
        state = _settle(state)
        assert not state.pending_decisions
        assert state.players[0].base_instance.damage == 2   # healed 1

    def test_sec_98_decline_no_heal(self, repo):
        state, typho, attacker = self._setup(repo, base_damage=3)
        state = _fire_on_attack(state, attacker, defender_ci=typho)
        state = _settle(state, decline_disclose=True)
        assert state.players[0].base_instance.damage == 3

    def test_sec_98_cannot_disclose_no_prompt(self, repo):
        state, typho, attacker = self._setup(repo, with_aspects=False, base_damage=3)
        state = _fire_on_attack(state, attacker, defender_ci=typho)
        state = _settle(state)
        assert not state.pending_decisions
        assert state.players[0].base_instance.damage == 3


# ── SEC_99 Naboo Royal Starship (Constant: friendly leader units gain Raid 2/OW) ─

class TestNabooRoyalStarship:
    def test_sec_99_grants_raid2_and_overwhelm_to_leader_units(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SEC", "99"), "space")   # the Starship
        leader = _place(state, "P0", _get_card(repo, "SEC", "16"), "ground")  # Padmé leader
        leader.deployed = True
        nonleader = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert keyword_value(state, leader, Keyword.RAID) == 2
        assert has_keyword(state, leader, Keyword.OVERWHELM)
        # A non-leader friendly unit gets neither.
        assert keyword_value(state, nonleader, Keyword.RAID) == 0
        assert not has_keyword(state, nonleader, Keyword.OVERWHELM)

    def test_sec_99_enemy_leader_unit_unaffected(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SEC", "99"), "space")
        enemy_leader = _place(state, "P1", _get_card(repo, "SEC", "16"), "ground")
        enemy_leader.deployed = True
        assert keyword_value(state, enemy_leader, Keyword.RAID) == 0
        assert not has_keyword(state, enemy_leader, Keyword.OVERWHELM)


# ── JTL_111 Seasoned Fleet Admiral (opponent draws → may give Experience) ────────

class TestSeasonedFleetAdmiral:
    def test_jtl_111_opponent_draw_offers_experience(self, repo):
        from swu.engine.actions import _draw_cards, _fire_draw_observers
        state = _make_state()
        admiral = _place(state, "P0", _get_card(repo, "JTL", "111"), "ground")
        _push_deck_top(state, "P1", _neutral(repo))
        _draw_cards(state, state.player_by_id("P1"), 1)   # opponent draws (ACTION)
        state = _fire_draw_observers(state)
        assert _has_trigger_option(state), "opponent draw should offer the trigger"
        state = _accept_trigger(state)
        state = _choose_target(state, admiral.instance_id)
        state = _resolve_all(state)
        assert not state.pending_decisions
        admiral = next(c for c in state.player_by_id("P0").ground_arena
                       if c.instance_id == admiral.instance_id)
        assert _experience_count(admiral) == 1

    def test_jtl_111_own_draw_no_trigger(self, repo):
        from swu.engine.actions import _draw_cards, _fire_draw_observers
        state = _make_state()
        _place(state, "P0", _get_card(repo, "JTL", "111"), "ground")
        _push_deck_top(state, "P0", _neutral(repo))
        _draw_cards(state, state.player_by_id("P0"), 1)   # controller's OWN draw
        state = _fire_draw_observers(state)
        assert not _has_trigger_option(state)
        assert not state.pending_decisions

    def test_jtl_111_opponent_draw_does_not_leak_drawn_card(self, repo):
        # Regression: the opponent-draw observer's decision belongs to P0, but the
        # draw event_ctx carries the id of the card P1 just drew into hand.  That id
        # must NOT ride the persisted trigger_option context into P0's view — else
        # P0 sees an opponent hand card (hidden-info leak; soak seeds 186/199).
        from swu.engine.actions import _draw_cards, _fire_draw_observers
        state = _make_state()
        _place(state, "P0", _get_card(repo, "JTL", "111"), "ground")
        _push_deck_top(state, "P1", _neutral(repo))
        p1 = state.player_by_id("P1")
        before = {ci.instance_id for ci in p1.hand}
        _draw_cards(state, p1, 1)   # opponent draws (ACTION)
        drawn_id = next(ci.instance_id for ci in p1.hand
                        if ci.instance_id not in before)
        state = _fire_draw_observers(state)
        assert _has_trigger_option(state), "opponent draw should offer the trigger"
        # The drawn card id is genuinely in P1's hand (hidden from P0)…
        assert any(ci.instance_id == drawn_id
                   for ci in state.player_by_id("P1").hand)
        # …and must not appear anywhere in P0's redacted view.
        assert f'"{drawn_id}"' not in state.view_for("P0").to_json()


# ── SEC_111 Jar Jar Binks (WhenPlayed: may give another friendly unit +2/+2) ─────

class TestJarJarBinks:
    def test_sec_111_buffs_another_friendly_unit(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        jarjar = _place(state, "P0", _get_card(repo, "SEC", "111"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        base_power = compute_power(state, ally)
        state = _fire_when_played(state, jarjar)
        state = _accept_trigger(state)
        state = _choose_target(state, ally.instance_id)
        state = _resolve_all(state)
        ally = next(c for c in state.player_by_id("P0").ground_arena
                    if c.instance_id == ally.instance_id)
        assert compute_power(state, ally) == base_power + 2

    def test_sec_111_alone_no_target_auto_declines(self, repo):
        # Only Jar Jar in play → "another friendly unit" has no target → no prompt.
        state = _make_state()
        jarjar = _place(state, "P0", _get_card(repo, "SEC", "111"), "ground")
        state = _fire_when_played(state, jarjar)
        assert not _has_trigger_option(state)
        assert not state.pending_decisions


# ── SEC_116 Nubian Star Skiff (conditional self-grant: Restore 2 with Official) ──

class TestNubianStarSkiff:
    def test_sec_116_gains_restore_with_official_unit(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        skiff = _place(state, "P0", _get_card(repo, "SEC", "116"), "space")
        _place(state, "P0", _get_card(repo, "SEC", "111"), "ground")  # Jar Jar = Official
        assert has_keyword(state, skiff, Keyword.RESTORE)
        assert keyword_value(state, skiff, Keyword.RESTORE) == 2

    def test_sec_116_no_restore_without_official(self, repo):
        # No Official unit → the conditional grant is off (proves the printed
        # "Restore" tag was sanitised, i.e. it is not an always-on keyword).
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        skiff = _place(state, "P0", _get_card(repo, "SEC", "116"), "space")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # not Official
        assert not has_keyword(state, skiff, Keyword.RESTORE)


# ── JTL_123 Dogfight (event: attack with an exhausted unit; can't attack bases) ──

class TestDogfight:
    def test_jtl_123_grants_attack_with_exhausted_unit_vs_enemy(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        attacker.exhausted = True   # exhausted — normally couldn't attack
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "JTL", "123", owner="P0")
        assert state.pending_decisions[-1].kind == "granted_attack"
        acts = legal_actions(state)
        # The exhausted unit is offered (allow_exhausted); bases are off-limits
        # (no_base) so it attacks the enemy unit, not the base.
        assert not any(isinstance(a, AttackWithUnit)
                       and a.attacker_id == attacker.instance_id
                       and a.defender_id is None for a in acts)
        atk = next(a for a in acts if isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id
                   and a.defender_id == enemy.instance_id)
        state = apply(state, atk)
        enemy = next((c for c in state.player_by_id("P1").ground_arena
                      if c.instance_id == enemy.instance_id), None)
        assert enemy is None or enemy.damage > 0   # took the attacker's power


# ══ Group padme-amidala:03 — Combat tricks, buffs & tempo ═════════════════════

def _cun(repo):
    """A hand card carrying the Cunning aspect icon (ISB Agent SOR_176)."""
    return _get_card(repo, "SOR", "176")


def _add_leader_to_base(state, owner, card_def):
    """Add an undeployed leader to ``owner``'s base zone (for CONTROLS_NAMED)."""
    from swu.engine.state import CardInstance, Zone
    import uuid as _u
    ci = CardInstance(
        instance_id=f"{owner}_ldr_{_u.uuid4().hex[:6]}",
        card_def=card_def, owner_id=owner, zone=Zone.BASE_ZONE,
    )
    state.player_by_id(owner).base_zone.append(ci)
    return ci


# ── SEC_129 With Thunderous Applause (buff a unit; disclose Command → another) ──

class TestWithThunderousApplause:
    def test_sec_129_buffs_first_then_another_via_disclose(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        a = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # 3-power
        b = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _add_hand(state, "P0", _her(repo))   # carries Command
        state, _evt = _play_event_from_hand(state, repo, "SEC", "129")
        # First buff → unit a gets +2/+2.
        state = _choose_target(state, a.instance_id)
        assert compute_power(state, a) == 5
        # Second target: "another unit" — a is excluded, b offered.
        from swu.engine.actions import legal_actions, ChooseTarget
        offered = {x.target_id for x in legal_actions(state)
                   if isinstance(x, ChooseTarget)}
        assert a.instance_id not in offered and b.instance_id in offered
        state = _choose_target(state, b.instance_id)
        assert state.pending_decisions[-1].kind == "disclose"
        state = _settle(state)   # disclose Command → buff_unit payoff on b
        assert not state.pending_decisions
        assert compute_power(state, b) == 5

    def test_sec_129_decline_disclose_only_first_buffed(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        a = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        b = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _add_hand(state, "P0", _her(repo))
        state, _evt = _play_event_from_hand(state, repo, "SEC", "129")
        state = _choose_target(state, a.instance_id)
        state = _choose_target(state, b.instance_id)
        state = _settle(state, decline_disclose=True)
        assert not state.pending_decisions
        assert compute_power(state, a) == 5   # first buff landed
        assert compute_power(state, b) == 3   # second declined

    def test_sec_129_single_unit_no_disclose(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        a = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _add_hand(state, "P0", _her(repo))   # Command available, but no 2nd unit
        state, _evt = _play_event_from_hand(state, repo, "SEC", "129")
        state = _choose_target(state, a.instance_id)
        assert not state.pending_decisions   # no "another unit" → no disclose
        assert compute_power(state, a) == 5


# ── SEC_201 Anakin Skywalker (conditional Raid 2 while you control Padmé) ───────

class TestAnakinSkywalkerSec201:
    def test_sec_201_gains_raid_2_while_padme_controlled(self, repo):
        from swu.engine.keywords import keyword_value, has_keyword, Keyword
        state = _make_state()
        anakin = _place(state, "P0", _get_card(repo, "SEC", "201"), "ground")
        _add_leader_to_base(state, "P0", _get_card(repo, "SEC", "16"))  # Padmé
        assert keyword_value(state, anakin, Keyword.RAID) == 2
        assert has_keyword(state, anakin, Keyword.HIDDEN)   # printed keyword kept

    def test_sec_201_no_raid_without_padme(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        anakin = _place(state, "P0", _get_card(repo, "SEC", "201"), "ground")
        # Queen Amidala (SEC_101) must NOT satisfy "Padmé Amidala".
        _place(state, "P0", _get_card(repo, "SEC", "101"), "ground")
        assert keyword_value(state, anakin, Keyword.RAID) == 0


# ── SEC_234 Bog Down in Procedure (exhaust a unit; disclose Cunning → another) ──

class TestBogDownInProcedure:
    def test_sec_234_exhausts_first_then_another_via_disclose(self, repo):
        from tests.test_sor_cards import _find_instance
        state = _make_state()
        a = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        b = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _add_hand(state, "P0", _cun(repo))   # carries Cunning
        state, _evt = _play_event_from_hand(state, repo, "SEC", "234")
        state = _choose_target(state, a.instance_id)
        assert _find_instance(state, a.instance_id).exhausted
        from swu.engine.actions import legal_actions, ChooseTarget
        offered = {x.target_id for x in legal_actions(state)
                   if isinstance(x, ChooseTarget)}
        assert a.instance_id not in offered and b.instance_id in offered
        state = _choose_target(state, b.instance_id)
        assert state.pending_decisions[-1].kind == "disclose"
        state = _settle(state)   # disclose Cunning → exhaust_unit payoff on b
        assert not state.pending_decisions
        assert _find_instance(state, b.instance_id).exhausted

    def test_sec_234_decline_disclose_only_first_exhausted(self, repo):
        from tests.test_sor_cards import _find_instance
        state = _make_state()
        a = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        b = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _add_hand(state, "P0", _cun(repo))
        state, _evt = _play_event_from_hand(state, repo, "SEC", "234")
        state = _choose_target(state, a.instance_id)
        state = _choose_target(state, b.instance_id)
        state = _settle(state, decline_disclose=True)
        assert not state.pending_decisions
        assert _find_instance(state, a.instance_id).exhausted
        assert not _find_instance(state, b.instance_id).exhausted

    def test_sec_234_single_unit_no_disclose(self, repo):
        from tests.test_sor_cards import _find_instance
        state = _make_state()
        a = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _add_hand(state, "P0", _cun(repo))
        state, _evt = _play_event_from_hand(state, repo, "SEC", "234")
        state = _choose_target(state, a.instance_id)
        assert not state.pending_decisions   # no "another unit" → no disclose
        assert _find_instance(state, a.instance_id).exhausted


# ══ Group padme-amidala:04 — Miscellaneous abilities ══════════════════════════

def _set_remaining_hp(state, ci, remaining):
    """Damage ``ci`` so its remaining HP equals ``remaining`` (for budget tests)."""
    from swu.engine.actions import compute_hp
    ci.damage = max(0, compute_hp(state, ci) - remaining)


def _attach_upgrade(state, host_ci, upgrade_def, owner="P0"):
    """Create an upgrade CardInstance and attach it to ``host_ci`` (for an upgrade
    WhenPlayed capture — Moral Authority SEC_256)."""
    from swu.engine.state import CardInstance
    import uuid as _u
    up = CardInstance(
        instance_id=f"{owner}_up_{_u.uuid4().hex[:6]}",
        card_def=upgrade_def, owner_id=owner, zone=host_ci.zone,
    )
    host_ci.attached_upgrades.append(up)
    return up


# ── SEC_106 Dismantle the Conspiracy (friendly unit captures any number ≤ 7 HP) ─

class TestDismantleTheConspiracy:
    def test_sec_106_captures_units_within_hp_budget(self, repo):
        from swu.engine.actions import (legal_actions, apply,
                                        SelectUnitToCaptureCombined)
        state = _make_state()
        captor = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        e1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        e2 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        big = _place(state, "P1", _get_card(repo, "SOR", "39"), "ground")   # 8/8
        _set_remaining_hp(state, e1, 3)
        _set_remaining_hp(state, e2, 4)
        _set_remaining_hp(state, big, 8)   # exceeds the 7 budget alone → never eligible
        state, _evt = _play_event_from_hand(state, repo, "SEC", "106")
        # First choose the friendly captor.
        state = _choose_target(state, captor.instance_id)
        assert state.pending_decisions[-1].kind == "capture_combined_hp"
        # The oversized unit is never offered.
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, SelectUnitToCaptureCombined)}
        assert big.instance_id not in offered
        assert {e1.instance_id, e2.instance_id} <= offered
        # Capture e1 (budget 7→4), then e2 (4→0) — auto-resolves when none remain.
        state = apply(state, SelectUnitToCaptureCombined(e1.instance_id))
        state = apply(state, SelectUnitToCaptureCombined(e2.instance_id))
        state = _resolve_all(state)   # pop the trailing single-effect resolve_effects
        assert not state.pending_decisions
        cap = {c.instance_id for c in state.player_by_id("P0").capture_pile}
        assert {e1.instance_id, e2.instance_id} <= cap
        # The oversized unit is untouched in P1's arena.
        from tests.test_sor_cards import _find_instance
        assert _find_instance(state, big.instance_id) is not None

    def test_sec_106_finish_captures_none(self, repo):
        from swu.engine.actions import apply, FinishCaptureCombined
        state = _make_state()
        captor = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        e1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _set_remaining_hp(state, e1, 3)
        state, _evt = _play_event_from_hand(state, repo, "SEC", "106")
        state = _choose_target(state, captor.instance_id)
        state = apply(state, FinishCaptureCombined())   # "any number" includes 0
        state = _resolve_all(state)   # pop the trailing single-effect resolve_effects
        assert not state.pending_decisions
        assert state.player_by_id("P0").capture_pile == []


# ── SEC_115 Taylander Shuttle (OnAttack, initiative-gated create Spy token) ─────

class TestTaylanderShuttle:
    def _spy_count(self, state, owner="P0"):
        ps = state.player_by_id(owner)
        return sum("Spy" in c.card_def.display_name
                   for c in ps.ground_arena + ps.space_arena)

    def test_sec_115_creates_spy_token_with_initiative(self, repo):
        state = _make_state()
        state.initiative_holder = 0   # P0 has initiative
        shuttle = _place(state, "P0", _get_card(repo, "SEC", "115"), "space")
        before = self._spy_count(state)
        state = _fire_on_attack(state, shuttle)
        assert not state.pending_decisions
        assert self._spy_count(state) == before + 1

    def test_sec_115_no_token_without_initiative(self, repo):
        state = _make_state()
        state.initiative_holder = 1   # P1 has initiative
        shuttle = _place(state, "P0", _get_card(repo, "SEC", "115"), "space")
        before = self._spy_count(state)
        state = _fire_on_attack(state, shuttle)
        assert not state.pending_decisions   # condition gates collection
        assert self._spy_count(state) == before


# ── SEC_120 Naboo Security Force (disclose Command → give a unit Sentinel) ──────

class TestNabooSecurityForce:
    def test_sec_120_when_played_grants_sentinel_via_disclose(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        nsf = _place(state, "P0", _get_card(repo, "SEC", "120"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _add_hand(state, "P0", _her(repo))   # carries Command
        assert not has_keyword(state, ally, Keyword.SENTINEL)
        state = _fire_when_played(state, nsf)
        state = _choose_target(state, ally.instance_id)
        assert state.pending_decisions[-1].kind == "disclose"
        state = _settle(state)   # disclose Command → grant_keyword payoff
        assert not state.pending_decisions
        ally = next(c for c in state.player_by_id("P0").ground_arena
                    if c.instance_id == ally.instance_id)
        assert has_keyword(state, ally, Keyword.SENTINEL)

    def test_sec_120_when_defeated_also_offers_disclose(self, repo):
        state = _make_state()
        nsf = _place(state, "P0", _get_card(repo, "SEC", "120"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # another friendly unit
        _add_hand(state, "P0", _her(repo))
        from tests.test_sor_cards import _defeat_and_fire
        state = _defeat_and_fire(state, nsf, "P0")
        # The friendly-unit target is chosen, then the disclose is offered.
        assert state.pending_decisions[-1].kind in ("resolve_effects", "disclose")

    def test_sec_120_no_command_no_disclose(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        nsf = _place(state, "P0", _get_card(repo, "SEC", "120"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _add_hand(state, "P0", _neutral(repo))   # no Command icon
        state = _fire_when_played(state, nsf)
        state = _choose_target(state, ally.instance_id)
        assert not state.pending_decisions   # push_disclose no-ops
        ally = next(c for c in state.player_by_id("P0").ground_arena
                    if c.instance_id == ally.instance_id)
        assert not has_keyword(state, ally, Keyword.SENTINEL)


# ── SEC_127 Charged with Corruption (disclose Command×2 → friendly captures) ────

class TestChargedWithCorruption:
    def test_sec_127_captures_enemy_via_disclose(self, repo):
        state = _make_state()
        captor = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _add_hand(state, "P0", _her(repo))   # Command #1
        _add_hand(state, "P0", _her(repo))   # Command #2
        state, _evt = _play_event_from_hand(state, repo, "SEC", "127")
        state = _choose_target(state, captor.instance_id)
        state = _choose_target(state, victim.instance_id)
        assert state.pending_decisions[-1].kind == "disclose"
        state = _settle(state)   # disclose Command+Command → capture payoff
        assert not state.pending_decisions
        cap = {c.instance_id for c in state.player_by_id("P0").capture_pile}
        assert victim.instance_id in cap

    def test_sec_127_decline_disclose_no_capture(self, repo):
        state = _make_state()
        captor = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _add_hand(state, "P0", _her(repo))
        _add_hand(state, "P0", _her(repo))
        state, _evt = _play_event_from_hand(state, repo, "SEC", "127")
        state = _choose_target(state, captor.instance_id)
        state = _choose_target(state, victim.instance_id)
        state = _settle(state, decline_disclose=True)
        assert not state.pending_decisions
        assert state.player_by_id("P0").capture_pile == []


# ── SEC_208 Hunter (Saboteur + OnAttack: exhausted defender gets −4/−0) ─────────

class TestHunter:
    def test_sec_208_debuffs_exhausted_defender(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        hunter = _place(state, "P0", _get_card(repo, "SEC", "208"), "ground")
        defender = _place(state, "P1", _get_card(repo, "SOR", "39"), "ground")  # 8/8
        defender.exhausted = True
        base = compute_power(state, defender)
        state = _fire_on_attack(state, hunter, defender)
        defender = next(c for c in state.player_by_id("P1").ground_arena
                        if c.instance_id == defender.instance_id)
        assert compute_power(state, defender) == base - 4

    def test_sec_208_ready_defender_unchanged(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        hunter = _place(state, "P0", _get_card(repo, "SEC", "208"), "ground")
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        defender.exhausted = False
        base = compute_power(state, defender)
        state = _fire_on_attack(state, hunter, defender)
        defender = next(c for c in state.player_by_id("P1").ground_arena
                        if c.instance_id == defender.instance_id)
        assert compute_power(state, defender) == base


# ── SEC_248 B2EMO (Restore + OnAttack disclose Heroism×2 → give Sentinel) ───────

class TestB2EMO:
    def test_sec_248_grants_sentinel_via_disclose(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        b2 = _place(state, "P0", _get_card(repo, "SEC", "248"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _add_hand(state, "P0", _her(repo))   # Heroism #1
        _add_hand(state, "P0", _her(repo))   # Heroism #2
        state = _fire_on_attack(state, b2)
        state = _choose_target(state, ally.instance_id)
        assert state.pending_decisions[-1].kind == "disclose"
        state = _settle(state)
        assert not state.pending_decisions
        ally = next(c for c in state.player_by_id("P0").ground_arena
                    if c.instance_id == ally.instance_id)
        assert has_keyword(state, ally, Keyword.SENTINEL)

    def test_sec_248_decline_disclose_no_sentinel(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        b2 = _place(state, "P0", _get_card(repo, "SEC", "248"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _add_hand(state, "P0", _her(repo))
        _add_hand(state, "P0", _her(repo))
        state = _fire_on_attack(state, b2)
        state = _choose_target(state, ally.instance_id)
        state = _settle(state, decline_disclose=True)
        assert not state.pending_decisions
        ally = next(c for c in state.player_by_id("P0").ground_arena
                    if c.instance_id == ally.instance_id)
        assert not has_keyword(state, ally, Keyword.SENTINEL)


# ── SEC_256 Moral Authority (upgrade WhenPlayed: capture a weaker enemy) ────────

class TestMoralAuthority:
    def test_sec_256_captures_enemy_with_less_remaining_hp(self, repo):
        from tests.test_sor_cards import _fire_upgrade_played
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        weak = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _set_remaining_hp(state, host, 7)
        _set_remaining_hp(state, weak, 3)   # < host's 7 → eligible
        upgrade = _attach_upgrade(state, host, _get_card(repo, "SEC", "256"))
        state = _fire_upgrade_played(state, upgrade, host)
        state = _choose_target(state, weak.instance_id)
        assert not state.pending_decisions
        cap = {c.instance_id for c in state.player_by_id("P0").capture_pile}
        assert weak.instance_id in cap

    def test_sec_256_no_capture_when_enemy_not_weaker(self, repo):
        from tests.test_sor_cards import _fire_upgrade_played, _find_instance
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        tough = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _set_remaining_hp(state, host, 3)
        _set_remaining_hp(state, tough, 5)   # ≥ host's 3 → not eligible
        upgrade = _attach_upgrade(state, host, _get_card(repo, "SEC", "256"))
        state = _fire_upgrade_played(state, upgrade, host)
        assert not state.pending_decisions   # mandatory-if-able → fizzles, no prompt
        assert state.player_by_id("P0").capture_pile == []
        assert _find_instance(state, tough.instance_id) is not None


# ── SEC_16 Padmé Amidala (WhenYouRevealOrDiscard observer, both sides) ─────────
# The new reveal-or-discard-from-hand observer: a GameMemory ledger recorded at the
# disclose-reveal / hand-discard chokepoints and drained at the action settle-point
# (mirroring WhenYouUseForce / WhenYouDraw).  These tests drive the observer both
# directly (record_hand_discard + _fire_reveal_discard_observers, the "any route"
# proof used for Yoda LOF_101) and through the two real chokepoints (a live Disclose
# reveal, and a live DiscardFromHand effect via Furtive Handmaiden SEC_197).

class TestPadmeAmidala:
    def _deployed(self, state, repo):
        padme = _place(state, "P0", _get_card(repo, "SEC", "16"), "ground")
        padme.deployed = True   # deployed side lives in the arena
        return padme

    # ---- deployed side: "may deal 1 damage to a unit" (no exhaust cost) ----

    def test_sec_16_deployed_deals_1_on_hand_discard(self, repo):
        from swu.engine.actions import (
            record_hand_discard, _fire_reveal_discard_observers,
            legal_actions, apply, AcceptTrigger, ChooseTarget)
        state = _make_state()
        padme = self._deployed(state, repo)
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        record_hand_discard(state, "P0")
        assert state.game_memory.hand_reveal_discards == ["P0"]
        state = _fire_reveal_discard_observers(state)
        acc = [a for a in legal_actions(state) if isinstance(a, AcceptTrigger)]
        assert acc, "deployed Padmé should offer 'may deal 1 damage'"
        state = apply(state, acc[0])
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 1
        # deployed side has no exhaust cost — Padmé stays ready
        assert not _find_instance(state, padme.instance_id).exhausted

    def test_sec_16_deployed_fires_on_every_discard(self, repo):
        # No exhaust gate on the deployed side: a SECOND discard offers it again.
        from swu.engine.actions import (
            record_hand_discard, _fire_reveal_discard_observers,
            legal_actions, apply, AcceptTrigger, ChooseTarget)
        state = _make_state()
        self._deployed(state, repo)
        enemy = _place(state, "P1", _get_card(repo, "SOR", "39"), "ground")  # 8/8
        for expected in (1, 2):
            record_hand_discard(state, "P0")
            state = _fire_reveal_discard_observers(state)
            acc = [a for a in legal_actions(state) if isinstance(a, AcceptTrigger)]
            assert acc, "deployed Padmé should re-fire on each discard"
            state = apply(state, acc[0])
            state = apply(state, ChooseTarget(enemy.instance_id))
            assert _find_instance(state, enemy.instance_id).damage == expected

    def test_sec_16_deployed_decline_no_damage(self, repo):
        from swu.engine.actions import (
            record_hand_discard, _fire_reveal_discard_observers,
            legal_actions, apply, DeclineTrigger)
        state = _make_state()
        self._deployed(state, repo)
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        record_hand_discard(state, "P0")
        state = _fire_reveal_discard_observers(state)
        dec = [a for a in legal_actions(state) if isinstance(a, DeclineTrigger)]
        assert dec
        state = apply(state, dec[0])
        assert _find_instance(state, enemy.instance_id).damage == 0
        assert not state.pending_decisions

    def test_sec_16_only_own_reveal_discard_fires(self, repo):
        # "When YOU reveal or discard" — an OPPONENT's discard does not fire Padmé.
        from swu.engine.actions import (
            record_hand_discard, _fire_reveal_discard_observers, legal_actions)
        state = _make_state()
        self._deployed(state, repo)
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        record_hand_discard(state, "P1")   # the opponent discarded
        state = _fire_reveal_discard_observers(state)
        assert not state.pending_decisions
        assert not legal_actions(state) or all(
            type(a).__name__ not in ("AcceptTrigger", "DeclineTrigger")
            for a in legal_actions(state))

    # ---- undeployed side: "may exhaust this leader; if you do, deal 1 damage" ----

    def test_sec_16_undeployed_exhausts_and_deals_1(self, repo):
        from swu.engine.actions import (
            record_hand_discard, _fire_reveal_discard_observers,
            legal_actions, apply, AcceptTrigger, ChooseTarget, AutoResolveEffects)
        state = _make_state()
        padme = _place_leader(state, "P0", _get_card(repo, "SEC", "16"))
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        record_hand_discard(state, "P0")
        state = _fire_reveal_discard_observers(state)
        acc = [a for a in legal_actions(state) if isinstance(a, AcceptTrigger)]
        assert acc, "undeployed Padmé should offer 'may exhaust + deal 1'"
        state = apply(state, acc[0])
        state = apply(state, ChooseTarget(enemy.instance_id))
        for _ in range(10):
            auto = [a for a in legal_actions(state)
                    if isinstance(a, AutoResolveEffects)]
            if not auto:
                break
            state = apply(state, auto[0])
        assert _find_instance(state, enemy.instance_id).damage == 1
        # the exhaust-self cost was paid
        assert state.player_by_id("P0").leader_instance.exhausted
        assert not state.pending_decisions

    def test_sec_16_undeployed_not_offered_when_exhausted(self, repo):
        # SOURCE_READY gate: an already-exhausted leader can't pay the exhaust cost,
        # so subsequent reveal/discard events don't offer the ability.
        from swu.engine.actions import (
            record_hand_discard, _fire_reveal_discard_observers,
            legal_actions, AcceptTrigger)
        state = _make_state()
        padme = _place_leader(state, "P0", _get_card(repo, "SEC", "16"))
        padme.exhausted = True
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        record_hand_discard(state, "P0")
        state = _fire_reveal_discard_observers(state)
        assert not state.pending_decisions
        assert not [a for a in legal_actions(state) if isinstance(a, AcceptTrigger)]

    # ---- real chokepoints: a live Disclose reveal, a live DiscardFromHand effect ----

    def test_sec_16_reveal_via_disclose_fires_observer(self, repo):
        # A successful Disclose reveals cards from hand → records the observer, which
        # drains at the settle-point of the DiscloseSelectCard apply and fires Padmé.
        from swu.engine.actions import (
            push_disclose, legal_actions, apply,
            DiscloseSelectCard, AcceptTrigger, ChooseTarget)
        state = _make_state()
        padme = self._deployed(state, repo)
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _add_hand(state, "P0", _her(repo))   # SOR_103 carries Command
        push_disclose(state, padme, ["Command"], payoff="draw",
                      payoff_args={"count": 0})
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, DiscloseSelectCard))
        state = apply(state, pick)   # discloses → reveal recorded → settle fires Padmé
        acc = [a for a in legal_actions(state) if isinstance(a, AcceptTrigger)]
        assert acc, "a Disclose reveal should fire Padmé's observer"
        state = apply(state, acc[0])
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 1

    def test_sec_16_discard_via_effect_fires_observer(self, repo):
        # A live DiscardFromHand effect (Furtive Handmaiden SEC_197 "On Attack:
        # discard a card → draw a card") records the observer through the resolver arm.
        from swu.engine.actions import (
            record_hand_discard, _fire_reveal_discard_observers,  # noqa: F401
            legal_actions, apply, AcceptTrigger, ChooseTarget, AutoResolveEffects)
        state = _make_state()
        self._deployed(state, repo)
        handmaiden = _place(state, "P0", _get_card(repo, "SEC", "197"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _add_hand(state, "P0", _neutral(repo))       # the card to discard
        _push_deck_top(state, "P0", _neutral(repo))  # the card to draw
        state = _fire_on_attack(state, handmaiden)
        # accept Furtive Handmaiden's optional "discard → draw"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)
                                  and a.source_id == handmaiden.instance_id))
        # drive the discard/draw effects to quiescence; the settle-drain then fires
        # Padmé's observer on top of the cleared stack.
        for _ in range(40):
            auto = [a for a in legal_actions(state)
                    if isinstance(a, AutoResolveEffects)]
            if not auto:
                break
            state = apply(state, auto[0])
        acc = [a for a in legal_actions(state) if isinstance(a, AcceptTrigger)]
        assert acc, "a DiscardFromHand effect should fire Padmé's observer"
        state = apply(state, acc[0])
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 1
