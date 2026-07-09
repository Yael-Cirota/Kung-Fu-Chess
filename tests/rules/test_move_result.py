from kfchess.rules.move_result import MoveRejectionReason, MoveValidationResult


class TestMoveRejectionReason:
    def test_members_are_distinct(self):
        members = list(MoveRejectionReason)
        assert len(members) == len(set(members))

    def test_expected_members_exist(self):
        expected = {
            "OUT_OF_BOUNDS",
            "EMPTY_ORIGIN",
            "NOT_A_LEGAL_SHAPE",
            "BLOCKED",
            "FRIENDLY_FIRE",
            "PIECE_ALREADY_MOVING",
            "GAME_OVER",
        }
        actual = {member.name for member in MoveRejectionReason}
        assert expected <= actual


class TestMoveValidationResult:
    def test_ok_is_legal_with_no_reason(self):
        result = MoveValidationResult.ok()
        assert result.legal is True
        assert result.reason is None

    def test_reject_is_illegal_with_given_reason(self):
        result = MoveValidationResult.reject(MoveRejectionReason.BLOCKED)
        assert result.legal is False
        assert result.reason is MoveRejectionReason.BLOCKED

    def test_equality(self):
        assert MoveValidationResult.ok() == MoveValidationResult.ok()
        assert MoveValidationResult.reject(
            MoveRejectionReason.FRIENDLY_FIRE
        ) == MoveValidationResult.reject(MoveRejectionReason.FRIENDLY_FIRE)
        assert MoveValidationResult.reject(
            MoveRejectionReason.FRIENDLY_FIRE
        ) != MoveValidationResult.reject(MoveRejectionReason.BLOCKED)
