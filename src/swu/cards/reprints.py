"""Reprint aliasing — make exact printed-face duplicates playable for free.

Many cards in ``data/swu.db`` are exact reprints of another card: the same
printed face (name, subtitle, type, cost, stats, rules text) with a different
``set_code``/``card_number`` and art (promos, prerelease variants, starter-deck
reprints). A reprint already carries correct stats/keywords/traits/aspects from
its own DB row; the *only* thing it lacks is an entry in the ability registry.

This module **aliases** a reprint's ``(set_code, card_number)`` registry key onto
an implemented twin's specs — copying ``_REGISTRY[canonical]`` (and escape-hatch
membership) onto the reprint key at import time, before any card is hydrated by
``repository._hydrate``. Both the runtime resolver and the keyword sanitizer
resolve abilities via ``get_abilities(set_code, card_number)``, so an aliased
reprint becomes fully playable with no duplicated card logic.

``REPRINT_ALIASES`` maps ``reprint -> canonical``. It is populated in Stage 2
(from ``docs/reprints_worklist.json`` produced by ``scripts/find_reprints.py``);
Stage 1 ships it empty, so ``apply_reprint_aliases()`` is a no-op.

The printed-face identity helper (:func:`face_key` / :func:`load_faces`) lives
here and is imported by ``scripts/find_reprints.py`` so the detector and the
alias guard can never disagree about what "the same card" is.
"""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

from swu.abilities.registry import _ESCAPE_HATCH, _REGISTRY

