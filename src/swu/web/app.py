"""
FastAPI application — the HTTP surface over the engine.

Routes (all JSON unless noted):
  POST   /api/games                       create a game            -> NewGameResponse
  GET    /api/games/{id}/state            redacted PlayerView      -> Snapshot
  GET    /api/games/{id}/actions          human's legal actions    -> Snapshot
  POST   /api/games/{id}/actions/{aid}    apply a human action     -> StepResult
  POST   /api/games/{id}/advance          run the bot's turn(s)    -> StepResult
  DELETE /api/games/{id}                  drop the session
  POST   /api/games/{id}/save             persist a game to a slot -> {ok,slot,path}
  GET    /api/saves                       list save slots          -> list[str]
  POST   /api/saves/{slot}/load           restore a saved game     -> NewGameResponse
  GET    /api/games/{id}/replay           export a replay bundle   -> dict
  POST   /api/import/swudb                import a SWUDB decklist   -> import report
  GET    /api/decks                       deck catalog             -> list[DeckChoice]
  GET    /api/cards/{card_id}/image       serve a local card image (binary)

Design notes
  * The human's view is always rendered from `view_for(HUMAN_ID)`, so the
    opponent's hidden information never leaves the engine's redaction.
  * `apply` and `advance` are deliberately separate: the frontend animates the
    human action's events, then calls `advance` to fetch the bot's events as a
    second animation batch.  This keeps the event→animation contract clean.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.responses import FileResponse

from swu.web.auth import (
    AlreadyExists,
    BadCredentials,
    EmptyPassword,
    NotAllowed,
    NotRegistered,
    UserStore,
)
from swu.web.bugs import (
    AdminTriage,
    BadStatus,
    BugNotFound,
    BugStore,
    BugSummary,
    BugThread,
    CreateBugRequest,
    ReplyRequest,
    ReporterArchiveRequest,
    StatusRequest,
    UnreadCount,
)
from swu.web.cards import image_file_for_card
from swu.web.decks import catalog
from swu.web.deckstore import (
    BadDeckId,
    CustomDeck,
    DeckNotFound,
    DeckSummary,
    InvalidCard,
    get_deck_store,
)
from swu.web.models import (
    AuthRequest,
    AuthResponse,
    CardDeltaRequest,
    CheckRequest,
    CheckResponse,
    CreateCustomDeckRequest,
    DeckChoice,
    ExplorerResponse,
    MeResponse,
    NewGameRequest,
    NewGameResponse,
    PatchCustomDeckRequest,
    ResetRequest,
    Snapshot,
    StepResult,
    UserSummary,
)
from swu.web.serializers import action_to_model, event_to_model, view_to_model
from swu.web.session import GameSession, IllegalStep, SessionStore

app = FastAPI(
    title="SWU Home Game — Web UI",
    version="0.1.0",
    description="Thin HTTP client surface over the frozen swu.engine contract.",
)

STORE = SessionStore()
AUTH = UserStore()
BUGS = BugStore()


# ── auth (user login) ─────────────────────────────────────────────────────────
#
# The login *gate* is enforced frontend-side (the hard gate); the game routes
# below are deliberately NOT wrapped in `Depends(current_user)` for now (the
# threat model is a 2-kid home LAN, and gating them would break the auth-free
# full-game HTTP tests). The extension point is `current_user` — apply it to the
# game/save routes and namespace saves per user once those become per-account.

def _token_from(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def current_user(authorization: str | None = Header(None)) -> dict:
    user = AUTH.user_for_token(_token_from(authorization))
    if user is None:
        raise HTTPException(status_code=401, detail="Not signed in.")
    return user


def require_admin(user: dict = Depends(current_user)) -> dict:
    if not user["admin"]:
        raise HTTPException(status_code=403, detail="Admins only.")
    return user


@app.post("/api/auth/check", response_model=CheckResponse)
def auth_check(req: CheckRequest) -> CheckResponse:
    exists, allowed = AUTH.check(req.username)
    return CheckResponse(exists=exists, allowed=allowed)


@app.post("/api/auth/register", response_model=AuthResponse)
def auth_register(req: AuthRequest) -> AuthResponse:
    try:
        token = AUTH.register(req.username, req.password)
    except NotAllowed:
        raise HTTPException(status_code=403, detail="That username isn't allowed here.")
    except AlreadyExists:
        raise HTTPException(status_code=409, detail="That user already exists — sign in instead.")
    except EmptyPassword:
        raise HTTPException(status_code=400, detail="Please choose a password.")
    user = AUTH.user_for_token(token)
    assert user is not None
    return AuthResponse(token=token, username=user["username"], admin=user["admin"])


@app.post("/api/auth/login", response_model=AuthResponse)
def auth_login(req: AuthRequest) -> AuthResponse:
    try:
        token = AUTH.login(req.username, req.password)
    except BadCredentials:
        raise HTTPException(status_code=401, detail="Wrong username or password.")
    user = AUTH.user_for_token(token)
    assert user is not None
    return AuthResponse(token=token, username=user["username"], admin=user["admin"])


@app.post("/api/auth/logout")
def auth_logout(authorization: str | None = Header(None)) -> dict:
    AUTH.logout(_token_from(authorization))
    return {"ok": True}


@app.get("/api/auth/me", response_model=MeResponse)
def auth_me(user: dict = Depends(current_user)) -> MeResponse:
    return MeResponse(username=user["username"], admin=user["admin"])


@app.get("/api/auth/users", response_model=list[UserSummary])
def auth_users(_: dict = Depends(require_admin)) -> list[UserSummary]:
    return [UserSummary(**u) for u in AUTH.list_users()]


@app.post("/api/auth/reset")
def auth_reset(req: ResetRequest, _: dict = Depends(require_admin)) -> dict:
    try:
        AUTH.set_password(req.username, req.new_password)
    except NotRegistered:
        raise HTTPException(status_code=404, detail="That user isn't registered yet.")
    except EmptyPassword:
        raise HTTPException(status_code=400, detail="Please choose a password.")
    return {"ok": True}


# ── bug reports & two-way messaging ───────────────────────────────────────────
#
# Every report is attributed to the authenticated username (never hardcoded), so
# the whole feature is multi-user for free.  Non-admins see only their own threads
# (the reporter inbox routes); an admin sees everyone's, bucketed for triage.

def _bug_owner_or_admin(bug_id: str, user: dict) -> None:
    """404 if the thread is missing, 403 unless the caller owns it or is admin."""
    try:
        author = BUGS.author_of(bug_id)
    except BugNotFound:
        raise HTTPException(status_code=404, detail=f"No such report: {bug_id}")
    if not user["admin"] and author != user["username"]:
        raise HTTPException(status_code=403, detail="Not your report.")


@app.post("/api/bugs", response_model=BugThread)
def create_bug(req: CreateBugRequest, user: dict = Depends(current_user)) -> BugThread:
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="A title is required.")
    return BUGS.create(
        author=user["username"],
        title=req.title.strip(),
        expected=req.expected,
        actual=req.actual,
        context=req.context,
        screenshot_b64=req.screenshot_b64,
        game=req.game,
    )


@app.get("/api/bugs", response_model=list[BugSummary])
def list_bugs(user: dict = Depends(current_user)) -> list[BugSummary]:
    return BUGS.list_for_user(user["username"])


@app.get("/api/bugs/unread-count", response_model=UnreadCount)
def bugs_unread_count(user: dict = Depends(current_user)) -> UnreadCount:
    return UnreadCount(count=BUGS.unread_count(user["username"]))


@app.get("/api/bugs/{bug_id}", response_model=BugThread)
def get_bug(bug_id: str, user: dict = Depends(current_user)) -> BugThread:
    _bug_owner_or_admin(bug_id, user)
    return BUGS.get(bug_id)


@app.post("/api/bugs/{bug_id}/reply", response_model=BugThread)
def reply_bug(bug_id: str, req: ReplyRequest, user: dict = Depends(current_user)) -> BugThread:
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="An empty reply can't be sent.")
    _bug_owner_or_admin(bug_id, user)
    return BUGS.add_message(bug_id, sender=user["username"], text=req.text.strip())


@app.post("/api/bugs/{bug_id}/read", response_model=BugThread)
def read_bug(bug_id: str, user: dict = Depends(current_user)) -> BugThread:
    _bug_owner_or_admin(bug_id, user)
    return BUGS.mark_read(bug_id, user["username"])


@app.post("/api/bugs/{bug_id}/reporter-archive", response_model=BugThread)
def reporter_archive_bug(
    bug_id: str, req: ReporterArchiveRequest, user: dict = Depends(current_user)
) -> BugThread:
    """The reporter tidies their own inbox — toggles the cosmetic ``reporter_archived``
    flag.  Never moves the folder, so it's independent of the admin's disk archive and
    invisible to his triage view."""
    _bug_owner_or_admin(bug_id, user)
    return BUGS.set_reporter_archived(bug_id, req.archived)


@app.get("/api/bugs/{bug_id}/screenshot")
def bug_screenshot(bug_id: str, user: dict = Depends(current_user)) -> Response:
    _bug_owner_or_admin(bug_id, user)
    path = BUGS.screenshot_path(bug_id)
    if path is None:
        raise HTTPException(status_code=404, detail="No screenshot for this report.")
    return FileResponse(path, media_type="image/png")


@app.get("/api/bugs/{bug_id}/game")
def bug_game(bug_id: str, user: dict = Depends(current_user)) -> Response:
    """Serve the report's replay bundle (game.json) so an admin can open the reported
    game in the ReplayViewer (Stage 4).  Owner-or-admin, like the screenshot."""
    _bug_owner_or_admin(bug_id, user)
    path = BUGS.game_path(bug_id)
    if path is None:
        raise HTTPException(status_code=404, detail="No game state for this report.")
    return FileResponse(path, media_type="application/json")


@app.get("/api/admin/bugs", response_model=AdminTriage)
def admin_list_bugs(user: dict = Depends(require_admin)) -> AdminTriage:
    return BUGS.list_all_bucketed(user["username"])


@app.post("/api/admin/bugs/{bug_id}/status", response_model=BugThread)
def admin_set_status(bug_id: str, req: StatusRequest, _: dict = Depends(require_admin)) -> BugThread:
    try:
        return BUGS.set_status(bug_id, req.status)
    except BugNotFound:
        raise HTTPException(status_code=404, detail=f"No such report: {bug_id}")
    except BadStatus:
        raise HTTPException(status_code=400, detail=f"Unknown status: {req.status}")


@app.post("/api/admin/bugs/{bug_id}/archive", response_model=BugThread)
def admin_archive_bug(bug_id: str, _: dict = Depends(require_admin)) -> BugThread:
    try:
        return BUGS.archive(bug_id)
    except BugNotFound:
        raise HTTPException(status_code=404, detail=f"No such report: {bug_id}")


# ── snapshot assembly ─────────────────────────────────────────────────────────

def _snapshot_fields(session: GameSession) -> dict:
    awaiting = session.awaiting()
    actions = [
        action_to_model(aid, a, session.label_for(a))
        for aid, a in session.human_actions()
    ]
    return dict(
        game_id=session.game_id,
        view=view_to_model(session.state.view_for(session.human_id)),
        awaiting=awaiting,
        actor_id=session.actor_id(),
        winner=session.winner,
        prompt=session.prompt(),
        actions=actions,
    )


def _snapshot(session: GameSession) -> Snapshot:
    return Snapshot(**_snapshot_fields(session))


def _step_result(session: GameSession, events: list) -> StepResult:
    return StepResult(
        **_snapshot_fields(session),
        events=[event_to_model(e) for e in events],
    )


def _get(game_id: str) -> GameSession:
    try:
        return STORE.get(game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No such game: {game_id}")


# ── game lifecycle ────────────────────────────────────────────────────────────

@app.post("/api/games", response_model=NewGameResponse)
def create_game_endpoint(req: NewGameRequest) -> NewGameResponse:
    try:
        session = STORE.create(
            human_deck=req.human.deck,
            bot_deck=req.bot.deck,
            seed=req.seed,
            difficulty=req.difficulty,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return NewGameResponse(player_id=session.human_id, **_snapshot_fields(session))


@app.get("/api/games/{game_id}/state", response_model=Snapshot)
def get_state(game_id: str) -> Snapshot:
    return _snapshot(_get(game_id))


@app.get("/api/games/{game_id}/actions", response_model=Snapshot)
def get_actions(game_id: str) -> Snapshot:
    return _snapshot(_get(game_id))


@app.post("/api/games/{game_id}/actions/{action_id}", response_model=StepResult)
def apply_action(game_id: str, action_id: str) -> StepResult:
    session = _get(game_id)
    try:
        events = session.apply_human(action_id)
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown action_id: {action_id}")
    except IllegalStep as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _step_result(session, events)


@app.post("/api/games/{game_id}/advance", response_model=StepResult)
def advance(game_id: str) -> StepResult:
    session = _get(game_id)
    events = session.advance_bot()
    return _step_result(session, events)


@app.delete("/api/games/{game_id}")
def delete_game(game_id: str) -> dict:
    STORE.delete(game_id)
    return {"ok": True}


# ── save / restore / replay ─────────────────────────────────────────────────

@app.post("/api/games/{game_id}/save")
def save_game(game_id: str, slot: str | None = Query(None)) -> dict:
    _get(game_id)
    try:
        path = STORE.save(game_id, slot)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No such game: {game_id}")
    return {"ok": True, "slot": slot or game_id, "path": str(path)}


@app.get("/api/saves")
def list_saves() -> list[str]:
    return STORE.list_saves()


@app.post("/api/saves/{slot}/load", response_model=NewGameResponse)
def load_game(slot: str) -> NewGameResponse:
    try:
        session = STORE.load(slot)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No such save: {slot}")
    return NewGameResponse(player_id=session.human_id, **_snapshot_fields(session))


@app.get("/api/games/{game_id}/replay")
def export_replay(game_id: str) -> dict:
    """Export a shareable, deterministic replay bundle for this game."""
    return _get(game_id).replay_bundle()


@app.post("/api/replay")
def replay_steps_endpoint(payload: dict = Body(...)) -> dict:
    """Reconstruct per-step board snapshots from a replay bundle so the UI can
    scrub forward/back.  Body: {"bundle": <replay bundle>} (or the bundle itself)."""
    from swu.web.session import replay_steps
    bundle = payload.get("bundle") if "bundle" in payload else payload
    try:
        human_id, steps = replay_steps(bundle)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid replay bundle: {e}")
    return {
        "human_id": human_id,
        "steps": [
            {
                "view": view_to_model(view),
                "events": [event_to_model(e) for e in events],
                "winner": winner,
            }
            for view, events, winner in steps
        ],
    }


# ── catalog & images ──────────────────────────────────────────────────────────

@app.get("/api/decks", response_model=list[DeckChoice])
def list_decks(authorization: str | None = Header(None)) -> list[DeckChoice]:
    """Official decks (built-in + graduated) plus, when a bearer token is
    supplied, the caller's *complete* custom decks appended and tagged
    ``kind="custom"``.  Anonymous callers get official decks only."""
    out = [
        DeckChoice(
            key=d.key, label=d.label,
            leader_name=d.leader_name, base_name=d.base_name,
            kind="official",
        )
        for d in catalog()
    ]
    user = AUTH.user_for_token(_token_from(authorization))
    if user is not None:
        out.extend(_custom_deck_choices(user["username"]))
    return out


# ── custom deck builder (Stage 3) ─────────────────────────────────────────────
#
# Per-user, auth-gated CRUD over the file-backed ``DeckStore`` (the bugs.py
# pattern).  Owner isolation is intrinsic: the store scopes every operation to the
# caller's own folder, so another user's deck id simply isn't found (404).

def _custom_deck_choices(username: str) -> list[DeckChoice]:
    """``DeckChoice`` rows for the caller's *complete* custom decks (start-screen
    dropdown).  Incomplete drafts are omitted — only playable decks can seat a
    game."""
    store = get_deck_store()
    repo = store.repo
    choices: list[DeckChoice] = []
    for summary in store.list_decks(username):
        if not summary.complete:
            continue
        deck = store.get(username, summary.id)
        leader = repo.by_id(deck.leader_id) if deck.leader_id is not None else None
        base = repo.by_id(deck.base_id) if deck.base_id is not None else None
        choices.append(DeckChoice(
            key=f"custom:{username.lower()}:{deck.id}",
            label=f"{deck.name} (custom)",
            leader_name=leader.name if leader is not None else "",
            base_name=base.name if base is not None else "",
            kind="custom",
        ))
    return choices


@app.get("/api/decks/custom", response_model=list[DeckSummary])
def list_custom_decks(user: dict = Depends(current_user)) -> list[DeckSummary]:
    return get_deck_store().list_decks(user["username"])


@app.post("/api/decks/custom", response_model=CustomDeck)
def create_custom_deck(
    req: CreateCustomDeckRequest, user: dict = Depends(current_user)
) -> CustomDeck:
    name = req.name.strip() or "Untitled deck"
    return get_deck_store().create(user["username"], name)


@app.get("/api/decks/custom/{deck_id}", response_model=CustomDeck)
def get_custom_deck(deck_id: str, user: dict = Depends(current_user)) -> CustomDeck:
    try:
        return get_deck_store().get(user["username"], deck_id)
    except (DeckNotFound, BadDeckId):
        raise HTTPException(status_code=404, detail=f"No such deck: {deck_id}")


@app.patch("/api/decks/custom/{deck_id}", response_model=CustomDeck)
def patch_custom_deck(
    deck_id: str, req: PatchCustomDeckRequest, user: dict = Depends(current_user)
) -> CustomDeck:
    store = get_deck_store()
    username = user["username"]
    fields = req.model_fields_set
    try:
        # Rename first (if requested), then the slot/card edits — return the final.
        if "name" in fields and req.name is not None:
            store.rename(username, deck_id, req.name.strip())
        slot_kwargs: dict = {}
        if "leader_id" in fields:
            slot_kwargs["leader_id"] = req.leader_id
        if "base_id" in fields:
            slot_kwargs["base_id"] = req.base_id
        if "cards" in fields:
            slot_kwargs["cards"] = req.cards or {}
        if slot_kwargs:
            return store.set_cards(username, deck_id, **slot_kwargs)
        return store.get(username, deck_id)
    except (DeckNotFound, BadDeckId):
        raise HTTPException(status_code=404, detail=f"No such deck: {deck_id}")
    except InvalidCard as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/decks/custom/{deck_id}/cards", response_model=CustomDeck)
def custom_deck_card_delta(
    deck_id: str, req: CardDeltaRequest, user: dict = Depends(current_user)
) -> CustomDeck:
    """Granular +/- for the Explorer's fast add: bump a pool card's count by
    ``delta`` (a count reaching ≤0 removes it).  Over-cap is allowed (drafts) and
    surfaced via the deck's derived ``errors``."""
    try:
        return get_deck_store().add_card(
            user["username"], deck_id, req.card_id, req.delta
        )
    except (DeckNotFound, BadDeckId):
        raise HTTPException(status_code=404, detail=f"No such deck: {deck_id}")
    except InvalidCard as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/decks/custom/{deck_id}")
