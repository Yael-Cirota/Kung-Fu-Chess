

import sys
from board_parser import BoardValidator, BoardParser
from game_engine import GameEngine
from commands import CommandParser
from pieces import King, Queen, Rook, Bishop, Knight, Pawn

def create_piece(token: str):
    """Factory function to convert text tokens into Piece objects."""
    if token == '.':
        return None
    
    color = token[0]
    piece_type = token[1]
    
    piece_classes = {
        'K': King, 'Q': Queen, 'R': Rook, 
        'B': Bishop, 'N': Knight, 'P': Pawn
    }
    
    piece_class = piece_classes.get(piece_type)
    return piece_class(color) if piece_class else None


def main():
    # 1. Standard Input Capture
    vpl_input = sys.stdin.read()
    
    # 2. Setup Board Parsing Dependencies
    chess_validator = BoardValidator(
        valid_colors={'w', 'b'}, 
        valid_pieces={'K', 'Q', 'R', 'B', 'N', 'P'}
    )
    parser = BoardParser(validator=chess_validator)
    
    # 3. Parse and reconstruct the initial layout
    raw_board_string = parser.parse(vpl_input)
    if not raw_board_string or raw_board_string.startswith("ERROR"):
        if raw_board_string:
            print(raw_board_string)
        return

    # 4. Convert the raw strings into a 2D grid of actual Piece Objects    raw_grid = [row.split() for row in raw_board_string.splitlines()]
    raw_grid = [row.split() for row in raw_board_string.splitlines()]
    object_grid = [[create_piece(token) for token in row] for row in raw_grid]
    # 4. Dependency Injection: Pass the board grid state directly to our Engine
    engine = GameEngine(board_state=object_grid)

    # 6. Dynamic Streaming of Section Command Lines
    commands_started = False
    lines = vpl_input.splitlines()
    
    for line in lines:
        line_str = line.strip()
        if line_str.startswith("Commands:"):
            commands_started = True
            continue
            
        if commands_started and line_str:
            # Command Execution Loop via Factory Parsing
            command = CommandParser.parse_line(line_str)
            if command:
                command.execute(engine)

if __name__ == "__main__":
    main()