# ── Reprint -> canonical alias table ─────────────────────────────────────────
#
# Each key is a reprint's (set_code, card_number); each value is the
# (set_code, card_number) of an already-implemented card with an IDENTICAL
# printed face. Do not hand-edit — take entries from docs/reprints_worklist.json
# (the `mirror` bucket) by running `python scripts/find_reprints.py`.
# apply_reprint_aliases() asserts the two DB faces are byte-identical before
# copying, so a stale/wrong entry fails loud at import rather than mis-aliasing.
REPRINT_ALIASES: dict[tuple[str, str], tuple[str, str]] = {
    # Ahsoka Tano  ->  JTL_201
    ("J25", "8"): ("JTL", "201"),
    # Asajj Ventress  ->  LOF_165
    ("P25", "84"): ("LOF", "165"),
    ("P25", "160"): ("JTL", "201"),
    ("P25", "170"): ("JTL", "201"),
    ("P26", "78"): ("JTL", "201"),
    ("P26", "94"): ("JTL", "201"),
    # Bail Organa  ->  SEC_198
    ("SECP", "17"): ("SEC", "198"),
    # Benthic “Two Tubes”  ->  LAW_57
    ("P26", "8"): ("LAW", "57"),
    # Boba Fett  ->  JTL_189
    ("JTLP", "15"): ("JTL", "189"),
    ("P25", "82"): ("JTL", "189"),
    # Boba Fett  ->  LAW_214
    ("C26", "1"): ("LAW", "214"),
    # C-3PO  ->  LAW_152
    ("LAWP", "13"): ("LAW", "152"),
    # Chopper  ->  LAW_55  (freed by the law-set:13 batch)
    ("LAWP", "4"): ("LAW", "55"),
    # Maz Kanata  ->  LAW_74   (freed by the law-set:14 batch)
    ("LAWP", "6"): ("LAW", "74"),
    # Jango Fett  ->  LAW_87   (freed by the law-set:14 batch)
    ("LAWP", "9"): ("LAW", "87"),
    # C-3PO  ->  SEC_93
    ("SECP", "7"): ("SEC", "93"),
    # Chopper  ->  SEC_147
    ("C25", "6"): ("SEC", "147"),
    ("P26", "44"): ("SEC", "147"),
    ("P26", "56"): ("SEC", "147"),
    # Confiscate  ->  SHD_262
    ("SOR", "251"): ("SHD", "262"),
    # Consortium StarViper  ->  SOR_112
    ("ASH", "122"): ("SOR", "112"),
    # Corrupted Saber  ->  LOF_187
    ("P25", "110"): ("LOF", "187"),
    # Count Dooku  ->  TWI_138
    ("J25", "7"): ("TWI", "138"),
    ("P25", "53"): ("TWI", "138"),
    # Crushing Blow  ->  LOF_77
    ("LOFP", "3"): ("LOF", "77"),
    # Do or Do Not  ->  LOF_175
    ("LOFP", "12"): ("LOF", "175"),
    # Heirloom Lightsaber  ->  LOF_53
    ("P25", "105"): ("LOF", "53"),
    # Yoda's Lightsaber  ->  LOF_102
    ("P25", "107"): ("LOF", "102"),
    # Jedi Consular  ->  LOF_94
    ("LOFP", "5"): ("LOF", "94"),
    # The Elite Squad  ->  SEC_143
    ("SECP", "11"): ("SEC", "143"),
    # Luthen Rael  ->  LOF_68
    ("LOFP", "1"): ("LOF", "68"),
    # Daring Delve  ->  LAW_203
    ("LAWP", "16"): ("LAW", "203"),
    # Daring Raid  ->  SHD_178
    ("TWI", "170"): ("SHD", "178"),
    # Darth Maul's Lightsaber  ->  LOF_140
    ("P25", "108"): ("LOF", "140"),
    # Darth Revan's Lightsabers  ->  LOF_238
    ("P25", "19"): ("LOF", "238"),
    # Death Trooper  ->  SHD_30
    ("SEC", "30"): ("SHD", "30"),
    ("SOR", "33"): ("SHD", "30"),
    # Disabling Fang Fighter  ->  SHD_166
    ("SOR", "162"): ("SHD", "166"),
    # Executor  ->  JTL_90
    ("P25", "88"): ("JTL", "90"),
    # First Light  ->  SEC_88
    ("P25", "25"): ("SEC", "88"),
    # Flight of the Inquisitor  ->  LOF_240
    ("LOFP", "20"): ("LOF", "240"),
    # Fulminatrix  ->  SEC_142
    ("SECP", "12"): ("SEC", "142"),
    # Grassroots Resistance  ->  SEC_258
    ("ASH", "258"): ("SEC", "258"),
    ("SECP", "20"): ("SEC", "258"),
    # Incapacitate  ->  LAW_131
    ("LAWP", "12"): ("LAW", "131"),
    # Haymaker  ->  LAW_168
    ("LAWP", "14"): ("LAW", "168"),
    # HK-47  ->  LOF_130
    ("J25", "12"): ("LOF", "130"),
    ("P25", "123"): ("LOF", "130"),
    ("P25", "135"): ("LOF", "130"),
    ("P26", "41"): ("LOF", "130"),
    ("P26", "53"): ("LOF", "130"),
    # HK-87 Assassin Droid  ->  LOF_235
    ("LOFP", "19"): ("LOF", "235"),
    # Homestead Militia  ->  SOR_113
    ("JTL", "113"): ("SOR", "113"),
    # Hunting Nexu  ->  SHD_168
    ("LOF", "162"): ("SHD", "168"),
    # IG-2000  ->  JTL_140
    ("P25", "124"): ("JTL", "140"),
    ("P25", "136"): ("JTL", "140"),
    ("P26", "43"): ("JTL", "140"),
    ("P26", "55"): ("JTL", "140"),
    # IG-88  ->  JTL_141
    ("JTLP", "9"): ("JTL", "141"),
    # J-Type Nubian Starship  ->  LOF_194
    ("LOFP", "16"): ("LOF", "194"),
    # Jedi Holocron  ->  LOF_51
    ("P25", "13"): ("LOF", "51"),
    # K-2SO  ->  LAW_79
    ("LAWP", "8"): ("LAW", "79"),
    # K-2SO  ->  SOR_145
    ("J24", "2"): ("SOR", "145"),
    # Loth-Cat  ->  LOF_207
    ("LOFP", "18"): ("LOF", "207"),
    # Mandalorian Armor  ->  SHD_73
    ("P25", "52"): ("SHD", "73"),
    # Millennium Falcon  ->  JTL_249
    ("JTLP", "19"): ("JTL", "249"),
    # Oggdo Bogdo  ->  LOF_63
    ("J25", "10"): ("LOF", "63"),
    # Onyx Squadron Brute  ->  JTL_33
    ("JTLP", "2"): ("JTL", "33"),
    # Patrolling V-Wing  ->  TWI_107
    ("SOR", "111"): ("TWI", "107"),
    # Planetary Bombardment  ->  JTL_181
    ("P25", "127"): ("JTL", "181"),
    ("P25", "139"): ("JTL", "181"),
    ("P26", "45"): ("JTL", "181"),
    ("P26", "57"): ("JTL", "181"),
    # Poe Dameron  ->  SHD_153
    ("P25", "158"): ("SHD", "153"),
    ("P25", "168"): ("SHD", "153"),
    # Poggle the Lesser  ->  TWI_80
    ("J25", "3"): ("TWI", "80"),
    # Prepare for Takeoff  ->  SOR_125
    ("JTL", "128"): ("SOR", "125"),
    # Qui-Gon Jinn's Lightsaber  ->  LOF_201
    ("P25", "111"): ("LOF", "201"),
    # R2-D2  ->  JTL_245
    ("C25", "3"): ("JTL", "245"),
    # Captain Tarkin  ->  JTL_161  (freed by the jtl-set:17 encoding)
    ("JTLP", "13"): ("JTL", "161"),
    # Red Five  ->  JTL_151
    ("JTLP", "12"): ("JTL", "151"),
    # Repair  ->  SOR_74
    ("JTL", "75"): ("SOR", "74"),
    # Resupply  ->  SOR_126
    ("TWI", "127"): ("SOR", "126"),
    # Sabine's Masterpiece  ->  JTL_250
    ("P26", "101"): ("JTL", "250"),
    ("P26", "85"): ("JTL", "250"),
    # Seasoned Shoretrooper  ->  SHD_83
    ("SOR", "81"): ("SHD", "83"),
    # Street Gang Recruiter  ->  SHD_260
    ("LAW", "261"): ("SHD", "260"),
    # Superlaser Blast  ->  SOR_43
    ("P25", "66"): ("SOR", "43"),
    # Supreme Leader Snoke  ->  SHD_37
    ("J24", "3"): ("SHD", "37"),
    ("P25", "76"): ("SHD", "37"),
    # Tactical Advantage  ->  TWI_124
    ("SOR", "124"): ("TWI", "124"),
    # Tech  ->  SHD_248
    ("J24", "6"): ("SHD", "248"),
    # Vanquish  ->  SOR_78
    ("TWI", "77"): ("SOR", "78"),
    # Victor Leader  ->  JTL_85
    ("P25", "154"): ("JTL", "85"),
    ("P25", "164"): ("JTL", "85"),
    # Wrecker  ->  SHD_154
    ("P25", "125"): ("SHD", "154"),
    ("P25", "137"): ("SHD", "154"),
    # Yaddle  ->  LOF_45
    ("P25", "143"): ("LOF", "45"),
    # Zeb Orellios  ->  LAW_45
    ("LAWP", "3"): ("LAW", "45"),
    # ── Stage 4 batch 5 (2026-07-08) — reprint-encode siblings ────────────────
    # Bo-Katan Kryze  ->  SEC_51
    ("SECP", "2"): ("SEC", "51"),
    # Enfys Nest  ->  TWI_198
    ("J25", "9"): ("TWI", "198"),
    # Hound's Tooth  ->  LAW_33
    ("LAWP", "1"): ("LAW", "33"),
    # Interrogation Droid  ->  LAW_75
    ("LAWP", "7"): ("LAW", "75"),
    # Luke Skywalker  ->  SOR_51
    ("P25", "173"): ("SOR", "51"),
    # The Mandalorian  ->  SHD_49
    ("P25", "101"): ("SHD", "49"),
    # ── Stage 4 batch 6 (2026-07-08) — reprint-encode siblings ────────────────
    # Chewbacca  ->  LAW_34
    ("P26", "10"): ("LAW", "34"),
    # Millennium Falcon  ->  LAW_68
    ("LAWP", "5"): ("LAW", "68"),
    # Ezra Bridger  ->  LOF_46
    ("P25", "77"): ("LOF", "46"),
    # Quinlan Vos  ->  LOF_163
    ("P25", "85"): ("LOF", "163"),
    # Kino Loy  ->  SEC_114
    ("SECP", "9"): ("SEC", "114"),
    # Swarming Vulture Droid  ->  JTL_256
    ("JTLP", "20"): ("JTL", "256"),

    # ── Stage 4 batch 7 (2026-07-08) — reprint-encode siblings ────────────────
    # Axe Woves  ->  LOF_62
    ("P25", "120"): ("LOF", "62"),
    ("P25", "132"): ("LOF", "62"),
    ("P26", "39"): ("LOF", "62"),
    ("P26", "51"): ("LOF", "62"),
    # Corellian Hounds  ->  SEC_170
    ("SECP", "15"): ("SEC", "170"),
    # Ferrix Uprising  ->  SEC_130
    ("SECP", "10"): ("SEC", "130"),
    # Backed by the Hutts  ->  LAW_247
    ("LAWP", "20"): ("LAW", "247"),
    # ISB Agent  ->  SOR_176
    ("SEC", "184"): ("SOR", "176"),
    # Grand Inquisitor  ->  LOF_132
    ("P25", "15"): ("LOF", "132"),
    ("P25", "81"): ("LOF", "132"),
    # ── Stage 4 batch 8 (2026-07-08) — reprint-encode siblings ────────────────
    # Anakin Skywalker  ->  LOF_70
    ("P25", "87"): ("LOF", "70"),
    ("P25", "145"): ("LOF", "70"),
    # Darth Malak  ->  LOF_234
    ("P25", "21"): ("LOF", "234"),
    # Kylo Ren's Lightsaber  ->  LOF_40
    ("P25", "104"): ("LOF", "40"),
    # General's Blade  ->  TWI_121
    ("P25", "156"): ("TWI", "121"),
    ("P25", "166"): ("TWI", "121"),
    # Shoot Down  ->  JTL_176
    ("JTLP", "14"): ("JTL", "176"),
    # Home One  ->  JTL_204
    ("P25", "9"): ("JTL", "204"),
    ("P25", "10"): ("JTL", "204"),
    ("P25", "11"): ("JTL", "204"),
    ("P25", "12"): ("JTL", "204"),
    # ── Reprint-sweep batch (2026-07-09) ─────────────────────────────────────
    # Avenger  ->  SOR_40
    ("J24", "1"): ("SOR", "40"),
    # Take Captive  ->  SHD_131
    ("TWI", "128"): ("SHD", "131"),
    # Rickety Quadjumper  ->  LAW_115
    ("SHD", "57"): ("LAW", "115"),
    # Darth Vader  ->  LOF_37
    ("P25", "75"): ("LOF", "37"),
    ("P25", "152"): ("LOF", "37"),
    ("P25", "162"): ("LOF", "37"),
    ("P26", "72"): ("LOF", "37"),
    ("P26", "88"): ("LOF", "37"),
    # Kylo Ren  ->  SHD_141
    ("C24", "4"): ("SHD", "141"),
    # Rey  ->  SHD_46
    ("P25", "59"): ("SHD", "46"),
    # ── Stage 4 batch 10 (2026-07-09) ────────────────────────────────────────
    # The Mandalorian  ->  SEC_209
    ("J25", "19"): ("SEC", "209"),
    # Lando Calrissian  ->  SEC_68
    ("SECP", "3"): ("SEC", "68"),
    # Chancellor Palpatine  ->  SEC_82
    ("P26", "62"): ("SEC", "82"),
    # Profundity  ->  JTL_154
    ("P25", "159"): ("JTL", "154"),
    ("P25", "169"): ("JTL", "154"),
    # Devastator  ->  JTL_143
    ("P25", "3"): ("JTL", "143"),
    ("P25", "4"): ("JTL", "143"),
    ("P25", "5"): ("JTL", "143"),
    ("P25", "6"): ("JTL", "143"),
    # ── Stage 4 batch 11 (2026-07-09) ────────────────────────────────────────
    # Inquisitor's Lightsaber  ->  LOF_90
    ("P25", "106"): ("LOF", "90"),
    # Grogu  ->  LOF_246
    ("P26", "49"): ("LOF", "246"),
    ("P26", "61"): ("LOF", "246"),
    # Constructed Lightsaber  ->  LOF_261
    ("P25", "112"): ("LOF", "261"),
    # Unnatural Life  ->  TWI_189
    ("P25", "56"): ("TWI", "189"),
    # Secret Battle of Pretend  ->  LAW_226
    ("LAWP", "19"): ("LAW", "226"),
    # ── Stage 4 batch 12 (2026-07-10) ────────────────────────────────────────
    # Han Solo (Piloting)  ->  JTL_203
    ("JTLP", "17"): ("JTL", "203"),
    ("P25", "93"): ("JTL", "203"),
    # Darth Vader (Piloting)  ->  JTL_142
    ("J25", "6"): ("JTL", "142"),
    ("P25", "171"): ("JTL", "142"),
    # Darth Traya  ->  SEC_188
    ("P26", "104"): ("SEC", "188"),
    # Oppression Breeds Rebellion  ->  SEC_158
    ("SECP", "14"): ("SEC", "158"),
    # ── Stage 4 batch 13 (2026-07-10) ────────────────────────────────────────
    # Darth Sion  ->  SEC_35
    ("J25", "15"): ("SEC", "35"),
    ("P26", "71"): ("SEC", "35"),
    ("P26", "87"): ("SEC", "35"),

    # ── Stage 4 batch 15 (2026-07-10) — choose-two-of-four aspect modals ──────
    # The four SOR aspect events, each "Choose two, in any order" (the
    # choose_two_modal primitive).
    ("P25", "126"): ("SOR", "155"),  # Aggression
    ("P25", "138"): ("SOR", "155"),
    ("P25", "122"): ("SOR", "107"),  # Command
    ("P25", "134"): ("SOR", "107"),
    ("P25", "130"): ("SOR", "203"),  # Cunning
    ("P25", "142"): ("SOR", "203"),
    ("P25", "119"): ("SOR", "58"),   # Vigilance
    ("P25", "131"): ("SOR", "58"),

    # ── Stage 4 batch 16 (2026-07-11) — the WhenYouDraw observer ──────────────
    # The Mandalorian "Let's See the Puck"  ->  LAW_52
    ("C26", "2"): ("LAW", "52"),
    # Rey "With Palpatine's Power"  ->  LOF_148
    ("J25", "13"): ("LOF", "148"),
    ("LOFP", "9"): ("LOF", "148"),
    ("P25", "71"): ("LOF", "148"),

    # ── Stage 4 batch 17 (2026-07-12) — the WhenYouUseForce observer ──────────
    # Yoda "My Ally is the Force"  ->  LOF_101
    ("J25", "11"): ("LOF", "101"),
    ("LOFP", "6"): ("LOF", "101"),

    # ── Stage 4 batch 18 (2026-07-12) — IBH easy-encode sweep (19 groups) ──────
    # The IBH set added fresh reprint faces, all encodable with existing
    # primitives (module src/swu/cards/ibh/abilities.py holds the canonicals).
    ("IBH", "85"): ("IBH", "82"),    # Admiral Ozzel
    ("IBH", "65"): ("IBH", "60"),    # Admiral Piett
    ("IBH", "41"): ("IBH", "19"),    # C-3PO
    ("IBH", "36"): ("IBH", "23"),    # General Rieekan
    ("IBH", "88"): ("IBH", "68"),    # General Veers
    ("IBH", "45"): ("IBH", "18"),    # Go for the Legs
    ("IBH", "92"): ("IBH", "64"),    # Hoth Lieutenant
    ("IBH", "102"): ("IBH", "74"),   # I Want Proof, Not Leads
    ("IBH", "39"): ("IBH", "5"),     # I'll Cover For You
    ("IBH", "25"): ("IBH", "9"),     # I've Found Them
    ("IBH", "100"): ("IBH", "62"),   # Imperial Deck Officer
    ("IBH", "30"): ("IBH", "21"),    # Improvised Detonation
    ("IBH", "27"): ("IBH", "16"),    # Ion Cannon
    ("IBH", "49"): ("IBH", "11"),    # R2-D2
    ("IBH", "24"): ("IBH", "6"),     # Rebellion Y-Wing
    ("IBH", "32"): ("IBH", "6"),
    ("IBH", "71"): ("IBH", "59"),    # Target the Main Generator
    ("IBH", "28"): ("IBH", "15"),    # Tauntaun Mount
    ("IBH", "51"): ("IBH", "15"),
    ("IBH", "91"): ("IBH", "66"),    # Too Strong for Blasters
    ("IBH", "86"): ("IBH", "61"),    # We're In Trouble

    # ── Stage 4 batch 19 (2026-07-12) — promo/anthology easy-encode sweep ──────
    # New anthology/convention/promo sets (ASH/C24/C25/G25/J25/P25/P26/JTLP/LOFP)
    # added fresh reprint faces, all encodable with existing primitives (module
    # src/swu/cards/promo/abilities.py holds the canonicals).
    ("P26", "97"): ("P26", "81"),    # Han Solo — Hibernation Sick
    ("P25", "2"): ("P25", "1"),      # Bossk — Hunt By Instinct
    ("P25", "68"): ("JTLP", "7"),    # Chewbacca — Faithful First Mate
    ("P26", "1"): ("ASH", "243"),    # Darth Vader — Meet Your Destiny
    ("P25", "118"): ("P25", "96"),   # Darth Tyranus — Servant of Sidious
    ("P25", "79"): ("G25", "3"),     # Obi-Wan Kenobi — Protective Padawan
    ("P26", "47"): ("J25", "18"),    # General Grievous — Scuttling to Safety
    ("P26", "59"): ("J25", "18"),
    ("P25", "57"): ("C24", "3"),     # Emperor Palpatine — Master of the Dark Side
    ("P26", "91"): ("P26", "75"),    # Naboo Royal Starship — Fit For A Queen
    ("P25", "8"): ("P25", "7"),      # Black One — Straight At Them (group A)
    ("P25", "167"): ("P25", "157"),  # Black One — Straight At Them (group B)
    ("P26", "76"): ("P25", "157"),
    ("P26", "92"): ("P25", "157"),
    ("P25", "69"): ("LOFP", "10"),   # Mace Windu — Leaping into Action
    ("P25", "141"): ("P25", "129"),  # Vernestra Rwoh — Precocious Knight
    ("P26", "48"): ("P25", "129"),
    ("P26", "60"): ("P25", "129"),
    ("P25", "161"): ("P25", "151"),  # Karis — We Don't Like Strangers
    ("P26", "70"): ("P25", "151"),
    ("P26", "86"): ("P25", "151"),
    ("P25", "95"): ("G25", "2"),     # Darth Sidious — The Phantom Menace
    ("C26", "4"): ("ASH", "226"),    # Qi'ra — Master of Teräs Käsi
    ("JTLP", "10"): ("C25", "2"),    # BB-8 — Happy Beeps

    # ── Stage 4 batch 20 (2026-07-12) — FRAMEWORK ESCALATION: the multi-decider
    #    return-then-owner-replays-free primitive (owner_may_replay decision kind).
    #    Clears TWO groups with one new primitive.
    ("LOFP", "14"): ("LOF", "185"),  # Baylan Skoll — Enigmatic Master
    ("P26", "2"): ("LAW", "93"),     # Rio Durant — Beckett's Right Hands

    # ── Stage 4 batch 21 (2026-07-12) — FRAMEWORK ESCALATION: the disclose
    #    primitive (disclose decision kind).  Clears TWO groups with one new
    #    primitive (and broadly unblocks the ~40 other SEC "You may disclose …"
    #    cards).  Each group holds TWO exact-faces — the SEC printing carries the
    #    "(reveal …)" reminder text, the J25/P26 anthology printings do not — and
    #    the strict face-identity guard aliases only within an identical face.  So
    #    the ability is registered under BOTH faces (SEC_148 + J25_17 for Karis;
    #    SEC_133 + P26_42 for Syril) and only same-face twins are aliased here.
    ("P26", "77"): ("J25", "17"),    # Karis Nemik — no-reminder face
    ("P26", "84"): ("J25", "17"),
    ("P26", "93"): ("J25", "17"),
    ("P26", "100"): ("J25", "17"),
    ("P26", "54"): ("P26", "42"),    # Syril Karn — no-reminder face

    # ── Stage 4 batch 22 (2026-07-13) — FRAMEWORK ESCALATION: defeat-Credits-for-a-
    #    scaling-payoff (the pay_resources_for_tokens decision kind generalised with a
    #    cost_source="credit" cost item).  Canonical Cad Bane LAW_32; all four faces
    #    byte-identical, so plain same-face aliases (no reminder-text split).
    ("C26", "5"): ("LAW", "32"),     # Cad Bane — Now It's My Turn
    ("P26", "80"): ("LAW", "32"),
    ("P26", "96"): ("LAW", "32"),

    # ── Stage 4 batch 23 (2026-07-13) — FRAMEWORK ESCALATION: opponent-decided
    #    modal (the choose_two_modal decision kind extended with a decider_id
    #    opponent shift + pick=1).  Canonical Luke Skywalker LAW_80; the P26
    #    printing is a byte-identical face (same 9/7, cost 7, same text).
    ("P26", "112"): ("LAW", "80"),   # Luke Skywalker — opponent chooses one

    # ── Stage 4 batch 24 (2026-07-13) — FRAMEWORK ESCALATION: put-on-deck (the
    #    new put_on_deck multi-decider decision kind; the chosen unit's OWNER
    #    orders it onto the top or bottom of their deck).  Canonical Qui-Gon Jinn
    #    LOF_200; both promo printings are byte-identical faces (7/5, cost 7,
    #    same Ambush + WhenDefeated text).
    ("P25", "94"): ("LOF", "200"),   # Qui-Gon Jinn — put a ground unit on deck
    ("P26", "64"): ("LOF", "200"),   # Qui-Gon Jinn — put a ground unit on deck

    # ── Stage 4 batch 25 (2026-07-13) — FRAMEWORK ESCALATION: conditional cost
    #    cap on target selection (the new TargetSpec.cost_max_boost field: return
    #    a non-leader unit costing ≤2, or ≤4 while you control a Command or
    #    Aggression unit).  Canonical Kanan Jarrus LAW_89; the promo printing is a
    #    byte-identical face (3/4, cost 4, same Restore 1 + WhenPlayed text).
    ("LAWP", "10"): ("LAW", "89"),   # Kanan Jarrus — conditional-cap return-to-hand

    # ── Stage 4 batch 26 (2026-07-13) — FRAMEWORK ESCALATION: the
    #    TargetSpec.select_extreme set-relative target selector ("the unit with the
    #    least remaining HP among other units").  Both members are byte-identical
    #    P26 promo faces (6/6, cost 7, same When Played/On Attack text); canonical
    #    P26_79 registered in promo/abilities.py, P26_95 aliased to it.
    ("P26", "95"): ("P26", "79"),    # Darth Nihilus — least-remaining-HP damage

    # ── Stage 4 batch 27 (2026-07-13) — FRAMEWORK ESCALATION: the ``permanent``
    #    keyword-grant that ends when its source leaves play (the keyword-layer
    #    mirror of Huyang TWI_110's permanent stat modifier).  Canonical BD-1 C25_4
    #    (in promo/abilities.py — both members are anthology/promo faces, no shipped
    #    twin); LOFP_15 is a byte-identical face (1/3, cost 1, Hidden, same text).
    ("LOFP", "15"): ("C25", "4"),    # BD-1 — permanent +1/+0 & Saboteur grant

    # ── Stage 4 batch 28 (2026-07-13) — FRAMEWORK ESCALATION: the keyword-copy aura
    #    ("each other friendly Spectre unit gains this unit's keywords").  Canonical
    #    The Ghost JTL_53 (shipped set → jtl/abilities.py); J25_1 and P25_86 are
    #    byte-identical faces (5/6, cost 5, same text, DB-mistagged printed Sentinel).
    ("J25", "1"): ("JTL", "53"),     # The Ghost — keyword-copy aura
    ("P25", "86"): ("JTL", "53"),    # The Ghost — keyword-copy aura

    # ── Stage 4 batch 29 (2026-07-13) — FRAMEWORK ESCALATION: deploy-leader-as-effect
    #    (Grogu "Charming Companion": "When you play a unique unit that costs 4 or
    #    more: you may deploy him").  Canonical ASH_18 (the shipped 267-card set, no
    #    dedicated module → promo/abilities.py); MV26_1 is the byte-identical face.
    ("MV26", "1"): ("ASH", "18"),    # Grogu — free deploy off a big-unique-unit play
    # Freed by the ash-set:10 batch (2026-08-13): implementing ASH_172 Razor Crest
    # ("On Attack: You may discard a card … +2/+0 for this attack") made its
    # byte-identical MV26 face a free mirror.
    ("MV26", "2"): ("ASH", "172"),   # Razor Crest — Blockade Runner

    # ── Stage 4 batch 30 (2026-07-13) — TWO trivial stragglers (zero new engine
    #    code, pure compositions of existing primitives) + ONE framework escalation.
    #    Shatterpoint P25_153 = "Choose one:" via choose_two_modal pick=1 + Force +
    #    DefeatUnit(hp_remaining_max) (all four faces byte-identical → promo module).
    ("P25", "163"): ("P25", "153"),  # Shatterpoint — modal + Force defeat
    ("P26", "74"): ("P25", "153"),
    ("P26", "90"): ("P25", "153"),
    #    Lawbringer LAW_101 = "Choose an aspect. Give each enemy unit with it –2/–2"
    #    via choose_two_modal pick=1 + mass ModifyStats(EACH_ENEMY, aspect filter)
    #    (canonical LAW = shipped set → law module; both promo faces byte-identical).
    ("P26", "83"): ("LAW", "101"),   # Lawbringer — choose-aspect mass debuff
    ("P26", "99"): ("LAW", "101"),
    #    Ki-Adi-Mundi (FRAMEWORK ESCALATION): "Coordinate — When an opponent plays
    #    their second card each phase: draw 2" via the new WhenOpponentPlaysNthCard
    #    observer trigger.  Canonical = the shipped TWI_64; J25_2 is a byte-identical
    #    reprint face (5/7, cost 5, same Coordinate text).
    ("J25", "2"): ("TWI", "64"),     # Ki-Adi-Mundi — opponent-plays-Nth-card observer

    # ── Stage 4 batch 31 (2026-07-14) — FRAMEWORK ESCALATION: the standing
    #    per-round conditional play-cost discount (StandingPlayDiscount marker read
    #    at _play_cost).  Director Krennic JTLP_1 = "Shielded. The first unit you
    #    play each round that has a 'When Defeated' ability costs 1 less."  Canonical
    #    = JTLP_1 (both faces promo); P25_65 byte-identical.
    ("P25", "65"): ("JTLP", "1"),    # Director Krennic — standing per-round discount

    # ── Stage 4 batch 32 (2026-07-14) — FRAMEWORK ESCALATION: the recurring
    #    regroup-phase "pay 1 or return to hand" upkeep (regroup_upkeep decision
    #    kind, fired at _enter_regroup via PhaseStartTrigger).  Millennium Falcon
    #    SOR_193 = "This unit enters play ready. When you ready cards during the
    #    regroup phase: Either pay [1 resource] or return this unit to her owner's
    #    hand."  Canonical = SOR_193 (shipped); P25_92 byte-identical.
    ("P25", "92"): ("SOR", "193"),   # Millennium Falcon — regroup pay-or-return upkeep
    # ── Stage 4 batch 33 (2026-07-14) — FRAMEWORK ESCALATION: the source-linked
    #    control-revert primitive (CardInstance.control_linked_to +
    #    actions._revert_linked_control, fired from _defeat_unit).  Maul LAW_54 =
    #    "When Attack Ends: If this unit dealt combat damage to a player's base, you
    #    may take control of a non-leader unit that player controls.  When this unit
    #    leaves play, that unit's owner takes control of that unit."  Canonical =
    #    LAW_54 (shipped); P26_4 byte-identical.
    ("P26", "4"): ("LAW", "54"),     # Maul — take-control-on-base-damage + revert-on-leave

    # ── Stage 4 batch 34 (2026-07-14) — FRAMEWORK ESCALATION: the
    #    attach-an-in-play-unit-as-a-Pilot-upgrade primitive (pilot_self_attach
    #    decision + actions._attach_unit_as_pilot relocation).  Poe Dameron JTLP_6 =
    #    "When played as a unit: Create an X-Wing token.  You may attach this unit as
    #    an upgrade to a friendly Vehicle unit without a Pilot on it."  Canonical =
    #    JTLP_6 (promo); P25_90 byte-identical.
    ("P25", "90"): ("JTLP", "6"),    # Poe Dameron — X-Wing + attach-self-as-pilot

    # ── Stage 4 batch 35 (2026-07-14) — FRAMEWORK ESCALATION: the
    #    choose_units_sacrifice_rest decision kind (choose N friendly units, buff
    #    each, defeat all other friendly units).  Always Two LOF_42 = "Choose 2
    #    friendly unique Sith units. If you do, give 2 Shield + 2 Experience tokens
    #    to each chosen unit. Defeat all other friendly units."  Canonical = LOF_42
    #    (shipped LOF); P26_73 / P26_89 byte-identical promos.
    ("P26", "73"): ("LOF", "42"),    # Always Two
    ("P26", "89"): ("LOF", "42"),    # Always Two

    # ── Stage 4 batch 36 (2026-07-14) — FRAMEWORK ESCALATION: the combined-cost
    #    budget multi-select search-and-play (push_search_and_play_multiple).
    #    Darth Vader — Commanding the First Legion = "When Played: Search the top
    #    10 cards of your deck for any number of [Villainy] units with combined
    #    cost 3 or less and play each of them for free."  Canonical = SOR_87
    #    (shipped SOR); C24_2 / P25_103 byte-identical faces.
    ("C24", "2"): ("SOR", "87"),     # Darth Vader — Commanding the First Legion
    ("P25", "103"): ("SOR", "87"),   # Darth Vader — Commanding the First Legion

    # ── Stage 4 batch 37 (2026-07-14) — FRAMEWORK ESCALATION: the location-gated
    #    ready restriction (ReadyRestriction marker + SOURCE_IN_SPACE_ARENA atom).
    #    Leia Organa = "While this unit is in the space arena, she can't ready and
    #    gains: 'Action [use the Force]: Move this unit to the ground arena and give
    #    each friendly Heroism unit +2/+2 for this phase.'"  Canonical = LOF_98
    #    (shipped LOF); P25_80 / P26_102 byte-identical faces.
    ("P25", "80"): ("LOF", "98"),    # Leia Organa
    ("P26", "102"): ("LOF", "98"),   # Leia Organa
    # ── Stage 4 batch 38 (2026-07-14) — FRAMEWORK ESCALATION: combat-damage redirect
    #    (a this_attack CombatDamageRedirect flag on the attacker, read at the
    #    combat-damage step).  Maul = "On Attack: You may choose another friendly
    #    Underworld unit … all combat damage that would be dealt to this unit during
    #    this attack is dealt to the chosen unit instead."  Canonical = SHD_90
    #    (shipped SHD); J24_4 / P25_155 / P25_165 same-face siblings.
    ("J24", "4"): ("SHD", "90"),     # Maul
    ("P25", "155"): ("SHD", "90"),   # Maul
    ("P25", "165"): ("SHD", "90"),   # Maul

    # ── Stage 4 batch 39 (2026-07-14) — FRAMEWORK ESCALATION: defender-first-strike
    #    (a this_attack defender_deals_first flag on the attacker, read at the
    #    unit-combat damage step — the mirror of attacker First Strike).  The Stranger
    #    = "While attacking, you may have the defending unit deal combat damage before
    #    this unit."  Canonical = LAW_86 (shipped LAW); P26_110 same-face sibling.
    ("P26", "110"): ("LAW", "86"),   # The Stranger

    # ── Stage 4 batch 40 (2026-07-15) — FRAMEWORK ESCALATION: extra-regroup-phase
    #    (an ExtraRegroupPhase passive marker + a regroup_count_this_round counter,
    #    read at the regroup-rollover site; a second regroup phase runs each round
    #    while a Max Rebo is in play).  Max Rebo "Encore!" = "There is an additional
    #    regroup phase after the first regroup phase each round."  Canonical = LAW_72
    #    (shipped LAW); P26_82 / P26_98 same-face siblings.
    ("P26", "82"): ("LAW", "72"),    # Max Rebo
    ("P26", "98"): ("LAW", "72"),    # Max Rebo
    # ── Stage 4 batch 41 (2026-07-15) — FRAMEWORK ESCALATION: ability-damage
    #    prevention (a PreventDamage passive marker read at the _apply_deal_damage
    #    chokepoint — a friendly Creature's ability damage to a friendly unit is
    #    dropped).  Malakili "The first Creature unit you play each phase costs 1
    #    less. / If a friendly Creature unit would deal damage to a friendly unit,
    #    prevent that damage."  Canonical = LOF_108 (shipped LOF); LOFP_7 same-face.
    ("LOFP", "7"): ("LOF", "108"),   # Malakili

    # ── Stage 4 batch 42 (2026-07-15) — FRAMEWORK ESCALATION: the capture_or_ready
    #    decision kind (an opponent-decided "give up a non-leader unit to be captured
    #    OR I ready" — the each_player_defeats/opponent_chooses_target deciding-player
    #    shift with a capture-or-ready payoff).  Grand Admiral Thrawn "When Played: An
    #    opponent may choose a non-leader unit they control.  If they do, this unit
    #    captures that unit.  If they don't, ready this unit. / When Defeated: A
    #    friendly unit captures an enemy non-leader unit in the same arena."  Canonical
    #    = SEC_193 (shipped Secrets of Power); P25_33 same-face promo.
    ("P25", "33"): ("SEC", "193"),   # Grand Admiral Thrawn

    # ── Stage 4 batch 43 (2026-07-15) — FRAMEWORK ESCALATION: the
    #    play_upgrade_from_hand decision kind (the upgrade sibling of the units-only
    #    play_from_hand subsystem — "play an upgrade from your hand for free, choosing
    #    a host") + a completion of ReturnToHand for upgrades.  Jabba the Hutt
    #    "When Played: You may return an upgrade to its owner's hand.  If it's returned
    #    to your hand, you may play it for free."  Canonical = ASH_42 (shipped set);
    #    C26_6 same-face promo (aspect-order cosmetic).
    ("C26", "6"): ("ASH", "42"),     # Jabba the Hutt

    # ── Stage 4 batch 44 (2026-07-15) — FRAMEWORK ESCALATION: the ability-suppression
    #    read-layer (CardInstance.abilities_suppressed, read as a skip/early-return at
    #    every ability-read site — the read-layer mirror of the trait/keyword query
    #    layers).  Mind Trick "Exhaust any number of units with a combined power of 4 or
    #    less.  If you control a Force unit, those units lose all abilities and can't
    #    gain abilities for this phase."  Canonical = LOF_202 (shipped Legends of the
    #    Force); LOFP_17 byte-identical promo.
    ("LOFP", "17"): ("LOF", "202"),  # Mind Trick

    # ── Stage 4 batch 45 (2026-07-15) — FRAMEWORK ESCALATION: the multi-defender
    #    attack primitive (MultiDefenderAttack marker + AttackTwoUnits action +
    #    _resolve_two_unit_combat).  Darth Maul "This unit can attack 2 units instead
    #    of 1" — both units are co-defenders of one attack (Maul deals his power to
    #    each, takes the sum of theirs; Overwhelm spills the combined excess).
    #    Canonical = C24_6; J25_5 / P25_91 byte-identical faces.
    ("J25", "5"): ("C24", "6"),   # Darth Maul
    ("P25", "91"): ("C24", "6"),  # Darth Maul

    # ── Stage 4 batch 46 (2026-07-15) — FRAMEWORK ESCALATION: name-based persistent
    #    ability suppression (a name_a_card decision + CardInstance.named_card + a
    #    state.is_name_suppressed scan woven into batch-44's ability-read guards).
    #    Galen Erso "When Played: Name a card.  While this unit is in play, each
    #    non-leader card an opponent owns with that name, including those not in play,
    #    loses all abilities." + Plot.  Persistence and out-of-play application fall out
    #    of the name-based scan over in-play namers.  Canonical = P25_31; P26_38 /
    #    P26_50 byte-identical faces.
    ("P26", "38"): ("P25", "31"),  # Galen Erso
    ("P26", "50"): ("P25", "31"),  # Galen Erso

    # ── Stage 4 batch 47 (2026-07-16) — FRAMEWORK ESCALATION: the replacement-effect
    #    framework (defeat half) — a WhenDefeatedAsUpgrade trigger collected from the
    #    _defeat_unit "defeated_upgrades" scan, relocating the just-defeated pilot from
    #    discard back to the ground arena as an exhausted unit.  Luke Skywalker "If this
    #    upgrade would be defeated, you may instead move him to the ground arena as a
    #    unit and exhaust him" (a defeat-replacement on the Pilot form; the Superlaser
    #    Technician SHD_85 discard-then-relocate pattern).  Canonical = J25_4; P25_89
    #    byte-identical face.
    ("P25", "89"): ("J25", "4"),  # Luke Skywalker
    #    ...and the ORIGINAL printing, JTL_94, which the batch-47 sweep missed:
    #    ``face_key`` compares ``epic_action`` verbatim, and JTL_94's spells out the
    #    Piloting reminder text ("(You may play this as an upgrade on a friendly
    #    Vehicle without a Pilot.)") that both promo faces omit — so JTL_94 keyed to
    #    its own SINGLETON group, which ``find_reprints.build_worklist`` skips
    #    (``len(raw_members) < 2``).  A singleton is invisible to the mirror-gap
    #    check, which is why ``--check`` stayed green with the original unplayable.
    #    Aliased here rather than re-registered in the JTL module so the card keeps
    #    exactly one implementation.  (``reprintOf`` in the DB actually points the
    #    other way — both promos declare JTL_94 as their original — but the sweep's
    #    canonical is whichever twin holds the code, and moving it would only churn.)
    ("JTL", "94"): ("J25", "4"),  # Luke Skywalker

    # ── Stage 4 batch 49 (2026-07-16) — FRAMEWORK ESCALATION: the replacement-effect
    #    framework (DAMAGE half, ability sink) completes Queen Amidala SEC_101 — "If
    #    damage would be dealt to this unit, you may defeat another friendly unit that
    #    shares a trait with this unit.  If you do, prevent that damage."  The combat
    #    half (B48) plus the new deferred ``ability_damage_prevention`` decision at the
    #    ``resolver._apply_deal_damage`` sink now cover her whole replacement, so she is
    #    registered (with a WhenPlayed CreateTokenUnit("Spy", 2)).  Canonical = SEC_101;
    #    J25_16 and P25_27 are byte-identical faces.
    ("J25", "16"): ("SEC", "101"),  # Queen Amidala
    ("P25", "27"): ("SEC", "101"),  # Queen Amidala

    # ── Stage 4 batch 50 (2026-07-16) — FRAMEWORK ESCALATION: two primitives (a
    #    delayed action-phase-start scheduler + a per-enemy pay-or-exhaust decision)
    #    encode The Eye of Aldhani SEC_73 — "At the start of the next action phase,
    #    for each enemy unit, its controller must pay 1 resource or exhaust that
    #    unit."  THE LAST needs_encoding group; the whole reprint sweep is now
    #    complete.  Canonical = SEC_73; SECP_5 is a byte-identical face (literally
    #    reprintOf SEC_73 in the DB).
    ("SECP", "5"): ("SEC", "73"),  # The Eye of Aldhani

    # ── Reminder-text sweep (2026-08-06) — the blind spot ``_norm_rules`` closed.
    #    ``face_key`` used to compare rules text verbatim, so two printings that
    #    differ only in whether the (non-functional) parenthesised reminder text was
    #    printed keyed to DIFFERENT groups.  Any card whose only twin was separated
    #    that way became a SINGLETON, and ``build_worklist`` skips singletons — so
    #    ``--check`` reported "every mirror gap is aliased" while these 36 faces sat
    #    unplayable next to an implemented, byte-identical twin.  Stripping reminder
    #    text from the identity (``_norm_rules``) merged the groups and surfaced them
    #    all at once; every pair below is machine-verified identical by the
    #    ``apply_reprint_aliases`` face guard.  Canonical is whichever twin already
    #    held the implementation, so the direction varies — eight of these are base-set
    #    ORIGINALS aliased onto a promo twin (JTL_100, JTL_94, LOF_79/149/191/195,
    #    SEC_46/187/244), which is exactly the case the old key could not see.
    ("C24", "1"): ("SOR", "38"),     # Count Dooku — Darth Tyranus
    ("J25", "14"): ("LOF", "249"),   # Luke Skywalker — A Hero's Beginning
    ("JTL", "100"): ("JTLP", "6"),   # Poe Dameron — One Hell of a Pilot
    ("JTLP", "3"): ("JTL", "45"),    # Hera Syndulla — We've Lost Enough
    ("JTLP", "4"): ("JTL", "48"),    # Cassian Andor — Threading the Eye
    ("JTLP", "5"): ("JTL", "97"),    # Leia Organa — Pilots, To Your Stations
    ("JTLP", "8"): ("JTL", "134"),   # General Hux — No Terms, No Surrender
    ("JTLP", "11"): ("JTL", "149"),  # Red Squadron Y-Wing
    ("LAWP", "17"): ("LAW", "216"),  # Jabba's Rancor — Snack Time!
    ("LOF", "79"): ("P25", "153"),   # Shatterpoint
    ("LOF", "149"): ("LOFP", "10"),  # Mace Windu — Leaping into Action
    ("LOF", "191"): ("C25", "4"),    # BD-1 — Beep Boo Boo Bweep
    ("LOF", "195"): ("P25", "129"),  # Vernestra Rwoh — Precocious Knight
    ("LOFP", "8"): ("LOF", "129"),   # Acolyte of the Beyond
    ("LOFP", "11"): ("LOF", "156"),  # Infused Brawler
    ("P25", "39"): ("SOR", "97"),    # Admiral Ackbar — Brilliant Strategist
    ("P25", "40"): ("SOR", "115"),   # Agent Kallus — Seeking the Rebels
    ("P25", "41"): ("SOR", "144"),   # Red Three — Unstoppable
    ("P25", "42"): ("SOR", "196"),   # Chewbacca — Loyal Companion
    ("P25", "43"): ("SOR", "198"),   # Han Solo — Reluctant Hero
    ("P25", "44"): ("SOR", "49"),    # Obi-Wan Kenobi — Following Fate
    ("P25", "54"): ("TWI", "165"),   # Kit Fisto — The Smiling Jedi
    ("P25", "55"): ("SOR", "184"),   # Fett's Firespray — Pursuing the Bounty
    ("P25", "67"): ("SHD", "44"),    # Razor Crest — Reliable Gunship
    ("P25", "72"): ("LOF", "229"),   # Kylo Ren — I Know Your Story
    ("P25", "73"): ("SOR", "5"),     # Luke Skywalker — Faithful Friend
    ("P25", "74"): ("SOR", "10"),    # Darth Vader — Dark Lord of the Sith
    ("P25", "78"): ("JTL", "89"),    # The Invisible Hand — Crawling With Vultures
    ("P25", "83"): ("TWI", "194"),   # Ahsoka Tano — Always Ready For Trouble
    ("SEC", "46"): ("P25", "31"),    # Galen Erso — You'll Never Win
    ("SEC", "187"): ("J25", "18"),   # General Grievous — Scuttling to Safety
    ("SEC", "244"): ("P26", "79"),   # Darth Nihilus — Lord of Hunger
    ("SECP", "1"): ("SEC", "37"),    # Cantwell Arrestor Cruiser
    ("SECP", "8"): ("SEC", "111"),   # Jar Jar Binks — Mesa Propose...
    ("SECP", "16"): ("SEC", "189"),  # Lurking Snub Fighter
    ("SECP", "19"): ("SEC", "248"),  # B2EMO — That's Two Lies
    # Freed by the gap-filling campaign (jtl-set:22) implementing JTL_49.
    ("C25", "1"): ("JTL", "49"),     # L3-37 — Droid Revolutionary
    # Freed by the gap-filling campaign (sec-set:15) implementing SEC_151.
    ("SECP", "13"): ("SEC", "151"),  # Kazuda Xiono — Best Pilot in the Galaxy

    # ── Letter-case sweep (2026-08-14) — the LAST blind spot in ``_norm``, and
    #    the last three cards of the gap-filling campaign.  ``_norm`` folded
    #    ``\xa0`` and the curly apostrophe but not letter CASE, so a printing
    #    that shouts a trait or lower-cases a cost keyword keyed to a SINGLETON
    #    group beside its byte-identical-modulo-case implemented twin — and
    #    ``build_worklist`` skips singletons, so ``--check`` stayed green.  Each
    #    of these three was planned as its own one-card encoding group; none
    #    needs any card logic, because the canonical already holds it.
    ("C24", "5"): ("TWI", "134"),    # Asajj Ventress — "another SEPARATIST unit"
    ("C25", "5"): ("SEC", "93"),     # C-3PO — "Action [exhaust, …]"
    ("J24", "5"): ("SHD", "154"),    # Wrecker — BOOM!
}


