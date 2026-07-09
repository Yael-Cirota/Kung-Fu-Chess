from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    """An immutable (row, col) coordinate on the board grid."""
    row: int
    col: int

    def __iter__(self):
        yield self.row
        yield self.col
