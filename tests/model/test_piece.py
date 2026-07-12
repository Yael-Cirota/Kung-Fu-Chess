import pytest
from kfchess.model.piece import PieceKind, DEFAULT_MOVE_DELAY_MS
from kfchess.model.piece import Piece


@pytest.mark.parametrize("kind,letter", [
    (PieceKind.KING, 'K'), (PieceKind.QUEEN, 'Q'), (PieceKind.ROOK, 'R'),
    (PieceKind.BISHOP, 'B'), (PieceKind.KNIGHT, 'N'), (PieceKind.PAWN, 'P'),
])
class TestPieceData:
    def test_initial_state(self, kind, letter):
        piece = Piece('w', kind)
        assert piece.color == 'w'
        assert piece.has_moved is False
        assert piece.move_delay_ms == DEFAULT_MOVE_DELAY_MS
