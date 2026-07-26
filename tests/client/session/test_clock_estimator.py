from client.session.clock_estimator import ClockEstimator


class TestJoinInProgress:
    """The highest-risk case this design exists for: a spectator or rejoining
    player receives their first snapshot with server_ms far ahead of their
    own elapsed local time. See 'the one non-obvious bug this design exists
    to avoid'."""

    def test_first_snapshot_snaps_local_ms_to_the_callers_elapsed_time_not_server_ms(self):
        estimator = ClockEstimator()

        estimator.on_snapshot(server_ms=45000, local_ms=0)

        assert estimator.local_ms == 0

    def test_motions_rebase_relative_to_the_new_offset(self):
        estimator = ClockEstimator()
        estimator.on_snapshot(server_ms=45000, local_ms=0)

        # A motion that started at server time 44000 (1000ms before this
        # snapshot) should land 1000ms before local_ms's origin too.
        assert estimator.to_local(44000) == -1000

    def test_after_joining_advancing_moves_local_ms_forward_normally(self):
        estimator = ClockEstimator()
        estimator.on_snapshot(server_ms=45000, local_ms=0)

        estimator.advance(16)

        assert estimator.local_ms == 16


class TestMonotonicity:
    def test_local_ms_never_goes_backward_even_if_the_server_clock_jumps_back(self):
        estimator = ClockEstimator()
        estimator.on_snapshot(server_ms=10000, local_ms=0)
        estimator.advance(100)
        before = estimator.local_ms

        # A server timestamp earlier than expected given elapsed local time -
        # this should never move local_ms backward.
        estimator.on_snapshot(server_ms=5000, local_ms=100)
        estimator.advance(16)

        assert estimator.local_ms >= before

    def test_advance_never_produces_a_negative_step(self):
        estimator = ClockEstimator(min_catchup_rate=0.5)
        estimator.on_snapshot(server_ms=10000, local_ms=1000)
        # local_ms is far ahead of what the next sample implies.
        estimator.on_snapshot(server_ms=10000, local_ms=1)

        before = estimator.local_ms
        estimator.advance(1)

        assert estimator.local_ms >= before


class TestDriftIsBoundedByCatchupRates:
    def test_small_drift_glides_within_one_frames_max_catchup_rate(self):
        estimator = ClockEstimator(max_catchup_rate=1.20, resync_threshold_ms=1000)
        estimator.on_snapshot(server_ms=10000, local_ms=0)
        estimator.advance(1000)  # local_ms == 1000

        # A fresh sample implying local_ms should be 1030 (30ms behind) -
        # well under the resync threshold, so this should glide, not snap.
        estimator.on_snapshot(server_ms=11030, local_ms=1030)
        before = estimator.local_ms
        estimator.advance(100)

        # capped at 100 * 1.20 = 120ms this frame, not a 30ms jump
        assert estimator.local_ms - before <= 120
        assert estimator.local_ms - before > 100

    def test_drift_is_fully_absorbed_over_enough_frames(self):
        estimator = ClockEstimator(max_catchup_rate=1.20, resync_threshold_ms=1000)
        estimator.on_snapshot(server_ms=10000, local_ms=0)
        estimator.advance(1000)

        estimator.on_snapshot(server_ms=11030, local_ms=1030)
        for _ in range(20):
            estimator.advance(16)

        # The 30ms drift is fully absorbed (on top of the 20 frames' own
        # 16ms each) well before the loop ends, then tracks 1:1 again.
        assert estimator.local_ms == 1000 + 30 + 20 * 16

    def test_large_drift_snaps_instead_of_gliding(self):
        estimator = ClockEstimator(resync_threshold_ms=1000)
        estimator.on_snapshot(server_ms=10000, local_ms=0)
        estimator.advance(1000)  # local_ms == 1000, offset == 10000

        # One frame elapses (local_ms == 1016) but server_ms implies a wildly
        # different offset (12000 vs 10000) - a 2000ms jump past the threshold.
        estimator.on_snapshot(server_ms=13016, local_ms=1016)

        # A snap sets local_ms straight to the caller's own value and clears
        # any pending glide, rather than easing toward it.
        assert estimator.local_ms == 1016
        before = estimator.local_ms
        estimator.advance(16)
        assert estimator.local_ms == before + 16

    def test_being_ahead_slows_down_via_min_catchup_rate(self):
        estimator = ClockEstimator(min_catchup_rate=0.85, resync_threshold_ms=1000)
        estimator.on_snapshot(server_ms=10000, local_ms=0)
        estimator.advance(1000)

        # Implies local_ms should only be 970 (client is 30ms ahead).
        estimator.on_snapshot(server_ms=10970, local_ms=970)
        before = estimator.local_ms
        estimator.advance(100)

        assert estimator.local_ms - before < 100
        assert estimator.local_ms - before >= 85  # 100 * 0.85


class TestHeartbeatAckRebasing:
    def test_corrects_for_half_the_round_trip_time(self):
        estimator = ClockEstimator()
        # sent at 0, ack received at 100 -> 100ms RTT -> 50ms half-RTT.
        # server_ms=5000 was stamped mid-flight; the true "now" is 5050.
        estimator.on_heartbeat_ack(client_sent_ms=0, server_ms=5000, client_recv_ms=100)

        assert estimator.to_local(5050) == 100

    def test_establishes_the_origin_ahead_of_the_first_state_update(self):
        # A spectator whose join races the broadcast loop: the heartbeat ack
        # lands before the first StateUpdate and must still establish a sane
        # origin on its own - the first sample always snaps.
        estimator = ClockEstimator()

        estimator.on_heartbeat_ack(client_sent_ms=0, server_ms=45000, client_recv_ms=10)

        assert estimator.local_ms == 10
        assert estimator.to_local(45005) == 10  # 45000 + 5ms half-RTT compensation
