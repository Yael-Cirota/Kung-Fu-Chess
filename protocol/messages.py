"""Frozen wire-format dataclasses, discriminated by a `type` string in codec.py.
Reuses kfchess.api DTOs directly for board/motion/score payloads rather than
re-declaring a parallel vocabulary."""

from dataclasses import dataclass
from typing import List, Optional

from kfchess.api.dto import MotionInfo, MoveLogEntry, PieceView, Position, Scoreboard

# --- Client -> Server ---


@dataclass(frozen=True)
class LoginRequest:
    username: str
    password: str


@dataclass(frozen=True)
class RegisterRequest:
    username: str
    password: str


@dataclass(frozen=True)
class PlayRequest:
    pass


@dataclass(frozen=True)
class CancelQueueRequest:
    pass


@dataclass(frozen=True)
class CreateRoomRequest:
    pass


@dataclass(frozen=True)
class JoinRoomRequest:
    room_id: str


@dataclass(frozen=True)
class LeaveRoomRequest:
    room_id: str


@dataclass(frozen=True)
class MoveRequest:
    from_row: int
    from_col: int
    to_row: int
    to_col: int
    client_seq: int


@dataclass(frozen=True)
class Heartbeat:
    client_ms: int


# --- Server -> Client ---


@dataclass(frozen=True)
class AuthOk:
    user_id: int
    username: str
    elo: int


@dataclass(frozen=True)
class AuthError:
    reason: str


@dataclass(frozen=True)
class MatchFound:
    room_id: str
    color: str


@dataclass(frozen=True)
class MatchTimedOut:
    pass


@dataclass(frozen=True)
class RoomCreated:
    room_id: str


@dataclass(frozen=True)
class RoomJoined:
    room_id: str
    role: str
    players: List[str]


@dataclass(frozen=True)
class GameStarted:
    server_ms: int
    rows: int
    cols: int


@dataclass(frozen=True)
class MotionEntry:
    """A piece's in-flight motion, keyed by piece_id for the wire (JSON has no
    tuple/object keys, so this stands in for a Dict[int, MotionInfo])."""

    piece_id: int
    motion: MotionInfo


@dataclass(frozen=True)
class StateUpdate:
    """The sole authority for position - carries the full board and motion
    set, never a delta. server_ms is session.clock_ms at emit time."""

    server_ms: int
    seq: int
    pieces: List[PieceView]
    motions: List[MotionEntry]
    move_log: List[MoveLogEntry]
    scoreboard: Scoreboard
    game_over: bool


@dataclass(frozen=True)
class MoveAck:
    client_seq: int
    accepted: bool
    reason: Optional[str] = None


@dataclass(frozen=True)
class OpponentDisconnected:
    deadline_server_ms: int


@dataclass(frozen=True)
class OpponentReconnected:
    pass


@dataclass(frozen=True)
class GameEnded:
    winner: Optional[str]
    reason: str
    elo_delta: int


@dataclass(frozen=True)
class HeartbeatAck:
    client_ms: int
    server_ms: int


@dataclass(frozen=True)
class DeltaEvent:
    """Advisory-only notification of one domain event, sent outside the
    broadcast_hz cadence. Never carries enough information to reconstruct
    board state - StateUpdate remains the sole authority for position."""

    kind: str
    trace_id: Optional[str]
    at_ms: int
    piece: Optional[PieceView]
    from_pos: Optional[Position]
    to_pos: Optional[Position]
    captured: Optional[PieceView]
    beneficiary_color: Optional[str]
    scoreboard: Scoreboard
