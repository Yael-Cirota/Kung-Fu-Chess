"""Server_Design.md §2: the matchmaker role. `MatchmakingService` (see
server/application/matchmaking.py) already has zero knowledge of rooms,
connections, or the wire protocol - it only reads/writes its own Elo-window
queue and publishes MATCH_FOUND/MATCH_TIMED_OUT - so this module is a thin
`AppConfig` -> `MatchmakingService` builder, not a new object graph.

No `if __name__ == "__main__":` yet, for the same reason as
`server/roles/room.py`: `PlayRequest`/`CancelQueueRequest` only ever reach a
matchmaker today via `MessageDispatcher`, in the same process as the
gateway's websocket connections. A standalone matchmaker has no way to
receive a ticket until gateways can relay requests to it - out of scope for
this pass."""

from common.config.schema import AppConfig
from common.events import EventBus
from server.application.matchmaking import MatchmakingService


def build_matchmaker(config: AppConfig, bus: EventBus) -> MatchmakingService:
    return MatchmakingService(
        bus,
        elo_window=config.matchmaking.elo_window,
        timeout_ms=config.matchmaking.timeout_ms,
    )
