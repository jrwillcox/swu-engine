# Encoding manifest — `shd-han-solo`

Deck readiness: **52/52** cards playable. Encoding groups: **10/10** complete.

Encode one group per session: paste its **group id** into `docs/encode_group_prompt.md`, review, then run `python scripts/verify_encoding.py shd-han-solo --group NN`.

## Groups (in dependency order)

| # | group id | kind | theme | cards | progress | new primitives | depends on |
|--:|----------|------|-------|------:|----------|----------------|------------|
| 1 | `shd-han-solo:01` | keyword | Smuggle keyword | 7 | 7/7 ✅ | grant-keyword-to-resources | — |
| 2 | `shd-han-solo:02` | keyword | Bounty keyword | 2 | 2/2 ✅ | control-change | — |
| 3 | `shd-han-solo:03` | ability | Card advantage & disruption | 1 | 1/1 ✅ | — | — |
| 4 | `shd-han-solo:04` | ability | Combat tricks, buffs & tempo | 2 | 2/2 ✅ | — | — |
| 5 | `shd-han-solo:05` | ability | New primitive: play-from-hand-act-on-result | 1 | 1/1 ✅ | play-from-hand-act-on-result | — |
| 6 | `shd-han-solo:06` | ability | New primitive: repeated-modal-per-X | 1 | 1/1 ✅ | repeated-modal-per-X | — |
| 7 | `shd-han-solo:07` | ability | New primitive: sacrifice-resource-cost | 1 | 1/1 ✅ | sacrifice-resource-cost | — |
| 8 | `shd-han-solo:08` | ability | New primitive: scaling-magnitude | 1 | 1/1 ✅ | scaling-magnitude | — |
| 9 | `shd-han-solo:09` | ability | New primitive: granted-attack-restricted-attacker | 1 | 1/1 ✅ | granted-attack-restricted-attacker | — |
| 10 | `shd-han-solo:10` | ability | New primitive: opponent-chooses-target | 1 | 1/1 ✅ | opponent-chooses-target | — |

## Copy-paste entries

Paste the **id** line into the standing prompt. The card names are shown only so you know what you're submitting.

### `shd-han-solo:01` — Smuggle keyword (✅ done)
```
shd-han-solo:01
# Cassian Andor (SHD_148), Nite Owl Skirmisher (SHD_149), Reckless Gunslinger (SHD_160), Hotshot DL-44 Blaster (SHD_174), Armed to the Teeth (SHD_175), Tech (SHD_248), Smuggler's Aid (SHD_252)
```

### `shd-han-solo:02` — Bounty keyword (✅ done)
```
shd-han-solo:02
# Stolen Landspeeder (SHD_161), Unlicensed Headhunter (SHD_165)
```

### `shd-han-solo:03` — Card advantage & disruption (✅ done)
```
shd-han-solo:03
# Wookiee Warrior (SHD_249)
```

### `shd-han-solo:04` — Combat tricks, buffs & tempo (✅ done)
```
shd-han-solo:04
# Hunting Nexu (SHD_168), Protector of the Throne (SHD_247)
```

### `shd-han-solo:05` — New primitive: play-from-hand-act-on-result (✅ done)
```
shd-han-solo:05
# Han Solo (SHD_13)
```

### `shd-han-solo:06` — New primitive: repeated-modal-per-X (✅ done)
```
shd-han-solo:06
# Poe Dameron (SHD_153)
```

### `shd-han-solo:07` — New primitive: sacrifice-resource-cost (✅ done)
```
shd-han-solo:07
# Wrecker (SHD_154)
```

### `shd-han-solo:08` — New primitive: scaling-magnitude (✅ done)
```
shd-han-solo:08
# The Chaos of War (SHD_159)
```

### `shd-han-solo:09` — New primitive: granted-attack-restricted-attacker (✅ done)
```
shd-han-solo:09
# Desperate Attack (SHD_179)
```

### `shd-han-solo:10` — New primitive: opponent-chooses-target (✅ done)
```
shd-han-solo:10
# Grey Squadron Y-Wing (SHD_246)
```

