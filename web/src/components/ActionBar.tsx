import type { ActionModel } from "../api/types";

// Controls that deserve prominent styling.
const PRIMARY = new Set(["Pass", "KeepHand", "ExploitCommit", "ContinueAttack"]);
const DANGER = new Set(["TakeMultiligan", "DeclineTrigger", "DeclineAmbush", "DeclineTarget"]);

function variant(kind: string): string {
  if (PRIMARY.has(kind)) return "btn-primary";
  if (DANGER.has(kind)) return "btn-danger";
  return "";
}

// "Claim initiative" actually locks initiative for next round; when you already
// hold it, claiming keeps the opponent from taking it — show that intent.
function labelFor(a: ActionModel, initiativeHeld: boolean): string {
  if (a.kind === "ClaimInitiative" && initiativeHeld) return "Keep initiative";
  return a.label;
}

export interface ResourcingControls {
  staged: number;
  required: number;
  canConfirm: boolean;
  onConfirm: () => void;
  onClear: () => void;
}

export function ActionBar({
  awaiting,
  playing,
  prompt,
  controls,
  contextActions,
  selectedName,
  idleHint,
  initiativeHeld,
  resourcing,
  onAct,
  onSkip,
  onClearSelection,
}: {
  awaiting: string;
  playing: boolean;
  prompt: string | null;
  controls: ActionModel[];
  contextActions: ActionModel[];
  selectedName: string | null;
  idleHint: string;
  initiativeHeld: boolean;
  resourcing: ResourcingControls | null;
  onAct: (id: string) => void;
  onSkip: () => void;
  onClearSelection: () => void;
}) {
  if (awaiting === "bot" || playing) {
    return (
      <div className="action-bar">
        <div className="waiting">
          <span className="dot-pulse" />
          {playing ? "Resolving…" : "Opponent is thinking…"}
        </div>
        <span className="spacer" />
        {playing && (
          <span className="skip-hint" onClick={onSkip}>
            click board to skip ▶▶
          </span>
        )}
      </div>
    );
  }

  if (awaiting === "terminal") return null;

  const hint = prompt
    ? prompt
    : selectedName
      ? `Selected ${selectedName} — choose a target, or pick an action.`
      : idleHint;

  return (
    <div className={`action-bar ${prompt ? "attn" : ""}`}>
      <div className={`hint ${prompt ? "prompt" : ""}`} title={hint}>
        {hint}
      </div>
      <div className="action-buttons">
        {resourcing && (
          <>
            <button
              className="btn btn-primary"
              disabled={!resourcing.canConfirm}
              onClick={resourcing.onConfirm}
            >
              Confirm resources ({resourcing.staged}/{resourcing.required})
            </button>
            {resourcing.staged > 0 && (
              <button className="btn btn-ghost" onClick={resourcing.onClear}>
                Clear
              </button>
            )}
            <span style={{ width: 8 }} />
          </>
        )}
        {selectedName && (
          <>
            {contextActions.map((a) => (
              <button
                key={a.action_id}
                className={`btn ${variant(a.kind)}`}
                onClick={() => onAct(a.action_id)}
              >
                {a.label}
              </button>
            ))}
            <button className="btn btn-ghost" onClick={onClearSelection}>
              Cancel
            </button>
            <span style={{ width: 8 }} />
          </>
        )}
        {controls.map((a) => (
          <button
            key={a.action_id}
            className={`btn ${variant(a.kind)}`}
            onClick={() => onAct(a.action_id)}
          >
            {labelFor(a, initiativeHeld)}
          </button>
        ))}
      </div>
    </div>
  );
}
