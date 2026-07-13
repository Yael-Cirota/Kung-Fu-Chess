from kfchess.realtime.cooldown import CooldownPolicy, CooldownTracker


class TestCooldownPolicy:
    def test_duration_for_move_returns_move_cooldown(self):
        policy = CooldownPolicy(move_cooldown_ms=300, jump_cooldown_ms=900)

        assert policy.duration_for(is_jump=False) == 300

    def test_duration_for_jump_returns_jump_cooldown(self):
        policy = CooldownPolicy(move_cooldown_ms=300, jump_cooldown_ms=900)

        assert policy.duration_for(is_jump=True) == 900

    def test_defaults_are_independent_of_each_other(self):
        policy = CooldownPolicy()

        assert policy.duration_for(is_jump=False) != policy.duration_for(is_jump=True)


class TestCooldownTracker:
    def test_is_active_false_before_any_cooldown_started(self):
        tracker = CooldownTracker()

        assert tracker.is_active(object(), now_ms=0) is False

    def test_is_active_true_before_expiry(self):
        tracker = CooldownTracker()
        piece = object()

        tracker.start(piece, expires_at_ms=1000)

        assert tracker.is_active(piece, now_ms=999) is True

    def test_is_active_false_at_and_after_expiry(self):
        tracker = CooldownTracker()
        piece = object()

        tracker.start(piece, expires_at_ms=1000)

        assert tracker.is_active(piece, now_ms=1000) is False
        assert tracker.is_active(piece, now_ms=1001) is False

    def test_restarting_cooldown_overwrites_previous_expiry(self):
        tracker = CooldownTracker()
        piece = object()

        tracker.start(piece, expires_at_ms=1000)
        tracker.start(piece, expires_at_ms=2000)

        assert tracker.is_active(piece, now_ms=1500) is True

    def test_clear_removes_active_cooldown(self):
        tracker = CooldownTracker()
        piece = object()

        tracker.start(piece, expires_at_ms=1000)
        tracker.clear(piece)

        assert tracker.is_active(piece, now_ms=0) is False

    def test_tracks_multiple_pieces_independently(self):
        tracker = CooldownTracker()
        first, second = object(), object()

        tracker.start(first, expires_at_ms=1000)

        assert tracker.is_active(first, now_ms=500) is True
        assert tracker.is_active(second, now_ms=500) is False
