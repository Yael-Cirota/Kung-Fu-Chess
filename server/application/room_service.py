import secrets
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol, runtime_checkable

from common.result import Result


@dataclass(frozen=True)
class PlayerRef:
    user_id: int
    username: str


@dataclass
class Room:
    """Seat assignment is by join order: P1=White, P2=Black, P3+=Viewer."""

    room_id: str
    players: List[PlayerRef] = field(default_factory=list)

    def role_for_index(self, index: int) -> str:
        if index == 0:
            return "white"
        if index == 1:
            return "black"
        return "viewer"


@dataclass(frozen=True)
class JoinResult:
    room: Room
    role: str


class RoomErrorReason:
    ROOM_NOT_FOUND = "room_not_found"
    ROOM_FULL = "room_full"


@runtime_checkable
class RoomIdGenerator(Protocol):
    def next_id(self) -> str: ...


class SequentialRoomIdGenerator:
    """Test double: deterministic, collision-free within a test run."""

    def __init__(self):
        self._counter = 0

    def next_id(self) -> str:
        self._counter += 1
        return f"room-{self._counter}"


class SecretsRoomIdGenerator:
    """Production generator: unguessable room ids, so a room cannot be joined
    by anyone who was not told its id. `length` is in characters; token_hex
    yields two characters per byte, hence the round-up."""

    def __init__(self, length: int = 6):
        self._length = length

    def next_id(self) -> str:
        return secrets.token_hex((self._length + 1) // 2)[: self._length]


class RoomService:
    def __init__(self, id_generator: RoomIdGenerator, max_viewers: int = 8):
        self._id_generator = id_generator
        self._max_viewers = max_viewers
        self._rooms: Dict[str, Room] = {}

    def create(self, host: PlayerRef) -> Room:
        room = Room(room_id=self._id_generator.next_id(), players=[host])
        self._rooms[room.room_id] = room
        return room

    def join(self, room_id: str, player: PlayerRef) -> Result[JoinResult]:
        room = self._rooms.get(room_id)
        if room is None:
            return Result.failure(RoomErrorReason.ROOM_NOT_FOUND)
        if len(room.players) >= 2 + self._max_viewers:
            return Result.failure(RoomErrorReason.ROOM_FULL)

        room.players.append(player)
        role = room.role_for_index(len(room.players) - 1)
        return Result.success(JoinResult(room=room, role=role))

    def cancel(self, room_id: str, user_id: int) -> None:
        room = self._rooms.get(room_id)
        if room is None:
            return
        room.players = [p for p in room.players if p.user_id != user_id]
        if not room.players:
            self._rooms.pop(room_id, None)

    def get(self, room_id: str) -> Optional[Room]:
        return self._rooms.get(room_id)
