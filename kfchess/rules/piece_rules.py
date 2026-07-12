from abc import ABC, abstractmethod
from typing import Iterable, Optional, Set, Tuple

from kfchess.model.board import Board
from kfchess.model.piece import PieceKind
from kfchess.model.position import Position

ROOK_DIRECTIONS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
BISHOP_DIRECTIONS = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
QUEEN_DIRECTIONS = ROOK_DIRECTIONS + BISHOP_DIRECTIONS
KNIGHT_OFFSETS = [(2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)]
KING_OFFSETS = QUEEN_DIRECTIONS


def _is_friendly(piece, occupant: Optional[object]) -> bool:
    return occupant is not None and occupant.color == piece.color


def _is_enemy(piece, occupant: Optional[object]) -> bool:
    return occupant is not None and occupant.color != piece.color


def _slide(board: Board, piece, origin: Position, directions: Iterable[Tuple[int, int]]) -> Set[Position]:
    """Walks each direction from origin until blocked, off-board, or a capture square is reached."""
    destinations: Set[Position] = set()
    for dr, dc in directions:
        row, col = origin.row + dr, origin.col + dc
        while True:
            pos = Position(row, col)
            if not board.is_within_bounds(pos):
                break
            occupant = board.get(pos)
            if _is_friendly(piece, occupant):
                break
            destinations.add(pos)
            if occupant is not None:
                break
            row += dr
            col += dc
    return destinations


def _step(board: Board, piece, origin: Position, offsets: Iterable[Tuple[int, int]]) -> Set[Position]:
    """Checks each fixed offset from origin, ignoring anything in between."""
    destinations: Set[Position] = set()
    for dr, dc in offsets:
        pos = Position(origin.row + dr, origin.col + dc)
        if not board.is_within_bounds(pos):
            continue
        if _is_friendly(piece, board.get(pos)):
            continue
        destinations.add(pos)
    return destinations


class PieceRule(ABC):
    """
    Stateless rule for a single piece kind. Computes legal destination
    squares from the board and the piece alone - never mutates the
    board or the piece, and never captures/moves anything itself.
    """

    @staticmethod
    @abstractmethod
    def legal_destinations(board: Board, piece) -> Set[Position]:
        raise NotImplementedError  # pragma: no cover

    @staticmethod
    def promotion_kind(board: Board, piece, to_pos: Position) -> Optional[PieceKind]:
        """Returns the kind `piece` should become after landing on to_pos, or None. Most pieces never promote."""
        return None


class RookRule(PieceRule):
    """Slides horizontally and vertically until blocked."""

    @staticmethod
    def legal_destinations(board: Board, piece) -> Set[Position]:
        origin = piece.cell
        return _slide(board, piece, origin, ROOK_DIRECTIONS)


class BishopRule(PieceRule):
    """Slides diagonally until blocked."""

    @staticmethod
    def legal_destinations(board: Board, piece) -> Set[Position]:
        origin = piece.cell
        return _slide(board, piece, origin, BISHOP_DIRECTIONS)


class QueenRule(PieceRule):
    """Combines rook and bishop movement."""

    @staticmethod
    def legal_destinations(board: Board, piece) -> Set[Position]:
        origin = piece.cell
        return _slide(board, piece, origin, QUEEN_DIRECTIONS)


class KnightRule(PieceRule):
    """Jumps in an L-shape, ignoring blockers along the way."""

    @staticmethod
    def legal_destinations(board: Board, piece) -> Set[Position]:
        origin = piece.cell
        return _step(board, piece, origin, KNIGHT_OFFSETS)


class KingRule(PieceRule):
    """Moves exactly one square in any direction."""

    @staticmethod
    def legal_destinations(board: Board, piece) -> Set[Position]:
        origin = piece.cell
        return _step(board, piece, origin, KING_OFFSETS)


class PawnRule(PieceRule):
    """
    Simplified pawn: one square forward (must be empty), two squares
    forward from its start row (path must be clear), or one square
    diagonally forward to capture an enemy piece. No en passant.
    """

    @staticmethod
    def legal_destinations(board: Board, piece) -> Set[Position]:
        origin = piece.cell
        direction = -1 if piece.color == 'w' else 1
        destinations: Set[Position] = set()

        forward = Position(origin.row + direction, origin.col)
        forward_clear = board.is_within_bounds(forward) and board.get(forward) is None
        if forward_clear:
            destinations.add(forward)

        if not piece.has_moved and forward_clear:
            double_forward = Position(origin.row + 2 * direction, origin.col)
            if board.is_within_bounds(double_forward) and board.get(double_forward) is None:
                destinations.add(double_forward)

        for dc in (-1, 1):
            capture = Position(origin.row + direction, origin.col + dc)
            if board.is_within_bounds(capture) and _is_enemy(piece, board.get(capture)):
                destinations.add(capture)

        return destinations

    @staticmethod
    def promotion_kind(board: Board, piece, to_pos: Position) -> Optional[PieceKind]:
        last_row = 0 if piece.color == 'w' else board.rows - 1
        return PieceKind.QUEEN if to_pos.row == last_row else None
