// The tutorial script. One declarative array of beats; the board state for each
// beat is DERIVED from its index (see phaseConstants) so Back always works and
// there is no imperative drift. Coach copy uses **bold** / *italic* markers.

export type Gate = { kind: "next" } | { kind: "mulligan" } | { kind: "pickResources"; count: 2 };

export interface Step {
  id: string;
  who?: string; // coach name line; defaults to C-3PO
  coach: string; // caption (supports **bold** and *italic*)
  pos: "top" | "bottom" | "center";
  highlight: string[]; // element ids to spotlight
  gate: Gate;
}

// Indices that flip board state. Kept here so TutorialScreen and the tests agree.
export const P = {
  RESCHOOSE: 4,
  PLAY: 5,
  INIT: 9,
  REGROUP: 10,
  ATTACK: 12,
  DEPLOY: 14,
  WIN: 15,
} as const;

const C3PO = "C-3PO · Protocol Droid";

export const STEPS: Step[] = [
  {
    id: "intro",
    who: C3PO,
    pos: "center",
    highlight: [],
    gate: { kind: "next" },
    coach:
      "Oh, hello! I am **C-3PO**, human–cyborg relations. In one quick match I shall teach you everything. Shall we? ▶",
  },
  {
    id: "goal",
    pos: "bottom",
    highlight: ["enemyBase", "myBase"],
    gate: { kind: "next" },
    coach:
      "One goal: reduce the **enemy Base** to **0 HP**. Yours is at the bottom — do protect it!",
  },
  {
    id: "leader",
    pos: "bottom",
    highlight: ["myLeader"],
    gate: { kind: "next" },
    coach:
      "This is your **Leader**, Darth Vader — your hero. He waits here for now. Remember him; we'll unleash him later.",
  },
  {
    id: "mulligan",
    pos: "top",
    highlight: ["hand"],
    gate: { kind: "mulligan" },
    coach:
      "Your opening **hand** of 6. Not happy with it? You may **redraw once** — a *mulligan*. Choose below.",
  },
  {
    id: "resources",
    pos: "top",
    highlight: ["hand", "resources"],
    gate: { kind: "pickResources", count: 2 },
    coach:
      "Now **you** choose! Tap **2 cards** to place face-down as **resources** — your energy all game. Standing upright = **READY** to spend.",
  },
  {
    id: "play",
    pos: "top",
    highlight: ["handTrooper"],
    gate: { kind: "next" },
    coach:
      "Play the **Snowtrooper**. It **costs 2**, so you **exhaust** (tap) your 2 resources to pay. Tap **Next**.",
  },
  {
    id: "exhausted",
    pos: "top",
    highlight: ["resources", "myTrooper"],
    gate: { kind: "next" },
    coach:
      "Tapped sideways = **EXHAUSTED** (spent). And a new unit also enters *exhausted* — see the ⤾.",
  },
  {
    id: "stats",
    pos: "top",
    highlight: ["myTrooper"],
    gate: { kind: "next" },
    coach:
      "So it **can't attack the turn it arrives** — it must rest first. Its card shows **Power** (damage it deals) and **HP** (damage it can take).",
  },
  {
    id: "arenas",
    pos: "bottom",
    highlight: ["groundArena", "spaceArena"],
    gate: { kind: "next" },
    coach:
      "Two battlefields! Ground units ◊ (like your Snowtrooper) fight in the **Ground Arena**. Space units ✦ (like your TIE fighter) fly in the **Space Arena**. A unit only battles others in its *own* arena — but any unit can attack the enemy **Base**.",
  },
  {
    id: "initiative",
    pos: "bottom",
    highlight: ["initToken"],
    gate: { kind: "next" },
    coach:
      "Nothing left to do? You **pass**. The first to pass may **Claim Initiative** — take this token and **go first next round**. Grab it!",
  },
  {
    id: "regroup",
    pos: "bottom",
    highlight: ["regroup"],
    gate: { kind: "next" },
    coach:
      "Both players pass → **Regroup**: everything **readies**, you draw, add a resource. Your Snowtrooper is ready now!",
  },
  {
    id: "sentinel",
    pos: "bottom",
    highlight: ["enemyGuard"],
    gate: { kind: "next" },
    coach:
      "You have initiative, so you go first. **Keyword — Sentinel:** this guard *must* be attacked before you can reach the Base.",
  },
  {
    id: "attack",
    pos: "top",
    highlight: ["myTrooper", "enemyBase"],
    gate: { kind: "next" },
    coach:
      "Attack the wounded guard! Your Snowtrooper hits harder and defeats it — and **Overwhelm** spills the leftover damage onto the **Base**.",
  },
  {
    id: "raid",
    pos: "top",
    highlight: ["handRogue"],
    gate: { kind: "next" },
    coach:
      "**Keyword — Raid 1.** When this Rogue Operative attacks it gets **+1 Power**. Keywords are printed on the card — always read them!",
  },
  {
    id: "epic",
    pos: "bottom",
    highlight: ["myLeader"],
    gate: { kind: "next" },
    coach:
      "Now the big one: Vader's **⚡ Epic Action** — deploy him as a mighty unit, *once per game*. And Leaders arrive **READY**, so they attack at once!",
  },
  {
    id: "win",
    who: C3PO,
    pos: "center",
    highlight: ["enemyBase"],
    gate: { kind: "next" },
    coach:
      "Vader leads the assault — the Base falls to **0**. You win! That's the whole game. Now go play for real. **May the Force be with you!**",
  },
];
