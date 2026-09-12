// Deck Manager (Stage 4) — the "playlist" management surface for custom decks.
// A signed-in user makes, renames, and deletes their own decks and sees each
// deck's state (count/50, leader/base, a Complete/Draft pill, and the rule
// violations behind the pill's tooltip). It is an App-level full-screen mode
// (like the Card Explorer), reached from the start screen's "My decks" button.
//
// Opening a deck shows a read-only contents list for now; Stage 5 evolves this
// into an "add to deck" deep-link into the Card Explorer.
//
// Backend contract: src/swu/web/deckstore.py + the /api/decks/custom routes.
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../api/client";
import { ConfirmDialog } from "./ui";
import { DECK_SIZE } from "../game/deckbuild";
import type { CustomDeck, ExplorerCard } from "../api/types";

// A lookup from DB card id → its catalog card, so we can show names/costs/types
// for the leader, base, and pool entries (custom decks store ids, not names).
type CardMap = Map<number, ExplorerCard>;

export function DeckManager({ onBack }: { onBack: () => void }) {
  const [decks, setDecks] = useState<CustomDeck[] | null>(null);
  const [cardMap, setCardMap] = useState<CardMap>(() => new Map());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [newName, setNewName] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameText, setRenameText] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<CustomDeck | null>(null);

  // Load a deck's full record for every summary so the list can show badges and
  // the errors tooltip (the summary alone lacks leader/base ids + errors).
  const reload = useCallback(async () => {
    try {
      const summaries = await api.customDecks.list();
      const full = await Promise.all(summaries.map((s) => api.customDecks.get(s.id)));
      setDecks(full);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't load your decks.");
      setDecks([]);
    }
  }, []);

  useEffect(() => {
    void reload();
    // The catalog gives names/costs for the stored ids; best-effort (a failure
    // just shows "#<id>" fallbacks, never blocks the manager).
    api
      .catalog()
      .then((cat) => {
        const m: CardMap = new Map();
        for (const c of cat.cards) m.set(c.id, c);
        setCardMap(m);
      })
      .catch(() => {
        /* ignore — fall back to ids */
      });
  }, [reload]);

  async function createDeck() {
    const name = newName.trim();
    if (!name || busy) return;
    setBusy(true);
    setError(null);
    try {
      const deck = await api.customDecks.create(name);
      setNewName("");
      await reload();
      setSelectedId(deck.id); // open the fresh deck
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't create the deck.");
    } finally {
      setBusy(false);
    }
  }

  async function saveRename(id: string) {
    const name = renameText.trim();
    if (!name) {
      setRenamingId(null);
      return;
    }
    setError(null);
    try {
      await api.customDecks.patch(id, { name });
      setRenamingId(null);
      await reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't rename the deck.");
    }
  }

  async function doDelete(deck: CustomDeck) {
    setConfirmDelete(null);
    setError(null);
    try {
      await api.customDecks.delete(deck.id);
      if (selectedId === deck.id) setSelectedId(null);
      await reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't delete the deck.");
    }
  }

  const selected = useMemo(
    () => (decks ?? []).find((d) => d.id === selectedId) ?? null,
    [decks, selectedId],
  );

  return (
    <div className="explorer deck-manager">
      <div className="explorer-bar">
        <button className="btn" onClick={selected ? () => setSelectedId(null) : onBack}>
          ← Back
        </button>
        <h1 className="explorer-title">{selected ? selected.name : "My decks"}</h1>
        <span className="spacer" style={{ flex: 1 }} />
        {!selected && (
          <span className="explorer-deck-count">
            🃏 {decks ? decks.length : 0} deck{decks && decks.length === 1 ? "" : "s"}
          </span>
        )}
      </div>

      {error && <p className="deck-manager-error">{error}</p>}

      {selected ? (
        <DeckDetail deck={selected} cardMap={cardMap} />
      ) : (
        <>
          <div className="deck-new-row">
            <input
              className="seed-input"
              placeholder="New deck name…"
              aria-label="New deck name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void createDeck();
              }}
            />
            <button
              className="btn btn-primary"
              disabled={!newName.trim() || busy}
              onClick={createDeck}
            >
              {busy ? "Creating…" : "New deck"}
            </button>
          </div>

          <div className="deck-list scroll">
            {decks === null ? (
              <p className="deck-manager-empty">Loading…</p>
            ) : decks.length === 0 ? (
              <p className="deck-manager-empty">No decks yet. Name one above and hit “New deck”.</p>
            ) : (
              decks.map((d) =>
                renamingId === d.id ? (
                  <div key={d.id} className="deck-row editing">
                    <input
                      className="seed-input"
                      aria-label="Deck name"
                      value={renameText}
                      autoFocus
                      onChange={(e) => setRenameText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") void saveRename(d.id);
                        if (e.key === "Escape") setRenamingId(null);
                      }}
                    />
                    <div className="deck-row-actions">
                      <button className="btn btn-primary" onClick={() => saveRename(d.id)}>
                        Save
                      </button>
                      <button className="btn btn-ghost" onClick={() => setRenamingId(null)}>
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <DeckRow
                    key={d.id}
                    deck={d}
                    cardMap={cardMap}
                    onOpen={() => setSelectedId(d.id)}
                    onRename={() => {
                      setRenamingId(d.id);
                      setRenameText(d.name);
                    }}
                    onDelete={() => setConfirmDelete(d)}
                  />
                ),
              )
            )}
          </div>
        </>
      )}

      {confirmDelete && (
        <ConfirmDialog
          title="Delete deck?"
          message={`Permanently delete “${confirmDelete.name}”? This can't be undone.`}
          confirmLabel="Delete"
          onConfirm={() => doDelete(confirmDelete)}
          onCancel={() => setConfirmDelete(null)}
        />
      )}
    </div>
  );
}

