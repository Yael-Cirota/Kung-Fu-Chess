import main
from game_engine import GameEngine
from pieces import King, Pawn


def test_create_piece_dot_returns_none():
    assert main.create_piece('.') is None


def test_create_piece_known_piece_returns_instance():
    piece = main.create_piece('wK')
    assert isinstance(piece, King)
    assert piece.color == 'w'


def test_create_piece_unknown_piece_type_returns_none():
    assert main.create_piece('wX') is None


def test_parse_board_grid_builds_piece_grid():
    raw = 'wK .\n. bP'
    grid = main.parse_board_grid(raw)

    assert isinstance(grid[0][0], King)
    assert grid[0][1] is None
    assert grid[1][0] is None
    assert isinstance(grid[1][1], Pawn)
    assert grid[1][1].color == 'b'


def test_execute_commands_runs_only_after_commands_section(monkeypatch):
    class FakeEngine:
        def __init__(self):
            self.calls = []

    class FakeCommand:
        def execute(self, engine):
            engine.calls.append('executed')

    seen_lines = []

    def fake_parse_line(line):
        seen_lines.append(line)
        return FakeCommand()

    monkeypatch.setattr(main.CommandParser, 'parse_line', fake_parse_line)

    engine = FakeEngine()
    main.execute_commands('click 0 0\nCommands:\nclick 10 10\nwait 100', engine)

    assert seen_lines == ['click 10 10', 'wait 100']
    assert engine.calls == ['executed', 'executed']


def test_execute_commands_skips_blank_lines(monkeypatch):
    seen_lines = []

    def fake_parse_line(line):
        seen_lines.append(line)
        return None

    monkeypatch.setattr(main.CommandParser, 'parse_line', fake_parse_line)

    engine = GameEngine([[None]])
    main.execute_commands('Commands:\n\n   \nprint board', engine)

    assert seen_lines == ['print board']


def test_run_application_prints_error_and_stops(capsys):
    vpl_input = 'Board:\nwK xZ\nCommands:'
    main.run_application(vpl_input)

    out = capsys.readouterr().out
    assert 'ERROR UNKNOWN_TOKEN' in out


def test_run_application_empty_board_stops_without_output(capsys):
    main.run_application('Commands:\nprint board')
    out = capsys.readouterr().out
    assert out == ''


def test_run_application_happy_path_calls_execute_commands(monkeypatch):
    captured = {}

    def fake_execute_commands(vpl_input, engine):
        captured['input'] = vpl_input
        captured['engine'] = engine

    monkeypatch.setattr(main, 'execute_commands', fake_execute_commands)

    vpl_input = 'Board:\nwK .\n. bP\nCommands:\nprint board'
    main.run_application(vpl_input)

    assert captured['input'] == vpl_input
    assert isinstance(captured['engine'], GameEngine)
    assert isinstance(captured['engine'].board[0][0], King)


def test_main_reads_stdin_and_calls_run_application(monkeypatch):
    captured = {}

    class FakeStdin:
        @staticmethod
        def read():
            return 'Board:\nwK .\nCommands:'

    def fake_run_application(vpl_input):
        captured['input'] = vpl_input

    monkeypatch.setattr(main.sys, 'stdin', FakeStdin())
    monkeypatch.setattr(main, 'run_application', fake_run_application)

    main.main()

    assert captured['input'] == 'Board:\nwK .\nCommands:'
