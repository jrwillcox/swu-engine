# Known rules deviations

The engine follows the *Star Wars: Unlimited* Comprehensive Rules. This page lists
the places where it knowingly doesn't. Each one is also documented in the code, at
the card or engine function it affects; search `src/` for `DEVIATION` or
`simplification` to find them.

The list was last audited on 2026-11-23, when all ~200 notes in the code were read
and sorted, and updated on 2026-11-25. If you fix one, remove it from this page in the same change.

## Deviations that can change a game

These can produce a different result from a real game.

None are known. The last two were fixed on 2026-11-25 (see below).

One limit remains in the engine but no card reaches it: inside a conditional
branch ("if …, do A, then B"), a choice pushed by A doesn't hold back B. No
registered card has a choice-pushing effect before another effect in a branch.

A second limit hasn't been audited yet. When an ability creates a token unit and
a later effect of the same ability chooses a unit ("Create a Beast token. Deal 1
damage to a friendly ground unit"), the choice is offered before the token
exists, so the new token can't be picked. Run Amok HMW_194, Howl HMW_241 and
Geonosian Picador HMW_199 work around it. Older cards written as a plain "create
token, then targeted effect" list have not been checked.

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

## Fixed on 2026-11-25

- A defeated unit no longer keeps its damage in the discard pile. A unit played
  again from the discard pile (Second Chance SHD_53 and other free replays) came
  back with its old damage and was defeated again at once.
- An ability's effects resolve in printed order even when one of them asks for a
  choice. The effects after the choice now wait for it; before, they resolved
  first. For example, No Bargain SHD_244's draw now comes after the opponent's
  discard. This applies to triggered abilities, events and activated abilities.
- A target chosen for an effect that has automatic effects printed before it is no
  longer lost; the player used to be asked twice.
- Malakili LAW_212: a Creature in your deck counts as Underworld for deck searches,
  and so does one in your hand or discard for the "choose a card" filters there.
  Local Support HMW_148 sees it on the top card of the deck.
- Smuggle costs take every discount, tax and halving a hand play takes (pending and
  standing discounts, the card's own reductions, aspect-penalty waivers, Del Meeko,
  The Starhawk), and the discount is used up. Smuggle can also be paid with Credit
  tokens. Piloting costs take upgrade discounts (Congress of Malastare SEC_64,
  Guardian of the Whills SOR_61), per-name taxes and The Starhawk.
- First Light SHD_36's Smuggle cost also deals 4 damage to a friendly unit of your
  choice, and can't be smuggled without one.
- "You may play it" can be declined: Directed by the Force LOF_123, The Invisible
  Hand JTL_89, Old Daka LOF_36, Tear This Ship Apart LAW_66.
- Mandatory gives and exhausts can't be stopped early: Leia Organa SEC_4, Senate
  Warden SEC_59, No One Ever Knew SEC_196, Public Enemy SHD_68.
- "When Attack Ends" abilities that don't need the attacker to survive now resolve
  when it was defeated: Fett's Firespray LAW_252, Chirrut Îmwe LAW_46, Padmé Amidala
  TS26_4.
- Leia Organa SOR_9's undeployed attack is mandatory, and is followed by at most one
  optional attack with another Rebel.
- Cantwell Arrestor Cruiser SEC_37's "can't ready" lasts while it is in play, across
  rounds, and ends when it leaves play.
- A Saboteur granted for one attack ignores Sentinel when choosing the defender (Swoop
  Down SHD_230 and the other "attack with a unit, it gains Saboteur" cards).
- A two-unit attack (Darth Maul C24_6, TWI_135) handles First Strike per defender,
  The Stranger's "defender deals damage first", a combat-damage redirect and each
  defender's power debuffs, and both defenders' "when attacked" abilities fire.
- "Doesn't ready during the next regroup phase" skips exactly one ready step, so
  under Max Rebo's extra regroup the unit readies in the second one (Dryden Vos
  SEC_137, Patient Hunter LAW_73; the list had named LAW_69).
