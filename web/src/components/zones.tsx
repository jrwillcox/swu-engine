import { AnimatePresence } from "motion/react";
import type { CardModel, ZoneModel } from "../api/types";
import { Card, type Highlight } from "./Card";

export interface SlotFns {
  hl: (card: CardModel) => Highlight;
  onClick: (card: CardModel) => void;
  onHover: (card: CardModel | null) => void;
  /** Press-and-hold (touch) to inspect a card large. */
  onInspect?: (card: CardModel) => void;
  defeated: (card: CardModel) => boolean;
}

function renderCard(card: CardModel, slot: SlotFns, extra = "fill") {
  return (
    <Card
      key={card.instance_id}
      card={card}
      className={extra}
      highlight={slot.hl(card)}
      defeated={slot.defeated(card)}
      onClick={slot.onClick}
      onHover={slot.onHover}
      onInspect={slot.onInspect}
    />
  );
}

/** Generic face-down back (opponent hand / resources / deck / discard). */
export function Back({
  className,
  exhausted,
  landscape,
}: {
  className: string;
  exhausted?: boolean;
  landscape?: boolean;
}) {
  return (
    <div
      className={`card ${landscape ? "landscape" : ""} ${className} ${exhausted ? "is-exhausted" : ""}`}
    >
      <div className="card-back" />
    </div>
  );
}

export function ArenaBand({
  arena,
  label,
  oppUnits,
  myUnits,
  slot,
  isTargetZone,
}: {
  arena: "space" | "ground";
  label: string;
  oppUnits: CardModel[];
  myUnits: CardModel[];
  slot: SlotFns;
  isTargetZone: boolean;
}) {
  return (
    <div className={`arena ${arena} ${isTargetZone ? "is-target-zone" : ""}`} data-arena={arena}>
      <div className="arena-label">{label}</div>
      <div className="arena-rows">
        <div className="arena-units foe">
          <AnimatePresence>{oppUnits.map((c) => renderCard(c, slot))}</AnimatePresence>
        </div>
        <div className="arena-units mine">
          <AnimatePresence>{myUnits.map((c) => renderCard(c, slot))}</AnimatePresence>
        </div>
      </div>
    </div>
  );
}

export function BaseCluster({
  zone,
  mine,
  slot,
}: {
  zone: ZoneModel;
  mine: boolean;
  slot: SlotFns;
}) {
  const base = zone.base_zone.find((c) => c.card_type === "Base");
  const leaders = zone.base_zone.filter((c) => c.card_type === "Leader");
  const hpRemaining = base ? base.effective_hp - base.damage : 0;
  const hpFrac = base && base.effective_hp ? hpRemaining / base.effective_hp : 1;

  return (
    <div>
      <div className="zone-label">{mine ? "Your Base / Leader" : "Enemy Base / Leader"}</div>
      <div className="base-cluster">
        {base && (
          <div className="base-slot">
            {renderCard(base, slot)}
            <div className="base-hp-bar">
              <div
                className={`base-hp-fill ${hpFrac < 0.34 ? "low" : ""}`}
                style={{ width: `${Math.max(0, hpFrac * 100)}%` }}
              />
            </div>
            <div className="base-readout">{hpRemaining}</div>
          </div>
        )}
        <AnimatePresence>
          {leaders.map((l) => (
            <div className="base-slot" key={l.instance_id}>
              {renderCard(l, slot)}
            </div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}

// Resources stay face-down. For the player's OWN row we pass `slot` so a
// smuggleable resource (Smuggle keyword) lights up with a legal-glow ring and
// becomes clickable — the card-back is reused, but it now carries the highlight,
// click, and hover-zoom (the owner may inspect their own resources) wiring.
// Without a `slot` (the opponent's row) every resource is an anonymous back.
export function ResourceRow({
  zone,
  mine,
  slot,
}: {
  zone: ZoneModel;
  mine?: boolean;
  slot?: SlotFns;
}) {
  return (
    <div className="res-block">
      <div className="zone-label">Resources</div>
      <div className="resources">
        {zone.resources
          .slice(0, 12)
          .map((r, i) =>
            mine && slot ? (
              <Card
                key={r.instance_id}
                card={r}
                faceDown
                className="res-card"
                highlight={slot.hl(r)}
                onClick={slot.onClick}
                onHover={slot.onHover}
                onInspect={slot.onInspect}
              />
            ) : (
              <Back key={r.instance_id + i} className="res-card" exhausted={r.exhausted} />
            ),
          )}
        <span className="res-count">
          {zone.available_resources}/{zone.resource_count} ready
        </span>
        {zone.credits > 0 && (
          <span
            className="res-credits"
            title="Credit tokens — each can be spent to pay 1 less for a card."
          >
            🪙 {zone.credits}
          </span>
        )}
        {zone.has_force_token && (
          <span
            className="res-force-token"
            title="The Force is with you — spend it to use Force abilities."
          >
            ✨ Force
          </span>
        )}
      </div>
    </div>
  );
}

export function Pile({
  label,
  count,
  topCard,
  onClick,
  onHover,
}: {
  label: string;
  count: number;
  topCard?: CardModel | null;
  onClick?: () => void;
  onHover?: (card: CardModel | null) => void;
}) {
  return (
    <div className={`pile ${onClick ? "clickable" : ""}`} onClick={onClick}>
      <div className="zone-label">{label}</div>
      {topCard && topCard.image_url ? (
        // data-instance lets the hover zoom anchor to the top card's rect.
        <div
          className="card pile-card"
          data-instance={topCard.instance_id}
          onMouseEnter={onHover ? () => onHover(topCard) : undefined}
          onMouseLeave={onHover ? () => onHover(null) : undefined}
        >
          <img className="card-img" src={topCard.image_url} alt={topCard.card_name} />
        </div>
      ) : (
        <Back className="pile-card" />
      )}
      <div className="count">{count}</div>
    </div>
  );
}

export function MyHand({ zone, slot }: { zone: ZoneModel; slot: SlotFns }) {
  return (
    <div className="hand">
      <AnimatePresence>
        {zone.hand.map((c) => (
          <Card
            key={c.instance_id}
            card={c}
            className="fill"
            lift
            highlight={slot.hl(c)}
            onClick={slot.onClick}
            onHover={slot.onHover}
            onInspect={slot.onInspect}
          />
        ))}
      </AnimatePresence>
    </div>
  );
}

/** Compact opponent-hand indicator: a few fanned backs plus the live count. */
export function OppHand({ count }: { count: number }) {
  return (
    <div className="hand-chip">
      <div className="zone-label">Hand</div>
      <div className="hand-chip-cards">
        {Array.from({ length: Math.min(count, 6) }).map((_, i) => (
          <Back key={i} className="mini" />
        ))}
        <span className="hand-chip-count">{count}</span>
      </div>
    </div>
  );
}
