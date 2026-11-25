# grand-moff-tarkin — assessment & outcome

**Source of truth:** `tests/fixtures/grand_moff_tarkin.json` (transcribed from the
printed *HMW* two-player-starter decklist card, partner of `chewbacca`).
Totals **52** = 1 leader + 1 base + 50 deck cards.

## Card-number resolution

Starred (`*`) entries are "card from a previous set"; everything else is HMW.

| printed | resolves to |
|---------|-------------|
| `22*` Senate Rotunda (base) | `SEC_22` |
| `103*` Display Piece | `LAW_103` |
| `91*` Craving Power | `LOF_91` |
| `43*` No Glory, Only Results | `JTL_43` |
| `72*` Doctor Pershing | `ASH_72` |
| `80*` Imperial Dark Trooper | `SEC_80` |
| `33*` Onyx Squadron Brute | `JTL_33` |
| `103*` Long Live the Empire | `ASH_103` |
| `30*` Death Trooper | `SEC_30` (also printed as `SHD_30`: same text and stats; SEC chosen to match the deck's other SEC cards) |
| `97*` Moff Gideon | `ASH_97` (the Unit, not a Leader) |
| `98*` AT-ST Raider | `ASH_98` |
| `48*` Imperial Armored Commando | `ASH_48` |
| `50*` Morgan Elsbeth | `ASH_50` |
| `171*` Stockpile | `LAW_171` |
| `133*` Trask Walker | `ASH_133` |

Watch two number collisions: `103` appears twice (`LAW_103` Display Piece and
`ASH_103` Long Live the Empire), and `HMW_4` is both the Tarkin leader and the Beast
token. `decklist._lookup` takes the first DB row for a set+number (it does not
filter by type); the leader row comes first, so `HMW_4` loads as the Leader — the
soaks confirm it.

## Encoding status — nothing to encode

`plan_encoding.py` reports **52/52 playable, 0 groups**. HMW was completed by the gap
campaign before this deck was transcribed.

## Soak

200-game mirror soak: clean first time. 300-game soak against `chewbacca`: clean.

## Graduation gate

See `docs/dev/decks_status.md`. Registered on the start screen as
`grand-moff-tarkin` (`data/ui_decks.json` is per-install: each deployment needs its
own entry).
