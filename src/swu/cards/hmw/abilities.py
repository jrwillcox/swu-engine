"""HMW (Homeworlds) card ability registrations.

Imported for its side effects (the ``@card_ability`` decorators populate the
registry).  Encoded group by group via ``/encode-next``; the plan lives in
``encoding/hmw-set/``.

⚠️ **TOKEN COLLISIONS**: HMW prints its tokens at LOW numbers, and each shares its
``(set, number)`` registry key with a LEADER of the same number:

* ``HMW_1`` Asajj Ventress (Leader) / Shield token UPGRADE
* ``HMW_2`` Maz Kanata (Leader) / **Weakness** token UPGRADE (new token type)
* ``HMW_3`` Doctor Hemlock (Leader) / **Beast** token UNIT (new token type)
* ``HMW_4`` Grand Moff Tarkin (Leader) / Beast token UNIT
* ``HMW_5`` Jar Jar Binks (Leader) / Beast token UNIT

Register those leaders ONLY from spec kinds a token can never reach (see the
same warning in ``swu/cards/ts26/abilities.py``):
``ActivatedAbility(undeployed_only=True)``, ``TriggerAbility(WhenDeployed())`` and
``TriggerAbility(deployed_only=True)``.  A ``ConstantAbility``, a
``GrantedAbility`` or a passive marker would NOT be safe there.
"""
from __future__ import annotations
