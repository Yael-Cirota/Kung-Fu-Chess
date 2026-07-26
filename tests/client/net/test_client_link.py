from client.net.client_link import ClientLink


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
