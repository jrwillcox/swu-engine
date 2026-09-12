# Encoding manifest — `jabba-the-hutt`

Deck readiness: **52/52** cards playable. Encoding groups: **8/8** complete.

Encode one group per session: paste its **group id** into `docs/encode_group_prompt.md`, review, then run `python scripts/verify_encoding.py jabba-the-hutt --group NN`.

## Groups (in dependency order)

| # | group id | kind | theme | cards | progress | new primitives | depends on |
|--:|----------|------|-------|------:|----------|----------------|------------|
| 1 | `jabba-the-hutt:01` | keyword | Plot keyword | 2 | 2/2 ✅ | — | — |
| 2 | `jabba-the-hutt:02` | keyword | Hidden keyword | 1 | 1/1 ✅ | opponent-chooses-target | — |
| 3 | `jabba-the-hutt:03` | ability | Direct damage & removal | 3 | 3/3 ✅ | — | — |
| 4 | `jabba-the-hutt:04` | ability | Card advantage & disruption | 3 | 3/3 ✅ | — | — |
| 5 | `jabba-the-hutt:05` | ability | Combat tricks, buffs & tempo | 6 | 6/6 ✅ | — | — |
| 6 | `jabba-the-hutt:06` | ability | Miscellaneous abilities | 2 | 2/2 ✅ | — | — |
| 7 | `jabba-the-hutt:07` | ability | New primitive: create-token-unit | 4 | 4/4 ✅ | create-token-unit | — |
| 8 | `jabba-the-hutt:08` | ability | New primitive: control-change | 1 | 1/1 ✅ | control-change | — |

## Copy-paste entries

Paste the **id** line into the standing prompt. The card names are shown only so you know what you're submitting.

### `jabba-the-hutt:01` — Plot keyword (✅ done)
```
jabba-the-hutt:01
# Garindan (SEC_186), Lurking Snub Fighter (SEC_189)
```

### `jabba-the-hutt:02` — Hidden keyword (✅ done)
```
jabba-the-hutt:02
# Jabba's Rancor (LAW_216)
```

### `jabba-the-hutt:03` — Direct damage & removal (✅ done)
```
jabba-the-hutt:03
# The Sarlacc of Carkoon (LAW_163), Boba Fett (LAW_214), Contracted Hunter (JTL_216)
```

### `jabba-the-hutt:04` — Card advantage & disruption (✅ done)
```
jabba-the-hutt:04
# Great Pit of Carkoon (LAW_23), Syndicate Spice Runner (LAW_136), The Axe Forgets (LAW_246)
```

### `jabba-the-hutt:05` — Combat tricks, buffs & tempo (✅ done)
```
jabba-the-hutt:05
# 4-LOM (LAW_65), Khetanna (LAW_158), Haymaker (LAW_168), Salacious Crumb (LAW_210), Weequay Pirate (LAW_231), Black Sun Cabalist (LAW_249)
```

### `jabba-the-hutt:06` — Miscellaneous abilities (✅ done)
```
jabba-the-hutt:06
# Malakili (LAW_212), Vermillion (LAW_215)
```

### `jabba-the-hutt:07` — New primitive: create-token-unit (✅ done)
```
jabba-the-hutt:07
# Jabba the Hutt (LAW_15), Bib Fortuna (LAW_134), Unmarked Credits (LAW_244), Fett's Firespray (LAW_252)
```

### `jabba-the-hutt:08` — New primitive: control-change (✅ done)
```
jabba-the-hutt:08
# Double-Cross (LAW_170)
```

