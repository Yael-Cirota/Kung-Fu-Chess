"""HTTP health-check surface multiplexed onto the same port as the
websocket handshake, via websockets' `process_request` hook (see
`ws_server.run_server`) - Server_Design.md §12.4 rules out a separate HTTP
framework so `websockets` stays the only base runtime dependency.

Two paths: `/healthz` is bare process liveness (always OK once serving).
`/readyz` reflects `ReadinessState`, a settable flag - true placement
eligibility (§11: "readiness reflects placement eligibility, not liveness")
depends on the placement pool §2's role split introduces, which doesn't
exist yet. Everything else returns None so the normal websocket upgrade
proceeds unmodified."""

from typing import Callable, Optional

from websockets import Headers, Request, Response

_PLAIN_TEXT_HEADERS = Headers([("Content-Type", "text/plain; charset=utf-8")])


class ReadinessState:
    """Shared between the accept loop's `process_request` hook and whatever
    deregisters this process from the placement pool (Server_Design.md
    §7.1 step 1: preStop/SIGTERM marks the instance ineligible for new
    placements and fails readiness in the same beat)."""

    def __init__(self) -> None:
        self.ready = True

    def mark_not_ready(self) -> None:
        self.ready = False


def make_process_request(readiness: ReadinessState) -> Callable[[object, Request], Optional[Response]]:
    def process_request(connection: object, request: Request) -> Optional[Response]:
        if request.path == "/healthz":
            return Response(200, "OK", _PLAIN_TEXT_HEADERS, b"ok")
        if request.path == "/readyz":
            if readiness.ready:
                return Response(200, "OK", _PLAIN_TEXT_HEADERS, b"ready")
            return Response(503, "Service Unavailable", _PLAIN_TEXT_HEADERS, b"draining")
        return None

    return process_request
