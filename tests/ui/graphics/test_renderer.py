from pathlib import Path

from controller.api import BoardSnapshot, MoveLogEntry, PieceView, Position
from ui.graphics.board_theme import BoardTheme
from ui.graphics.piece_visual_state import PieceVisualState
from ui.graphics.renderer import BoardRenderer


def make_piece_view(piece_id, symbol, row, col, color="w"):
    return PieceView(piece_id=piece_id, symbol=symbol, color=color, cell=Position(row, col))


def snapshot(rows, cols, *piece_views):
    return BoardSnapshot(rows=rows, cols=cols, piece_views=list(piece_views))


class FakeFrame:
    """The opaque handle a FakeCanvas hands back for the loaded board image."""

    def __init__(self, path, size):
        self.path = path
        self.size = size


class FakeBlankFrame:
    """The opaque handle a FakeCanvas hands back for a composed (board + panel) frame."""

    def __init__(self, size, color):
        self.size = size
        self.color = color


class FakeCanvas:
    """
    Records load_image/blit calls instead of touching real pixels - the whole
    point of the Canvas seam. load_image returns a distinct FakeFrame for the
    board and a symbol-tagged handle for each sprite, so blits can be asserted
    by (symbol, x, y).
    """

    def __init__(self):
        self.blits = []  # (frame, sprite_handle, x, y)
        self.blanks = []  # (size, color)
        self.fills = []  # (x, y, w, h, color, alpha)
        self.texts = []  # (text, x, y, scale, color, thickness)

    def load_image(self, path, size=None, keep_aspect=False):
        return FakeFrame(Path(path), size)

    def blank(self, size, color):
        frame = FakeBlankFrame(size, color)
        self.blanks.append(frame)
        return frame

    def blit(self, frame, image, x, y):
        self.blits.append((frame, image, x, y))

    def fill_rect(self, frame, x, y, w, h, color, alpha=1.0):
        self.fills.append((x, y, w, h, color, alpha))

    def draw_text(self, frame, text, x, y, font_scale, color, thickness=1):
        self.texts.append((text, x, y, font_scale, color, thickness))


class FakeMoveLogPanel:
    def __init__(self, width_px=120, bg_color=(9, 9, 9)):
        self.width_px = width_px
        self.bg_color = bg_color
        self.draw_calls = []

    def draw(self, canvas, frame, move_log, board_width_px, board_height_px, rows):
        self.draw_calls.append((frame, move_log, board_width_px, board_height_px, rows))


class FakeScorePanel:
    def __init__(self, height_px=64):
        self.height_px = height_px
        self.draw_calls = []

    def draw(self, canvas, frame, scoreboard, board_width_px):
        self.draw_calls.append((frame, scoreboard, board_width_px))


class FakeSpriteLoader:
    def __init__(self):
        self.requests = []

    def get(self, symbol, state=None, frame_index=None):
        self.requests.append((symbol, state, frame_index))
        return f"sprite:{symbol}"


class TestBackgroundSizing:
    def test_reads_board_image_sized_to_grid(self):
        canvas = FakeCanvas()
        board = snapshot(2, 2)
        renderer = BoardRenderer(canvas, FakeSpriteLoader(), "/assets/board.png", cell_size_px=64)

        frame = renderer.render(board)

        assert frame.path == Path("/assets/board.png")
        assert frame.size == (128, 128)  # (cols*64, rows*64)

    def test_empty_grid_is_handled(self):
        canvas = FakeCanvas()
        board = snapshot(0, 0)
        renderer = BoardRenderer(canvas, FakeSpriteLoader(), "/assets/board.png", cell_size_px=64)

        frame = renderer.render(board)

        assert frame.size == (0, 0)


