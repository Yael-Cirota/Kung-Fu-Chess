from common.clock import Clock, ManualClock, MonotonicClock


class TestManualClock:
    def test_starts_at_given_time(self):
        assert ManualClock(500).now_ms() == 500

    def test_defaults_to_zero(self):
        assert ManualClock().now_ms() == 0

    def test_advance_moves_time_forward(self):
        clock = ManualClock()
        clock.advance(250)
        assert clock.now_ms() == 250
        clock.advance(250)
        assert clock.now_ms() == 500

    def test_satisfies_clock_protocol(self):
        assert isinstance(ManualClock(), Clock)


class TestMonotonicClock:
    def test_satisfies_clock_protocol(self):
        assert isinstance(MonotonicClock(), Clock)

    def test_now_ms_is_non_negative_and_advances(self):
        clock = MonotonicClock()
        first = clock.now_ms()
        second = clock.now_ms()
        assert first >= 0
        assert second >= first
