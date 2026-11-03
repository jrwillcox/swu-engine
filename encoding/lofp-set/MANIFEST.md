# Encoding manifest — `lofp-set`

Deck readiness: **20/20** cards playable. Encoding groups: **3/3** complete.

Encode one group per session: paste its **group id** into `docs/dev/encode_group_prompt.md`, review, then run `python scripts/verify_encoding.py lofp-set --group NN`.

## Groups (in dependency order)

| # | group id | kind | theme | cards | progress | new primitives | depends on |
|--:|----------|------|-------|------:|----------|----------------|------------|
| 1 | `lofp-set:01` | ability | Direct damage & removal | 1 | 1/1 ✅ | — | — |
| 2 | `lofp-set:02` | ability | Card advantage & disruption | 2 | 2/2 ✅ | — | — |
| 3 | `lofp-set:03` | ability | Miscellaneous abilities | 2 | 2/2 ✅ | — | — |

## Copy-paste entries

Paste the **id** line into the standing prompt. The card names are shown only so you know what you're submitting.

### `lofp-set:01` — Direct damage & removal (✅ done)
```
lofp-set:01
# Infused Brawler (LOFP_11)
```

### `lofp-set:02` — Card advantage & disruption (✅ done)
```
lofp-set:02
# Luthen Rael (LOFP_1), Do or Do Not (LOFP_12)
```

### `lofp-set:03` — Miscellaneous abilities (✅ done)
```
lofp-set:03
# Jedi Consular (LOFP_5), Acolyte of the Beyond (LOFP_8)
```

