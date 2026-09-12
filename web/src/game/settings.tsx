// User-facing presentation settings: animation speed, reduced motion, card art.
// Persisted to localStorage and reflected onto <html data-*> so CSS variables
// (theme.css) can react. Pure presentation — never touches game logic.
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Speed = "fast" | "normal" | "slow";
import type { VariantMode } from "./variants";
export type { VariantMode } from "./variants";

export interface Settings {
  speed: Speed;
  reducedMotion: boolean;
  /** Which card-art printing to show (cosmetic). Default "standard". */
  variantMode: VariantMode;
  /**
   * Show the "available to play" state in the Card Explorer (the Available
   * filter + the per-card Playable/Not-yet badges). Off by default now that the
   * whole printed range is implemented — the distinction is only interesting
   * again when a new set lands part-encoded.
   */
  showAvailability: boolean;
  setSpeed: (s: Speed) => void;
  setReducedMotion: (b: boolean) => void;
  setVariantMode: (m: VariantMode) => void;
  setShowAvailability: (b: boolean) => void;
  /** Effective animation duration multiplier (0 ≈ instant). */
  factor: number;
}

const SPEED_FACTOR: Record<Speed, number> = { fast: 0.45, normal: 1, slow: 2.1 };

const Ctx = createContext<Settings | null>(null);

function load<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v === null ? fallback : (JSON.parse(v) as T);
  } catch {
    return fallback;
  }
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [speed, setSpeed] = useState<Speed>(() => load("swu.speed", "normal"));
  const [reducedMotion, setReducedMotion] = useState<boolean>(() => load("swu.reduced", false));
  const [variantMode, setVariantMode] = useState<VariantMode>(() =>
    load("swu.variantMode", "standard"),
  );
  const [showAvailability, setShowAvailability] = useState<boolean>(() =>
    load("swu.showAvail", false),
  );

  useEffect(() => {
    localStorage.setItem("swu.variantMode", JSON.stringify(variantMode));
  }, [variantMode]);
  useEffect(() => {
    localStorage.setItem("swu.speed", JSON.stringify(speed));
    document.documentElement.dataset.speed = speed;
  }, [speed]);
  useEffect(() => {
    localStorage.setItem("swu.reduced", JSON.stringify(reducedMotion));
    document.documentElement.dataset.reduced = String(reducedMotion);
  }, [reducedMotion]);
  useEffect(() => {
    localStorage.setItem("swu.showAvail", JSON.stringify(showAvailability));
  }, [showAvailability]);

  const factor = reducedMotion ? 0.001 : SPEED_FACTOR[speed];

  const value = useMemo<Settings>(
    () => ({
      speed,
      reducedMotion,
      variantMode,
      showAvailability,
      setSpeed,
      setReducedMotion,
      setVariantMode,
      setShowAvailability,
      factor,
    }),
    [speed, reducedMotion, variantMode, showAvailability, factor],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSettings(): Settings {
  const v = useContext(Ctx);
  if (!v) throw new Error("useSettings must be used within SettingsProvider");
  return v;
}
