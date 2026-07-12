from kfchess.model.board import Board


class BoardPrinter:
    """Prints a Board's current piece layout, one row per line."""

    def print(self, board: Board) -> None:
        for row in board.as_grid():
            row_str = " ".join(piece.get_symbol() if piece is not None else '.' for piece in row)
            print(row_str)
