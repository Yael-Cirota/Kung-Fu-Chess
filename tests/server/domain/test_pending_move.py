from kfchess.api import Position
from server.domain.connection_id import ConnectionId
from server.domain.pending_move import PendingMove


def test_holds_the_given_fields():
    move = PendingMove(
        color="w",
        from_pos=Position(0, 0),
        to_pos=Position(0, 2),
        client_seq=3,
        connection_id=ConnectionId("conn-1"),
        trace_id="trace-1",
    )
    assert move.color == "w"
    assert move.from_pos == Position(0, 0)
    assert move.client_seq == 3
    assert move.trace_id == "trace-1"


def test_trace_id_defaults_to_none():
    move = PendingMove(
        color="b", from_pos=Position(0, 0), to_pos=Position(0, 1),
        client_seq=1, connection_id=ConnectionId("conn-1"),
    )
    assert move.trace_id is None
