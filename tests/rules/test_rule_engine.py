from kfchess.model.piece import Piece, PieceKind
from kfchess.model.board import Board
from kfchess.model.position import Position
from kfchess.rules.move_validation import MoveRejectionReason
from kfchess.rules.rule_engine import RuleEngine


def empty_grid(rows=8, cols=8):
    return [[None] * cols for _ in range(rows)]


def board_with(*pieces_at):
    grid = empty_grid()
    for (row, col), piece in pieces_at:
        grid[row][col] = piece
    return Board(grid)


class TestRuleEngineValidate:
    def setup_method(self):
        self.engine = RuleEngine()

    def test_destination_out_of_bounds(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((0, 0), rook))
        result = self.engine.validate(board, Position(0, 0), Position(0, 8))
        assert result.is_valid is False
        assert result.reason == MoveRejectionReason.OUTSIDE_BOARD

    def test_origin_out_of_bounds(self):
        board = board_with()
        result = self.engine.validate(board, Position(-1, 0), Position(0, 0))
        assert result.is_valid is False
        assert result.reason == MoveRejectionReason.OUTSIDE_BOARD

    def test_empty_source(self):
        board = board_with()
        result = self.engine.validate(board, Position(4, 4), Position(4, 5))
        assert result.is_valid is False
        assert result.reason == MoveRejectionReason.EMPTY_SOURCE

    def test_same_cell_destination_is_a_legal_jump(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((4, 4), rook))
        result = self.engine.validate(board, Position(4, 4), Position(4, 4))
        assert result.is_valid is True
        assert result.reason == "ok"

    def test_illegal_piece_move(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((0, 0), rook))
        result = self.engine.validate(board, Position(0, 0), Position(1, 1))
        assert result.is_valid is False
        assert result.reason == MoveRejectionReason.ILLEGAL_PIECE_MOVE

    def test_blocked_path_is_reported_as_illegal_piece_move(self):
        rook = Piece('w', PieceKind.ROOK)
        blocker = Piece('b', PieceKind.PAWN)
        board = board_with(((4, 0), rook), ((4, 3), blocker))
        result = self.engine.validate(board, Position(4, 0), Position(4, 7))
        assert result.is_valid is False
        assert result.reason == MoveRejectionReason.ILLEGAL_PIECE_MOVE

    def test_friendly_destination(self):
        rook = Piece('w', PieceKind.ROOK)
        friend = Piece('w', PieceKind.PAWN)
        board = board_with(((0, 0), rook), ((0, 7), friend))
        result = self.engine.validate(board, Position(0, 0), Position(0, 7))
        assert result.is_valid is False
        assert result.reason == MoveRejectionReason.FRIENDLY_DESTINATION

    def test_legal_move_is_ok(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((0, 0), rook))
        result = self.engine.validate(board, Position(0, 0), Position(0, 7))
        assert result.is_valid is True
        assert result.reason == "ok"

    def test_legal_capture_is_ok(self):
        rook = Piece('w', PieceKind.ROOK)
        enemy = Piece('b', PieceKind.PAWN)
        board = board_with(((0, 0), rook), ((0, 7), enemy))
        result = self.engine.validate(board, Position(0, 0), Position(0, 7))
        assert result.is_valid is True
        assert result.reason == "ok"


class TestRuleEnginePromotionKind:
    def setup_method(self):
        self.engine = RuleEngine()

    def test_white_pawn_reaching_row_zero_promotes_to_queen(self):
        pawn = Piece('w', PieceKind.PAWN)
        board = board_with(((1, 0), pawn))
        assert self.engine.promotion_kind(board, pawn, Position(0, 0)) is PieceKind.QUEEN

    def test_black_pawn_reaching_last_row_promotes_to_queen(self):
        pawn = Piece('b', PieceKind.PAWN)
        board = board_with(((6, 0), pawn))
        assert self.engine.promotion_kind(board, pawn, Position(7, 0)) is PieceKind.QUEEN

    def test_pawn_not_on_last_row_does_not_promote(self):
        pawn = Piece('w', PieceKind.PAWN)
        board = board_with(((4, 0), pawn))
        assert self.engine.promotion_kind(board, pawn, Position(3, 0)) is None

    def test_non_pawn_never_promotes(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((1, 0), rook))
        assert self.engine.promotion_kind(board, rook, Position(0, 0)) is None
