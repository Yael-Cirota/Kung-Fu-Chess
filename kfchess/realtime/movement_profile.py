from abc import ABC, abstractmethod
from typing import Dict, List

from kfchess.model.piece import PieceKind
from kfchess.model.position import Position

# Milliseconds a piece spends crossing a single cell of board distance.
# Kept here (rather than imported from real_time_arbiter) so movement
# geometry owns its own timing and there is no import cycle between the
# two modules. This is engine-internal timing, unrelated to any rendering
# unit - ui defines its own pixel cell size independently.
MOVE_DURATION_MS_PER_CELL = 1000


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)


def _chebyshev(from_pos: Position, to_pos: Position) -> int:
    return max(abs(to_pos.row - from_pos.row), abs(to_pos.col - from_pos.col))


class MovementProfile(ABC):
    """
    Piece-type movement Strategy. Turns a from->to move into the ordered
    list of squares the piece progressively occupies and the time it
    spends on each step. This is where the "preceding square" semantics
    live: a slider occupies every square along its line, so its preceding
    square is the previous one in the path; a jumper never occupies the
    squares in between, so its preceding square is always its origin.
    Stateless and board-agnostic - occupancy is resolved elsewhere.
    """

    @abstractmethod
    def occupied_path(self, from_pos: Position, to_pos: Position) -> List[Position]:
        """Ordered squares the piece will occupy, excluding origin, including destination."""
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def step_duration_ms(self, from_pos: Position, to_pos: Position) -> int:
        """Milliseconds spent advancing one square of the occupied path."""
        raise NotImplementedError  # pragma: no cover


class SlidingProfile(MovementProfile):
    """Occupies every square along a straight or diagonal line, one cell per step."""

    def occupied_path(self, from_pos: Position, to_pos: Position) -> List[Position]:
        step_row = _sign(to_pos.row - from_pos.row)
        step_col = _sign(to_pos.col - from_pos.col)
        length = _chebyshev(from_pos, to_pos)
        path: List[Position] = []
        row, col = from_pos.row, from_pos.col
        for _ in range(length):
            row += step_row
            col += step_col
            path.append(Position(row, col))
        return path

    def step_duration_ms(self, from_pos: Position, to_pos: Position) -> int:
        return MOVE_DURATION_MS_PER_CELL


class JumpingProfile(MovementProfile):
    """Hops straight to the destination; intermediate squares are never occupied."""

    def occupied_path(self, from_pos: Position, to_pos: Position) -> List[Position]:
        return [to_pos]

    def step_duration_ms(self, from_pos: Position, to_pos: Position) -> int:
        # Single step, but its duration spans the whole distance so total
        # flight time stays identical to a slider covering the same reach.
        return _chebyshev(from_pos, to_pos) * MOVE_DURATION_MS_PER_CELL


DEFAULT_MOVEMENT_PROFILES: Dict[PieceKind, MovementProfile] = {
    PieceKind.ROOK: SlidingProfile(),
    PieceKind.BISHOP: SlidingProfile(),
    PieceKind.QUEEN: SlidingProfile(),
    PieceKind.KING: SlidingProfile(),
    PieceKind.PAWN: SlidingProfile(),
    PieceKind.KNIGHT: JumpingProfile(),
}
