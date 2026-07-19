from kfchess.api import MoveResult, PieceView, Position

from ui.board_geometry import BoardGeometry
from ui.click_handler import ClickHandler


def piece_view(piece_id, symbol, row, col, color="w"):
    return PieceView(piece_id=piece_id, symbol=symbol, color=color, cell=Position(row, col))


class FakeSession:
    """
    Minimal stand-in for kfchess.api.GameSession, narrowed to the three
    methods ClickHandler actually calls - that trio *is* the seam between
    click handling and the engine.
    """

    def __init__(self, pieces=None, next_result=None):
        self._pieces = dict(pieces or {})  # Position -> PieceView
        self._next_result = next_result if next_result is not None else MoveResult.accepted()
        self.request_move_calls = []

    def is_within_bounds(self, pos):
        return 0 <= pos.row < 8 and 0 <= pos.col < 8

    def piece_at(self, pos):
        return self._pieces.get(pos)

    def request_move(self, from_pos, to_pos):
        self.request_move_calls.append((from_pos, to_pos))
        return self._next_result


class TestClickHandlerSelection:
    def test_click_empty_cell_with_no_selection_is_noop(self):
        session = FakeSession()
        handler = ClickHandler(session, BoardGeometry())

        handler.on_click(50, 50)

        assert handler.selected is None

    def test_click_piece_selects_it(self):
        king = piece_view(1, "wK", row=2, col=3)
        session = FakeSession({Position(2, 3): king})
        handler = ClickHandler(session, BoardGeometry())

        handler.on_click(350, 250)  # col=3, row=2

        assert handler.selected == Position(2, 3)

    def test_click_outside_board_is_ignored(self):
        king = piece_view(1, "wK", row=0, col=0)
        session = FakeSession({Position(0, 0): king})
        handler = ClickHandler(session, BoardGeometry())

        handler.on_click(900, 900)

        assert handler.selected is None

    def test_click_friendly_piece_replaces_selection(self):
        king = piece_view(1, "wK", row=0, col=0)
        rook = piece_view(2, "wR", row=0, col=1)
        session = FakeSession({Position(0, 0): king, Position(0, 1): rook})
        handler = ClickHandler(session, BoardGeometry())

        handler.on_click(50, 50)   # select king at (0,0)
        handler.on_click(150, 50)  # click rook at (0,1)

        assert session.request_move_calls == []
        assert handler.selected == Position(0, 1)

    def test_off_board_click_with_selection_cancels_it_without_a_command(self):
        rook = piece_view(1, "wR", row=0, col=0)
        session = FakeSession({Position(0, 0): rook})
        handler = ClickHandler(session, BoardGeometry())

        handler.on_click(50, 50)    # select rook at (0,0)
        handler.on_click(900, 900)  # off-board click cancels selection

        assert handler.selected is None
        assert session.request_move_calls == []


class TestClickHandlerJump:
    def test_clicking_the_selected_piece_again_requests_a_jump(self):
        rook = piece_view(1, "wR", row=4, col=0)
        session = FakeSession({Position(4, 0): rook})
        handler = ClickHandler(session, BoardGeometry())

        handler.on_click(50, 450)  # select rook at (4,0)
        handler.on_click(50, 450)  # click the same cell again

        assert session.request_move_calls == [(Position(4, 0), Position(4, 0))]
        assert handler.selected is None


class TestClickHandlerMoveAttempts:
    def test_legal_move_calls_request_move_and_clears_selection(self):
        rook = piece_view(1, "wR", row=4, col=0)
        session = FakeSession({Position(4, 0): rook})
        handler = ClickHandler(session, BoardGeometry())

        handler.on_click(50, 450)   # select rook at (4,0)
        handler.on_click(750, 450)  # attempt move to (4,7)

        assert session.request_move_calls == [(Position(4, 0), Position(4, 7))]
        assert handler.selected is None

    def test_illegal_move_still_calls_request_move_and_clears_selection(self):
        rook = piece_view(1, "wR", row=4, col=0)
        session = FakeSession({Position(4, 0): rook}, next_result=MoveResult.rejected("illegal_piece_move"))
        handler = ClickHandler(session, BoardGeometry())

        handler.on_click(50, 450)   # select rook at (4,0)
        handler.on_click(150, 350)  # diagonal - illegal for rook

        assert session.request_move_calls == [(Position(4, 0), Position(3, 1))]
        assert handler.selected is None
