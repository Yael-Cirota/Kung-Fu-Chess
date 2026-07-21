from common.config.schema import AppConfig, EngineConfigData


class TestDefaults:
    def test_app_config_builds_with_no_arguments(self):
        config = AppConfig()
        assert config.engine.move_duration_ms_per_cell == 1000
        assert config.server.port == 8765
        assert config.matchmaking.starting_elo == 1200
        assert config.connection.disconnect_grace_ms == 20000
        assert config.rooms.max_viewers == 8
        assert config.database.path == "kfchess.db"
        assert config.logging.level == "INFO"
        assert config.client.fps == 60

    def test_engine_config_default_point_values(self):
        assert EngineConfigData().point_values == {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9, "K": 10}

    def test_configs_are_frozen(self):
        config = AppConfig()
        try:
            config.server.port = 1
            assert False, "expected FrozenInstanceError"
        except Exception as exc:
            assert type(exc).__name__ == "FrozenInstanceError"
