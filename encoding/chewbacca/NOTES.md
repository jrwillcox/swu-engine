# chewbacca — assessment & outcome

**Source of truth:** `tests/fixtures/chewbacca_hmw.json` (transcribed from the printed
*HMW* two-player-starter decklist card, partner of `grand-moff-tarkin`).
Totals **52** = 1 leader + 1 base + 50 deck cards.

## Card-number resolution

Starred (`*`) entries are "card from a previous set"; everything else is HMW.

| printed | resolves to |
|---------|-------------|
| `34*` Wicket | `ASH_34` |
| `56*` Cassian Andor | `LAW_56` |
| `103*` Mon Mothma | `SEC_103` |
| `166*` Ewok Warrior | `ASH_166` |
| `95*` Phoenix Squadron A-Wing | `JTL_95` |
| `96*` Blue Leader | `JTL_96` |
| `108*` Crix Madine | `ASH_108` |
| `146*` Massassi Group Marines | `LAW_146` |
| `151*` Red Five | `JTL_151` |
| `164*` Cham Syndulla | `JTL_164` |
| `62*` Defiant Hammerhead | `LAW_62` |
| `168*` Insurgent Saboteurs | `JTL_168` |

Watch the collisions between starred and un-starred entries with the same number:
`164` is both `HMW_164` Chief Chirpa and `JTL_164` Cham Syndulla, and `168` is both
`HMW_168` Ezra Bridger and `JTL_168` Insurgent Saboteurs. The fixture file is named
`chewbacca_hmw.json` because many Chewbacca leaders exist.

## Encoding status — nothing to encode

`plan_encoding.py` reports **52/52 playable, 0 groups**.

## The one real defect (found by soak, fixed)

The first 200-game mirror soak failed **1/200** (seed 162) with
`[invariant] Duplicate instance_id` — a Defiant Hammerhead `LAW_62` in the discard
twice. Chewbacca's leader ability made a damaged Hammerhead attack; it took the
+4/+0 ("defeat this unit after completing this attack") and was killed by combat
damage. `_settle_defeat_after_attack` then saw it via `state.find_instance`, which
**reaches the discard**, and defeated it again.

Fix: `_apply_defeat_unit` (resolver) now refuses to defeat a unit that is not in an
arena, which covers every caller rather than one card (same trap as `ASH_101` in
`emperor-palpatine`). Regression test:
`tests/test_law_cards.py::TestDefiantHammerhead_LAW_62::test_LAW_62_killed_by_combat_is_not_defeated_a_second_time`.

After the fix: 200-game mirror soak clean; 300-game soak against
`grand-moff-tarkin` clean.

## Graduation gate

See `docs/dev/decks_status.md`. Registered on the start screen as `chewbacca`
(`data/ui_decks.json` is per-install: each deployment needs its own entry).
