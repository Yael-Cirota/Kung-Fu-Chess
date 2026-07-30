from client.shell.commands import Command, CommandError, parse
from protocol import messages as m


class TestParseEmptyOrUnknown:
    def test_empty_line_is_unknown(self):
        result = parse("")

        assert result.ok is False
        assert result.command is None
        assert result.error == CommandError.UNKNOWN_COMMAND

    def test_whitespace_only_line_is_unknown(self):
        result = parse("   ")

        assert result.ok is False
        assert result.error == CommandError.UNKNOWN_COMMAND

    def test_unrecognized_word_is_unknown(self):
        result = parse("frobnicate")

        assert result.ok is False
        assert result.error == CommandError.UNKNOWN_COMMAND


class TestArgCountValidation:
    def test_login_with_too_few_args_is_rejected(self):
        result = parse("login alice")

        assert result.ok is False
        assert result.command is Command.LOGIN
        assert result.error == CommandError.WRONG_ARG_COUNT

    def test_play_with_extra_args_is_rejected(self):
        result = parse("play now")

        assert result.ok is False
        assert result.command is Command.PLAY
        assert result.error == CommandError.WRONG_ARG_COUNT


class TestBuildsMessages:
    def test_login_builds_login_request(self):
        result = parse("login alice secret")

        assert result.ok is True
        assert result.command is Command.LOGIN
        assert result.message == m.LoginRequest(username="alice", password="secret")

    def test_register_builds_register_request(self):
        result = parse("register bob hunter2")

        assert result.message == m.RegisterRequest(username="bob", password="hunter2")

    def test_play_builds_play_request(self):
        result = parse("play")

        assert result.message == m.PlayRequest()

    def test_cancel_builds_cancel_queue_request(self):
        result = parse("cancel")

        assert result.message == m.CancelQueueRequest()

    def test_create_room_builds_create_room_request(self):
        result = parse("create-room")

        assert result.message == m.CreateRoomRequest()

    def test_join_room_builds_join_room_request(self):
        result = parse("join-room abc123")

        assert result.message == m.JoinRoomRequest(room_id="abc123")

    def test_leave_room_builds_leave_room_request(self):
        result = parse("leave-room abc123")

        assert result.message == m.LeaveRoomRequest(room_id="abc123")

    def test_command_name_is_case_insensitive(self):
        result = parse("PLAY")

        assert result.ok is True
        assert result.command is Command.PLAY


class TestLocalOnlyCommands:
    def test_help_has_no_wire_message(self):
        result = parse("help")

        assert result.ok is True
        assert result.command is Command.HELP
        assert result.message is None

    def test_quit_has_no_wire_message(self):
        result = parse("quit")

        assert result.ok is True
        assert result.command is Command.QUIT
        assert result.message is None
