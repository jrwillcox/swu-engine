# Encoding manifest — `ibh-set`

Deck readiness: **104/104** cards playable. Encoding groups: **4/4** complete.

Encode one group per session: paste its **group id** into `docs/dev/encode_group_prompt.md`, review, then run `python scripts/verify_encoding.py ibh-set --group NN`.

## Groups (in dependency order)

| # | group id | kind | theme | cards | progress | new primitives | depends on |
|--:|----------|------|-------|------:|----------|----------------|------------|
| 1 | `ibh-set:01` | ability | Direct damage & removal | 6 | 6/6 ✅ | — | — |
| 2 | `ibh-set:02` | ability | Card advantage & disruption | 1 | 1/1 ✅ | — | — |
| 3 | `ibh-set:03` | ability | Combat tricks, buffs & tempo | 4 | 4/4 ✅ | — | — |
| 4 | `ibh-set:04` | ability | Miscellaneous abilities | 1 | 1/1 ✅ | — | — |

## Copy-paste entries

Paste the **id** line into the standing prompt. The card names are shown only so you know what you're submitting.

### `ibh-set:01` — Direct damage & removal (✅ done)
```
ibh-set:01
# Luke Skywalker (IBH_20), Darth Vader (IBH_53), Avenger (IBH_72), You Have Failed Me (IBH_95), Blizzard One (IBH_99), The Desolation of Hoth (IBH_104)
```

### `ibh-set:02` — Card advantage & disruption (✅ done)
```
ibh-set:02
# Watch This (IBH_52)
```

### `ibh-set:03` — Combat tricks, buffs & tempo (✅ done)
```
ibh-set:03
# Leia Organa (IBH_1), Recovery (IBH_13), Millennium Falcon (IBH_31), Han Solo (IBH_42)
```

### `ibh-set:04` — Miscellaneous abilities (✅ done)
```
ibh-set:04
# Han Solo (IBH_10)
```

