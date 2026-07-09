import pytest

from kfchess.model.piece import King, Rook, Bishop, Queen, Knight, Pawn
from kfchess.model.board import Board
from kfchess.model.position import Position
from kfchess.rules.movement_rules import MovementRules


def empty_grid(rows=8, cols=8):
    return [[None] * cols for _ in range(rows)]


def board_with(*pieces_at, rows=8, cols=8):
    grid = empty_grid(rows, cols)
    for (row, col), piece in pieces_at:
        grid[row][col] = piece
    return Board(grid)


class TestMovementRulesKing:
    @pytest.mark.parametrize("dr,dc", [
        (0, 1), (0, -1), (1, 0), (-1, 0),
        (1, 1), (1, -1), (-1, 1), (-1, -1),
    ])
    def test_legal_one_step(self, dr, dc):
        king = King('w')
        board = board_with(((4, 4), king))
        assert MovementRules.is_legal_shape(
            board, king, Position(4, 4), Position(4 + dr, 4 + dc)
        ) is True

    def test_illegal_no_move(self):
        king = King('w')
        board = board_with(((4, 4), king))
        assert MovementRules.is_legal_shape(
            board, king, Position(4, 4), Position(4, 4)
        ) is False

    def test_illegal_two_squares(self):
        king = King('w')
        board = board_with(((4, 4), king))
        assert MovementRules.is_legal_shape(
            board, king, Position(4, 4), Position(4, 6)
        ) is False
        assert MovementRules.is_legal_shape(
            board, king, Position(4, 4), Position(6, 6)
        ) is False


class TestMovementRulesRook:
    def test_legal_horizontal(self):
        rook = Rook('w')
        board = board_with(((4, 0), rook))
        assert MovementRules.is_legal_shape(
            board, rook, Position(4, 0), Position(4, 7)
        ) is True

    def test_legal_vertical(self):
        rook = Rook('w')
        board = board_with(((0, 3), rook))
        assert MovementRules.is_legal_shape(
            board, rook, Position(0, 3), Position(7, 3)
        ) is True

    def test_illegal_no_move(self):
        rook = Rook('w')
        board = board_with(((3, 3), rook))
        assert MovementRules.is_legal_shape(
            board, rook, Position(3, 3), Position(3, 3)
        ) is False

    def test_illegal_diagonal(self):
        rook = Rook('w')
        board = board_with(((0, 0), rook))
        assert MovementRules.is_legal_shape(
            board, rook, Position(0, 0), Position(3, 3)
        ) is False

    def test_blocked_path(self):
        rook = Rook('w')
        blocker = Rook('b')
        board = board_with(((4, 0), rook), ((4, 3), blocker))
        assert MovementRules.is_legal_shape(
            board, rook, Position(4, 0), Position(4, 7)
        ) is False

    def test_capture_adjacent(self):
        rook = Rook('w')
        target = Rook('b')
        board = board_with(((4, 0), rook), ((4, 1), target))
        assert MovementRules.is_legal_shape(
            board, rook, Position(4, 0), Position(4, 1)
        ) is True


class TestMovementRulesBishop:
    def test_legal_diagonal(self):
        bishop = Bishop('w')
        board = board_with(((0, 0), bishop))
        assert MovementRules.is_legal_shape(
            board, bishop, Position(0, 0), Position(5, 5)
        ) is True

    def test_illegal_no_move(self):
        bishop = Bishop('w')
        board = board_with(((3, 3), bishop))
        assert MovementRules.is_legal_shape(
            board, bishop, Position(3, 3), Position(3, 3)
        ) is False

    def test_illegal_straight(self):
        bishop = Bishop('w')
        board = board_with(((3, 3), bishop))
        assert MovementRules.is_legal_shape(
            board, bishop, Position(3, 3), Position(3, 6)
        ) is False
        assert MovementRules.is_legal_shape(
            board, bishop, Position(3, 3), Position(6, 3)
        ) is False

    def test_blocked_path(self):
        bishop = Bishop('w')
        blocker = Bishop('b')
        board = board_with(((0, 0), bishop), ((2, 2), blocker))
        assert MovementRules.is_legal_shape(
            board, bishop, Position(0, 0), Position(4, 4)
        ) is False


