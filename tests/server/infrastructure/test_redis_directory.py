import asyncio
from typing import Dict, Optional

from server.domain.room_directory import RoomDirectory
from server.infrastructure.redis_directory import RedisRoomDirectory


class FakeRedisClient:
    """Just enough of `redis.asyncio.Redis` for RedisRoomDirectory: string
    GET/SET (with `xx`/`ex`) and DELETE. No TTL expiry is simulated - nothing
    under test relies on wall-clock expiry, only on the value comparisons the
    directory itself performs."""

    def __init__(self):
        self._values: Dict[str, str] = {}

    async def get(self, key: str) -> Optional[str]:
        return self._values.get(key)

    async def set(self, key: str, value: str, ex=None, nx=False, xx=False):
        exists = key in self._values
        if nx and exists:
            return None
        if xx and not exists:
            return None
        self._values[key] = value
        return True

    async def delete(self, key: str) -> None:
        self._values.pop(key, None)


def make_directory():
    return RedisRoomDirectory(FakeRedisClient(), ttl_seconds=6)


class TestClaim:
    def test_first_claim_mints_epoch_one(self):
        directory = make_directory()
        lease = asyncio.run(directory.claim("room-1", "server-a"))

        assert lease.room_id == "room-1"
        assert lease.server_id == "server-a"
        assert lease.lease_epoch == 1

    def test_reclaim_mints_the_next_epoch(self):
        directory = make_directory()
        asyncio.run(directory.claim("room-1", "server-a"))
        lease = asyncio.run(directory.claim("room-1", "server-b"))

        assert lease.server_id == "server-b"
        assert lease.lease_epoch == 2

    def test_satisfies_the_protocol(self):
        assert isinstance(make_directory(), RoomDirectory)


class TestRenew:
    def test_renew_with_current_epoch_succeeds(self):
        directory = make_directory()
        lease = asyncio.run(directory.claim("room-1", "server-a"))

        assert asyncio.run(directory.renew("room-1", "server-a", lease.lease_epoch)) is True

    def test_renew_with_stale_epoch_fails(self):
        directory = make_directory()
        asyncio.run(directory.claim("room-1", "server-a"))
        asyncio.run(directory.claim("room-1", "server-b"))  # reclaim: epoch bumps to 2

        assert asyncio.run(directory.renew("room-1", "server-a", 1)) is False

    def test_renew_by_a_server_that_never_claimed_fails(self):
        directory = make_directory()
        asyncio.run(directory.claim("room-1", "server-a"))

        assert asyncio.run(directory.renew("room-1", "server-b", 1)) is False

    def test_renew_of_an_unknown_room_fails(self):
        directory = make_directory()
        assert asyncio.run(directory.renew("ghost", "server-a", 1)) is False

    def test_renew_refreshes_the_stored_value(self):
        # Regression guard: renew must SET(xx=True), not merely check-and-return -
        # otherwise a real Redis TTL would never be refreshed and every lease
        # would silently expire on schedule regardless of heartbeats.
        directory = make_directory()
        lease = asyncio.run(directory.claim("room-1", "server-a"))

        asyncio.run(directory.renew("room-1", "server-a", lease.lease_epoch))

        assert asyncio.run(directory.resolve("room-1")) == lease


class TestResolve:
    def test_resolve_unknown_room_returns_none(self):
        directory = make_directory()
        assert asyncio.run(directory.resolve("ghost")) is None

    def test_resolve_returns_the_current_lease(self):
        directory = make_directory()
        claimed = asyncio.run(directory.claim("room-1", "server-a"))

        assert asyncio.run(directory.resolve("room-1")) == claimed


class TestRelease:
    def test_release_removes_a_matching_lease(self):
        directory = make_directory()
        lease = asyncio.run(directory.claim("room-1", "server-a"))
        asyncio.run(directory.release("room-1", "server-a", lease.lease_epoch))

        assert asyncio.run(directory.resolve("room-1")) is None

    def test_release_with_a_stale_epoch_is_a_no_op(self):
        directory = make_directory()
        asyncio.run(directory.claim("room-1", "server-a"))
        asyncio.run(directory.claim("room-1", "server-b"))  # epoch bumps to 2

        asyncio.run(directory.release("room-1", "server-a", 1))  # server-a's old epoch

        assert asyncio.run(directory.resolve("room-1")) is not None

    def test_release_of_an_unknown_room_is_a_no_op(self):
        directory = make_directory()
        asyncio.run(directory.release("ghost", "server-a", 1))  # must not raise
