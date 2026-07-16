from typing import Dict, Tuple

from controller.api import GameController

from ui.animation import motion_predictor
from ui.animation.piece_animator import PieceAnimator
from ui.graphics.piece_visual_state import PieceVisualState


def cell_top_left_px(cell, cell_size_px: int) -> Tuple[int, int]:
    return cell.col * cell_size_px, cell.row * cell_size_px


def build_visual_states(
    game_controller: GameController, animator: PieceAnimator, now_ms: int, cell_size_px: int,
) -> Dict[int, PieceVisualState]:
    """
    Per-frame glue: for every piece in the controller's board snapshot,
    decide whether it's mid-flight (per GameController.motion_for) and if
    so where along its path it currently sits, then ask PieceAnimator for
    its current (sprite_state, frame_index). Keyed by piece_id - ui never
    touches a kfchess type, even through controller. This is the only
    place that combines pixel geometry, motion queries, and animation
    state; none of the three collaborators know about each other.
    """
    visual_states: Dict[int, PieceVisualState] = {}

    for piece_view in game_controller.board_snapshot().pieces():
        motion = game_controller.motion_for(piece_view.piece_id)
        if motion is not None:
            t = motion_predictor.progress(motion.start_ms, motion.duration_ms, now_ms)
            pixel_x, pixel_y = motion_predictor.interpolate(
                cell_top_left_px(motion.from_pos, cell_size_px),
                cell_top_left_px(motion.to_pos, cell_size_px),
                t,
            )
            sprite_state, frame_index = animator.update(
                piece_view.piece_id, is_moving=True, is_jump=motion.is_jump, now_ms=now_ms
            )
        else:
            pixel_x, pixel_y = cell_top_left_px(piece_view.cell, cell_size_px)
            sprite_state, frame_index = animator.update(
                piece_view.piece_id, is_moving=False, is_jump=False, now_ms=now_ms
            )

        visual_states[piece_view.piece_id] = PieceVisualState(pixel_x, pixel_y, sprite_state, frame_index)

    return visual_states
