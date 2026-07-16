from dataclasses import dataclass


@dataclass(frozen=True)
class PieceVisualState:
    """
    What BoardRenderer needs to draw one piece on one frame: where its
    top-left pixel sits right now (which may be mid-glide between two
    squares) and which animation sprite (state + frame) to show there.
    Built once per frame by the caller from PendingMotionTracker +
    motion_predictor + PieceAnimator - BoardRenderer never derives it.
    """
    pixel_x: float
    pixel_y: float
    sprite_state: str
    frame_index: int
