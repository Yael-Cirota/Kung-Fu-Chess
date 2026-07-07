import sys
from board_parser import BoardValidator, BoardParser
from game_engine import GameEngine
from commands import CommandParser

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

    # Turn the validated layout back into a usable dynamic 2D array structure
    initial_grid = [row.split() for row in raw_board_string.splitlines()]

    # 4. Dependency Injection: Pass the board grid state directly to our Engine
    engine = GameEngine(board_state=initial_grid)

    # 5. Dynamic Streaming of Section Command Lines
    lines = vpl_input.splitlines()
    commands_started = False
    
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

    