import pytest
from commands import (
    ClickCommand, WaitCommand, PrintBoardCommand, CommandParser
)


# ==========================================
# 1. COMMAND OBJECTS
# ==========================================

class FakeEngine:
    """Minimal stand-in for GameEngine to capture method calls."""
    def __init__(self):
        self.clicks = []
        self.waits = []
        self.prints = 0

    def handle_click(self, x, y):
        self.clicks.append((x, y))

    def advance_clock(self, ms):
        self.waits.append(ms)

    def print_board(self):
        self.prints += 1


class TestClickCommand:
    def test_execute_delegates_to_engine(self):
        engine = FakeEngine()
        ClickCommand(150, 250).execute(engine)
        assert engine.clicks == [(150, 250)]

    def test_stores_coordinates(self):
        cmd = ClickCommand(10, 20)
        assert cmd.x == 10
        assert cmd.y == 20


class TestWaitCommand:
    def test_execute_advances_clock(self):
        engine = FakeEngine()
        WaitCommand(500).execute(engine)
        assert engine.waits == [500]

    def test_stores_ms(self):
        cmd = WaitCommand(300)
        assert cmd.ms == 300


class TestPrintBoardCommand:
    def test_execute_calls_print_board(self):
        engine = FakeEngine()
        PrintBoardCommand().execute(engine)
        assert engine.prints == 1


# ==========================================
# 2. COMMAND PARSER
# ==========================================

class TestCommandParser:
    def test_parse_click(self):
        cmd = CommandParser.parse_line("click 150 250")
        assert isinstance(cmd, ClickCommand)
        assert cmd.x == 150
        assert cmd.y == 250

    def test_parse_wait(self):
        cmd = CommandParser.parse_line("wait 1000")
        assert isinstance(cmd, WaitCommand)
        assert cmd.ms == 1000

    def test_parse_print_board(self):
        cmd = CommandParser.parse_line("print board")
        assert isinstance(cmd, PrintBoardCommand)

    def test_parse_empty_line(self):
        assert CommandParser.parse_line("") is None
        assert CommandParser.parse_line("   ") is None

    def test_parse_unknown_command(self):
        assert CommandParser.parse_line("move a2 a4") is None

    def test_parse_click_non_integer_returns_none(self):
        result = CommandParser.parse_line("click abc 250")
        assert result is None

    def test_parse_wait_non_integer_returns_none(self):
        result = CommandParser.parse_line("wait xyz")
        assert result is None

    @pytest.mark.parametrize("line", [
        "click 100",          # missing y
        "click 100 200 300",  # too many args
    ])
    def test_parse_click_wrong_arg_count(self, line):
        assert CommandParser.parse_line(line) is None

    def test_parse_wait_wrong_arg_count(self):
        assert CommandParser.parse_line("wait") is None

    def test_parse_click_with_extra_whitespace(self):
        cmd = CommandParser.parse_line("  click  50  75  ")
        assert isinstance(cmd, ClickCommand)
        assert cmd.x == 50
        assert cmd.y == 75
