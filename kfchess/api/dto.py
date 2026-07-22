from dataclasses import dataclass
from typing import List

from kfchess.model.position import Position
from kfchess.engine.move_result import MoveResult

__all__ = ["Position", "MoveResult", "PieceView", "BoardSnapshot", "MotionInfo", "MoveLogEntry", "Scoreboard"]


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
class MoveLogEntry:
    """One issued move handed across the kfchess.api boundary - `color` lets ui
    file it under the player who made it, from_pos/to_pos + symbol let ui render
    it in whatever notation it likes, without ever seeing a kfchess type."""
    color: str
    symbol: str
    from_pos: Position
    to_pos: Position


@dataclass(frozen=True)
class Scoreboard:
    """Accumulated capture points for each player, handed across the kfchess.api
    boundary so ui can display the running score without seeing a kfchess type."""
    white: int
    black: int


@dataclass(frozen=True)
class MotionInfo:
    """A piece's in-flight motion, computed entirely by RealTimeArbiter - callers never recompute timing/is_jump."""
    from_pos: Position
    to_pos: Position
    start_ms: int
    duration_ms: int
    is_jump: bool
