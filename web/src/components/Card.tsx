import { memo } from "react";
import { motion } from "motion/react";
import type { CardModel } from "../api/types";
import { useSettings } from "../game/settings";
import { useLongPress } from "../game/useLongPress";
import { artFor } from "../game/variants";

export type Highlight = "legal" | "target" | "selected" | "staged" | "dim" | null;

export interface CardProps {
  card: CardModel;
  faceDown?: boolean;
  highlight?: Highlight;
  defeated?: boolean;
  onClick?: (card: CardModel) => void;
  onHover?: (card: CardModel | null) => void;
  /** Press-and-hold (touch) to inspect — pops the large card zoom. */
  onInspect?: (card: CardModel) => void;
  className?: string;
  /** Lift on hover via Motion (CSS :hover transform loses to Motion's layout). */
  lift?: boolean;
}

const TOKEN_NAMES = new Set(["Shield", "Experience"]);
const isToken = (c: CardModel) => c.card_type === "Token Upgrade" || TOKEN_NAMES.has(c.card_name);
const isUnitLike = (t: string) => t === "Unit" || t === "Leader";
// Leader & Base art is landscape (418×300); units are portrait (300×418).
const isLandscape = (t: string) => t === "Leader" || t === "Base";

function Tokens({ card }: { card: CardModel }) {
  const tokens = card.attached_upgrades.filter(isToken);
  if (!tokens.length) return null;
  return (
    <div className="tokens">
      {tokens.map((t, i) => (
        <div
          key={t.instance_id + i}
          className={`token ${t.card_name === "Shield" ? "shield" : "xp"}`}
          title={t.card_name}
        >
          {t.card_name === "Shield" ? "⛉" : "✦"}
        </div>
      ))}
    </div>
  );
}

// Attached upgrades peek out along the host's bottom edge as small art chips.
// Hovering a chip surfaces that upgrade in the zoom; hovering off it falls back
// to the host card so the zoom doesn't flicker to nothing.
function Upgrades({
  card,
  host,
  onHover,
}: {
  card: CardModel;
  host: CardModel;
  onHover?: (card: CardModel | null) => void;
}) {
  const ups = card.attached_upgrades.filter((u) => !isToken(u));
  if (!ups.length) return null;
  return (
    <div className="upgrades">
      {ups.map((u) => (
        <div
          key={u.instance_id}
          className="upgrade-chip"
          title={u.card_name}
          data-instance={u.instance_id}
          onMouseEnter={onHover ? () => onHover(u) : undefined}
          onMouseLeave={onHover ? () => onHover(host) : undefined}
        >
          {u.image_url ? (
            <img src={u.image_url} alt={u.card_name} draggable={false} />
          ) : (
            <span className="upgrade-chip-fallback">⬆</span>
          )}
        </div>
      ))}
    </div>
  );
}

const DEFEAT_EXIT = {
  opacity: 0,
  scale: 0.6,
  filter: "saturate(0) brightness(1.8)",
  rotate: -8,
  transition: { duration: 0.45 },
};
const SOFT_EXIT = { opacity: 0, scale: 0.9, transition: { duration: 0.3 } };

