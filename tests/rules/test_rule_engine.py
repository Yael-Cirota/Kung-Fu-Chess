from kfchess.model.piece import Rook, Pawn
from kfchess.model.board import Board
from kfchess.model.position import Position
from kfchess.rules.move_result import MoveRejectionReason
from kfchess.rules.rule_engine import RuleEngine


def empty_grid(rows=8, cols=8):
    return [[None] * cols for _ in range(rows)]


def board_with(*pieces_at):
    grid = empty_grid()
    for (row, col), piece in pieces_at:
        grid[row][col] = piece
    return Board(grid)


class TestRuleEngineValidate:
    def test_destination_out_of_bounds(self):
        rook = Rook('w')
        board = board_with(((0, 0), rook))
        result = RuleEngine.validate(board, Position(0, 0), Position(0, 8))
        assert result.legal is False
        assert result.reason is MoveRejectionReason.OUT_OF_BOUNDS

    def test_origin_out_of_bounds(self):
        board = board_with()
        result = RuleEngine.validate(board, Position(-1, 0), Position(0, 0))
        assert result.legal is False
        assert result.reason is MoveRejectionReason.OUT_OF_BOUNDS

    def test_empty_origin(self):
        board = board_with()
        result = RuleEngine.validate(board, Position(4, 4), Position(4, 5))
        assert result.legal is False
        assert result.reason is MoveRejectionReason.EMPTY_ORIGIN

    def test_same_cell_destination_is_a_legal_jump(self):
        rook = Rook('w')
        board = board_with(((4, 4), rook))
        result = RuleEngine.validate(board, Position(4, 4), Position(4, 4))
        assert result.legal is True
        assert result.reason is None

    def test_illegal_shape(self):
        rook = Rook('w')
        board = board_with(((0, 0), rook))
        result = RuleEngine.validate(board, Position(0, 0), Position(1, 1))
        assert result.legal is False
        assert result.reason is MoveRejectionReason.NOT_A_LEGAL_SHAPE

    def test_blocked_path_reported_as_blocked(self):
        rook = Rook('w')
        blocker = Pawn('b')
        board = board_with(((4, 0), rook), ((4, 3), blocker))
        result = RuleEngine.validate(board, Position(4, 0), Position(4, 7))
        assert result.legal is False
        assert result.reason is MoveRejectionReason.BLOCKED

    def test_blocked_path_for_non_sliding_piece_is_still_not_a_legal_shape(self):
        # Knights jump, so an intervening piece never blocks them - a
        # rejected knight move is always NOT_A_LEGAL_SHAPE, never BLOCKED.
        from kfchess.model.piece import Knight
        knight = Knight('w')
        board = board_with(((4, 4), knight))
        result = RuleEngine.validate(board, Position(4, 4), Position(4, 6))
        assert result.legal is False
        assert result.reason is MoveRejectionReason.NOT_A_LEGAL_SHAPE

    def test_friendly_fire(self):
        rook = Rook('w')
        friend = Pawn('w')
        board = board_with(((0, 0), rook), ((0, 7), friend))
        result = RuleEngine.validate(board, Position(0, 0), Position(0, 7))
        assert result.legal is False
        assert result.reason is MoveRejectionReason.FRIENDLY_FIRE

    def test_legal_move_is_ok(self):
        rook = Rook('w')
        board = board_with(((0, 0), rook))
        result = RuleEngine.validate(board, Position(0, 0), Position(0, 7))
        assert result.legal is True
        assert result.reason is None

    def test_legal_capture_is_ok(self):
        rook = Rook('w')
        enemy = Pawn('b')
        board = board_with(((0, 0), rook), ((0, 7), enemy))
        result = RuleEngine.validate(board, Position(0, 0), Position(0, 7))
        assert result.legal is True
        assert result.reason is None
