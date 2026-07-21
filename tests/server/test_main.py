import json
import logging
from dataclasses import replace

from common.config.schema import AppConfig
from common.events import Event, EventNames, InMemoryEventBus
from server.main import SERVER_LOGGER_NAME, Server, build_server, build_server_from_path
from server.presentation.dispatcher import MessageDispatcher


def make_config(tmp_path, **overrides):
    """An AppConfig safe to build a real server from: in-memory database (so
    no kfchess.db lands in the repo) and a log file under tmp_path."""
    config = AppConfig()
    config = replace(config, database=replace(config.database, path=":memory:"))
    config = replace(config, logging=replace(config.logging, server_file=str(tmp_path / "server.log")))
    for section, values in overrides.items():
        config = replace(config, **{section: replace(getattr(config, section), **values)})
    return config


def read_log_lines(tmp_path):
    for handler in logging.getLogger(SERVER_LOGGER_NAME).handlers:
        handler.flush()
    return (tmp_path / "server.log").read_text().splitlines()


class TestAssembly:
    def test_builds_every_collaborator(self, tmp_path):
        server = build_server(make_config(tmp_path))

        assert isinstance(server, Server)
        assert isinstance(server.dispatcher, MessageDispatcher)
        assert isinstance(server.bus, InMemoryEventBus)
        assert server.rooms == {}

    def test_rooms_dict_is_shared_by_identity_with_dispatcher_and_ticker(self, tmp_path):
        """The dispatcher looks rooms up and the ticker iterates them; both
        must see the same dict a future room-creation path writes into."""
        server = build_server(make_config(tmp_path))

        server.rooms["room-1"] = object()

        assert server.dispatcher._rooms is server.rooms
        assert server.ticker._rooms is server.rooms


class TestConfigIsHonored:
    def test_connection_and_room_knobs_come_from_config(self, tmp_path):
        config = make_config(
            tmp_path,
            connection={"heartbeat_timeout_ms": 4321, "disconnect_grace_ms": 999, "max_frame_bytes": 64},
            rooms={"max_viewers": 3},
        )

        server = build_server(config)

        assert server.connection_monitor._timeout_ms == 4321
        assert server.disconnect_policy._grace_ms == 999
        assert server.dispatcher._max_frame_bytes == 64
        assert server.room_service._max_viewers == 3

    def test_matchmaking_knobs_come_from_config(self, tmp_path):
        config = make_config(
            tmp_path,
            matchmaking={"elo_window": 42, "timeout_ms": 111, "starting_elo": 900, "k_factor": 16},
        )

        server = build_server(config)

        assert server.matchmaking_service._elo_window == 42
        assert server.matchmaking_service._timeout_ms == 111
        assert server.auth_service._starting_elo == 900
        assert server.elo_calculator._k == 16


class TestLoggingIsConnected:
    def test_a_domain_event_on_the_assembled_bus_reaches_the_configured_log_file(self, tmp_path):
        server = build_server(make_config(tmp_path))

        server.bus.publish(Event(
            name=EventNames.GAME_OVER,
            payload={"room_id": "room-7", "at_ms": 1234},
            trace_id="trace-abc",
        ))

        lines = read_log_lines(tmp_path)
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["event"] == EventNames.GAME_OVER
        assert entry["room_id"] == "room-7"
        assert entry["trace_id"] == "trace-abc"
        assert entry["at_ms"] == 1234
        assert entry["layer"] == "domain"

    def test_unsubscribed_events_are_not_logged(self, tmp_path):
        server = build_server(make_config(tmp_path))

        server.bus.publish(Event(name=EventNames.SCORE_CHANGED, payload={}))

        assert read_log_lines(tmp_path) == []

    def test_log_level_comes_from_config(self, tmp_path):
        server = build_server(make_config(tmp_path, logging={"level": "WARNING"}))

        server.bus.publish(Event(name=EventNames.GAME_OVER, payload={}))

        assert server.logger.level == logging.WARNING
        assert read_log_lines(tmp_path) == []

    def test_server_logger_does_not_propagate_to_the_root_logger(self, tmp_path):
        """The whole reason configure_logger sets propagate=False: server lines
        must not bleed into any root handler a client shares the process with."""
        build_server(make_config(tmp_path))

        assert logging.getLogger(SERVER_LOGGER_NAME).propagate is False

    def test_rebuilding_does_not_duplicate_handlers(self, tmp_path):
        build_server(make_config(tmp_path))
        server = build_server(make_config(tmp_path))

        server.bus.publish(Event(name=EventNames.GAME_OVER, payload={"room_id": "r"}))

        assert len(read_log_lines(tmp_path)) == 1


class TestBuildFromPath:
    def test_loads_the_repo_default_toml(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KFC_DB_PATH", ":memory:")
        monkeypatch.setenv("KFC_LOG_LEVEL", "ERROR")
        monkeypatch.chdir(tmp_path)

        server = build_server_from_path()

        assert server.config.server.port == 8765
        assert server.config.database.path == ":memory:"
        assert server.logger.level == logging.ERROR
