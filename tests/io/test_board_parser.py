import pytest
from kfchess.io.board_parser import BoardValidator, BoardParser

@pytest.fixture
def validator():
    """Fixture to inject a standard configuration of BoardValidator."""
    return BoardValidator(
        valid_colors={'w', 'b'}, 
        valid_pieces={'K', 'Q', 'R', 'B', 'N', 'P'}
    )

@pytest.fixture
def parser(validator):
    """Fixture to inject a BoardParser instance pre-loaded with the validator."""
    return BoardParser(validator=validator)


# ==========================================
# 1. UNIT TESTS FOR: BoardValidator
# ==========================================

def test_validator_valid_tokens(validator):
    """Should return True for valid tokens and empty cells."""
    assert validator.validate_token('.') is True
    assert validator.validate_token('wK') is True
    assert validator.validate_token('bQ') is True


@pytest.mark.parametrize("invalid_token", ['xZ', 'w', 'wKK', 'K'])
def test_validator_invalid_tokens(validator, invalid_token):
    """Should return False for poorly formatted or unknown tokens."""
    assert validator.validate_token(invalid_token) is False


def test_validator_row_widths_match(validator):
    """Should return True when all rows have identical token counts."""
    valid_rows = [
        ['wK', '.', 'bK'],
        ['.', 'wN', '.'],
        ['bP', '.', 'wR']
    ]
    assert validator.validate_row_widths(valid_rows) is True


def test_validator_row_widths_mismatch(validator):
    """Should return False when at least one row has a different width."""
    invalid_rows = [
        ['wK', '.', 'bK'],
        ['.', 'bK']  # Length 2 instead of 3
    ]
    assert validator.validate_row_widths(invalid_rows) is False


def test_validator_row_widths_empty_rows(validator):
    """Should return True for an empty row list (edge case)."""
    assert validator.validate_row_widths([]) is True


# ==========================================
# 2. INTEGRATION / PARSER TESTS (VPL Scenarios)
# ==========================================

def test_parse_valid_rectangular_board(parser):
    """Test 2 & 3: Should successfully parse and return canonical form."""
    vpl_input = (
        "Board:\n"
        "wK . bQ\n"
        ". wN .\n"
        "bP . wR\n"
        "Commands:\n"
        "print board"
    )
    expected_output = "wK . bQ\n. wN .\nbP . wR"
    assert parser.parse(vpl_input) == expected_output


def test_parse_reject_unknown_token(parser):
    """Test 4: Should intercept invalid tokens and return specific error."""
    vpl_input = (
        "Board:\n"
        "wK xZ\n"
        ". .\n"
        "Commands:"
    )
    assert parser.parse(vpl_input) == "ERROR UNKNOWN_TOKEN"


def test_parse_reject_row_width_mismatch(parser):
    """Test 5: Should intercept row dimension mismatch and return specific error."""
    vpl_input = (
        "Board:\n"
        "wK . .\n"
        ". bK\n"
        "Commands:"
    )
    assert parser.parse(vpl_input) == "ERROR ROW_WIDTH_MISMATCH"


@pytest.mark.parametrize("empty_input", ["", "Commands:\nprint board"])
def test_parse_empty_input(parser, empty_input):
    """Edge Case: Should safely handle empty strings or missing board sections."""
    assert parser.parse(empty_input) == ""


def test_parse_ignores_blank_lines_inside_board_section(parser):
    """Should skip blank lines while parsing board rows."""
    vpl_input = (
        "Board:\n"
        "wK bK\n"
        "\n"
        ". .\n"
        "Commands:"
    )
    assert parser.parse(vpl_input) == "wK bK\n. ."