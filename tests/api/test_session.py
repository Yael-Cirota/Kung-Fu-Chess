from kfchess.api import (
    BoardSnapshot,
    GameSession,
    MotionInfo,
    MoveLogEntry,
    PieceView,
    Position,
    Scoreboard,
    create_game_session,
)


def make_session(text='wR . .\n. . .\nbK . .'):
    return create_game_session(text)


class TestFactoryContract:
    def test_created_session_satisfies_protocol(self):
        assert isinstance(make_session(), GameSession)


class TestClockAndGameOver:
    def test_clock_starts_at_zero(self):
        assert make_session().clock_ms == 0

    def test_clock_advances_with_wait(self):
        session = make_session()
        session.wait(500)
        assert session.clock_ms == 500

    def test_game_over_is_false_at_start(self):
        assert make_session().game_over is False


class TestWinner:
    def test_winner_is_none_before_the_game_ends(self):
        assert make_session().winner is None

    def test_winner_is_set_once_the_king_is_captured(self):
        session = make_session()
        session.request_move(Position(0, 0), Position(2, 0))  # rook captures the king
        session.wait(5000)

        assert session.game_over is True
        assert session.winner == "w"


class TestBounds:
    def test_in_bounds_position(self):
        assert make_session().is_within_bounds(Position(1, 1)) is True

    def test_out_of_bounds_position(self):
        assert make_session().is_within_bounds(Position(9, 9)) is False


class TestPieceAt:
    def test_occupied_cell_returns_piece_view(self):
        view = make_session().piece_at(Position(0, 0))
        assert isinstance(view, PieceView)
        assert view.symbol == 'wR'
        assert view.color == 'w'
        assert view.cell == Position(0, 0)

    def test_empty_cell_returns_none(self):
        assert make_session().piece_at(Position(1, 1)) is None


class TestBoardSnapshot:
    def test_snapshot_reports_dimensions_and_pieces(self):
        snapshot = make_session().board_snapshot()
        assert isinstance(snapshot, BoardSnapshot)
        assert (snapshot.rows, snapshot.cols) == (3, 3)
        assert len(snapshot.pieces()) == 2


class TestRequestMove:
    def test_accepted_move_reports_ok(self):
        session = make_session()
        result = session.request_move(Position(0, 0), Position(0, 2))
        assert result.is_accepted is True

    def test_rejected_move_is_not_accepted(self):
        session = make_session()
        # Rook cannot move diagonally.
        result = session.request_move(Position(0, 0), Position(1, 1))
        assert result.is_accepted is False


class TestIsMoving:
    def test_stationary_piece_is_not_moving(self):
        session = make_session()
        piece_id = session.piece_at(Position(0, 0)).piece_id
        assert session.is_moving(piece_id) is False

    def test_piece_is_moving_after_accepted_move(self):
        session = make_session()
        piece_id = session.piece_at(Position(0, 0)).piece_id
        session.request_move(Position(0, 0), Position(0, 2))
        assert session.is_moving(piece_id) is True

    def test_unknown_piece_id_is_not_moving(self):
        assert make_session().is_moving(9999) is False


class TestMotionFor:
    def test_stationary_piece_has_no_motion(self):
        session = make_session()
        piece_id = session.piece_at(Position(0, 0)).piece_id
        assert session.motion_for(piece_id) is None

    def test_moving_piece_reports_motion_info(self):
        session = make_session()
        piece_id = session.piece_at(Position(0, 0)).piece_id
        session.request_move(Position(0, 0), Position(0, 2))

        motion = session.motion_for(piece_id)
        assert isinstance(motion, MotionInfo)
        assert motion.from_pos == Position(0, 0)
        assert motion.to_pos == Position(0, 2)
        assert motion.is_jump is False

    def test_unknown_piece_id_has_no_motion(self):
        assert make_session().motion_for(9999) is None


class TestMoveLog:
    def test_empty_before_any_move(self):
        assert make_session().move_log() == []

    def test_accepted_move_is_logged_as_an_entry(self):
        session = make_session()
        session.request_move(Position(0, 0), Position(0, 2))

        log = session.move_log()
        assert len(log) == 1
        entry = log[0]
        assert isinstance(entry, MoveLogEntry)
        assert entry.color == 'w'
        assert entry.symbol == 'wR'
        assert entry.from_pos == Position(0, 0)
        assert entry.to_pos == Position(0, 2)

    def test_rejected_move_is_not_logged(self):
        session = make_session()
        session.request_move(Position(0, 0), Position(1, 1))  # illegal rook diagonal
        assert session.move_log() == []


class TestScoreboard:
    def test_scoreboard_starts_at_zero(self):
        board = make_session().scoreboard()
        assert isinstance(board, Scoreboard)
        assert (board.white, board.black) == (0, 0)

    def test_capture_is_reflected_in_the_scoreboard(self):
        # wR at (0,0) captures the bK at (2,0) by sliding down file a.
        session = make_session()
        session.request_move(Position(0, 0), Position(2, 0))
        session.wait(2000)

        board = session.scoreboard()
        assert board.white == 10  # king value
        assert board.black == 0
