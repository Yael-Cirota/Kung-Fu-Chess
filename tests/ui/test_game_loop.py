from kfchess.api import BoardSnapshot, PieceView, Position, Scoreboard

import ui.game_loop as game_loop_module
from ui.game_loop import MAX_ENGINE_STEP_MS, run_game_loop, run_winner_screen
from ui.ui_config import CELL_SIZE_PX


class FakeClock:
    """Returns each scripted time in turn (in seconds); pins to the last once exhausted."""

    def __init__(self, times_s):
        self._times = list(times_s)
        self._last = self._times[-1] if self._times else 0.0

    def __call__(self):
        if self._times:
            self._last = self._times.pop(0)
        return self._last


class FakeClickHandler:
    def __init__(self):
        self.clicks = []

    def on_click(self, x, y):
        self.clicks.append((x, y))


class FakeSession:
    def __init__(self, game_over_after_frames=None, winner=None):
        self.clock_ms = 0
        self.advances = []
        self.winner = winner
        self._piece = PieceView(piece_id=1, symbol="wP", color="w", cell=Position(6, 4))
        self._game_over_after = game_over_after_frames
        self._frame_checks = 0

    def wait(self, ms):
        self.advances.append(ms)
        self.clock_ms += ms

    @property
    def game_over(self):
        # The loop reads this exactly once per iteration (its while-condition),
        # so it doubles as a frame counter: report game-over from frame N on.
        if self._game_over_after is None:
            return False
        self._frame_checks += 1
        return self._frame_checks > self._game_over_after

    def board_snapshot(self):
        return BoardSnapshot(rows=8, cols=8, piece_views=[self._piece])

    def motion_for(self, piece_id):
        return None

    def move_log(self):
        return []

    def scoreboard(self):
        return Scoreboard(white=0, black=0)


class FakeAnimator:
    def update(self, piece_id, is_moving, is_jump, now_ms):
        return ("idle", 0)


class FakeRenderer:
    def __init__(self):
        self.render_calls = 0
        self.render_args = []

    def render(self, board_snapshot, visual_states=None, move_log=None, scoreboard=None,
               winner=None, winner_elapsed_ms=0):
        self.render_calls += 1
        self.render_args.append((board_snapshot, visual_states, move_log, scoreboard, winner, winner_elapsed_ms))
        return object()


class FakeCanvas:
    """Scripts clicks and show()-results per frame - the seam the loop is written against."""

    def __init__(self, clicks_per_frame=None, show_results=None):
        self._clicks = list(clicks_per_frame or [])
        self._show_results = list(show_results or [])
        self.shows = []

    def drain_clicks(self):
        return self._clicks.pop(0) if self._clicks else []

    def show(self, frame, delay_ms):
        self.shows.append((frame, delay_ms))
        return self._show_results.pop(0) if self._show_results else False


