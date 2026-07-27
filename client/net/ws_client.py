"""The websockets transport adapter for the client side of 'Client threading
model': a background thread running its own asyncio loop, mirroring
server/presentation/ws_server.py's shape (send/receive coroutines plus one
dumb `asyncio.sleep` driver for heartbeats, matching tick_forever
server-side). Everything here is untestable without a real socket and is
pragma'd; `ClientLink` and `inbound_router` carry all the logic worth unit
testing."""

from __future__ import annotations

import asyncio
import threading
from typing import Callable, Optional

import websockets

from protocol import codec, messages as m
from client.net.client_link import ClientLink

_STOP_SENTINEL = object()

SECONDS_PER_MS = 1.0 / 1000


class WsClient:  # pragma: no cover - real socket + background thread
    """Owns the background thread's lifetime. `start` spawns a daemon thread
    running `_run`; `stop` asks that thread's loop to shut down and joins
    it, so a hard exit can never hang the process even if `stop` is never
    called.

    `clock_ms` must return elapsed time from the same origin
    `RemoteGameSession._apply` stamps `HeartbeatAck` receipt against (i.e.
    `RemoteGameSession.elapsed_ms`) - a HeartbeatAck's RTT compensation is
    only meaningful if send and receive timestamps share a clock. This
    thread has no RemoteGameSession of its own on purpose: it is a plain
    transport adapter, so the caller (client/main.py) injects the callable
    instead."""

    def __init__(self, server_url: str, link: ClientLink, clock_ms: Callable[[], int], heartbeat_interval_ms: int):
        self._server_url = server_url
        self._link = link
        self._clock_ms = clock_ms
        self._heartbeat_interval_ms = heartbeat_interval_ms
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        # Unblocks _send_loop's executor thread, which is parked on a
        # blocking queue.Queue.get() that task.cancel() cannot interrupt.
        self._link.outbound.put(_STOP_SENTINEL)
        if self._loop is not None and self._stop_event is not None:
            self._loop.call_soon_threadsafe(self._stop_event.set)
        if self._thread is not None:
            self._thread.join()

    def _run(self) -> None:
        asyncio.run(self._main())

    async def _main(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()

        async with websockets.connect(self._server_url) as websocket:
            send_task = asyncio.ensure_future(self._send_loop(websocket))
            recv_task = asyncio.ensure_future(self._recv_loop(websocket))
            heartbeat_task = asyncio.ensure_future(self._heartbeat_loop())
            await self._stop_event.wait()
            send_task.cancel()
            recv_task.cancel()
            heartbeat_task.cancel()

    async def _send_loop(self, websocket) -> None:
        loop = asyncio.get_running_loop()
        while True:
            message = await loop.run_in_executor(None, self._link.outbound.get)
            if message is _STOP_SENTINEL:
                return
            await websocket.send(codec.encode(message))

    async def _recv_loop(self, websocket) -> None:
        async for raw in websocket:
            self._link.receive(codec.decode(raw))

    async def _heartbeat_loop(self) -> None:
        """The one place asyncio.sleep appears here, per 'Timeouts without
        real waiting' - liveness (ConnectionMonitor) and RTT sync
        (ClockEstimator.on_heartbeat_ack) both depend on this never
        stopping for as long as the connection is up."""
        while True:
            self._link.send(m.Heartbeat(client_ms=self._clock_ms()))
            await asyncio.sleep(self._heartbeat_interval_ms * SECONDS_PER_MS)
