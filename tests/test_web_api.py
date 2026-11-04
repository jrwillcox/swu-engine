"""
Backend API tests — drive the game entirely through HTTP.

These exercise the thin-client seam: a full scripted game to a win over the
API (the HTTP-level equivalent of the engine soak), the Phase-4 hidden-info
invariant on the *actual JSON payload* a player receives, image serving, and
clean rejection of an invalid action id.
"""
from __future__ import annotations

import random

import pytest

from tests.dbpath import require_db, require_row

# The web layer is an optional extra (`pip install -e ".[web]"`). Skip the whole
# module cleanly when it isn't installed instead of failing at collection, so the
# fast tier needs no `--ignore` flag on a machine without the web deps.
pytest.importorskip("fastapi", reason="web extra not installed (pip install -e '.[web]')")

from fastapi.testclient import TestClient

from swu.web.app import app

# Mirrors WeightedBot's bias so the scripted human makes forward progress and
# the game terminates rather than passing forever.
_WEIGHTS = {
    "PlayCard": 8, "AttackWithUnit": 6, "DeployLeader": 5, "AttackWithLeader": 4,
    "UseAbility": 4, "AcceptTrigger": 4, "ExploitCommit": 5, "ExploitSacrifice": 4,
    "KeepHand": 3, "ResourceCard": 3, "ClaimInitiative": 2,
}


@pytest.fixture()
def client():
    return TestClient(app)


