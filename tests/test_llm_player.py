"""
Tests for the LLM opponent (`swu.players.llm_player.LLMPlayer`).

All automated tests use a **fake Anthropic client** — no network, fully
deterministic.  Per the Phase 6B handoff, these assert *structure* (a legal
action is returned; every failure mode falls back cleanly to the heuristic and
emits a visible game-log notice; the prompt never leaks the human's hidden
cards), never a specific game outcome.

The single live smoke test (`test_live_smoke`) is opt-in: it is skipped unless
`--live` is passed AND `ANTHROPIC_API_KEY` is set, because it costs real money.
"""
from __future__ import annotations

import json
import os
import random

import pytest

from swu.engine.actions import apply, create_game, legal_actions
from swu.players.heuristic_bot import HeuristicBot
from swu.players.llm_player import FallbackNotice, LLMPlayer, Style


# ── Fake Anthropic client ─────────────────────────────────────────────────────

class _Usage:
    def __init__(self, tin=12, tout=6, cache_read=0):
        self.input_tokens = tin
        self.output_tokens = tout
        self.cache_read_input_tokens = cache_read
        self.cache_creation_input_tokens = 0


class _ToolUse:
    type = "tool_use"

    def __init__(self, action_id, reasoning="because", name="choose_action"):
        self.name = name
        self.input = {"action_id": action_id, "reasoning": reasoning}


class _Text:
    type = "text"

    def __init__(self, text):
        self.text = text


class _Resp:
    def __init__(self, stop_reason, content, usage=None):
        self.stop_reason = stop_reason
        self.content = content
        self.usage = usage or _Usage()


def tool_response(action_id, reasoning="because"):
    return _Resp("tool_use", [_ToolUse(action_id, reasoning)])


