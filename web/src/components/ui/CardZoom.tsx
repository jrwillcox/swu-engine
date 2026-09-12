// The card-inspect overlay — anchored (hover) and centred (long-press) modes.
import { useLayoutEffect, useState, type CSSProperties } from "react";
import { motion } from "motion/react";
import type { CardModel } from "../../api/types";
import { useSettings } from "../../game/settings";
import { artFor } from "../../game/variants";

// Card zoom. Two modes:
//  • anchored (default) — desktop hover: pinned beside the hovered card's own
//    rect (NOT the cursor), so it doesn't re-render the table on every move.
//  • centered (touch inspect) — long-press: shown centred over a tap-to-dismiss
//    scrim, so it's readable without a mouse.
// Leaders/bases render landscape, and a leader's reverse (unit) side is shown
// alongside the front.
export function CardZoom({
  card,
  anchored = true,
  onDismiss,
}: {
  card: CardModel | null;
  anchored?: boolean;
  onDismiss?: () => void;
}) {
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);

  const s = useSettings();
  const art = card ? artFor(card, s.variantMode) : { front: null, back: null };
  // Front of a leader/base is landscape; a leader's reverse (unit) side is portrait.
  const frontLandscape = card ? card.card_type === "Leader" || card.card_type === "Base" : false;
  const hasBack = !!art.back;
  const isTokenUp = (u: CardModel) =>
    u.card_type === "Token Upgrade" || u.card_name === "Shield" || u.card_name === "Experience";
  // Real (non-token) upgrades attached to the hovered card, surfaced below it.
  const upgrades = (card?.attached_upgrades ?? []).filter((u) => !isTokenUp(u));
  // Token counts (Shield / Experience) so they're visible in the zoom too.
  const tokenUps = (card?.attached_upgrades ?? []).filter(isTokenUp);
  const shields = tokenUps.filter((u) => u.card_name === "Shield").length;
  const xp = tokenUps.filter((u) => u.card_name === "Experience").length;
  const hasTokens = shields > 0 || xp > 0;
  // Aspect-penalty surcharge for an off-aspect card in your own hand (0 otherwise).
  const penalty = card?.aspect_penalty ?? 0;
  const hasPenalty = penalty > 0;
  // Smuggle cost for one of your own resources (base bracket cost + aspect penalty).
  const smuggleBase = card?.smuggle_base ?? null;
  const smugglePen = card?.smuggle_penalty ?? 0;
  const hasSmuggle = smuggleBase !== null;
  const W = frontLandscape ? 360 : 250;
  // Per-face height: landscape faces are W*300/418, portrait faces W*418/300.
  // A leader shows a landscape front + a portrait (unit) reverse, stacked.
  const frontFaceH = frontLandscape ? Math.round(W * (300 / 418)) : Math.round(W * (418 / 300));
  const backFaceH = Math.round(W * (418 / 300)); // reverse is always the portrait unit side
  // Upgrades render as a row of small portrait thumbnails beneath the host.
  const upW = Math.round(W * 0.44);
  const upBlockH = upgrades.length ? Math.round(upW * (418 / 300)) + 26 : 0;
  const tokenBlockH = hasTokens ? 34 : 0;
  const penaltyBlockH = hasPenalty ? 34 : 0;
  const smuggleBlockH = hasSmuggle ? 34 : 0;
  const H =
    (hasBack ? frontFaceH + backFaceH + 38 : frontFaceH + 8) +
    upBlockH +
    tokenBlockH +
    penaltyBlockH +
    smuggleBlockH;

  useLayoutEffect(() => {
    if (!card || !anchored) {
      setPos(null);
      return;
    }
    const el = document.querySelector(`[data-instance="${card.instance_id}"]`);
    if (!el) {
      setPos(null);
      return;
    }
    const r = el.getBoundingClientRect();
    let left = r.right + 16;
    if (left + W > window.innerWidth - 8) left = r.left - W - 16;
    if (left < 8) left = 8;
    let top = r.top + r.height / 2 - H / 2;
    top = Math.max(8, Math.min(top, window.innerHeight - H - 8));
    setPos({ left, top });
  }, [card, W, H, anchored]);

  if (!card || !art.front) return null;
  if (anchored && !pos) return null;

  const body = (
    <>
      <div className={`zoom-face ${frontLandscape ? "landscape" : "portrait"}`}>
        <img src={art.front} alt={card.card_name} />
        {hasBack && <span className="zoom-tag">Front</span>}
        {hasPenalty && (
          <div className="cost-penalty zoom" title="Aspect cost penalty (off-aspect)">
            +{penalty}
          </div>
        )}
      </div>
      {hasBack && (
        <div className="zoom-face portrait">
          <img src={art.back!} alt={`${card.card_name} (reverse)`} />
          <span className="zoom-tag">Reverse</span>
        </div>
      )}
      {hasPenalty && (
        <div className="zoom-penalty" title={`Off-aspect — costs ${card.cost + penalty} to play`}>
          <span className="zoom-penalty-badge">+{penalty}</span>
          <span>Aspect cost penalty</span>
        </div>
      )}
      {hasSmuggle && (
        <div
          className="zoom-penalty smuggle"
          title={`Smuggle cost: ${smuggleBase! + smugglePen}${
            smugglePen > 0 ? ` (${smuggleBase} + ${smugglePen} off-aspect)` : ""
          }`}
        >
          <span className="zoom-penalty-badge neutral">{smuggleBase}</span>
          {smugglePen > 0 && <span className="zoom-penalty-badge">+{smugglePen}</span>}
          <span>Smuggle cost</span>
        </div>
      )}
      {hasTokens && (
        <div className="zoom-tokens">
          {shields > 0 && (
            <div className="zoom-token shield" title={`${shields} Shield${shields > 1 ? "s" : ""}`}>
              <span className="zoom-token-icon">⛉</span>
              <span>
                Shield{shields > 1 ? <span className="zoom-token-count"> ×{shields}</span> : null}
              </span>
            </div>
          )}
          {xp > 0 && (
            <div className="zoom-token xp" title={`${xp} Experience`}>
              <span className="zoom-token-icon">✦</span>
              <span>
                Experience{xp > 1 ? <span className="zoom-token-count"> ×{xp}</span> : null}
              </span>
            </div>
          )}
        </div>
      )}
      {upgrades.length > 0 && (
        <div className="zoom-upgrades" style={{ "--up-w": `${upW}px` } as CSSProperties}>
          {upgrades.map((u) => (
            <div className="zoom-up" key={u.instance_id}>
              {u.image_url && <img src={u.image_url} alt={u.card_name} />}
              <span className="zoom-tag">Upgrade</span>
            </div>
          ))}
        </div>
      )}
    </>
  );

  // Touch inspect: centred over a tap-anywhere scrim to dismiss.
  if (!anchored) {
    return (
      <div className="scrim card-zoom-scrim" onClick={onDismiss}>
        <motion.div
          className="card-zoom centered"
          style={{ width: W }}
          onClick={(e) => e.stopPropagation()}
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.12 }}
        >
          {body}
        </motion.div>
      </div>
    );
  }

  // Desktop hover: pinned beside the card.
  return (
    <motion.div
      className="card-zoom"
      style={{ left: pos!.left, top: pos!.top, width: W }}
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.1 }}
    >
      {body}
    </motion.div>
  );
}
