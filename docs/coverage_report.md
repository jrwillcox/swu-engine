# Coverage Report

Total cards in DB: **3277** | Registered in ability registry: **2548**

## Summary by card type

| Type | Vanilla | Kw-Complete | Implemented | Escape-Hatch | Kw-Deferred | Text-Bearing | Total |
|------|--------:|------------:|------------:|-------------:|------------:|-------------:|------:|
| Base | 79 | 0 | 44 | 0 | 0 | 0 | 123 |
| Credit Token | 0 | 0 | 1 | 0 | 0 | 1 | 2 |
| Event | 0 | 0 | 514 | 0 | 0 | 19 | 533 |
| Force Token | 0 | 0 | 1 | 0 | 0 | 0 | 1 |
| Leader | 0 | 0 | 181 | 0 | 0 | 10 | 191 |
| Token Unit | 0 | 2 | 15 | 0 | 0 | 0 | 17 |
| Token Upgrade | 2 | 0 | 19 | 0 | 0 | 1 | 22 |
| Unit | 116 | 332 | 1620 | 0 | 0 | 111 | 2179 |
| Upgrade | 11 | 5 | 189 | 0 | 0 | 4 | 209 |
| **TOTAL** | **208** | **339** | **2584** | **0** | **0** | **146** | **3277** |

## Classification definitions
- **vanilla**: no keywords, no ability text — Phase 1 handles fully
- **keyword-complete**: only Phase 2 keywords (Grit, Raid, Sentinel, etc.) — Phase 2 handles fully
- **implemented**: registered in the ability registry with declarative or custom logic
- **escape-hatch**: registered with `escape_hatch=True` — simplified or stub implementation
- **keyword-deferred**: has an unimplemented Phase 3 keyword (Support)
- **text-bearing**: has ability text but NOT yet registered — implementation gap

**Playable** (vanilla + kw-complete + implemented): 3131 (95.5%)

## Phase 2 keyword counts
| Keyword | Cards |
|---------|------:|
| Sentinel | 251 |
| Raid | 179 |
| Overwhelm | 171 |
| Ambush | 155 |
| Restore | 151 |
| Saboteur | 124 |
| Shielded | 113 |
| Hidden | 113 |
| Grit | 80 |
| Piloting | 61 |
| Plot | 43 |
| Support | 38 |
| Smuggle | 35 |
| Bounty | 33 |
| Exploit | 26 |
| Coordinate | 25 |
| Fortify | 17 |

## Deferred keyword counts
| Keyword | Cards |
|---------|------:|

## Escape-hatch cards (simplified implementations)
| Set | Number | Name |
|-----|-------:|------|
