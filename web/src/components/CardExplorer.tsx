// The card-explorer screen: filters, the grid/details views, and add-to-deck mode.
//
// This file holds the screen's state and layout only. The pieces it composes live
// in ./cardExplorer/ — model.ts (labels, sorting, deck identity: no JSX, so the
// copy-limit and sort rules are testable on their own), controls.tsx (the two
// filter inputs), ExplorerList/ExplorerTile (the two result views), DeckPanel (the
// add-mode rail) and CardZoom (the explorer's own, larger card detail overlay —
// not the in-game one in ./ui).
import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import { ConfirmDialog, SettingsPanel } from "./ui";
import { useSettings } from "../game/settings";
import { DECK_SIZE, DEFAULT_MAX_COPIES } from "../game/deckbuild";
import type { CustomDeck, CustomDeckSummary, ExplorerCard, ExplorerResponse } from "../api/types";
import {
  PAGE,
  LIST_PAGE,
  VIEW_KEY,
  loadView,
  DEFAULT_SORT,
  compareCards,
  cardKind,
  groupKey,
  withPoolDelta,
} from "./cardExplorer/model";
import type { Availability, ViewMode, SortKey, Sort, CardKind, Cell } from "./cardExplorer/model";
import { CardZoom } from "./cardExplorer/CardZoom";
import { DeckPanel } from "./cardExplorer/DeckPanel";
import { ExplorerList } from "./cardExplorer/ExplorerList";
import { ExplorerTile } from "./cardExplorer/ExplorerTile";
import { MultiSelect, Select } from "./cardExplorer/controls";

