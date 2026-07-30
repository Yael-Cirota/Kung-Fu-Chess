from client.net.client_link import ClientLink
from protocol import messages as m


class TestSend:
    def test_send_enqueues_onto_outbound(self):
        link = ClientLink()

        link.send("move-request")

        assert link.outbound.get_nowait() == "move-request"


class TestDrainGame:
    def test_drains_everything_currently_queued_in_order(self):
        link = ClientLink()
        link.inbound_game.put("a")
        link.inbound_game.put("b")

        assert link.drain_game() == ["a", "b"]

    def test_an_empty_queue_drains_to_an_empty_list(self):
        link = ClientLink()
        assert link.drain_game() == []

    def test_draining_leaves_the_queue_empty(self):
        link = ClientLink()
        link.inbound_game.put("a")
        link.drain_game()

        assert link.drain_game() == []


class TestDrainShell:
    def test_drains_independently_of_inbound_game(self):
        link = ClientLink()
        link.inbound_game.put("game-message")
        link.inbound_shell.put("shell-message")

        assert link.drain_shell() == ["shell-message"]
        assert link.drain_game() == ["game-message"]


class TestReceive:
    def test_routes_a_game_message_onto_inbound_game(self):
        link = ClientLink()

        link.receive(m.HeartbeatAck(client_ms=1, server_ms=2))

        assert link.drain_game() == [m.HeartbeatAck(client_ms=1, server_ms=2)]
        assert link.drain_shell() == []

    def test_routes_a_shell_message_onto_inbound_shell(self):
        link = ClientLink()

        link.receive(m.AuthOk(user_id=1, username="a", elo=1200))

        assert link.drain_shell() == [m.AuthOk(user_id=1, username="a", elo=1200)]
        assert link.drain_game() == []
