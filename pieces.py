from abc import ABC, abstractmethod
from typing import List, Optional

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
    def is_legal_move(self, board: List[List[Optional['Piece']]], from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
        """Validates if the target cell matches the geometric movement shape AND if the path is clear."""
        pass

    def _is_path_clear(self, board: List[List[Optional['Piece']]], from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
        """Helper to check if all squares between start and end are empty."""
        dr = to_row - from_row
        dc = to_col - from_col
        
        # Determine the direction of the step (-1, 0, or 1)
        step_r = 0 if dr == 0 else (1 if dr > 0 else -1)
        step_c = 0 if dc == 0 else (1 if dc > 0 else -1)
        
        curr_r = from_row + step_r
        curr_c = from_col + step_c

        # Iterate until we reach the destination square
        while curr_r != to_row or curr_c != to_col:
            if board[curr_r][curr_c] is not None:
                return False  # Path is blocked
            curr_r += step_r
            curr_c += step_c
            
        return True


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

    def is_legal_move(self, board: List[List[Optional['Piece']]], from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
        dr = abs(to_row - from_row)
        dc = abs(to_col - from_col)
        
        if dr == 0 and dc == 0:
            return False
            
        if not (dr == 0 or dc == 0):
            return False
            
        return self._is_path_clear(board, from_row, from_col, to_row, to_col)


class Bishop(Piece):
    def get_symbol(self) -> str:
        return f"{self.color}B"

    def is_legal_move(self, board: List[List[Optional['Piece']]], from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
        dr = abs(to_row - from_row)
        dc = abs(to_col - from_col)
        
        if dr == 0 and dc == 0:
            return False
            
        if dr != dc:
            return False
            
        return self._is_path_clear(board, from_row, from_col, to_row, to_col)


class Queen(Piece):
    def get_symbol(self) -> str:
        return f"{self.color}Q"

    def is_legal_move(self, board: List[List[Optional['Piece']]], from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
        dr = abs(to_row - from_row)
        dc = abs(to_col - from_col)
        
        if dr == 0 and dc == 0:
            return False
            
        if not (dr == 0 or dc == 0 or dr == dc):
            return False
            
        return self._is_path_clear(board, from_row, from_col, to_row, to_col)


class Knight(Piece):
    def get_symbol(self) -> str:
        return f"{self.color}N"

    def is_legal_move(self, board: List[List[Optional['Piece']]], from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
        dr = abs(to_row - from_row)
        dc = abs(to_col - from_col)
        
        if dr == 0 and dc == 0:
            return False
        
        # Notice we do NOT check _is_path_clear here, allowing the knight to jump!
        return (dr == 2 and dc == 1) or (dr == 1 and dc == 2)


class Pawn(Piece):
    def get_symbol(self) -> str:
        return f"{self.color}P"

    def is_legal_move(self, board: List[List[Optional['Piece']]], from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
        # Pawns have complex rules (directionality, attacks vs. moves, en passant).
        # Returning True as a placeholder for this iteration.
        dr = abs(to_row - from_row)
        dc = abs(to_col - from_col)
        
        if dr == 0 and dc == 0:
            return False
            
        return True