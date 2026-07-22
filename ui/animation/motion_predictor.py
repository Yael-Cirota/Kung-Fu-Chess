from typing import Tuple

Pixel = Tuple[float, float]


def progress(start_ms: int, duration_ms: int, now_ms: int) -> float:
    """
    Fraction in [0, 1] of a motion elapsed by now_ms, clamped at both ends.
    Takes now_ms as a parameter rather than reading a clock so it can be
    tested without waiting in real time.
    """
    if duration_ms <= 0:
        return 1.0
    return max(0.0, min(1.0, (now_ms - start_ms) / duration_ms))


def ease_in_out(t: float) -> float:
    """
    Smoothstep easing of a progress fraction: eases in and out so a piece
    accelerates off its origin and decelerates into its destination instead of
    gliding at a constant speed. This is a *monotonic remap of the fraction
    only* - endpoints are exact (ease(0)=0, ease(1)=1) and the midpoint is
    unmoved (ease(0.5)=0.5), so arrival time and the resolved landing cell are
    untouched. It never overshoots [0, 1], so a piece is never drawn past its
    destination. Applied to the engine-clock fraction, so it stays inside the
    "two clocks" rule (position remains engine-derived; only its shape changes).
    """
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def interpolate(from_px: Pixel, to_px: Pixel, t: float) -> Pixel:
    """Straight-line pixel position at fraction t of the way from from_px to to_px."""
    t = max(0.0, min(1.0, t))
    x = from_px[0] + (to_px[0] - from_px[0]) * t
    y = from_px[1] + (to_px[1] - from_px[1]) * t
    return (x, y)
