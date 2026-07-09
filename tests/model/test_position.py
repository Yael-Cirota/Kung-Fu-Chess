import pytest
from dataclasses import FrozenInstanceError
from kfchess.model.position import Position


class TestPosition:
    def test_stores_row_and_col(self):
        pos = Position(2, 3)
        assert pos.row == 2
        assert pos.col == 3

    def test_equality(self):
        assert Position(1, 2) == Position(1, 2)
        assert Position(1, 2) != Position(2, 1)

    def test_hashable_usable_as_set_or_dict_key(self):
        s = {Position(0, 0), Position(0, 0), Position(1, 1)}
        assert len(s) == 2

        d = {Position(4, 5): "piece"}
        assert d[Position(4, 5)] == "piece"

    def test_immutable(self):
        pos = Position(0, 0)
        with pytest.raises(FrozenInstanceError):
            pos.row = 5

    def test_tuple_unpacking(self):
        row, col = Position(3, 4)
        assert (row, col) == (3, 4)

    def test_repr_contains_row_and_col(self):
        assert "3" in repr(Position(3, 4))
        assert "4" in repr(Position(3, 4))
