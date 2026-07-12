from kfchess.model.piece import Piece, PieceKind
from kfchess.model.board import Board
from kfchess.io.board_printer import BoardPrinter


def test_print_prints_symbols_and_dots_row_by_row(capsys):
    grid = [
        [Piece('w', PieceKind.KING), None, Piece('b', PieceKind.QUEEN)],
        [None, Piece('w', PieceKind.KNIGHT), None],
        [Piece('b', PieceKind.PAWN), None, Piece('w', PieceKind.ROOK)],
    ]
    board = Board(grid)

    BoardPrinter().print(board)

    out = capsys.readouterr().out
    assert out == "wK . bQ\n. wN .\nbP . wR\n"
