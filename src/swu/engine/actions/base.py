"""The Action contract: the one type every decision in the game implements.

This is the bottom of the ``actions`` package — it imports nothing else from it,
and 206 of the package's other definitions depend on it.  Keeping it alone in a
leaf module is what lets every other module import the base class without
dragging in the rest of the engine.

An ``Action`` is a *value*: ``__eq__`` and ``__hash__`` compare instance state, so
two separately-constructed actions describing the same decision are the same
action.  The bots and the web layer both rely on that — offered actions are
matched by equality, not identity.

``type(action).__name__`` is part of the HTTP API: ``swu/web/serializers.py`` sends
it as an action's ``kind`` and ``dataclasses.asdict(action)`` as its ``params``, and
the React frontend is written against those names.  Renaming an ``Action`` subclass
or one of its dataclass fields is a breaking API change, pinned by
``tests/test_actions_contract.py``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from swu.engine.state import GameState


class IllegalActionError(Exception):
    pass


# ── Abstract base ─────────────────────────────────────────────────────────────

class Action(ABC):
    @abstractmethod
    def apply(self, state: GameState) -> GameState:
        raise NotImplementedError

    @abstractmethod
    def describe(self) -> str:
        raise NotImplementedError

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other) and self.__dict__ == other.__dict__

    def __hash__(self) -> int:
        return hash((type(self), tuple(sorted(self.__dict__.items()))))