# Token card types are NOT reprints of each other — a Leader and its
# same-numbered Token collide on (set, number). Mirrors
# ``scripts/audit_coverage.TOKEN_TYPES``; the detector asserts the two stay equal
# so the single source of truth can never silently diverge.
TOKEN_TYPES = frozenset({
    "Token Unit", "Token Upgrade", "Credit Token", "Force Token",
})

# The DB columns that make up a printed face — the identity key defined in
# docs/dev/plans/reprint_duplicates_plan.md.
_FACE_COLUMNS = (
    "name", "subtitle", "type", "cost",
    "power", "hp", "upgrade_power", "upgrade_hp",
    "text", "deploy_box", "epic_action",
)

_WS_RE = re.compile(r"\s+")


def _norm(s) -> str:
    """Whitespace/unicode/**case**-normalise a text field (``\\xa0`` -> space,
    ``’`` -> ``'``, collapse whitespace runs, case-fold). ``None`` -> ``""``.
    Extends the normalisation ``audit_coverage.CardRow.full_text`` applies.

    The case-fold is the last cosmetic difference this identity used to trip
    over, and it is the same blind spot ``_norm_rules`` closed for reminder
    text: letter case is never functional, but printings really do differ in it
    — C24_5 Asajj Ventress shouts "another SEPARATIST unit" where TWI_134 prints
    "another Separatist unit", and C25_5 C-3PO writes "Action [exhaust, …]"
    where SEC_93 writes "Action [Exhaust, …]".  Comparing verbatim keyed each of
    those to a SINGLETON group, and ``find_reprints.build_worklist`` skips
    singletons, so ``--check`` stayed green while four faces sat unplayable
    beside an implemented twin.  MEASURED DB-wide: case-folding merges exactly
    four groups (Asajj Ventress, C-3PO, Wrecker, General Tagge) and every merged
    group is a single card name, so it can join no two different cards.
    """
    if not s:
        return ""
    return _WS_RE.sub(
        " ", str(s).replace("\xa0", " ").replace("’", "'")
    ).strip().casefold()


