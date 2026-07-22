from kfchess.api import Position

from ui.board_geometry import BoardGeometry


class TestPixelToCell:
    def test_origin_pixel_maps_to_origin_cell(self):
        assert BoardGeometry(100).pixel_to_cell(0, 0) == Position(0, 0)

    def test_maps_x_to_col_and_y_to_row(self):
        assert BoardGeometry(100).pixel_to_cell(350, 250) == Position(2, 3)

    def test_any_pixel_within_a_cell_maps_to_that_cell(self):
        geometry = BoardGeometry(100)
        assert geometry.pixel_to_cell(100, 100) == geometry.pixel_to_cell(199, 199) == Position(1, 1)

    def test_uses_custom_cell_size(self):
        assert BoardGeometry(50).pixel_to_cell(100, 50) == Position(1, 2)


class TestCellToPixel:
    def test_origin_cell_is_at_the_origin_pixel(self):
        assert BoardGeometry(100).cell_to_pixel(Position(0, 0)) == (0, 0)

    def test_returns_the_top_left_corner(self):
        assert BoardGeometry(100).cell_to_pixel(Position(2, 3)) == (300, 200)

    def test_uses_custom_cell_size(self):
        assert BoardGeometry(50).cell_to_pixel(Position(1, 2)) == (100, 50)


class TestCellCenter:
    def test_center_is_offset_by_half_a_cell(self):
        assert BoardGeometry(100).cell_center(Position(0, 0)) == (50, 50)

    def test_center_of_an_inner_cell(self):
        assert BoardGeometry(100).cell_center(Position(2, 3)) == (350, 250)


class TestRoundTrip:
    def test_a_cell_center_maps_back_to_its_own_cell(self):
        geometry = BoardGeometry(100)
        for pos in (Position(0, 0), Position(3, 5), Position(7, 7)):
            assert geometry.pixel_to_cell(*geometry.cell_center(pos)) == pos
