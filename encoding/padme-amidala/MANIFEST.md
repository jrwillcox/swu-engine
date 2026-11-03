# Encoding manifest — `padme-amidala`

Deck readiness: **52/52** cards playable. Encoding groups: **5/5** complete.

Encode one group per session: paste its **group id** into `docs/dev/encode_group_prompt.md`, review, then run `python scripts/verify_encoding.py padme-amidala --group NN`.

## Groups (in dependency order)

| # | group id | kind | theme | cards | progress | new primitives | depends on |
|--:|----------|------|-------|------:|----------|----------------|------------|
| 1 | `padme-amidala:01` | ability | Card advantage & disruption | 2 | 2/2 ✅ | — | — |
| 2 | `padme-amidala:02` | ability | Combat tricks, buffs & tempo | 7 | 7/7 ✅ | — | — |
| 3 | `padme-amidala:03` | ability | Combat tricks, buffs & tempo | 3 | 3/3 ✅ | — | — |
| 4 | `padme-amidala:04` | ability | Miscellaneous abilities | 7 | 7/7 ✅ | — | — |
| 5 | `padme-amidala:05` | ability | New primitive: reveal-or-discard-trigger | 1 | 1/1 ✅ | reveal-or-discard-trigger | — |

## Copy-paste entries

Paste the **id** line into the standing prompt. The card names are shown only so you know what you're submitting.

### `padme-amidala:01` — Card advantage & disruption (✅ done)
```
padme-amidala:01
# Mina Bonteri (SEC_94), Furtive Handmaiden (SEC_197)
```

### `padme-amidala:02` — Combat tricks, buffs & tempo (✅ done)
```
padme-amidala:02
# Ahsoka Tano (SEC_96), Captain Typho (SEC_98), Naboo Royal Starship (SEC_99), Seasoned Fleet Admiral (JTL_111), Jar Jar Binks (SEC_111), Nubian Star Skiff (SEC_116), Dogfight (JTL_123)
```

### `padme-amidala:03` — Combat tricks, buffs & tempo (✅ done)
```
padme-amidala:03
# With Thunderous Applause (SEC_129), Anakin Skywalker (SEC_201), Bog Down in Procedure (SEC_234)
```

### `padme-amidala:04` — Miscellaneous abilities (✅ done)
```
padme-amidala:04
# Dismantle the Conspiracy (SEC_106), Taylander Shuttle (SEC_115), Naboo Security Force (SEC_120), Charged with Corruption (SEC_127), Hunter (SEC_208), B2EMO (SEC_248), Moral Authority (SEC_256)
```

### `padme-amidala:05` — New primitive: reveal-or-discard-trigger (✅ done)
```
padme-amidala:05
# Padmé Amidala (SEC_16)
```

