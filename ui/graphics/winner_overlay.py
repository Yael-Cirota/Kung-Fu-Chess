"""
The winner banner shown once a game ends: a translucent wash over the board
plus a pulsing "White Wins!"/"Black Wins!" title and the final score, all
timed off the wall clock (the engine clock is frozen once game_over is true,
so there is nothing left to interpolate from it).

`format_winner_title`/`format_winner_subtitle` turn data into text with no
pixels involved; `backdrop_alpha`/`title_pulse_scale` turn an elapsed
wall-clock duration into an animation curve with no canvas involved. Keeping
all four pure means the animation math is unit-testable without a canvas, and
`WinnerOverlay.draw` is left doing nothing but layout: measuring text through
the Canvas seam (never cv2 itself) so the banner centers correctly regardless
of string length or board width.
"""

import math


def format_winner_title(winner_color: str) -> str:
    """'w'/'b' -> 'White Wins!' / 'Black Wins!'."""
    label = "White" if winner_color == "w" else "Black"
    return f"{label} Wins!"


def format_winner_subtitle(scoreboard) -> str:
    """The final score line, e.g. 'White 12 - Black 7'."""
    return f"White {scoreboard.white} - Black {scoreboard.black}"


def backdrop_alpha(elapsed_ms: float, fade_in_ms: float, max_alpha: float) -> float:
    """Linear fade-in from 0 to `max_alpha` over `fade_in_ms`, then held."""
    if fade_in_ms <= 0:
        return max_alpha
    return max_alpha * min(1.0, max(0.0, elapsed_ms / fade_in_ms))


def title_pulse_scale(elapsed_ms: float, base_scale: float, amplitude: float, period_ms: float) -> float:
    """A slow sine breathe around `base_scale`, so the title never sits dead still."""
    if period_ms <= 0:
        return base_scale
    phase = (elapsed_ms % period_ms) / period_ms
    return base_scale + amplitude * math.sin(2 * math.pi * phase)


class WinnerOverlay:
    """
    Draws the game-over banner over the board area of a rendered frame. Holds
    every pixel/color/timing knob so a caller only supplies the winner color,
    the final Scoreboard, the board's pixel size, and how long the overlay has
    been on screen.
    """

    def __init__(
        self, backdrop_color, backdrop_max_alpha, fade_in_ms,
        title_white_color, title_black_color, title_base_font_scale,
        title_pulse_amplitude, title_pulse_period_ms, title_thickness,
        subtitle_color, subtitle_font_scale, subtitle_thickness, title_to_subtitle_gap_px,
    ):
        self._backdrop_color = backdrop_color
        self._backdrop_max_alpha = backdrop_max_alpha
        self._fade_in_ms = fade_in_ms
        self._title_white_color = title_white_color
        self._title_black_color = title_black_color
        self._title_base_font_scale = title_base_font_scale
        self._title_pulse_amplitude = title_pulse_amplitude
        self._title_pulse_period_ms = title_pulse_period_ms
        self._title_thickness = title_thickness
        self._subtitle_color = subtitle_color
        self._subtitle_font_scale = subtitle_font_scale
        self._subtitle_thickness = subtitle_thickness
        self._title_to_subtitle_gap_px = title_to_subtitle_gap_px

    def draw(self, canvas, frame, winner_color, scoreboard, board_w, board_h, elapsed_ms) -> None:
        alpha = backdrop_alpha(elapsed_ms, self._fade_in_ms, self._backdrop_max_alpha)
        canvas.fill_rect(frame, 0, 0, board_w, board_h, self._backdrop_color, alpha=alpha)

        title = format_winner_title(winner_color)
        title_color = self._title_white_color if winner_color == "w" else self._title_black_color
        title_scale = title_pulse_scale(
            elapsed_ms, self._title_base_font_scale, self._title_pulse_amplitude, self._title_pulse_period_ms,
        )
        title_w, title_h = canvas.text_size(title, title_scale, self._title_thickness)
        title_y = board_h // 2
        canvas.draw_text(
            frame, title, (board_w - title_w) // 2, title_y,
            title_scale, title_color, self._title_thickness,
        )

        subtitle = format_winner_subtitle(scoreboard)
        subtitle_w, _ = canvas.text_size(subtitle, self._subtitle_font_scale, self._subtitle_thickness)
        subtitle_y = title_y + self._title_to_subtitle_gap_px
        canvas.draw_text(
            frame, subtitle, (board_w - subtitle_w) // 2, subtitle_y,
            self._subtitle_font_scale, self._subtitle_color, self._subtitle_thickness,
        )
