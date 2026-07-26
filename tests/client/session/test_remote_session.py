from common.clock import ManualClock
from common.events import EventNames
from kfchess.api import GameSession
from kfchess.api.dto import MotionInfo, PieceView, Position, Scoreboard
from protocol import messages as m
from client.net.client_link import ClientLink
from client.session.remote_session import RemoteGameSession
from client.session.sync_event_bus import SyncEventBus


class TestSatisfiesGameSessionProtocol:
    def test_isinstance_check_passes(self):
        session = RemoteGameSession(ClientLink())
        assert isinstance(session, GameSession)


class TestRequestMove:
    def test_sends_a_move_request_with_an_incrementing_client_seq(self):
        link = ClientLink()
        session = RemoteGameSession(link)

        session.request_move(Position(0, 0), Position(0, 2))
        session.request_move(Position(1, 1), Position(2, 2))

        first = link.outbound.get_nowait()
        second = link.outbound.get_nowait()
        assert first == m.MoveRequest(from_row=0, from_col=0, to_row=0, to_col=2, client_seq=1)
        assert second == m.MoveRequest(from_row=1, from_col=1, to_row=2, to_col=2, client_seq=2)

    def test_returns_an_optimistic_accepted_result(self):
        session = RemoteGameSession(ClientLink())
        result = session.request_move(Position(0, 0), Position(0, 2))
        assert result.is_accepted is True


class TestJoinInProgress:
    """The highest-risk scenario in the whole design: a spectator or
    rejoining player's first snapshot arrives with server_ms far ahead of
    their own elapsed local time - see 'the one non-obvious bug this design
    exists to avoid'."""

    def test_clock_ms_starts_near_zero_not_at_the_servers_far_advanced_time(self):
        link = ClientLink()
        clock = ManualClock(0)
        session = RemoteGameSession(link, clock=clock)
        link.inbound_game.put(m.GameStarted(server_ms=45000, rows=8, cols=8))

        session.wait(0)

        assert session.clock_ms == 0

    def test_a_motion_that_started_before_the_join_shows_correct_progress(self):
        link = ClientLink()
        clock = ManualClock(0)
        session = RemoteGameSession(link, clock=clock)
        link.inbound_game.put(m.GameStarted(server_ms=45000, rows=8, cols=8))
        session.wait(0)

        # A motion the server started 1000ms before this snapshot, taking
        # 3000ms total - so it's 1/3 of the way through relative to server
        # time, and must render that way locally too.
        raw_motion = MotionInfo(from_pos=Position(0, 0), to_pos=Position(0, 3), start_ms=44000, duration_ms=3000, is_jump=False)
        link.inbound_game.put(m.StateUpdate(
            server_ms=45000, seq=1,
            pieces=[], motions=[m.MotionEntry(piece_id=1, motion=raw_motion)],
            move_log=[], scoreboard=Scoreboard(white=0, black=0),
            game_over=False,
        ))
        session.wait(0)

        motion = session.motion_for(1)
        assert motion.start_ms == -1000  # rebased onto the local timeline
        assert session.clock_ms - motion.start_ms == 1000  # 1000ms of 3000ms elapsed

    def test_motions_keep_advancing_normally_after_joining(self):
        link = ClientLink()
        clock = ManualClock(0)
        session = RemoteGameSession(link, clock=clock)
        link.inbound_game.put(m.GameStarted(server_ms=45000, rows=8, cols=8))
        session.wait(0)

        session.wait(16)
        session.wait(16)

        assert session.clock_ms == 32


class TestDelegatedReads:
    def test_is_within_bounds_delegates_to_the_store(self):
        link = ClientLink()
        session = RemoteGameSession(link, clock=ManualClock(0))
        link.inbound_game.put(m.GameStarted(server_ms=0, rows=8, cols=8))
        session.wait(0)

        assert session.is_within_bounds(Position(0, 0)) is True
        assert session.is_within_bounds(Position(8, 0)) is False

    def test_is_moving_is_true_only_when_a_motion_exists(self):
        link = ClientLink()
        session = RemoteGameSession(link, clock=ManualClock(0))
        assert session.is_moving(1) is False

    def test_motion_for_an_unknown_piece_is_none(self):
        session = RemoteGameSession(ClientLink(), clock=ManualClock(0))
        assert session.motion_for(999) is None

    def test_move_log_and_scoreboard_delegate_to_the_store(self):
        session = RemoteGameSession(ClientLink(), clock=ManualClock(0))
        assert session.move_log() == []
        assert session.scoreboard() == Scoreboard(white=0, black=0)


class TestHeartbeatAckHandling:
    def test_a_heartbeat_ack_feeds_the_clock_estimator(self):
        link = ClientLink()
        clock = ManualClock(0)
        session = RemoteGameSession(link, clock=clock)
        link.inbound_game.put(m.HeartbeatAck(client_ms=0, server_ms=45000))

        session.wait(0)

        assert session.clock_ms == 0