- Bamboozle SOR_199 can be played by discarding a Cunning card instead of paying.
- Bossk SHD_10's undeployed "you may give it +1/+0 for this phase" is offered.
- Bounty Posting SHD_228 offers to play the upgrade it found (the list had named
  Enticing Reward SHD_222).
- Enticing Reward SHD_222's collector discards after drawing the two cards, choosing
  from the hand that holds them.
- Malakili LAW_212: Creature units you own that aren't in play are Underworld (for
  play-from-hand trait filters and "next Underworld unit" discounts).
- Tear This Ship Apart LAW_66 can play an event or upgrade from the opponent's
  resources, not only a unit.
- Altering the Deal SHD_243 lets you choose the captured card; Reckless Sacrifice
  ASH_163 lets you choose the unit to discard, and the 5 damage can't be skipped.

## Fixed on 2026-11-24

- Every "discard a card" now lets the discarding player choose: about 25 cards that
  did their own discard (Merrin, Bail Organa, Profundity, Force Throw, Ninth
  Sister, Gungi, Bix Caleen, Zorii Bliss's regroup discard, Luthen's Haulcraft,
  Jedi in Hiding, and others), and the "discard a card" cost of activated abilities
  (Kylo Ren SHD_11, Dryden Vos SEC_7, Krrsantan LAW_84). Syril Karn SEC_133 and
  Kouhun Assassination TS26_33 now discard a chosen card, not a random one.
- "Look at an opponent's hand and discard a card from it" now lets you pick the
  card (Spark of Rebellion SOR_200, Bodhi Rook SOR_201).
- "Use this ability only once each round" is enforced for Cad Bane SHD_14, Cassian
  Andor SOR_13 and Agent Kallus SOR_115.
- A leader ability printed on both sides now works while the leader is undeployed
  (Director Krennic SOR_1, Gar Saxon SHD_1).
- A Vehicle takes one Pilot, plus any extra slots, on every Pilot play. R2-D2
  JTL_245 can join a piloted Vehicle and doesn't count against the limit (the
  official ruling).
- "You" in card-specific code is now the card's controller, not its owner (about
  700 places). A stolen unit's abilities work for the player who took it, and its
  When Defeated for the player who controlled it when it was defeated. An upgrade
  stays under the control of the player who played it, even on an enemy unit (the
  Comprehensive Rules). An event played from another player's cards resolves for
  the player who played it.
- "If a unit left play this phase" counts every way out of play: defeated,
  returned to hand, put on a deck or captured (Yoda TWI_4, Chancellor Palpatine
  TWI_203, Disturbance in the Force LOF_216, Let's Talk SEC_131, Fateful Goodbye
  ASH_211). Boba Fett SOR_15's "When an enemy unit leaves play" fires on all of
  them too.
- "When damage is dealt to this unit" now sees ability and indirect damage, not only
  combat damage (Jabba the Hutt SEC_2, The Elite Squad SEC_143). So do the
  "damaged a base this phase" counts (Cassian Andor SOR_13 and SEC_12, Forced
  Surrender SOR_175, Retaliation SEC_77), which also now count Overwhelm damage.
  Cassian Andor SOR_13's "When you deal damage to an enemy base" fires for any of
  your cards' damage, not only his own attacks.
- "Play a card from your hand" offers events and upgrades as well as units
  (Daimyo's Palace LAW_20 and the seven other LAW bases with the same Epic Action,
  Agent Kallus LAW_3, From a Certain Point of View LAW_264, Count Dooku TWI_5).
  Agent Kallus and From a Certain Point of View now ignore the card's whole aspect
  penalty, not just one aspect.
- A keyword granted "while attacking a (damaged / Bounty) unit" applies only to
  that attack, not at all times (Moff Gideon SHD_7, Jango Fett SHD_138, Miraj
  Scintel SEC_139).

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
