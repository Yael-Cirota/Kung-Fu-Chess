from client.net.client_link import ClientLink
from client.shell.shell import ActiveRoom, HELP_TEXT, Shell
from protocol import messages as m


class TestHandleCommandSendsWireMessages:
    def test_login_enqueues_a_login_request_onto_outbound(self):
        link = ClientLink()
        shell = Shell(link)

        outcome = shell.handle_command("login alice secret")

        assert link.outbound.get_nowait() == m.LoginRequest(username="alice", password="secret")
        assert outcome.lines == []
        assert outcome.should_quit is False

    def test_join_room_enqueues_a_join_room_request(self):
        link = ClientLink()
        shell = Shell(link)

        shell.handle_command("join-room abc123")

        assert link.outbound.get_nowait() == m.JoinRoomRequest(room_id="abc123")


class TestHandleCommandLocalOnly:
    def test_quit_signals_should_quit_and_sends_nothing(self):
        link = ClientLink()
        shell = Shell(link)

        outcome = shell.handle_command("quit")

        assert outcome.should_quit is True
        assert link.outbound.empty()

    def test_help_prints_help_text_and_sends_nothing(self):
        link = ClientLink()
        shell = Shell(link)

        outcome = shell.handle_command("help")

        assert outcome.lines == [HELP_TEXT]
        assert link.outbound.empty()


class TestHandleCommandErrors:
    def test_unknown_command_reports_an_error_line(self):
        shell = Shell(ClientLink())

        outcome = shell.handle_command("frobnicate")

        assert len(outcome.lines) == 1
        assert "Unknown command" in outcome.lines[0]
        assert outcome.should_quit is False

    def test_wrong_arg_count_names_the_offending_command(self):
        shell = Shell(ClientLink())

        outcome = shell.handle_command("login alice")

        assert "login" in outcome.lines[0]


class TestDrainNotifications:
    def test_empty_queue_yields_no_lines(self):
        shell = Shell(ClientLink())

        assert shell.drain_notifications() == []

    def test_auth_ok_is_formatted(self):
        link = ClientLink()
        link.inbound_shell.put(m.AuthOk(user_id=1, username="alice", elo=1200))
        shell = Shell(link)

        lines = shell.drain_notifications()

        assert lines == ["Logged in as alice (elo 1200)"]

    def test_auth_error_is_formatted(self):
        link = ClientLink()
        link.inbound_shell.put(m.AuthError(reason="bad_credentials"))
        shell = Shell(link)

        assert shell.drain_notifications() == ["Auth failed: bad_credentials"]

    def test_match_timed_out_is_formatted(self):
        link = ClientLink()
        link.inbound_shell.put(m.MatchTimedOut())
        shell = Shell(link)

        assert shell.drain_notifications() == ["Matchmaking timed out, still searching."]

    def test_room_created_is_formatted(self):
        link = ClientLink()
        link.inbound_shell.put(m.RoomCreated(room_id="abc123"))
        shell = Shell(link)

        assert shell.drain_notifications() == ["Room created: abc123"]

    def test_room_error_is_formatted(self):
        link = ClientLink()
        link.inbound_shell.put(m.RoomError(room_id="abc123", reason="room_not_found"))
        shell = Shell(link)

        assert shell.drain_notifications() == ["Room error: room_not_found"]

    def test_multiple_queued_messages_are_drained_in_order(self):
        link = ClientLink()
        link.inbound_shell.put(m.AuthOk(user_id=1, username="a", elo=1200))
        link.inbound_shell.put(m.RoomCreated(room_id="xyz"))
        shell = Shell(link)

        assert shell.drain_notifications() == ["Logged in as a (elo 1200)", "Room created: xyz"]


class TestActiveRoomTracking:
    def test_match_found_sets_active_room(self):
        link = ClientLink()
        link.inbound_shell.put(m.MatchFound(room_id="abc123", color="white"))
        shell = Shell(link)

        shell.drain_notifications()

        assert shell.active_room == ActiveRoom(room_id="abc123", role="white")

    def test_room_joined_sets_active_room(self):
        link = ClientLink()
        link.inbound_shell.put(m.RoomJoined(room_id="abc123", role="black", players=["a", "b"]))
        shell = Shell(link)

        shell.drain_notifications()

        assert shell.active_room == ActiveRoom(room_id="abc123", role="black")

    def test_room_created_alone_does_not_set_active_room(self):
        link = ClientLink()
        link.inbound_shell.put(m.RoomCreated(room_id="abc123"))
        shell = Shell(link)

        shell.drain_notifications()

        assert shell.active_room is None

    def test_no_active_room_before_any_notification(self):
        shell = Shell(ClientLink())

        assert shell.active_room is None
