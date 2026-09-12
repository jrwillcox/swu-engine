# Encoding manifest — `p25-set`

Deck readiness: **130/130** cards playable. Encoding groups: **5/5** complete.

Encode one group per session: paste its **group id** into `docs/encode_group_prompt.md`, review, then run `python scripts/verify_encoding.py p25-set --group NN`.

## Groups (in dependency order)

| # | group id | kind | theme | cards | progress | new primitives | depends on |
|--:|----------|------|-------|------:|----------|----------------|------------|
| 1 | `p25-set:01` | ability | Direct damage & removal | 3 | 3/3 ✅ | — | — |
| 2 | `p25-set:02` | ability | Card advantage & disruption | 5 | 5/5 ✅ | — | — |
| 3 | `p25-set:03` | ability | Combat tricks, buffs & tempo | 7 | 7/7 ✅ | — | — |
| 4 | `p25-set:04` | ability | Combat tricks, buffs & tempo | 1 | 1/1 ✅ | — | — |
| 5 | `p25-set:05` | ability | Miscellaneous abilities | 1 | 1/1 ✅ | — | — |

## Copy-paste entries

Paste the **id** line into the standing prompt. The card names are shown only so you know what you're submitting.

### `p25-set:01` — Direct damage & removal (✅ done)
```
p25-set:01
# Admiral Ackbar (P25_39), Kit Fisto (P25_54), Darth Vader (P25_74)
```

### `p25-set:02` — Card advantage & disruption (✅ done)
```
p25-set:02
# Agent Kallus (P25_40), Obi-Wan Kenobi (P25_44), Razor Crest (P25_67), Kylo Ren (P25_72), The Invisible Hand (P25_78)
```

### `p25-set:03` — Combat tricks, buffs & tempo (✅ done)
```
p25-set:03
# Red Three (P25_41), Chewbacca (P25_42), Kylo Ren (P25_46), Fett's Firespray (P25_55), Luke Skywalker (P25_73), Ahsoka Tano (P25_83), Heirloom Lightsaber (P25_105)
```

### `p25-set:04` — Combat tricks, buffs & tempo (✅ done)
```
p25-set:04
# Yoda's Lightsaber (P25_107)
```

### `p25-set:05` — Miscellaneous abilities (✅ done)
```
p25-set:05
# Han Solo (P25_43)
```

