"""
LLM-backed opponent (Phase 6B).

``LLMPlayer`` satisfies the same ``Player`` protocol as ``HeuristicBot``
(`choose_action(view, legal) -> Action`) but delegates the *strategic* choice to
a small Claude model via the Anthropic API.  It is wired in behind the bot
factory (`swu.players.difficulty.make_opponent`) for the **Normal** (casual) and
**Hard** (competitive) difficulties; **Easy stays a pure heuristic and never
constructs this class**.

Design principles (from the project owner):

1.  **No silent failures.**  Every way the model call can go wrong — API error,
    timeout, ``max_tokens``/truncation, a malformed/parse-less response, or an
    ``action_id`` that is not legal even after one corrective retry — is caught,
    logged with detail to ``data/llm.log``, and surfaced as a *visible* entry in
    the in-game event log (the heuristic quietly takes over for that one
    decision).  We never let a truncated response masquerade as a clean answer.
2.  **Cost & latency matter.**  We default to the smallest fast model
    (``claude-haiku-4-5``), skip the API entirely for forced/trivial choices,
    force a single ``choose_action`` tool call (bounded output), and mark the
    static rules brief for prompt caching so it is not re-billed every turn.

The model only ever sees *this* player's redacted ``PlayerView`` (built by the
engine's ``build_view``) — never the raw ``GameState`` and never the opponent's
hand or deck order.  See ``_serialise_view`` and the hidden-info test.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from enum import Enum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

try:  # The SDK is a hard dep for Normal/Hard, but the game must survive its absence.
    import anthropic
except ImportError:  # pragma: no cover - exercised only when the SDK is missing
    anthropic = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from swu.engine.actions import Action
    from swu.engine.views import PlayerView


# ── Config (constructor- and env-overridable so the model can change per
#    difficulty without code edits) ─────────────────────────────────────────────

# Confirmed against the official Claude API reference (smallest/fastest tier):
#   claude-haiku-4-5 — $1.00 / 1M input, $5.00 / 1M output, 200K context.
DEFAULT_MODEL = "claude-haiku-4-5"
_MODEL_ENV = "SWU_LLM_MODEL"          # global override for the model id
_TIMEOUT_ENV = "SWU_LLM_TIMEOUT"      # per-call timeout in seconds

DEFAULT_TIMEOUT_S = 20.0
# Enough for one short reasoning sentence + the tool call; anything that needs
# more is treated as truncation (stop_reason != "tool_use") and falls back.
DEFAULT_MAX_TOKENS = 256

# Approximate Haiku-tier pricing ($/token) for the optional end-of-game cost line.
_PRICE_IN = 1.00 / 1_000_000
_PRICE_OUT = 5.00 / 1_000_000


class Style(str, Enum):
    """How hard the model should try.  ``str`` mixin so ``"casual"`` coerces."""

    CASUAL = "casual"          # Normal — play reasonably, occasionally suboptimally
    COMPETITIVE = "competitive"  # Hard — play to win: tempo, board, lethal

    @classmethod
    def coerce(cls, value: "Style | str | None") -> "Style":
        if isinstance(value, cls):
            return value
        if value is None:
            return cls.CASUAL
        try:
            return cls(str(value).strip().lower())
        except ValueError:
            return cls.CASUAL


# ── In-game log notice (the web seam) ─────────────────────────────────────────

@dataclass(frozen=True)
class FallbackNotice:
    """A user-visible event the web layer drains from the player after a turn.

    It is *not* an engine event — the engine never emits it — but it serialises
    through ``event_to_model`` like any dataclass (``type="FallbackNotice"``),
    and the frontend log renders ``message``.  This is how a silent heuristic
    takeover becomes a *visible* "Opponent fell back …" line, per the owner's
    no-silent-failures rule.
    """

    message: str   # human-readable, shown in the in-game log
    reason: str    # short reason code (max_tokens, api_error, illegal_choice, …)


# ── Logger (rotating file at data/llm.log) ────────────────────────────────────

def _data_dir() -> Path:
    # .../swu-game/src/swu/players/llm_player.py -> parents[3] == .../swu-game
    return Path(__file__).resolve().parents[3] / "data"


def _build_logger() -> logging.Logger:
    log = logging.getLogger("swu.llm")
    log.setLevel(logging.DEBUG)
    log.propagate = False
    if not any(isinstance(h, RotatingFileHandler) for h in log.handlers):
        try:
            path = _data_dir() / "llm.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(
                path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
            )
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            )
            log.addHandler(handler)
        except OSError:  # pragma: no cover - never let logging setup break play
            log.addHandler(logging.NullHandler())
    return log


_LOG = _build_logger()


# ── Internal failure signals ──────────────────────────────────────────────────

class _LLMUnavailable(Exception):
    """Configuration-level: SDK missing or no API key — not a per-call failure.

    Surfaced once (not per decision) so a game run with no key configured does
    not spam the in-game log; it just plays at heuristic strength.
    """


class _LLMFailure(Exception):
    """A per-call failure (API error, truncation, parse, illegal choice).

    Each occurrence is logged *and* surfaced in the in-game log as a fallback.
    """


# ── Tool definition (forced single call) ──────────────────────────────────────

_CHOOSE_ACTION_TOOL = {
    "name": "choose_action",
    "description": (
        "Commit to exactly one legal action for the current decision, naming it "
        "by its action_id from the provided list."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action_id": {
                "type": "string",
                "description": "The chosen action's id. MUST be one of the listed action_ids.",
            },
            "reasoning": {
                "type": "string",
                "description": "One short sentence (keep it brief) explaining the choice.",
            },
        },
        "required": ["action_id", "reasoning"],
        "additionalProperties": False,
    },
}

_RULES_BRIEF = """\
You are playing Star Wars: Unlimited, a two-player card game, as the opponent of \
a human. You control the seat whose view is given to you.

