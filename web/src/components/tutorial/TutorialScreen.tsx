import { useEffect, useState, type ReactNode } from "react";
import { CARDS, type CardKey, type TutCard } from "./tutorialDeck";
import { P, STEPS } from "./steps";
import "./tutorial.css";

const cx = (...xs: (string | false | undefined)[]) => xs.filter(Boolean).join(" ");

// Tiny inline markdown: **bold** and *italic* → <b>/<i>. Coach copy only.
function coachText(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g).map((p, k) => {
    if (p.startsWith("**") && p.endsWith("**")) return <b key={k}>{p.slice(2, -2)}</b>;
    if (p.startsWith("*") && p.endsWith("*")) return <i key={k}>{p.slice(1, -1)}</i>;
    return <span key={k}>{p}</span>;
  });
}

function Droid() {
  return (
    <svg className="tut-droid" viewBox="0 0 66 82" aria-hidden="true">
      <defs>
        <linearGradient id="tgold" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#f8dc7e" />
          <stop offset=".5" stopColor="#e0ad2f" />
          <stop offset="1" stopColor="#b07d18" />
        </linearGradient>
        <linearGradient id="tgoldh" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#fbe9a6" />
          <stop offset=".55" stopColor="#e6b53c" />
          <stop offset="1" stopColor="#a9781a" />
        </linearGradient>
      </defs>
      <ellipse cx="33" cy="79" rx="19" ry="3.2" fill="#00000033" />
      <path
        d="M17 80 L17 58 Q17 52 24 50 L42 50 Q49 52 49 58 L49 80 Z"
        fill="url(#tgold)"
        stroke="#8f6612"
        strokeWidth="1.4"
      />
      <circle cx="18" cy="56" r="6.2" fill="url(#tgoldh)" stroke="#8f6612" strokeWidth="1.4" />
      <circle cx="48" cy="56" r="6.2" fill="url(#tgoldh)" stroke="#8f6612" strokeWidth="1.4" />
      <rect
        x="26"
        y="55"
        width="14"
        height="10"
        rx="2.5"
        fill="#a9781a"
        stroke="#8f6612"
        strokeWidth="1"
      />
      <circle cx="33" cy="60" r="2.1" fill="#6e4f10" />
      <g stroke="#9aa2b0" strokeWidth="1.5" strokeLinecap="round">
        <line x1="26" y1="68" x2="26" y2="78" />
        <line x1="30" y1="68" x2="30" y2="78" />
        <line x1="34" y1="68" x2="34" y2="78" />
        <line x1="38" y1="68" x2="38" y2="78" />
      </g>
      <g stroke="#9aa2b0" strokeWidth="1.7" strokeLinecap="round">
        <line x1="29" y1="44" x2="29" y2="51" />
        <line x1="33" y1="44" x2="33" y2="51" />
        <line x1="37" y1="44" x2="37" y2="51" />
      </g>
      <path
        d="M33 6 Q47 7 47 26 Q47 39 33 44 Q19 39 19 26 Q19 7 33 6 Z"
        fill="url(#tgoldh)"
        stroke="#8f6612"
        strokeWidth="1.5"
      />
      <path d="M21 23 Q33 16 45 23" fill="none" stroke="#8f6612" strokeWidth="1.4" />
      <circle cx="27" cy="26" r="5.2" fill="#3a2c0e" />
      <circle cx="27" cy="26" r="3.1" fill="#fff4b8" />
      <circle cx="25.8" cy="24.8" r="1" fill="#fff" />
      <circle cx="39" cy="26" r="5.2" fill="#3a2c0e" />
      <circle cx="39" cy="26" r="3.1" fill="#fff4b8" />
      <circle cx="37.8" cy="24.8" r="1" fill="#fff" />
      <rect x="28" y="35" width="10" height="6" rx="1.5" fill="#5a4310" />
      <g stroke="#caa64a" strokeWidth=".9">
        <line x1="30.5" y1="35" x2="30.5" y2="41" />
        <line x1="33" y1="35" x2="33" y2="41" />
        <line x1="35.5" y1="35" x2="35.5" y2="41" />
      </g>
    </svg>
  );
}

// One card face (real art) + optional tutorial-state overlays.
function CardFace({
  card,
  id,
  deployedSide,
  className,
  onClick,
  children,
}: {
  card: TutCard;
  id?: string;
  deployedSide?: boolean;
  className?: string;
  onClick?: () => void;
  children?: ReactNode;
}) {
  const src = deployedSide ? (card.back ?? card.img) : card.img;
  return (
    <div
      id={id}
      className={cx("tut-card", card.landscape && "landscape", className)}
      onClick={onClick}
    >
      <img src={src} alt={card.name} draggable={false} />
      {card.arena && (
        <span className={cx("tut-atype", card.arena)}>{card.arena === "space" ? "✦" : "◊"}</span>
      )}
      {children}
    </div>
  );
}