class TestRunGameLoop:
    def test_feeds_drained_clicks_into_the_click_handler(self):
        session, click_handler = FakeSession(), FakeClickHandler()
        canvas = FakeCanvas(
            clicks_per_frame=[[(10, 20), (30, 40)]],
            show_results=[False],  # quit after one frame
        )

        run_game_loop(
            canvas, session, click_handler, FakeAnimator(), FakeRenderer(), CELL_SIZE_PX,
            clock=FakeClock([0.0, 0.0]),
        )

        assert click_handler.clicks == [(10, 20), (30, 40)]

    def test_advances_engine_by_elapsed_wall_time(self):
        session, click_handler = FakeSession(), FakeClickHandler()
        canvas = FakeCanvas(show_results=[True, False])

        # start=0.0; frame1 wall=0.040s -> advance 40ms; frame2 wall=0.100s -> advance 60ms
        run_game_loop(
            canvas, session, click_handler, FakeAnimator(), FakeRenderer(), CELL_SIZE_PX,
            clock=FakeClock([0.0, 0.040, 0.100]),
        )

        assert session.advances == [40, 60]
        assert session.clock_ms == 100

    def test_clamps_a_large_wall_gap_to_the_max_engine_step(self):
        session, click_handler = FakeSession(), FakeClickHandler()
        canvas = FakeCanvas(show_results=[False])

        # a 2s stall between start and first frame must not advance the engine 2000ms at once
        run_game_loop(
            canvas, session, click_handler, FakeAnimator(), FakeRenderer(), CELL_SIZE_PX,
            clock=FakeClock([0.0, 2.0]),
        )

        assert session.advances == [MAX_ENGINE_STEP_MS]

    def test_does_not_advance_when_no_wall_time_has_passed(self):
        session, click_handler = FakeSession(), FakeClickHandler()
        canvas = FakeCanvas(show_results=[False])

        run_game_loop(
            canvas, session, click_handler, FakeAnimator(), FakeRenderer(), CELL_SIZE_PX,
            clock=FakeClock([0.0, 0.0]),
        )

        assert session.advances == []

    def test_stops_when_show_reports_quit(self):
        session, click_handler = FakeSession(), FakeClickHandler()
        renderer = FakeRenderer()
        canvas = FakeCanvas(show_results=[True, True, False])

        run_game_loop(
            canvas, session, click_handler, FakeAnimator(), renderer, CELL_SIZE_PX,
            clock=FakeClock([0.0, 0.01, 0.02, 0.03]),
        )

        assert renderer.render_calls == 3
        assert len(canvas.shows) == 3

    def test_stops_when_the_game_is_over(self):
        # is_game_over reports True from the 3rd iteration, so only 2 frames render.
        session, click_handler = FakeSession(game_over_after_frames=2), FakeClickHandler()
        renderer = FakeRenderer()
        canvas = FakeCanvas(show_results=[True, True, True, True])

        run_game_loop(
            canvas, session, click_handler, FakeAnimator(), renderer, CELL_SIZE_PX,
            clock=FakeClock([0.0, 0.01, 0.02, 0.03, 0.04]),
        )

        assert renderer.render_calls == 2

    def test_paces_frames_at_the_requested_fps(self):
        session, click_handler = FakeSession(), FakeClickHandler()
        canvas = FakeCanvas(show_results=[False])

        run_game_loop(
            canvas, session, click_handler, FakeAnimator(), FakeRenderer(), CELL_SIZE_PX,
            fps=50, clock=FakeClock([0.0, 0.0]),
        )

        assert canvas.shows[0][1] == 20  # 1000 / 50

    def test_routes_the_two_clocks_to_build_visual_states(self, monkeypatch):
        session, click_handler = FakeSession(), FakeClickHandler()
        canvas = FakeCanvas(show_results=[False])
        recorded = {}

        def spy_build(session, animator, engine_ms, render_ms, cell_size_px):
            recorded["engine_ms"] = engine_ms
            recorded["render_ms"] = render_ms
            return {}

        monkeypatch.setattr(game_loop_module, "build_visual_states", spy_build)

        # start=0.0, frame wall=0.040s -> render_ms=40, engine advanced 40 -> engine_ms=40
        run_game_loop(
            canvas, session, click_handler, FakeAnimator(), FakeRenderer(), CELL_SIZE_PX,
            clock=FakeClock([0.0, 0.040]),
        )

        assert recorded["render_ms"] == 40  # wall clock
        assert recorded["engine_ms"] == session.clock_ms == 40  # engine clock, read after advance


class TestRunWinnerScreen:
    def test_reads_the_frozen_game_state_once_and_renders_it_every_frame(self):
        session = FakeSession(winner="w")
        renderer = FakeRenderer()
        canvas = FakeCanvas(show_results=[True, True, False])

        run_winner_screen(
            canvas, session, renderer, duration_ms=1000,
            clock=FakeClock([0.0, 0.01, 0.02, 0.03]),
        )

        assert renderer.render_calls == 3
        for _board, _visual, _log, _score, winner, _elapsed in renderer.render_args:
            assert winner == "w"

    def test_passes_increasing_elapsed_wall_time_to_render(self):
        session = FakeSession(winner="b")
        renderer = FakeRenderer()
        canvas = FakeCanvas(show_results=[True, False])

        run_winner_screen(
            canvas, session, renderer, duration_ms=1000,
            clock=FakeClock([0.0, 0.050, 0.120]),
        )

        elapsed_values = [args[5] for args in renderer.render_args]
        assert elapsed_values == [50, 120]

    def test_stops_once_the_duration_elapses(self):
        session = FakeSession(winner="w")
        renderer = FakeRenderer()
        canvas = FakeCanvas(show_results=[True, True, True, True])

        run_winner_screen(
            canvas, session, renderer, duration_ms=100,
            clock=FakeClock([0.0, 0.04, 0.09, 0.15, 0.20]),
        )

        # Frames render while elapsed_ms < 100; the 0.15s frame (150ms) ends the loop.
        assert renderer.render_calls == 3

    def test_stops_early_when_show_reports_quit(self):
        session = FakeSession(winner="w")
        renderer = FakeRenderer()
        canvas = FakeCanvas(show_results=[True, False])

        run_winner_screen(
            canvas, session, renderer, duration_ms=10000,
            clock=FakeClock([0.0, 0.01, 0.02]),
        )

        assert renderer.render_calls == 2

    def test_never_advances_the_engine_clock(self):
        session = FakeSession(winner="w")
        renderer = FakeRenderer()
        canvas = FakeCanvas(show_results=[True, False])

        run_winner_screen(
            canvas, session, renderer, duration_ms=1000,
            clock=FakeClock([0.0, 0.01, 0.02]),
        )

        assert session.advances == []
