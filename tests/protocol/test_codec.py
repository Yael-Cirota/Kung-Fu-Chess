import pytest

from kfchess.api.dto import MotionInfo, MoveLogEntry, PieceView, Position, Scoreboard
from protocol import codec, messages as m
from protocol.errors import ProtocolError


def roundtrip(message):
    decoded = codec.decode(codec.encode(message))
    assert decoded == message
    return decoded


class TestClientToServerRoundTrip:
    def test_login_request(self):
        roundtrip(m.LoginRequest(username="alice", password="secret"))

    def test_register_request(self):
        roundtrip(m.RegisterRequest(username="bob", password="hunter2"))

    def test_play_request(self):
        roundtrip(m.PlayRequest())

    def test_cancel_queue_request(self):
        roundtrip(m.CancelQueueRequest())

    def test_create_room_request(self):
        roundtrip(m.CreateRoomRequest())

    def test_join_room_request(self):
        roundtrip(m.JoinRoomRequest(room_id="abc123"))

    def test_leave_room_request(self):
        roundtrip(m.LeaveRoomRequest(room_id="abc123"))

    def test_move_request(self):
        roundtrip(m.MoveRequest(from_row=0, from_col=0, to_row=2, to_col=2, client_seq=7))

    def test_heartbeat(self):
        roundtrip(m.Heartbeat(client_ms=1234))


class TestServerToClientRoundTrip:
    def test_auth_ok(self):
        roundtrip(m.AuthOk(user_id=1, username="alice", elo=1200))

    def test_auth_error(self):
        roundtrip(m.AuthError(reason="bad_credentials"))

    def test_match_found(self):
        roundtrip(m.MatchFound(room_id="r1", color="w"))

    def test_match_timed_out(self):
        roundtrip(m.MatchTimedOut())

    def test_room_created(self):
        roundtrip(m.RoomCreated(room_id="r1"))

    def test_room_joined(self):
        roundtrip(m.RoomJoined(room_id="r1", role="viewer", players=["alice", "bob"]))

    def test_game_started(self):
        roundtrip(m.GameStarted(server_ms=0, rows=8, cols=8))

    def test_state_update_with_full_board_motion_and_scoreboard_fidelity(self):
        piece = PieceView(piece_id=1, symbol="wR", color="w", cell=Position(0, 0))
        motion = MotionInfo(from_pos=Position(0, 0), to_pos=Position(0, 3), start_ms=0, duration_ms=3000, is_jump=False)
        move_entry = MoveLogEntry(color="w", symbol="wR", from_pos=Position(0, 0), to_pos=Position(0, 3))
        scoreboard = Scoreboard(white=3, black=1)

        state_update = m.StateUpdate(
            server_ms=1500,
            seq=42,
            pieces=[piece],
            motions=[m.MotionEntry(piece_id=1, motion=motion)],
            move_log=[move_entry],
            scoreboard=scoreboard,
            game_over=False,
        )

        decoded = roundtrip(state_update)
        assert decoded.pieces[0].cell == Position(0, 0)
        assert decoded.motions[0].motion.to_pos == Position(0, 3)
        assert decoded.scoreboard.white == 3

    def test_state_update_with_empty_collections(self):
        roundtrip(m.StateUpdate(
            server_ms=0, seq=0, pieces=[], motions=[], move_log=[],
            scoreboard=Scoreboard(white=0, black=0), game_over=False,
        ))

    def test_move_ack_accepted(self):
        roundtrip(m.MoveAck(client_seq=3, accepted=True, reason=None))

    def test_move_ack_rejected_carries_a_reason(self):
        roundtrip(m.MoveAck(client_seq=3, accepted=False, reason="cooldown_active"))

    def test_opponent_disconnected(self):
        roundtrip(m.OpponentDisconnected(deadline_server_ms=20000))

    def test_opponent_reconnected(self):
        roundtrip(m.OpponentReconnected())

    def test_game_ended(self):
        roundtrip(m.GameEnded(winner="w", reason="king_captured", elo_delta=8))

    def test_game_ended_with_no_winner(self):
        roundtrip(m.GameEnded(winner=None, reason="draw", elo_delta=0))

    def test_heartbeat_ack(self):
        roundtrip(m.HeartbeatAck(client_ms=1000, server_ms=1005))

    def test_delta_event(self):
        piece = PieceView(piece_id=1, symbol="wR", color="w", cell=Position(0, 3))
        roundtrip(m.DeltaEvent(
            kind="piece_captured",
            trace_id="trace-1",
            at_ms=1000,
            piece=piece,
            from_pos=Position(0, 0),
            to_pos=Position(0, 3),
            captured=piece,
            beneficiary_color="w",
            scoreboard=Scoreboard(white=1, black=0),
        ))

    def test_delta_event_with_no_trace_id_or_positions(self):
        roundtrip(m.DeltaEvent(
            kind="game_over",
            trace_id=None,
            at_ms=1000,
            piece=None,
            from_pos=None,
            to_pos=None,
            captured=None,
            beneficiary_color="w",
            scoreboard=Scoreboard(white=1, black=0),
        ))


