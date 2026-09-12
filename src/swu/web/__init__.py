"""
Phase 5 — local web UI backend.

A thin HTTP/JSON layer over the frozen swu.engine contract
(`legal_actions` / `apply` / `view_for`).  The backend owns the GameState,
maps it to/from JSON, drives the bot seat, and serves card images.  It never
re-implements a game rule: the frontend references actions only by the id the
backend assigned.

See `app.py` for the FastAPI application and the route surface.
"""
