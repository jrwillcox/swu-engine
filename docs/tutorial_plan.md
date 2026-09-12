# Interactive Tutorial — Design & Implementation Plan

**Status:** approved, building (2026-07-25). A clickable look-and-flow mockup was
agreed first (C-3PO-coached, on-rails, full game to a win). This doc is the build
plan for turning that into a real front-end feature.

## Goal

Teach a complete newcomer (age 10+) the core of Star Wars: Unlimited in one short,
guided game — hand/mulligan, resources, cost, Ground vs Space, power/HP,
ready/exhausted, attacking, initiative, the turn phases, and a few common keywords —
ending in a scripted win. Visual, on-rails, minimal words in a large friendly font
clearly distinct from normal game UI.

## Agreed decisions

1. **Style:** on-rails guided game (the board only allows the correct next action;
   everything else dimmed).
2. **Scope:** a full first game, ending in a scripted victory.
3. **Coach:** **C-3PO**, a gold protocol-droid mentor (fictional character; personal
   use), speaking in a warm cream caption panel unmistakably not-the-game.
4. **Approach:** **scripted front-end** (not the live engine) — a self-contained
   `TutorialScreen` running a fixed step-script, **reusing the real `Card`
   component + card art + playmat** for authentic visuals. Rationale: for a fixed
   16-step onboarding the value is a smooth, unbreakable, kid-proof experience, not
   engine fidelity. A live-engine "sandbox practice mode" is a possible *future*
   feature, not this build.
5. **Scripted deck:** the **SOR Luke-vs-Vader starter** (the app's default `luke`/
   `vader` decks) so the cards, art, and rules are ones the player will actually meet.
6. **Resource step:** keep the **interactive tap-2** (player taps 2 hand cards to
   place as resources — teaches that resourcing is their choice).
7. **Launch:** from a **"How to Play" button** on `NewGameScreen` only. **No**
   first-run auto-prompt and **no** `tutorial_done` flag ⇒ **zero backend changes**
   for the MVP.
8. **Animations:** included in the MVP (card-play, attack lunge, base-HP tick).

## The 16 beats (final content)

intro → the goal (both bases) → meet your Leader → mulligan (Keep / redraw once) →
**choose 2 resources (tap-2)** → play a unit (exhaust 2 resources to pay) →
ready ↔ exhausted (units enter exhausted) → why it can't attack yet + Power/HP →
**Ground vs Space arenas** → **Claim Initiative** (token slides to you) →
Regroup (ready, draw, +1 resource) → Sentinel → attack + Overwhelm → Raid →
Epic Action (deploy the Leader — arrives READY) → win (base to 0).

Rules accuracy confirmed against the engine: units enter play **exhausted**
(`actions._put_unit_in_play`), a deployed **leader enters READY** (the
`DeployLeader` rule), and **Claim Initiative** is a distinct action offered to the
first passer (`actions.ClaimInitiative`).

## Architecture

Front-end only. New screen in `App.tsx`, same pattern as `explorer`/`deckManager`:

- `App.tsx` — add a `tutorial` boolean; when set, render `<TutorialScreen
  onExit={…}/>` taking over the screen (like `ReplayViewer`).
- `NewGameScreen` — add a **"📖 How to Play"** button (new optional
  `onOpenTutorial` prop) next to "Browse the card explorer" / "My decks".

### Components

| Component | Build/Reuse | Notes |
|---|---|---|
| `TutorialScreen` | new | owns step index; renders the tutorial board + overlay |
| `CoachPanel` | new | C-3PO SVG, caption, Next/Back — ported from the mockup |
| `Spotlight` | new | dim layer + glow ring on the highlighted element(s) |
| tutorial board (arenas/hand/resources/base/leader) | new, purpose-built | simpler than the full `Table`; not wired to `useGame` |
| `Card` | **reuse** | real art via `card.image_url` / `artFor` |
| playmat background | reuse | `playmats/` |

### Step-script data model

```ts
type Gate =
  | { kind: "next" }                       // Next button / tap / →
  | { kind: "mulligan" }                    // Keep / Redraw (both advance)
  | { kind: "pickResources"; count: 2 };    // tap-2 from hand, unlocks Next at 2
type Step = {
  id: string;
  coach: string;              // C-3PO caption (**bold**, *italic*)
  pos: "top" | "bottom" | "center";
  highlight: string[];        // element ids to spotlight
  gate: Gate;
};
```

Board state is **derived from the step index** (played? exhausted? guardGone?
deployed? initiativeClaimed? baseHP) exactly like the mockup — so **Back always
works** and there is no imperative drift.

### Scripted cards

A small `tutorialDeck.ts` holds ~8 real cards as `CardModel`s (real DB `card_id`,
so `/api/cards/{id}/image` art resolves): Luke's Leader + Base, a Trooper (cost /
Ground), a starfighter (Space), a unit with Sentinel (enemy), one with Overwhelm,
one with Raid, plus two "spare" hand cards for the resource pick. Exact ids pulled
from the Luke/Vader starter fixtures.

## Interaction gating

Only the current gate's control is live; everything else is dimmed and inert (the
on-rails guarantee). `pickResources` blocks Next until 2 cards are tapped. Skip ✕
and Back are always available.

## Animations (MVP)

Motion (already a dep) for: a hand card sliding into the arena on play; a short
attack lunge; the base-HP number ticking down; the initiative token sliding to the
player's side. All gated behind `prefers-reduced-motion`.

## Testing

`web/tests/tutorial.test.tsx` (vitest + RTL), mirroring existing web tests:
advances on Next; Back restores prior board state; `pickResources` blocks Next
until 2 chosen; mulligan buttons advance; Skip exits; reaches the win step;
"How to Play" button opens the tutorial from `NewGameScreen`.

## Deployment

Front-end only ⇒ flows through the existing `deploy.ps1` (dev `swu-game` →
`swu-game-deployed` → `-Server`). No `data/` or backend changes.

## Phasing

- **MVP (this build):** `TutorialScreen` + coach + spotlight + 16 scripted steps
  with real Luke/Vader cards, the three gate types, animations, Skip/Back, launched
  from the "How to Play" button, tests.
- **Future:** a live-engine **sandbox practice mode** (real easy bot) as a separate
  feature — the natural graduation from the tutorial.
