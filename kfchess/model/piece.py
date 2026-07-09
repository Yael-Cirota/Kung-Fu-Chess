from abc import ABC, abstractmethod

DEFAULT_MOVE_DELAY_MS = 1000

class Piece(ABC):
    """
    Abstract Base Class for all chess pieces.
    Encapsulates identity/state only (color, has_moved, move_delay_ms).
    Movement legality lives in kfchess.rules.movement_rules.MovementRules.
    """
    def __init__(self, color: str):
        self.color = color         # 'w' or 'b'
        self.has_moved = False     # Crucial for castling and pawn double-moves
        self.move_delay_ms = DEFAULT_MOVE_DELAY_MS  # Default move delay

    @abstractmethod
    def get_symbol(self) -> str:
        """Returns the 2-character string representation (e.g., 'wK', 'bP')."""
        pass  # pragma: no cover


class King(Piece):
    def get_symbol(self) -> str:
        return f"{self.color}K"


class Rook(Piece):
    def get_symbol(self) -> str:
        return f"{self.color}R"


class Bishop(Piece):
    def get_symbol(self) -> str:
        return f"{self.color}B"


class Queen(Piece):
    def get_symbol(self) -> str:
        return f"{self.color}Q"


class Knight(Piece):
    def get_symbol(self) -> str:
        return f"{self.color}N"


class Pawn(Piece):
    def get_symbol(self) -> str:
        return f"{self.color}P"
