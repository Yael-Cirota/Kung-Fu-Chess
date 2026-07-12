import pytest

from kfchess.model.piece import PieceKind
from kfchess.texttests.script_parser import (
    ScriptParser, ClickCommand, WaitCommand, PrintBoardCommand, JumpCommand,
    create_piece, parse_board_grid, parse_command_line,
)


class TestCreatePiece:
    def test_dot_returns_none(self):
        assert create_piece('.') is None

    def test_known_piece_returns_instance(self):
        piece = create_piece('wK')
        assert piece.kind is PieceKind.KING
        assert piece.color == 'w'

    def test_unknown_piece_type_returns_none(self):
        assert create_piece('wX') is None


class TestParseBoardGrid:
    def test_builds_piece_grid(self):
        raw = 'wK .\n. bP'
        grid = parse_board_grid(raw)

        assert grid[0][0].kind is PieceKind.KING
        assert grid[0][1] is None
        assert grid[1][0] is None
        assert grid[1][1].kind is PieceKind.PAWN
        assert grid[1][1].color == 'b'


class TestParseCommandLine:
    def test_parse_click(self):
        cmd = parse_command_line("click 150 250")
        assert cmd == ClickCommand(150, 250)

    def test_parse_wait(self):
        cmd = parse_command_line("wait 1000")
        assert cmd == WaitCommand(1000)

    def test_parse_print_board(self):
        assert parse_command_line("print board") == PrintBoardCommand()

    def test_parse_empty_line(self):
        assert parse_command_line("") is None
        assert parse_command_line("   ") is None

    def test_parse_unknown_command(self):
        assert parse_command_line("move a2 a4") is None

    def test_parse_wait_non_integer_returns_none(self):
        assert parse_command_line("wait xyz") is None

    def test_parse_click_with_extra_whitespace(self):
        cmd = parse_command_line("  click  50  75  ")
        assert cmd == ClickCommand(50, 75)

    def test_parse_jump(self):
        cmd = parse_command_line("jump 150 250")
        assert cmd == JumpCommand(150, 250)

    @pytest.mark.parametrize("keyword", ["click", "jump"])
    def test_parse_non_integer_returns_none(self, keyword):
        assert parse_command_line(f"{keyword} abc 250") is None

    @pytest.mark.parametrize("keyword", ["click", "jump"])
    def test_parse_wrong_arg_count(self, keyword):
        assert parse_command_line(f"{keyword} 100") is None
        assert parse_command_line(f"{keyword} 100 200 300") is None


class TestScriptParser:
    def test_parses_board_and_commands(self):
        vpl_input = (
            "Board:\n"
            "wK . bQ\n"
            "Commands:\n"
            "click 50 50\n"
            "wait 1000\n"
            "print board"
        )

        script = ScriptParser().parse(vpl_input)

        assert script.board_grid[0][0].kind is PieceKind.KING
        assert script.error is None
        assert script.commands == [
            ClickCommand(50, 50), WaitCommand(1000), PrintBoardCommand(),
        ]

    def test_row_width_mismatch_reported_as_error(self):
        vpl_input = "Board:\nwK .\n. . .\nCommands:\nprint board"

        script = ScriptParser().parse(vpl_input)

        assert script.error == "ERROR ROW_WIDTH_MISMATCH"
        assert script.board_grid is None
        assert script.commands == []

    def test_unknown_token_reported_as_error(self):
        vpl_input = "Board:\nwK xZ\nCommands:"

        script = ScriptParser().parse(vpl_input)

        assert script.error == "ERROR UNKNOWN_TOKEN"

    def test_empty_board_has_no_grid_and_no_error(self):
        script = ScriptParser().parse("Commands:\nprint board")

        assert script.board_grid is None
        assert script.error is None
        assert script.commands == []

    def test_blank_lines_between_commands_are_skipped(self):
        vpl_input = (
            "Board:\n"
            "wK .\n"
            "Commands:\n"
            "\n"
            "   \n"
            "print board"
        )

        script = ScriptParser().parse(vpl_input)

        assert script.commands == [PrintBoardCommand()]
