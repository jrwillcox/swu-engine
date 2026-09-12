"""Promo / anthology reprint-duplicate ability registrations.

The promo, convention, and anthology sets (ASH / C24 / C25 / G25 / J25 / P25 /
P26 / JTLP / LOFP) contain many reprint-duplicate faces (each shares a *name*
with an earlier-set card but carries its own subtitle/text, so each is its own
reprint group with no shipped-set member).  Every card registered here composes
from EXISTING engine primitives — no new decision kind, no trigger/decision-
machinery change — the batch-7-through-18 "easy encode" shape.  Registered
canonical (one member) of each group; siblings are aliased in
``src/swu/cards/reprints.py``.  Imported for its side effects (the
``@card_ability`` decorators populate the registry).
"""
import swu.cards.promo.abilities  # noqa: F401 — side-effect: registers abilities
