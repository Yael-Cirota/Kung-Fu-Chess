from typing import List, Tuple, Optional

class GameEngine:
    """
    Manages the running game state, coordinate system calculations,
    and piece selection mechanics.
    """
    def __init__(self, board_state: List[List[str]]):
        self.board = board_state  # 2D list representing the grid
        self.clock_ms = 0
        self.selected_cell: Optional[Tuple[int, int]] = None  # Stores (row, col)

    @property
    def rows(self) -> int:
        return len(self.board)

    @property
    def cols(self) -> int:
        return len(self.board[0]) if self.board else 0

    def is_within_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.rows and 0 <= col < self.cols

    def advance_clock(self, ms: int):
        self.clock_ms += ms

    def handle_click(self, x: int, y: int):
        # Rule: Each board cell is 100x100 pixels
        col = x // 100
        row = y // 100

        # Rule: Clicking outside the board is ignored
        if not self.is_within_bounds(row, col):
            return

        target_token = self.board[row][col]

        # Scenario 1 & 2: No active selection
        if self.selected_cell is None:
            if target_token != '.':
                # Rule: Clicking a piece selects it
                self.selected_cell = (row, col)
            # Rule: Clicking an empty cell with no selection is ignored
            return

        # If we reach here, a piece is already selected
        sel_row, sel_col = self.selected_cell
        selected_token = self.board[sel_row][sel_col]
        
        # Determine friendliness based on token's first character color prefix ('w' or 'b')
        if target_token != '.' and target_token[0] == selected_token[0]:
            # Rule: Clicking another friendly piece replaces the selection
            self.selected_cell = (row, col)
        else:
            # Rule: Clicking another cell sends a move request from selected piece to that cell
            self._execute_move(sel_row, sel_col, row, col)
            self.selected_cell = None  # Clear selection after the move action

    def _execute_move(self, from_row: int, from_col: int, to_row: int, to_col: int):
        """Helper to physically move the token on the board array."""
        piece = self.board[from_row][from_col]
        self.board[from_row][from_col] = '.'
        self.board[to_row][to_col] = piece

    def print_board(self):
        # Rule: Prints the current settled board state after all completed moves
        for row in self.board:
            print(" ".join(row))