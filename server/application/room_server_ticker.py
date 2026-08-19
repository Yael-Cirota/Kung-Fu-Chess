"""The room-server's own tick loop (Server_Design.md §2/§8) - room ticking
plus lease renewal only. Deliberately narrower than today's `RoomTicker`,
which also drives `connection_monitor`/`disconnect_policy`/
`matchmaking_service`: those are gateway and matchmaker concerns that a real
room-server, reached only via the ADR-001 relay, has no business owning.
`RoomTicker` stays as the monolith's tick loop; this is what a standalone
room-server process runs instead.

Renewal is throttled to `renew_interval_ms` (default 2000, matching §8's "every
2s, TTL 6s") rather than happening on every call to `tick` - the room engine
itself needs frequent ticks to keep its simulated clock from drifting behind
wall time (`GameRoom.tick`'s `dt` is capped by `max_engine_step_ms`), but
renewal is a heartbeat, not a per-tick check. Same throttling shape as
`GameRoom._broadcast_interval_ms`."""

from dataclasses import dataclass
from typing import Dict

from server.application.game_room import GameRoom
from server.domain.room_directory import RoomDirectory, RoomLease

_DEFAULT_RENEW_INTERVAL_MS = 2000


@dataclass
class _Tracked:
    lease: RoomLease
    last_renew_ms: int


class RoomServerTicker:
    def __init__(
        self,
        rooms: Dict[str, GameRoom],
        directory: RoomDirectory,
        server_id: str,
        renew_interval_ms: int = _DEFAULT_RENEW_INTERVAL_MS,
    ):
        self._rooms = rooms
        self._directory = directory
        self._server_id = server_id
        self._renew_interval_ms = renew_interval_ms
        # One entry per tracked room, lease and last-renewal time together -
        # a room can never have a lease without a renewal clock or vice versa.
        self._tracked: Dict[str, _Tracked] = {}

    def track(self, lease: RoomLease, now_ms: int) -> None:
        """Registers the lease minted when a room was claimed (at creation
        time, outside this class - see server/roles/room.py), so this
        ticker's renewals know which epoch to prove."""
        self._tracked[lease.room_id] = _Tracked(lease=lease, last_renew_ms=now_ms)

    async def tick(self, now_ms: int) -> None:
        for room_id, room in list(self._rooms.items()):
            tracked = self._tracked.get(room_id)
            if tracked is None:
                continue  # tracked by a caller that hasn't claimed yet - not this ticker's concern

            due = now_ms - tracked.last_renew_ms >= self._renew_interval_ms
            if due and not await self._directory.renew(room_id, self._server_id, tracked.lease.lease_epoch):
                # Server_Design.md §8: lost the lease - don't recover, abandon.
                await room.abandon()
                del self._rooms[room_id]
                del self._tracked[room_id]
                continue
            if due:
                tracked.last_renew_ms = now_ms

            await room.tick(now_ms)
