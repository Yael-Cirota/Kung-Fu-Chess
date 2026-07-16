import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kfchess.api import Position, create_game_session

from controller.factory import build_game_controller

from ui.ui_config import (
    CELL_SIZE_PX, BOARD_IMAGE_PATH, PIECES_DIR, SPRITE_STATE, SPRITE_FRAME_FILENAME,
    RENDERED_BOARD_OUTPUT_PATH, ANIMATION_FRAMES_OUTPUT_DIR,
)
from ui.animation.animation_config_loader import load_animation_configs
from ui.animation.piece_animator import PieceAnimator
from ui.graphics.sprite_resolver import SpriteResolver
from ui.graphics.sprite_loader import SpriteLoader
from ui.graphics.renderer import BoardRenderer
from ui.graphics.img_canvas import ImgCanvas
from ui.app import build_visual_states
from ui.demo_driver import FrameWriter, run_move_and_capture, write_image
from ui.game_loop import run_game_loop

STARTING_BOARD = (
    "bR bN bB bQ bK bB bN bR\n"
    "bP bP bP bP bP bP bP bP\n"
    ".  .  .  .  .  .  .  .\n"
    ".  .  .  .  .  .  .  .\n"
    ".  .  .  .  .  .  .  .\n"
    ".  .  .  .  .  .  .  .\n"
    "wP wP wP wP wP wP wP wP\n"
    "wR wN wB wQ wK wB wN wR"
)


def cell_center_px(row: int, col: int) -> tuple:
    return col * CELL_SIZE_PX + CELL_SIZE_PX // 2, row * CELL_SIZE_PX + CELL_SIZE_PX // 2


def print_board(game_controller) -> None:
    """Text dump of the current board, built from controller.api.BoardSnapshot rather than any kfchess type."""
    snapshot = game_controller.board_snapshot()
    grid = [["." for _ in range(snapshot.cols)] for _ in range(snapshot.rows)]
    for piece_view in snapshot.pieces():
        grid[piece_view.cell.row][piece_view.cell.col] = piece_view.symbol
    for row in grid:
        print(" ".join(row))


def _build_scene(window_title: str):
    """Wires the full render/controller/animation stack, returning the pieces both entry points share."""
    session = create_game_session(STARTING_BOARD)
    game_controller = build_game_controller(session, cell_size_px=CELL_SIZE_PX)
    animator = PieceAnimator(load_animation_configs(PIECES_DIR))

    canvas = ImgCanvas(window_title)
    resolver = SpriteResolver(PIECES_DIR, SPRITE_STATE, SPRITE_FRAME_FILENAME)
    sprite_loader = SpriteLoader(canvas, resolver, sprite_size_px=(CELL_SIZE_PX, CELL_SIZE_PX))
    renderer = BoardRenderer(canvas, sprite_loader, BOARD_IMAGE_PATH, CELL_SIZE_PX)
    return session, game_controller, animator, canvas, renderer


def main() -> None:
    """Real interactive game: a human clicks pieces in the live window to play in real time."""
    _, game_controller, animator, canvas, renderer = _build_scene("Kung-Fu-Chess")

    print("Starting board:")
    print_board(game_controller)
    print("\nClick a piece, then its destination. Press Esc or q to quit.")

    try:
        run_game_loop(canvas, game_controller, animator, renderer, CELL_SIZE_PX)
    finally:
        canvas.close()

    print("\nFinal board:")
    print_board(game_controller)


def run_capture_demo(show_window: bool = True) -> None:
    """Deterministic scripted demo: plays two fixed opening moves and captures every tick to disk."""
    _, game_controller, animator, canvas, renderer = _build_scene("Kung-Fu-Chess - Stage 4 motion demo")
    live_canvas = canvas if show_window else None

    ANIMATION_FRAMES_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frame_writer = FrameWriter(canvas, ANIMATION_FRAMES_OUTPUT_DIR)

    print("Starting board:")
    print_board(game_controller)

    try:
        # White pawn opening move: e2-e4, a 2-cell slide (row 6,col4 -> row 4,col4).
        pawn = game_controller.piece_at(Position(6, 4))
        select_x, select_y = cell_center_px(6, 4)
        dest_x, dest_y = cell_center_px(4, 4)
        game_controller.on_click(select_x, select_y)
        game_controller.on_click(dest_x, dest_y)
        run_move_and_capture(
            game_controller, animator, renderer, frame_writer, pawn.piece_id,
            "pawn slide (2 cells)", CELL_SIZE_PX, live_canvas,
        )

        print("\nBoard after the pawn's opening move:")
        print_board(game_controller)

        # White knight opening move: Nb1-c3 (row 7,col1 -> row 5,col2) - exercises
        # the "jump" animation, since JumpingProfile is what covers a knight move.
        knight = game_controller.piece_at(Position(7, 1))
        select_x, select_y = cell_center_px(7, 1)
        dest_x, dest_y = cell_center_px(5, 2)
        game_controller.on_click(select_x, select_y)
        game_controller.on_click(dest_x, dest_y)
        run_move_and_capture(
            game_controller, animator, renderer, frame_writer, knight.piece_id,
            "knight jump", CELL_SIZE_PX, live_canvas,
        )

        print("\nBoard after the knight's opening move:")
        print_board(game_controller)
    finally:
        canvas.close()

    rendered = renderer.render(
        game_controller.board_snapshot(),
        build_visual_states(
            game_controller, animator,
            engine_ms=game_controller.clock_ms, render_ms=game_controller.clock_ms,
            cell_size_px=CELL_SIZE_PX,
        ),
    )
    write_image(canvas, RENDERED_BOARD_OUTPUT_PATH, rendered)
    print(f"\nRendered board image saved to: {RENDERED_BOARD_OUTPUT_PATH}")
    print(f"Per-tick animation frames saved under: {ANIMATION_FRAMES_OUTPUT_DIR} ({frame_writer.frames_written} frames)")


if __name__ == "__main__":  # pragma: no cover - script entry point, not exercised by imports
    if "--demo" in sys.argv:
        run_capture_demo(show_window="--no-window" not in sys.argv)
    else:
        main()
