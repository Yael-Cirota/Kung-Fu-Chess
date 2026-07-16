from dataclasses import dataclass

from kfchess.api import engine_mapping
from kfchess.api.dto import BoardSnapshot, MotionInfo, PieceView
from kfchess.model.piece import Piece, PieceKind
from kfchess.model.position import Position


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
