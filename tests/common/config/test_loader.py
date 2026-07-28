from common.config.loader import load_config


class TestMissingPathUsesDefaults:
    def test_no_path_returns_all_defaults(self):
        config = load_config(path=None, env={})
        assert config.server.port == 8765
        assert config.engine.move_duration_ms_per_cell == 1000

    def test_nonexistent_path_falls_back_to_defaults(self, tmp_path):
        config = load_config(path=tmp_path / "missing.toml", env={})
        assert config.server.port == 8765


class TestTomlOverrides:
    def test_toml_values_override_defaults(self, tmp_path):
        toml_path = tmp_path / "config.toml"
        toml_path.write_text(
            "[server]\nport = 9999\n\n[engine]\nmove_duration_ms_per_cell = 500\n"
        )

        config = load_config(path=toml_path, env={})

        assert config.server.port == 9999
        assert config.engine.move_duration_ms_per_cell == 500
        # keys not present in the TOML still fall back to their dataclass default.
        assert config.server.host == "127.0.0.1"

    def test_point_values_subtable_overrides_the_default_mapping(self, tmp_path):
        toml_path = tmp_path / "config.toml"
        toml_path.write_text("[engine.point_values]\nP = 2\n")

        config = load_config(path=toml_path, env={})

        assert config.engine.point_values == {"P": 2}


class TestEnvOverrides:
    def test_env_overrides_take_precedence_over_toml(self, tmp_path):
        toml_path = tmp_path / "config.toml"
        toml_path.write_text("[server]\nport = 9999\n")

        config = load_config(path=toml_path, env={"KFC_PORT": "7777"})

        assert config.server.port == 7777

    def test_env_overrides_apply_over_defaults_with_no_toml(self):
        config = load_config(
            path=None,
            env={
                "KFC_DB_PATH": "/tmp/other.db",
                "KFC_HOST": "0.0.0.0",
                "KFC_LOG_LEVEL": "DEBUG",
            },
        )
        assert config.database.path == "/tmp/other.db"
        assert config.server.host == "0.0.0.0"
        assert config.logging.level == "DEBUG"

    def test_unset_env_vars_leave_defaults_untouched(self):
        config = load_config(path=None, env={})
        assert config.database.path == "kfchess.db"


class TestGenericEnvOverrideRule:
    def test_section_field_env_var_overrides_any_config_field(self):
        config = load_config(
            path=None,
            env={
                "KFC_REDIS_URL": "redis://cache:6379",
                "KFC_PG_DSN": "postgresql://kfchess@postgres/kfchess",
                "KFC_SERVER_BROADCAST_HZ": "10",
                "KFC_SERVER_ROLE": "gateway",
            },
        )
        assert config.redis.url == "redis://cache:6379"
        assert config.pg.dsn == "postgresql://kfchess@postgres/kfchess"
        assert config.server.broadcast_hz == 10
        assert config.server.role == "gateway"

    def test_legacy_alias_still_wins_over_generic_form_of_same_key(self, tmp_path):
        # KFC_HOST is the pre-existing alias for KFC_SERVER_HOST; both firing
        # at once should still resolve deterministically to the alias.
        config = load_config(
            path=None,
            env={"KFC_HOST": "0.0.0.0", "KFC_SERVER_HOST": "10.0.0.1"},
        )
        assert config.server.host == "0.0.0.0"

    def test_mapping_typed_fields_are_not_env_overridable(self):
        # point_values is Mapping[str, int]; there's no sane single-value env
        # encoding for it, so a same-named env var is simply ignored.
        config = load_config(path=None, env={"KFC_ENGINE_POINT_VALUES": "nonsense"})
        assert config.engine.point_values == {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9, "K": 10}
