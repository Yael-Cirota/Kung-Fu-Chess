def parse_and_validate_board(input_text: str) -> str:
    lines = input_text.splitlines()
    
    board_started = False
    board_lines = []
    
    # Define valid tokens based on chess piece representation
    valid_pieces = {'K', 'Q', 'R', 'B', 'N', 'P'}
    valid_colors = {'w', 'b'}
    
    # Extract the board section from the input text
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
            
    if not board_lines:
        return ""

    expected_width = None
    parsed_board = []

    # Validate rows and tokens
    for row_str in board_lines:
        tokens = row_str.split()
        if not tokens:
            continue
            
        # Validate row width uniformity
        if expected_width is None:
            expected_width = len(tokens)
            
        elif len(tokens) != expected_width:
            return "ERROR ROW_WIDTH_MISMATCH"
            
        # Validate individual token format
        for token in tokens:
            if token == '.':
                continue
            
            # Token must be exactly 2 characters long (e.g., wK, bQ)
            if len(token) != 2 or token[0] not in valid_colors or token[1] not in valid_pieces:
                return "ERROR UNKNOWN_TOKEN"
                
        parsed_board.append(tokens)

    # Construct the canonical output string
    output_rows = [" ".join(row) for row in parsed_board]
    return "\n".join(output_rows)