class TestPieceFallbackPosition:
    def test_piece_without_visual_state_draws_at_its_grid_cell(self):
        canvas = FakeCanvas()
        rook = make_piece_view(1, "wR", row=0, col=1)
        board = snapshot(2, 2, rook)
        loader = FakeSpriteLoader()
        renderer = BoardRenderer(canvas, loader, "/assets/board.png", cell_size_px=64)

        renderer.render(board)

        assert loader.requests == [("wR", None, None)]
        assert len(canvas.blits) == 1
        _frame, sprite, x, y = canvas.blits[0]
        assert sprite == "sprite:wR"
        assert (x, y) == (64, 0)  # col 1, row 0

    def test_no_pieces_draws_nothing(self):
        canvas = FakeCanvas()
        board = snapshot(1, 2)
        loader = FakeSpriteLoader()
        renderer = BoardRenderer(canvas, loader, "/assets/board.png", cell_size_px=64)

        renderer.render(board)

        assert loader.requests == []
        assert canvas.blits == []


class TestPieceWithVisualState:
    def test_uses_pixel_position_and_sprite_state_from_visual_state(self):
        canvas = FakeCanvas()
        knight = make_piece_view(1, "bN", row=0, col=0)
        board = snapshot(1, 1, knight)
        loader = FakeSpriteLoader()
        renderer = BoardRenderer(canvas, loader, "/assets/board.png", cell_size_px=64)
        visual_states = {1: PieceVisualState(pixel_x=12.7, pixel_y=30.2, sprite_state="jump", frame_index=2)}

        renderer.render(board, visual_states)

        assert loader.requests == [("bN", "jump", 2)]
        _frame, _sprite, x, y = canvas.blits[0]
        assert (x, y) == (12, 30)  # truncated to int

    def test_piece_missing_from_visual_states_falls_back(self):
        canvas = FakeCanvas()
        knight = make_piece_view(1, "bN", row=0, col=0)
        rook = make_piece_view(2, "wR", row=0, col=1)
        board = snapshot(1, 2, knight, rook)
        loader = FakeSpriteLoader()
        renderer = BoardRenderer(canvas, loader, "/assets/board.png", cell_size_px=64)
        visual_states = {1: PieceVisualState(pixel_x=5, pixel_y=5, sprite_state="move", frame_index=0)}

        renderer.render(board, visual_states)

        assert ("wR", None, None) in loader.requests


class TestMoveLogPanel:
    def test_no_move_log_keeps_the_board_only_frame_and_skips_the_panel(self):
        canvas = FakeCanvas()
        panel = FakeMoveLogPanel()
        board = snapshot(2, 2)
        renderer = BoardRenderer(canvas, FakeSpriteLoader(), "/assets/board.png", 64, panel)

        renderer.render(board)  # move_log defaults to None

        assert canvas.blanks == []
        assert panel.draw_calls == []

    def test_with_move_log_composes_a_wide_frame_with_the_board_at_the_origin(self):
        canvas = FakeCanvas()
        panel = FakeMoveLogPanel(width_px=120, bg_color=(9, 9, 9))
        board = snapshot(2, 2)
        renderer = BoardRenderer(canvas, FakeSpriteLoader(), "/assets/board.png", 64, panel)

        frame = renderer.render(board, move_log=[])

        # 2x2 board at 64px = 128x128; panel adds 120px of width.
        assert frame.size == (128 + 120, 128)
        assert frame.color == (9, 9, 9)
        # The board image is blitted onto the composed frame at the origin.
        board_blit = canvas.blits[0]
        assert board_blit[0] is frame and board_blit[2:] == (0, 0)

    def test_delegates_to_the_panel_with_board_geometry(self):
        canvas = FakeCanvas()
        panel = FakeMoveLogPanel(width_px=120)
        board = snapshot(2, 2)
        renderer = BoardRenderer(canvas, FakeSpriteLoader(), "/assets/board.png", 64, panel)
        log = ["entry"]

        frame = renderer.render(board, move_log=log)

        assert panel.draw_calls == [(frame, log, 128, 128, 2)]

    def test_pieces_draw_at_board_coordinates_on_the_composed_frame(self):
        canvas = FakeCanvas()
        panel = FakeMoveLogPanel(width_px=120)
        rook = make_piece_view(1, "wR", row=0, col=1)
        board = snapshot(2, 2, rook)
        renderer = BoardRenderer(canvas, FakeSpriteLoader(), "/assets/board.png", 64, panel)

        renderer.render(board, move_log=[])

        # First blit is the board background; the sprite blit follows at its grid cell.
        sprite_blit = canvas.blits[1]
        assert sprite_blit[1] == "sprite:wR"
        assert sprite_blit[2:] == (64, 0)


