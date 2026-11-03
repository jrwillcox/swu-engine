# Encoding manifest — `ahsoka-tano`

Deck readiness: **52/52** cards playable. Encoding groups: **6/6** complete.

Encode one group per session: paste its **group id** into `docs/dev/encode_group_prompt.md`, review, then run `python scripts/verify_encoding.py ahsoka-tano --group NN`.

## Groups (in dependency order)

| # | group id | kind | theme | cards | progress | new primitives | depends on |
|--:|----------|------|-------|------:|----------|----------------|------------|
| 1 | `ahsoka-tano:01` | keyword | Coordinate keyword | 9 | 9/9 ✅ | — | — |
| 2 | `ahsoka-tano:02` | ability | Direct damage & removal | 2 | 2/2 ✅ | — | — |
| 3 | `ahsoka-tano:03` | ability | Card advantage & disruption | 2 | 2/2 ✅ | — | — |
| 4 | `ahsoka-tano:04` | ability | Combat tricks, buffs & tempo | 7 | 7/7 ✅ | — | — |
| 5 | `ahsoka-tano:05` | ability | New primitive: create-token-unit | 4 | 4/4 ✅ | create-token-unit | — |
| 6 | `ahsoka-tano:06` | ability | New primitive: scaling-magnitude | 1 | 1/1 ✅ | scaling-magnitude | — |

## Copy-paste entries

Paste the **id** line into the standing prompt. The card names are shown only so you know what you're submitting.

### `ahsoka-tano:01` — Coordinate keyword (✅ done)
```
ahsoka-tano:01
# Ahsoka Tano (TWI_11), Echo (TWI_90), Coruscant Guard (TWI_106), Clone Commander Cody (TWI_114), Anakin Skywalker (TWI_147), Clone Heavy Gunner (TWI_158), Hevy (TWI_164), 332nd Stalwart (TWI_240), Republic Commando (TWI_243)
```

### `ahsoka-tano:02` — Direct damage & removal (✅ done)
```
ahsoka-tano:02
# Grenade Strike (TWI_171), Open Fire (TWI_174)
```

### `ahsoka-tano:03` — Card advantage & disruption (✅ done)
```
ahsoka-tano:03
# Patrolling V-Wing (TWI_107), Tranquility (TWI_246)
```

### `ahsoka-tano:04` — Combat tricks, buffs & tempo (✅ done)
```
ahsoka-tano:04
# Republic Tactical Officer (TWI_91), Admiral Yularen (TWI_92), 501st Liberator (TWI_109), Outflank (TWI_123), Encouraging Leadership (TWI_126), Anakin's Interceptor (TWI_142), Ahsoka's Padawan Lightsaber (TWI_248)
```

### `ahsoka-tano:05` — New primitive: create-token-unit (✅ done)
```
ahsoka-tano:05
# Shaak Ti (TWI_94), Captain Rex (TWI_97), Batch Brothers (TWI_144), Drop In (TWI_251)
```

### `ahsoka-tano:06` — New primitive: scaling-magnitude (✅ done)
```
ahsoka-tano:06
# Synchronized Strike (TWI_99)
```