OBJECTIVE: Reduce the ENEMY base to 0 remaining HP to win. If YOUR base reaches \
0 you lose. A unit's remaining HP = effective_hp - damage; the same holds for a \
base's entry in base_zone.

CORE RULES (brief):
- Each turn you take ONE action, then the turn passes. Plan one action at a time.
- Play units/upgrades/events from hand by paying their cost from available_resources.
- Units attack enemy units or the enemy base; attacking exhausts the attacker. \
Combat deals simultaneous damage equal to attacker/defender power.
- "Sentinel" enemy units must be attacked before the base. Keywords (Raid, Overwhelm, \
Ambush, Restore, Shielded, Grit, Sentinel, Saboteur, Exploit, …) modify combat — the \
card glossary explains the relevant ones.
- Deploy your leader once its resource threshold is met to get a premium body + ability.
- Pass when you have nothing worthwhile to do; the round ends when both players pass.

HOW TO READ THE STATE (JSON in the user message):
- `my` is YOU: full hand, board (ground_arena/space_arena), base_zone, resources.
- `opponent` is the HUMAN: only public info — board, base, discard, and COUNTS for \
their hidden hand/deck. You never see their hand.
- `legal_actions` is the numbered list of the ONLY moves allowed right now. Each has \
an `action_id`, a human `label`, and `params`. You MUST pick one of these action_ids.
- `card_glossary` gives rules text for cards currently relevant (in play / in hand).
- `event_log_tail` is recent history (most recent last).

Call the `choose_action` tool exactly once with one legal `action_id` and a one-sentence reason."""

_STYLE_BRIEF = {
    Style.CASUAL: """\
STYLE: Play like a reasonable, friendly casual player — develop your board, take \
sensible attacks, and go for the win when it is clearly there, but you do NOT have \
to find the optimal line. The occasional suboptimal trade is fine; you are meant to \
be beatable and not play like a tournament grinder.""",
    Style.COMPETITIVE: """\
