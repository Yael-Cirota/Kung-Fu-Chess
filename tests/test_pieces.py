import pytest
from pieces import King, Queen, Rook, Bishop, Knight, Pawn, DEFAULT_MOVE_DELAY_MS


@pytest.mark.parametrize("piece_class,letter", [
    (King, 'K'), (Queen, 'Q'), (Rook, 'R'),
    (Bishop, 'B'), (Knight, 'N'), (Pawn, 'P'),
])
class TestPieceData:
    def test_get_symbol(self, piece_class, letter):
        assert piece_class('w').get_symbol() == f"w{letter}"
        assert piece_class('b').get_symbol() == f"b{letter}"

    def test_initial_state(self, piece_class, letter):
        piece = piece_class('w')
        assert piece.color == 'w'
        assert piece.has_moved is False
        assert piece.move_delay_ms == DEFAULT_MOVE_DELAY_MS
