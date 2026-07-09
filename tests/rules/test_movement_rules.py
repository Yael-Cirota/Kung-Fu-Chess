from pieces import King, Rook, Bishop, Queen, Knight, Pawn
from kfchess.model.board import Board
from kfchess.model.position import Position
from kfchess.rules.movement_rules import MovementRules


def empty_grid(rows=8, cols=8):
    return [[None] * cols for _ in range(rows)]


def board_with(*pieces_at):
    grid = empty_grid()
    for (row, col), piece in pieces_at:
        grid[row][col] = piece
    return Board(grid)


class TestMovementRulesKing:
    def test_one_step_is_legal(self):
        king = King('w')
        board = board_with(((4, 4), king))
        assert MovementRules.is_legal_shape(
            board, king, Position(4, 4), Position(4, 5)
        ) is True

    def test_two_steps_is_illegal(self):
        king = King('w')
        board = board_with(((4, 4), king))
        assert MovementRules.is_legal_shape(
            board, king, Position(4, 4), Position(4, 6)
        ) is False


class TestMovementRulesRook:
    def test_straight_move_is_legal(self):
        rook = Rook('w')
        board = board_with(((0, 0), rook))
        assert MovementRules.is_legal_shape(
            board, rook, Position(0, 0), Position(0, 7)
        ) is True

    def test_diagonal_move_is_illegal(self):
        rook = Rook('w')
        board = board_with(((0, 0), rook))
        assert MovementRules.is_legal_shape(
            board, rook, Position(0, 0), Position(1, 1)
        ) is False

    def test_blocked_path_is_illegal(self):
        rook = Rook('w')
        blocker = Pawn('b')
        board = board_with(((4, 0), rook), ((4, 3), blocker))
        assert MovementRules.is_legal_shape(
            board, rook, Position(4, 0), Position(4, 7)
        ) is False


class TestMovementRulesBishop:
    def test_diagonal_move_is_legal(self):
        bishop = Bishop('w')
        board = board_with(((2, 2), bishop))
        assert MovementRules.is_legal_shape(
            board, bishop, Position(2, 2), Position(5, 5)
        ) is True

    def test_blocked_diagonal_is_illegal(self):
        bishop = Bishop('w')
        blocker = Pawn('b')
        board = board_with(((2, 2), bishop), ((3, 3), blocker))
        assert MovementRules.is_legal_shape(
            board, bishop, Position(2, 2), Position(5, 5)
        ) is False


class TestMovementRulesQueen:
    def test_straight_move_is_legal(self):
        queen = Queen('w')
        board = board_with(((0, 0), queen))
        assert MovementRules.is_legal_shape(
            board, queen, Position(0, 0), Position(0, 5)
        ) is True

    def test_knight_shaped_move_is_illegal(self):
        queen = Queen('w')
        board = board_with(((0, 0), queen))
        assert MovementRules.is_legal_shape(
            board, queen, Position(0, 0), Position(2, 1)
        ) is False


class TestMovementRulesKnight:
    def test_l_shape_is_legal(self):
        knight = Knight('w')
        board = board_with(((4, 4), knight))
        assert MovementRules.is_legal_shape(
            board, knight, Position(4, 4), Position(2, 3)
        ) is True

    def test_jumps_over_blocking_pieces(self):
        knight = Knight('w')
        blocker = Pawn('w')
        board = board_with(((4, 4), knight), ((3, 4), blocker))
        assert MovementRules.is_legal_shape(
            board, knight, Position(4, 4), Position(2, 3)
        ) is True


class TestMovementRulesPawn:
    def test_forward_move_into_empty_cell_is_legal(self):
        pawn = Pawn('w')
        board = board_with(((6, 0), pawn))
        assert MovementRules.is_legal_shape(
            board, pawn, Position(6, 0), Position(5, 0)
        ) is True

    def test_diagonal_move_without_capture_is_illegal(self):
        pawn = Pawn('w')
        board = board_with(((6, 0), pawn))
        assert MovementRules.is_legal_shape(
            board, pawn, Position(6, 0), Position(5, 1)
        ) is False

    def test_diagonal_capture_is_legal(self):
        pawn = Pawn('w')
        enemy = Rook('b')
        board = board_with(((6, 0), pawn), ((5, 1), enemy))
        assert MovementRules.is_legal_shape(
            board, pawn, Position(6, 0), Position(5, 1)
        ) is True
