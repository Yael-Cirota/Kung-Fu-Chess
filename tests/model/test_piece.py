import pytest
from kfchess.model.piece import Color
from kfchess.model.piece import PieceKind
from kfchess.model.piece import Piece


class TestColor:
    def test_opponent_of_white_is_black(self):
        assert Color.WHITE.opponent() is Color.BLACK

    def test_opponent_of_black_is_white(self):
        assert Color.BLACK.opponent() is Color.WHITE


@pytest.mark.parametrize("kind,letter", [
    (PieceKind.KING, 'K'), (PieceKind.QUEEN, 'Q'), (PieceKind.ROOK, 'R'),
    (PieceKind.BISHOP, 'B'), (PieceKind.KNIGHT, 'N'), (PieceKind.PAWN, 'P'),
])
class TestPieceData:
    def test_initial_state(self, kind, letter):
        piece = Piece('w', kind)
        assert piece.color == 'w'
        assert piece.has_moved is False