export function CardExplorer({ onBack }: { onBack: () => void }) {
  const [data, setData] = useState<ExplorerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Filters. All but Availability are multi-select (OR within a filter, AND
  // across filters); each holds the selected values.
  const [search, setSearch] = useState("");
  const [sets, setSets] = useState<string[]>([]);
  const [deckFilters, setDeckFilters] = useState<string[]>([]);
  const [costs, setCosts] = useState<string[]>([]);
  const [aspects, setAspects] = useState<string[]>([]);
  const [arenas, setArenas] = useState<string[]>([]);
  const [keywords, setKeywords] = useState<string[]>([]);
  const [traits, setTraits] = useState<string[]>([]);
  const [types, setTypes] = useState<string[]>([]);
  const [avail, setAvail] = useState<Availability>("all");
  // "Available to play" is opt-in (Settings → Card availability): with it off the
  // filter and the per-card badges disappear entirely and nothing is hidden.
  const { showAvailability } = useSettings();
  const [showSettings, setShowSettings] = useState(false);

  // Thumbnails vs. the sortable details table, and that table's sort column.
  const [view, setView] = useState<ViewMode>(loadView);
  const [sort, setSort] = useState<Sort>(DEFAULT_SORT);

  const [visible, setVisible] = useState(PAGE);
  const [zoom, setZoom] = useState<ExplorerCard | null>(null);

  // ── add-to-deck mode ──────────────────────────────────────────────────────
  // The caller's custom decks (for the "Adding to" selector); the one currently
  // being edited (its id + freshly-loaded full record); and edit errors.
  const [myDecks, setMyDecks] = useState<CustomDeckSummary[]>([]);
  const [addDeckId, setAddDeckId] = useState<string | null>(null);
  const [deck, setDeck] = useState<CustomDeck | null>(null);
  const [addError, setAddError] = useState<string | null>(null);
  // A leader/base slot already occupied by a different card → confirm the swap.
  const [pendingSlot, setPendingSlot] = useState<{ kind: CardKind; card: ExplorerCard } | null>(
    null,
  );

  // Serialised writes: clicks are dispatched optimistically, then the delta/patch
  // is enqueued so requests apply in order. Only the latest write's server truth
  // (for the still-active deck) is committed, so intermediate optimistic state is
  // never clobbered by an out-of-order response.
  const writeChain = useRef<Promise<unknown>>(Promise.resolve());
  const seqRef = useRef(0);
  const activeDeckRef = useRef<string | null>(null);

  useEffect(() => {
    api
      .catalog()
      .then(setData)
      .catch((e) => setError(String(e)));
    // Best-effort: load the caller's decks for the selector. Guarded so the
    // explorer still works when the API surface is absent (unit tests) or the
    // user isn't signed in — the selector simply doesn't appear.
    const p = api.customDecks?.list?.();
    if (p) p.then(setMyDecks).catch(() => setMyDecks([]));
  }, []);

  // Load the full record whenever the selected deck changes.
  useEffect(() => {
    activeDeckRef.current = addDeckId;
    setAddError(null);
    if (addDeckId == null) {
      setDeck(null);
      return;
    }
    let alive = true;
    setDeck(null);
    api.customDecks
      .get(addDeckId)
      .then((d) => {
        if (alive) setDeck(d);
      })
      .catch((e) => {
        if (alive) setAddError(e instanceof ApiError ? e.message : "Couldn't load that deck.");
      });
    return () => {
      alive = false;
    };
  }, [addDeckId]);

  const cardById = useMemo(() => {
    const m = new Map<number, ExplorerCard>();
    for (const c of data?.cards ?? []) m.set(c.id, c);
    return m;
  }, [data]);

  // Distinct printed costs across the catalog, numerically sorted, for the Cost
  // filter's checkboxes. Cards with no cost (leaders/bases) contribute nothing.
  const costOptions = useMemo<[string, string][]>(() => {
    const seen = new Set<number>();
    for (const c of data?.cards ?? []) if (c.cost !== null) seen.add(c.cost);
    return [...seen].sort((a, b) => a - b).map((n) => [String(n), String(n)]);
  }, [data]);

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = search.trim().toLowerCase();
    // Each multi-select matches a card that has ANY of its selected values (OR),
    // EXCEPT Aspect, which is a SUBSET test: a card shows only if EVERY aspect it
    // carries is among the selected ones — so selecting Heroism + Cunning shows
    // cards that are only-Heroism, only-Cunning, or Heroism+Cunning, but NOT a
    // card that also has Villainy. Aspectless (neutral) cards have an empty set,
    // a subset of anything, so they always show. An empty filter matches
    // everything.
    return data.cards.filter((c) => {
      if (sets.length && !sets.includes(c.set_code)) return false;
      if (deckFilters.length && !deckFilters.some((d) => c.decks.includes(d))) return false;
      if (costs.length && (c.cost === null || !costs.includes(String(c.cost)))) return false;
      if (aspects.length && !c.aspects.every((a) => aspects.includes(a))) return false;
      if (arenas.length && !arenas.some((a) => c.arenas.includes(a))) return false;
      if (keywords.length && !keywords.some((k) => c.keywords.includes(k))) return false;
      if (traits.length && !traits.some((t) => c.traits.includes(t))) return false;
      if (types.length && !types.includes(c.type)) return false;
      if (showAvailability) {
        if (avail === "yes" && !c.playable) return false;
        if (avail === "no" && c.playable) return false;
      }
      if (q) {
        const hay = `${c.name} ${c.subtitle ?? ""} ${c.set_code} ${c.card_number}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [
    data,
    search,
    sets,
    deckFilters,
    costs,
    aspects,
    arenas,
    keywords,
    traits,
    types,
    avail,
    showAvailability,
  ]);

  // The details table is sorted; the grid keeps the catalog's own order.
  const rows = useMemo(
    () => (view === "list" ? [...filtered].sort((a, b) => compareCards(a, b, sort)) : filtered),
    [filtered, sort, view],
  );

  const pageSize = view === "list" ? LIST_PAGE : PAGE;

  // Reset the page window whenever the result set — or how much of it fits on a
  // page — changes.
  useEffect(() => setVisible(pageSize), [filtered, pageSize]);

  // Clicking a column heading sorts by it; clicking the active one flips it.
  const onSort = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: 1 }));

  const chooseView = (v: ViewMode) => {
    setView(v);
    try {
      localStorage.setItem(VIEW_KEY, v);
    } catch {
      /* private mode — the choice just doesn't persist */
    }
  };

  const addMode = addDeckId != null;

  // ── live custom-deck edits ────────────────────────────────────────────────
  const enqueue = (optimistic: (d: CustomDeck) => CustomDeck, call: () => Promise<CustomDeck>) => {
    const mySeq = ++seqRef.current;
    setAddError(null);
    setDeck((d) => (d ? optimistic(d) : d));
    writeChain.current = writeChain.current
      .then(call)
      .then((server) => {
        // Only the latest write, and only for the still-selected deck, wins.
        if (seqRef.current === mySeq && server.id === activeDeckRef.current) setDeck(server);
      })
      .catch((e) => {
        if (seqRef.current !== mySeq) return;
        setAddError(e instanceof ApiError ? e.message : "Couldn't update the deck.");
        // Re-sync from server truth after a failed optimistic edit.
        const id = activeDeckRef.current;
        if (id)
          return api.customDecks
            .get(id)
            .then((d) => setDeck(d))
            .catch(() => {});
      });
  };

  const poolDelta = (cardId: number, delta: number) =>
    enqueue(
      (d) => withPoolDelta(d, cardId, delta),
      () => api.customDecks.cards(addDeckId as string, cardId, delta),
    );

  const setSlot = (kind: CardKind, cardId: number | null) =>
    enqueue(
      (d) => (kind === "leader" ? { ...d, leader_id: cardId } : { ...d, base_id: cardId }),
      () =>
        api.customDecks.patch(
          addDeckId as string,
          kind === "leader" ? { leader_id: cardId } : { base_id: cardId },
        ),
    );

  const cellFor = (card: ExplorerCard): Cell => {
    if (!deck) return { count: 0, canAdd: false, canRemove: false, addTitle: "Loading…" };
    const nameKey = groupKey(card);
    const kind = cardKind(card);
    if (kind === "leader" || kind === "base") {
      const slotId = kind === "leader" ? deck.leader_id : deck.base_id;
      const here = slotId === card.id;
      return {
        count: here ? 1 : 0,
        canAdd: !here,
        canRemove: here,
        addTitle: here
          ? `Already your ${kind}`
          : slotId != null
            ? `Replace your ${kind}`
            : `Set as ${kind}`,
      };
    }
    // Cap by title+subtitle across printings: sum every pool entry whose card
    // shares this card's name+subtitle (a reprint), and use the group's highest
    // per-card override (matching the backend's max-over-the-group cap).
    let cap = card.deckbuild_max_copies ?? DEFAULT_MAX_COPIES;
    let groupCount = 0;
    for (const [id, n] of Object.entries(deck.cards)) {
      const c = cardById.get(Number(id));
      if (c && groupKey(c) === nameKey) {
        groupCount += n;
        cap = Math.max(cap, c.deckbuild_max_copies ?? DEFAULT_MAX_COPIES);
      }
    }
    const count = deck.cards[String(card.id)] ?? 0;
    // The pool target comes from the backend (it moves with the base — Data Vault
    // JTL_24 wants 60), never from the DECK_SIZE constant, which is only the
    // fallback for an older payload.
    const target = deck.required ?? DECK_SIZE;
    const poolFull = deck.count >= target;
    const atCap = groupCount >= cap;
    return {
      count,
      canAdd: !atCap && !poolFull,
      canRemove: count > 0,
      addTitle: atCap
        ? `Max ${cap} copies (incl. other printings)`
        : poolFull
          ? `Deck full (${target})`
          : "",
    };
  };

  const onAdd = (card: ExplorerCard) => {
    if (!deck) return;
    const kind = cardKind(card);
    if (kind === "pool") {
      poolDelta(card.id, +1);
      return;
    }
    const slotId = kind === "leader" ? deck.leader_id : deck.base_id;
    if (slotId === card.id) return; // already the slot card
    if (slotId != null) {
      setPendingSlot({ kind, card }); // occupied by a different card → confirm swap
      return;
    }
    setSlot(kind, card.id);
  };

  const onRemove = (card: ExplorerCard) => {
    if (!deck) return;
    const kind = cardKind(card);
    if (kind === "pool") {
      poolDelta(card.id, -1);
      return;
    }
    const slotId = kind === "leader" ? deck.leader_id : deck.base_id;
    if (slotId === card.id) setSlot(kind, null);
  };

  if (error) {
    return (
      <div className="explorer">
        <div className="explorer-bar">
          <button className="btn" onClick={onBack}>
            ← Back
          </button>
          <span style={{ color: "var(--danger)" }}>
            Could not load the card catalog ({error}). Is the backend running on :8000?
          </span>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="explorer">
        <div className="explorer-bar">
          <button className="btn" onClick={onBack}>
            ← Back
          </button>
          <span className="meta">Loading card catalog…</span>
        </div>
      </div>
    );
  }

  const resetFilters = () => {
    setSearch("");
    setSets([]);
    setDeckFilters([]);
    setCosts([]);
    setAspects([]);
    setArenas([]);
    setKeywords([]);
    setTraits([]);
    setTypes([]);
    setAvail("all");
    setSort(DEFAULT_SORT); // the list view's sort column is part of the row too
  };

  return (
    <div className="explorer">
      <div className="explorer-bar">
        <button className="btn" onClick={onBack}>
          ← Back
        </button>
        <h1 className="explorer-title">Card Explorer</h1>
        <input
          className="seed-input explorer-search"
          placeholder="Search name…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search cards"
        />
        {myDecks.length > 0 && (
          <label className="explorer-select explorer-addto">
            <span>Adding to</span>
            <select
              value={addDeckId ?? ""}
              onChange={(e) => setAddDeckId(e.target.value || null)}
              aria-label="Adding to deck"
            >
              <option value="">None (just browsing)</option>
              {myDecks.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} ({d.count}/{d.required ?? DECK_SIZE})
                </option>
              ))}
            </select>
          </label>
        )}
        <span className="spacer" style={{ flex: 1 }} />
        <button className="btn btn-ghost" onClick={() => setShowSettings(true)} title="Settings">
          ⚙
        </button>
      </div>
      {showSettings && <SettingsPanel onClose={() => setShowSettings(false)} />}

      <div className="explorer-filters">
        <MultiSelect
          label="Set"
          selected={sets}
          onChange={setSets}
          options={data.sets.map((s) => [s.code, `${s.code} — ${s.name}`])}
        />
        <MultiSelect
          label="Deck"
          selected={deckFilters}
          onChange={setDeckFilters}
          options={data.decks.map((d) => [d.key, d.label])}
        />
        <MultiSelect label="Cost" selected={costs} onChange={setCosts} options={costOptions} />
        <MultiSelect
          label="Aspect"
          selected={aspects}
          onChange={setAspects}
          options={data.aspects.map((a) => [a, a])}
        />
        <MultiSelect
          label="Arena"
          selected={arenas}
          onChange={setArenas}
          options={[
            ["Ground", "Ground"],
            ["Space", "Space"],
          ]}
        />
        <MultiSelect
          label="Keyword"
          selected={keywords}
          onChange={setKeywords}
          options={data.keywords.map((k) => [k, k])}
        />
        <MultiSelect
          label="Trait"
          selected={traits}
          onChange={setTraits}
          options={data.traits.map((t) => [t, t])}
        />
        <MultiSelect
          label="Type"
          selected={types}
          onChange={setTypes}
          options={data.types.map((t) => [t, t])}
        />
        {showAvailability && (
          <Select
            label="Available"
            value={avail}
            onChange={(v) => setAvail(v as Availability)}
            options={[
              ["all", "All"],
              ["yes", "Available to play"],
              ["no", "Not yet"],
            ]}
            allowEmpty={false}
          />
        )}
        <button className="btn btn-ghost" onClick={resetFilters}>
          Reset
        </button>
        <div className="explorer-view" role="group" aria-label="View">
          <button
            type="button"
            className={view === "grid" ? "active" : ""}
            aria-pressed={view === "grid"}
            onClick={() => chooseView("grid")}
            title="Card thumbnails"
          >
            ▦ Cards
          </button>
          <button
            type="button"
            className={view === "list" ? "active" : ""}
            aria-pressed={view === "list"}
            onClick={() => chooseView("list")}
            title="Sortable details list"
          >
            ☰ List
          </button>
        </div>
      </div>

      {addError && <p className="deck-manager-error">{addError}</p>}

      <div className="explorer-body">
        <div className="explorer-main">
          <div className="explorer-count meta">
            {rows.length} card{rows.length === 1 ? "" : "s"}
            {rows.length > visible ? ` (showing ${visible})` : ""}
          </div>

          {view === "grid" ? (
            <div className="explorer-grid scroll">
              {rows.slice(0, visible).map((c) => (
                <ExplorerTile
                  key={c.id}
                  card={c}
                  cell={addMode ? cellFor(c) : null}
                  onOpen={() => setZoom(c)}
                  onAdd={() => onAdd(c)}
                  onRemove={() => onRemove(c)}
                />
              ))}
            </div>
          ) : (
            <ExplorerList
              cards={rows.slice(0, visible)}
              sort={sort}
              onSort={onSort}
              cellFor={addMode ? cellFor : null}
              onOpen={setZoom}
              onAdd={onAdd}
              onRemove={onRemove}
            />
          )}

          {rows.length > visible && (
            <div className="explorer-more">
              <button className="btn" onClick={() => setVisible((v) => v + pageSize)}>
                Load more ({rows.length - visible} remaining)
              </button>
            </div>
          )}
        </div>

        {addMode && (
          <DeckPanel
            deck={deck}
            cardById={cardById}
            onRemovePool={(id) => poolDelta(id, -1)}
            onClearSlot={(kind) => setSlot(kind, null)}
          />
        )}
      </div>

      {zoom && (
        <CardZoom
          key={zoom.id}
          card={zoom}
          cell={addMode ? cellFor(zoom) : null}
          onClose={() => setZoom(null)}
          onAdd={() => onAdd(zoom)}
          onRemove={() => onRemove(zoom)}
        />
      )}

      {pendingSlot && (
        <ConfirmDialog
          title={`Replace your ${pendingSlot.kind}?`}
          message={`This deck already has a ${pendingSlot.kind}. Replace it with “${pendingSlot.card.name}”?`}
          confirmLabel="Replace"
          onConfirm={() => {
            const { kind, card } = pendingSlot;
            setPendingSlot(null);
            setSlot(kind, card.id);
          }}
          onCancel={() => setPendingSlot(null)}
        />
      )}
    </div>
  );
}
