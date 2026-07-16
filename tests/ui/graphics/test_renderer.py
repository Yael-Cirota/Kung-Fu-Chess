from pathlib import Path

import ui.graphics.renderer as renderer_module
from controller.api import BoardSnapshot, PieceView, Position
from ui.graphics.piece_visual_state import PieceVisualState
from ui.graphics.renderer import BoardRenderer


def make_piece_view(piece_id, symbol, row, col, color="w"):
    return PieceView(piece_id=piece_id, symbol=symbol, color=color, cell=Position(row, col))


def snapshot(rows, cols, *piece_views):
    return BoardSnapshot(rows=rows, cols=cols, piece_views=list(piece_views))


class FakeFrameImg:
    def __init__(self):
        self.read_path = None
        self.read_size = None
        self.draws = []

    def read(self, path, size=None):
        self.read_path = path
        self.read_size = size
        return self

    def draw_on(self, other_img, x, y):
        other_img.draws.append((self, x, y))


def install_fake_img(monkeypatch):
    monkeypatch.setattr(renderer_module, "Img", FakeFrameImg)


class FakeSpriteLoader:
    def __init__(self):
        self.requests = []

    def get(self, symbol, state=None, frame_index=None):
        self.requests.append((symbol, state, frame_index))
        sprite = FakeFrameImg()
        sprite.symbol = symbol
        return sprite


class TestBackgroundSizing:
    def test_reads_board_image_sized_to_grid(self, monkeypatch):
        install_fake_img(monkeypatch)
        board = snapshot(2, 2)
        renderer = BoardRenderer(FakeSpriteLoader(), "/assets/board.png", cell_size_px=64)

        frame = renderer.render(board)

        assert frame.read_path == Path("/assets/board.png")
        assert frame.read_size == (128, 128)  # (cols*64, rows*64)

    def test_empty_grid_is_handled(self, monkeypatch):
        install_fake_img(monkeypatch)
        board = snapshot(0, 0)
        renderer = BoardRenderer(FakeSpriteLoader(), "/assets/board.png", cell_size_px=64)

        frame = renderer.render(board)

        assert frame.read_size == (0, 0)


class TestPieceFallbackPosition:
    def test_piece_without_visual_state_draws_at_its_grid_cell(self, monkeypatch):
        install_fake_img(monkeypatch)
        rook = make_piece_view(1, "wR", row=0, col=1)
        board = snapshot(2, 2, rook)
        loader = FakeSpriteLoader()
        renderer = BoardRenderer(loader, "/assets/board.png", cell_size_px=64)

        frame = renderer.render(board)

        assert loader.requests == [("wR", None, None)]
        assert len(frame.draws) == 1
        sprite, x, y = frame.draws[0]
        assert (x, y) == (64, 0)  # col 1, row 0

    def test_no_pieces_draws_nothing(self, monkeypatch):
        install_fake_img(monkeypatch)
        board = snapshot(1, 2)
        loader = FakeSpriteLoader()
        renderer = BoardRenderer(loader, "/assets/board.png", cell_size_px=64)

        renderer.render(board)

        assert loader.requests == []


class TestPieceWithVisualState:
    def test_uses_pixel_position_and_sprite_state_from_visual_state(self, monkeypatch):
        install_fake_img(monkeypatch)
        knight = make_piece_view(1, "bN", row=0, col=0)
        board = snapshot(1, 1, knight)
        loader = FakeSpriteLoader()
        renderer = BoardRenderer(loader, "/assets/board.png", cell_size_px=64)
        visual_states = {1: PieceVisualState(pixel_x=12.7, pixel_y=30.2, sprite_state="jump", frame_index=2)}

        frame = renderer.render(board, visual_states)

        assert loader.requests == [("bN", "jump", 2)]
        sprite, x, y = frame.draws[0]
        assert (x, y) == (12, 30)  # truncated to int

    def test_piece_missing_from_visual_states_falls_back(self, monkeypatch):
        install_fake_img(monkeypatch)
        knight = make_piece_view(1, "bN", row=0, col=0)
        rook = make_piece_view(2, "wR", row=0, col=1)
        board = snapshot(1, 2, knight, rook)
        loader = FakeSpriteLoader()
        renderer = BoardRenderer(loader, "/assets/board.png", cell_size_px=64)
        visual_states = {1: PieceVisualState(pixel_x=5, pixel_y=5, sprite_state="move", frame_index=0)}

        renderer.render(board, visual_states)

        assert ("wR", None, None) in loader.requests