function cardName(cardMap: CardMap, id: number | null): string {
  if (id == null) return "—";
  return cardMap.get(id)?.name ?? `#${id}`;
}

function DeckRow({
  deck,
  cardMap,
  onOpen,
  onRename,
  onDelete,
}: {
  deck: CustomDeck;
  cardMap: CardMap;
  onOpen: () => void;
  onRename: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="deck-row">
      <button className="deck-row-main" onClick={onOpen}>
        <span className="deck-row-title">{deck.name}</span>
        <span className="deck-row-sub">
          <span
            className={`deck-pill ${deck.complete ? "complete" : "draft"}`}
            title={deck.errors.length ? deck.errors.join("\n") : undefined}
          >
            {deck.complete ? "Complete" : "Draft"}
          </span>
          <span className="deck-count">
            {deck.count}/{deck.required ?? DECK_SIZE}
          </span>
          <span className="deck-badge" title="Leader">
            👑 {cardName(cardMap, deck.leader_id)}
          </span>
          <span className="deck-badge" title="Base">
            🛡 {cardName(cardMap, deck.base_id)}
          </span>
        </span>
      </button>
      <div className="deck-row-actions">
        <button className="btn btn-ghost" onClick={onRename} aria-label={`Rename ${deck.name}`}>
          Rename
        </button>
        <button className="btn btn-danger" onClick={onDelete} aria-label={`Delete ${deck.name}`}>
          Delete
        </button>
      </div>
    </div>
  );
}

// Read-only contents of an opened deck (Stage 5 turns this into add-mode). Groups
// the pool by name with a ×count, and shows the leader/base slots.
function DeckDetail({ deck, cardMap }: { deck: CustomDeck; cardMap: CardMap }) {
  const pool = Object.entries(deck.cards)
    .map(([id, count]) => ({
      id: Number(id),
      name: cardName(cardMap, Number(id)),
      count,
    }))
    .sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div className="deck-detail scroll">
      <div className="deck-detail-head">
        <span
          className={`deck-pill ${deck.complete ? "complete" : "draft"}`}
          title={deck.errors.length ? deck.errors.join("\n") : undefined}
        >
          {deck.complete ? "Complete" : "Draft"}
        </span>
        <span className="deck-count">
          {deck.count}/{deck.required ?? DECK_SIZE} cards
        </span>
      </div>

      {deck.errors.length > 0 && (
        <ul className="deck-errors">
          {deck.errors.map((e, i) => (
            <li key={i}>{e}</li>
          ))}
        </ul>
      )}

      <div className="deck-slots">
        <div className="deck-slot">
          <span className="deck-slot-label">Leader</span>
          <span className="deck-slot-name">{cardName(cardMap, deck.leader_id)}</span>
        </div>
        <div className="deck-slot">
          <span className="deck-slot-label">Base</span>
          <span className="deck-slot-name">{cardName(cardMap, deck.base_id)}</span>
        </div>
      </div>

      <h3 className="deck-pool-head">Deck ({deck.count})</h3>
      {pool.length === 0 ? (
        <p className="deck-manager-empty">No cards yet. Add them from the Card Explorer.</p>
      ) : (
        <ul className="deck-pool">
          {pool.map((c) => (
            <li key={c.id}>
              <span className="deck-pool-name">{c.name}</span>
              <span className="deck-pool-count">×{c.count}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
