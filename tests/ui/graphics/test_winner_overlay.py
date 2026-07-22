import math

from kfchess.api import Scoreboard
from ui.graphics.winner_overlay import (
    WinnerOverlay, backdrop_alpha, format_winner_subtitle, format_winner_title, title_pulse_scale,
)


class FakeCanvas:
    """Records fill_rect/draw_text/text_size calls so overlay layout can be asserted without pixels."""

    def __init__(self):
        self.fills = []  # (x, y, w, h, color, alpha)
        self.texts = []  # (text, x, y, scale, color, thickness)

    def fill_rect(self, frame, x, y, w, h, color, alpha=1.0):
        self.fills.append((x, y, w, h, color, alpha))

    def draw_text(self, frame, text, x, y, font_scale, color, thickness=1):
        self.texts.append((text, x, y, font_scale, color, thickness))

    def text_size(self, text, font_scale, thickness=1):
        # A fake monospace metric: deterministic and easy to reason about in assertions.
        return (len(text) * 10, 20)


def make_overlay(fade_in_ms=400, backdrop_max_alpha=0.65, title_pulse_period_ms=1400, title_pulse_amplitude=0.08):
    return WinnerOverlay(
        backdrop_color=(20, 20, 20), backdrop_max_alpha=backdrop_max_alpha, fade_in_ms=fade_in_ms,
        title_white_color=(9, 9, 9), title_black_color=(8, 8, 8), title_base_font_scale=1.6,
        title_pulse_amplitude=title_pulse_amplitude, title_pulse_period_ms=title_pulse_period_ms,
        title_thickness=3, subtitle_color=(7, 7, 7), subtitle_font_scale=0.8, subtitle_thickness=2,
        title_to_subtitle_gap_px=46,
    )


class TestFormatWinnerTitle:
    def test_white_wins(self):
        assert format_winner_title("w") == "White Wins!"

    def test_black_wins(self):
        assert format_winner_title("b") == "Black Wins!"


class TestFormatWinnerSubtitle:
    def test_reads_as_both_totals(self):
        assert format_winner_subtitle(Scoreboard(white=12, black=7)) == "White 12 - Black 7"


class TestBackdropAlpha:
    def test_starts_at_zero(self):
        assert backdrop_alpha(0, fade_in_ms=400, max_alpha=0.65) == 0.0

    def test_ramps_linearly_mid_fade(self):
        assert backdrop_alpha(200, fade_in_ms=400, max_alpha=0.65) == 0.325

    def test_holds_at_max_after_the_fade_completes(self):
        assert backdrop_alpha(400, fade_in_ms=400, max_alpha=0.65) == 0.65
        assert backdrop_alpha(10000, fade_in_ms=400, max_alpha=0.65) == 0.65

    def test_instant_when_fade_in_is_zero(self):
        assert backdrop_alpha(0, fade_in_ms=0, max_alpha=0.65) == 0.65


class TestTitlePulseScale:
    def test_starts_at_base_scale(self):
        assert title_pulse_scale(0, base_scale=1.6, amplitude=0.08, period_ms=1400) == 1.6

    def test_stays_within_the_amplitude_band(self):
        for elapsed in range(0, 3000, 37):
            scale = title_pulse_scale(elapsed, base_scale=1.6, amplitude=0.08, period_ms=1400)
            assert 1.6 - 0.08 <= scale <= 1.6 + 0.08

    def test_matches_the_sine_curve_at_a_quarter_period(self):
        scale = title_pulse_scale(350, base_scale=1.6, amplitude=0.08, period_ms=1400)
        assert math.isclose(scale, 1.6 + 0.08, rel_tol=1e-9)

    def test_flat_when_period_is_zero(self):
        assert title_pulse_scale(500, base_scale=1.6, amplitude=0.08, period_ms=0) == 1.6


class TestDraw:
    def test_washes_the_full_board_area(self):
        canvas = FakeCanvas()
        make_overlay().draw(canvas, frame=object(), winner_color="w", scoreboard=Scoreboard(0, 0),
                             board_w=800, board_h=800, elapsed_ms=400)

        assert canvas.fills == [(0, 0, 800, 800, (20, 20, 20), 0.65)]

    def test_draws_the_title_in_the_winners_color(self):
        canvas = FakeCanvas()
        make_overlay().draw(canvas, frame=object(), winner_color="b", scoreboard=Scoreboard(1, 2),
                             board_w=800, board_h=800, elapsed_ms=0)

        by_text = {t[0]: t for t in canvas.texts}
        assert by_text["Black Wins!"][4] == (8, 8, 8)

    def test_title_and_subtitle_are_both_centered_on_board_width(self):
        canvas = FakeCanvas()
        make_overlay().draw(canvas, frame=object(), winner_color="w", scoreboard=Scoreboard(12, 7),
                             board_w=800, board_h=800, elapsed_ms=0)

        by_text = {t[0]: t for t in canvas.texts}
        title_w = len("White Wins!") * 10
        subtitle_w = len("White 12 - Black 7") * 10
        assert by_text["White Wins!"][1] == (800 - title_w) // 2
        assert by_text["White 12 - Black 7"][1] == (800 - subtitle_w) // 2

    def test_subtitle_sits_below_the_title_by_the_configured_gap(self):
        canvas = FakeCanvas()
        make_overlay().draw(canvas, frame=object(), winner_color="w", scoreboard=Scoreboard(0, 0),
                             board_w=800, board_h=600, elapsed_ms=0)

        by_text = {t[0]: t for t in canvas.texts}
        title_y = by_text["White Wins!"][2]
        subtitle_y = by_text["White 0 - Black 0"][2]
        assert title_y == 300  # board_h // 2
        assert subtitle_y == title_y + 46
