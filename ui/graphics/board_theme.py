"""
Cosmetic board-overlay settings, grouped into one immutable value object so the
renderer's constructor doesn't sprout a dozen loose style parameters. Purely
decorative: every field here changes only pixels drawn *over* the board
background (a last-move highlight and edge coordinate labels), never geometry,
never click mapping - the board still starts at the origin and every cell keeps
its size. Colours are BGR to match OpenCV. A `None` theme (the renderer's
default) simply skips all of it, which is why the existing board-only/demo
paths are unchanged.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class BoardTheme:
    # Translucent wash over the from/to cells of the most recent logged move,
    # so a player can see at a glance what just happened on a boardful of pieces.
    highlight_last_move: bool = True
    last_move_color: Tuple[int, int, int] = (90, 200, 130)  # BGR: soft green
    last_move_alpha: float = 0.30

    # Translucent wash over the cell of whichever piece the player currently
    # has selected, so the selection stays visibly marked until the piece
    # moves or is deselected - independent of (and drawn over) the last-move
    # wash above.
    highlight_selected: bool = True
    selected_color: Tuple[int, int, int] = (60, 170, 250)  # BGR: warm amber
    selected_alpha: float = 0.35

    # File letters (a-h) along the bottom edge and rank numbers (1-8) down the
    # left edge, drawn small in the cell corners so they never cover a sprite.
    show_coordinates: bool = True
    coordinate_color: Tuple[int, int, int] = (230, 230, 230)  # BGR: near-white glyph
    coordinate_font_scale: float = 0.38
    coordinate_thickness: int = 1
    coordinate_margin_px: int = 5
    # A darker halo drawn under each glyph so a light label stays legible over a
    # light square (and vice versa). Set outline_thickness to 0 to disable it.
    coordinate_outline_color: Tuple[int, int, int] = (30, 30, 30)  # BGR: near-black
    coordinate_outline_thickness: int = 3
