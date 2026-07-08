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
        self.pending_moves = []  # Queue of moves waiting to be executed

    @property
    def rows(self) -> int:
        return len(self.board)

    @property
    def cols(self) -> int:
        return len(self.board[0]) if self.board else 0

    def is_within_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.rows and 0 <= col < self.cols

    def advance_clock(self, ms: int):
        """
        Advances the virtual clock and executes any scheduled moves 
        whose execution time has arrived or passed.
        """
        self.clock_ms += ms
        
        # Filter out moves that are ready to be executed
        ready_moves = [m for m in self.pending_moves if m['execute_at'] <= self.clock_ms]
        
        # Sort by target time to maintain proper chronological order
        ready_moves.sort(key=lambda m: m['execute_at'])
        
        # Keep only the remaining future moves in the pending queue
        self.pending_moves = [m for m in self.pending_moves if m['execute_at'] > self.clock_ms]
        
        # Physically execute each matured move on the board
        for move in ready_moves:
            self._execute_move(move['from_row'], move['from_col'], move['to_row'], move['to_col'])

    def handle_click(self, x: int, y: int):
        # Rule: Each board cell is 100x100 pixels
        col = x // 100
        row = y // 100

        # Rule: Clicking outside the board is ignored
        if not self.is_within_bounds(row, col):
            return

        target_piece = self.board[row][col]

        # Scenario 1 & 2: No active selection
        if self.selected_cell is None:
            if target_piece is not None:
                # Rule: Clicking a piece selects it
                self.selected_cell = (row, col)
            # Rule: Clicking an empty cell with no selection is ignored
            return

        # If we reach here, a piece is already selected
        sel_row, sel_col = self.selected_cell
        selected_piece = self.board[sel_row][sel_col]

        # Failsafe
        if selected_piece is None:
            self.selected_cell = None
            return
        
        # Determine friendliness based on token's first character color prefix ('w' or 'b')
        if target_piece is not None and target_piece.color == selected_piece.color:
            # Rule: Clicking another friendly piece replaces the selection
            self.selected_cell = (row, col)
        else:
            # Rule: Clicking another cell sends a move request from selected piece to that cell
            if selected_piece.is_legal_move(self.board, sel_row, sel_col, row, col):
                self._schedule_move(selected_piece, sel_row, sel_col, row, col)
                
            self.selected_cell = None  # Clear selection after the move action

    def _execute_move(self, from_row: int, from_col: int, to_row: int, to_col: int):
        """Helper to physically move the token on the board array."""
        piece = self.board[from_row][from_col]
        if piece is not None:
            piece.has_moved = True  # Update the piece's internal state!
            
        self.board[from_row][from_col] = None
        self.board[to_row][to_col] = piece

    def print_board(self):
        # Rule: Prints the current settled board state after all completed moves
        for row in self.board:
            row_str = " ".join(piece.get_symbol() if piece is not None else '.' for piece in row)
            print(row_str)

    def _schedule_move(self, piece, from_row: int, from_col: int, to_row: int, to_col: int):
        """Calculates distance and schedules the move in the pending queue."""
        dr = abs(to_row - from_row)
        dc = abs(to_col - from_col)
        distance = max(dr, dc)
        
        if distance == 0:
            distance = 1 

        total_move_time = distance * piece.move_delay_ms
        target_time = self.clock_ms + total_move_time

        self.pending_moves.append({
            'execute_at': target_time,
            'from_row': from_row,
            'from_col': from_col,
            'to_row': to_row,
            'to_col': to_col
        })