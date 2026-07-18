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


class TestEaseInOut:
    def test_endpoints_are_exact(self):
        assert motion_predictor.ease_in_out(0.0) == 0.0
        assert motion_predictor.ease_in_out(1.0) == 1.0

    def test_midpoint_is_unmoved(self):
        # Smoothstep is symmetric about 0.5, so the halfway point stays exact -
        # which is what keeps the existing "interpolates on the engine clock"
        # midpoint assertion valid once easing is applied.
        assert motion_predictor.ease_in_out(0.5) == 0.5

    def test_eases_in_slower_than_linear_early(self):
        # smoothstep(0.25) = 0.25^2 * (3 - 0.5) = 0.15625, i.e. behind linear.
        assert motion_predictor.ease_in_out(0.25) == 0.15625

    def test_eases_out_faster_than_linear_late(self):
        # Symmetric: smoothstep(0.75) = 1 - smoothstep(0.25) = 0.84375, ahead of linear.
        assert motion_predictor.ease_in_out(0.75) == 0.84375

    def test_is_monotonic_and_stays_within_unit_interval(self):
        values = [motion_predictor.ease_in_out(i / 20) for i in range(21)]
        assert values == sorted(values)
        assert all(0.0 <= v <= 1.0 for v in values)

    def test_clamps_out_of_range_inputs(self):
        assert motion_predictor.ease_in_out(-0.5) == 0.0
        assert motion_predictor.ease_in_out(1.5) == 1.0


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
