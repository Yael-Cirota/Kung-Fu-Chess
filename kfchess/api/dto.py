from dataclasses import dataclass
from typing import List

from kfchess.model.position import Position
from kfchess.engine.move_result import MoveResult

__all__ = ["Position", "MoveResult", "PieceView", "BoardSnapshot", "MotionInfo"]


@dataclass(frozen=True)
class PieceView:
    """Read-only view of a piece, handed across the kfchess.api boundary instead of the live Piece object."""
    piece_id: int
    symbol: str
    color: str
    cell: Position


@dataclass(frozen=True)
class BoardSnapshot:
    """Read-only view of board occupancy, replacing direct Board/Piece access outside kfchess."""
    rows: int
    cols: int
    piece_views: List[PieceView]

    def pieces(self) -> List[PieceView]:
        return list(self.piece_views)


@dataclass(frozen=True)
class MotionInfo:
    """A piece's in-flight motion, computed entirely by RealTimeArbiter - callers never recompute timing/is_jump."""
    from_pos: Position
    to_pos: Position
    start_ms: int
    duration_ms: int
    is_jump: bool
