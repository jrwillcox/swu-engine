// Pure helpers that map the backend's fully-enumerated legal actions onto the
// UI's click model. The engine already lists every concrete (attacker, target)
// pair as its own action, so the frontend never constructs targets — it just
// anchors each action to the card(s) it names and routes clicks to action ids.
import type { ActionModel } from "../api/types";

export const BASE_TARGET = "BASE";

// Actions shown as buttons (no single obvious card to click), incl. leader-zone
// and flow controls. Card-anchored kinds are everything else.
const CONTROL_KINDS = new Set([
  "Pass",
  "ClaimInitiative",
  "KeepHand",
  "TakeMultiligan",
  "SkipResource",
  "ExploitCommit",
  "DeclineTarget",
  "AutoResolveEffects",
  "DeployLeader",
  "AttackWithLeader",
  "DeclineAmbush",
  "DeclineGrantedAttack",
  // "Play up to N units …" (Dathomiri Magicks ASH_104) — the loop's stop button;
  // it names no card, so it can never be card-anchored.
  "DeclinePlayFromHand",
  "AnswerTestDecision",
  // Trigger decisions carry a source_id, but their source may be an attached
  // upgrade with no clickable board subject (e.g. Luke's Lightsaber on R2-D2),
  // so they must always be flow-control buttons — never card-anchored.
  "AcceptTrigger",
  "DeclineTrigger",
]);

function asStr(v: unknown): string | undefined {
  return typeof v === "string" ? v : undefined;
}

/** The card a click on the board should originate from, if any. */
export function subjectOf(a: ActionModel): string | undefined {
  const p = a.params;
  return asStr(p.attacker_id) ?? asStr(p.source_id) ?? asStr(p.unit_id) ?? asStr(p.instance_id);
}

/** The card (or BASE) a subject's action resolves against, if it needs one. */
export function targetOf(a: ActionModel): string | undefined {
  const p = a.params;
  if (a.kind === "AttackWithUnit" || a.kind === "ContinueAttack") {
    return asStr(p.defender_id) ?? BASE_TARGET;
  }
  if (a.kind === "ChooseTarget") return asStr(p.target_id);
  if (a.kind === "UseAmbush") return asStr(p.target_id);
  if (
    (a.kind === "PlayCard" || a.kind === "SmugglePlay" || a.kind === "PlayViaSmuggle") &&
    p.upgrade_target_id
  ) {
    // Smuggling an upgrade picks a host to attach to, exactly like playing one
    // from hand — the resource is the subject, the host unit is the target.
    return asStr(p.upgrade_target_id);
  }
  return undefined;
}

export interface Interaction {
  /** Actions presented as buttons (controls + decisions). */
  controls: ActionModel[];
  /** instance_id -> the actions anchored to that card as their subject. */
  bySubject: Map<string, ActionModel[]>;
  /** instance_ids that are clickable subjects right now. */
  subjects: Set<string>;
  /** instance_ids (or BASE) that are valid resolve_effects / choose targets. */
  freeTargets: Set<string>;
}

export function buildInteraction(actions: ActionModel[]): Interaction {
  const controls: ActionModel[] = [];
  const bySubject = new Map<string, ActionModel[]>();
  const freeTargets = new Set<string>();

  for (const a of actions) {
    if (a.kind === "ChooseTarget") {
      const t = targetOf(a);
      if (t) freeTargets.add(t);
      controls.push(a); // also offer in the decision banner as a fallback
      continue;
    }
    const subj = CONTROL_KINDS.has(a.kind) ? undefined : subjectOf(a);
    if (subj === undefined) {
      controls.push(a);
    } else {
      const list = bySubject.get(subj) ?? [];
      list.push(a);
      bySubject.set(subj, list);
    }
  }

  return {
    controls,
    bySubject,
    subjects: new Set(bySubject.keys()),
    freeTargets,
  };
}

/** Targets (card ids or BASE) reachable from a selected subject card. */
export function targetsForSubject(inter: Interaction, subjectId: string): Map<string, ActionModel> {
  const out = new Map<string, ActionModel>();
  for (const a of inter.bySubject.get(subjectId) ?? []) {
    const t = targetOf(a);
    if (t) out.set(t, a);
  }
  return out;
}

/** The subset of a subject's actions that need no further target choice. */
export function directActions(inter: Interaction, subjectId: string): ActionModel[] {
  return (inter.bySubject.get(subjectId) ?? []).filter((a) => targetOf(a) === undefined);
}
