import itertools
from enum import Enum
from typing import Optional

from kfchess.model.position import Position

_id_counter = itertools.count(1)

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
    Encapsulates identity/state only (color, kind, state, has_moved).
    Movement legality lives in kfchess.rules.piece_rules; movement timing
    and active-motion tracking live entirely in kfchess.realtime.
    """
    def __init__(self, color: str, kind: PieceKind, cell: Optional[Position] = None):
        self.piece_id = next(_id_counter)
        self.color = Color(color)
        self.kind = kind
        self.cell = cell           # type: Position | None
        self.state = PieceState.IDLE
        self.has_moved = False     # Crucial for castling and pawn double-moves

    def get_symbol(self) -> str:
        """Returns the 2-character string representation (e.g., 'wK', 'bP')."""
        return f"{self.color.value}{self.kind.value}"
