// The login gate — the front door. Type a username; if it has no password yet
// you're asked to *create* one, otherwise to *enter* it. Reuses the start-screen
// panel/button styling.
import { useState } from "react";
import { ApiError } from "../api/client";
import { useUser } from "../game/auth";

export function LoginScreen() {
  const auth = useUser();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [stage, setStage] = useState<"username" | "password">("username");
  const [exists, setExists] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const msg = (e: unknown) =>
    e instanceof ApiError ? e.message : "Something went wrong — try again.";

  async function continueUsername() {
    const name = username.trim();
    if (!name) return;
    setBusy(true);
    setError(null);
    try {
      const { exists, allowed } = await auth.check(name);
      if (!allowed) {
        setError("That name can't sign in here.");
        return;
      }
      setExists(exists);
      setStage("password");
    } catch (e) {
      setError(msg(e));
    } finally {
      setBusy(false);
    }
  }

  async function submitPassword() {
    if (!password) return;
    setBusy(true);
    setError(null);
    try {
      if (exists) await auth.login(username.trim(), password);
      else await auth.register(username.trim(), password);
      // On success the provider sets the user and this screen unmounts.
    } catch (e) {
      setError(msg(e));
    } finally {
      setBusy(false);
    }
  }

  function back() {
    setStage("username");
    setPassword("");
    setError(null);
  }

  return (
    <div className="start-screen">
      <div className="start-card panel" style={{ maxWidth: 420 }}>
        <h1>Star Wars: Unlimited</h1>
        <div className="sub">
          {stage === "username"
            ? "Sign in to play."
            : exists
              ? `Welcome back, ${username.trim()}.`
              : `Hi ${username.trim()} — choose a password to set up your account.`}
        </div>

        {stage === "username" ? (
          <div className="start-row" style={{ marginTop: 18 }}>
            <input
              className="seed-input"
              style={{ flex: 1 }}
              aria-label="Username"
              placeholder="Username"
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && continueUsername()}
            />
            <button
              className="btn btn-primary"
              disabled={busy || !username.trim()}
              onClick={continueUsername}
            >
              Continue
            </button>
          </div>
        ) : (
          <>
            <div className="start-row" style={{ marginTop: 18 }}>
              <input
                className="seed-input"
                style={{ flex: 1 }}
                type="password"
                aria-label={exists ? "Password" : "Create a password"}
                placeholder={exists ? "Password" : "Create a password"}
                autoFocus
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && submitPassword()}
              />
              <button
                className="btn btn-primary"
                disabled={busy || !password}
                onClick={submitPassword}
              >
                {exists ? "Sign in" : "Create account"}
              </button>
            </div>
            <div className="start-row" style={{ marginTop: 4 }}>
              <button className="btn btn-ghost" onClick={back} disabled={busy}>
                ← Use a different name
              </button>
            </div>
          </>
        )}

        {error && <p style={{ color: "var(--danger)", marginTop: 14 }}>{error}</p>}
      </div>
    </div>
  );
}
