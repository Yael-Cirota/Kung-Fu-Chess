from typing import Tuple

from kfchess.api import Position


class BoardGeometry:
    """
    The single owner of cell <-> pixel conversion for a rendered board.

    Split out of ClickHandler deliberately: geometry changes for layout
    reasons (a different cell size, or a board flipped 180 degrees so the
    Black player sees their own pieces at the bottom), while click handling
    changes for interaction reasons. Different reasons to change, so they
    are different classes - and every part of ui that needs to map a cell to
    where it is drawn shares this one implementation instead of repeating
    the multiply.
    """

    def __init__(self, cell_size_px: int = 100):
        self._cell_size_px = cell_size_px

    def pixel_to_cell(self, x: int, y: int) -> Position:
        return Position(y // self._cell_size_px, x // self._cell_size_px)

    def cell_to_pixel(self, cell: Position) -> Tuple[int, int]:
        """Top-left corner of `cell`, in pixels - the anchor sprites are drawn from."""
        return cell.col * self._cell_size_px, cell.row * self._cell_size_px

    def cell_center(self, cell: Position) -> Tuple[int, int]:
        half = self._cell_size_px // 2
        x, y = self.cell_to_pixel(cell)
        return x + half, y + half
