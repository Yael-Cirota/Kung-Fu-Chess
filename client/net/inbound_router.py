"""Decides which ClientLink queue a decoded inbound message belongs on (see
'Client threading model'): `inbound_game` feeds RemoteGameSession.wait() every
render frame, `inbound_shell` feeds the REPL's per-iteration notification
drain. A pure lookup so the routing rule is unit-testable without a real
websocket - ws_client.py is the only caller."""

from enum import Enum

from protocol import messages as m


class InboundQueue(Enum):
    GAME = "game"
    SHELL = "shell"


_MESSAGE_TYPE_TO_QUEUE = {
    m.GameStarted: InboundQueue.GAME,
    m.StateUpdate: InboundQueue.GAME,
    m.MoveAck: InboundQueue.GAME,
    m.GameEnded: InboundQueue.GAME,
    m.OpponentDisconnected: InboundQueue.GAME,
    m.OpponentReconnected: InboundQueue.GAME,
    m.HeartbeatAck: InboundQueue.GAME,
    m.DeltaEvent: InboundQueue.GAME,
    m.AuthOk: InboundQueue.SHELL,
    m.AuthError: InboundQueue.SHELL,
    m.MatchFound: InboundQueue.SHELL,
    m.MatchTimedOut: InboundQueue.SHELL,
    m.RoomCreated: InboundQueue.SHELL,
    m.RoomJoined: InboundQueue.SHELL,
    m.RoomError: InboundQueue.SHELL,
}


def route(message: object) -> InboundQueue:
    """Every S->C message type must appear in the table above; an unmapped
    type is a programming error (a new message added to protocol/messages.py
    without an entry here), not a runtime condition to swallow."""
    return _MESSAGE_TYPE_TO_QUEUE[type(message)]
