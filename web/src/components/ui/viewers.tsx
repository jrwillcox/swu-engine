// Decision overlays: the screens that hold a game while a player looks at cards
// and chooses.  Each one renders real card art for a decision the engine has already
// scoped to that player, and routes the chosen action back out.
import { motion } from "motion/react";
import type { ActionModel, CardModel } from "../../api/types";

// Mulligan "moment": at the start of the game, hold the screen and show the
// opening hand large with a clear Keep / Mulligan choice, rather than letting the
// decision hide among the normal action buttons.
export function MulliganViewer({
  hand,
  actions,
  onAct,
}: {
  hand: CardModel[];
  actions: ActionModel[];
  onAct: (id: string) => void;
}) {
  const keep = actions.find((a) => a.kind === "KeepHand");
  const mull = actions.find((a) => a.kind === "TakeMultiligan");
  return (
    <div className="scrim">
      <motion.div
        className="modal panel mulligan-viewer"
        initial={{ opacity: 0, scale: 0.94, y: 14 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 300, damping: 26 }}
      >
        <h2>Your opening hand</h2>
        <p className="peek-prompt">
          Keep this hand, or take a mulligan to shuffle it back and draw a fresh six.
        </p>
        <div className="mulligan-hand">
          {hand.map((c) => (
            <div className="card" key={c.instance_id} data-card-name={c.card_name}>
              {c.image_url ? (
                <img className="card-img" src={c.image_url} alt={c.card_name} draggable={false} />
              ) : (
                <div className="card-back" />
              )}
            </div>
          ))}
        </div>
        <div className="peek-actions">
          {mull && (
            <button className="btn btn-danger" onClick={() => onAct(mull.action_id)}>
              Mulligan (redraw 6)
            </button>
          )}
          {keep && (
            <button className="btn btn-primary" onClick={() => onAct(keep.action_id)}>
              Keep this hand
            </button>
          )}
        </div>
      </motion.div>
    </div>
  );
}
export function DiscardViewer({
  cards,
  title,
  onClose,
}: {
  cards: CardModel[];
  title: string;
  onClose: () => void;
}) {
  return (
    <div className="scrim" onClick={onClose}>
      <div className="modal panel" onClick={(e) => e.stopPropagation()}>
        <h2>
          {title} ({cards.length})
        </h2>
        {cards.length === 0 ? (
          <p>Empty.</p>
        ) : (
          <div className="discard-grid">
            {cards.map((c) => (
              <div className="card" key={c.instance_id}>
                {c.image_url ? (
                  <img className="card-img" src={c.image_url} alt={c.card_name} />
                ) : (
                  <div className="card-back" />
                )}
              </div>
            ))}
          </div>
        )}
        <div style={{ marginTop: 18, textAlign: "right" }}>
          <button className="btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
// Top-of-deck peek (R2-D2 / C-3PO). The engine reveals the card only to the
// deciding player (it's their own deck), so we show it large and hold the screen
// until they choose — the card never just flashes past. The choice buttons live
// in the overlay so the decision is made right here, looking at the card.
const PEEK_LABEL: Record<string, string> = {
  may_bottom: "Look at the top card of your deck — keep it on top, or move it to the bottom.",
  may_draw: "The top card's cost matches your number — reveal and draw it, or leave it on top.",
  reveal_only: "The top card's cost doesn't match your number — it stays on top of your deck.",
};
export function PeekViewer({
  cardId,
  cardName,
  mode,
  actions,
  onAct,
}: {
  cardId: number;
  cardName: string;
  mode: string;
  actions: ActionModel[];
  onAct: (id: string) => void;
}) {
  const src = cardId >= 0 ? `/api/cards/${cardId}/image?face=front` : null;
  return (
    <div className="scrim">
      <motion.div
        className="modal panel peek-viewer"
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, scale: 0.92, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 320, damping: 26 }}
      >
        <h2>Top of your deck</h2>
        <p className="peek-prompt">{PEEK_LABEL[mode] ?? "Decide what to do with this card."}</p>
        <div className="peek-card card">
          {src ? (
            <img className="card-img" src={src} alt={cardName} draggable={false} />
          ) : (
            <div className="card-back" />
          )}
        </div>
        <div className="peek-name">{cardName}</div>
        <div className="peek-actions">
          {actions.map((a) => (
            <button
              key={a.action_id}
              className="btn btn-primary"
              onClick={() => onAct(a.action_id)}
            >
              {a.label}
            </button>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
// Reveal-and-reorder moment (For a Cause I Believe In, SOR_152). The engine
// reveals the top N cards only to the deciding player (their own deck), so we
// show them all large and resolve each in place — discard it, or keep it on top.
// The click order of "Keep" is the resulting top order (first kept is drawn
// first), so the player keeps full control of ordering by choosing the order
// they click. Replaces the spill-over row of opaque "keep human_41 on top"
// buttons with the actual cards.
export interface RevealedCard {
  instance_id: string;
  card_id: number;
  card_name: string;
}
export function RevealViewer({
  revealed,
  pending,
  keptOrder,
  actions,
  onAct,
}: {
  revealed: RevealedCard[];
  pending: string[];
  keptOrder: string[];
  actions: ActionModel[];
  onAct: (id: string) => void;
}) {
  const pendingSet = new Set(pending);
  const keptIndex = new Map(keptOrder.map((id, i) => [id, i + 1]));
  const actFor = (kind: string, id: string) =>
    actions.find((a) => a.kind === kind && a.params.card_id === id);
  const remaining = pending.length;
  return (
    <div className="scrim">
      <motion.div
        className="modal panel reveal-viewer"
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, scale: 0.94, y: 14 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 300, damping: 26 }}
      >
        <h2>Top {revealed.length} cards of your deck</h2>
        <p className="peek-prompt">
          Discard any you don't want; keep the rest. The order you keep them becomes the new top of
          your deck — the first card you keep is the next you'll draw.{" "}
          {remaining > 0 ? `${remaining} still to resolve.` : "All resolved — finishing up…"}
        </p>
        <div className="reveal-row">
          {revealed.map((c) => {
            const isPending = pendingSet.has(c.instance_id);
            const keptAt = keptIndex.get(c.instance_id);
            const status = isPending ? "pending" : keptAt ? "kept" : "discarded";
            const src = c.card_id >= 0 ? `/api/cards/${c.card_id}/image?face=front` : null;
            const keep = actFor("KeepRevealed", c.instance_id);
            const discard = actFor("DiscardRevealed", c.instance_id);
            return (
              <div className={`reveal-card ${status}`} key={c.instance_id}>
                <div className="reveal-card-img card">
                  {src ? (
                    <img className="card-img" src={src} alt={c.card_name} draggable={false} />
                  ) : (
                    <div className="card-back" />
                  )}
                  {status === "kept" && <span className="reveal-badge kept">Top #{keptAt}</span>}
                  {status === "discarded" && (
                    <span className="reveal-badge discarded">Discarded</span>
                  )}
                </div>
                <div className="reveal-card-name">{c.card_name}</div>
                {isPending && (
                  <div className="reveal-card-actions">
                    {keep && (
                      <button className="btn btn-primary" onClick={() => onAct(keep.action_id)}>
                        Keep on top
                      </button>
                    )}
                    {discard && (
                      <button className="btn btn-danger" onClick={() => onAct(discard.action_id)}>
                        Discard
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </motion.div>
    </div>
  );
}
// Look at an opponent's hand (Viper Probe Droid SOR_228 / SEC_239). The engine
// reveals the hand only to the inspecting player (carried in their redacted
// decision context), so we show the cards large and hold the screen until they
// acknowledge — instead of the old invisible no-op the player could never see.
export interface RevealedHandCard {
  card_id: number;
  card_name: string;
}
export function LookHandViewer({
  cards,
  action,
  onAct,
}: {
  cards: RevealedHandCard[];
  action: ActionModel | undefined;
  onAct: (id: string) => void;
}) {
  return (
    <div className="scrim">
      <motion.div
        className="modal panel reveal-viewer"
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, scale: 0.94, y: 14 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 300, damping: 26 }}
      >
        <h2>Opponent's hand ({cards.length})</h2>
        <p className="peek-prompt">
          {cards.length === 0
            ? "Your opponent's hand is empty."
            : "You're looking at your opponent's hand. Take note, then close."}
        </p>
        {cards.length > 0 && (
          <div className="reveal-row">
            {cards.map((c, i) => {
              const src = c.card_id >= 0 ? `/api/cards/${c.card_id}/image?face=front` : null;
              return (
                <div className="reveal-card" key={`${c.card_id}-${i}`}>
                  <div className="reveal-card-img card">
                    {src ? (
                      <img className="card-img" src={src} alt={c.card_name} draggable={false} />
                    ) : (
                      <div className="card-back" />
                    )}
                  </div>
                  <div className="reveal-card-name">{c.card_name}</div>
                </div>
              );
            })}
          </div>
        )}
        <div className="peek-actions">
          {action && (
            <button className="btn btn-primary" onClick={() => onAct(action.action_id)}>
              Done
            </button>
          )}
        </div>
      </motion.div>
    </div>
  );
}
// Generic "pick one of these cards" overlay for decisions whose candidate cards
// are NOT laid out as clickable board subjects — cards in the deck (deck_search:
// Greef Karga / tutors) or in the discard pile / a discard-played hand card
// (return_from_discard: Razor Crest; the Sarlacc recycle; Gideon's Light Cruiser
// playing from discard). Each candidate maps to a Select/Play action by its
// instance_id; an optional Finish button covers "up to N" / "you may" stops.
export interface CardCandidate {
  instance_id: string;
  card_id: number;
  card_name: string;
}
export function ChooseCardsViewer({
  title,
  prompt,
  candidates,
  actionForId,
  finish,
  finishLabel,
  onAct,
}: {
  title: string;
  prompt: string;
  candidates: CardCandidate[];
  actionForId: (instanceId: string) => ActionModel | undefined;
  finish: ActionModel | undefined;
  finishLabel: string;
  onAct: (id: string) => void;
}) {
  return (
    <div className="scrim">
      <motion.div
        className="modal panel reveal-viewer"
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, scale: 0.94, y: 14 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 300, damping: 26 }}
      >
        <h2>{title}</h2>
        <p className="peek-prompt">{prompt}</p>
        {candidates.length > 0 ? (
          <div className="reveal-row">
            {candidates.map((c) => {
              const action = actionForId(c.instance_id);
              const src = c.card_id >= 0 ? `/api/cards/${c.card_id}/image?face=front` : null;
              return (
                <div className="reveal-card" key={c.instance_id}>
                  <button
                    className="reveal-card-img card choose-card"
                    disabled={!action}
                    onClick={() => action && onAct(action.action_id)}
                    title={c.card_name}
                  >
                    {src ? (
                      <img className="card-img" src={src} alt={c.card_name} draggable={false} />
                    ) : (
                      <div className="card-back" />
                    )}
                  </button>
                  <div className="reveal-card-name">{c.card_name}</div>
                </div>
              );
            })}
          </div>
        ) : (
          <p>No eligible cards.</p>
        )}
        {finish && (
          <div className="peek-actions">
            <button className="btn btn-primary" onClick={() => onAct(finish.action_id)}>
              {finishLabel}
            </button>
          </div>
        )}
      </motion.div>
    </div>
  );
}
