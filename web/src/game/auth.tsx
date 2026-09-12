// User login state. Holds the signed-in user + bearer token, persists the token
// to localStorage so the same machine stays signed in, and exposes
// login/register/logout. Mirrors the SettingsProvider context pattern.
//
// The token is the source of truth for "remembered on this machine": on mount we
// read it and validate via GET /api/auth/me; a stale/invalid token is cleared.
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, setAuthToken } from "../api/client";

const TOKEN_KEY = "swu.authToken";

export interface AuthUser {
  username: string;
  admin: boolean;
}

export interface Auth {
  /** The signed-in user, or null when signed out. */
  user: AuthUser | null;
  /** False until the stored token has been validated (avoid a login flash). */
  ready: boolean;
  check: (username: string) => Promise<{ exists: boolean; allowed: boolean }>;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const Ctx = createContext<Auth | null>(null);

export function UserProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);

  // On load: validate a remembered token, else go straight to the login screen.
  useEffect(() => {
    let token: string | null = null;
    try {
      token = localStorage.getItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
    if (!token) {
      setReady(true);
      return;
    }
    setAuthToken(token);
    api.auth
      .me()
      .then((me) => setUser({ username: me.username, admin: me.admin }))
      .catch(() => {
        try {
          localStorage.removeItem(TOKEN_KEY);
        } catch {
          /* ignore */
        }
        setAuthToken(null);
      })
      .finally(() => setReady(true));
  }, []);

  const value = useMemo<Auth>(() => {
    const apply = (token: string, username: string, admin: boolean) => {
      try {
        localStorage.setItem(TOKEN_KEY, token);
      } catch {
        /* ignore */
      }
      setAuthToken(token);
      setUser({ username, admin });
    };
    return {
      user,
      ready,
      check: (username) => api.auth.check(username),
      login: async (username, password) => {
        const r = await api.auth.login(username, password);
        apply(r.token, r.username, r.admin);
      },
      register: async (username, password) => {
        const r = await api.auth.register(username, password);
        apply(r.token, r.username, r.admin);
      },
      logout: async () => {
        try {
          await api.auth.logout();
        } catch {
          /* ignore — clear locally regardless */
        }
        try {
          localStorage.removeItem(TOKEN_KEY);
        } catch {
          /* ignore */
        }
        setAuthToken(null);
        setUser(null);
      },
    };
  }, [user, ready]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useUser(): Auth {
  const v = useContext(Ctx);
  if (!v) throw new Error("useUser must be used within UserProvider");
  return v;
}
