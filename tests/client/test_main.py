from client.main import Client, build_client, build_client_from_path
from client.session.remote_session import RemoteGameSession
from common.config.schema import AppConfig


class TestBuildClient:
    def test_wires_a_fully_formed_client(self):
        client = build_client(AppConfig())

        assert isinstance(client, Client)
        assert isinstance(client.session, RemoteGameSession)
        assert client.shell._link is client.link
        assert client.session._link is client.link
        assert client.session._bus is client.bus

    def test_session_uses_client_config_clock_estimator_knobs(self):
        config = AppConfig()
        client = build_client(config)

        assert client.session._estimator._resync_threshold_ms == config.client.resync_threshold_ms


class TestBuildClientFromPath:
    def test_loads_defaults_when_no_config_file_present(self, tmp_path):
        client = build_client_from_path(tmp_path / "does-not-exist.toml")

        assert isinstance(client, Client)