function CardInner({
  card,
  faceDown,
  highlight = null,
  defeated = false,
  onClick,
  onHover,
  onInspect,
  className = "",
  lift = false,
}: CardProps) {
  const { variantMode } = useSettings();
  // Press-and-hold to inspect (touch). Works on any card, even ones with no
  // available action — so a player can read opponent/board cards too.
  const { handlers: pressHandlers, consumeLongPress } = useLongPress(
    onInspect ? () => onInspect(card) : undefined,
  );
  const art = artFor(card, variantMode);
  // A deployed leader shows its unit (back) side if we have that art.
  const useBack = card.card_type === "Leader" && card.deployed && !!art.back;
  const src = useBack ? art.back : art.front;
  const hidden = faceDown || card.face_down || !src;
  const clickable =
    !!onClick &&
    (highlight === "legal" ||
      highlight === "target" ||
      highlight === "selected" ||
      highlight === "staged");
  // Leaders/Bases are landscape — but a deployed leader's *back* is its portrait
  // unit art, so don't apply the landscape (418/300) frame when showing it
  // (else object-fit:cover crops the unit side, hiding its ability text).
  const landscape = isLandscape(card.card_type) && !useBack;

  const classes = [
    "card",
    landscape ? "landscape" : "",
    isUnitLike(card.card_type) ? "unit" : "",
    card.card_type === "Leader" ? "leader" : "",
    card.exhausted ? "is-exhausted" : "",
    clickable ? "clickable" : "",
    highlight ? `hl-${highlight}` : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  const showStats = isUnitLike(card.card_type) && !hidden;
  const damaged = card.damage > 0;

  // Exhausted cards turn sideways. A rotated element keeps its upright layout
  // box, so a portrait unit would overhang its neighbours; scaling it down by
  // its aspect ratio makes the sideways footprint match the upright width.
  // Landscape cards (leaders/bases) get narrower when rotated, so no scaling.
  const exhaustScale = card.exhausted && !landscape ? 300 / 418 : 1;

  return (
    <motion.div
      layout
      layoutId={card.instance_id}
      className={classes}
      exit={defeated ? DEFEAT_EXIT : SOFT_EXIT}
      initial={{ opacity: 0, scale: 0.85 }}
      animate={{ opacity: 1, scale: exhaustScale, rotate: card.exhausted ? 90 : 0 }}
      whileHover={lift ? { y: -16, scale: 1.07, zIndex: 6 } : undefined}
      transition={{ type: "spring", stiffness: 520, damping: 34 }}
      onClick={
        clickable
          ? () => {
              // A press-and-hold inspect already handled this gesture — don't
              // also fire the card's action on the trailing click.
              if (consumeLongPress()) return;
              onClick?.(card);
            }
          : undefined
      }
      {...pressHandlers}
      onMouseEnter={onHover ? () => onHover(card) : undefined}
      onMouseLeave={onHover ? () => onHover(null) : undefined}
      data-instance={card.instance_id}
      data-card-name={hidden ? "[hidden]" : card.card_name}
    >
      {hidden ? (
        <div className="card-back" />
      ) : (
        <img className="card-img" src={src!} alt={card.card_name} draggable={false} />
      )}

      {/* Smuggle cost on your own (face-down) resource — base bracket cost + the
          red "+N" aspect-penalty surcharge, mirroring the hand-card pill. Shown
          even though the card is face-down (the cost is what matters here). */}
      {(card.smuggle_base ?? null) !== null && (
        <div
          className="smuggle-cost"
          title={`Smuggle cost: ${card.smuggle_base! + (card.smuggle_penalty ?? 0)}${
            (card.smuggle_penalty ?? 0) > 0
              ? ` (${card.smuggle_base} + ${card.smuggle_penalty} off-aspect)`
              : ""
          }`}
        >
          <span className="smuggle-base">{card.smuggle_base}</span>
          {(card.smuggle_penalty ?? 0) > 0 && (
            <span className="smuggle-pen">+{card.smuggle_penalty}</span>
          )}
        </div>
      )}

      {!hidden && damaged && <div className="dmg-counter">{card.damage}</div>}
      {!hidden && (card.aspect_penalty ?? 0) > 0 && (
        <div
          className="cost-penalty"
          title={`Aspect cost penalty: +${card.aspect_penalty} (off-aspect — costs ${card.cost + (card.aspect_penalty ?? 0)} to play)`}
        >
          +{card.aspect_penalty}
        </div>
      )}
      {!hidden && <Tokens card={card} />}
      {!hidden && <Upgrades card={card} host={card} onHover={onHover} />}

      {showStats && (
        <div className="card-stats">
          <span className="pip power">{card.effective_power}</span>
          <span className={`pip hp${damaged ? " damaged" : ""}`}>
            {Math.max(0, card.effective_hp - card.damage)}
          </span>
        </div>
      )}
    </motion.div>
  );
}

export const Card = memo(CardInner);
