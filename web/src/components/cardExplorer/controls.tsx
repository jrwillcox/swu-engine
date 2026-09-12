// The two filter inputs: a plain labelled <select>, and a checkbox dropdown for
// the filters that accept several values at once.
import { useEffect, useRef, useState } from "react";

export function Select({
  label,
  value,
  onChange,
  options,
  allowEmpty = true,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: [string, string][];
  allowEmpty?: boolean;
}) {
  return (
    <label className="explorer-select">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {allowEmpty && <option value="">Any</option>}
        {options.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
    </label>
  );
}
// A compact checkbox dropdown for filters that accept several values at once.
// Mirrors `Select`'s label/box styling (and its [value, label] option tuples, so
// value can differ from the shown text) but holds an array; the trigger shows a
// short summary ("Any" / the sole value's label / "N selected") and the popover
// closes on an outside click. Every explorer filter but Availability uses it.
export function MultiSelect({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: [string, string][];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const toggle = (v: string) =>
    onChange(selected.includes(v) ? selected.filter((x) => x !== v) : [...selected, v]);

  const labelOf = (v: string) => options.find(([val]) => val === v)?.[1] ?? v;
  const summary =
    selected.length === 0
      ? "Any"
      : selected.length === 1
        ? labelOf(selected[0])
        : `${selected.length} selected`;

  return (
    <div className="explorer-select explorer-multi" ref={ref}>
      <span>{label}</span>
      <button
        type="button"
        className="explorer-multi-btn"
        onClick={() => setOpen((o) => !o)}
        aria-label={label}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className={`explorer-multi-summary ${selected.length ? "" : "empty"}`}>
          {summary}
        </span>
        <span className="explorer-multi-caret">▾</span>
      </button>
      {open && (
        <div className="explorer-multi-pop scroll" role="listbox">
          <button
            type="button"
            className="explorer-multi-clear"
            disabled={selected.length === 0}
            onClick={() => onChange([])}
          >
            Clear ({selected.length})
          </button>
          {options.map(([value, text]) => (
            <label key={value} className="explorer-multi-opt">
              <input
                type="checkbox"
                checked={selected.includes(value)}
                onChange={() => toggle(value)}
              />
              <span>{text}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
