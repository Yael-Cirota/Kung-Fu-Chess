from server.application.disconnect_policy import DisconnectPolicy, ForcedResign


class TestOnDisconnectAndDeadline:
    def test_deadline_is_now_plus_grace_period(self):
        policy = DisconnectPolicy(grace_ms=20000)
        policy.on_disconnect("room-1", "white", now_ms=1000)

        assert policy.deadline_for("room-1", "white") == 21000

    def test_no_deadline_when_never_disconnected(self):
        policy = DisconnectPolicy(grace_ms=20000)
        assert policy.deadline_for("room-1", "white") is None


class TestOnReconnect:
    def test_cancels_the_pending_countdown(self):
        policy = DisconnectPolicy(grace_ms=20000)
        policy.on_disconnect("room-1", "white", now_ms=0)

        policy.on_reconnect("room-1", "white")

        assert policy.deadline_for("room-1", "white") is None
        assert policy.tick(now_ms=999999) == []

    def test_reconnect_with_no_pending_countdown_is_a_no_op(self):
        policy = DisconnectPolicy(grace_ms=20000)
        policy.on_reconnect("room-1", "white")  # must not raise


class TestTick:
    def test_before_the_deadline_no_resign(self):
        policy = DisconnectPolicy(grace_ms=20000)
        policy.on_disconnect("room-1", "white", now_ms=0)

        assert policy.tick(now_ms=19999) == []

    def test_at_the_deadline_forces_a_resign(self):
        policy = DisconnectPolicy(grace_ms=20000)
        policy.on_disconnect("room-1", "white", now_ms=0)

        assert policy.tick(now_ms=20000) == [ForcedResign(room_id="room-1", color="white")]

    def test_resign_at_deadline_minus_one_ms_does_not_fire_but_deadline_plus_one_does(self):
        policy = DisconnectPolicy(grace_ms=20000)
        policy.on_disconnect("room-1", "white", now_ms=0)

        assert policy.tick(now_ms=19999) == []
        assert policy.tick(now_ms=20001) == [ForcedResign(room_id="room-1", color="white")]

    def test_a_resigned_countdown_does_not_fire_twice(self):
        policy = DisconnectPolicy(grace_ms=20000)
        policy.on_disconnect("room-1", "white", now_ms=0)
        policy.tick(now_ms=20000)

        assert policy.tick(now_ms=999999) == []

    def test_multiple_independent_countdowns_resign_independently(self):
        policy = DisconnectPolicy(grace_ms=20000)
        policy.on_disconnect("room-1", "white", now_ms=0)
        policy.on_disconnect("room-2", "black", now_ms=5000)

        resigned_first = policy.tick(now_ms=20000)
        assert resigned_first == [ForcedResign(room_id="room-1", color="white")]

        resigned_second = policy.tick(now_ms=25000)
        assert resigned_second == [ForcedResign(room_id="room-2", color="black")]
