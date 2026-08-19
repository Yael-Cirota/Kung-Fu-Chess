import asyncio

from common.config.schema import AppConfig
from common.events import EventNames, InMemoryEventBus
from common.tracing import SequentialTraceIdGenerator
from server.domain.room_directory import InMemoryRoomDirectory
from server.roles.room import build_room_server


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


def make_room_server(bus=None, directory=None, server_id="room-server-1"):
    return build_room_server(
        AppConfig(),
        FakeWebSocketManager(),
        bus if bus is not None else InMemoryEventBus(),
        SequentialTraceIdGenerator(),
        directory if directory is not None else InMemoryRoomDirectory(),
        server_id,
    )


class TestCreateRoom:
    def test_registers_the_room_locally(self):
        server = make_room_server()

        room = asyncio.run(server.create_room("room-1", now_ms=0))

        assert server.rooms["room-1"] is room

    def test_claims_a_lease_under_this_servers_id(self):
        directory = InMemoryRoomDirectory()
        server = make_room_server(directory=directory, server_id="room-server-1")

        asyncio.run(server.create_room("room-1", now_ms=0))

        lease = asyncio.run(directory.resolve("room-1"))
        assert lease.server_id == "room-server-1"
        assert lease.lease_epoch == 1


class TestTickingAndRenewal:
    def test_a_created_room_advances_its_clock_when_ticked(self):
        server = make_room_server()
        asyncio.run(server.create_room("room-1", now_ms=0))

        asyncio.run(server.ticker.tick(now_ms=0))
        asyncio.run(server.ticker.tick(now_ms=50))

        assert server.rooms["room-1"].session.clock_ms > 0

    def test_survives_many_ticks_past_the_renewal_interval(self):
        server = make_room_server()
        asyncio.run(server.create_room("room-1", now_ms=0))

        for now_ms in range(0, 10001, 500):
            asyncio.run(server.ticker.tick(now_ms=now_ms))

        assert "room-1" in server.rooms


class TestLosingTheLease:
    def test_a_reclaim_by_another_server_abandons_the_room_on_next_renewal(self):
        bus = InMemoryEventBus()
        received = []
        bus.subscribe(EventNames.GAME_OVER, recorder(received))
        directory = InMemoryRoomDirectory()
        server = make_room_server(bus=bus, directory=directory, server_id="room-server-1")
        asyncio.run(server.create_room("room-1", now_ms=0))

        # A partition: another room-server reclaims the room, bumping the epoch.
        asyncio.run(directory.claim("room-1", "room-server-2"))

        asyncio.run(server.ticker.tick(now_ms=2000))  # renewal is due and now fails

        assert "room-1" not in server.rooms
        assert len(received) == 1
        assert received[0].payload["reason"] == "server_fault"
