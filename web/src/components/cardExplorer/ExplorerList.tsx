// The "Details" view — one row per card, every column sortable.
// The "Details" view: one row per card with every stat the tile can't show, and
// a sortable heading on each column. The table scrolls in both directions inside
// its own box (sticky header) so a narrow screen/iPad can still reach the
// right-hand columns without the page itself scrolling.
import { useSettings } from "../../game/settings";
import type { ExplorerCard } from "../../api/types";
import { ASPECT_COLOR, codeOf } from "./model";
import type { SortKey, Sort, Cell } from "./model";

export function ExplorerList({
  cards,
  sort,
  onSort,
  cellFor,
  onOpen,
  onAdd,
  onRemove,
}: {
  cards: ExplorerCard[];
  sort: Sort;
  onSort: (key: SortKey) => void;
  cellFor: ((card: ExplorerCard) => Cell) | null;
  onOpen: (card: ExplorerCard) => void;
  onAdd: (card: ExplorerCard) => void;
  onRemove: (card: ExplorerCard) => void;
}) {
  const { showAvailability } = useSettings();

  const Th = ({ k, label, cls }: { k: SortKey; label: string; cls?: string }) => {
    const active = sort.key === k;
    return (
      <th
        className={`${cls ?? ""} ${active ? "sorted" : ""}`}
        aria-sort={active ? (sort.dir === 1 ? "ascending" : "descending") : "none"}
      >
        <button type="button" onClick={() => onSort(k)} title={`Sort by ${label}`}>
          <span>{label}</span>
          <span className="xlist-caret">{active ? (sort.dir === 1 ? "▲" : "▼") : ""}</span>
        </button>
      </th>
    );
  };

  return (
    <div className="explorer-list scroll">
      <table className="xlist">
        <thead>
          <tr>
            {cellFor && <th className="xlist-deck">Deck</th>}
            <Th k="code" label="Set №" cls="xlist-code-col" />
            <Th k="name" label="Name" />
            <Th k="subtitle" label="Subtitle" />
            <Th k="type" label="Type" />
            <Th k="arena" label="Arena" />
            <Th k="cost" label="Cost" cls="xlist-num" />
            <Th k="power" label="Power" cls="xlist-num" />
            <Th k="hp" label="HP" cls="xlist-num" />
            <Th k="aspects" label="Aspects" />
            <Th k="keywords" label="Keywords" />
            <Th k="traits" label="Traits" />
            <Th k="rarity" label="Rarity" />
            {showAvailability && <Th k="playable" label="Available" />}
          </tr>
        </thead>
        <tbody>
          {cards.map((c) => {
            const cell = cellFor ? cellFor(c) : null;
            return (
              <tr
                key={c.id}
                className={cell && cell.count > 0 ? "selected" : ""}
                onClick={() => onOpen(c)}
                title={`${c.name} — click for the card`}
              >
                {cell && (
                  <td className="xlist-deck" onClick={(e) => e.stopPropagation()}>
                    <span className="xtile-stepper">
                      <button
                        onClick={() => onRemove(c)}
                        disabled={!cell.canRemove}
                        aria-label={`Remove copy of ${c.name}`}
                      >
                        −
                      </button>
                      <span className="xlist-count">{cell.count || ""}</span>
                      <button
                        onClick={() => onAdd(c)}
                        disabled={!cell.canAdd}
                        title={cell.addTitle || undefined}
                        aria-label={`Add copy of ${c.name}`}
                      >
                        +
                      </button>
                    </span>
                  </td>
                )}
                <td className="xlist-code-col">{codeOf(c)}</td>
                <td className="xlist-name">
                  {c.name}
                  {c.unique && (
                    <span className="xlist-unique" title="Unique">
                      ◆
                    </span>
                  )}
                </td>
                <td className="xlist-sub">{c.subtitle ?? ""}</td>
                <td>{c.type}</td>
                <td>{c.arenas.join(" / ")}</td>
                <td className="xlist-num">{c.cost ?? ""}</td>
                <td className="xlist-num">{c.power ?? ""}</td>
                <td className="xlist-num">{c.hp ?? ""}</td>
                <td>
                  {c.aspects.map((a, i) => (
                    <span
                      key={a + i}
                      className="chip aspect"
                      style={{ background: ASPECT_COLOR[a] ?? "#444", color: "#06101a" }}
                    >
                      {a}
                    </span>
                  ))}
                </td>
                <td className="xlist-words" title={c.keywords.join(", ")}>
                  {c.keywords.join(", ")}
                </td>
                <td className="xlist-words" title={c.traits.join(", ")}>
                  {c.traits.join(", ")}
                </td>
                <td>{c.rarity ?? ""}</td>
                {showAvailability && (
                  <td className={`xlist-avail ${c.playable ? "ok" : "no"}`}>
                    {c.playable ? "● Playable" : "○ Not yet"}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
