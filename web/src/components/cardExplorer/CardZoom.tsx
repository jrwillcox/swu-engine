// The explorer's own card-detail overlay: bigger than the in-game CardZoom and
// showing the full stat block, printings and rules text.
import { useState } from "react";
import { useSettings } from "../../game/settings";
import type { ExplorerCard } from "../../api/types";
import { VARIANT_LABELS, ASPECT_COLOR } from "./model";
import type { Cell } from "./model";

export function CardZoom({
  card,
  cell,
  onClose,
  onAdd,
  onRemove,
}: {
  card: ExplorerCard;
  cell: Cell | null;
  onClose: () => void;
  onAdd: () => void;
  onRemove: () => void;
}) {
  const { showAvailability } = useSettings();
  // "" = standard art; otherwise a key into card.variants.
  const [variant, setVariant] = useState("");
  const [showBack, setShowBack] = useState(false);

  const variantTypes = Object.keys(card.variants ?? {});
  const variantImgs = variant ? card.variants?.[variant] : null;
  // A variant without its own back falls back to the standard back image.
  const frontUrl = variantImgs?.image_url ?? card.image_url;
  const backUrl = variantImgs?.back_image_url ?? card.back_image_url;
  const hasBack = !!backUrl;
  const imgUrl = showBack && hasBack ? backUrl : frontUrl;

  return (
    <div className="xzoom-backdrop" onClick={onClose}>
      <div className="xzoom panel" onClick={(e) => e.stopPropagation()}>
        <button className="xzoom-close" onClick={onClose} aria-label="Close">
          ✕
        </button>
        <div className="xzoom-art">
          {imgUrl ? (
            <img src={imgUrl} alt={card.name} draggable={false} />
          ) : (
            <div className="xtile-noimg">{card.name}</div>
          )}
          <div className="xzoom-art-ctl">
            {hasBack && (
              <button className="btn btn-ghost" onClick={() => setShowBack((b) => !b)}>
                {showBack ? "Show front" : "Show back ⟳"}
              </button>
            )}
            {variantTypes.length > 0 && (
              <label className="explorer-select">
                <span>Variant</span>
                <select value={variant} onChange={(e) => setVariant(e.target.value)}>
                  <option value="">Standard</option>
                  {variantTypes.map((v) => (
                    <option key={v} value={v}>
                      {VARIANT_LABELS[v] ?? v}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
        </div>
        <div className="xzoom-info">
          <h2>
            {card.name}
            {card.unique && (
              <span className="xzoom-unique" title="Unique">
                ◆
              </span>
            )}
          </h2>
          {card.subtitle && <div className="xzoom-sub">{card.subtitle}</div>}
          <div className="xzoom-meta">
            {card.set_code} {card.card_number} · {card.type}
            {card.rarity ? ` · ${card.rarity}` : ""}
          </div>

          <div className="xzoom-stats">
            {card.cost !== null && <Stat label="Cost" value={card.cost} />}
            {card.power !== null && <Stat label="Power" value={card.power} />}
            {card.hp !== null && <Stat label="HP" value={card.hp} />}
          </div>

          {card.aspects.length > 0 && (
            <div className="xzoom-chips">
              {card.aspects.map((a, i) => (
                <span
                  key={a + i}
                  className="chip aspect"
                  style={{ background: ASPECT_COLOR[a] ?? "#444", color: "#06101a" }}
                >
                  {a}
                </span>
              ))}
            </div>
          )}
          {card.keywords.length > 0 && (
            <div className="xzoom-chips">
              {card.keywords.map((k) => (
                <span key={k} className="chip">
                  {k}
                </span>
              ))}
            </div>
          )}
          {card.traits.length > 0 && (
            <div className="xzoom-chips">
              {card.traits.map((t) => (
                <span key={t} className="chip trait">
                  {t}
                </span>
              ))}
            </div>
          )}

          {showAvailability && (
            <div className={`xzoom-avail ${card.playable ? "ok" : "no"}`}>
              {card.playable ? "● Available to play" : `○ Not playable yet — ${card.status}`}
            </div>
          )}

          {cell && (
            <div className="xzoom-select">
              <span className="meta">In deck:</span>
              <button className="btn" onClick={onRemove} disabled={!cell.canRemove}>
                −
              </button>
              <span className="xzoom-count">{cell.count}</span>
              <button
                className="btn"
                onClick={onAdd}
                disabled={!cell.canAdd}
                title={cell.addTitle || undefined}
              >
                +
              </button>
              {cell.addTitle && !cell.canAdd && <span className="meta">({cell.addTitle})</span>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
export function Stat({ label, value }: { label: string; value: number }) {
  return (
    <span className="xzoom-stat">
      <span className="xzoom-stat-label">{label}</span>
      <span className="xzoom-stat-value">{value}</span>
    </span>
  );
}
