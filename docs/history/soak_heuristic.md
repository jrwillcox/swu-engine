# SWU Soak Campaign Report

Generated: 2026-06-15T15:14:19.106638Z
Total games: 500  OK: 500  Failed: 0  Elapsed: 376.0s

## ⚠ Anomalies flagged

- Seat win rate for P0 is 65.6% (outside 35–65%).
- Seat win rate for P1 is 34.4% (outside 35–65%).
- ⚠ 3 zero-fire active ability(ies) on cards REACHABLE in this campaign's decks (likely no-op/stub bug): SOR_234, SOR_78, SOR_92.

## Win Rates

- P0: 328 wins (65.6%)
- P1: 172 wins (34.4%)

## Game Length

Actions — {'min': 61, 'max': 271, 'mean': 134.1, 'p25': 109, 'p50': 131, 'p75': 157}
Rounds  — {'min': 5, 'max': 18, 'mean': 9.5, 'p25': 8, 'p50': 9, 'p75': 11}

## Leader Deploy Rates

- P0: 98.8% (avg round 5.88)
- P1: 100.0% (avg round 5.0)

## Action Kind Frequencies

- AttackWithUnit: 15940
- PlayCard: 11418
- ResourceCard: 10474
- ChooseTarget: 5894
- Pass: 4543
- ClaimInitiative: 4423
- ContinueAttack: 3825
- AcceptTrigger: 3538
- UseAbility: 2518
- DeployLeader: 994
- KeepHand: 887
- KeepTopCard: 520
- ChooseNumber: 515
- UseAmbush: 375
- DrawTopCard: 181
- ChooseModalOption: 168
- ChooseModalTarget: 168
- AutoResolveEffects: 141
- SelectSearchCard: 116
- DeclineAmbush: 114

## Ability Coverage

Registered abilities: 45  Fired at least once: 36  Passive (constant-only): 6  Zero-fire active: 3

**ZERO-FIRE ACTIVE abilities (investigate each):**
- SOR_234 (EventAbility)  ⚠ REACHABLE (likely bug)
- SOR_78 (EventAbility)  ⚠ REACHABLE (likely bug)
- SOR_92 (EventAbility)  ⚠ REACHABLE (likely bug)

Passive constant-only abilities (expected zero via the resolver tracker; active whenever the card is in play):
  SOR_198, SOR_230, SOR_242, SOR_48, SOR_79, SOR_89

### Fire counts (effects resolved across the campaign)
- SOR_10: 3036
- SOR_123: 14
- SOR_126: 6
- SOR_129: 105
- SOR_130: 120
- SOR_132: 77
- SOR_135: 4
- SOR_136: 13
- SOR_139: 5
- SOR_172: 6
- SOR_189: 168
- SOR_196: 55
- SOR_217: 14
- SOR_218: 40
- SOR_220: 17
- SOR_222: 7
- SOR_226: 141
- SOR_227: 128
- SOR_228: 142
- SOR_231: 25
- SOR_233: 9
- SOR_236: 520
- SOR_238: 515
- SOR_240: 171
- SOR_241: 36
- SOR_244: 59
- SOR_45: 49
- SOR_49: 19
- SOR_5: 2450
- SOR_53: 18
- SOR_59: 897
- SOR_74: 29
- SOR_83: 99
- SOR_84: 51
- SOR_86: 28
- SOR_88: 5

## Effect Efficacy

**No fired-but-whiffed abilities** — every ability that resolved a targeted effect hit a target at least once.

### Per-ability efficacy (fired / targets / nominal amount)
- SOR_10: fired 3036, targets 3036, amount 4474 [DealDamage×3036]
- SOR_123: fired 14, targets 0, amount 0 [CustomEffect×14]
- SOR_126: fired 6, targets 0, amount 0 [CustomEffect×6]
- SOR_129: fired 105, targets 0, amount 0 [CustomEffect×105]
- SOR_130: fired 120, targets 0, amount 0 [CustomEffect×120]
- SOR_132: fired 77, targets 77, amount 231 [DealDamage×77]
- SOR_135: fired 4, targets 0, amount 0 [CustomEffect×4]
- SOR_136: fired 13, targets 13, amount 0 [CustomEffect×13]
- SOR_139: fired 5, targets 4, amount 0 [CustomEffect×5]
- SOR_172: fired 6, targets 6, amount 24 [DealDamage×6]
- SOR_189: fired 168, targets 0, amount 0 [CustomEffect×168]
- SOR_196: fired 55, targets 55, amount 0 [ReadyCard×55]
- SOR_217: fired 14, targets 0, amount 0 [CustomEffect×14]
- SOR_218: fired 40, targets 40, amount 20 [ExhaustCard×20,GiveToken×20]
- SOR_220: fired 17, targets 0, amount 0 [CustomEffect×17]
- SOR_222: fired 7, targets 7, amount 0 [ReturnToHand×7]
- SOR_226: fired 141, targets 141, amount 0 [ReadyCard×141]
- SOR_227: fired 128, targets 0, amount 0 [CustomEffect×128]
- SOR_228: fired 142, targets 0, amount 0 [CustomEffect×142]
- SOR_231: fired 25, targets 23, amount 50 [GiveToken×25]
- SOR_233: fired 9, targets 9, amount 0 [CustomEffect×9]
- SOR_236: fired 520, targets 0, amount 0 [CustomEffect×520]
- SOR_238: fired 515, targets 0, amount 0 [CustomEffect×515]
- SOR_240: fired 171, targets 0, amount 0 [CustomEffect×171]
- SOR_241: fired 36, targets 34, amount 72 [GiveToken×36]
- SOR_244: fired 59, targets 2, amount 0 [ExhaustCard×59]
- SOR_45: fired 49, targets 0, amount 49 [DrawCards×49]
- SOR_49: fired 19, targets 19, amount 0 [CustomEffect×19]
- SOR_5: fired 2450, targets 1524, amount 2450 [GiveToken×2450]
- SOR_53: fired 18, targets 0, amount 0 [CustomEffect×18]
- SOR_59: fired 897, targets 897, amount 1794 [Heal×897]
- SOR_74: fired 29, targets 29, amount 87 [Heal×29]
- SOR_83: fired 99, targets 0, amount 0 [CustomEffect×99]
- SOR_84: fired 51, targets 0, amount 0 [CustomEffect×51]
- SOR_86: fired 28, targets 28, amount 0 [GrantKeyword×28]
- SOR_88: fired 5, targets 5, amount 15 [DealDamage×5]

## Game-length tail

Action cap: 2000
No games ran within 90% of the action cap.

## Determinism re-run

All re-run sampled games reproduced identically.