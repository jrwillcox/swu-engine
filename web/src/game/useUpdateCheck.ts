import { useEffect, useState } from "react";

// Detects that a newer build has been deployed while this copy of the app is still
// running. A tablet can keep the app open (or suspended in the background) for days,
// so without this it carries on with old code after a deploy. Each build writes its
// id to version.json (see buildVersion in vite.config.ts); we compare that file with
// the id baked into this bundle.

const CHECK_EVERY_MS = 5 * 60_000;

export interface UpdateCheckOptions {
  /** The id of the build that is running. */
  current?: string;
  /** Where the deployed build's id is published. */
  url?: string;
  intervalMs?: number;
  /** Off in dev: the dev server has no version.json. */
  enabled?: boolean;
}

/** True once the server is serving a different build from the one running here. */
export function useUpdateCheck({
  current = __APP_BUILD__,
  url = `${import.meta.env.BASE_URL}version.json`,
  intervalMs = CHECK_EVERY_MS,
  enabled = import.meta.env.PROD,
}: UpdateCheckOptions = {}): boolean {
  const [updateReady, setUpdateReady] = useState(false);

  useEffect(() => {
    if (!enabled || updateReady) return;
    let cancelled = false;

    async function check() {
      try {
        const res = await fetch(`${url}?t=${Date.now()}`, { cache: "no-store" });
        if (!res.ok) return;
        const { build } = (await res.json()) as { build?: unknown };
        if (!cancelled && typeof build === "string" && build && build !== current) {
          setUpdateReady(true);
        }
      } catch {
        /* offline or server restarting: try again next time */
      }
    }

    // Coming back to the app (switching to it, or reopening it from the home screen)
    // is when a stale copy is most likely, so check then as well as on a timer.
    function onVisible() {
      if (document.visibilityState === "visible") void check();
    }

    void check();
    const timer = setInterval(check, intervalMs);
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("pageshow", onVisible);
    return () => {
      cancelled = true;
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("pageshow", onVisible);
    };
  }, [current, url, intervalMs, enabled, updateReady]);

  return updateReady;
}