class TestUnmappedDeltaKind:
    def test_a_delta_with_no_bus_mapping_is_a_harmless_no_op(self):
        link = ClientLink()
        bus = SyncEventBus()
        session = RemoteGameSession(link, bus=bus, clock=ManualClock(0))
        link.inbound_game.put(m.DeltaEvent(
            kind="move_aborted", trace_id=None, at_ms=0, piece=None,
            from_pos=None, to_pos=None, captured=None, beneficiary_color=None,
            scoreboard=Scoreboard(white=0, black=0),
        ))

        session.wait(0)  # must not raise


class TestStateUpdateAppliesToTheBoard:
    def make_state_update(self, **overrides):
        defaults = dict(
            server_ms=1000, seq=1,
            pieces=[PieceView(piece_id=1, symbol="wR", color="w", cell=Position(0, 0))],
            motions=[], move_log=[], scoreboard=Scoreboard(white=0, black=0), game_over=False,
        )
        defaults.update(overrides)
        return m.StateUpdate(**defaults)

    def test_piece_at_reflects_the_latest_state_update(self):
        link = ClientLink()
        session = RemoteGameSession(link, clock=ManualClock(0))
        link.inbound_game.put(self.make_state_update())

        session.wait(0)

        assert session.piece_at(Position(0, 0)).symbol == "wR"

    def test_game_over_flag_is_reflected(self):
        link = ClientLink()
        session = RemoteGameSession(link, clock=ManualClock(0))
        link.inbound_game.put(self.make_state_update(game_over=True))

        session.wait(0)

        assert session.game_over is True


class TestGameEnded:
    def test_sets_game_over_and_winner(self):
        link = ClientLink()
        session = RemoteGameSession(link, clock=ManualClock(0))
        link.inbound_game.put(m.GameEnded(winner="white", reason="king_captured", elo_delta=16))

        session.wait(0)

        assert session.game_over is True
        assert session.winner == "white"


class TestDeltaEventHandling:
    def make_delta(self, kind="piece_captured"):
        return m.DeltaEvent(
            kind=kind, trace_id="trace-1", at_ms=100, piece=None,
            from_pos=None, to_pos=None, captured=None, beneficiary_color="white",
            scoreboard=Scoreboard(white=1, black=0),
        )

    def test_a_delta_event_is_republished_on_the_client_bus_under_its_domain_event_name(self):
        link = ClientLink()
        bus = SyncEventBus()
        received = []
        bus.subscribe(EventNames.PIECE_CAPTURED, lambda event: received.append(event))
        session = RemoteGameSession(link, bus=bus, clock=ManualClock(0))
        link.inbound_game.put(self.make_delta())

        session.wait(0)

        assert len(received) == 1
        assert received[0].payload["delta"].kind == "piece_captured"

    def test_a_delta_event_never_mutates_board_position(self):
        link = ClientLink()
        session = RemoteGameSession(link, clock=ManualClock(0))
        link.inbound_game.put(self.make_delta())

        session.wait(0)

        assert session.board_snapshot().pieces() == []

    def test_with_no_bus_wired_a_delta_event_is_a_harmless_no_op(self):
        link = ClientLink()
        session = RemoteGameSession(link, clock=ManualClock(0))
        link.inbound_game.put(self.make_delta())

        session.wait(0)  # must not raise


class TestMoveAckHandling:
    def test_a_rejected_move_ack_publishes_move_rejected(self):
        link = ClientLink()
        bus = SyncEventBus()
        received = []
        bus.subscribe(EventNames.MOVE_REJECTED, lambda event: received.append(event))
        session = RemoteGameSession(link, bus=bus, clock=ManualClock(0))
        link.inbound_game.put(m.MoveAck(client_seq=1, accepted=False, reason="motion_in_progress"))

        session.wait(0)

        assert len(received) == 1
        assert received[0].payload["reason"] == "motion_in_progress"

    def test_with_no_bus_wired_a_rejected_move_ack_is_a_harmless_no_op(self):
        link = ClientLink()
        session = RemoteGameSession(link, clock=ManualClock(0))
        link.inbound_game.put(m.MoveAck(client_seq=1, accepted=False, reason="motion_in_progress"))

        session.wait(0)  # must not raise

    def test_an_accepted_move_ack_publishes_nothing(self):
        link = ClientLink()
        bus = SyncEventBus()
        received = []
        bus.subscribe(EventNames.MOVE_REJECTED, lambda event: received.append(event))
        session = RemoteGameSession(link, bus=bus, clock=ManualClock(0))
        link.inbound_game.put(m.MoveAck(client_seq=1, accepted=True, reason=None))

        session.wait(0)

        assert received == []
