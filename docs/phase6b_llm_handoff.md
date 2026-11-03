# Phase 6B — LLM Opponent: Implementation Handoff

> **6B in five lines.** Phase 6A shipped a strong heuristic opponent behind a
> clean bot factory and a difficulty selector (Easy/Normal/Hard, default Normal,
> remembered in the browser). Your job in 6B is to add an `LLMPlayer` that plays
> via the Anthropic API and wire it into **one** function — the factory — so that
> **Normal** plays casually and **Hard** plays to win, each falling back to the
> heuristic when the model errors or returns an illegal/unparseable choice.
> **Easy stays a pure heuristic forever — it must never call the API.** You do
> not touch the engine, the UI, or the HTTP routes; the seam is already there.

This document is self-contained: a fresh session should be able to implement the
LLM player from it alone.

---

## 1. The `Player` protocol — exactly what you implement

`src/swu/players/base.py` defines the protocol every opponent satisfies. The
**runtime contract** (what the backend and soak harness actually call) is:

```python
def choose_action(self, view: PlayerView, legal: list[Action]) -> Action: ...
def observe(self, state, action, actor_id: str) -> None: ...   # optional, no-op ok
player_id: str
```

Notes that matter:

- `choose_action` is handed a **`PlayerView`** (the redacted, per-player snapshot —
  *not* the full `GameState`) and the engine's **fully-enumerated** list of legal
  `Action` objects. **It must return one of the objects in `legal`** (the same
  instance / an equal one), never a freshly constructed action. Returning
  anything not in `legal` will be rejected.
- It is a **pure function of `view` + `legal` + the player's own state**. The
  bot sees only what the human-style view exposes — never the opponent's hand or
  deck order (see §6).
- The base-module docstring's signature says `state: GameState`; the **real**
  callers (`web/session.py`, `scripts/soak.py`, every existing bot) pass a
  `PlayerView`. Follow the view contract — that is the source of truth.

The LLM player will:
1. Serialise `view` (+ relevant card rules text, §5) and the numbered `legal`
   list into a prompt.
2. Call the Anthropic API (latest capable model; see `/claude-api` skill for IDs
   — default to a current Claude model, e.g. `claude-haiku-4-5-20251001` for
   latency or a Sonnet/Opus for strength).
3. Parse the model's chosen **index** back into `legal[i]`.
4. On any failure (network, parse, out-of-range, timeout) **fall back to the
   heuristic's choice** for the same `(view, legal)` — see §3.

A stub already exists at `src/swu/players/llm_player.py` (raises
`NotImplementedError`); replace it.

---

## 2. The factory seam — the *only* file you change to wire it up

`src/swu/players/difficulty.py`:

```python
class Difficulty(str, Enum):
    EASY = "easy"; NORMAL = "normal"; HARD = "hard"

def make_opponent(difficulty, *, player_id: str, seed=None, rng=None) -> Player:
    ...
    if diff is Difficulty.EASY:
        return HeuristicBot(player_id, rng=bot_rng, mistake_rate=0.25)
    if diff is Difficulty.HARD:
        return HeuristicBot(player_id, rng=bot_rng, sharp_targeting=True)   # ← change
    return HeuristicBot(player_id, rng=bot_rng)                            # ← change (NORMAL)
```

**The one-line change for 6B** (Normal and Hard branches only):

```python
from swu.players.llm_player import LLMPlayer
# NORMAL:
return LLMPlayer(player_id, fallback=HeuristicBot(player_id, rng=bot_rng), style="casual")
# HARD:
return LLMPlayer(player_id, fallback=HeuristicBot(player_id, rng=bot_rng, sharp_targeting=True),
                 style="competitive")
```

