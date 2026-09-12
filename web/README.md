# Web UI

A web client for playing Star Wars: Unlimited against the built-in bots. **React + Vite + TypeScript** frontend over a **FastAPI** backend
that wraps the frozen `swu.engine`. The frontend knows no game rules — it renders
the redacted `PlayerView`, shows the legal actions the backend assigned, and
animates the event stream the engine emits.

## Run it

You need **two terminals** (backend + frontend), from the repository root:

### 1. Backend (FastAPI) — terminal 1

```powershell
# one-time: install the web extras into the project venv
.\.venv\Scripts\python.exe -m pip install -e ".[web]"

# start the API on http://127.0.0.1:8000
.\.venv\Scripts\python.exe -m swu.web
```

### 2. Frontend (Vite) — terminal 2

```powershell
cd web
npm install          # one-time
npm run dev          # http://localhost:5173
```

### 3. Play

Open **http://localhost:5173**, pick a deck for each side (Luke vs Vader),
and click **Start game**. Vite proxies `/api` to the backend, so there's no CORS
setup and the browser only ever talks HTTP.

## Play from another device on your LAN

The Vite dev server listens on every network interface (`server.host: true` in
[vite.config.ts](vite.config.ts)), and the `/api` proxy runs **host-side** against
the backend — so the **backend can stay bound to `127.0.0.1`** and only the
front-end URL changes. No CORS, no static build needed.

1. Start the backend and Vite as above.
2. Vite prints a **Network:** URL (e.g. `http://192.168.1.23:5173/`). Use that.
3. On a device on the same network, open `http://<host-ip>:5173`. A tablet in
   landscape is the best experience; on iOS, Share → _Add to Home Screen_ runs it
   full-screen.

Reaching it by _hostname_ rather than IP additionally requires
`SWU_ALLOWED_HOSTS` — see [.env.example](../.env.example). IP addresses always work.

Touch controls: **tap** a card to select it, then tap a highlighted target/zone to
act (the same model as the mouse). **Long-press** any card to inspect it large
(there is no hover on touch). Tap **📜** in the top bar to show/hide the battle
log.

Accounts are required — see `SWU_ALLOWED_USERS` in [.env.example](../.env.example).
The login gate is front-end only; the game routes themselves are unguarded, which
is fine on a trusted network and is **not** suitable for exposure to the internet.

### Manual touch-device smoke checklist

1. Start a game; the mulligan Keep/Mulligan buttons tap cleanly.
2. Resource step: tap two cards to stage them, then **Confirm resources**.
3. Play a card / declare an attack via tap-select → tap-target.
4. Long-press a card (hand, board, opponent, discard top, upgrade chip) shows the
   zoom; tap the backdrop to dismiss; **no iOS "Save Image" menu** appears.
5. Double-tapping the board does **not** zoom the page; no rubber-band bounce; the
   action bar is never hidden behind the browser toolbar.
6. 📜 log drawer slides in/out; the board uses the full landscape width.
7. Rotating to portrait shows a "rotate to landscape" hint.

## Playmats (drop-in)

Official playmat artwork is licensed IP and is never fetched or bundled. Ship
defaults are original, trademark-free CSS backdrops. To use your own scans, drop
images in [public/playmats/](public/playmats/) and map a leader to them in
[src/playmats/playmats.ts](src/playmats/playmats.ts).

## Tests

```powershell
npm run typecheck      # tsc --noEmit
npm test               # vitest: interaction, formatting, EffectsLayer, Table render
npx playwright test    # headless e2e smoke (auto-starts servers; reuses running ones)
```

Backend API tests live with the engine suite:
`..\.venv\Scripts\python.exe -m pytest tests/test_web_api.py -q`.

## How it fits together

```
Browser (React)  ──/api──►  FastAPI (src/swu/web)  ──in-process──►  swu.engine
  render view                owns GameState                          (frozen)
  show actions               assigns action ids
  animate events             drives the WeightedBot seat
```

- **`src/api/`** — typed client + payload types mirroring `docs/openapi.json`.
- **`src/game/`** — `useGame` (state + interruptible event queue), `interaction`
  (maps enumerated actions to clicks), `settings`, `format`.
- **`src/components/`** — `Table` and the zone/card/effects/overlay components.
- **`src/playmats/`** — backdrops + leader→playmat mapping.

The event log is the animation script: each step returns the events it produced,
and the UI plays them through a skippable queue while Motion handles card travel
(layout), entrances, and defeat/exit animations.