class TestScorePanel:
    def test_draws_the_score_panel_over_the_board_width_when_a_scoreboard_is_given(self):
        canvas = FakeCanvas()
        score_panel = FakeScorePanel()
        board = snapshot(2, 2)
        renderer = BoardRenderer(
            canvas, FakeSpriteLoader(), "/assets/board.png", 64, FakeMoveLogPanel(), score_panel
        )

        frame = renderer.render(board, move_log=[], scoreboard="SB")

        # board is 2x2 at 64px = 128 wide; the panel draws over that width.
        assert score_panel.draw_calls == [(frame, "SB", 128)]

    def test_score_panel_is_skipped_without_a_scoreboard(self):
        canvas = FakeCanvas()
        score_panel = FakeScorePanel()
        board = snapshot(2, 2)
        renderer = BoardRenderer(
            canvas, FakeSpriteLoader(), "/assets/board.png", 64, FakeMoveLogPanel(), score_panel
        )

        renderer.render(board, move_log=[])  # move log present, but no scoreboard

        assert score_panel.draw_calls == []

    def test_score_panel_is_skipped_on_a_board_only_frame(self):
        canvas = FakeCanvas()
        score_panel = FakeScorePanel()
        board = snapshot(2, 2)
        renderer = BoardRenderer(
            canvas, FakeSpriteLoader(), "/assets/board.png", 64, FakeMoveLogPanel(), score_panel
        )

        renderer.render(board, scoreboard="SB")  # no move_log -> board-only path

        assert score_panel.draw_calls == []


def move_entry(color, symbol, frm, to):
    return MoveLogEntry(color=color, symbol=symbol, from_pos=frm, to_pos=to)


class TestBoardThemeCoordinates:
    def test_no_theme_draws_no_coordinate_labels(self):
        canvas = FakeCanvas()
        board = snapshot(2, 2)
        renderer = BoardRenderer(canvas, FakeSpriteLoader(), "/assets/board.png", cell_size_px=64)

        renderer.render(board)

        assert canvas.texts == []

    def test_theme_labels_files_along_the_bottom_and_ranks_down_the_left(self):
        canvas = FakeCanvas()
        board = snapshot(2, 2)
        # No halo here so each label maps to exactly one draw_text call.
        theme = BoardTheme(highlight_last_move=False, coordinate_outline_thickness=0)
        renderer = BoardRenderer(canvas, FakeSpriteLoader(), "/assets/board.png", 64, board_theme=theme)

        renderer.render(board)

        labels = [t[0] for t in canvas.texts]
        assert labels == ["a", "b", "2", "1"]  # files a,b along bottom; ranks 2,1 top-to-bottom
        by_label = {t[0]: t for t in canvas.texts}
        # file 'a' sits at the left of col 0, near the bottom edge (board_h=128).
        assert by_label["a"][1] == theme.coordinate_margin_px
        assert by_label["a"][2] == 128 - theme.coordinate_margin_px
        # rank '2' labels the top row, in the left margin.
        assert by_label["2"][1] == theme.coordinate_margin_px

    def test_each_glyph_gets_a_darker_halo_drawn_under_it_for_contrast(self):
        canvas = FakeCanvas()
        board = snapshot(1, 1)  # a single cell -> one file 'a' and one rank '1'
        theme = BoardTheme(
            highlight_last_move=False, coordinate_color=(230, 230, 230),
            coordinate_thickness=1, coordinate_outline_color=(30, 30, 30),
            coordinate_outline_thickness=3,
        )
        renderer = BoardRenderer(canvas, FakeSpriteLoader(), "/assets/board.png", 64, board_theme=theme)

        renderer.render(board)

        # Per glyph: the thick dark halo is drawn first, the light label second on top.
        colors_and_thickness = [(t[4], t[5]) for t in canvas.texts]
        assert colors_and_thickness == [
            ((30, 30, 30), 3), ((230, 230, 230), 1),   # 'a' halo then label
            ((30, 30, 30), 3), ((230, 230, 230), 1),   # '1' halo then label
        ]

    def test_coordinates_can_be_disabled(self):
        canvas = FakeCanvas()
        board = snapshot(2, 2)
        theme = BoardTheme(show_coordinates=False, highlight_last_move=False)
        renderer = BoardRenderer(canvas, FakeSpriteLoader(), "/assets/board.png", 64, board_theme=theme)

        renderer.render(board)

        assert canvas.texts == []


