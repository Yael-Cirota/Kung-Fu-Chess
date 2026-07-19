"""
The real-time interactive game loop - the beating heart that replaced the
scripted fixed-tick demo. Each frame it polls real mouse clicks, feeds them
to the click handler, advances the engine by however much wall time has
actually elapsed, then diffs and draws.

It is written entirely against the Canvas protocol and the kfchess.api
GameSession DTO boundary (never cv2, never a live engine object), so a fake
canvas can drive it headlessly in tests:
scripted clicks come back from drain_clicks(), and show() returning False ends
the loop exactly as an Esc/q keypress does in the live window.

The "two clocks" separation is the whole point of this module:
  - The engine clock (GameSession.clock_ms) is simulated time; it only ever
    advances when we call wait(). We read it *after* advancing and hand it
    to build_visual_states as the basis for motion interpolation, so a piece is
    never drawn further along its path than the engine has actually simulated.
  - The render clock is the wall clock. It paces the frame rate (via the show
    delay) and drives cosmetic sprite-frame selection. It ticks continuously,
    independent of how far the engine stepped on any given frame.
"""

import time

from ui.app import build_visual_states

DEFAULT_FRAMES_PER_SECOND = 60

# A single advance() is never asked to swallow more than this much wall time.
# After a stall (a drag, a breakpoint, a scheduler hiccup) the engine catches
# up in bounded steps on later frames rather than leaping over the collision
# granularity the arbiter resolves motion at in one giant tick.
MAX_ENGINE_STEP_MS = 100

MS_IN_SECOND = 1000


def run_game_loop(
    canvas, session, click_handler, animator, renderer, cell_size_px,
    fps: int = DEFAULT_FRAMES_PER_SECOND, clock=time.monotonic,
) -> None:
    frame_delay_ms = max(1, round(MS_IN_SECOND / fps))
    start = clock()

    running = True
    while running and not session.game_over:
        for x, y in canvas.drain_clicks():
            click_handler.on_click(x, y)

        render_ms = round((clock() - start) * MS_IN_SECOND)
        dt_ms = min(render_ms - session.clock_ms, MAX_ENGINE_STEP_MS)
        if dt_ms > 0:
            session.wait(dt_ms)

        visual_states = build_visual_states(
            session, animator,
            engine_ms=session.clock_ms,
            render_ms=render_ms,
            cell_size_px=cell_size_px,
        )
        rendered = renderer.render(
            session.board_snapshot(), visual_states,
            move_log=session.move_log(), scoreboard=session.scoreboard(),
        )

        running = canvas.show(rendered, delay_ms=frame_delay_ms)
