# Soak results

Bot-vs-bot campaigns run with `scripts/soak.py`, with the invariant oracle
checking the game state after every action. A failure is a crash, an invariant
break, or a game reaching the action cap. Every campaign also replayed a sample
of games from the same seed and got identical results.

| Campaign | Date | Games | Failures |
|---|---|---:|---:|
| Heuristic bot | 2026-06-15 | 500 | 0 |
| Deck: Ahsoka Tano | 2026-06-27 | 2,000 | 0 |
| Deck: Jabba the Hutt | 2026-06-27 | 2,000 | 0 |
| Deck: Leia Organa | 2026-06-27 | 2,000 | 0 |
| Deck: Moff Gideon | 2026-06-27 | 2,000 | 0 |
| Deck: Sabine (Mean Green) | 2026-06-27 | 2,000 | 0 |
| Deck: Han Solo (SHD) | 2026-06-27 | 2,000 | 0 |
| Deck: The Mandalorian | 2026-06-27 | 2,000 | 0 |
| Default run | 2026-08-29 | 200 | 0 |
| Heuristic-bot overhaul | 2026-08-31 | 400 | 0 |
| **Total** | | **15,100** | **0** |

The full per-run reports (win rates, game lengths, ability coverage) are in git
history before this file was added. A new run writes its report to the
gitignored `soak_reports/`; see [testing.md](testing.md#soak-campaigns).
