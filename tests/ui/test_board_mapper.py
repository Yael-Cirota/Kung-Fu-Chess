from kfchess.model.position import Position
from kfchess.ui.board_mapper import BoardMapper


class TestBoardMapper:
    def test_default_cell_size_is_100(self):
        mapper = BoardMapper()
        assert mapper.pixel_to_position(350, 250) == Position(2, 3)

    def test_maps_origin_to_position_zero_zero(self):
        mapper = BoardMapper()
        assert mapper.pixel_to_position(0, 0) == Position(0, 0)

    def test_boundary_pixel_rounds_down_into_next_cell(self):
        mapper = BoardMapper()
        assert mapper.pixel_to_position(99, 99) == Position(0, 0)
        assert mapper.pixel_to_position(100, 100) == Position(1, 1)

    def test_custom_cell_size(self):
        mapper = BoardMapper(cell_size_px=50)
        assert mapper.pixel_to_position(120, 60) == Position(1, 2)
