// The "new version is ready" check: useUpdateCheck compares the build id baked into
// the running bundle with the deployed version.json; UpdateBanner offers the reload.
import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useUpdateCheck } from "../src/game/useUpdateCheck";
import { UpdateBanner } from "../src/components/UpdateBanner";

function serve(body: unknown, ok = true) {
  const fetchMock = vi.fn(async () => ({ ok, json: async () => body }) as Response);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const opts = { current: "build-1", url: "/version.json", enabled: true };

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useUpdateCheck", () => {
  it("stays quiet while the server serves the running build", async () => {
    const fetchMock = serve({ build: "build-1" });
    const { result } = renderHook(() => useUpdateCheck(opts));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(result.current).toBe(false);
  });

  it("reports an update once the server serves a different build", async () => {
    serve({ build: "build-2" });
    const { result } = renderHook(() => useUpdateCheck(opts));
    await waitFor(() => expect(result.current).toBe(true));
  });

  it("bypasses the cache when asking for the deployed build", async () => {
    const fetchMock = serve({ build: "build-1" });
    renderHook(() => useUpdateCheck(opts));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toMatch(/^\/version\.json\?t=\d+$/);
    expect(init.cache).toBe("no-store");
  });

  it("ignores a missing or malformed version file and a failed request", async () => {
    for (const setup of [
      () => serve({}, false),
      () => serve({ nope: 1 }),
      () =>
        vi.stubGlobal(
          "fetch",
          vi.fn(async () => Promise.reject(new Error("offline"))),
        ),
    ]) {
      setup();
      const { result, unmount } = renderHook(() => useUpdateCheck(opts));
      await waitFor(() => expect(fetch).toHaveBeenCalled());
      await act(async () => {});
      expect(result.current).toBe(false);
      unmount();
    }
  });

  it("checks again when the app comes back to the foreground", async () => {
    const fetchMock = serve({ build: "build-1" });
    const { result } = renderHook(() => useUpdateCheck(opts));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(result.current).toBe(false);

    // A deploy happens while the tablet has the app in the background.
    serve({ build: "build-2" });
    act(() => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await waitFor(() => expect(result.current).toBe(true));
  });

  it("does nothing when disabled (the dev server has no version file)", async () => {
    const fetchMock = serve({ build: "build-2" });
    const { result } = renderHook(() => useUpdateCheck({ ...opts, enabled: false }));
    await act(async () => {});
    expect(fetchMock).not.toHaveBeenCalled();
    expect(result.current).toBe(false);
  });
});

describe("UpdateBanner", () => {
  it("reloads when the player taps Update now", () => {
    const onReload = vi.fn();
    render(<UpdateBanner onReload={onReload} />);
    expect(screen.getByRole("status")).toHaveTextContent(/new version/i);
    fireEvent.click(screen.getByRole("button", { name: /update now/i }));
    expect(onReload).toHaveBeenCalledTimes(1);
  });
});
