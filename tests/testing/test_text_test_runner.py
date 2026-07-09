from pieces import King, Pawn
from kfchess.testing.text_test_runner import TextTestRunner, create_piece, parse_board_grid


class TestCreatePiece:
    def test_dot_returns_none(self):
        assert create_piece('.') is None

    def test_known_piece_returns_instance(self):
        piece = create_piece('wK')
        assert isinstance(piece, King)
        assert piece.color == 'w'

    def test_unknown_piece_type_returns_none(self):
        assert create_piece('wX') is None


class TestParseBoardGrid:
    def test_builds_piece_grid(self):
        raw = 'wK .\n. bP'
        grid = parse_board_grid(raw)

        assert isinstance(grid[0][0], King)
        assert grid[0][1] is None
        assert grid[1][0] is None
        assert isinstance(grid[1][1], Pawn)
        assert grid[1][1].color == 'b'


class TestTextTestRunnerRun:
    def test_canonical_vpl_example_reproduces_expected_output(self):
        vpl_input = (
            "Board:\n"
            "wK . bQ\n"
            ". wN .\n"
            "bP . wR\n"
            "Commands:\n"
            "print board"
        )

        output = TextTestRunner().run(vpl_input)

        assert output == "wK . bQ\n. wN .\nbP . wR\n"

    def test_run_file_matches_run(self, tmp_path):
        vpl_text = (
            "Board:\n"
            "wK .\n"
            "Commands:\n"
            "print board"
        )
        script = tmp_path / "sample.vpl"
        script.write_text(vpl_text)

        runner = TextTestRunner()

        assert runner.run_file(script) == runner.run(vpl_text)

    def test_row_width_mismatch_error_surfaces_unchanged(self):
        vpl_input = "Board:\nwK .\n. . .\nCommands:\nprint board"

        output = TextTestRunner().run(vpl_input)

        assert output == "ERROR ROW_WIDTH_MISMATCH\n"

    def test_unknown_token_error_surfaces_unchanged(self):
        vpl_input = 'Board:\nwK xZ\nCommands:'

        output = TextTestRunner().run(vpl_input)

        assert output == "ERROR UNKNOWN_TOKEN\n"

    def test_empty_board_produces_no_output(self):
        output = TextTestRunner().run('Commands:\nprint board')

        assert output == ""

    def test_blank_lines_between_commands_are_skipped(self):
        vpl_input = (
            "Board:\n"
            "wK .\n"
            "Commands:\n"
            "\n"
            "   \n"
            "print board"
        )

        output = TextTestRunner().run(vpl_input)

        assert output == "wK .\n"

    def test_click_wait_print_board_sequence(self):
        vpl_input = (
            "Board:\n"
            "wR . .\n"
            "Commands:\n"
            "click 50 50\n"
            "click 250 50\n"
            "wait 1000\n"
            "print board\n"
            "wait 1000\n"
            "print board"
        )

        output = TextTestRunner().run(vpl_input)

        assert output == "wR . .\n. . wR\n"