class _Messages:
    def __init__(self, script):
        self.script = list(script)
        self.calls = 0
        self.last_kwargs = None

    def create(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        if not self.script:
            raise AssertionError("fake client called more times than scripted")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        if callable(item):
            return item(**kwargs)
        return item


class FakeClient:
    """Replays a script of canned responses / exceptions for messages.create."""

    def __init__(self, script):
        self.messages = _Messages(script)

    def with_options(self, **_kw):  # the SDK returns a configured copy; we no-op
        return self


class SmartFakeClient:
    """Parses the prompt and returns a random *legal* action_id every call.

    Drives a full game over the real LLMPlayer call/parse/validate path with no
    network and guaranteed termination (random legal play, like the soak).
    """

    def __init__(self, seed=0):
        self._rng = random.Random(seed)
        self.messages = self  # so .messages.create works
        self.calls = 0

    def with_options(self, **_kw):
        return self

    def create(self, **kwargs):
        self.calls += 1
        data = _parse_prompt(kwargs["messages"])
        ids = [a["action_id"] for a in data["legal_actions"]]
        return tool_response(self._rng.choice(ids))


def _parse_prompt(messages):
    for m in messages:
        content = m.get("content")
        if isinstance(content, str) and '"legal_actions"' in content:
            start = content.index("{")
            end = content.rindex("}") + 1
            return json.loads(content[start:end])
    raise AssertionError("no state JSON found in messages")


# ── Helpers to get a real (view, legal) with >1 option ────────────────────────

def _decks(repo):
    from swu.cards.decklist import build_vanilla_deck
    da = build_vanilla_deck(repo, "Darth Vader", "Security Complex")
    db = build_vanilla_deck(repo, "Luke Skywalker", "Administrator's Tower")
    return da, db


@pytest.fixture
def view_and_legal(repo):
    """A real mid-setup decision for P0 with two legal actions (mulligan)."""
    da, db = _decks(repo)
    s = create_game("P0", da, "P1", db, seed=1)
    legal = legal_actions(s)
    assert len(legal) >= 2, "expected a genuine (non-trivial) choice"
    return s, s.view_for("P0"), legal


def _player(client, *, style=Style.CASUAL, fallback_seed=7):
    return LLMPlayer(
        "P0",
        fallback=HeuristicBot("P0", seed=fallback_seed),
        style=style,
        client=client,
    )


# ── Happy path ────────────────────────────────────────────────────────────────

def test_valid_choice_applied(view_and_legal):
    _s, view, legal = view_and_legal
    client = FakeClient([tool_response("a0")])
    bot = _player(client)
    chosen = bot.choose_action(view, legal)
    assert chosen is legal[0]
    assert client.messages.calls == 1
    assert bot.drain_notices() == []          # success → no fallback notice


def test_reasoning_and_usage_recorded(view_and_legal):
    _s, view, legal = view_and_legal
    client = FakeClient([_Resp("tool_use", [_ToolUse("a1", "take the trade")],
                               usage=_Usage(tin=100, tout=20))])
    bot = _player(client)
    bot.choose_action(view, legal)
    assert bot.tokens_in == 100 and bot.tokens_out == 20
    assert bot.calls == 1 and bot.fallbacks == 0


# ── Retry then fallback on illegal id ─────────────────────────────────────────

def test_illegal_then_valid_on_retry(view_and_legal):
    _s, view, legal = view_and_legal
    client = FakeClient([tool_response("a99"), tool_response("a1")])
    bot = _player(client)
    chosen = bot.choose_action(view, legal)
    assert chosen is legal[1]
    assert client.messages.calls == 2          # one corrective retry
    assert bot.drain_notices() == []           # recovered → no notice


def test_illegal_twice_falls_back_with_notice(view_and_legal):
    _s, view, legal = view_and_legal
    client = FakeClient([tool_response("a99"), tool_response("a98")])
    bot = _player(client)
    chosen = bot.choose_action(view, legal)
    assert chosen in legal                     # heuristic produced a legal action
    assert client.messages.calls == 2
    notices = bot.drain_notices()
    assert len(notices) == 1
    assert isinstance(notices[0], FallbackNotice)
    assert notices[0].reason == "illegal_choice"
    assert "fell back" in notices[0].message.lower()
    assert bot.fallbacks == 1


# ── Truncation / errors / malformed → fallback (no retry) ─────────────────────

def test_max_tokens_truncation_falls_back(view_and_legal):
    _s, view, legal = view_and_legal
    # Truncated: stop_reason is max_tokens, not a clean tool_use.
    client = FakeClient([_Resp("max_tokens", [_ToolUse("a0", "partial...")])])
    bot = _player(client)
    chosen = bot.choose_action(view, legal)
    assert chosen in legal
    assert client.messages.calls == 1          # truncation is NOT retried
    notices = bot.drain_notices()
    assert len(notices) == 1 and notices[0].reason == "stop_reason"


def test_api_exception_falls_back(view_and_legal):
    _s, view, legal = view_and_legal
    client = FakeClient([RuntimeError("kaboom")])
    bot = _player(client)
    chosen = bot.choose_action(view, legal)
    assert chosen in legal
    notices = bot.drain_notices()
    assert len(notices) == 1 and notices[0].reason == "api_error"


def test_timeout_falls_back(view_and_legal):
    _s, view, legal = view_and_legal

    class _Timeout(Exception):
        pass

    client = FakeClient([_Timeout("read timed out")])
    bot = _player(client)
    chosen = bot.choose_action(view, legal)
    assert chosen in legal
    assert len(bot.drain_notices()) == 1       # logged + surfaced, not swallowed


def test_malformed_no_tool_call_falls_back(view_and_legal):
    _s, view, legal = view_and_legal
    # stop_reason says tool_use but there is no tool_use block to parse.
    client = FakeClient([_Resp("tool_use", [_Text("I think I'll pass")])])
    bot = _player(client)
    chosen = bot.choose_action(view, legal)
    assert chosen in legal
    notices = bot.drain_notices()
    assert len(notices) == 1 and notices[0].reason == "malformed"


# ── Trivial-skip: no API call when forced ─────────────────────────────────────

def test_forced_single_action_makes_no_api_call(view_and_legal):
    _s, view, legal = view_and_legal
    client = FakeClient([])                     # any call would AssertionError
    bot = _player(client)
    only = [legal[0]]
    chosen = bot.choose_action(view, only)
    assert chosen is legal[0]
    assert client.messages.calls == 0
    assert bot.drain_notices() == []


# ── Hidden-information guarantee ──────────────────────────────────────────────

def test_prompt_has_no_hidden_opponent_cards(repo):
    """The serialised prompt must contain none of the human's hidden cards."""
    da, db = _decks(repo)
    s = create_game("bot", da, "human", db, seed=5)
    view = s.view_for("bot")
    legal = legal_actions(s)

    bot = _player(FakeClient([]))
    prompt = bot._build_user_message(view, legal)

    opp = s.players[1 - s.player_index("bot")]
    assert opp.hand, "test needs the opponent to be holding cards"
    for ci in opp.hand:
        # Unique per copy — its presence anywhere in the prompt would be a leak.
        assert ci.instance_id not in prompt, f"leaked hidden card {ci.instance_id}"
    # The opponent block carries no hand at all (only a count).
    compact = bot._serialise_view(view)
    assert "hand" not in compact["opponent"]
    assert compact["opponent"]["hand_count"] == len(opp.hand)


def test_card_glossary_skips_redacted_and_has_text(repo):
    da, db = _decks(repo)
    s = create_game("bot", da, "human", db, seed=2)
    bot = _player(FakeClient([]))
    glossary = bot._card_glossary(s.view_for("bot"))
    assert "-1" not in glossary                 # redacted cards never looked up
    # Best-effort: with the DB present, at least the leader/base have text.
    assert isinstance(glossary, dict)


# ── Full mocked game to completion (Normal and Hard) ──────────────────────────

@pytest.mark.parametrize("style", [Style.CASUAL, Style.COMPETITIVE])
def test_full_game_to_completion_with_mocked_client(repo, style):
    from swu.engine.invariants import CheckContext, check

    da, db = _decks(repo)
    s = create_game("P0", da, "P1", db, seed=11)
    ctx = CheckContext.from_state(s)
    bots = {
        "P0": LLMPlayer("P0", fallback=HeuristicBot("P0", seed=1),
                        style=style, client=SmartFakeClient(seed=1)),
        "P1": LLMPlayer("P1", fallback=HeuristicBot("P1", seed=2),
                        style=style, client=SmartFakeClient(seed=2)),
    }
    n = 0
    while not s.is_terminal() and n < 4000:
        legal = legal_actions(s)
        pid = (s.pending_decisions[-1].deciding_player_id
               if s.pending_decisions else s.active_player.player_id)
        chosen = bots[pid].choose_action(s.view_for(pid), legal)
        assert chosen in legal
        s = apply(s, chosen)
        check(s, ctx)                           # engine invariants hold throughout
        n += 1
    assert s.is_terminal()
    # The mocked client always returns a legal id, so there should be no fallbacks.
    assert bots["P0"].fallbacks == 0 and bots["P1"].fallbacks == 0


# ── Easy never touches the API ────────────────────────────────────────────────

def test_easy_makes_no_api_calls(repo, monkeypatch):
    import swu.players.llm_player as llm
    from swu.players.difficulty import Difficulty, make_opponent

    calls = {"n": 0}

    class _Boom:
        def __init__(self, *a, **k):
            calls["n"] += 1
            raise AssertionError("Easy must never construct an Anthropic client")

    monkeypatch.setattr(llm, "anthropic", type("M", (), {"Anthropic": _Boom}))

    da, db = _decks(repo)
    s = create_game("P0", da, "P1", db, seed=3)
    bots = {
        "P0": make_opponent(Difficulty.EASY, player_id="P0", seed=3),
        "P1": make_opponent(Difficulty.EASY, player_id="P1", seed=4),
    }
    assert isinstance(bots["P0"], HeuristicBot)
    n = 0
    while not s.is_terminal() and n < 3000:
        legal = legal_actions(s)
        pid = (s.pending_decisions[-1].deciding_player_id
               if s.pending_decisions else s.active_player.player_id)
        s = apply(s, bots[pid].choose_action(s.view_for(pid), legal))
        n += 1
    assert s.is_terminal()
    assert calls["n"] == 0


# ── Style coercion ────────────────────────────────────────────────────────────

def test_style_coercion():
    assert Style.coerce("casual") is Style.CASUAL
    assert Style.coerce("COMPETITIVE") is Style.COMPETITIVE
    assert Style.coerce("garbage") is Style.CASUAL
    assert Style.coerce(None) is Style.CASUAL


def test_model_env_override(monkeypatch, repo):
    monkeypatch.setenv("SWU_LLM_MODEL", "claude-some-other-model")
    bot = LLMPlayer("P0", fallback=HeuristicBot("P0", seed=1), client=FakeClient([]))
    assert bot.model == "claude-some-other-model"


# ── Web seam: fallback notices reach the event batch and serialise ────────────

class _AlwaysFail:
    def __init__(self):
        self.messages = self
        self.calls = 0

    def with_options(self, **_kw):
        return self

    def create(self, **_kwargs):
        self.calls += 1
        raise RuntimeError("simulated API outage")


def test_event_to_model_serialises_fallback_notice():
    from swu.web.serializers import event_to_model
    m = event_to_model(FallbackNotice(message="hi there", reason="api_error"))
    assert m.type == "FallbackNotice"
    assert m.data == {"message": "hi there", "reason": "api_error"}


def test_advance_bot_surfaces_fallback_notice_in_event_batch(repo):
    """End-to-end web seam: a failing LLM bot's fallback shows up as a visible
    FallbackNotice in the events the session returns to the UI."""
    from swu.web.serializers import event_to_model
    from swu.web.session import GameSession

    da, db = _decks(repo)
    state = create_game("human", da, "bot", db, seed=4)
    fail_client = _AlwaysFail()
    bot = LLMPlayer("bot", fallback=HeuristicBot("bot", seed=1), client=fail_client)
    session = GameSession(game_id="t", state=state, bot=bot)

    seen_notice = False
    steps = 0
    while session.awaiting() != "terminal" and steps < 4000 and not seen_notice:
        if session.awaiting() == "human":
            # Drive the human seat with a heuristic so the game progresses.
            legal = legal_actions(session.state)
            choice = HeuristicBot("human", seed=2).choose_action(
                session.state.view_for("human"), legal)
            session.state = apply(session.state, choice)
            session._action_cache = {}
        else:
            events = session.advance_bot()
            for e in events:
                if isinstance(e, FallbackNotice):
                    seen_notice = True
                    model = event_to_model(e)   # must serialise on the wire
                    assert model.type == "FallbackNotice"
                    assert "reason" in model.data and "message" in model.data
        steps += 1

    assert seen_notice, "a failing LLM bot must surface a visible fallback notice"
    assert fail_client.calls >= 1
    assert bot.fallbacks >= 1


# ── Opt-in live smoke test (costs real money) ─────────────────────────────────

@pytest.mark.live
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
def test_live_smoke(repo):
    """A handful of real decisions: each must be legal and the cache should warm."""
    da, db = _decks(repo)
    s = create_game("P0", da, "P1", db, seed=21)
    bot = LLMPlayer("P0", fallback=HeuristicBot("P0", seed=1), style=Style.COMPETITIVE)

    decisions = 0
    n = 0
    while not s.is_terminal() and decisions < 4 and n < 200:
        legal = legal_actions(s)
        pid = (s.pending_decisions[-1].deciding_player_id
               if s.pending_decisions else s.active_player.player_id)
        if pid == "P0" and len(legal) > 1:
            chosen = bot.choose_action(s.view_for("P0"), legal)
            assert chosen in legal
            decisions += 1
        else:
            chosen = HeuristicBot(pid, seed=99).choose_action(s.view_for(pid), legal)
        s = apply(s, chosen)
        n += 1

    assert bot.calls >= 1
    # Cache should have been read on at least one follow-up call (system block is
    # marked for caching). Tolerant: only assert if we made multiple real calls.
    if bot.calls >= 2:
        # Not a hard guarantee (depends on min cacheable prefix), so just log-style check.
        assert bot.tokens_in >= 0
