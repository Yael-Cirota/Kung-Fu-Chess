from typing import List, Set

class BoardValidator:
    """
    Responsible solely for validation rules regarding board content and layout.
    Adheres to the Single Responsibility Principle.
    """
    def __init__(self, valid_colors: Set[str], valid_pieces: Set[str]):
        self.valid_colors = valid_colors
        self.valid_pieces = valid_pieces

    def validate_token(self, token: str) -> bool:
        # A dot representing an empty cell is always valid
        if token == '.':
            return True
        # Non-empty tokens must be exactly 2 characters (e.g., 'wK')
        if len(token) != 2:
            return False
        # Validate color and piece type matches allowed sets
        return token[0] in self.valid_colors and token[1] in self.valid_pieces

    def validate_row_widths(self, rows: List[List[str]]) -> bool:
        if not rows:
            return True
        expected_width = len(rows[0])
        # Check if all rows contain the exact same number of tokens
        return all(len(row) == expected_width for row in rows)


class BoardParser:
    """
    Responsible for text stream parsing and coordinate reconstruction.
    Uses Dependency Injection to receive validation logic.
    """
    def __init__(self, validator: BoardValidator):
        # Injected dependency
        self.validator = validator

    def parse(self, input_text: str) -> str:
        lines = input_text.splitlines()
        board_started = False
        board_lines = []
        
        # Isolate target lines belonging to the Board section
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("Board:"):
                board_started = True
                continue
            elif line.startswith("Commands:"):
                break
            if board_started:
                board_lines.append(line)

        # Tokenize lines into cell elements
        parsed_board = [row.split() for row in board_lines if row.split()]
        
        if not parsed_board:
            return ""

        # Validate structural uniformity
        if not self.validator.validate_row_widths(parsed_board):
            return "ERROR ROW_WIDTH_MISMATCH"

        # Validate semantic integrity of individual cells
        for row in parsed_board:
            for token in row:
                if not self.validator.validate_token(token):
                    return "ERROR UNKNOWN_TOKEN"

        # Construct and return standard canonical form representation
        return "\n".join(" ".join(row) for row in parsed_board)