# Github repository:
# https://github.com/Yael-Cirota/Kung-Fu-Chess

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

def parse_board_grid(raw_board_string: str) -> list:
    """Converts a raw string board into a 2D grid of Piece objects."""
    raw_grid = [row.split() for row in raw_board_string.splitlines()]
    return [[create_piece(token) for token in row] for row in raw_grid]

def execute_commands(vpl_input: str, engine: GameEngine):
    """Extracts and executes commands from the input sequence."""
    commands_started = False
    
    for line in vpl_input.splitlines():
        line_str = line.strip()
        
        if line_str.startswith("Commands:"):
            commands_started = True
            continue
            
        if commands_started and line_str:
            command = CommandParser.parse_line(line_str)
            if command:
                command.execute(engine)

def run_application(vpl_input: str):
    """Core application logic orchestrator."""
    # 1. Setup Dependencies
    chess_validator = BoardValidator(
        valid_colors={'w', 'b'}, 
        valid_pieces={'K', 'Q', 'R', 'B', 'N', 'P'}
    )
    parser = BoardParser(validator=chess_validator)
    
    # 2. Parse Board
    raw_board_string = parser.parse(vpl_input)
    if not raw_board_string or raw_board_string.startswith("ERROR"):
        if raw_board_string:
            print(raw_board_string)
        return

    
    # 3. Initialize Engine
    object_grid = parse_board_grid(raw_board_string)
    engine = GameEngine(board_state=object_grid)

    # 4. Run Commands
    execute_commands(vpl_input, engine)

def main():
    """Entry point - Only handles OS-level I/O."""
    vpl_input = sys.stdin.read()
    run_application(vpl_input)

if __name__ == "__main__":  # pragma: no cover
    main()