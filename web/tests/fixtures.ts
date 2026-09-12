import type {
  ActionModel,
  CardModel,
  PlayerViewModel,
  Snapshot,
  ZoneModel,
} from "../src/api/types";

export function card(partial: Partial<CardModel> & { instance_id: string }): CardModel {
  return {
    card_id: 1,
    card_name: "Test Card",
    card_type: "Unit",
    owner_id: "human",
    zone: "GROUND_ARENA",
    exhausted: false,
    damage: 0,
    face_down: false,
    deployed: false,
    epic_action_spent: false,
    effective_power: 3,
    effective_hp: 4,
    cost: 2,
    attached_upgrades: [],
    keywords: [],
    image_url: `/api/cards/1/image?face=front`,
    back_image_url: null,
    ...partial,
  };
}

export function zone(player_id: string, partial: Partial<ZoneModel> = {}): ZoneModel {
  return {
    player_id,
    deck_count: 30,
    hand: [],
    hand_count: 5,
    discard: [],
    resources: [],
    resource_count: 4,
    available_resources: 4,
    credits: 0,
    has_force_token: false,
    ground_arena: [],
    space_arena: [],
    base_zone: [
      card({
        instance_id: `${player_id}_base`,
        card_type: "Base",
        card_name: "Base",
        effective_hp: 30,
      }),
    ],
    is_eliminated: false,
    ...partial,
  };
}

export function view(partial: Partial<PlayerViewModel> = {}): PlayerViewModel {
  return {
    viewer_id: "human",
    phase: "ACTION",
    round_number: 2,
    active_player_id: "human",
    initiative_holder_id: "human",
    my: zone("human"),
    opponent: zone("bot"),
    event_log_tail: [],
    pending_decisions: [],
    ...partial,
  };
}

export function snapshot(partial: Partial<Snapshot> = {}): Snapshot {
  return {
    game_id: "test",
    view: view(),
    awaiting: "human",
    actor_id: "human",
    winner: null,
    prompt: null,
    actions: [],
    ...partial,
  };
}

export function action(
  kind: string,
  params: Record<string, unknown>,
  id = "a0",
  label = kind,
): ActionModel {
  return { action_id: id, kind, label, params };
}
