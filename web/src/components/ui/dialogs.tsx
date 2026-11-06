// Modal prompts and the settings panel.
import { useSettings, type Speed, type VariantMode } from "../../game/settings";

// A small "are you sure?" gate. Used to catch unlikely-intentional moves — e.g.
// attaching an upgrade to an *enemy* unit, which is legal but almost always a
// misclick (you'd be buffing your opponent). Rules-free: the caller decides when
// to raise it; this only renders the prompt and routes the two outcomes.
export function ConfirmDialog({
  title,
  message,
  confirmLabel,
  onConfirm,
  onCancel,
}: {
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="scrim" onClick={onCancel}>
      <div className="modal panel confirm-dialog" onClick={(e) => e.stopPropagation()}>
        <h2>{title}</h2>
        <p className="confirm-message">{message}</p>
        <div className="confirm-actions">
          <button className="btn btn-ghost" onClick={onCancel}>
            Cancel
          </button>
          <button className="btn btn-danger" onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
const VARIANT_MODES: { value: VariantMode; label: string; hint: string }[] = [
  {
    value: "standard",
    label: "standard",
    hint: "Always the normal printing's art.",
  },
  {
    value: "best",
    label: "best",
    hint: "The fanciest art each card has: showcase, then hyperspace foil, then hyperspace.",
  },
  {
    value: "random",
    label: "random",
    hint: "A random printing per card, all equally likely. Each card keeps its art for the whole game.",
  },
  {
    value: "lottery",
    label: "lottery",
    hint: "Mostly standard, with rare pulls of the fancy art — like opening packs.",
  },
];
// `onLeaveGame` is passed only during a game; it adds a "Leave game" button.
export function SettingsPanel({
  onClose,
  onLeaveGame,
}: {
  onClose: () => void;
  onLeaveGame?: () => void;
}) {
  const s = useSettings();
  const speeds: Speed[] = ["fast", "normal", "slow"];
  return (
    <div className="scrim" onClick={onClose}>
      <div className="settings-panel panel" onClick={(e) => e.stopPropagation()}>
        <h2 style={{ margin: 0 }}>Settings</h2>
        <div className="settings-row">
          <span>Animation speed</span>
          <div className="seg">
            {speeds.map((sp) => (
              <button
                key={sp}
                className={s.speed === sp ? "active" : ""}
                onClick={() => s.setSpeed(sp)}
              >
                {sp}
              </button>
            ))}
          </div>
        </div>
        <div className="settings-row">
          <span title="Which printing's art to show for each card.">Card art</span>
          <div className="seg">
            {VARIANT_MODES.map((m) => (
              <button
                key={m.value}
                title={m.hint}
                className={s.variantMode === m.value ? "active" : ""}
                onClick={() => s.setVariantMode(m.value)}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>
        <div className="settings-row">
          <span>Reduced motion</span>
          <input
            type="checkbox"
            checked={s.reducedMotion}
            onChange={(e) => s.setReducedMotion(e.target.checked)}
          />
        </div>
        <div className="settings-row">
          <span title="Show the Available filter and the Playable / Not-yet badges in the Card Explorer. Off by default — every printed card is playable.">
            Show card availability
          </span>
          <input
            type="checkbox"
            checked={s.showAvailability}
            onChange={(e) => s.setShowAvailability(e.target.checked)}
          />
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
          {onLeaveGame ? (
            <button className="btn btn-danger" onClick={onLeaveGame}>
              Leave game
            </button>
          ) : (
            <span />
          )}
          <button className="btn btn-primary" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
