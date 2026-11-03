import { useEffect, useMemo, useState } from "react";
import type { ActionModel, CardModel } from "../api/types";
import type { Game } from "../game/useGame";
import { BASE_TARGET, buildInteraction, targetOf, targetsForSubject } from "../game/interaction";
import { playmatBackground, playmatFor } from "../playmats/playmats";
import type { Highlight } from "./Card";
import { ActionBar } from "./ActionBar";
import { EffectsLayer } from "./EffectsLayer";
import { ArenaBand, BaseCluster, MyHand, OppHand, Pile, ResourceRow, type SlotFns } from "./zones";
import {
  type CardCandidate,
  CardZoom,
  ChooseCardsViewer,
  ConfirmDialog,
  DiscardViewer,
  EndScreen,
  Hud,
  LookHandViewer,
  MulliganViewer,
  PeekViewer,
  type RevealedCard,
  type RevealedHandCard,
  RevealViewer,
  SettingsPanel,
  Toast,
  TurnGate,
} from "./ui";
import { api } from "../api/client";

// Top-of-deck peek actions (R2-D2 / C-3PO) — surfaced in their own overlay.
const PEEK_KINDS = new Set(["KeepTopCard", "BottomTopCard", "DrawTopCard"]);

function leaderName(cards: CardModel[]): string | undefined {
  return cards.find((c) => c.card_type === "Leader")?.card_name;
}

