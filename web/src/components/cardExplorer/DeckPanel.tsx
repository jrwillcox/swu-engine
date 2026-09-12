// The live deck rail shown while adding to a custom deck.
// The live deck rail shown in add mode: the deck's leader/base slots, running
// total (X/50) + remaining, and the pool listed "SET NUM · Name ×count".
import { DECK_SIZE } from "../../game/deckbuild";
import type { CustomDeck, ExplorerCard } from "../../api/types";
import type { CardKind } from "./model";

export function DeckPanel({
  deck,
  cardById,
  onRemovePool,
  onClearSlot,
}: {
  deck: CustomDeck | null;
  cardById: Map<number, ExplorerCard>;
  onRemovePool: (cardId: number) => void;
  onClearSlot: (kind: CardKind) => void;
}) {
  if (!deck) {
    return (
      <aside className="deck-panel">
        <p className="deck-manager-empty">Loading deck…</p>
      </aside>
    );
  }

  const target = deck.required ?? DECK_SIZE;
  const remaining = Math.max(0, target - deck.count);
  const leader = deck.leader_id != null ? cardById.get(deck.leader_id) : null;
  const base = deck.base_id != null ? cardById.get(deck.base_id) : null;
  const pool = Object.entries(deck.cards)
    .map(([id, count]) => {
      const c = cardById.get(Number(id));
      return {
        id: Number(id),
        count,
        name: c?.name ?? `#${id}`,
        code: c ? `${c.set_code} ${c.card_number}` : "",
      };
    })
    .sort((a, b) => a.name.localeCompare(b.name));

  return (
    <aside className="deck-panel">
      <div className="deck-panel-head">
        <span className="deck-panel-name" title={deck.name}>
          {deck.name}
        </span>
        <span
          className={`deck-pill ${deck.complete ? "complete" : "draft"}`}
          title={deck.errors.length ? deck.errors.join("\n") : undefined}
        >
          {deck.complete ? "Complete" : "Draft"}
        </span>
      </div>

      <div className="deck-panel-totals">
        <span className="deck-count">
          {deck.count}/{target}
        </span>
        <span className="meta">{remaining} to go</span>
      </div>

      <div className="deck-panel-slots">
        <SlotRow
          icon="👑"
          label="Leader"
          name={leader?.name ?? null}
          onClear={() => onClearSlot("leader")}
        />
        <SlotRow
          icon="🛡"
          label="Base"
          name={base?.name ?? null}
          onClear={() => onClearSlot("base")}
        />
      </div>

      <div className="deck-panel-pool scroll">
        {pool.length === 0 ? (
          <p className="deck-manager-empty">No cards yet — click ＋ on a card.</p>
        ) : (
          pool.map((p) => (
            <div className="deck-panel-row" key={p.id}>
              <span className="deck-panel-card">
                {p.code && <span className="deck-panel-code">{p.code}</span>}
                <span className="deck-panel-cname">{p.name}</span>
              </span>
              <span className="deck-panel-x">×{p.count}</span>
              <button
                className="deck-panel-del"
                onClick={() => onRemovePool(p.id)}
                aria-label={`Remove ${p.name}`}
              >
                −
              </button>
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
export function SlotRow({
  icon,
  label,
  name,
  onClear,
}: {
  icon: string;
  label: string;
  name: string | null;
  onClear: () => void;
}) {
  return (
    <div className="deck-panel-slot">
      <span className="deck-panel-slot-icon" title={label}>
        {icon}
      </span>
      <span className={`deck-panel-slot-name ${name ? "" : "empty"}`}>
        {name ?? `No ${label.toLowerCase()}`}
      </span>
      {name && (
        <button className="deck-panel-del" onClick={onClear} aria-label={`Clear ${label}`}>
          −
        </button>
      )}
    </div>
  );
}