class TestBoardThemeLastMoveHighlight:
    def test_highlights_the_from_and_to_cells_of_the_last_logged_move(self):
        canvas = FakeCanvas()
        panel = FakeMoveLogPanel()
        board = snapshot(8, 8)
        theme = BoardTheme(show_coordinates=False, last_move_color=(90, 200, 130), last_move_alpha=0.3)
        renderer = BoardRenderer(
            canvas, FakeSpriteLoader(), "/assets/board.png", 64, panel, board_theme=theme
        )
        log = [
            move_entry("w", "wP", Position(6, 0), Position(5, 0)),  # older move
            move_entry("b", "bP", Position(1, 3), Position(3, 3)),  # newest -> highlighted
        ]

        renderer.render(board, move_log=log)

        # from (1,3) and to (3,3), each a 64px cell washed at the theme's alpha.
        assert canvas.fills == [
            (3 * 64, 1 * 64, 64, 64, (90, 200, 130), 0.3),
            (3 * 64, 3 * 64, 64, 64, (90, 200, 130), 0.3),
        ]

    def test_no_highlight_on_the_board_only_path(self):
        canvas = FakeCanvas()
        board = snapshot(8, 8)
        theme = BoardTheme(show_coordinates=False)
        renderer = BoardRenderer(canvas, FakeSpriteLoader(), "/assets/board.png", 64, board_theme=theme)

        renderer.render(board)  # move_log is None

        assert canvas.fills == []

    def test_no_highlight_when_the_log_is_empty(self):
        canvas = FakeCanvas()
        panel = FakeMoveLogPanel()
        board = snapshot(8, 8)
        theme = BoardTheme(show_coordinates=False)
        renderer = BoardRenderer(
            canvas, FakeSpriteLoader(), "/assets/board.png", 64, panel, board_theme=theme
        )

        renderer.render(board, move_log=[])

        assert canvas.fills == []

    def test_highlight_can_be_disabled(self):
        canvas = FakeCanvas()
        panel = FakeMoveLogPanel()
        board = snapshot(8, 8)
        theme = BoardTheme(highlight_last_move=False, show_coordinates=False)
        renderer = BoardRenderer(
            canvas, FakeSpriteLoader(), "/assets/board.png", 64, panel, board_theme=theme
        )

        renderer.render(board, move_log=[move_entry("w", "wP", Position(6, 0), Position(5, 0))])

        assert canvas.fills == []

    def test_highlight_sits_under_the_pieces(self):
        # The wash must be painted before the sprites, so a piece standing on a
        # highlighted cell is drawn on top of the tint, not hidden by it.
        canvas = FakeCanvas()
        panel = FakeMoveLogPanel()
        pawn = make_piece_view(1, "wP", row=5, col=0)
        board = snapshot(8, 8, pawn)
        theme = BoardTheme(show_coordinates=False)
        renderer = BoardRenderer(
            canvas, FakeSpriteLoader(), "/assets/board.png", 64, panel, board_theme=theme
        )

        # Record fills and *sprite* blits (not the board blit) in call order.
        order = []
        real_fill, real_blit = canvas.fill_rect, canvas.blit

        def spy_fill(*a, **k):
            order.append("fill")
            return real_fill(*a, **k)

        def spy_blit(frame, image, x, y):
            if image == "sprite:wP":
                order.append("piece")
            return real_blit(frame, image, x, y)

        canvas.fill_rect = spy_fill
        canvas.blit = spy_blit

        renderer.render(board, move_log=[move_entry("w", "wP", Position(6, 0), Position(5, 0))])

        assert order == ["fill", "fill", "piece"]
