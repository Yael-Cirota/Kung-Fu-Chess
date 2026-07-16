"""
Drives the graphics demo: steps the simulation and captures frames.

Splits the concerns the demo used to cram into one function:
  - FrameWriter owns writing rendered frames to disk (the only place the
    demo touches cv2 for output, keeping cv2 out of ui.main).
  - run_move_and_capture owns the settle-loop control flow and delegates
    rendering, disk-writing, live display, and reporting to its collaborators.
"""

import cv2

from ui.app import build_visual_states


class FrameWriter:
    """Sequentially numbered on-disk sink for rendered frames - the one place the demo writes frame images."""

    def __init__(self, output_dir):
        self._output_dir = output_dir
        self.frames_written = 0

    def write(self, rendered) -> None:
        path = self._output_dir / f"{self.frames_written:04d}.png"
        cv2.imwrite(str(path), rendered.img)
        self.frames_written += 1


def write_image(path, rendered) -> None:
    """Writes a single rendered image to `path` (the demo's final still-board export)."""
    cv2.imwrite(str(path), rendered.img)


def run_move_and_capture(
    game_controller, animator, renderer, frame_writer, piece_id, label, cell_size_px,
    window=None, tick_ms=40, reporter=print,
):
    """
    Steps simulated time forward in small ticks - rendering, saving (via
    `frame_writer`), and (if a Window was supplied) live-displaying a frame
    each tick - until the piece identified by `piece_id` (whose move was
    already requested via the controller's clicks) has finished moving and
    settled back into an idle-bound rest animation. Reports pixel position
    and animation state/frame each tick through `reporter` so the glide can
    also be verified without a live window.
    """
    if game_controller.motion_for(piece_id) is None:
        reporter(f"\n[{label}] move was not accepted (no motion recorded for this piece)")
        return

    settle_ticks_remaining = 10  # keep capturing briefly after arrival to show the rest animation
    while True:
        game_controller.advance(tick_ms)
        visual_states = build_visual_states(game_controller, animator, game_controller.clock_ms, cell_size_px)

        visual = visual_states.get(piece_id)
        reporter(
            f"  t={game_controller.clock_ms:5d}ms  pixel=({visual.pixel_x:6.1f},{visual.pixel_y:6.1f})  "
            f"state={visual.sprite_state:<10s} frame={visual.frame_index}"
        )

        rendered = renderer.render(game_controller.board_snapshot(), visual_states)
        frame_writer.write(rendered)

        if window is not None:
            if not window.show(rendered, delay_ms=tick_ms):
                return

        if game_controller.motion_for(piece_id) is None:
            settle_ticks_remaining -= 1
            if settle_ticks_remaining <= 0:
                break
