import pytest
from kfchess.model.piece import PieceKind
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