export function Table({ game, onToggleLog }: { game: Game; onToggleLog?: () => void }) {
  const {
    snapshot,
    active,
    defeated,
    locked,
    playing,
    act,
    skipAnimations,
    reset,
    save,
    gameId,
    resourceCards,
    turnGate,
    dismissTurnGate,
  } = game;
  const [selected, setSelected] = useState<string | null>(null);
  const [hover, setHover] = useState<CardModel | null>(null);
  // Long-press inspect target (touch). Separate from hover so a desktop mouse
  // and a touch hold never fight over the same overlay.
  const [inspected, setInspected] = useState<CardModel | null>(null);
  const [discardView, setDiscardView] = useState<null | "mine" | "opp">(null);
  const [showSettings, setShowSettings] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  // Two-stage resourcing: hand cards picked but not yet committed.
  const [staged, setStaged] = useState<string[]>([]);

  async function quickSave() {
    const slot = await save("quicksave");
    setToast(slot ? "Game saved — resume it from the start screen." : "Save failed.");
  }

  async function exportReplay() {
    if (!gameId) return;
    try {
      const bundle = await api.exportReplay(gameId);
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `swu-replay-${gameId}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setToast("Replay exported.");
    } catch {
      setToast("Export failed.");
    }
  }
  const [confirm, setConfirm] = useState<{
    action: ActionModel;
    upgradeName: string;
    targetName: string;
  } | null>(null);

  const view = snapshot!.view;
  const awaiting = snapshot!.awaiting;
  const interactive = awaiting === "human" && !locked;

  const inter = useMemo(
    () => buildInteraction(interactive ? snapshot!.actions : []),
    [snapshot, interactive],
  );

  useEffect(() => {
    if (selected && !inter.subjects.has(selected)) setSelected(null);
  }, [inter, selected]);

  // Two-stage resourcing. During SETUP_RESOURCES / REGROUP every eligible hand
  // card is its own ResourceCard action; instead of committing on click we stage
  // locally and dispatch the batch on Confirm (see useGame.resourceCards).
  const resourceActions = useMemo(
    () => (interactive ? snapshot!.actions.filter((a) => a.kind === "ResourceCard") : []),
    [snapshot, interactive],
  );
  const resourceableIds = useMemo(
    () => new Set(resourceActions.map((a) => a.params.instance_id as string)),
    [resourceActions],
  );
  const isResourcing =
    resourceActions.length > 0 && (view.phase === "SETUP_RESOURCES" || view.phase === "REGROUP");
  const requiredResources = view.phase === "SETUP_RESOURCES" ? 2 : 1;

  // Drop staged ids that are no longer eligible (phase change / server resync).
  useEffect(() => {
    if (!isResourcing) {
      setStaged((prev) => (prev.length ? [] : prev));
      return;
    }
    setStaged((prev) => {
      const next = prev.filter((id) => resourceableIds.has(id));
      return next.length === prev.length ? prev : next;
    });
  }, [isResourcing, resourceableIds]);

  function confirmResources() {
    if (staged.length !== requiredResources) return;
    const ids = staged;
    setStaged([]);
    resourceCards(ids);
  }

  const oppBaseId = view.opponent.base_zone.find((c) => c.card_type === "Base")?.instance_id;

  // A pending "look at the top card" decision the human owns: show the revealed
  // card in its own overlay so it can be studied before choosing.
  const topDecision = view.pending_decisions.slice(-1)[0];
  const peek =
    interactive && topDecision?.kind === "peek_top" && topDecision.is_mine ? topDecision : null;
  const peekActions = peek ? snapshot!.actions.filter((a) => PEEK_KINDS.has(a.kind)) : [];

  // A pending "reveal the top N, discard any, keep the rest on top in the order
  // you choose" decision (For a Cause I Believe In). Show the revealed cards in
  // their own overlay so the player resolves each by looking at the card.
  const reveal =
    interactive && topDecision?.kind === "reveal_top" && topDecision.is_mine ? topDecision : null;
  const revealActions = reveal
    ? snapshot!.actions.filter((a) => a.kind === "KeepRevealed" || a.kind === "DiscardRevealed")
    : [];

  // "Look at an opponent's hand" (Viper Probe Droid) — the engine carries the
  // revealed hand only in the inspecting player's context, so show it here.
  const lookHand =
    interactive && topDecision?.kind === "look_hand" && topDecision.is_mine ? topDecision : null;
  const lookHandAck = lookHand
    ? snapshot!.actions.find((a) => a.kind === "AckLookHand")
    : undefined;

  // Generic "pick a card you can't click on the board" overlay (cards in the
  // deck or discard pile). Maps each decision kind to its candidate list, the
  // Select/Play action kind, and an optional Finish/decline action.
  const chooser = (() => {
    if (!interactive || !topDecision?.is_mine) return null;
    const ctx = topDecision.context as Record<string, unknown>;
    const acts = snapshot!.actions;
    const findFinish = (kind: string) => acts.find((a) => a.kind === kind);
    const ctxCandidates = (ctx.candidates as CardCandidate[] | undefined) ?? [];
    type Cfg = {
      title: string;
      prompt: string;
      candidates: CardCandidate[];
      pickKind: string;
      finish?: ActionModel;
      finishLabel: string;
    };
    switch (topDecision.kind) {
      case "deck_search":
        return {
          title: "Search your deck",
          prompt: "Take a revealed card. The rest go to the bottom of your deck.",
          candidates: ctxCandidates,
          pickKind: "SelectSearchCard",
          finish: findFinish("FinishSearch"),
          finishLabel: "Finish (bottom the rest)",
        } as Cfg;
      case "return_from_discard":
        return {
          title: "Return from discard",
          prompt: "Return eligible cards from your discard pile to your hand.",
          candidates: ctxCandidates,
          pickKind: "SelectDiscardCard",
          finish: findFinish("FinishReturnFromDiscard"),
          finishLabel: "Done",
        } as Cfg;
      case "resource_from_discard":
        return {
          title: "Resource from discard",
          prompt: "Choose a card in your discard pile to put into play as a resource.",
          candidates: ctxCandidates,
          pickKind: "SelectResourceFromDiscard",
          finish: findFinish("DeclineResourceFromDiscard"),
          finishLabel: "Decline",
        } as Cfg;
      case "bottom_from_discard":
        return {
          title: "Choose from a discard pile",
          prompt: "Pick cards one at a time, then finish.",
          candidates: ctxCandidates,
          pickKind: "SelectBottomDiscardCard",
          finish: findFinish("FinishBottomFromDiscard"),
          finishLabel: "Done",
        } as Cfg;
      case "select_distinct_return_random":
        return {
          title: "Choose from your discard",
          prompt: "Pick cards with different names — one of them returns to your hand at random.",
          candidates: ctxCandidates,
          pickKind: "SelectDistinctDiscardCard",
          finishLabel: "",
        } as Cfg;
      case "play_captured_card":
        return {
          title: "Play a captured card",
          prompt: "Choose a card captured by one of your units to play for free.",
          candidates: ctxCandidates,
          pickKind: "SelectCapturedToPlay",
          finish: findFinish("DeclineCapturedPlay"),
          finishLabel: "Decline",
        } as Cfg;
      case "recur_and_buff":
        if (ctx.stage !== "recur") return null; // the buff targets are on-board
        return {
          title: "Recycle units from your discard",
          prompt: "Put units from your discard pile on the bottom of your deck, then finish.",
          candidates: ctxCandidates,
          pickKind: "SelectRecurUnit",
          finish: findFinish("FinishRecur"),
          finishLabel: "Done",
        } as Cfg;
      case "cull_for_damage":
        if (ctx.stage !== "select") return null; // the damage target is on-board
        return {
          title: ctx.pool === "hand" ? "Discard for damage" : "Defeat tokens for damage",
          prompt:
            ctx.pool === "hand"
              ? "Discard any number of cards from your hand — you deal that many damage."
              : "Defeat any number of your tokens — you deal that many damage.",
          candidates: ctxCandidates,
          pickKind: "SelectCullCard",
          finish: findFinish("FinishCull"),
          finishLabel: "Done",
        } as Cfg;
      case "discard_unit_damage":
        if (ctx.stage !== "select") return null; // the damage target is on-board
        return {
          title: "Recycle a unit from your discard",
          prompt:
            "Put a unit from your discard pile on the bottom of your deck — it deals its power as damage.",
          candidates: ctxCandidates,
          pickKind: "SelectDiscardUnitForDamage",
          finishLabel: "",
        } as Cfg;
      case "play_from_hand": {
        const discardCands = (ctx.discard_candidates as CardCandidate[] | undefined) ?? [];
        if (discardCands.length === 0) return null; // hand-only: board click works
        // Show every candidate (hand + discard) in one place; resolve hand-card
        // identities from the in-view hand so they render alongside discard ones.
        const playActs = acts.filter((a) => a.kind === "PlayFromHand");
        const handById = new Map(view.my.hand.map((c) => [c.instance_id, c]));
        const candidates: CardCandidate[] = playActs.map((a) => {
          const id = a.params.instance_id as string;
          const fromDiscard = discardCands.find((c) => c.instance_id === id);
          if (fromDiscard) return fromDiscard;
          const h = handById.get(id);
          return {
            instance_id: id,
            card_id: h?.card_id ?? -1,
            card_name: h?.card_name ?? "Unknown card",
          };
        });
        return {
          title: "Play a unit for free",
          prompt: "Play one of these units from your hand or discard pile.",
          candidates,
          pickKind: "PlayFromHand",
          finishLabel: "",
        } as Cfg;
      }
      default:
        return null;
    }
  })();

  const selTargets = useMemo(() => {
    const out = new Map<string, ActionModel>();
    if (!selected) return out;
    targetsForSubject(inter, selected).forEach((a, k) => {
      out.set(k === BASE_TARGET ? (oppBaseId ?? k) : k, a);
    });
    return out;
  }, [selected, inter, oppBaseId]);

  const enemyUnitIds = useMemo(
    () =>
      new Set(
        [...view.opponent.ground_arena, ...view.opponent.space_arena].map((c) => c.instance_id),
      ),
    [view],
  );

  function cardOf(id: string | undefined): CardModel | undefined {
    if (!id) return undefined;
    const all = [
      ...view.my.ground_arena,
      ...view.my.space_arena,
      ...view.my.hand,
      ...view.my.resources,
      ...view.my.base_zone,
      ...view.opponent.ground_arena,
      ...view.opponent.space_arena,
    ];
    return all.find((c) => c.instance_id === id);
  }

  function nameOf(id: string | undefined): string {
    return cardOf(id)?.card_name ?? "a unit";
  }

  // An upgrade is "beneficial" only if it grants a net-positive stat line. A
  // net-neutral upgrade (no stat bonus — e.g. a Bounty or control upgrade) is the
  // one kind that legitimately belongs on an enemy unit, so it skips the confirm.
  function isBeneficialUpgrade(id: string | undefined): boolean {
    const c = cardOf(id);
    if (!c) return true; // unknown — keep the safety prompt
    return (c.upgrade_power ?? 0) > 0 || (c.upgrade_hp ?? 0) > 0;
  }

  // Dispatch an action, gating the easy-to-misclick case: attaching a
  // *beneficial* upgrade to an *enemy* unit. That's legal (CR allows upgrades on
  // enemy units) but almost always unintended — so we confirm first instead of
  // acting outright. A net-neutral upgrade (Bounty/control) on an enemy is the
  // intended play, so it is not gated.
  function requestAct(a: ActionModel) {
    const targetId =
      a.kind === "PlayCard" || a.kind === "SmugglePlay"
        ? (a.params.upgrade_target_id as string | undefined)
        : undefined;
    if (
      targetId &&
      enemyUnitIds.has(targetId) &&
      isBeneficialUpgrade(a.params.instance_id as string | undefined)
    ) {
      setConfirm({
        action: a,
        upgradeName: nameOf(a.params.instance_id as string | undefined),
        targetName: nameOf(targetId),
      });
      return;
    }
    setSelected(null);
    act(a.action_id);
  }

  function hl(card: CardModel): Highlight {
    if (!interactive) return null;
    if (isResourcing) {
      if (staged.includes(card.instance_id)) return "staged";
      if (resourceableIds.has(card.instance_id)) return "legal";
      return null;
    }
    if (selected) {
      if (card.instance_id === selected) return "selected";
      if (selTargets.has(card.instance_id)) return "target";
      return null;
    }
    if (inter.subjects.has(card.instance_id)) return "legal";
    if (inter.freeTargets.has(card.instance_id)) return "target";
    return null;
  }

  function clickCard(card: CardModel) {
    if (!interactive) return;
    const id = card.instance_id;
    if (isResourcing) {
      if (!resourceableIds.has(id)) return;
      setStaged((prev) =>
        prev.includes(id)
          ? prev.filter((x) => x !== id)
          : prev.length >= requiredResources
            ? prev
            : [...prev, id],
      );
      return;
    }
    if (selected) {
      if (id === selected) return setSelected(null);
      const a = selTargets.get(id);
      if (a) requestAct(a);
      return;
    }
    if (inter.freeTargets.has(id)) {
      const a = snapshot!.actions.find((x) => x.kind === "ChooseTarget" && targetOf(x) === id);
      if (a) act(a.action_id);
      return;
    }
    if (inter.subjects.has(id)) {
      const all = inter.bySubject.get(id) ?? [];
      if (all.length === 1) {
        act(all[0].action_id);
        return;
      }
      setSelected(id);
    }
  }

  const slot: SlotFns = {
    hl,
    onClick: clickCard,
    onHover: (c) => setHover(c),
    onInspect: (c) => setInspected(c),
    defeated: (c) => defeated.has(c.instance_id),
  };

  const selectedCard = selected
    ? [
        ...view.my.ground_arena,
        ...view.my.space_arena,
        ...view.my.hand,
        ...view.my.base_zone,
        ...view.my.resources, // a selected smuggle source lives in the resource zone
      ].find((c) => c.instance_id === selected)
    : null;
  const contextActions = selected ? (inter.bySubject.get(selected) ?? []) : [];

  const humanMat = playmatFor(leaderName(view.my.base_zone), "human");
  const botMat = playmatFor(leaderName(view.opponent.base_zone), "bot");

  const idleHint = (() => {
    switch (view.phase) {
      case "SETUP_MULLIGAN":
        return "Opening hand: keep it, or take a mulligan (buttons on the right).";
      case "SETUP_RESOURCES":
        return "Choose two cards to set as resources, then press Confirm.";
      case "REGROUP":
        return "Regroup: choose a card to resource and Confirm — or Skip.";
      default:
        return "Your turn — click a card to play or attack.";
    }
  })();

  const targetArenas = new Set<string>();
  if (selected) {
    selTargets.forEach((_a, id) => {
      if (view.opponent.ground_arena.some((c) => c.instance_id === id)) targetArenas.add("ground");
      if (view.opponent.space_arena.some((c) => c.instance_id === id)) targetArenas.add("space");
    });
  }

  return (
    <div
      className="table"
      onClick={() => {
        if (playing) skipAnimations();
      }}
    >
      <div className="playmat top" style={{ background: playmatBackground(botMat) }} />
      <div className="playmat bottom" style={{ background: playmatBackground(humanMat) }} />

      <div className="table-content">
        <Hud
          view={view}
          awaiting={awaiting}
          onSettings={() => setShowSettings(true)}
          onSave={quickSave}
          onToggleLog={onToggleLog}
        >
          <ActionBar
            awaiting={awaiting}
            playing={playing}
            prompt={snapshot!.prompt}
            controls={inter.controls}
            contextActions={contextActions}
            selectedName={selectedCard ? selectedCard.card_name : null}
            idleHint={idleHint}
            initiativeHeld={view.initiative_holder_id === "human"}
            resourcing={
              isResourcing
                ? {
                    staged: staged.length,
                    required: requiredResources,
                    canConfirm: staged.length === requiredResources,
                    onConfirm: confirmResources,
                    onClear: () => setStaged([]),
                  }
                : null
            }
            onAct={(id) => {
              const a = snapshot!.actions.find((x) => x.action_id === id);
              if (a) requestAct(a);
              else {
                setSelected(null);
                act(id);
              }
            }}
            onSkip={skipAnimations}
            onClearSelection={() => setSelected(null)}
          />
        </Hud>

        <div className="board">
          {/* Opponent rail: hand + base / leader / resources / piles */}
          <div className={`rail opp panel ${view.opponent.is_eliminated ? "eliminated" : ""}`}>
            <OppHand count={view.opponent.hand_count} />
            <BaseCluster zone={view.opponent} mine={false} slot={slot} />
            <ResourceRow zone={view.opponent} />
            <span className="spacer" />
            <div className="piles">
              <Pile label="Deck" count={view.opponent.deck_count} />
              <Pile
                label="Discard"
                count={view.opponent.discard.length}
                topCard={view.opponent.discard.slice(-1)[0]}
                onClick={() => setDiscardView("opp")}
                onHover={(c) => setHover(c)}
              />
            </div>
          </div>

          {/* Shared arenas — ground on the left, space on the right. Each keeps
            two rows (opponent above, you below) but now gets the full board
            height, so cards are roughly twice as large. */}
          <div className="arenas">
            <ArenaBand
              arena="ground"
              label="Ground"
              oppUnits={view.opponent.ground_arena}
              myUnits={view.my.ground_arena}
              slot={slot}
              isTargetZone={targetArenas.has("ground")}
            />
            <ArenaBand
              arena="space"
              label="Space"
              oppUnits={view.opponent.space_arena}
              myUnits={view.my.space_arena}
              slot={slot}
              isTargetZone={targetArenas.has("space")}
            />
          </div>

          {/* My base / leader / resources / piles */}
          <div className={`rail panel ${view.my.is_eliminated ? "eliminated" : ""}`}>
            <BaseCluster zone={view.my} mine={true} slot={slot} />
            <ResourceRow zone={view.my} mine={true} slot={slot} />
            <span className="spacer" />
            <div className="piles">
              <Pile label="Deck" count={view.my.deck_count} />
              <Pile
                label="Discard"
                count={view.my.discard.length}
                topCard={view.my.discard.slice(-1)[0]}
                onClick={() => setDiscardView("mine")}
                onHover={(c) => setHover(c)}
              />
            </div>
          </div>

          {/* My hand */}
          <MyHand zone={view.my} slot={slot} />
        </div>
      </div>

      <EffectsLayer active={active} />
      <CardZoom card={hover} />
      {inspected && (
        <CardZoom card={inspected} anchored={false} onDismiss={() => setInspected(null)} />
      )}

      {discardView && (
        <DiscardViewer
          title={discardView === "mine" ? "Your discard" : "Opponent discard"}
          cards={discardView === "mine" ? view.my.discard : view.opponent.discard}
          onClose={() => setDiscardView(null)}
        />
      )}
      {showSettings && <SettingsPanel onClose={() => setShowSettings(false)} />}

      {confirm && (
        <ConfirmDialog
          title="Attach to an enemy unit?"
          message={`${confirm.upgradeName} would be attached to ${confirm.targetName}, an enemy unit — its bonuses help your opponent. Play it there anyway?`}
          confirmLabel="Attach to enemy"
          onConfirm={() => {
            const a = confirm.action;
            setConfirm(null);
            setSelected(null);
            act(a.action_id);
          }}
          onCancel={() => setConfirm(null)}
        />
      )}

      {peek && peekActions.length > 0 && (
        <PeekViewer
          cardId={
            typeof peek.context.peeked_card_id === "number" ? peek.context.peeked_card_id : -1
          }
          cardName={
            typeof peek.context.peeked_card_name === "string"
              ? peek.context.peeked_card_name
              : "Unknown card"
          }
          mode={typeof peek.context.mode === "string" ? peek.context.mode : ""}
          actions={peekActions}
          onAct={(id) => act(id)}
        />
      )}

      {reveal && (
        <RevealViewer
          revealed={(reveal.context.revealed as RevealedCard[]) ?? []}
          pending={(reveal.context.pending as string[]) ?? []}
          keptOrder={(reveal.context.kept_order as string[]) ?? []}
          actions={revealActions}
          onAct={(id) => act(id)}
        />
      )}

      {lookHand && (
        <LookHandViewer
          cards={(lookHand.context.revealed_hand as RevealedHandCard[]) ?? []}
          action={lookHandAck}
          onAct={(id) => act(id)}
        />
      )}

      {chooser && (
        <ChooseCardsViewer
          title={chooser.title}
          prompt={chooser.prompt}
          candidates={chooser.candidates}
          actionForId={(iid) =>
            snapshot!.actions.find(
              (a) => a.kind === chooser.pickKind && a.params.instance_id === iid,
            )
          }
          finish={chooser.finish}
          finishLabel={chooser.finishLabel}
          onAct={(id) => act(id)}
        />
      )}

      {peek === null &&
        interactive &&
        view.phase === "SETUP_MULLIGAN" &&
        snapshot!.actions.some((a) => a.kind === "KeepHand") && (
          <MulliganViewer hand={view.my.hand} actions={snapshot!.actions} onAct={(id) => act(id)} />
        )}

      {toast && <Toast message={toast} onDone={() => setToast(null)} />}

      {turnGate !== null && !playing && awaiting !== "terminal" && (
        <TurnGate round={turnGate} onStart={dismissTurnGate} />
      )}

      {awaiting === "terminal" && (
        <EndScreen
          won={snapshot!.winner === "human"}
          onPlayAgain={reset}
          onExportReplay={exportReplay}
        />
      )}
    </div>
  );
}