**Leave EASY exactly as it is** — a `HeuristicBot` with `mistake_rate`. That is a
hard product requirement (a child's level: instant, free, never hits the API).

Nothing else in the backend or UI knows which kind of bot it received. The
session stores whatever `make_opponent` returns and calls `choose_action`.

---

## 3. The heuristic as fallback

`src/swu/players/heuristic_bot.py` — `HeuristicBot(player_id, *, rng=None,
seed=None, mistake_rate=0.0, sharp_targeting=False)`.

- It answers **every** decision kind the engine can present (main phase,
  mulligan, resourcing, targeting, triggers, trigger ordering, and every pending
  decision: ambush, exploit, resolve_effects, say_no, distribute_damage,
  deck_search, peek_top, choose_number, modal, granted_attack, …). Anything it
  has no opinion on falls through to a safe default.
- `choose_action` is wrapped so it **never raises**: any internal error returns a
  safe legal action (`_safe_default`). This is the property your LLM fallback
  relies on — you can always call `self.fallback.choose_action(view, legal)` and
  trust it returns a legal action without throwing.
- It is fast (no search) and seed-deterministic.

Recommended LLM-player shape:

```python
class LLMPlayer:
    def __init__(self, player_id, *, fallback, style, model=...): ...
    def choose_action(self, view, legal):
        try:
            idx = self._ask_model(view, legal)        # may raise / time out
            return legal[idx]                          # validate 0 <= idx < len(legal)
        except Exception:
            return self.fallback.choose_action(view, legal)
```

The robustness soak (`scripts/soak.py --bots heuristic`) proves the fallback is
legal-for-every-decision across the starter, vanilla, and keyword decks. **Your
LLM-path tests must not assume determinism (§10); test the fallback path and the
parse/validation logic deterministically instead.**

---

## 4. What `view` and the legal actions look like as JSON

The bot receives Python objects, but they serialise 1:1 to the JSON the web
layer already sends (`PlayerView.to_dict()` / `view_to_model`, and
`action_to_model`). Use these shapes when building the prompt.

### 4a. `PlayerView` (real mid-game snapshot, P0, round 3 — trimmed)

```jsonc
{
  "viewer_id": "P0",
  "phase": "ACTION",                      // SETUP_MULLIGAN | SETUP_RESOURCES | ACTION | REGROUP
  "round_number": 3,
  "active_player_id": "P0",
  "initiative_holder_id": "P0",
  "my": {
    "player_id": "P0",
    "deck_count": 40,                     // count only — no order
    "hand": [                             // YOUR hand: full identities
      { "instance_id": "P0_8", "card_id": 115, "card_name": "Admiral Ozzel — Overconfident",
        "card_type": "Unit", "zone": "HAND", "exhausted": false, "damage": 0,
        "deployed": false, "epic_action_spent": false,
        "effective_power": 2, "effective_hp": 3, "cost": 2,
        "attached_upgrades": [], "keywords": [] },
      { "instance_id": "P0_6", "card_id": 35, "card_name": "TIE/ln Fighter", "card_type": "Unit",
        "effective_power": 2, "effective_hp": 1, "cost": 1, "keywords": [], "attached_upgrades": [] }
      // …
    ],
    "hand_count": 4,
    "discard": [ /* CardViews, full identity */ ],
    "resources": [ /* YOUR resources: full identity, face_down:true */ ],
    "resource_count": 8,
    "available_resources": 8,             // unexhausted resources (what you can spend now)
    "ground_arena": [ /* CardViews */ ],
    "space_arena": [ /* CardViews */ ],
    "base_zone": [ /* your Base (card_type "Base") + undeployed Leader */ ],
    "is_eliminated": false
  },
  "opponent": {
    "player_id": "P1",
    "deck_count": 41,
    "hand": [],                           // OPPONENT hand: REDACTED — empty list
    "hand_count": 5,                      // count only
    "discard": [ /* visible */ ],
    "resources": [ { "card_id": -1, "card_name": "[hidden]", "face_down": true, ... } ], // redacted stubs
    "resource_count": 7,
    "available_resources": 7,
    "ground_arena": [ /* visible — cards in play are public */ ],
    "space_arena": [ /* visible */ ],
    "base_zone": [ /* opponent Base (visible) + their deployed/undeployed leader */ ],
    "is_eliminated": false
  },
  "event_log_tail": ["CardPlayed", "AttackDeclared", "DamageDealt", "..."],  // see §6
  "pending_decisions": [
    // empty in a normal main-phase turn; when non-empty, the TOP is [-1] and
    // legal actions are ONLY that decision's options (see §4c).
    // { "deciding_player_id": "P0", "kind": "resolve_effects", "context": {...}, "is_mine": true }
  ]
}
```

`CardView` fields: `instance_id`, `card_id` (== DB `cards.id`, §5), `card_name`
(name + subtitle), `card_type` (`Unit`|`Leader`|`Base`|`Event`|`Upgrade`),
`owner_id`, `zone`, `exhausted`, `damage`, `face_down`, `deployed`,
`epic_action_spent`, `effective_power`, `effective_hp`, `cost`,
`attached_upgrades` (nested CardViews — Shield/Experience tokens appear here),
`keywords`. **Effective HP remaining = `effective_hp - damage`.** Base remaining
HP works the same on the `card_type:"Base"` entry in `base_zone`.

`card_id == -1` / `card_name == "[hidden]"` marks a redacted card you may not
see (opponent resources). The opponent's hand is simply absent (`hand: []` with a
correct `hand_count`).