export function TutorialScreen({ onExit }: { onExit: () => void }) {
  const [i, setI] = useState(0);
  const [picked, setPicked] = useState<CardKey[]>([]);
  const step = STEPS[i];
  const gate = step.gate;
  const lit = (elId: string) => (step.highlight.includes(elId) ? "tut-lit" : "");

  // ── board state derived purely from the step index (Back always works) ──
  const played = i >= P.PLAY;
  const trooperExh = played && i < P.REGROUP;
  const resExh = played && i < P.REGROUP;
  const guardGone = i >= P.ATTACK;
  const deployed = i >= P.DEPLOY;
  const initClaimed = i >= P.INIT;
  const rcount = i < P.RESCHOOSE ? 0 : i === P.RESCHOOSE ? picked.length : i >= P.REGROUP ? 3 : 2;
  const enemyHp = i >= P.WIN ? 0 : i >= P.ATTACK ? 28 : 30;
  const hitBase = i === P.ATTACK || i === P.WIN;

  const pickReady = gate.kind !== "pickResources" || picked.length === 2;
  const showNext = gate.kind !== "mulligan" && pickReady;
  const lastStep = i === STEPS.length - 1;
  const nextLabel = lastStep
    ? "Start playing ✦"
    : gate.kind === "pickResources"
      ? "Place resources ▶"
      : "Next ▶";

  function go(delta: number) {
    if (delta > 0 && gate.kind === "pickResources" && picked.length < 2) return;
    const n = i + delta;
    if (n < 0) return;
    if (n >= STEPS.length) return onExit();
    setI(n);
  }
  function pickCard(key: CardKey) {
    if (gate.kind !== "pickResources") return;
    setPicked((prev) => {
      if (prev.includes(key)) return prev.filter((k) => k !== key);
      if (prev.length >= 2) return prev;
      return [...prev, key];
    });
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") return onExit();
      if (e.key === "ArrowLeft") return go(-1);
      if ((e.key === "ArrowRight" || e.key === "Enter") && gate.kind !== "mulligan" && pickReady)
        go(1);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [i, picked]);

  const hpBadge = (hp: number) => (
    <span className="tut-hp">
      {hp}
      <small>/30</small>
    </span>
  );

  // hand cards: the two picked spares leave the hand once placed (i >= PLAY)
  const handCards: { key: CardKey; id?: string; spare?: boolean }[] = [
    { key: "snowtrooper", id: "handTrooper" },
    { key: "tie", id: "handTie" },
    { key: "rogue", id: "handRogue" },
    { key: "sp1", spare: true },
    { key: "sp2", spare: true },
    { key: "sp3", spare: true },
  ];

  return (
    <div className="tut-root">
      <div className="tut-topbar">
        <div className="tut-chip">
          <span>
            {i === 0 ? "Tutorial · Welcome" : `Tutorial · Step ${i} of ${STEPS.length - 1}`}
          </span>
          <span className="tut-dots">
            {STEPS.map((_, n) => (
              <i key={n} className={cx(n === i && "on", n < i && "done")} />
            ))}
          </span>
        </div>
        <button className="tut-skip" onClick={onExit}>
          Skip tutorial ✕
        </button>
      </div>

      <div
        className={cx("tut-inittoken", initClaimed && "claimed", lit("initToken"))}
        id="initToken"
      >
        <span className="itk">◆</span> Initiative
      </div>

      <div className="tut-board">
        {/* opponent */}
        <div className="tut-row" style={{ justifyContent: "space-between" }}>
          <span className="tut-side-label" style={{ top: 58 }}>
            Opponent
          </span>
          <CardFace card={CARDS.lukeLeader} />
          <div id="enemyBase" className={cx("tut-base", hitBase && "hit", lit("enemyBase"))}>
            <CardFace card={CARDS.adminTower} />
            {hpBadge(enemyHp)}
          </div>
          <div className="tut-res-stack">
            <div className="tut-back">⤾</div>
            <div className="tut-back">⤾</div>
            <span className="tut-res-count">Enemy hand</span>
          </div>
        </div>

        {/* arenas */}
        <div style={{ display: "grid", gridTemplateRows: "1fr 1fr", gap: 8 }}>
          <div id="groundArena" className={cx("tut-arena", lit("groundArena"))}>
            <span className="tut-arena-tag">◊ Ground Arena</span>
            <div className="tut-row">
              {!guardGone && (
                <CardFace card={CARDS.guard} id="enemyGuard" className={lit("enemyGuard")}>
                  <span className="tut-dmg" title="2 damage">
                    2
                  </span>
                </CardFace>
              )}
            </div>
            <div className="tut-row">
              {played && (
                <CardFace
                  card={CARDS.snowtrooper}
                  id="myTrooper"
                  className={cx(
                    trooperExh && "exh",
                    i === P.PLAY && "enter",
                    i === P.ATTACK && "lunge",
                    lit("myTrooper"),
                  )}
                >
                  {played && !trooperExh && i < P.ATTACK && (
                    <span className="tut-rdytag">Ready</span>
                  )}
                </CardFace>
              )}
              {deployed && (
                <CardFace
                  card={CARDS.vaderLeader}
                  id="myLeaderUnit"
                  deployedSide
                  className="enter"
                />
              )}
            </div>
            {i === P.REGROUP && (
              <div className="tut-regroup">
                <div className="t">↻ Regroup Phase</div>
                <div className="s">Ready all cards · Draw 2 · Add a resource</div>
              </div>
            )}
          </div>
          <div
            id="spaceArena"
            className={cx("tut-arena", lit("spaceArena"))}
            style={{ opacity: 0.55 }}
          >
            <span className="tut-arena-tag">✦ Space Arena</span>
            <div className="tut-row">
              <span style={{ color: "#4a5985", fontSize: 12 }}>— empty —</span>
            </div>
          </div>
        </div>

        {/* you */}
        <div className="tut-row" style={{ justifyContent: "space-between" }}>
          <span className="tut-side-label" style={{ bottom: 150 }}>
            You
          </span>
          <div className="tut-row" style={{ gap: 10 }}>
            {!deployed && (
              <CardFace card={CARDS.vaderLeader} id="myLeader" className={lit("myLeader")} />
            )}
            <div id="myBase" className="tut-base">
              <CardFace card={CARDS.commandCenter} />
              {hpBadge(30)}
            </div>
          </div>
          <div id="resources" className={cx("tut-res-stack", lit("resources"))}>
            {Array.from({ length: rcount }).map((_, n) => (
              <div key={n} className={cx("tut-back", resExh && n < 2 && "exh")}>
                R
              </div>
            ))}
            <span className="tut-res-count">
              {i === P.RESCHOOSE
                ? `${picked.length} / 2 chosen`
                : rcount === 0
                  ? ""
                  : resExh
                    ? "0 ready (2 used)"
                    : i >= P.REGROUP
                      ? "3 ready"
                      : "2 ready"}
            </span>
          </div>
          <div id="hand" className={cx("tut-row", lit("hand"))}>
            {handCards.map(({ key, id, spare }) => {
              if (key === "snowtrooper" && played) return null; // now in the arena
              if (spare && picked.includes(key) && i >= P.PLAY) return null; // now a resource
              const pickable = spare && gate.kind === "pickResources";
              const locked = !spare && gate.kind === "pickResources";
              return (
                <CardFace
                  key={key}
                  card={CARDS[key]}
                  id={id}
                  onClick={pickable ? () => pickCard(key) : undefined}
                  className={cx(
                    pickable && "pickable",
                    picked.includes(key) && "picked",
                    locked && "locked",
                    id && lit(id),
                  )}
                />
              );
            })}
          </div>
        </div>
      </div>

      <div className={cx("tut-dim", "show")} />
      <div className={cx("tut-winfx", lastStep && "show")} />

      {gate.kind === "mulligan" && (
        <div className="tut-mull">
          <button className="tut-mbtn keep" onClick={() => go(1)}>
            Keep hand ✓
          </button>
          <button className="tut-mbtn redraw" onClick={() => go(1)}>
            Mulligan ↺ (redraw once)
          </button>
        </div>
      )}

      <div className={cx("tut-coach", `pos-${step.pos}`)}>
        <Droid />
        <div className="tut-bubble">
          <div className="tut-who">{step.who ?? "C-3PO · Protocol Droid"}</div>
          <div className="tut-say">{coachText(step.coach)}</div>
        </div>
        <div className="tut-ctrl">
          {showNext && (
            <button className="tut-next" onClick={() => go(1)}>
              {nextLabel}
            </button>
          )}
          <button className="tut-back-btn" disabled={i === 0} onClick={() => go(-1)}>
            ◀ Back
          </button>
        </div>
      </div>
    </div>
  );
}
