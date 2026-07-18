"""
The score band at the top of the right-hand strip: each player's running
capture-point total, always on screen.

`format_score` is a pure function - one player's label + number in, a display
string out - so the wording is trivially testable and never entangled with
pixels. `ScorePanel` owns only the layout: it stacks the White and Black
totals in a fixed-height band, drawing through the Canvas seam (draw_text) so
cv2 never leaks in here. It reserves `height_px` at the top of the strip; the
move-log panel below is told to start beneath it.
"""


def format_score(label: str, points: int) -> str:
    """One score line, e.g. 'White: 7'."""
    return f"{label}: {points}"


class ScorePanel:
    """
    Renders the two per-player score totals into the top of the strip to the
    right of the board. Pure layout math over an injected Canvas; holds every
    pixel knob so a caller only supplies the Scoreboard and board width.
    """

    def __init__(
        self, height_px, white_text_color, black_text_color,
        font_scale, line_height_px, header_height_px, padding_px,
    ):
        self.height_px = height_px
        self._white_text_color = white_text_color
        self._black_text_color = black_text_color
        self._font_scale = font_scale
        self._line_height_px = line_height_px
        self._header_height_px = header_height_px
        self._padding_px = padding_px

    def draw(self, canvas, frame, scoreboard, board_width_px) -> None:
        x = board_width_px + self._padding_px
        white_y = self._header_height_px
        black_y = white_y + self._line_height_px

        canvas.draw_text(
            frame, format_score("White", scoreboard.white), x, white_y,
            self._font_scale, self._white_text_color, thickness=1,
        )
        canvas.draw_text(
            frame, format_score("Black", scoreboard.black), x, black_y,
            self._font_scale, self._black_text_color, thickness=1,
        )
