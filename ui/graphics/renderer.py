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

    def __init__(self, canvas: Canvas, sprite_loader: SpriteLoader, board_image_path: Path, cell_size_px: int,
                 move_log_panel=None, score_panel=None, board_theme=None):
        self._canvas = canvas
        self._sprite_loader = sprite_loader
        self._board_image_path = Path(board_image_path)
        self._cell_size_px = cell_size_px
        self._move_log_panel = move_log_panel
        self._score_panel = score_panel
        # Optional cosmetic overlays (last-move highlight, coordinate labels).
        # None keeps the bare board exactly as before, so the demo/board-only
        # paths and their tests are unaffected.
        self._board_theme = board_theme

    def render(self, board_snapshot, visual_states: Optional[Dict[int, PieceVisualState]] = None,
               move_log=None, scoreboard=None) -> ImageHandle:
        rows, cols = board_snapshot.rows, board_snapshot.cols
        visual_states = visual_states or {}
        board_w = cols * self._cell_size_px
        board_h = rows * self._cell_size_px

        board_image = self._canvas.load_image(self._board_image_path, size=(board_w, board_h))
        if move_log is None:
            # Board-only frame: no panel, unchanged from before (also the demo path).
            frame = board_image
        else:
            # Compose the board (kept at the origin) plus a right-hand log panel.
            frame = self._canvas.blank(
                (board_w + self._move_log_panel.width_px, board_h), self._move_log_panel.bg_color
            )
            self._canvas.blit(frame, board_image, 0, 0)

        # Cosmetic overlays sit between the board and the pieces so a moving
        # sprite always rides on top of its highlight, never under it.
        if self._board_theme is not None:
            self._draw_last_move_highlight(frame, move_log)
            self._draw_coordinates(frame, rows, cols, board_h)

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

        if move_log is not None:
            if self._score_panel is not None and scoreboard is not None:
                self._score_panel.draw(self._canvas, frame, scoreboard, board_w)
            self._move_log_panel.draw(self._canvas, frame, move_log, board_w, board_h, rows)

        return frame

    def _draw_last_move_highlight(self, frame, move_log) -> None:
        """Washes the from/to cells of the newest logged move in a translucent tint."""
        theme = self._board_theme
        if not theme.highlight_last_move or not move_log:
            return
        last = move_log[-1]
        for pos in (last.from_pos, last.to_pos):
            self._canvas.fill_rect(
                frame, pos.col * self._cell_size_px, pos.row * self._cell_size_px,
                self._cell_size_px, self._cell_size_px,
                theme.last_move_color, alpha=theme.last_move_alpha,
            )

    def _draw_coordinates(self, frame, rows, cols, board_h) -> None:
        """File letters along the bottom edge and rank numbers down the left edge."""
        theme = self._board_theme
        if not theme.show_coordinates:
            return
        margin = theme.coordinate_margin_px
        for col in range(cols):
            self._draw_label(frame, chr(ord("a") + col), col * self._cell_size_px + margin, board_h - margin)
        for row in range(rows):
            self._draw_label(frame, str(rows - row), margin, row * self._cell_size_px + margin + self._text_baseline_px())

    def _draw_label(self, frame, text, x, y) -> None:
        """One coordinate glyph: a darker halo underneath (if enabled) then the label on top."""
        theme = self._board_theme
        if theme.coordinate_outline_thickness:
            self._canvas.draw_text(
                frame, text, x, y, theme.coordinate_font_scale,
                theme.coordinate_outline_color, theme.coordinate_outline_thickness,
            )
        self._canvas.draw_text(
            frame, text, x, y, theme.coordinate_font_scale,
            theme.coordinate_color, theme.coordinate_thickness,
        )

    def _text_baseline_px(self) -> int:
        """Rough cap height so a top-anchored rank label drops below the top edge, not above it."""
        return max(8, int(self._board_theme.coordinate_font_scale * 26))
