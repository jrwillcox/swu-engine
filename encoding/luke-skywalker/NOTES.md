# luke-skywalker — assessment & outcome

**Source of truth:** `tests/fixtures/luke_skywalker_ash.json` (transcribed from the
printed *Ashes of the Empire* two-player-starter decklist card — the Luke half of
the same pair as [`emperor-palpatine`](../emperor-palpatine/NOTES.md)).
Totals **52** = 1 leader + 1 base + 50 deck cards.

> Not to be confused with the pre-existing `tests/fixtures/starter_luke.json`,
> which is the **SOR** two-player starter (`SOR_5` / `SOR_29`). This is a new,
> separate deck: `ASH_5` / `ASH_24`.

## Card-number resolution

Four entries are starred (`*`) on the printed list = "card from a previous set";
everything else is ASH. Each starred number resolves to exactly one DB printing:

| printed | resolves to | why |
|---------|-------------|-----|
| `47*` Baze Malbus | `LAW_47` (*Good Luck*) | the other printing is `SOR_65` *Temple Guardian*, number 65 |
| `62*` Silver Angel | `JTL_62` (*Trace's Hope*) | only printing in the DB |
| `51*` Red Squadron X-Wing | `JTL_51` | only printing in the DB |
| `254*` Stalwart Fleet Trooper | `LAW_254` | only printing in the DB |

Number collisions to watch on the un-starred ASH entries — every one of these
names has many printings and only the ASH number is correct:
`5` Luke Skywalker is the **Leader** *I Can Save Him* (15 Luke printings, incl.
`ASH_112` *Answering the Call* in the same set); `31` Hera Syndulla is
*Renegade General* (not the `SOR_8`/`LAW_9` Leaders); `59` Leia Organa is
*Vigilant for Danger* (11 printings, 5 of them Leaders); `158` Han Solo is
*It'll Work* (15 printings); `255` Anakin Skywalker is *You Were Right About Me*
(13 printings); `65` Home One is *Heart of the Fleet*. Note `254*` and `255` sit
adjacent on the printed list but belong to **different sets**.

## Encoding status — nothing to encode

`plan_encoding.py` reports **52/52 playable, 0 groups**. Per-card classification:

* 22 `implemented` (registered ability functions)
* 2 `keyword-complete` — pure keyword bars, engine-native:
  `ASH_166` Ewok Warrior (Hidden), `LAW_254` Stalwart Fleet Trooper (Sentinel)
* 2 `vanilla` — `ASH_24` Dragonsnake Bog (blank 30-HP base) and
  `ASH_61` Strike Team Vanguard (blank 4-cost 5/5)

No escape-hatches, no reprint aliases, no deferred keywords. The gap-filling
campaign had already covered every card; this deck needed **no new card encoding
at all**, so there are no group specs to hand to `docs/encode_group_prompt.md`.

## Interaction hot-spots (all clean, but this is where to look first)

The deck is built around *heal → punish*, which is unusually loop-prone:

* `ASH_5` Luke (leader) fires on **every** friendly attack end and heals the
  attacker or the base — a very high-frequency trigger.
* `LAW_47` Baze Malbus and `JTL_62` Silver Angel both trigger *"when 1 or more
  damage is healed from this unit"* and respond by **dealing damage**. Luke's heal
  therefore chains into damage on the same attack-end fire.
* `ASH_65` Home One heals **all** damage from **each** friendly unit on play —
  one play can fan out into several heal-triggered damage events at once.
* `ASH_72` Doctor Pershing, `ASH_59` Leia and `ASH_156` R5-D4 all carry
  **Support**, so their On-Attack abilities are read through the borrowed-abilities
  layer rather than off the attacker itself.
* `ASH_184` Follow Me and `ASH_162` Rash Action are granted-attack events
  (`ASH_162` also grants a temporary attack-end ability), and `ASH_158`/`ASH_159`
  use ASH **Advantage tokens**.

None of this misbehaved across 200 games — recorded so a future regression has a
starting point, not because anything is outstanding.

## Graduation gate — passing

```
[x] 100% of deck cards implemented-or-better  (52/52)
[x] fast suite green                 5625 passed, 10 skipped
[x] medium suite green               3 passed
[x] clean 200-game soak (this deck)  200 ok, 0 failed — clean on the first run
[~] [manual] UI smoke pass
```

Marked shippable in `docs/decks_status.md` and registered on the **dev** start
screen (`data/ui_decks.json`) as *Luke Skywalker — Vigilance/Heroism (Ashes of the
Empire)*. The deployed instance is untouched until a deploy.