class TestMalformedInputRejection:
    def test_invalid_json_raises_malformed_json(self):
        with pytest.raises(ProtocolError) as excinfo:
            codec.decode("{not json")
        assert excinfo.value.reason == ProtocolError.MALFORMED_JSON

    def test_json_that_is_not_an_object_raises_malformed_json(self):
        with pytest.raises(ProtocolError) as excinfo:
            codec.decode("[1, 2, 3]")
        assert excinfo.value.reason == ProtocolError.MALFORMED_JSON

    def test_missing_type_key_raises_malformed_json(self):
        with pytest.raises(ProtocolError) as excinfo:
            codec.decode('{"payload": {}}')
        assert excinfo.value.reason == ProtocolError.MALFORMED_JSON

    def test_missing_payload_key_raises_malformed_json(self):
        with pytest.raises(ProtocolError) as excinfo:
            codec.decode('{"type": "heartbeat"}')
        assert excinfo.value.reason == ProtocolError.MALFORMED_JSON

    def test_unknown_type_discriminator_raises_unknown_type(self):
        with pytest.raises(ProtocolError) as excinfo:
            codec.decode('{"type": "not_a_real_type", "payload": {}}')
        assert excinfo.value.reason == ProtocolError.UNKNOWN_TYPE

    def test_missing_required_field_raises_schema_mismatch(self):
        with pytest.raises(ProtocolError) as excinfo:
            codec.decode('{"type": "heartbeat", "payload": {}}')
        assert excinfo.value.reason == ProtocolError.SCHEMA_MISMATCH

    def test_nested_field_that_should_be_an_object_but_is_not_raises_schema_mismatch(self):
        # move_ack.reason should be a string or null - MoveAck itself has no
        # nested dataclass field, so use state_update.scoreboard: it must be
        # an object, not a bare number.
        with pytest.raises(ProtocolError) as excinfo:
            codec.decode(
                '{"type": "state_update", "payload": {"server_ms": 0, "seq": 0, '
                '"pieces": [], "motions": [], "move_log": [], '
                '"scoreboard": 42, "game_over": false}}'
            )
        assert excinfo.value.reason == ProtocolError.SCHEMA_MISMATCH

    def test_field_that_should_be_a_list_but_is_not_raises_schema_mismatch(self):
        with pytest.raises(ProtocolError) as excinfo:
            codec.decode(
                '{"type": "state_update", "payload": {"server_ms": 0, "seq": 0, '
                '"pieces": "not_a_list", "motions": [], "move_log": [], '
                '"scoreboard": {"white": 0, "black": 0}, "game_over": false}}'
            )
        assert excinfo.value.reason == ProtocolError.SCHEMA_MISMATCH

    def test_nested_dataclass_missing_field_raises_schema_mismatch(self):
        # state_update.pieces is a List[PieceView]; a PieceView dict missing
        # its "cell" field must be rejected during the recursive rebuild.
        with pytest.raises(ProtocolError) as excinfo:
            codec.decode(
                '{"type": "state_update", "payload": {"server_ms": 0, "seq": 0, '
                '"pieces": [{"piece_id": 1, "symbol": "wR", "color": "w"}], '
                '"motions": [], "move_log": [], '
                '"scoreboard": {"white": 0, "black": 0}, "game_over": false}}'
            )
        assert excinfo.value.reason == ProtocolError.SCHEMA_MISMATCH


class TestEncodeUnknownMessageType:
    def test_encoding_an_unregistered_type_raises_key_error(self):
        with pytest.raises(KeyError):
            codec.encode(object())