### 4b. Legal actions (`action_to_model`)

Each legal action serialises to:

```jsonc
{ "action_id": "a3",            // backend-assigned handle (web layer only)
  "kind": "AttackWithUnit",     // engine Action class name
  "label": "Attack unit P1_56 with P0_17",   // from Action.describe()
  "params": { "attacker_id": "P0_17", "defender_id": "P1_56" } }  // the dataclass fields
```

A real main-phase list (13 actions): several `PlayCard`
(`{instance_id, upgrade_target_id}`), `AttackWithUnit`
(`{attacker_id, defender_id}` — `defender_id:null` = attack base), maybe
`DeployLeader` (`{}`), `UseAbility` (`{source_id, ability_idx}`),
`ClaimInitiative` (`{}`), and always `Pass` (`{}`).

When you build the prompt, **number the actions and ask the model for an index**;
map the index back to `legal[i]`. (The `action_id` is only meaningful to the web
client; the LLM player works directly with the `legal` list it was given.)

### 4c. How decisions / targets / mulligan / trigger-ordering appear

The engine fully enumerates *everything* as actions — there is no separate
"decision API". You always just pick from `legal`:

| Situation | `legal` contains (kinds) |
|---|---|
| **Mulligan** | `KeepHand`, `TakeMultiligan` |
| **Setup resourcing** | one `ResourceCard{instance_id}` per hand card |
| **Regroup** | `ResourceCard{instance_id}` per hand card + `SkipResource` |
| **Main phase** | `PlayCard`, `AttackWithUnit`, `DeployLeader`, `AttackWithLeader`, `UseAbility`, `ClaimInitiative`, `Pass` |
| **Target a card** (resolve_effects) | `ChooseTarget{target_id}` per legal target, `DeclineTarget` (if optional), or a single `AutoResolveEffects` |
| **Optional triggered ability** | `AcceptTrigger{source_id}`, `DeclineTrigger{source_id}` |
| **Trigger ordering** | the engine presents simultaneous triggers as a sequence of `trigger_option`/`resolve_effects` decisions; you order them by which you accept/resolve first |
| **Ambush** | `UseAmbush{attacker_id,target_id}` per target, `DeclineAmbush{unit_id}` |
| **Exploit** | `ExploitSacrifice{unit_id}` per unit, `ExploitCommit` (offered only when affordable) |
| **Continue attack** | single `ContinueAttack{attacker_id,defender_id}` |
| **Modal "choose one"** | `ChooseModalOption{mode}` then `ChooseModalTarget{target_id}` |
| **Distribute damage** | `AssignDamage{target_id}` / `ChooseDamageTarget{target_id}` / `ChooseDamageSource{unit_id}` |
| **Deck search** | `SelectSearchCard{instance_id}` per candidate, `FinishSearch` |
| **Peek top of deck** | `KeepTopCard`, `BottomTopCard` / `DrawTopCard` |
| **Choose a number** | `ChooseNumber{number}` per value |
| **Opponent reaction** | `AllowEffect`/`SayNo`; `ReadyUnit{instance_id}`/`DeclineReadyUnit` |
| **Granted attack** | `AttackWithUnit{...}` per option, `DeclineGrantedAttack` (if optional) |

