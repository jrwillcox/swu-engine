// Auth: the login gate's first-time-create vs returning-login flows, a remembered
// token on reload, sign out, the non-whitelisted rejection, and the admin-only
// "Manage users" control on the start screen.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// One mock of the API client for the whole file. ApiError is re-implemented so
// the LoginScreen's `instanceof ApiError` message path works.
vi.mock("../src/api/client", () => {
  class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
      this.name = "ApiError";
    }
  }
  return {
    ApiError,
    setAuthToken: vi.fn(),
    api: {
      decks: vi.fn(async () => [
        { key: "luke", label: "Luke", leader_name: "Luke", base_name: "Tower" },
        { key: "vader", label: "Vader", leader_name: "Vader", base_name: "Command" },
      ]),
      listSaves: vi.fn(async () => []),
      auth: {
        check: vi.fn(),
        login: vi.fn(),
        register: vi.fn(),
        logout: vi.fn(async () => {}),
        me: vi.fn(),
        users: vi.fn(),
        reset: vi.fn(),
      },
    },
  };
});

import { api } from "../src/api/client";
import { LoginScreen } from "../src/components/LoginScreen";
import { NewGameScreen } from "../src/components/NewGameScreen";
import { UserProvider, useUser } from "../src/game/auth";

const auth = api.auth as unknown as Record<string, ReturnType<typeof vi.fn>>;

// Mirrors App's gate so we can observe provider state transitions.
function Harness() {
  const a = useUser();
  if (!a.ready) return <div>loading</div>;
  if (!a.user) return <LoginScreen />;
  return (
    <div>
      <div>
        hello {a.user.username}
        {a.user.admin ? " (admin)" : ""}
      </div>
      <button onClick={a.logout}>do-signout</button>
    </div>
  );
}

function renderGate() {
  return render(
    <UserProvider>
      <Harness />
    </UserProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe("login gate", () => {
  it("first-time username asks to create a password and registers", async () => {
    auth.check.mockResolvedValue({ exists: false, allowed: true });
    auth.register.mockResolvedValue({ token: "tok", username: "Alice", admin: true });
    renderGate();

    fireEvent.change(await screen.findByLabelText("Username"), {
      target: { value: "Alice" },
    });
    fireEvent.click(screen.getByText("Continue"));

    // First-time → "Create a password" + a "Create account" button.
    const pw = await screen.findByLabelText("Create a password");
    fireEvent.change(pw, { target: { value: "secret" } });
    fireEvent.click(screen.getByText("Create account"));

    expect(await screen.findByText("hello Alice (admin)")).toBeTruthy();
    expect(auth.register).toHaveBeenCalledWith("Alice", "secret");
    expect(localStorage.getItem("swu.authToken")).toBe("tok");
  });

  it("returning username asks for the password and logs in", async () => {
    auth.check.mockResolvedValue({ exists: true, allowed: true });
    auth.login.mockResolvedValue({ token: "tok", username: "Bob", admin: false });
    renderGate();

    fireEvent.change(await screen.findByLabelText("Username"), {
      target: { value: "Bob" },
    });
    fireEvent.click(screen.getByText("Continue"));

    const pw = await screen.findByLabelText("Password");
    fireEvent.change(pw, { target: { value: "pw" } });
    fireEvent.click(screen.getByText("Sign in"));

    expect(await screen.findByText("hello Bob")).toBeTruthy();
    expect(auth.login).toHaveBeenCalledWith("Bob", "pw");
  });

  it("remembers a valid token across a reload (no login screen)", async () => {
    localStorage.setItem("swu.authToken", "remembered");
    auth.me.mockResolvedValue({ username: "Alice", admin: true });
    renderGate();

    expect(await screen.findByText("hello Alice (admin)")).toBeTruthy();
    expect(auth.me).toHaveBeenCalled();
  });

  it("clears a stale token and falls back to the login screen", async () => {
    localStorage.setItem("swu.authToken", "stale");
    auth.me.mockRejectedValue(new Error("401"));
    renderGate();

    expect(await screen.findByLabelText("Username")).toBeTruthy();
    expect(localStorage.getItem("swu.authToken")).toBeNull();
  });

  it("signs out back to the login screen", async () => {
    localStorage.setItem("swu.authToken", "remembered");
    auth.me.mockResolvedValue({ username: "Alice", admin: true });
    renderGate();

    fireEvent.click(await screen.findByText("do-signout"));
    expect(await screen.findByLabelText("Username")).toBeTruthy();
    expect(auth.logout).toHaveBeenCalled();
    expect(localStorage.getItem("swu.authToken")).toBeNull();
  });

  it("rejects a non-whitelisted name and stays on the username step", async () => {
    auth.check.mockResolvedValue({ exists: false, allowed: false });
    renderGate();

    fireEvent.change(await screen.findByLabelText("Username"), {
      target: { value: "Bob" },
    });
    fireEvent.click(screen.getByText("Continue"));

    expect(await screen.findByText("That name can't sign in here.")).toBeTruthy();
    // Still on the username step — no password field appeared.
    expect(screen.queryByLabelText("Create a password")).toBeNull();
  });
});

describe("account bar", () => {
  async function renderStart(user: { username: string; admin: boolean } | null) {
    render(
      <NewGameScreen onStart={vi.fn()} busy={false} error={null} user={user} onSignOut={vi.fn()} />,
    );
    await waitFor(() => expect(screen.getByText("Start game")).not.toBeDisabled());
  }

  it("shows Manage users only for an admin", async () => {
    await renderStart({ username: "Alice", admin: true });
    expect(screen.getByText("Manage users")).toBeTruthy();
    expect(screen.getByText("Sign out")).toBeTruthy();
  });

  it("hides Manage users for a non-admin", async () => {
    await renderStart({ username: "Bob", admin: false });
    expect(screen.queryByText("Manage users")).toBeNull();
    expect(screen.getByText("Sign out")).toBeTruthy();
  });
});
