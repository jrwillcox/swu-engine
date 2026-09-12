// Types mirroring the backend's Pydantic models (src/swu/web/models.py).
// Kept hand-written and minimal; the OpenAPI schema at docs/openapi.json is the
// source of truth if these ever drift.

export interface CardModel {
  instance_id: string;
  card_id: number;
  card_name: string;
  card_type: string;
  owner_id: string;
  zone: string;
  exhausted: boolean;
  damage: number;
  face_down: boolean;
  deployed: boolean;
  epic_action_spent: boolean;
  effective_power: number;
  effective_hp: number;
  /** Stat bonus this card grants when played as an upgrade. An upgrade-in-hand
   * reports effective_power/hp of 0, so these carry its printed buff. Both 0 for
   * a net-neutral upgrade (e.g. a Bounty/control upgrade) — the only kind that
   * legitimately belongs on an enemy unit, so the enemy-attach confirm is
   * skipped for it. */
  upgrade_power?: number;
  upgrade_hp?: number;
  cost: number;
  /** Aspect-penalty surcharge (+2 per unmatched pip) for this card in your own
   * hand; 0 for on-aspect / in-play / opponent / hidden cards. Shown as a "+N"
   * pill beside the printed cost. */
  aspect_penalty?: number;
  /** Smuggle cost of one of your own smuggle-able resources: base bracket/granted
   * cost + the aspect-penalty surcharge. null/0 otherwise. Shown as a
   * "<base> +<N>" badge on the (face-down) resource. */
  smuggle_base?: number | null;
  smuggle_penalty?: number;
  attached_upgrades: CardModel[];
  keywords: string[];
  image_url: string | null;
  back_image_url: string | null;
  /** Available alternate art, keyed by variant type. Empty for most cards. */
  variants?: Record<string, CardVariantImages>;
}

export interface CardVariantImages {
  image_url: string | null;
  back_image_url: string | null;
}

export interface ZoneModel {
  player_id: string;
  deck_count: number;
  hand: CardModel[];
  hand_count: number;
  discard: CardModel[];
  resources: CardModel[];
  resource_count: number;
  available_resources: number;
  credits: number;
  has_force_token: boolean;
  ground_arena: CardModel[];
  space_arena: CardModel[];
  base_zone: CardModel[];
  is_eliminated: boolean;
}

export interface PendingDecisionModel {
  deciding_player_id: string;
  kind: string;
  context: Record<string, unknown>;
  is_mine: boolean;
}

export interface PlayerViewModel {
  viewer_id: string;
  phase: string;
  round_number: number;
  active_player_id: string;
  initiative_holder_id: string;
  my: ZoneModel;
  opponent: ZoneModel;
  event_log_tail: string[];
  pending_decisions: PendingDecisionModel[];
}

export interface ActionModel {
  action_id: string;
  kind: string;
  label: string;
  params: Record<string, unknown>;
}

export interface GameEvent {
  type: string;
  data: Record<string, unknown>;
}

export type Awaiting = "human" | "bot" | "terminal";

export interface Snapshot {
  game_id: string;
  view: PlayerViewModel;
  awaiting: Awaiting;
  actor_id: string | null;
  winner: string | null;
  prompt: string | null;
  actions: ActionModel[];
}

export interface StepResult extends Snapshot {
  events: GameEvent[];
}

export interface NewGameResponse extends Snapshot {
  player_id: string;
}

export interface DeckChoice {
  key: string;
  label: string;
  leader_name: string;
  base_name: string;
  /** "official" (built-in / graduated) or "custom" (the caller's own deck).
   * Optional for back-compat; treat a missing value as "official". */
  kind?: "official" | "custom";
}

// ── Custom deck builder (mirrors src/swu/web/deckstore.py) ───────────────────

/** Row for the Deck Manager list. `count` = sum of the pool counts; `required` =
 * how many that pool needs (50, or whatever the base shifts it to);
 * `complete` = leader+base set, count==required, every entry within its copy cap. */
export interface CustomDeckSummary {
  id: string;
  name: string;
  count: number;
  required: number;
  complete: boolean;
}

/** A full custom deck. `cards` maps str(DB card id) -> count (the pool);
 * `count`/`required`/`complete`/`errors` are derived by the backend on read.
 * `required` is 50 unless the chosen base moves it (Data Vault → 60, Thermal
 * Oscillator → 45) — always prefer it over the DECK_SIZE constant. */
export interface CustomDeck {
  id: string;
  name: string;
  owner: string;
  leader_id: number | null;
  base_id: number | null;
  cards: Record<string, number>;
  created: string;
  updated: string;
  count: number;
  required: number;
  complete: boolean;
  errors: string[];
}

/** Partial edit for PATCH /api/decks/custom/{id}. An omitted field is unchanged;
 * an explicit null clears the leader/base slot. */
export interface PatchCustomDeckRequest {
  name?: string;
  leader_id?: number | null;
  base_id?: number | null;
  cards?: Record<string, number>;
}

export interface SeatConfig {
  kind: "human" | "weighted_bot";
  deck: string;
}

