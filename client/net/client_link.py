"""Owns both queue endpoints crossing the main-thread/background-asyncio-
thread boundary (see 'Client threading model'). Exactly three plain
queue.Queue instances carrying immutable frozen dataclass messages - no
locks, no shared mutable state, no engine object crosses this boundary.

`outbound` is drained by the background websocket thread (client/net/
ws_client.py); `inbound_game` feeds RemoteGameSession.wait() every render
frame; `inbound_shell` feeds the REPL's per-iteration notification drain."""

import queue
from typing import Any, List

from client.net.inbound_router import InboundQueue, route


class ClientLink:
    def __init__(self):
        self.outbound: "queue.Queue[Any]" = queue.Queue()
        self.inbound_game: "queue.Queue[Any]" = queue.Queue()
        self.inbound_shell: "queue.Queue[Any]" = queue.Queue()

    def send(self, message: Any) -> None:
        self.outbound.put(message)

    def receive(self, message: Any) -> None:
        """Single entry point for the websocket thread: routes a decoded
        inbound message onto the queue its consumer drains from, per
        client.net.inbound_router."""
        queue_for_message = self.inbound_game if route(message) is InboundQueue.GAME else self.inbound_shell
        queue_for_message.put(message)

    def drain_game(self) -> List[Any]:
        return self._drain(self.inbound_game)

    def drain_shell(self) -> List[Any]:
        return self._drain(self.inbound_shell)

    @staticmethod
    def _drain(q: "queue.Queue[Any]") -> List[Any]:
        messages = []
        while True:
            try:
                messages.append(q.get_nowait())
            except queue.Empty:
                break
        return messages