class TestMovementRulesQueen:
    def test_legal_horizontal(self):
        queen = Queen('w')
        board = board_with(((4, 0), queen))
        assert MovementRules.is_legal_shape(
            board, queen, Position(4, 0), Position(4, 7)
        ) is True

    def test_legal_vertical(self):
        queen = Queen('w')
        board = board_with(((0, 4), queen))
        assert MovementRules.is_legal_shape(
            board, queen, Position(0, 4), Position(7, 4)
        ) is True

    def test_legal_diagonal(self):
        queen = Queen('w')
        board = board_with(((0, 0), queen))
        assert MovementRules.is_legal_shape(
            board, queen, Position(0, 0), Position(5, 5)
        ) is True

    def test_illegal_no_move(self):
        queen = Queen('w')
        board = board_with(((3, 3), queen))
        assert MovementRules.is_legal_shape(
            board, queen, Position(3, 3), Position(3, 3)
        ) is False

    def test_illegal_knight_shape(self):
        queen = Queen('w')
        board = board_with(((3, 3), queen))
        assert MovementRules.is_legal_shape(
            board, queen, Position(3, 3), Position(5, 4)
        ) is False

    def test_blocked_path(self):
        queen = Queen('w')
        blocker = Queen('b')
        board = board_with(((0, 0), queen), ((3, 3), blocker))
        assert MovementRules.is_legal_shape(
            board, queen, Position(0, 0), Position(5, 5)
        ) is False


class TestMovementRulesKnight:
    @pytest.mark.parametrize("dr,dc", [
        (2, 1), (2, -1), (-2, 1), (-2, -1),
        (1, 2), (1, -2), (-1, 2), (-1, -2),
    ])
    def test_all_legal_l_shapes(self, dr, dc):
        knight = Knight('w')
        board = board_with(((4, 4), knight))
        assert MovementRules.is_legal_shape(
            board, knight, Position(4, 4), Position(4 + dr, 4 + dc)
        ) is True

    def test_illegal_no_move(self):
        knight = Knight('w')
        board = board_with(((4, 4), knight))
        assert MovementRules.is_legal_shape(
            board, knight, Position(4, 4), Position(4, 4)
        ) is False

    def test_illegal_straight(self):
        knight = Knight('w')
        board = board_with(((4, 4), knight))
        assert MovementRules.is_legal_shape(
            board, knight, Position(4, 4), Position(4, 6)
        ) is False

    def test_jumps_over_pieces(self):
        knight = Knight('w')
        blocker = Rook('b')
        board = board_with(((4, 4), knight), ((4, 5), blocker), ((5, 4), blocker))
        assert MovementRules.is_legal_shape(
            board, knight, Position(4, 4), Position(6, 5)
        ) is True


class TestMovementRulesPawn:
    def test_white_pawn_forward(self):
        pawn = Pawn('w')
        board = board_with(((4, 3), pawn))
        assert MovementRules.is_legal_shape(
            board, pawn, Position(4, 3), Position(3, 3)
        ) is True

    def test_black_pawn_forward(self):
        pawn = Pawn('b')
        board = board_with(((3, 3), pawn))
        assert MovementRules.is_legal_shape(
            board, pawn, Position(3, 3), Position(4, 3)
        ) is True

    def test_blocked_by_piece(self):
        pawn = Pawn('w')
        blocker = Pawn('b')
        board = board_with(((4, 3), pawn), ((3, 3), blocker))
        assert MovementRules.is_legal_shape(
            board, pawn, Position(4, 3), Position(3, 3)
        ) is False

    def test_diagonal_capture(self):
        pawn = Pawn('w')
        target = Pawn('b')
        board = board_with(((4, 3), pawn), ((3, 4), target))
        assert MovementRules.is_legal_shape(
            board, pawn, Position(4, 3), Position(3, 4)
        ) is True

    def test_cannot_capture_forward(self):
        pawn = Pawn('w')
        target = Pawn('b')
        board = board_with(((4, 3), pawn), ((3, 3), target))
        assert MovementRules.is_legal_shape(
            board, pawn, Position(4, 3), Position(3, 3)
        ) is False

    def test_cannot_capture_friendly(self):
        pawn = Pawn('w')
        friendly = Pawn('w')
        board = board_with(((4, 3), pawn), ((3, 4), friendly))
        assert MovementRules.is_legal_shape(
            board, pawn, Position(4, 3), Position(3, 4)
        ) is False

    def test_no_diagonal_without_capture(self):
        pawn = Pawn('w')
        board = board_with(((4, 3), pawn))
        assert MovementRules.is_legal_shape(
            board, pawn, Position(4, 3), Position(3, 4)
        ) is False

    def test_cannot_move_backward(self):
        pawn = Pawn('w')
        board = board_with(((4, 3), pawn))
        assert MovementRules.is_legal_shape(
            board, pawn, Position(4, 3), Position(5, 3)
        ) is False

    def test_no_double_move(self):
        pawn = Pawn('w')
        board = board_with(((6, 3), pawn))
        assert MovementRules.is_legal_shape(
            board, pawn, Position(6, 3), Position(4, 3)
        ) is False

    def test_no_move(self):
        pawn = Pawn('w')
        board = board_with(((4, 3), pawn))
        assert MovementRules.is_legal_shape(
            board, pawn, Position(4, 3), Position(4, 3)
        ) is False