_REMINDER_RE = re.compile(r"\([^()]*\)")


def _norm_rules(s) -> str:
    """:func:`_norm` a rules-text field, additionally dropping **reminder text** —
    any parenthesised span.

    Reminder text restates a keyword's rules and is non-functional, so two faces
    that differ only in whether it was printed are the same card.  They routinely
    do differ: the original JTL_94 Luke Skywalker spells out "Piloting [3 resources
    Command Heroism] (You may play this as an upgrade on a friendly Vehicle without
    a Pilot.)" while its J25_4 / P25_89 reprints print only the keyword line.
    Comparing verbatim put JTL_94 in a SINGLETON group, and ``find_reprints``
    skips singletons — so the mirror-gap check could not see that the original was
    the unimplemented member of an otherwise-covered group.

    Non-greedy on a per-span basis (``[^()]*``) so an unbalanced parenthesis eats
    only to the next one rather than the rest of the text."""
    return _norm(_REMINDER_RE.sub(" ", str(s or "")))


def face_key(face) -> tuple:
    """Return the printed-face identity tuple for a ``face`` mapping (a dict or
    ``sqlite3.Row`` carrying the :data:`_FACE_COLUMNS` keys).

    Two rows with the same key are the same printed face — an exact reprint.
    Text fields are whitespace/unicode-normalised; stats/cost/type are compared
    verbatim.
    """
    return (
        _norm(face["name"]),
        _norm(face["subtitle"]),
        face["type"],
        face["cost"],
        face["power"],
        face["hp"],
        face["upgrade_power"],
        face["upgrade_hp"],
        _norm_rules(face["text"]),
        _norm_rules(face["deploy_box"]),
        _norm_rules(face["epic_action"]),
    )


