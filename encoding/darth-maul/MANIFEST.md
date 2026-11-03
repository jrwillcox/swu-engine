# Encoding manifest — `darth-maul`

Deck readiness: **52/52** cards playable. Encoding groups: **5/5** complete.

Encode one group per session: paste its **group id** into `docs/dev/encode_group_prompt.md`, review, then run `python scripts/verify_encoding.py darth-maul --group NN`.

## Groups (in dependency order)

| # | group id | kind | theme | cards | progress | new primitives | depends on |
|--:|----------|------|-------|------:|----------|----------------|------------|
| 1 | `darth-maul:01` | ability | Direct damage & removal | 5 | 5/5 ✅ | — | — |
| 2 | `darth-maul:02` | ability | Card advantage & disruption | 1 | 1/1 ✅ | — | — |
| 3 | `darth-maul:03` | ability | Combat tricks, buffs & tempo | 3 | 3/3 ✅ | — | — |
| 4 | `darth-maul:04` | ability | New primitive: force-token | 7 | 7/7 ✅ | force-token | — |
| 5 | `darth-maul:05` | ability | New primitive: force-token | 5 | 5/5 ✅ | force-token | — |

## Copy-paste entries

Paste the **id** line into the standing prompt. The card names are shown only so you know what you're submitting.

### `darth-maul:01` — Direct damage & removal (✅ done)
```
darth-maul:01
# Pong Krell (LOF_38), Fallen Lightsaber (SOR_137), Sith Holocron (LOF_138), Count Dooku (TWI_138), Merrin (LOF_160)
```

### `darth-maul:02` — Card advantage & disruption (✅ done)
```
darth-maul:02
# Nightsister Warrior (LOF_59)
```

### `darth-maul:03` — Combat tricks, buffs & tempo (✅ done)
```
darth-maul:03
# Oggdo Bogdo (LOF_63), Darth Maul's Lightsaber (LOF_140), Scimitar (LOF_233)
```

### `darth-maul:04` — New primitive: force-token (✅ done)
```
darth-maul:04
# Darth Maul (LOF_9), Shadowed Undercity (LOF_21), Karis (LOF_31), Talzin's Assassin (LOF_35), Darth Sidious (LOF_39), Drain Essence (LOF_41), Chirrut Îmwe (LOF_67)
```

### `darth-maul:05` — New primitive: force-token (✅ done)
```
darth-maul:05
# Acolyte of the Beyond (LOF_129), Savage Opress (LOF_137), Infused Brawler (LOF_156), Kylo Ren (LOF_229), Darth Tyranus (LOF_231)
```

