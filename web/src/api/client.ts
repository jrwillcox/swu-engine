// Thin fetch wrapper over the backend. The frontend computes no game rules —
// it only POSTs the action_id the backend assigned and renders what comes back.
import type {
  AdminTriage,
  AuthResponse,
  BugGame,
  BugSummary,
  BugThread,
  CheckResponse,
  CreateBugRequest,
  CustomDeck,
  CustomDeckSummary,
  DeckChoice,
  ExplorerResponse,
  ImportReport,
  MeResponse,
  NewGameRequest,
  NewGameResponse,
  PatchCustomDeckRequest,
  ReplayBundle,
  ReplayResponse,
  SaveResult,
  Snapshot,
  StepResult,
  UserSummary,
} from "./types";

// The current user's bearer token, sent as `Authorization: Bearer <token>` on
// authenticated calls. Held in a module variable (set by the auth context after
// login / on app load) so the client stays a plain function module.
let authToken: string | null = null;
export function setAuthToken(token: string | null) {
  authToken = token;
}
function authHeaders(json = false): Record<string, string> {
  const h: Record<string, string> = {};
  if (json) h["Content-Type"] = "application/json";
  if (authToken) h["Authorization"] = `Bearer ${authToken}`;
  return h;
}

async function jsonOrThrow<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(resp.status, detail);
  }
  return resp.json() as Promise<T>;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const api = {
  // ── Auth (user login) ──────────────────────────────────────────────────────
  auth: {
    async check(username: string): Promise<CheckResponse> {
      return jsonOrThrow(
        await fetch("/api/auth/check", {
          method: "POST",
          headers: authHeaders(true),
          body: JSON.stringify({ username }),
        }),
      );
    },
    async register(username: string, password: string): Promise<AuthResponse> {
      return jsonOrThrow(
        await fetch("/api/auth/register", {
          method: "POST",
          headers: authHeaders(true),
          body: JSON.stringify({ username, password }),
        }),
      );
    },
    async login(username: string, password: string): Promise<AuthResponse> {
      return jsonOrThrow(
        await fetch("/api/auth/login", {
          method: "POST",
          headers: authHeaders(true),
          body: JSON.stringify({ username, password }),
        }),
      );
    },
    async logout(): Promise<void> {
      await fetch("/api/auth/logout", { method: "POST", headers: authHeaders() });
    },
    async me(): Promise<MeResponse> {
      return jsonOrThrow(await fetch("/api/auth/me", { headers: authHeaders() }));
    },
    async users(): Promise<UserSummary[]> {
      return jsonOrThrow(await fetch("/api/auth/users", { headers: authHeaders() }));
    },
    async reset(username: string, new_password: string): Promise<void> {
      await jsonOrThrow(
        await fetch("/api/auth/reset", {
          method: "POST",
          headers: authHeaders(true),
          body: JSON.stringify({ username, new_password }),
        }),
      );
    },
  },

  async decks(): Promise<DeckChoice[]> {
    // Send the bearer token when signed in so the backend appends the caller's
    // *complete* custom decks (tagged kind="custom"); anonymous → official only.
    return jsonOrThrow(await fetch("/api/decks", { headers: authHeaders() }));
  },

  async catalog(): Promise<ExplorerResponse> {
    return jsonOrThrow(await fetch("/api/catalog/cards"));
  },

  // ── Custom deck builder (per-user, auth-gated CRUD) ────────────────────────
  // Every call resolves the current user from the bearer token; the store scopes
  // by username, so owner isolation is intrinsic (another user's id → 404).
  customDecks: {
    async list(): Promise<CustomDeckSummary[]> {
      return jsonOrThrow(await fetch("/api/decks/custom", { headers: authHeaders() }));
    },
    async create(name: string): Promise<CustomDeck> {
      return jsonOrThrow(
        await fetch("/api/decks/custom", {
          method: "POST",
          headers: authHeaders(true),
          body: JSON.stringify({ name }),
        }),
      );
    },
    async get(id: string): Promise<CustomDeck> {
      return jsonOrThrow(
        await fetch(`/api/decks/custom/${encodeURIComponent(id)}`, {
          headers: authHeaders(),
        }),
      );
    },
    async patch(id: string, req: PatchCustomDeckRequest): Promise<CustomDeck> {
      return jsonOrThrow(
        await fetch(`/api/decks/custom/${encodeURIComponent(id)}`, {
          method: "PATCH",
          headers: authHeaders(true),
          body: JSON.stringify(req),
        }),
      );
    },
    async delete(id: string): Promise<{ ok: boolean }> {
      return jsonOrThrow(
        await fetch(`/api/decks/custom/${encodeURIComponent(id)}`, {
          method: "DELETE",
          headers: authHeaders(),
        }),
      );
    },
    // Granular +/- for the Explorer's fast add (Stage 5): bump a pool card's
    // count by `delta` (a count reaching ≤0 removes it).
    async cards(id: string, card_id: number, delta: number): Promise<CustomDeck> {
      return jsonOrThrow(
        await fetch(`/api/decks/custom/${encodeURIComponent(id)}/cards`, {
          method: "POST",
          headers: authHeaders(true),
          body: JSON.stringify({ card_id, delta }),
        }),
      );
    },
  },

  async newGame(req: NewGameRequest): Promise<NewGameResponse> {
    return jsonOrThrow(
      await fetch("/api/games", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
      }),
    );
  },

  async state(gameId: string): Promise<Snapshot> {
    return jsonOrThrow(await fetch(`/api/games/${gameId}/state`));
  },

  async applyAction(gameId: string, actionId: string): Promise<StepResult> {
    return jsonOrThrow(await fetch(`/api/games/${gameId}/actions/${actionId}`, { method: "POST" }));
  },

  async advance(gameId: string): Promise<StepResult> {
    return jsonOrThrow(await fetch(`/api/games/${gameId}/advance`, { method: "POST" }));
  },

  /** Drop an abandoned game from the server's memory. */
  async deleteGame(gameId: string): Promise<void> {
    await jsonOrThrow(await fetch(`/api/games/${gameId}`, { method: "DELETE" }));
  },

  // ── Part D: save / restore / replay / import ──────────────────────────────

  async saveGame(gameId: string, slot?: string): Promise<SaveResult> {
    const q = slot ? `?slot=${encodeURIComponent(slot)}` : "";
    return jsonOrThrow(await fetch(`/api/games/${gameId}/save${q}`, { method: "POST" }));
  },

  async listSaves(): Promise<string[]> {
    return jsonOrThrow(await fetch("/api/saves"));
  },

  async loadGame(slot: string): Promise<NewGameResponse> {
    return jsonOrThrow(
      await fetch(`/api/saves/${encodeURIComponent(slot)}/load`, { method: "POST" }),
    );
  },

  async exportReplay(gameId: string): Promise<ReplayBundle> {
    return jsonOrThrow(await fetch(`/api/games/${gameId}/replay`));
  },

  async replay(bundle: ReplayBundle): Promise<ReplayResponse> {
    return jsonOrThrow(
      await fetch("/api/replay", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bundle }),
      }),
    );
  },

  async importSwudb(payload: {
    deck?: unknown;
    ref?: string;
    name?: string;
  }): Promise<ImportReport> {
    return jsonOrThrow(
      await fetch("/api/import/swudb", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }),
    );
  },

  // ── Bug reports & two-way messaging ───────────────────────────────────────
  // Every call resolves the current user from the bearer token (like /auth/me),
  // so the store is multi-user for free. The screenshot endpoint needs the
  // header too, so it can't be a bare <img src> (fetch + object URL in the UI).
  bugs: {
    async create(req: CreateBugRequest): Promise<BugThread> {
      return jsonOrThrow(
        await fetch("/api/bugs", {
          method: "POST",
          headers: authHeaders(true),
          body: JSON.stringify(req),
        }),
      );
    },
    async list(): Promise<BugSummary[]> {
      return jsonOrThrow(await fetch("/api/bugs", { headers: authHeaders() }));
    },
    async get(id: string): Promise<BugThread> {
      return jsonOrThrow(
        await fetch(`/api/bugs/${encodeURIComponent(id)}`, { headers: authHeaders() }),
      );
    },
    async reply(id: string, text: string): Promise<BugThread> {
      return jsonOrThrow(
        await fetch(`/api/bugs/${encodeURIComponent(id)}/reply`, {
          method: "POST",
          headers: authHeaders(true),
          body: JSON.stringify({ text }),
        }),
      );
    },
    async markRead(id: string): Promise<BugThread> {
      return jsonOrThrow(
        await fetch(`/api/bugs/${encodeURIComponent(id)}/read`, {
          method: "POST",
          headers: authHeaders(),
        }),
      );
    },
    // The reporter's cosmetic inbox archive (never moves the folder on disk).
    async setArchived(id: string, archived: boolean): Promise<BugThread> {
      return jsonOrThrow(
        await fetch(`/api/bugs/${encodeURIComponent(id)}/reporter-archive`, {
          method: "POST",
          headers: authHeaders(true),
          body: JSON.stringify({ archived }),
        }),
      );
    },
    // The screenshot endpoint needs the bearer header, so it can't be a bare
    // <img src>. Fetch it with auth and hand back an object URL the caller must
    // revoke when done. Returns null on any failure (best-effort artifact).
    async screenshotObjectUrl(id: string): Promise<string | null> {
      try {
        const r = await fetch(`/api/bugs/${encodeURIComponent(id)}/screenshot`, {
          headers: authHeaders(),
        });
        if (!r.ok) return null;
        return URL.createObjectURL(await r.blob());
      } catch {
        return null;
      }
    },
    async unreadCount(): Promise<number> {
      const r = await jsonOrThrow<{ count: number }>(
        await fetch("/api/bugs/unread-count", { headers: authHeaders() }),
      );
      return r.count;
    },
    // The replay bundle written for a game-screen report (game.json); the admin opens
    // it in the ReplayViewer. 404 (no game state) throws an ApiError like any call.
    async game(id: string): Promise<BugGame> {
      return jsonOrThrow(
        await fetch(`/api/bugs/${encodeURIComponent(id)}/game`, {
          headers: authHeaders(),
        }),
      );
    },
    // Admin triage.
    async adminList(): Promise<AdminTriage> {
      return jsonOrThrow(await fetch("/api/admin/bugs", { headers: authHeaders() }));
    },
    async adminSetStatus(id: string, status: string): Promise<BugThread> {
      return jsonOrThrow(
        await fetch(`/api/admin/bugs/${encodeURIComponent(id)}/status`, {
          method: "POST",
          headers: authHeaders(true),
          body: JSON.stringify({ status }),
        }),
      );
    },
    async adminArchive(id: string): Promise<BugThread> {
      return jsonOrThrow(
        await fetch(`/api/admin/bugs/${encodeURIComponent(id)}/archive`, {
          method: "POST",
          headers: authHeaders(),
        }),
      );
    },
  },
};