# ── DB access ────────────────────────────────────────────────────────────────

def _find_db(db_path: str | None = None) -> str | None:
    """Locate ``swu.db`` robustly, independent of the current working directory
    (this module's aliases are applied at import time). ``None`` if absent."""
    if db_path:
        return db_path
    env = os.environ.get("SWU_DB")
    if env and Path(env).exists():
        return env
    here = Path(__file__).resolve()
    # src/swu/cards/reprints.py -> parents[3] == swu-game
    candidates = [
        here.parents[3] / "data" / "swu.db",
        here.parents[2] / "data" / "swu.db",
        Path("data") / "swu.db",
    ]
    for cand in candidates:
        if cand.exists():
            return str(cand)
    return None


def _resolve_db(db_path: str | None = None) -> str:
    """Like :func:`_find_db`, but raises when the database is missing.

    For callers that genuinely cannot proceed without card data.
    """
    found = _find_db(db_path)
    if found is not None:
        return found
    raise FileNotFoundError(
        "Cannot locate swu.db for reprint aliasing — set the SWU_DB env var."
    )


def is_partial_db(db_path: str | None = None) -> bool:
    """Whether the resolved database is a deliberately incomplete SUBSET of the corpus.

    ``scripts/make_fixture_db.py`` stamps a ``fixture_meta`` table into the small
    test fixture (``tests/fixtures/swu_fixture.db``, a few hundred cards).  The
    integrity checks below are written against the *whole* corpus — "this reprint
    key must exist" is a true invariant of the real database and a false one of a
    subset — so they consult this before raising.  A real build has no such table
    and is therefore never treated as partial.
    """
    path = _find_db(db_path)
    if path is None:
        return False
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        row = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='fixture_meta'"
        ).fetchone()
    finally:
        con.close()
    return row is not None