STYLE: Play to win. Value tempo, board presence, and favourable trades; recognise \
and take lethal on the enemy base; remove the biggest threats; make the strongest \
legal play available each decision.""",
}


def _system_prompt(style: Style) -> str:
    return f"{_RULES_BRIEF}\n\n{_STYLE_BRIEF[style]}"


# ── DB card-text lookup (best effort) ─────────────────────────────────────────

def _resolve_db_path() -> Optional[Path]:
    env = os.environ.get("SWU_DB")
    candidates = []
    if env:
        candidates.append(Path(env))
    candidates.append(_data_dir() / "swu.db")
    for c in candidates:
        if c.exists():
            return c
    return None


class LLMPlayer:
    """An opponent whose strategic decisions come from a small Claude model.

    Constructed by the bot factory as
    ``LLMPlayer(player_id, fallback=<HeuristicBot>, style=Style.CASUAL|COMPETITIVE)``.
    Falls back to ``fallback`` (a never-raising heuristic) on any failure.
    """

    def __init__(
        self,
        player_id: str,
        *,
        fallback: "Any",
        style: "Style | str" = Style.CASUAL,
        model: Optional[str] = None,
        client: "Any" = None,
        timeout: Optional[float] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self.player_id = player_id
        self.fallback = fallback
        self.style = Style.coerce(style)
        self.model = model or os.environ.get(_MODEL_ENV) or DEFAULT_MODEL
        self.max_tokens = max_tokens
        self.timeout = timeout if timeout is not None else _env_timeout()

        self._injected_client = client      # tests pass a fake here
        self._client: Any = client
        self._client_ready = client is not None
        self._unavailable_reason: Optional[str] = None
        self._announced_unavailable = False

        self._system = _system_prompt(self.style)
        self._notices: list[FallbackNotice] = []

        # Card-text lookup cache (per game instance).
        self._db_path = _resolve_db_path()
        self._card_text_cache: dict[int, str] = {}

        # Lightweight per-game usage counter (optional cost visibility).
        self.calls = 0
        self.fallbacks = 0
        self.tokens_in = 0
        self.tokens_out = 0

    # ── Player protocol ────────────────────────────────────────────────────

    def choose_action(self, view: "PlayerView", legal: list["Action"]) -> "Action":
        if not legal:  # defensive; the engine never offers an empty list while live
            return self.fallback.choose_action(view, legal)

        # 1) Skip the model for forced/trivial choices — a major cost/latency win.
        if len(legal) == 1:
            _LOG.debug("auto: single legal action (%s)", _describe(legal[0]))
            return legal[0]

        id_to_index = {f"a{i}": i for i in range(len(legal))}

        try:
            client = self._ensure_client()
            user_msg = self._build_user_message(view, legal)
            idx, reasoning, meta = self._ask_with_retry(client, user_msg, id_to_index, legal)
        except _LLMUnavailable as e:
            return self._handle_unavailable(view, legal, str(e))
        except _LLMFailure as e:
            return self._handle_failure(view, legal, str(e))
        except Exception as e:  # pragma: no cover - last-resort safety net
            return self._handle_failure(view, legal, f"unexpected:{type(e).__name__}:{e}")

        chosen = legal[idx]
        _LOG.info(
            "success model=%s style=%s %s latency=%.2fs in=%s out=%s cache_read=%s reason=%r",
            self.model, self.style.value, meta.get("attempt_note", ""),
            meta.get("latency", 0.0), meta.get("in", 0), meta.get("out", 0),
            meta.get("cache_read", 0), reasoning,
        )
        return chosen

    def observe(self, state: object, action: object, actor_id: str) -> None:
        pass

    # ── Web seam: the session drains these after each turn ──────────────────

    def drain_notices(self) -> list[FallbackNotice]:
        out = self._notices
        self._notices = []
        return out

    def usage_summary(self) -> str:
        cost = self.tokens_in * _PRICE_IN + self.tokens_out * _PRICE_OUT
        return (
            f"calls={self.calls} fallbacks={self.fallbacks} "
            f"tokens_in={self.tokens_in} tokens_out={self.tokens_out} est_cost=${cost:.4f}"
        )

    # ── Model call (+ one corrective retry) ─────────────────────────────────

    def _ask_with_retry(self, client, user_msg, id_to_index, legal):
        attempt_messages = [{"role": "user", "content": user_msg}]
        for attempt in (1, 2):
            action_id, reasoning, meta = self._ask_once(client, attempt_messages)
            if action_id in id_to_index:
                meta["attempt_note"] = f"attempt={attempt}"
                return id_to_index[action_id], reasoning, meta
            # Illegal/missing id — retry once with a corrective note, else fail.
            if attempt == 1:
                _LOG.warning(
                    "retry: model returned illegal action_id=%r (legal: %s)",
                    action_id, ",".join(id_to_index),
                )
                legal_ids = ", ".join(id_to_index)
                attempt_messages = attempt_messages + [
                    {"role": "assistant", "content": [
                        {"type": "text", "text": f"(chose {action_id!r})"}]},
                    {"role": "user", "content": (
                        f"That action_id was not in the legal list. Choose exactly "
                        f"one of: {legal_ids}. Call choose_action again."
                    )},
                ]
        raise _LLMFailure(f"illegal_choice: model never named a legal action_id ({action_id!r})")

    def _ask_once(self, client, messages):
        """One API call; returns (action_id, reasoning, meta) or raises _LLMFailure."""
        start = time.monotonic()
        try:
            resp = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=[{
                    "type": "text",
                    "text": self._system,
                    "cache_control": {"type": "ephemeral"},  # cache the static brief
                }],
                tools=[_CHOOSE_ACTION_TOOL],
                tool_choice={"type": "tool", "name": "choose_action"},
                messages=messages,
            )
        except Exception as e:
            raise _LLMFailure(f"api_error:{type(e).__name__}:{e}") from e
        latency = time.monotonic() - start
        self.calls += 1

        usage = getattr(resp, "usage", None)
        tin = int(getattr(usage, "input_tokens", 0) or 0)
        tout = int(getattr(usage, "output_tokens", 0) or 0)
        cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        self.tokens_in += tin
        self.tokens_out += tout

        stop_reason = getattr(resp, "stop_reason", None)
        meta = {"latency": latency, "in": tin, "out": tout, "cache_read": cache_read}
        if stop_reason != "tool_use":
            # max_tokens (truncation), refusal, end_turn with no tool call, etc.
            raw = _safe_repr(getattr(resp, "content", None))
            _LOG.error(
                "fallback-trigger stop_reason=%r (not a clean tool_use); raw=%s",
                stop_reason, raw,
            )
            raise _LLMFailure(f"stop_reason:{stop_reason}")

        action_id, reasoning = _extract_tool_call(resp)
        if action_id is None:
            raw = _safe_repr(getattr(resp, "content", None))
            _LOG.error("fallback-trigger malformed tool_use; raw=%s", raw)
            raise _LLMFailure("malformed: no choose_action tool call in response")
        return action_id, reasoning, meta

    # ── Client lifecycle ────────────────────────────────────────────────────

    def _ensure_client(self):
        if self._client_ready:
            return self._client
        if self._unavailable_reason is not None:
            raise _LLMUnavailable(self._unavailable_reason)
        if anthropic is None:
            self._unavailable_reason = "anthropic SDK not installed"
            raise _LLMUnavailable(self._unavailable_reason)
        if not os.environ.get("ANTHROPIC_API_KEY"):
            self._unavailable_reason = "ANTHROPIC_API_KEY not set"
            raise _LLMUnavailable(self._unavailable_reason)
        try:
            self._client = anthropic.Anthropic()
            if self.timeout is not None and hasattr(self._client, "with_options"):
                self._client = self._client.with_options(timeout=self.timeout)
            self._client_ready = True
            return self._client
        except Exception as e:  # pragma: no cover - construction rarely fails
            self._unavailable_reason = f"client init failed: {type(e).__name__}: {e}"
            raise _LLMUnavailable(self._unavailable_reason) from e

    # ── Fallback handlers ───────────────────────────────────────────────────

    def _handle_failure(self, view, legal, reason: str) -> "Action":
        self.fallbacks += 1
        _LOG.warning("FALLBACK (per-decision) reason=%s | %s", reason, self.usage_summary())
        short = reason.split(":", 1)[0]
        self._notices.append(FallbackNotice(
            message=f"Opponent fell back to standard play for this decision (reason: {short}).",
            reason=short,
        ))
        return self.fallback.choose_action(view, legal)

    def _handle_unavailable(self, view, legal, reason: str) -> "Action":
        # Configuration condition (no key / no SDK): announce ONCE, then quietly
        # play at heuristic strength — do not spam a notice on every decision.
        if not self._announced_unavailable:
            self._announced_unavailable = True
            _LOG.warning("LLM unavailable — running at heuristic strength: %s", reason)
            self._notices.append(FallbackNotice(
                message=f"Opponent is playing in standard mode ({reason}).",
                reason="unavailable",
            ))
        return self.fallback.choose_action(view, legal)

    # ── Prompt construction ─────────────────────────────────────────────────

    def _build_user_message(self, view: "PlayerView", legal: list["Action"]) -> str:
        compact = self._serialise_view(view)
        compact["legal_actions"] = _serialise_legal(legal)
        compact["card_glossary"] = self._card_glossary(view)
        return (
            "Current game state, your legal actions, and the relevant card rules:\n"
            + json.dumps(compact, separators=(",", ":"), default=str)
            + "\n\nChoose exactly one action_id via the choose_action tool."
        )

    @staticmethod
    def _serialise_view(view: "PlayerView") -> dict:
        """Compact, hidden-info-safe projection of THIS player's own view.

        Built only from ``view.to_dict()`` (the engine's redaction), so the
        opponent's hand is already ``[]`` and their resources are ``[hidden]``
        stubs.  We additionally strip card_ids from those redacted stubs.
        """
        d = view.to_dict()

        def zone(z: dict, *, mine: bool) -> dict:
            out = {
                "player_id": z["player_id"],
                "deck_count": z["deck_count"],
                "hand_count": z["hand_count"],
                "resource_count": z["resource_count"],
                "available_resources": z["available_resources"],
                "ground_arena": [_card_brief(c) for c in z["ground_arena"]],
                "space_arena": [_card_brief(c) for c in z["space_arena"]],
                "base_zone": [_card_brief(c) for c in z["base_zone"]],
                "discard": [_card_brief(c) for c in z.get("discard", [])],
            }
            if mine:
                out["hand"] = [_card_brief(c) for c in z["hand"]]
            return out

        return {
            "viewer_id": d["viewer_id"],
            "phase": d["phase"],
            "round_number": d["round_number"],
            "active_player_id": d["active_player_id"],
            "initiative_holder_id": d["initiative_holder_id"],
            "my": zone(d["my"], mine=True),
            "opponent": zone(d["opponent"], mine=False),  # hand omitted (redacted)
            "event_log_tail": d.get("event_log_tail", [])[-12:],
            "pending_decisions": d.get("pending_decisions", []),
        }

    def _card_glossary(self, view: "PlayerView") -> dict:
        """Rules text for cards currently relevant: own hand + all cards in play.

        Keyed by card_id (== DB cards.id).  Redacted cards (card_id == -1) and
        cards with no text are skipped.  Best effort — if the DB is unavailable
        the model still has stats + keywords.
        """
        d = view.to_dict()
        ids: set[int] = set()

        def collect(cards: list[dict]) -> None:
            for c in cards:
                cid = c.get("card_id", -1)
                if isinstance(cid, int) and cid >= 0:
                    ids.add(cid)
                for u in c.get("attached_upgrades", []):
                    collect([u])

        for zkey in ("my", "opponent"):
            z = d[zkey]
            for arena in ("ground_arena", "space_arena", "base_zone"):
                collect(z.get(arena, []))
        collect(d["my"].get("hand", []))  # opponent hand is [] — nothing to add

        glossary: dict[str, str] = {}
        for cid in sorted(ids):
            text = self._card_text(cid)
            if text:
                glossary[str(cid)] = text
        return glossary

    def _card_text(self, card_id: int) -> Optional[str]:
        if card_id in self._card_text_cache:
            return self._card_text_cache[card_id] or None
        text = self._lookup_card_text(card_id)
        self._card_text_cache[card_id] = text or ""
        return text or None

    def _lookup_card_text(self, card_id: int) -> Optional[str]:
        if not self._db_path:
            return None
        try:
            con = sqlite3.connect(self._db_path)
            con.row_factory = sqlite3.Row
            try:
                row = con.execute(
                    "SELECT name, type, text, deploy_box, epic_action "
                    "FROM cards WHERE id = ?",
                    (card_id,),
                ).fetchone()
            finally:
                con.close()
        except sqlite3.Error:  # pragma: no cover - DB best effort
            return None
        if row is None:
            return None
        parts: list[str] = []
        for key in ("text", "deploy_box", "epic_action"):
            val = row[key]
            if val:
                parts.append(_norm(val))
        return " | ".join(parts) if parts else None


# ── Module helpers ─────────────────────────────────────────────────────────────

def _env_timeout() -> float:
    raw = os.environ.get(_TIMEOUT_ENV)
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    return DEFAULT_TIMEOUT_S


def _norm(s: str) -> str:
    return s.replace("\xa0", " ").strip()


def _card_brief(c: dict) -> dict:
    """A compact card projection for the prompt (drops noisy/irrelevant fields)."""
    out = {
        "instance_id": c["instance_id"],
        "card_id": c["card_id"],
        "name": c["card_name"],
        "type": c["card_type"],
    }
    # Stats only matter for things with a body; keep the payload lean otherwise.
    if c.get("effective_power") or c.get("effective_hp") or c["card_type"] in ("Unit", "Leader", "Base"):
        out["power"] = c.get("effective_power", 0)
        out["hp"] = c.get("effective_hp", 0)
        out["damage"] = c.get("damage", 0)
    if c.get("cost"):
        out["cost"] = c["cost"]
    if c.get("exhausted"):
        out["exhausted"] = True
    if c.get("keywords"):
        out["keywords"] = c["keywords"]
    ups = c.get("attached_upgrades") or []
    if ups:
        out["upgrades"] = [_card_brief(u) for u in ups]
    return out


def _serialise_legal(legal: list["Action"]) -> list[dict]:
    out = []
    for i, a in enumerate(legal):
        out.append({
            "action_id": f"a{i}",
            "kind": type(a).__name__,
            "label": _describe(a),
            "params": _action_params(a),
        })
    return out


def _describe(a: "Action") -> str:
    try:
        return a.describe()
    except Exception:  # pragma: no cover - describe is total in practice
        return type(a).__name__


def _action_params(a: "Action") -> dict:
    from dataclasses import asdict, is_dataclass
    if is_dataclass(a):
        try:
            return {k: v for k, v in asdict(a).items()}
        except Exception:  # pragma: no cover
            pass
    return {}


def _extract_tool_call(resp) -> tuple[Optional[str], str]:
    """Pull (action_id, reasoning) from the forced choose_action tool call."""
    content = getattr(resp, "content", None) or []
    for block in content:
        btype = _block_field(block, "type")
        if btype != "tool_use":
            continue
        if _block_field(block, "name") != "choose_action":
            continue
        raw = _block_field(block, "input") or {}
        if not isinstance(raw, dict):
            return None, ""
        action_id = raw.get("action_id")
        reasoning = raw.get("reasoning") or ""
        if isinstance(action_id, str):
            return action_id, str(reasoning)
        return None, str(reasoning)
    return None, ""


def _block_field(block, name):
    if isinstance(block, dict):
        return block.get(name)
    return getattr(block, name, None)


def _safe_repr(obj) -> str:
    try:
        text = repr(obj)
    except Exception:  # pragma: no cover
        text = "<unrepresentable>"
    return text[:500]
