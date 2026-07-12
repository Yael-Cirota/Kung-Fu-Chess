import pytest
from kfchess.model.position import Position
from kfchess.model.board import Board


def make_grid(rows=8, cols=8):
    return [[None] * cols for _ in range(rows)]


class TestBoardDimensions:
    def test_rows_and_cols_from_grid(self):
        board = Board(make_grid(4, 6))
        assert board.rows == 4
        assert board.cols == 6

    def test_empty_grid_has_zero_cols(self):
        board = Board([])
        assert board.rows == 0
        assert board.cols == 0


class TestBoardBounds:
    def test_within_bounds_true_at_corners(self):
        board = Board(make_grid(8, 8))
        assert board.is_within_bounds(Position(0, 0)) is True
        assert board.is_within_bounds(Position(7, 7)) is True

    def test_out_of_bounds_false(self):
        board = Board(make_grid(8, 8))
        assert board.is_within_bounds(Position(8, 0)) is False
        assert board.is_within_bounds(Position(0, 8)) is False
        assert board.is_within_bounds(Position(-1, 0)) is False
        assert board.is_within_bounds(Position(0, -1)) is False


class TestBoardCellAccess:
    def test_get_returns_none_for_empty_cell(self):
        board = Board(make_grid())
        assert board.get(Position(3, 3)) is None

    def test_set_then_get_returns_the_piece(self):
        piece = object()
        board = Board(make_grid())
        board.set(Position(2, 4), piece)
        assert board.get(Position(2, 4)) is piece

    def test_set_only_mutates_targeted_cell(self):
        piece = object()
        board = Board(make_grid())
        board.set(Position(2, 4), piece)
        assert board.get(Position(2, 5)) is None
        assert board.get(Position(3, 4)) is None

    def test_set_on_occupied_cell_overwrites_it(self):
        first_piece = object()
        second_piece = object()
        board = Board(make_grid())
        board.set(Position(2, 4), first_piece)

        board.set(Position(2, 4), second_piece)

        assert board.get(Position(2, 4)) is second_piece

    def test_remove_clears_cell_and_returns_previous_occupant(self):
        piece = object()
        board = Board(make_grid())
        board.set(Position(1, 1), piece)

        removed = board.move_piece(Position(1, 1))

        assert removed is piece
        assert board.get(Position(1, 1)) is None

    def test_move_piece_on_empty_cell_returns_none(self):
        board = Board(make_grid())
        assert board.move_piece(Position(0, 0)) is None


class TestBoardFromGrid:
    def test_from_grid_round_trips(self):
        piece = object()
        grid = make_grid(3, 3)
        grid[1][2] = piece

        board = Board.from_grid(grid)

        assert board.get(Position(1, 2)) is piece
        assert board.rows == 3
        assert board.cols == 3


class TestBoardAsGrid:
    def test_as_grid_reflects_current_state(self):
        piece = object()
        board = Board(make_grid(2, 2))
        board.set(Position(0, 1), piece)

        grid = board.as_grid()

        assert grid[0][1] is piece
        assert grid[1][0] is None