def load_faces(db_path: str | None = None) -> dict[tuple[str, str], dict]:
    """Return every card's printed face keyed by ``(set_code, card_number)``.

    Resolves the Leader-vs-Token ``(set, number)`` collision in favour of the
    real (non-token) row, matching ``audit_coverage.index_by_set_number``.
    """
    con = sqlite3.connect(_resolve_db(db_path))
    con.row_factory = sqlite3.Row
    cols = "set_code, card_number, " + ", ".join(_FACE_COLUMNS)
    rows = con.execute(f"SELECT {cols} FROM cards").fetchall()
    con.close()
    faces: dict[tuple[str, str], dict] = {}
    for r in rows:
        key = (r["set_code"], r["card_number"])
        existing = faces.get(key)
        if existing is None or (
            existing["type"] in TOKEN_TYPES and r["type"] not in TOKEN_TYPES
        ):
            faces[key] = {c: r[c] for c in _FACE_COLUMNS}
    return faces


# ── Alias application (called from swu.cards.__init__ at import time) ─────────

def apply_reprint_aliases(db_path: str | None = None) -> int:
    """Copy each registered canonical's specs onto its reprint key.

    Guards against data drift: for every ``reprint -> canonical`` it asserts the
    canonical is actually registered and that the two DB faces are byte-identical
    (raising a clear error naming both keys otherwise), so a future DB refresh
    that changes one member's text can never silently alias a now-different card.

    Returns the number of aliases applied. A no-op (returns 0, touches no DB)
    while :data:`REPRINT_ALIASES` is empty.  Against a deliberately partial
    database (see :func:`is_partial_db`) the aliases are applied without that
    verification — the reasoning is at the loop below.
    """
    if not REPRINT_ALIASES:
        return 0
    # Aliasing verifies each reprint against the card DB, and this runs at import
    # time from swu.cards.__init__ — so a missing database must not make
    # `import swu.cards` raise. A fresh clone has no data/ until the pipeline has
    # run (see README), and every consumer that truly needs card data reports that
    # itself: the test suite skips, the web app returns a clear error. Skipping
    # here costs nothing in that state, because with no DB there are no cards to
    # look up. When a DB IS present the full integrity check below still runs.
    if _find_db(db_path) is None:
        return 0
    partial = is_partial_db(db_path)
    faces = {} if partial else load_faces(db_path)
    # On a partial database (the committed test fixture) the aliases are applied
    # but NOT verified.  REPRINT_ALIASES is checked-in code, so applying it is
    # deterministic — it is the verification that needs the whole corpus, in two
    # ways.  Most reprint keys are simply absent from a subset; worse, the keys
    # that ARE present can be the wrong card, because ``(set, number)`` is not
    # unique and ``load_faces`` resolves a collision in favour of the non-token
    # row: with the real card absent, P25_1 resolves to the Battle Droid token
    # instead of Bossk, and comparing that against its twin "proves" a mismatch
    # that does not exist.  Skipping the aliases instead is not an option — it
    # would change what ``get_abilities`` returns for a reprint key, so a fixture
    # run would exercise different engine behaviour than a real one.
    applied = 0
    for reprint, canonical in REPRINT_ALIASES.items():
        if canonical not in _REGISTRY:
            raise ValueError(
                f"reprint alias canonical {canonical} is not registered "
                f"(renumbered away?); reprint={reprint}"
            )
        if partial:
            _REGISTRY[reprint] = _REGISTRY[canonical]
            if canonical in _ESCAPE_HATCH:
                _ESCAPE_HATCH.add(reprint)
            applied += 1
            continue
        rface = faces.get(reprint)
        cface = faces.get(canonical)
        if rface is None or cface is None:
            missing = reprint if rface is None else canonical
            raise ValueError(
                f"reprint alias references a (set, number) not in the DB: "
                f"{missing} (reprint={reprint}, canonical={canonical})"
            )
        if face_key(rface) != face_key(cface):
            raise ValueError(
                f"reprint alias face mismatch — {reprint} is NOT an exact reprint "
                f"of {canonical}; refusing to alias a different card"
            )
        _REGISTRY[reprint] = _REGISTRY[canonical]
        if canonical in _ESCAPE_HATCH:
            _ESCAPE_HATCH.add(reprint)
        applied += 1
    return applied
