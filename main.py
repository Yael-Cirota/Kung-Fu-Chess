import sys
from board_parser import BoardValidator, BoardParser

def main():
    # 1. Initialize dependencies configuration
    chess_validator = BoardValidator(
        valid_colors={'w', 'b'}, 
        valid_pieces={'K', 'Q', 'R', 'B', 'N', 'P'}
    )
    
    # 2. Perform Dependency Injection during object construction
    parser = BoardParser(validator=chess_validator)
    
    # 3. Read input from standard execution stream
    vpl_input = sys.stdin.read()
    result = parser.parse(vpl_input)
    
    # 4. Standard stream output print execution
    if result:
        print(result)

if __name__ == "__main__":
    main()