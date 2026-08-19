import asyncio

from common.events import EventNames, InMemoryEventBus
from server.application.game_room import create_game_room
from server.application.room_server_ticker import RoomServerTicker
from server.domain.room_directory import InMemoryRoomDirectory


class FakeWebSocketManager:
    def register(self, conn):
        pass

    def unregister(self, conn_id):
        pass

    def send_to(self, conn_id, raw):
        pass

    def broadcast(self, conn_ids, raw):
        pass

    def connection_ids(self):
        return []


def recorder(sink):
    async def handler(event):
        sink.append(event)

    return handler


class SpyRoomDirectory(InMemoryRoomDirectory):
    def __init__(self):
        super().__init__()
        self.renew_calls = 0

    async def renew(self, room_id, server_id, lease_epoch):
        self.renew_calls += 1
        return await super().renew(room_id, server_id, lease_epoch)


def make_room(room_id="room-1", bus=None):
    return create_game_room(room_id, "wR . .\n. . .\n. . .", FakeWebSocketManager(), bus=bus)


class TestTrackedRoomsAreTicked:
    def test_tracked_room_advances_its_clock(self):
        room = make_room()
        rooms = {"room-1": room}
        directory = InMemoryRoomDirectory()
        lease = asyncio.run(directory.claim("room-1", "server-a"))
        ticker = RoomServerTicker(rooms, directory, "server-a")
        ticker.track(lease, now_ms=0)

        asyncio.run(ticker.tick(now_ms=0))
        asyncio.run(ticker.tick(now_ms=50))

        assert room.session.clock_ms > 0

    def test_untracked_room_is_left_alone(self):
        # A room present in `rooms` but never handed to track() isn't this
        # ticker's concern - see the module docstring.
        room = make_room()
        rooms = {"room-1": room}
        directory = InMemoryRoomDirectory()
        ticker = RoomServerTicker(rooms, directory, "server-a")

        asyncio.run(ticker.tick(now_ms=0))

        assert room.session.clock_ms == 0
        assert "room-1" in rooms


class TestRenewalIsThrottled:
    def test_renewal_only_happens_once_the_interval_elapses(self):
        room = make_room()
        rooms = {"room-1": room}
        directory = SpyRoomDirectory()
        lease = asyncio.run(directory.claim("room-1", "server-a"))
        ticker = RoomServerTicker(rooms, directory, "server-a", renew_interval_ms=2000)
        ticker.track(lease, now_ms=0)

        for now_ms in (0, 500, 1000, 2000, 2500):
            asyncio.run(ticker.tick(now_ms=now_ms))

        assert directory.renew_calls == 1


class TestRenewalFailureAbandonsTheRoom:
    def test_lost_lease_ends_the_game_and_drops_the_room(self):
        bus = InMemoryEventBus()
        received = []
        bus.subscribe(EventNames.GAME_OVER, recorder(received))
        room = make_room(bus=bus)
        rooms = {"room-1": room}
        directory = InMemoryRoomDirectory()
        lease = asyncio.run(directory.claim("room-1", "server-a"))
        ticker = RoomServerTicker(rooms, directory, "server-a", renew_interval_ms=1000)
        ticker.track(lease, now_ms=0)

        # A partition: another server reclaims the room, bumping the epoch
        # past what "server-a" is still trying to renew.
        asyncio.run(directory.claim("room-1", "server-b"))

        asyncio.run(ticker.tick(now_ms=1000))  # renewal is due and now fails

        assert "room-1" not in rooms
        assert len(received) == 1
        assert received[0].payload["reason"] == "server_fault"

    def test_a_second_tick_after_abandonment_does_not_re_renew(self):
        directory = SpyRoomDirectory()
        room = make_room()
        rooms = {"room-1": room}
        lease = asyncio.run(directory.claim("room-1", "server-a"))
        ticker = RoomServerTicker(rooms, directory, "server-a", renew_interval_ms=1000)
        ticker.track(lease, now_ms=0)
        asyncio.run(directory.claim("room-1", "server-b"))

        asyncio.run(ticker.tick(now_ms=1000))  # abandons and drops the room
        calls_after_abandon = directory.renew_calls
        asyncio.run(ticker.tick(now_ms=2000))

        assert directory.renew_calls == calls_after_abandon
