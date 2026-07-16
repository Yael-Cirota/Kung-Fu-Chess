from controller.api import MoveLogEntry, Position
from ui.graphics.move_log_panel import MoveLogPanel, format_move, square_name


def entry(color, symbol, frm, to):
    return MoveLogEntry(color=color, symbol=symbol, from_pos=frm, to_pos=to)


class FakeCanvas:
    """Records draw_text calls so panel layout can be asserted without pixels."""

    def __init__(self):
        self.texts = []  # (text, x, y, scale, color, thickness)

    def draw_text(self, frame, text, x, y, font_scale, color, thickness=1):
        self.texts.append((text, x, y, font_scale, color, thickness))


def make_panel(width_px=200, line_height_px=20, header_height_px=30, padding_px=10):
    return MoveLogPanel(
        width_px=width_px, bg_color=(0, 0, 0), header_color=(1, 1, 1),
        white_text_color=(2, 2, 2), black_text_color=(3, 3, 3),
        font_scale=0.5, line_height_px=line_height_px,
        header_height_px=header_height_px, padding_px=padding_px,
    )


class TestSquareName:
    def test_bottom_left_is_a1_on_an_eight_row_board(self):
        assert square_name(Position(7, 0), rows=8) == "a1"

    def test_top_right_is_h8_on_an_eight_row_board(self):
        assert square_name(Position(0, 7), rows=8) == "h8"


class TestFormatMove:
    def test_pawn_double_step_reads_like_algebraic(self):
        # e2-e4: row6/col4 -> row4/col4 on an 8-row board.
        assert format_move(entry("w", "wP", Position(6, 4), Position(4, 4)), rows=8) == "Pe2-e4"

    def test_uses_the_kind_letter_from_the_symbol(self):
        assert format_move(entry("b", "bN", Position(0, 1), Position(2, 2)), rows=8) == "Nb8-c6"


class TestBgColor:
    def test_exposes_configured_background(self):
        assert make_panel().bg_color == (0, 0, 0)


class TestDraw:
    def test_draws_a_header_per_column(self):
        canvas = FakeCanvas()
        make_panel().draw(canvas, frame=object(), move_log=[], board_width_px=800, board_height_px=800, rows=8)

        titles = [t[0] for t in canvas.texts]
        assert titles == ["White", "Black"]

    def test_files_each_move_under_its_players_column(self):
        canvas = FakeCanvas()
        log = [
            entry("w", "wP", Position(6, 4), Position(4, 4)),  # Pe2-e4
            entry("b", "bN", Position(0, 1), Position(2, 2)),  # Nb8-c6
        ]
        panel = make_panel(width_px=200, padding_px=10)
        panel.draw(canvas, frame=object(), move_log=log, board_width_px=800, board_height_px=800, rows=8)

        white_x = 800 + 10                # board_width + padding
        black_x = 800 + 200 // 2 + 10     # board_width + half_width + padding
        by_text = {t[0]: t for t in canvas.texts}
        assert by_text["1. Pe2-e4"][1] == white_x
        assert by_text["1. Pe2-e4"][4] == (2, 2, 2)  # white text color
        assert by_text["1. Nb8-c6"][1] == black_x
        assert by_text["1. Nb8-c6"][4] == (3, 3, 3)  # black text color

    def test_numbers_moves_per_color(self):
        canvas = FakeCanvas()
        log = [
            entry("w", "wP", Position(6, 0), Position(5, 0)),
            entry("w", "wP", Position(6, 1), Position(5, 1)),
        ]
        make_panel().draw(canvas, frame=object(), move_log=log, board_width_px=800, board_height_px=800, rows=8)

        texts = [t[0] for t in canvas.texts]
        assert "1. Pa2-a3" in texts
        assert "2. Pb2-b3" in texts

    def test_shows_only_the_tail_that_fits_and_keeps_numbering(self):
        canvas = FakeCanvas()
        # header at y=30, line height 20, board height 90 -> capacity = (90-50)//20 = 2.
        panel = make_panel(line_height_px=20, header_height_px=30)
        log = [entry("w", "wP", Position(6, c), Position(5, c)) for c in range(4)]  # 4 white moves

        panel.draw(canvas, frame=object(), move_log=log, board_width_px=800, board_height_px=90, rows=8)

        move_texts = [t[0] for t in canvas.texts if t[0] != "White" and t[0] != "Black"]
        assert move_texts == ["3. Pc2-c3", "4. Pd2-d3"]  # newest two, still numbered 3 and 4

    def test_zero_capacity_draws_headers_only(self):
        canvas = FakeCanvas()
        panel = make_panel(line_height_px=20, header_height_px=30)
        log = [entry("w", "wP", Position(6, 0), Position(5, 0))]

        # board height leaves no room for even one line below the first-line offset.
        panel.draw(canvas, frame=object(), move_log=log, board_width_px=800, board_height_px=40, rows=8)

        assert [t[0] for t in canvas.texts] == ["White", "Black"]
