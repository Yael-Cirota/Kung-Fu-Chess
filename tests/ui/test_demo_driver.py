from pathlib import Path

from kfchess.api import BoardSnapshot, MotionInfo, PieceView, Position
from ui.demo_driver import FrameWriter, run_move_and_capture, write_image
from ui.ui_config import CELL_SIZE_PX


class FakeAnimator:
    def update(self, piece_id, is_moving, is_jump, now_ms):
        return ("some_state", 1)


class FakeGameController:
    """Single-piece stand-in for controller.api.GameController, keyed by piece_id 1."""

    def __init__(self, moving_until_ms=None, motion=None):
        self.clock_ms = 0
        self._piece = PieceView(piece_id=1, symbol="wP", color="w", cell=Position(4, 0))
        self._moving_until_ms = moving_until_ms
        self._motion = motion

    def advance(self, ms):
        self.clock_ms += ms

    def motion_for(self, piece_id):
        if self._moving_until_ms is None:
            return None
        return self._motion if self.clock_ms < self._moving_until_ms else None

    def board_snapshot(self):
        return BoardSnapshot(rows=8, cols=8, piece_views=[self._piece])


class FakeRendered:
    def __init__(self):
        self.img = "fake-pixels"


class FakeRenderer:
    def __init__(self):
        self.render_calls = 0

    def render(self, board_snapshot, visual_states):
        self.render_calls += 1
        return FakeRendered()


class FakeCanvas:
    """Records save() and show() calls - stands in for ImgCanvas without cv2."""

    def __init__(self, show_results=None):
        self.saves = []
        self.shows = []
        self._show_results = list(show_results or [])

    def save(self, frame, path):
        self.saves.append((frame, path))

    def show(self, frame, delay_ms):
        self.shows.append((frame, delay_ms))
        return self._show_results.pop(0)


class FakeFrameWriter:
    def __init__(self):
        self.writes = 0

    def write(self, rendered):
        self.writes += 1


def silent(*_args, **_kwargs):
    pass


class TestFrameWriter:
    def test_writes_sequentially_numbered_frames_through_the_canvas(self):
        canvas = FakeCanvas()
        writer = FrameWriter(canvas, Path("frames"))

        writer.write(FakeRendered())
        writer.write(FakeRendered())

        assert writer.frames_written == 2
        assert canvas.saves[0][1] == Path("frames") / "0000.png"
        assert canvas.saves[1][1] == Path("frames") / "0001.png"


class TestWriteImage:
    def test_saves_a_single_frame_to_the_given_path_through_the_canvas(self):
        canvas = FakeCanvas()
        rendered = FakeRendered()

        write_image(canvas, Path("out.png"), rendered)

        assert canvas.saves == [(rendered, Path("out.png"))]


class TestRunMoveAndCapture:
    def test_returns_immediately_when_move_was_not_accepted(self):
        controller = FakeGameController()  # motion_for always returns None
        renderer = FakeRenderer()
        frame_writer = FakeFrameWriter()

        run_move_and_capture(
            controller, FakeAnimator(), renderer, frame_writer, piece_id=1,
            label="label", cell_size_px=CELL_SIZE_PX, reporter=silent,
        )

        assert renderer.render_calls == 0
        assert frame_writer.writes == 0

    def test_captures_frames_until_piece_settles(self):
        motion = MotionInfo(from_pos=Position(4, 0), to_pos=Position(4, 2), start_ms=0, duration_ms=1000, is_jump=False)
        controller = FakeGameController(moving_until_ms=80, motion=motion)
        renderer = FakeRenderer()
        frame_writer = FakeFrameWriter()

        run_move_and_capture(
            controller, FakeAnimator(), renderer, frame_writer, piece_id=1,
            label="label", cell_size_px=CELL_SIZE_PX, tick_ms=40, reporter=silent,
        )

        # 1 tick still moving (t=40) + 10 settle ticks (t=80..440) = 11 frames
        assert renderer.render_calls == 11
        assert frame_writer.writes == 11

    def test_stops_early_when_live_canvas_reports_quit(self):
        motion = MotionInfo(from_pos=Position(4, 0), to_pos=Position(4, 2), start_ms=0, duration_ms=100_000, is_jump=False)
        controller = FakeGameController(moving_until_ms=1_000_000, motion=motion)  # never settles on its own
        renderer = FakeRenderer()
        frame_writer = FakeFrameWriter()
        live_canvas = FakeCanvas(show_results=[False])

        run_move_and_capture(
            controller, FakeAnimator(), renderer, frame_writer, piece_id=1,
            label="label", cell_size_px=CELL_SIZE_PX, live_canvas=live_canvas, tick_ms=40, reporter=silent,
        )

        assert len(live_canvas.shows) == 1
        assert live_canvas.shows[0][1] == 40  # delay_ms == tick_ms
        assert renderer.render_calls == 1
        assert frame_writer.writes == 1
