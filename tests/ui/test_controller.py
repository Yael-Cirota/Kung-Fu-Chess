from pieces import King, Rook
from kfchess.model.board import Board
from kfchess.model.position import Position
from kfchess.rules.move_result import MoveRejectionReason, MoveValidationResult
from kfchess.ui.board_mapper import BoardMapper
from kfchess.ui.controller import Controller


def empty_grid(rows=8, cols=8):
    return [[None] * cols for _ in range(rows)]


def board_with(*pieces_at):
    grid = empty_grid()
    for (row, col), piece in pieces_at:
        grid[row][col] = piece
    return Board(grid)


class FakeGameEngine:
    """Minimal stand-in for kfchess.engine.GameEngine to keep Controller tests unit-level."""

    def __init__(self, board, moving_pieces=None, game_over=False, next_result=None):
        self._board = board
        self._moving = moving_pieces or set()
        self.game_over = game_over
        self._next_result = next_result if next_result is not None else MoveValidationResult.ok()
        self.request_move_calls = []

    def is_within_bounds(self, pos):
        return self._board.is_within_bounds(pos)

    def piece_at(self, pos):
        return self._board.get(pos)

    def is_moving(self, piece):
        return piece in self._moving

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
        king = King('w')
        engine = FakeGameEngine(board_with(((2, 3), king)))
        controller = make_controller(engine)

        controller.on_click(350, 250)  # col=3, row=2

        assert controller.selected == Position(2, 3)

    def test_click_outside_board_is_ignored(self):
        king = King('w')
        engine = FakeGameEngine(board_with(((0, 0), king)))
        controller = make_controller(engine)

        controller.on_click(900, 900)

        assert controller.selected is None

    def test_click_friendly_piece_replaces_selection(self):
        king = King('w')
        rook = Rook('w')
        engine = FakeGameEngine(board_with(((0, 0), king), ((0, 1), rook)))
        controller = make_controller(engine)

        controller.on_click(50, 50)   # select king at (0,0)
        controller.on_click(150, 50)  # click rook at (0,1)

        assert controller.selected == Position(0, 1)

    def test_click_friendly_moving_piece_keeps_current_selection(self):
        king = King('w')
        rook = Rook('w')
        engine = FakeGameEngine(board_with(((0, 0), king), ((0, 1), rook)), moving_pieces={rook})
        controller = make_controller(engine)

        controller.on_click(50, 50)   # select king at (0,0)
        controller.on_click(150, 50)  # click moving rook at (0,1)

        assert controller.selected == Position(0, 0)

    def test_failsafe_clears_selection_when_selected_piece_is_missing(self):
        rook = Rook('w')
        board = board_with(((0, 0), rook))
        engine = FakeGameEngine(board)
        controller = make_controller(engine)

        controller.on_click(50, 50)  # select rook at (0,0)
        board.remove(Position(0, 0))  # out-of-band mutation removes the selected piece

        controller.on_click(150, 50)  # triggers failsafe branch

        assert controller.selected is None
        assert engine.request_move_calls == []


class TestControllerMoveAttempts:
    def test_legal_move_calls_request_move_and_clears_selection(self):
        rook = Rook('w')
        engine = FakeGameEngine(board_with(((4, 0), rook)))
        controller = make_controller(engine)

        controller.on_click(50, 450)   # select rook at (4,0)
        controller.on_click(750, 450)  # attempt move to (4,7)

        assert engine.request_move_calls == [(Position(4, 0), Position(4, 7))]
        assert controller.selected is None

    def test_illegal_move_still_calls_request_move_and_clears_selection(self):
        rook = Rook('w')
        engine = FakeGameEngine(
            board_with(((4, 0), rook)),
            next_result=MoveValidationResult.reject(MoveRejectionReason.NOT_A_LEGAL_SHAPE),
        )
        controller = make_controller(engine)

        controller.on_click(50, 450)   # select rook at (4,0)
        controller.on_click(150, 350)  # diagonal - illegal for rook

        assert engine.request_move_calls == [(Position(4, 0), Position(3, 1))]
        assert controller.selected is None


class TestControllerGameOver:
    def test_click_ignored_when_game_is_over(self):
        king = King('w')
        engine = FakeGameEngine(board_with(((0, 0), king)), game_over=True)
        controller = make_controller(engine)

        controller.on_click(50, 50)

        assert controller.selected is None