def _new_game(client, seed=42, human="luke", bot="vader", difficulty=None):
    payload = {
        "human": {"kind": "human", "deck": human},
        "bot": {"kind": "weighted_bot", "deck": bot},
        "seed": seed,
    }
    if difficulty is not None:
        payload["difficulty"] = difficulty
    resp = client.post("/api/games", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _pick(rng, actions):
    weights = [_WEIGHTS.get(a["kind"], 1) for a in actions]
    return rng.choices(actions, weights=weights, k=1)[0]


def test_decks_catalog(client):
    decks = client.get("/api/decks").json()
    keys = {d["key"] for d in decks}
    assert {"luke", "vader"} <= keys


def test_create_game_returns_human_snapshot(client):
    snap = _new_game(client)
    assert snap["player_id"] == "human"
    assert snap["awaiting"] in ("human", "bot")
    assert snap["view"]["viewer_id"] == "human"
    # Human can see their own opening hand.
    assert snap["view"]["my"]["hand_count"] == 6
    assert len(snap["view"]["my"]["hand"]) == 6


def test_hidden_info_redaction_on_payload(client):
    """The opponent's hand/deck/resource identities must never be in the JSON."""
    snap = _new_game(client)
    opp = snap["view"]["opponent"]
    # Opponent hand identities are not present; only a count.
    assert opp["hand"] == []
    assert opp["hand_count"] == 6
    # Opponent resources are redacted stubs (no card identity).
    for r in opp["resources"]:
        assert r["card_id"] == -1
        assert r["card_name"] == "[hidden]"
    # Deck is a count only — no list of card ids anywhere under opponent.
    assert isinstance(opp["deck_count"], int)
    assert "deck" not in opp  # only counts are exposed


def test_invalid_action_id_rejected(client):
    snap = _new_game(client)
    gid = snap["game_id"]
    resp = client.post(f"/api/games/{gid}/actions/does-not-exist")
    assert resp.status_code in (400, 409)


def test_card_image_served(client):
    from tests.dbpath import skip_on_fixture
    skip_on_fixture("serving card art needs a local image build")
    snap = _new_game(client)
    leader = snap["view"]["my"]["base_zone"][0]
    # base_zone holds base + leader; find one with an image url.
    card = next(c for c in snap["view"]["my"]["base_zone"] if c["image_url"])
    resp = client.get(card["image_url"])
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/")
    assert len(resp.content) > 100


def test_variant_image_served_and_falls_back(client):
    """A card's alternate art is served by ?variant=…, falling back to standard."""
    from swu.web.cards import _variant_index

    idx = _variant_index()
    if not idx:
        pytest.skip("no card_variants in this DB (run build_db.py --variants-only)")
    # A card that actually has a downloaded variant.
    card_id, vmap = next(iter(idx.items()))
    vtype = next(iter(vmap))

    resp = client.get(f"/api/cards/{card_id}/image?variant={vtype}")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("image/")
    assert len(resp.content) > 100

    # A variant the card does NOT have falls back to the standard art (still 200).
    missing = next(
        v for v in ("hyperspace", "hyperspace_foil", "showcase") if v not in vmap
    )
    resp = client.get(f"/api/cards/{card_id}/image?variant={missing}")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/")

    # A bogus variant value is rejected by the route validator.
    assert client.get(f"/api/cards/{card_id}/image?variant=bogus").status_code == 422


def test_card_model_exposes_variants():
    """The serializer surfaces available variants with ?variant= image urls."""
    from swu.web.cards import _variant_index
    from swu.web.serializers import _card_variants

    idx = _variant_index()
    if not idx:
        pytest.skip("no card_variants in this DB (run build_db.py --variants-only)")
    card_id, vmap = next(iter(idx.items()))

    variants = _card_variants(card_id)
    assert set(variants.keys()) == set(vmap.keys())
    for vtype, imgs in variants.items():
        # A cache-busting `&v=<mtime>` may be appended (see serializers._card_image_url).
        base = f"/api/cards/{card_id}/image?face=front&variant={vtype}"
        assert imgs.image_url == base or imgs.image_url.startswith(base + "&v=")

    # A card with no variants serialises to an empty dict.
    assert _card_variants(-1) == {}


def test_image_url_has_cache_bust_version():
    """A real card's image url carries `&v=<mtime>` so corrected art isn't stale."""
    from swu.web.cards import _image_index, image_file_for_card
    from swu.web.serializers import _card_image_url

    # A card whose front image actually resolves on disk.
    card_id = next(
        (cid for cid in _image_index() if image_file_for_card(cid, "front") is not None),
        None,
    )
    if card_id is None:
        pytest.skip("no on-disk card images in this DB")
    url = _card_image_url(card_id, "front")
    assert url.startswith(f"/api/cards/{card_id}/image?face=front")
    assert "&v=" in url

    # A redacted (hidden) card id yields no url at all.
    assert _card_image_url(-1, "front") is None


def test_full_game_over_http_reaches_a_winner(client):
    """The API-level soak: play a complete game to termination over HTTP."""
    require_db()  # engine token lookup / from_json needs the card database
    snap = _new_game(client, seed=123)
    gid = snap["game_id"]
    rng = random.Random(7)
    steps = 0
    while snap["awaiting"] != "terminal" and steps < 8000:
        if snap["awaiting"] == "human":
            actions = snap["actions"]
            assert actions, "human turn must offer at least one action"
            choice = _pick(rng, actions)
            resp = client.post(f"/api/games/{gid}/actions/{choice['action_id']}")
            assert resp.status_code == 200, resp.text
            snap = resp.json()
            # Every step returns its event batch (the animation script).
            assert "events" in snap
        else:  # bot's turn
            resp = client.post(f"/api/games/{gid}/advance")
            assert resp.status_code == 200, resp.text
            snap = resp.json()
        steps += 1

    assert snap["awaiting"] == "terminal", f"game did not finish in {steps} steps"
    assert snap["winner"] in ("human", "bot")
    # Terminal state offers no actions.
    assert snap["actions"] == []


# ── Phase 6A: difficulty selection ──────────────────────────────────────────

def _play_to_finish(client, snap, rng_seed=7, cap=8000):
    gid = snap["game_id"]
    rng = random.Random(rng_seed)
    steps = 0
    while snap["awaiting"] != "terminal" and steps < cap:
        if snap["awaiting"] == "human":
            choice = _pick(rng, snap["actions"])
            resp = client.post(f"/api/games/{gid}/actions/{choice['action_id']}")
            assert resp.status_code == 200, resp.text
            snap = resp.json()
        else:
            resp = client.post(f"/api/games/{gid}/advance")
            assert resp.status_code == 200, resp.text
            snap = resp.json()
        steps += 1
    return snap


@pytest.mark.parametrize("difficulty", ["easy", "normal", "hard"])
def test_each_difficulty_yields_playable_game(client, difficulty):
    """Creating a game at each difficulty produces a working opponent and a
    game that can be played to completion over the API."""
    require_db()  # engine token lookup / from_json needs the card database
    snap = _new_game(client, seed=321, difficulty=difficulty)
    assert snap["awaiting"] in ("human", "bot")
    final = _play_to_finish(client, snap)
    assert final["awaiting"] == "terminal"
    assert final["winner"] in ("human", "bot")


def test_difficulty_defaults_to_normal_when_omitted(client):
    """Omitting difficulty is accepted (defaults to Normal) and still playable."""
    snap = _new_game(client, seed=55)  # no difficulty field sent
    assert snap["awaiting"] in ("human", "bot")


def test_unknown_difficulty_falls_back_not_errors(client):
    """A stale/garbage difficulty value must not 500 — it coerces to Normal."""
    snap = _new_game(client, seed=55, difficulty="impossible")
    assert snap["awaiting"] in ("human", "bot")


# ── Auto-resolve the forced "Continue the attack" click ───────────────────────


class _NoopBot:
    """Minimal Player stand-in; never asked to act in these tests."""
    def choose_action(self, view, legal):
        return legal[0]


def _action_state_with_droid():
    """ACTION-phase state where the human (P0) has 2-1B Surgical Droid (optional
    On-Attack heal) and a damaged friendly, attacking an enemy unit."""
    from swu.cards.repository import CardRepository
    from tests.test_golden_scenarios import _make_action_state, _place, _get_card
    repo = CardRepository(require_db())
    droid_def = _get_card(repo, "SOR", "59")
    friendly_def = _get_card(repo, "SOR", "46")
    enemy_def = _get_card(repo, "SOR", "128")
    state = _make_action_state()
    droid_ci = _place(state, "P0", droid_def, "ground")
    friendly_ci = _place(state, "P0", friendly_def, "ground")
    friendly_ci.damage = 5
    enemy_ci = _place(state, "P1", enemy_def, "ground")
    return state, droid_ci, friendly_ci, enemy_ci


def test_continue_attack_is_auto_resolved_for_human():
    """After an On-Attack trigger resolves, the human is never left holding a
    bare 'Continue the attack' (ContinueAttack) decision — the session collapses
    that forced single-option step and resolves combat in place."""
    from swu.web.session import GameSession
    from swu.engine.actions import (
        AttackWithUnit, apply, legal_actions, AcceptTrigger, ChooseTarget,
        ContinueAttack,
    )

    state, droid_ci, friendly_ci, enemy_ci = _action_state_with_droid()
    state = apply(state, AttackWithUnit(droid_ci.instance_id, enemy_ci.instance_id))
    accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
    state = apply(state, accept)

    sess = GameSession(game_id="t", state=state, bot=_NoopBot(),
                       human_id="P0", bot_id="P1")

    # Human chooses the heal target; this resolves the last trigger decision and
    # surfaces the pre_attack bookmark — which the session must auto-resolve.
    actions = dict(sess.human_actions())
    choose_id = next(
        aid for aid, a in actions.items()
        if isinstance(a, ChooseTarget) and a.target_id == friendly_ci.instance_id
    )
    sess.apply_human(choose_id)

    # No pre_attack decision should remain, and the human should not be offered
    # a ContinueAttack anywhere.
    assert not any(d.kind == "pre_attack" for d in sess.state.pending_decisions)
    assert not any(isinstance(a, ContinueAttack) for _, a in sess.human_actions())

    # Combat actually resolved: Stormtrooper (1 hp) defeated by the droid's hit.
    p1_discard = sess.state.players[1].discard
    assert any(ci.instance_id == enemy_ci.instance_id for ci in p1_discard)

    # The auto-applied ContinueAttack is still recorded so replay stays faithful.
    assert sess.action_history[-1]["kind"] == "ContinueAttack"


def test_pointless_decline_granted_attack_is_auto_resolved():
    """Playing Fleet Lieutenant with no unit able to attack must not leave the
    human staring at a lone 'Decline granted attack' button — the session
    collapses that forced no-op decision."""
    from swu.web.session import GameSession
    from swu.engine.actions import PlayCard, DeclineGrantedAttack
    from swu.engine.state import CardInstance, Zone
    from swu.cards.repository import CardRepository
    from tests.test_golden_scenarios import _make_action_state, _give_resources
    import uuid

    repo = CardRepository(require_db())
    with repo._con() as con:
        row = con.execute(
            "SELECT * FROM cards WHERE set_code='SOR' AND card_number='240'"
        ).fetchone()
        fleet_def = repo._hydrate(con, require_row(row, "SOR_240"))

    state = _make_action_state()
    # Fleet Lieutenant costs 3; the dummy base matches no aspect, so the
    # off-aspect penalty inflates the effective cost — give plenty of resources.
    _give_resources(state, "P0", 8)
    fleet_ci = CardInstance(
        instance_id=f"P0_{uuid.uuid4().hex[:6]}", card_def=fleet_def,
        owner_id="P0", zone=Zone.HAND,
    )
    state.player_by_id("P0").hand.append(fleet_ci)

    sess = GameSession(game_id="t", state=state, bot=_NoopBot(),
                       human_id="P0", bot_id="P1")

    play_id = next(
        aid for aid, a in sess.human_actions()
        if isinstance(a, PlayCard) and a.instance_id == fleet_ci.instance_id
    )
    sess.apply_human(play_id)

    # The granted_attack decision must be gone (no friendly unit could attack:
    # Fleet Lieutenant entered exhausted and there were no others).
    assert not any(d.kind == "granted_attack" for d in sess.state.pending_decisions)
    assert not any(
        isinstance(a, DeclineGrantedAttack) for _, a in sess.human_actions()
    )
    assert sess.action_history[-1]["kind"] == "DeclineGrantedAttack"


def test_smuggle_play_label_uses_card_name():
    """A SmugglePlay button must read the smuggled card's name ('Smuggle Cassian
    Andor'), not the raw resource instance id from describe()."""
    from swu.web.session import GameSession
    from swu.engine.actions import SmugglePlay
    from swu.engine.state import CardInstance, Zone
    from swu.cards.repository import CardRepository
    from tests.test_golden_scenarios import _make_action_state, _get_card
    import uuid

    repo = CardRepository(require_db())
    cassian = _get_card(repo, "SHD", "148")  # Cassian Andor — carries Smuggle
    state = _make_action_state()
    res_ci = CardInstance(
        instance_id=f"P0_{uuid.uuid4().hex[:6]}", card_def=cassian,
        owner_id="P0", zone=Zone.RESOURCES, face_down=True,
    )
    state.player_by_id("P0").resources.append(res_ci)

    sess = GameSession(game_id="t", state=state, bot=_NoopBot(),
                       human_id="P0", bot_id="P1")
    label = sess.label_for(SmugglePlay(res_ci.instance_id))
    assert label == f"Smuggle {cassian.display_name}"
    assert res_ci.instance_id not in label


def test_choose_target_label_uses_card_name():
    """A target-picking decision button must read the target card's name, not a
    raw instance id (Wing Leader → 'Give 2 Experience to another Rebel unit')."""
    from swu.web.session import GameSession
    from swu.web.serializers import action_to_model
    from swu.engine.actions import PlayCard, ChooseTarget
    from swu.engine.state import CardInstance, Zone
    from swu.cards.repository import CardRepository
    from tests.test_golden_scenarios import (
        _make_action_state, _give_resources, _get_card, _place,
    )
    import uuid

    repo = CardRepository(require_db())
    with repo._con() as con:
        row = con.execute(
            "SELECT * FROM cards WHERE set_code='SOR' AND card_number='241'"
        ).fetchone()
        wing_def = repo._hydrate(con, require_row(row, "SOR_241"))
    fleet_def = _get_card(repo, "SOR", "240")  # Fleet Lieutenant — a Rebel unit

    state = _make_action_state()
    _give_resources(state, "P0", 12)
    fleet_ci = _place(state, "P0", fleet_def, "ground")  # the eligible target
    wing_ci = CardInstance(
        instance_id=f"P0_{uuid.uuid4().hex[:6]}", card_def=wing_def,
        owner_id="P0", zone=Zone.HAND,
    )
    state.player_by_id("P0").hand.append(wing_ci)

    sess = GameSession(game_id="t", state=state, bot=_NoopBot(),
                       human_id="P0", bot_id="P1")
    play_id = next(
        aid for aid, a in sess.human_actions()
        if isinstance(a, PlayCard) and a.instance_id == wing_ci.instance_id
    )
    sess.apply_human(play_id)

    targets = [(aid, a) for aid, a in sess.human_actions()
               if isinstance(a, ChooseTarget)]
    assert targets, "Wing Leader should offer a ChooseTarget for the Rebel unit"
    labels = [action_to_model(aid, a, sess.label_for(a)).label for aid, a in targets]
    assert any(lbl == "Target Fleet Lieutenant" for lbl in labels), labels
    # And never the raw instance id.
    assert not any(fleet_ci.instance_id in lbl for lbl in labels), labels


def test_no_button_label_shows_a_raw_instance_id(client):
    """Regression: actions without a label_for case fell back to describe(), so
    buttons read "Attack unit bot_60 with human_0" and "Play human_26"."""
    import re
    raw_id = re.compile(r"\b(?:human|bot|ci)_\d+\b")
    snap = _new_game(client, seed=8)
    gid = snap["game_id"]
    rng = random.Random(8)
    seen = set()
    for _ in range(400):
        if snap["winner"] or snap["awaiting"] == "terminal":
            break
        if snap["awaiting"] == "bot":
            snap = client.post(f"/api/games/{gid}/advance").json()
            continue
        for a in snap["actions"]:
            assert not raw_id.search(a["label"]), a
            seen.add(a["kind"])
        snap = client.post(f"/api/games/{gid}/actions/{_pick(rng, snap['actions'])['action_id']}").json()
    assert {"PlayCard", "AttackWithUnit", "ResourceCard"} <= seen, seen


def test_deployed_leader_prompt_quotes_its_unit_side():
    """Regression: a deployed leader's optional-ability prompt quoted its leader
    side (``text``) instead of its unit side (``deploy_box``)."""
    from swu.web.session import GameSession
    from swu.engine.actions import AttackWithUnit
    from swu.cards.repository import CardRepository
    from tests.test_golden_scenarios import _make_action_state, _get_card, _place

    repo = CardRepository(require_db())
    state = _make_action_state()
    luke = _place(state, "P0", _get_card(repo, "SOR", "5"), "ground")
    luke.deployed = True
    _place(state, "P0", _get_card(repo, "SOR", "240"), "ground")  # a Shield target
    sess = GameSession(game_id="t", state=state, bot=_NoopBot(),
                       human_id="P0", bot_id="P1")
    attack = next(aid for aid, a in sess.human_actions()
                  if isinstance(a, AttackWithUnit) and a.attacker_id == luke.instance_id)
    sess.apply_human(attack)

    prompt = sess.prompt() or ""
    assert "On Attack: You may give another unit a Shield token" in prompt, prompt
    assert "Action [" not in prompt, prompt


def test_force_and_pilot_labels_name_the_cards():
    """The Force cost choice read "Use force option exhaust_friendly" for every
    unit, and a pilot play read "PilotPlay <pilot> on <vehicle>"."""
    from swu.web.session import GameSession
    from swu.engine.actions import PilotPlay, UseForceOption
    from swu.cards.repository import CardRepository
    from tests.test_golden_scenarios import _make_action_state, _get_card, _place

    repo = CardRepository(require_db())
    state = _make_action_state()
    unit = _place(state, "P0", _get_card(repo, "SOR", "240"), "ground")
    other = _place(state, "P0", _get_card(repo, "SHD", "148"), "ground")
    sess = GameSession(game_id="t", state=state, bot=_NoopBot(),
                       human_id="P0", bot_id="P1")
    a, b = unit.card_def.display_name, other.card_def.display_name
    assert sess.label_for(UseForceOption("force")) == "Use the Force (spend your Force token)"
    assert sess.label_for(UseForceOption("exhaust_friendly", unit.instance_id)) == \
        f"Exhaust {a} to use the Force"
    assert sess.label_for(PilotPlay(unit.instance_id, other.instance_id)) == f"Pilot {a} onto {b}"


def test_label_does_not_name_an_opponents_hidden_card():
    """The name lookup must not reveal a face-down enemy resource."""
    from swu.web.session import GameSession
    from swu.engine.actions import SacrificeResource
    from swu.engine.state import CardInstance, Zone
    from swu.cards.repository import CardRepository
    from tests.test_golden_scenarios import _make_action_state, _get_card

    cassian = _get_card(CardRepository(require_db()), "SHD", "148")
    state = _make_action_state()
    for pid in ("P0", "P1"):
        state.player_by_id(pid).resources.append(CardInstance(
            instance_id=f"{pid}_7", card_def=cassian, owner_id=pid,
            zone=Zone.RESOURCES, face_down=True,
        ))
    sess = GameSession(game_id="t", state=state, bot=_NoopBot(),
                       human_id="P0", bot_id="P1")
    assert sess.label_for(SacrificeResource("P0_7")) == f"Defeat resource {cassian.display_name}"
    assert sess.label_for(SacrificeResource("P1_7")) == "Defeat resource P1_7"
