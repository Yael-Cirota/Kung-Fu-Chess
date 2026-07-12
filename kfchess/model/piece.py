from enum import Enum
from typing import Optional

from kfchess.model.position import Position

DEFAULT_MOVE_DELAY_MS = 1000


class Color(str, Enum):
    WHITE = 'w'
    BLACK = 'b'


class PieceState(Enum):
    IDLE = 'idle'
    MOVING = 'moving'
    CAPTURED = 'captured'


class PieceKind(Enum):
    KING = 'K'
    QUEEN = 'Q'
    ROOK = 'R'
    BISHOP = 'B'
    KNIGHT = 'N'
    PAWN = 'P'


class Piece:
    """
    A single concrete class for all chess pieces, distinguished by `kind`.
    Encapsulates identity/state only (color, kind, state, has_moved, move_delay_ms).
    Movement legality lives in kfchess.rules.piece_rules.
    """
    def __init__(self, color: str, kind: PieceKind, cell: Optional[Position] = None):
        self.color = Color(color)
        self.kind = kind
        self.cell = cell           # type: Position | None
        self.state = PieceState.IDLE
        self.has_moved = False     # Crucial for castling and pawn double-moves
        self.move_delay_ms = DEFAULT_MOVE_DELAY_MS  # Default move delay

    def get_symbol(self) -> str:
        """Returns the 2-character string representation (e.g., 'wK', 'bP')."""
        return f"{self.color.value}{self.kind.value}"
