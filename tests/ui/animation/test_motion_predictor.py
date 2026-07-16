from ui.animation import motion_predictor


class TestProgress:
    def test_zero_at_start(self):
        assert motion_predictor.progress(start_ms=1000, duration_ms=500, now_ms=1000) == 0.0

    def test_one_at_end(self):
        assert motion_predictor.progress(start_ms=1000, duration_ms=500, now_ms=1500) == 1.0

    def test_fraction_partway_through(self):
        assert motion_predictor.progress(start_ms=1000, duration_ms=500, now_ms=1250) == 0.5

    def test_clamped_below_zero_when_now_precedes_start(self):
        assert motion_predictor.progress(start_ms=1000, duration_ms=500, now_ms=900) == 0.0

    def test_clamped_above_one_when_now_exceeds_duration(self):
        assert motion_predictor.progress(start_ms=1000, duration_ms=500, now_ms=2000) == 1.0

    def test_zero_duration_is_instantly_complete(self):
        assert motion_predictor.progress(start_ms=1000, duration_ms=0, now_ms=1000) == 1.0

    def test_negative_duration_is_instantly_complete(self):
        assert motion_predictor.progress(start_ms=1000, duration_ms=-10, now_ms=1000) == 1.0


class TestInterpolate:
    def test_t_zero_returns_from_position(self):
        assert motion_predictor.interpolate((0.0, 0.0), (100.0, 200.0), 0.0) == (0.0, 0.0)

    def test_t_one_returns_to_position(self):
        assert motion_predictor.interpolate((0.0, 0.0), (100.0, 200.0), 1.0) == (100.0, 200.0)

    def test_t_half_returns_midpoint(self):
        assert motion_predictor.interpolate((0.0, 0.0), (100.0, 200.0), 0.5) == (50.0, 100.0)

    def test_clamps_t_above_one(self):
        assert motion_predictor.interpolate((0.0, 0.0), (10.0, 10.0), 1.5) == (10.0, 10.0)

    def test_clamps_t_below_zero(self):
        assert motion_predictor.interpolate((0.0, 0.0), (10.0, 10.0), -0.5) == (0.0, 0.0)

    def test_handles_negative_direction(self):
        assert motion_predictor.interpolate((100.0, 100.0), (0.0, 0.0), 0.25) == (75.0, 75.0)
