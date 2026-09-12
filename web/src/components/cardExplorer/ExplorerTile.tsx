// One card thumbnail in the grid view.
import { useSettings } from "../../game/settings";
import type { ExplorerCard } from "../../api/types";
import type { Cell } from "./model";

export function ExplorerTile({
  card,
  cell,
  onOpen,
  onAdd,
  onRemove,
}: {
  card: ExplorerCard;
  cell: Cell | null;
  onOpen: () => void;
  onAdd: () => void;
  onRemove: () => void;
}) {
  const { showAvailability } = useSettings();
  return (
    <div className={`xtile ${cell && cell.count > 0 ? "selected" : ""}`}>
      <button className="xtile-img" onClick={onOpen} title={card.name}>
        {card.image_url ? (
          <img src={card.image_url} alt={card.name} loading="lazy" draggable={false} />
        ) : (
          <div className="xtile-noimg">{card.name}</div>
        )}
        {showAvailability && (
          <span
            className={`xtile-badge ${card.playable ? "ok" : "no"}`}
            title={card.playable ? "Available to play" : `Not playable yet (${card.status})`}
          >
            {card.playable ? "● Playable" : "○ Not yet"}
          </span>
        )}
        {cell && cell.count > 0 && <span className="xtile-count">×{cell.count}</span>}
      </button>
      <div className="xtile-foot">
        <span className="xtile-code">
          {card.set_code} {card.card_number}
        </span>
        {cell && (
          <span className="xtile-stepper">
            <button onClick={onRemove} disabled={!cell.canRemove} aria-label="Remove copy">
              −
            </button>
            <button
              onClick={onAdd}
              disabled={!cell.canAdd}
              title={cell.addTitle || undefined}
              aria-label="Add copy"
            >
              +
            </button>
          </span>
        )}
      </div>
    </div>
  );
}
