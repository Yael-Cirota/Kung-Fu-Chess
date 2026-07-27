"""Phase 5 mandated driving the real run_game_loop against a RemoteGameSession
+ FakeCanvas + FakeClientLink, proving (not just asserting) that
ui/game_loop.py needs zero changes for a remote session. It also pins down
why RemoteGameSession.reset_clock_origin() exists: client/main.py's REPL can
block on input() for an arbitrary, human-length amount of real time before a
room fills - and without re-anchoring first, that wait gets baked into
clock_ms right as run_game_loop's own render_ms starts fresh from zero,
freezing the board (see 'the one non-obvious bug this design exists to
avoid' and RemoteGameSession.reset_clock_origin's docstring)."""

from common.clock import ManualClock
from kfchess.api.dto import Scoreboard
from protocol import messages as m
from client.net.client_link import ClientLink
from client.session.remote_session import RemoteGameSession
from ui.game_loop import run_game_loop
from ui.ui_config import CELL_SIZE_PX


class FakeCanvas:
    """Scripts show()-results per frame - no real clicks needed for this test."""

    def __init__(self, show_results):
        self._show_results = list(show_results)

    def drain_clicks(self):
        return []

    def show(self, frame, delay_ms):
        return self._show_results.pop(0) if self._show_results else False


class FakeClickHandler:
    selected = None

    def on_click(self, x, y):
        pass


class FakeAnimator:
    def update(self, piece_id, is_moving, is_jump, now_ms):
        return ("idle", 0)


class FakeRenderer:
    def render(self, board_snapshot, visual_states=None, move_log=None, scoreboard=None,
               winner=None, winner_elapsed_ms=0, selected=None):
        return object()


class FakeSecondsClock:
    """run_game_loop's `clock` param returns seconds and is entirely
    independent of RemoteGameSession's own ms-based Clock - render_ms starts
    at 0 the instant run_game_loop is called, no matter how long the REPL
    took beforehand."""

    def __init__(self, times_s):
        self._times = list(times_s)
        self._last = self._times[-1] if self._times else 0.0

    def __call__(self):
        if self._times:
            self._last = self._times.pop(0)
        return self._last


def _queue_started_game(link, server_ms=0):
    link.inbound_game.put(m.GameStarted(server_ms=server_ms, rows=8, cols=8))
    link.inbound_game.put(m.StateUpdate(
        server_ms=server_ms, seq=1, pieces=[], motions=[], move_log=[],
        scoreboard=Scoreboard(white=0, black=0), game_over=False,
    ))


class TestClockOriginAcrossAReplWait:
    def test_without_a_reset_the_board_freezes_after_a_long_repl_wait(self):
        clock = ManualClock(0)
        link = ClientLink()
        session = RemoteGameSession(link, clock=clock)

        clock.advance(60_000)  # 60s spent in the REPL before this game starts
        _queue_started_game(link)
        session.wait(0)  # what _await_first_snapshot does, applied too early

        assert session.clock_ms == 60_000  # the bug: snapped to the wait, not to 0

        canvas = FakeCanvas(show_results=[True, True, False])
        run_game_loop(
            canvas, session, FakeClickHandler(), FakeAnimator(), FakeRenderer(), CELL_SIZE_PX,
            clock=FakeSecondsClock([0.0, 0.01, 0.02, 0.03]),
        )

        # render_ms never overtakes the frozen clock_ms within these frames,
        # so wait() (and therefore drain_game) is never invoked again.
        assert session.clock_ms == 60_000

    def test_reset_clock_origin_keeps_clock_ms_and_render_ms_in_sync(self):
        clock = ManualClock(0)
        link = ClientLink()
        session = RemoteGameSession(link, clock=clock)

        clock.advance(60_000)
        session.reset_clock_origin()
        _queue_started_game(link)
        session.wait(0)

        assert session.clock_ms == 0

        canvas = FakeCanvas(show_results=[True, True, False])
        run_game_loop(
            canvas, session, FakeClickHandler(), FakeAnimator(), FakeRenderer(), CELL_SIZE_PX,
            clock=FakeSecondsClock([0.0, 0.01, 0.02, 0.03]),
        )

        assert session.clock_ms > 0
