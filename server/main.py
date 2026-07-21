"""Server composition root: the one place that constructs concrete classes
and hands them to each other. Everything below this module receives its
collaborators injected and knows nothing about how they were built.

`build_server` is deliberately transport-free - it assembles config, logging,
the event bus and the application/presentation services, and stops there. The
live websockets accept/read loop and MATCH_FOUND -> room orchestration are
Phase 4 concerns (see MessageDispatcher's docstring); `rooms` starts empty and
is the dict those will populate.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Union

from common.config.loader import load_config
from common.config.schema import AppConfig
from common.events import EventBus, InMemoryEventBus
from common.logging_setup import configure_logger
from common.tracing import SecretsTraceIdGenerator
from server.application.activity_log import ActivityLog
from server.application.auth_service import AuthService, Pbkdf2PasswordHasher
from server.application.broadcast_observer import BroadcastObserver
from server.application.disconnect_policy import DisconnectPolicy
from server.application.elo import EloCalculator
from server.application.game_room import GameRoom
from server.application.matchmaking import MatchmakingService
from server.application.room_service import RoomService, SecretsRoomIdGenerator
from server.application.rating_updater import RatingUpdater
from server.application.room_ticker import RoomTicker
from server.domain.client_session import InMemoryClientSessionRegistry
from server.infrastructure.connection_factory import create_connection
from server.infrastructure.sqlite_game_record_repository import SqliteGameRecordRepository
from server.infrastructure.sqlite_user_repository import SqliteUserRepository
from server.presentation.connection import ConnectionRegistry
from server.presentation.dispatcher import MessageDispatcher
from server.presentation.heartbeat import ConnectionMonitor

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "default.toml"

SERVER_LOGGER_NAME = "kfchess.server"


@dataclass(frozen=True)
class Server:
    """The assembled object graph. Holds the subscribers (`activity_log`,
    `broadcast_observer`, `rating_updater`) even though nothing reads them
    back: they register themselves on the bus at construction time, and
    keeping them here makes the wiring visible rather than implicit."""

    config: AppConfig
    bus: EventBus
    logger: logging.Logger
    rooms: Dict[str, GameRoom]
    activity_log: ActivityLog
    broadcast_observer: BroadcastObserver
    websocket_manager: ConnectionRegistry
    client_sessions: InMemoryClientSessionRegistry
    connection_monitor: ConnectionMonitor
    disconnect_policy: DisconnectPolicy
    auth_service: AuthService
    room_service: RoomService
    matchmaking_service: MatchmakingService
    elo_calculator: EloCalculator
    rating_updater: RatingUpdater
    dispatcher: MessageDispatcher
    ticker: RoomTicker


def build_server(config: AppConfig) -> Server:
    """Wires the whole server from `config`. No I/O beyond opening the sqlite
    database and the log file, and no clock reads - the caller drives time by
    passing now_ms into `ticker.tick` / `dispatcher.dispatch`."""
    logger = configure_logger(
        SERVER_LOGGER_NAME,
        level=config.logging.level,
        file_path=config.logging.server_file,
    )

    bus = InMemoryEventBus()
    rooms: Dict[str, GameRoom] = {}
    websocket_manager = ConnectionRegistry()

    activity_log = ActivityLog(bus, logger)
    broadcast_observer = BroadcastObserver(bus, websocket_manager, rooms)

    db_connection = create_connection(config.database.path)
    users = SqliteUserRepository(db_connection)
    game_records = SqliteGameRecordRepository(db_connection)
    auth_service = AuthService(
        users,
        Pbkdf2PasswordHasher(),
        starting_elo=config.matchmaking.starting_elo,
    )

    client_sessions = InMemoryClientSessionRegistry()
    connection_monitor = ConnectionMonitor(timeout_ms=config.connection.heartbeat_timeout_ms)
    disconnect_policy = DisconnectPolicy(grace_ms=config.connection.disconnect_grace_ms)
    trace_id_generator = SecretsTraceIdGenerator()

    room_service = RoomService(
        SecretsRoomIdGenerator(config.rooms.room_id_length),
        max_viewers=config.rooms.max_viewers,
    )
    matchmaking_service = MatchmakingService(
        bus,
        elo_window=config.matchmaking.elo_window,
        timeout_ms=config.matchmaking.timeout_ms,
    )
    elo_calculator = EloCalculator(k_factor=config.matchmaking.k_factor)
    rating_updater = RatingUpdater(
        bus=bus,
        rooms=rooms,
        users=users,
        game_records=game_records,
        elo_calculator=elo_calculator,
    )

    dispatcher = MessageDispatcher(
        auth_service=auth_service,
        rooms=rooms,
        client_sessions=client_sessions,
        websocket_manager=websocket_manager,
        connection_monitor=connection_monitor,
        disconnect_policy=disconnect_policy,
        trace_id_generator=trace_id_generator,
        max_frame_bytes=config.connection.max_frame_bytes,
    )
    ticker = RoomTicker(
        rooms=rooms,
        connection_monitor=connection_monitor,
        disconnect_policy=disconnect_policy,
        matchmaking_service=matchmaking_service,
        client_sessions=client_sessions,
    )

    return Server(
        config=config,
        bus=bus,
        logger=logger,
        rooms=rooms,
        activity_log=activity_log,
        broadcast_observer=broadcast_observer,
        websocket_manager=websocket_manager,
        client_sessions=client_sessions,
        connection_monitor=connection_monitor,
        disconnect_policy=disconnect_policy,
        auth_service=auth_service,
        room_service=room_service,
        matchmaking_service=matchmaking_service,
        elo_calculator=elo_calculator,
        rating_updater=rating_updater,
        dispatcher=dispatcher,
        ticker=ticker,
    )


def build_server_from_path(path: Optional[Union[str, Path]] = DEFAULT_CONFIG_PATH) -> Server:
    """Convenience entry: load TOML (plus env overrides) and assemble."""
    return build_server(load_config(path))


if __name__ == "__main__":  # pragma: no cover
    build_server_from_path()
