"""Exceptions the engine raises on purpose.

:class:`Refusal` is the one a client may show to a player. It means "the rules
do not allow that action right now" and carries a reason written for players.
Every other exception is a programming or configuration error and is never
shown to a player as is.
"""

from __future__ import annotations


class Refusal(ValueError):  # noqa: N818 - a refusal is the rules saying no, not an error
    """An action the rules do not allow, with a reason that is safe to show the player."""

    def __init__(self, reason: str) -> None:
        """Keep ``reason`` both as the exception message and as a public attribute."""
        super().__init__(reason)
        self.reason = reason
