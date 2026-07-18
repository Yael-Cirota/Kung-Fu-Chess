from kfchess.api import BoardSnapshot, MotionInfo, MoveResult, PieceView, Position, Scoreboard
from controller.board_mapper import BoardMapper
from controller.game_controller import GameController


def piece_view(piece_id, symbol, row, col, color="w"):
    return PieceView(piece_id=piece_id, symbol=symbol, color=color, cell=Position(row, col))


class FakeSession:
    """Minimal stand-in for kfchess.api.GameSession to keep GameController tests unit-level."""

    def __init__(self, pieces=None, next_result=None, scoreboard=None):
        self._pieces = dict(pieces or {})  # Position -> PieceView
        self._next_result = next_result if next_result is not None else MoveResult.accepted()
        self.request_move_calls = []
        self._motions = {}  # piece_id -> MotionInfo
        self.clock_ms = 0
        self._scoreboard = scoreboard if scoreboard is not None else Scoreboard(white=0, black=0)

    def is_within_bounds(self, pos):
        return 0 <= pos.row < 8 and 0 <= pos.col < 8

    def piece_at(self, pos):
        return self._pieces.get(pos)

    def request_move(self, from_pos, to_pos):
        self.request_move_calls.append((from_pos, to_pos))
        return self._next_result

    def wait(self, ms):
        self.clock_ms += ms

    @property
    def game_over(self):
        return False

    def is_moving(self, piece_id):
        return piece_id in self._motions

    def board_snapshot(self):
        return BoardSnapshot(rows=8, cols=8, piece_views=list(self._pieces.values()))

    def set_motion(self, piece_id, motion):
        self._motions[piece_id] = motion

    def motion_for(self, piece_id):
        return self._motions.get(piece_id)

    def move_log(self):
        return [(f, t) for f, t in self.request_move_calls]

    def scoreboard(self):
        return self._scoreboard


def make_controller(session):
    return GameController(session, BoardMapper())


class TestControllerSelection:
    def test_click_empty_cell_with_no_selection_is_noop(self):
        session = FakeSession()
        controller = make_controller(session)

        controller.on_click(50, 50)

        assert controller.selected is None

    def test_click_piece_selects_it(self):
        king = piece_view(1, "wK", row=2, col=3)
        session = FakeSession({Position(2, 3): king})
        controller = make_controller(session)

        controller.on_click(350, 250)  # col=3, row=2

        assert controller.selected == Position(2, 3)

    def test_click_outside_board_is_ignored(self):
        king = piece_view(1, "wK", row=0, col=0)
        session = FakeSession({Position(0, 0): king})
        controller = make_controller(session)

        controller.on_click(900, 900)

        assert controller.selected is None

    def test_click_friendly_piece_replaces_selection(self):
        king = piece_view(1, "wK", row=0, col=0)
        rook = piece_view(2, "wR", row=0, col=1)
        session = FakeSession({Position(0, 0): king, Position(0, 1): rook})
        controller = make_controller(session)

        controller.on_click(50, 50)   # select king at (0,0)
        controller.on_click(150, 50)  # click rook at (0,1)

        assert session.request_move_calls == []
        assert controller.selected == Position(0, 1)

    def test_off_board_click_with_selection_cancels_it_without_a_command(self):
        rook = piece_view(1, "wR", row=0, col=0)
        session = FakeSession({Position(0, 0): rook})
        controller = make_controller(session)

        controller.on_click(50, 50)    # select rook at (0,0)
        controller.on_click(900, 900)  # off-board click cancels selection

        assert controller.selected is None
        assert session.request_move_calls == []


class TestControllerJump:
    def test_clicking_the_selected_piece_again_requests_a_jump(self):
        rook = piece_view(1, "wR", row=4, col=0)
        session = FakeSession({Position(4, 0): rook})
        controller = make_controller(session)

        controller.on_click(50, 450)  # select rook at (4,0)
        controller.on_click(50, 450)  # click the same cell again

        assert session.request_move_calls == [(Position(4, 0), Position(4, 0))]
        assert controller.selected is None


class TestControllerMoveAttempts:
    def test_legal_move_calls_request_move_and_clears_selection(self):
        rook = piece_view(1, "wR", row=4, col=0)
        session = FakeSession({Position(4, 0): rook})
        controller = make_controller(session)

        controller.on_click(50, 450)   # select rook at (4,0)
        controller.on_click(750, 450)  # attempt move to (4,7)

        assert session.request_move_calls == [(Position(4, 0), Position(4, 7))]
        assert controller.selected is None

    def test_illegal_move_still_calls_request_move_and_clears_selection(self):
        rook = piece_view(1, "wR", row=4, col=0)
        session = FakeSession({Position(4, 0): rook}, next_result=MoveResult.rejected("illegal_piece_move"))
        controller = make_controller(session)

        controller.on_click(50, 450)   # select rook at (4,0)
        controller.on_click(150, 350)  # diagonal - illegal for rook

        assert session.request_move_calls == [(Position(4, 0), Position(3, 1))]
        assert controller.selected is None


class TestPassthroughs:
    def test_is_game_over_delegates_to_session(self):
        session = FakeSession()
        controller = make_controller(session)

        assert controller.is_game_over is False

    def test_clock_ms_delegates_to_session(self):
        session = FakeSession()
        controller = make_controller(session)

        controller.advance(500)

        assert controller.clock_ms == 500

    def test_piece_at_delegates_to_session(self):
        rook = piece_view(1, "wR", row=4, col=0)
        session = FakeSession({Position(4, 0): rook})
        controller = make_controller(session)

        assert controller.piece_at(Position(4, 0)) is rook
        assert controller.piece_at(Position(0, 0)) is None

    def test_board_snapshot_delegates_to_session(self):
        rook = piece_view(1, "wR", row=4, col=0)
        session = FakeSession({Position(4, 0): rook})
        controller = make_controller(session)

        assert controller.board_snapshot().pieces() == [rook]

    def test_motion_for_delegates_to_session(self):
        motion = MotionInfo(from_pos=Position(4, 0), to_pos=Position(4, 3), start_ms=0, duration_ms=3000, is_jump=False)
        session = FakeSession()
        session.set_motion(1, motion)
        controller = make_controller(session)

        assert controller.motion_for(1) is motion
        assert controller.motion_for(2) is None

    def test_move_log_delegates_to_session(self):
        rook = piece_view(1, "wR", row=4, col=0)
        session = FakeSession({Position(4, 0): rook})
        controller = make_controller(session)

        controller.on_click(50, 450)   # select rook at (4,0)
        controller.on_click(750, 450)  # move to (4,7)

        assert controller.move_log() == [(Position(4, 0), Position(4, 7))]

    def test_scoreboard_delegates_to_session(self):
        board = Scoreboard(white=7, black=3)
        session = FakeSession(scoreboard=board)
        controller = make_controller(session)

        assert controller.scoreboard() is board
