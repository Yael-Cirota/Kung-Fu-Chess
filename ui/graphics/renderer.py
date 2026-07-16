from pathlib import Path
from typing import Dict, Optional

from ui.graphics.canvas import Canvas, ImageHandle
from ui.graphics.piece_visual_state import PieceVisualState
from ui.graphics.sprite_loader import SpriteLoader


class BoardRenderer:
    """
    Composes one frame: the board background plus every piece's sprite at
    its current pixel position. Only knows a controller.api.BoardSnapshot
    (rows/cols + a list of PieceView, each exposing symbol/cell/piece_id) -
    no kfchess types and no motion-timing/animation-state-machine logic are
    known here. Pixels are loaded and blitted through an injected Canvas, so
    this class never imports Img/cv2. Per-piece pixel position and
    (sprite_state, frame_index) are supplied by the caller via
    `visual_states` (keyed by piece_id); a piece absent from that mapping
    falls back to its resting cell position and the static idle sprite,
    exactly as in Stage 2/3.
    """

    def __init__(self, canvas: Canvas, sprite_loader: SpriteLoader, board_image_path: Path, cell_size_px: int):
        self._canvas = canvas
        self._sprite_loader = sprite_loader
        self._board_image_path = Path(board_image_path)
        self._cell_size_px = cell_size_px

    def render(self, board_snapshot, visual_states: Optional[Dict[int, PieceVisualState]] = None) -> ImageHandle:
        rows, cols = board_snapshot.rows, board_snapshot.cols
        visual_states = visual_states or {}

        frame = self._canvas.load_image(
            self._board_image_path, size=(cols * self._cell_size_px, rows * self._cell_size_px)
        )

        for piece_view in board_snapshot.pieces():
            visual = visual_states.get(piece_view.piece_id)
            if visual is not None:
                pixel_x, pixel_y = int(visual.pixel_x), int(visual.pixel_y)
                sprite = self._sprite_loader.get(piece_view.symbol, visual.sprite_state, visual.frame_index)
            else:
                pixel_x = piece_view.cell.col * self._cell_size_px
                pixel_y = piece_view.cell.row * self._cell_size_px
                sprite = self._sprite_loader.get(piece_view.symbol)

            self._canvas.blit(frame, sprite, pixel_x, pixel_y)

        return frame
