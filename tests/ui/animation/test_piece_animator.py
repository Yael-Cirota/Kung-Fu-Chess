from dataclasses import dataclass

from ui.animation.piece_animator import PieceAnimator


@dataclass(frozen=True)
class FakeStateConfig:
    frame_count: int
    frames_per_sec: int
    is_loop: bool
    next_state: str


def make_configs():
    return {
        "idle": FakeStateConfig(frame_count=4, frames_per_sec=4, is_loop=True, next_state="idle"),
        "move": FakeStateConfig(frame_count=5, frames_per_sec=10, is_loop=False, next_state="short_rest"),
        "jump": FakeStateConfig(frame_count=3, frames_per_sec=10, is_loop=False, next_state="long_rest"),
        "short_rest": FakeStateConfig(frame_count=2, frames_per_sec=2, is_loop=False, next_state="idle"),
        "long_rest": FakeStateConfig(frame_count=6, frames_per_sec=3, is_loop=False, next_state="idle"),
    }


class TestNewPiece:
    def test_starts_idle_at_frame_zero(self):
        animator = PieceAnimator(make_configs())

        state, frame = animator.update("piece", is_moving=False, is_jump=False, now_ms=0)

        assert state == "idle"
        assert frame == 0


class TestEnteringMotion:
    def test_switches_to_move_state_on_first_moving_tick(self):
        animator = PieceAnimator(make_configs())

        state, frame = animator.update("piece", is_moving=True, is_jump=False, now_ms=100)

        assert state == "move"
        assert frame == 0

    def test_switches_to_jump_state_when_is_jump(self):
        animator = PieceAnimator(make_configs())

        state, frame = animator.update("piece", is_moving=True, is_jump=True, now_ms=100)

        assert state == "jump"

    def test_frame_advances_with_elapsed_time(self):
        animator = PieceAnimator(make_configs())
        animator.update("piece", is_moving=True, is_jump=False, now_ms=0)

        _, frame = animator.update("piece", is_moving=True, is_jump=False, now_ms=250)

        assert frame == 2  # int(0.25s * 10fps)

    def test_frame_clamps_at_last_frame_for_non_looping_state(self):
        animator = PieceAnimator(make_configs())
        animator.update("piece", is_moving=True, is_jump=False, now_ms=0)

        _, frame = animator.update("piece", is_moving=True, is_jump=False, now_ms=10_000)

        assert frame == 4  # move.frame_count - 1

    def test_switching_from_move_to_jump_restarts_clip(self):
        animator = PieceAnimator(make_configs())
        animator.update("piece", is_moving=True, is_jump=False, now_ms=0)
        animator.update("piece", is_moving=True, is_jump=False, now_ms=200)

        state, frame = animator.update("piece", is_moving=True, is_jump=True, now_ms=250)

        assert state == "jump"
        assert frame == 0


class TestLeavingMotion:
    def test_motion_state_hands_off_to_its_next_state_immediately(self):
        animator = PieceAnimator(make_configs())
        animator.update("piece", is_moving=True, is_jump=False, now_ms=0)

        state, _ = animator.update("piece", is_moving=False, is_jump=False, now_ms=1000)

        assert state == "short_rest"

    def test_jump_hands_off_to_long_rest(self):
        animator = PieceAnimator(make_configs())
        animator.update("piece", is_moving=True, is_jump=True, now_ms=0)

        state, _ = animator.update("piece", is_moving=False, is_jump=False, now_ms=1000)

        assert state == "long_rest"

    def test_stays_in_rest_state_until_its_clip_finishes(self):
        animator = PieceAnimator(make_configs())
        animator.update("piece", is_moving=True, is_jump=False, now_ms=0)
        animator.update("piece", is_moving=False, is_jump=False, now_ms=1000)  # -> short_rest @1000

        state, frame = animator.update("piece", is_moving=False, is_jump=False, now_ms=1200)

        assert state == "short_rest"
        assert frame == 0  # int(0.2s * 2fps)

    def test_advances_to_next_state_once_clip_duration_elapses(self):
        animator = PieceAnimator(make_configs())
        animator.update("piece", is_moving=True, is_jump=False, now_ms=0)
        animator.update("piece", is_moving=False, is_jump=False, now_ms=1000)  # -> short_rest @1000
        # short_rest clip duration = frame_count / fps * 1000 = 2 / 2 * 1000 = 1000ms

        state, frame = animator.update("piece", is_moving=False, is_jump=False, now_ms=2100)

        assert state == "idle"
        assert frame == 0

    def test_idle_frame_wraps_around_when_looping(self):
        animator = PieceAnimator(make_configs())
        animator.update("piece", is_moving=False, is_jump=False, now_ms=0)

        _, frame = animator.update("piece", is_moving=False, is_jump=False, now_ms=1250)

        assert frame == 1  # int(1.25s * 4fps) % 4 == 5 % 4


class TestMultiplePieces:
    def test_pieces_are_tracked_independently(self):
        animator = PieceAnimator(make_configs())

        animator.update("a", is_moving=True, is_jump=False, now_ms=0)
        state_b, frame_b = animator.update("b", is_moving=False, is_jump=False, now_ms=0)
        state_a, _ = animator.update("a", is_moving=True, is_jump=False, now_ms=0)

        assert state_a == "move"
        assert state_b == "idle"
        assert frame_b == 0


class TestForget:
    def test_forgotten_piece_restarts_from_idle(self):
        animator = PieceAnimator(make_configs())
        animator.update("piece", is_moving=True, is_jump=False, now_ms=0)

        animator.forget("piece")
        state, frame = animator.update("piece", is_moving=False, is_jump=False, now_ms=5000)

        assert state == "idle"
        assert frame == 0

    def test_forgetting_unknown_piece_is_a_no_op(self):
        animator = PieceAnimator(make_configs())

        animator.forget("never-seen")  # should not raise
