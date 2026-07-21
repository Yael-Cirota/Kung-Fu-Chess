from kfchess.api import GameSession, Position, create_game_session
from kfchess.api.engine_config import EngineConfig
from kfchess.model.piece import PieceKind


class TestNoConfigMatchesHardCodedDefaults:
    def test_created_session_satisfies_the_protocol(self):
        session = create_game_session('wR . .\n. . .\n. . .')
        assert isinstance(session, GameSession)

    def test_default_move_takes_one_second_per_cell(self):
        session = create_game_session('wR . .\n. . .\n. . .')
        session.request_move(Position(0, 0), Position(0, 2))
        session.wait(1999)
        assert session.piece_at(Position(0, 1)) is not None
        session.wait(1)
        assert session.piece_at(Position(0, 2)) is not None


class TestConfigThreadsMovementTiming:
    def test_custom_move_duration_per_cell_changes_arrival_time(self):
        config = EngineConfig(move_duration_ms_per_cell=100)
        session = create_game_session('wR . .\n. . .\n. . .', config=config)

        session.request_move(Position(0, 0), Position(0, 2))
        session.wait(200)

        assert session.piece_at(Position(0, 2)) is not None
        assert session.piece_at(Position(0, 0)) is None

    def test_custom_jump_duration_changes_a_same_square_jump(self):
        config = EngineConfig(jump_duration_ms=50)
        session = create_game_session('wK . .\n. . .\n. . .', config=config)

        session.request_move(Position(0, 0), Position(0, 0))
        session.wait(49)
        # Still mid-flight: the piece has not landed and cooldown hasn't started.
        rejected = session.request_move(Position(0, 0), Position(0, 1))
        assert rejected.is_accepted is False

        session.wait(1)  # jump lands


class TestConfigThreadsCooldown:
    def test_custom_move_cooldown_blocks_an_immediate_second_move(self):
        config = EngineConfig(move_duration_ms_per_cell=10, move_cooldown_ms=5000)
        session = create_game_session('wR . .\n. . .\n. . .', config=config)

        session.request_move(Position(0, 0), Position(0, 1))
        session.wait(10)  # move lands, cooldown starts

        rejected = session.request_move(Position(0, 1), Position(0, 2))
        assert rejected.is_accepted is False


class TestConfigThreadsScoring:
    def test_custom_point_values_are_used_for_captures(self):
        config = EngineConfig(point_values={
            PieceKind.PAWN: 500, PieceKind.KNIGHT: 3, PieceKind.BISHOP: 3,
            PieceKind.ROOK: 5, PieceKind.QUEEN: 9, PieceKind.KING: 10,
        })
        session = create_game_session('wR . bP\n. . .\n. . .', config=config)

        session.request_move(Position(0, 0), Position(0, 2))
        session.wait(2000)

        assert session.scoreboard().white == 500
