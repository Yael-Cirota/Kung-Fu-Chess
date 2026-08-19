from dataclasses import replace

from common.config.schema import AppConfig
from common.events import InMemoryEventBus
from common.tracing import SequentialTraceIdGenerator
from server.application.room_factory import build_room_factory, engine_config_from


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


class TestEngineConfigFrom:
    def test_maps_every_engine_config_field_from_app_config(self):
        config = AppConfig()
        engine_config = engine_config_from(config)

        assert engine_config.move_duration_ms_per_cell == config.engine.move_duration_ms_per_cell
        assert engine_config.jump_duration_ms == config.engine.jump_duration_ms
        assert engine_config.move_cooldown_ms == config.engine.move_cooldown_ms
        assert engine_config.jump_cooldown_ms == config.engine.jump_cooldown_ms


class TestBuildRoomFactory:
    def test_returns_a_playable_room_built_from_config(self):
        config = AppConfig()
        build_room = build_room_factory(
            config, FakeWebSocketManager(), InMemoryEventBus(), SequentialTraceIdGenerator()
        )

        room = build_room("room-1")

        assert room.room_id == "room-1"
        assert room.session is not None

    def test_uses_the_configured_broadcast_and_step_settings(self):
        config = AppConfig()
        config = replace(config, server=replace(config.server, broadcast_hz=5, max_engine_step_ms=250))
        build_room = build_room_factory(
            config, FakeWebSocketManager(), InMemoryEventBus(), SequentialTraceIdGenerator()
        )

        room = build_room("room-1")

        assert room._broadcast_interval_ms == 1000 / 5
        assert room._max_engine_step_ms == 250
