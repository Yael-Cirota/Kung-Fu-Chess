from kfchess.model.piece import Piece, PieceKind
from kfchess.model.board import Board
from kfchess.model.position import Position
from kfchess.rules.move_validation import MoveRejectionReason, MoveValidation
from kfchess.input.board_mapper import BoardMapper
from kfchess.input.controller import Controller


def empty_grid(rows=8, cols=8):
    return [[None] * cols for _ in range(rows)]


def board_with(*pieces_at):
    grid = empty_grid()
    for (row, col), piece in pieces_at:
        grid[row][col] = piece
    return Board(grid)


class FakeGameEngine:
    """Minimal stand-in for kfchess.engine.GameEngine to keep Controller tests unit-level."""

    def __init__(self, board, next_result=None):
        self._board = board
        self._next_result = next_result if next_result is not None else MoveValidation.ok()
        self.request_move_calls = []

    def is_within_bounds(self, pos):
        return self._board.is_within_bounds(pos)

    def piece_at(self, pos):
        return self._board.get(pos)

    def request_move(self, from_pos, to_pos):
        self.request_move_calls.append((from_pos, to_pos))
        return self._next_result


def make_controller(engine):
    return Controller(engine, BoardMapper())


class TestControllerSelection:
    def test_click_empty_cell_with_no_selection_is_noop(self):
        engine = FakeGameEngine(board_with())
        controller = make_controller(engine)

        controller.on_click(50, 50)

        assert controller.selected is None

    def test_click_piece_selects_it(self):
        king = Piece('w', PieceKind.KING)
        engine = FakeGameEngine(board_with(((2, 3), king)))
        controller = make_controller(engine)

        controller.on_click(350, 250)  # col=3, row=2

        assert controller.selected == Position(2, 3)

    def test_click_outside_board_is_ignored(self):
        king = Piece('w', PieceKind.KING)
        engine = FakeGameEngine(board_with(((0, 0), king)))
        controller = make_controller(engine)

        controller.on_click(900, 900)

        assert controller.selected is None

    def test_click_friendly_piece_on_second_click_still_requests_move(self):
        king = Piece('w', PieceKind.KING)
        rook = Piece('w', PieceKind.ROOK)
        engine = FakeGameEngine(board_with(((0, 0), king), ((0, 1), rook)))
        controller = make_controller(engine)

        controller.on_click(50, 50)   # select king at (0,0)
        controller.on_click(150, 50)  # click rook at (0,1)

        assert engine.request_move_calls == [(Position(0, 0), Position(0, 1))]
        assert controller.selected is None

    def test_off_board_click_with_selection_cancels_it_without_a_command(self):
        rook = Piece('w', PieceKind.ROOK)
        engine = FakeGameEngine(board_with(((0, 0), rook)))
        controller = make_controller(engine)

        controller.on_click(50, 50)    # select rook at (0,0)
        controller.on_click(900, 900)  # off-board click cancels selection

        assert controller.selected is None
        assert engine.request_move_calls == []


class TestControllerJump:
    def test_clicking_the_selected_piece_again_requests_a_jump(self):
        rook = Piece('w', PieceKind.ROOK)
        engine = FakeGameEngine(board_with(((4, 0), rook)))
        controller = make_controller(engine)

        controller.on_click(50, 450)  # select rook at (4,0)
        controller.on_click(50, 450)  # click the same cell again

        assert engine.request_move_calls == [(Position(4, 0), Position(4, 0))]
        assert controller.selected is None


class TestControllerMoveAttempts:
    def test_legal_move_calls_request_move_and_clears_selection(self):
        rook = Piece('w', PieceKind.ROOK)
        engine = FakeGameEngine(board_with(((4, 0), rook)))
        controller = make_controller(engine)

        controller.on_click(50, 450)   # select rook at (4,0)
        controller.on_click(750, 450)  # attempt move to (4,7)

        assert engine.request_move_calls == [(Position(4, 0), Position(4, 7))]
        assert controller.selected is None

    def test_illegal_move_still_calls_request_move_and_clears_selection(self):
        rook = Piece('w', PieceKind.ROOK)
        engine = FakeGameEngine(
            board_with(((4, 0), rook)),
            next_result=MoveValidation.invalid(MoveRejectionReason.ILLEGAL_PIECE_MOVE),
        )
        controller = make_controller(engine)

        controller.on_click(50, 450)   # select rook at (4,0)
        controller.on_click(150, 350)  # diagonal - illegal for rook

        assert engine.request_move_calls == [(Position(4, 0), Position(3, 1))]
        assert controller.selected is None