When `pending_decisions` is non-empty, `legal` contains **only** the top
decision's options, and `pending_decisions[-1].context` carries the decision's
data **only when `is_mine` is true** (it's `{}` for the other player). The
heuristic's per-handler logic in `heuristic_bot.py` is a worked reference for how
to reason about each of these — read it when designing the prompt.

---

## 5. Card rules text — where it is and how to look it up from the view

The view gives you `keywords` and stats but **not the rules text**. The full card
text lives in `data/swu.db` (SQLite), table `cards`:

- Relevant columns: `id`, `set_code`, `card_number`, `name`, `subtitle`, `type`,
  `cost`, `power`, `hp`, `upgrade_power`, `upgrade_hp`, **`text`** (unit/event
  body), **`deploy_box`** (leader sides), **`epic_action`** (leader epic action),
  `image_front_path`, …
- Keywords and traits are in side tables `card_keywords(card_id, name)` and
  `card_traits(card_id, name)` (FK → `cards.id`).

**Lookup from a `CardView`:** `card_view["card_id"]` **is** `cards.id`. So:

```sql
SELECT name, type, cost, power, hp, text, deploy_box, epic_action
FROM cards WHERE id = :card_id;
```

(Equivalently key by `set_code + card_number`.) Use the existing
`swu.cards.repository.CardRepository` rather than raw SQL if convenient — it
already loads a `CardDef` (with parsed `keywords`/`traits`) by id/name.

For the prompt, include rules text for: the bot's own hand + units in play, and
the **opponent's visible cards in play** (they are public). Non-breaking spaces
(`\xa0`) appear in some rows — normalise to regular spaces. Note `card_id == -1`
(redacted) has no text to fetch.

---

## 6. Event-log format and hidden-information guarantees

- `view.event_log_tail` is the **last 20 events as class-name strings** (e.g.
  `"CardPlayed"`, `"AttackDeclared"`, `"DamageDealt"`, `"UnitDefeated"`,
  `"LeaderDeployed"`, `"RoundStarted"`). It is a compact recent-history hint. If
  you want richer history for the prompt, the *web* layer serialises full event
  objects (`event_to_model`: `{type, data}`) and the UI already streams them; but
  the player view itself only carries the name tail by design (keeps the view
  small and avoids leaking hidden info through event payloads).
- **Hidden-info guarantee (do not violate):** `build_view(state, player_id)` is
  the only thing that should ever produce the data you feed the model, and it
  already redacts: opponent hand → `[]` (+count), opponent resources → `[hidden]`
  stubs, both decks → counts only, no deck order. **Never** build the LLM prompt
  from the raw `GameState` or from the human's view — only ever from *this*
  player's `PlayerView`. The web API enforces this on the wire
  (`test_hidden_info_redaction_on_payload`); keep the same discipline inside the
  LLM player. The model must only ever receive the bot's own view.

---

## 7. How bot turns are driven (backend), and where latency surfaces

`src/swu/web/session.py`:

- `GameSession.advance_bot()` loops while it is the bot's turn
  (`actor_id() == bot_id`) and **synchronously** calls
  `self.bot.choose_action(self.state.view_for(self.bot_id), legal_actions(...))`,
  applying each chosen action and collecting the produced events. It returns the
  ordered event batch.
- `actor_id()` returns the pending decision's `deciding_player_id` when a decision
  is on the stack, else the active player — so the bot is also driven through its
  own pending decisions inside this same loop.
- HTTP: the frontend calls `POST /api/games/{id}/actions/{action_id}` for the
  human action (animates that event batch), then `POST /api/games/{id}/advance`
  to run the bot's turn(s) and animate the second batch. `apply` and `advance`
  are deliberately separate.

**Latency / "thinking" indicator.** Today `advance` is synchronous and fast
(heuristic). The LLM call adds seconds. Two options for 6B:
1. Keep `advance` synchronous; the frontend already shows a busy state while the
   `advance` request is in flight (`useGame` `busy`/`locked`). A minimal change is
   to surface a "thinking…" label during that request. **No backend route change
   is required** for a working first cut.
2. If you want a live indicator independent of request timing, add an async/poll
   variant — but that is optional and out of scope for the core seam.
Either way, **the engine, the routes, and `advance_bot`'s shape do not need to
change** — only the `Player` instance behind `session.bot` differs.

---

## 8. Determinism note

- The heuristic is **seed-deterministic**: `(seed, difficulty, decks)` replays to
  an identical game. The soak's determinism oracle depends on this and stays
  valid for Easy (always heuristic) and for Normal/Hard *whenever the heuristic
  fallback is exercised*.
- The **LLM is not deterministic** and that is expected. When `make_opponent`
  returns an `LLMPlayer` for Normal/Hard, same-seed replays will diverge. This is
  fine for the product, but:
  - Do **not** run the determinism oracle / seeded-replay assertions against the
    LLM path.
  - Keep the LLM out of the soak's deterministic bot pool; soak the **heuristic**
    (the fallback) for the determinism/robustness guarantees.
  - LLM-path tests should assert *structure* (returns a legal action, falls back
    cleanly on a forced error, parses a canned model response correctly) — never a
    specific game outcome.

---

## 9. Quick checklist for 6B

1. Implement `LLMPlayer(player_id, *, fallback, style, model)` in
   `src/swu/players/llm_player.py`:
   - prompt from `view` (+ card text via §5) and numbered `legal`;
   - parse an index; validate; **fall back to `self.fallback` on any error**;
   - never receive anything but this player's own view (§6).
2. Edit **only** the NORMAL and HARD branches of `make_opponent` (§2). Leave EASY.
3. Tests: parse/validation unit tests + forced-fallback test (non-determinism-safe).
4. Optional: a "thinking…" indicator during `advance` (§7) — no route changes.
5. Cost/latency: pick the model via the `/claude-api` reference; consider a small
   model for casual/Normal and a stronger one for Hard.