export type Difficulty = "easy" | "normal" | "hard";

export interface NewGameRequest {
  human: SeatConfig;
  bot: SeatConfig;
  seed?: number | null;
  difficulty: Difficulty;
}

// ── Part D: save / replay / import ──────────────────────────────────────────

export interface SaveResult {
  ok: boolean;
  slot: string;
  path: string;
}

export interface ReplayBundle {
  format: number;
  kind: string;
  seed: number | null;
  difficulty: string;
  human_deck: string;
  bot_deck: string;
  action_history: { kind: string; desc: string }[];
}

export interface ReplayStep {
  view: PlayerViewModel;
  events: GameEvent[];
  winner: string | null;
}

export interface ReplayResponse {
  human_id: string;
  steps: ReplayStep[];
}

// ── Auth (user login) ───────────────────────────────────────────────────────

export interface CheckResponse {
  exists: boolean; // this username already has a password set
  allowed: boolean; // this username is on the whitelist (may register)
}

export interface AuthResponse {
  token: string;
  username: string; // display name (the casing the user typed)
  admin: boolean;
}

export interface MeResponse {
  username: string;
  admin: boolean;
}

export interface UserSummary {
  username: string;
  admin: boolean;
  registered: boolean;
}

// ── Card explorer (catalog browsing / future deck-builder) ──────────────────

export interface ExplorerCard {
  id: number; // DB primary key — also the image endpoint key
  set_code: string;
  card_number: string;
  name: string;
  subtitle: string | null;
  type: string;
  rarity: string | null;
  cost: number | null;
  power: number | null;
  hp: number | null;
  unique: boolean;
  aspects: string[];
  keywords: string[];
  traits: string[];
  arenas: string[];
  status: string;
  /** "Available to play" — implemented correctly in the engine yet. */
  playable: boolean;
  /** The deck-builder copy cap for this card (default 3; some cards print an
   * override, e.g. Swarming Vulture Droid = 15). Optional for back-compat. */
  deckbuild_max_copies?: number;
  /** Catalog deck keys this card appears in. */
  decks: string[];
  image_url: string | null;
  /** Card back (Leaders / double-sided Bases); null for single-faced cards. */
  back_image_url: string | null;
  /** Available alternate art, keyed by variant type. Empty for most cards. */
  variants?: Record<string, CardVariantImages>;
}

export interface ExplorerResponse {
  cards: ExplorerCard[];
  sets: { code: string; name: string }[];
  types: string[];
  aspects: string[];
  keywords: string[];
  traits: string[];
  decks: { key: string; label: string }[];
}

export interface ImportReport {
  ok: boolean;
  legal: boolean;
  errors: string[];
  total_cards: number;
  playable_cards: number;
  unimplemented: { id: string; name: string; label: string; count: number }[];
  fixture_path: string | null;
  planner_hint: string | null;
}

// ── Bug reports & two-way messaging (mirrors src/swu/web/bugs.py) ────────────

// What clicking "Report Bug" sends. `context` is freeform capture metadata
// (screen, game_id, your_turn, pending_decision, last_action, …); `game` is the
// replay bundle + snapshot written to game.json; both optional. A bad/absent
// screenshot never fails the report (best-effort capture).
export interface CreateBugRequest {
  title: string;
  expected?: string;
  actual?: string;
  context?: Record<string, unknown>;
  screenshot_b64?: string | null;
  game?: Record<string, unknown> | null;
}

// One message in a thread. The initial report carries the three form fields
// (title/expected/actual); replies (either direction) carry `text`.
export interface BugMessage {
  from: string;
  ts: string;
  read_by: string[];
  text?: string | null;
  title?: string | null;
  expected?: string | null;
  actual?: string | null;
}

export interface BugThread {
  id: string;
  title: string;
  status: string;
  author: string;
  created: string;
  reporter_archived: boolean;
  archived: boolean;
  context: Record<string, unknown>;
  has_screenshot: boolean;
  has_game: boolean;
  messages: BugMessage[];
}

export interface BugSummary {
  id: string;
  title: string;
  status: string;
  author: string;
  created: string;
  updated: string;
  last_from: string;
  unread: number;
  reporter_archived: boolean;
  archived: boolean;
  has_screenshot: boolean;
  has_game: boolean;
  // The reporter's original submission, so the triage list shows the gist.
  expected?: string;
  actual?: string;
}

// Admin triage: all users' active threads bucketed on "does this need the admin?".
export interface AdminTriage {
  needs_you: BugSummary[];
  waiting_on_reporter: BugSummary[];
  resolved: BugSummary[];
}

// The game.json a game-screen report carries (written by ReportBug). `replay` is
// the bundle the admin feeds to /api/replay to scrub the reported game in the viewer;
// null when the replay export failed at capture time. The rest pins the exact
// state the report was filed from.
export interface BugGame {
  replay: ReplayBundle | null;
  snapshot?: PlayerViewModel;
  awaiting?: string;
  winner?: string | null;
  pending_decision?: string | null;
}