def delete_custom_deck(deck_id: str, user: dict = Depends(current_user)) -> dict:
    try:
        get_deck_store().delete(user["username"], deck_id)
    except (DeckNotFound, BadDeckId):
        raise HTTPException(status_code=404, detail=f"No such deck: {deck_id}")
    return {"ok": True}


@app.get("/api/catalog/cards", response_model=ExplorerResponse)
def explorer_cards() -> ExplorerResponse:
    """The whole card catalog for the explorer screen, with filter facets and a
    per-card ``playable`` ("Available to play") flag."""
    from swu.web.explorer import build_catalog
    return ExplorerResponse(**build_catalog())


@app.post("/api/import/swudb")
def import_swudb(payload: dict = Body(...)) -> dict:
    """Import a SWUDB decklist (pasted ``deck`` JSON, or a ``ref`` url/id), report
    legality + which cards aren't playable yet, and write a fixture the planner
    can consume.  Body: {"deck": <swudb json>} or {"ref": "<url|id>"}, "name"?."""
    from swu.web.decks import _repo
    from swu.web.swudb_import import import_deck, fetch_swudb_deck

    data = payload.get("deck")
    if data is None and payload.get("ref"):
        try:
            data = fetch_swudb_deck(payload["ref"])
        except Exception as e:  # network/parse failure
            raise HTTPException(status_code=400, detail=f"Could not fetch deck: {e}")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Provide a 'deck' JSON object or a 'ref'.")

    name = payload.get("name") or "imported"
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name).strip("_") or "imported"
    out = Path(__file__).resolve().parents[3] / "data" / "imported" / f"{safe}.json"
    try:
        report = import_deck(data, _repo(), write_to=out, slug=safe)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid decklist: {e}")
    return report.to_dict()


@app.get("/api/cards/{card_id}/image")
def card_image(
    card_id: int,
    face: str = Query("front", pattern="^(front|back)$"),
    variant: str | None = Query(None, pattern="^(hyperspace|hyperspace_foil|showcase)$"),
) -> Response:
    path = image_file_for_card(card_id, face, variant)
    if path is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(
        path,
        headers={"Cache-Control": "public, max-age=86400, immutable"},
    )


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}
