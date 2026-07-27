import pytest

from client.net.inbound_router import InboundQueue, route
from protocol import messages as m


class TestRoute:
    @pytest.mark.parametrize(
        "message",
        [
            m.GameStarted(server_ms=0, rows=8, cols=8),
            m.StateUpdate(server_ms=0, seq=0, pieces=[], motions=[], move_log=[], scoreboard=None, game_over=False),
            m.MoveAck(client_seq=1, accepted=True),
            m.GameEnded(winner="white", reason="king_captured", elo_delta=8),
            m.OpponentDisconnected(deadline_server_ms=1000),
            m.OpponentReconnected(),
            m.HeartbeatAck(client_ms=1, server_ms=2),
            m.DeltaEvent(
                kind="piece_captured", trace_id=None, at_ms=0, piece=None,
                from_pos=None, to_pos=None, captured=None, beneficiary_color=None, scoreboard=None,
            ),
        ],
    )
    def test_game_messages_route_to_the_game_queue(self, message):
        assert route(message) is InboundQueue.GAME

    @pytest.mark.parametrize(
        "message",
        [
            m.AuthOk(user_id=1, username="a", elo=1200),
            m.AuthError(reason="bad_credentials"),
            m.MatchFound(room_id="abc123", color="white"),
            m.MatchTimedOut(),
            m.RoomCreated(room_id="abc123"),
            m.RoomJoined(room_id="abc123", role="black", players=["a", "b"]),
            m.RoomError(room_id="abc123", reason="room_not_found"),
        ],
    )
    def test_shell_messages_route_to_the_shell_queue(self, message):
        assert route(message) is InboundQueue.SHELL
