from movement_tracker import MovementTracker
from pieces import Rook


def test_set_moving_and_is_moving_with_piece():
    tracker = MovementTracker()
    rook = Rook('w')

    assert tracker.is_moving(rook) is False
    tracker.set_moving(rook)
    assert tracker.is_moving(rook) is True


def test_set_arrived_removes_piece_from_moving_set():
    tracker = MovementTracker()
    rook = Rook('w')

    tracker.set_moving(rook)
    assert tracker.is_moving(rook) is True

    tracker.set_arrived(rook)
    assert tracker.is_moving(rook) is False


def test_set_moving_ignores_none_piece():
    tracker = MovementTracker()

    tracker.set_moving(None)

    assert tracker.is_moving(None) is False


def test_set_arrived_ignores_none_piece():
    tracker = MovementTracker()

    tracker.set_arrived(None)

    assert tracker.is_moving(None) is False