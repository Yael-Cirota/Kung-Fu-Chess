"""
The side panel that shows each player the moves they issued.

`format_move` is a pure function - board geometry in, algebraic-ish notation
string out - so notation is trivially testable and never entangled with pixels.
`MoveLogPanel` owns only the layout: it splits the log by color into a White
column and a Black column and paints the tail that fits, drawing through the
Canvas seam (blank/draw_text) so cv2 never leaks in here either.
"""

WHITE = "w"
BLACK = "b"


def square_name(pos, rows: int) -> str:
    """(row, col) -> chess square, e.g. row 6/col 4 on an 8-row board -> 'e4'.

    Column 0 is file 'a'; the bottom board row (white's back rank) is rank 1,
    so rank counts up from the bottom: rank = rows - row.
    """
    return f"{chr(ord('a') + pos.col)}{rows - pos.row}"


def format_move(entry, rows: int) -> str:
    """One log line: piece letter + from-square + '-' + to-square, e.g. 'Pe2-e4'.

    The piece letter is the kind half of a 'wP'/'bN' symbol (index 1), so it is
    already the uppercase K/Q/R/B/N/P used in standard notation.
    """
    kind = entry.symbol[1]
    return f"{kind}{square_name(entry.from_pos, rows)}-{square_name(entry.to_pos, rows)}"


class MoveLogPanel:
    """
    Renders the two per-player move columns into the strip to the right of the
    board. Pure layout math over an injected Canvas; holds every pixel knob so
    a caller only supplies data and board dimensions.
    """

    def __init__(
        self, width_px, bg_color, header_color, white_text_color, black_text_color,
        font_scale, line_height_px, header_height_px, padding_px,
    ):
        self.width_px = width_px
        self._bg_color = bg_color
        self._header_color = header_color
        self._white_text_color = white_text_color
        self._black_text_color = black_text_color
        self._font_scale = font_scale
        self._line_height_px = line_height_px
        self._header_height_px = header_height_px
        self._padding_px = padding_px

    @property
    def bg_color(self):
        return self._bg_color

    def draw(self, canvas, frame, move_log, board_width_px, board_height_px, rows) -> None:
        white_moves = [e for e in move_log if e.color == WHITE]
        black_moves = [e for e in move_log if e.color == BLACK]

        half_width = self.width_px // 2
        left_x = board_width_px + self._padding_px
        right_x = board_width_px + half_width + self._padding_px

        self._draw_column(canvas, frame, "White", white_moves, rows, left_x, board_height_px, self._white_text_color)
        self._draw_column(canvas, frame, "Black", black_moves, rows, right_x, board_height_px, self._black_text_color)

    def _draw_column(self, canvas, frame, title, moves, rows, x, board_height_px, text_color) -> None:
        canvas.draw_text(frame, title, x, self._header_height_px, self._font_scale, self._header_color, thickness=1)

        first_line_y = self._header_height_px + self._line_height_px
        capacity = max(0, (board_height_px - first_line_y) // self._line_height_px)
        # Keep the newest moves visible: once the column fills, show the tail.
        visible = moves[-capacity:] if capacity else []
        first_number = len(moves) - len(visible) + 1

        for offset, entry in enumerate(visible):
            y = first_line_y + offset * self._line_height_px
            text = f"{first_number + offset}. {format_move(entry, rows)}"
            canvas.draw_text(frame, text, x, y, self._font_scale, text_color, thickness=1)
