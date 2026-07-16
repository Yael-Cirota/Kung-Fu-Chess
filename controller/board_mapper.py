from kfchess.api import Position


class BoardMapper:
    """Translates pixel coordinates into board Positions."""

    def __init__(self, cell_size_px: int = 100):
        self._cell_size_px = cell_size_px

    def pixel_to_position(self, x: int, y: int) -> Position:
        col = x // self._cell_size_px
        row = y // self._cell_size_px
        return Position(row, col)

    def position_to_pixel(self, pos: Position) -> tuple[int, int]:
        x = pos.col * self._cell_size_px
        y = pos.row * self._cell_size_px
        return x, y