"""
The real-time interactive game loop - the beating heart that replaced the
scripted fixed-tick demo. Each frame it polls real mouse clicks, feeds them
to the controller, advances the engine by however much wall time has actually
elapsed, then diffs and draws.

It is written entirely against the Canvas and GameController protocols (never
cv2, never a kfchess type), so a fake canvas can drive it headlessly in tests:
scripted clicks come back from drain_clicks(), and show() returning False ends
the loop exactly as an Esc/q keypress does in the live window.

The "two clocks" separation is the whole point of this module:
  - The engine clock (GameController.clock_ms) is simulated time; it only ever
    advances when we call advance(). We read it *after* advancing and hand it
    to build_visual_states as the basis for motion interpolation, so a piece is
    never drawn further along its path than the engine has actually simulated.
  - The render clock is the wall clock. It paces the frame rate (via the show
    delay) and drives cosmetic sprite-frame selection. It ticks continuously,
    independent of how far the engine stepped on any given frame.
"""

import time

from ui.app import build_visual_states

DEFAULT_FPS = 60

# A single advance() is never asked to swallow more than this much wall time.
# After a stall (a drag, a breakpoint, a scheduler hiccup) the engine catches
# up in bounded steps on later frames rather than leaping over the collision
# granularity the arbiter resolves motion at in one giant tick.
MAX_ENGINE_STEP_MS = 100


def run_game_loop(
    canvas, game_controller, animator, renderer, cell_size_px,
    fps: int = DEFAULT_FPS, clock=time.monotonic,
) -> None:
    frame_delay_ms = max(1, round(1000 / fps))
    start = clock()

    running = True
    while running and not game_controller.is_game_over:
        for x, y in canvas.drain_clicks():
            game_controller.on_click(x, y)

        render_ms = round((clock() - start) * 1000)
        dt_ms = min(render_ms - game_controller.clock_ms, MAX_ENGINE_STEP_MS)
        if dt_ms > 0:
            game_controller.advance(dt_ms)

        visual_states = build_visual_states(
            game_controller, animator,
            engine_ms=game_controller.clock_ms,
            render_ms=render_ms,
            cell_size_px=cell_size_px,
        )
        rendered = renderer.render(
            game_controller.board_snapshot(), visual_states,
            move_log=game_controller.move_log(), scoreboard=game_controller.scoreboard(),
        )

        running = canvas.show(rendered, delay_ms=frame_delay_ms)
