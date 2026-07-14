from kfchess.model.position import Position
from kfchess.realtime.motion import Motion, MoveOutcome, MoveOutcomeStatus


class TestMoveOutcome:
    def test_defaults_captured_piece_to_none(self):
        outcome = MoveOutcome(
            status=MoveOutcomeStatus.EXECUTED,
            piece=object(),
            from_pos=Position(0, 0),
            to_pos=Position(0, 1),
        )
        assert outcome.captured_piece is None

    def test_status_members_are_distinct(self):
        members = list(MoveOutcomeStatus)
        assert len(members) == len(set(members))


class TestMotion:
    def test_stores_fields(self):
        piece = object()
        motion = Motion(
            piece=piece, origin=Position(0, 0), current=Position(0, 0),
            remaining=[Position(0, 1), Position(0, 2)], next_step_at=1000,
            step_duration_ms=1000, is_jump=False, seq=1,
        )

        assert motion.piece is piece
        assert motion.origin == Position(0, 0)
        assert motion.current == Position(0, 0)
        assert motion.remaining == [Position(0, 1), Position(0, 2)]
        assert motion.next_step_at == 1000
        assert motion.step_duration_ms == 1000
        assert motion.is_jump is False
        assert motion.seq == 1

    def test_target_is_last_square_of_remaining_path(self):
        motion = Motion(
            piece=object(), origin=Position(0, 0), current=Position(0, 1),
            remaining=[Position(0, 2), Position(0, 3)], next_step_at=0,
            step_duration_ms=1000, is_jump=False, seq=1,
        )
        assert motion.target == Position(0, 3)

    def test_target_falls_back_to_current_when_path_exhausted(self):
        motion = Motion(
            piece=object(), origin=Position(4, 4), current=Position(4, 4),
            remaining=[], next_step_at=0, step_duration_ms=1000, is_jump=True, seq=1,
        )
        assert motion.target == Position(4, 4)
