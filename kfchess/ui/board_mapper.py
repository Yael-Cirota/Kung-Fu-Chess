from kfchess.model.position import Position


class BoardMapper:
    """Translates pixel coordinates into board Positions."""

    def __init__(self, cell_size_px: int = 100):
        self._cell_size_px = cell_size_px

    def pixel_to_position(self, x: int, y: int) -> Position:
        col = x // self._cell_size_px
        row = y // self._cell_size_px
        return Position(row, col)
