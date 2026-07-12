from typing import List, Optional

from kfchess.model.position import Position


class Board:
    """
    Stores logical piece occupancy for a grid of cells.
    Contains no movement rules and no rendering awareness.
    """

    def __init__(self, grid: List[List[Optional[object]]]):
        self._grid = grid
        for row in range(self.rows):
            for col in range(self.cols):
                self._track_cell(grid[row][col], Position(row, col))

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
        self._track_cell(piece, pos)

    def move_piece(self, pos: Position) -> Optional[object]:
        previous = self._grid[pos.row][pos.col]
        self._grid[pos.row][pos.col] = None
        # Only clear the piece's tracked cell if it still points at the
        # square we just vacated - callers relocate a piece by calling
        # set(to_pos, piece) *before* move_piece(from_pos), so by the time
        # this runs the piece's cell may already have been updated to
        # to_pos and must not be clobbered back to None.
        if previous is not None and hasattr(previous, "cell") and previous.cell == pos:
            previous.cell = None
        return previous

    def as_grid(self) -> List[List[Optional[object]]]:
        """Row-by-row read access, e.g. for printing the board."""
        return self._grid

    @staticmethod
    def _track_cell(piece: Optional[object], pos: Optional[Position]) -> None:
        """Keeps piece.cell in sync with where the board actually places it."""
        if piece is not None and hasattr(piece, "cell"):
            piece.cell = pos
