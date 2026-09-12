// EffectsLayer — decorative overlays driven by the active event from the queue.
// It anchors to cards via their data-instance attribute (set by <Card/>), so it
// rides on top of the truth board that Motion already animates. Purely cosmetic:
// it never changes game state.
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import type { GameEvent } from "../api/types";
import type { ActiveEvent } from "../game/useGame";

interface Fx {
  key: number;
  kind: "dmg" | "heal" | "over" | "defeat" | "shield" | "token" | "attack";
  x: number;
  y: number;
  text?: string;
}
interface Banner {
  key: number;
  text: string;
  color: string;
}

function anchor(instanceId: string | null | undefined): { x: number; y: number } | null {
  if (!instanceId) return null;
  const el = document.querySelector(`[data-instance="${instanceId}"]`);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
}

function toFx(ev: GameEvent, key: number): { fx?: Fx; banner?: Banner } {
  const d = ev.data;
  switch (ev.type) {
    case "DamageDealt": {
      const a = anchor(d.target_instance_id as string);
      if (!a) return {};
      return { fx: { key, kind: "dmg", ...a, text: `-${d.amount}` } };
    }
    case "RestoreHealing":
      return { banner: { key, text: `+${d.amount} Restore`, color: "var(--good)" } };
    case "OverwhelmDamage":
      return { banner: { key, text: "Overwhelm!", color: "var(--warn)" } };
    case "UnitDefeated": {
      const a = anchor(d.instance_id as string);
      return a ? { fx: { key, kind: "defeat", ...a } } : {};
    }
    case "ShieldDefeated": {
      const a = anchor(d.host_instance_id as string);
      return a ? { fx: { key, kind: "shield", ...a, text: "⛉" } } : {};
    }
    case "TokenAttached": {
      const a = anchor(d.host_instance_id as string);
      return a
        ? { fx: { key, kind: "token", ...a, text: d.token_name === "Shield" ? "⛉" : "✦" } }
        : {};
    }
    case "AttackDeclared": {
      const a = anchor(d.attacker_instance_id as string);
      return a ? { fx: { key, kind: "attack", ...a } } : {};
    }
    case "LeaderDeployed":
      return { banner: { key, text: `${d.leader_name} deploys!`, color: "var(--accent)" } };
    default:
      return {};
  }
}

export function EffectsLayer({ active }: { active: ActiveEvent | null }) {
  const [fx, setFx] = useState<Fx | null>(null);
  const [banner, setBanner] = useState<Banner | null>(null);

  useEffect(() => {
    if (!active) return;
    // Defer one frame so the truth board has laid out the relevant cards.
    const raf = requestAnimationFrame(() => {
      const { fx: f, banner: b } = toFx(active.ev, active.key);
      if (f) setFx(f);
      if (b) setBanner(b);
    });
    return () => cancelAnimationFrame(raf);
  }, [active]);

  return (
    <div className="fx-layer">
      <AnimatePresence>
        {fx && fx.kind === "dmg" && (
          <motion.div
            key={fx.key}
            className="fx-float dmg"
            style={{ left: fx.x, top: fx.y }}
            initial={{ opacity: 0, scale: 0.4, y: 0 }}
            animate={{ opacity: 1, scale: 1.2, y: -34 }}
            exit={{ opacity: 0, y: -54 }}
            transition={{ duration: 0.5 }}
            onAnimationComplete={() => setFx(null)}
          >
            {fx.text}
          </motion.div>
        )}
        {fx && fx.kind === "defeat" && (
          <motion.div
            key={fx.key}
            className="fx-ring"
            style={{ left: fx.x, top: fx.y, borderColor: "var(--danger)" }}
            initial={{ opacity: 0.9, scale: 0.4 }}
            animate={{ opacity: 0, scale: 2.4 }}
            transition={{ duration: 0.5 }}
            onAnimationComplete={() => setFx(null)}
          />
        )}
        {fx && fx.kind === "attack" && (
          <motion.div
            key={fx.key}
            className="fx-ring"
            style={{ left: fx.x, top: fx.y }}
            initial={{ opacity: 0.8, scale: 0.5 }}
            animate={{ opacity: 0, scale: 1.8 }}
            transition={{ duration: 0.4 }}
            onAnimationComplete={() => setFx(null)}
          />
        )}
        {fx && (fx.kind === "shield" || fx.kind === "token") && (
          <motion.div
            key={fx.key}
            className="fx-shield"
            style={{ left: fx.x, top: fx.y }}
            initial={{ opacity: 0, scale: 0.3, rotate: -20 }}
            animate={{ opacity: 1, scale: 1.4, rotate: 0 }}
            exit={{ opacity: 0, scale: 0.6 }}
            transition={{ duration: 0.45 }}
            onAnimationComplete={() => setFx(null)}
          >
            {fx.text}
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {banner && (
          <motion.div
            key={banner.key}
            className="fx-banner"
            style={{ color: banner.color }}
            initial={{ opacity: 0, scale: 0.7 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.2 }}
            transition={{ duration: 0.4 }}
            onAnimationComplete={() => setTimeout(() => setBanner(null), 400)}
          >
            {banner.text}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
