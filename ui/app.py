from typing import Dict

from kfchess.api import GameSession

from ui.animation import motion_predictor
from ui.board_geometry import BoardGeometry
from ui.animation.piece_animator import PieceAnimator
from ui.graphics.piece_visual_state import PieceVisualState


def build_visual_states(
    session: GameSession, animator: PieceAnimator,
    engine_ms: int, render_ms: int, cell_size_px: int,
) -> Dict[int, PieceVisualState]:
    """
    Per-frame glue: for every piece in the session's board snapshot,
    decide whether it's mid-flight (per GameSession.motion_for) and if
    so where along its path it currently sits, then ask PieceAnimator for
    its current (sprite_state, frame_index). Keyed by piece_id - ui deals
    only in kfchess.api DTOs, never a live engine object. This is the only
    place that combines pixel geometry, motion queries, and animation
    state; none of the three collaborators know about each other.

    The "two clocks" rule lives here, in the split between the two time
    arguments:
      - engine_ms drives *only* motion_predictor.progress, i.e. where along
        the path a piece is drawn. Motion.start_ms/duration_ms are in the
        engine's own clock basis, so position must be read against that same
        clock - otherwise we could interpolate a piece past a collision the
        engine hasn't resolved yet, rendering an outcome that never happened.
        The fraction is smoothstep-eased (ease_in_out) purely for a nicer
        glide; that remap is monotonic with exact endpoints, so it stays on
        the engine clock and never moves a piece past its resolved arrival.
      - render_ms drives *only* the animator, i.e. cosmetic sprite-frame
        selection and the idle/rest state-machine pacing. Those run on the
        wall clock so animations stay smooth and time-based even on frames
        where the engine clock didn't advance.
    The motion *signals* (is_moving/is_jump) stay engine-derived; only the
    clip pacing is wall-based.
    """
    geometry = BoardGeometry(cell_size_px)
    visual_states: Dict[int, PieceVisualState] = {}

    for piece_view in session.board_snapshot().pieces():
        motion = session.motion_for(piece_view.piece_id)
        if motion is not None:
            t = motion_predictor.progress(motion.start_ms, motion.duration_ms, engine_ms)
            pixel_x, pixel_y = motion_predictor.interpolate(
                geometry.cell_to_pixel(motion.from_pos),
                geometry.cell_to_pixel(motion.to_pos),
                motion_predictor.ease_in_out(t),
            )
            sprite_state, frame_index = animator.update(
                piece_view.piece_id, is_moving=True, is_jump=motion.is_jump, now_ms=render_ms
            )
        else:
            pixel_x, pixel_y = geometry.cell_to_pixel(piece_view.cell)
            sprite_state, frame_index = animator.update(
                piece_view.piece_id, is_moving=False, is_jump=False, now_ms=render_ms
            )

        visual_states[piece_view.piece_id] = PieceVisualState(pixel_x, pixel_y, sprite_state, frame_index)

    return visual_states
