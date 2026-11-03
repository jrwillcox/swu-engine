# Encoding manifest — `jtlp-set`

Deck readiness: **20/20** cards playable. Encoding groups: **3/3** complete.

Encode one group per session: paste its **group id** into `docs/dev/encode_group_prompt.md`, review, then run `python scripts/verify_encoding.py jtlp-set --group NN`.

## Groups (in dependency order)

| # | group id | kind | theme | cards | progress | new primitives | depends on |
|--:|----------|------|-------|------:|----------|----------------|------------|
| 1 | `jtlp-set:01` | ability | Direct damage & removal | 2 | 2/2 ✅ | — | — |
| 2 | `jtlp-set:02` | ability | Card advantage & disruption | 3 | 3/3 ✅ | — | — |
| 3 | `jtlp-set:03` | ability | Combat tricks, buffs & tempo | 3 | 3/3 ✅ | — | — |

## Copy-paste entries

Paste the **id** line into the standing prompt. The card names are shown only so you know what you're submitting.

### `jtlp-set:01` — Direct damage & removal (✅ done)
```
jtlp-set:01
# Red Squadron Y-Wing (JTLP_11), Fett's Firespray (JTLP_18)
```

### `jtlp-set:02` — Card advantage & disruption (✅ done)
```
jtlp-set:02
# Cassian Andor (JTLP_4), General Hux (JTLP_8), Anakin Skywalker (JTLP_16)
```

### `jtlp-set:03` — Combat tricks, buffs & tempo (✅ done)
```
jtlp-set:03
# Hera Syndulla (JTLP_3), Leia Organa (JTLP_5), Captain Tarkin (JTLP_13)
```

