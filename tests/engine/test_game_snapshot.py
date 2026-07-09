from pieces import King, Rook
from kfchess.model.board import Board
from kfchess.model.position import Position
from kfchess.engine.game_snapshot import GameSnapshot, PieceView


def empty_grid(rows=8, cols=8):
    return [[None] * cols for _ in range(rows)]


def board_with(*pieces_at, rows=8, cols=8):
    grid = empty_grid(rows, cols)
    for (row, col), piece in pieces_at:
        grid[row][col] = piece
    return Board(grid)


class TestGameSnapshot:
    def test_dimensions_match_board(self):
        board = board_with(rows=3, cols=4)
        snapshot = GameSnapshot.of(board, clock_ms=0, game_over=False)

        assert snapshot.rows == 3
        assert snapshot.cols == 4

    def test_piece_at_returns_piece_view_with_symbol_and_color(self):
        king = King('w')
        board = board_with(((0, 0), king))
        snapshot = GameSnapshot.of(board, clock_ms=0, game_over=False)

        view = snapshot.piece_at(Position(0, 0))

        assert isinstance(view, PieceView)
        assert view.symbol == "wK"
        assert view.color == 'w'

    def test_piece_at_empty_cell_is_none(self):
        board = board_with()
        snapshot = GameSnapshot.of(board, clock_ms=0, game_over=False)

        assert snapshot.piece_at(Position(0, 0)) is None

    def test_clock_ms_and_game_over_are_captured(self):
        board = board_with()
        snapshot = GameSnapshot.of(board, clock_ms=1500, game_over=True)

        assert snapshot.clock_ms == 1500
        assert snapshot.game_over is True

    def test_snapshot_is_immutable_to_later_board_mutation(self):
        rook = Rook('w')
        board = board_with(((0, 0), rook))
        snapshot = GameSnapshot.of(board, clock_ms=0, game_over=False)

        board.remove(Position(0, 0))
        board.set(Position(0, 1), rook)

        assert snapshot.piece_at(Position(0, 0)) is not None
        assert snapshot.piece_at(Position(0, 1)) is None
