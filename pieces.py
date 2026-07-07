from abc import ABC, abstractmethod

class Piece(ABC):
    """
    Abstract Base Class for all chess pieces.
    Encapsulates state (color, has_moved) and movement logic.
    """
    def __init__(self, color: str):
        self.color = color         # 'w' or 'b'
        self.has_moved = False     # Crucial for castling and pawn double-moves

    @abstractmethod
    def get_symbol(self) -> str:
        """Returns the 2-character string representation (e.g., 'wK', 'bP')."""
        pass

    @abstractmethod
    def is_legal_move(self, from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
        """Validates if the target cell matches the geometric movement shape of the piece."""
        pass


class King(Piece):
    def get_symbol(self) -> str:
        return f"{self.color}K"

    def is_legal_move(self, from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
        dr = abs(to_row - from_row)
        dc = abs(to_col - from_col)
        
        if dr == 0 and dc == 0:
            return False
            
        return dr <= 1 and dc <= 1


class Rook(Piece):
    def get_symbol(self) -> str:
        return f"{self.color}R"

    def is_legal_move(self, from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
        dr = abs(to_row - from_row)
        dc = abs(to_col - from_col)
        
        if dr == 0 and dc == 0:
            return False
            
        return dr == 0 or dc == 0


class Bishop(Piece):
    def get_symbol(self) -> str:
        return f"{self.color}B"

    def is_legal_move(self, from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
        dr = abs(to_row - from_row)
        dc = abs(to_col - from_col)
        
        if dr == 0 and dc == 0:
            return False
            
        return dr == dc


class Queen(Piece):
    def get_symbol(self) -> str:
        return f"{self.color}Q"

    def is_legal_move(self, from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
        dr = abs(to_row - from_row)
        dc = abs(to_col - from_col)
        
        if dr == 0 and dc == 0:
            return False
            
        return (dr == 0 or dc == 0) or (dr == dc)


class Knight(Piece):
    def get_symbol(self) -> str:
        return f"{self.color}N"

    def is_legal_move(self, from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
        dr = abs(to_row - from_row)
        dc = abs(to_col - from_col)
        
        if dr == 0 and dc == 0:
            return False
            
        return (dr == 2 and dc == 1) or (dr == 1 and dc == 2)


class Pawn(Piece):
    def get_symbol(self) -> str:
        return f"{self.color}P"

    def is_legal_move(self, from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
        # Pawns have complex rules (directionality, attacks vs. moves, en passant).
        # Returning True as a placeholder for this iteration.
        dr = abs(to_row - from_row)
        dc = abs(to_col - from_col)
        
        if dr == 0 and dc == 0:
            return False
            
        return True