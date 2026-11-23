# Known rules deviations

The engine follows the *Star Wars: Unlimited* Comprehensive Rules. This page lists
the places where it knowingly doesn't. Each one is also documented in the code, at
the card or engine function it affects; search `src/` for `DEVIATION` or
`simplification` to find them.

The list was last audited on 2026-11-23, when all ~200 notes in the code were read
and sorted. If you fix one, remove it from this page in the same change.

## Deviations that can change a game

These can produce a different result from a real game.

### Choices made for the player

| What happens | Cards |
|---|---|
| A hand discard written as card-specific code takes the **first card in hand** instead of letting the discarding player choose. (The shared `DiscardFromHand` effect lets them choose. About 25 cards still do their own discard; search `hand.pop(0)`.) | Merrin LOF_160, Bail Organa SEC_198, Profundity JTL_154, Spark of Rebellion SOR_200, SOR_201, Force Throw SOR_167, SOR_175, Jedi in Hiding LOF_159, Zorii Bliss SHD_203 (regroup discard), ASH_147, ASH_148, LAW_186, LAW_203, LOF_138, SEC_88, JTL_216, G25_2, P26_42, SHD_194, and the discard cost of activated abilities (`DiscardCardCost`) |
| A card that says "play a card" only offers units. | LAW_20, TWI_2; LOF_10 offers events but not upgrades |
| Some "you may play it" plays are mandatory: the play-from-hand decision has no decline. | LOF_1, LOF_123, The Invisible Hand JTL_89 |
| Some mandatory "give a token / exhaust" effects can be stopped early, because they reuse an "up to" decision. | SEC_4, SEC_59, SEC_196, SHD_68 |

### Timing and triggers

| What happens | Cards |
|---|---|
| "If a unit left play this phase" counts only defeated units. Bounced or captured units are missed. | Yoda TWI_4, LOF_216, SEC_131, Fateful Goodbye ASH_211, SOR_15 |
| "Use this ability only once each round" is not enforced. | Cad Bane SHD_14 (deployed), Cassian Andor SOR_13 (deployed), SOR_115 |
| "When this unit is dealt damage" and similar observers fire on combat damage only, not ability or indirect damage. | Jabba the Hutt SEC_2, SEC_143 |
| Base-damage ledgers count combat damage only. | Cassian Andor SOR_13, SOR_175, SEC_12 |
| "When this unit attacks and defeats a unit" and "when this attack ends" need the attacker to survive the attack. | LAW_252, Chirrut LAW_46, Padmé TS26_2 |
| A decision pushed in the middle of an ability resolves after that ability's remaining automatic effects. Cards whose order matters use a rider instead (Furtive Handmaiden SEC_197's draw follows its discard choice). | Any two-part ability where the second part reads the first |

### Board state

| What happens | Cards |
|---|---|
| A leader's constant ability printed on **both** sides applies only while the leader is deployed. | Director Krennic SOR_1, Moff Gideon SHD_1 |
| A Vehicle can take more than one Pilot through an ordinary Pilot play. The one-Pilot limit is checked only when a leader deploys as a Pilot. | Any Piloting unit |
| A keyword granted "while attacking a <kind of> unit" is shown on the unit at all times. Overwhelm only matters during an attack, so the effect is an attack on an undamaged or bounty-less defender gaining Overwhelm. | Moff Gideon SHD_7, Jango Fett SHD_138, SEC_139 |
| A Saboteur or First Strike granted for one attack doesn't let the attacker ignore Sentinel when choosing a defender. | Swoop Down SHD_230, Shoot First |
| "Can't ready while this unit is in play" lasts until the end of the round instead. | Cantwell Arrestor Cruiser SEC_37 |
| A two-unit attack is always simultaneous: no First Strike, and only the first defender's "when attacked" fires. | Darth Maul C24_6 |
| Some per-round flags carry through Max Rebo's extra regroup phase. | LAW_69, SEC_137 |

### Control

The target filters, the conditions and the shared effects all judge "friendly",
"enemy" and "you" by who **controls** a card. Some older card-specific code still
reads the card's **owner** instead. That only matters for a unit whose control has
changed (Traitorous, Change of Heart, Stolen Landspeeder, Maul LAW_54). An event
played from another player's deck also still resolves for its owner.

### Costs and riders

| What happens | Cards |
|---|---|
| Smuggle and Piloting costs ignore play discounts and taxes. Every other way of playing a card applies them. | Smuggle and Piloting cards |
| Smuggle riders such as "deal 4 damage to a friendly unit" aren't charged. | First Light SHD_36, and the other Smuggle cards with a rider |
| An alternative cost ("discard a Cunning card instead of paying") isn't offered. | SOR_199 |
| An optional extra is left out. | Bossk SHD_10 (undeployed +1/+0), SHD_222 (play the found upgrade), Malakili LAW_212 (out-of-play Creatures gaining Underworld) |
| Leia Organa's undeployed attack is optional, and the follow-up can repeat with every Rebel instead of once. | Leia Organa SOR_9 |

## Shortcuts that don't change a sensible game

These remove a choice nobody would make differently, or change only how something
is shown. They are documented at each card. The main patterns:

- **"Choose a player" goes to the obvious player.** Opponents discard; you draw.
- **Interchangeable cards are picked automatically.** Face-down resources, and
  "exhaust the best ready enemy unit" when that's the only sensible pick.
- **"Up to N" takes the maximum** when more is always better. Examples: heal as
  much as possible (SEC_3, LOF_246), and defeat every upgrade on the chosen unit
  (SOR_167, SOR_170).
- **Replacement effects are applied afterwards.** For example, ASH_83 creates the
  extra tokens after the normal ones, and a Shield-priced prevention is used
  automatically (ASH_62). The board ends the same.
- **Naming a card offers only names in the opponent's hand.** Naming anything else
  can only miss (Chimaera SOR_185, Garindan SEC_186, SEC_210, SEC_260).
- **Cosmetic order or timing.** Examples: a "reveal" read without showing the card
  (JTL_17), and a top-card peek after the regroup draw (TWI_40).

## Fixed on 2026-11-23

- Plays made by card abilities, and Exploit plays from hand, now count as plays.
  They fire "when you play a card" abilities and the per-phase play counts.
- Play discounts, taxes and cost halving now apply to plays made by abilities, and
  each discount is used up exactly once.
- The shared "discard a card" effect, K-2SO's and Poe's discards, and Rash Action
  now let the discarding player choose. Garindan now names a card.
- "Friendly" and "enemy" now follow control in the shared targeting, conditions and
  effects. A unit taken by a card is returned, and captured cards are released,
  when that card leaves play in any way, not only when it is defeated.
- Exploit is offered when an ability plays the card (Ezra Bridger SOR_192).
- An undeployed leader is a legal "(leader or unit)" target (Soulless One TWI_179).
- A keyword granted only by another card's aura now counts as "having a keyword"
  (Boba Fett SHD_8, Rex HMW_141).
- A granted attack's follow-ups ("attack with another unit", "then defeat it") now
  happen even when the attack pauses for a choice.
- A unit's HP can now reach 0, so −X/−X effects can defeat an undamaged unit.
