from kfchess.texttests.script_runner import ScriptRunner


class TestScriptRunnerRun:
    def test_canonical_vpl_example_reproduces_expected_output(self):
        vpl_input = (
            "Board:\n"
            "wK . bQ\n"
            ". wN .\n"
            "bP . wR\n"
            "Commands:\n"
            "print board"
        )

        output = ScriptRunner().run(vpl_input)

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

        runner = ScriptRunner()

        assert runner.run_file(script) == runner.run(vpl_text)

    def test_row_width_mismatch_error_surfaces_unchanged(self):
        vpl_input = "Board:\nwK .\n. . .\nCommands:\nprint board"

        output = ScriptRunner().run(vpl_input)

        assert output == "ERROR ROW_WIDTH_MISMATCH\n"

    def test_unknown_token_error_surfaces_unchanged(self):
        vpl_input = 'Board:\nwK xZ\nCommands:'

        output = ScriptRunner().run(vpl_input)

        assert output == "ERROR UNKNOWN_TOKEN\n"

    def test_empty_board_produces_no_output(self):
        output = ScriptRunner().run('Commands:\nprint board')

        assert output == ""

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

        output = ScriptRunner().run(vpl_input)

        assert output == "wR . .\n. . wR\n"

    def test_jump_command_requests_a_move_back_to_the_same_square(self):
        # A same-square move never mutates the board, so a broken (no-op)
        # JumpCommand handler would produce this exact output too. The
        # click/click pair after the jump proves the jump actually fired:
        # if it did, the rook is still mid-flight and this second move
        # request is rejected as MOTION_IN_PROGRESS; if the jump were a
        # no-op, this request would succeed and move the rook to (0, 2)
        # within the wait window, changing the printed board.
        vpl_input = (
            "Board:\n"
            "wR . .\n"
            "Commands:\n"
            "jump 50 50\n"
            "click 50 50\n"
            "click 250 50\n"
            "wait 2000\n"
            "print board"
        )

        output = ScriptRunner().run(vpl_input)

        assert output == "wR . .\n"
