# emperor-palpatine — assessment & outcome

**Source of truth:** `tests/fixtures/emperor_palpatine.json` (transcribed from the
printed *Ashes of the Empire* two-player-starter decklist card).
Totals **52** = 1 leader + 1 base + 50 deck cards.

## Card-number resolution

Two entries are starred (`*`) on the printed list = "card from a previous set";
everything else is ASH. Both starred numbers resolve to a single DB printing:

| printed | resolves to | why |
|---------|-------------|-----|
| `91*` Craving Power | `LOF_91` (Upgrade) | only printing in the DB |
| `185*` Screeching TIE Fighter | `SEC_185` (Unit) | only printing in the DB |

Watch the number collisions on the ASH entries: `36` Rukh is `ASH_36`
(*From the Shadows*), **not** `SOR_85` (*Thrawn's Assassin*); `97` Moff Gideon is the
**Unit** *Remnant Commander*, not the `ASH_8` Leader; `243` Darth Vader is
*Meet Your Destiny*, one of nineteen Vader printings.

## Encoding status — nothing to encode

`plan_encoding.py` reports **52/52 playable, 0 groups**. Per-card classification:

* 22 `implemented` (registered ability functions)
* 3 `keyword-complete` — pure keyword bars, all engine-native:
  `ASH_215` Flanking TIE Interceptor (Support), `ASH_96` Forest Patroller
  (Overwhelm, Restore), `ASH_193` Emperor's Champion (Shielded, Saboteur)
* 1 `vanilla` — `ASH_21` Emperor's Throne Room, a genuinely blank base

No escape-hatches, no reprint aliases, no deferred keywords. `validate_decklist`
returns no errors. The gap-filling campaign had already covered every card; this
deck needed **no new card encoding at all**.

## The one real defect (found by soak, fixed)

A 200-game deck soak failed **29/200** with
`[invariant] Duplicate instance_id … ` — a unit sitting in the discard pile twice.
A control soak of the already-graduated `moff-gideon` deck was clean, so the fault
was specific to this deck's cards.

Root cause: **`ASH_101` The Great Mothers** — *"When Attack Ends: if this unit dealt
combat damage to 1 or more non-leader units, defeat those units."*
`_great_mothers_defeat_damaged` looked its victims up with `state.find_instance`,
which **reaches the discard**. A unit the combat damage had *already* killed still
resolved, so the sweep defeated it a second time and appended it to the discard
again. The function's own docstring asserted the opposite ("no longer in an arena,
so it is simply skipped") — a wrong assumption, not a missing feature.

Fix: an arena-zone guard in `src/swu/cards/ash/abilities.py`
(`ci.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA) → continue`), plus the
regression test
`tests/test_ash_cards.py::TestTheGreatMothersASH101::test_ASH_101_does_not_re_defeat_a_unit_the_combat_damage_killed`
(verified to fail with the guard removed).

## Graduation gate — passing

```
[x] 100% of deck cards implemented-or-better  (52/52)
[x] fast suite green
[x] medium suite green
[x] clean 200-game soak (this deck)      # was 171 ok / 29 failed before the fix
[~] [manual] UI smoke pass
```

Marked shippable in `docs/decks_status.md` and registered on the **dev** start
screen (`data/ui_decks.json`). The deployed instance is untouched until a deploy.
