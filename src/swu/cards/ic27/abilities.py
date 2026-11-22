"""IC27 (Icons 2027 Edition) card ability registrations.

Imported for its side effects (the ``@card_ability`` decorators populate the
registry).  Encoded group by group via ``/encode-next``; the plan lives in
``encoding/ic27-set/``.  Run the reprint sweep (``scripts/find_reprints.py``)
before encoding here: a card whose printed face matches an implemented card is
aliased in ``swu/cards/reprints.py``, not re-encoded.

⚠️ **TOKEN COLLISIONS**: ``IC27_1`` Darth Vader (Leader) shares its registry key
with the Experience token UPGRADE, and ``IC27_2`` Rey (Leader) with the Shield
token UPGRADE.  Register those leaders ONLY from spec kinds a token can never
reach (see the same warning in ``swu/cards/ts26/abilities.py``):
``ActivatedAbility(undeployed_only=True)``, ``TriggerAbility(WhenDeployed())`` and
``TriggerAbility(deployed_only=True)``.
"""
from __future__ import annotations
