"""The websockets transport adapter: the only place this server touches a
real socket or `asyncio.sleep` (see 'VPL path stays free of networking' and
'the async layer is one dumb driver'). `WebSocketConnection` and
`handle_connection` are ordinary coroutines exercised in
tests/server/presentation/test_ws_server.py against a scripted fake
connection; only `run_server` - which calls `websockets.serve` against a real
socket and loops forever - is pragma'd, per this project's convention for
untestable entry-point glue."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional

import websockets

from common.clock import Clock, MonotonicClock
from server.domain.connection_id import ConnectionId

if TYPE_CHECKING:
    # Deferred: server.main is the composition root and imports this module
    # to build run_server's entry point, so an eager import here would cycle.
    from server.main import Server

SECONDS_PER_TICK_HZ = 1.0


class WebSocketConnection:
    """Adapts one `websockets` server connection to the `Connection`
    Protocol. `send` is non-blocking from the caller's thread/coroutine: it
    only enqueues, and `drain` is the single task that actually awaits
    `raw.send`, one frame at a time, in enqueue order - the FIFO-per-
    connection guarantee 'Event-driven broadcasting' depends on so a
    DeltaEvent can never be reordered behind the StateUpdate that follows
    it."""

    def __init__(self, raw_connection):
        self._raw = raw_connection
        self._queue: "asyncio.Queue[str]" = asyncio.Queue()

    @property
    def connection_id(self) -> ConnectionId:
        return ConnectionId(str(self._raw.id))

    def send(self, raw: str) -> None:
        # `handle_connection`, `GameRoom.tick`, and everything upstream of it
        # all run as coroutines on this same connection's event loop, so a
        # direct, synchronous enqueue is enough - `flush`'s `queue.join()`
        # needs the item counted immediately, not deferred to a future loop
        # iteration the way `call_soon_threadsafe` would.
        self._queue.put_nowait(raw)

    def close(self) -> None:
        asyncio.ensure_future(self._raw.close())

    async def drain(self) -> None:
        while True:
            raw = await self._queue.get()
            await self._raw.send(raw)
            self._queue.task_done()

    async def flush(self) -> None:
        """Waits until every frame enqueued so far has actually been sent -
        called once on disconnect so a response to the client's last message
        isn't dropped by cancelling `drain` out from under it."""
        await self._queue.join()


async def handle_connection(raw_connection, server: Server, clock: Optional[Clock] = None) -> None:
    """One coroutine per accepted connection: register, pump inbound frames
    through the dispatcher, send back whatever it returns, and unregister on
    disconnect - the accept-loop body `websockets.serve` calls per client."""
    clock = clock if clock is not None else MonotonicClock()
    connection = WebSocketConnection(raw_connection)
    server.websocket_manager.register(connection)
    sender_task = asyncio.ensure_future(connection.drain())
    try:
        async for raw in raw_connection:
            response = await server.dispatcher.dispatch(connection.connection_id, raw, clock.now_ms())
            if response is not None:
                connection.send(response)
    finally:
        await connection.flush()
        sender_task.cancel()
        server.websocket_manager.unregister(connection.connection_id)


async def tick_forever(server: Server, clock: Optional[Clock] = None) -> None:
    """The one place `asyncio.sleep` appears: every timeout in this design
    (matchmaking, heartbeat, disconnect grace) is instead a synchronous
    `tick(now_ms)` sweep against stored deadlines (see 'Timeouts without real
    waiting') - this loop is just what calls `tick` on a cadence."""
    clock = clock if clock is not None else MonotonicClock()
    interval_s = SECONDS_PER_TICK_HZ / server.config.server.tick_hz
    while True:
        await server.ticker.tick(clock.now_ms())
        await asyncio.sleep(interval_s)


async def run_server(server: Server) -> None:  # pragma: no cover - real socket + infinite loop
    """Accepts connections forever while the tick driver runs alongside it.
    Never awaited to completion; the process is killed to stop it."""
    async with websockets.serve(
        lambda raw_connection: handle_connection(raw_connection, server),
        server.config.server.host,
        server.config.server.port,
    ):
        await tick_forever(server)
