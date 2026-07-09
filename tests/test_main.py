import main


def test_run_application_prints_error_and_stops(capsys):
    vpl_input = 'Board:\nwK xZ\nCommands:'
    main.run_application(vpl_input)

    out = capsys.readouterr().out
    assert 'ERROR UNKNOWN_TOKEN' in out


def test_run_application_empty_board_stops_without_output(capsys):
    main.run_application('Commands:\nprint board')
    out = capsys.readouterr().out
    assert out == ''


def test_run_application_produces_expected_board_output(capsys):
    vpl_input = 'Board:\nwK .\n. bP\nCommands:\nprint board'
    main.run_application(vpl_input)

    out = capsys.readouterr().out
    assert out == 'wK .\n. bP\n'


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
