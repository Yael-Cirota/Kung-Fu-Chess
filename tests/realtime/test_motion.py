from kfchess.model.position import Position
from kfchess.realtime.motion import MoveOutcome, MoveOutcomeStatus, PendingMove


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


class TestPendingMove:
    def test_stores_fields(self):
        piece = object()
        move = PendingMove(piece=piece, from_pos=Position(0, 0), to_pos=Position(0, 1), execute_at=1000)

        assert move.piece is piece
        assert move.from_pos == Position(0, 0)
        assert move.to_pos == Position(0, 1)
        assert move.execute_at == 1000
