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


def interpolate(from_px: Pixel, to_px: Pixel, t: float) -> Pixel:
    """Straight-line pixel position at fraction t of the way from from_px to to_px."""
    t = max(0.0, min(1.0, t))
    x = from_px[0] + (to_px[0] - from_px[0]) * t
    y = from_px[1] + (to_px[1] - from_px[1]) * t
    return (x, y)
