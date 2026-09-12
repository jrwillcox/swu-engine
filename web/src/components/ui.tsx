// The shared UI surface, re-exported from ./ui/*.
//
// This was one 909-line file holding everything from the fullscreen button to the
// reveal-decision overlays.  It is now four modules grouped by what they do, and
// this barrel keeps the import path (`from "./ui"`) that the seven call sites and
// the tests already use — so the split is a move, not a rename, and nothing in
// the app or the vitest suite had to change with it.
//
//   chrome.tsx    HUD, toasts, log, turn gate, end screen — frame, not gameplay
//   CardZoom.tsx  the card-inspect overlay (anchored hover + centred long-press)
//   viewers.tsx   decision overlays: mulligan, discard, peek, reveal, choose
//   dialogs.tsx   confirm prompt + settings panel
//
// Import straight from the module when you only need one thing; the barrel is for
// call sites that pull several.
export {
  FullscreenButton,
  Hud,
  RotateHint,
  Toast,
  TurnGate,
  LogPanel,
  EndScreen,
} from "./ui/chrome";

export { CardZoom } from "./ui/CardZoom";

export {
  MulliganViewer,
  DiscardViewer,
  PeekViewer,
  RevealViewer,
  LookHandViewer,
  ChooseCardsViewer,
} from "./ui/viewers";
export type { RevealedCard, RevealedHandCard, CardCandidate } from "./ui/viewers";

export { ConfirmDialog, SettingsPanel } from "./ui/dialogs";
