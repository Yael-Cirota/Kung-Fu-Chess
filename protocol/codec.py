"""JSON <-> messages <-> kfchess DTOs. The only place that knows the wire
envelope shape ({"type": ..., "payload": ...}); everything else works with
the frozen dataclasses in protocol.messages."""

import dataclasses
import json
import typing
from typing import Any, Dict, Type

from protocol import messages as m
from protocol.errors import ProtocolError

_TYPE_TO_CLASS: Dict[str, Type] = {
    "login_request": m.LoginRequest,
    "register_request": m.RegisterRequest,
    "play_request": m.PlayRequest,
    "cancel_queue_request": m.CancelQueueRequest,
    "create_room_request": m.CreateRoomRequest,
    "join_room_request": m.JoinRoomRequest,
    "leave_room_request": m.LeaveRoomRequest,
    "move_request": m.MoveRequest,
    "heartbeat": m.Heartbeat,
    "auth_ok": m.AuthOk,
    "auth_error": m.AuthError,
    "match_found": m.MatchFound,
    "match_timed_out": m.MatchTimedOut,
    "room_created": m.RoomCreated,
    "room_joined": m.RoomJoined,
    "game_started": m.GameStarted,
    "state_update": m.StateUpdate,
    "move_ack": m.MoveAck,
    "opponent_disconnected": m.OpponentDisconnected,
    "opponent_reconnected": m.OpponentReconnected,
    "game_ended": m.GameEnded,
    "heartbeat_ack": m.HeartbeatAck,
    "delta_event": m.DeltaEvent,
}
_CLASS_TO_TYPE = {cls: name for name, cls in _TYPE_TO_CLASS.items()}


def encode(message: Any) -> str:
    """Message -> wire JSON string."""
    type_name = _CLASS_TO_TYPE[type(message)]
    payload = dataclasses.asdict(message)
    return json.dumps({"type": type_name, "payload": payload})


def decode(raw: str) -> Any:
    """Wire JSON string -> message. Raises ProtocolError on anything that
    isn't a well-formed, known, schema-matching frame."""
    try:
        envelope = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        raise ProtocolError(ProtocolError.MALFORMED_JSON)

    if not isinstance(envelope, dict) or "type" not in envelope or "payload" not in envelope:
        raise ProtocolError(ProtocolError.MALFORMED_JSON)

    cls = _TYPE_TO_CLASS.get(envelope["type"])
    if cls is None:
        raise ProtocolError(ProtocolError.UNKNOWN_TYPE)

    try:
        return _from_dict(cls, envelope["payload"])
    except (TypeError, KeyError, AttributeError):
        raise ProtocolError(ProtocolError.SCHEMA_MISMATCH)


def _from_dict(field_type: Any, data: Any) -> Any:
    if dataclasses.is_dataclass(field_type):
        if not isinstance(data, dict):
            raise ProtocolError(ProtocolError.SCHEMA_MISMATCH)
        hints = typing.get_type_hints(field_type)
        kwargs = {f.name: _from_dict(hints[f.name], data[f.name]) for f in dataclasses.fields(field_type)}
        return field_type(**kwargs)

    origin = typing.get_origin(field_type)
    if origin is list:
        if not isinstance(data, list):
            raise ProtocolError(ProtocolError.SCHEMA_MISMATCH)
        (item_type,) = typing.get_args(field_type)
        return [_from_dict(item_type, item) for item in data]

    if origin is typing.Union:
        non_none = [a for a in typing.get_args(field_type) if a is not type(None)]
        if data is None:
            return None
        return _from_dict(non_none[0], data)

    return data
