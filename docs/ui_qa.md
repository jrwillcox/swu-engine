# Phase 5 — Manual QA checklist (Web UI)

Run the backend and frontend (see [web/README.md](../web/README.md)), open
`http://localhost:5173`, and walk this list. Tick each on a fresh game of
**Luke (you) vs Vader (bot)**.

## Setup & start
- [ ] New-game screen lists decks from `/api/decks`; Luke/Vader selectable.
- [ ] "Start game" deals; the table appears with both bases and leaders.
- [ ] HUD shows phase, round, initiative holder, and whose turn it is.
- [ ] Backend unreachable → the start screen shows a clear error, not a blank page.

## Core play
- [ ] Mulligan: "Keep hand" / "Take mulligan" buttons work for your seat.
- [ ] Resource step: clicking a hand card resources it (face-down into your row).
- [ ] Play a unit from hand → it travels hand→arena and lands in the right arena.
- [ ] Play an upgrade → select the card, valid hosts glow, click one to attach.
- [ ] Deploy leader (when resources allow) → leader moves into an arena.
- [ ] Attack a unit → attacker lunges, both take simultaneous damage, counters update.
- [ ] Attack the base → base HP readout + bar drop; overwhelm banner if it applies.
- [ ] Pass / Claim Initiative controls behave; round advances through Regroup.

## Decisions & prompts
- [ ] A triggered/optional ability shows an **unmissable** pulsing prompt with
      Accept/Decline buttons.
- [ ] A target choice highlights legal targets; clicking one resolves it.
- [ ] Exploit/Ambush decisions surface with the right options.

## Defeat & tokens
- [ ] A unit defeated in combat shakes/desaturates and dissolves to discard.
- [ ] Shield consumption flashes a shield badge break.
- [ ] Experience/Shield tokens pop in as badges on the host.
- [ ] Discard pile is browsable on click (yours and opponent's).

## Hidden information
- [ ] Opponent hand shows as a fan of card backs (count only), never identities.
- [ ] Opponent resources/deck show as backs/counts only.
- [ ] Your own hand and resources are visible to you.

## Animation controls
- [ ] Settings (⚙): speed Fast/Normal/Slow visibly changes pacing.
- [ ] "Reduced motion" makes transitions near-instant.
- [ ] While animating, inputs are locked; clicking the board fast-forwards.
- [ ] `prefers-reduced-motion` at the OS level is respected on load.

## Win / lose
- [ ] Reducing a base to 0 ends the game.
- [ ] Victory/Defeat screen appears with a "Play again" button.
- [ ] "Play again" returns to the new-game screen cleanly.

## Presentation
- [ ] Playmat backgrounds show under each player's half.
- [ ] Dropping an image in `web/public/playmats/` and mapping it in
      `playmats.ts` swaps the backdrop.
- [ ] Hovering a card shows a large readable zoom.
- [ ] Battle log on the right reads as a human-friendly feed.

## Responsiveness
- [ ] Layout holds at 1440×900 and degrades acceptably at tablet width (~1024).
