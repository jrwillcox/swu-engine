// Human-readable rendering of engine events for the log panel.
// Mirrors the CLI's _render_event conceptually, but friendlier.
import type { GameEvent } from "../api/types";

const who = (id: unknown) => (id === "human" ? "You" : id === "bot" ? "Opponent" : String(id));

export interface LogLine {
  text: string;
  tone: "neutral" | "good" | "bad" | "info";
  /** Rendered as a full-width round separator rather than a normal line. */
  divider?: boolean;
}

export function formatEvent(ev: GameEvent): LogLine | null {
  const d = ev.data;
  switch (ev.type) {
    case "GameStarted":
      return { text: "Game start.", tone: "info" };
    case "RoundStarted":
      return { text: `Round ${d.round_number}`, tone: "info", divider: true };
    case "PhaseChanged":
      return { text: `Phase: ${d.new_phase}`, tone: "info" };
    case "CardPlayed":
      return {
        text: `${who(d.player_id)} played ${d.card_name} (${d.cost_paid}).`,
        tone: "neutral",
      };
    case "UnitEntersPlay":
      return { text: `${d.card_name} enters the ${d.arena} arena.`, tone: "neutral" };
    case "UpgradePlayed":
      return { text: `${who(d.player_id)} attached ${d.card_name}.`, tone: "neutral" };
    case "LeaderDeployed":
      return { text: `${who(d.player_id)} deployed ${d.leader_name}!`, tone: "info" };
    case "LeaderReturnedToBase":
      return { text: `${d.leader_name} returns to base.`, tone: "neutral" };
    case "ControlChanged":
      return {
        text: `${who(d.to_player_id)} take${d.to_player_id === "human" ? "" : "s"} control of ${d.card_name}.`,
        tone: "info",
      };
    case "UnitCaptured":
      return { text: `${d.captor_name} captures ${d.captured_name}!`, tone: "bad" };
    case "UnitReturnedFromCapture":
      return { text: `${d.card_name} is freed and returns to play.`, tone: "info" };
    case "AttackDeclared":
      return {
        text: d.forced_by_sentinel
          ? `${d.attacker_name} attacks ${d.defender_name} (forced — it has Sentinel).`
          : `${d.attacker_name} attacks ${d.defender_name}.`,
        tone: "neutral",
      };
    case "DamageDealt":
      return {
        text: d.source_name
          ? `${d.target_name} takes ${d.amount} damage from ${d.source_name}.`
          : `${d.target_name} takes ${d.amount} damage.`,
        tone: "bad",
      };
    case "OverwhelmDamage":
      return { text: `Overwhelm: ${d.amount} to the base!`, tone: "bad" };
    case "CombatDamagePrevented":
      return { text: `${d.unit_name}'s combat damage is prevented.`, tone: "good" };
    case "DamagePrevented":
      return { text: `${d.unit_name}'s damage is prevented.`, tone: "good" };
    case "UnitDefeated":
      return { text: `${d.card_name} is defeated.`, tone: "bad" };
    case "ShieldDefeated":
      return { text: `${d.host_name}'s shield breaks.`, tone: "info" };
    case "ExperienceDefeated":
      return { text: `${d.host_name} loses an Experience token.`, tone: "info" };
    case "TokenAttached":
      return { text: `${d.host_name} gains a ${d.token_name} token.`, tone: "good" };
    case "CreditTokenCreated":
      return {
        text: `${who(d.player_id)} create${d.player_id === "human" ? "" : "s"} a Credit token.`,
        tone: "good",
      };
    case "CreditDefeated":
      return {
        text: `${who(d.player_id)} spend${d.player_id === "human" ? "" : "s"} a Credit (pay 1 less).`,
        tone: "neutral",
      };
    case "RestoreHealing": {
      const verb = d.player_id === "human" ? "restore" : "restores";
      const src = d.source_name ? ` (${d.source_name})` : "";
      return { text: `${who(d.player_id)} ${verb} ${d.amount}${src}.`, tone: "good" };
    }
    case "CardResourced":
    case "RegroupResourced":
      return { text: `${who(d.player_id)} resourced a card.`, tone: "neutral" };
    case "InitiativeTaken":
      return { text: `${who(d.player_id)} claimed initiative.`, tone: "info" };
    case "PlayerPassed":
      return { text: `${who(d.player_id)} passes.`, tone: "neutral" };
    case "EmptyDeckDamage":
      return { text: `${who(d.player_id)} mills — ${d.damage} to base.`, tone: "bad" };
    case "GameOver":
      return {
        text: `${who(d.winner_player_id)} win${d.winner_player_id === "human" ? "" : "s"}!`,
        tone: "good",
      };
    case "FallbackNotice":
      // Phase 6B — the LLM opponent dropped to its heuristic for a decision.
      // Surfaced as a visible log line (not debug-only) by design.
      return { text: String(d.message), tone: "info" };
    case "HandKept":
    case "MulliganTaken":
    case "HandDrawn":
    case "RegroupDrawn":
    case "RegroupSkipped":
    case "AllCardsReadied":
    case "DecisionPushed":
    case "DecisionResolved":
      return null; // too noisy for the log
    default:
      return null;
  }
}
