"""Redis-backed `RoomDirectory` (Server_Design.md §2/§8). Stores one string
key per room - `room:<room_id> -> "<server_id>:<lease_epoch>"` with a TTL - and
never uses a Lua script: every primitive here is a plain GET/SET/DELETE so the
tests can drive it through a small hand-written fake client instead of a
mocking framework (CLAUDE.md §3), matching how every other infra seam in this
codebase is tested.

That choice has a cost: `renew`/`release`/`claim` are each a GET followed by a
conditional SET, not a single atomic compare-and-swap, so there is a narrow
TOCTOU window between the two calls where a concurrent claimant could win the
race. Closing it fully needs a Lua `EVAL` script or a WATCH/MULTI transaction,
deferred - the race window is a couple of Redis round-trips, not the seconds-
wide partition scenario the lease TTL itself defends against, so it is an
acceptable gap for this pass rather than the mechanism this pass is built to
prove out."""

from typing import Optional

from server.domain.room_directory import RoomLease

_KEY_PREFIX = "room:"
_DEFAULT_TTL_SECONDS = 6  # Server_Design.md §8: heartbeat every 2s, TTL 6s


class RedisRoomDirectory:
    def __init__(self, client, ttl_seconds: int = _DEFAULT_TTL_SECONDS):
        self._client = client
        self._ttl_seconds = ttl_seconds

    async def claim(self, room_id: str, server_id: str) -> RoomLease:
        key = _key(room_id)
        current_raw = await self._client.get(key)
        lease_epoch = _decode_epoch(current_raw) + 1
        await self._client.set(key, _encode(server_id, lease_epoch), ex=self._ttl_seconds)
        return RoomLease(room_id=room_id, server_id=server_id, lease_epoch=lease_epoch)

    async def renew(self, room_id: str, server_id: str, lease_epoch: int) -> bool:
        key = _key(room_id)
        expected = _encode(server_id, lease_epoch)
        current = await self._client.get(key)
        if current != expected:
            return False
        result = await self._client.set(key, expected, xx=True, ex=self._ttl_seconds)
        return result is not None

    async def resolve(self, room_id: str) -> Optional[RoomLease]:
        raw = await self._client.get(_key(room_id))
        if raw is None:
            return None
        server_id, lease_epoch = _decode(raw)
        return RoomLease(room_id=room_id, server_id=server_id, lease_epoch=lease_epoch)

    async def release(self, room_id: str, server_id: str, lease_epoch: int) -> None:
        key = _key(room_id)
        expected = _encode(server_id, lease_epoch)
        current = await self._client.get(key)
        if current == expected:
            await self._client.delete(key)


def _key(room_id: str) -> str:
    return f"{_KEY_PREFIX}{room_id}"


def _encode(server_id: str, lease_epoch: int) -> str:
    return f"{server_id}:{lease_epoch}"


def _decode(raw: str) -> "tuple[str, int]":
    server_id, _, epoch_str = raw.rpartition(":")
    return server_id, int(epoch_str)


def _decode_epoch(raw: Optional[str]) -> int:
    return 0 if raw is None else _decode(raw)[1]
