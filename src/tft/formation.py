"""Formations: where units stand on the board and what standing there means.

The board is a grid of ``rules.board_rows`` rows by ``rules.board_cols``
columns. Row 0 is the front, the hedge book: smaller positions whose
drawdowns are partly absorbed. The last row is the back, the alpha book: the
largest positions, which pay extra for their drawdowns unless an ally stands
in front of them in the same column. The column also decides which symbol of
its origin a unit trades, so spreading an origin over columns diversifies it
and stacking it in one column concentrates it.
"""

from __future__ import annotations

from collections.abc import Collection

from tft.errors import Refusal
from tft.items import Effect
from tft.rules import DEFAULT_RULES, Rules

Cell = tuple[int, int]
"""A board cell as ``(row, column)``; row 0 is the front."""

FRONT_ROLES: frozenset[str] = frozenset({"Hedger", "Arbitrageur"})
"""Classes that stand in the front row by default."""

MIDDLE_ROLES: frozenset[str] = frozenset({"Swing", "Contrarian", "Quant"})
"""Classes that stand in the second row by default; every other class goes to the back."""

PERCENT = 100


def check_cell(cell: Cell, rules: Rules = DEFAULT_RULES) -> None:
    """Check that ``cell`` is on the board.

    Raises:
        Refusal: If the row or the column is out of range.
    """
    row, col = cell
    if not (0 <= row < rules.board_rows and 0 <= col < rules.board_cols):
        rows, cols = rules.board_rows - 1, rules.board_cols - 1
        raise Refusal(f"the board has rows 0 to {rows} and columns 0 to {cols}")


def column_order(cols: int) -> tuple[int, ...]:
    """Return the columns from the centre outwards, left before right."""
    centre = cols // 2
    return tuple(sorted(range(cols), key=lambda col: (abs(col - centre), col)))


def preferred_row(role: str, rules: Rules = DEFAULT_RULES) -> int:
    """Return the row a class stands in by default: hedges in front, carries at the back."""
    if role in FRONT_ROLES:
        return 0
    if role in MIDDLE_ROLES:
        return min(1, rules.board_rows - 1)
    return rules.board_rows - 1


def row_order(preferred: int, rows: int) -> tuple[int, ...]:
    """Return the rows by distance from ``preferred``, the row further back first on a tie."""
    return tuple(sorted(range(rows), key=lambda row: (abs(row - preferred), -row)))


def default_cell(role: str, occupied: Collection[Cell], rules: Rules = DEFAULT_RULES) -> Cell:
    """Return the free cell a unit of class ``role`` takes when none is given.

    Raises:
        Refusal: If every cell is taken.
    """
    for row in row_order(preferred_row(role, rules), rules.board_rows):
        for col in column_order(rules.board_cols):
            if (row, col) not in occupied:
                return (row, col)
    raise Refusal("the board has no free cell")


def is_back_half(cell: Cell, rules: Rules = DEFAULT_RULES) -> bool:
    """Return whether ``cell`` is in the back half of the board, where cover matters."""
    return cell[0] >= rules.board_rows // 2


def is_covered(cell: Cell, occupied: Collection[Cell]) -> bool:
    """Return whether an ally stands in front of ``cell`` in the same column."""
    row, col = cell
    return any(other_col == col and other_row < row for other_row, other_col in occupied)


def position_effect(cell: Cell, occupied: Collection[Cell], rules: Rules = DEFAULT_RULES) -> Effect:
    """Return what standing on ``cell`` does to a unit's size and drawdown shield.

    The row sets the size and the base shield. In the back half, an ally in
    front in the same column adds the cover shield; without one the unit is
    exposed and its drawdowns weigh more.

    Raises:
        Refusal: If ``cell`` is not on the board.
    """
    check_cell(cell, rules)
    row = cell[0]
    shield = rules.row_shield_percent[row]
    if is_back_half(cell, rules):
        covered = is_covered(cell, occupied)
        shield += rules.cover_shield_percent if covered else -rules.exposed_penalty_percent
    return Effect(size_percent=rules.row_size_percent[row] - PERCENT, shield_percent=shield)
