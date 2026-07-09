from dataclasses import dataclass
from typing import Optional, Tuple

from kfchess.model.board import Board
from kfchess.model.position import Position


@dataclass(frozen=True)
class PieceView:
    symbol: str
    color: str


@dataclass(frozen=True)
class GameSnapshot:
    rows: int
    cols: int
    cells: Tuple[Tuple[Optional[PieceView], ...], ...]
    clock_ms: int
    game_over: bool

    @staticmethod
    def of(board: Board, clock_ms: int, game_over: bool) -> "GameSnapshot":
        cells = tuple(
            tuple(
                PieceView(symbol=piece.get_symbol(), color=piece.color) if piece is not None else None
                for piece in row
            )
            for row in board.as_grid()
        )
        return GameSnapshot(
            rows=board.rows, cols=board.cols, cells=cells, clock_ms=clock_ms, game_over=game_over
        )

    def piece_at(self, pos: Position) -> Optional[PieceView]:
        return self.cells[pos.row][pos.col]
