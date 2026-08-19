"""Turns `AppConfig` into a room-creation callable. Shared by the monolith
(`server/main.py`) and the standalone room-server builder
(`server/roles/room.py`) so the `AppConfig` -> `EngineConfig` mapping and the
`create_game_room` call exist in exactly one place instead of drifting apart
across two composition roots."""

from typing import Callable

from kfchess.api import EngineConfig, point_values_from_symbols
from common.config.schema import AppConfig
from common.events import EventBus
from common.tracing import TraceIdGenerator
from server.application.game_room import GameRoom, create_game_room
from server.domain.websocket_port import WebSocketManager

RoomFactory = Callable[[str], GameRoom]


def engine_config_from(config: AppConfig) -> EngineConfig:
    return EngineConfig(
        move_duration_ms_per_cell=config.engine.move_duration_ms_per_cell,
        jump_duration_ms=config.engine.jump_duration_ms,
        move_cooldown_ms=config.engine.move_cooldown_ms,
        jump_cooldown_ms=config.engine.jump_cooldown_ms,
        point_values=point_values_from_symbols(config.engine.point_values),
    )


def build_room_factory(
    config: AppConfig,
    websocket_manager: WebSocketManager,
    bus: EventBus,
    trace_id_generator: TraceIdGenerator,
) -> RoomFactory:
    engine_config = engine_config_from(config)

    def build_room(room_id: str) -> GameRoom:
        return create_game_room(
            room_id,
            config.engine.starting_board,
            websocket_manager,
            bus=bus,
            trace_id_generator=trace_id_generator,
            engine_config=engine_config,
            broadcast_hz=config.server.broadcast_hz,
            max_engine_step_ms=config.server.max_engine_step_ms,
        )

    return build_room
