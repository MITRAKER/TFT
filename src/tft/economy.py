"""Economy arithmetic: interest, streak bonus and round income.

This is the example module that ships with the scaffold. It models the gold
economy of an auto-battler round: a flat income, interest on banked gold and a
bonus for win or loss streaks. The numbers follow the common Teamfight Tactics
table and are easy to change; the point of the module is to give the pipeline
(tests, type checks, standards checks, CodeQL) real code to run against.
"""

from __future__ import annotations

BASE_INCOME: int = 5
"""Gold granted every round before interest and streak bonuses."""

INTEREST_STEP: int = 10
"""Gold that must be banked for one point of interest."""

MAX_INTEREST: int = 5
"""Cap on interest per round, reached at 50 banked gold."""

MAX_STREAK_BONUS: int = 3
"""Cap on the streak bonus per round."""

_STREAK_TABLE: tuple[tuple[int, int], ...] = ((5, 3), (4, 2), (2, 1))
"""(minimum streak length, bonus) pairs, longest streak first."""


def interest(gold: int) -> int:
    """Return the interest earned on ``gold`` banked at the end of a round.

    Interest is one gold per :data:`INTEREST_STEP` banked, capped at
    :data:`MAX_INTEREST`.

    Args:
        gold: Gold in the bank when the round ends. Must not be negative.

    Returns:
        Interest gold for the round, between 0 and :data:`MAX_INTEREST`.

    Raises:
        ValueError: If ``gold`` is negative.
    """
    if gold < 0:
        msg = f"gold must not be negative, got {gold}"
        raise ValueError(msg)
    return min(gold // INTEREST_STEP, MAX_INTEREST)


def streak_bonus(streak: int) -> int:
    """Return the bonus gold for a win or loss streak of ``streak`` rounds.

    The sign of ``streak`` does not matter: a loss streak pays the same as a win
    streak of the same length.

    Args:
        streak: Consecutive wins (positive) or losses (negative).

    Returns:
        Bonus gold between 0 and :data:`MAX_STREAK_BONUS`.
    """
    length = abs(streak)
    for minimum, bonus in _STREAK_TABLE:
        if length >= minimum:
            return bonus
    return 0


def round_income(gold: int, streak: int = 0, *, base: int = BASE_INCOME) -> int:
    """Return the total gold earned at the end of a round.

    Args:
        gold: Gold in the bank when the round ends. Must not be negative.
        streak: Consecutive wins (positive) or losses (negative).
        base: Flat income granted every round.

    Returns:
        ``base`` plus interest plus the streak bonus.

    Raises:
        ValueError: If ``gold`` or ``base`` is negative.
    """
    if base < 0:
        msg = f"base must not be negative, got {base}"
        raise ValueError(msg)
    return base + interest(gold) + streak_bonus(streak)


def rounds_to_reach(target: int, gold: int, *, streak: int = 0, max_rounds: int = 100) -> int:
    """Return how many rounds it takes to bank ``target`` gold without spending any.

    Each round adds :func:`round_income` to the balance. The loop has a fixed upper
    bound so the function always returns (Power of Ten, rule 2).

    Args:
        target: Gold to reach.
        gold: Gold in the bank now. Must not be negative.
        streak: Streak carried through every round.
        max_rounds: Hard limit on the number of rounds simulated.

    Returns:
        The number of rounds needed, or ``-1`` when ``target`` is not reached
        within ``max_rounds`` rounds.

    Raises:
        ValueError: If ``target``, ``gold`` or ``max_rounds`` is negative.
    """
    if target < 0 or max_rounds < 0:
        msg = "target and max_rounds must not be negative"
        raise ValueError(msg)
    balance = gold
    for rounds_played in range(max_rounds + 1):
        if balance >= target:
            return rounds_played
        balance += round_income(balance, streak)
    return -1
