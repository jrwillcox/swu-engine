# Encoding manifest — `hmwp-set`

Deck readiness: **20/20** cards playable. Encoding groups: **6/6** complete.

Encode one group per session: paste its **group id** into `docs/dev/encode_group_prompt.md`, review, then run `python scripts/verify_encoding.py hmwp-set --group NN`.

## Groups (in dependency order)

| # | group id | kind | theme | cards | progress | new primitives | depends on |
|--:|----------|------|-------|------:|----------|----------------|------------|
| 1 | `hmwp-set:01` | ability | Direct damage & removal | 6 | 6/6 ✅ | — | — |
| 2 | `hmwp-set:02` | ability | Card advantage & disruption | 1 | 1/1 ✅ | — | — |
| 3 | `hmwp-set:03` | ability | Combat tricks, buffs & tempo | 4 | 4/4 ✅ | — | — |
| 4 | `hmwp-set:04` | ability | Miscellaneous abilities | 3 | 3/3 ✅ | — | — |
| 5 | `hmwp-set:05` | ability | New primitive: beast-token | 1 | 1/1 ✅ | — | — |
| 6 | `hmwp-set:06` | ability | New primitive: weakness-token | 1 | 1/1 ✅ | — | — |

## Copy-paste entries

Paste the **id** line into the standing prompt. The card names are shown only so you know what you're submitting.

### `hmwp-set:01` — Direct damage & removal (✅ done)
```
hmwp-set:01
# Scorch (HMWP_2), Always a Bigger Fish (HMWP_6), Arena Acklay (HMWP_10), General Grievous (HMWP_11), Adamant Ewoks (HMWP_14), Don't Touch Anything (HMWP_17)
```

### `hmwp-set:02` — Card advantage & disruption (✅ done)
```
hmwp-set:02
# Boga (HMWP_8)
```

### `hmwp-set:03` — Combat tricks, buffs & tempo (✅ done)
```
hmwp-set:03
# Batcher (HMWP_4), Gunga City Guard (HMWP_5), Invasion Lander (HMWP_7), Chief Chirpa (HMWP_13)
```

### `hmwp-set:04` — Miscellaneous abilities (✅ done)
```
hmwp-set:04
# Zam Wesell (HMWP_9), Teebo (HMWP_12), New Tactics (HMWP_18)
```

### `hmwp-set:05` — New primitive: beast-token (✅ done)
```
hmwp-set:05
# Eravana (HMWP_1)
```

### `hmwp-set:06` — New primitive: weakness-token (✅ done)
```
hmwp-set:06
# Inferno Squad (HMWP_15)
```

