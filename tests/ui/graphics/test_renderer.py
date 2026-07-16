from pathlib import Path

from controller.api import BoardSnapshot, PieceView, Position
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


class FakeCanvas:
    """
    Records load_image/blit calls instead of touching real pixels - the whole
    point of the Canvas seam. load_image returns a distinct FakeFrame for the
    board and a symbol-tagged handle for each sprite, so blits can be asserted
    by (symbol, x, y).
    """

    def __init__(self):
        self.blits = []  # (frame, sprite_handle, x, y)

    def load_image(self, path, size=None, keep_aspect=False):
        return FakeFrame(Path(path), size)

    def blit(self, frame, image, x, y):
        self.blits.append((frame, image, x, y))


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
