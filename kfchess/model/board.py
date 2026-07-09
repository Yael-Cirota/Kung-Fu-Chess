from typing import List, Optional

from kfchess.model.position import Position


class Board:
    """
    Stores logical piece occupancy for a grid of cells.
    Contains no movement rules and no rendering awareness.
    """

    def __init__(self, grid: List[List[Optional[object]]]):
        self._grid = grid

    @staticmethod
    def from_grid(grid: List[List[Optional[object]]]) -> "Board":
        return Board(grid)

    @property
    def rows(self) -> int:
        return len(self._grid)

    @property
    def cols(self) -> int:
        return len(self._grid[0]) if self._grid else 0

    def is_within_bounds(self, pos: Position) -> bool:
        return 0 <= pos.row < self.rows and 0 <= pos.col < self.cols

    def get(self, pos: Position) -> Optional[object]:
        return self._grid[pos.row][pos.col]

    def set(self, pos: Position, piece: Optional[object]) -> None:
        self._grid[pos.row][pos.col] = piece

    def remove(self, pos: Position) -> Optional[object]:
        previous = self._grid[pos.row][pos.col]
        self._grid[pos.row][pos.col] = None
        return previous

    def as_grid(self) -> List[List[Optional[object]]]:
        """Row-by-row read access, e.g. for building a GameSnapshot."""
        return self._grid
