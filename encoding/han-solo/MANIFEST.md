# Encoding manifest — `han-solo`

Deck readiness: **52/52** cards playable. Encoding groups: **8/8** complete.

Encode one group per session: paste its **group id** into `docs/encode_group_prompt.md`, review, then run `python scripts/verify_encoding.py han-solo --group NN`.

## Groups (in dependency order)

| # | group id | kind | theme | cards | progress | new primitives | depends on |
|--:|----------|------|-------|------:|----------|----------------|------------|
| 1 | `han-solo:01` | keyword | Bounty keyword | 2 | 2/2 ✅ | — | — |
| 2 | `han-solo:02` | ability | Direct damage & removal | 1 | 1/1 ✅ | — | — |
| 3 | `han-solo:03` | ability | Card advantage & disruption | 4 | 4/4 ✅ | — | — |
| 4 | `han-solo:04` | ability | Combat tricks, buffs & tempo | 7 | 7/7 ✅ | — | — |
| 5 | `han-solo:05` | ability | Combat tricks, buffs & tempo | 3 | 3/3 ✅ | — | — |
| 6 | `han-solo:06` | ability | Miscellaneous abilities | 2 | 2/2 ✅ | — | — |
| 7 | `han-solo:07` | ability | New primitive: scaling-magnitude | 2 | 2/2 ✅ | scaling-magnitude | — |
| 8 | `han-solo:08` | ability | New primitive: control-change | 1 | 1/1 ✅ | control-change | — |

## Copy-paste entries

Paste the **id** line into the standing prompt. The card names are shown only so you know what you're submitting.

### `han-solo:01` — Bounty keyword (✅ done)
```
han-solo:01
# Clone Deserter (SHD_95), Cartel Turncoat (SHD_195)
```

### `han-solo:02` — Direct damage & removal (✅ done)
```
han-solo:02
# Greedo (SOR_204)
```

### `han-solo:03` — Card advantage & disruption (✅ done)
```
han-solo:03
# Wolf Pack Escort (TWI_191), Ezra Bridger (SOR_192), Shuttle Tydirium (JTL_200), BoShek (JTL_215)
```

### `han-solo:04` — Combat tricks, buffs & tempo (✅ done)
```
han-solo:04
# Han Solo (JTL_17), Nien Nunb (JTL_93), Blue Leader (JTL_96), Leia Organa (JTL_97), Huyang (TWI_110), Tandem Assault (JTL_124), It's a Trap (JTL_209)
```

### `han-solo:05` — Combat tricks, buffs & tempo (✅ done)
```
han-solo:05
# The Mandalorian (JTL_210), Death Space Skirmisher (JTL_217), Millennium Falcon (JTL_249)
```

### `han-solo:06` — Miscellaneous abilities (✅ done)
```
han-solo:06
# Chewbacca (JTL_103), R2-D2 (JTL_245)
```

### `han-solo:07` — New primitive: scaling-magnitude (✅ done)
```
han-solo:07
# Admiral Ackbar (SOR_97), Never Tell Me the Odds (JTL_208)
```

### `han-solo:08` — New primitive: control-change (✅ done)
```
han-solo:08
# Commandeer (JTL_235)
```

