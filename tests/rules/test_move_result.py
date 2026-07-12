from kfchess.rules.move_result import MoveRejectionReason, MoveValidation


class TestMoveRejectionReason:
    def test_expected_reasons_are_stable_strings(self):
        assert MoveRejectionReason.OK == "ok"
        assert MoveRejectionReason.OUTSIDE_BOARD == "outside_board"
        assert MoveRejectionReason.EMPTY_SOURCE == "empty_source"
        assert MoveRejectionReason.FRIENDLY_DESTINATION == "friendly_destination"
        assert MoveRejectionReason.ILLEGAL_PIECE_MOVE == "illegal_piece_move"
        assert MoveRejectionReason.PIECE_ALREADY_MOVING == "piece_already_moving"
        assert MoveRejectionReason.GAME_OVER == "game_over"


class TestMoveValidation:
    def test_ok_is_valid_with_ok_reason(self):
        result = MoveValidation.ok()
        assert result.is_valid is True
        assert result.reason == "ok"

    def test_invalid_carries_given_reason(self):
        result = MoveValidation.invalid(MoveRejectionReason.FRIENDLY_DESTINATION)
        assert result.is_valid is False
        assert result.reason == MoveRejectionReason.FRIENDLY_DESTINATION

    def test_equality(self):
        assert MoveValidation.ok() == MoveValidation.ok()
        assert MoveValidation.invalid(
            MoveRejectionReason.FRIENDLY_DESTINATION
        ) == MoveValidation.invalid(MoveRejectionReason.FRIENDLY_DESTINATION)
        assert MoveValidation.invalid(
            MoveRejectionReason.FRIENDLY_DESTINATION
        ) != MoveValidation.invalid(MoveRejectionReason.ILLEGAL_PIECE_MOVE)
