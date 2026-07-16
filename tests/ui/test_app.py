from kfchess.api import BoardSnapshot, MotionInfo, PieceView, Position
from ui.app import build_visual_states, cell_top_left_px
from ui.ui_config import CELL_SIZE_PX


def piece_view(piece_id, row, col, symbol="wP"):
    return PieceView(piece_id=piece_id, symbol=symbol, color=symbol[0], cell=Position(row, col))


class FakeGameController:
    def __init__(self, pieces, motions=None):
        self._pieces = pieces
        self._motions = motions or {}

    def board_snapshot(self):
        return BoardSnapshot(rows=8, cols=8, piece_views=self._pieces)

    def motion_for(self, piece_id):
        return self._motions.get(piece_id)


class FakeAnimator:
    def __init__(self):
        self.calls = []

    def update(self, piece_id, is_moving, is_jump, now_ms):
        self.calls.append((piece_id, is_moving, is_jump, now_ms))
        return ("some_state", 1)


class TestCellTopLeftPx:
    def test_top_left_of_origin_cell(self):
        assert cell_top_left_px(Position(0, 0), CELL_SIZE_PX) == (0, 0)

    def test_scales_by_cell_size(self):
        assert cell_top_left_px(Position(2, 3), CELL_SIZE_PX) == (3 * CELL_SIZE_PX, 2 * CELL_SIZE_PX)


class TestBuildVisualStates:
    def test_stationary_piece_uses_its_resting_cell(self):
        piece = piece_view(1, row=1, col=1)
        controller = FakeGameController([piece])
        animator = FakeAnimator()

        visuals = build_visual_states(
            controller, animator, engine_ms=1000, render_ms=7000, cell_size_px=CELL_SIZE_PX
        )

        visual = visuals[1]
        assert (visual.pixel_x, visual.pixel_y) == cell_top_left_px(Position(1, 1), CELL_SIZE_PX)
        # The animator (cosmetic frames) is driven by the render/wall clock, not the engine clock.
        assert animator.calls == [(1, False, False, 7000)]

    def test_moving_piece_interpolates_on_the_engine_clock(self):
        piece = piece_view(1, row=4, col=0)
        motion = MotionInfo(from_pos=Position(4, 0), to_pos=Position(4, 2), start_ms=0, duration_ms=1000, is_jump=False)
        controller = FakeGameController([piece], motions={1: motion})
        animator = FakeAnimator()

        # engine_ms=500 is halfway through the 1000ms motion; render_ms differs
        # to prove position tracks the engine clock, not the wall clock.
        visuals = build_visual_states(
            controller, animator, engine_ms=500, render_ms=12345, cell_size_px=CELL_SIZE_PX
        )

        visual = visuals[1]
        from_x, from_y = cell_top_left_px(Position(4, 0), CELL_SIZE_PX)
        to_x, to_y = cell_top_left_px(Position(4, 2), CELL_SIZE_PX)
        assert visual.pixel_x == (from_x + to_x) / 2
        assert visual.pixel_y == (from_y + to_y) / 2
        # ...while the animator still sees the render clock.
        assert animator.calls == [(1, True, False, 12345)]

    def test_moving_piece_forwards_is_jump_flag(self):
        piece = piece_view(1, row=7, col=1)
        motion = MotionInfo(from_pos=Position(7, 1), to_pos=Position(5, 2), start_ms=0, duration_ms=250, is_jump=True)
        controller = FakeGameController([piece], motions={1: motion})
        animator = FakeAnimator()

        build_visual_states(controller, animator, engine_ms=100, render_ms=100, cell_size_px=CELL_SIZE_PX)

        assert animator.calls == [(1, True, True, 100)]

    def test_no_pieces_produces_empty_visual_states(self):
        controller = FakeGameController([])
        animator = FakeAnimator()

        visuals = build_visual_states(controller, animator, engine_ms=0, render_ms=0, cell_size_px=CELL_SIZE_PX)

        assert visuals == {}
        assert animator.calls == []

    def test_sprite_state_and_frame_come_from_animator(self):
        piece = piece_view(1, row=0, col=0)
        controller = FakeGameController([piece])
        animator = FakeAnimator()

        visuals = build_visual_states(controller, animator, engine_ms=0, render_ms=0, cell_size_px=CELL_SIZE_PX)

        assert visuals[1].sprite_state == "some_state"
        assert visuals[1].frame_index == 1
