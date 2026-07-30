import asyncio

from common.clock import ManualClock
from server.domain.connection_id import ConnectionId
from server.presentation.connection import ConnectionRegistry
from server.presentation.ws_server import WebSocketConnection, handle_connection, tick_forever


class FakeRawConnection:
    """A scripted fake standing in for a websockets ServerConnection: `id`,
    an async-iterable of inbound frames, and recorded outbound sends."""

    def __init__(self, conn_id, incoming):
        self.id = conn_id
        self._incoming = list(incoming)
        self.sent = []
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._incoming:
            raise StopAsyncIteration
        return self._incoming.pop(0)

    async def send(self, raw):
        self.sent.append(raw)

    async def close(self):
        self.closed = True


class FakeDispatcher:
    def __init__(self, responses, websocket_manager=None):
        self._responses = responses
        self.calls = []
        self._websocket_manager = websocket_manager
        self.was_registered_during_call = []

    async def dispatch(self, conn_id, raw, now_ms):
        self.calls.append((conn_id, raw, now_ms))
        if self._websocket_manager is not None:
            self.was_registered_during_call.append(self._websocket_manager.get(conn_id) is not None)
        return self._responses.get(raw)


class FakeServer:
    def __init__(self, dispatcher):
        self.websocket_manager = ConnectionRegistry()
        self.dispatcher = dispatcher


class TestHandleConnection:
    def test_dispatches_every_inbound_frame_with_the_clocks_time(self):
        raw = FakeRawConnection("c1", ["hello", "world"])
        dispatcher = FakeDispatcher({"hello": None, "world": None})
        server = FakeServer(dispatcher)

        asyncio.run(handle_connection(raw, server, clock=ManualClock(1234)))

        assert dispatcher.calls == [
            (ConnectionId("c1"), "hello", 1234),
            (ConnectionId("c1"), "world", 1234),
        ]

    def test_registers_before_dispatching_and_unregisters_on_disconnect(self):
        raw = FakeRawConnection("c1", ["hello"])
        dispatcher = FakeDispatcher({"hello": None})
        server = FakeServer(dispatcher)
        dispatcher._websocket_manager = server.websocket_manager

        asyncio.run(handle_connection(raw, server, clock=ManualClock(0)))

        assert dispatcher.was_registered_during_call == [True]
        assert server.websocket_manager.get(ConnectionId("c1")) is None

    def test_a_non_none_response_is_sent_back_on_the_raw_connection(self):
        raw = FakeRawConnection("c1", ["move"])
        dispatcher = FakeDispatcher({"move": "move-ack"})
        server = FakeServer(dispatcher)

        asyncio.run(handle_connection(raw, server, clock=ManualClock(0)))

        assert raw.sent == ["move-ack"]

    def test_a_none_response_sends_nothing(self):
        raw = FakeRawConnection("c1", ["heartbeat"])
        dispatcher = FakeDispatcher({"heartbeat": None})
        server = FakeServer(dispatcher)

        asyncio.run(handle_connection(raw, server, clock=ManualClock(0)))

        assert raw.sent == []

    def test_multiple_responses_are_sent_in_the_order_they_were_produced(self):
        raw = FakeRawConnection("c1", ["a", "b", "c"])
        dispatcher = FakeDispatcher({"a": "resp-a", "b": None, "c": "resp-c"})
        server = FakeServer(dispatcher)

        asyncio.run(handle_connection(raw, server, clock=ManualClock(0)))

        assert raw.sent == ["resp-a", "resp-c"]


class FakeTicker:
    def __init__(self):
        self.calls = []

    async def tick(self, now_ms):
        self.calls.append(now_ms)


class FakeServerConfig:
    def __init__(self, tick_hz):
        self.tick_hz = tick_hz


class FakeAppConfig:
    def __init__(self, tick_hz):
        self.server = FakeServerConfig(tick_hz)


class FakeTickerServer:
    def __init__(self, tick_hz):
        self.config = FakeAppConfig(tick_hz)
        self.ticker = FakeTicker()


class TestTickForever:
    def test_calls_ticker_tick_repeatedly_with_the_clocks_time(self):
        server = FakeTickerServer(tick_hz=1000)  # 1ms interval - several ticks fit in the timeout

        async def scenario():
            try:
                await asyncio.wait_for(tick_forever(server, clock=ManualClock(5000)), timeout=0.05)
            except asyncio.TimeoutError:
                pass

        asyncio.run(scenario())

        assert len(server.ticker.calls) >= 2
        assert all(call == 5000 for call in server.ticker.calls)


class TestWebSocketConnection:
    def test_connection_id_wraps_the_raw_connections_id(self):
        raw = FakeRawConnection("abc", [])
        connection = WebSocketConnection(raw)
        assert connection.connection_id == ConnectionId("abc")

    def test_close_closes_the_raw_connection(self):
        raw = FakeRawConnection("abc", [])

        async def scenario():
            connection = WebSocketConnection(raw)
            connection.close()
            await asyncio.sleep(0)

        asyncio.run(scenario())

        assert raw.closed is True

    def test_send_then_flush_delivers_frames_in_fifo_order(self):
        raw = FakeRawConnection("abc", [])

        async def scenario():
            connection = WebSocketConnection(raw)
            connection.send("first")
            connection.send("second")
            drain_task = asyncio.ensure_future(connection.drain())
            await connection.flush()
            drain_task.cancel()

        asyncio.run(scenario())

        assert raw.sent == ["first", "second"]
