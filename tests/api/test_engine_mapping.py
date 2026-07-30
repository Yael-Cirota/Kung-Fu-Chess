from dataclasses import dataclass

from kfchess.api import engine_mapping
from kfchess.api.dto import BoardSnapshot, MotionInfo, MoveLogEntry, PieceView, Scoreboard
from kfchess.api.events import EngineEventKind
from kfchess.engine.move_log import MoveRecord
from kfchess.model.piece import Piece, PieceKind
from kfchess.model.position import Position
from kfchess.realtime.motion import MoveOutcome, MoveOutcomeStatus


def make_piece(color='w', kind=PieceKind.ROOK, cell=Position(0, 0)):
    return Piece(color, kind, cell)


@dataclass
class FakeMotion:
    origin: Position
    target: Position
    started_at_ms: int
    total_duration_ms: int
    is_jump: bool


class TestPieceToView:
    def test_maps_piece_fields_onto_view(self):
        piece = make_piece(color='b', kind=PieceKind.KING, cell=Position(2, 3))
        view = engine_mapping.piece_to_view(piece)

        assert isinstance(view, PieceView)
        assert view.piece_id == piece.piece_id
        assert view.symbol == 'bK'
        assert view.color == 'b'
        assert view.cell == Position(2, 3)


class TestMotionToInfo:
    def test_renames_engine_fields_onto_info(self):
        motion = FakeMotion(
            origin=Position(0, 0),
            target=Position(0, 4),
            started_at_ms=100,
            total_duration_ms=2000,
            is_jump=True,
        )
        info = engine_mapping.motion_to_info(motion)

        assert isinstance(info, MotionInfo)
        assert info.from_pos == Position(0, 0)
        assert info.to_pos == Position(0, 4)
        assert info.start_ms == 100
        assert info.duration_ms == 2000
        assert info.is_jump is True


class TestMoveRecordToEntry:
    def test_maps_record_fields_onto_entry(self):
        record = MoveRecord(color='b', symbol='bN', from_pos=Position(0, 1), to_pos=Position(2, 2))
        entry = engine_mapping.move_record_to_entry(record)

        assert isinstance(entry, MoveLogEntry)
        assert entry.color == 'b'
        assert entry.symbol == 'bN'
        assert entry.from_pos == Position(0, 1)
        assert entry.to_pos == Position(2, 2)


class TestScoreboardFromScores:
    def test_maps_color_keyed_scores_onto_white_and_black_fields(self):
        board = engine_mapping.scoreboard_from_scores({"w": 7, "b": 3})

        assert isinstance(board, Scoreboard)
        assert board.white == 7
        assert board.black == 3

    def test_missing_colors_default_to_zero(self):
        board = engine_mapping.scoreboard_from_scores({})
        assert (board.white, board.black) == (0, 0)


class TestSnapshotFromGrid:
    def test_reports_dimensions_and_only_occupied_cells(self):
        grid = [
            [make_piece(), None],
            [None, make_piece(color='b', kind=PieceKind.PAWN, cell=Position(1, 1))],
        ]
        snapshot = engine_mapping.snapshot_from_grid(grid)

        assert isinstance(snapshot, BoardSnapshot)
        assert (snapshot.rows, snapshot.cols) == (2, 2)
        assert len(snapshot.pieces()) == 2

    def test_empty_grid_reports_zero_cols(self):
        snapshot = engine_mapping.snapshot_from_grid([])
        assert (snapshot.rows, snapshot.cols) == (0, 0)
        assert snapshot.pieces() == []


class TestFindPieceById:
    def test_returns_matching_piece(self):
        target = make_piece()
        grid = [[None, target], [None, None]]
        assert engine_mapping.find_piece_by_id(grid, target.piece_id) is target

    def test_returns_none_when_not_found(self):
        grid = [[make_piece(), None], [None, None]]
        assert engine_mapping.find_piece_by_id(grid, 999_999) is None


class TestOutcomeToEvent:
    def test_executed_without_capture_maps_to_move_executed(self):
        piece = make_piece(color='w', kind=PieceKind.ROOK)
        outcome = MoveOutcome(MoveOutcomeStatus.EXECUTED, piece, Position(0, 0), Position(0, 3))

        event = engine_mapping.outcome_to_event(outcome, at_ms=1000)

        assert event.kind is EngineEventKind.MOVE_EXECUTED
        assert event.at_ms == 1000
        assert event.piece.piece_id == piece.piece_id
        assert event.from_pos == Position(0, 0)
        assert event.to_pos == Position(0, 3)
        assert event.captured is None
        assert event.beneficiary_color is None

    def test_executed_with_capture_credits_the_moving_piece_color(self):
        attacker = make_piece(color='w', kind=PieceKind.ROOK)
        captured_piece = make_piece(color='b', kind=PieceKind.PAWN, cell=Position(0, 3))
        outcome = MoveOutcome(
            MoveOutcomeStatus.EXECUTED, attacker, Position(0, 0), Position(0, 3),
            captured_piece=captured_piece,
        )

        event = engine_mapping.outcome_to_event(outcome, at_ms=2000)

        assert event.kind is EngineEventKind.PIECE_CAPTURED
        assert event.captured.piece_id == captured_piece.piece_id
        assert event.beneficiary_color == 'w'

    def test_captured_on_arrival_credits_the_opposing_color(self):
        # The outcome's own piece is the loser here, so the beneficiary is
        # the opposite color - mirroring GameEngine._scoring_capture.
        loser = make_piece(color='b', kind=PieceKind.BISHOP)
        outcome = MoveOutcome(MoveOutcomeStatus.CAPTURED_ON_ARRIVAL, loser, Position(4, 3), Position(4, 4))

        event = engine_mapping.outcome_to_event(outcome, at_ms=3000)

        assert event.kind is EngineEventKind.PIECE_CAPTURED
        assert event.captured.piece_id == loser.piece_id
        assert event.beneficiary_color == 'w'

    def test_stopped_by_friendly_maps_to_move_stopped(self):
        piece = make_piece(color='w', kind=PieceKind.KING)
        outcome = MoveOutcome(MoveOutcomeStatus.STOPPED_BY_FRIENDLY, piece, Position(0, 0), Position(0, 0))

        event = engine_mapping.outcome_to_event(outcome, at_ms=4000)

        assert event.kind is EngineEventKind.MOVE_STOPPED
        assert event.captured is None
        assert event.beneficiary_color is None

    def test_aborted_premove_maps_to_move_aborted(self):
        piece = make_piece(color='w', kind=PieceKind.QUEEN)
        outcome = MoveOutcome(MoveOutcomeStatus.ABORTED_PREMOVE, piece, Position(1, 1), Position(1, 4))

        event = engine_mapping.outcome_to_event(outcome, at_ms=5000)

        assert event.kind is EngineEventKind.MOVE_ABORTED
        assert event.captured is None
        assert event.beneficiary_color is None
