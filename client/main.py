"""Client composition root - the mirror of server/main.py. `build_client`
wires ClientLink -> RemoteGameSession -> Shell entirely without a socket, so
it is testable synchronously; the module's `__main__` block is the only
place that starts the background websocket thread, blocks on stdin, and
opens a cv2 window, and is pragma'd for exactly that reason (same convention
as server/main.py's `__main__` block and ws_server.run_server)."""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from common.config.loader import load_config
from common.config.schema import AppConfig
from client.net.client_link import ClientLink
from client.session.remote_session import RemoteGameSession
from client.session.sync_event_bus import SyncEventBus
from client.shell.shell import Shell

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "default.toml"

# How long to poll for the room's first GameStarted/StateUpdate once the REPL
# hands off, before giving up rather than handing an empty (rows=0, cols=0)
# board_snapshot to BoardRenderer - see _await_first_snapshot's docstring.
AWAIT_FIRST_SNAPSHOT_TIMEOUT_S = 10.0
AWAIT_FIRST_SNAPSHOT_POLL_INTERVAL_S = 0.05


@dataclass(frozen=True)
class Client:
    link: ClientLink
    bus: SyncEventBus
    session: RemoteGameSession
    shell: Shell


def build_client(config: AppConfig) -> Client:
    """No I/O: the caller (the `__main__` block below) is responsible for
    starting the actual websocket connection against `client.link`."""
    link = ClientLink()
    bus = SyncEventBus()
    session = RemoteGameSession(
        link,
        bus,
        resync_threshold_ms=config.client.resync_threshold_ms,
        max_catchup_rate=config.client.max_catchup_rate,
        min_catchup_rate=config.client.min_catchup_rate,
    )
    shell = Shell(link)
    return Client(link=link, bus=bus, session=session, shell=shell)


def build_client_from_path(path: Optional[Union[str, Path]] = DEFAULT_CONFIG_PATH) -> Client:
    """Convenience entry mirroring server.main.build_server_from_path."""
    return build_client(load_config(path))


def _await_first_snapshot(session: RemoteGameSession) -> bool:  # pragma: no cover - real timing
    """A fresh RemoteGameSession's board_snapshot() is (rows=0, cols=0, [])
    until its first wait() drains a GameStarted/StateUpdate off the wire.
    run_game_loop's very first frame skips calling wait() (its `dt_ms > 0`
    guard: session.clock_ms and render_ms both start at ~0), so entering the
    game loop before a real snapshot exists hands BoardRenderer a 0x0 board -
    which cv2.resize rejects outright, not just draws blank. Poll here,
    synchronously, before _build_scene/run_game_loop ever run a frame.
    Returns False on timeout (server never started the game)."""
    deadline = time.monotonic() + AWAIT_FIRST_SNAPSHOT_TIMEOUT_S
    while session.board_snapshot().rows == 0:
        session.wait(0)
        if session.board_snapshot().rows > 0:
            return True
        if time.monotonic() > deadline:
            return False
        time.sleep(AWAIT_FIRST_SNAPSHOT_POLL_INTERVAL_S)
    return True


def run() -> None:  # pragma: no cover - real socket, stdin, and cv2 window
    """Phased main thread (see 'Client threading model'): REPL until a room
    becomes active or the user quits, then the cv2 game loop for that one
    match. One game per process invocation - `client.session`'s
    ClockEstimator origin and `elapsed_ms` (the Heartbeat clock source
    below) are only valid for a single game's timeline, and swapping
    RemoteGameSession instances mid-connection would desynchronize
    HeartbeatAck RTT compensation (client_ms and the receipt timestamp must
    share an origin - see WsClient's docstring). Restart the process to play
    again. The background websocket thread runs for the whole process
    lifetime alongside it."""
    from client.net.ws_client import WsClient
    from client.shell.repl import run_repl
    from ui.game_loop import run_game_loop, run_winner_screen
    from ui.main import _build_scene
    from ui.ui_config import CELL_SIZE_PX, WINNER_DISPLAY_DURATION_MS

    config = load_config(DEFAULT_CONFIG_PATH)
    client = build_client(config)
    ws_client = WsClient(
        config.client.server_url,
        client.link,
        clock_ms=client.session.elapsed_ms,
        heartbeat_interval_ms=config.connection.heartbeat_interval_ms,
    )
    ws_client.start()

    try:
        if run_repl(client.shell):
            return
        # The REPL can block on input() for an arbitrary, human-length amount
        # of time (login, room setup, waiting for an opponent) - re-anchor
        # before consuming any of that wait as if it were game time. See
        # RemoteGameSession.reset_clock_origin's docstring.
        client.session.reset_clock_origin()
        if not _await_first_snapshot(client.session):
            return

        click_handler, animator, canvas, renderer, sound_board = _build_scene(
            "Kung-Fu-Chess (online)", client.session
        )
        try:
            run_game_loop(
                canvas, client.session, click_handler, animator, renderer,
                CELL_SIZE_PX, sound_board=sound_board,
            )
            if client.session.game_over:
                run_winner_screen(
                    canvas, client.session, renderer, WINNER_DISPLAY_DURATION_MS, sound_board=sound_board,
                )
        finally:
            canvas.close()
    finally:
        ws_client.stop()


if __name__ == "__main__":  # pragma: no cover
    run()
