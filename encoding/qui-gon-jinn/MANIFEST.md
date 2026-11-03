# Encoding manifest — `qui-gon-jinn`

Deck readiness: **52/52** cards playable. Encoding groups: **6/6** complete.

Encode one group per session: paste its **group id** into `docs/dev/encode_group_prompt.md`, review, then run `python scripts/verify_encoding.py qui-gon-jinn --group NN`.

## Groups (in dependency order)

| # | group id | kind | theme | cards | progress | new primitives | depends on |
|--:|----------|------|-------|------:|----------|----------------|------------|
| 1 | `qui-gon-jinn:01` | ability | Direct damage & removal | 2 | 2/2 ✅ | — | — |
| 2 | `qui-gon-jinn:02` | ability | Card advantage & disruption | 3 | 3/3 ✅ | — | — |
| 3 | `qui-gon-jinn:03` | ability | Combat tricks, buffs & tempo | 7 | 7/7 ✅ | — | — |
| 4 | `qui-gon-jinn:04` | ability | Combat tricks, buffs & tempo | 1 | 1/1 ✅ | — | — |
| 5 | `qui-gon-jinn:05` | ability | Miscellaneous abilities | 2 | 2/2 ✅ | — | — |
| 6 | `qui-gon-jinn:06` | ability | New primitive: force-token | 7 | 7/7 ✅ | force-token | — |

## Copy-paste entries

Paste the **id** line into the standing prompt. The card names are shown only so you know what you're submitting.

### `qui-gon-jinn:01` — Direct damage & removal (✅ done)
```
qui-gon-jinn:01
# Stinger Mantis (LOF_198), Sneak Attack (SOR_219)
```

### `qui-gon-jinn:02` — Card advantage & disruption (✅ done)
```
qui-gon-jinn:02
# Luminous Beings (LOF_104), R2-D2 (TWI_193), J-Type Nubian Starship (LOF_194)
```

### `qui-gon-jinn:03` — Combat tricks, buffs & tempo (✅ done)
```
qui-gon-jinn:03
# Obi-Wan Kenobi (LOF_96), Maz Kanata (SHD_96), Paladin Training Corvette (LOF_99), Maz Kanata (LOF_111), Ahsoka Tano (JTL_201), Qui-Gon Jinn's Lightsaber (LOF_201), Refugee of The Path (LOF_242)
```

### `qui-gon-jinn:04` — Combat tricks, buffs & tempo (✅ done)
```
qui-gon-jinn:04
# Curious Flock (LOF_255)
```

### `qui-gon-jinn:05` — Miscellaneous abilities (✅ done)
```
qui-gon-jinn:05
# Kelleran Beq (LOF_100), Qui-Gon Jinn's Aethersprite (LOF_197)
```

### `qui-gon-jinn:06` — New primitive: force-token (✅ done)
```
qui-gon-jinn:06
# Qui-Gon Jinn (LOF_16), Jedi Temple (LOF_23), Youngling Padawan (LOF_193), Jedi Sentinel (LOF_196), Impossible Escape (LOF_218), The Will of the Force (LOF_227), Luke Skywalker (LOF_249)
```

