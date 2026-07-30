from kfchess.api.dto import MotionInfo, MoveLogEntry, PieceView, Position, Scoreboard
from protocol import messages as m
from client.session.snapshot_store import SnapshotStore


class TestDefaults:
    def test_starts_with_no_pieces_and_not_game_over(self):
        store = SnapshotStore()
        assert store.board_snapshot().pieces() == []
        assert store.game_over is False
        assert store.winner is None


class TestGameStarted:
    def test_sets_board_dimensions(self):
        store = SnapshotStore()
        store.apply_game_started(m.GameStarted(server_ms=0, rows=8, cols=8))

        snapshot = store.board_snapshot()
        assert snapshot.rows == 8
        assert snapshot.cols == 8

    def test_bounds_check_uses_the_dimensions(self):
        store = SnapshotStore()
        store.apply_game_started(m.GameStarted(server_ms=0, rows=8, cols=8))

        assert store.is_within_bounds(Position(0, 0)) is True
        assert store.is_within_bounds(Position(7, 7)) is True
        assert store.is_within_bounds(Position(8, 0)) is False
        assert store.is_within_bounds(Position(-1, 0)) is False


class TestStateUpdate:
    def make_update(self, **overrides):
        defaults = dict(
            server_ms=1234,
            seq=1,
            pieces=[PieceView(piece_id=1, symbol="wR", color="w", cell=Position(0, 0))],
            motions=[],
            move_log=[],
            scoreboard=Scoreboard(white=0, black=0),
            game_over=False,
        )
        defaults.update(overrides)
        return m.StateUpdate(**defaults)

    def test_updates_server_ms(self):
        store = SnapshotStore()
        store.apply_state_update(self.make_update(server_ms=999))
        assert store.server_ms == 999

    def test_piece_at_finds_a_piece_by_cell(self):
        store = SnapshotStore()
        store.apply_state_update(self.make_update())

        piece = store.piece_at(Position(0, 0))
        assert piece.symbol == "wR"
        assert store.piece_at(Position(5, 5)) is None

    def test_motion_for_looks_up_by_piece_id(self):
        motion = MotionInfo(from_pos=Position(0, 0), to_pos=Position(0, 3), start_ms=0, duration_ms=3000, is_jump=False)
        store = SnapshotStore()
        store.apply_state_update(self.make_update(motions=[m.MotionEntry(piece_id=1, motion=motion)]))

        assert store.motion_for(1) == motion
        assert store.motion_for(999) is None

    def test_move_log_and_scoreboard_are_carried_through(self):
        entry = MoveLogEntry(color="w", symbol="wR", from_pos=Position(0, 0), to_pos=Position(0, 3))
        store = SnapshotStore()
        store.apply_state_update(self.make_update(move_log=[entry], scoreboard=Scoreboard(white=5, black=3)))

        assert store.move_log() == [entry]
        assert store.scoreboard() == Scoreboard(white=5, black=3)

    def test_game_over_flag_is_carried_through(self):
        store = SnapshotStore()
        store.apply_state_update(self.make_update(game_over=True))
        assert store.game_over is True


class TestGameEnded:
    def test_sets_game_over_and_winner(self):
        store = SnapshotStore()
        store.apply_game_ended(m.GameEnded(winner="black", reason="king_captured", elo_delta=16))

        assert store.game_over is True
        assert store.winner == "black"
