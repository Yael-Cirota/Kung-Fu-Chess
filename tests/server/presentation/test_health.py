from websockets import Headers, Request

from server.presentation.health import ReadinessState, make_process_request


def _request(path: str) -> Request:
    return Request(path, Headers())


class TestHealthz:
    def test_healthz_is_always_ok(self):
        process_request = make_process_request(ReadinessState())
        response = process_request(None, _request("/healthz"))
        assert response.status_code == 200

    def test_healthz_is_ok_even_when_not_ready(self):
        readiness = ReadinessState()
        readiness.mark_not_ready()
        process_request = make_process_request(readiness)
        response = process_request(None, _request("/healthz"))
        assert response.status_code == 200


class TestReadyz:
    def test_readyz_is_ok_by_default(self):
        process_request = make_process_request(ReadinessState())
        response = process_request(None, _request("/readyz"))
        assert response.status_code == 200

    def test_readyz_is_503_once_marked_not_ready(self):
        readiness = ReadinessState()
        readiness.mark_not_ready()
        process_request = make_process_request(readiness)
        response = process_request(None, _request("/readyz"))
        assert response.status_code == 503


class TestOtherPaths:
    def test_websocket_upgrade_path_falls_through_to_none(self):
        process_request = make_process_request(ReadinessState())
        assert process_request(None, _request("/")) is None
