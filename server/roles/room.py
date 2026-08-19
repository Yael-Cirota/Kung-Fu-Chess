"""Server_Design.md §2: the room-server role. Bundles room creation (via the
shared `room_factory`), the `rooms` dict, and lease-epoch fencing
(`RoomServerTicker` + `RoomDirectory`, §8) into the object graph a standalone
room-server process would run.

No `if __name__ == "__main__":` yet, deliberately. A room-server only ever
receives rooms to run via the ADR-001 gateway relay - the persistent
connection a gateway opens to hand off client-room membership - and that
relay doesn't exist in this codebase yet (see `server/roles/gateway.py`).
Running this module as a standalone process today would build a correct,
tested object graph with nothing to ever call `create_room` on it: not a bug,
but not worth a `__main__` that would spin forever doing nothing, since that
reads as "done" when it isn't. `RoomServer.create_room` is exercised directly
by tests instead, proving the claim -> track -> tick -> renew -> abandon
lifecycle end-to-end without needing the relay to drive it."""

from typing import Dict

from common.config.schema import AppConfig
from common.events import EventBus
from common.tracing import TraceIdGenerator
from server.application.game_room import GameRoom
from server.application.room_factory import build_room_factory
from server.application.room_server_ticker import RoomServerTicker
from server.domain.room_directory import RoomDirectory
from server.domain.websocket_port import WebSocketManager


class RoomServer:
    def __init__(self, rooms, ticker, directory, server_id, room_factory):
        self.rooms: Dict[str, GameRoom] = rooms
        self.ticker = ticker
        self.directory = directory
        self.server_id = server_id
        self._room_factory = room_factory

    async def create_room(self, room_id: str, now_ms: int) -> GameRoom:
        """Claims the room under this server's id before the room is even
        registered locally - `RoomServerTicker.tick` only renews rooms handed
        to `track`, so claim-then-track-then-register is the order that keeps
        every room in `self.rooms` covered by a lease from the moment it's
        reachable. The reverse order (register first) would let a live room
        sit in `self.rooms` for one tick before it has a tracked lease, and
        `tick` silently skips untracked rooms rather than ticking them
        unfenced - worse than this order's actual failure mode, which is: if
        `directory.claim` raises, nothing is registered locally at all, and
        the directory is left holding a lease nothing will ever renew. On
        real Redis that lease simply expires on its TTL; there is no local
        state to clean up either way."""
        room = self._room_factory(room_id)
        lease = await self.directory.claim(room_id, self.server_id)
        self.ticker.track(lease, now_ms)
        self.rooms[room_id] = room
        return room


def build_room_server(
    config: AppConfig,
    websocket_manager: WebSocketManager,
    bus: EventBus,
    trace_id_generator: TraceIdGenerator,
    directory: RoomDirectory,
    server_id: str,
) -> RoomServer:
    rooms: Dict[str, GameRoom] = {}
    ticker = RoomServerTicker(rooms, directory, server_id)
    room_factory = build_room_factory(config, websocket_manager, bus, trace_id_generator)
    return RoomServer(rooms, ticker, directory, server_id, room_factory)
