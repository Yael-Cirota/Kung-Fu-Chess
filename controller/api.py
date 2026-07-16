from typing import List, Optional, Protocol, runtime_checkable

from kfchess.api import BoardSnapshot, MotionInfo, MoveLogEntry, PieceView, Position

__all__ = ["Position", "PieceView", "BoardSnapshot", "MotionInfo", "MoveLogEntry", "GameController"]


@runtime_checkable
class GameController(Protocol):
    """
    The only contract ui depends on. ui never imports kfchess - even for
    types - because BoardSnapshot/MotionInfo/PieceView/Position are
    re-exported here.
    """

    def on_click(self, x: int, y: int) -> None: ...

    def advance(self, ms: int) -> None: ...

    def piece_at(self, pos: Position) -> Optional[PieceView]: ...

    @property
    def clock_ms(self) -> int: ...

    @property
    def is_game_over(self) -> bool: ...

    def board_snapshot(self) -> BoardSnapshot: ...

    def motion_for(self, piece_id: int) -> Optional[MotionInfo]: ...

    def move_log(self) -> List[MoveLogEntry]: ...
